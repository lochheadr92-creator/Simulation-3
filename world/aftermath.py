"""Death and what follows it: a grave, a record, belongings somebody may collect, news that spreads.

When somebody dies a marker is set where they fell and a record is saved: when, where, how old, the cause (what an
observer reading the run may see), who stood in sight, and what they held. Nobody learns of a death by magic. Those
who can see the marker believe it, and anybody can be told. A person only grieves for a death they know of. The
dead person's belongings stay in their account until a living person collects them from the grave: the heirs first
(partner, parents, children), anybody after a grace period. Collecting is an ordinary kernel transfer, issued
in the dead person's name from their own account, so every unit stays accounted for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_TRANSFER
from kernel.state import actor_account
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

GO_GRAVE, MOURN, COLLECT = "go_grave", "mourn", "collect"
GRAVE_KINDS = frozenset({GO_GRAVE, MOURN, COLLECT})
CAUSES = ("starved", "died of thirst", "froze to death", "was killed by a wolf", "died of old age", "died")
AFTER_LEVERS = (("heir_grace", 60), ("grave_range", 8), ("mourn_relief", 1), ("grave_margin", 8))

AFTERMATH = Feature(
    name="aftermath",
    summary="The dead are marked and recorded; their belongings can be collected; people learn of deaths by seeing or being told.",
    rule=(
        "When somebody dies a grave is set where they fell and a record is saved: the tick, the cell, their age, the cause "
        "(starved, died of thirst, froze to death, killed by a wolf, died of old age, or died), those living and in sight at the "
        "time, what they held in each resource (units on hold for a promise included), and later who collected it. The cause and the record are for whoever reads "
        "the run; the people know only what they saw or were told. Somebody who sees a grave believes that the person "
        "died, at that cell and tick, and may tell others in conversation. Grief comes only from a death somebody has just "
        "learned of. The belongings stay in the dead person's account: the partner, a parent or a child (or a "
        "guardian's dependent) who knows of the grave and is free walks there within grave_range steps and collects "
        "them all; after heir_grace ticks anybody who knows of the grave, is free and has no food or no water may. "
        "Collecting hands every unit over by kernel transfers in the dead person's name. A grave somebody has seen with nothing left in it "
        "is remembered as emptied, and nobody walks there to collect. Somebody grieving, free and "
        "knowing a grave within grave_range steps walks to it and rests there, and mourning at the grave takes mourn_relief "
        "more off their grief each tick."),
    needs=("beliefs",),
    levers=AFTER_LEVERS,
    tables={"causes": list(CAUSES)},
)


@dataclass(frozen=True)
class Death:
    person: str
    tick: int
    x: int
    y: int
    age: int
    cause: str
    witnesses: tuple[str, ...] = ()
    estate: tuple[tuple[str, int], ...] = ()           # what they held, (resource, units); food is "food"
    taker: str = ""                                    # who collected it, once somebody has
    partner: str = ""                                  # who they were paired with when they died

    @property
    def cell(self) -> tuple[int, int]:
        return (self.x, self.y)

    def canonical(self) -> list[Any]:
        return [self.person, self.tick, self.x, self.y, self.age, self.cause, list(self.witnesses),
                [list(e) for e in self.estate], self.taker, self.partner]

    @classmethod
    def from_canonical(cls, data: Any) -> "Death":
        if not isinstance(data, (list, tuple)) or len(data) != 10:
            raise ValueError(f"a death record is person, tick, x, y, age, cause, witnesses, estate, taker, partner: {data!r}")
        person, tick, x, y, age, cause, witnesses, estate, taker, partner = data
        if (not isinstance(person, str) or cause not in CAUSES or any(type(n) is not int or n < 0 for n in (tick, x, y, age))
                or not all(isinstance(w, str) for w in witnesses) or not isinstance(taker, str) or not isinstance(partner, str)
                or any(not isinstance(r, str) or type(n) is not int or n < 1 for r, n in estate)):
            raise ValueError(f"a death record is not valid: {data!r}")
        return cls(person, tick, x, y, age, cause, tuple(witnesses), tuple((r, n) for r, n in estate), taker, partner)


def cause_of(config: "WorldConfig", previous: Any, current: Any, person: str, lifespan_of: Any) -> str:
    """What killed them, from the recorded levels at the end of the tick they died."""
    if current.hunger.get(person, 0) >= config.death_at:
        return "starved"
    if config.water_on and current.thirst.get(person, 0) >= config.thirst_death_at:
        return "died of thirst"
    if config.warmth_on and current.cold.get(person, 0) >= config.cold_death_at:
        return "froze to death"
    if config.on("wolves") and current.persona.hurt.get(person, 0) >= config.lever("lethal_hurt"):
        return "was killed by a wolf"
    if config.on("family") and current.age.get(person, 0) >= lifespan_of(config, person):
        return "died of old age"
    return "died"


def estate_of(ledger: Any, person: str) -> tuple[tuple[str, int], ...]:
    """Every unit the person holds, by resource, including any that a promise has put on hold."""
    out = [("food", ledger.balances.get(person, 0))]
    out += [(resource, ledger.holdings[resource].get(person, 0)) for resource in sorted(ledger.holdings)]
    return tuple((r, n) for r, n in out if n > 0)


def heirs(overlay: Any, death: Death) -> set[str]:
    """Who the dead person left behind: partner, parents and children (and their guardian's dependents)."""
    kin = {death.partner} - {""}
    kin |= {p for p in (overlay.parent.get(death.person), overlay.second_parent.get(death.person)) if p}
    kin |= {c for c, p in overlay.parent.items() if p == death.person}
    kin |= {c for c, p in overlay.second_parent.items() if p == death.person}
    return {k for k in kin if overlay.alive(k)}


def advance_aftermath(previous: Any, current: Any, decisions: Mapping[str, Any], record: Any, ledger: Any,
                      config: "WorldConfig") -> tuple[tuple[Death, ...], tuple[Any, ...]]:
    """The death records and the grave markers after one tick."""
    from world.family import lifespan
    from world.sky import sight
    from world.structures import Struct
    deaths = list(previous.things.deaths)
    structs = list(current.things.structures)
    new = sorted(a for a in current.died_at if a not in previous.died_at)
    radius = sight(config, previous.sky, config.perception_radius)
    for dead in new:
        x, y = current.positions[dead]
        seen = tuple(sorted(a for a in current.living if max(abs(current.positions[a][0] - x), abs(current.positions[a][1] - y)) <= radius))
        partner = previous.family.partner.get(dead, "") if config.on("family") else ""
        deaths.append(Death(dead, current.tick, x, y, current.age.get(dead, 0), cause_of(config, previous, current, dead, lifespan),
                            seen, estate_of(ledger, dead), "", partner))
        structs.append(Struct("grave", dead, x, y, current.tick, 0))
    collectors: dict[str, str] = {}
    for o in record.outcomes:
        if o.operation == OP_TRANSFER and o.accepted and o.actor in previous.died_at:
            receiver = next((e.account.rsplit(":", 1)[-1] for e in o.effects if e.delta > 0), "")
            collectors.setdefault(o.actor, receiver)                     # the first transfer out of their account since they died names who took it
    if collectors:
        deaths = [replace(d, taker=collectors[d.person]) if d.person in collectors and not d.taker else d for d in deaths]
        structs = [replace(s, b=1) if s.kind == "grave" and s.owner in collectors else s for s in structs]
    return tuple(deaths), tuple(sorted(structs, key=lambda s: (s.kind, s.owner)))
