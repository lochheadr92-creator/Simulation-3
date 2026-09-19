"""Repair regressions beyond the original adversarial reproductions."""
import json
import sys
from itertools import permutations

import pytest

from kernel import Engine, Proposal, Source, WorldState, canonical_bytes, claim, consume, transfer
from tests.test_review_regressions import isolated_harness


def world():
    return WorldState.genesis(balances={'A': 2, 'B': 0})


def test_generator_reentry_preserves_boundary_and_releases_guard():
    engine = Engine(world())
    before = engine.state.digest()
    def proposals():
        engine.tick([consume('nested', 'A', 0, amount=1)])
        yield consume('outer', 'A', 0, amount=1)
    with pytest.raises(RuntimeError, match='already in progress'):
        engine.tick(proposals())
    assert engine.state.digest() == before
    assert engine.tick([consume('next', 'A', 0, amount=1)]).outcomes[0].accepted
    assert engine.state.tick == 1
    assert engine.state.balances['A'] == 1


def test_settlement_failure_releases_guard_without_a_commit():
    engine = Engine(world())
    before = engine.state.digest()
    with pytest.raises(TypeError):
        engine.tick([None])
    assert engine.state.digest() == before
    engine.tick()
    assert engine.state.tick == 1


def test_guard_is_per_engine():
    other = Engine(world())
    class Sink:
        def record(self, event, payload):
            other.tick([consume('other', 'A', 0, amount=1)])
    engine = Engine(world(), diagnostics=Sink())
    record = engine.tick()
    assert record.next_state_digest == engine.state.digest()
    assert engine.state.balances['A'] == 2
    assert other.state.balances['A'] == 1


def test_diagnostics_reentry_is_counted_and_later_ticks_still_work():
    class Sink:
        def record(self, event, payload):
            engine.tick()
    engine = Engine(world(), diagnostics=Sink())
    for tick in (1, 2):
        record = engine.tick()
        assert engine.state.tick == tick
        assert record.next_state_digest == engine.state.digest()
        assert engine.diagnostics_failures == tick


def test_engine_sequences_do_not_copy_sparse_caller_orders():
    submitted = [consume('last', 'A', 10 ** 5000, amount=1), transfer('first', 'A', 7, to='B', amount=1)]
    seen = set()
    for order in permutations(submitted):
        engine = Engine(world())
        record = engine.tick(order)
        assert [(o.proposal_id, o.sequence) for o in record.outcomes] == [('first', 0), ('last', 1)]
        assert submitted[0].order == 10 ** 5000
        assert not hasattr(submitted[0], 'sequence')
        seen.add(record.digest())
    assert len(seen) == 1


def test_input_cannot_set_the_engine_sequence_keyword():
    with pytest.raises(TypeError):
        Proposal('p', 'A', sequence=0, operation='consume', params={'amount': 1})


def test_sequences_restart_at_each_tick_and_are_actor_local():
    engine = Engine(WorldState.genesis(balances={'A': 2, 'B': 2}))
    for tick in (0, 1):
        record = engine.tick([consume('a', 'A', 99, amount=1), consume('b', 'B', 500, amount=1)])
        assert {o.sequence for o in record.outcomes} == {0}
        assert record.tick == tick


@pytest.mark.parametrize('amount', [0, 1, -1, 999_999_999, 1_000_000_000, -1_000_000_000, 10 ** 100 + 123])
def test_canonical_bytes_match_existing_json_for_ordinary_values(amount):
    value = {'z': ['line\nquote"', '\\', '\u2603', None, amount], 'a': {'b': amount, 'a': -amount}}
    expected = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')
    assert canonical_bytes(value) == expected


@pytest.mark.parametrize('digits', [639, 640, 4299, 4300, 5000, 10000])
def test_large_signed_integer_digits_without_changing_global_policy(digits):
    limit = sys.get_int_max_str_digits()
    value = 10 ** digits
    expected = b'1' + b'0' * digits
    assert canonical_bytes(value) == expected
    assert canonical_bytes(-value) == b'-' + expected
    assert sys.get_int_max_str_digits() == limit


def test_huge_claim_and_consume_preserve_conservation_and_next_tick_boundary():
    amount = 10 ** 5000
    engine = Engine(WorldState.genesis(balances={'A': 0}, sources={'S': Source(amount, frozenset({'A'}))}))
    first = engine.tick([claim('claim', 'A', 0, sources={'S': amount}), consume('early', 'A', 1, amount=amount)])
    assert first.outcomes[0].accepted
    assert not first.outcomes[1].accepted
    assert first.next_state_digest == engine.state.digest()
    assert engine.state.total() == amount
    second = engine.tick([consume('later', 'A', 0, amount=amount)])
    assert second.outcomes[0].accepted
    assert engine.state.consumed == amount
    assert engine.state.total() == amount


@pytest.mark.parametrize('code, failures', [(1, []), (2, []), (2, ['test']), (3, []), (4, []), (5, []), (1, ['ERROR:collection']), (1, ['test', 'ERROR:teardown'])])
def test_invalid_mutation_execution_is_unknown(monkeypatch, tmp_path, capsys, code, failures):
    harness = isolated_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(harness, 'UNREACHABLE', {})
    monkeypatch.setattr(harness, 'run_suite', lambda label: (code, failures) if label.startswith('01-') else (0, []))
    assert harness.main() != 0
    output = capsys.readouterr().out
    assert 'UNKNOWN mutation results' in output
    assert '1 of 1 mutations were detected' not in output
    assert (tmp_path/'probe.py').read_text() == 'ORIGINAL'


def test_executed_failing_test_is_a_mutation_detection(monkeypatch, tmp_path, capsys):
    harness = isolated_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(harness, 'UNREACHABLE', {})
    monkeypatch.setattr(harness, 'run_suite', lambda label: (1, ['test_mutated_rule']) if label.startswith('01-') else (0, []))
    assert harness.main() == 0
    assert '1 of 1 mutations were detected' in capsys.readouterr().out
