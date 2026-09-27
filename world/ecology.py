"""Local patch recovery and the optional world-wide food seasons."""

from __future__ import annotations

from collections.abc import Mapping

from kernel import TickRecord
from kernel.proposals import OP_CLAIM
from kernel.state import source_account

CONDITION_MAX = 100
FULL_GROWTH_AT = 50
WEAR_PER_UNIT = 10
RECOVERY_PER_TICK = 1
SEASON_TICKS = 120
SEASONS = ("plentiful", "lean")


def season_at(tick: int) -> str:
    """The completed tick determines the season, including a boundary renewal."""
    return SEASONS[(tick // SEASON_TICKS) % len(SEASONS)]


def seasonal_growth(normal: int, season: str) -> int:
    """Alternate 150% rounded up and 50% rounded down before patch wear."""
    if season == "plentiful":
        return (3 * normal + 1) // 2
    if season == "lean":
        return normal // 2
    raise ValueError(f"unknown season: {season!r}")


def recover_patches(previous: Mapping[str, int], sources: tuple[str, ...], record: TickRecord) -> dict[str, int]:
    """Aggregate accepted claims before updating each patch once. A failed
    claim or merely standing at a patch does not disturb its recovery."""
    harvested = {source_account(source): 0 for source in sources}
    for outcome in record.outcomes:
        if outcome.accepted and outcome.operation == OP_CLAIM:
            for effect in outcome.effects:
                if effect.account in harvested and effect.delta < 0:
                    harvested[effect.account] -= effect.delta
    condition = {}
    for source in sources:
        taken = harvested[source_account(source)]
        before = previous.get(source, CONDITION_MAX)
        condition[source] = (max(0, before - WEAR_PER_UNIT * taken) if taken
                             else min(CONDITION_MAX, before + RECOVERY_PER_TICK))
    return condition


def food_growth(normal: int, condition: int) -> int:
    """Worn patches grow half as much, rounded up. Zero renewal stays zero."""
    return normal if condition >= FULL_GROWTH_AT else (normal + 1) // 2
