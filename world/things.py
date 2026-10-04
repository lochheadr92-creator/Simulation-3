"""The things in the world that are not people, not food and not a building: so far, wolves.

One immutable block carried in the overlay and written into every tick, so the viewer
reads recorded positions and replay checks them. Each later kind of thing (plots, fires,
graves) adds a member here, validated by the module that owns it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from world.aftermath import Death
from world.farming import Plot
from world.structures import Struct
from world.wolves import Wolf


@dataclass(frozen=True)
class Things:
    wolves: tuple[Wolf, ...] = ()
    plots: tuple[Plot, ...] = ()
    structures: tuple[Struct, ...] = ()
    deaths: tuple[Death, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.deaths, tuple) or any(not isinstance(d, Death) for d in self.deaths):
            raise ValueError("deaths must be a tuple of Death")
        if len({d.person for d in self.deaths}) != len(self.deaths):
            raise ValueError("a person dies once")
        if not isinstance(self.structures, tuple) or any(not isinstance(s, Struct) for s in self.structures):
            raise ValueError("structures must be a tuple of Struct")
        if len({(s.kind, s.owner) for s in self.structures}) != len(self.structures):
            raise ValueError("a person has at most one structure of each kind")
        if not isinstance(self.plots, tuple) or any(not isinstance(p, Plot) for p in self.plots):
            raise ValueError("plots must be a tuple of Plot")
        if len({p.owner for p in self.plots}) != len(self.plots):
            raise ValueError("two plots cannot share an owner")
        if not isinstance(self.wolves, tuple) or any(not isinstance(w, Wolf) for w in self.wolves):
            raise ValueError("wolves must be a tuple of Wolf")
        if len({w.id for w in self.wolves}) != len(self.wolves):
            raise ValueError("two wolves cannot share an id")

    def check(self, roster: set[str], died_at: Mapping[str, int], tick: int) -> None:
        """Every record and marker for the dead names somebody who really died, on the tick they died."""
        for d in self.deaths:
            if d.person not in roster or died_at.get(d.person) != d.tick or d.tick > tick:
                raise ValueError(f"a death record for {d.person!r} does not match when they died")
            if any(w not in roster for w in d.witnesses) or (d.taker and d.taker not in roster) or (d.partner and d.partner not in roster):
                raise ValueError(f"the death record for {d.person!r} names somebody who is not a known person")
        for s in self.structures:
            if s.kind == "grave" and (s.owner not in roster or died_at.get(s.owner) != s.a or s.b not in (0, 1)):
                raise ValueError(f"the grave of {s.owner!r} does not match when they died")

    def __bool__(self) -> bool:
        return bool(self.wolves or self.plots or self.structures or self.deaths)

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.wolves:
            out["wolves"] = [w.canonical() for w in self.wolves]
        if self.plots:
            out["plots"] = [p.canonical() for p in self.plots]
        if self.structures:
            out["structures"] = [s.canonical() for s in self.structures]
        if self.deaths:
            out["deaths"] = [d.canonical() for d in self.deaths]
        return out

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Things":
        if not isinstance(data, Mapping) or set(data) - {"wolves", "plots", "structures", "deaths"}:
            raise ValueError("a canonical block of things holds wolves, plots, structures and deaths only")
        return cls(wolves=tuple(Wolf.from_canonical(w) for w in data.get("wolves", ())),
                   plots=tuple(Plot.from_canonical(p) for p in data.get("plots", ())),
                   structures=tuple(Struct.from_canonical(s) for s in data.get("structures", ())),
                   deaths=tuple(Death.from_canonical(d) for d in data.get("deaths", ())))
