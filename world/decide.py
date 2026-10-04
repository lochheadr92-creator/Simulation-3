"""Candidates and the one live selection rule.

`candidates` lists what a person could do this tick given their observation;
`decide` picks one by fixed priority (OFF) or declared integer pairs (ON).
Both are pure. The record keeps the actual scores when ON and the
eligible set beside the choice so a later reader can see what was passed over.

Priority, highest first:
  eat    hungry and holding a free unit
  claim  hungry, standing on the source, source has free stock
  wait   hungry, standing on the source, source empty (stay; hunger continues)
  yield  hungry, not emergency, off the source, source in view, crowd on the
         source >= yield_at and observed stock < crowd (stay; hunger continues)
  go     hungry, elsewhere: one step toward the source; or (trips on) holding
         no food, elsewhere, and hunger + hunger_rate * estimated travel ticks
         >= hungry_at, so a person far from food leaves in time to arrive as
         hunger reaches hungry_at. With terrain and routing on, the estimate
         uses seen and remembered rough ground; unseen ground counts as open.
          Fishing includes one casting tick: arrive and cast before hungry,
          then use the ordinary hungry claim and later eating rules.
  home   not hungry, away from home: one step toward home
  A child - anybody who has lived fewer than adult_at ticks - will not go
  more than child_leash steps from home for anything, builds nothing, and is
  nobody's partner. A parent who is free and holding food takes a unit to
  their own child, in view and carrying none, before anybody else.

  ask    hungry, holding nothing, and somebody in view is carrying food:
         ask them for it, and keep walking to the source meanwhile. Asking
         is speech and costs no tick; the walk happens either way
  agree  somebody asked last tick, nothing of one's own is calling, and
         there is a unit in hand and no errand already running: take it on.
         Anyone who cannot, or is busy with their own need, simply does not
         answer, and the asking lapses - saying no is not an act either
  offer  no need calling, holding a spare unit, and somebody visibly
         starving is alongside: hand them one unit through the kernel
  go_offer  the same, but they are further off: one step towards them
  Water care (water_care_on, off by default): a parent with nothing of their own
         calling who holds water and sees their dependent child in a visible
         thirst emergency hands over one unit; a parent who holds none and has
         a dependent child whose home is further from water than child_leash
         walks to water and draws, then brings it home. A child born out of
         reach of water cannot fetch it, and nobody else notices them.
  build  no need calling, at home, no shelter there yet: spend the tick
         putting one up. It is permanent, and it slows hunger and thirst
         for whoever stands on it afterwards
  rest   not hungry, at home
A dead person has no candidates and decides nothing.

Water adds drink, draw, wait_water and go_water; warmth (2026-09-27) adds warm
and go_shelter, where shelter is the person's own home cell. When more than one
need calls, `_decide_needs` serves the one nearest its lethal level.

CLAIM requires the source to be in view. Standing on the source is
distance 0, so the requirement is always met there; it is stated so the
rule stays honest if the radius changes. The claim amount is
min(claim_amount, observed stock). If stock is not observed the person
cannot be at the source; that is asserted, not defaulted.

YIELD uses only the observation: crowd is the number of seen others whose
position equals the source cell. Dead people are neither seen nor counted.
Emergency never yields. A yield proposes nothing and does not step.

With several sources of a kind, "the source" is the one the observation
targets (world/observe.py `target_source`), and the decision records it as
`target` on every claim, wait, yield, go, draw, wait_water and go_water; a
claim or draw takes from that source. With one source of a kind no target is
recorded, so those decisions are exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from heapq import heappop, heappush
from math import inf as INF
from typing import Any

from world.config import WATER, WorldConfig
from world.observe import Observation
from world.overlay import Position
from world.storage import spare_for_store, store_id, start_provisioning
from world.housing import GO_SETTLE, SETTLE, GO_RELOCATE, RELOCATE, choose_site, choose_relocation
from world.fishing import FISH_SOURCE, FISH
from world.materials import GATHER_WOOD, GO_WOOD, WAIT_WOOD, WOOD_PACK, wood_cost, remaining_wood
from world.explain import (DANGEROUS, FAILED_BEFORE, HURT, LESS_URGENT, TOO_LATE, UNAVAILABLE, UNWILLING,
                           WEATHER, rejection)
from world.rest import COLLAPSE, GO_SLEEP, SLEEP, fatigue_slack, tired_threshold
from world.traits import (FISHING, GATHERING, build_goal, caution_ticks, generous, skill_level, stingy)
from world.society import CHAT, CONFRONT, GO_VISIT, bond_with, find, grudge_of, is_friend, resents
from world.traits import SOCIABILITY, trait_lean
from world.wolves import FLEE, manhattan

EAT, CLAIM, WAIT, YIELD, GO, HOME, REST, DEAD = (
    "eat", "claim", "wait", "yield", "go", "home", "rest", "dead",
)
BUILD = "build"
DEPOSIT = "deposit"
OFFER, GO_OFFER = "offer", "go_offer"
ASK, AGREE = "ask", "agree"
LEG5_PRIORITY = (EAT, CLAIM, FISH, WAIT, YIELD, ASK, GO, AGREE, OFFER, GO_OFFER, HOME, BUILD, REST)
DRINK, DRAW, WAIT_WATER, GO_WATER = "drink", "draw", "wait_water", "go_water"
WATER_PRIORITY = (DRINK, DRAW, WAIT_WATER, GO_WATER)
WARM, GO_SHELTER = "warm", "go_shelter"
WARMTH_PRIORITY = (WARM, GO_SHELTER)
IDLE = (HOME, REST, BUILD, OFFER, GO_OFFER, AGREE)   # nothing of one's own is calling


@dataclass(frozen=True)
class Decision:
    actor: str
    kind: str
    reason: str
    candidates: tuple[str, ...]
    amount: int = 0                      # units to eat or claim
    step: Position | None = None         # the cell a move ends on
    scores: tuple[tuple[str, tuple[int, int]], ...] | None = None
    target: str | None = None            # the source aimed at, when its kind has several
    helped_at: int | None = None         # remembered gift that changed this recipient choice
    home_site: Position | None = None
    provisioning: str | None = None
    announced_to: tuple[str, ...] = ()
    waiting_for_food: str | None = None
    source_report: tuple[str, int] | None = None
    report_to: tuple[str, ...] = ()
    resource: str | None = None          # what an offer hands over; None means food
    rejected: tuple[tuple[str, str, str], ...] = ()   # options weighed and set aside: what, reason code, detail
    greeted: tuple[str, ...] = ()        # people they said hello to (speech costs no tick)
    confronted: tuple[str, ...] = ()     # people they told they were angry with them (speech costs no tick)
    told_to: tuple[str, ...] = ()        # people called to, who hear what is told (speech costs no tick)
    told: tuple[tuple[str, str, int, int, int], ...] = ()   # what is told: kind, subject, x, y, tick first seen

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "reason": self.reason, "candidates": list(self.candidates)}
        if self.amount:
            out["amount"] = self.amount
        if self.step is not None:
            out["step"] = list(self.step)
        if self.greeted:
            out["greeted"] = list(self.greeted)
        if self.confronted:
            out["confronted"] = list(self.confronted)
        if self.told_to:
            out["told_to"] = list(self.told_to)
            out["told"] = [list(entry) for entry in self.told]
        if self.scores is not None:
            out["scores"] = {action: list(pair) for action, pair in self.scores}
        if self.target is not None:
            out["target"] = self.target
        if self.helped_at is not None:
            out["helped_at"] = self.helped_at
        if self.home_site is not None:
            out["home_site"] = list(self.home_site)
        if self.provisioning is not None:
            out["provisioning"] = self.provisioning
        if self.announced_to:
            out["announced_to"] = list(self.announced_to)
        if self.source_report is not None:
            out["source_report"] = list(self.source_report)
            out["report_to"] = list(self.report_to)
        if self.waiting_for_food is not None:
            out["waiting_for_food"] = self.waiting_for_food
        if self.resource is not None:
            out["resource"] = self.resource
        if self.rejected:
            out["rejected"] = [list(entry) for entry in self.rejected]
        return out


def step_toward(origin: Position, target: Position) -> Position:
    """One step along the longer axis, x on ties. Returns origin when there."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return origin
    if abs(dx) >= abs(dy):
        return (origin[0] + (1 if dx > 0 else -1), origin[1])
    return (origin[0], origin[1] + (1 if dy > 0 else -1))


def route_step(observation: Observation, target: Position, config: WorldConfig) -> Position:
    """The next step selected by the existing personal route search."""
    return _route_plan(observation, target, config)[0]


