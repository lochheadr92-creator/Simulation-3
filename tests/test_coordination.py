"""Housemates hear a food-trip announcement, act on it, and stop waiting."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import RunWriter, read_run
from world.config import WorldConfig, genesis
from world.decide import decide
from world.observe import SeenPerson, observe
from world.overlay import Overlay
from world.process import _births
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.storage import FOOD_EXPECT_TICKS, food_expectation, update_food_expectations
from world.viewer import render_html
from world.viewer_index import build_index


def house():
    cfg = WorldConfig(seed=7, actors=2, stores_on=True, homes_on=True,
                      provisioning_on=True, coordination_on=True, terrain_on=False,
                      water_on=False, births_on=False, offers_on=False,
                      renewal_every=1000)
    ledger, world = genesis(cfg)
    source = cfg.food_positions()[0]
    home = (source[0]-2, source[1])
    homes = {p: home for p in world.roster}
    ledger = replace(ledger, balances={p: 1 for p in world.roster})
    world = replace(world, homes=homes, positions=homes, shelters=(home,),
                    home_caches={"store-p01": home}, hunger={p: 0 for p in homes},
                    cold={"p01": 0, "p02": 3})
    return cfg, ledger, world


def test_announcement_costs_no_action_and_listener_waits_then_uses_delivery():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    silent = world_step(Engine(ledger), world, replace(cfg, coordination_on=False))
    assert first.decisions["p01"].kind == silent.decisions["p01"].kind == "go"
    assert first.decisions["p01"].step == silent.decisions["p01"].step
    assert first.decisions["p01"].announced_to == ("p02",)
    assert first.decisions["p02"].kind == "warm"  # still making this tick's own choice
    assert first.processed.overlay.food_expected == {"p02": ("p01", 1)}
    second = world_step(first.engine, first.processed.overlay, cfg)
    assert second.decisions["p02"].kind == "rest"
    assert second.decisions["p02"].waiting_for_food == "p01"
    assert not second.decisions["p01"].announced_to  # no repeated broadcast during the walk
    assert decide(observe("p02", first.engine.state, first.processed.overlay,
                          replace(cfg, coordination_on=False)), replace(cfg, coordination_on=False)).kind == "go"
    step = second
    for _ in range(12):
        step = world_step(step.engine, step.processed.overlay, cfg)
        assert step.engine.state.totals() == ledger.totals()
        if step.engine.state.sources["store-p01"].stock:
            break
    assert step.engine.state.sources["store-p01"].stock > 0
    hungry = replace(step.processed.overlay, hunger=dict(step.processed.overlay.hunger, p02=cfg.hungry_at))
    own_meal = world_step(step.engine, hungry, cfg)
    assert own_meal.decisions["p02"].kind == "eat"
    hungry_again = replace(own_meal.processed.overlay, hunger=dict(own_meal.processed.overlay.hunger, p02=cfg.hungry_at))
    take = world_step(own_meal.engine, hungry_again, cfg)
    assert take.decisions["p02"].kind == "claim" and take.decisions["p02"].target == "store-p01"
    eat = world_step(take.engine, take.processed.overlay, cfg)
    assert eat.decisions["p02"].kind == "eat"
    assert eat.engine.state.totals() == ledger.totals()


def test_only_local_housemates_hear_and_simultaneous_departures_are_not_assigned():
    cfg, ledger, world = house()
    remote = replace(world, positions=dict(world.positions, p02=(11, 11)))
    assert not world_step(Engine(ledger), remote, cfg).decisions["p01"].announced_to
    neighbour = replace(world, homes=dict(world.homes, p02=(11, 11)))
    assert not world_step(Engine(ledger), neighbour, cfg).decisions["p01"].announced_to
    together = replace(world, cold={p: 0 for p in world.roster})
    both = world_step(Engine(ledger), together, cfg)
    assert all(d.kind == "go" and d.announced_to for d in both.decisions.values())
    after = world_step(both.engine, both.processed.overlay, cfg)
    assert all(d.kind == "go" and not d.waiting_for_food for d in after.decisions.values())


def test_needs_help_and_warming_keep_priority_over_a_remembered_announcement():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    view = observe("p02", first.engine.state, first.processed.overlay, cfg)
    assert decide(view, cfg).waiting_for_food
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    assert decide(replace(view, cold=1), cfg).kind == "warm"
    water_cfg = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=cfg.thirsty_at, water=1,
                          water_source=view.home, water_stock=0), water_cfg).kind == "drink"
    help_view = replace(view, dependents=frozenset({"p01"}),
                        others=(SeenPerson("p01", view.home, 0),))
    assert decide(help_view, cfg).kind == "offer"
    # A new food trip for one's own hunger is not suppressed either.
    hungry = replace(view, food=0, hunger=cfg.hungry_at)
    assert decide(hungry, cfg).kind == "go"


def test_expiry_lets_listener_leave_when_the_supplier_never_returns():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    world = replace(first.processed.overlay, positions=dict(first.processed.overlay.positions, p01=(11, 11)))
    last_tick = 1 + FOOD_EXPECT_TICKS - 1
    before = observe("p02", replace(first.engine.state, tick=last_tick), replace(world, tick=last_tick), cfg)
    assert decide(before, cfg).waiting_for_food == "p01"
    deadline = last_tick+1
    expired = observe("p02", replace(first.engine.state, tick=deadline), replace(world, tick=deadline), cfg)
    assert expired.food_expected is None and expired.food_expectation_end == "the announcement expired"
    assert decide(expired, cfg).provisioning == "gather"


def test_hidden_death_refill_and_trip_progress_do_not_supply_remote_knowledge():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    away = replace(first.processed.overlay, positions={"p01": (11, 11), "p02": (0, 0)})
    base = observe("p02", first.engine.state, away, cfg)
    changed = replace(away, died_at={"p01": 1}, provision_trips={})
    refilled = replace(first.engine.state, sources={s: replace(v, stock=6) if s == "store-p01" else v
                                                  for s,v in first.engine.state.sources.items()})
    assert observe("p02", refilled, changed, cfg) == base
    assert base.food_expected == ("p01", 1)


def test_visible_return_even_empty_or_stocked_cache_ends_expectation():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    returned = replace(first.processed.overlay, positions=world.positions)
    seen = observe("p02", first.engine.state, returned, cfg)
    assert seen.food_expected is None and seen.food_expectation_end == "the housemate returned without spare food"
    assert decide(seen, cfg).provisioning == "gather"
    loaded = replace(first.engine.state, balances=dict(first.engine.state.balances,p01=3))
    still_waiting = observe("p02", loaded, returned, cfg)
    assert still_waiting.food_expected == ("p01",1)
    assert decide(still_waiting,cfg).waiting_for_food == "p01"
    stock = replace(first.engine.state, sources={s: replace(v, stock=2) if s == "store-p01" else v
                                               for s,v in first.engine.state.sources.items()})
    seen = observe("p02", stock, first.processed.overlay, cfg)
    assert seen.food_expected is None and seen.food_expectation_end == "the home cache is stocked"


def test_witnessed_death_ends_wait_after_actual_death_and_starts_an_outing():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    # Controlled setup: the announced traveller is now empty-handed and one
    # tick from starvation. Death still comes through ordinary world processing.
    endangered = replace(first.processed.overlay,
                         hunger=dict(first.processed.overlay.hunger, p01=cfg.death_at - 1))
    empty = replace(first.engine.state, balances=dict(first.engine.state.balances, p01=0))
    second = world_step(Engine(empty), endangered, cfg)
    assert second.decisions['p02'].waiting_for_food == 'p01'
    assert second.processed.overlay.died_at == {'p01': 2}
    assert second.processed.overlay.food_expected == {'p02': ('p01', 1)}
    assert second.processed.ledger.totals() == empty.totals()

    third = world_step(second.engine, second.processed.overlay, cfg)
    seen = third.views['p02']
    assert seen.witnessed_deaths == ('p01',)
    assert seen.compact()['witnessed_deaths'] == ['p01']
    assert seen.food_expected is None
    assert seen.food_expectation_end == "witnessed the housemate's death"
    assert third.decisions['p02'].provisioning == 'gather'
    assert not third.decisions['p02'].waiting_for_food
    uninformed = replace(seen, food_expected=('p01', 1), food_expectation_end=None,
                         witnessed_deaths=())
    assert decide(uninformed, cfg).waiting_for_food == 'p01'
    assert not third.processed.overlay.food_expected
    assert second.processed.overlay.food_expected == {'p02': ('p01', 1)}  # immutable input
    restored = Overlay.from_canonical(third.processed.overlay.canonical())
    fourth = world_step(third.engine, restored, cfg)
    assert not fourth.views['p02'].witnessed_deaths
    assert not fourth.processed.overlay.food_expected

    # Learning what happened changes the expectation, not need priority.
    assert decide(replace(seen, hunger=cfg.hungry_at), cfg).kind == 'eat'
    assert decide(replace(seen, cold=1), cfg).kind == 'warm'
    water_cfg = replace(cfg, water_on=True)
    assert decide(replace(seen, thirst=cfg.thirsty_at, water=1,
                          water_source=seen.home, water_stock=0), water_cfg).kind == 'drink'


@pytest.mark.parametrize('offset, radius, when, witnessed', [
    ((0, 0), 0, 2, True), ((1, 1), 1, 2, True), ((2, 0), 1, 2, False),
    ((1, 0), 0, 2, False), ((0, 0), 1, 1, False),
])
def test_death_information_is_local_and_only_at_the_completed_boundary(offset, radius, when, witnessed):
    cfg, ledger, world = house()
    cfg = replace(cfg, perception_radius=radius)
    home = world.homes['p02']
    world = replace(world, tick=2, cold={'p01': 0, 'p02': 0},
                    positions=dict(world.positions, p01=(home[0]+offset[0], home[1]+offset[1])),
                    died_at={'p01': when}, food_expected={'p02': ('p01', 1)})
    view = observe('p02', replace(ledger, tick=2), world, cfg)
    assert bool(view.witnessed_deaths) is witnessed
    assert (view.food_expected is None) is witnessed
    assert (decide(view, cfg).provisioning == 'gather') is witnessed
    without_expectation = observe('p02', replace(ledger, tick=2), replace(world, food_expected={}), cfg)
    assert not without_expectation.witnessed_deaths  # no general death-knowledge system
    off = observe('p02', replace(ledger, tick=2), world, replace(cfg, coordination_on=False))
    assert 'witnessed_deaths' not in off.compact()


def test_witnessing_someone_else_does_not_cancel_the_speakers_promise():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    view = observe('p02', first.engine.state, first.processed.overlay, cfg)
    assert food_expectation(view.food_expected, view.tick, view.home, view.others,
                            view.home_store_food, ('someone-else',)) == (('p01', 1), None)


def save_witnessed_death_scene(path):
    """Controlled scene, not generated genesis or ordinary-world frequency evidence.

    Two adults share a built home. A short hunger margin and empty patches
    expose the whole sequence in nine ticks. No state is edited after start.
    """
    cfg, ledger, world = house()
    cfg = replace(cfg, satiation=1, emergency_at=26, death_at=27)
    world = replace(world, hunger={'p01': 24, 'p02': 0})
    ledger = replace(ledger, sources={s: replace(v, stock=0) for s, v in ledger.sources.items()})
    engine = Engine(ledger)
    with RunWriter(path, run_id='controlled-witnessed-death', genesis=ledger,
                   scenario=cfg.describe(), world=world.canonical(), horizon=9) as writer:
        for _ in range(9):
            step = world_step(engine, world, cfg)
            writer.record(step.record, step.committed, inputs=step.proposals, **step.line_fields())
            assert step.processed.ledger.totals() == ledger.totals()
            world, engine = step.processed.overlay, step.engine
        return writer.close()


def test_saved_witnessed_death_recovery_repeat_and_native_viewer(tmp_path):
    path = tmp_path / 'witnessed.jsonl'
    trail = save_witnessed_death_scene(path)
    run = read_run(path)
    assert run.complete
    assert run.ticks[0]['decisions']['p01']['announced_to'] == ['p02']
    assert run.ticks[1]['decisions']['p02']['waiting_for_food'] == 'p01'
    assert run.ticks[3]['world']['died_at'] == {'p01': 4}
    witness = run.ticks[4]['observations']['p02']
    assert witness['witnessed_deaths'] == ['p01']
    assert witness['food_expectation_end'] == "witnessed the housemate's death"
    assert run.ticks[4]['decisions']['p02']['provisioning'] == 'gather'
    assert not run.ticks[4]['world'].get('food_expected')
    events = build_index(run)['events']
    assert any(e['kind'] == 'food_expectation_end' and e['k'] == 5
               and "witnessed the housemate's death" in e['text'] for e in events)
    assert "witnessed the housemate's death" in render_html(run)
    assert "Witnessed deaths" in render_html(run)
    # Custom initial conditions are deliberately not claimed as generated-world
    # replay. Recovery restores the actual saved ledger/overlay at each cut.
    lines = path.read_bytes().splitlines(keepends=True)
    for tick in (2, 3, 4):  # before death, before witnessing, after clearing
        end = next(i for i, line in enumerate(lines)
                   if json.loads(line).get('kind') == 'tick' and json.loads(line).get('tick') == tick)
        cut, restored = tmp_path / f'cut-{tick}.jsonl', tmp_path / f'restored-{tick}.jsonl'
        cut.write_bytes(b''.join(lines[:end+1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks
    assert save_witnessed_death_scene(tmp_path / 'repeat.jsonl') == trail


def test_expectations_are_immutable_preserved_by_births_and_cleared_by_listener_move_or_death():
    cfg, ledger, world = house()
    home = world.homes["p01"]
    world = replace(world, tick=1, food_expected={"p02": ["p01", 1]},
                    held={p:0 for p in world.roster}, built={p:cfg.build_ticks for p in world.roster},
                    cold={p:0 for p in world.roster},
                    positions=dict(world.positions,p01=(home[0]+1,home[1])))
    assert Overlay.from_canonical(world.canonical()).canonical() == world.canonical()
    with pytest.raises(TypeError): world.food_expected["p02"] = ("p01", 0)
    for entry in (("p02",1), ("ghost",1), ("p01",2), ("p01",True), ("p01",)):
        with pytest.raises(ValueError): replace(world, food_expected={"p02":entry})
    grown, _, born = _births(world, replace(ledger,tick=1), replace(cfg,births_on=True,together_ticks=1))
    assert born and grown.food_expected == {"p02":("p01",1)}
    away = replace(world, positions=dict(world.positions,p01=(home[0]+1,home[1])))
    view = observe("p02",replace(ledger,tick=1),away,cfg)
    for current in (replace(away,homes=dict(away.homes,p02=(0,0))), replace(away,died_at={"p02":1})):
        assert not update_food_expectations(away,current,{}, {"p02":view})


def test_headers_cli_and_default_compatibility():
    cfg, _, _ = house()
    off = replace(cfg,coordination_on=False)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    assert WorldConfig.from_describe(off.describe()) == off
    assert "coordination" not in off.describe() and genesis(cfg)==genesis(off)
    assert run_id_for(cfg,100)!=run_id_for(off,100)
    args=build_parser().parse_args(["--seed","7","--stores","on","--provisioning","on","--coordination","on"])
    assert config_from(args).coordination_on
    with pytest.raises(ValueError): replace(cfg,coordination_on=1)
    with pytest.raises(ValueError): replace(cfg,provisioning_on=False)
    bad=cfg.describe(); bad["food_expect_ticks"]=100
    with pytest.raises(ValueError): WorldConfig.from_describe(bad)


def test_saved_announcement_replay_recovery_repeat_and_viewer(tmp_path):
    cfg=WorldConfig(seed=23,stores_on=True,homes_on=True,provisioning_on=True,coordination_on=True,
                    fishing_on=True,source_memory_on=True,wood_on=True,relocation_on=True,
                    seasons_on=True,regrowth_on=True,source_stock=8,source_cap=16,renewal_amount=3)
    path=tmp_path/"coordination.jsonl"; result=run_world(cfg,220,path)
    run=read_run(path)
    assert run.complete and replay_world(path).identical
    events=build_index(run)["events"]
    assert {"food_announcement","food_expected_wait","food_expectation_end"} <= {e["kind"] for e in events}
    assert "Expecting food" in render_html(run)
    active=next(t["tick"] for t in run.ticks if t["world"].get("food_expected"))
    lines=path.read_bytes().splitlines(keepends=True)
    end=next(i for i,line in enumerate(lines) if json.loads(line).get("kind")=="tick" and json.loads(line).get("tick")==active)
    cut,restored=tmp_path/"cut.jsonl",tmp_path/"restored.jsonl"
    cut.write_bytes(b"".join(lines[:end+1])); recover_world(cut,restored)
    assert read_run(restored).ticks==run.ticks and replay_world(restored).identical
    assert run_world(cfg,220,tmp_path/"repeat.jsonl").trail_digest==result.trail_digest
