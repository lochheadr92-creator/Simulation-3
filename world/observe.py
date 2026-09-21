"""What one person sees at the start of a tick.

Bounded on purpose: own position, own hunger, own free food (the kernel's
availability, so held units are not counted), the source's place and its
free stock as the kernel reports it at tick start. No other person is
visible yet; perception radius and bounded views are the next checkpoint.
The source position is a known landmark in this world, declared in config.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel import WorldState

from world.config import FOOD_SOURCE, WorldConfig
from world.overlay import Overlay, Position


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
    source_food: int          # free stock at tick start, as the kernel reports it

    @property
    def at_source(self) -> bool:
        return self.position == self.source

    @property
    def at_home(self) -> bool:
        return self.position == self.home

    def canonical(self) -> dict[str, Any]:
        return {
            "alive": 1 if self.alive else 0, "position": list(self.position), "hunger": self.hunger,
            "food": self.food, "source_food": self.source_food,
        }


def observe(actor: str, ledger: WorldState, overlay: Overlay, config: WorldConfig) -> Observation:
    view = ledger.view_for(actor)
    return Observation(
        actor=actor,
        tick=ledger.tick,
        alive=overlay.alive(actor),
        position=overlay.positions[actor],
        home=overlay.homes[actor],
        hunger=overlay.hunger[actor],
        food=view.own_available,
        source=config.source_position,
        source_food=view.sources[FOOD_SOURCE].available_stock,
    )
