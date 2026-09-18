"""Small helpers shared by the Stage 1a focused tests.

These read the engine's own objects through its public accessors. They do not
reimplement any rule, keep any ledger of their own, or compute an expected
outcome by a second route.
"""

from __future__ import annotations

from typing import Mapping

from kernel import Source, WorldState


def source(stock: int, *authorised: str) -> Source:
    """A shared source holding `stock` units, claimable by `authorised`."""
    return Source(stock=stock, authorised=authorised)


def genesis(
    *,
    tick: int = 0,
    balances: Mapping[str, int] | None = None,
    sources: Mapping[str, Source] | None = None,
    consumed: int = 0,
) -> WorldState:
    return WorldState.genesis(
        tick=tick,
        balances=dict(balances or {}),
        sources=dict(sources or {}),
        consumed=consumed,
    )


def balances_of(state: WorldState) -> dict[str, int]:
    return dict(state.balances)


def stocks_of(state: WorldState) -> dict[str, int]:
    return {source_id: src.stock for source_id, src in state.sources.items()}


def reason_of(record, proposal_id: str) -> str:
    """The single recorded reason for `proposal_id`.

    Raises when a proposal identity is absent or recorded more than once, so a
    test can never quietly read the first of several outcomes.
    """
    found = [outcome.reason for outcome in record.outcomes if outcome.proposal_id == proposal_id]
    if len(found) != 1:
        raise AssertionError(f"expected exactly one outcome for {proposal_id!r}, found {len(found)}")
    return found[0]


def accepted_ids(record) -> tuple[str, ...]:
    return tuple(outcome.proposal_id for outcome in record.outcomes if outcome.accepted)


def denied_ids(record) -> tuple[str, ...]:
    return tuple(outcome.proposal_id for outcome in record.outcomes if not outcome.accepted)
