"""What one person sees at the start of a tick.

The view is bounded. Distance is Chebyshev (max(|dx|, |dy|)): movement is
four-neighbour, but sight is not a walk. A cell is visible when
distance <= perception_radius (inclusive). Self is always in view
(distance 0).

What is visible about another living person inside the radius: identity,
position, their free food (the kernel's availability), and whether they
are visibly in distress - a hunger or thirst emergency, which shows.
The level of a need is still internal: you can see that somebody is in a
bad way, not how bad. Home and the decision they are about to take stay
invisible.

The source's POSITION is a known landmark, declared in config, and is
always present on the observation. Its STOCK is observed only when the
source cell is within the radius. Outside the radius the observation
carries no stock value (None), not a stale number and not zero.

Recorded form (run file, from 2026-09-25): `sees`, the identities of the
living others in view in roster order, plus `source_food` when the source is
in view. Their positions and free food are the tick-start world positions and
ledger availability already in the same file, so they are not repeated; older
files recorded them per observation as `others`.

Rough ground (2026-09-28) is seen like anything else. A person remembers the
rough cells they have seen before, so `rough_in_view` holds current rough in
sight plus remembered rough elsewhere. Stock and people are still current-view
only.

Housing observes places: a finished shelter in sight can show room for another
resident. Optional relocation remembers those places and refreshes their
vacancies only in sight; a distant remembered vacancy may no longer be free.

Warmth (2026-09-27) needs no landmark: shelter is the person's own home cell,
which the observation already carries, so `cold` is the only field it adds.

Several sources of a kind (2026-09-26): every source position is a known
landmark. The one a person heads for (`target_source`) is the nearest (steps,
then id) seen with free stock; when none in view has stock, it is the nearest.
Optional fishing adds one tick of casting effort to that distance ranking.
A source out of view never attracts anyone, so without memory nobody walks
back and forth at the edge of their sight. `source` / `source_food` (and
`water_source` / `water_stock`) then describe that target, and the record adds
`seen_stock`: the free stock of every source in view. With one source of each
kind nothing changes, and the record is exactly as before.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from kernel import WorldState
from kernel.state import actor_account, source_account

from world.config import FOOD_SOURCE, WATER, WATER_SOURCE, WorldConfig, store_sites, stone_sites, wood_sites, fishing_sites
from world.crafting import STONE, tools_held
from world.farming import GRAIN, STATES, plot_of
from world.storage import food_expectation
from world.foraging import remember_empty, remember_sightings, usable_reports
from world.materials import WOOD
from world.housing import visible_sites, remembered_shelters, can_relocate
from world.overlay import Overlay, Position
from world.pledges import views as pledge_views
from world.sky import Sky, exposure, sight
from world.society import IDLE_LOOK
from world.wolves import danger_cells, is_active


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
    starving: bool = False    # visibly in a hunger emergency
    parched: bool = False     # visibly in a thirst emergency
    water: int | None = None  # free water units; filled in only when water care is on
    asleep: bool = False      # visibly asleep (the sleep feature)
    busy: bool = False        # visibly occupied with something else: walking somewhere, drawing, eating (bonds feature)
    wood: int | None = None   # free wood carried; filled in only when pledges and wood are on

    @property
    def in_distress(self) -> bool:
        return self.starving or self.parched

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.actor, "at": list(self.position), "food": self.food}
        if self.starving:
            out["starving"] = 1
        if self.parched:
            out["parched"] = 1
        if self.water:
            out["water"] = self.water
        if self.wood:
            out["wood"] = self.wood
        return out


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
    source_id: str = FOOD_SOURCE           # which food source `source` is: the one this person heads for
    water_source_id: str = WATER_SOURCE    # likewise for water
    seen_stock: tuple[tuple[str, int], ...] = ()   # several sources of a kind: free stock of each source in view
    cold: int = 0                          # warmth on only; shelter is `home`, so it needs no separate landmark
    home_built: bool = False               # a shelter already stands on this person's home cell
    work_done: int = 0                     # ticks of work already put into it
    asked_by: str | None = None            # somebody asked this person for food last tick
    owed_to: str | None = None             # this person agreed to bring food to somebody
    waiting_on: str | None = None          # this person asked somebody and has had no answer yet
    rough_in_view: frozenset[Position] = frozenset()   # visible rough plus remembered rough, for choosing a way round
    rough_seen_now: frozenset[Position] = frozenset()  # just this tick's visible rough cells
    held: int = 0                         # own remaining rough-ground movement delay
    age: int = 10 ** 6                     # ticks lived; the default is somebody long grown
    children: frozenset[str] = frozenset() # who this person is a parent to
    dependents: frozenset[str] = frozenset()   # those of them still too young to fend for themselves
    food_memory: tuple[tuple[str, int], ...] = ()  # my own remembered donors and completed ticks
    home_store_food: int | None = None  # resident's cache, seen only while at home
    home_store_id: str | None = None
    choosing_home: bool = False
    home_target: Position | None = None
    home_options: tuple[tuple[Position, bool], ...] = ()
    relocating: bool = False
    home_strain: int = 0
    known_homes: tuple[Position, ...] = ()
    wood: int = 0
    wood_source_id: str | None = None
    wood_source: Position | None = None
    wood_stock: int | None = None
    fishing_ready: bool = False
    food_sightings: tuple[tuple[str, int, int], ...] = ()
    source_reports: tuple[tuple[str, str, int, int], ...] = ()
    report_listeners: tuple[str, ...] = ()
    report_food_avoided: str | None = None
    report_provision_avoided: str | None = None
    empty_sources: tuple[tuple[str, int], ...] = ()
    food_choice_changed: str | None = None  # target without empty-source memory
    food_target: str | None = None
    provision_phase: str | None = None
    provision_source: tuple[str, Position, int | None] | None = None
    provision_avoided: str | None = None
    housemates_in_view: tuple[str, ...] = ()
    food_expected: tuple[str, int] | None = None
    food_expectation_end: str | None = None
    witnessed_deaths: tuple[str, ...] = ()  # expected speaker's locally witnessed death
    traits: tuple[int, ...] = ()           # own traits, in world.traits order; empty when personality is off
    skills: tuple[int, ...] = ()           # own practice points, in world.traits order; empty when skills are off
    fatigue: int | None = None             # own tiredness; None when sleep is off
    asleep: bool = False                   # was asleep at the start of the tick
    tried: tuple[tuple[str, str, int, int], ...] = ()   # own recent attempts: kind, target, tick, 1 ok / 0 refused
    doing: str | None = None               # the kind of what this person decided last tick
    sky: Sky | None = None                 # phase, weather and temperature, which everybody feels (sky feature)
    chill: int = 0                         # extra cold a tick out in the open in this sky; everybody feels it
    wolves_seen: tuple[tuple[str, Position], ...] = ()   # wolves within sight right now: id and cell (wolves feature)
    wolves_active: frozenset[str] = frozenset()          # which of them are visibly stalking rather than lying quiet
    beliefs: tuple[tuple[Any, ...], ...] = ()            # own beliefs: kind, subject, x, y, seen, learned, via
    hurt: int = 0                                        # own injury; 0 when wolves are off
    danger: frozenset[Position] = frozenset()            # cells near a wolf they see or believe in; routes avoid them
    bonds: tuple[tuple[Any, ...], ...] = ()              # own view of each person they have dealt with (bonds feature)
    lonely: int = 0                                      # own need for company
    talking: tuple[str, int] | None = None               # who they are talking to and since when
    stone: int = 0                                       # own stone in hand (crafting feature)
    stone_source_id: str | None = None
    stone_source: Position | None = None
    stone_stock: int | None = None
    tools: tuple[str, ...] = ()                          # tools they carry
    grain: int = 0                                       # own grain in hand (farming feature)
    plot: tuple[int, ...] | None = None                  # their field if in sight: x, y, state index, soil, cared, grown
    field_stock: int | None = None                       # grain standing in it, if in sight
    field_id: str | None = None
    pledge_requests: tuple[tuple[Any, ...], ...] = ()    # asked of them, asker in sight: asker, kind, amount, x, y (pledges feature)
    pledge_owed: tuple[tuple[Any, ...], ...] = ()        # promised by them: id, kind, asker, amount, x, y, due, held, action, arrived, done
    pledge_asked: tuple[tuple[Any, ...], ...] = ()       # asked by them: id, kind, helper, asked or promised (once heard), made, due

    @property
    def storm(self) -> bool:
        return self.sky is not None and self.sky.storm

    @property
    def night(self) -> bool:
        return self.sky is not None and self.sky.night

    @property
    def at_source(self) -> bool:
        return self.position == self.source

    @property
    def at_home(self) -> bool:
        return self.position == self.home

    @property
    def sheltered(self) -> bool:
        """Shelter is a person's own home cell: the one need met by a place."""
        return self.at_home

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
        if self.witnessed_deaths:
            out["witnessed_deaths"] = list(self.witnessed_deaths)
        if self.food_expected is not None:
            out["food_expected"] = list(self.food_expected)
        if self.food_expectation_end is not None:
            out["food_expectation_end"] = self.food_expectation_end
        if self.housemates_in_view:
            out["housemates_in_view"] = list(self.housemates_in_view)
        if self.provision_phase is not None:
            out["provision_phase"] = self.provision_phase
        if self.provision_source is not None:
            sid, pos, stock = self.provision_source
            out["provision_source"] = {"id": sid, "position": list(pos), "stock": stock}
        if self.provision_avoided is not None:
            out["provision_avoided"] = self.provision_avoided
        if self.report_food_avoided is not None:
            out["report_food_avoided"] = self.report_food_avoided
        if self.report_provision_avoided is not None:
            out["report_provision_avoided"] = self.report_provision_avoided
        if self.food_sightings:
            out["food_sightings"] = [list(e) for e in self.food_sightings]
        if self.source_reports:
            out["source_reports"] = [list(e) for e in self.source_reports]
        if self.report_listeners:
            out["report_listeners"] = list(self.report_listeners)
        if self.wolves_seen:
            out["wolves_seen"] = [[wolf, cell[0], cell[1], int(wolf in self.wolves_active)] for wolf, cell in self.wolves_seen]
        if self.empty_sources:
            out["empty_sources"] = dict(self.empty_sources)
        if self.food_choice_changed is not None:
            out["food_choice_changed"] = self.food_choice_changed
            out["food_target"] = self.food_target
        if self.fishing_ready:
            out["fishing_ready"] = 1
        if self.source_food is not None:
            out["source_food"] = self.source_food
        if self.water_stock is not None:
            out["water_stock"] = self.water_stock
        if self.seen_stock:
            out["seen_stock"] = dict(self.seen_stock)
        if self.home_store_food is not None:
            out["home_store_food"] = self.home_store_food
        if self.wood_source_id is not None:
            out["wood"] = self.wood
            out["wood_source"] = self.wood_source_id
            if self.wood_stock is not None:
                out["wood_stock"] = self.wood_stock
        if self.known_homes:
            out["known_homes"] = [list(site) for site in self.known_homes]
        if self.home_strain:
            out["home_strain"] = self.home_strain
        if self.relocating:
            out["relocating"] = 1
        if self.choosing_home or self.relocating:
            out["home_options"] = [{"at": list(pos), "built": int(built)} for pos, built in self.home_options]
            if self.home_target is not None:
                out["home_target"] = list(self.home_target)
        return out


