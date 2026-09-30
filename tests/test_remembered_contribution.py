"""A witnessed home-cache deposit can choose among competing food-trip announcements.

The memory is one event: who put food in the shared cache, and on which tick.
It is not a measure of reliability.
"""

import json
from dataclasses import replace

import pytest

from kernel import Engine, deposit
from kernel.outcomes import ProposalOutcome
from kernel.reasons import ACCEPTED
from kernel.state import Effect
from stream.run_file import RunWriter, read_run
from world.config import WorldConfig, genesis
from world.decide import Decision, decide
from world.housing import SETTLE
from world.observe import in_view, observe
from world.overlay import Overlay
from world.process import _births, advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.storage import (
    accepted_food_deposits,
    eligible_announcements,
    prefer_contribution,
    remember_contributions,
    update_food_expectations,
)
from world.viewer import render_html
from world.viewer_index import build_index


def household(**changes):
    cfg = WorldConfig(seed=4, actors=4, stores_on=True, homes_on=True,
                      provisioning_on=True, coordination_on=True,
                      remembered_contribution_on=True, terrain_on=False,
                      water_on=False, warmth_on=False, births_on=False,
                      offers_on=False, social_memory_on=False, renewal_every=1000,
                      food_sources=1, **changes)
    ledger, world = genesis(cfg)
    home = (4, 6)
    elsewhere = (4, 7)
    homes = {"p01": home, "p02": home, "p03": home, "p04": elsewhere}
    caches = {"store-p01": home, "store-p04": elsewhere}
    world = replace(world, homes=homes, positions=dict(homes), shelters=(home, elsewhere),
                    home_caches=caches, hunger={p: 0 for p in homes})
    ledger = replace(ledger, balances={p: 1 for p in homes})
    return cfg, ledger, world, home


def _sources(ledger, **stocks):
    sources = dict(ledger.sources)
    for sid, stock in stocks.items():
        sources[sid] = replace(sources[sid], stock=stock)
    return replace(ledger, sources=sources)


def test_tick_start_sight_not_same_tick_movement_or_another_household():
    """Arriving into view learns nothing. Leaving after the sight still remembers."""
    cfg, ledger, world, home = household(perception_radius=1)
    ledger = _sources(ledger, **{"store-p01": 0, "store-p04": 0})
    ledger = replace(ledger, balances={"p01": 1, "p02": 0, "p03": 4, "p04": 2})
    world = replace(world, positions={"p03": home, "p02": (5, 7), "p01": (6, 7), "p04": (4, 7)},
                    hunger={"p01": 0, "p02": cfg.hungry_at, "p03": 0, "p04": 0})
    step = world_step(Engine(ledger), world, cfg)
    views = step.views
    assert "p03" in [person.actor for person in views["p02"].others]
    assert "p03" not in [person.actor for person in views["p01"].others]
    assert "p03" in [person.actor for person in views["p04"].others]
    assert step.decisions["p03"].kind == "deposit"
    assert step.decisions["p02"].kind == "go" and step.decisions["p02"].step == (6, 7)
    assert step.decisions["p01"].kind == "home" and step.decisions["p01"].step == (5, 7)
    end = step.processed.overlay.positions
    assert not in_view(end["p02"], home, cfg.perception_radius)
    assert in_view(end["p01"], home, cfg.perception_radius)
    memory = step.processed.overlay.contribution_memory
    assert memory["p02"] == ("p03", 1)
    assert "p01" not in memory and "p03" not in memory and "p04" not in memory
    assert step.record.outcomes
    assert any(outcome.accepted and outcome.operation == "deposit" for outcome in step.record.outcomes)
    # The same sight, with the switch off, changes no decision and stores nothing.
    silent = world_step(Engine(ledger), world, replace(cfg, remembered_contribution_on=False))
    assert {actor: choice.canonical() for actor, choice in silent.decisions.items()} == {
        actor: choice.canonical() for actor, choice in step.decisions.items()}
    assert "contribution_memory" not in silent.processed.overlay.canonical()


