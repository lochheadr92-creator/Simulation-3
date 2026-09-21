"""Candidates and the one live selection rule.

`candidates` lists what a person could do this tick given their observation;
`decide` picks one by a fixed priority. Both are pure. The record keeps the
eligible set beside the choice so a later reader can see what was passed
over (DOCTRINE 2: observation, eligibility, ranking kept separate).

Priority, highest first:
  eat    hungry and holding a free unit
  claim  hungry, standing on the source, source has free stock
  wait   hungry, standing on the source, source empty (stay; hunger continues)
  go     hungry, elsewhere: one step toward the source
  home   not hungry, away from home: one step toward home
  rest   not hungry, at home
A dead person has no candidates and decides nothing.

CLAIM requires the source to be in view. Standing on the source is
distance 0, so the requirement is always met there; it is stated so the
rule stays honest if the radius changes. The claim amount is
min(claim_amount, observed stock). If stock is not observed the person
cannot be at the source; that is asserted, not defaulted. No new
candidate kinds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from world.config import WorldConfig
from world.observe import Observation
from world.overlay import Position

EAT, CLAIM, WAIT, GO, HOME, REST, DEAD = "eat", "claim", "wait", "go", "home", "rest", "dead"


@dataclass(frozen=True)
class Decision:
    actor: str
    kind: str
    reason: str
    candidates: tuple[str, ...]
    amount: int = 0                      # units to eat or claim
    step: Position | None = None         # the cell a move ends on

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "reason": self.reason, "candidates": list(self.candidates)}
        if self.amount:
            out["amount"] = self.amount
        if self.step is not None:
            out["step"] = list(self.step)
        return out


def step_toward(origin: Position, target: Position) -> Position:
    """One step along the longer axis, x on ties. Returns origin when there."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return origin
    if abs(dx) >= abs(dy):
        return (origin[0] + (1 if dx > 0 else -1), origin[1])
    return (origin[0], origin[1] + (1 if dy > 0 else -1))


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
        found.append(GO)
    if not hungry:
        found.append(REST if observation.at_home else HOME)
    return tuple(found)


def decide(observation: Observation, config: WorldConfig) -> Decision:
    options = candidates(observation, config)
    actor = observation.actor
    if not options:
        return Decision(actor, DEAD, "dead", ())
    urgency = "emergency" if observation.hunger >= config.emergency_at else "hungry"
    if EAT in options:
        return Decision(actor, EAT, f"{urgency}, holding {observation.food}", options, amount=1)
    if CLAIM in options:
        seen = observation.source_food
        if seen is None:
            raise AssertionError("claim selected without observed source stock")
        amount = min(config.claim_amount, seen)
        return Decision(actor, CLAIM, f"{urgency}, at source with {seen} free", options, amount=amount)
    if WAIT in options:
        return Decision(actor, WAIT, f"{urgency}, source empty", options)
    if GO in options:
        return Decision(actor, GO, f"{urgency}, walking to source", options,
                        step=step_toward(observation.position, observation.source))
    if HOME in options:
        return Decision(actor, HOME, "fed, walking home", options, step=step_toward(observation.position, observation.home))
    return Decision(actor, REST, "fed, at home", options)
