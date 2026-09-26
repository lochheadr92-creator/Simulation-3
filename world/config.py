"""The declared world levers and the seeded genesis.

Levers are the ones ROADMAP Stage 2 allows: geometry, distribution, renewal,
initial supplies, perception radius, consumption rates, and the crowd-yield
trait set. Changing one is a new configuration, and every value is written
into the run header so a run is readable on its own.

Genesis uses one named deterministic generator, `homes-uniform-v1+yield-v1`:
homes are drawn without replacement from every cell except the source cells
(every food and water source) using `random.Random(seed)`, then `yield_at` is
drawn from the same RNG instance. Home draws are unchanged from
`homes-uniform-v1`. Nothing else in a run uses randomness; decisions and
processes are pure rules (DOCTRINE: no runtime randomness through Stage 3).

The default world (2026-09-26) has two food sources and, with water on, two
water sources. The world before that, one food source and no water, is
`ONE_SOURCE_FOOD_ONLY`; its headers, decisions and records are unchanged.

Warmth (2026-09-27) is the third need and the only one met by a place rather
than by a resource: a person's home cell is their shelter, cold rises away
from it and falls on it, and nothing is claimed, carried or consumed.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from kernel import Source, WorldState

from world.overlay import Overlay

GENESIS_GENERATOR = "homes-uniform-v1+yield-v1"
TERRAIN_GENERATOR = "terrain-uniform-v1"   # its own stream, so terrain levers never move a home
FOOD_SOURCE = "food"
WATER_SOURCE = "water"         # the water source id
WATER = "water"                # the kernel's named resource for water
WATER_LEVERS = ("starting_water", "water_stock", "water_cap", "water_renewal_every", "water_renewal_amount",
                "draw_amount", "thirst_rate", "quench", "thirsty_at", "thirst_emergency_at", "thirst_death_at")
WARMTH_LEVERS = ("cold_rate", "warming", "cold_at", "cold_emergency_at", "cold_death_at")
DISTANCE_METRIC = "chebyshev"
PERCEPTION_BOUNDARY = "distance <= radius"
DEFAULT_YIELD_SET = (1, 2, 3)

# The defaults before 2026-09-25: an 11-tick window from hungry (5) to dead (16)
# that kept people within about 8 steps of food, claims of 2, and no early
# departure. Kept so earlier checkpoint results and fixtures can be reproduced:
# WorldConfig(seed=..., **SHORT_RANGE_LEVERS).
SHORT_RANGE_LEVERS = {"hungry_at": 5, "emergency_at": 10, "death_at": 16, "satiation": 6,
                      "renewal_every": 3, "claim_amount": 2, "plan_trips": False,
                      "food_sources": 1, "water_on": False, "warmth_on": False, "stagger_start": False,
                      "terrain_on": False, "building_on": False, "offers_on": False, "births_on": False,
                      "childhood_on": False}

# The world before the second food source and default water (2026-09-25): one
# food source and no water. WorldConfig(seed=..., **ONE_SOURCE_FOOD_ONLY).
ONE_SOURCE_FOOD_ONLY = {"food_sources": 1, "water_on": False, "warmth_on": False, "stagger_start": False,
                        "terrain_on": False, "building_on": False, "offers_on": False, "births_on": False,
                        "childhood_on": False}
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
    water_on: bool = True         # a second need: thirst, met from water sources (2026-09-25; default on)
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
    food_sources: int = 2         # 1 or 2 food sources (the second from 2026-09-25), each with the levers above
    water_sources: int = 2        # 1 or 2 water sources when water is on, each with the water levers
    warmth_on: bool = True        # a third need: cold, met by sheltering at home (2026-09-27; default on)
    stagger_start: bool = True    # spread starting hunger and thirst across the roster so nobody runs in step
    terrain_on: bool = True       # rough ground and shelter spots scattered over the grid (2026-09-27)
    rough_pct: int = 18           # percent of free cells that are rough: crossing one costs an extra tick
    shelter_pct: int = 6          # percent of free cells that are shelter spots
    shelter_relief: int = 1       # hunger and thirst each rise this much slower on a shelter spot
    route_around: bool = True     # walk round rough ground you can see, rather than straight through it
    building_on: bool = True      # a fed, watered person at home spends their spare ticks building there
    build_ticks: int = 12         # ticks of work a shelter takes; interrupted work keeps its progress
    offers_on: bool = True        # carry a spare unit to somebody visibly starving nearby (2026-09-27)
    requests_on: bool = False     # asking for food: built and watchable, but see WORLD_DIRECTIONS.md (2026-09-28)
    births_on: bool = True        # the roster grows when life is good (2026-09-27)
    together_ticks: int = 3       # consecutive ticks two settled neighbours must spend side by side
    childhood_on: bool = True     # the newly born are children for a while (2026-09-28)
    adult_at: int = 60            # ticks lived before a child is grown
    child_leash: int = 5          # how far from home a child will go for food or water
    cold_rate: int = 1            # cold added per tick spent away from shelter
    warming: int = 3              # cold removed per tick spent at shelter
    cold_at: int = 25             # cold at which a person seeks shelter
    cold_emergency_at: int = 50
    cold_death_at: int = 80

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
            "capacity": self.actors <= self.width * self.height - len(self.all_source_positions()),
            "sources": (self.food_sources in (1, 2) and self.water_sources in (1, 2)
                        and len(set(self.all_source_positions())) == len(self.all_source_positions())),
            "water": (not self.water_on) or (
                self.starting_water >= 0 and 0 <= self.water_stock <= self.water_cap
                and self.water_renewal_every >= 1 and self.water_renewal_amount >= 0 and self.draw_amount >= 1
                and self.thirst_rate >= 0 and self.quench >= 1
                and 0 <= self.thirsty_at <= self.thirst_emergency_at < self.thirst_death_at
                and self.water_position != self.source_position),
            "water_with_scoring": not (self.water_on and self.scoring_on),   # scoring has no water actions yet
            "warmth": (not self.warmth_on) or (
                self.cold_rate >= 0 and self.warming >= 1
                and 0 <= self.cold_at <= self.cold_emergency_at < self.cold_death_at),
            "warmth_with_scoring": not (self.warmth_on and self.scoring_on),  # nor warmth actions
            "requests_with_scoring": not (self.requests_on and self.scoring_on),  # nor asking
            "building": (not self.building_on) or self.build_ticks >= 1,
            "terrain": (not self.terrain_on) or (
                0 <= self.rough_pct and 0 <= self.shelter_pct and self.rough_pct + self.shelter_pct <= 90
                and self.shelter_relief >= 0),
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"invalid world configuration: {', '.join(bad)}")
        object.__setattr__(self, "yield_set", tuple(self.yield_set))

    @property
    def name(self) -> str:
        return "grid-world"

    @property
    def source_position(self) -> tuple[int, int]:
        return (self.width // 2, self.height // 2)

    @property
    def water_position(self) -> tuple[int, int]:
        return (self.width // 4, self.height // 4)

    def food_source_ids(self) -> tuple[str, ...]:
        return (FOOD_SOURCE, FOOD_SOURCE + "2")[: self.food_sources]

    def food_positions(self) -> tuple[tuple[int, int], ...]:
        return ((self.width // 2, self.height // 2), (3 * self.width // 4, self.height // 4))[: self.food_sources]

    def water_source_ids(self) -> tuple[str, ...]:
        return (WATER_SOURCE, WATER_SOURCE + "2")[: self.water_sources] if self.water_on else ()

    def water_positions(self) -> tuple[tuple[int, int], ...]:
        if not self.water_on:
            return ()
        return ((self.width // 4, self.height // 4), (self.width // 4, 3 * self.height // 4))[: self.water_sources]

    def all_source_positions(self) -> tuple[tuple[int, int], ...]:
        return self.food_positions() + self.water_positions()

    def terrain(self) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
        """Rough cells and shelter cells, drawn once from their own generator.

        Sources and homes are left as open ground, so terrain only ever changes
        the journey, never where somebody lives or what a source costs to use.
        The stream is seeded apart from the genesis one: changing a terrain
        lever cannot move a home or a trait."""
        return _terrain_of(self)

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
                "thirst_rate * steps reaches thirsty_at")
        if self.warmth_on:
            # Written only when on, so every earlier header still round-trips.
            out["warmth"] = "on"
            for name in WARMTH_LEVERS:
                out[name] = getattr(self, name)
            out["decision"] += (
                "; warmth, a need met by a place: shelter is a person's own home cell; cold rises by cold_rate "
                "each tick that ends away from it and falls by warming each tick that ends on it, whatever the "
                "person chose; warm at shelter if cold; walk to shelter if cold, or when cold + cold_rate * steps "
                "home reaches cold_at (leave in time)")

        if self.terrain_on:
            rough, shelter = self.terrain()
            out["terrain"] = "on"
            out["terrain_generator"] = TERRAIN_GENERATOR
            out["rough_pct"], out["shelter_pct"], out["shelter_relief"] = (
                self.rough_pct, self.shelter_pct, self.shelter_relief)
            out["rough"] = [list(cell) for cell in rough]
            out["shelter_spots"] = [list(cell) for cell in shelter]
            if self.route_around:
                out["routing"] = ("a person walking somewhere picks their way round the rough ground they can "
                                  "see, counting a rough cell as two ticks and anything else as one, and "
                                  "counting whatever lies beyond their sight as open ground in a straight line; "
                                  "going round a single rough cell costs more than crossing it, so they only "
                                  "avoid a run of them")
            out["ground"] = ("rough ground costs an extra tick to cross: a person who steps onto it spends the "
                             "next tick getting off again; on a shelter spot hunger and thirst each rise "
                             "shelter_relief slower; sources and homes are always open ground")
        if self.building_on:
            out["building"] = "on"
            out["build_ticks"] = self.build_ticks
            out["decision"] += ("; a person who is fed, watered and standing at home with no shelter on it "
                                "spends the tick working on one; a shelter takes build_ticks ticks of work, "
                                "and work already done is kept when a need calls them away; a finished shelter "
                                "is permanent and slows hunger and thirst by shelter_relief for whoever stands "
                                "on it, like a shelter spot")
        if self.offers_on:
            out["offers"] = "on"
            out["decision"] += ("; with nothing of their own calling and a spare unit of food in hand, a person "
                                "who can see somebody in a hunger emergency goes to them - nearest by steps, "
                                "then id - and hands over one unit when they are alongside; the kernel settles "
                                "the handover like any other move of food, and it can be refused")
        if self.requests_on:
            out["requests"] = "on"
            out["decision"] += ("; a hungry person holding no food who can see somebody carrying some asks "
                                "them for it - nearest by steps, then id, never somebody visibly starving - "
                                "and walks on towards the source while they ask, because asking is speech and "
                                "costs no tick. The person asked answers on their next tick: if nothing "
                                "of their own is calling and they hold a unit they agree, and the errand becomes "
                                "theirs until it is delivered or they lose sight of the asker; anybody else "
                                "does not answer at all, and the asking lapses - saying no is not an act either")
        if self.childhood_on:
            out["childhood"] = "on"
            out["adult_at"], out["child_leash"] = self.adult_at, self.child_leash
            out["decision"] += ("; somebody born into the world is a child until they have lived adult_at ticks. "
                                "A child will not go further than child_leash steps from home for food or water, "
                                "builds nothing and has no children of their own, and a parent who is free and "
                                "holding food takes a unit to their own child, in view and carrying none, before "
                                "anybody else")
        if self.births_on:
            out["births"] = "on"
            out["together_ticks"] = self.together_ticks
            out["decision"] += ("; when two people who have each finished a shelter, and who are neither hungry "
                                "nor thirsty nor cold, stand on adjacent cells for together_ticks ticks running, "
                                "a new person arrives: a home on the nearest free cell to the first of them, "
                                "nothing held, every need at nought. A birth creates no food and no water")
        if self.stagger_start:
            # Written only when on, so the worlds that started level round-trip.
            out["stagger_start"] = "on"
            out["genesis_stagger"] = ("person i of n starts at hunger i * hungry_at // n, and with water on at "
                                      "thirst i * thirsty_at // n, so the roster does not get hungry in step")
        if self.water_on or self.warmth_on:
            out["decision"] += (
                "; when more than one need calls, serve the one with the least slack, where a need's slack is "
                "(its lethal level - its level) // its rate, the ticks before it kills at the rate it rises; "
                "how far its remedy is does not enter, because subtracting the walk makes two needs swap places "
                "every step; a need that does not rise never runs out; on ties thirst, then cold, then hunger")
        # Written only when there is more than one, so earlier headers round-trip.
        if self.food_sources > 1:
            out["food_sources"] = [{"id": i, "position": list(p)}
                                   for i, p in zip(self.food_source_ids(), self.food_positions())]
        if self.water_on and self.water_sources > 1:
            out["water_sources"] = [{"id": i, "position": list(p)}
                                    for i, p in zip(self.water_source_ids(), self.water_positions())]
        if self.food_sources > 1 or (self.water_on and self.water_sources > 1):
            out["decision"] += ("; with several sources of a kind, head for the nearest (steps, then id) seen "
                                "with free stock, or the nearest if none in view has stock; a claim or draw "
                                "takes from that source, recorded as the decision's target")
            out["perception"] += ("; with several sources, every source position is a known landmark and "
                                  "seen_stock records the free stock of each source in view")
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
        if described.get("name") != "grid-world" or described.get("genesis_generator") != GENESIS_GENERATOR:
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
        warmth = described.get("warmth", "off")
        if not isinstance(warmth, str) or warmth not in switches:
            raise ValueError("warmth must be 'on' or 'off'")
        need_values: dict[str, Any] = {}
        terrain = described.get("terrain", "off")
        if not isinstance(terrain, str) or terrain not in switches:
            raise ValueError("terrain must be 'on' or 'off'")
        if switches[terrain]:
            for name in ("rough_pct", "shelter_pct", "shelter_relief"):
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"terrain lever {name} must be an integer, got {value!r}")
                need_values[name] = value
        building = described.get("building", "off")
        if not isinstance(building, str) or building not in switches:
            raise ValueError("building must be 'on' or 'off'")
        if switches[building]:
            value = described.get("build_ticks")
            if type(value) is not int:
                raise ValueError(f"build_ticks must be an integer, got {value!r}")
            need_values["build_ticks"] = value
        childhood = described.get("childhood", "off")
        if not isinstance(childhood, str) or childhood not in switches:
            raise ValueError("childhood must be 'on' or 'off'")
        if switches[childhood]:
            for name in ("adult_at", "child_leash"):
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"{name} must be an integer, got {value!r}")
                need_values[name] = value
        requests = described.get("requests", "off")
        if not isinstance(requests, str) or requests not in switches:
            raise ValueError("requests must be 'on' or 'off'")
        births = described.get("births", "off")
        if not isinstance(births, str) or births not in switches:
            raise ValueError("births must be 'on' or 'off'")
        if switches[births]:
            value = described.get("together_ticks")
            if type(value) is not int:
                raise ValueError(f"together_ticks must be an integer, got {value!r}")
            need_values["together_ticks"] = value
        offers = described.get("offers", "off")
        if not isinstance(offers, str) or offers not in switches:
            raise ValueError("offers must be 'on' or 'off'")
        stagger = described.get("stagger_start", "off")
        if not isinstance(stagger, str) or stagger not in switches:
            raise ValueError("stagger_start must be 'on' or 'off'")
        if switches[water]:
            for name in WATER_LEVERS:
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"water lever {name} must be an integer, got {value!r}")
                need_values[name] = value
        if switches[warmth]:
            for name in WARMTH_LEVERS:
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"warmth lever {name} must be an integer, got {value!r}")
                need_values[name] = value
        counts: dict[str, int] = {}
        for key in ("food_sources", "water_sources"):
            listed = described.get(key)
            if listed is not None and not isinstance(listed, list):
                raise ValueError(f"{key} must be a list when present, got {listed!r}")
            counts[key] = len(listed) if listed is not None else 1
        if not switches[water]:
            counts["water_sources"] = cls.__dataclass_fields__["water_sources"].default   # unused when off
        config = cls(**values, yield_set=tuple(yield_set), yield_on=switches[described["yield"]],
                     scoring_on=switches[described["scoring"]], plan_trips=switches[trips],
                     water_on=switches[water], warmth_on=switches[warmth],
                     stagger_start=switches[stagger], terrain_on=switches[terrain],
                     building_on=switches[building], offers_on=switches[offers],
                     births_on=switches[births], requests_on=switches[requests],
                     childhood_on=switches[childhood], **need_values, **counts)
        if config.describe() != dict(described):
            raise ValueError("the world description does not round-trip exactly")
        return config


@lru_cache(maxsize=None)
def _terrain_of(config: "WorldConfig") -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    if not config.terrain_on:
        return (), ()
    taken = set(config.all_source_positions()) | set(homes_for(config).values())
    free = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) not in taken]
    rough_count = len(free) * config.rough_pct // 100
    shelter_count = len(free) * config.shelter_pct // 100
    picks = random.Random(config.seed + 1_000_003).sample(free, rough_count + shelter_count)
    return tuple(sorted(picks[:rough_count])), tuple(sorted(picks[rough_count:]))


def _homes_from(rng: random.Random, config: WorldConfig) -> dict[str, tuple[int, int]]:
    """First RNG draw: distinct cells for every person, never a source cell."""
    cells = [(x, y) for y in range(config.height) for x in range(config.width)
             if (x, y) not in config.all_source_positions()]
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


def staggered(config: WorldConfig, level_at: int) -> dict[str, int]:
    """Starting levels spread evenly across the roster, so people do not all
    reach a need on the same tick. No randomness: person i of n starts at
    i * level_at // n."""
    actors = config.actor_ids()
    if not config.stagger_start:
        return {actor: 0 for actor in actors}
    return {actor: index * level_at // len(actors) for index, actor in enumerate(actors)}


def genesis(config: WorldConfig) -> tuple[WorldState, Overlay]:
    """The saved initial state: a kernel ledger and the overlay beside it."""
    actors = config.actor_ids()
    sources = {source_id: Source(stock=config.source_stock, authorised=frozenset(actors))
               for source_id in config.food_source_ids()}
    water: dict[str, Any] = {}
    if config.water_on:
        sources.update({source_id: Source(stock=config.water_stock, authorised=frozenset(actors), resource=WATER)
                        for source_id in config.water_source_ids()})
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
        hunger=staggered(config, config.hungry_at),
        yield_at=_yield_from(rng, config),
        died_at={},
        thirst=staggered(config, config.thirsty_at) if config.water_on else {},
        cold={actor: 0 for actor in actors} if config.warmth_on else {},
        age={actor: config.adult_at for actor in actors} if config.childhood_on else {},
    )
    return ledger, overlay