def _route_plan(observation: Observation, target: Position, config: WorldConfig) -> tuple[Position, int]:
    """Next step and estimated cost, picking a way round known rough ground.

    Rough inside sight counts, and remembered rough counts after it leaves
    sight. Known rough costs two ticks to enter and anything else costs one;
    unknown ground is still counted as open. The cheapest total wins. With no
    known rough this is the plain step along the longer axis, x on ties, so a
    world without terrain moves exactly as it always did.

    Detouring round a single rough cell costs two extra steps against the one
    tick of crossing it, so nobody bothers; a wall of them is worth going
    round, and that is the case this exists for."""
    origin = observation.position
    if too_far_for_a_child(observation, config, target):
        target = observation.home
    straight = step_toward(origin, target)
    if too_far_for_a_child(observation, config, straight):
        x, y = origin
        legal = [cell for cell in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                 if 0 <= cell[0] < config.width and 0 <= cell[1] < config.height
                 and not too_far_for_a_child(observation, config, cell)
                 and steps_to(cell, target) < steps_to(origin, target)]
        straight = legal[0] if legal else origin
    if origin == target or not config.route_around:
        return straight, steps_to(origin, target)
    if observation.danger:
        return _danger_plan(observation, target, config, straight)
    if not observation.rough_in_view:
        return straight, steps_to(origin, target)
    radius, rough = config.perception_radius, observation.rough_in_view
    seen_limit = radius
    remembered_limit = max([chebyshev_steps(origin, target), seen_limit]
                           + [chebyshev_steps(origin, cell) for cell in rough])

    def neighbours(cell: Position) -> list[Position]:
        x, y = cell
        near = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in near if 0 <= c[0] < config.width and 0 <= c[1] < config.height
                and not too_far_for_a_child(observation, config, c)
                and chebyshev_steps(origin, c) <= remembered_limit]

    # rank the first step so ties fall the way the plain rule would have gone
    order = {cell: i for i, cell in enumerate(dict.fromkeys([straight] + neighbours(origin)))}
    best_first: dict[Position, Position] = {}
    seen: dict[Position, tuple[int, int]] = {origin: (0, 0)}
    queue: list[tuple[int, int, int, int, Position]] = [(0, 0, origin[1], origin[0], origin)]
    while queue:
        cost, rank, _, _, cell = heappop(queue)
        if (cost, rank) > seen.get(cell, (INF, INF)):
            continue
        for nxt in neighbours(cell):
            step = cost + (2 if nxt in rough else 1)
            first = nxt if cell == origin else best_first[cell]
            nrank = order.get(first, len(order)) if cell == origin else rank
            if (step, nrank) < seen.get(nxt, (INF, INF)):
                seen[nxt], best_first[nxt] = (step, nrank), first
                heappush(queue, (step, nrank, nxt[1], nxt[0], nxt))
    # Judge only where sight runs out, or the target itself. At a cell in the
    # middle of the window the straight-line estimate pretends the rough beyond
    # it is not there, even though the person can see it, and a cell just short
    # of a wall then looks like the best place in the world to be.
    def edge(cell: Position) -> bool:
        dist = chebyshev_steps(origin, cell)
        if remembered_limit > seen_limit:
            return cell == target or dist == remembered_limit
        return cell == target or dist == seen_limit

    ends = [c for c in best_first if edge(c)] or list(best_first)
    if not ends:
        return straight, steps_to(origin, target)
    choice = min(ends, key=lambda c: (seen[c][0] + steps_to(c, target),
                                      order.get(best_first[c], len(order)), c[1], c[0]))
    return best_first[choice], seen[choice][0] + steps_to(choice, target)


def _danger_plan(observation: Observation, target: Position, config: WorldConfig,
                 straight: Position) -> tuple[Position, int]:
    """Next step and cost of the cheapest way to the target when somebody believes a wolf is about.

    Each cell costs one tick to enter, one more if it is rough ground they know of, and danger_cost more if
    they believe a wolf is near it. The whole map is searched so that a step taken now is the first step of
    the same cheapest way next tick (a search that judged only a window of the map changed its mind with every
    step); ground they know nothing of counts as open. Ties go to the plain step."""
    origin, rough, danger = observation.position, observation.rough_in_view, observation.danger
    price = config.lever("danger_cost")
    x, y = origin
    first_moves = [cell for cell in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))]
    order = {cell: i for i, cell in enumerate(dict.fromkeys([straight] + first_moves))}
    best_first: dict[Position, Position] = {}
    seen: dict[Position, tuple[int, int]] = {origin: (0, 0)}
    queue: list[tuple[int, int, int, int, Position]] = [(0, 0, origin[1], origin[0], origin)]
    while queue:
        cost, rank, _, _, cell = heappop(queue)
        if cell == target:
            break
        if (cost, rank) > seen.get(cell, (INF, INF)):
            continue
        cx, cy = cell
        for nxt in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if (not (0 <= nxt[0] < config.width and 0 <= nxt[1] < config.height)
                    or too_far_for_a_child(observation, config, nxt)):
                continue
            step = cost + 1 + (1 if nxt in rough else 0) + (price if nxt in danger else 0)
            first = nxt if cell == origin else best_first[cell]
            nrank = order.get(first, len(order)) if cell == origin else rank
            if (step, nrank) < seen.get(nxt, (INF, INF)):
                seen[nxt], best_first[nxt] = (step, nrank), first
                heappush(queue, (step, nrank, nxt[1], nxt[0], nxt))
    if target not in best_first:
        return straight, steps_to(origin, target)
    return best_first[target], seen[target][0]


def chebyshev_steps(a: Position, b: Position) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def steps_to_source(observation: Observation) -> int:
    """Moves to the source cell: movement is one four-neighbour step per tick."""
    return abs(observation.source[0] - observation.position[0]) + abs(observation.source[1] - observation.position[1])


def food_travel_ticks(observation: Observation, config: WorldConfig) -> int:
    """Estimate the selected food trip using only personally known ground.

    Share the route search and its costs, including our current movement
    delay; unseen ground still counts as open.
    With terrain or routing off, retain the nominal Manhattan estimate.
    This is not a prediction of interruptions, competition or shelter relief.
    """
    if not config.terrain_on or not config.route_around:
        return steps_to_source(observation)
    if observation.at_source:
        return 0
    # held is the remaining movement delay, not carried food.
    return observation.held + _route_plan(observation, observation.source, config)[1]


def trip_due(observation: Observation, config: WorldConfig) -> bool:
    """Leave using known route cost and nominal hunger rate, plus a fishing cast."""
    casting = int(config.fishing_on and observation.source_id == FISH_SOURCE)
    # A cautious person sets off a few ticks earlier, a bold one a few later; zero when traits are off.
    ticks = max(0, food_travel_ticks(observation, config) + casting + caution_ticks(observation.traits))
    return (config.plan_trips and observation.food == 0 and not observation.at_source
            and observation.hunger + config.hunger_rate * ticks >= config.hungry_at)


def arrived_early(observation: Observation, config: WorldConfig) -> bool:
    """At a stocked source, holding no food, not yet hungry, but within this person's own
    caution margin of being so. Only people with traits of caution above the middle ever are."""
    margin = max(caution_ticks(observation.traits), int(config.on("steady")))
    return (margin > 0 and config.plan_trips and observation.alive and observation.food == 0
            and observation.at_source and observation.source_food is not None and observation.source_food >= 1
            and observation.hunger < config.hungry_at
            and observation.hunger + config.hunger_rate * margin >= config.hungry_at)


def crowd_on_source(observation: Observation) -> int:
    """Living others this person can see who are standing on the source cell."""
    return sum(1 for seen in observation.others if seen.position == observation.source)


def yield_eligible(observation: Observation, config: WorldConfig) -> bool:
    if not observation.alive:
        return False
    if observation.hunger < config.hungry_at or observation.hunger >= config.emergency_at:
        return False
    if observation.at_source or observation.source_food is None:
        return False
    crowd = crowd_on_source(observation)
    return crowd >= observation.yield_at and observation.source_food < crowd


def is_child(observation: Observation, config: WorldConfig) -> bool:
    return config.childhood_on and observation.age < config.adult_at


def too_far_for_a_child(observation: Observation, config: WorldConfig, target: Position) -> bool:
    """A child will not leave home by more than child_leash steps. One born
    within reach of a source feeds itself; one born in a far corner is at the
    mercy of whoever thinks to bring it something."""
    return is_child(observation, config) and steps_to(observation.home, target) > config.child_leash


def in_view(observation: Observation, actor: str | None) -> bool:
    return actor is not None and any(seen.actor == actor for seen in observation.others)


def adjacent_request(observation: Observation, config: WorldConfig) -> str | None:
    """A visible, empty-handed asker who can receive food without a journey."""
    if not config.requests_on or observation.owed_to is not None:
        return None
    return next((seen.actor for seen in observation.others
                 if seen.actor == observation.asked_by and seen.food < 1
                 and steps_to(observation.position, seen.position) <= 1), None)


def someone_to_help(observation: Observation, config: WorldConfig) -> str | None:
    """The person this one is carrying a spare unit to.

    Empty-handed dependents come first (optionally visible hunger emergencies
    before distance and id), then direct answers and an existing
    promise. Otherwise help someone visibly starving, preferring a remembered
    donor before distance and id. Memory never reveals an absent person or
    creates a need. Thirst shows too, but food does not help it."""
    if observation.food < 1:
        return None
    # your own child, in front of you and carrying nothing, comes before anybody
    hungry_children = [seen for seen in observation.others
                       if seen.actor in observation.dependents and seen.food < 1]
    if hungry_children:
        return min(hungry_children, key=lambda seen: (config.care_by_need_on and not seen.starving,
                                                      steps_to(observation.position, seen.position),
                                                      seen.actor)).actor
    nearby = adjacent_request(observation, config)
    if nearby is not None:
        return nearby
    if in_view(observation, observation.owed_to):
        return observation.owed_to
    if not config.offers_on:
        return None
    starving = [seen for seen in observation.others if seen.starving]
    social = config.on("bonds")
    if social:
        # nobody goes out of their way for somebody they resent, unless it is their own child
        starving = [seen for seen in starving
                    if seen.actor in observation.dependents or not resents(observation.bonds, seen.actor, config)]
    if stingy(observation.traits) and observation.food < 2:
        # a stingy person keeps their last unit from strangers; their own children, and their friends, are fed regardless
        starving = [seen for seen in starving if seen.actor in observation.dependents
                    or (social and is_friend(observation.bonds, seen.actor, config))]
    if not starving:
        return None
    remembered = dict(observation.food_memory) if config.social_memory_on else {}
    return min(starving, key=lambda seen: (social and not is_friend(observation.bonds, seen.actor, config),
                                         seen.actor not in remembered,
                                         steps_to(observation.position, seen.position), seen.actor)).actor


