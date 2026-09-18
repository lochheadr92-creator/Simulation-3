"""A8 - diagnostics on or off, and repeated execution, give identical results.

Optional diagnostic capture is inert: it is handed a fresh canonical copy after
each decision is already fixed, and nothing it does can reach canonical history.
"""

from __future__ import annotations

import pytest

from kernel import (
    CollectingDiagnostics,
    Engine,
    canonical,
    claim,
    consume,
    transfer,
)

from tests.support import genesis, source


def scenario():
    return genesis(
        balances={"A": 2, "B": 0, "C": 1},
        sources={"S1": source(1, "A", "B"), "S2": source(2, "B", "C")},
    )


def proposal_batch():
    return [
        claim("p1", "A", 0, sources={"S1": 1}),
        claim("p2", "B", 0, sources={"S1": 1, "S2": 1}),
        consume("p3", "C", 0, amount=1),
        transfer("p4", "A", 1, to="B", amount=2),
    ]


def run(diagnostics=None, ticks=3):
    engine = Engine(scenario(), diagnostics=diagnostics)
    digests = []
    for _ in range(ticks):
        record = engine.tick(proposal_batch())
        digests.append((record.digest(), engine.state.digest()))
    return tuple(digests)


def test_diagnostics_on_and_off_produce_identical_canonical_results():
    without = run(diagnostics=None)
    sink = CollectingDiagnostics()
    with_sink = run(diagnostics=sink)

    assert with_sink == without
    assert sink.events, "the collecting sink recorded nothing, so the comparison proves nothing"


def test_repeated_identical_execution_produces_identical_canonical_results():
    assert run() == run()
    assert run(diagnostics=CollectingDiagnostics()) == run(diagnostics=CollectingDiagnostics())


class HostileDiagnostics:
    """Attempts to corrupt whatever it is handed, and to fail loudly."""

    def __init__(self):
        self.calls = 0

    def record(self, event, payload):
        self.calls += 1
        payload["tick"] = 9999
        payload["outcomes"] = []
        payload.clear()
        raise RuntimeError("diagnostics failure")


def test_a_hostile_diagnostics_sink_cannot_change_canonical_results():
    hostile = HostileDiagnostics()
    engine = Engine(scenario(), diagnostics=hostile)

    hostile_digests = []
    for _ in range(3):
        record = engine.tick(proposal_batch())
        hostile_digests.append((record.digest(), engine.state.digest()))

    assert hostile.calls == 3
    assert tuple(hostile_digests) == run()


def test_a_failing_diagnostics_sink_is_counted_rather_than_hidden():
    hostile = HostileDiagnostics()
    engine = Engine(scenario(), diagnostics=hostile)

    engine.tick(proposal_batch())

    assert engine.diagnostics_failures == 1


def test_the_canonical_form_refuses_floats():
    with pytest.raises(canonical.CanonicalError):
        canonical.canonical_bytes({"amount": 1.5})
    with pytest.raises(canonical.CanonicalError):
        canonical.canonical_bytes({"amount": 1.0})


def test_the_canonical_form_refuses_booleans():
    with pytest.raises(canonical.CanonicalError):
        canonical.canonical_bytes({"flag": True})


def test_the_canonical_form_is_independent_of_mapping_order():
    forward = canonical.canonical_bytes({"a": 1, "b": {"x": 1, "y": 2}})
    reverse = canonical.canonical_bytes({"b": {"y": 2, "x": 1}, "a": 1})

    assert forward == reverse
    assert forward == b'{"a":1,"b":{"x":1,"y":2}}'


def test_a_state_digest_is_independent_of_input_map_order():
    forward = genesis(balances={"A": 1, "B": 2}, sources={"S1": source(1, "A", "B")})
    reverse = genesis(balances={"B": 2, "A": 1}, sources={"S1": source(1, "B", "A")})

    assert forward.digest() == reverse.digest()


def test_the_record_carries_the_declared_versions_and_state_identities():
    from kernel import ENGINE_VERSION, SCHEMA_VERSION

    state = scenario()
    engine = Engine(state)
    prior_digest = state.digest()

    record = engine.tick(proposal_batch())

    assert record.engine_version == ENGINE_VERSION
    assert record.schema_version == SCHEMA_VERSION
    assert record.prior_state_digest == prior_digest
    assert record.next_state_digest == engine.state.digest()


def test_the_engine_allocates_no_identity_of_its_own_in_this_slice():
    """Diagnostics cannot perturb identity allocation because there is none yet.

    Recorded as a limitation in the stage record: this is a weaker check than
    the roadmap's clause, which slice 1c must satisfy properly.
    """
    engine = Engine(scenario())
    record = engine.tick(proposal_batch())

    submitted = {proposal.proposal_id for proposal in proposal_batch()}
    assert {outcome.proposal_id for outcome in record.outcomes} == submitted
