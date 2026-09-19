"""Proposal identity and the actor-local sequence.

The roadmap requires that all proposals sharing a duplicate identity are
rejected, regardless of which arrived first. The actor-local sequence carries
the same requirement: if an actor declares two proposals at the same position in
its own order, the engine has no declared way to order them and rejects both
rather than picking one by arrival.

These rules are what let the resolution order be derived from content alone, so
they are part of what A4 rests on.
"""

from __future__ import annotations

from kernel import Engine, Reason, claim, consume, transfer

from tests.support import accepted_ids, balances_of, genesis, reason_of, source, stocks_of


def test_all_proposals_sharing_an_identity_are_rejected():
    state = genesis(balances={"A": 0, "B": 0}, sources={"S": source(2, "A", "B")})
    engine = Engine(state)

    record = engine.tick(
        [
            claim("same", "A", 0, sources={"S": 1}),
            claim("same", "B", 0, sources={"S": 1}),
        ]
    )

    outcomes = record.outcomes_for("same")
    assert len(outcomes) == 2
    assert {outcome.reason for outcome in outcomes} == {Reason.DENIED_DUPLICATE_PROPOSAL_ID}
    assert stocks_of(engine.state) == {"S": 2}
    assert balances_of(engine.state) == {"A": 0, "B": 0}


def test_a_duplicate_identity_is_rejected_whichever_arrived_first():
    forward = Engine(genesis(balances={"A": 0, "B": 0}, sources={"S": source(2, "A", "B")}))
    reverse = Engine(genesis(balances={"A": 0, "B": 0}, sources={"S": source(2, "A", "B")}))

    first = claim("same", "A", 0, sources={"S": 1})
    second = claim("same", "B", 0, sources={"S": 1})

    forward_record = forward.tick([first, second])
    reverse_record = reverse.tick([second, first])

    assert accepted_ids(forward_record) == ()
    assert accepted_ids(reverse_record) == ()
    assert forward_record.digest() == reverse_record.digest()


def test_a_duplicate_identity_does_not_take_an_unrelated_proposal_with_it():
    engine = Engine(genesis(balances={"A": 0, "B": 0}, sources={"S": source(3, "A", "B")}))

    record = engine.tick(
        [
            claim("same", "A", 0, sources={"S": 1}),
            claim("same", "A", 1, sources={"S": 1}),
            claim("distinct", "B", 0, sources={"S": 1}),
        ]
    )

    assert accepted_ids(record) == ("distinct",)
    assert stocks_of(engine.state) == {"S": 2}
    assert balances_of(engine.state) == {"A": 0, "B": 1}


def test_an_actor_cannot_declare_two_proposals_at_the_same_sequence():
    engine = Engine(genesis(balances={"A": 2, "B": 0}))

    record = engine.tick(
        [
            transfer("give", "A", 0, to="B", amount=1),
            consume("eat", "A", 0, amount=1),
        ]
    )

    assert reason_of(record, "give") == Reason.DENIED_DUPLICATE_ACTOR_SEQUENCE
    assert reason_of(record, "eat") == Reason.DENIED_DUPLICATE_ACTOR_SEQUENCE
    assert balances_of(engine.state) == {"A": 2, "B": 0}
    assert engine.state.consumed == 0


def test_two_actors_may_share_a_sequence_because_it_is_actor_local():
    """Control: the sequence orders one actor's own proposals, not the world's."""
    engine = Engine(genesis(balances={"A": 1, "B": 1, "C": 0}))

    record = engine.tick(
        [
            transfer("a_gives", "A", 0, to="C", amount=1),
            transfer("b_gives", "B", 0, to="C", amount=1),
        ]
    )

    assert accepted_ids(record) == ("a_gives", "b_gives")
    assert balances_of(engine.state) == {"A": 0, "B": 0, "C": 2}


def test_a_duplicate_sequence_is_rejected_whichever_arrived_first():
    forward = Engine(genesis(balances={"A": 2, "B": 0}))
    reverse = Engine(genesis(balances={"A": 2, "B": 0}))

    first = transfer("give", "A", 0, to="B", amount=1)
    second = consume("eat", "A", 0, amount=1)

    forward_record = forward.tick([first, second])
    reverse_record = reverse.tick([second, first])

    assert accepted_ids(forward_record) == ()
    assert accepted_ids(reverse_record) == ()
    assert forward_record.digest() == reverse_record.digest()


def test_a_sequence_gap_is_not_an_error():
    """Input order may be sparse; settlement assigns dense output sequences."""
    engine = Engine(genesis(balances={"A": 2, "B": 0}))

    record = engine.tick(
        [
            consume("later", "A", 90, amount=1),
            transfer("earlier", "A", 7, to="B", amount=1),
        ]
    )

    assert [outcome.proposal_id for outcome in record.outcomes] == ["earlier", "later"]
    assert [outcome.sequence for outcome in record.outcomes] == [0, 1]
    assert accepted_ids(record) == ("earlier", "later")
    assert balances_of(engine.state) == {"A": 0, "B": 1}
    assert engine.state.consumed == 1


def test_every_copy_of_a_duplicate_stays_in_the_record():
    engine = Engine(genesis(balances={"A": 0, "B": 0, "C": 0}, sources={"S": source(3, "A", "B", "C")}))

    record = engine.tick(
        [
            claim("same", "A", 0, sources={"S": 1}),
            claim("same", "B", 0, sources={"S": 1}),
            claim("same", "C", 0, sources={"S": 1}),
        ]
    )

    assert len(record.outcomes) == 3
    assert len(record.outcomes_for("same")) == 3