def test_rejected_zero_and_non_cache_deposits_leave_no_memory():
    cfg, ledger, world, home = household()
    ledger = replace(ledger, balances={"p01": 1, "p02": 1, "p03": 0, "p04": 1})
    views = {actor: observe(actor, ledger, world, cfg) for actor in world.living}
    engine = Engine(ledger)
    rejected = engine.tick([deposit("over", "p03", 0, source="store-p01", amount=1)])
    assert not rejected.outcomes[0].accepted
    assert remember_contributions(world, replace(world, tick=1), rejected, views, cfg) == {}
    engine = Engine(ledger)
    zero = engine.tick([deposit("zero", "p03", 0, source="store-p01", amount=0)])
    assert not zero.outcomes[0].accepted
    assert remember_contributions(world, replace(world, tick=1), zero, views, cfg) == {}
    rich = replace(ledger, balances={"p01": 1, "p02": 1, "p03": 2, "p04": 1})
    views = {actor: observe(actor, rich, world, cfg) for actor in world.living}
    natural = Engine(rich).tick([deposit("patch", "p03", 0, source=cfg.food_source_ids()[0], amount=1)])
    assert natural.outcomes[0].accepted
    assert remember_contributions(world, replace(world, tick=1), natural, views, cfg) == {}
    water = ProposalOutcome("w", "p03", 0, "deposit", ACCEPTED, effects=(
        Effect("actor@water:p03", -1), Effect("source:store-p01", 1)))

    class Record:
        outcomes = (water,)

    assert accepted_food_deposits(Record()) == ()


def test_latest_tick_wins_and_the_lower_actor_id_breaks_a_tie():
    assert prefer_contribution(None, ("p03", 4)) == ("p03", 4)
    assert prefer_contribution(("p01", 3), ("p03", 4)) == ("p03", 4)
    assert prefer_contribution(("p03", 4), ("p01", 4)) == ("p01", 4)
    assert prefer_contribution(("p01", 4), ("p03", 4)) == ("p01", 4)
    cfg, ledger, world, home = household()
    ledger = _sources(ledger, **{"store-p01": 2})
    ledger = replace(ledger, balances={"p01": 4, "p02": 1, "p03": 4, "p04": 1})
    world = replace(world, homes={p: home for p in world.roster},
                    home_caches={"store-p01": home},
                    positions={p: home for p in ("p01", "p02", "p03")} | {"p04": (11, 11)})
    step = world_step(Engine(ledger), world, cfg)
    assert step.decisions["p01"].kind == step.decisions["p03"].kind == "deposit"
    assert step.decisions["p02"].kind == "rest"
    assert step.processed.overlay.contribution_memory["p02"] == ("p01", 1)
    assert "p04" not in step.processed.overlay.contribution_memory
    reversed_views = dict(reversed(list(step.views.items())))
    assert remember_contributions(world, step.processed.overlay, step.record, step.views, cfg) == (
        remember_contributions(world, step.processed.overlay, step.record, reversed_views, cfg))
    # A later deposit by the higher id replaces the tie result.
    later_world = step.processed.overlay
    later_ledger = _sources(step.engine.state, **{"store-p01": 2})
    later_ledger = replace(later_ledger, balances=dict(later_ledger.balances) | {"p01": 1, "p03": 4})
    later = world_step(Engine(later_ledger), later_world, cfg)
    assert later.decisions["p03"].kind == "deposit"
    assert later.processed.overlay.contribution_memory["p02"] == ("p03", later.processed.overlay.tick)
    # Seeing the stock afterwards still does not name a contributor.
    absent = replace(later.processed.overlay, positions=dict(later.processed.overlay.positions, p04=home))
    seen = observe("p04", later.engine.state, absent, cfg)
    assert seen.home_store_food is not None and seen.contribution_memory is None
    quiet = world_step(later.engine, absent, cfg)
    assert "p04" not in quiet.processed.overlay.contribution_memory