def someone_to_ask(observation: Observation, config: WorldConfig) -> str | None:
    """Who a hungry person with nothing asks: the nearest other they can see
    carrying food, by steps then id. Never somebody visibly starving - their
    need is plain and they need it more.

    Asking is speech, not work: they call out while they carry on walking to
    the source, so it costs them nothing and does not replace the journey. An
    earlier version made asking its own action, and the tick it cost was fatal
    - people stopped to ask, almost nobody was ever free to answer, and whole
    populations died of the delay. Nobody asks twice while an answer is still
    owed to them, and nobody asks while they are busy answering somebody
    else."""
    if not config.requests_on or observation.food >= 1:
        return None
    if observation.waiting_on is not None or observation.asked_by is not None:
        return None
    holders = [seen for seen in observation.others if seen.food >= 1 and not seen.starving
               and (not config.adjacent_requests or steps_to(observation.position, seen.position) <= 1)]
    if not holders:
        return None
    return min(holders, key=lambda seen: (steps_to(observation.position, seen.position), seen.actor)).actor


def _seen(observation: Observation, actor: str) -> Position:
    return next(seen.position for seen in observation.others if seen.actor == actor)


def candidates(observation: Observation, config: WorldConfig) -> tuple[str, ...]:
    if not observation.alive:
        return ()
    hungry = observation.hunger >= config.hungry_at
    found: list[str] = []
    if hungry and observation.food >= 1:
        found.append(EAT)
    if hungry and observation.at_source:
        if observation.source_food is None:
            raise AssertionError(f"{observation.actor} is at the source but did not observe its stock")
        gather = (FISH if config.fishing_on and observation.source_id == FISH_SOURCE
                  and not observation.fishing_ready else CLAIM)
        found.append(gather if observation.source_food >= 1 else WAIT)
    if hungry and not observation.at_source:
        waiting = bool(errand_holds(observation, config, "food"))
        if yield_eligible(observation, config):
            found.append(YIELD)
        if not waiting and someone_to_ask(observation, config) is not None:
            found.append(ASK)
        if too_far_for_a_child(observation, config, observation.source):
            found.append(REST if observation.at_home else HOME)   # too small to go that far; wait to be fed
        elif waiting:
            found.append(REST if observation.at_home else HOME)  # put off: stay in, or walk home to wait
        else:
            found.append(GO)
    if not hungry:
        if arrived_early(observation, config):
            # a cautious person who set off early and has arrived within their margin stocks up now,
            # rather than turning round and setting off again
            found.append(FISH if config.fishing_on and observation.source_id == FISH_SOURCE
                         and not observation.fishing_ready else CLAIM)
        elif (trip_due(observation, config) and not too_far_for_a_child(observation, config, observation.source)
              and not errand_holds(observation, config, "food")):
            found.append(GO)
        elif (config.plan_trips and config.fishing_on and observation.source_id == FISH_SOURCE
              and observation.at_source and observation.food == 0 and not observation.fishing_ready
              and observation.source_food is not None and observation.source_food > 0
              and observation.hunger + config.hunger_rate >= config.hungry_at):
            found.append(FISH)  # finish the planned cast as hunger reaches the gathering threshold
        elif (config.requests_on and not config.adjacent_requests and observation.asked_by is not None
                and in_view(observation, observation.asked_by)
                and observation.food >= 1 and observation.owed_to is None
                and not observation.dependents
                and adjacent_request(observation, config) is None):
            # one errand at a time, and never while a child of your own still
            # needs you: an adult away on a stranger's errand is an adult not
            # feeding their own, and that killed more children than it saved
            found.append(AGREE)
        elif someone_to_help(observation, config) is not None:
            hurt = someone_to_help(observation, config)
            found.append(OFFER if steps_to(observation.position, _seen(observation, hurt)) <= 1 else GO_OFFER)
        elif not observation.at_home:
            found.append(HOME)
        elif (config.building_on and not observation.home_built and not is_child(observation, config)
                and not observation.storm
                and not (config.on("wolves") and observation.hurt >= config.lever("limp_at"))):
            found.append(BUILD)          # nothing is calling and home has no shelter yet (not in a storm, not limping)
        else:
            found.append(REST)
    return tuple(found)


def action_score(action: str, observation: Observation, config: WorldConfig) -> tuple[int, int]:
    """Score one eligible action from its bounded tick-start observation only.

    GO is odd, YIELD even. GO > YIELD iff hunger >= hungry_at + crowd -
    yield_at + 1. Equal increments for hunger and crowd are an authored scale.
    These pairs never enter the kernel's food-allocation order.
    """
    if action == EAT:
        return (2, 0)
    if action in (CLAIM, FISH, WAIT):
        return (1, 0)
    if action == GO:
        return (0, 2 * (observation.hunger - config.hungry_at) + 1)
    if action == YIELD:
        return (0, 2 * (crowd_on_source(observation) - observation.yield_at + 1))
    if action in IDLE:
        return (0, 0)
    raise ValueError(f"no score for action {action!r}")


def decide(observation: Observation, config: WorldConfig) -> Decision:
    choice = _decide(observation, config)
    if choice.kind == CHAT:
        # a quiet word: what they know of wolves seen lately, and where they live, with the dates they were first seen
        news = sorted(((b[4], b[1], b[2], b[3]) for b in observation.beliefs if b[0] == "wolf"
                       and observation.tick - b[4] <= config.lever("danger_span")), reverse=True) if config.on("wolves") else []
        told = [("home", observation.actor, observation.home[0], observation.home[1], observation.tick)]
        told += [("wolf", subject, x, y, seen) for seen, subject, x, y in news]
        choice = replace(choice, told_to=(choice.target,), told=tuple(told[:config.lever("told_per_chat")]))
    if config.on("bonds") and observation.alive and not observation.asleep and choice.kind != DEAD:
        # whoever is within reach and awake gets a hello, unless they have dealt with them lately, and a word if they
        # are angry with them; neither takes any time
        reach, again, grudge_at = config.lever("talk_range"), config.lever("greet_every"), config.lever("grudge_at")
        hello, words = [], []
        for seen in observation.others:
            if seen.asleep or max(abs(seen.position[0] - observation.position[0]),
                                  abs(seen.position[1] - observation.position[1])) > reach:
                continue
            held = find(observation.bonds, seen.actor)
            if held is not None and held[3] >= grudge_at:
                if not _tried_lately(observation, CONFRONT, seen.actor, 3 * config.lever("retry_after")):
                    words.append(seen.actor)
            elif held is None or observation.tick - held[4] >= again:
                hello.append(seen.actor)
        if hello or words:
            choice = replace(choice, greeted=tuple(sorted(hello)), confronted=tuple(sorted(words)))
    if config.on("wolves") and observation.alive and observation.wolves_seen:
        # seeing a wolf, they call out to everybody they can see who is awake; speech costs no tick
        # (once per sighting: not again while they keep seeing the same wolf, nor when they were just told of it)
        fresh = [(wolf, cell) for wolf, cell in observation.wolves_seen if wolf in observation.wolves_active
                 and not any(b[0] == "wolf" and b[1] == wolf and b[4] >= observation.tick - 1 for b in observation.beliefs)]
        listeners = tuple(seen.actor for seen in observation.others if not seen.asleep)
        if fresh and listeners:
            choice = replace(choice, told_to=listeners, told=tuple(
                ("wolf", wolf, cell[0], cell[1], observation.tick) for wolf, cell in fresh))
    if config.on("explain") and observation.alive and observation.traits and choice.kind in (HOME, REST, BUILD):
        # Free to help, somebody visibly starving, and only their own temperament said no.
        wanted = someone_to_help(replace(observation, traits=()), config)
        if wanted is not None and someone_to_help(observation, config) is None:
            choice = replace(choice, rejected=choice.rejected + (rejection(
                "offer", UNWILLING, f"{wanted} looks starving, but with {observation.food} unit "
                f"and generosity {observation.traits[0]} they keep it"),))
    if not config.knowledge_sharing_on or not observation.alive:
        return choice
    avoided = observation.report_provision_avoided if choice.provisioning == "gather" else observation.report_food_avoided
    report = next((e for e in observation.source_reports if e[0] == avoided), None)
    if report is not None and choice.kind in (GO, WAIT, CLAIM, FISH, YIELD):
        sid, speaker, seen, heard = report
        choice = replace(choice, reason=choice.reason + f"; {speaker} reported {sid} empty at tick {seen} (heard at {heard})")
    empty = [e for e in observation.food_sightings if e[1] == 0]
    if empty and observation.report_listeners:
        sid, _, seen = min(empty, key=lambda e: (-e[2], e[0]))
        choice = replace(choice, source_report=(sid, seen), report_to=observation.report_listeners)
    return choice


