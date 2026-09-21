"""Reviewer probes for Stage 1b (reservations) on the snapshot of the
uncommitted working tree. Written from the declarations in RECORD.md, the
roadmap tick algorithm and the kernel source, not from tests/test_reservations.py."""
import random
from itertools import permutations

import pytest

from kernel import (Effect, Engine, Reservation, Source, WorldState, cancel, claim, complete,
                    consume, reserve, settle, transfer)
from kernel import reasons


def world(tick=0, balances=None, sources=None, reservations=None):
    return WorldState.genesis(tick=tick, balances=balances or {}, sources=sources or {}, reservations=reservations or {})


def outcome(record, pid):
    found = [o for o in record.outcomes if o.proposal_id == pid]
    assert len(found) == 1, (pid, found)
    return found[0]


def reason(record, pid):
    return outcome(record, pid).reason


# --- phase precedence versus actor order -----------------------------------------

def test_actor_order_cannot_put_a_spend_ahead_of_its_own_completion_or_use_held_units():
    engine = Engine(world(balances={'A': 1, 'B': 0}))
    first = engine.tick([reserve('r', 'A', 0, operation='consume', params={'amount': 1})])
    action = outcome(first, 'r').action_id
    # A declares the spend first (order 0) and the completion second (order 1).
    second = engine.tick([consume('spend', 'A', 0, amount=1), complete('done', 'A', 1, action_id=action)])
    assert reason(second, 'done') == reasons.ACCEPTED
    assert reason(second, 'spend') == reasons.DENIED_INSUFFICIENT_BALANCE
    assert [o.proposal_id for o in second.outcomes] == ['done', 'spend']  # phase before sequence in the record
    assert engine.state.balances['A'] == 0 and engine.state.consumed == 1 and engine.state.total() == 1


def test_hold_survives_many_ticks_of_other_activity_and_zero_free_balance():
    engine = Engine(world(balances={'A': 2, 'B': 0}, sources={'S': Source(3, ('B',))}))
    first = engine.tick([reserve('r', 'A', 0, operation='transfer', params={'to': 'B', 'amount': 2})])
    action = outcome(first, 'r').action_id
    for tick in range(1, 25):
        rec = engine.tick([claim(f'b{tick}', 'B', 0, sources={'S': 1}), consume(f'a{tick}', 'A', 0, amount=1),
                           consume(f'bb{tick}', 'B', 1, amount=1)])
        assert reason(rec, f'a{tick}') == reasons.DENIED_INSUFFICIENT_BALANCE  # both units are held
        assert engine.state.reservations[action].actor == 'A'
        assert engine.state.balances['A'] == 2 and engine.state.total() == 5
    done = engine.tick([complete('done', 'A', 0, action_id=action)])
    assert reason(done, 'done') == reasons.ACCEPTED
    assert engine.state.balances['A'] == 0 and not engine.state.reservations and engine.state.total() == 5


def test_two_actors_contending_to_reserve_the_last_unit_get_exactly_one_hold():
    for tick in (0, 1, 2, 3):
        for order in permutations(['A', 'B']):
            engine = Engine(world(tick=tick, balances={'A': 0, 'B': 0}, sources={'S': Source(1, ('A', 'B'))}))
            rec = engine.tick([reserve(f'r{a}', a, 0, operation='claim', params={'sources': {'S': 1}}) for a in order])
            holds = [o for o in rec.outcomes if o.accepted]
            assert len(holds) == 1 and holds[0].actor == ('A' if tick % 2 == 0 else 'B')
            assert len(engine.state.reservations) == 1 and engine.state.availability()['source:S'] == 0
            assert engine.state.sources['S'].stock == 1 and engine.state.total() == 1


def test_cross_actor_cancel_attempt_alongside_own_completion():
    engine = Engine(world(balances={'A': 1, 'B': 1}))
    first = engine.tick([reserve('ra', 'A', 0, operation='consume', params={'amount': 1}),
                         reserve('rb', 'B', 0, operation='consume', params={'amount': 1})])
    ida, idb = outcome(first, 'ra').action_id, outcome(first, 'rb').action_id
    assert ida != idb
    second = engine.tick([cancel('steal', 'A', 0, action_id=idb), complete('mine', 'A', 1, action_id=ida)])
    assert reason(second, 'steal') == reasons.DENIED_UNAUTHORISED and reason(second, 'mine') == reasons.ACCEPTED
    assert set(engine.state.reservations) == {idb}
    assert engine.state.balances == {'A': 0, 'B': 1} and engine.state.consumed == 1


