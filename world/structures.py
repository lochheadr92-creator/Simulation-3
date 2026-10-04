"""Things people build and keep up: shelters that wear, fires that burn wood, wells somebody digs.

A shelter's condition falls with time and storms. Somebody who sees theirs worn mends it with wood (a neighbour
may lend a hand); one left to fall to nothing collapses and its owner must build again. A fire burns for as long as
its fuel lasts, warms whoever stands at it, lights the cells near it at night and keeps wolves from biting there.
A well is dug over many ticks from wood already in hand; once finished it gives water by recorded production, and it
is not a landmark: nobody uses it until they have seen it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_CONSUME
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

REPAIR, LIGHT, DIG = "repair", "light", "dig"
KINDS = ("shelter", "fire", "well", "grave")
MAINTAIN_KINDS = frozenset({REPAIR, LIGHT, DIG})
STRUCT_LEVERS = (("wear_every", 6), ("storm_wear", 1), ("repair_at", 45), ("repair_to", 80), ("repair_gain", 25), ("fire_burn", 14),
                 ("fire_warmth", 2), ("fire_light", 1), ("well_ticks", 12), ("well_wood", 4), ("well_every", 5),
                 ("well_cap", 6), ("leak_below", 50), ("repair_margin", 6))

STRUCTURES = Feature(
    name="structures",
    summary="Shelters wear and are mended or fall down; people light fires and dig wells.",
    rule=(
        "A finished shelter starts with condition 100 and loses 1 every wear_every ticks, and storm_wear more on every "
        "storm tick. Below leak_below it leaks: whoever is sheltered there in rain or a storm still pays the cold. "
        "At 0 it collapses: the shelter is gone and its residents' building work starts over. Somebody at home, free, "
        "whose shelter is below repair_at and who has wood, mends it, spending one wood (through the kernel) "
        "for repair_gain condition a tick, carrying on until it is repair_to or better; without wood they fetch some when their needs leave room (repair_margin "
        "ticks). They may ask a neighbour for a hand, and a neighbour at the door adds the same again. At night "
        "(or when cold at half its seeking level) with wolves about, somebody at home with wood lights a "
        "fire, spending one wood for fire_burn ticks of fuel; the fire gives fire_warmth less cold a tick to anybody "
        "standing on it, lets them see fire_light further at night within two cells, and no wolf bites anybody "
        "within a cell of it. A free, diligent person with well_wood wood in hand and a housed home may dig a well "
        "at their well site: the wood is spent at the start and well_ticks ticks of digging finish it. A finished well "
        "gains one unit every well_every ticks up to well_cap, by recorded production. A finished well is not a "
        "landmark: a person only uses it after they have seen it."),
    levers=STRUCT_LEVERS,
    tables={"kinds": list(KINDS)},
)


@dataclass(frozen=True)
class Struct:
    kind: str
    owner: str
    x: int
    y: int
    a: int = 0       # shelter: condition; fire: fuel ticks left; well: ticks dug; grave: the tick they died
    b: int = 0       # well: 1 once it is finished; grave: 1 once somebody has collected their belongings

    @property
    def cell(self) -> tuple[int, int]:
        return (self.x, self.y)

    def canonical(self) -> list[Any]:
        return [self.kind, self.owner, self.x, self.y, self.a, self.b]

    @classmethod
    def from_canonical(cls, data: Any) -> "Struct":
        if not isinstance(data, (list, tuple)) or len(data) != 6:
            raise ValueError(f"a structure is kind, owner, x, y, a, b: {data!r}")
        kind, owner, x, y, a, b = data
        if (kind not in KINDS or not isinstance(owner, str) or any(type(n) is not int or n < 0 for n in (x, y, a, b))
                or b not in (0, 1) or (kind == "shelter" and a > 100)):
            raise ValueError(f"a structure is not valid: {data!r}")
        return cls(kind, owner, x, y, a, b)


def well_id(owner: str) -> str:
    return f"well-{owner}"


def find(structs: tuple[Struct, ...], kind: str, owner: str) -> Struct | None:
    return next((s for s in structs if s.kind == kind and s.owner == owner), None)


def burning(structs: tuple[Struct, ...]) -> list[Struct]:
    return [s for s in structs if s.kind == "fire" and s.a > 0]


def lit_cells(structs: tuple[Struct, ...], reach: int) -> set[tuple[int, int]]:
    return {(s.x + dx, s.y + dy) for s in burning(structs) for dx in range(-reach, reach + 1)
            for dy in range(-reach, reach + 1) if abs(dx) + abs(dy) <= reach}


def _replace_struct(structs: list[Struct], new: Struct) -> None:
    structs[:] = [s for s in structs if (s.kind, s.owner) != (new.kind, new.owner)] + [new]


def advance_structures(previous: Any, current: Any, decisions: Mapping[str, Any], record: Any, ledger: Any,
                       shelters: set[tuple[int, int]], boosted: set[str], config: "WorldConfig"
                       ) -> tuple[tuple[Struct, ...], set[tuple[int, int]], dict[str, int], Any, list[dict[str, Any]], list[tuple[str, tuple[int, int]]]]:
    """Structures after one tick: the new set of shelters, owners whose building starts over, the ledger after wells
    give water, the production entries that say so, and the collapses (owner, cell).

    `boosted` is the owners a neighbour helped with a repair this tick."""
    from dataclasses import replace as rep
    now = previous.tick + 1
    wear_every, gain = config.lever("wear_every"), config.lever("repair_gain")
    spent = {o.actor: o.accepted for o in record.outcomes if o.operation == OP_CONSUME}
    structs = list(previous.things.structures)
    production: list[dict[str, Any]] = []
    fallen: list[tuple[str, tuple[int, int]]] = []
    reset: dict[str, int] = {}
    # a shelter somebody has finished gets a condition to keep up
    owners = {cell: owner for owner, cell in sorted(previous.homes.items())}
    for cell in sorted(shelters):
        owner = owners.get(cell)
        if owner and not any(s.kind == "shelter" and s.cell == cell for s in structs):
            structs.append(Struct("shelter", owner, cell[0], cell[1], 100))
    storm = previous.sky is not None and previous.sky.storm
    kept: list[Struct] = []
    for s in structs:
        if s.kind == "shelter":
            if s.cell not in shelters:
                continue                                       # gone some other way
            a = s.a
            d = decisions.get(s.owner)
            if d is not None and d.kind == REPAIR and spent.get(s.owner) and previous.positions.get(s.owner) == s.cell:
                a = min(100, a + gain * (2 if s.owner in boosted else 1))
            a -= int(now % wear_every == 0) + (config.lever("storm_wear") if storm else 0)
            if a <= 0:
                for owner, home in previous.homes.items():
                    if home == s.cell:
                        reset[owner] = 0
                        fallen.append((owner, s.cell))
                shelters.discard(s.cell)
                continue
            s = rep(s, a=a)
        elif s.kind == "fire":
            d = decisions.get(s.owner)
            fuel = s.a
            if d is not None and d.kind == LIGHT and spent.get(s.owner):
                fuel += config.lever("fire_burn")
            s = rep(s, a=max(0, fuel - 1))
            if s.a == 0 and fuel == 0:
                continue                                       # burnt out and not refuelled: the ashes are not a thing
        elif s.kind == "well" and not s.b:
            d = decisions.get(s.owner)
            if d is not None and d.kind == DIG and previous.positions.get(s.owner) == s.cell and (s.a > 0 or spent.get(s.owner)):
                s = rep(s, a=s.a + 1)
                if s.a >= config.lever("well_ticks"):
                    s = rep(s, b=1)
        elif s.kind == "well" and s.b and now % config.lever("well_every") == 0:
            source = ledger.sources[well_id(s.owner)]
            amount = min(1, config.lever("well_cap") - source.stock)
            if amount > 0:
                sources = dict(ledger.sources)
                sources[well_id(s.owner)] = rep(source, stock=source.stock + amount)
                ledger = rep(ledger, sources=sources)
                production.append({"source": well_id(s.owner), "amount": amount})
        kept.append(s)
    # a fire lit this tick where there was none, a well begun
    for actor in sorted(decisions):
        d = decisions[actor]
        if d.kind == LIGHT and spent.get(actor) and find(tuple(kept), "fire", actor) is None and actor in previous.homes:
            kept.append(Struct("fire", actor, *previous.homes[actor], config.lever("fire_burn") - 1))
        if d.kind == DIG and spent.get(actor) and find(tuple(kept), "well", actor) is None:
            site = previous.positions[actor]
            kept.append(Struct("well", actor, site[0], site[1], 1))
    return tuple(sorted(kept, key=lambda s: (s.kind, s.owner))), shelters, reset, ledger, production, fallen
