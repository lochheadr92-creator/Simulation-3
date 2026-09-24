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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from kernel import Source, WorldState

from world.overlay import Overlay

GENESIS_GENERATOR = "homes-uniform-v1+yield-v1"
FOOD_SOURCE = "food"
WATER_SOURCE = "water"         # the water source id
WATER = "water"                # the kernel's named resource for water
WATER_LEVERS = ("starting_water", "water_stock", "water_cap", "water_renewal_every", "water_renewal_amount",
                "draw_amount", "thirst_rate", "quench", "thirsty_at", "thirst_emergency_at", "thirst_death_at")
DISTANCE_METRIC = "chebyshev"
PERCEPTION_BOUNDARY = "distance <= radius"
DEFAULT_YIELD_SET = (1, 2, 3)

# The defaults before 2026-09-25: an 11-tick window from hungry (5) to dead (16)
# that kept people within about 8 steps of food, claims of 2, and no early
# departure. Kept so earlier checkpoint results and fixtures can be reproduced:
# WorldConfig(seed=..., **SHORT_RANGE_LEVERS).
SHORT_RANGE_LEVERS = {"hungry_at": 5, "emergency_at": 10, "death_at": 16, "satiation": 6,
                      "renewal_every": 3, "claim_amount": 2, "plan_trips": False}
INTEGER_LEVERS = ("seed", "width", "height", "actors", "starting_food", "source_stock", "source_cap",
                  "renewal_every", "renewal_amount", "claim_amount", "hunger_rate", "satiation",
                  "hungry_at", "emergency_at", "death_at", "perception_radius")


