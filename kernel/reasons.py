"""The outcome reason vocabulary.

Every submitted proposal leaves the tick with exactly one of these. Denial,
transfer and completion carry an explicit reason rather than disappearing from
the record.
"""

from __future__ import annotations

ACCEPTED = "accepted"

DENIED_UNKNOWN_ACTOR = "denied_unknown_actor"
DENIED_UNKNOWN_SOURCE = "denied_unknown_source"
DENIED_UNKNOWN_OPERATION = "denied_unknown_operation"
DENIED_MALFORMED_PARAMS = "denied_malformed_params"
DENIED_NON_INTEGER_AMOUNT = "denied_non_integer_amount"
DENIED_NON_POSITIVE_AMOUNT = "denied_non_positive_amount"
DENIED_DUPLICATE_PROPOSAL_ID = "denied_duplicate_proposal_id"
DENIED_DUPLICATE_ACTOR_SEQUENCE = "denied_duplicate_actor_sequence"
DENIED_UNAUTHORISED = "denied_unauthorised"
DENIED_INSUFFICIENT_SOURCE = "denied_insufficient_source"
DENIED_INSUFFICIENT_BALANCE = "denied_insufficient_balance"
DENIED_UNBALANCED_EFFECTS = "denied_unbalanced_effects"
DENIED_SELF_TRANSFER = "denied_self_transfer"

ALL = frozenset(
    {
        ACCEPTED,
        DENIED_UNKNOWN_ACTOR,
        DENIED_UNKNOWN_SOURCE,
        DENIED_UNKNOWN_OPERATION,
        DENIED_MALFORMED_PARAMS,
        DENIED_NON_INTEGER_AMOUNT,
        DENIED_NON_POSITIVE_AMOUNT,
        DENIED_DUPLICATE_PROPOSAL_ID,
        DENIED_DUPLICATE_ACTOR_SEQUENCE,
        DENIED_UNAUTHORISED,
        DENIED_INSUFFICIENT_SOURCE,
        DENIED_INSUFFICIENT_BALANCE,
        DENIED_UNBALANCED_EFFECTS,
        DENIED_SELF_TRANSFER,
    }
)


class Rejected(Exception):
    """Raised while shaping a proposal, carrying the reason to record."""

    def __init__(self, reason: str) -> None:
        if reason not in ALL:
            raise ValueError(f"unknown outcome reason: {reason!r}")
        super().__init__(reason)
        self.reason = reason
