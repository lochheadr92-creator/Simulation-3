"""Relationships: who knows whom, how well, whether they trust each other, and what they hold against each other.

A bond is one person's view of one other: how friendly they are (`bond`), how far they trust them,
a grudge (with what it is for and when it was last fed), when they last dealt with each other and in
what tone. Nobody is a stranger by default: no bond means no dealings yet.

Everything here is grounded in something the run recorded. A conversation needs both people to have
chosen it, face to face. A grudge starts when somebody who was starving saw another carrying spare
food and was not helped, and the other had seen them starving. A gift softens a grudge. Time fades one.
Loneliness is a need nobody dies of: it rises while nobody is in view and falls with talk.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_CLAIM, OP_TRANSFER
from kernel.state import actor_account
from world.feature import Feature
from world.traits import GENEROSITY, SOCIABILITY

if TYPE_CHECKING:
    from world.config import WorldConfig

Bond = tuple[str, int, int, int, int, str, int, str]     # other, bond, trust, grudge, last, why, grieved, tone

CHAT, GO_VISIT, CONFRONT = "chat", "go_visit", "confront"
GRIEVANCES = {"kept_food": "kept food while I was starving", "beat_to_it": "got the food or water I was after",
              "quarrel": "we quarrelled"}
TONES = ("", "greeting", "warm", "quarrel", "apology", "gift")
NEUTRAL_TRUST = 50

SOCIETY_LEVERS = (("talk_range", 1), ("chat_len", 4), ("chat_gain", 3), ("lonely_every", 5), ("chat_at", 4),
                  ("lonely_at", 12), ("lonely_max", 60), ("chat_relief", 2), ("friend_at", 20), ("believe_at", 25),
                  ("grudge_gain", 10), ("grudge_at", 10), ("grudge_fade", 10), ("apology_relief", 12),
                  ("quarrel_cost", 6), ("grievance_gap", 10), ("retry_after", 6), ("told_per_chat", 3),
                  ("greet_every", 8), ("greet_gain", 1), ("greet_relief", 0))

SOCIETY = Feature(
    name="bonds",
    summary="People talk, become friends, share what they know, fall out and make it up.",
    rule=(
        "Anybody awake who has somebody awake within talk_range, whom they do not resent and have not "
        "dealt with in the last greet_every ticks, greets them; a greeting costs no tick. When two greet "
        "each other each bond rises by greet_gain, and each one's loneliness falls by greet_relief. "
        "Two people in each other's reach (talk_range) who both choose to talk to each other talk for "
        "chat_len ticks. Each tick of it lowers each one's loneliness by chat_relief; loneliness rises by 1 "
        "every lonely_every ticks, never above lonely_max, and nobody dies of it. Somebody idle and awake who "
        "is lonely to chat_at (half of it is enough to talk back, and to carry on once started) talks to "
        "the best liked person within talk_range whom they do not resent and did not try or talk to in the "
        "last retry_after ticks. Somebody lonely to lonely_at, lowered a point for every 5 that "
        "sociability is over 50, with nobody in reach walks to the best liked such person in view; with "
        "nobody in view, in daylight and a fit state, to the home of the friend they know of. Talking, each says to the "
        "other what they know of wolves that was seen lately and where they live, up to told_per_chat "
        "things, with the dates they were first seen; a listener believes it only when they trust the "
        "speaker at believe_at or better. A conversation adds chat_gain to both bonds (one more when both "
        "are sociable) and one to trust. Somebody idle who holds a grudge of grudge_at or more against a "
        "person in reach, and has not had it out with them for 3 * retry_after ticks, confronts them: "
        "they say so, once, to whoever is awake. When the one resented is generous enough (generosity 40 "
        "or more) and holds no grudge of their own they apologise, the grudge falls by apology_relief and "
        "the bond recovers; otherwise they quarrel, both bonds fall by quarrel_cost, the other now holds "
        "a grudge of grudge_gain too, and nobody starts a talk with somebody they resent. Two things "
        "start a grudge, each adding grudge_gain, no more than once every grievance_gap "
        "ticks for the same person, and each taking 5 off trust and 2 off the bond: somebody starving who "
        "saw another in view carrying two or more spare food units, who had seen them starving and was free "
        "to help, and did not offer; and somebody whose claim on a source was refused for lack of stock on "
        "the tick another person in view had a claim on it accepted. Receiving a unit of food "
        "adds 4 to the bond and 5 to trust and takes 6 off a grudge. A grudge fades by one every "
        "grudge_fade ticks. Friends (bond friend_at or more) come first when somebody chooses whom to "
        "help, and a stingy person gives to a friend as readily as to their child."),
    needs=("beliefs",),
    levers=SOCIETY_LEVERS,
    tables={"grievances": GRIEVANCES, "tones": list(TONES)},
)


def find(bonds: tuple[Bond, ...], other: str) -> Bond | None:
    return next((b for b in bonds if b[0] == other), None)


def grudge_of(bonds: tuple[Bond, ...], other: str) -> int:
    entry = find(bonds, other)
    return entry[3] if entry else 0


def bond_with(bonds: tuple[Bond, ...], other: str) -> int:
    entry = find(bonds, other)
    return entry[1] if entry else 0


def trust_in(bonds: tuple[Bond, ...], other: str) -> int:
    entry = find(bonds, other)
    return entry[2] if entry else NEUTRAL_TRUST


def is_friend(bonds: tuple[Bond, ...], other: str, config: "WorldConfig") -> bool:
    return bond_with(bonds, other) >= config.lever("friend_at")


def resents(bonds: tuple[Bond, ...], other: str, config: "WorldConfig") -> bool:
    return grudge_of(bonds, other) >= config.lever("grudge_at")


def put(bonds: tuple[Bond, ...], other: str, **changes: Any) -> tuple[Bond, ...]:
    """The bonds with one entry changed (created neutral when there was none), kept in a fixed order.
    Levels stay between 0 and 100."""
    current = find(bonds, other) or (other, 0, NEUTRAL_TRUST, 0, 0, "", 0, "")
    names = ("bond", "trust", "grudge", "last", "why", "grieved", "tone")
    values = dict(zip(names, current[1:]))
    for name, value in changes.items():
        if name not in values:
            raise KeyError(name)
        values[name] = min(100, max(0, value)) if name in ("bond", "trust", "grudge") else value
    if not values["grudge"]:
        values["why"], values["grieved"] = "", 0
    entry: Bond = (other, *(values[n] for n in names))     # type: ignore[assignment]
    return tuple(sorted([b for b in bonds if b[0] != other] + [entry]))


def check_bond(owner: str, entry: Any, roster: set[str], tick: int) -> Bond:
    """One bond from a saved run, checked strictly."""
    if not isinstance(entry, (list, tuple)) or len(entry) != 8:
        raise ValueError(f"{owner!r} has a bond that is not other, bond, trust, grudge, last, why, grieved, tone: {entry!r}")
    other, bond, trust, grudge, last, why, grieved, tone = entry
    if not isinstance(other, str) or other not in roster or other == owner:
        raise ValueError(f"{owner!r} has a bond with somebody who is not another known person: {entry!r}")
    if any(type(n) is not int for n in (bond, trust, grudge, last, grieved)) or not (
            0 <= bond <= 100 and 0 <= trust <= 100 and 0 <= grudge <= 100 and 0 <= last <= tick and 0 <= grieved <= tick):
        raise ValueError(f"{owner!r} has a bond with levels or dates out of range: {entry!r}")
    if why and why not in GRIEVANCES or (not grudge and (why or grieved)) or (grudge and not why):
        raise ValueError(f"{owner!r} has a grudge without a cause, or a cause without a grudge: {entry!r}")
    if tone not in TONES:
        raise ValueError(f"{owner!r} has a bond with an unknown tone: {entry!r}")
    return (other, bond, trust, grudge, last, why, grieved, tone)


IDLE_LOOK = frozenset({"rest", "build", "chat", "confront", "warm", "sleep", "collapse"})     # what standing about looks like
APOLOGY_GENEROSITY = 40          # how generous somebody must be to apologise to a person who resents them
IDLE_KINDS = frozenset({"rest", "home", "build"})        # free to help: nothing of their own was calling


def _near(a: tuple[int, int], b: tuple[int, int], reach: int) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= reach


def _source_of(decision: Any) -> str:
    """The source a claim aimed at: its recorded target, or the only source of its kind."""
    from world.config import FOOD_SOURCE, WATER_SOURCE
    return decision.target or (WATER_SOURCE if decision.kind == "draw" else FOOD_SOURCE)


def advance_society(previous: Any, current: Any, decisions: Mapping[str, Any], observations: Mapping[str, Any],
                    record: Any, config: "WorldConfig") -> tuple[dict[str, tuple[Bond, ...]], dict[str, int],
                                                                  dict[str, tuple[str, int]],
                                                                  list[tuple[str, str, str, int, int]]]:
    """Everybody's bonds, loneliness and conversation after one tick, and the attempts that came to nothing.

    `previous` and `current` are the overlays either side of the tick. Only what the run recorded counts:
    the choices people made, what they observed, and the outcomes the kernel settled."""
    tick = previous.tick
    persona = previous.persona
    living = set(current.living)
    bonds = {actor: persona.bonds.get(actor, ()) for actor in current.roster}
    lonely = {actor: persona.lonely.get(actor, 0) for actor in living}
    traits = persona.traits
    failed: list[tuple[str, str, str, int, int]] = []

    def trait(actor: str, index: int) -> int:
        return traits[actor][index] if actor in traits else 50

    gain, gap = config.lever("grudge_gain"), config.lever("grievance_gap")

    def grieve(victim: str, culprit: str, why: str) -> None:
        entry = find(bonds[victim], culprit)
        if entry is not None and entry[3] and tick - entry[6] < gap:
            return
        bonds[victim] = put(bonds[victim], culprit, grudge=(entry[3] if entry else 0) + gain,
                            why=entry[5] if entry and entry[3] else why, grieved=tick,
                            trust=(entry[2] if entry else NEUTRAL_TRUST) - 5, bond=(entry[1] if entry else 0) - 2)

    # a unit handed over softens whatever the one who received it held against the giver
    people = {actor_account(actor): actor for actor in living}
    for outcome in record.outcomes:
        if not outcome.accepted or outcome.operation != OP_TRANSFER or outcome.actor not in living:
            continue
        for effect in outcome.effects:
            receiver = people.get(effect.account)
            if effect.delta > 0 and receiver is not None and receiver != outcome.actor:
                held = find(bonds[receiver], outcome.actor)
                bonds[receiver] = put(bonds[receiver], outcome.actor, bond=(held[1] if held else 0) + 4,
                                      trust=(held[2] if held else NEUTRAL_TRUST) + 5,
                                      grudge=(held[3] if held else 0) - 6, last=tick, tone="gift")
                given = find(bonds[outcome.actor], receiver)
                bonds[outcome.actor] = put(bonds[outcome.actor], receiver, bond=(given[1] if given else 0) + 1, last=tick,
                                           tone="gift")

    # a claim refused for lack of stock on the tick somebody they could see had one accepted
    won: dict[str, list[str]] = {}
    lost: list[tuple[str, str]] = []
    for outcome in record.outcomes:
        decision = decisions.get(outcome.actor)
        if outcome.operation != OP_CLAIM or decision is None:
            continue
        if outcome.accepted:
            won.setdefault(_source_of(decision), []).append(outcome.actor)
        elif outcome.reason == "denied_insufficient_source" and outcome.actor in living:
            lost.append((outcome.actor, _source_of(decision)))
    for loser, source in lost:
        view = observations.get(loser)
        seen = {s.actor for s in view.others} if view is not None else set()
        for winner in won.get(source, []):
            if winner in seen and winner in living and winner != loser:
                grieve(loser, winner, "beat_to_it")

    # somebody starving who saw another carrying spare food, who had seen them starving, free, and did not offer
    for hungry in sorted(living):
        view = observations.get(hungry)
        if view is None or view.hunger < config.emergency_at:
            continue
        for seen in view.others:
            other = seen.actor
            theirs, decision = observations.get(other), decisions.get(other)
            if (seen.food < 2 or other not in living or theirs is None or decision is None
                    or theirs.hunger >= config.emergency_at or decision.kind not in IDLE_KINDS
                    or not any(s.actor == hungry and s.starving for s in theirs.others)):
                continue
            grieve(hungry, other, "kept_food")

    reach, grudge_at = config.lever("talk_range"), config.lever("grudge_at")
    chat_gain, cost, relief = config.lever("chat_gain"), config.lever("quarrel_cost"), config.lever("apology_relief")

    # a greeting is mutual: both said it, within reach, both awake
    greeted = sorted({tuple(sorted((a, b))) for a in decisions for b in getattr(decisions[a], "greeted", ())
                      if a in living and b in living and a in getattr(decisions.get(b), "greeted", ())
                      and a not in persona.asleep and b not in persona.asleep
                      and _near(previous.positions[a], previous.positions[b], reach)})
    gap_ticks, greet_gain = config.lever("greet_every"), config.lever("greet_gain")
    for a, b in greeted:
        for one, other in ((a, b), (b, a)):
            held = find(bonds[one], other)
            if held is not None and tick - held[4] < gap_ticks:
                continue
            bonds[one] = put(bonds[one], other, bond=(held[1] if held else 0) + greet_gain,
                             trust=held[2] if held else NEUTRAL_TRUST, last=tick, tone="greeting")
            lonely[one] = max(0, lonely[one] - config.lever("greet_relief"))

    # having it out: the aggrieved says so to somebody awake in reach, who answers by what sort of person they are
    for x in sorted(decisions):
        for y in getattr(decisions[x], "confronted", ()):
            if (x not in living or y not in living or y in persona.asleep or x in persona.asleep
                    or not _near(previous.positions[x], previous.positions[y], reach)):
                continue
            held = find(bonds[x], y)
            if held is None or held[3] < grudge_at:
                continue
            failed.append((x, CONFRONT, y, tick, 1))
            if trait(y, GENEROSITY) >= APOLOGY_GENEROSITY and grudge_of(bonds[y], x) < grudge_at:
                bonds[x] = put(bonds[x], y, grudge=held[3] - relief, bond=held[1] + 2, trust=held[2] + 2,
                               last=tick, tone="apology")
                bonds[y] = put(bonds[y], x, last=tick, tone="apology")
            else:
                bonds[x] = put(bonds[x], y, bond=held[1] - cost, grudge=held[3] + 2, grieved=tick, last=tick, tone="quarrel")
                theirs = find(bonds[y], x)
                bonds[y] = put(bonds[y], x, bond=(theirs[1] if theirs else 0) - cost,
                               grudge=max(theirs[3] if theirs else 0, gain),
                               why=theirs[5] if theirs and theirs[3] else "quarrel", grieved=tick, last=tick, tone="quarrel")

    # talk: both must have chosen it, face to face, and be awake and alive
    def chat_target(actor: str) -> str | None:
        decision = decisions.get(actor)
        return decision.target if decision is not None and decision.kind == CHAT else None

    pairs = sorted({tuple(sorted((a, b))) for a in decisions
                    if (b := chat_target(a)) is not None and chat_target(b) == a and a in living and b in living
                    and a not in persona.asleep and b not in persona.asleep
                    and _near(previous.positions[a], previous.positions[b], reach)})
    for a in sorted(decisions):
        b = chat_target(a)
        if b is not None and tuple(sorted((a, b))) not in pairs and a in living:
            failed.append((a, CHAT, b, tick, 0))              # they talked to somebody who did not talk back
    for a, b in pairs:
        both_sociable = trait(a, SOCIABILITY) >= 50 and trait(b, SOCIABILITY) >= 50
        for one, other in ((a, b), (b, a)):
            held = find(bonds[one], other)
            bonds[one] = put(bonds[one], other, bond=(held[1] if held else 0) + chat_gain + int(both_sociable),
                             trust=(held[2] if held else NEUTRAL_TRUST) + 1, last=tick, tone="warm")
    talked = {actor for pair in pairs for actor in pair}
    talking: dict[str, tuple[str, int]] = {}
    for a, b in pairs:
        for one, other in ((a, b), (b, a)):
            before = persona.talking.get(one)
            talking[one] = (other, before[1] if before is not None and before[0] == other else tick)

    # loneliness rises with the time since they last talked and falls with talk
    every, top = config.lever("lonely_every"), config.lever("lonely_max")
    for actor in sorted(living):
        if actor in talked:
            lonely[actor] = max(0, lonely[actor] - config.lever("chat_relief"))
        elif (tick + int(actor[1:])) % every == 0:
            lonely[actor] = min(top, lonely[actor] + 1)
    # time fades a grudge
    if (tick + 1) % config.lever("grudge_fade") == 0:
        for actor in bonds:
            for entry in bonds[actor]:
                if entry[3]:
                    bonds[actor] = put(bonds[actor], entry[0], grudge=entry[3] - 1)
    out = {actor: entries for actor, entries in bonds.items() if entries and actor in living}
    return out, {actor: level for actor, level in lonely.items() if level}, talking, failed