def observe(actor: str, ledger: WorldState, overlay: Overlay, config: WorldConfig,
            available: Mapping[str, int] | None = None) -> Observation:
    """`available` is the ledger's availability map; a caller observing many
    people passes it once per tick rather than having it rebuilt per person."""
    if available is None:
        available = ledger.availability()
    view = ledger.view_for(actor)
    origin = overlay.positions[actor]
    persona = overlay.persona
    asleep = actor in persona.asleep
    # A sleeper sees only their own cell; everybody else can see that they are asleep.
    radius = 0 if asleep else sight(config, overlay.sky, config.perception_radius)
    others = tuple(
        SeenPerson(other, overlay.positions[other], available[actor_account(other)],
                   starving=overlay.hunger[other] >= config.emergency_at,
                   parched=config.water_on and overlay.thirst[other] >= config.thirst_emergency_at,
                   water=available[actor_account(other, WATER)] if (config.water_care_on or config.on("pledges")) else None,
                   wood=available[actor_account(other, WOOD)] if config.on("pledges") and config.wood_on else None,
                   asleep=other in persona.asleep,
                   busy=(config.on("bonds") and persona.doing.get(other) is not None
                         and persona.doing[other] not in IDLE_LOOK))
        for other in overlay.living
        if other != actor and in_view(origin, overlay.positions[other], radius)
    )
    food_known = tuple(zip(config.food_source_ids(), config.food_positions())) + fishing_sites(config)
    empty_sources = (remember_empty(overlay.empty_sources.get(actor, ()),
                     tuple((sid, available[source_account(sid)]) for sid,pos in food_known
                           if in_view(origin, pos, radius)), ledger.tick) if config.source_memory_on else ())
    sightings = ()
    reports = ()
    if config.knowledge_sharing_on:
        visible_food = tuple((sid, available[source_account(sid)]) for sid, pos in food_known
                             if in_view(origin, pos, radius))
        sightings = remember_sightings(overlay.food_sightings.get(actor, ()), visible_food, ledger.tick)
        reports = usable_reports(overlay.source_reports.get(actor, ()), sightings, ledger.tick)
    avoided_sources = frozenset(sid for sid, _ in empty_sources) | frozenset(e[0] for e in reports)
    provision_source = None
    provision_avoided = None
    report_provision_avoided = None
    if config.provisioning_on:
        effort = {sid: 1 for sid, _ in fishing_sites(config)}
        provision_source = target_source(origin, food_known, radius, available, effort,
                                        avoided_sources)
        if reports:
            personal = target_source(origin, food_known, radius, available, effort,
                                     frozenset(sid for sid, _ in empty_sources))
            if personal[0] != provision_source[0]:
                report_provision_avoided = personal[0]
        ordinary_natural = target_source(origin, food_known, radius, available, effort)
        if ordinary_natural[0] != provision_source[0]:
            provision_avoided = ordinary_natural[0]
    caches = (tuple((sid, pos, None) for sid, pos in overlay.home_caches.items())
              if config.homes_on else store_sites(config))
    own_cache = next((sid for sid, pos, resident in caches
                      if origin == pos and (overlay.homes[actor] == pos if config.homes_on else resident == actor)), None)
    # Death follows movement. An existing listener can witness their speaker at
    # the final positions of the just-completed boundary. Do not give newborns
    # knowledge of deaths before their birth, or reveal distant/older deaths.
    expectation = overlay.food_expected.get(actor) if config.coordination_on else None
    speaker = expectation[0] if expectation else None
    witnessed_deaths = ((speaker,) if speaker is not None
                        and overlay.died_at.get(speaker) == overlay.tick
                        and in_view(origin, overlay.positions[speaker], radius) else ())
    expected, expectation_end = (food_expectation(
        overlay.food_expected.get(actor), ledger.tick, overlay.homes[actor], others,
        ledger.sources[own_cache].stock if own_cache is not None else None, witnessed_deaths)
        if config.coordination_on else (None, None))
    choosing_home = (config.homes_on and overlay.alive(actor) and actor in overlay.parent
                     and overlay.age.get(actor, 0) >= config.adult_at and actor not in overlay.home_settled)
    relocating = can_relocate(actor, overlay, config)
    wood_view = {}
    if config.wood_on:
        sid, site, stock = target_source(origin, wood_sites(config), radius, available)
        wood_view = {"wood": available[actor_account(actor, WOOD)], "wood_source_id": sid,
                     "wood_source": site, "wood_stock": stock}
    if config.on("farming"):
        mine = plot_of(overlay.things.plots, actor)
        wood_view["grain"] = available[actor_account(actor, GRAIN)]
        if mine is not None and in_view(origin, mine.cell, radius):
            wood_view.update({"plot": (mine.x, mine.y, STATES.index(mine.state), mine.soil, mine.cared, mine.grown),
                              "field_stock": available[source_account(mine.source)], "field_id": mine.source})
    if config.on("crafting"):
        sid, site, stock = target_source(origin, stone_sites(config), radius, available)
        wood_view.update({"stone": available[actor_account(actor, STONE)], "stone_source_id": sid, "stone_source": site,
                          "stone_stock": stock, "tools": tools_held(available, actor)})
    visible_caches = tuple((sid, pos) for sid, pos, _ in caches
                           if pos in overlay.shelters and in_view(origin, pos, radius))
    # An empty or unseen cache must never replace the ordinary patch fallback.
    food_known += tuple((sid, pos) for sid, pos in visible_caches if available[source_account(sid)] > 0)
    effort = {sid: 1 for sid,_ in fishing_sites(config)}
    ordinary = target_source(origin, food_known, radius, available, effort)
    source_id, source, source_food = target_source(origin, food_known, radius, available, effort,
                                                  avoided_sources)
    report_food_avoided = None
    if reports:
        personal = target_source(origin, food_known, radius, available, effort,
                                 frozenset(sid for sid, _ in empty_sources))
        if personal[0] != source_id:
            report_food_avoided = personal[0]
    known = food_known + tuple(zip(config.water_source_ids(), config.water_positions()))
    several = len(food_known) > 1 or len(config.water_source_ids()) > 1
    seen_stock = tuple((sid, available[source_account(sid)]) for sid, position in known
                       if in_view(origin, position, radius)) if several else ()
    seen_stock = tuple(sorted(dict(seen_stock + tuple((sid, available[source_account(sid)])
                                                    for sid, _ in visible_caches)).items()))
    sighted = ([wolf for wolf in overlay.things.wolves if in_view(origin, wolf.position, radius)]
               if config.on("wolves") else [])
    wolves_seen = tuple((wolf.id, wolf.position) for wolf in sighted)
    beliefs = persona.beliefs.get(actor, ())
    asked, owing, asking = (pledge_views(overlay.pledges, actor, {seen.actor for seen in others})
                            if config.on("pledges") else ((), (), ()))
    return Observation(
        pledge_requests=asked, pledge_owed=owing, pledge_asked=asking,
        wolves_seen=wolves_seen, beliefs=beliefs, hurt=persona.hurt.get(actor, 0),
        bonds=persona.bonds.get(actor, ()), lonely=persona.lonely.get(actor, 0), talking=persona.talking.get(actor),
        wolves_active=frozenset(wolf.id for wolf in sighted if is_active(wolf, overlay.sky)),
        danger=(danger_cells(beliefs, wolves_seen, ledger.tick, config, overlay.sky)
                if config.on("wolves") else frozenset()),
        food_sightings=sightings, source_reports=reports,
        report_food_avoided=report_food_avoided, report_provision_avoided=report_provision_avoided,
        report_listeners=tuple(seen.actor for seen in others
                               if overlay.homes[seen.actor] == overlay.homes[actor]
                               and chebyshev(origin, seen.position) <= 1) if config.knowledge_sharing_on else (),
        housemates_in_view=tuple(seen.actor for seen in others if overlay.homes[seen.actor] == overlay.homes[actor])
            if config.coordination_on else (),
        food_expected=expected,
        food_expectation_end=expectation_end,
        witnessed_deaths=witnessed_deaths,
        provision_phase=overlay.provision_trips.get(actor) if config.provisioning_on else None,
        provision_source=provision_source,
        provision_avoided=provision_avoided,
        empty_sources=empty_sources,
        food_choice_changed=ordinary[0] if ordinary[0] != source_id else None,
        food_target=source_id if config.source_memory_on else None,
        fishing_ready=overlay.fishing_cast.get(actor) == origin,
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
        source_id=source_id,
        seen_stock=seen_stock,
        food_memory=overlay.food_memory.get(actor, ()) if config.social_memory_on else (),
        home_store_food=ledger.sources[own_cache].stock if own_cache is not None else None,
        home_store_id=own_cache,
        choosing_home=choosing_home,
        home_target=overlay.home_targets.get(actor) if choosing_home or relocating else None,
        home_options=visible_sites(actor, overlay, config) if choosing_home else (),
        relocating=relocating,
        home_strain=overlay.home_strain.get(actor, 0) if config.relocation_on else 0,
        known_homes=remembered_shelters(actor, overlay, config) if config.relocation_on else (),
        **({"cold": overlay.cold[actor]} if config.warmth_on else {}),
        home_built=overlay.homes[actor] in set(overlay.shelters),
        **wood_view,
        work_done=overlay.built.get(actor, 0),
        asked_by=next((who for who, asked in overlay.requests.items()
                       if asked == actor and any(seen.actor == who for seen in others)), None),
        owed_to=next((seen.actor for seen in others if seen.actor == overlay.promises.get(actor)), None),
        waiting_on=next((seen.actor for seen in others if seen.actor == overlay.requests.get(actor)), None),
        held=overlay.held.get(actor, 0),
        rough_seen_now=frozenset(cell for cell in config.terrain()[0] if in_view(origin, cell, radius)),
        rough_in_view=frozenset(overlay.terrain_memory.get(actor, ()))
        | frozenset(cell for cell in config.terrain()[0] if in_view(origin, cell, radius)),
        **({"age": overlay.age.get(actor, config.adult_at),
           "children": overlay.children_of(actor),
           "dependents": frozenset(kid for kid in overlay.children_of(actor)
                                   if overlay.alive(kid)
                                   and overlay.age.get(kid, config.adult_at) < config.adult_at)}
          if config.childhood_on else {}),
        traits=persona.traits.get(actor, ()), skills=persona.skills.get(actor, ()),
        fatigue=persona.fatigue.get(actor), asleep=asleep, tried=persona.tried.get(actor, ()),
        doing=persona.doing.get(actor), sky=overlay.sky, chill=exposure(config, overlay.sky, False),
        **_water_view(actor, origin, overlay, config, available, radius),
    )