def test_competing_announcements_follow_the_witness_and_drop_without_that_memory():
    cfg, ledger, world, home = household()
    world = replace(world, homes={p: home for p in ("p01", "p02", "p03")} | {"p04": (0, 0)},
                    positions={p: home for p in ("p01", "p02", "p03")} | {"p04": (0, 0)},
                    home_caches={"store-p01": home, "store-p04": (0, 0)})
    ledger = _sources(replace(ledger, balances={"p01": 1, "p02": 1, "p03": 4, "p04": 1}), **{"store-p01": 2})
    world = replace(world, positions={"p03": home, "p02": home, "p01": (4, 10), "p04": (0, 0)})
    witnessed = world_step(Engine(ledger), world, cfg)
    assert witnessed.decisions["p03"].kind == "deposit"
    assert "p03" not in [person.actor for person in witnessed.views["p01"].others]
    assert witnessed.processed.overlay.positions["p01"] == (4, 9)
    assert not in_view((4, 10), home, cfg.perception_radius)
    assert in_view((4, 9), home, cfg.perception_radius)
    memory = witnessed.processed.overlay.contribution_memory
    assert memory == {"p02": ("p03", 1)}
    # Reachable announcement state: two housemates at the low cache, the witness one step away.
    start = witnessed.processed.overlay
    announce_world = replace(start, positions={"p01": home, "p03": home, "p02": (home[0], home[1] + 1), "p04": (0, 0)},
                             hunger={p: 0 for p in start.hunger}, provision_trips={})
    announce_ledger = _sources(replace(witnessed.engine.state, balances={p: 1 for p in start.roster}),
                               **{"store-p01": 0})
    heard = world_step(Engine(announce_ledger), announce_world, cfg)
    speakers = eligible_announcements(announce_world, heard.processed.overlay, heard.decisions)["p02"]
    assert speakers[0] == "p01" and "p03" in speakers and speakers[0] != "p03"
    assert heard.processed.overlay.food_expected["p02"] == ("p03", heard.processed.overlay.tick)
    choice = heard.processed.overlay.contribution_selection["p02"]
    assert choice[0] == "p03" and choice[2] == "p03" and choice[3] == 1
    waiting = world_step(heard.engine, heard.processed.overlay, cfg)
    assert waiting.decisions["p02"].waiting_for_food == "p03"
    assert waiting.decisions["p02"].step is None
    assert waiting.decisions["p02"].contribution_changed == 1
    assert waiting.decisions["p02"].reason == (
        "Expecting p03's food trip; saw p03 contribute food at world tick 1")
    # The same announcement state without only p02's memory keeps the old tie-break.
    forgotten = replace(announce_world, contribution_memory={})
    plain = world_step(Engine(announce_ledger), forgotten, cfg)
    assert plain.processed.overlay.food_expected["p02"] == ("p01", plain.processed.overlay.tick)
    assert "p02" not in plain.processed.overlay.contribution_selection
    plain_wait = world_step(plain.engine, plain.processed.overlay, cfg)
    assert plain_wait.decisions["p02"].waiting_for_food == "p01"
    assert plain_wait.decisions["p02"].step is None
    assert plain_wait.decisions["p02"].kind == waiting.decisions["p02"].kind
    assert "contribution_tick" not in plain_wait.decisions["p02"].canonical()
    disabled = world_step(Engine(announce_ledger), announce_world, replace(cfg, remembered_contribution_on=False))
    assert disabled.processed.overlay.food_expected["p02"][0] == "p01"
    assert "contribution_memory" not in disabled.processed.overlay.canonical()
    assert {actor: choice.canonical() for actor, choice in disabled.decisions.items()} == {
        actor: choice.canonical() for actor, choice in plain.decisions.items()}
    # One speaker, and a memory of someone who is not speaking, do not rewrite the fallback.
    only = replace(announce_world, positions=dict(announce_world.positions, p01=(11, 11)))
    single = world_step(Engine(announce_ledger), only, cfg)
    assert single.processed.overlay.food_expected["p02"][0] == "p03"
    assert "p02" not in single.processed.overlay.contribution_selection
    irrelevant = replace(announce_world, contribution_memory={"p02": ("p04", 1)})
    ignored = world_step(Engine(announce_ledger), irrelevant, cfg)
    assert ignored.processed.overlay.food_expected["p02"][0] == "p01"
    assert "p02" not in ignored.processed.overlay.contribution_selection
    # Memory of the person the tie-break already picks is recorded and does not claim influence.
    same = replace(announce_world, contribution_memory={"p02": ("p01", 1)})
    unchanged = world_step(Engine(announce_ledger), same, cfg)
    recorded = unchanged.processed.overlay.contribution_selection["p02"]
    assert recorded[2] == "p01" and recorded[3] == 0
    unchanged_wait = world_step(unchanged.engine, unchanged.processed.overlay, cfg)
    assert "did not change the selected speaker" in unchanged_wait.decisions["p02"].reason
    assert "saw p01 contribute" not in unchanged_wait.decisions["p02"].reason
    # Shuffled decision order cannot change the result.
    low = Decision("p01", "go", "out", ("go",), announced_to=("p02",))
    high = Decision("p03", "go", "out", ("go",), announced_to=("p02",))
    current = replace(announce_world, tick=announce_world.tick + 1)
    forward = update_food_expectations(announce_world, current, {"p01": low, "p03": high}, {},
                                       announce_world.contribution_memory, {})
    backward = update_food_expectations(announce_world, current, {"p03": high, "p01": low}, {},
                                        announce_world.contribution_memory, {})
    assert forward == backward