def _decide(observation: Observation, config: WorldConfig) -> Decision:
    """Food alone when it is the only need (the rule above, unchanged); otherwise
    every need that is on, arbitrated by `_decide_needs`."""
    if config.water_on or config.warmth_on or config.on("sleep"):
        choice = _decide_needs(observation, config)
    else:
        choice = _decide_food(observation, config)
    if observation.food_choice_changed and choice.kind in (GO, WAIT, CLAIM, FISH, YIELD):
        choice = replace(choice, reason=choice.reason +
                         f"; avoiding {observation.food_choice_changed}, remembered empty; trying {observation.source_id}")
    if config.homes_on and observation.choosing_home and choice.kind in (HOME, BUILD, REST):
        site = choose_site(observation, config)
        if site is not None:
            arrived = observation.position == site
            kind = SETTLE if arrived else GO_SETTLE
            return Decision(observation.actor, kind,
                            f"grown up; {'settling at' if arrived else 'walking to'} an adult home at {site}",
                            choice.candidates + (kind,), home_site=site,
                            step=None if arrived else route_step(observation, site, config),
                            scores=choice.scores + ((kind, (0, 1)),) if choice.scores is not None else None)
    if observation.relocating and not observation.storm and choice.kind in (HOME, BUILD, REST, GO_SHELTER):
        site = choose_relocation(observation, config)
        if site is not None:
            if config.warmth_on and observation.at_home and observation.cold > 0:
                return Decision(observation.actor, WARM, "warming up before moving home",
                                choice.candidates + ((WARM,) if WARM not in choice.candidates else ()),
                                scores=choice.scores + ((WARM, (0, 1)),) if choice.scores is not None else None)
            if choice.kind == GO_SHELTER and steps_to(observation.position, site) > steps_to(observation.position, observation.home):
                return choice
            arrived = observation.position == site
            kind = RELOCATE if arrived else GO_RELOCATE
            return Decision(observation.actor, kind,
                            f"repeated costly supply outings; {'moving into' if arrived else 'walking to'} a nearer home at {site}",
                            choice.candidates + (kind,), home_site=site,
                            step=None if arrived else route_step(observation, site, config),
                            scores=choice.scores + ((kind, (0, 1)),) if choice.scores is not None else None)
    if (config.wood_on and not observation.home_built and not is_child(observation, config)
            and not observation.storm and choice.kind in (HOME, BUILD)):
        cost = wood_cost(observation.work_done)
        if observation.wood < cost:
            site = observation.wood_source
            if site is None:
                raise ValueError("wood construction requires an observed grove landmark")
            kind = GO_WOOD if observation.position != site else GATHER_WOOD if observation.wood_stock else WAIT_WOOD
            amount = min(WOOD_PACK, remaining_wood(observation.work_done, build_goal(config.build_ticks, observation.skills)) - observation.wood,
                         observation.wood_stock or 0) if kind == GATHER_WOOD else 0
            return Decision(observation.actor, kind, "shelter work needs wood; " + {
                GO_WOOD: "walking to a grove", GATHER_WOOD: "gathering wood to carry home", WAIT_WOOD: "waiting at an empty grove"}[kind],
                choice.candidates + (kind,), amount=amount, target=observation.wood_source_id,
                step=route_step(observation, site, config) if kind == GO_WOOD else None,
                scores=choice.scores + ((kind, (0, 1)),) if choice.scores is not None else None)
        if choice.kind == BUILD:
            return replace(choice, amount=cost, reason=f"building shelter; {cost} wood due for this work tick")
    if config.stores_on and choice.kind == REST and not is_child(observation, config):
        spare = spare_for_store(observation)
        if spare:
            return Decision(observation.actor, DEPOSIT,
                            f"putting {spare} spare food in the shared home cache; keeping one meal",
                            choice.candidates + (DEPOSIT,), amount=spare,
                            target=observation.home_store_id or store_id(observation.actor),
                            scores=choice.scores + ((DEPOSIT, (0, 1)),) if choice.scores is not None else None)
    if config.on("bonds") and choice.kind in (HOME, BUILD, REST):
        talk = _social(observation, config, choice)
        if talk is not None:
            return talk
    if config.provisioning_on and choice.kind in (REST, HOME):
        return _provision_decision(observation, config, choice)
    return choice


def _tried_lately(observation: Observation, kind: str, other: str, window: int) -> bool:
    return any(k == kind and who == other and observation.tick - when < window for k, who, when, _ in observation.tried)


def _social(observation: Observation, config: WorldConfig, choice: Decision) -> Decision | None:
    """Idle people look for company, have it out with somebody they resent, or carry on a conversation.

    Only what they observe and remember counts: who is in view, how they feel about each, who they
    tried lately, how lonely they are, and the homes of friends they were told of."""
    if observation.asleep or not observation.alive or observation.storm:
        return None
    actor, here, bonds, lonely = observation.actor, observation.position, observation.bonds, observation.lonely
    reach, retry = config.lever("talk_range"), config.lever("retry_after")
    awake = [seen for seen in observation.others if not seen.asleep]
    free = [seen for seen in awake if not seen.busy]

    def near(seen) -> bool:
        return max(abs(seen.position[0] - here[0]), abs(seen.position[1] - here[1])) <= reach

    # carry on a conversation, or start one
    talking = observation.talking
    chat_at = config.lever("chat_at")
    partners = []
    for seen in free:
        held = find(bonds, seen.actor)
        if resents(bonds, seen.actor, config) or _tried_lately(observation, CHAT, seen.actor, retry):
            continue
        carrying_on = talking is not None and talking[0] == seen.actor and observation.tick - talking[1] < config.lever("chat_len")
        if (not carrying_on and held is not None and held[7] == "warm"
                and observation.tick - held[4] <= retry):
            continue                                                  # they have just talked: give it a rest
        partners.append((seen, carrying_on))
    ready = lonely >= max(1, chat_at // 2)             # half the need is enough to talk back, and to carry on
    close = sorted((p for p in partners if near(p[0])), key=lambda p: (not p[1], -bond_with(bonds, p[0].actor),
                                                                      max(abs(p[0].position[0] - here[0]), abs(p[0].position[1] - here[1])),
                                                                      p[0].actor))
    if close and (ready or (close[0][1] and lonely >= 1)):
        seen = close[0][0]
        how = ("a friend" if is_friend(bonds, seen.actor, config) else "somebody they know" if find(bonds, seen.actor)
               else "somebody new")
        return Decision(actor, CHAT, f"lonely {lonely}; talking with {seen.actor}, {how}",
                        choice.candidates + (CHAT,), target=seen.actor)
    if observation.night or observation.hurt >= (config.lever("limp_at") if config.on("wolves") else 10 ** 9):
        return None
    # walk to company: somebody in view, else the home of somebody they know, else the well
    want = lonely >= max(chat_at, config.lever("lonely_at") - trait_lean(observation.traits, SOCIABILITY) // 5)
    if not want:
        return None
    if partners:
        seen = min(partners, key=lambda p: (-bond_with(bonds, p[0].actor), steps_to(here, p[0].position), p[0].actor))[0]
        return Decision(actor, GO_VISIT, f"lonely {lonely}; walking over to talk with {seen.actor}",
                        choice.candidates + (GO_VISIT,), target=seen.actor,
                        step=route_step(observation, seen.position, config))
    known = sorted(((bond_with(bonds, b[1]), b[1], (b[2], b[3])) for b in observation.beliefs
                    if b[0] == "home" and find(bonds, b[1]) is not None and not resents(bonds, b[1], config)),
                   key=lambda f: (-f[0], steps_to(here, f[2]), f[1]))
    if known:
        _, who, cell = known[0]
        if cell != here and steps_to(here, cell) <= 3 * config.perception_radius + 6:
            return Decision(actor, GO_VISIT, f"lonely {lonely}; going to see {who}, whose home they know",
                            choice.candidates + (GO_VISIT,), target=who, step=route_step(observation, cell, config))
    # nobody known to call on: the well is where people meet, so go and wait there
    hub = observation.water_source or observation.source
    if here == hub:
        return Decision(actor, REST, f"lonely {lonely}; waiting at the well for somebody to talk to", choice.candidates)
    if steps_to(here, hub) <= 3 * config.perception_radius + 6:
        return Decision(actor, GO_VISIT, f"lonely {lonely}; going to the well to see who is about",
                        choice.candidates + (GO_VISIT,), step=route_step(observation, hub, config))
    return None


def _provision_decision(observation: Observation, config: WorldConfig, choice: Decision) -> Decision:
    """Use spare time for one natural-source collection, then carry it home."""
    phase = observation.provision_phase
    if phase is None and (observation.storm or not start_provisioning(observation, config)):
        return choice                                    # no new optional outing in a storm
    if is_child(observation, config) or observation.provision_source is None:
        return choice
    if phase is None and config.warmth_on and observation.cold > 0:
        return Decision(observation.actor, WARM, "warming up before gathering food for home",
                        choice.candidates + (WARM,),
                        scores=choice.scores + ((WARM, (0, 1)),) if choice.scores is not None else None)
    if phase is None and config.coordination_on and observation.food_expected is not None:
        speaker, heard = observation.food_expected
        return replace(choice, waiting_for_food=speaker,
                       reason=f"{speaker} said they were getting food at tick {heard}; postponing my cache trip")
    phase = phase or "gather"
    sid, site, stock = observation.provision_source
    if phase == "return":
        if observation.at_home:
            return choice
        kind, target, amount = HOME, None, 0
        step = route_step(observation, observation.home, config)
        reason = "returning from a food trip for the shared home cache"
    else:
        if observation.position == site and stock is None:
            raise AssertionError("provisioning at a source requires observed stock")
        kind = (GO if observation.position != site else WAIT if not stock else
                FISH if sid == FISH_SOURCE and not observation.fishing_ready else CLAIM)
        target, amount = sid, min(pack_size(observation, config, sid), stock) if kind == CLAIM else 0
        step = route_step(observation, site, config) if kind == GO else None
        reason = "food trip for the low shared home cache; " + {
            GO: f"walking to {sid}", WAIT: f"waiting at empty {sid}",
            FISH: "casting from the bank", CLAIM: f"collecting at {sid} to carry home"}[kind]
        if observation.provision_avoided:
            reason += f"; avoiding {observation.provision_avoided}, remembered empty"
    options = choice.candidates + ((kind,) if kind not in choice.candidates else ())
    scores = None if choice.scores is None else tuple(
        (action, (0, 1) if action == kind else score) for action, score in choice.scores)
    if scores is not None and kind not in dict(scores):
        scores += ((kind, (0, 1)),)
    return Decision(observation.actor, kind, reason, options, target=target,
                    amount=amount, step=step, scores=scores, provisioning=phase,
                    announced_to=observation.housemates_in_view if config.coordination_on
                    and observation.provision_phase is None else ())


def steps_to(origin: Position, target: Position) -> int:
    return abs(target[0] - origin[0]) + abs(target[1] - origin[1])


def pack_size(observation: Observation, config: WorldConfig, source_id: str | None = None) -> int:
    """Most units one food claim takes: the pack, plus one for every two levels of
    gathering skill (fishing skill at the fishing spot). Plain claim_amount without skills."""
    fishing = (source_id or observation.source_id) == FISH_SOURCE
    return config.claim_amount + skill_level(observation.skills, FISHING if fishing else GATHERING) // 2


def water_trip_due(observation: Observation, config: WorldConfig) -> bool:
    """The leave-in-time rule for water: holding none, and far enough that
    leaving now arrives as thirst reaches thirsty_at."""
    well = observation.water_source
    return (config.plan_trips and well is not None and observation.water == 0 and observation.position != well
            and observation.thirst + config.thirst_rate
            * max(0, steps_to(observation.position, well) + caution_ticks(observation.traits)) >= config.thirsty_at)


def water_candidates(observation: Observation, config: WorldConfig) -> tuple[str, ...]:
    """drink: thirsty and holding water; draw: thirsty at the water with stock;
    wait_water: thirsty at empty water; go_water: thirsty elsewhere, or due to leave."""
    if not observation.alive or observation.water_source is None:
        return ()
    thirsty = observation.thirst >= config.thirsty_at
    at_water = observation.position == observation.water_source
    found: list[str] = []
    if thirsty and observation.water >= 1:
        found.append(DRINK)
    if thirsty and at_water:
        if observation.water_stock is None:
            raise AssertionError(f"{observation.actor} is at the water but did not observe its stock")
        found.append(DRAW if observation.water_stock >= 1 else WAIT_WATER)
    if (not at_water and (thirsty or water_trip_due(observation, config))
            and not too_far_for_a_child(observation, config, observation.water_source)
            and not errand_holds(observation, config, "water")):
        found.append(GO_WATER)
    margin = max(caution_ticks(observation.traits), int(config.on("steady")))
    if (at_water and not thirsty and margin > 0 and config.plan_trips and observation.water == 0
            and observation.water_stock is not None and observation.water_stock >= 1
            and observation.thirst + config.thirst_rate * margin >= config.thirsty_at):
        found.append(DRAW)               # arrived early within their caution margin: draw now
    return tuple(found)


def slack(level: int, lethal: int, rate: int) -> int | float:
    """Ticks before this need kills, at the rate it rises: (lethal - level) //
    rate. A need that does not rise never runs out.

    Deliberately blind to how far the remedy is. Subtracting the steps to the
    remedy looks more informed and oscillates: walking towards food shortens
    the way to food and lengthens the way to shelter, so the two needs swap
    places every step and the person thrashes between them and reaches
    neither. Rate alone is stable, and rate is what the seed 3 death turned
    on - thirst rising twice as fast as cold."""
    return (lethal - level) // rate if rate > 0 else INF


def _threat(observation: Observation, config: WorldConfig) -> int | None:
    """Ticks before a wolf they can see could be beside them, or None when no wolf in sight is within alarm
    steps or they are under their own finished roof. It competes with the other needs by the same
    least-time-left rule."""
    if not config.on("wolves") or not observation.alive or not observation.wolves_active:
        return None
    if observation.at_home and observation.home_built:
        return None
    gap = min(manhattan(observation.position, cell) for wolf, cell in observation.wolves_seen
              if wolf in observation.wolves_active)
    return max(0, gap - 1) if gap <= config.lever("alarm") else None


def flee_step(observation: Observation, config: WorldConfig) -> Position:
    """Where a person runs from a wolf they see: home when it is built, otherwise away from the wolf, and never
    onto a cell beside one when another is free. Ties fall to the lower cell."""
    x, y = observation.position
    wolves = [cell for wolf, cell in observation.wolves_seen if wolf in observation.wolves_active]
    options = [cell for cell in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))
               if 0 <= cell[0] < config.width and 0 <= cell[1] < config.height
               and not too_far_for_a_child(observation, config, cell)] or [observation.position]

    def gap(cell: Position) -> int:
        return min(manhattan(cell, wolf) for wolf in wolves)

    if observation.home_built:
        return min(options, key=lambda c: (gap(c) <= 1, steps_to(c, observation.home), -gap(c), c))
    return min(options, key=lambda c: (gap(c) <= 1, -gap(c), steps_to(c, observation.home), c))


