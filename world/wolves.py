"""Wolves: a danger that can be seen, remembered, told of and avoided.

Wolves belong to the world, not to anybody's mind. They arrive at one tick, wander, and
hunt anyone in the open within their sense: a person under a finished shelter is safe.
A wolf beside somebody bites, and the person is hurt; hurt slows them, heals with rest
and, past a limit, kills. What people do about it - see it, run, warn others, remember
where it was, keep away from there, put a trip off - is decided in `decide` from what
they can observe and believe. A wolf nobody has seen, and nobody has been told of,
changes nobody's plans.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from world.draw import draw
from world.feature import Feature

if TYPE_CHECKING:
    from world.belief import Belief
    from world.config import WorldConfig
    from world.sky import Sky

Position = tuple[int, int]

FLEE = "flee"
HEALING_KINDS = frozenset({"rest", "sleep", "warm", "collapse"})      # what a hurt person does that mends them fastest

WOLF_LEVERS = (("wolves", 1), ("wolf_arrival", 40), ("wolf_sense", 4), ("bite", 25),
               ("lethal_hurt", 100), ("bite_pause", 8), ("chase_limit", 10), ("giveup_pause", 16),
               ("limp_at", 40), ("heal_every", 3), ("heal_rest", 2), ("alarm", 3), ("danger_radius", 2),
               ("danger_span", 30), ("danger_cost", 6), ("wolf_margin", 6))

WOLVES = Feature(
    name="wolves",
    summary="Wolves hunt from dusk to dawn; people see them, run, warn each other and keep away from where they were.",
    rule=(
        "At tick wolf_arrival, `wolves` wolves appear, each at its own den: a cell on the map's edge drawn "
        "from the seed that nobody lives on and no source occupies. Wolves hunt only at dusk and at night. By day, and while resting, a wolf walks back "
        "to its den one step a tick and stays there. A hunting wolf looks for the nearest person standing in "
        "the open (not under a finished shelter) within wolf_sense steps. If one is beside it (one step or "
        "less) it bites: the person gains `bite` hurt and the wolf rests bite_pause ticks. Otherwise it steps "
        "towards them, and after chase_limit ticks of chasing without a bite it gives up and rests "
        "giveup_pause ticks. A hunting wolf with nobody within sense prowls: one step in a direction drawn "
        "from the seed, the wolf and the tick, or none. Hurt falls by heal_rest a tick for somebody resting, "
        "sleeping or warming at home and by one every heal_every ticks otherwise, and a person whose hurt "
        "reaches lethal_hurt dies. At limp_at hurt every step costs an extra tick, and a person at home "
        "does not set out on a food or water errand while the need can wait (a reason of hurt). "
        "A person sees a wolf that is within their sight (shorter at night and in a storm; a sleeper sees "
        "only their own cell). They run - one step home when their home is built, else away from the "
        "wolf, never onto a cell beside it when another is free - when a wolf they see is within alarm "
        "steps, unless a need runs out sooner. Seeing a wolf they did not see the tick before, they call "
        "out to everybody they can see who is awake, who then believe it with the date it was seen. "
        "A wolf seen by day is lying by its den and nobody runs from it; at dusk and night every wolf seen "
        "counts as hunting, since a wolf backing off for a moment looks like one stalking. Everybody knows "
        "wolves hunt at dusk and night, so by day no place counts as dangerous. "
        "At dusk and night anybody about to set out on a food or water errand puts it off when the place is "
        "within danger_radius of a wolf they believe in that was seen no more than danger_span ticks ago (a "
        "reason of dangerous); on the way, such cells cost danger_cost extra ticks to cross in the route they "
        "choose. Every put-off ends when the need is at its emergency level or has no more than the ticks "
        "to reach and finish the errand plus wolf_margin left; they then go, and say they are taking the risk."),
    needs=("beliefs", "sky"),
    levers=WOLF_LEVERS,
)


@dataclass(frozen=True)
class Wolf:
    id: str
    position: Position
    pause: int = 0                    # ticks it will neither hunt nor bite
    chase: int = 0                    # consecutive ticks spent chasing
    den: Position | None = None       # where it goes to rest; where it first appeared

    def __post_init__(self) -> None:
        if self.den is None:
            object.__setattr__(self, "den", self.position)

    def canonical(self) -> list[Any]:
        return [self.id, self.position[0], self.position[1], self.pause, self.chase, self.den[0], self.den[1]]

    @classmethod
    def from_canonical(cls, data: Any) -> "Wolf":
        if not isinstance(data, (list, tuple)) or len(data) != 7 or not isinstance(data[0], str) or not data[0]:
            raise ValueError(f"a wolf is an id, a cell, a rest, a chase count and a den, got {data!r}")
        ident, x, y, pause, chase, dx, dy = data
        if any(type(n) is not int or n < 0 for n in (x, y, pause, chase, dx, dy)):
            raise ValueError(f"a wolf needs non-negative integers, got {data!r}")
        return cls(ident, (x, y), pause, chase, (dx, dy))


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def choose_den(config: "WorldConfig", index: int, taken: set[Position]) -> Position:
    """A wolf's den: a cell on the map's edge, drawn from the seed, that nobody lives on and no source
    occupies (the first draw that qualifies, so it is fixed by the seed and the world)."""
    w, h = config.width, config.height
    first = None
    for attempt in range(64):
        side = draw(config.seed, "wolf-side", index, attempt) % 4
        along = draw(config.seed, "wolf-along", index, attempt)
        cell = ((along % w, 0), (w - 1, along % h), (along % w, h - 1), (0, along % h))[side]
        first = first or cell
        if cell not in taken:
            return cell
    return first


def spawn(config: "WorldConfig", taken: set[Position] = frozenset()) -> tuple[Wolf, ...]:
    """The wolves as they arrive, each at its own den. `taken` are cells somebody lives on or a source occupies."""
    wolves: list[Wolf] = []
    used = set(taken)
    for index in range(config.lever("wolves")):
        den = choose_den(config, index, used)
        used.add(den)
        wolves.append(Wolf(f"w{index + 1}", den))
    return tuple(wolves)


def _wander(config: "WorldConfig", wolf: Wolf, tick: int) -> Position:
    heading = draw(config.seed, "wolf", wolf.id, tick) % 5
    dx, dy = ((0, 0), (0, -1), (1, 0), (0, 1), (-1, 0))[heading]
    x, y = wolf.position
    return (min(config.width - 1, max(0, x + dx)), min(config.height - 1, max(0, y + dy)))


def _toward(origin: Position, target: Position) -> Position:
    """One step along the longer axis, x on ties; nowhere when already there."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return origin
    if abs(dx) >= abs(dy):
        return (origin[0] + (1 if dx > 0 else -1), origin[1])
    return (origin[0], origin[1] + (1 if dy > 0 else -1))