def test_birth_starts_empty_and_moving_home_clears_only_that_observer():
    cfg, ledger, world, home = household()
    world = replace(world, tick=1, contribution_memory={"p02": ("p03", 1), "p03": ("p02", 1)},
                    contribution_selection={"p02": ("p03", 1, "p03", 1, 1)},
                    held={p: 0 for p in world.roster}, built={p: 0 for p in world.roster})
    grown, _, born = _births(world, replace(ledger, tick=1), replace(cfg, births_on=True, together_ticks=1))
    assert born
    assert grown.contribution_memory["p02"] == ("p03", 1)
    assert born[0] not in grown.contribution_memory
    moved = replace(world, homes=dict(world.homes, p02=(0, 0)), tick=2)
    kept = remember_contributions(world, moved, Engine(replace(ledger, tick=1)).tick([]), {}, cfg)
    assert "p02" not in kept and kept["p03"] == ("p02", 1)
    # A real home settlement drops the arriving adult's memory and keeps the other's.
    cfg, ledger, overlay, home = household()
    origin = (3, 2)
    overlay = replace(overlay, tick=1, parent={"p02": "p01"}, age={p: cfg.adult_at for p in overlay.roster},
                      contribution_memory={"p02": ("p03", 1), "p03": ("p01", 1)},
                      homes={"p01": home, "p02": origin, "p03": (5, 6), "p04": (4, 7)},
                      positions={"p01": home, "p02": home, "p03": (5, 6), "p04": (4, 7)},
                      shelters=(home, origin), home_settled={},
                      home_caches={"store-p01": home, "store-p02": origin})
    ledger = replace(ledger, tick=1)
    engine = Engine(ledger)
    record = engine.tick([])
    choice = Decision("p02", SETTLE, "arrived", (SETTLE,), home_site=home)
    settled = advance(overlay, {"p02": choice}, record, engine.state, cfg)
    assert settled.overlay.homes["p02"] == home
    assert "p02" not in settled.overlay.contribution_memory
    assert settled.overlay.contribution_memory["p03"] == ("p01", 1)


