"""Request lifecycle without learned donor preference; controlled cases are explicit."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world, world_step
from world.viewer_index import build_index


def encounter(*, adjacent=True, positions=None, balances=None, hunger=None, **changes):
    positions = positions or {'p01': (3, 5), 'p02': (4, 5)}
    options = dict(seed=1, actors=len(positions), requests_on=True,
                      adjacent_requests=adjacent, social_memory_on=False,
                      water_on=False, warmth_on=False, terrain_on=False,
                      building_on=False, births_on=False, childhood_on=False,
                      offers_on=False, plan_trips=False, stagger_start=False,
                      source_stock=0, source_cap=0, renewal_amount=0)
    options.update(changes)
    cfg = WorldConfig(**options)
    ledger, world = genesis(cfg)
    ledger = replace(ledger, balances=balances or {'p01': 0, 'p02': 1})
    world = replace(world, homes=positions, positions=positions,
                    hunger=hunger or {'p01': cfg.hungry_at, 'p02': 0})
    return cfg, ledger, world


def advance(cfg, ledger, world, ticks):
    engine = Engine(ledger)
    steps = []
    for _ in range(ticks):
        step = world_step(engine, world, cfg)
        assert not step.processed.overlay.food_memory
        assert all(not view.food_memory for view in step.views.values())
        assert step.committed.totals() == ledger.totals()
        steps.append(step)
        engine, world = step.engine, step.processed.overlay
    return steps


@pytest.mark.parametrize('adjacent', [False, True])
def test_request_runs_through_agreement_or_direct_transfer_and_meal_without_memory(adjacent):
    positions = None if adjacent else {'p01': (2, 5), 'p02': (5, 5)}
    cfg, ledger, world = encounter(adjacent=adjacent, positions=positions)
    steps = advance(cfg, ledger, world, 6)
    assert steps[0].decisions['p01'].kind == 'ask'
    helper_actions = [step.decisions['p02'].kind for step in steps]
    assert ('agree' in helper_actions) is (not adjacent)
    donated = next(i for i, step in enumerate(steps)
                   if any(o.actor == 'p02' and o.operation == 'transfer' and o.accepted
                          for o in step.record.outcomes))
    assert steps[donated].committed.balances['p01'] == 1
    assert steps[donated + 1].decisions['p01'].kind == 'eat'
    assert steps[donated + 1].processed.overlay.hunger['p01'] < steps[donated].processed.overlay.hunger['p01']


def test_helper_may_eat_instead_of_answering_and_the_request_lapses():
    cfg, ledger, world = encounter(hunger={'p01': 25, 'p02': 24})
    first, answer = advance(cfg, ledger, world, 2)
    assert first.processed.overlay.requests == {'p01': 'p02'}
    assert answer.decisions['p02'].kind == 'eat'
    assert not any(o.operation == 'transfer' for o in answer.record.outcomes)
    assert not answer.processed.overlay.requests


def test_two_requesters_compete_for_one_real_unit():
    cfg, ledger, world = encounter(
        positions={'p01': (3, 5), 'p02': (4, 6), 'p03': (4, 5)},
        balances={'p01': 0, 'p02': 0, 'p03': 1},
        hunger={'p01': 25, 'p02': 25, 'p03': 0})
    first, answer = advance(cfg, ledger, world, 2)
    assert first.processed.overlay.requests == {'p01': 'p03', 'p02': 'p03'}
    transfers = [o for o in answer.record.outcomes if o.operation == 'transfer' and o.accepted]
    assert len(transfers) == 1 and transfers[0].actor == 'p03'
    assert dict(answer.committed.balances) == {'p01': 1, 'p02': 0, 'p03': 0}


@pytest.mark.parametrize('missing', ['sight', 'stock'])
def test_pending_request_rechecks_current_sight_and_stock(missing):
    cfg, ledger, world = encounter(hunger={'p01': 0, 'p02': 0})
    world = replace(world, requests={'p01': 'p02'})
    if missing == 'sight':
        world = replace(world, positions={'p01': (0, 0), 'p02': (7, 7)})
    else:
        ledger = replace(ledger, balances={'p01': 0, 'p02': 0})
    step, = advance(cfg, ledger, world, 1)
    assert step.decisions['p02'].kind not in ('agree', 'offer', 'go_offer')
    assert not step.processed.overlay.requests
    assert not step.processed.overlay.promises


def test_personal_need_interrupts_an_existing_delivery_without_inventing_food():
    cfg, ledger, world = encounter(adjacent=False, hunger={'p01': 25, 'p02': 25})
    world = replace(world, promises={'p02': 'p01'})
    step, = advance(cfg, ledger, world, 1)
    assert step.decisions['p02'].kind == 'eat'
    assert step.committed.balances['p01'] == 0
    assert not any(o.operation == 'transfer' for o in step.record.outcomes)


def test_asker_death_before_answer_clears_the_request():
    cfg, ledger, world = encounter(hunger={'p01': 79, 'p02': 0})
    first, second = advance(cfg, ledger, world, 2)
    assert first.decisions['p01'].kind == 'ask'
    assert 'p01' in first.processed.overlay.died_at
    assert not first.processed.overlay.requests
    assert second.decisions['p02'].kind not in ('agree', 'offer', 'go_offer')


def test_helper_death_before_answer_clears_the_request():
    cfg, ledger, world = encounter(water_on=True)
    ledger = replace(ledger, holdings={'water': {'p01': 0, 'p02': 0}},
                     consumed_by={'water': 0})
    world = replace(world, thirst={'p01': 0, 'p02': cfg.thirst_death_at - cfg.thirst_rate})
    first, second = advance(cfg, ledger, world, 2)
    assert first.decisions['p01'].kind == 'ask'
    assert 'p02' in first.processed.overlay.died_at
    assert not first.processed.overlay.requests and not second.processed.overlay.promises


@pytest.mark.long_run
@pytest.mark.parametrize('adjacent', [False, True])
def test_ordinary_requests_without_social_memory_save_replay_and_recover(tmp_path, adjacent):
    cfg = WorldConfig(seed=23, requests_on=True, adjacent_requests=adjacent,
                      social_memory_on=False)
    path = tmp_path / 'asking.jsonl'
    run_world(cfg, 220, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    assert all(not tick['world'].get('food_memory') for tick in run.ticks)
    events = build_index(run)['events']
    deliveries = [e for e in events if e['kind'] == 'delivered']
    assert deliveries, 'An empty request-event list cannot establish the positive chain'
    # Recover with an actual pending request, not only from an idle boundary.
    at = next(i for i, tick in enumerate(run.ticks) if tick['world'].get('requests'))
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines)
               if (data := json.loads(line)).get('kind') == 'tick' and data['tick'] == at)
    cut, restored = tmp_path / 'cut.jsonl', tmp_path / 'restored.jsonl'
    cut.write_bytes(b''.join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
