"""Personal terrain knowledge changes food departure timing, not destinations."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import decide, food_travel_ticks, route_step, water_trip_due
from world.observe import Observation, observe
from world.overlay import Overlay
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world, world_step
from world.viewer import render_html


def repeat_trip_config():
    return WorldConfig(seed=1, actors=1, width=7, height=7, food_sources=1,
        water_on=False, warmth_on=False, offers_on=False, births_on=False,
        childhood_on=False, building_on=False, stagger_start=False,
        perception_radius=1, shelter_pct=0, rough_pct=40, starting_food=0,
        claim_amount=1, source_stock=8, source_cap=8, renewal_every=5)


def view(**changes):
    fields = dict(actor='p01', tick=0, alive=True, position=(0, 0), home=(0, 0),
                  hunger=19, food=0, source=(4, 0), source_food=None,
                  rough_in_view=frozenset({(1, 0), (2, 0), (3, 0)}))
    return Observation(**(fields | changes))


@pytest.mark.parametrize('rough,expected,step', [
    (frozenset(), 4, (1, 0)),
    (frozenset({(1, 0)}), 5, (1, 0)),
    (frozenset({(1, 0), (2, 0), (3, 0)}), 6, (0, 1)),
    (frozenset({(6, 6)}), 4, (1, 0)),
])
def test_cost_matches_route_crossing_or_detour(rough, expected, step):
    cfg, seen = repeat_trip_config(), view(rough_in_view=rough)
    assert food_travel_ticks(seen, cfg) == expected
    assert route_step(seen, seen.source, cfg) == step


@pytest.mark.parametrize('changes', [{'terrain_on': False}, {'route_around': False}])
def test_disabled_routing_or_terrain_retains_nominal_timing(changes):
    cfg = replace(repeat_trip_config(), **changes)
    assert food_travel_ticks(view(held=1), cfg) == 4
    assert decide(view(), cfg).kind == 'rest'


@pytest.mark.parametrize('changes,config_changes', [
    ({'food': 1}, {}), ({'hunger': 18}, {}), ({}, {'plan_trips': False}),
    ({}, {'hunger_rate': 0}), ({'age': 0}, {'childhood_on': True, 'child_leash': 3}),
])
def test_knowledge_does_not_relax_food_trip_conditions(changes, config_changes):
    assert decide(view(**changes), replace(repeat_trip_config(), **config_changes)).kind == 'rest'


def test_current_movement_delay_and_fishing_cast_are_counted_once():
    cfg = repeat_trip_config()
    assert food_travel_ticks(view(held=1), cfg) == 7
    assert food_travel_ticks(view(position=(4, 0), held=1), cfg) == 0
    fishing = replace(cfg, fishing_on=True)
    assert decide(view(hunger=18, source_id='fish'), fishing).kind == 'go'
    assert decide(view(hunger=18, source_id='food'), fishing).kind == 'rest'
    assert decide(view(hunger=17, source_id='fish'), fishing).kind == 'rest'


def test_water_timing_and_need_priority_are_unchanged():
    cfg = replace(repeat_trip_config(), water_on=True)
    seen = view(water=0, water_source=(4, 0), thirst=16)
    assert not water_trip_due(seen, cfg)  # 16 + 2 * 4 < 25, despite known rough
    assert decide(seen, cfg).kind == 'go'
    assert decide(replace(seen, thirst=50), cfg).kind == 'go_water'


def test_repeat_trip_uses_acquired_memory_and_control_does_not_receive_it():
    cfg = repeat_trip_config()
    ledger, world = genesis(cfg)
    engine, observations, decisions = Engine(ledger), [], []
    for tick in range(56):
        if tick == 48:
            # Matched control: same needs/location/ledger, without the earlier
            # sightings. It still learns normally from this point onwards.
            restored = Overlay.from_canonical(world.canonical())
            assert restored.digest() == world.digest()
            control = replace(restored, terrain_memory={})
            control_engine = Engine(engine.state)
            control_before = control.canonical()
            before = world.canonical()
            treatment_view = observe('p01', engine.state, restored, cfg)
            control_view = observe('p01', control_engine.state, control, cfg)
            assert treatment_view.source == control_view.source
            assert treatment_view.rough_seen_now == control_view.rough_seen_now
            assert food_travel_ticks(treatment_view, cfg) == 6
            assert food_travel_ticks(control_view, cfg) == 4
            assert decide(treatment_view, cfg).kind == 'go'
            assert decide(control_view, cfg).kind == 'rest'
            assert world.canonical() == before and control.canonical() == control_before
            control_history = []
            for _ in range(10):
                step = world_step(control_engine, control, cfg)
                control_history.append((step.views['p01'].hunger, step.decisions['p01'].kind))
                control, control_engine = step.processed.overlay, step.engine
            assert control_history[:2] == [(19, 'rest'), (20, 'rest')]
            assert next(h for h, kind in control_history if kind == 'claim') == 27
        step = world_step(engine, world, cfg)
        observations.append(step.views['p01'])
        decisions.append(step.decisions['p01'])
        world, engine = step.processed.overlay, step.engine
    assert decisions[21].kind == 'go' and observations[21].hunger == 21
    assert decisions[27].kind == 'claim' and observations[27].hunger == 27
    assert observations[48].rough_in_view > observations[21].rough_in_view
    assert all(decisions[t].kind == 'go' for t in range(48, 54))
    assert decisions[54].kind == 'claim' and observations[54].hunger == 25
    assert decisions[55].kind == 'eat'


@pytest.mark.parametrize('trips', [False, True])
@pytest.mark.parametrize('terrain', [False, True])
@pytest.mark.parametrize('routing', [False, True])
def test_saved_rule_only_changes_for_enabled_terrain_planning(trips, terrain, routing):
    cfg = replace(repeat_trip_config(), plan_trips=trips, terrain_on=terrain, route_around=routing)
    description = cfg.describe()
    assert ('personal food departure timing' in description['decision']) == (trips and terrain and routing)
    restored = WorldConfig.from_describe(description)
    assert restored.describe() == description
    assert (restored.plan_trips, restored.terrain_on, restored.route_around) == (trips, terrain, routing)


def test_old_rule_description_is_not_silently_reinterpreted():
    description = repeat_trip_config().describe()
    # In this food-only configuration the new clause is the last decision rule.
    description['decision'] = description['decision'].split('; personal food departure timing')[0]
    with pytest.raises(ValueError):
        WorldConfig.from_describe(description)


def test_saved_experience_replays_recovers_and_reaches_the_viewer(tmp_path):
    cfg = repeat_trip_config()
    path = tmp_path / 'travel.jsonl'
    result = run_world(cfg, 80, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    assert 'allowing 6 travel ticks' in run.ticks[48]['decisions']['p01']['reason']
    assert 'allowing 6 travel ticks' in render_html(run)
    # Recover once with acquired memory at home, once while held on rough ground.
    lines = path.read_bytes().splitlines(keepends=True)
    for tick in (47, 49):
        end = next(i for i, line in enumerate(lines)
                   if json.loads(line).get('kind') == 'tick' and json.loads(line).get('tick') == tick)
        cut, recovered = tmp_path / f'cut{tick}.jsonl', tmp_path / f'recovered{tick}.jsonl'
        cut.write_bytes(b''.join(lines[:end + 1]))
        recover_world(cut, recovered)
        assert read_run(recovered).ticks == run.ticks
        assert replay_world(recovered).identical
    assert run_world(cfg, 80, tmp_path / 'repeat.jsonl').trail_digest == result.trail_digest