def test_headers_round_trip_and_old_overlays_still_load():
    cfg, ledger, world, _home = household()
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    off = replace(cfg, remembered_contribution_on=False)
    assert "remembered_contribution" not in off.describe()
    assert WorldConfig.from_describe(off.describe()) == off
    assert genesis(cfg)[1].canonical() == genesis(off)[1].canonical()
    assert run_id_for(cfg, 20) != run_id_for(off, 20)
    args = build_parser().parse_args(["--seed", "4", "--stores", "on", "--provisioning", "on",
                                      "--coordination", "on", "--homes", "on",
                                      "--remembered-contribution", "on", "--water", "off"])
    assert config_from(args).remembered_contribution_on
    with pytest.raises(ValueError):
        WorldConfig(seed=1, remembered_contribution_on=True)
    with pytest.raises(ValueError):
        replace(cfg, remembered_contribution_on=1)
    bad = cfg.describe()
    bad["remembered_contribution"] = "sometimes"
    with pytest.raises(ValueError):
        WorldConfig.from_describe(bad)
    remembered = replace(world, tick=2, contribution_memory={"p02": ["p03", 1]},
                         contribution_selection={"p02": ["p03", 1, "p03", 1, 2]})
    assert Overlay.from_canonical(remembered.canonical()).canonical() == remembered.canonical()
    old = world.canonical()
    assert "contribution_memory" not in old
    loaded = Overlay.from_canonical(old)
    assert loaded.contribution_memory == {} and loaded.contribution_selection == {}
    with pytest.raises(TypeError):
        loaded.contribution_memory["p02"] = ("p03", 1)
    for entry in (("p02",), ("p03", True), ("ghost", 1), ("p02", 1)):
        with pytest.raises(ValueError):
            replace(remembered, contribution_memory={"p02": entry})


def _write(path, cfg, ledger, world, steps):
    with RunWriter(path, run_id=path.stem, genesis=ledger, scenario=cfg.describe(),
                   world=world.canonical(), horizon=len(steps)) as writer:
        for step in steps:
            writer.record(step.record, step.committed, inputs=step.proposals, **step.line_fields())


def test_saved_scene_replays_from_its_continuation_and_the_viewer_uses_the_record(tmp_path):
    cfg, ledger, world, home = household()
    world = replace(world, positions={"p03": home, "p02": home, "p01": (4, 10), "p04": (0, 0)},
                    homes={p: home for p in ("p01", "p02", "p03")} | {"p04": (0, 0)})
    ledger = _sources(replace(ledger, balances={"p01": 1, "p02": 1, "p03": 4, "p04": 1}), **{"store-p01": 2})
    witnessed = world_step(Engine(ledger), world, cfg)
    witness_path = tmp_path / "witness.jsonl"
    _write(witness_path, cfg, ledger, world, [witnessed])
    witness_run = read_run(witness_path)
    assert witness_run.complete
    assert "contribution_witnessed" in {event["kind"] for event in build_index(witness_run)["events"]}
    announce_world = replace(witnessed.processed.overlay,
                             positions={"p01": home, "p03": home, "p02": (home[0], home[1] + 1), "p04": (0, 0)},
                             hunger={p: 0 for p in witnessed.processed.overlay.hunger}, provision_trips={})
    announce_ledger = _sources(replace(witnessed.engine.state, balances={p: 1 for p in announce_world.roster}),
                               **{"store-p01": 0})
    steps = []
    engine, overlay = Engine(announce_ledger), announce_world
    for _ in range(2):
        step = world_step(engine, overlay, cfg)
        steps.append(step)
        engine, overlay = step.engine, step.processed.overlay
    path = tmp_path / "scene.jsonl"
    _write(path, cfg, announce_ledger, announce_world, steps)
    run = read_run(path)
    assert run.complete and run.ticks[0]["world"].get("contribution_memory")
    repeat = []
    engine, overlay = Engine(announce_ledger), announce_world
    for _ in range(2):
        step = world_step(engine, overlay, cfg)
        repeat.append(step.processed.overlay.digest())
        engine, overlay = step.engine, step.processed.overlay
    assert repeat == [step.processed.overlay.digest() for step in steps]
    active = next(tick["tick"] for tick in run.ticks if tick["world"].get("contribution_selection"))
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines)
               if json.loads(line).get("kind") == "tick" and json.loads(line).get("tick") == active)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
    events = build_index(run)["events"]
    assert "contribution_choice" in {event["kind"] for event in events}
    page = render_html(run)
    assert "Expecting p03's food trip; saw p03 contribute food at world tick 1" in page
    assert "Remembered contribution" in page
    assert "did not change the selected speaker" not in steps[1].decisions["p02"].reason
    short = WorldConfig(seed=2, stores_on=True, homes_on=True, provisioning_on=True, coordination_on=True,
                        remembered_contribution_on=True)
    short_path = tmp_path / "genesis.jsonl"
    run_world(short, 40, short_path)
    assert replay_world(short_path).identical
