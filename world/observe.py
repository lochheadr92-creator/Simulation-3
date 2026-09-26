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
carries no stock value (None), not a stale number and not zero. There is
no memory, observation age, or belief store; this is the local-knowledge
hook without retained facts (Stage 4).

Recorded form (run file, from 2026-09-25): `sees`, the identities of the
living others in view in roster order, plus `source_food` when the source is
in view. Their positions and free food are the tick-start world positions and
ledger availability already in the same file, so they are not repeated; older
files recorded them per observation as `others`.

Rough ground (2026-09-28) is seen like anything else: `rough_in_view` holds
the rough cells inside the radius, and nothing beyond it. A person picks their
way around what they can see and walks blind into what they cannot.

Warmth (2026-09-27) needs no landmark: shelter is the person's own home cell,
which the observation already carries, so `cold` is the only field it adds.

Several sources of a kind (2026-09-26): every source position is a known
landmark. The one a person heads for (`target_source`) is the nearest (steps,
then id) seen with free stock; when none in view has stock, it is the nearest.
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
    starving: bool = False    # visibly in a hunger emergency
    parched: bool = False     # visibly in a thirst emergency

    @property
    def in_distress(self) -> bool:
        return self.starving or self.parched

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.actor, "at": list(self.position), "food": self.food}
        if self.starving:
            out["starving"] = 1
        if self.parched:
            out["parched"] = 1
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
    rough_in_view: frozenset[Position] = frozenset()   # rough cells they can see, for choosing a way round
    age: int = 10 ** 6                     # ticks lived; the default is somebody long grown
    children: frozenset[str] = frozenset() # who this person is a parent to

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
        if self.source_food is not None:
            out["source_food"] = self.source_food
        if self.water_stock is not None:
            out["water_stock"] = self.water_stock
        if self.seen_stock:
            out["seen_stock"] = dict(self.seen_stock)
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
        SeenPerson(other, overlay.positions[other], available[actor_account(other)],
                   starving=overlay.hunger[other] >= config.emergency_at,
                   parched=config.water_on and overlay.thirst[other] >= config.thirst_emergency_at)
        for other in overlay.living
        if other != actor and in_view(origin, overlay.positions[other], radius)
    )
    food_known = tuple(zip(config.food_source_ids(), config.food_positions()))
    source_id, source, source_food = target_source(origin, food_known, radius, available)
    known = food_known + tuple(zip(config.water_source_ids(), config.water_positions()))
    several = len(food_known) > 1 or len(config.water_source_ids()) > 1
    seen_stock = tuple((sid, available[source_account(sid)]) for sid, position in known
                       if in_view(origin, position, radius)) if several else ()
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
        source_id=source_id,
        seen_stock=seen_stock,
        **({"cold": overlay.cold[actor]} if config.warmth_on else {}),
        home_built=overlay.homes[actor] in set(overlay.shelters),
        work_done=overlay.built.get(actor, 0),
        asked_by=next((who for who, asked in overlay.requests.items() if asked == actor), None),
        owed_to=overlay.promises.get(actor),
        waiting_on=overlay.requests.get(actor),
        rough_in_view=frozenset(cell for cell in config.terrain()[0] if in_view(origin, cell, radius)),
        **({"age": overlay.age.get(actor, config.adult_at),
           "children": frozenset(kid for kid, mum in overlay.parent.items() if mum == actor)}
          if config.childhood_on else {}),
        **_water_view(actor, origin, overlay, config, available),
    )


def steps_between(a: Position, b: Position) -> int:
    """Moves between two cells: movement is one four-neighbour step per tick."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def target_source(origin: Position, known: tuple[tuple[str, Position], ...], radius: int,
                  available: Mapping[str, int]) -> tuple[str, Position, int | None]:
    """The source of one kind a person heads for, from what they can see now:
    the nearest (steps, then id) seen with free stock; if none in view has
    stock, the nearest. Returns its id, position, and free stock when in view
    (None when out of view). With one source it is always that source."""
    ranked = sorted(known, key=lambda item: (steps_between(origin, item[1]), item[0]))
    options = [(sid, position, available[source_account(sid)] if in_view(origin, position, radius) else None)
               for sid, position in ranked]
    stocked = [option for option in options if option[2] is not None and option[2] > 0]
    return (stocked or options)[0]


def _water_view(actor: str, origin: Position, overlay: Overlay, config: WorldConfig,
                available: Mapping[str, int]) -> dict[str, Any]:
    if not config.water_on:
        return {}
    known = tuple(zip(config.water_source_ids(), config.water_positions()))
    well_id, well, stock = target_source(origin, known, config.perception_radius, available)
    return {
        "thirst": overlay.thirst[actor],
        "water": available[actor_account(actor, WATER)],
        "water_source": well,
        "water_stock": stock,
        "water_source_id": well_id,
    }