def test_nested_reserve_and_reserve_of_terminal_ops_leave_no_hold():
    engine = Engine(world(balances={'A': 3}))
    rec = engine.tick([
        reserve('n1', 'A', 0, operation='reserve', params={'operation': 'consume', 'params': {'amount': 1}}),
        reserve('n2', 'A', 1, operation='cancel', params={'action_id': 'x'}),
        reserve('n3', 'A', 2, operation='consume', params={'amount': 1, 'extra': 1}),
    ])
    assert reason(rec, 'n1') == reasons.DENIED_UNKNOWN_OPERATION
    assert reason(rec, 'n2') == reasons.DENIED_UNKNOWN_OPERATION
    assert reason(rec, 'n3') == reasons.ACCEPTED  # the inner expander ignores unknown extra keys, as claim/consume already did in 1a
    assert len(engine.state.reservations) == 1 and engine.state.balances['A'] == 3


def test_held_units_count_once_in_the_total_and_in_availability():
    plan = Reservation('action:x', 'A', 0, 'consume', (Effect('actor:A', -1), Effect('sink:consumed', 1)))
    state = world(tick=1, balances={'A': 1}, reservations={'action:x': plan})
    assert state.total() == 1 and state.availability()['actor:A'] == 0
    view = state.view_for('A')
    assert view.own_balance == 1 and view.own_available == 0
    with pytest.raises(ValueError):
        world(tick=1, balances={'A': 1}, reservations={'action:x': plan, 'action:y': Reservation(
            'action:y', 'A', 0, 'consume', (Effect('actor:A', -1), Effect('sink:consumed', 1)))})


def test_reserved_transfer_recipient_gets_nothing_until_completion_then_next_tick_spendable():
    engine = Engine(world(balances={'A': 1, 'B': 0}))
    action = outcome(engine.tick([reserve('r', 'A', 0, operation='transfer', params={'to': 'B', 'amount': 1})]), 'r').action_id
    assert engine.state.balances == {'A': 1, 'B': 0}
    mid = engine.tick([consume('bx', 'B', 0, amount=1)])
    assert reason(mid, 'bx') == reasons.DENIED_INSUFFICIENT_BALANCE
    done = engine.tick([complete('c', 'A', 0, action_id=action), consume('by', 'B', 0, amount=1)])
    assert reason(done, 'c') == reasons.ACCEPTED and reason(done, 'by') == reasons.DENIED_INSUFFICIENT_BALANCE
    assert engine.state.balances == {'A': 0, 'B': 1}
    assert reason(engine.tick([consume('bz', 'B', 0, amount=1)]), 'bz') == reasons.ACCEPTED


def test_action_id_is_deterministic_across_engines_and_differs_by_tick_actor_sequence():
    def hold(tick, actor, extra_first=False):
        engine = Engine(world(tick=tick, balances={'A': 3, 'B': 3}))
        ps = [reserve('r', actor, 5, operation='consume', params={'amount': 1})]
        if extra_first:
            ps.insert(0, consume('other', actor, 1, amount=1))
        return outcome(engine.tick(ps), 'r').action_id
    assert hold(0, 'A') == hold(0, 'A')
    assert hold(0, 'A') != hold(1, 'A') != hold(1, 'B')
    assert hold(0, 'A') != hold(0, 'A', extra_first=True)  # a preceding proposal shifts the dense sequence
    assert hold(0, 'A').startswith('action:') and len(hold(0, 'A')) == len('action:') + 64


# --- fuzz: lifecycle exactly-once, availability, conservation, determinism -----------

