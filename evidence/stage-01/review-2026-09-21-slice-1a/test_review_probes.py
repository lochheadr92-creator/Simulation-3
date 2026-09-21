"""Reviewer probes against the pinned Stage 1a kernel (fb5a895).

Written from the declarations in RECORD.md and the kernel source, not from the
existing tests. Each probe reads engine objects through public accessors only.
"""
import hashlib
import itertools
import random

import pytest

from kernel import (CanonicalError, CollectingDiagnostics, Engine, Proposal, Source, WorldState,
                    canonical_bytes, claim, consume, transfer, settle)
from kernel import reasons


def world(tick=0, balances=None, sources=None, consumed=0):
    return WorldState.genesis(tick=tick, balances=balances or {}, sources=sources or {}, consumed=consumed)


def reason(record, pid):
    found = [o.reason for o in record.outcomes if o.proposal_id == pid]
    assert len(found) == 1, (pid, found)
    return found[0]


def invariants(before, after, record, proposals):
    assert after.total() == before.total()
    assert all(v >= 0 for v in after.balances.values())
    assert all(s.stock >= 0 for s in after.sources.values())
    assert after.consumed >= 0
    assert sorted(o.proposal_id for o in record.outcomes) == sorted(p.proposal_id for p in proposals)
    for o in record.outcomes:
        assert o.reason in reasons.ALL
        assert sum(e.delta for e in o.effects) == 0
        assert bool(o.effects) == o.accepted
    # Availability boundary: no account is debited beyond its tick-start holding in one tick.
    debits = {}
    for o in record.outcomes:
        for e in o.effects:
            if e.delta < 0:
                debits[e.account] = debits.get(e.account, 0) - e.delta
    for account, amount in debits.items():
        kind, _, ident = account.partition(':')
        start = before.balances[ident] if kind == 'actor' else before.sources[ident].stock
        assert amount <= start, (account, amount, start)


# --- identity namespaces and collisions ---------------------------------------

def test_actor_ids_that_look_like_accounts_do_not_collide():
    w = world(balances={'x': 1, 'actor:x': 0, 'sink:consumed': 2}, sources={'x': Source(1, ('x',))})
    ps = [transfer('t1', 'x', 0, to='actor:x', amount=1), claim('c1', 'x', 1, sources={'x': 1}),
          consume('k1', 'sink:consumed', 0, amount=1), transfer('t2', 'actor:x', 0, to='x', amount=1)]
    rec = settle(w, ps)
    after = rec.next_state
    invariants(w, after, rec, ps)
    assert reason(rec, 't1') == reasons.ACCEPTED
    assert reason(rec, 'c1') == reasons.ACCEPTED
    assert reason(rec, 'k1') == reasons.ACCEPTED
    assert reason(rec, 't2') == reasons.DENIED_INSUFFICIENT_BALANCE  # credit this tick is not spendable
    assert dict(after.balances) == {'x': 1, 'actor:x': 1, 'sink:consumed': 1}
    assert after.consumed == 1 and after.sources['x'].stock == 0


def test_transfer_to_sink_or_unknown_target_is_denied_and_debits_nothing():
    w = world(balances={'A': 3})
    ps = [transfer('s', 'A', 0, to='sink:consumed', amount=1), transfer('u', 'A', 1, to='Nobody', amount=1)]
    rec = settle(w, ps)
    assert reason(rec, 's') == reasons.DENIED_UNKNOWN_ACTOR
    assert reason(rec, 'u') == reasons.DENIED_UNKNOWN_ACTOR
    assert dict(rec.next_state.balances) == {'A': 3} and rec.next_state.consumed == 0


# --- all-or-nothing and availability ------------------------------------------

def test_three_source_claim_fails_whole_when_the_last_source_is_short():
    w = world(balances={'A': 0}, sources={'s1': Source(5, ('A',)), 's2': Source(5, ('A',)), 's3': Source(1, ('A',))})
    p = claim('c', 'A', 0, sources={'s1': 5, 's2': 5, 's3': 2})
    rec = settle(w, [p])
    assert reason(rec, 'c') == reasons.DENIED_INSUFFICIENT_SOURCE
    assert {k: v.stock for k, v in rec.next_state.sources.items()} == {'s1': 5, 's2': 5, 's3': 1}
    assert rec.next_state.balances['A'] == 0


