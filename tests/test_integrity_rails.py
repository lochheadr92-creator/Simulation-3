"""The settlement integrity rails.

These are raised, never clamped and never turned into a denial reason: a broken
invariant is a kernel defect, not a simulation outcome. Correctness cannot be
switched off, so the rails are checked with explicit conditions rather than with
`assert`, which `python -O` would strip.

The rails sit behind the ordinary validation path, and the mutation check under
`evidence/stage-01/instrument/` records that no ordinary input reaches them.
They are therefore exercised here by calling the commit step directly with the
staged effects that would trip them. That is the only honest way to show a
backstop works: reach past what is meant to make it unnecessary.
"""

from __future__ import annotations

import pytest

from kernel import Engine, IntegrityError, claim, consume, settlement

from tests.support import genesis, source


def world():
    return genesis(balances={"A": 1, "B": 0}, sources={"S": source(2, "A")}, consumed=3)


def test_the_negative_balance_rail_refuses_to_commit():
    state = world()

    with pytest.raises(IntegrityError, match="negative balance"):
        settlement._commit(state, {"actor:A": -5, "sink:consumed": 5})


def test_the_negative_stock_rail_refuses_to_commit():
    state = world()

    with pytest.raises(IntegrityError, match="negative balance"):
        settlement._commit(state, {"source:S": -9, "actor:A": 9})


def test_the_balanced_effects_rail_refuses_to_commit():
    state = world()

    with pytest.raises(IntegrityError, match="do not sum to zero"):
        settlement._commit(state, {"actor:A": 7})


def test_the_account_containment_rail_refuses_to_commit():
    state = world()

    with pytest.raises(IntegrityError, match="outside the world"):
        settlement._commit(state, {"actor:GHOST": 1, "actor:A": -1})


def test_a_legitimate_commit_passes_every_rail():
    """Control: the rails do not refuse ordinary settlement."""
    state = world()

    committed = settlement._commit(state, {"source:S": -2, "actor:A": 2})

    assert committed.tick == state.tick + 1
    assert dict(committed.balances) == {"A": 3, "B": 0}
    assert committed.sources["S"].stock == 0
    assert committed.total() == state.total()


def test_an_empty_commit_passes_every_rail():
    """Null control."""
    state = world()

    committed = settlement._commit(state, {})

    assert dict(committed.balances) == dict(state.balances)
    assert committed.total() == state.total()


def test_the_rails_are_not_assertions_that_optimisation_would_remove():
    source_text = (
        __import__("pathlib").Path(settlement.__file__).read_text(encoding="utf-8")
    )
    body = source_text.split("def _commit(", 1)[1]
    assert "assert " not in body
    assert "raise IntegrityError" in body


def test_an_ordinary_contended_tick_still_settles_under_the_rails():
    """Control: the rails are in the live path, not only in these tests."""
    engine = Engine(genesis(balances={"A": 0, "B": 0}, sources={"S": source(1, "A", "B")}))

    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )

    assert len(record.outcomes) == 2
    assert engine.state.total() == 1


def test_consumption_stays_inside_the_conserved_total():
    state = genesis(balances={"A": 2})
    engine = Engine(state)

    engine.tick([consume("eat", "A", 0, amount=2)])

    assert dict(engine.state.balances) == {"A": 0}
    assert engine.state.consumed == 2
    assert engine.state.total() == state.total() == 2
