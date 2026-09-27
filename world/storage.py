"""Shared food caches at founding homes. Quantities live only in the ledger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world.observe import Observation

STORE_TARGET = 6


def store_id(resident: str) -> str:
    return f"store-{resident}"


def spare_for_store(observation: "Observation") -> int:
    """Only a resident at their finished shelter can put food aside.

    Keep one carried meal and stop filling at six. Needs and help get their
    normal turn first; the caller uses this only instead of resting.
    """
    if (not observation.alive or not observation.at_home or not observation.home_built
            or observation.home_store_food is None):
        return 0
    return max(0, min(observation.food - 1, STORE_TARGET - observation.home_store_food))
