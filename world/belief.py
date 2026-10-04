"""What a person believes about the world: dated, attributed, and allowed to fade.

A belief is one remembered fact: what kind of thing, which one, where it was, when it
was seen, when this person learned of it and who told them (nobody, for a sighting of
their own). Hearsay keeps the date of the original sighting, so a rumour does not get
younger by being repeated. Beliefs fade: one older than `memory_span` ticks is dropped,
and only the `memory_slots` most recently seen are kept.

Nothing here looks at the world. It files what it is given, and the rules that give it
things (sight, being told) are in `observe` and `process`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

Belief = tuple[str, str, int, int, int, int, str]     # kind, subject, x, y, seen, learned, via
KINDS = ("wolf", "home", "death", "well", "empty")                                     # what can be believed; each phase that adds a thing adds a kind

BELIEFS = Feature(
    name="beliefs",
    summary="People remember what they have seen and been told, with its age and who said so, and forget it in time.",
    rule=(
        "A belief is a kind of thing (a wolf, somebody's home, a grave, an emptied grave or a well), which one, the cell it was at, the tick it was seen, "
        "the tick this person learned of it and who told them (nobody for their own sighting). Somebody "
        "who sees a wolf believes it; somebody told about one believes it with the original sighting tick, "
        "so repeating a rumour never makes it fresher. For the same thing the later sighting replaces the "
        "earlier, and on a tie their own sight replaces hearsay. A belief older than memory_span ticks is "
        "forgotten, and only the memory_slots most recently seen are kept. Confidence is not stored: it is "
        "100 less 100 * age / memory_span, three quarters of that for hearsay."),
    levers=(("memory_span", 240), ("memory_slots", 10)),
    tables={"belief_kinds": list(KINDS)},
)


def age(belief: Belief, now: int) -> int:
    """Ticks since it was seen, whoever saw it."""
    return now - belief[4]


def confidence(belief: Belief, now: int, memory_span: int) -> int:
    """0 to 100: how much weight the belief deserves. Derived, never stored."""
    fresh = max(0, 100 - 100 * age(belief, now) // memory_span)
    return fresh if not belief[6] else fresh * 3 // 4


def file_beliefs(held: tuple[Belief, ...], incoming: tuple[Belief, ...], now: int,
                 config: "WorldConfig") -> tuple[Belief, ...]:
    """The beliefs held after taking in `incoming` and forgetting what has faded.

    The same thing is one belief: the later sighting wins, and on the same sighting the one
    seen first-hand (nobody told them) wins."""
    span, slots = config.lever("memory_span"), config.lever("memory_slots")
    kept: dict[tuple[str, str], Belief] = {}
    for belief in held + incoming:
        key = (belief[0], belief[1])
        current = kept.get(key)
        if current is None or (belief[4], not belief[6]) > (current[4], not current[6]):
            kept[key] = belief
    # a death is dated by the day it happened, but is remembered from the day it was learned of
    live = [b for b in kept.values() if now - (b[5] if b[0] == "death" else b[4]) <= span]
    live.sort(key=lambda b: (-b[4], b[0], b[1]))
    return tuple(sorted(live[:slots], key=lambda b: (b[0], b[1])))


def check_belief(owner: str, entry: Any, roster: set[str], tick: int) -> Belief:
    """One belief from a saved run, checked strictly."""
    if not isinstance(entry, (list, tuple)) or len(entry) != 7:
        raise ValueError(f"{owner!r} has a belief that is not kind, subject, x, y, seen, learned, via: {entry!r}")
    kind, subject, x, y, seen, learned, via = entry
    if kind not in KINDS or not isinstance(subject, str) or not subject:
        raise ValueError(f"{owner!r} believes in an unknown kind of thing: {entry!r}")
    if any(type(n) is not int for n in (x, y, seen, learned)) or x < 0 or y < 0:
        raise ValueError(f"{owner!r} has a belief with a bad place or date: {entry!r}")
    if not 0 <= seen <= learned <= tick:
        raise ValueError(f"{owner!r} has a belief seen or learned out of order: {entry!r}")
    if not isinstance(via, str) or (via and (via not in roster or via == owner)):
        raise ValueError(f"{owner!r} has a belief told by somebody who is not another known person: {entry!r}")
    return (kind, subject, x, y, seen, learned, via)


def advance_beliefs(previous: Any, current: Any, decisions: Any, observations: Any,
                    config: "WorldConfig") -> dict[str, tuple[Belief, ...]]:
    """Everybody's beliefs after one tick: what they saw themselves, what they were told, less what has faded.

    `previous` and `current` are the overlays either side of the tick. A sighting is dated to the tick the
    person saw it; something they were told keeps the date it was first seen and records the teller and the
    tick of telling. Only a listener who is alive afterwards, and whom the speaker could see, is told."""
    seen_at = previous.tick
    told: dict[str, list[Belief]] = {}
    friendly = config.on("bonds")
    for speaker in sorted(decisions):
        decision = decisions[speaker]
        for listener in getattr(decision, "told_to", ()):
            if getattr(decision, "kind", "") == "chat":
                # a quiet word is heard only by somebody who chose to talk back
                answer = decisions.get(listener)
                if answer is None or getattr(answer, "kind", "") != "chat" or getattr(answer, "target", None) != speaker:
                    continue
            if friendly:
                from world.society import trust_in
                if trust_in(previous.persona.bonds.get(listener, ()), speaker) < config.lever("believe_at"):
                    continue                              # they do not believe what this person says
            for kind, subject, x, y, seen in getattr(decision, "told", ()):
                told.setdefault(listener, []).append((kind, subject, x, y, seen, seen_at, speaker))
    out: dict[str, tuple[Belief, ...]] = {}
    for actor in current.living:
        view = observations.get(actor)
        sighted = tuple(("wolf", wolf, cell[0], cell[1], seen_at, seen_at, "")
                        for wolf, cell in (view.wolves_seen if view is not None else ()))
        sighted += tuple(("death", dead, x, y, tick, seen_at, "")
                         for dead, x, y, tick, *_ in (getattr(view, "graves", ()) if view is not None else ()))
        sighted += tuple(("empty", dead, x, y, seen_at, seen_at, "")                     # a grave seen with nothing left in it
                         for dead, x, y, _, estate, _, held in (getattr(view, "graves", ()) if view is not None else ()) if not held)
        sighted += tuple(("well", owner, x, y, seen_at, seen_at, "")
                         for owner, x, y in (getattr(view, "wells_seen", ()) if view is not None else ()))
        filed = file_beliefs(previous.persona.beliefs.get(actor, ()), sighted + tuple(told.get(actor, ())),
                             current.tick, config)
        if filed:
            out[actor] = filed
    return out
