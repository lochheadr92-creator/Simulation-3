"""Who each person is: temperament, practised skills, tiredness, recent attempts.

Traits are fixed at birth. Skills grow only from successful work, and every
point comes from an accepted outcome or a finished work tick, never from time
passing. Fatigue and sleep belong to `world/rest.py`'s rules and are kept here
with the rest of what is true of one person's inner state.

Everything is an integer, because the canonical form refuses anything else.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_CLAIM

from world.belief import check_belief
from world.feature import Feature
from world.rest import COLLAPSE, SLEEP, WORK_KINDS, rest_rate
from world.society import check_bond
from world.traits import BUILDING, CRAFTING, FISHING, GATHERING, SKILL_STEPS, SKILLS, TRAITS

if TYPE_CHECKING:
    from world.config import WorldConfig
    from world.overlay import Overlay

TRAIT_SEED_OFFSET = 2_000_003              # its own generator: traits never move a home or a terrain cell
TRIED_LIMIT = 4

PERSONALITY = Feature(
    name="personality",
    summary="Each person has five fixed traits that change what they choose.",
    rule=(
        "Everyone has five traits from 0 to 100: generosity, sociability, caution, diligence, curiosity. "
        "At genesis each person draws them from their own generator (seed + 2000003), in id order. A newborn "
        "takes the average of its two birth adults plus a deterministic offset of -15 to 15 from the seed, "
        "its name and the trait, kept between 5 and 95. Traits never change. A trait is compared with 50, "
        "so a middling person behaves as before. Generosity under 35: with food in hand, offers it to a "
        "visibly starving stranger only when holding two or more (their own children are fed regardless); "
        "35 to 74: as before; 75 or more: also hands a unit of water to a visibly parched stranger. "
        "Caution moves every leave-in-time estimate (food, water, shelter) by (caution - 50) // 10 ticks "
        "earlier and brings tiredness on by the same amount. Diligence lets work continue through "
        "(diligence - 50) // 5 more points of fatigue and, at a shared home cache, raises the meals that "
        "count as low by one when 70 or more and lowers it by one when under 30. "
        "Sociability and curiosity are drawn and inherited from the start and act through conversation "
        "and exploration when those are on."),
    tables={"traits": list(TRAITS)},
)

SKILLS_FEATURE = Feature(
    name="skills",
    summary="Practice at gathering, fishing and building makes people better at them.",
    rule=(
        "Five skills (gathering, fishing, building, farming, crafting) start at zero practice. One point is "
        "earned for each accepted food or wood claim (gathering; fishing when the claim is at the fishing "
        "spot), each fishing cast, and each work tick on a shelter (building). Levels begin at 0, 8, 24, "
        "48, 80 and 120 points. Every two gathering levels add one unit to the pack a claim takes, every "
        "two fishing levels add one unit to a catch, and each building level takes one work tick off "
        "the shelter, to a minimum of four. Points are never lost. Farming and crafting count practice "
        "once those activities are on."),
    tables={"skills": list(SKILLS), "skill_steps": list(SKILL_STEPS)},
)


def _digest_int(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def draw_traits(seed: int, actors: tuple[str, ...]) -> dict[str, tuple[int, ...]]:
    rng = random.Random(seed + TRAIT_SEED_OFFSET)
    return {actor: tuple(rng.randint(10, 90) for _ in TRAITS) for actor in actors}


def inherit_traits(seed: int, name: str, first: tuple[int, ...], second: tuple[int, ...]) -> tuple[int, ...]:
    out = []
    for index, trait in enumerate(TRAITS):
        offset = _digest_int(seed, name, trait) % 31 - 15
        out.append(min(95, max(5, (first[index] + second[index]) // 2 + offset)))
    return tuple(out)


def _frozen(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: raw[key] for key in sorted(raw)})


def _tuples(raw: Mapping[str, Any], name: str, length: int, low: int, high: int | None) -> Mapping[str, tuple[int, ...]]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{name} must map people to values")
    out = {}
    for actor in sorted(raw):
        values = raw[actor]
        if (not isinstance(actor, str) or not isinstance(values, (list, tuple)) or len(values) != length
                or any(type(v) is not int or v < low or (high is not None and v > high) for v in values)):
            raise ValueError(f"{name} of {actor!r} needs {length} integers from {low}" + (f" to {high}" if high is not None else ""))
        out[actor] = tuple(values)
    return MappingProxyType(out)


def _ints(raw: Mapping[str, Any], name: str) -> Mapping[str, int]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{name} must map people to numbers")
    out = {}
    for actor in sorted(raw):
        if not isinstance(actor, str) or type(raw[actor]) is not int or raw[actor] < 0:
            raise ValueError(f"{name} of {actor!r} must be an integer of zero or more")
        out[actor] = raw[actor]
    return MappingProxyType(out)


@dataclass(frozen=True)
class Persona:
    """Per-person inner state. Each part is empty when its feature is off."""

    traits: Mapping[str, tuple[int, ...]] = field(default_factory=dict)   # person -> TRAITS order, 0..100
    skills: Mapping[str, tuple[int, ...]] = field(default_factory=dict)   # person -> SKILLS order, practice points
    fatigue: Mapping[str, int] = field(default_factory=dict)
    asleep: Mapping[str, int] = field(default_factory=dict)               # person -> tick they fell asleep
    tried: Mapping[str, tuple[tuple[str, str, int, int], ...]] = field(default_factory=dict)  # kind, target, tick, 1 ok / 0 refused
    doing: Mapping[str, str] = field(default_factory=dict)                # what each person decided last tick, so a choice can resist flip-flopping
    beliefs: Mapping[str, tuple[tuple[Any, ...], ...]] = field(default_factory=dict)   # person -> what they believe (world.belief)
    hurt: Mapping[str, int] = field(default_factory=dict)                 # person -> injury; the dead keep what they died of
    bonds: Mapping[str, tuple[tuple[Any, ...], ...]] = field(default_factory=dict)   # person -> their view of each other (world.society)
    lonely: Mapping[str, int] = field(default_factory=dict)               # person -> need for company; nobody dies of it
    talking: Mapping[str, tuple[str, int]] = field(default_factory=dict)  # person -> (who they are talking to, tick it began)

    def __post_init__(self) -> None:
        if not isinstance(self.doing, Mapping) or any(
                not isinstance(a, str) or not isinstance(k, str) or not k or len(k) > 24 for a, k in self.doing.items()):
            raise ValueError("doing must map people to the kind of what they last decided")
        object.__setattr__(self, "doing", MappingProxyType({a: self.doing[a] for a in sorted(self.doing)}))
        object.__setattr__(self, "traits", _tuples(self.traits, "traits", len(TRAITS), 0, 100))
        object.__setattr__(self, "skills", _tuples(self.skills, "skills", len(SKILLS), 0, None))
        object.__setattr__(self, "fatigue", _ints(self.fatigue, "fatigue"))
        object.__setattr__(self, "asleep", _ints(self.asleep, "asleep"))
        if not isinstance(self.tried, Mapping):
            raise ValueError("tried must map people to recent attempts")
        tried = {}
        for actor in sorted(self.tried):
            entries = self.tried[actor]
            if not isinstance(actor, str) or not isinstance(entries, (list, tuple)) or len(entries) > TRIED_LIMIT:
                raise ValueError(f"tried of {actor!r} needs at most {TRIED_LIMIT} attempts")
            checked = []
            for entry in entries:
                if (not isinstance(entry, (list, tuple)) or len(entry) != 4 or not isinstance(entry[0], str)
                        or not isinstance(entry[1], str) or type(entry[2]) is not int or entry[2] < 0
                        or entry[3] not in (0, 1) or type(entry[3]) is not int):
                    raise ValueError(f"tried of {actor!r} has a bad attempt {entry!r}")
                checked.append(tuple(entry))
            if checked:
                tried[actor] = tuple(checked)
        object.__setattr__(self, "tried", MappingProxyType(tried))
        object.__setattr__(self, "hurt", _ints(self.hurt, "hurt"))
        if not isinstance(self.beliefs, Mapping):
            raise ValueError("beliefs must map people to what they believe")
        beliefs = {}
        for actor in sorted(self.beliefs):
            entries = self.beliefs[actor]
            if not isinstance(actor, str) or not isinstance(entries, (list, tuple)):
                raise ValueError(f"beliefs of {actor!r} must be a list")
            if any(not isinstance(e, (list, tuple)) or len(e) != 7 for e in entries):
                raise ValueError(f"beliefs of {actor!r} must each be kind, subject, x, y, seen, learned, via")
            ordered = tuple(sorted((tuple(e) for e in entries), key=lambda e: (str(e[0]), str(e[1]))))
            if len({(e[0], e[1]) for e in ordered}) != len(ordered):
                raise ValueError(f"{actor!r} believes the same thing twice")
            if ordered:
                beliefs[actor] = ordered
        object.__setattr__(self, "beliefs", MappingProxyType(beliefs))
        object.__setattr__(self, "lonely", _ints(self.lonely, "lonely"))
        if not isinstance(self.bonds, Mapping) or not isinstance(self.talking, Mapping):
            raise ValueError("bonds and talking must map people to values")
        bonds = {}
        for actor in sorted(self.bonds):
            entries = self.bonds[actor]
            if not isinstance(actor, str) or not isinstance(entries, (list, tuple)) or any(
                    not isinstance(e, (list, tuple)) or len(e) != 8 for e in entries):
                raise ValueError(f"bonds of {actor!r} must each be other, bond, trust, grudge, last, why, grieved, tone")
            ordered = tuple(sorted((tuple(e) for e in entries), key=lambda e: str(e[0])))
            if len({e[0] for e in ordered}) != len(ordered):
                raise ValueError(f"{actor!r} has two bonds with the same person")
            if ordered:
                bonds[actor] = ordered
        object.__setattr__(self, "bonds", MappingProxyType(bonds))
        talking = {}
        for actor in sorted(self.talking):
            entry = self.talking[actor]
            if (not isinstance(actor, str) or not isinstance(entry, (list, tuple)) or len(entry) != 2
                    or not isinstance(entry[0], str) or type(entry[1]) is not int or entry[1] < 0):
                raise ValueError(f"talking of {actor!r} must be a partner and the tick it began")
            talking[actor] = tuple(entry)
        object.__setattr__(self, "talking", MappingProxyType(talking))

    def __bool__(self) -> bool:
        return bool(self.traits or self.skills or self.fatigue or self.asleep or self.tried or self.doing
                    or self.beliefs or self.hurt or self.bonds or self.lonely or self.talking)

    def check(self, roster: set[str], tick: int) -> None:
        for name in ("traits", "skills", "fatigue"):
            names = set(getattr(self, name))
            if names and names != roster:
                raise ValueError(f"{name} must name every person, or nobody")
        for name in ("asleep", "tried", "doing", "beliefs", "hurt", "bonds", "lonely", "talking"):
            if set(getattr(self, name)) - roster:
                raise ValueError(f"{name} must name known people")
        for actor, entries in self.bonds.items():
            for entry in entries:
                check_bond(actor, entry, roster, tick)
        for actor, (partner, since) in self.talking.items():
            if partner not in roster or partner == actor or since > tick:
                raise ValueError(f"talking of {actor!r} must name another known person and a past tick")
        for actor, entries in self.beliefs.items():
            for entry in entries:
                check_belief(actor, entry, roster, tick)
        if any(when > tick for when in self.asleep.values()):
            raise ValueError("somebody fell asleep after the overlay's tick")
        if any(entry[2] > tick for entries in self.tried.values() for entry in entries):
            raise ValueError("an attempt is dated after the overlay's tick")

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.traits:
            out["traits"] = {a: list(v) for a, v in self.traits.items()}
        if self.skills:
            out["skills"] = {a: list(v) for a, v in self.skills.items()}
        if self.fatigue:
            out["fatigue"] = dict(self.fatigue)
        if self.asleep:
            out["asleep"] = dict(self.asleep)
        if self.tried:
            out["tried"] = {a: [list(e) for e in entries] for a, entries in self.tried.items()}
        if self.doing:
            out["doing"] = dict(self.doing)
        if self.beliefs:
            out["beliefs"] = {a: [list(e) for e in entries] for a, entries in self.beliefs.items()}
        if self.hurt:
            out["hurt"] = dict(self.hurt)
        if self.bonds:
            out["bonds"] = {a: [list(e) for e in entries] for a, entries in self.bonds.items()}
        if self.lonely:
            out["lonely"] = dict(self.lonely)
        if self.talking:
            out["talking"] = {a: list(entry) for a, entry in self.talking.items()}
        return out

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Persona":
        if not isinstance(data, Mapping) or set(data) - {"traits", "skills", "fatigue", "asleep", "tried", "doing",
                                                         "beliefs", "hurt", "bonds", "lonely", "talking"}:
            raise ValueError("a canonical persona holds traits, skills, fatigue, asleep, tried, doing, beliefs, hurt, "
                             "bonds, lonely and talking only")
        return cls(traits=dict(data.get("traits", {})), skills=dict(data.get("skills", {})),
                   fatigue=dict(data.get("fatigue", {})), asleep=dict(data.get("asleep", {})),
                   tried={a: tuple(tuple(e) for e in entries) for a, entries in dict(data.get("tried", {})).items()},
                   doing=dict(data.get("doing", {})),
                   beliefs={a: tuple(tuple(e) for e in entries) for a, entries in dict(data.get("beliefs", {})).items()},
                   hurt=dict(data.get("hurt", {})),
                   bonds={a: tuple(tuple(e) for e in entries) for a, entries in dict(data.get("bonds", {})).items()},
                   lonely=dict(data.get("lonely", {})),
                   talking={a: tuple(entry) for a, entry in dict(data.get("talking", {})).items()})


def genesis_persona(config: "WorldConfig", actors: tuple[str, ...]) -> Persona:
    traits = draw_traits(config.seed, actors) if config.on("personality") else {}
    skills = {actor: (0,) * len(SKILLS) for actor in actors} if config.on("skills") else {}
    fatigue: dict[str, int] = {}
    if config.on("sleep"):
        spread = config.lever("tired_at")
        fatigue = {actor: index * spread // len(actors) for index, actor in enumerate(actors)}
    lonely = ({actor: index * config.lever("lonely_at") // len(actors) for index, actor in enumerate(actors)}
              if config.on("bonds") else {})
    return Persona(traits=traits, skills=skills, fatigue=fatigue, lonely={a: n for a, n in lonely.items() if n})


def born(persona: Persona, name: str, first: str, second: str, config: "WorldConfig") -> Persona:
    """A newcomer's inner state: inherited traits, no practice, fully rested."""
    traits, skills, fatigue = dict(persona.traits), dict(persona.skills), dict(persona.fatigue)
    if config.on("personality"):
        traits[name] = inherit_traits(config.seed, name, persona.traits[first], persona.traits[second])
    if config.on("skills"):
        skills[name] = (0,) * len(SKILLS)
    if config.on("sleep"):
        fatigue[name] = 0
    return replace(persona, traits=traits, skills=skills, fatigue=fatigue)


