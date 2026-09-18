"""A6 - the roadmap's A to B transfer/consume fixture.

"A owns one unit, B owns none. At T, A to B is A's first proposal and is
accepted. A's subsequent claim on that unit is denied. B's consume proposal at T
is denied regardless of resolver order. At T plus one, B may consume if the unit
remains held."

Both resolver orders are exercised: at tick 0 the rotation puts A first, at tick
1 it puts B first.
"""

from __future__ import annotations

import pytest

from kernel import Engine, Reason, claim, consume, transfer

from tests.support import accepted_ids, balances_of, genesis, reason_of, source, stocks_of


@pytest.mark.parametrize("start_tick", [0, 1])
def test_the_roadmap_credit_fixture(start_tick):
    state = genesis(tick=start_tick, balances={"A": 1, "B": 0})
    engine = Engine(state)

    record = engine.tick(
        [
            transfer("a_gives", "A", 0, to="B", amount=1),
            consume("a_spends_again", "A", 1, amount=1),
            consume("b_spends_early", "B", 0, amount=1),
        ]
    )

    assert reason_of(record, "a_gives") == Reason.ACCEPTED
    assert reason_of(record, "a_spends_again") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert reason_of(record, "b_spends_early") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 0, "B": 1}
    assert engine.state.consumed == 0
    assert engine.state.total() == state.total() == 1

    next_record = engine.tick([consume("b_spends_later", "B", 0, amount=1)])

    assert reason_of(next_record, "b_spends_later") == Reason.ACCEPTED
    assert balances_of(engine.state) == {"A": 0, "B": 0}
    assert engine.state.consumed == 1
    assert engine.state.total() == 1


@pytest.mark.parametrize("start_tick", [0, 1])
def test_the_giver_cannot_spend_the_same_unit_twice_by_transferring_it_again(start_tick):
    engine = Engine(genesis(tick=start_tick, balances={"A": 1, "B": 0, "C": 0}))

    record = engine.tick(
        [
            transfer("to_b", "A", 0, to="B", amount=1),
            transfer("to_c", "A", 1, to="C", amount=1),
        ]
    )

    assert reason_of(record, "to_b") == Reason.ACCEPTED
    assert reason_of(record, "to_c") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 0, "B": 1, "C": 0}


def test_the_recipient_cannot_pass_on_a_unit_received_this_tick():
    engine = Engine(genesis(balances={"A": 1, "B": 0, "C": 0}))

    record = engine.tick(
        [
            transfer("a_to_b", "A", 0, to="B", amount=1),
            transfer("b_to_c", "B", 0, to="C", amount=1),
        ]
    )

    assert reason_of(record, "a_to_b") == Reason.ACCEPTED
    assert reason_of(record, "b_to_c") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 0, "B": 1, "C": 0}

    next_record = engine.tick([transfer("b_to_c", "B", 0, to="C", amount=1)])

    assert reason_of(next_record, "b_to_c") == Reason.ACCEPTED
    assert balances_of(engine.state) == {"A": 0, "B": 0, "C": 1}


def test_a_unit_claimed_this_tick_is_not_spendable_until_the_next_one():
    """The same availability boundary applies to a credit taken from a source."""
    state = genesis(balances={"A": 0}, sources={"S": source(1, "A")})
    engine = Engine(state)

    record = engine.tick(
        [
            claim("take", "A", 0, sources={"S": 1}),
            consume("eat", "A", 1, amount=1),
        ]
    )

    assert reason_of(record, "take") == Reason.ACCEPTED
    assert reason_of(record, "eat") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert balances_of(engine.state) == {"A": 1}
    assert stocks_of(engine.state) == {"S": 0}
    assert engine.state.consumed == 0

    next_record = engine.tick([consume("eat", "A", 0, amount=1)])

    assert reason_of(next_record, "eat") == Reason.ACCEPTED
    assert balances_of(engine.state) == {"A": 0}
    assert engine.state.consumed == 1
    assert engine.state.total() == state.total() == 1


def test_a_unit_given_away_is_not_double_counted_in_the_total():
    state = genesis(balances={"A": 2, "B": 0})
    engine = Engine(state)

    for _ in range(2):
        engine.tick([transfer("give", "A", 0, to="B", amount=1)])

    assert balances_of(engine.state) == {"A": 0, "B": 2}
    assert engine.state.total() == state.total() == 2


def test_the_order_of_the_recipients_own_proposals_does_not_rescue_an_early_spend():
    """B asking before or after A gives makes no difference to availability."""
    early = Engine(genesis(balances={"A": 1, "B": 0}))
    late = Engine(genesis(balances={"A": 1, "B": 0}))

    early_record = early.tick(
        [
            consume("b_first", "B", 0, amount=1),
            transfer("a_gives", "A", 0, to="B", amount=1),
        ]
    )
    late_record = late.tick(
        [
            transfer("a_gives", "A", 0, to="B", amount=1),
            consume("b_first", "B", 0, amount=1),
        ]
    )

    assert accepted_ids(early_record) == ("a_gives",)
    assert accepted_ids(late_record) == ("a_gives",)
    assert early_record.digest() == late_record.digest()
    assert early.state.digest() == late.state.digest()
