"""Deterministic resolution order.

The tick-start roster is sorted by identity and rotated left by `tick mod
actor_count`. Identity stabilises the ordering; the rotation stops it conferring
permanent priority. This is deterministic priority, not a fairness guarantee: it
says nothing about claimants whose opportunity or eligibility differ.
"""

from __future__ import annotations

from collections.abc import Iterable


def sorted_roster(actor_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(actor_ids))


def rotated_roster(actor_ids: Iterable[str], tick: int) -> tuple[str, ...]:
    roster = sorted_roster(actor_ids)
    if not roster:
        return ()
    offset = tick % len(roster)
    return roster[offset:] + roster[:offset]


def actor_ranks(rotated: Iterable[str]) -> dict[str, int]:
    return {actor_id: rank for rank, actor_id in enumerate(rotated)}
