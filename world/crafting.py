"""Stone, tools and making things.

A quarry gives stone. A person at home with the materials makes a tool: the inputs are consumed through the
kernel like any other spending, and the tool itself is a named resource that comes into being by a recorded
production entry tied to that consumption, so nothing appears without a visible cause. Tools change what
people can do: an axe saves building ticks, a basket carries more food, a pick takes stone faster.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_CONSUME
from kernel.state import actor_account
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

STONE = "stone"
STONE_STOCK = 10
STONE_RENEWAL_EVERY = 50
STONE_RENEWAL = 1
GO_STONE, GATHER_STONE, WAIT_STONE, CRAFT = "go_stone", "gather_stone", "wait_stone", "craft"
TOOLS = ("axe", "pick", "basket", "hoe")
RECIPES: dict[str, tuple[tuple[str, int], ...]] = {
    "axe": (("wood", 1), ("stone", 2)), "pick": (("wood", 1), ("stone", 2)),
    "basket": (("wood", 2),), "hoe": (("wood", 1), ("stone", 2)),
}
MAKER_KINDS = frozenset({GO_STONE, GATHER_STONE, WAIT_STONE, CRAFT})

CRAFT_LEVERS = (("stone_hand", 1), ("stone_pack", 3), ("axe_saves", 2), ("basket_bonus", 2), ("craft_diligence", 40),
                ("craft_margin", 6))

CRAFTING = Feature(
    name="crafting",
    summary="A quarry gives stone; people make axes, picks and baskets from wood and stone, and the tools help.",
    rule=(
        "One quarry holds stone_stock stone and renews one every 50 ticks. Somebody idle at home (or already on "
        "the way to fetch materials), not in a storm, with their own needs far enough off to make the trip "
        "(craft_margin ticks to spare), no wolf they know of near the place, and a diligence of "
        "craft_diligence or more or the materials already in hand, makes the first tool they lack that is "
        "useful to them: an axe (1 wood, 2 stone) while their shelter is unfinished, then a basket (2 wood), "
        "then a pick (1 wood, 2 stone), then an axe if they have none. They fetch missing wood or stone from the grove or quarry, a pack at "
        "a time, and make the tool at home in one tick. Making spends the inputs through the kernel; the tool "
        "is a named resource added by a recorded production entry only when every input was accepted. "
        "An axe takes axe_saves ticks off building a shelter (never below four). A basket adds "
        "basket_bonus to a food claim. A pick lets a stone claim take stone_pack rather than stone_hand. "
        "Making a tool counts as crafting practice and gathering stone as gathering practice."),
    levers=CRAFT_LEVERS,
    tables={"tools": list(TOOLS), "recipes": {tool: [list(pair) for pair in parts] for tool, parts in RECIPES.items()}},
)


def tools_held(available: Mapping[str, int], actor: str) -> tuple[str, ...]:
    return tuple(tool for tool in TOOLS if available.get(actor_account(actor, tool), 0) >= 1)


def apply_crafting(ledger: Any, decisions: Mapping[str, Any], record: Any,
                   config: "WorldConfig") -> tuple[Any, list[dict[str, Any]]]:
    """Add each tool whose every input the kernel accepted spending this tick, and record why it exists."""
    from dataclasses import replace
    accepted: dict[str, dict[str, int]] = {}
    for outcome in record.outcomes:
        if outcome.operation != OP_CONSUME or not outcome.accepted:
            continue
        for effect in outcome.effects:
            if effect.delta < 0:
                accepted.setdefault(outcome.actor, {})[effect.account] = -effect.delta
    made: list[dict[str, Any]] = []
    holdings = {resource: dict(held) for resource, held in ledger.holdings.items()}
    for actor in sorted(decisions):
        d = decisions[actor]
        if d.kind != CRAFT or d.target not in RECIPES:
            continue
        spent = accepted.get(actor, {})
        if all(spent.get(actor_account(actor, resource)) == units for resource, units in RECIPES[d.target]):
            holdings[d.target][actor] = holdings[d.target].get(actor, 0) + 1
            made.append({"made": actor, "item": d.target, "amount": 1})
    return (replace(ledger, holdings=holdings) if made else ledger), made


def build_saves(tools: tuple[str, ...], config: "WorldConfig") -> int:
    return config.lever("axe_saves") if "axe" in tools else 0
