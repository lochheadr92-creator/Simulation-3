"""Preserved adversarial assertions, integrated into the repair regression suite."""
from pathlib import Path
from itertools import product, permutations
import importlib.util
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
COPY = ROOT
sys.path.insert(0, str(COPY))
from kernel import Engine, Source, WorldState, Proposal, claim, consume, transfer

OBSERVATIONS = {}

@pytest.fixture(scope='session', autouse=True)
def save_observations(tmp_path_factory):
    yield
    (tmp_path_factory.mktemp('review-observations') / 'observations.json').write_text(json.dumps(OBSERVATIONS, indent=2), encoding='utf-8')

def basic_world():
    return WorldState.genesis(balances={'A': 2, 'B': 0})

def test_unknown_actors_with_duplicate_ids_are_order_independent():
    proposals = [consume('duplicate', 'GHOST_A', 0, amount=1), consume('duplicate', 'GHOST_B', 0, amount=1)]
    seen = []
    for ordering in permutations(proposals):
        engine = Engine(basic_world())
        record = engine.tick(ordering)
        seen.append({'digest': record.digest(), 'actors': [o.actor for o in record.outcomes],
                     'reasons': [o.reason for o in record.outcomes], 'state': engine.state.digest()})
    OBSERVATIONS['unknown_duplicate_ids'] = seen
    assert len({x['digest'] for x in seen}) == 1, 'Rejected proposal records depend on arrival order'

def test_unknown_actor_unique_ids_control():
    proposals = [consume('one', 'GHOST_A', 0, amount=1), consume('two', 'GHOST_B', 0, amount=1)]
    digests = [Engine(basic_world()).tick(ordering).digest() for ordering in permutations(proposals)]
    assert len(set(digests)) == 1

def test_diagnostic_callback_cannot_reenter_the_public_tick_api():
    class SteppingDiagnostics:
        engine = None
        fired = False
        def record(self, event, payload):
            if not self.fired:
                self.fired = True
                self.engine.tick([consume('diagnostic-spend', 'A', 0, amount=1)])

    sink = SteppingDiagnostics()
    observed = Engine(basic_world(), diagnostics=sink)
    sink.engine = observed
    quiet = Engine(basic_world())
    quiet_record = quiet.tick()
    observed_record = observed.tick()
    OBSERVATIONS['reentrant_diagnostics'] = {
        'quiet_tick': quiet.state.tick, 'observed_tick': observed.state.tick,
        'quiet_balance': quiet.state.balances['A'], 'observed_balance': observed.state.balances['A'],
        'returned_record_matches_current_state': observed_record.next_state_digest == observed.state.digest(),
        'returned_records_identical': quiet_record.digest() == observed_record.digest()}
    assert observed.state.digest() == quiet.state.digest(), 'Diagnostics changed canonical state through public reentry'

def test_payload_only_diagnostic_corruption_control():
    class Sink:
        def record(self, event, payload):
            payload.clear()
            raise RuntimeError('intentional')
    quiet = Engine(basic_world())
    observed = Engine(basic_world(), diagnostics=Sink())
    assert quiet.tick().digest() == observed.tick().digest()
    assert quiet.state.digest() == observed.state.digest()
    assert observed.diagnostics_failures == 1

def test_proposal_iterator_reentry_cannot_duplicate_accepted_source_claims():
    engine = Engine(WorldState.genesis(balances={'A': 0}, sources={'S': Source(1, frozenset({'A'}))}))
    records = []
    def proposals():
        records.append(engine.tick([claim('inner', 'A', 0, sources={'S': 1})]))
        yield claim('outer', 'A', 0, sources={'S': 1})
    error = None
    try:
        records.append(engine.tick(proposals()))
    except RuntimeError as caught:
        error = type(caught).__name__
    credits = sum(e.delta for r in records for o in r.outcomes if o.accepted for e in o.effects if e.account == 'actor:A')
    OBSERVATIONS['iterator_reentry'] = {'error': error, 'record_ticks': [r.tick for r in records],
        'credited_in_accepted_records': credits, 'final_tick': engine.state.tick,
        'final_balance': engine.state.balances['A'], 'final_source_stock': engine.state.sources['S'].stock}
    assert credits <= 1, 'Two accepted records credit the same one-unit source'