def steps_between(a: Position, b: Position) -> int:
    """Moves between two cells: movement is one four-neighbour step per tick."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def target_source(origin: Position, known: tuple[tuple[str, Position], ...], radius: int,
                  available: Mapping[str, int], effort: Mapping[str, int] | None = None,
                  avoid: frozenset[str] = frozenset()) -> tuple[str, Position, int | None]:
    """The source of one kind a person heads for, from what they can see now:
    visible stocked sources come first, then sources not remembered empty,
    then all sources as a fallback. Each group is ranked by steps plus any
    gathering effort, then id. Stock is None outside sight. Without memory
    or gathering effort this is the original nearest-source rule."""
    ranked = sorted(known, key=lambda item: (steps_between(origin, item[1]) + (effort or {}).get(item[0], 0), item[0]))
    options = [(sid, position, available[source_account(sid)] if in_view(origin, position, radius) else None)
               for sid, position in ranked]
    stocked = [option for option in options if option[2] is not None and option[2] > 0]
    untried = [option for option in options if option[0] not in avoid]
    return (stocked or untried or options)[0]


def _water_view(actor: str, origin: Position, overlay: Overlay, config: WorldConfig,
                available: Mapping[str, int], radius: int) -> dict[str, Any]:
    if not config.water_on:
        return {}
    known = tuple(zip(config.water_source_ids(), config.water_positions()))
    well_id, well, stock = target_source(origin, known, radius, available)
    return {
        "thirst": overlay.thirst[actor],
        "water": available[actor_account(actor, WATER)],
        "water_source": well,
        "water_stock": stock,
        "water_source_id": well_id,
    }
