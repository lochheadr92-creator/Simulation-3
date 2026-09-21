"""Immutable records of what a tick decided.

Every submitted proposal leaves the tick with exactly one explicit reason and,
when accepted, the effects that were actually committed. Nothing disappears from
the record.

This is not yet the sealed evidence stream: slice 1c specifies and writes that,
including immutable copies of the inputs and alternatives a decision used. What
exists here is the in-memory record the settlement produced, which slice 1c will
serialise rather than reconstruct.
"""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass

from kernel import reasons
from kernel.canonical import digest as canonical_digest
from kernel.state import Effect, Reservation
from kernel.version import ENGINE_VERSION, SCHEMA_VERSION


@dataclass(frozen=True)
class ProposalOutcome:
    proposal_id: str
    actor: str
    sequence: int
    operation: str
    reason: str
    effects: tuple[Effect, ...] = ()
    action_id: str | None = None
    reservation: Reservation | None = None

    def __post_init__(self) -> None:
        if self.reason not in reasons.ALL:
            raise ValueError(f"unknown outcome reason: {self.reason!r}")
        object.__setattr__(self, "effects", tuple(self.effects))

    @property
    def accepted(self) -> bool:
        return self.reason == reasons.ACCEPTED

    def canonical(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "actor": self.actor,
            "sequence": self.sequence,
            "operation": self.operation,
            "reason": self.reason,
            "accepted": 1 if self.accepted else 0,
            "effects": [effect.canonical() for effect in self.effects],
            "action_id": self.action_id,
            "reservation": self.reservation.canonical() if self.reservation is not None else None,
        }


@dataclass(frozen=True)
class TickRecord:
    tick: int
    prior_state_digest: str
    next_state_digest: str
    rotated_roster: tuple[str, ...]
    outcomes: tuple[ProposalOutcome, ...]
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "rotated_roster", tuple(self.rotated_roster))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))

    def outcomes_for(self, proposal_id: str) -> tuple[ProposalOutcome, ...]:
        """Every outcome under this identity. More than one means it was a duplicate."""
        return tuple(outcome for outcome in self.outcomes if outcome.proposal_id == proposal_id)

    def canonical(self) -> dict[str, Any]:
        """A fresh copy each call, so an observer that edits it edits only its copy."""
        return {
            "schema_version": self.schema_version,
            "engine_version": self.engine_version,
            "tick": self.tick,
            "prior_state_digest": self.prior_state_digest,
            "next_state_digest": self.next_state_digest,
            "rotated_roster": list(self.rotated_roster),
            "outcomes": [outcome.canonical() for outcome in self.outcomes],
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())