@dataclass(frozen=True)
class WorldConfig:
    seed: int
    width: int = 12
    height: int = 12
    actors: int = 6
    starting_food: int = 1        # units each person holds at genesis
    source_stock: int = 4         # units in the source at genesis
    source_cap: int = 8           # renewal never lifts stock above this
    renewal_every: int = 15       # ticks between renewals
    renewal_amount: int = 2       # units added per renewal, capped
    claim_amount: int = 3         # most units one claim takes: the pack carried away
    hunger_rate: int = 1          # hunger added per tick while alive
    satiation: int = 30           # hunger removed per unit eaten
    hungry_at: int = 25           # hunger at which a person seeks food
    emergency_at: int = 50        # hunger at which the state is an emergency
    death_at: int = 80            # hunger at which a person dies
    perception_radius: int = 3    # Chebyshev cells; self is always in view
    yield_set: tuple[int, ...] = DEFAULT_YIELD_SET
    yield_on: bool = True         # False assigns yield_at = actors + 1 so the rule never fires
    scoring_on: bool = False      # opt in; OFF preserves the leg-5 selector and decision shape
    plan_trips: bool = True       # holding no food, leave for the source in time to arrive as hunger reaches hungry_at
    water_on: bool = False        # a second need: thirst, met from a water source (2026-09-25)
    starting_water: int = 1       # water units each person holds at genesis
    water_stock: int = 6          # units in the water source at genesis
    water_cap: int = 12           # water renewal never lifts stock above this
    water_renewal_every: int = 5
    water_renewal_amount: int = 3
    draw_amount: int = 3          # most water units one draw takes
    thirst_rate: int = 2          # thirst rises faster than hunger
    quench: int = 30              # thirst removed per unit drunk
    thirsty_at: int = 25
    thirst_emergency_at: int = 50
    thirst_death_at: int = 80

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
            "capacity": self.actors <= self.width * self.height - (2 if self.water_on else 1),
            "water": (not self.water_on) or (
                self.starting_water >= 0 and 0 <= self.water_stock <= self.water_cap
                and self.water_renewal_every >= 1 and self.water_renewal_amount >= 0 and self.draw_amount >= 1
                and self.thirst_rate >= 0 and self.quench >= 1
                and 0 <= self.thirsty_at <= self.thirst_emergency_at < self.thirst_death_at
                and self.water_position != self.source_position),
            "water_with_scoring": not (self.water_on and self.scoring_on),   # scoring has no water actions yet
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

    @property
    def water_position(self) -> tuple[int, int]:
        return (self.width // 4, self.height // 4)

    def actor_ids(self) -> tuple[str, ...]:
        return tuple(f"p{index:02d}" for index in range(1, self.actors + 1))

    def describe(self) -> dict[str, Any]:
        out: dict[str, Any] = {
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
            "scoring": "on" if self.scoring_on else "off",
            "scoring_formula": {
                "eat": "(2, 0)", "claim": "(1, 0)", "wait": "(1, 0)",
                "go": "(0, 2 * (hunger - hungry_at) + 1)",
                "yield": "(0, 2 * (seen_crowd - yield_at + 1))",
                "home": "(0, 0)", "rest": "(0, 0)",
            },
            "scoring_order": "lexicographic (tier, pressure), greatest first; eligibility unchanged",
            "scoring_scale": (
                "one hunger point and one observed person each add 2 pressure units; "
                "equal weighting is a modelling assumption, not an empirical scale"
            ),
            "scoring_crossover": "GO > YIELD iff hunger >= hungry_at + seen_crowd - yield_at + 1 (both eligible)",
            "scoring_crossover_configured": f"hunger >= seen_crowd - yield_at + {self.hungry_at + 1} (both eligible)",
            "scoring_ties": "GO odd, YIELD even: never equal; CLAIM/WAIT and HOME/REST mutually exclusive; no additional tie policy",
            "food_allocation": "kernel sorted full tick-start roster (including inactive actors), rotated by tick mod actor_count; personal scores confer no priority",
            "movement": "one step per tick along the longer axis (x on ties), four neighbours, co-location allowed",
            "decision": (
                ("score existing eligible actions; " if self.scoring_on else "fixed priority: ")
                + "eat if hungry and holding; claim if hungry at the source; wait if hungry at an empty source; "
                "yield if hungry, not emergency, off the source, source in view, crowd >= yield_at and stock < crowd; "
                "walk to the source if hungry; else walk home"
            ),
        }
        if self.plan_trips:
            # Written only when on, so a header from before this rule existed
            # (which never carried it) still round-trips, as trips off.
            out["trips"] = "on"
            out["decision"] = out["decision"].replace(
                "walk to the source if hungry; else walk home",
                "walk to the source if hungry, or when holding no food and hunger + hunger_rate * steps to the "
                "source reaches hungry_at (leave in time); else walk home")
        if self.water_on:
            # Written only when on, so every earlier header still round-trips.
            out["water"] = "on"
            out["water_source"] = WATER_SOURCE
            out["water_position"] = list(self.water_position)
            for name in WATER_LEVERS:
                out[name] = getattr(self, name)
            out["decision"] += (
                "; water, the second need: drink if thirsty and holding water; draw if thirsty at the water; "
                "wait if thirsty at empty water; walk to the water if thirsty, or holding none when thirst + "
                "thirst_rate * steps reaches thirsty_at; when both needs call, serve the one nearer its lethal "
                "level (hunger/death_at against thirst/thirst_death_at, thirst on ties)")
        return out

    @classmethod
    def from_describe(cls, described: Mapping[str, Any]) -> "WorldConfig":
        """The configuration a run header describes (slice 1c replay and recovery).

        Refused unless `describe()` of the result equals the description exactly:
        the world name, the genesis generator, every lever and every line of
        declared rule text must be what this code writes, so a header from
        another generator or rule set cannot be replayed as this one.
        """
        if not isinstance(described, Mapping):
            raise ValueError("a world description must be a mapping")
        if described.get("name") != "one-source-grid" or described.get("genesis_generator") != GENESIS_GENERATOR:
            raise ValueError(f"unknown world or genesis generator: "
                             f"{described.get('name')!r} {described.get('genesis_generator')!r}")
        values: dict[str, Any] = {}
        for name in INTEGER_LEVERS:
            value = described.get(name)
            if type(value) is not int:
                raise ValueError(f"world lever {name} must be an integer, got {value!r}")
            values[name] = value
        yield_set = described.get("yield_set")
        if not isinstance(yield_set, list):
            raise ValueError(f"yield_set must be a list, got {yield_set!r}")
        switches = {"on": True, "off": False}
        if any(not isinstance(described.get(name), str) or described.get(name) not in switches
               for name in ("yield", "scoring")):
            raise ValueError("yield and scoring must each be 'on' or 'off'")
        trips = described.get("trips", "off")
        if not isinstance(trips, str) or trips not in switches:
            raise ValueError("trips must be 'on' or 'off'")
        water = described.get("water", "off")
        if not isinstance(water, str) or water not in switches:
            raise ValueError("water must be 'on' or 'off'")
        water_values: dict[str, Any] = {}
        if switches[water]:
            for name in WATER_LEVERS:
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"water lever {name} must be an integer, got {value!r}")
                water_values[name] = value
        config = cls(**values, yield_set=tuple(yield_set), yield_on=switches[described["yield"]],
                     scoring_on=switches[described["scoring"]], plan_trips=switches[trips],
                     water_on=switches[water], **water_values)
        if config.describe() != dict(described):
            raise ValueError("the world description does not round-trip exactly")
        return config


def _homes_from(rng: random.Random, config: WorldConfig) -> dict[str, tuple[int, int]]:
    """First RNG draw: distinct cells for every person, never the source cell."""
    cells = [(x, y) for y in range(config.height) for x in range(config.width)
             if (x, y) != config.source_position and not (config.water_on and (x, y) == config.water_position)]
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
    sources = {FOOD_SOURCE: Source(stock=config.source_stock, authorised=frozenset(actors))}
    water: dict[str, Any] = {}
    if config.water_on:
        sources[WATER_SOURCE] = Source(stock=config.water_stock, authorised=frozenset(actors), resource=WATER)
        water = {"holdings": {WATER: {actor: config.starting_water for actor in actors}}, "consumed_by": {WATER: 0}}
    ledger = WorldState.genesis(
        balances={actor: config.starting_food for actor in actors},
        sources=sources,
        **water,
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
        thirst={actor: 0 for actor in actors} if config.water_on else {},
    )
    return ledger, overlay