def _flee_decision(observation: Observation, config: WorldConfig, selected: str) -> Decision:
    wolf, cell = min(((w, c) for w, c in observation.wolves_seen if w in observation.wolves_active),
                     key=lambda w: (manhattan(observation.position, w[1]), w[0]))
    gap = manhattan(observation.position, cell)
    where = "for home" if observation.home_built else "away from it"
    return Decision(observation.actor, FLEE, f"{wolf} is {gap} steps away; running {where}", (),
                    step=flee_step(observation, config))


def _decide_needs(observation: Observation, config: WorldConfig) -> Decision:
    """Serve the need with the least slack - the one whose lethal level arrives
    soonest at the rate it rises. Ranking by level alone ignored rate, so a need
    with ticks to spare could outrank one about to kill (ROADMAP, seed 3). Ties
    go to thirst, then cold, then sleep, then hunger, the order they are listed here.

    Hunger only enters the ranking when food is actually calling; a person with
    nothing to do falls back to the food rule's walk home or rest.

    Sleep (the sleep feature) is a need that nobody dies of: its slack is the time
    before collapse. A sleeper stays asleep until rested unless another need is
    urgent, and a tired person does not start sleeping while one is: a need is
    urgent when its slack is no more than the ticks to reach and finish its
    remedy plus a small margin. That is the one place the distance to a remedy
    enters the choice; the ranking itself stays blind to it (see `slack`).

    The candidate block records every action that was open, food first, then
    water, then warmth, then rest, whichever need was served."""
    food = candidates(observation, config)
    if not food:
        return Decision(observation.actor, DEAD, "dead", ())
    water = water_candidates(observation, config)
    warmth = warmth_candidates(observation, config)
    rest = rest_candidates(observation, config)
    every = food + water + warmth + rest
    if rest == (COLLAPSE,):
        # too exhausted for anything but one tick that saves a life: eating or drinking what is already in hand
        lifesaving = ((EAT in food and observation.hunger >= config.emergency_at)
                      or (DRINK in water and observation.thirst >= config.thirst_emergency_at))
        if not lifesaving:
            return replace(_rest_decision(observation, config, COLLAPSE), candidates=every)
        rest = ()
    calling: list[tuple[int | float, tuple[str, ...], tuple[str, ...], Any, str]] = []
    if water:
        calling.append((slack(observation.thirst, config.thirst_death_at, config.thirst_rate),
                        WATER_PRIORITY, water, _water_decision, "water"))
    if warmth:
        calling.append((cold_slack(observation, config), WARMTH_PRIORITY, warmth, _warmth_decision, "warmth"))
    if rest:
        calling.append((fatigue_slack(config, observation.fatigue), REST_PRIORITY, rest, _rest_decision, "sleep"))
    threat = _threat(observation, config)
    if threat is not None:
        every += (FLEE,)
        calling.append((threat, (FLEE,), (FLEE,), _flee_decision, "safety"))
    if calling and any(action not in IDLE for action in food):
        calling.append((slack(observation.hunger, config.death_at, config.hunger_rate), (), (), None, "food"))
    explained = config.on("explain")
    held = [(errand, code, detail) for errand, need in ((GO_WATER, "water"), (GO, "food"))
            for code, detail in errand_holds(observation, config, need)]
    postponed: tuple[tuple[str, str, str], ...] = (
        tuple(rejection(errand, code, detail) for errand, code, detail in held) if explained else ())
    if rest:
        margin = config.lever("urgent_margin")
        urgent = [(entry, _relief_wait(observation, config, entry[4])) for entry in calling
                  if entry[4] != "sleep" and (entry[0] <= _relief_wait(observation, config, entry[4]) + margin
                                              or (not observation.asleep and _in_emergency(observation, config, entry[4])))]
        if urgent:
            if explained:
                entry, wait = min(urgent, key=lambda item: item[0][0])
                postponed += (rejection("sleep", TOO_LATE,
                                        f"{entry[4]} has {entry[0]} ticks left and needs {wait} to reach and finish; "
                                        "it cannot wait for sleep"),)
            calling = [entry for entry in calling if entry[4] != "sleep"]
        elif observation.asleep:
            return replace(_rest_decision(observation, config, rest[0]), candidates=every)
        else:
            # Tired but not yet asleep: a food or water errand that fits before collapse is finished
            # first, so nobody turns back mid-trip and has to make it twice.
            errands = [entry for entry in calling if entry[4] in ("water", "food")]
            if errands:
                cost = (sum(_relief_wait(observation, config, entry[4]) for entry in errands)
                        + max(_trip_home(observation, entry[4]) for entry in errands))
                left = fatigue_slack(config, observation.fatigue)
                # Hysteresis: somebody already on an errand needs a few more ticks of reason to turn back,
                # and somebody already heading for bed a few more to turn aside. Without it a person at the
                # edge of the margin changes their mind every tick as what they can see shifts their estimate.
                lean = (COMMITMENT if observation.doing in ERRAND_KINDS
                        else -COMMITMENT if observation.doing == GO_SLEEP else 0)
                if left > cost + margin - lean:
                    if explained:
                        postponed += (rejection("sleep", LESS_URGENT,
                                                f"collapse is {left} ticks away; finishing the {errands[0][4]} errand "
                                                f"and getting home takes {cost}"),)
                    calling = [entry for entry in calling if entry[4] != "sleep"]
    if config.water_care_on:
        care = _water_care(observation, config, food, water)
        if care is not None:
            return replace(care, candidates=every + ((care.kind,) if care.kind not in every else ()))
    if config.on("personality") and not rest:
        gift = _water_gift(observation, config, food, water, warmth)
        if gift is not None:
            return replace(gift, candidates=every + ((gift.kind,) if gift.kind not in every else ()))
    # Finish a handoff already within reach before heading home early. This
    # buys no extra walking time and never postpones an active need or a
    # water trip. The usual food choice still owns the recipient and transfer.
    if (config.childhood_on and OFFER in food and not water
            and warmth == (GO_SHELTER,) and observation.cold < config.cold_at
            and observation.hunger < config.hungry_at
            and (not config.water_on or observation.thirst < config.thirsty_at)
            and someone_to_help(observation, config) in observation.dependents):
        handoff = _decide_food(observation, config)
        reason = (f"{handoff.target} is my child alongside with no food; "
                  "handing over one before heading home for warmth")
        if config.care_by_need_on:
            reason = f"{handoff.reason}; before heading home for warmth"
        return replace(handoff, candidates=every, reason=reason)
    notes = tuple(detail for _, _, detail in held)
    if not calling:
        food_choice = _decide_food(observation, config)
        return _with(food_choice, every, postponed, notes, risk_note(observation, config, food_choice))
    serving = NEED_OF.get(observation.doing) if config.on("steady") else None      # what they were just doing
    lean = config.lever("commitment") if config.on("steady") else 0
    at_hand = {"water": any(a in AT_HAND for a in water), "food": any(a in AT_HAND for a in food)} if lean else {}

    def counts_for(ranked: tuple) -> int:
        """Ticks a need counts as more urgent for being what they were doing, and for being takeable right now."""
        return (lean if ranked[4] == serving else 0) + (lean if at_hand.get(ranked[4]) else 0)

    winner = min(calling, key=lambda ranked: ranked[0] - counts_for(ranked))
    _, priority, options, build, served = winner
    rejected = postponed
    if explained:
        carried = (", which they were already doing" if served == serving
                   else ", which could be taken right there" if at_hand.get(served) else "")
        rejected += tuple(rejection(entry[4], LESS_URGENT,
                                    f"{entry[0]} ticks left, against {winner[0]} for {served}"
                                    f"{carried if winner[0] > entry[0] else ''}")
                          for entry in calling if entry is not winner and entry[0] != INF and winner[0] != INF)
    if build is None:
        food_choice = _decide_food(observation, config)
        return _with(food_choice, every, rejected, notes, risk_note(observation, config, food_choice))
    chosen = next(action for action in priority if action in options)
    built = build(observation, config, chosen)
    return _with(built, every, rejected, notes, risk_note(observation, config, built))


