"""The things in the world that are not people, not food and not a building: so far, wolves.

One immutable block carried in the overlay and written into every tick, so the viewer
reads recorded positions and replay checks them. Each later kind of thing (plots, fires,
graves) adds a member here, validated by the module that owns it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from world.wolves import Wolf


@dataclass(frozen=True)
class Things:
    wolves: tuple[Wolf, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.wolves, tuple) or any(not isinstance(w, Wolf) for w in self.wolves):
            raise ValueError("wolves must be a tuple of Wolf")
        if len({w.id for w in self.wolves}) != len(self.wolves):
            raise ValueError("two wolves cannot share an id")

    def __bool__(self) -> bool:
        return bool(self.wolves)

    def canonical(self) -> dict[str, Any]:
        return {"wolves": [w.canonical() for w in self.wolves]} if self.wolves else {}

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Things":
        if not isinstance(data, Mapping) or set(data) - {"wolves"}:
            raise ValueError("a canonical block of things holds wolves only")
        return cls(wolves=tuple(Wolf.from_canonical(w) for w in data.get("wolves", ())))
