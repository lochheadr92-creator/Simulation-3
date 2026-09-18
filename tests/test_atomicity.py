"""A2 - an invalid or unauthorised transaction cannot partially commit.

A single-debit transaction cannot show all-or-nothing settlement, because it has
no second leg to leave behind. The declarations therefore allow a claim to name
several sources, and these tests make one leg fail while the other would have
succeeded on its own.
"""

from __future__ import annotations

import pytest

from kernel import Effect, Engine, Proposal, Reason, claim, consume, proposals, transfer

from tests.support import balances_of, genesis, reason_of, source, stocks_of


def two_source_world(tick: int = 0):
    return genesis(
        tick=tick,
        balances={"A": 0, "B": 0},
        sources={
            "OPEN": source(1, "A", "B"),
            "CLOSED": source(1, "B"),
        },
    )


def test_an_unauthorised_leg_prevents_the_authorised_leg_from_committing():
    state = two_source_world()
    engine = Engine(state)

    record = engine.tick([claim("grab", "A", 0, sources={"OPEN": 1, "CLOSED": 1})])

    assert reason_of(record, "grab") == Reason.DENIED_UNAUTHORISED
    assert stocks_of(engine.state) == {"OPEN": 1, "CLOSED": 1}
    assert balances_of(engine.state) == {"A": 0, "B": 0}
    assert engine.state.total() == state.total()


def test_the_authorised_leg_alone_would_have_succeeded():
    """Control for the test above: OPEN really was claimable by A."""
    engine = Engine(two_source_world())

    record = engine.tick([claim("grab", "A", 0, sources={"OPEN": 1})])

    assert reason_of(record, "grab") == Reason.ACCEPTED
    assert stocks_of(engine.state) == {"OPEN": 0, "CLOSED": 1}
    assert balances_of(engine.state) == {"A": 1, "B": 0}


def test_a_denied_transaction_stages_no_effects_at_all():
    engine = Engine(two_source_world())

    record = engine.tick([claim("grab", "A", 0, sources={"OPEN": 1, "CLOSED": 1})])

    assert record.outcomes[0].effects == ()


def test_losing_one_leg_to_contention_leaves_the_other_leg_untouched():
    """B takes the only CLOSED unit first, so A's two-source claim fails whole."""
    state = genesis(
        tick=0,
        balances={"A": 0, "B": 0},
        sources={"OPEN": source(1, "A", "B"), "CLOSED": source(1, "A", "B")},
    )
    engine = Engine(state)

    record = engine.tick(
        [
            # A resolves first at tick 0 and asks for both units.
            claim("wide", "A", 0, sources={"OPEN": 1, "CLOSED": 1}),
            claim("narrow", "B", 0, sources={"CLOSED": 1}),
        ]
    )

    assert reason_of(record, "wide") == Reason.ACCEPTED
    assert reason_of(record, "narrow") == Reason.DENIED_INSUFFICIENT_SOURCE

    # Now the same contention with the rotation reversed: B wins CLOSED first,
    # and A's wide claim must leave OPEN alone rather than half-commit.
    engine = Engine(
        genesis(
            tick=1,
            balances={"A": 0, "B": 0},
            sources={"OPEN": source(1, "A", "B"), "CLOSED": source(1, "A", "B")},
        )
    )

    record = engine.tick(
        [
            claim("wide", "A", 0, sources={"OPEN": 1, "CLOSED": 1}),
            claim("narrow", "B", 0, sources={"CLOSED": 1}),
        ]
    )

    assert reason_of(record, "narrow") == Reason.ACCEPTED
    assert reason_of(record, "wide") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert stocks_of(engine.state) == {"OPEN": 1, "CLOSED": 0}
    assert balances_of(engine.state) == {"A": 0, "B": 1}


def test_an_unauthorised_single_source_claim_changes_nothing():
    state = two_source_world()
    engine = Engine(state)

    record = engine.tick([claim("grab", "A", 0, sources={"CLOSED": 1})])

    assert reason_of(record, "grab") == Reason.DENIED_UNAUTHORISED
    assert stocks_of(engine.state) == stocks_of(state)
    assert balances_of(engine.state) == balances_of(state)


def test_a_proposal_from_an_actor_outside_the_roster_is_denied():
    state = two_source_world()
    engine = Engine(state)

    record = engine.tick([claim("grab", "GHOST", 0, sources={"OPEN": 1})])

    assert reason_of(record, "grab") == Reason.DENIED_UNKNOWN_ACTOR
    assert stocks_of(engine.state) == stocks_of(state)
    assert balances_of(engine.state) == balances_of(state)


def test_a_claim_naming_an_unknown_source_commits_nothing():
    state = two_source_world()
    engine = Engine(state)

    record = engine.tick([claim("grab", "A", 0, sources={"OPEN": 1, "NOWHERE": 1})])

    assert reason_of(record, "grab") == Reason.DENIED_UNKNOWN_SOURCE
    assert stocks_of(engine.state) == stocks_of(state)
    assert balances_of(engine.state) == balances_of(state)