def test_same_actor_two_claims_on_one_source_second_denied_no_overdraw():
    w = world(balances={'A': 0}, sources={'S': Source(3, ('A',))})
    ps = [claim('c1', 'A', 0, sources={'S': 2}), claim('c2', 'A', 1, sources={'S': 2})]
    rec = settle(w, ps)
    assert reason(rec, 'c1') == reasons.ACCEPTED and reason(rec, 'c2') == reasons.DENIED_INSUFFICIENT_SOURCE
    assert rec.next_state.sources['S'].stock == 1 and rec.next_state.balances['A'] == 2
    invariants(w, rec.next_state, rec, ps)


@pytest.mark.parametrize('tick', range(6))
def test_transfer_chain_cannot_forward_a_same_tick_credit_at_any_rotation(tick):
    w = world(tick=tick, balances={'A': 1, 'B': 0, 'C': 0})
    ps = [transfer('ab', 'A', 0, to='B', amount=1), transfer('bc', 'B', 0, to='C', amount=1)]
    for order in (ps, ps[::-1]):
        rec = settle(w, order)
        assert reason(rec, 'ab') == reasons.ACCEPTED
        assert reason(rec, 'bc') == reasons.DENIED_INSUFFICIENT_BALANCE
        assert dict(rec.next_state.balances) == {'A': 0, 'B': 1, 'C': 0}
    later = settle(rec.next_state, [transfer('bc2', 'B', 0, to='C', amount=1)])
    assert reason(later, 'bc2') == reasons.ACCEPTED


def test_unauthorised_claim_denied_while_valid_sibling_proposal_settles():
    w = world(balances={'A': 2, 'B': 0}, sources={'S': Source(1, ('B',))})
    ps = [claim('bad', 'A', 0, sources={'S': 1}), consume('ok', 'A', 1, amount=1)]
    rec = settle(w, ps)
    assert reason(rec, 'bad') == reasons.DENIED_UNAUTHORISED and reason(rec, 'ok') == reasons.ACCEPTED
    assert rec.next_state.sources['S'].stock == 1 and rec.next_state.balances['A'] == 1 and rec.next_state.consumed == 1


def test_duplicate_id_across_actors_denies_both_but_not_others():
    w = world(balances={'A': 1, 'B': 1})
    ps = [consume('same', 'A', 0, amount=1), consume('same', 'B', 0, amount=1), consume('other', 'B', 1, amount=1)]
    rec = settle(w, ps)
    assert [o.reason for o in rec.outcomes if o.proposal_id == 'same'] == [reasons.DENIED_DUPLICATE_PROPOSAL_ID] * 2
    assert reason(rec, 'other') == reasons.ACCEPTED
    assert dict(rec.next_state.balances) == {'A': 1, 'B': 0}


# --- engine sequence ownership (R5) and order independence --------------------

def test_sparse_orders_and_dense_orders_give_identical_record_identity():
    w = world(balances={'A': 3, 'B': 0})
    dense = [transfer('t', 'A', 0, to='B', amount=1), consume('k', 'A', 1, amount=1)]
    sparse = [transfer('t', 'A', 7, to='B', amount=1), consume('k', 'A', 10 ** 30, amount=1)]
    a, b = Engine(w).tick(dense), Engine(w).tick(sparse)
    assert a.digest() == b.digest()
    assert [o.sequence for o in b.outcomes] == [0, 1]


def test_random_shuffles_and_map_orders_give_one_digest():
    rng = random.Random(1234)
    base_balances = {'A': 2, 'B': 1, 'C': 0, 'D': 5}
    base_sources = {'S': Source(2, ('A', 'C')), 'T': Source(1, ('B', 'C', 'D'))}
    ps = [claim('a0', 'A', 0, sources={'S': 1}), claim('c0', 'C', 0, sources={'S': 2, 'T': 1}),
          transfer('b0', 'B', 0, to='C', amount=1), consume('d0', 'D', 0, amount=2),
          transfer('d1', 'D', 1, to='A', amount=3), consume('a1', 'A', 1, amount=2),
          consume('zz', 'Z', 0, amount=1), claim('dup', 'B', 1, sources={'T': 1}), claim('dup', 'D', 2, sources={'T': 1})]
    digests = set()
    for _ in range(300):
        bal_keys = list(base_balances); rng.shuffle(bal_keys)
        src_keys = list(base_sources); rng.shuffle(src_keys)
        w = WorldState.genesis(tick=rng.randrange(0, 4) * 0 + 1, balances={k: base_balances[k] for k in bal_keys},
                               sources={k: base_sources[k] for k in src_keys})
        order = list(ps); rng.shuffle(order)
        engine = Engine(w)
        rec = engine.tick(order)
        digests.add((rec.digest(), engine.state.digest()))
    assert len(digests) == 1