def _with(decision: Decision, candidates: tuple[str, ...], extra: tuple[tuple[str, str, str], ...],
          notes: tuple[str, ...] = (), risk: str = "") -> Decision:
    """The decision with the full block of open actions and any further options set aside,
    keeping whatever it already recorded. A person who stays in or keeps to their work says why they did
    not go out (`notes`); one who goes out into a known danger says they are taking the risk."""
    reason = decision.reason
    if notes and decision.kind in (REST, BUILD, HOME):
        reason += "; " + "; ".join(notes)
    if risk:
        reason += "; " + risk
    return replace(decision, candidates=candidates, reason=reason, rejected=decision.rejected + extra)


REST_PRIORITY = (COLLAPSE, SLEEP, GO_SLEEP)
COMMITMENT = 8                     # ticks of extra reason needed to drop what one was just doing
ERRAND_KINDS = frozenset({GO, CLAIM, FISH, GO_WATER, DRAW, EAT, DRINK})    # progress towards relief; waiting is not
AT_HAND = frozenset({DRINK, DRAW, EAT, CLAIM, FISH})        # relief that can be taken this very tick
NEED_OF = {GO_WATER: "water", DRAW: "water", WAIT_WATER: "water", DRINK: "water",         # what each decision served,
           GO: "food", CLAIM: "food", FISH: "food", WAIT: "food", EAT: "food",            # for the steady feature
           GO_SHELTER: "warmth", WARM: "warmth", FLEE: "safety"}


def rest_candidates(observation: Observation, config: WorldConfig) -> tuple[str, ...]:
    """sleep: tired and at home, or already asleep and not yet rested; go_sleep: tired
    and away from home; collapse: too exhausted to do anything else."""
    if not config.on("sleep") or not observation.alive or observation.fatigue is None:
        return ()
    floor = config.lever("collapse_at") - config.lever("collapse_recovery")
    if observation.fatigue >= config.lever("collapse_at") or (observation.asleep and observation.fatigue > floor):
        return (COLLAPSE,)                       # down, and staying down until some of it has been slept off
    if observation.asleep:
        return (SLEEP,) if observation.fatigue > config.lever("wake_at") else ()
    if observation.fatigue >= tired_threshold(config, observation.traits, observation.sky):
        return (SLEEP,) if observation.at_home else (GO_SLEEP,)
    return ()


def _relief_wait(observation: Observation, config: WorldConfig, name: str) -> int:
    """Ticks to reach and finish the remedy for a need: the walk, then taking it."""
    if name == "safety":
        return 1                                   # one step out of reach
    if name == "water":
        if observation.water >= 1 or observation.water_source is None:
            return 1
        if observation.position == observation.water_source and observation.water_stock == 0:
            return config.water_renewal_every + 2    # a dry well may take a full renewal period
        return steps_to(observation.position, observation.water_source) + 2     # walk, draw, drink
    if name == "warmth":
        return steps_to(observation.position, observation.home) + 1
    if observation.food >= 1:
        return 1
    if observation.at_source and observation.source_food == 0:
        return config.renewal_every + 2          # an empty source may take a full renewal period to give anything
    return food_travel_ticks(observation, config) + 2                              # walk, claim, eat


def _in_emergency(observation: Observation, config: WorldConfig, name: str) -> bool:
    """The need is at the level the world calls an emergency, which visibly shows to others."""
    if name == "safety":
        return True                                # a wolf in sight and close is always an emergency
    if name == "water":
        return config.water_on and observation.thirst >= config.thirst_emergency_at
    if name == "warmth":
        return config.warmth_on and observation.cold >= config.cold_emergency_at
    return observation.hunger >= config.emergency_at


def _trip_home(observation: Observation, name: str) -> int:
    """Ticks to walk home from where a need's remedy is taken, plus the tick to lie down."""
    if name == "water":
        place = observation.position if observation.water >= 1 or observation.water_source is None \
            else observation.water_source
    else:
        place = observation.position if observation.food >= 1 else observation.source
    return steps_to(place, observation.home) + 1


def _rest_decision(observation: Observation, config: WorldConfig, selected: str) -> Decision:
    actor, fatigue = observation.actor, observation.fatigue
    if selected == COLLAPSE:
        reason = (f"exhausted, fatigue {fatigue} of {config.lever('collapse_at')}; collapsed where they stood"
                  if not observation.asleep else
                  f"too exhausted to get up, fatigue {fatigue}; down until {config.lever('collapse_at') - config.lever('collapse_recovery')}")
        return Decision(actor, COLLAPSE, reason, ())
    if selected == SLEEP:
        where = "at home" if observation.at_home else "where they lie"
        reason = (f"asleep {where}; fatigue {fatigue}, waking at {config.lever('wake_at')}" if observation.asleep
                  else f"tired, fatigue {fatigue}; sleeping {where}")
        return Decision(actor, SLEEP, reason, ())
    return Decision(actor, GO_SLEEP, f"tired, fatigue {fatigue}; going home to sleep", (),
                    step=route_step(observation, observation.home, config))


def _water_gift(observation: Observation, config: WorldConfig, food: tuple[str, ...], water: tuple[str, ...],
                warmth: tuple[str, ...]) -> Decision | None:
    """A generous person with water to spare gives a unit to somebody visibly in a thirst
    emergency, when nothing of their own is calling. Their own children are the water
    care rule's business."""
    if (not generous(observation.traits) or not config.water_on or observation.water < 2
            or water or warmth or any(action not in IDLE for action in food)
            or OFFER in food or GO_OFFER in food):
        return None
    parched = [seen for seen in observation.others if seen.parched and seen.actor not in observation.dependents]
    if not parched:
        return None
    seen = min(parched, key=lambda s: (steps_to(observation.position, s.position), s.actor))
    away = steps_to(observation.position, seen.position)
    if away <= 1:
        return Decision(observation.actor, OFFER, f"{seen.actor} looks parched; being generous, handing over "
                        f"one of {observation.water} water", (), amount=1, target=seen.actor, resource=WATER)
    return Decision(observation.actor, GO_OFFER, f"{seen.actor} looks parched, {away} steps away; being generous, "
                    "carrying water to them", (), step=route_step(observation, seen.position, config),
                    target=seen.actor, resource=WATER)


