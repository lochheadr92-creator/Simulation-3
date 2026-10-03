"""A low cache causes a real outing; only settled food can come back."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, fishing_sites, genesis
from world.decide import decide
from world.observe import SeenPerson, observe
from world.overlay import Overlay
from world.process import _births
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index
from world.storage import update_provisioning


def household(**changes):
    cfg = WorldConfig(seed=7, actors=2, stores_on=True, homes_on=True,
                      provisioning_on=True, terrain_on=False, water_on=False,
                      warmth_on=False, births_on=False, offers_on=False,
                      renewal_every=1000, **changes)
    ledger, world = genesis(cfg)
    source = cfg.food_positions()[0]
    home = (source[0] - 2, source[1])
    homes = {"p01": home, "p02": (cfg.width-1, cfg.height-1)}
    ledger = replace(ledger, balances={"p01": 1, "p02": 0})
    world = replace(world, homes=homes, positions=homes, hunger={p: 0 for p in homes},
                    shelters=(home,), home_caches={"store-p01": home})
    return cfg, ledger, world


def test_home_to_patch_to_cache_to_another_person():
    cfg, ledger, world = household()
    initial = ledger.totals()
    engine = Engine(ledger)
    kinds = []
    for _ in range(10):
        step = world_step(engine, world, cfg)
        choice = step.decisions["p01"]
        kinds.append(choice.kind)
        assert step.processed.ledger.totals() == initial
        engine, world = step.engine, step.processed.overlay
        if choice.kind == "deposit":
            break
    assert kinds == ["go", "go", "claim", "home", "home", "deposit"]
    assert engine.state.sources["store-p01"].stock == cfg.claim_amount
    assert engine.state.balances["p01"] == 1
    assert not world.provision_trips
    world = replace(world, positions=dict(world.positions, p02=world.homes["p01"]),
                    hunger=dict(world.hunger, p02=cfg.hungry_at))
    take = world_step(engine, world, cfg)
    assert take.decisions["p02"].kind == "claim"
    assert take.decisions["p02"].target == "store-p01"
    assert take.engine.state.sources["store-p01"].stock == 0
    eat = world_step(take.engine, take.processed.overlay, cfg)
    assert eat.decisions["p02"].kind == "eat"
    assert eat.engine.state.totals() == initial


def test_only_idle_adult_residents_start_and_ordinary_deposits_come_first():
    cfg, ledger, world = household()
    view = observe("p01", ledger, world, cfg)
    assert decide(view, cfg).provisioning == "gather"
    for changed in (replace(view, age=0), replace(view, home_store_food=None),
                    replace(view, home_store_food=2), replace(view, home_built=False)):
        assert decide(changed, cfg).provisioning is None
    assert decide(replace(view, food=3), cfg).kind == "deposit"
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    helping = replace(view, dependents=frozenset({"p02"}),
                      others=(SeenPerson("p02", view.home, 0),))
    assert decide(helping, cfg).kind == "offer"
    water = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=water.thirsty_at, water=1,
                          water_source=view.home, water_stock=0), water).kind == "drink"
    warmth = replace(cfg, warmth_on=True)
    assert decide(replace(view, cold=warmth.cold_at), warmth).kind == "warm"
    warming = decide(replace(view, cold=1), warmth)
    assert warming.kind == "warm" and warming.provisioning is None
    assert decide(replace(view, cold=0), warmth).provisioning == "gather"


def test_outing_remembers_why_it_left_without_seeing_hidden_cache_changes():
    cfg, ledger, world = household(perception_radius=1)
    first = world_step(Engine(ledger), world, cfg)
    first = world_step(first.engine, first.processed.overlay, cfg)
    world, ledger = first.processed.overlay, first.processed.ledger
    assert world.provision_trips["p01"] == "gather"
    view = observe("p01", ledger, world, cfg)
    assert view.home_store_food is None
    # The cache is not observed while away; a refill does not remotely end the trip.
    refilled = replace(ledger, sources={s: replace(v, stock=6) if s == "store-p01" else v
                                       for s, v in ledger.sources.items()})
    assert observe("p01", refilled, world, cfg) == view
    interrupted = replace(world, hunger=dict(world.hunger, p01=cfg.hungry_at))
    eat = world_step(first.engine, interrupted, cfg)
    assert eat.decisions["p01"].kind == "eat"
    assert eat.processed.overlay.provision_trips["p01"] == "gather"
    assert decide(observe("p01", eat.engine.state, eat.processed.overlay, cfg), cfg).provisioning == "gather"


def test_natural_sources_only_and_empty_memory_guides_provisioning():
    cfg, ledger, world = household(source_memory_on=True, perception_radius=1)
    ledger = replace(ledger, sources={s: replace(v, stock=1) if s == "store-p01" else v
                                     for s, v in ledger.sources.items()})
    world = replace(world, empty_sources={"p01": (("food", 0),)})
    view = observe("p01", ledger, world, cfg)
    assert view.source_id == "store-p01"  # a meal for oneself would use the cache
    choice = decide(view, cfg)
    assert choice.target == "food2" and choice.provisioning == "gather"
    assert "remembered empty" in choice.reason
    assert view.provision_source[2] is None


def test_fishing_cast_catch_and_return_and_last_fish_contention():
    cfg, ledger, world = household(fishing_on=True, source_memory_on=True)
    bank = fishing_sites(cfg)[0][1]
    world = replace(world, positions={p: bank for p in world.roster},
                    provision_trips={p: "gather" for p in world.roster})
    ledger = replace(ledger, sources={s: replace(v, stock=1 if s == "fish" else 0)
                                     for s, v in ledger.sources.items()})
    cast = world_step(Engine(ledger), world, cfg)
    assert all(d.kind == "fish" and d.provisioning == "gather" for d in cast.decisions.values())
    catch = world_step(cast.engine, cast.processed.overlay, cfg)
    winners = [o.actor for o in catch.record.outcomes if o.accepted]
    assert len(winners) == 1
    assert catch.processed.overlay.provision_trips[winners[0]] == "return"
    loser = next(p for p in world.roster if p not in winners)
    assert catch.processed.overlay.provision_trips[loser] == "gather"
    assert catch.engine.state.sources["fish"].stock == 0
    # Fishing renewal has not occurred yet; the initial food is conserved.
    assert catch.engine.state.totals() == ledger.totals()
    returning = decide(observe(winners[0], catch.engine.state, catch.processed.overlay, cfg), cfg)
    assert returning.kind == "home" and returning.provisioning == "return"


def test_returning_does_not_gather_again_after_giving_or_eating_the_catch():
    cfg, ledger, world = household()
    world = replace(world, positions=dict(world.positions, p01=cfg.food_positions()[0]),
                    provision_trips={"p01": "return"})
    ledger = replace(ledger, balances={"p01": 0, "p02": 0})
    choice = decide(observe("p01", ledger, world, cfg), cfg)
    assert choice.kind == "home" and choice.provisioning == "return"
    step = world_step(Engine(ledger), world, cfg)
    arrived = world_step(step.engine, step.processed.overlay, cfg)
    assert "p01" not in arrived.processed.overlay.provision_trips


def test_outing_survives_births_but_not_death_and_is_immutable():
    cfg, ledger, world = household()
    world = replace(world, tick=1, provision_trips={"p01": "gather"},
                    held={p: 0 for p in world.roster}, built={p: cfg.build_ticks for p in world.roster},
                    positions={"p01": (0, 0), "p02": (1, 0)},
                    homes={"p01": (0, 0), "p02": (1, 0)}, shelters=((0, 0), (1, 0)))
    cfg = replace(cfg, births_on=True, together_ticks=1)
    grown, _, births = _births(world, replace(ledger, tick=1), cfg)
    assert births and grown.provision_trips == {"p01": "gather"}
    assert Overlay.from_canonical(grown.canonical()).canonical() == grown.canonical()
    with pytest.raises(TypeError):
        grown.provision_trips["p01"] = "return"
    for trips in ({"ghost": "gather"}, {"p01": "unknown"}):
        with pytest.raises(ValueError):
            replace(world, provision_trips=trips)
    dying = replace(world, hunger=dict(world.hunger, p01=cfg.death_at - 1))
    empty = replace(ledger, tick=1, balances={p: 0 for p in world.roster},
                    sources={s: replace(v, stock=0) for s, v in ledger.sources.items()})
    dead = world_step(Engine(empty), dying, cfg)
    assert not dead.processed.overlay.alive("p01")
    assert "p01" not in dead.processed.overlay.provision_trips


def test_optional_switch_headers_and_no_default_change():
    cfg, _, _ = household()
    old = replace(cfg, provisioning_on=False)
    assert "provisioning" not in old.describe()
    assert WorldConfig.from_describe(old.describe()) == old
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    assert genesis(old) == genesis(cfg)
    assert run_id_for(old, 100) != run_id_for(cfg, 100)
    args = build_parser().parse_args(["--seed", "7", "--stores", "on", "--provisioning", "on"])
    assert config_from(args).provisioning_on
    with pytest.raises(ValueError):
        replace(cfg, stores_on=False)
    with pytest.raises(ValueError):
        replace(cfg, provisioning_on=1)


def test_shared_home_residents_notice_the_same_cache_and_moves_end_old_outings():
    cfg, ledger, world = household()
    home = world.homes["p01"]
    world = replace(world, homes={p: home for p in world.roster}, positions={p: home for p in world.roster})
    views = [observe(p, ledger, world, cfg) for p in world.roster]
    assert all(v.home_store_id == "store-p01" and v.home_store_food == 0 for v in views)
    assert all(decide(v, cfg).provisioning == "gather" for v in views)
    step = world_step(Engine(ledger), world, cfg)
    previous = step.processed.overlay
    moved = replace(previous, homes=dict(previous.homes, p01=(0, 0)))
    trips = update_provisioning(previous, moved, {}, Engine(step.engine.state).tick([]))
    assert "p01" not in trips and trips["p02"] == "gather"


def test_scored_choices_record_the_selected_gathering_action():
    cfg, ledger, world = household(scoring_on=True)
    choice = decide(observe("p01", ledger, world, cfg), cfg)
    assert choice.kind in choice.candidates
    assert max(choice.scores, key=lambda item: item[1])[0] == choice.kind


@pytest.mark.long_run
def test_saved_outing_replays_recovers_and_is_visible(tmp_path):
    cfg = WorldConfig(seed=7, stores_on=True, homes_on=True, provisioning_on=True,
                      fishing_on=True, source_memory_on=True, regrowth_on=True,
                      seasons_on=True, source_stock=8, source_cap=16, renewal_amount=3)
    path = tmp_path / "provisioning.jsonl"
    result = run_world(cfg, 220, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    events = build_index(run)["events"]
    assert any(e["kind"] == "provision_start" for e in events)
    assert any(e["kind"] == "provision_home" for e in events)
    assert "Food for home" in render_html(run)
    lines = path.read_bytes().splitlines(keepends=True)
    for phase in ("gather", "return"):
        active = next(t["tick"] for t in run.ticks if phase in t["world"].get("provision_trips", {}).values())
        end = next(i for i, line in enumerate(lines) if json.loads(line).get("kind") == "tick"
                   and json.loads(line).get("tick") == active)
        cut, restored = tmp_path / f"cut-{phase}.jsonl", tmp_path / f"restored-{phase}.jsonl"
        cut.write_bytes(b"".join(lines[:end+1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks
        assert replay_world(restored).identical
    assert run_world(cfg, 220, tmp_path / "again.jsonl").trail_digest == result.trail_digest