def _script(rng, actors, sources, live, n):
    ps = []
    for i in range(n):
        actor = rng.choice(actors * 5 + ['Ghost'])
        order = i if rng.random() > 0.1 else rng.randrange(0, n)
        pid = f'p{i}' if rng.random() > 0.05 else f'p{rng.randrange(0, n)}'
        amount = rng.choice([1, 1, 1, 2, 3, 0, True, 1.5])
        kind = rng.choice(['reserve', 'reserve', 'complete', 'complete', 'cancel', 'claim', 'transfer', 'consume'])
        inner = rng.choice(['claim', 'transfer', 'consume'])
        if kind in ('complete', 'cancel'):
            target = rng.choice(live + ['action:bogus', 'action:' + '0' * 64]) if live else 'action:bogus'
            ps.append((complete if kind == 'complete' else cancel)(pid, actor, order, action_id=target))
            continue
        if kind == 'claim' or (kind == 'reserve' and inner == 'claim'):
            params = {'sources': {s: amount for s in rng.sample(sources, rng.randrange(1, len(sources) + 1))}}
        elif kind == 'transfer' or (kind == 'reserve' and inner == 'transfer'):
            params = {'to': rng.choice(actors + ['Ghost']), 'amount': amount}
        else:
            params = {'amount': amount}
        if kind == 'reserve':
            ps.append(reserve(pid, actor, order, operation=inner, params=params))
        else:
            ps.append({'claim': claim, 'transfer': transfer, 'consume': consume}[kind](pid, actor, order, **params))
    return ps


def test_fuzz_reservation_lifecycle_over_many_ticks_twice():
    actors = ['A', 'B', 'C', 'D']
    sources = ['S', 'T']
    # Nothing produces units in this slice, so a deep economy keeps the accept path alive for 300 ticks.
    genesis = world(balances={a: 150 for a in actors}, sources={'S': Source(200, ('A', 'B', 'C')), 'T': Source(200, ('B', 'C', 'D'))})
    trails = []
    for run in range(2):
        rng = random.Random(99)  # same script both runs
        engine = Engine(genesis)
        live, created, closed, completions, closes_by_action = [], {}, set(), 0, {}
        trail = []
        for tick in range(300):
            ps = _script(rng, actors, sources, live, rng.randrange(0, 10))
            random.Random(run * 7919 + tick).shuffle(ps)  # collection order differs between runs
            before = engine.state
            free_before = before.availability()
            rec = engine.tick(ps)
            after = engine.state
            # conservation and non-negativity, holds counted once
            assert after.total() == before.total() == genesis.total()
            assert all(v >= 0 for v in after.availability().values())
            # one reason per submission
            assert sorted(o.proposal_id for o in rec.outcomes) == sorted(p.proposal_id for p in ps)
            debits = {}
            for o in rec.outcomes:
                assert o.reason in reasons.ALL
                if o.operation == 'reserve' and o.accepted:
                    assert o.effects == () and o.reservation is not None and o.action_id in after.reservations
                    assert after.reservations[o.action_id] == o.reservation and o.reservation.created_tick == before.tick
                    created[o.action_id] = o.reservation
                    for e in o.reservation.effects:
                        if e.delta < 0:
                            debits[e.account] = debits.get(e.account, 0) - e.delta
                elif o.operation in ('complete', 'cancel'):
                    if o.accepted:
                        assert o.action_id in before.reservations and o.action_id not in after.reservations
                        assert o.action_id not in closed  # exactly once, ever
                        closed.add(o.action_id)
                        closes_by_action[o.action_id] = closes_by_action.get(o.action_id, 0) + 1
                        plan = before.reservations[o.action_id]
                        assert o.effects == (plan.effects if o.operation == 'complete' else ())
                        assert plan.actor == o.actor
                        completions += o.operation == 'complete'
                    else:
                        assert o.effects == ()
                elif o.accepted:
                    for e in o.effects:
                        if e.delta < 0:
                            debits[e.account] = debits.get(e.account, 0) - e.delta
            # phase-2 debits (new holds and ordinary spends) never exceed tick-start free stock
            for account, amount in debits.items():
                assert amount <= free_before[account], (account, amount, free_before[account])
            # holds that were not closed this tick persist unchanged
            for action_id, plan in before.reservations.items():
                if action_id not in closed:
                    assert after.reservations[action_id] == plan
            live = list(after.reservations)
            trail.append((rec.digest(), after.digest()))
        assert max(closes_by_action.values()) == 1
        assert completions > 20 and len(created) > 60 and len(closed) > 40, (completions, len(created), len(closed))
        trails.append(trail)
    assert trails[0] == trails[1]
