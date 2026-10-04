"""What people know of the ground, and the curiosity that takes them to see more of it.

The map is cut into square patches. Each person remembers, for every patch, the last tick any part of it was in
sight. Rough ground they have seen is remembered for as long as its patch has been seen within `terrain_span` ticks,
and then forgotten, so a way round a rubble field fades if nobody goes back. Somebody curious, with nothing pressing
to do and a patch near home they have not seen for a long time, goes to look at it. A well somebody sees is
remembered like any other thing seen, and used from afar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

EXPLORE = "explore"
GROUND_LEVERS = (("patch", 3), ("terrain_span", 240), ("roam", 6), ("stale_after", 150), ("explore_from", 60),
                 ("explore_margin", 12))

EXPLORATION = Feature(
    name="exploration",
    summary="People remember which parts of the map they have seen lately, forget rough ground they have not looked at for a long time, and the curious go to see what they have not seen.",
    rule=(
        "The map is cut into square patches patch cells wide. Each person keeps, for every patch, the last tick any cell "
        "of it was in their sight. Rough ground they have seen is remembered while its patch has been in sight within "
        "terrain_span ticks, and forgotten after that; ground seen again is refreshed. Somebody whose curiosity is "
        "explore_from or more, who is free, awake, fed and watered with explore_margin ticks to spare over the walk, "
        "in daylight and fair weather, with no wolf believed near, and who has chosen nothing but to rest or go "
        "home, walks to the nearest patch within roam steps of their home that they have not had in sight for "
        "stale_after ticks. A well somebody sees finished is believed in as any thing seen is, and a believed well "
        "is used for water from out of sight; a well in sight that is dry is not."),
    needs=("beliefs", "personality"),
    levers=GROUND_LEVERS,
    tables={"explore_kinds": [EXPLORE]},
)


def patch_grid(config: "WorldConfig") -> tuple[int, int, int]:
    """(patches across, patches down, patch side)."""
    side = config.lever("patch")
    return -(-config.width // side), -(-config.height // side), side


def patch_of(cell: tuple[int, int], config: "WorldConfig") -> int:
    across, _, side = patch_grid(config)
    return (cell[1] // side) * across + cell[0] // side


def patch_centre(index: int, config: "WorldConfig") -> tuple[int, int]:
    across, _, side = patch_grid(config)
    return (min((index % across) * side + side // 2, config.width - 1),
            min((index // across) * side + side // 2, config.height - 1))


def patches_in_view(origin: tuple[int, int], radius: int, config: "WorldConfig") -> frozenset[int]:
    """Every patch with at least one cell inside the view window."""
    across, _, side = patch_grid(config)
    x0, x1 = max(0, origin[0] - radius) // side, min(config.width - 1, origin[0] + radius) // side
    y0, y1 = max(0, origin[1] - radius) // side, min(config.height - 1, origin[1] + radius) // side
    return frozenset(py * across + px for py in range(y0, y1 + 1) for px in range(x0, x1 + 1))


@dataclass(frozen=True)
class Ground:
    seen: Mapping[str, tuple[tuple[int, int], ...]] = None      # person -> ((patch, last tick any of it was in sight), ...)

    def __post_init__(self) -> None:
        out = {}
        for actor, entries in sorted((self.seen or {}).items()):
            entries = tuple(sorted((int(p), int(t)) for p, t in entries))
            if entries:
                out[actor] = entries
        object.__setattr__(self, "seen", MappingProxyType(out))

    def __bool__(self) -> bool:
        return bool(self.seen)

    def check(self, roster: set[str], tick: int) -> None:
        for actor, entries in self.seen.items():
            if actor not in roster:
                raise ValueError(f"ground is remembered by a known person, not {actor!r}")
            patches = [p for p, _ in entries]
            if len(set(patches)) != len(patches):
                raise ValueError(f"{actor!r} remembers one patch twice")
            for patch, when in entries:
                if patch < 0 or not 0 <= when <= tick:
                    raise ValueError(f"{actor!r} remembers patch {patch} as seen at {when}, which is not a past tick")

    def canonical(self) -> dict[str, Any]:
        return {actor: [list(e) for e in entries] for actor, entries in self.seen.items()}

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Ground":
        if not isinstance(data, Mapping):
            raise ValueError("canonical ground maps people to the patches they have seen")
        out = {}
        for actor, entries in data.items():
            if not isinstance(actor, str) or not isinstance(entries, (list, tuple)):
                raise ValueError("canonical ground maps people to lists of patch and tick")
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) != 2 or any(type(n) is not int for n in entry):
                    raise ValueError(f"a remembered patch is a patch number and a tick: {entry!r}")
            out[actor] = tuple((p, t) for p, t in entries)
        return cls(seen=out)


def refresh_ground(overlay: Any, observations: Mapping[str, Any], memory: dict[str, set[tuple[int, int]]],
                   config: "WorldConfig") -> Ground:
    """Everybody's ground after one tick: the patches they had in sight are stamped with the tick they saw them
    (the overlay's own tick), and rough cells in patches left unseen for terrain_span ticks are dropped from
    `memory`, in place."""
    now, span = overlay.tick, config.lever("terrain_span")
    seen: dict[str, tuple[tuple[int, int], ...]] = {}
    for actor in overlay.living:
        mine = dict(overlay.ground.seen.get(actor, ()))
        view = observations.get(actor)
        here = view.rough_seen_now if view is not None else frozenset()
        for patch in (view.patches_seen_now if view is not None else ()):
            mine[patch] = now
        memory[actor] = {cell for cell in memory.get(actor, ())
                         if cell in here or now - mine.get(patch_of(cell, config), -span - 1) <= span}
        seen[actor] = tuple(sorted(mine.items()))
    return Ground(seen=seen)