def _remember(tried: dict[str, tuple], actor: str, entry: tuple[str, str, int, int]) -> None:
    """Keep the four most recent distinct (kind, target) attempts, newest first."""
    kept = [e for e in tried.get(actor, ()) if (e[0], e[1]) != (entry[0], entry[1])]
    tried[actor] = tuple(([entry] + kept)[:TRIED_LIMIT])


remember_attempt = _remember


def advance_persona(previous: "Overlay", current: "Overlay", decisions: Mapping[str, Any], record: Any,
                    config: "WorldConfig") -> Persona:
    """Tiredness, sleep, practice and recent attempts after one settled tick.

    Reads what actually happened: a decision made, an outcome the kernel accepted
    or refused, a work tick finished. Nothing here moves a unit of anything."""
    persona = current.persona
    fatigue, asleep = dict(persona.fatigue), dict(persona.asleep)
    skills, tried = dict(persona.skills), dict(persona.tried)
    doing = dict(persona.doing)
    outcomes: dict[str, list[Any]] = {}
    for outcome in record.outcomes:
        outcomes.setdefault(outcome.actor, []).append(outcome)

    for actor in previous.living:
        decision = decisions.get(actor)
        if decision is None:
            continue
        mine = outcomes.get(actor, [])
        if config.on("explain") or config.on("sleep") or config.on("bonds"):
            doing[actor] = decision.kind
        if config.on("sleep"):
            sleeping = decision.kind in (SLEEP, COLLAPSE)
            night = config.on("sky") and previous.sky is not None and previous.sky.night
            if sleeping:
                rate = rest_rate(config, current.positions[actor] == current.homes[actor]) + (
                    config.lever("night_rest") if night else 0)
                fatigue[actor] = max(0, fatigue[actor] - rate)
                asleep[actor] = asleep.get(actor, previous.tick)
            else:
                worked = decision.kind in WORK_KINDS
                fatigue[actor] += (config.lever("fatigue_rate") + (config.lever("work_fatigue") if worked else 0)
                                   + (config.lever("night_fatigue") if night else 0))
                asleep.pop(actor, None)
        if config.on("skills"):
            gained = [0] * len(SKILLS)
            if decision.kind == "build" and current.built.get(actor, 0) > previous.built.get(actor, 0):
                gained[BUILDING] += 1
            elif decision.kind == "help" and any(
                    p.id == getattr(decision, "keeping", None)
                    and current.built.get(p.asker, 0) - previous.built.get(p.asker, 0) >= 2 for p in previous.pledges.open):
                gained[BUILDING] += 1                   # a hand at somebody's shelter counts as practice
            elif decision.kind == "fish":
                gained[FISHING] += 1
            elif decision.kind == "craft" and mine and all(o.accepted for o in mine):
                gained[CRAFTING] += 1
            elif decision.kind in ("claim", "gather_wood", "gather_stone") and any(
                    o.accepted and o.operation == OP_CLAIM for o in mine):
                gained[FISHING if decision.target == "fish" else GATHERING] += 1
            if any(gained):
                skills[actor] = tuple(points + extra for points, extra in zip(skills[actor], gained))
        if config.on("explain") and decision.kind in ("claim", "draw", "gather_wood", "offer", "eat"):
            for outcome in mine:
                _remember(tried, actor, (decision.kind, decision.target or "", previous.tick, 1 if outcome.accepted else 0))
    for actor in [a for a in asleep if a in current.died_at]:
        del asleep[actor]                      # the dead are not asleep
    for actor in [a for a in doing if a in current.died_at]:
        del doing[actor]
    return replace(persona, skills=skills, fatigue=fatigue, asleep=asleep, tried=tried, doing=doing)
