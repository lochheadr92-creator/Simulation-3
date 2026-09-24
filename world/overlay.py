"""The world state the kernel does not hold: homes, positions, hunger, deaths.

Immutable and canonical like the kernel's WorldState; replaced, never edited.
Food units are not here on purpose: they live in the kernel ledger, and the
overlay only ever reads them through the kernel's own views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from kernel import digest as canonical_digest

Position = tuple[int, int]


def _positions(raw: Mapping[str, Any]) -> Mapping[str, Position]:
    out: dict[str, Position] = {}
    for actor in sorted(raw):
        x, y = raw[actor]
        if type(x) is not int or type(y) is not int or x < 0 or y < 0:
            raise ValueError(f"{actor!r} needs a non-negative integer position, got {raw[actor]!r}")
        out[actor] = (x, y)
    return MappingProxyType(out)


def _positive_ints(raw: Mapping[str, Any], *, roster: set[str], name: str) -> Mapping[str, int]:
    if set(raw) != roster:
        raise ValueError(f"{name} must name the same people as homes")
    out = {actor: raw[actor] for actor in sorted(raw)}
    for actor, value in out.items():
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} of {actor!r} must be a positive integer, got {value!r}")
    return MappingProxyType(out)


@dataclass(frozen=True)
class Overlay:
    tick: int
    homes: Mapping[str, Position]
    positions: Mapping[str, Position]
    hunger: Mapping[str, int]
    yield_at: Mapping[str, int]
    died_at: Mapping[str, int] = field(default_factory=dict)
    thirst: Mapping[str, int] = field(default_factory=dict)   # empty unless water is on

    def __post_init__(self) -> None:
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("a tick must be an integer of zero or more")
        homes = _positions(self.homes)
        positions = _positions(self.positions)
        if set(homes) != set(positions) or set(positions) != set(self.hunger):
            raise ValueError("homes, positions and hunger must name the same people")
        hunger = {actor: self.hunger[actor] for actor in sorted(self.hunger)}
        for actor, value in hunger.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"hunger of {actor!r} must be an integer of zero or more")
        died = {actor: self.died_at[actor] for actor in sorted(self.died_at)}
        for actor, when in died.items():
            if actor not in positions or type(when) is not int or when < 0 or when > self.tick:
                raise ValueError(f"death of {actor!r} must name a known person and an earlier tick")
        yield_at = _positive_ints(self.yield_at, roster=set(homes), name="yield_at")
        thirst = {actor: self.thirst[actor] for actor in sorted(self.thirst)}
        if thirst and set(thirst) != set(positions):
            raise ValueError("thirst must name the same people as positions, or be empty")
        for actor, value in thirst.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"thirst of {actor!r} must be an integer of zero or more")
        object.__setattr__(self, "thirst", MappingProxyType(thirst))
        object.__setattr__(self, "homes", homes)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "hunger", MappingProxyType(hunger))
        object.__setattr__(self, "died_at", MappingProxyType(died))
        object.__setattr__(self, "yield_at", yield_at)

    @property
    def roster(self) -> tuple[str, ...]:
        return tuple(sorted(self.positions))

    def alive(self, actor: str) -> bool:
        return actor not in self.died_at

    @property
    def living(self) -> tuple[str, ...]:
        return tuple(actor for actor in self.roster if self.alive(actor))

    def canonical(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "homes": {actor: list(pos) for actor, pos in self.homes.items()},
            "positions": {actor: list(pos) for actor, pos in self.positions.items()},
            "hunger": dict(self.hunger),
            "yield_at": dict(self.yield_at),
            "died_at": dict(self.died_at),
            **({"thirst": dict(self.thirst)} if self.thirst else {}),
        }

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Overlay":
        """Rebuild an overlay from `canonical()` (slice 1c: replay, recovery).
        The shape is checked here; every value is validated by the constructor."""
        keys = {"tick", "homes", "positions", "hunger", "yield_at", "died_at"}
        if isinstance(data, Mapping) and "thirst" in data:
            keys = keys | {"thirst"}
        if not isinstance(data, Mapping) or set(data) != keys:
            raise ValueError(f"a canonical overlay needs exactly the keys {sorted(keys)}")
        for name in sorted(keys - {"tick"}):
            if not isinstance(data[name], Mapping):
                raise ValueError(f"a canonical overlay needs a mapping of {name}")

        def cells(raw: Mapping[str, Any]) -> dict[str, Position]:
            out: dict[str, Position] = {}
            for actor, cell in raw.items():
                if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                    raise ValueError(f"{actor!r} needs a two-integer position, got {cell!r}")
                out[actor] = (cell[0], cell[1])
            return out

        return cls(tick=data["tick"], homes=cells(data["homes"]), positions=cells(data["positions"]),
                   hunger=dict(data["hunger"]), yield_at=dict(data["yield_at"]), died_at=dict(data["died_at"]),
                   thirst=dict(data.get("thirst", {})))

    def digest(self) -> str:
        return canonical_digest(self.canonical())
