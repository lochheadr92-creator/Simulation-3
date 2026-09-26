"""Candidates and the one live selection rule.

`candidates` lists what a person could do this tick given their observation;
`decide` picks one by fixed priority (OFF) or declared integer pairs (ON).
Both are pure. The record keeps the actual scores when ON and the
eligible set beside the choice so a later reader can see what was passed
over (DOCTRINE 2: observation, eligibility, ranking kept separate).

Priority, highest first:
  eat    hungry and holding a free unit
  claim  hungry, standing on the source, source has free stock
  wait   hungry, standing on the source, source empty (stay; hunger continues)
  yield  hungry, not emergency, off the source, source in view, crowd on the
         source >= yield_at and observed stock < crowd (stay; hunger continues)
  go     hungry, elsewhere: one step toward the source; or (trips on) holding
         no food, elsewhere, and hunger + hunger_rate * steps to the source
         >= hungry_at, so a person far from food leaves in time to arrive as
         hunger reaches hungry_at (once due, it stays due on the way)
  home   not hungry, away from home: one step toward home
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

from world.config import WorldConfig
from world.observe import Observation
from world.overlay import Position

EAT, CLAIM, WAIT, YIELD, GO, HOME, REST, DEAD = (
    "eat", "claim", "wait", "yield", "go", "home", "rest", "dead",
)
BUILD = "build"
OFFER, GO_OFFER = "offer", "go_offer"
ASK, AGREE = "ask", "agree"
LEG5_PRIORITY = (EAT, CLAIM, WAIT, YIELD, ASK, GO, AGREE, OFFER, GO_OFFER, HOME, BUILD, REST)
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

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "reason": self.reason, "candidates": list(self.candidates)}
        if self.amount:
            out["amount"] = self.amount
        if self.step is not None:
            out["step"] = list(self.step)
        if self.scores is not None:
            out["scores"] = {action: list(pair) for action, pair in self.scores}
        if self.target is not None:
            out["target"] = self.target
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
    """One step towards target, picking a way round the rough ground this
    person can see.

    Only what is inside the perception radius counts. Within it a rough cell
    costs two ticks to enter and anything else costs one; beyond it nothing is
    known, so the rest of the journey is counted as open ground in a straight
    line. The cheapest total wins. With nothing rough in view this is the plain
    step along the longer axis, x on ties, so a world without terrain moves
    exactly as it always did.

    Detouring round a single rough cell costs two extra steps against the one
    tick of crossing it, so nobody bothers; a wall of them is worth going
    round, and that is the case this exists for."""
    origin = observation.position
    if origin == target or not config.route_around or not observation.rough_in_view:
        return step_toward(origin, target)
    radius, rough = config.perception_radius, observation.rough_in_view
    straight = step_toward(origin, target)

    def neighbours(cell: Position) -> list[Position]:
        x, y = cell
        near = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in near if 0 <= c[0] < config.width and 0 <= c[1] < config.height
                and chebyshev_steps(origin, c) <= radius]

    # rank the first step so ties fall the way the plain rule would have gone
    order = {cell: i for i, cell in enumerate([straight] + neighbours(origin))}
    best_first: dict[Position, Position] = {}
    seen: dict[Position, int] = {origin: 0}
    queue: list[tuple[int, int, int, int, Position]] = [(0, 0, origin[1], origin[0], origin)]
    while queue:
        cost, rank, _, _, cell = heappop(queue)
        if cost > seen.get(cell, INF):
            continue
        for nxt in neighbours(cell):
            step = cost + (2 if nxt in rough else 1)
            first = nxt if cell == origin else best_first[cell]
            nrank = order.get(first, len(order)) if cell == origin else rank
            if step < seen.get(nxt, INF):
                seen[nxt], best_first[nxt] = step, first
                heappush(queue, (step, nrank, nxt[1], nxt[0], nxt))
    # Judge only where sight runs out, or the target itself. At a cell in the
    # middle of the window the straight-line estimate pretends the rough beyond
    # it is not there, even though the person can see it, and a cell just short
    # of a wall then looks like the best place in the world to be.
    def edge(cell: Position) -> bool:
        return cell == target or chebyshev_steps(origin, cell) == radius

    ends = [c for c in best_first if edge(c)] or list(best_first)
    if not ends:
        return straight
    choice = min(ends, key=lambda c: (seen[c] + steps_to(c, target),
                                      order.get(best_first[c], len(order)), c[1], c[0]))
    return best_first[choice]


def chebyshev_steps(a: Position, b: Position) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def steps_to_source(observation: Observation) -> int:
    """Moves to the source cell: movement is one four-neighbour step per tick."""
    return abs(observation.source[0] - observation.position[0]) + abs(observation.source[1] - observation.position[1])


def trip_due(observation: Observation, config: WorldConfig) -> bool:
    """Holding no food and far enough that leaving now arrives as hunger reaches
    hungry_at. Each step adds hunger_rate and removes one step, so once due it
    stays due until the person arrives."""
    return (config.plan_trips and observation.food == 0 and not observation.at_source
            and observation.hunger + config.hunger_rate * steps_to_source(observation) >= config.hungry_at)


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


def in_view(observation: Observation, actor: str | None) -> bool:
    return actor is not None and any(seen.actor == actor for seen in observation.others)


def someone_to_help(observation: Observation, config: WorldConfig) -> str | None:
    """The person this one is carrying a spare unit to.

    Somebody they agreed to supply comes first, and keeps coming first for as
    long as they can see them: an errand taken on is not dropped because a
    nearer stranger starts to look worse. Failing that, the nearest visibly
    starving other, by steps then id. Thirst shows too, but food does not help
    it, so only hunger draws anyone out."""
    if observation.food < 1:
        return None
    if in_view(observation, observation.owed_to):
        return observation.owed_to
    if not config.offers_on:
        return None
    starving = [seen for seen in observation.others if seen.starving]
    if not starving:
        return None
    return min(starving, key=lambda seen: (steps_to(observation.position, seen.position), seen.actor)).actor


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
    holders = [seen for seen in observation.others if seen.food >= 1 and not seen.starving]
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
        found.append(CLAIM if observation.source_food >= 1 else WAIT)
    if hungry and not observation.at_source:
        if yield_eligible(observation, config):
            found.append(YIELD)
        if someone_to_ask(observation, config) is not None:
            found.append(ASK)
        found.append(GO)
    if not hungry:
        if trip_due(observation, config):
            found.append(GO)
        elif (config.requests_on and observation.asked_by is not None
                and observation.food >= 1 and observation.owed_to is None):
            found.append(AGREE)          # one errand at a time; anyone else lets the asking go unanswered
        elif someone_to_help(observation, config) is not None:
            hurt = someone_to_help(observation, config)
            found.append(OFFER if steps_to(observation.position, _seen(observation, hurt)) <= 1 else GO_OFFER)
        elif not observation.at_home:
            found.append(HOME)
        elif config.building_on and not observation.home_built:
            found.append(BUILD)          # nothing is calling and home has no shelter yet
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
    if action in (CLAIM, WAIT):
        return (1, 0)
    if action == GO:
        return (0, 2 * (observation.hunger - config.hungry_at) + 1)
    if action == YIELD:
        return (0, 2 * (crowd_on_source(observation) - observation.yield_at + 1))
    if action in IDLE:
        return (0, 0)
    raise ValueError(f"no score for action {action!r}")


def decide(observation: Observation, config: WorldConfig) -> Decision:
    """Food alone when it is the only need (the rule above, unchanged); otherwise
    every need that is on, arbitrated by `_decide_needs`."""
    if config.water_on or config.warmth_on:
        return _decide_needs(observation, config)
    return _decide_food(observation, config)


def steps_to(origin: Position, target: Position) -> int:
    return abs(target[0] - origin[0]) + abs(target[1] - origin[1])


def water_trip_due(observation: Observation, config: WorldConfig) -> bool:
    """The leave-in-time rule for water: holding none, and far enough that
    leaving now arrives as thirst reaches thirsty_at."""
    well = observation.water_source
    return (config.plan_trips and well is not None and observation.water == 0 and observation.position != well
            and observation.thirst + config.thirst_rate * steps_to(observation.position, well) >= config.thirsty_at)


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
    if not at_water and (thirsty or water_trip_due(observation, config)):
        found.append(GO_WATER)
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


def _decide_needs(observation: Observation, config: WorldConfig) -> Decision:
    """Serve the need with the least slack - the one whose lethal level arrives
    soonest at the rate it rises. Ranking by level alone ignored rate, so a need
    with ticks to spare could outrank one about to kill (ROADMAP, seed 3). Ties
    go to thirst, then cold, then hunger, the order they are listed here.

    Hunger only enters the ranking when food is actually calling; a person with
    nothing to do falls back to the food rule's walk home or rest.

    The candidate block records every action that was open, food first, then
    water, then warmth, whichever need was served."""
    food = candidates(observation, config)
    if not food:
        return Decision(observation.actor, DEAD, "dead", ())
    water = water_candidates(observation, config)
    warmth = warmth_candidates(observation, config)
    every = food + water + warmth
    calling: list[tuple[int | float, tuple[str, ...], tuple[str, ...], Any]] = []
    if water:
        calling.append((slack(observation.thirst, config.thirst_death_at, config.thirst_rate),
                        WATER_PRIORITY, water, _water_decision))
    if warmth:
        calling.append((slack(observation.cold, config.cold_death_at, config.cold_rate),
                        WARMTH_PRIORITY, warmth, _warmth_decision))
    if calling and any(action not in IDLE for action in food):
        calling.append((slack(observation.hunger, config.death_at, config.hunger_rate), (), (), None))
    if not calling:
        return replace(_decide_food(observation, config), candidates=every)
    _, priority, options, build = min(calling, key=lambda ranked: ranked[0])
    if build is None:
        return replace(_decide_food(observation, config), candidates=every)
    chosen = next(action for action in priority if action in options)
    return replace(build(observation, config, chosen), candidates=every)


def shelter_trip_due(observation: Observation, config: WorldConfig) -> bool:
    """The leave-in-time rule for warmth: away from shelter and far enough that
    setting off now reaches it as cold reaches cold_at."""
    return (config.plan_trips and not observation.sheltered
            and observation.cold + config.cold_rate * steps_to(observation.position, observation.home)
            >= config.cold_at)


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
        return Decision(actor, DRAW, f"{urgency}, at water with {stock} free", (), amount=min(config.draw_amount, stock),
                        target=target)
    if selected == WAIT_WATER:
        return Decision(actor, WAIT_WATER, f"{urgency}, water empty", (), target=target)
    well = observation.water_source
    reason = (f"{urgency}, walking to water" if observation.thirst >= config.thirsty_at
              else f"leaving in time for water: thirst {observation.thirst}, {steps_to(observation.position, well)} "
                   f"steps, none held")
    return Decision(actor, GO_WATER, reason, (), step=route_step(observation, well, config), target=target)


def _decide_food(observation: Observation, config: WorldConfig) -> Decision:
    options = candidates(observation, config)
    actor = observation.actor
    target = observation.source_id if config.food_sources > 1 else None
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
    if selected == CLAIM:
        seen = observation.source_food
        if seen is None:
            raise AssertionError("claim selected without observed source stock")
        amount = min(config.claim_amount, seen)
        return Decision(actor, CLAIM, f"{urgency}, at source with {seen} free", options, amount=amount, scores=scores,
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
        return Decision(actor, GO, reason, options,
                        step=route_step(observation, observation.source, config), scores=scores, target=target)
    if selected == HOME:
        return Decision(actor, HOME, "fed, walking home", options, step=route_step(observation, observation.home, config), scores=scores)
    if selected == ASK:
        who = someone_to_ask(observation, config)
        return Decision(actor, ASK, f"{urgency}, holding none; asking {who} for food while walking on",
                        options, target=who, step=route_step(observation, observation.source, config),
                        scores=scores)
    if selected == AGREE:
        return Decision(actor, AGREE, f"{observation.asked_by} asked; holding {observation.food}, so taking it to them",
                        options, target=observation.asked_by, scores=scores)
    if selected in (OFFER, GO_OFFER):
        hurt = someone_to_help(observation, config)
        where = _seen(observation, hurt)
        if selected == OFFER:
            return Decision(actor, OFFER, f"{hurt} is starving alongside; handing over one of {observation.food}",
                            options, amount=1, target=hurt, scores=scores)
        return Decision(actor, GO_OFFER, f"{hurt} is starving {steps_to(observation.position, where)} steps away",
                        options, step=route_step(observation, where, config), target=hurt, scores=scores)
    if selected == BUILD:
        return Decision(actor, BUILD, "nothing wanting, building a shelter at home", options, scores=scores)
    return Decision(actor, REST, "fed, at home", options, scores=scores)
