"""Validation, deterministic resolution, and atomic settlement.

This is the only write path to a balance. A domain cannot reach around it,
because no state object has a public mutator and settlement is the only code
that builds the next state.

The order of work follows the roadmap's tick algorithm:

1. the caller freezes the tick-start state and collects proposals against it;
2. shape, identity, authority and precondition validation, rejecting all
   proposals that share a duplicate identity regardless of arrival order;
3. authorised cancellation of reserved work;
4. surviving reserved completions, then new transactions and reservations;
5. validation of each whole transaction against remaining tick-start
   availability, staging balanced effects and committing all or none of each;
6. commit of the next state.

The roadmap's total key is (phase, rotated actor rank, actor-local sequence).
Cancellation is phase 0, completion phase 1, and new work phase 2.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from kernel import reasons
from kernel.canonical import digest as canonical_digest
from kernel.ordering import actor_ranks, rotated_roster
from kernel.outcomes import ProposalOutcome
from kernel.proposals import (
    OP_CANCEL, OP_COMPLETE, OP_RESERVE, Proposal, expand, requested_action, reserved_plan,
)
from kernel.state import (
    SINK_ACCOUNT,
    Effect,
    Reservation,
    Source,
    WorldState,
    actor_account,
    actor_of,
    is_actor_account,
    is_sink_account,
    is_source_account,
    resource_of,
    sink_account,
    source_account,
    source_of,
)


class IntegrityError(RuntimeError):
    """A declared invariant did not hold.

    This is a kernel defect, not a simulation outcome. It is raised, never
    clamped and never turned into a denial reason, because correctness cannot be
    switched off.
    """


@dataclass(frozen=True)
class Settlement:
    next_state: WorldState
    outcomes: tuple[ProposalOutcome, ...]
    rotated_roster: tuple[str, ...]


def effects_are_balanced(effects: Iterable[Effect]) -> bool:
    return sum(effect.delta for effect in effects) == 0


def _accounts_exist(effects: Iterable[Effect], state: WorldState) -> str | None:
    for effect in effects:
        account = effect.account
        named = resource_of(account)
        if named is not None and named not in state.holdings:
            return reasons.DENIED_UNKNOWN_RESOURCE
        if is_sink_account(account):
            continue
        if is_actor_account(account):
            if actor_of(account) not in state.balances:
                return reasons.DENIED_UNKNOWN_ACTOR
        elif is_source_account(account):
            if source_of(account) not in state.sources:
                return reasons.DENIED_UNKNOWN_SOURCE
        else:
            return reasons.DENIED_MALFORMED_PARAMS
    return None


def _authority(actor_id: str, effects: Iterable[Effect], state: WorldState) -> str | None:
    """Authority is checked per debited account, for the whole transaction.

    Crediting needs no authority: an actor may be given units unasked. Debiting
    the consumption sink is never permitted, so consumed units cannot return.
    """
    for effect in effects:
        if effect.delta >= 0:
            continue
        account = effect.account
        if is_sink_account(account):
            return reasons.DENIED_UNAUTHORISED
        if is_actor_account(account):
            if actor_of(account) != actor_id:
                return reasons.DENIED_UNAUTHORISED
        elif is_source_account(account):
            if not state.sources[source_of(account)].permits(actor_id):
                return reasons.DENIED_UNAUTHORISED
    return None


def _resources_balanced(effects: Iterable[Effect], state: WorldState) -> bool:
    """Each resource balances on its own. A source account moves its Source's
    resource; actor and sink accounts move the resource in their address."""
    sums: dict[str | None, int] = {}
    for effect in effects:
        if is_source_account(effect.account):
            resource = state.sources[source_of(effect.account)].resource
        else:
            resource = resource_of(effect.account)
        sums[resource] = sums.get(resource, 0) + effect.delta
    return all(total == 0 for total in sums.values())


def _shortfall(effects: Iterable[Effect], available: dict[str, int]) -> str | None:
    """The first account, by address, that the whole transaction cannot cover."""
    required: dict[str, int] = {}
    for effect in effects:
        if effect.delta < 0:
            required[effect.account] = required.get(effect.account, 0) - effect.delta
    for account in sorted(required):
        if available.get(account, 0) < required[account]:
            return account
    return None


def _phase(operation: str) -> int:
    return {OP_CANCEL: 0, OP_COMPLETE: 1}.get(operation, 2)


def settle(state: WorldState, proposals: Iterable[Proposal]) -> Settlement:
    submitted = tuple(proposals)
    for proposal in submitted:
        if not isinstance(proposal, Proposal):
            raise TypeError(f"expected a Proposal, got {type(proposal).__name__}")

    id_counts = Counter(proposal.proposal_id for proposal in submitted)
    order_counts = Counter((proposal.actor, proposal.order) for proposal in submitted)
    orders_by_actor: dict[str, set[int]] = {}
    for proposal in submitted:
        orders_by_actor.setdefault(proposal.actor, set()).add(proposal.order)
    sequences = {
        (actor, order): sequence
        for actor, orders in orders_by_actor.items()
        for sequence, order in enumerate(sorted(orders))
    }

    verdicts: dict[int, str] = {}
    committed: dict[int, tuple[Effect, ...]] = {}
    action_ids: dict[int, str] = {}
    reserved: dict[int, Reservation] = {}
    plans: dict[int, Proposal] = {}
    candidates: list[tuple[int, Proposal, tuple[Effect, ...]]] = []

    for index, proposal in enumerate(submitted):
        if proposal.operation in (OP_CANCEL, OP_COMPLETE):
            target = proposal.params.get("action_id")
            if isinstance(target, str) and target:
                action_ids[index] = target
        if id_counts[proposal.proposal_id] > 1:
            verdicts[index] = reasons.DENIED_DUPLICATE_PROPOSAL_ID
            continue
        if order_counts[(proposal.actor, proposal.order)] > 1:
            verdicts[index] = reasons.DENIED_DUPLICATE_ACTOR_SEQUENCE
            continue
        if proposal.actor not in state.balances:
            verdicts[index] = reasons.DENIED_UNKNOWN_ACTOR
            continue
        try:
            if proposal.operation in (OP_CANCEL, OP_COMPLETE):
                action_id = requested_action(proposal)
                reservation = state.reservations.get(action_id)
                if reservation is None:
                    raise reasons.Rejected(reasons.DENIED_UNKNOWN_ACTION)
                if reservation.actor != proposal.actor:
                    raise reasons.Rejected(reasons.DENIED_UNAUTHORISED)
                effects = reservation.effects if proposal.operation == OP_COMPLETE else ()
            else:
                plan = reserved_plan(proposal) if proposal.operation == OP_RESERVE else proposal
                plans[index] = plan
                effects = expand(plan)
        except reasons.Rejected as rejection:
            verdicts[index] = rejection.reason
            continue

        refusal = _accounts_exist(effects, state)
        if refusal is None:
            refusal = _authority(proposal.actor, effects, state)
        if refusal is None and not effects_are_balanced(effects):
            refusal = reasons.DENIED_UNBALANCED_EFFECTS
        if refusal is None and not _resources_balanced(effects, state):
            refusal = reasons.DENIED_RESOURCE_MISMATCH
        if refusal is not None:
            verdicts[index] = refusal
            continue

        candidates.append((index, proposal, effects))

    rotated = rotated_roster(state.roster, state.tick)
    ranks = actor_ranks(rotated)
    candidates.sort(key=lambda candidate: (
        _phase(candidate[1].operation), ranks[candidate[1].actor],
        sequences[(candidate[1].actor, candidate[1].order)],
    ))

    # Capture free stock before any release. Cancelling a hold cannot enable
    # an ordinary spend until the next tick, even though cancellation runs first.
    available = state.availability()
    reservations = dict(state.reservations)

    staged: dict[str, int] = {}
    for index, proposal, effects in candidates:
        if proposal.operation in (OP_CANCEL, OP_COMPLETE):
            action_id = action_ids[index]
            if action_id not in reservations:
                verdicts[index] = reasons.DENIED_UNKNOWN_ACTION
                continue
            del reservations[action_id]
            for effect in effects:
                staged[effect.account] = staged.get(effect.account, 0) + effect.delta
            verdicts[index] = reasons.ACCEPTED
            committed[index] = effects
            continue

        short = _shortfall(effects, available)
        if short is not None:
            verdicts[index] = (
                reasons.DENIED_INSUFFICIENT_SOURCE
                if is_source_account(short)
                else reasons.DENIED_INSUFFICIENT_BALANCE
            )
            continue
        # Acceptance reduces availability immediately. Credits never raise it:
        # a unit credited at this tick becomes spendable at the next tick start.
        for effect in effects:
            if effect.delta < 0:
                available[effect.account] += effect.delta
        if proposal.operation == OP_RESERVE:
            action_id = "action:" + canonical_digest({
                "tick": state.tick, "actor": proposal.actor,
                "sequence": sequences[(proposal.actor, proposal.order)],
            })
            if action_id in reservations:
                raise IntegrityError("reservation action identity collided")
            reservation = Reservation(action_id, proposal.actor, state.tick, plans[index].operation, effects)
            reservations[action_id] = reservation
            action_ids[index] = action_id
            reserved[index] = reservation
            committed[index] = ()
        else:
            for effect in effects:
                staged[effect.account] = staged.get(effect.account, 0) + effect.delta
            committed[index] = effects
        verdicts[index] = reasons.ACCEPTED

    next_state = _commit(state, staged, reservations)

    outcomes = [
        ProposalOutcome(
            proposal_id=proposal.proposal_id,
            actor=proposal.actor,
            sequence=sequences[(proposal.actor, proposal.order)],
            operation=proposal.operation,
            reason=verdicts[index],
            effects=committed.get(index, ()),
            action_id=action_ids.get(index),
            reservation=reserved.get(index),
        )
        for index, proposal in enumerate(submitted)
    ]
    unranked = len(rotated)
    outcomes.sort(
        key=lambda outcome: (
            _phase(outcome.operation),
            ranks.get(outcome.actor, unranked),
            outcome.actor,
            outcome.sequence,
            outcome.proposal_id,
            outcome.operation,
            outcome.action_id or "",
        )
    )

    return Settlement(
        next_state=next_state,
        outcomes=tuple(outcomes),
        rotated_roster=rotated,
    )


def _commit(
    state: WorldState, staged: dict[str, int],
    reservations: Mapping[str, Reservation] | None = None,
) -> WorldState:
    """Apply the staged effects together, after the declared rails pass."""
    known = (
        {actor_account(actor_id) for actor_id in state.balances}
        | {source_account(source_id) for source_id in state.sources}
        | {SINK_ACCOUNT}
        | {actor_account(actor_id, resource) for resource in state.holdings for actor_id in state.balances}
        | {sink_account(resource) for resource in state.holdings}
    )
    stray = set(staged) - known
    if stray:
        raise IntegrityError(f"settlement touched accounts outside the world: {sorted(stray)}")
    if sum(staged.values()) != 0:
        raise IntegrityError("committed effects do not sum to zero")

    balances = {
        actor_id: amount + staged.get(actor_account(actor_id), 0)
        for actor_id, amount in state.balances.items()
    }
    stocks = {
        source_id: source.stock + staged.get(source_account(source_id), 0)
        for source_id, source in state.sources.items()
    }
    consumed = state.consumed + staged.get(SINK_ACCOUNT, 0)
    holdings = {
        resource: {actor_id: amount + staged.get(actor_account(actor_id, resource), 0)
                   for actor_id, amount in amounts.items()}
        for resource, amounts in state.holdings.items()
    }
    consumed_by = {resource: amount + staged.get(sink_account(resource), 0)
                   for resource, amount in state.consumed_by.items()}

    negatives = (
        [f"actor {actor_id}" for actor_id, amount in balances.items() if amount < 0]
        + [f"source {source_id}" for source_id, stock in stocks.items() if stock < 0]
        + (["the consumption sink"] if consumed < 0 else [])
        + [f"actor {actor_id} {resource}" for resource, amounts in holdings.items()
           for actor_id, amount in amounts.items() if amount < 0]
        + [f"the {resource} sink" for resource, amount in consumed_by.items() if amount < 0]
    )
    if negatives:
        raise IntegrityError(f"settlement would leave a negative balance: {negatives}")

    try:
        next_state = WorldState(
            tick=state.tick + 1,
            balances=balances,
            sources={
                source_id: Source(stock=stocks[source_id], authorised=source.authorised, resource=source.resource)
                for source_id, source in state.sources.items()
            },
            consumed=consumed,
            reservations=state.reservations if reservations is None else reservations,
            holdings=holdings,
            consumed_by=consumed_by,
        )
    except ValueError as error:
        raise IntegrityError(f"settlement produced invalid reservation state: {error}") from error
    if next_state.totals() != state.totals():
        raise IntegrityError(
            f"settlement did not conserve the declared totals: {state.totals()} became {next_state.totals()}"
        )
    if next_state.roster != state.roster:
        raise IntegrityError("settlement changed the roster, which slices 1a/1b do not do")
    return next_state
