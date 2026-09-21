"""The declared world levers and the seeded genesis.

Levers are the ones ROADMAP Stage 2 allows: geometry, distribution, renewal,
initial supplies, perception radius, consumption rates, and the crowd-yield
trait set. Changing one is a new configuration, and every value is written
into the run header so a run is readable on its own.

Genesis uses one named deterministic generator, `homes-uniform-v1+yield-v1`:
homes are drawn without replacement from every cell except the source cell
using `random.Random(seed)`, then `yield_at` is drawn from the same RNG
instance. Home draws are unchanged from `homes-uniform-v1`. Nothing else in a
run uses randomness; decisions and processes are pure rules (DOCTRINE: no
runtime randomness through Stage 3).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from kernel import Source, WorldState

from world.overlay import Overlay

GENESIS_GENERATOR = "homes-uniform-v1+yield-v1"
FOOD_SOURCE = "food"
DISTANCE_METRIC = "chebyshev"
PERCEPTION_BOUNDARY = "distance <= radius"
DEFAULT_YIELD_SET = (1, 2, 3)


@dataclass(frozen=True)
class WorldConfig:
    seed: int
    width: int = 12
    height: int = 12
    actors: int = 6
    starting_food: int = 1        # units each person holds at genesis
    source_stock: int = 4         # units in the source at genesis
    source_cap: int = 8           # renewal never lifts stock above this
    renewal_every: int = 3        # ticks between renewals
    renewal_amount: int = 2       # units added per renewal, capped
    claim_amount: int = 2         # most units one claim asks for
    hunger_rate: int = 1          # hunger added per tick while alive
    satiation: int = 6            # hunger removed per unit eaten
    hungry_at: int = 5            # hunger at which a person seeks food
    emergency_at: int = 10        # hunger at which the state is an emergency
    death_at: int = 16            # hunger at which a person dies
    perception_radius: int = 3    # Chebyshev cells; self is always in view
    yield_set: tuple[int, ...] = DEFAULT_YIELD_SET
    yield_on: bool = True         # False assigns yield_at = actors + 1 so the rule never fires

    def __post_init__(self) -> None:
        checks = {
            "width": self.width >= 3, "height": self.height >= 3, "actors": self.actors >= 1,
            "starting_food": self.starting_food >= 0, "source_stock": self.source_stock >= 0,
            "source_cap": self.source_cap >= self.source_stock, "renewal_every": self.renewal_every >= 1,
            "renewal_amount": self.renewal_amount >= 0, "claim_amount": self.claim_amount >= 1,
            "hunger_rate": self.hunger_rate >= 0, "satiation": self.satiation >= 1,
            "hungry_at": 0 <= self.hungry_at, "emergency_at": self.hungry_at <= self.emergency_at,
            "death_at": self.emergency_at < self.death_at,
            "perception_radius": self.perception_radius >= 0,
            "yield_set": (
                len(self.yield_set) >= 1
                and all(type(value) is int and value >= 1 for value in self.yield_set)
            ),
            "capacity": self.actors <= self.width * self.height - 1,
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"invalid world configuration: {', '.join(bad)}")
        object.__setattr__(self, "yield_set", tuple(self.yield_set))

    @property
    def name(self) -> str:
        return "one-source-grid"

    @property
    def source_position(self) -> tuple[int, int]:
        return (self.width // 2, self.height // 2)

    def actor_ids(self) -> tuple[str, ...]:
        return tuple(f"p{index:02d}" for index in range(1, self.actors + 1))

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "genesis_generator": GENESIS_GENERATOR,
            "seed": self.seed,
            "width": self.width, "height": self.height, "actors": self.actors,
            "source": FOOD_SOURCE, "source_position": list(self.source_position),
            "starting_food": self.starting_food, "source_stock": self.source_stock,
            "source_cap": self.source_cap, "renewal_every": self.renewal_every,
            "renewal_amount": self.renewal_amount, "claim_amount": self.claim_amount,
            "hunger_rate": self.hunger_rate, "satiation": self.satiation,
            "hungry_at": self.hungry_at, "emergency_at": self.emergency_at, "death_at": self.death_at,
            "distance_metric": DISTANCE_METRIC,
            "perception_radius": self.perception_radius,
            "perception_boundary": PERCEPTION_BOUNDARY,
            "perception": (
                "self always; others in radius: identity, position, free food "
                "(not hunger, home, or decision); source position is a known landmark; "
                "source stock only when the source cell is in view (absent otherwise, never stale)"
            ),
            "dead_are_not_seen": "dead people are neither seen nor counted",
            "yield_set": list(self.yield_set),
            "yield": "on" if self.yield_on else "off",
            "movement": "one step per tick along the longer axis (x on ties), four neighbours, co-location allowed",
            "decision": (
                "eat if hungry and holding; claim if hungry at the source; wait if hungry at an empty source; "
                "yield if hungry, not emergency, off the source, source in view, crowd >= yield_at and stock < crowd; "
                "walk to the source if hungry; else walk home"
            ),
        }


def _homes_from(rng: random.Random, config: WorldConfig) -> dict[str, tuple[int, int]]:
    """First RNG draw: distinct cells for every person, never the source cell."""
    cells = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) != config.source_position]
    picks = rng.sample(cells, config.actors)
    return dict(zip(config.actor_ids(), picks))


def _yield_from(rng: random.Random, config: WorldConfig) -> dict[str, int]:
    """Second RNG draw, after homes. OFF assigns actor_count + 1 so the rule cannot fire."""
    actors = config.actor_ids()
    if not config.yield_on:
        return {actor: config.actors + 1 for actor in actors}
    bag: list[int] = []
    while len(bag) < config.actors:
        bag.extend(config.yield_set)
    bag = bag[:config.actors]
    rng.shuffle(bag)
    return dict(zip(actors, bag))


def homes_for(config: WorldConfig) -> dict[str, tuple[int, int]]:
    """Home placement: the first draw of `homes-uniform-v1+yield-v1`, unchanged from `homes-uniform-v1`."""
    return _homes_from(random.Random(config.seed), config)


def yield_at_for(config: WorldConfig) -> dict[str, int]:
    rng = random.Random(config.seed)
    _homes_from(rng, config)
    return _yield_from(rng, config)


def genesis(config: WorldConfig) -> tuple[WorldState, Overlay]:
    """The saved initial state: a kernel ledger and the overlay beside it."""
    actors = config.actor_ids()
    ledger = WorldState.genesis(
        balances={actor: config.starting_food for actor in actors},
        sources={FOOD_SOURCE: Source(stock=config.source_stock, authorised=frozenset(actors))},
    )
    rng = random.Random(config.seed)
    homes = _homes_from(rng, config)
    overlay = Overlay(
        tick=0,
        homes=homes,
        positions=dict(homes),
        hunger={actor: 0 for actor in actors},
        yield_at=_yield_from(rng, config),
        died_at={},
    )
    return ledger, overlay