def test_a_transfer_to_an_unknown_actor_commits_nothing():
    state = genesis(balances={"A": 1, "B": 0})
    engine = Engine(state)

    record = engine.tick([transfer("give", "A", 0, to="GHOST", amount=1)])

    assert reason_of(record, "give") == Reason.DENIED_UNKNOWN_ACTOR
    assert balances_of(engine.state) == {"A": 1, "B": 0}
    assert engine.state.total() == state.total()


def test_a_self_transfer_is_denied():
    state = genesis(balances={"A": 1})
    engine = Engine(state)

    record = engine.tick([transfer("give", "A", 0, to="A", amount=1)])

    assert reason_of(record, "give") == Reason.DENIED_SELF_TRANSFER
    assert balances_of(engine.state) == {"A": 1}


def test_an_unknown_operation_is_denied():
    state = genesis(balances={"A": 1})
    engine = Engine(state)

    record = engine.tick(
        [Proposal("odd", "A", 0, "teleport", {"amount": 1})]
    )

    assert reason_of(record, "odd") == Reason.DENIED_UNKNOWN_OPERATION
    assert balances_of(engine.state) == {"A": 1}


def test_nothing_may_debit_the_consumption_sink(monkeypatch):
    """The sink is credit only: units leave circulation and never come back."""

    def raid(proposal):
        amount = proposal.params["amount"]
        return (Effect("sink:consumed", -amount), Effect("actor:" + proposal.actor, amount))

    monkeypatch.setitem(proposals.EXPANDERS, "raid", raid)

    state = genesis(balances={"A": 0}, consumed=5)
    engine = Engine(state)

    record = engine.tick([Proposal("raid", "A", 0, "raid", {"amount": 3})])

    assert reason_of(record, "raid") == Reason.DENIED_UNAUTHORISED
    assert engine.state.consumed == 5
    assert balances_of(engine.state) == {"A": 0}


def test_an_unbalanced_transaction_is_refused_by_the_integrity_rail(monkeypatch):
    """Adversarial case: an operation that would mint a unit from nowhere."""

    def mint(proposal):
        return (Effect("actor:" + proposal.actor, proposal.params["amount"]),)

    monkeypatch.setitem(proposals.EXPANDERS, "mint", mint)

    state = genesis(balances={"A": 0}, sources={"OPEN": source(1, "A")})
    engine = Engine(state)

    record = engine.tick([Proposal("mint", "A", 0, "mint", {"amount": 7})])

    assert reason_of(record, "mint") == Reason.DENIED_UNBALANCED_EFFECTS
    assert balances_of(engine.state) == {"A": 0}
    assert engine.state.total() == state.total()


def test_a_balanced_but_unauthorised_transfer_of_another_actors_stock_is_denied(monkeypatch):
    """Adversarial case: an operation that spends an account it does not own."""

    def steal(proposal):
        amount = proposal.params["amount"]
        victim = proposal.params["from"]
        return (Effect("actor:" + victim, -amount), Effect("actor:" + proposal.actor, amount))

    monkeypatch.setitem(proposals.EXPANDERS, "steal", steal)

    state = genesis(balances={"A": 0, "B": 4})
    engine = Engine(state)

    record = engine.tick([Proposal("steal", "A", 0, "steal", {"amount": 4, "from": "B"})])

    assert reason_of(record, "steal") == Reason.DENIED_UNAUTHORISED
    assert balances_of(engine.state) == {"A": 0, "B": 4}


def test_settlement_is_the_only_write_path_to_a_balance():
    """There is no public mutator anywhere on the state objects."""
    state = genesis(balances={"A": 1}, sources={"S": source(1, "A")})

    for obj in (state, state.sources["S"]):
        writable = [
            name
            for name in dir(obj)
            if not name.startswith("_") and name.startswith(("set_", "add_", "credit", "debit", "apply"))
        ]
        assert writable == []

    with pytest.raises(Exception):
        state.balances["A"] = 99


def test_a_denied_transaction_does_not_consume_availability_for_a_later_one():
    """Rejection leaves availability unchanged, so the next proposal still fits."""
    engine = Engine(genesis(balances={"A": 0}, sources={"OPEN": source(1, "A"), "CLOSED": source(1, "B")}))

    record = engine.tick(
        [
            claim("doomed", "A", 0, sources={"OPEN": 1, "CLOSED": 1}),
            claim("modest", "A", 1, sources={"OPEN": 1}),
        ]
    )

    assert reason_of(record, "doomed") == Reason.DENIED_UNAUTHORISED
    assert reason_of(record, "modest") == Reason.ACCEPTED
    assert balances_of(engine.state) == {"A": 1}


def test_consume_of_an_unknown_actor_is_denied():
    state = genesis(balances={"A": 1})
    engine = Engine(state)

    record = engine.tick([consume("eat", "GHOST", 0, amount=1)])

    assert reason_of(record, "eat") == Reason.DENIED_UNKNOWN_ACTOR
    assert engine.state.consumed == 0