# --- reentrancy (R1) ---------------------------------------------------------

def test_reentry_from_diagnostics_sink_is_refused_and_counted_without_double_commit():
    class Hostile:
        def __init__(self): self.engine = None; self.attempts = 0
        def record(self, event, payload):
            self.attempts += 1
            self.engine.tick([consume('inner', 'A', 0, amount=1)])  # must raise inside the guard
    sink = Hostile()
    engine = Engine(world(balances={'A': 3}), sink)
    sink.engine = engine
    rec = engine.tick([consume('outer', 'A', 0, amount=1)])
    assert sink.attempts == 1 and engine.diagnostics_failures == 1
    assert engine.state.balances['A'] == 2 and engine.state.tick == 1 and engine.state.consumed == 1
    assert rec.next_state_digest == engine.state.digest()


def test_reentry_from_proposal_generator_raises_and_leaves_state_intact():
    engine = Engine(world(balances={'A': 3}))
    before = engine.state.digest()

    def gen():
        yield consume('p1', 'A', 0, amount=1)
        engine.tick([])  # reentry
        yield consume('p2', 'A', 1, amount=1)
    with pytest.raises(RuntimeError):
        engine.tick(gen())
    assert engine.state.digest() == before and engine.state.tick == 0
    rec = engine.tick([consume('p3', 'A', 0, amount=1)])  # guard released
    assert reason(rec, 'p3') == reasons.ACCEPTED and engine.state.tick == 1


def test_non_proposal_input_raises_before_any_change():
    engine = Engine(world(balances={'A': 1}))
    with pytest.raises(TypeError):
        engine.tick([consume('p', 'A', 0, amount=1), object()])
    assert engine.state.tick == 0 and engine.state.balances['A'] == 1


# --- observation -----------------------------------------------------------------

def test_observers_cannot_mutate_state_views_records_or_sources():
    w = world(balances={'A': 1}, sources={'S': Source(1, ('A',))})
    engine = Engine(w)
    view = engine.view_for('A')
    rec = engine.tick([claim('c', 'A', 0, sources={'S': 1})])
    for target, op in [(view.balances, lambda m: m.__setitem__('A', 9)), (engine.state.balances, lambda m: m.__setitem__('A', 9)),
                       (engine.state.sources, lambda m: m.pop('S')), (view.sources, lambda m: m.clear())]:
        with pytest.raises((TypeError, AttributeError)):
            op(target)
    with pytest.raises(AttributeError):
        rec.outcomes = ()
    with pytest.raises(AttributeError):
        engine.state.sources['S'].authorised.add('B')
    digest_before_edit = rec.digest()
    copy = rec.canonical(); copy['outcomes'].clear(); copy['tick'] = 99
    assert rec.digest() == digest_before_edit and rec.tick == 0
    settled = engine.state.digest()
    assert rec.next_state_digest == settled
    assert engine.tick([]).prior_state_digest == settled
    assert view.balances['A'] == 1 and view.sources['S'].stock == 1  # earlier view unchanged after two ticks
    assert engine.state.balances['A'] == 2 and engine.state.sources['S'].stock == 0


# --- canonical form (R4) ----------------------------------------------------------

