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
  rest   not hungry, at home
A dead person has no candidates and decides nothing.

CLAIM requires the source to be in view. Standing on the source is
distance 0, so the requirement is always met there; it is stated so the
rule stays honest if the radius changes. The claim amount is
min(claim_amount, observed stock). If stock is not observed the person
cannot be at the source; that is asserted, not defaulted.

YIELD uses only the observation: crowd is the number of seen others whose
position equals the source cell. Dead people are neither seen nor counted.
Emergency never yields. A yield proposes nothing and does not step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from world.config import WorldConfig
from world.observe import Observation
from world.overlay import Position

EAT, CLAIM, WAIT, YIELD, GO, HOME, REST, DEAD = (
    "eat", "claim", "wait", "yield", "go", "home", "rest", "dead",
)
LEG5_PRIORITY = (EAT, CLAIM, WAIT, YIELD, GO, HOME, REST)


@dataclass(frozen=True)
class Decision:
    actor: str
    kind: str
    reason: str
    candidates: tuple[str, ...]
    amount: int = 0                      # units to eat or claim
    step: Position | None = None         # the cell a move ends on
    scores: tuple[tuple[str, tuple[int, int]], ...] | None = None

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "reason": self.reason, "candidates": list(self.candidates)}
        if self.amount:
            out["amount"] = self.amount
        if self.step is not None:
            out["step"] = list(self.step)
        if self.scores is not None:
            out["scores"] = {action: list(pair) for action, pair in self.scores}
        return out


def step_toward(origin: Position, target: Position) -> Position:
    """One step along the longer axis, x on ties. Returns origin when there."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return origin
    if abs(dx) >= abs(dy):
        return (origin[0] + (1 if dx > 0 else -1), origin[1])
    return (origin[0], origin[1] + (1 if dy > 0 else -1))


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
        found.append(GO)
    if not hungry:
        if trip_due(observation, config):
            found.append(GO)
        else:
            found.append(REST if observation.at_home else HOME)
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
    if action in (HOME, REST):
        return (0, 0)
    raise ValueError(f"no score for action {action!r}")


def decide(observation: Observation, config: WorldConfig) -> Decision:
    options = candidates(observation, config)
    actor = observation.actor
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
        return Decision(actor, CLAIM, f"{urgency}, at source with {seen} free", options, amount=amount, scores=scores)
    if selected == WAIT:
        return Decision(actor, WAIT, f"{urgency}, source empty", options, scores=scores)
    if selected == YIELD:
        crowd = crowd_on_source(observation)
        return Decision(
            actor, YIELD,
            f"{urgency}, saw {crowd} on source, stock {observation.source_food}, yield_at {observation.yield_at}",
            options, scores=scores,
        )
    if selected == GO:
        reason = (f"{urgency}, walking to source" if observation.hunger >= config.hungry_at
                  else f"fed, leaving in time: hunger {observation.hunger}, "
                       f"{steps_to_source(observation)} steps to source, no food held")
        return Decision(actor, GO, reason, options,
                        step=step_toward(observation.position, observation.source), scores=scores)
    if selected == HOME:
        return Decision(actor, HOME, "fed, walking home", options, step=step_toward(observation.position, observation.home), scores=scores)
    return Decision(actor, REST, "fed, at home", options, scores=scores)