def away_rate(observation: Observation, config: WorldConfig) -> int:
    """Cold added each tick spent out in the open as things are now: the world's rate plus what the
    sky adds (nothing when the sky feature is off)."""
    return config.cold_rate + observation.chill


def cold_slack(observation: Observation, config: WorldConfig) -> int | float:
    """Ticks before cold kills at the rate it rises out in the open now: at home, the time they would last
    if they set out. When the sky is adding cold and they are away from home, it is what is left after the
    walk back: someone further out than they can walk back before the cold kills them is already lost, so
    they must turn for home while there is still time. In mild weather the plain count is used."""
    left = slack(observation.cold, config.cold_death_at, away_rate(observation, config))
    if observation.chill > 0 and not observation.sheltered:
        return left - steps_to(observation.position, observation.home)
    return left


def shelter_trip_due(observation: Observation, config: WorldConfig) -> bool:
    """The leave-in-time rule for warmth: away from shelter and far enough that
    setting off now reaches it as cold reaches cold_at, at the rate of the sky they are in."""
    # somebody already out on an errand needs a little more reason to turn back for shelter (steady feature)
    patience = config.lever("commitment") if config.on("steady") and observation.doing in ERRAND_KINDS else 0
    return (config.plan_trips and not observation.sheltered
            and observation.cold + away_rate(observation, config)
            * max(0, steps_to(observation.position, observation.home) + caution_ticks(observation.traits))
            >= config.cold_at + patience)


def _due_errand(observation: Observation, config: WorldConfig, need: str):
    """The errand somebody at home is about to set out on for this need, as (ticks out, place, level, rate,
    emergency level, lethal level), or None: they hold what they need, are already there, are too young to
    go that far, or it is not yet time."""
    if need == "food":
        place = observation.source
        if (observation.food >= 1 or observation.at_source or too_far_for_a_child(observation, config, place)
                or (observation.hunger < config.hungry_at and not trip_due(observation, config))):
            return None
        out = food_travel_ticks(observation, config) + int(config.fishing_on and observation.source_id == FISH_SOURCE)
        return out, place, observation.hunger, config.hunger_rate, config.emergency_at, config.death_at
    well = observation.water_source
    if (well is None or observation.water >= 1 or observation.position == well
            or too_far_for_a_child(observation, config, well)
            or (observation.thirst < config.thirsty_at and not water_trip_due(observation, config))):
        return None
    return (steps_to(observation.position, well), well, observation.thirst, config.thirst_rate,
            config.thirst_emergency_at, config.thirst_death_at)


def wolf_news(observation: Observation, config: WorldConfig, place: Position) -> tuple[int, str] | None:
    """The freshest word of a wolf within danger_radius of a place, as (ticks since it was seen, who told
    them - empty when they saw it themselves), or None. Only what they see now and what they believe."""
    radius, span = config.lever("danger_radius"), config.lever("danger_span")
    best: tuple[int, str] | None = None
    if any(chebyshev_steps(cell, place) <= radius for _, cell in observation.wolves_seen):
        best = (0, "")
    for kind, _, x, y, seen, _, via in observation.beliefs:
        age = observation.tick - seen
        if kind == "wolf" and age <= span and chebyshev_steps((x, y), place) <= radius and (best is None or age < best[0]):
            best = (age, via)
    return best


def _news_words(news: tuple[int, str], radius: int, need: str) -> str:
    age, via = news
    return (f"a wolf {'was seen' if not via else 'was reported by ' + via} within {radius} steps of the "
            f"{'well' if need == 'water' else 'food'}{'' if not age else f', {age} ticks ago'}")


def errand_holds(observation: Observation, config: WorldConfig, need: str) -> tuple[tuple[str, str], ...]:
    """Why somebody puts off a due food or water errand, as (reason code, plain detail) pairs; empty when
    they set out.

    Three things can hold them back, each only while the need can wait: the weather would make the round
    trip cost more cold than they can spare; a wolf they have seen or heard of lately was near the place;
    they are too hurt to go out. The first and last apply to somebody at home; the wolf applies wherever
    they are. A need at its emergency level, or with no more than the ticks to reach and finish the errand
    plus a margin left, never waits: they go, and say so if it was a risk."""
    home = observation.at_home
    if not ((home and (observation.chill > 0 or observation.hurt)) or observation.danger):
        return ()
    errand = _due_errand(observation, config, need)
    if errand is None:
        return ()
    out, place, level, rate, emergency, death = errand
    if level >= emergency:
        return ()
    left = slack(level, death, rate)
    room = left - (out + 2)                          # ticks the need could still wait once the errand is allowed for
    holds: list[tuple[str, str]] = []
    if home and observation.chill > 0 and config.warmth_on and room > config.lever("weather_margin"):
        away = 2 * out + 2                           # out, take it and eat or drink, back
        per_tick = away_rate(observation, config)
        reach = observation.cold + per_tick * (away + caution_ticks(observation.traits))
        if reach > config.cold_emergency_at:
            sky = observation.sky
            outside = (f"the {sky.weather}{' at night' if sky.night else ''}" if sky.weather in ("rain", "storm")
                       else f"the cold {sky.phase}")
            holds.append((WEATHER, f"waiting out {outside}: the {need} errand is about {away} ticks out and back at "
                                   f"+{per_tick} cold a tick, which would take cold {observation.cold} to about {reach}; "
                                   f"{left} ticks of {need} left"))
    if observation.danger and place in observation.danger and room > config.lever("wolf_margin"):
        news = wolf_news(observation, config, place)
        if news is not None:
            holds.append((DANGEROUS, f"{_news_words(news, config.lever('danger_radius'), need)}; staying in "
                                     f"with {left} ticks of {need} left"))
    if home and config.on("wolves") and observation.hurt >= config.lever("limp_at") and room > config.lever("wolf_margin"):
        holds.append((HURT, f"hurt {observation.hurt} and limping; staying in while the {need} can wait "
                            f"({left} ticks left)"))
    return tuple(holds)


def risk_note(observation: Observation, config: WorldConfig, decision: Decision) -> str:
    """A person who goes out to a place a wolf was lately near says so: it was a risk they took because the
    need could not wait."""
    if not config.on("wolves") or decision.kind not in (GO, GO_WATER) or not observation.danger:
        return ""
    water = decision.kind == GO_WATER
    place = observation.water_source if water else observation.source
    news = wolf_news(observation, config, place) if place in observation.danger else None
    return f"taking the risk: {_news_words(news, config.lever('danger_radius'), 'water' if water else 'food')}" if news else ""


def warmth_candidates(observation: Observation, config: WorldConfig) -> tuple[str, ...]:
    """warm: cold at shelter; go_shelter: cold away from it, or due to leave.

    Warmth is the one need met by a place, so there is nothing to claim, carry
    or consume: the only actions are to be at shelter or to walk to it."""
    if not observation.alive or not config.warmth_on:
        return ()
    cold = observation.cold >= config.cold_at
    if observation.sheltered:
        return (WARM,) if cold else ()
    return (GO_SHELTER,) if cold or shelter_trip_due(observation, config) else ()


def _warmth_decision(observation: Observation, config: WorldConfig, selected: str) -> Decision:
    actor = observation.actor
    urgency = "cold emergency" if observation.cold >= config.cold_emergency_at else "cold"
    if selected == WARM:
        return Decision(actor, WARM, f"{urgency}, sheltered at home", ())
    reason = (f"{urgency}, walking to shelter" if observation.cold >= config.cold_at
              else f"leaving in time for shelter: cold {observation.cold}, "
                   f"{steps_to(observation.position, observation.home)} steps home")
    return Decision(actor, GO_SHELTER, reason, (), step=route_step(observation, observation.home, config))


def _water_decision(observation: Observation, config: WorldConfig, selected: str) -> Decision:
    actor = observation.actor
    urgency = "thirst emergency" if observation.thirst >= config.thirst_emergency_at else "thirsty"
    if selected == DRINK:
        return Decision(actor, DRINK, f"{urgency}, holding {observation.water} water", (), amount=1)
    target = observation.water_source_id if len(config.water_source_ids()) > 1 else None
    if selected == DRAW:
        stock = observation.water_stock
        if stock is None:
            raise AssertionError("draw selected without observed water stock")
        reason = (f"{urgency}, at water with {stock} free" if observation.thirst >= config.thirsty_at
                  else f"not yet thirsty, but cautious: drawing water with {stock} free before it is needed")
        return Decision(actor, DRAW, reason, (), amount=min(config.draw_amount, stock), target=target)
    if selected == WAIT_WATER:
        return Decision(actor, WAIT_WATER, f"{urgency}, water empty", (), target=target)
    well = observation.water_source
    reason = (f"{urgency}, walking to water" if observation.thirst >= config.thirsty_at
              else f"leaving in time for water: thirst {observation.thirst}, {steps_to(observation.position, well)} "
                   f"steps, none held")
    return Decision(actor, GO_WATER, reason, (), step=route_step(observation, well, config), target=target)


