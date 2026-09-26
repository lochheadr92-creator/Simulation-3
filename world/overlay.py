"""The world state the kernel does not hold: homes, positions, needs, deaths,
and the shelters people have built.

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


def _levels(raw: Mapping[str, Any], *, positions: Mapping[str, Position], name: str) -> Mapping[str, int]:
    """One need level per person: the same roster as positions, or empty when
    that need is off. Hunger is always present; thirst and cold are not."""
    out = {actor: raw[actor] for actor in sorted(raw)}
    if out and set(out) != set(positions):
        raise ValueError(f"{name} must name the same people as positions, or be empty")
    for actor, value in out.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} of {actor!r} must be an integer of zero or more")
    return MappingProxyType(out)


def _links(raw: Mapping[str, Any], *, positions: Mapping[str, Position], name: str) -> Mapping[str, str]:
    """One person naming another: who asked whom, who owes whom. Both ends must
    be people the world knows, and nobody names themselves."""
    out = {actor: raw[actor] for actor in sorted(raw)}
    for actor, other in out.items():
        if actor not in positions or not isinstance(other, str) or other not in positions or other == actor:
            raise ValueError(f"{name} must name two different known people, got {actor!r} -> {other!r}")
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
    cold: Mapping[str, int] = field(default_factory=dict)     # empty unless warmth is on
    held: Mapping[str, int] = field(default_factory=dict)     # ticks still owed to the rough cell underfoot
    built: Mapping[str, int] = field(default_factory=dict)    # ticks of work each person has put into their shelter
    shelters: tuple[Position, ...] = ()                       # cells somebody has finished; permanent
    together: Mapping[str, int] = field(default_factory=dict) # "a|b" -> consecutive ticks side by side and well
    requests: Mapping[str, str] = field(default_factory=dict) # asker -> the person they asked, awaiting an answer
    promises: Mapping[str, str] = field(default_factory=dict) # helper -> the person they agreed to bring food to

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
        object.__setattr__(self, "thirst", _levels(self.thirst, positions=positions, name="thirst"))
        object.__setattr__(self, "cold", _levels(self.cold, positions=positions, name="cold"))
        object.__setattr__(self, "held", _levels(self.held, positions=positions, name="held"))
        object.__setattr__(self, "built", _levels(self.built, positions=positions, name="built"))
        together = {pair: self.together[pair] for pair in sorted(self.together)}
        for pair, value in together.items():
            ends = pair.split("|") if isinstance(pair, str) else []
            if len(ends) != 2 or any(end not in positions for end in ends) or ends[0] >= ends[1]:
                raise ValueError(f"a pair must name two known people in order, got {pair!r}")
            if type(value) is not int or value < 0:
                raise ValueError(f"the count for {pair!r} must be an integer of zero or more")
        object.__setattr__(self, "together", MappingProxyType(together))
        object.__setattr__(self, "requests", _links(self.requests, positions=positions, name="requests"))
        object.__setattr__(self, "promises", _links(self.promises, positions=positions, name="promises"))
        shelters = tuple(sorted(tuple(cell) for cell in self.shelters))
        for cell in shelters:
            if (len(cell) != 2 or type(cell[0]) is not int or type(cell[1]) is not int
                    or cell[0] < 0 or cell[1] < 0):
                raise ValueError(f"a shelter needs a non-negative integer cell, got {cell!r}")
        if len(set(shelters)) != len(shelters):
            raise ValueError("a cell cannot hold two shelters")
        object.__setattr__(self, "shelters", shelters)
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
            **({"cold": dict(self.cold)} if self.cold else {}),
            **({"held": dict(self.held)} if any(self.held.values()) else {}),
            **({"built": dict(self.built)} if any(self.built.values()) else {}),
            **({"shelters": [list(cell) for cell in self.shelters]} if self.shelters else {}),
            **({"together": dict(self.together)} if self.together else {}),
            **({"requests": dict(self.requests)} if self.requests else {}),
            **({"promises": dict(self.promises)} if self.promises else {}),
        }

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Overlay":
        """Rebuild an overlay from `canonical()` (slice 1c: replay, recovery).
        The shape is checked here; every value is validated by the constructor."""
        keys = {"tick", "homes", "positions", "hunger", "yield_at", "died_at"}
        if isinstance(data, Mapping):
            for extra in ("thirst", "cold", "held", "built", "shelters", "together", "requests", "promises"):
                if extra in data:
                    keys = keys | {extra}
        if not isinstance(data, Mapping) or set(data) != keys:
            raise ValueError(f"a canonical overlay needs exactly the keys {sorted(keys)}")
        for name in sorted(keys - {"tick", "shelters"}):
            if not isinstance(data[name], Mapping):
                raise ValueError(f"a canonical overlay needs a mapping of {name}")
        if "shelters" in keys and not isinstance(data["shelters"], list):
            raise ValueError("a canonical overlay needs a list of shelters")

        def cells(raw: Mapping[str, Any]) -> dict[str, Position]:
            out: dict[str, Position] = {}
            for actor, cell in raw.items():
                if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                    raise ValueError(f"{actor!r} needs a two-integer position, got {cell!r}")
                out[actor] = (cell[0], cell[1])
            return out

        return cls(tick=data["tick"], homes=cells(data["homes"]), positions=cells(data["positions"]),
                   hunger=dict(data["hunger"]), yield_at=dict(data["yield_at"]), died_at=dict(data["died_at"]),
                   thirst=dict(data.get("thirst", {})), cold=dict(data.get("cold", {})),
                   held=dict(data.get("held", {})), built=dict(data.get("built", {})),
                   shelters=tuple(tuple(cell) for cell in data.get("shelters", ())),
                   together=dict(data.get("together", {})),
                   requests=dict(data.get("requests", {})), promises=dict(data.get("promises", {})))

    def digest(self) -> str:
        return canonical_digest(self.canonical())
