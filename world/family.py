"""Couples, pregnancy, growing old, orphans, grief and travellers.

Two adults who have come to like and trust each other, and are talking, become a couple. A couple that spends time
side by side may conceive; the carrier is pregnant for a fixed time, hungrier for it, and the child is then born next
door. People age past adulthood: slower once elder, and every person has a lifespan fixed by the seed, at the end of
which they die of old age. A child whose parents are all dead is taken in by an adult who can see them. Somebody
who loses a partner, a parent, a child or a friend grieves, and does no optional chores while it lasts. A traveller
comes when few people are left. The numbers that limit the population are settings written into the run header.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from world.draw import draw
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

FAMILY_LEVERS = (("couple_at", 18), ("couple_trust", 50), ("gestation", 30), ("pop_cap", 14), ("pregnant_hunger", 3),
                 ("elder_at", 300), ("old_age_at", 480), ("old_age_spread", 160), ("grief_kin", 60), ("grief_friend", 30),
                 ("grief_fade", 4), ("grief_at", 20), ("arrive_every", 120), ("arrive_below", 5), ("max_arrivals", 6))

FAMILY = Feature(
    name="family",
    summary="People pair up, have children, grow old and die of it; orphans are taken in, the bereaved grieve, travellers come.",
    rule=(
        "Two adults, both with no partner, who talk to each other this tick while each holds a bond of couple_at or "
        "more and trust of couple_trust or more in the other, and who are neither parent and child nor share a parent, "
        "become a couple. A couple who have spent together_ticks side by side, when the living plus those already "
        "pregnant number fewer than pop_cap, make the second of them pregnant; the pregnancy lasts gestation ticks, "
        "adds one hunger every pregnant_hunger ticks, and ends in a birth beside the carrier with the couple as "
        "parents. Nobody else is born in this world. Everybody's age keeps counting; from elder_at every third step "
        "costs an extra tick, and each person dies of old age at an age of old_age_at plus a number from 0 to "
        "old_age_spread fixed by the seed and their name. A child whose parents are all dead and who has no living "
        "guardian is taken in by the nearest living adult who can see them and has fewer than two dependents. When "
        "somebody dies, their living partner, parents and children grieve grief_kin, and anybody with a bond of "
        "friend_at or more grieves grief_friend; grief falls by one every grief_fade ticks, and while it is grief_at "
        "or more nobody mends, farms, makes tools or digs, and they grow lonelier. (With the aftermath feature on, only "
        "somebody who has just learned of the death grieves.) When fewer than arrive_below "
        "people are alive, and no traveller has come for arrive_every ticks, a traveller of grown age with traits "
        "of their own arrives at a free cell near the edge, at most max_arrivals times in all."),
    needs=("bonds",),
    levers=FAMILY_LEVERS,
    tables={"stages": ["child", "adult", "elder"]},
)


def lifespan(config: "WorldConfig", actor: str) -> int:
    """The age at which this person dies of old age: fixed by the seed and their name, never random at runtime."""
    return config.lever("old_age_at") + draw(config.seed, "lifespan", actor) % (config.lever("old_age_spread") + 1)


def stage(config: "WorldConfig", age: int) -> str:
    return "child" if age < config.adult_at else "elder" if age >= config.lever("elder_at") else "adult"


def _ints(raw: Mapping[str, int], name: str, high: int | None = None) -> Mapping[str, int]:
    out = {}
    for actor in sorted(raw):
        if not isinstance(actor, str) or type(raw[actor]) is not int or raw[actor] < 0 or (high is not None and raw[actor] > high):
            raise ValueError(f"{name} of {actor!r} must be an integer of zero or more")
        out[actor] = raw[actor]
    return MappingProxyType(out)


@dataclass(frozen=True)
class Family:
    partner: Mapping[str, str] = None                 # person -> their partner; always mutual
    pregnant: Mapping[str, tuple[int, str]] = None    # carrier -> (due tick, the other parent)
    grief: Mapping[str, int] = None                   # person -> 1..100
    guardian: Mapping[str, str] = None                # orphan -> the adult who took them in
    arrivals: int = 0                                 # travellers who have come, and the tick of the last one
    last_arrival: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "partner", MappingProxyType(dict(sorted((self.partner or {}).items()))))
        object.__setattr__(self, "pregnant", MappingProxyType(dict(sorted((self.pregnant or {}).items()))))
        object.__setattr__(self, "grief", _ints({a: n for a, n in (self.grief or {}).items() if n}, "grief", 100))
        object.__setattr__(self, "guardian", MappingProxyType(dict(sorted((self.guardian or {}).items()))))

    def __bool__(self) -> bool:
        return bool(self.partner or self.pregnant or self.grief or self.guardian or self.arrivals)

    def check(self, roster: set[str], tick: int) -> None:
        for a, b in self.partner.items():
            if a not in roster or b not in roster or a == b or self.partner.get(b) != a:
                raise ValueError(f"partners must be two different known people who name each other: {a!r} {b!r}")
        for carrier, (due, other) in self.pregnant.items():
            if carrier not in roster or other not in roster or carrier == other or type(due) is not int or due < 0:
                raise ValueError(f"a pregnancy needs a known carrier, another known parent and a due tick: {carrier!r}")
        if set(self.grief) - roster:
            raise ValueError("grief must name known people")
        for child, adult in self.guardian.items():
            if child not in roster or adult not in roster or child == adult:
                raise ValueError(f"a guardian must be another known person: {child!r} {adult!r}")
        if (type(self.arrivals) is not int or self.arrivals < 0 or type(self.last_arrival) is not int
                or not 0 <= self.last_arrival <= tick):
            raise ValueError("arrivals must be a count and the tick of the last one a past tick")

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.partner:
            out["partner"] = dict(self.partner)
        if self.pregnant:
            out["pregnant"] = {a: list(v) for a, v in self.pregnant.items()}
        if self.grief:
            out["grief"] = dict(self.grief)
        if self.guardian:
            out["guardian"] = dict(self.guardian)
        if self.arrivals:
            out["arrivals"] = [self.arrivals, self.last_arrival]
        return out

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Family":
        if not isinstance(data, Mapping) or set(data) - {"partner", "pregnant", "grief", "guardian", "arrivals"}:
            raise ValueError("a canonical family holds partner, pregnant, grief, guardian and arrivals only")
        arrivals = data.get("arrivals", [0, 0])
        return cls(partner=dict(data.get("partner", {})),
                   pregnant={a: tuple(v) for a, v in dict(data.get("pregnant", {})).items()},
                   grief=dict(data.get("grief", {})), guardian=dict(data.get("guardian", {})),
                   arrivals=arrivals[0], last_arrival=arrivals[1])


def are_kin(overlay: Any, a: str, b: str) -> bool:
    """Parent and child, or sharing a parent: not a pair who may become a couple."""
    pa = {overlay.parent.get(a), overlay.second_parent.get(a)} - {None}
    pb = {overlay.parent.get(b), overlay.second_parent.get(b)} - {None}
    return b in pa or a in pb or bool(pa & pb)


def advance_family(previous: Any, current: Any, config: "WorldConfig") -> Family:
    """Couples, grief and guardians after one tick. Births, arrivals and old-age deaths are made where people are added or die."""
    from world.society import bond_with, find, is_friend, trust_in
    family = previous.family
    persona = current.persona
    living = set(current.living)
    partner = {a: b for a, b in family.partner.items() if a in living and b in living}
    pregnant = {c: v for c, v in family.pregnant.items() if c in living}
    grief = {a: n for a, n in family.grief.items() if a in living}
    adult_at = config.adult_at

    def adult(a: str) -> bool:
        return current.age.get(a, adult_at) >= adult_at

    # a couple: two free adults talking, each fond and trusting
    for actor, (other, since) in sorted(persona.talking.items()):
        if (actor >= other or actor in partner or other in partner or actor not in living or other not in living
                or not adult(actor) or not adult(other) or are_kin(current, actor, other)):
            continue
        if persona.talking.get(other, (None,))[0] != actor:
            continue
        ok = all(bond_with(persona.bonds.get(x, ()), y) >= config.lever("couple_at")
                 and trust_in(persona.bonds.get(x, ()), y) >= config.lever("couple_trust")
                 for x, y in ((actor, other), (other, actor)))
        if ok:
            partner[actor], partner[other] = other, actor
    # With the aftermath feature, grief comes from a death somebody has just learned of: by seeing the marker or being
    # told. Without it, as before, everybody who loved the dead person grieves at the moment they die, wherever they are.
    knowers: dict[str, set[str]] = {}
    if config.on("aftermath"):
        for a in sorted(living):
            for b in persona.beliefs.get(a, ()):
                if b[0] == "death" and b[5] == previous.tick and b[1] not in living:
                    knowers.setdefault(b[1], set()).add(a)
    else:
        for dead in sorted(a for a in current.died_at if a not in previous.died_at):
            knowers[dead] = set(living)
    for dead, who in sorted(knowers.items()):
        mine = family.partner.get(dead)
        for x in sorted(who):
            kin = overlay_kin(current, x, dead) or mine == x
            level = (config.lever("grief_kin") if kin
                     else config.lever("grief_friend") if is_friend(persona.bonds.get(x, ()), dead, config) else 0)
            if level:
                grief[x] = max(grief.get(x, 0), level)
    if (current.tick + 1) % config.lever("grief_fade") == 0:
        grief = {a: n - 1 for a, n in grief.items() if n > 1}
    # a child with nobody left is taken in by an adult who can see them
    from world.sky import sight
    guardian = {c: g for c, g in family.guardian.items() if c in living and g in living}
    radius = sight(config, previous.sky, config.perception_radius)
    for child in sorted(living):
        if adult(child) or child in guardian:
            continue
        parents = {p for p in (current.parent.get(child), current.second_parent.get(child)) if p}
        if not parents or any(p in living for p in parents):
            continue
        near = sorted((max(abs(current.positions[a][0] - current.positions[child][0]),
                           abs(current.positions[a][1] - current.positions[child][1])), a) for a in living
                      if adult(a) and a != child
                      and max(abs(current.positions[a][0] - current.positions[child][0]),
                              abs(current.positions[a][1] - current.positions[child][1])) <= radius
                      and sum(1 for c, g in guardian.items() if g == a) + len(current.children_of(a)) < 2)
        if near:
            guardian[child] = near[0][1]
    return replace(family, partner=partner, pregnant=pregnant, grief=grief, guardian=guardian)


def overlay_kin(overlay: Any, x: str, dead: str) -> bool:
    """x is a parent or child of the dead person."""
    return (dead in {overlay.parent.get(x), overlay.second_parent.get(x)}) or (
        x in {overlay.parent.get(dead), overlay.second_parent.get(dead)})