def stranded_from_water(observation: Observation, config: WorldConfig) -> bool:
    """A dependent child lives at this person's home and the home is further
    from every water source than a child will go. Derived from the home and
    the map only; it does not reveal how thirsty the child is or where."""
    return (bool(observation.dependents) and bool(config.water_positions())
            and min(steps_to(observation.home, well) for well in config.water_positions()) > config.child_leash)


CARE_MARGIN = 2   # ticks a parent keeps in hand when putting a child's thirst before their own needs


def own_slack(observation: Observation, config: WorldConfig) -> int | float:
    """Ticks before the nearest of this person's own lethal levels arrives."""
    levels = [slack(observation.thirst, config.thirst_death_at, config.thirst_rate),
              slack(observation.hunger, config.death_at, config.hunger_rate)]
    if config.warmth_on:
        levels.append(cold_slack(observation, config))
    return min(levels)


def _water_care(observation: Observation, config: WorldConfig, food: tuple[str, ...],
                water: tuple[str, ...]) -> Decision | None:
    """Parents bringing water to a child who cannot fetch it. A parent puts this
    ahead of their own needs only while those leave enough ticks in hand for
    the walk and CARE_MARGIN to spare. Returns None when neither part applies,
    and the usual rules decide.

    Hand over: holding water, with a dependent child in view who is visibly
    parched, or who is out of reach of water and holds none. Parched children
    first, then distance and id.
    Fetch: holding none, a dependent child out of reach of water, nothing of
    their own calling for food or water, and no food handoff under way."""
    actor = observation.actor
    if not observation.alive or observation.water_source is None:
        return None
    stranded = stranded_from_water(observation, config)
    slack_left = own_slack(observation, config)
    if observation.water >= 1:
        wanting = [seen for seen in observation.others if seen.actor in observation.dependents
                   and (seen.parched or (stranded and seen.water == 0))]
        if wanting:
            seen = min(wanting, key=lambda s: (not s.parched, steps_to(observation.position, s.position), s.actor))
            away = steps_to(observation.position, seen.position)
            why = "visibly parched" if seen.parched else "out of reach of water and holding none"
            if slack_left > away + CARE_MARGIN:
                if away <= 1:
                    return Decision(actor, OFFER, f"{seen.actor} is my child, {why}; "
                                    f"handing over one of {observation.water} water", (), amount=1,
                                    target=seen.actor, resource=WATER)
                return Decision(actor, GO_OFFER, f"{seen.actor} is my child, {why}, {away} steps away; "
                                "carrying water to them", (), step=route_step(observation, seen.position, config),
                                target=seen.actor, resource=WATER)
    well = observation.water_source
    if (observation.water == 0 and stranded and not water and all(action in IDLE for action in food)
            and OFFER not in food and GO_OFFER not in food
            and slack_left > 2 * steps_to(observation.position, well) + CARE_MARGIN):
        target = observation.water_source_id if len(config.water_source_ids()) > 1 else None
        if observation.position == well:
            stock = observation.water_stock
            if stock is None:
                raise AssertionError(f"{actor} is at the water but did not observe its stock")
            if stock < 1:
                return None
            return Decision(actor, DRAW, f"my child cannot reach water; drawing {min(config.draw_amount, stock)} "
                            "to take home", (), amount=min(config.draw_amount, stock), target=target)
        return Decision(actor, GO_WATER, f"my child cannot reach water; walking {steps_to(observation.position, well)} "
                        "steps to bring some home", (), step=route_step(observation, well, config), target=target)
    return None


def _decide_food(observation: Observation, config: WorldConfig) -> Decision:
    options = candidates(observation, config)
    actor = observation.actor
    target = observation.source_id if config.food_sources > 1 or config.stores_on or config.fishing_on else None
    if not options:
        return Decision(actor, DEAD, "dead", ())
    scores = None
    if config.scoring_on:
        # Sorting stabilises the native candidate block; it is not a tie rule.
        # All simultaneously eligible pairs are distinct under this model.
        options = tuple(sorted(options))
        scores = tuple((action, action_score(action, observation, config)) for action in options)
        selected = max(scores, key=lambda item: item[1])[0]
    else:
        selected = next(action for action in LEG5_PRIORITY if action in options)
    urgency = "emergency" if observation.hunger >= config.emergency_at else "hungry"
    if selected == EAT:
        return Decision(actor, EAT, f"{urgency}, holding {observation.food}", options, amount=1, scores=scores)
    if selected == FISH:
        reason = (f"{urgency}, casting from the bank" if observation.hunger >= config.hungry_at
                  else "fed, casting from the bank before hunger reaches the food threshold")
        return Decision(actor, FISH, reason, options, scores=scores, target=target)
    if selected == CLAIM:
        seen = observation.source_food
        if seen is None:
            raise AssertionError("claim selected without observed source stock")
        amount = min(pack_size(observation, config), seen)
        reason = (f"{urgency}, catching fish with {seen} available" if observation.source_id == FISH_SOURCE
                  else f"{urgency}, at source with {seen} free")
        if observation.hunger < config.hungry_at:
            reason = f"fed, but cautious: stocking up at the source with {seen} free before getting hungry"
        return Decision(actor, CLAIM, reason, options, amount=amount, scores=scores,
                        target=target)
    if selected == WAIT:
        return Decision(actor, WAIT, f"{urgency}, source empty", options, scores=scores, target=target)
    if selected == YIELD:
        crowd = crowd_on_source(observation)
        return Decision(
            actor, YIELD,
            f"{urgency}, saw {crowd} on source, stock {observation.source_food}, yield_at {observation.yield_at}",
            options, scores=scores, target=target,
        )
    if selected == GO:
        reason = (f"{urgency}, walking to source" if observation.hunger >= config.hungry_at
                  else f"fed, leaving in time: hunger {observation.hunger}, "
                       f"{steps_to_source(observation)} steps to source, no food held")
        if observation.hunger < config.hungry_at:
            travel = food_travel_ticks(observation, config)
            if travel != steps_to_source(observation):
                reason += f"; allowing {travel} travel ticks over seen or remembered ground"
        if observation.hunger < config.hungry_at and config.fishing_on and observation.source_id == FISH_SOURCE:
            reason += "; allowing one tick to cast"
        return Decision(actor, GO, reason, options,
                        step=route_step(observation, observation.source, config), scores=scores, target=target)
    if selected == HOME:
        return Decision(actor, HOME, "walking home" if errand_holds(observation, config, "food") else "fed, walking home",
                        options, step=route_step(observation, observation.home, config), scores=scores)
    if selected == ASK:
        who = someone_to_ask(observation, config)
        if too_far_for_a_child(observation, config, observation.source):
            return Decision(actor, ASK, f"{urgency}, asking {who} while staying near home; food is beyond child leash",
                            options, target=who,
                            step=None if observation.at_home else route_step(observation, observation.home, config),
                            scores=scores)
        return Decision(actor, ASK, f"{urgency}, holding none; asking {who} for food while walking on",
                        options, target=who, step=route_step(observation, observation.source, config),
                        scores=scores)
    if selected == AGREE:
        return Decision(actor, AGREE, f"{observation.asked_by} asked; holding {observation.food}, so taking it to them",
                        options, target=observation.asked_by, scores=scores)
    if selected in (OFFER, GO_OFFER):
        hurt = someone_to_help(observation, config)
        where = _seen(observation, hurt)
        if hurt in observation.dependents:
            priority = ("; visibly starving, prioritised among my empty-handed children"
                        if config.care_by_need_on
                        and any(seen.actor == hurt and seen.starving for seen in observation.others)
                        else "")
            if selected == OFFER:
                return Decision(actor, OFFER,
                                f"{hurt} is my child alongside with no food; handing over one of {observation.food}{priority}",
                                options, amount=1, target=hurt, scores=scores)
            return Decision(actor, GO_OFFER,
                            f"{hurt} is my child with no food, {steps_to(observation.position, where)} steps away{priority}",
                            options, step=route_step(observation, where, config), target=hurt, scores=scores)
        if observation.food_memory and hurt != someone_to_help(replace(observation, food_memory=()), config):
            when = dict(observation.food_memory)[hurt]
            action = "handing over one" if selected == OFFER else "taking food to them"
            return Decision(actor, selected,
                            f"{hurt} gave me food at tick {when} and now looks starving; {action}",
                            options, amount=1 if selected == OFFER else 0,
                            step=None if selected == OFFER else route_step(observation, where, config),
                            target=hurt, scores=scores, helped_at=when)
        if selected == OFFER:
            if hurt == adjacent_request(observation, config):
                return Decision(actor, OFFER, f"{hurt} asked and is alongside; handing over one of {observation.food}",
                                options, amount=1, target=hurt, scores=scores)
            return Decision(actor, OFFER, f"{hurt} is starving alongside; handing over one of {observation.food}",
                            options, amount=1, target=hurt, scores=scores)
        return Decision(actor, GO_OFFER, f"{hurt} is starving {steps_to(observation.position, where)} steps away",
                        options, step=route_step(observation, where, config), target=hurt, scores=scores)
    if selected == BUILD:
        return Decision(actor, BUILD, "nothing wanting, building a shelter at home", options, scores=scores)
    waiting = bool(errand_holds(observation, config, "food"))
    if (observation.storm and config.building_on and not observation.home_built and not is_child(observation, config)):
        return Decision(actor, REST, "at home; too stormy to build outside" if waiting
                        else "fed, at home; too stormy to build outside", options, scores=scores,
                        rejected=(rejection("build", UNAVAILABLE, "a storm: too wet and windy to work outside"),)
                        if config.on("explain") else ())
    return Decision(actor, REST, "at home" if waiting else "fed, at home", options, scores=scores)