def test_normal_proposal_iterator_control():
    engine = Engine(WorldState.genesis(balances={'A': 0}, sources={'S': Source(1, frozenset({'A'}))}))
    record = engine.tick(p for p in [claim('take', 'A', 0, sources={'S': 1})])
    assert record.outcomes[0].accepted
    assert engine.state.balances['A'] == 1

def test_declared_unbounded_integer_state_has_a_canonical_identity():
    state = WorldState.genesis(balances={'A': 10 ** 5000})
    engine = Engine(state)
    try:
        record = engine.tick()
    except ValueError as error:
        OBSERVATIONS['large_integer'] = {'accepted_by_genesis': True, 'tick_after_error': engine.state.tick,
                                         'error': str(error), 'python_digit_limit': sys.get_int_max_str_digits()}
        raise
    assert record.next_state_digest == engine.state.digest()

def test_large_integer_below_serialisation_limit_control():
    engine = Engine(WorldState.genesis(balances={'A': 10 ** 100}))
    record = engine.tick([consume('spend', 'A', 0, amount=1)])
    assert record.outcomes[0].accepted
    assert engine.state.consumed == 1

def load_mutation_harness():
    path = COPY / 'evidence/stage-01/instrument/mutation_check.py'
    spec = importlib.util.spec_from_file_location('reviewed_mutation_harness', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_mutation_harness_must_not_count_runner_failure_as_detected(monkeypatch, tmp_path):
    harness = isolated_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(harness, 'MUTATIONS', harness.MUTATIONS[:1])
    monkeypatch.setattr(harness, 'UNREACHABLE', {})
    def fake_suite(label):
        return (2, []) if label.startswith('01-') else (0, [])
    monkeypatch.setattr(harness, 'run_suite', fake_suite)
    result = harness.main()
    OBSERVATIONS['harness_runner_failure'] = {'injected_mutant_exit': 2, 'identified_failed_tests': 0,
                                              'harness_exit': result}
    assert result != 0, 'Harness accepted an interrupted/failed test runner as mutation detection'

def test_mutation_harness_surviving_mutant_control(monkeypatch, tmp_path):
    harness = isolated_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(harness, 'MUTATIONS', harness.MUTATIONS[:1])
    monkeypatch.setattr(harness, 'UNREACHABLE', {})
    monkeypatch.setattr(harness, 'run_suite', lambda label: (0, []))
    assert harness.main() != 0

def test_exhaustive_small_contested_transactions():
    cases = 0
    source_sets = [('S1',), ('S2',), ('S1', 'S2')]
    for s1, s2, a, b, tick, asrc, bsrc, aq, bq in product(range(3), range(3), range(2), range(2), range(2), source_sets, source_sets, (1, 2), (1, 2)):
        state = WorldState.genesis(tick=tick, balances={'A': a, 'B': b}, sources={
            'S1': Source(s1, frozenset({'A', 'B'})), 'S2': Source(s2, frozenset({'A', 'B'}))})
        proposals = [claim('a', 'A', 0, sources={s: aq for s in asrc}), claim('b', 'B', 0, sources={s: bq for s in bsrc})]
        records = []
        for ordered in (proposals, list(reversed(proposals))):
            engine = Engine(state)
            record = engine.tick(ordered)
            assert engine.state.total() == state.total()
            assert all(n >= 0 for n in engine.state.balances.values())
            assert all(s.stock >= 0 for s in engine.state.sources.values())
            spent = {}
            for outcome in record.outcomes:
                assert sum(e.delta for e in outcome.effects) == 0
                for effect in outcome.effects:
                    if effect.delta < 0:
                        spent[effect.account] = spent.get(effect.account, 0) - effect.delta
            assert spent.get('source:S1', 0) <= s1
            assert spent.get('source:S2', 0) <= s2
            records.append(record.digest())
        assert records[0] == records[1]
        cases += 1
    OBSERVATIONS['exhaustive_contention'] = {'cases': cases, 'orderings_per_case': 2, 'checks': 'stock availability, nonnegative balances, conservation, canonical ordering'}


def isolated_harness(monkeypatch, tmp_path):
    harness = load_mutation_harness()
    monkeypatch.setattr(harness, 'ROOT', tmp_path)
    monkeypatch.setattr(harness, 'MUTATIONS', [('probe', 'controlled mutation', 'probe.py', 'ORIGINAL', 'MUTANT')])
    (tmp_path / 'probe.py').write_text('ORIGINAL', encoding='utf-8')
    return harness
