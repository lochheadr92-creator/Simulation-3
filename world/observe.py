"""What one person sees at the start of a tick.

The view is bounded. Distance is Chebyshev (max(|dx|, |dy|)): movement is
four-neighbour, but sight is not a walk. A cell is visible when
distance <= perception_radius (inclusive). Self is always in view
(distance 0).

What is visible about another living person inside the radius: identity,
position, and their free food (the kernel's availability). Hunger is
internal: it is not visible, and neither is home nor the decision they
are about to take.

The source's POSITION is a known landmark, declared in config, and is
always present on the observation. Its STOCK is observed only when the
source cell is within the radius. Outside the radius the observation
carries no stock value (None), not a stale number and not zero. There is
no memory, observation age, or belief store; this is the local-knowledge
hook without retained facts (Stage 4).

Recorded form (run file, from 2026-09-25): `sees`, the identities of the
living others in view in roster order, plus `source_food` when the source is
in view. Their positions and free food are the tick-start world positions and
ledger availability already in the same file, so they are not repeated; older
files recorded them per observation as `others`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from kernel import WorldState
from kernel.state import actor_account, source_account

from world.config import FOOD_SOURCE, WATER, WATER_SOURCE, WorldConfig
from world.overlay import Overlay, Position


def chebyshev(a: Position, b: Position) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def in_view(origin: Position, target: Position, radius: int) -> bool:
    """True when target is visible from origin, including the origin cell."""
    return chebyshev(origin, target) <= radius


@dataclass(frozen=True)
class SeenPerson:
    actor: str
    position: Position
    food: int                 # free units at tick start, as the kernel reports them

    def canonical(self) -> dict[str, Any]:
        return {"id": self.actor, "at": list(self.position), "food": self.food}


@dataclass(frozen=True)
class Observation:
    actor: str
    tick: int
    alive: bool
    position: Position
    home: Position
    hunger: int
    food: int                 # own free units at tick start
    source: Position
    source_food: int | None   # free stock if the source cell is in view; else None
    yield_at: int = 99        # own trait; visible to self, not recorded about others
    others: tuple[SeenPerson, ...] = field(default_factory=tuple)
    thirst: int = 0                        # water on only, like the three fields below
    water: int = 0                         # own free water units at tick start
    water_source: Position | None = None   # a known landmark, like the food source
    water_stock: int | None = None         # free water stock if its cell is in view; else None

    @property
    def at_source(self) -> bool:
        return self.position == self.source

    @property
    def at_home(self) -> bool:
        return self.position == self.home

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "alive": 1 if self.alive else 0, "position": list(self.position), "hunger": self.hunger,
            "food": self.food, "others": [seen.canonical() for seen in self.others],
        }
        if self.source_food is not None:
            out["source_food"] = self.source_food
        return out

    def compact(self) -> dict[str, Any]:
        """Run-file form: seen identities, and source stock if seen."""
        out: dict[str, Any] = {"sees": [seen.actor for seen in self.others]}
        if self.source_food is not None:
            out["source_food"] = self.source_food
        if self.water_stock is not None:
            out["water_stock"] = self.water_stock
        return out


def observe(actor: str, ledger: WorldState, overlay: Overlay, config: WorldConfig,
            available: Mapping[str, int] | None = None) -> Observation:
    """`available` is the ledger's availability map; a caller observing many
    people passes it once per tick rather than having it rebuilt per person."""
    if available is None:
        available = ledger.availability()
    view = ledger.view_for(actor)
    origin = overlay.positions[actor]
    radius = config.perception_radius
    others = tuple(
        SeenPerson(other, overlay.positions[other], available[actor_account(other)])
        for other in overlay.living
        if other != actor and in_view(origin, overlay.positions[other], radius)
    )
    source = config.source_position
    source_food = view.sources[FOOD_SOURCE].available_stock if in_view(origin, source, radius) else None
    return Observation(
        actor=actor,
        tick=ledger.tick,
        alive=overlay.alive(actor),
        position=origin,
        home=overlay.homes[actor],
        hunger=overlay.hunger[actor],
        food=view.own_available,
        source=source,
        source_food=source_food,
        yield_at=overlay.yield_at[actor],
        others=others,
        **_water_view(actor, origin, overlay, config, available),
    )


def _water_view(actor: str, origin: Position, overlay: Overlay, config: WorldConfig,
                available: Mapping[str, int]) -> dict[str, Any]:
    if not config.water_on:
        return {}
    well = config.water_position
    return {
        "thirst": overlay.thirst[actor],
        "water": available[actor_account(actor, WATER)],
        "water_source": well,
        "water_stock": available[source_account(WATER_SOURCE)] if in_view(origin, well, config.perception_radius) else None,
    }
