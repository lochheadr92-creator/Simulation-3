"""The world state the kernel does not hold: homes, positions, needs, deaths,
the shelters people have built, and what each person remembers seeing.

Immutable and canonical like the kernel's WorldState; replaced, never edited.
Food units are not here on purpose: they live in the kernel ledger, and the
overlay only ever reads them through the kernel's own views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from kernel import digest as canonical_digest
from world.social import FOOD_MEMORY_LIMIT
from world.ecology import CONDITION_MAX, SEASONS
from world.persona import Persona
from world.pledges import Pledges
from world.sky import Sky
from world.things import Things

Position = tuple[int, int]


def _positions(raw: Mapping[str, Any]) -> Mapping[str, Position]:
    out: dict[str, Position] = {}
    for actor in sorted(raw):
        x, y = raw[actor]
        if type(x) is not int or type(y) is not int or x < 0 or y < 0:
            raise ValueError(f"{actor!r} needs a non-negative integer position, got {raw[actor]!r}")
        out[actor] = (x, y)
    return MappingProxyType(out)


def _levels(raw: Mapping[str, Any], *, positions: Mapping[str, Position], name: str) -> Mapping[str, int]:
    """One need level per person: the same roster as positions, or empty when
    that need is off. Hunger is always present; thirst and cold are not."""
    out = {actor: raw[actor] for actor in sorted(raw)}
    if out and set(out) != set(positions):
        raise ValueError(f"{name} must name the same people as positions, or be empty")
    for actor, value in out.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} of {actor!r} must be an integer of zero or more")
    return MappingProxyType(out)


def _links(raw: Mapping[str, Any], *, positions: Mapping[str, Position], name: str) -> Mapping[str, str]:
    """One person naming another: who asked whom, who owes whom. Both ends must
    be people the world knows, and nobody names themselves."""
    out = {actor: raw[actor] for actor in sorted(raw)}
    for actor, other in out.items():
        if actor not in positions or not isinstance(other, str) or other not in positions or other == actor:
            raise ValueError(f"{name} must name two different known people, got {actor!r} -> {other!r}")
    return MappingProxyType(out)


def _positive_ints(raw: Mapping[str, Any], *, roster: set[str], name: str) -> Mapping[str, int]:
    if set(raw) != roster:
        raise ValueError(f"{name} must name the same people as homes")
    out = {actor: raw[actor] for actor in sorted(raw)}
    for actor, value in out.items():
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} of {actor!r} must be a positive integer, got {value!r}")
    return MappingProxyType(out)


def _terrain_memory(raw: Mapping[str, Any], *, roster: set[str]) -> Mapping[str, tuple[Position, ...]]:
    """Per-person rough cells remembered from earlier views."""
    if set(raw) - roster:
        raise ValueError("terrain_memory must name known people")
    out: dict[str, tuple[Position, ...]] = {}
    for actor in sorted(raw):
        cells: list[Position] = []
        for cell in raw[actor]:
            if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                raise ValueError(f"{actor!r} remembers a bad terrain cell {cell!r}")
            x, y = cell
            if type(x) is not int or type(y) is not int or x < 0 or y < 0:
                raise ValueError(f"{actor!r} remembers a bad terrain cell {cell!r}")
            cells.append((x, y))
        out[actor] = tuple(sorted(set(cells)))
    return MappingProxyType(out)


@dataclass(frozen=True)
class Overlay:
    tick: int
    homes: Mapping[str, Position]
    positions: Mapping[str, Position]
    hunger: Mapping[str, int]
    yield_at: Mapping[str, int]
    died_at: Mapping[str, int] = field(default_factory=dict)
    thirst: Mapping[str, int] = field(default_factory=dict)   # empty unless water is on
    cold: Mapping[str, int] = field(default_factory=dict)     # empty unless warmth is on
    held: Mapping[str, int] = field(default_factory=dict)     # ticks still owed to the rough cell underfoot
    built: Mapping[str, int] = field(default_factory=dict)    # ticks of work each person has put into their shelter
    shelters: tuple[Position, ...] = ()                       # cells somebody has finished; permanent
    together: Mapping[str, int] = field(default_factory=dict) # "a|b" -> consecutive ticks side by side and well
    requests: Mapping[str, str] = field(default_factory=dict) # asker -> the person they asked, awaiting an answer
    promises: Mapping[str, str] = field(default_factory=dict) # helper -> the person they agreed to bring food to
    age: Mapping[str, int] = field(default_factory=dict)      # ticks lived; everyone at genesis starts grown
    parent: Mapping[str, str] = field(default_factory=dict)   # child -> the person whose home they were born beside
    second_parent: Mapping[str, str] = field(default_factory=dict)  # child -> other birth parent, when shared care is on
    birth_ready: Mapping[str, int] = field(default_factory=dict)  # first tick eligible after birth recovery
    terrain_memory: Mapping[str, tuple[Position, ...]] = field(default_factory=dict)  # actor -> rough cells remembered
    food_memory: Mapping[str, tuple[tuple[str, int], ...]] = field(default_factory=dict)  # recipient -> (donor, tick)
    patch_condition: Mapping[str, int] = field(default_factory=dict)  # food source -> growing condition
    season: str | None = None  # recorded world season; absent in older runs
    home_targets: Mapping[str, Position] = field(default_factory=dict)
    home_settled: Mapping[str, int] = field(default_factory=dict)
    home_caches: Mapping[str, Position] = field(default_factory=dict)
    home_trip_ticks: Mapping[str, int] = field(default_factory=dict)
    home_strain: Mapping[str, int] = field(default_factory=dict)
    shelter_memory: Mapping[str, tuple[Position, ...]] = field(default_factory=dict)
    fishing_cast: Mapping[str, Position] = field(default_factory=dict)
    food_sightings: Mapping[str, tuple[tuple[str, int, int], ...]] = field(default_factory=dict)  # source, stocked, seen tick
    source_reports: Mapping[str, tuple[tuple[str, str, int, int], ...]] = field(default_factory=dict)  # source, speaker, seen, heard
    empty_sources: Mapping[str, tuple[tuple[str, int], ...]] = field(default_factory=dict)
    provision_trips: Mapping[str, str] = field(default_factory=dict)  # gather once, then return home
    food_expected: Mapping[str, tuple[str, int]] = field(default_factory=dict)  # listener -> speaker, heard tick
    persona: Persona = field(default_factory=Persona)  # traits, skills, fatigue, sleep, recent attempts (rich-world features)
    sky: Sky | None = None  # the sky of this tick: phase, weather, temperature (sky feature)
    things: Things = field(default_factory=Things)  # what is in the world besides people and food: wolves so far
    pledges: Pledges = field(default_factory=Pledges)  # requests for help, promises, and how each ended this tick (pledges feature)

    def __post_init__(self) -> None:
        if self.season is not None and self.season not in SEASONS:
            raise ValueError("season must be plentiful, lean, or absent")
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("a tick must be an integer of zero or more")
        homes = _positions(self.homes)
        positions = _positions(self.positions)
        expectations = {}
        if not isinstance(self.food_expected, Mapping):
            raise ValueError("food expectations must map listeners to announcements")
        for listener, entry in self.food_expected.items():
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise ValueError("a food expectation needs a speaker and heard tick")
            speaker, heard = entry
            if (listener not in positions or not isinstance(speaker, str) or speaker not in positions
                    or speaker == listener or type(heard) is not int or not 0 <= heard <= self.tick):
                raise ValueError("food expectations need distinct known people and a past heard tick")
            expectations[listener] = (speaker, heard)
        object.__setattr__(self, "food_expected", MappingProxyType(dict(sorted(expectations.items()))))
        trips = dict(self.provision_trips)
        if any(p not in positions or phase not in ("gather", "return") for p, phase in trips.items()):
            raise ValueError("provision trips need known people and gather or return phases")
        object.__setattr__(self, "provision_trips", MappingProxyType(dict(sorted(trips.items()))))
        for name in ("home_trip_ticks", "home_strain"):
            values = dict(getattr(self, name))
            if any(p not in positions or type(n) is not int or n < 0 for p,n in values.items()):
                raise ValueError(f"{name} needs known people and non-negative integer counts")
            object.__setattr__(self, name, MappingProxyType(dict(sorted(values.items()))))
        object.__setattr__(self, "shelter_memory", _terrain_memory(self.shelter_memory, roster=set(positions)))
        for name, length in (("food_sightings", 3), ("source_reports", 4)):
            raw = getattr(self, name)
            if not isinstance(raw, Mapping):
                raise ValueError(f"{name} must map people to observations")
            memories = {}
            for actor, entries in raw.items():
                if actor not in positions or not isinstance(entries, (tuple, list)):
                    raise ValueError(f"{name} needs known people and a list of entries")
                recent = {}
                for entry in entries:
                    if not isinstance(entry, (tuple, list)) or len(entry) != length:
                        raise ValueError(f"invalid {name} entry")
                    sid = entry[0]
                    if not isinstance(sid, str) or not sid or sid in recent:
                        raise ValueError(f"{name} needs distinct source names")
                    if length == 3:
                        _, stocked, seen = entry
                        valid = type(stocked) is int and stocked in (0, 1)
                    else:
                        _, speaker, seen, heard = entry
                        valid = (isinstance(speaker, str) and speaker in positions and speaker != actor
                                 and type(heard) is int and type(seen) is int and seen < heard <= self.tick)
                    if not valid or type(seen) is not int or not 0 <= seen <= self.tick:
                        raise ValueError(f"invalid {name} provenance or date")
                    recent[sid] = tuple(entry)
                if recent:
                    memories[actor] = tuple(recent[sid] for sid in sorted(recent))
            object.__setattr__(self, name, MappingProxyType(dict(sorted(memories.items()))))
        empty = {}
        if not isinstance(self.empty_sources, Mapping):
            raise ValueError("empty_sources must map people to remembered sightings")
        for actor, entries in self.empty_sources.items():
            if actor not in positions or not isinstance(entries, (tuple, list)):
                raise ValueError("empty source memories need a known person and a list of sightings")
            recent = {}
            for entry in entries:
                if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                    raise ValueError("an empty source memory needs a source and tick")
                sid, when = entry
                if (not isinstance(sid, str) or not sid or sid in recent
                        or type(when) is not int or not 0 <= when <= self.tick):
                    raise ValueError("empty source memories need distinct source names and observed ticks")
                recent[sid] = when
            if recent:
                empty[actor] = tuple(sorted(recent.items()))
        object.__setattr__(self, "empty_sources", MappingProxyType(dict(sorted(empty.items()))))
        casts = _positions(self.fishing_cast)
        if set(casts) - set(positions):
            raise ValueError("fishing casts must name known people")
        object.__setattr__(self, "fishing_cast", casts)
        targets = _positions(self.home_targets)
        if set(targets) - set(positions):
            raise ValueError("home targets must name known people")
        settled = dict(self.home_settled)
        for actor, when in settled.items():
            if actor not in positions or type(when) is not int or not 0 < when <= self.tick:
                raise ValueError("home settlement needs a known person and completed tick")
        if any(not isinstance(sid, str) or not sid for sid in self.home_caches):
            raise ValueError("home caches need source names")
        caches = _positions(self.home_caches)
        if len(set(caches.values())) != len(caches):
            raise ValueError("a home cannot have two caches")
        object.__setattr__(self, "home_targets", targets)
        object.__setattr__(self, "home_settled", MappingProxyType(dict(sorted(settled.items()))))
        object.__setattr__(self, "home_caches", caches)
        if set(homes) != set(positions) or set(positions) != set(self.hunger):
            raise ValueError("homes, positions and hunger must name the same people")
        hunger = {actor: self.hunger[actor] for actor in sorted(self.hunger)}
        for actor, value in hunger.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"hunger of {actor!r} must be an integer of zero or more")
        died = {actor: self.died_at[actor] for actor in sorted(self.died_at)}
        for actor, when in died.items():
            if actor not in positions or type(when) is not int or when < 0 or when > self.tick:
                raise ValueError(f"death of {actor!r} must name a known person and an earlier tick")
        yield_at = _positive_ints(self.yield_at, roster=set(homes), name="yield_at")
        if self.sky is not None and not isinstance(self.sky, Sky):
            raise ValueError("sky must be a Sky or absent")
        if not isinstance(self.persona, Persona):
            raise ValueError("persona must be a Persona")
        if not isinstance(self.things, Things):
            raise ValueError("things must be a Things")
        if not isinstance(self.pledges, Pledges):
            raise ValueError("pledges must be a Pledges")
        self.pledges.check(set(positions), self.tick)
        self.persona.check(set(positions), self.tick)
        object.__setattr__(self, "thirst", _levels(self.thirst, positions=positions, name="thirst"))
        object.__setattr__(self, "cold", _levels(self.cold, positions=positions, name="cold"))
        object.__setattr__(self, "held", _levels(self.held, positions=positions, name="held"))
        object.__setattr__(self, "built", _levels(self.built, positions=positions, name="built"))
        together = {pair: self.together[pair] for pair in sorted(self.together)}
        for pair, value in together.items():
            ends = pair.split("|") if isinstance(pair, str) else []
            if len(ends) != 2 or any(end not in positions for end in ends) or ends[0] >= ends[1]:
                raise ValueError(f"a pair must name two known people in order, got {pair!r}")
            if type(value) is not int or value < 0:
                raise ValueError(f"the count for {pair!r} must be an integer of zero or more")
        object.__setattr__(self, "together", MappingProxyType(together))
        object.__setattr__(self, "requests", _links(self.requests, positions=positions, name="requests"))
        object.__setattr__(self, "promises", _links(self.promises, positions=positions, name="promises"))
        object.__setattr__(self, "age", _levels(self.age, positions=positions, name="age"))
        object.__setattr__(self, "birth_ready", _levels(self.birth_ready, positions=positions, name="birth_ready"))
        object.__setattr__(self, "parent", _links(self.parent, positions=positions, name="parent"))
        if not isinstance(self.second_parent, Mapping):
            raise ValueError("second_parent must map children to their other birth parent")
        second_parent = _links(self.second_parent, positions=positions, name="second_parent")
        if any(child not in self.parent or self.parent[child] == other
               for child, other in second_parent.items()):
            raise ValueError("second_parent needs an existing child and a distinct birth parent")
        object.__setattr__(self, "second_parent", second_parent)
        object.__setattr__(self, "terrain_memory", _terrain_memory(self.terrain_memory, roster=set(positions)))
        memories = {}
        if not isinstance(self.food_memory, Mapping):
            raise ValueError("food_memory must map recipients to remembered donors")
        for actor, entries in self.food_memory.items():
            if actor not in positions or not isinstance(entries, (list, tuple)) or len(entries) > FOOD_MEMORY_LIMIT:
                raise ValueError("food_memory needs a known recipient and at most four donors")
            recent = {}
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                    raise ValueError("a food memory needs a donor and tick")
                donor, when = entry
                if (not isinstance(donor, str) or donor not in positions or donor == actor or donor in recent
                        or type(when) is not int or not 0 < when <= self.tick):
                    raise ValueError("a food memory needs a distinct known donor and completed tick")
                recent[donor] = when
            if recent:
                memories[actor] = tuple(sorted(recent.items(), key=lambda item: (-item[1], item[0])))
        object.__setattr__(self, "food_memory", MappingProxyType(dict(sorted(memories.items()))))
        if not isinstance(self.patch_condition, Mapping):
            raise ValueError("patch_condition must map food sources to condition")
        condition = {}
        for source, value in self.patch_condition.items():
            if (not isinstance(source, str) or not source or type(value) is not int
                    or not 0 <= value <= CONDITION_MAX):
                raise ValueError("patch condition needs a source name and integer from zero to 100")
            condition[source] = value
        object.__setattr__(self, "patch_condition", MappingProxyType(dict(sorted(condition.items()))))
        shelters = tuple(sorted(tuple(cell) for cell in self.shelters))
        for cell in shelters:
            if (len(cell) != 2 or type(cell[0]) is not int or type(cell[1]) is not int
                    or cell[0] < 0 or cell[1] < 0):
                raise ValueError(f"a shelter needs a non-negative integer cell, got {cell!r}")
        if len(set(shelters)) != len(shelters):
            raise ValueError("a cell cannot hold two shelters")
        object.__setattr__(self, "shelters", shelters)
        object.__setattr__(self, "homes", homes)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "hunger", MappingProxyType(hunger))
        object.__setattr__(self, "died_at", MappingProxyType(died))
        object.__setattr__(self, "yield_at", yield_at)

    @property
    def roster(self) -> tuple[str, ...]:
        return tuple(sorted(self.positions))

    def alive(self, actor: str) -> bool:
        return actor not in self.died_at

    def children_of(self, actor: str) -> frozenset[str]:
        """Birth relationships persist through moves, adulthood and death."""
        return frozenset(child for links in (self.parent, self.second_parent)
                         for child, parent in links.items() if parent == actor)

    @property
    def living(self) -> tuple[str, ...]:
        return tuple(actor for actor in self.roster if self.alive(actor))

    def canonical(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            **({"provision_trips": dict(self.provision_trips)} if self.provision_trips else {}),
            **({"food_expected": {p: list(entry) for p, entry in self.food_expected.items()}} if self.food_expected else {}),
            **({"food_sightings": {p: [list(e) for e in entries] for p, entries in self.food_sightings.items()}} if self.food_sightings else {}),
            **({"source_reports": {p: [list(e) for e in entries] for p, entries in self.source_reports.items()}} if self.source_reports else {}),
            **({"empty_sources": {p: [list(e) for e in entries] for p,entries in self.empty_sources.items()}}
               if self.empty_sources else {}),
            **({"fishing_cast": {p: list(pos) for p,pos in self.fishing_cast.items()}} if self.fishing_cast else {}),
            "homes": {actor: list(pos) for actor, pos in self.homes.items()},
            "positions": {actor: list(pos) for actor, pos in self.positions.items()},
            "hunger": dict(self.hunger),
            "yield_at": dict(self.yield_at),
            "died_at": dict(self.died_at),
            **({"home_targets": {p: list(pos) for p, pos in self.home_targets.items()}} if self.home_targets else {}),
            **({"home_settled": dict(self.home_settled)} if self.home_settled else {}),
            **({"home_caches": {s: list(pos) for s, pos in self.home_caches.items()}} if self.home_caches else {}),
            **({"home_trip_ticks": dict(self.home_trip_ticks)} if self.home_trip_ticks else {}),
            **({"home_strain": dict(self.home_strain)} if self.home_strain else {}),
            **({"shelter_memory": {p: [list(pos) for pos in sites] for p,sites in self.shelter_memory.items()}}
               if self.shelter_memory else {}),
            **({"season": self.season} if self.season is not None else {}),
            **({"patch_condition": dict(self.patch_condition)} if self.patch_condition else {}),
            **({"food_memory": {actor: [list(entry) for entry in entries]
                                for actor, entries in self.food_memory.items()}} if self.food_memory else {}),
            **({"thirst": dict(self.thirst)} if self.thirst else {}),
            **({"cold": dict(self.cold)} if self.cold else {}),
            **({"held": dict(self.held)} if any(self.held.values()) else {}),
            **({"built": dict(self.built)} if any(self.built.values()) else {}),
            **({"shelters": [list(cell) for cell in self.shelters]} if self.shelters else {}),
            **({"together": dict(self.together)} if self.together else {}),
            **({"requests": dict(self.requests)} if self.requests else {}),
            **({"promises": dict(self.promises)} if self.promises else {}),
            **({"age": dict(self.age)} if self.age else {}),
            **({"birth_ready": dict(self.birth_ready)} if self.birth_ready else {}),
            **({"parent": dict(self.parent)} if self.parent else {}),
            **({"second_parent": dict(self.second_parent)} if self.second_parent else {}),
            **({"persona": self.persona.canonical()} if self.persona else {}),
            **({"sky": self.sky.canonical()} if self.sky is not None else {}),
            **({"things": self.things.canonical()} if self.things else {}),
            **({"pledges": self.pledges.canonical()} if self.pledges else {}),
            **({"terrain_memory": {actor: [list(cell) for cell in cells]
                                   for actor, cells in self.terrain_memory.items()}}
               if self.terrain_memory else {}),
        }

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Overlay":
        """Rebuild an overlay from `canonical()` (slice 1c: replay, recovery).
        The shape is checked here; every value is validated by the constructor."""
        keys = {"tick", "homes", "positions", "hunger", "yield_at", "died_at"}
        if isinstance(data, Mapping):
            for extra in ("thirst", "cold", "held", "built", "shelters", "together", "requests", "promises",
                          "age", "parent", "second_parent", "terrain_memory", "birth_ready", "food_memory", "patch_condition", "season",
                          "home_targets", "home_settled", "home_caches", "home_trip_ticks", "home_strain", "shelter_memory", "fishing_cast", "empty_sources", "provision_trips", "food_expected", "food_sightings", "source_reports", "persona", "sky", "things", "pledges"):
                if extra in data:
                    keys = keys | {extra}
        if not isinstance(data, Mapping) or set(data) != keys:
            raise ValueError(f"a canonical overlay needs exactly the keys {sorted(keys)}")
        for name in sorted(keys - {"tick", "shelters", "season"}):
            if not isinstance(data[name], Mapping):
                raise ValueError(f"a canonical overlay needs a mapping of {name}")
        if "shelters" in keys and not isinstance(data["shelters"], list):
            raise ValueError("a canonical overlay needs a list of shelters")

        def cells(raw: Mapping[str, Any]) -> dict[str, Position]:
            out: dict[str, Position] = {}
            for actor, cell in raw.items():
                if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                    raise ValueError(f"{actor!r} needs a two-integer position, got {cell!r}")
                out[actor] = (cell[0], cell[1])
            return out

        return cls(tick=data["tick"], homes=cells(data["homes"]), positions=cells(data["positions"]),
                   hunger=dict(data["hunger"]), yield_at=dict(data["yield_at"]), died_at=dict(data["died_at"]),
                   thirst=dict(data.get("thirst", {})), cold=dict(data.get("cold", {})),
                   held=dict(data.get("held", {})), built=dict(data.get("built", {})),
                   shelters=tuple(tuple(cell) for cell in data.get("shelters", ())),
                   together=dict(data.get("together", {})),
                   requests=dict(data.get("requests", {})), promises=dict(data.get("promises", {})),
                   age=dict(data.get("age", {})), parent=dict(data.get("parent", {})),
                   second_parent=dict(data.get("second_parent", {})),
                   persona=Persona.from_canonical(data["persona"]) if "persona" in data else Persona(),
                   sky=Sky.from_canonical(data["sky"]) if "sky" in data else None,
                   things=Things.from_canonical(data["things"]) if "things" in data else Things(),
                   pledges=Pledges.from_canonical(data["pledges"]) if "pledges" in data else Pledges(),
                   birth_ready=dict(data.get("birth_ready", {})),
                   food_memory=dict(data.get("food_memory", {})),
                   patch_condition=dict(data.get("patch_condition", {})),
                   season=data.get("season"),
                   empty_sources=dict(data.get("empty_sources", {})),
                   food_sightings=dict(data.get("food_sightings", {})),
                   source_reports=dict(data.get("source_reports", {})),
                   provision_trips=dict(data.get("provision_trips", {})),
                   food_expected=dict(data.get("food_expected", {})),
                   fishing_cast=cells(data.get("fishing_cast", {})),
                   home_targets=cells(data.get("home_targets", {})),
                   home_settled=dict(data.get("home_settled", {})),
                   home_caches=cells(data.get("home_caches", {})),
                   home_trip_ticks=dict(data.get("home_trip_ticks", {})),
                   home_strain=dict(data.get("home_strain", {})),
                   shelter_memory=dict(data.get("shelter_memory", {})),
                   terrain_memory={actor: tuple(tuple(cell) for cell in cells)
                                   for actor, cells in dict(data.get("terrain_memory", {})).items()})

    def digest(self) -> str:
        return canonical_digest(self.canonical())
