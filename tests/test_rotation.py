"""A5 - the declared rotation leaves no permanent winner.

Rotation is a function of the tick number and the tick-start roster alone, so
equivalent contention at successive tick values is exactly a sweep over the
genesis tick. Nothing in slice 1a produces resources, so a shared source cannot
be refilled inside one continuous run to contend over it again; the continuous
run below therefore checks the rotation the engine actually applied at each
tick, and the sweep checks who wins under it.

Rotation is deterministic priority, not a fairness guarantee. It only removes a
fixed permanent winner among otherwise equivalent claimants.
"""

from __future__ import annotations

from kernel import Engine, claim, ordering

from tests.support import accepted_ids, genesis, source


def test_rotated_roster_matches_the_declared_rule():
    roster = ("A", "B", "C")
    assert ordering.rotated_roster(roster, 0) == ("A", "B", "C")
    assert ordering.rotated_roster(roster, 1) == ("B", "C", "A")
    assert ordering.rotated_roster(roster, 2) == ("C", "A", "B")
    assert ordering.rotated_roster(roster, 3) == ("A", "B", "C")


def test_an_empty_roster_rotates_to_nothing():
    """Null control: the declared empty-roster case."""
    for tick in range(4):
        assert ordering.rotated_roster((), tick) == ()


def test_rotation_sorts_by_identity_and_ignores_insertion_order():
    assert ordering.rotated_roster(("C", "A", "B"), 1) == ("B", "C", "A")
    assert ordering.rotated_roster(("B", "C", "A"), 1) == ("B", "C", "A")


def test_equivalent_contention_has_no_permanent_winner_across_successive_ticks():
    winners = []
    for tick in range(6):
        engine = Engine(
            genesis(tick=tick, balances={"A": 0, "B": 0}, sources={"S": source(1, "A", "B")})
        )
        record = engine.tick(
            [
                claim("pA", "A", 0, sources={"S": 1}),
                claim("pB", "B", 0, sources={"S": 1}),
            ]
        )
        assert len(accepted_ids(record)) == 1
        winners.append(accepted_ids(record)[0])

    assert winners == ["pA", "pB", "pA", "pB", "pA", "pB"]
    assert len(set(winners)) == 2


def test_three_way_equivalent_contention_cycles_across_successive_ticks():
    winners = []
    for tick in range(6):
        engine = Engine(
            genesis(
                tick=tick,
                balances={"A": 0, "B": 0, "C": 0},
                sources={"S": source(1, "A", "B", "C")},
            )
        )
        record = engine.tick(
            [
                claim("pA", "A", 0, sources={"S": 1}),
                claim("pB", "B", 0, sources={"S": 1}),
                claim("pC", "C", 0, sources={"S": 1}),
            ]
        )
        winners.append(accepted_ids(record)[0])

    assert winners == ["pA", "pB", "pC", "pA", "pB", "pC"]
    assert set(winners) == {"pA", "pB", "pC"}


def test_the_engine_rotates_tick_over_tick_within_one_continuous_run():
    engine = Engine(genesis(tick=0, balances={"A": 0, "B": 0, "C": 0}))

    seen = [engine.tick([]).rotated_roster for _ in range(4)]

    assert seen == [
        ("A", "B", "C"),
        ("B", "C", "A"),
        ("C", "A", "B"),
        ("A", "B", "C"),
    ]


def test_a_later_identity_does_not_win_by_being_lower_in_sort_order():
    """The sorted roster stabilises ordering; it must not confer priority."""
    winners = []
    for tick in range(4):
        engine = Engine(
            genesis(tick=tick, balances={"aaa": 0, "zzz": 0}, sources={"S": source(1, "aaa", "zzz")})
        )
        record = engine.tick(
            [
                claim("low", "aaa", 0, sources={"S": 1}),
                claim("high", "zzz", 0, sources={"S": 1}),
            ]
        )
        winners.append(accepted_ids(record)[0])

    assert winners == ["low", "high", "low", "high"]


def test_rotation_does_not_reorder_one_actors_own_proposals():
    """An actor's declared sequence survives the rotation."""
    engine = Engine(
        genesis(tick=1, balances={"A": 0, "B": 0}, sources={"S": source(1, "A", "B")})
    )

    record = engine.tick(
        [
            claim("second", "A", 1, sources={"S": 1}),
            claim("first", "A", 0, sources={"S": 1}),
            claim("theirs", "B", 0, sources={"S": 1}),
        ]
    )

    assert [outcome.proposal_id for outcome in record.outcomes] == ["theirs", "first", "second"]
    assert accepted_ids(record) == ("theirs",)