def test_integer_text_matches_json_for_random_and_boundary_values_and_handles_huge():
    rng = random.Random(7)
    values = [0, 1, -1, 10 ** 9 - 1, 10 ** 9, 10 ** 9 + 1, 10 ** 18, -(10 ** 18), 999_999_999_999_999_999]
    values += [rng.randrange(-10 ** 40, 10 ** 40) for _ in range(500)]
    for v in values:
        assert canonical_bytes(v) == str(v).encode()
    huge = 10 ** 5000 + 12345
    raw = canonical_bytes({'balances': {'A': huge}, 'x': [1, 'é', None]})
    assert raw.startswith(b'{"balances":{"A":1') and raw.endswith(b'12345},"x":[1,"\\u00e9",null]}')
    assert len(raw) == len(b'{"balances":{"A":') + 5001 + len(b'},"x":[1,"\\u00e9",null]}')
    for bad in (True, 1.5, {1: 2}, {'a': [False]}, object()):
        with pytest.raises(CanonicalError):
            canonical_bytes(bad)
    w = world(balances={'A': huge}, sources={'S': Source(huge, ('A',))})
    rec = settle(w, [claim('c', 'A', 0, sources={'S': huge}), consume('k', 'A', 1, amount=huge)])
    assert reason(rec, 'c') == reasons.ACCEPTED and reason(rec, 'k') == reasons.ACCEPTED
    assert rec.next_state.total() == w.total() == 2 * huge
    assert rec.next_state.balances['A'] == huge and rec.next_state.consumed == huge
    assert len(rec.next_state.digest()) == 64


# --- fuzz: conservation, rails, one-reason-per-proposal, determinism ------------

def _random_proposals(rng, actors, sources, n):
    ops = []
    for i in range(n):
        actor = rng.choice(actors + ['Ghost'])
        order = rng.choice([i, i, i, rng.randrange(0, n)])  # some duplicate orders
        pid = f'p{i}' if rng.random() > 0.05 else f'p{rng.randrange(0, n)}'
        amount = rng.choice([1, 1, 2, 3, 0, -1, 1.5, True, 10 ** 6])
        kind = rng.choice(['claim', 'transfer', 'consume', 'bogus'])
        if kind == 'claim':
            chosen = rng.sample(sources, rng.randrange(0, len(sources) + 1))
            ops.append(Proposal(pid, actor, order, 'claim', {'sources': {s: amount for s in chosen}}))
        elif kind == 'transfer':
            ops.append(Proposal(pid, actor, order, 'transfer', {'to': rng.choice(actors + [actor, 'Ghost']), 'amount': amount}))
        elif kind == 'consume':
            ops.append(Proposal(pid, actor, order, 'consume', {'amount': amount}))
        else:
            ops.append(Proposal(pid, actor, order, 'bogus', {'amount': amount}))
    return ops


def test_fuzz_conservation_rails_and_determinism_over_many_ticks():
    actors = ['A', 'B', 'C', 'D', 'E']
    sources = ['S', 'T', 'U']
    genesis = world(balances={a: 3 for a in actors},
                    sources={'S': Source(6, ('A', 'B')), 'T': Source(4, ('C', 'D', 'E')), 'U': Source(2, tuple(actors))})
    rng = random.Random(2026)
    scripts = [_random_proposals(rng, actors, sources, rng.randrange(0, 12)) for _ in range(250)]
    trail = []
    accepted_per_run = []
    for run in range(2):
        engine = Engine(genesis, CollectingDiagnostics())
        accepted = 0
        for tick, ps in enumerate(scripts):
            before = engine.state
            order = list(ps)
            random.Random(run * 1000 + tick).shuffle(order)  # different collection order on the second run
            rec = engine.tick(order)
            invariants(before, engine.state, rec, ps)
            assert rec.tick == tick and rec.prior_state_digest == before.digest()
            accepted += sum(o.accepted for o in rec.outcomes)
            trail.append((rec.digest(), engine.state.digest()))
        assert accepted > 20, accepted  # the fuzz actually exercised the accept path (attempt 1 saw 40)
        accepted_per_run.append(accepted)
    assert accepted_per_run[0] == accepted_per_run[1]
    assert trail[:250] == trail[250:]
    assert engine.state.total() == genesis.total() == 15 + 12


def test_empty_roster_denies_everything_and_still_advances():
    rec = settle(world(), [consume('p', 'A', 0, amount=1)])
    assert reason(rec, 'p') == reasons.DENIED_UNKNOWN_ACTOR and rec.next_state.tick == 1 and rec.rotated_roster == ()
