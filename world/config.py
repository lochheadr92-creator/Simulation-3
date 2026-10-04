"""The declared world levers and the seeded genesis.

Levers include geometry, distribution, renewal, initial supplies, perception
radius, consumption rates, and the crowd-yield trait set.
Changing one is a new configuration, and every value is written
into the run header so a run is readable on its own.

Genesis uses one named deterministic generator, `homes-uniform-v1+yield-v1`:
homes are drawn without replacement from every cell except the source cells
(every food and water source) using `random.Random(seed)`, then `yield_at` is
drawn from the same RNG instance. Home draws are unchanged from
`homes-uniform-v1`. Nothing else in a run uses randomness; decisions and
processes are pure rules.

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
from dataclasses import dataclass, fields
from functools import cached_property
from typing import Any

from kernel import Source, WorldState

from world.overlay import Overlay
from world.persona import Persona, genesis_persona
from world.sky import sky_at
from world.registry import (FEATURES, LEVER_DEFAULTS, cross_checks, feature_problems, lever_defaults)
from world.storage import STORE_TARGET, STORE_LOW, FOOD_EXPECT_TICKS, store_id
from world.housing import HOME_CAPACITY, LONG_OUTING, DIFFICULT_OUTINGS, MOVE_COOLDOWN, ROUTE_IMPROVEMENT
from world.foraging import EMPTY_SOURCE_TICKS
from world.fishing import FISH_SOURCE, FISH_STOCK, FISH_RENEWAL_EVERY, FISH_RENEWAL
from world.crafting import STONE, STONE_STOCK, TOOLS
from world.materials import WOOD, WOOD_STOCK, WOOD_RENEWAL_EVERY, WOOD_RENEWAL, WOOD_PACK, WORK_PER_WOOD
from world.ecology import (CONDITION_MAX, FULL_GROWTH_AT, RECOVERY_PER_TICK, WEAR_PER_UNIT,
                           SEASON_TICKS, SEASONS, season_at, seasonal_growth)

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
                      "childhood_on": False, "social_memory_on": False}

# The world before the second food source and default water (2026-09-25): one
# food source and no water. WorldConfig(seed=..., **ONE_SOURCE_FOOD_ONLY).
ONE_SOURCE_FOOD_ONLY = {"food_sources": 1, "water_on": False, "warmth_on": False, "stagger_start": False,
                        "terrain_on": False, "building_on": False, "offers_on": False, "births_on": False,
                        "childhood_on": False, "social_memory_on": False}
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
    regrowth_on: bool = False     # food patches wear after harvest and recover on quiet ticks
    seasons_on: bool = False      # alternate plentiful and lean food growth
    stores_on: bool = False       # spare food at founding homes can be collected by neighbours
    homes_on: bool = False        # grown children choose and physically move into their first adult home
    relocation_on: bool = False   # adults can move after repeated costly supply outings
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
    route_around: bool = True     # walk round known rough ground, including rough cells remembered from earlier views
    building_on: bool = True      # a fed, watered person at home spends their spare ticks building there
    build_ticks: int = 12         # ticks of work a shelter takes; interrupted work keeps its progress
    offers_on: bool = True        # carry a spare unit to somebody visibly starving nearby (2026-09-27)
    social_memory_on: bool = True  # remember received food and favour former helpers in distress
    requests_on: bool = False     # asking for food: built and watchable, but see WORLD_DIRECTIONS.md (2026-09-28)
    adjacent_requests: bool = False  # requests may start a handoff, never a walking errand
    births_on: bool = True        # the roster grows when life is good (2026-09-27)
    together_ticks: int = 3       # consecutive ticks two settled neighbours must spend side by side
    birth_spacing: int = 0        # recovery ticks before either adult can begin another birth countdown
    childhood_on: bool = True     # the newly born are children for a while (2026-09-28)
    shared_care_on: bool = False  # record both birth parents and give both the existing caregiving role
    care_by_need_on: bool = False  # prefer visibly starving children among empty-handed dependents
    water_care_on: bool = False   # parents bring water to dependent children who cannot reach it themselves
    adult_at: int = 60            # ticks lived before a child is grown
    child_leash: int = 5          # how far from home a child will go for food or water
    cold_rate: int = 1            # cold added per tick spent away from shelter
    warming: int = 3              # cold removed per tick spent at shelter
    cold_at: int = 25             # cold at which a person seeks shelter
    cold_emergency_at: int = 50
    cold_death_at: int = 80
    wood_on: bool = False         # gather and spend wood to build shelters
    fishing_on: bool = False      # one bank fishing spot with season-independent stock
    source_memory_on: bool = False  # remember empty natural food sources for later journeys
    provisioning_on: bool = False  # make food trips for a low shared home cache
    knowledge_sharing_on: bool = False  # share firsthand empty-source sightings with adjacent housemates
    coordination_on: bool = False  # briefly trust a nearby housemate's announced food trip
    features: tuple[str, ...] = ()  # optional rich-world features, by name: see world/registry.py
    feature_levers: tuple[tuple[str, int], ...] = ()  # settings that differ from their feature's defaults

    def __post_init__(self) -> None:
        # Check every scalar integer, including inactive feature settings, before
        # comparisons, geometry, random seeds or canonical identities use it.
        # Annotations are strings under postponed evaluation; bool is not int.
        bad_types = [field.name for field in fields(self)
                     if field.type in (int, "int") and type(getattr(self, field.name)) is not int]
        if bad_types:
            raise ValueError(f"world configuration requires integer values: {', '.join(bad_types)}")
        bad_booleans = [field.name for field in fields(self)
                        if field.type in (bool, "bool") and type(getattr(self, field.name)) is not bool]
        if bad_booleans:
            raise ValueError(f"world configuration requires boolean values: {', '.join(bad_booleans)}")
        if not isinstance(self.yield_set, (tuple, list)):
            raise ValueError("yield_set must be a tuple or list of positive integers")
        try:
            features = tuple(self.features)
            overrides = dict(self.feature_levers)
        except (TypeError, ValueError) as exc:
            raise ValueError("features must be a list of names and feature_levers name/value pairs") from exc
        # Store only the settings that differ from their defaults, so a configuration
        # rebuilt from its own description compares equal to the original.
        defaults = lever_defaults(features)
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "feature_levers", tuple(sorted(
            ((name, value) for name, value in overrides.items() if defaults.get(name) != value),
            key=lambda item: str(item[0]))))
        checks = {
            "features": not feature_problems(self.features, self.feature_levers)
                        and not cross_checks(self.features, self.feature_levers),
            "features_with_scoring": not (self.features and self.scoring_on),   # scoring has no rich actions
            "regrowth": type(self.regrowth_on) is bool,
            "seasons": type(self.seasons_on) is bool,
            "stores": type(self.stores_on) is bool,
            "provisioning": type(self.provisioning_on) is bool and (not self.provisioning_on or self.stores_on),
            "coordination": type(self.coordination_on) is bool and (not self.coordination_on or self.provisioning_on),
            "homes": type(self.homes_on) is bool and (not self.homes_on or self.childhood_on),
            "shared_care": not self.shared_care_on or self.childhood_on,
            "care_by_need": not self.care_by_need_on or self.childhood_on,
            "water_care": not self.water_care_on or (self.childhood_on and self.water_on),
            "relocation": type(self.relocation_on) is bool and (not self.relocation_on or self.homes_on),
            "knowledge_sharing": type(self.knowledge_sharing_on) is bool and (not self.knowledge_sharing_on or self.source_memory_on),
            "source_memory": type(self.source_memory_on) is bool,
            "fishing": type(self.fishing_on) is bool,
            "wood": type(self.wood_on) is bool and (not self.wood_on or self.building_on),
            "social_memory": type(self.social_memory_on) is bool,
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
            "capacity": self.actors <= self.width * self.height - len(self.food_positions() + self.water_positions()),
            "sources": (self.food_sources in (1, 2) and self.water_sources in (1, 2)
                        and len(set(self.food_positions() + self.water_positions())) == len(self.food_positions() + self.water_positions())),
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
            "pledges_with_requests": not (self.on("pledges") and self.requests_on),   # one way of asking, not two
            "crafting_needs_wood": not self.on("crafting") or (self.wood_on and self.building_on),
            "adjacent_requests": type(self.adjacent_requests) is bool and (not self.adjacent_requests or self.requests_on),
            "building": (not self.building_on) or self.build_ticks >= 1,
            "birth_spacing": type(self.birth_spacing) is int and self.birth_spacing >= 0,
            "terrain": (not self.terrain_on) or (
                0 <= self.rough_pct and 0 <= self.shelter_pct and self.rough_pct + self.shelter_pct <= 90
                and self.shelter_relief >= 0),
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"invalid world configuration: {', '.join(bad)}")
        object.__setattr__(self, "yield_set", tuple(self.yield_set))
        if self.fishing_on and not fishing_sites(self):
            raise ValueError("fishing needs a clear bank cell outside homes and sources")
        if self.wood_on and not wood_sites(self):
            raise ValueError("wood needs at least one clear cell outside homes and existing sources")

    @property
    def name(self) -> str:
        return "grid-world"

    def on(self, feature: str) -> bool:
        """Whether an optional rich-world feature is switched on."""
        return feature in self.features

    @cached_property
    def _lever_values(self) -> dict[str, int]:
        return {**LEVER_DEFAULTS, **dict(self.feature_levers)}

    def lever(self, name: str) -> int:
        """The effective value of a feature setting: its default unless overridden."""
        return self._lever_values[name]

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
        return (self.food_positions() + self.water_positions()
                + tuple(pos for _,pos in wood_sites(self) + fishing_sites(self) + stone_sites(self)))

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
        if self.regrowth_on:
            out["regrowth"] = "on"
            out["patch_rules"] = {"condition_max": CONDITION_MAX, "full_growth_at": FULL_GROWTH_AT,
                                  "wear_per_unit": WEAR_PER_UNIT, "recovery_per_tick": RECOVERY_PER_TICK}
            out["patch_recovery"] = ("Food patches start at full condition. Each unit actually harvested "
                                     "removes wear_per_unit condition, floored at zero. A tick without a "
                                     "successful harvest restores recovery_per_tick, capped at condition_max. "
                                     "After that update, on the usual renewal tick, a patch below full_growth_at "
                                     "grows half renewal_amount rounded up; otherwise it grows renewal_amount. "
                                     "Stock remains capped, zero renewal stays zero, and water is unchanged.")
        if self.knowledge_sharing_on:
            out["knowledge_sharing"] = "on"
            out["knowledge_sharing_rule"] = (
                "Alongside their normal action, living people tell visible housemates within one "
                "Chebyshev cell their most recent firsthand empty natural-food sighting, source id breaking ties. "
                "Listeners use it next tick; reports retain source, speaker, sighting tick and heard tick. "
                "Newest sightings win, then speaker id. Own equally recent or newer sight overrides reports. "
                "Current sight always overrides reports, and reports expire empty_source_ticks after the "
                "original sighting, never after retelling. Reports cannot be relayed. Food and optional "
                "provisioning use the existing source ranking with these additional empty-source reports; "
                "needs, gathering, movement, accounting and water rules stay unchanged.")
        if self.source_memory_on:
            out["source_memory"] = "on"
            out["empty_source_ticks"] = EMPTY_SOURCE_TICKS
            out["source_memory_rule"] = (
                "Remember empty berry patches and fishing spots observed at tick start. "
                "Current visible stock clears an empty memory; visible emptiness refreshes its date. "
                "Forget after empty_source_ticks without seeing it empty. Prefer visible stocked food, "
                "then sources not remembered empty, then the nearest fallback when all are remembered empty. "
                "Rank within each group by travel plus gathering effort, then source id. "
                "Caches still attract only while visibly stocked. Memory never reveals distant stock.")
        if self.fishing_on:
            out["fishing"] = "on"
            out["fishing_sources"] = [{"id": sid, "position": list(pos)} for sid,pos in fishing_sites(self)]
            out["fishing_rules"] = {"stock": FISH_STOCK, "cap": FISH_STOCK,
                                    "renewal_every": FISH_RENEWAL_EVERY, "renewal": FISH_RENEWAL}
            out["fishing_rule"] = (
                "One tick casts from the bank, the next consecutive food claim catches up to claim_amount. "
                "Other actions interrupt the cast. Catches are ordinary food, settled against finite stock. "
                "Fish renew independently of berry wear and seasons. Positions are known landmarks; "
                "stock is visible only in sight. Travel choice includes one extra step of fishing effort.")
        if self.wood_on:
            out["wood"] = "on"
            out["wood_sources"] = [{"id": sid, "position": list(pos)} for sid,pos in wood_sites(self)]
            out["wood_rules"] = {"stock": WOOD_STOCK, "cap": WOOD_STOCK,
                                 "renewal_every": WOOD_RENEWAL_EVERY, "renewal": WOOD_RENEWAL,
                                 "pack": WOOD_PACK, "work_per_wood": WORK_PER_WOOD}
            out["wood_rule"] = (
                "Adults with an unfinished home gather wood when their next building work needs it. "
                "Needs, helping and housing choices retain priority. Grove positions are known landmarks; "
                "only visible stocks are known. Prefer the nearest visible stocked grove, otherwise the "
                "nearest grove, by distance then id. Walk there, claim up to pack or the remaining shelter "
                "requirement, carry it home, then build. Pay one wood through settlement before each group "
                "of work_per_wood building ticks. A refused payment gives no work. Wood stays in the named "
                "consumption sink after use; interrupted work is kept. Groves renew independently of food "
                "and seasons, up to their cap. No wood trading, storage, skills or salvage is added.")
        if self.on("crafting"):
            out["stone_sources"] = [{"id": sid, "position": list(pos)} for sid, pos in stone_sites(self)]
        if self.relocation_on:
            out["relocation"] = "on"
            out["relocation_rules"] = {"long_outing": LONG_OUTING, "difficult_outings": DIFFICULT_OUTINGS,
                                       "cooldown": MOVE_COOLDOWN, "route_improvement": ROUTE_IMPROVEMENT}
            out["relocation_rule"] = (
                "Adults remember finished shelters seen with room, refreshing vacancies only in sight. "
                "Count ticks spent walking, waiting, asking or collecting food/water away from home, until "
                "returning home. An outing of at least long_outing ticks raises home strain by one, up to "
                "difficult_outings; a shorter supply outing lowers it by one. At that threshold, after "
                "cooldown ticks since the last home choice or genesis, an adult without dependent children "
                "can walk to a remembered shelter whose combined food/water landmark distance is shorter "
                "by route_improvement. Prefer the shortest supply routes, then walking distance, row and "
                "column. Needs and helping retain priority. Warm fully before leaving home; when warmth "
                "calls en route, the chosen finished shelter can replace the old home if it is no farther "
                "away. Keep the destination through interruptions, "
                "but recheck room in sight and on arrival. A successful move resets strain and outing effort; "
                "old shelters, food and family links remain. Offspring first make their adult home choice.")
        if self.homes_on:
            out["homes"] = "on"
            out["home_capacity"] = HOME_CAPACITY
            out["home_rule"] = (
                "A grown child who would walk home, build or rest chooses an adult home once. "
                "Only currently visible finished shelters with room or clear sites are candidates. "
                "Prefer finished shelters, then the shortest combined distance to known food and water "
                "landmarks, distance from the current home, row and column. A chosen destination persists "
                "through interruptions; needs and helping keep priority. Walk there before settling. "
                "Arrivals use the tick's rotated roster; finished homes hold up to home_capacity living "
                "residents, while an unbuilt site must be free of other homes. Reset building progress "
                "and time together after settling. Old shelters and food stay in place. With stores on, "
                "record an empty cache at a new site; anyone living there can deposit. Six food is a "
                "refill target, not a hard cap: simultaneous residents can overshoot it. Newborns retain "
                "their own nearby childhood home until making this choice. No later relocation rule.")
        if self.coordination_on:
            out["coordination"] = "on"
            out["food_expect_ticks"] = FOOD_EXPECT_TICKS
            out["coordination_rule"] = (
                "Starting a provisioning outing announces it to living housemates in sight at tick start. "
                "Speech costs no extra action; listeners hear after making this tick's choices. "
                "Remember one speaker and the completed heard tick; simultaneous speakers use ID order. "
                "For food_expect_ticks, postpone only a new optional cache trip. Needs, helping, "
                "warming and existing outings keep priority. At the next tick start, seeing that "
                "speaker's death at the just-completed boundary ends the expectation: use both "
                "people's final positions and the listener's sight radius. Older deaths discovered "
                "later do not count as witnessed. Seeing that speaker back at home with "
                "at most one carried meal or "
                "seeing at least provision_low meals in one's home cache ends the expectation early. "
                "Unseen events do not update it. Moving home or dying clears one's expectation; "
                "births preserve existing listeners. There is no same-tick worker allocation.")
        if self.provisioning_on:
            out["provisioning"] = "on"
            out["provision_low"] = STORE_LOW
            out["provision_rule"] = (
                "An adult at their finished home who would rest, holds at most one meal, "
                "and sees fewer than provision_low meals in the shared cache starts a food outing "
                "after warming fully at home. "
                "Use natural food sources with normal local stock and empty-source memory ranking; "
                "never haul from another cache. Collect once through normal settlement, then return. "
                "Needs, helping, building and home changes keep priority. Interruptions retain the "
                "outing until home arrival, a move or death; births preserve other people's outings. "
                "At home the existing deposit rule keeps one meal and stores any spare food.")
        if self.stores_on:
            out["stores"] = "on"
            out["food_stores"] = [{"id": sid, "position": list(pos), "resident": resident}
                                  for sid, pos, resident in store_sites(self)]
            out["store_target"] = STORE_TARGET
            out["store_rule"] = (
                "Founding homes have empty shared food caches. Once their shelter is built, "
                "an adult resident who would rest deposits spare food, keeping one carried meal "
                "and filling towards store_target. Needs and helping retain priority. Any person "
                "can choose a visible stocked cache at a finished shelter alongside visible food "
                "patches by distance then id, walk there and claim normally. Empty or unseen caches "
                "do not attract trips. Deposits and claims settle through the kernel; deposits "
                "become available next tick. Caches never grow food and remain after a resident "
                "dies. Newborns can collect but have no new cache of their own.")
        if self.seasons_on:
            out["seasons"] = "on"
            out["season_ticks"] = SEASON_TICKS
            out["season_growth"] = {name: seasonal_growth(self.renewal_amount, name) for name in SEASONS}
            out["season_rule"] = (
                "Start plentiful at tick zero; alternate plentiful and lean every season_ticks. "
                "The completed tick sets the season before renewal. Plentiful grows 150% of "
                "renewal_amount rounded up; lean grows 50% rounded down. With local regrowth, "
                "apply patch wear to that seasonal amount afterwards. Cadence and stock caps "
                "stay the same; zero renewal stays zero. Water, cold and patch recovery are unchanged.")
        if self.plan_trips:
            # Written only when on, so a header from before this rule existed
            # (which never carried it) still round-trips, as trips off.
            out["trips"] = "on"
            out["decision"] = out["decision"].replace(
                "walk to the source if hungry; else walk home",
                "walk to the source if hungry, or when holding no food and hunger + hunger_rate * steps to the "
                "source reaches hungry_at (leave in time); else walk home")
            if self.fishing_on:
                out["decision"] = out["decision"].replace(
                    "steps to the source reaches", "(steps to the source + one casting tick for fishing) reaches")
                out["fishing_rule"] += (
                    " With planned trips, an empty-handed person leaves one casting tick earlier and may cast "
                    "at stocked fish before hungry when hunger + hunger_rate reaches hungry_at. "
                    "For personal food trips, claiming and eating still require hunger.")
        if self.plan_trips and self.terrain_on and self.route_around:
            out["decision"] += (
                "; personal food departure timing uses the selected route estimate over seen and "
                "personally remembered rough ground, plus any current personal movement delay: "
                "known rough costs two ticks, other ground one; "
                "unseen ground stays open in the estimate. This changes departure timing only, "
                "not source selection, water or shelter planning. Nominal hunger rate and any "
                "fishing cast still apply; interruptions, contention and shelter relief are not predicted.")
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
                out["routing"] = ("a person walking somewhere picks their way round rough ground they can see "
                                  "or remember, counting a known rough cell as two ticks and anything else as "
                                  "one; ground that has never been seen is still treated as open, so a route "
                                  "learned is kept but the unknown stays unknown; equal-cost routes keep "
                                  "the straight first step when possible")
            out["ground"] = ("rough ground costs an extra tick to cross: a person who steps onto it spends the "
                             "next tick getting off again; on a shelter spot hunger and thirst each rise "
                             "shelter_relief slower; sources and homes are always open ground")
        if not self.terrain_on and not self.route_around:
            out["route_around"] = False
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
        if self.social_memory_on:
            out["social_memory"] = "on"
            out["decision"] += ("; remember the four most recent distinct people whose food transfers "
                                "actually arrived, dated by completed tick, keeping names after death. "
                                "For unsolicited help, prefer remembered donors among visible people in "
                                "a hunger emergency, then distance and id. Own needs, dependent children, "
                                "direct answers and existing promises keep their priority")
        if self.requests_on:
            out["requests"] = "on"
            out["decision"] += ("; a hungry person holding no food who can see somebody carrying some asks "
                                "them for it - nearest by steps, then id, never somebody visibly starving - "
                                "and walks on towards the source while they ask, because asking is speech and "
                                "costs no tick. The person asked answers on their next tick: a direct handoff "
                                "to an empty-handed asker alongside needs no walking agreement and is allowed "
                                "for a parent; feeding a dependent child comes first. Otherwise they agree "
                                "if nothing of their own is calling, they hold a unit, they are not already "
                                "carrying one for somebody else, and no child of their own still depends on "
                                "them; the errand is then theirs until it is delivered or they lose sight of "
                                "the living asker. Promises end only when food reaches that recipient, either "
                                "person dies, or they leave sight; feeding someone else does not complete the "
                                "errand. Anybody else does not answer at all and the asking lapses, because "
                                "saying no is not an act either")
        if self.adjacent_requests:
            out["request_range"] = "adjacent"
            out["decision"] += ("; requests are restricted to the same or an adjacent cell. A helper can "
                                "answer with a direct handoff next tick if still alongside, but never "
                                "agrees to a walking errand. Own needs and feeding one's child come first")
        if self.childhood_on:
            out["childhood"] = "on"
            out["adult_at"], out["child_leash"] = self.adult_at, self.child_leash
            out["decision"] += ("; somebody born into the world is a child until they have lived adult_at ticks. "
                                "A child will not go further than child_leash steps from home for food or water, "
                                "builds nothing and has no children of their own, and a parent who is free and "
                                "holding food takes a unit to their own dependent child below adult_at, in view "
                                "and carrying none, before "
                                "anybody else")
            out["decision"] += ("; the child leash also bounds early departures, walking while asking, "
                                "and route detours; an unreachable destination sends a child home")
            out["decision"] += ("; before an early trip home for warmth, a parent hands one food to an "
                                "empty-handed dependent already on the same or an adjacent cell, only "
                                "while below every active need threshold and with no water trip due. "
                                "This does not extend a walking errand")
        if self.care_by_need_on:
            out["care_by_need"] = "on"
            out["decision"] += ("; among visible empty-handed dependent children, prefer those visibly "
                                "in a hunger emergency, then distance and id. Exact hunger is private. "
                                "Personal needs and the existing nearby-handoff exception retain priority; "
                                "parents choose separately, without reserving recipients")
        if self.water_care_on:
            out["water_care"] = "on"
            out["decision"] += ("; a parent with no need calling who has a living dependent child whose home is "
                                "further from water than child_leash, and holds no water, walks to water and draws "
                                "for them. A parent holding water who sees their dependent child in a visible "
                                "thirst emergency hands over one unit through the kernel. Personal needs keep "
                                "priority; parents do not learn an absent child's thirst or position")
        if self.shared_care_on:
            out["shared_care"] = "on"
            out["decision"] += ("; record both adults in each birth as parents. Both have the existing "
                                "local caregiving priority and dependent-child relocation restriction. "
                                "Homes and personal needs are unchanged. Simultaneous handoffs each "
                                "transfer one real unit through settlement; parents do not coordinate "
                                "their choices or learn an absent child's condition")
        if self.births_on:
            out["births"] = "on"
            out["together_ticks"] = self.together_ticks
            out["decision"] += ("; when two people who have each finished a shelter, and who are neither hungry "
                                "nor thirsty nor cold, stand on adjacent cells for together_ticks ticks running, "
                                "a new person arrives: a home on the nearest free open-ground cell to the first "
                                "of them, excluding rough ground and shelter spots, "
                                "nothing held, every need at nought. A birth creates no food and no water")
        if self.birth_spacing:
            out["birth_spacing"] = self.birth_spacing
            out["decision"] += ("; after a birth both adults recover for birth_spacing ticks before "
                                "counting time together again, including with a different partner")
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
        if self.features:
            # Written only when something is on, so every earlier header still round-trips.
            out["features"] = list(self.features)
            out["feature_levers"] = {name: self.lever(name) for name in sorted(lever_defaults(self.features))}
            out["feature_rules"] = {name: FEATURES[name].rule for name in self.features}
            tables = {key: value for name in self.features for key, value in FEATURES[name].tables.items()}
            if tables:
                out["feature_tables"] = tables
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
        routing = described.get("route_around", "routing" in described if switches[terrain] else True)
        if type(routing) is not bool:
            raise ValueError("route_around must be a boolean")
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
        shared_care = described.get("shared_care", "off")
        if not isinstance(shared_care, str) or shared_care not in switches:
            raise ValueError("shared_care must be 'on' or 'off'")
        care_by_need = described.get("care_by_need", "off")
        if not isinstance(care_by_need, str) or care_by_need not in switches:
            raise ValueError("care_by_need must be 'on' or 'off'")
        water_care = described.get("water_care", "off")
        if not isinstance(water_care, str) or water_care not in switches:
            raise ValueError("water_care must be 'on' or 'off'")
        if switches[childhood]:
            for name in ("adult_at", "child_leash"):
                value = described.get(name)
                if type(value) is not int:
                    raise ValueError(f"{name} must be an integer, got {value!r}")
                need_values[name] = value
        requests = described.get("requests", "off")
        if not isinstance(requests, str) or requests not in switches:
            raise ValueError("requests must be 'on' or 'off'")
        request_range = described.get("request_range", "visible")
        if request_range not in ("visible", "adjacent"):
            raise ValueError("request_range must be 'visible' or 'adjacent'")
        births = described.get("births", "off")
        if not isinstance(births, str) or births not in switches:
            raise ValueError("births must be 'on' or 'off'")
        if switches[births]:
            value = described.get("together_ticks")
            if type(value) is not int:
                raise ValueError(f"together_ticks must be an integer, got {value!r}")
            need_values["together_ticks"] = value
        offers = described.get("offers", "off")
        regrowth = described.get("regrowth", "off")
        seasons = described.get("seasons", "off")
        stores = described.get("stores", "off")
        provisioning = described.get("provisioning", "off")
        coordination = described.get("coordination", "off")
        if not isinstance(coordination, str) or coordination not in switches:
            raise ValueError("coordination must be on or off")
        if not isinstance(provisioning, str) or provisioning not in switches:
            raise ValueError("provisioning must be on or off")
        homes = described.get("homes", "off")
        relocation = described.get("relocation", "off")
        knowledge_sharing = described.get("knowledge_sharing", "off")
        if not isinstance(knowledge_sharing, str) or knowledge_sharing not in switches:
            raise ValueError("knowledge_sharing must be on or off")
        source_memory = described.get("source_memory", "off")
        if not isinstance(source_memory, str) or source_memory not in switches:
            raise ValueError("source_memory must be on or off")
        fishing = described.get("fishing", "off")
        if not isinstance(fishing, str) or fishing not in switches:
            raise ValueError("fishing must be on or off")
        wood = described.get("wood", "off")
        if not isinstance(wood, str) or wood not in switches:
            raise ValueError("wood must be 'on' or 'off'")
        if not isinstance(relocation, str) or relocation not in switches:
            raise ValueError("relocation must be 'on' or 'off'")
        if not isinstance(homes, str) or homes not in switches:
            raise ValueError("homes must be 'on' or 'off'")
        if not isinstance(stores, str) or stores not in switches:
            raise ValueError("stores must be 'on' or 'off'")
        if not isinstance(seasons, str) or seasons not in switches:
            raise ValueError("seasons must be 'on' or 'off'")
        if not isinstance(regrowth, str) or regrowth not in switches:
            raise ValueError("regrowth must be 'on' or 'off'")
        social_memory = described.get("social_memory", "off")
        if not isinstance(social_memory, str) or social_memory not in switches:
            raise ValueError("social_memory must be 'on' or 'off'")
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
        features = described.get("features", [])
        if not isinstance(features, list) or any(not isinstance(name, str) for name in features):
            raise ValueError("features must be a list of names")
        feature_levers = described.get("feature_levers", {})
        if not isinstance(feature_levers, dict) or any(type(v) is not int for v in feature_levers.values()):
            raise ValueError("feature_levers must map names to integers")
        config = cls(**values, birth_spacing=described.get("birth_spacing", 0),
                     features=tuple(features), feature_levers=tuple(feature_levers.items()),
                     yield_set=tuple(yield_set), yield_on=switches[described["yield"]],
                     scoring_on=switches[described["scoring"]], plan_trips=switches[trips],
                     water_on=switches[water], warmth_on=switches[warmth],
                     stagger_start=switches[stagger], terrain_on=switches[terrain],
                     route_around=routing,
                     building_on=switches[building], offers_on=switches[offers],
                     social_memory_on=switches[social_memory],
                     regrowth_on=switches[regrowth],
                     seasons_on=switches[seasons],
                     stores_on=switches[stores],
                     provisioning_on=switches[provisioning],
                     coordination_on=switches[coordination],
                     homes_on=switches[homes],
                     relocation_on=switches[relocation],
                     wood_on=switches[wood], fishing_on=switches[fishing],
                     source_memory_on=switches[source_memory],
                     knowledge_sharing_on=switches[knowledge_sharing],
                     births_on=switches[births], requests_on=switches[requests],
                     adjacent_requests=request_range == "adjacent",
                     childhood_on=switches[childhood], shared_care_on=switches[shared_care],
                     care_by_need_on=switches[care_by_need],
                     water_care_on=switches[water_care], **need_values, **counts)
        if config.describe() != dict(described):
            raise ValueError("the world description does not round-trip exactly")
        return config


@lru_cache(maxsize=None)
def _terrain_of(config: "WorldConfig") -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    if not config.terrain_on:
        return (), ()
    taken = set(config.food_positions() + config.water_positions()) | set(homes_for(config).values())
    free = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) not in taken]
    rough_count = len(free) * config.rough_pct // 100
    shelter_count = len(free) * config.shelter_pct // 100
    picks = random.Random(config.seed + 1_000_003).sample(free, rough_count + shelter_count)
    return tuple(sorted(picks[:rough_count])), tuple(sorted(picks[rough_count:]))


def _homes_from(rng: random.Random, config: WorldConfig) -> dict[str, tuple[int, int]]:
    """First RNG draw: distinct cells for every person, never a source cell."""
    cells = [(x, y) for y in range(config.height) for x in range(config.width)
             if (x, y) not in config.food_positions() + config.water_positions()]
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


@lru_cache(maxsize=None)
def store_sites(config: WorldConfig) -> tuple[tuple[str, tuple[int, int], str], ...]:
    """Fixed founding sites; residents are people, caches are source accounts."""
    if not config.stores_on:
        return ()
    return tuple((store_id(actor), pos, actor) for actor, pos in homes_for(config).items())


@lru_cache(maxsize=None)
def wood_sites(config: WorldConfig) -> tuple[tuple[str, tuple[int, int]], ...]:
    """Place groves on existing clear ground without changing homes, traits or terrain."""
    if not config.wood_on:
        return ()
    rough, spots = config.terrain()
    taken = set(homes_for(config).values()) | set(config.food_positions() + config.water_positions()) | set(rough) | set(spots)
    free = {(x,y) for y in range(config.height) for x in range(config.width) if (x,y) not in taken}
    sites = []
    for anchor in ((config.width//4, config.height//2), (3*config.width//4, 3*config.height//4)):
        if not free:
            break
        site = min(free, key=lambda p: (abs(p[0]-anchor[0]) + abs(p[1]-anchor[1]), p[1], p[0]))
        free.remove(site)
        sites.append((WOOD if not sites else WOOD+"2", site))
    return tuple(sites)


@lru_cache(maxsize=None)
def stone_sites(config: WorldConfig) -> tuple[tuple[str, tuple[int, int]], ...]:
    """One quarry on clear ground away from homes, other sources, groves and the bank."""
    if not config.on("crafting"):
        return ()
    rough, spots = config.terrain()
    taken = (set(homes_for(config).values()) | set(config.food_positions() + config.water_positions())
             | set(rough) | set(spots) | {pos for _, pos in wood_sites(config) + fishing_sites(config)})
    free = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) not in taken]
    if not free:
        return ()
    anchor = (config.width // 2, config.height // 4)
    return ((STONE, min(free, key=lambda p: (abs(p[0] - anchor[0]) + abs(p[1] - anchor[1]), p[1], p[0]))),)


@lru_cache(maxsize=None)
def fishing_sites(config: WorldConfig) -> tuple[tuple[str, tuple[int, int]], ...]:
    """Use a clear bank cell near the west edge without moving existing landmarks."""
    if not config.fishing_on:
        return ()
    rough, spots = config.terrain()
    taken = (set(homes_for(config).values()) | set(config.food_positions() + config.water_positions())
             | set(rough) | set(spots) | {pos for _,pos in wood_sites(config)})
    free = [(x,y) for y in range(config.height) for x in range(config.width) if (x,y) not in taken]
    if not free:
        return ()
    anchor = (1, config.height // 2)
    site = min(free, key=lambda p: (abs(p[0]-anchor[0])+abs(p[1]-anchor[1]), p[1], p[0]))
    return ((FISH_SOURCE, site),)


def genesis(config: WorldConfig) -> tuple[WorldState, Overlay]:
    """The saved initial state: a kernel ledger and the overlay beside it."""
    actors = config.actor_ids()
    sources = {source_id: Source(stock=config.source_stock, authorised=frozenset(actors))
               for source_id in config.food_source_ids()}
    sources.update({sid: Source(stock=FISH_STOCK, authorised=frozenset(actors)) for sid,_ in fishing_sites(config)})
    water: dict[str, Any] = {}
    sources.update({sid: Source(stock=0, authorised=frozenset(actors))
                    for sid, _, _ in store_sites(config)})
    if config.water_on:
        sources.update({source_id: Source(stock=config.water_stock, authorised=frozenset(actors), resource=WATER)
                        for source_id in config.water_source_ids()})
        water = {"holdings": {WATER: {actor: config.starting_water for actor in actors}}, "consumed_by": {WATER: 0}}
    if config.wood_on:
        sources.update({sid: Source(stock=WOOD_STOCK, authorised=frozenset(actors), resource=WOOD)
                        for sid,_ in wood_sites(config)})
        water.setdefault("holdings", {})[WOOD] = {actor: 0 for actor in actors}
        water.setdefault("consumed_by", {})[WOOD] = 0
    if config.on("crafting"):
        sources.update({sid: Source(stock=STONE_STOCK, authorised=frozenset(actors), resource=STONE)
                        for sid, _ in stone_sites(config)})
        for resource in (STONE,) + TOOLS:
            water.setdefault("holdings", {})[resource] = {actor: 0 for actor in actors}
            water.setdefault("consumed_by", {})[resource] = 0
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
        home_caches={sid: pos for sid, pos, _ in store_sites(config)} if config.homes_on else {},
        season=season_at(0) if config.seasons_on else None,
        patch_condition={source: CONDITION_MAX for source in config.food_source_ids()} if config.regrowth_on else {},
        thirst=staggered(config, config.thirsty_at) if config.water_on else {},
        cold={actor: 0 for actor in actors} if config.warmth_on else {},
        age={actor: config.adult_at for actor in actors} if config.childhood_on else {},
        persona=genesis_persona(config, actors) if config.features else Persona(),
        sky=sky_at(config, 0) if config.on("sky") else None,
    )
    return ledger, overlay
