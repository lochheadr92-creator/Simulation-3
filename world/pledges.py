"""Asking for help, answering, and keeping a word.

One person asks another they can see for something: water, food, wood, a hand with their shelter, or
news of the wolf. The other answers a tick later, if the asker is still in sight, yes or no and why. A yes
to a unit of something is a promise backed by the kernel: the units are reserved inside the helper's own
account (a native reservation), so they cannot be eaten or given away meanwhile, and they are handed
over by completing that reservation or given back by cancelling it. A promise ends one of five ways: it
is kept, declined, expires, fails (the helper had to break it) or is interrupted (a death, a flight).
Each ending is recorded with its reason on the tick it happens.

This module owns the stored pledges and what happens to them each tick. What people decide about them is
in world/decide.py; what each of them can see of them is in world/observe.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_COMPLETE, OP_RESERVE, OP_TRANSFER
from kernel.state import actor_account
from world.feature import Feature
from world.materials import WORK_PER_WOOD

if TYPE_CHECKING:
    from world.config import WorldConfig

HELP, GO_HELP = "help", "go_help"
KINDS = ("water", "food", "wood", "build", "repair", "news")
RESOURCES = {"food": None, "water": "water", "wood": "wood"}      # what a kind hands over, by kernel resource name
STATES = ("asked", "promised")
OUTCOMES = ("kept", "declined", "expired", "failed", "interrupted")
REASONS = {
    "handed_over": "handed it over", "work_done": "the work was done", "told": "told them what they knew",
    "not_needed": "was not needed in the end",
    "nothing_to_spare": "had nothing to spare", "need_it_myself": "needed it for themselves",
    "busy": "was already busy with something", "no_trust": "did not trust them", "unwilling": "would rather not",
    "unfit": "was in no state or place to", "too_far": "was too far away", "nothing_known": "knew nothing to tell",
    "gave_it_up": "had to break the promise: needed it", "could_not_hand_over": "could not hand it over",
    "not_there": "got there and found nobody", "no_answer": "nobody answered", "ran_out_of_time": "took too long",
    "helper_died": "the one helping died", "asker_died": "the one who asked died",
    "ran_from_wolf": "ran from a wolf", "collapsed": "collapsed from tiredness",
}
# the reasons a person who says no may give, and what a refusal to somebody in need is held against them for
DECLINES = ("nothing_to_spare", "need_it_myself", "busy", "no_trust", "unwilling", "unfit", "too_far", "nothing_known")
BLAMED = frozenset({"unwilling"})

PLEDGE_LEVERS = (("ask_wait", 3), ("promise_span", 40), ("place_wait", 5), ("ask_again", 12), ("accept_trust", 20),
                 ("help_margin", 4), ("help_range", 5), ("build_ask", 4), ("news_after", 10), ("host_at", 3))

PLEDGES = Feature(
    name="pledges",
    summary="People ask each other for water, food, wood, help building and news, promise, and keep or break their word.",
    rule=(
        "Somebody at home, with no storm out, who cannot go for water or food because the weather, an injury "
        "or a wolf holds them back, who has no wood for the shelter they are building, who is building it with "
        "at least six ticks of work to go, or who is staying in on a rumour of a wolf that is news_after ticks "
        "old or more, may ask one person they can see: friends first, then the nearest; never somebody asleep, "
        "somebody they resent, somebody they asked in the last ask_again ticks, or somebody more than help_range "
        "steps away. They ask for one unit of what they lack (nobody is asked for water, food or wood they are "
        "not seen carrying, except that anybody not visibly busy may be asked to fetch wood), for build_ask ticks "
        "of work (fewer when less is left), or for news of the wolf. Speech costs no tick and nobody has two open "
        "requests. The one asked hears it only while the asker is in sight and answers on the next tick. They say "
        "no, with a reason, when they do not trust the asker (trust below accept_trust, or a grudge), are stingy "
        "and the asker is neither a friend nor their child, already hold a promise, are hurt, out in a storm, "
        "would be walking into a wolf they know of or into more cold than they can stand, have nothing to spare "
        "(wood needed for their own shelter is not spare), are more than help_range steps away, or could not "
        "make the walk with help_margin ticks of their own need to spare. Otherwise they say yes. A yes to "
        "water, food or wood reserves the unit in their own account (a native kernel reservation), so they "
        "cannot eat or give it away, until it is handed over by completing the reservation. Somebody with a "
        "finished shelter and no wood promises to fetch some from the grove and hand it over. A builder who has "
        "asked for wood waits at home for it. A yes to building help is work: the helper goes to the asker's "
        "door and, whenever the asker builds while they stand there, adds one tick of work to the asker's, "
        "until the work asked for is done or the shelter stands, and never a tick that would start a group "
        "of four the asker has not paid wood for. A yes to news is the freshest wolf news they hold, told with "
        "its date, believed only by a listener who trusts them. A promise lasts promise_span ticks; a helper "
        "who reaches the asker's door and does not see them for place_wait ticks gives up. A helper whose own "
        "water or food reaches its emergency with none free gives the reservation up and says so; one who runs "
        "from a wolf, collapses or dies, or whose asker dies, has the promise end and the reservation "
        "returned. A request nobody answers within ask_wait ticks lapses; a shelter finished before the helper "
        "lifted a hand ends the promise as not needed. A refusal from a stingy person to somebody in a "
        "hunger or thirst emergency, and a promise broken or run out of time that the asker had heard, are "
        "held against the one who said no or broke their word. A host at home with host_at or more food hands "
        "a unit to somebody they know, not resented, within a step, who carries none."),
    needs=("bonds",),
    levers=PLEDGE_LEVERS,
    tables={"kinds": list(KINDS), "outcomes": list(OUTCOMES), "reasons": REASONS},
)

Position = tuple[int, int]


@dataclass(frozen=True)
class Pledge:
    kind: str
    asker: str
    helper: str
    state: str                  # asked: waiting for an answer; promised: the helper said yes
    made: int                   # the tick it was asked
    due: int                    # when it lapses
    amount: int                 # units, ticks of work, or 1 for news
    place: Position             # where the asker said they would be
    held: int = 0               # units reserved inside the helper's account
    action: str = ""            # the kernel's name for that reservation
    heard: int = 0              # 1 once the asker has heard the helper say yes
    arrived: int = 0            # the tick the helper reached the place, or 0
    done: int = 0               # units handed over or ticks of work given

    @property
    def id(self) -> str:
        return f"{self.asker}@{self.made}"

    def canonical(self) -> list[Any]:
        return [self.kind, self.asker, self.helper, self.state, self.made, self.due, self.amount,
                self.place[0], self.place[1], self.held, self.action, self.heard, self.arrived, self.done]

    @classmethod
    def from_canonical(cls, data: Any) -> "Pledge":
        if not isinstance(data, (list, tuple)) or len(data) != 14:
            raise ValueError(f"a pledge is kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, "
                             f"done: {data!r}")
        kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, done = data
        return cls(kind, asker, helper, state, made, due, amount, (x, y), held, action, heard, arrived, done)


@dataclass(frozen=True)
class Closed:
    kind: str
    asker: str
    helper: str
    outcome: str
    reason: str
    tick: int

    def canonical(self) -> list[Any]:
        return [self.kind, self.asker, self.helper, self.outcome, self.reason, self.tick]

    @classmethod
    def from_canonical(cls, data: Any) -> "Closed":
        if not isinstance(data, (list, tuple)) or len(data) != 6:
            raise ValueError(f"an ended pledge is kind, asker, helper, outcome, reason, tick: {data!r}")
        return cls(*data)


@dataclass(frozen=True)
class Pledges:
    """Every request still open, what ended on the tick this describes, and reservations to hand back."""
    open: tuple[Pledge, ...] = ()
    closed: tuple[Closed, ...] = ()
    release: tuple[tuple[str, str], ...] = ()          # (helper, kernel reservation) to cancel on the next tick

    def __bool__(self) -> bool:
        return bool(self.open or self.closed or self.release)

    def check(self, roster: set[str], tick: int) -> None:
        for p in self.open:
            _check_pledge(p, roster, tick)
        for end in self.closed:
            if (end.kind not in KINDS or end.outcome not in OUTCOMES or end.reason not in REASONS
                    or end.asker not in roster or end.helper not in roster or end.asker == end.helper
                    or type(end.tick) is not int or not 0 <= end.tick <= tick):
                raise ValueError(f"an ended pledge is not valid: {end!r}")
        askers = [p.asker for p in self.open]
        promised = [p.helper for p in self.open if p.state == "promised"]
        if len(set(askers)) != len(askers):
            raise ValueError("somebody has two open requests")
        if len(set(promised)) != len(promised):
            raise ValueError("somebody has promised twice")
        for helper, action in self.release:
            if helper not in roster or not isinstance(action, str) or not action:
                raise ValueError(f"a reservation to hand back is not valid: {(helper, action)!r}")

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.open:
            out["open"] = [p.canonical() for p in self.open]
        if self.closed:
            out["closed"] = [end.canonical() for end in self.closed]
        if self.release:
            out["release"] = [list(pair) for pair in self.release]
        return out

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Pledges":
        if not isinstance(data, Mapping) or set(data) - {"open", "closed", "release"}:
            raise ValueError("canonical pledges hold open, closed and release only")
        return cls(open=tuple(Pledge.from_canonical(p) for p in data.get("open", ())),
                   closed=tuple(Closed.from_canonical(c) for c in data.get("closed", ())),
                   release=tuple(tuple(pair) for pair in data.get("release", ())))


def _check_pledge(p: Pledge, roster: set[str], tick: int) -> None:
    ints = (p.made, p.due, p.amount, p.held, p.heard, p.arrived, p.done, *p.place)
    if (p.kind not in KINDS or p.state not in STATES or p.asker not in roster or p.helper not in roster
            or p.asker == p.helper or any(type(n) is not int or n < 0 for n in ints)
            or not isinstance(p.action, str) or not p.made <= tick or p.due < p.made or p.amount < 1
            or p.heard not in (0, 1) or p.held > p.amount or p.done > p.amount):
        raise ValueError(f"a pledge is not valid: {p!r}")
    if p.state == "asked" and (p.held or p.action or p.heard or p.arrived or p.done):
        raise ValueError(f"a request nobody has answered holds, has heard, or has done nothing: {p!r}")
    if bool(p.held) != bool(p.action) or (p.held and p.kind not in RESOURCES):
        raise ValueError(f"a pledge holds units without a reservation, or the reverse: {p!r}")
    if p.state == "promised" and p.kind == "news":
        raise ValueError(f"news is answered at once and is never promised: {p!r}")


def open_for(pledges: Pledges, actor: str) -> list[Pledge]:
    return [p for p in pledges.open if actor in (p.asker, p.helper)]


def views(pledges: Pledges, actor: str, in_view: set[str]) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    """What one person knows of the requests that concern them: asked of them (only while the asker is in
    sight), promised by them, and asked by them (promised only once they have heard it)."""
    asked = tuple((p.asker, p.kind, p.amount, p.place[0], p.place[1]) for p in pledges.open
                  if p.helper == actor and p.state == "asked" and p.asker in in_view)
    owing = tuple((p.id, p.kind, p.asker, p.amount, p.place[0], p.place[1], p.due, p.held, p.action, p.arrived, p.done)
                  for p in pledges.open if p.helper == actor and p.state == "promised")
    asking = tuple((p.id, p.kind, p.helper, "promised" if p.state == "promised" and p.heard else "asked", p.made, p.due)
                   for p in pledges.open if p.asker == actor)
    return asked, owing, asking


def help_credit(previous: Any, decisions: Mapping[str, Any], owner: str, built_before: int, goal: int,
                config: "WorldConfig") -> str | None:
    """The promised helper who adds a tick of work on the tick `owner` builds, as the pledge's id.

    The helper must have started the tick at the owner's door and be helping. Their tick never carries
    the work past the finished shelter, and with wood on never starts a group of four the owner has not
    paid for (that payment is made on the owner's own tick)."""
    for p in previous.pledges.open:
        if p.kind != "build" or p.state != "promised" or p.asker != owner:
            continue
        d = decisions.get(p.helper)
        if (d is not None and d.kind == HELP and getattr(d, "keeping", None) == p.id
                and previous.positions[p.helper] == p.place and previous.alive(p.helper)
                and built_before + 1 < goal
                and (not config.wood_on or (built_before + 1) % WORK_PER_WOOD != 0)):
            return p.id
    return None


def repair_credit(previous: Any, decisions: Mapping[str, Any], owner: str) -> str | None:
    """The promised helper who stands at the owner's door while they mend their shelter, as the pledge's id."""
    for p in previous.pledges.open:
        if p.kind != "repair" or p.state != "promised" or p.asker != owner:
            continue
        d = decisions.get(p.helper)
        if (d is not None and d.kind == HELP and getattr(d, "keeping", None) == p.id
                and previous.positions[p.helper] == p.place and previous.alive(p.helper)):
            return p.id
    return None


def _near(a: Position, b: Position, reach: int) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= reach


def advance_pledges(previous: Any, decisions: Mapping[str, Any], observations: Mapping[str, Any], record: Any,
                    positions: Mapping[str, Position], died: set[str], credited: Mapping[str, int],
                    sheltered: set[Position], config: "WorldConfig") -> tuple[
                        Pledges, list[tuple[str, str, str, int, int]], list[tuple[str, str, str]]]:
    """The pledges after one tick, the requests that came to nothing for the one who asked, and the
    grievances an ending leaves behind (victim, culprit, reason).

    Only what the run recorded counts: who asked whom and was heard, what each decided, what the kernel
    settled, where everybody ended the tick."""
    from world.rest import COLLAPSE
    from world.sky import sight
    from world.wolves import FLEE
    now, then = previous.tick + 1, previous.tick
    living = set(previous.living) - died
    asleep = previous.persona.asleep
    radius = sight(config, previous.sky, config.perception_radius)
    ask_wait, span = config.lever("ask_wait"), config.lever("promise_span")
    place_wait = config.lever("place_wait")
    outcomes: dict[str, list[Any]] = {}
    for outcome in record.outcomes:
        outcomes.setdefault(outcome.actor, []).append(outcome)

    closed: list[Closed] = []
    release: list[tuple[str, str]] = []
    tried: list[tuple[str, str, str, int, int]] = []
    grievances: list[tuple[str, str, str]] = []
    keep: list[Pledge] = []

    def hears(listener: str, speaker: str) -> bool:
        """Speech is said at the start of the tick, so it is heard by whoever was in earshot then."""
        return (listener in living and speaker in living and listener not in asleep
                and _near(previous.positions[listener], previous.positions[speaker], radius))

    def end(p: Pledge, outcome: str, reason: str, handed_back: bool = False) -> None:
        closed.append(Closed(p.kind, p.asker, p.helper, outcome, reason, now))
        if p.action and outcome != "kept" and not handed_back:
            release.append((p.helper, p.action))          # the reservation goes back to the helper next tick

    def disappointed(p: Pledge, why: str) -> None:
        tried.append((p.asker, "ask", p.helper, then, 0))
        if p.asker in living and p.heard:
            grievances.append((p.asker, p.helper, why))

    for p in previous.pledges.open:
        helper_choice, asker_choice = decisions.get(p.helper), decisions.get(p.asker)
        if p.helper in died or p.asker in died:
            end(p, "interrupted", "helper_died" if p.helper in died else "asker_died")
            continue
        if p.state == "asked":
            answer = next((a for a in getattr(helper_choice, "answered", ())
                           if a[0] == p.asker and a[1] == p.kind), None)
            if answer is None:
                if now >= p.made + ask_wait:
                    end(p, "expired", "no_answer")
                    tried.append((p.asker, "ask", p.helper, then, 0))
                else:
                    keep.append(p)
                continue
            _, _, verdict, reason, held = answer
            reserved = next((o.action_id for o in outcomes.get(p.helper, ())
                             if o.operation == OP_RESERVE and o.accepted and o.action_id), "")
            if verdict != "yes":
                end(p, "declined", reason if reason in DECLINES else "unwilling")
                if hears(p.asker, p.helper):
                    tried.append((p.asker, "ask", p.helper, then, 0))
                    view = observations.get(p.asker)
                    in_need = (view is not None and p.kind in ("water", "food")
                               and (view.thirst >= config.thirst_emergency_at if p.kind == "water" and config.water_on
                                    else view.hunger >= config.emergency_at))
                    if in_need and reason in BLAMED:
                        grievances.append((p.asker, p.helper, "refused"))
            elif p.kind == "news":
                end(p, "kept", "told")
            elif held and not reserved:
                end(p, "declined", "nothing_to_spare")      # the kernel would not hold the units
                if hears(p.asker, p.helper):
                    tried.append((p.asker, "ask", p.helper, then, 0))
            else:
                keep.append(replace(p, state="promised", due=now + span, held=held, action=reserved,
                                    heard=int(hears(p.asker, p.helper))))
            continue
        # promised
        mine = outcomes.get(p.helper, [])
        if getattr(helper_choice, "gave_up", None) == p.id:
            end(p, "failed", "gave_it_up", handed_back=True)
            disappointed(p, "broke_promise")
            continue
        if helper_choice is not None and helper_choice.kind in (FLEE, COLLAPSE):
            end(p, "interrupted", "ran_from_wolf" if helper_choice.kind == FLEE else "collapsed")
            continue
        done = p.done
        if getattr(helper_choice, "keeping", None) == p.id:
            if helper_choice.kind == "offer":
                gave = 0
                for o in mine:
                    if o.operation in (OP_COMPLETE, OP_TRANSFER) and o.accepted:
                        gave += sum(e.delta for e in o.effects if e.delta > 0
                                    and e.account == actor_account(p.asker, RESOURCES[p.kind]))
                if not gave:
                    end(p, "failed", "could_not_hand_over")
                    disappointed(p, "broke_promise")
                    continue
                done += gave
            elif p.kind in ("build", "repair"):
                done += credited.get(p.id, 0)
        if p.kind in RESOURCES and done >= p.amount:
            end(p, "kept", "handed_over", handed_back=True)
            continue
        if p.kind == "repair":
            mended = next((s.a for s in previous.things.structures if s.kind == "shelter" and s.owner == p.asker), 100)
            if done >= p.amount or mended >= config.lever("repair_to"):
                if done:
                    end(p, "kept", "work_done")
                else:
                    end(p, "expired", "not_needed")
                continue
        if p.kind == "build" and (done >= p.amount or previous.homes[p.asker] in sheltered):
            if done:
                end(p, "kept", "work_done")
            else:
                end(p, "expired", "not_needed")             # the shelter stood before the helper had lifted a hand
            continue
        arrived = p.arrived or (now if positions[p.helper] == p.place else 0)
        if arrived and now - arrived >= place_wait and not _near(positions[p.helper], positions[p.asker], radius):
            end(p, "failed", "not_there")
            if hears(p.asker, p.helper):
                disappointed(p, "broke_promise")
            continue
        if now >= p.due:
            end(p, "expired", "ran_out_of_time")
            disappointed(p, "broke_promise")
            continue
        keep.append(replace(p, done=done, arrived=arrived))

    # new requests: spoken to somebody the asker could see, one at a time
    taken = {p.asker for p in keep}
    for asker in sorted(decisions):
        view = observations.get(asker)
        for helper, kind, amount in getattr(decisions[asker], "asked", ()):
            if (asker in living and helper in living and asker not in taken and kind in KINDS and amount >= 1
                    and view is not None and any(s.actor == helper for s in view.others)):
                keep.append(Pledge(kind, asker, helper, "asked", then + 1, then + 1 + ask_wait, amount,
                                   previous.positions[asker]))
                taken.add(asker)
                tried.append((asker, "ask", helper, then, 1))
    return (Pledges(open=tuple(sorted(keep, key=lambda p: (p.made, p.asker))),
                    closed=tuple(sorted(closed, key=lambda c: (c.asker, c.kind))),
                    release=tuple(sorted(release))), tried, grievances)
