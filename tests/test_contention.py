"""A1 - two authorised claimants, one unit, exactly one winner.

The proof object of slice 1a. One shared source holds a single unit and two
actors authorised to claim it each propose to take it.
"""

from __future__ import annotations

from kernel import Engine, Reason, claim

from tests.support import accepted_ids, balances_of, denied_ids, genesis, reason_of, source, stocks_of


def contested_world(tick: int = 0):
    return genesis(
        tick=tick,
        balances={"A": 0, "B": 0},
        sources={"S": source(1, "A", "B")},
    )


def test_two_authorised_claims_on_one_unit_produce_exactly_one_winner():
    state = contested_world()
    engine = Engine(state)

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert accepted_ids(record) == ("pA",)
    assert denied_ids(record) == ("pB",)
    assert balances_of(engine.state) == {"A": 1, "B": 0}
    assert stocks_of(engine.state) == {"S": 0}


def test_the_single_unit_is_credited_exactly_once():
    engine = Engine(contested_world())

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    credits = [
        effect
        for outcome in record.outcomes
        for effect in outcome.effects
        if effect.delta > 0
    ]
    assert len(credits) == 1
    assert credits[0].delta == 1


def test_the_losing_claimant_carries_an_explicit_denial_reason():
    engine = Engine(contested_world())

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert reason_of(record, "pA") == Reason.ACCEPTED
    assert reason_of(record, "pB") == Reason.DENIED_INSUFFICIENT_SOURCE


def test_every_submitted_proposal_appears_in_the_record_exactly_once():
    engine = Engine(contested_world())

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert [outcome.proposal_id for outcome in record.outcomes] == ["pA", "pB"]


def test_a_denied_claim_stages_no_effects():
    engine = Engine(contested_world())

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    denied = [outcome for outcome in record.outcomes if not outcome.accepted]
    assert [outcome.effects for outcome in denied] == [()]


def test_contended_tick_conserves_the_declared_total():
    state = contested_world()
    engine = Engine(state)

    engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert state.total() == 1
    assert engine.state.total() == state.total()


def test_no_balance_or_stock_goes_negative_under_contention():
    engine = Engine(contested_world())

    engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert all(amount >= 0 for amount in engine.state.balances.values())
    assert all(src.stock >= 0 for src in engine.state.sources.values())
    assert engine.state.consumed >= 0


def test_one_actor_cannot_take_the_same_unit_twice_in_one_tick():
    engine = Engine(genesis(balances={"A": 0}, sources={"S": source(1, "A")}))

    record = engine.tick(
        [
            claim("first", "A", 0, sources={"S": 1}),
            claim("second", "A", 1, sources={"S": 1}),
        ]
    )

    assert reason_of(record, "first") == Reason.ACCEPTED
    assert reason_of(record, "second") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert balances_of(engine.state) == {"A": 1}
    assert stocks_of(engine.state) == {"S": 0}


def test_an_uncontested_claim_is_accepted():
    """Null control: the same machinery must not deny an ordinary claim."""
    engine = Engine(genesis(balances={"A": 0}, sources={"S": source(1, "A")}))

    record = engine.tick([claim("only", "A", 0, sources={"S": 1})])

    assert reason_of(record, "only") == Reason.ACCEPTED
    assert balances_of(engine.state) == {"A": 1}


def test_a_tick_with_no_proposals_changes_nothing_but_the_tick_number():
    """Null control: an empty proposal collection."""
    state = genesis(balances={"A": 3}, sources={"S": source(2, "A")})
    engine = Engine(state)

    record = engine.tick([])

    assert record.outcomes == ()
    assert balances_of(engine.state) == balances_of(state)
    assert stocks_of(engine.state) == stocks_of(state)
    assert engine.state.tick == state.tick + 1
