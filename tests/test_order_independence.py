"""A4 - reordering input maps or the proposal collection changes nothing.

Every ordering is generated, not sampled, so a surviving dependence on
incidental iteration order cannot hide in an untried permutation.
"""

from __future__ import annotations

from itertools import permutations

from kernel import Engine, Source, WorldState, claim, consume, transfer

from tests.support import genesis, source


def build_state(balance_order, source_order, authorised_order) -> WorldState:
    balances = {actor: amount for actor, amount in balance_order}
    sources = {
        "S1": Source(stock=1, authorised=authorised_order),
        "S2": Source(stock=2, authorised=("B", "C")),
    }
    ordered_sources = {name: sources[name] for name in source_order}
    return WorldState.genesis(tick=0, balances=balances, sources=ordered_sources)


def build_proposals(order):
    catalogue = {
        "p1": claim("p1", "A", 0, sources={"S1": 1}),
        "p2": claim("p2", "B", 0, sources={"S1": 1, "S2": 1}),
        "p3": consume("p3", "C", 0, amount=1),
        "p4": transfer("p4", "A", 1, to="B", amount=2),
    }
    return [catalogue[name] for name in order]


BALANCES = (("A", 2), ("B", 0), ("C", 1))
SOURCE_NAMES = ("S1", "S2")
AUTHORISED = ("A", "B")
PROPOSAL_NAMES = ("p1", "p2", "p3", "p4")


def run(balance_order, source_order, authorised_order, proposal_order):
    engine = Engine(build_state(balance_order, source_order, authorised_order))
    record = engine.tick(build_proposals(proposal_order))
    return engine.state.digest(), record.digest()


def test_every_permutation_of_the_inputs_gives_one_canonical_result():
    results = set()
    runs = 0
    for balance_order in permutations(BALANCES):
        for source_order in permutations(SOURCE_NAMES):
            for authorised_order in permutations(AUTHORISED):
                for proposal_order in permutations(PROPOSAL_NAMES):
                    results.add(run(balance_order, source_order, authorised_order, proposal_order))
                    runs += 1

    assert runs == 6 * 2 * 2 * 24
    assert len(results) == 1


def test_the_recorded_outcomes_are_themselves_order_independent():
    baseline = None
    for proposal_order in permutations(PROPOSAL_NAMES):
        engine = Engine(build_state(BALANCES, SOURCE_NAMES, AUTHORISED))
        record = engine.tick(build_proposals(proposal_order))
        seen = tuple((outcome.proposal_id, outcome.reason) for outcome in record.outcomes)
        if baseline is None:
            baseline = seen
        assert seen == baseline

    assert baseline == (
        ("p1", "accepted"),
        ("p4", "accepted"),
        ("p2", "denied_insufficient_source"),
        ("p3", "accepted"),
    )


def test_permuting_a_claim_source_map_changes_nothing():
    forward = Engine(genesis(balances={"A": 0}, sources={"S1": source(1, "A"), "S2": source(1, "A")}))
    reverse = Engine(genesis(balances={"A": 0}, sources={"S1": source(1, "A"), "S2": source(1, "A")}))

    forward_record = forward.tick([claim("grab", "A", 0, sources={"S1": 1, "S2": 1})])
    reverse_record = reverse.tick([claim("grab", "A", 0, sources={"S2": 1, "S1": 1})])

    assert forward_record.digest() == reverse_record.digest()
    assert forward.state.digest() == reverse.state.digest()


def test_the_effects_of_a_multi_source_claim_are_recorded_in_a_declared_order():
    engine = Engine(genesis(balances={"A": 0}, sources={"S1": source(1, "A"), "S2": source(1, "A")}))

    record = engine.tick([claim("grab", "A", 0, sources={"S2": 1, "S1": 1})])

    assert [effect.account for effect in record.outcomes[0].effects] == [
        "actor:A",
        "source:S1",
        "source:S2",
    ]


def test_the_digest_still_notices_a_real_difference():
    """Control: the digests above are not constant."""
    base = Engine(genesis(balances={"A": 0}, sources={"S": source(1, "A")}))
    other = Engine(genesis(balances={"A": 0}, sources={"S": source(2, "A")}))

    base_record = base.tick([claim("grab", "A", 0, sources={"S": 1})])
    other_record = other.tick([claim("grab", "A", 0, sources={"S": 1})])

    assert base.state.digest() != other.state.digest()
    assert base_record.digest() != other_record.digest()