def hunting_hours(sky: "Sky | None") -> bool:
    return sky is not None and sky.phase in ("dusk", "night")


def is_active(wolf: Wolf, sky: "Sky | None") -> bool:
    """Whether a wolf looks dangerous: by day one lying by its den plainly is not, but at dusk and night
    nobody can tell a wolf that is stalking from one that has backed off for a moment."""
    return hunting_hours(sky)


def advance_wolves(config: "WorldConfig", tick: int, wolves: tuple[Wolf, ...], positions: Mapping[str, Position],
                   living: set[str], covered: set[Position], sky: "Sky | None",
                   taken: set[Position] = frozenset()) -> tuple[tuple[Wolf, ...], dict[str, int]]:
    """The wolves after one tick, and the hurt they did.

    `tick` is the tick being completed, `positions` is where everybody stands once they have moved,
    `covered` the cells under a finished shelter, `taken` the cells a new wolf may not make its den.
    Returns the wolves and, per bitten person, the hurt added."""
    if not wolves:
        return (spawn(config, taken) if tick == config.lever("wolf_arrival") else ()), {}
    sense = config.lever("wolf_sense")
    prey = {actor: positions[actor] for actor in sorted(living) if positions[actor] not in covered}
    hunting = hunting_hours(sky)
    out: list[Wolf] = []
    bites: dict[str, int] = {}
    for wolf in wolves:
        if wolf.pause > 0 or not hunting:
            out.append(replace(wolf, position=_toward(wolf.position, wolf.den), pause=max(0, wolf.pause - 1), chase=0))
            continue
        near = [(manhattan(cell, wolf.position), actor) for actor, cell in prey.items()
                if manhattan(cell, wolf.position) <= sense]
        if not near:
            out.append(replace(wolf, position=_wander(config, wolf, tick), chase=0))
            continue
        gap, target = min(near)
        if gap <= 1:
            bites[target] = bites.get(target, 0) + config.lever("bite")
            out.append(replace(wolf, pause=config.lever("bite_pause"), chase=0))
        elif wolf.chase + 1 > config.lever("chase_limit"):
            out.append(replace(wolf, pause=config.lever("giveup_pause"), chase=0))
        else:
            out.append(replace(wolf, position=_toward(wolf.position, prey[target]), chase=wolf.chase + 1))
    return tuple(out), bites


def mend(hurt: Mapping[str, int], living: set[str], resting: set[str], tick: int,
         config: "WorldConfig") -> dict[str, int]:
    """Hurt after a tick's healing: faster for those resting at home, one point every heal_every ticks for the rest."""
    out: dict[str, int] = {}
    for actor, level in hurt.items():
        if actor in living:
            level = max(0, level - (config.lever("heal_rest") if actor in resting
                                    else 1 if tick % config.lever("heal_every") == 0 else 0))
        if level > 0:
            out[actor] = level                 # the dead keep what they died of
    return out


def danger_cells(beliefs: tuple["Belief", ...], seen_now: tuple[tuple[str, Position], ...], now: int,
                 config: "WorldConfig", sky: "Sky | None") -> frozenset[Position]:
    """Cells within danger_radius of a wolf somebody sees now or believes in that was seen no more than
    danger_span ticks ago, but only while wolves hunt: everybody knows they are quiet by day. Only what this
    person saw or was told: the wolves themselves are not consulted."""
    if not hunting_hours(sky):
        return frozenset()
    radius, span = config.lever("danger_radius"), config.lever("danger_span")
    centres = {cell for _, cell in seen_now}
    centres |= {(b[2], b[3]) for b in beliefs if b[0] == "wolf" and now - b[4] <= span}
    return frozenset((x, y) for cx, cy in centres
                     for x in range(max(0, cx - radius), min(config.width, cx + radius + 1))
                     for y in range(max(0, cy - radius), min(config.height, cy + radius + 1)))
