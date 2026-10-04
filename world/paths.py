"""Desire paths: ground wears with walking, and people walk where the ground is worn.

Every step onto a cell adds a little wear and every cell slowly recovers. A cell worn to `worn_at` is a path.
Rough ground that has become a path costs no extra tick to cross. Somebody choosing between two equal ways to
take the next step takes the worn one if they can see it, so the paths people make draw more walkers.
What a person believes about rough ground is what they saw: a cell remembered as rough that has since been
worn through still looks rough to them until they see it again.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

PATH_LEVERS = (("wear_gain", 1), ("wear_cap", 40), ("recover_every", 30), ("worn_at", 8))

PATHS = Feature(
    name="paths",
    summary="Walked ground wears into paths, rough ground that is walked enough stops slowing people, and people prefer the worn way.",
    rule=(
        "Whoever steps onto a cell adds wear_gain wear to it, up to wear_cap, and every recover_every ticks every worn "
        "cell loses one. A cell with worn_at wear or more is a path. A path that was rough ground costs no extra tick "
        "to enter. Choosing the next step towards somewhere, when two steps are equally near, somebody takes the one "
        "that is a path if it is in their sight and no danger is believed near. Somebody's route round rough ground "
        "counts a cell they remember as rough as rough until they see it again, even if it has since become a path."),
    levers=PATH_LEVERS,
    tables={"wear_levels": ["wear", "path"]},
)


def worn(paths: tuple[tuple[int, int, int], ...], config: "WorldConfig") -> frozenset[tuple[int, int]]:
    """The cells that are paths now."""
    at = config.lever("worn_at")
    return frozenset((x, y) for x, y, w in paths if w >= at)


def advance_paths(overlay: Any, positions: Mapping[str, tuple[int, int]], config: "WorldConfig") -> tuple[tuple[int, int, int], ...]:
    """The wear after one tick: a step onto a cell adds to it, and every recover_every ticks all cells lose one."""
    wear = {(x, y): w for x, y, w in overlay.things.paths}
    for actor in sorted(overlay.living):
        cell = positions.get(actor)
        if cell is not None and cell != overlay.positions[actor]:
            wear[cell] = min(config.lever("wear_cap"), wear.get(cell, 0) + config.lever("wear_gain"))
    if (overlay.tick + 1) % config.lever("recover_every") == 0:
        wear = {cell: w - 1 for cell, w in wear.items()}
    return tuple(sorted((x, y, w) for (x, y), w in wear.items() if w > 0))
