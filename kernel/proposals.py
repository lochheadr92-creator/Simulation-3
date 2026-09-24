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
from kernel.state import Effect, actor_account, is_resource_name, sink_account, source_account
from kernel.units import is_integer, is_valid_transaction_amount

OP_CLAIM = "claim"
OP_TRANSFER = "transfer"
OP_CONSUME = "consume"
OP_RESERVE = "reserve"
OP_COMPLETE = "complete"
OP_CANCEL = "cancel"


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

    `order` expresses the actor's intended ordering, not an assigned sequence.
    Settlement validates unique orders and assigns dense actor-local sequences
    from them, independently of the order proposals happen to be collected.
    """

    proposal_id: str
    actor: str
    order: int
    operation: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id:
            raise ValueError("a proposal needs a non-empty identity")
        if not isinstance(self.actor, str) or not self.actor:
            raise ValueError("a proposal needs a non-empty actor identity")
        if not is_integer(self.order) or self.order < 0:
            raise ValueError("an actor-local order must be an integer of zero or more")
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


def _resource(params: Mapping[str, Any]) -> str | None:
    """The optional `resource` parameter: absent means the base resource."""
    if "resource" not in params:
        return None
    if not is_resource_name(params["resource"]):
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    return params["resource"]


def expand_claim(proposal: Proposal) -> tuple[Effect, ...]:
    wanted = proposal.params.get("sources")
    if not isinstance(wanted, Mapping) or not wanted:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    if any(not isinstance(source_id, str) or not source_id for source_id in wanted):
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)

    resource = _resource(proposal.params)
    taken = 0
    effects: list[Effect] = []
    for source_id in sorted(wanted):
        amount = _amount(wanted, source_id)
        taken += amount
        effects.append(Effect(source_account(source_id), -amount))
    effects.append(Effect(actor_account(proposal.actor, resource), taken))
    return _ordered(effects)


def expand_transfer(proposal: Proposal) -> tuple[Effect, ...]:
    target = proposal.params.get("to")
    if not isinstance(target, str) or not target:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    amount = _amount(proposal.params, "amount")
    resource = _resource(proposal.params)
    if target == proposal.actor:
        raise reasons.Rejected(reasons.DENIED_SELF_TRANSFER)
    return _ordered(
        [
            Effect(actor_account(proposal.actor, resource), -amount),
            Effect(actor_account(target, resource), amount),
        ]
    )


def expand_consume(proposal: Proposal) -> tuple[Effect, ...]:
    amount = _amount(proposal.params, "amount")
    resource = _resource(proposal.params)
    return _ordered(
        [
            Effect(actor_account(proposal.actor, resource), -amount),
            Effect(sink_account(resource), amount),
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


def _with_resource(params: dict[str, Any], resource: str | None) -> dict[str, Any]:
    if resource is not None:
        params["resource"] = resource
    return params


def claim(proposal_id: str, actor: str, order: int, *, sources: Mapping[str, int],
          resource: str | None = None) -> Proposal:
    """Take the named amounts from the named shared sources, as one transaction.
    Every source must hold `resource` (None: the base resource)."""
    return Proposal(proposal_id, actor, order, OP_CLAIM, _with_resource({"sources": dict(sources)}, resource))


def transfer(proposal_id: str, actor: str, order: int, *, to: str, amount: int,
             resource: str | None = None) -> Proposal:
    """Give `amount` of the proposer's own holding to another actor."""
    return Proposal(proposal_id, actor, order, OP_TRANSFER, _with_resource({"to": to, "amount": amount}, resource))


def consume(proposal_id: str, actor: str, order: int, *, amount: int, resource: str | None = None) -> Proposal:
    """Spend `amount` of the proposer's own holding into the consumption sink."""
    return Proposal(proposal_id, actor, order, OP_CONSUME, _with_resource({"amount": amount}, resource))


def reserve(proposal_id: str, actor: str, order: int, *, operation: str, params: Mapping[str, Any]) -> Proposal:
    """Hold a claim, transfer or consumption plan for a later tick."""
    return Proposal(proposal_id, actor, order, OP_RESERVE, {"operation": operation, "params": params})


def complete(proposal_id: str, actor: str, order: int, *, action_id: str) -> Proposal:
    """Commit the owner's previously reserved plan exactly once."""
    return Proposal(proposal_id, actor, order, OP_COMPLETE, {"action_id": action_id})


def cancel(proposal_id: str, actor: str, order: int, *, action_id: str) -> Proposal:
    """Cancel the owner's reserved plan; its stock is free next tick."""
    return Proposal(proposal_id, actor, order, OP_CANCEL, {"action_id": action_id})


def reserved_plan(proposal: Proposal) -> Proposal:
    """Validate the wrapper before using the existing operation expanders."""
    operation = proposal.params.get("operation")
    params = proposal.params.get("params")
    if set(proposal.params) != {"operation", "params"} or not isinstance(params, Mapping):
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    if not isinstance(operation, str) or operation not in (OP_CLAIM, OP_TRANSFER, OP_CONSUME):
        raise reasons.Rejected(reasons.DENIED_UNKNOWN_OPERATION)
    if any(not isinstance(key, str) for key in params):
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    return Proposal(proposal.proposal_id, proposal.actor, proposal.order, operation, params)


def requested_action(proposal: Proposal) -> str:
    action_id = proposal.params.get("action_id")
    if set(proposal.params) != {"action_id"} or not isinstance(action_id, str) or not action_id:
        raise reasons.Rejected(reasons.DENIED_MALFORMED_PARAMS)
    return action_id
