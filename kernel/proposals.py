"""Proposals, the operations they name, and the balanced effects they expand to.

A transaction is a list of effects whose signed amounts sum to zero. An
operation is a named constructor for such a list. Expansion is pure shape: it
knows what an operation means, not whether the world can afford it or whether
the proposer is allowed to ask. Existence, authority, availability and
commitment all belong to settlement.

`claim` accepts several sources because a single-debit transaction has no second
leg to leave behind, and so cannot demonstrate all-or-nothing settlement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable

from kernel import reasons
from kernel.state import SINK_ACCOUNT, Effect, actor_account, source_account
from kernel.units import is_integer, is_valid_transaction_amount

OP_CLAIM = "claim"
OP_TRANSFER = "transfer"
OP_CONSUME = "consume"


def _freeze(value: Any) -> Any:
    """Copy `value` into an immutable form, so a caller cannot edit it afterwards."""
    if isinstance(value, Mapping):
        try:
            keys = sorted(value)
        except TypeError:
            keys = list(value)
        return MappingProxyType({key: _freeze(value[key]) for key in keys})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class Proposal:
    """One actor's request to run one transaction at one tick.

    `sequence` is the actor-local proposal sequence. The actor declares the order
    of its own proposals within the tick, and the engine validates that the
    declaration is unique. Carrying it on the proposal is what keeps resolution
    order independent of the order in which proposals happen to be collected.
    """

    proposal_id: str
    actor: str
    sequence: int
    operation: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id:
            raise ValueError("a proposal needs a non-empty identity")
        if not isinstance(self.actor, str) or not self.actor:
            raise ValueError("a proposal needs a non-empty actor identity")
        if not is_integer(self.sequence) or self.sequence < 0:
            raise ValueError(f"an actor-local sequence must be an integer of zero or more, got {self.sequence!r}")
        if not isinstance(self.operation, str) or not self.operation:
            raise ValueError("a proposal needs a non-empty operation name")
        if not isinstance(self.params, Mapping):
            raise ValueError("proposal parameters must be a mapping")
        for key in self.params:
            if not isinstance(key, str):
                raise ValueError("proposal parameter names must be strings")
        object.__setattr__(self, "params", _freeze(self.params))


def _ordered(effects: list[Effect]) -> tuple[Effect, ...]:
    """Effects are recorded by account, not by the order the operation built them."""
    return tuple(sorted(effects, key=lambda effect: effect.account))


def _amount(params: Mapping[str, Any], name: str) -> int:
    if name not in params:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    amount = params[name]
    if not is_integer(amount):
        raise reasons.Rejected(reasons.DENIED_NON_INTEGER_AMOUNT)
    if not is_valid_transaction_amount(amount):
        raise reasons.Rejected(reasons.DENIED_NON_POSITIVE_AMOUNT)
    return amount


def expand_claim(proposal: Proposal) -> tuple[Effect, ...]:
    wanted = proposal.params.get("sources")
    if not isinstance(wanted, Mapping) or not wanted:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    if any(not isinstance(source_id, str) or not source_id for source_id in wanted):
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)

    taken = 0
    effects: list[Effect] = []
    for source_id in sorted(wanted):
        amount = _amount(wanted, source_id)
        taken += amount
        effects.append(Effect(source_account(source_id), -amount))
    effects.append(Effect(actor_account(proposal.actor), taken))
    return _ordered(effects)


def expand_transfer(proposal: Proposal) -> tuple[Effect, ...]:
    target = proposal.params.get("to")
    if not isinstance(target, str) or not target:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    amount = _amount(proposal.params, "amount")
    if target == proposal.actor:
        raise reasons.Rejected(reasons.DENIED_SELF_TRANSFER)
    return _ordered(
        [
            Effect(actor_account(proposal.actor), -amount),
            Effect(actor_account(target), amount),
        ]
    )


def expand_consume(proposal: Proposal) -> tuple[Effect, ...]:
    amount = _amount(proposal.params, "amount")
    return _ordered(
        [
            Effect(actor_account(proposal.actor), -amount),
            Effect(SINK_ACCOUNT, amount),
        ]
    )


EXPANDERS: dict[str, Callable[[Proposal], tuple[Effect, ...]]] = {
    OP_CLAIM: expand_claim,
    OP_TRANSFER: expand_transfer,
    OP_CONSUME: expand_consume,
}


def expand(proposal: Proposal) -> tuple[Effect, ...]:
    """The effects an operation means, or `Rejected` carrying the reason it does not."""
    expander = EXPANDERS.get(proposal.operation)
    if expander is None:
        raise reasons.Rejected(reasons.DENIED_UNKNOWN_OPERATION)
    return tuple(expander(proposal))


def claim(proposal_id: str, actor: str, sequence: int, *, sources: Mapping[str, int]) -> Proposal:
    """Take the named amounts from the named shared sources, as one transaction."""
    return Proposal(proposal_id, actor, sequence, OP_CLAIM, {"sources": dict(sources)})


def transfer(proposal_id: str, actor: str, sequence: int, *, to: str, amount: int) -> Proposal:
    """Give `amount` of the proposer's own holding to another actor."""
    return Proposal(proposal_id, actor, sequence, OP_TRANSFER, {"to": to, "amount": amount})


def consume(proposal_id: str, actor: str, sequence: int, *, amount: int) -> Proposal:
    """Spend `amount` of the proposer's own holding into the consumption sink."""
    return Proposal(proposal_id, actor, sequence, OP_CONSUME, {"amount": amount})
