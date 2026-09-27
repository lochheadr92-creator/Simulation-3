"""Remember food that actually arrived, without changing any balance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel import TickRecord
from kernel.proposals import OP_TRANSFER
from kernel.state import actor_account

if TYPE_CHECKING:
    from world.overlay import Overlay

FOOD_MEMORY_LIMIT = 4


def remember_food(overlay: Overlay, record: TickRecord) -> dict[str, tuple[tuple[str, int], ...]]:
    """Keep each recipient's four most recent distinct donors, newest first.

    Dates are completed world ticks, matching the viewer. Rejected transfers,
    water and promises leave no food memory. Death does not erase a life story.
    """
    memories = dict(overlay.food_memory)
    living = set(overlay.living)
    people = {actor_account(p): p for p in living}
    for outcome in record.outcomes:
        if not outcome.accepted or outcome.operation != OP_TRANSFER:
            continue
        donor = outcome.actor
        if donor not in living:
            continue
        for effect in outcome.effects:
            recipient = people.get(effect.account)
            if effect.delta <= 0 or recipient is None or recipient == donor:
                continue
            recent = dict(memories.get(recipient, ()))
            recent[donor] = overlay.tick + 1
            memories[recipient] = tuple(sorted(recent.items(), key=lambda item: (-item[1], item[0]))
                                        [:FOOD_MEMORY_LIMIT])
    return memories
