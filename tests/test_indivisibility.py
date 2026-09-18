"""A3 - insufficient stock rejects an indivisible transaction, with no partial credit.

A unit is indivisible and a transaction is all-or-nothing, so a shortfall must
produce a denial rather than a smaller transfer.
"""

from __future__ import annotations

from kernel import Engine, Proposal, Reason, claim, consume, transfer

from tests.support import balances_of, genesis, reason_of, source, stocks_of


def test_a_claim_larger_than_the_source_is_denied_without_partial_credit():
    state = genesis(balances={"A": 0}, sources={"S": source(1, "A")})
    engine = Engine(state)

    record = engine.tick([claim("greedy", "A", 0, sources={"S": 2})])

    assert reason_of(record, "greedy") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert stocks_of(engine.state) == {"S": 1}
    assert balances_of(engine.state) == {"A": 0}
    assert engine.state.total() == state.total()


def test_a_consume_larger_than_the_balance_is_denied_without_partial_credit():
    state = genesis(balances={"A": 1})
    engine = Engine(state)

    record = engine.tick([consume("feast", "A", 0, amount=2)])

    assert reason_of(record, "feast") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 1}
    assert engine.state.consumed == 0
    assert engine.state.total() == state.total()


def test_a_transfer_larger_than_the_balance_is_denied_without_partial_credit():
    state = genesis(balances={"A": 1, "B": 0})
    engine = Engine(state)

    record = engine.tick([transfer("give", "A", 0, to="B", amount=2)])

    assert reason_of(record, "give") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 1, "B": 0}


def test_a_partly_available_multi_source_claim_is_denied_whole():
    state = genesis(
        balances={"A": 0},
        sources={"FULL": source(5, "A"), "THIN": source(1, "A")},
    )
    engine = Engine(state)

    record = engine.tick([claim("sweep", "A", 0, sources={"FULL": 1, "THIN": 2})])

    assert reason_of(record, "sweep") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert stocks_of(engine.state) == {"FULL": 5, "THIN": 1}
    assert balances_of(engine.state) == {"A": 0}


def test_an_exactly_sufficient_claim_is_accepted():
    """Control: the boundary is inclusive, so taking the whole stock works."""
    engine = Engine(genesis(balances={"A": 0}, sources={"S": source(2, "A")}))

    record = engine.tick([claim("all", "A", 0, sources={"S": 2})])

    assert reason_of(record, "all") == Reason.ACCEPTED
    assert stocks_of(engine.state) == {"S": 0}
    assert balances_of(engine.state) == {"A": 2}


def test_a_zero_amount_is_denied_rather_than_treated_as_a_no_op():
    state = genesis(balances={"A": 1}, sources={"S": source(1, "A")})
    engine = Engine(state)

    record = engine.tick(
        [
            claim("zero_claim", "A", 0, sources={"S": 0}),
            consume("zero_consume", "A", 1, amount=0),
        ]
    )

    assert reason_of(record, "zero_claim") == Reason.DENIED_NON_POSITIVE_AMOUNT
    assert reason_of(record, "zero_consume") == Reason.DENIED_NON_POSITIVE_AMOUNT
    assert balances_of(engine.state) == {"A": 1}
    assert stocks_of(engine.state) == {"S": 1}


def test_a_negative_amount_is_denied_rather_than_reversing_a_transaction():
    state = genesis(balances={"A": 1, "B": 3})
    engine = Engine(state)

    record = engine.tick([transfer("pull", "A", 0, to="B", amount=-2)])

    assert reason_of(record, "pull") == Reason.DENIED_NON_POSITIVE_AMOUNT
    assert balances_of(engine.state) == {"A": 1, "B": 3}


def test_a_fractional_amount_is_denied_rather_than_rounded():
    state = genesis(balances={"A": 3})
    engine = Engine(state)

    record = engine.tick([consume("half", "A", 0, amount=1.5)])

    assert reason_of(record, "half") == Reason.DENIED_NON_INTEGER_AMOUNT
    assert balances_of(engine.state) == {"A": 3}
    assert engine.state.consumed == 0


def test_a_whole_valued_float_is_still_denied():
    """1.0 is not an integer unit count; accepting it would admit float arithmetic."""
    engine = Engine(genesis(balances={"A": 3}))

    record = engine.tick([consume("one_point_oh", "A", 0, amount=1.0)])

    assert reason_of(record, "one_point_oh") == Reason.DENIED_NON_INTEGER_AMOUNT
    assert engine.state.consumed == 0


def test_a_boolean_amount_is_denied_even_though_python_calls_it_an_integer():
    engine = Engine(genesis(balances={"A": 3}))

    record = engine.tick([consume("truthy", "A", 0, amount=True)])

    assert reason_of(record, "truthy") == Reason.DENIED_NON_INTEGER_AMOUNT
    assert engine.state.consumed == 0


def test_malformed_parameters_are_denied():
    state = genesis(balances={"A": 3}, sources={"S": source(1, "A")})
    engine = Engine(state)

    record = engine.tick(
        [
            Proposal("no_amount", "A", 0, "consume", {}),
            Proposal("no_sources", "A", 1, "claim", {"sources": {}}),
            Proposal("wrong_shape", "A", 2, "claim", {"sources": 1}),
            Proposal("no_target", "A", 3, "transfer", {"amount": 1}),
        ]
    )

    for proposal_id in ("no_amount", "no_sources", "wrong_shape", "no_target"):
        assert reason_of(record, proposal_id) == Reason.DENIED_MALFORMED_PARAMS

    assert balances_of(engine.state) == balances_of(state)
    assert stocks_of(engine.state) == stocks_of(state)
