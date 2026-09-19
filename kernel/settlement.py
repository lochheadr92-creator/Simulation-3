"""Validation, deterministic resolution, and atomic settlement.

This is the only write path to a balance. A domain cannot reach around it,
because no state object has a public mutator and settlement is the only code
that builds the next state.

The order of work follows the roadmap's tick algorithm:

1. the caller freezes the tick-start state and collects proposals against it;
2. shape, identity, authority and precondition validation, rejecting all
   proposals that share a duplicate identity regardless of arrival order;
3. cancellation of reserved work, which does not exist until slice 1b;
4. resolution in the declared total order;
5. validation of each whole transaction against remaining tick-start
   availability, staging balanced effects and committing all or none of each;
6. commit of the next state.

The roadmap's total key is (phase, rotated actor rank, actor-local sequence).
The phase term is constant here because reserved completions arrive in slice 1b,
so the key below carries its two remaining components.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from kernel import reasons
from kernel.ordering import actor_ranks, rotated_roster
from kernel.outcomes import ProposalOutcome
from kernel.proposals import Proposal, expand
from kernel.state import (
    SINK_ACCOUNT,
    Effect,
    Source,
    WorldState,
    actor_account,
    actor_of,
    is_actor_account,
    is_source_account,
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
        if account == SINK_ACCOUNT:
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
        if account == SINK_ACCOUNT:
            return reasons.DENIED_UNAUTHORISED
        if is_actor_account(account):
            if actor_of(account) != actor_id:
                return reasons.DENIED_UNAUTHORISED
        elif is_source_account(account):
            if not state.sources[source_of(account)].permits(actor_id):
                return reasons.DENIED_UNAUTHORISED
    return None


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
    candidates: list[tuple[int, Proposal, tuple[Effect, ...]]] = []

    for index, proposal in enumerate(submitted):
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
            effects = expand(proposal)
        except reasons.Rejected as rejection:
            verdicts[index] = rejection.reason
            continue

        refusal = _accounts_exist(effects, state)
        if refusal is None:
            refusal = _authority(proposal.actor, effects, state)
        if refusal is None and not effects_are_balanced(effects):
            refusal = reasons.DENIED_UNBALANCED_EFFECTS
        if refusal is not None:
            verdicts[index] = refusal
            continue

        candidates.append((index, proposal, effects))

    rotated = rotated_roster(state.roster, state.tick)
    ranks = actor_ranks(rotated)
    candidates.sort(key=lambda candidate: (ranks[candidate[1].actor], sequences[(candidate[1].actor, candidate[1].order)]))

    available = {actor_account(actor_id): amount for actor_id, amount in state.balances.items()}
    available.update(
        {source_account(source_id): source.stock for source_id, source in state.sources.items()}
    )
    available[SINK_ACCOUNT] = 0

    staged: dict[str, int] = {}
    for index, proposal, effects in candidates:
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
            staged[effect.account] = staged.get(effect.account, 0) + effect.delta
        verdicts[index] = reasons.ACCEPTED
        committed[index] = effects

    next_state = _commit(state, staged)

    outcomes = [
        ProposalOutcome(
            proposal_id=proposal.proposal_id,
            actor=proposal.actor,
            sequence=sequences[(proposal.actor, proposal.order)],
            operation=proposal.operation,
            reason=verdicts[index],
            effects=committed.get(index, ()),
        )
        for index, proposal in enumerate(submitted)
    ]
    unranked = len(rotated)
    outcomes.sort(
        key=lambda outcome: (
            ranks.get(outcome.actor, unranked),
            outcome.actor,
            outcome.sequence,
            outcome.proposal_id,
            outcome.operation,
        )
    )

    return Settlement(
        next_state=next_state,
        outcomes=tuple(outcomes),
        rotated_roster=rotated,
    )


def _commit(state: WorldState, staged: dict[str, int]) -> WorldState:
    """Apply the staged effects together, after the declared rails pass."""
    known = (
        {actor_account(actor_id) for actor_id in state.balances}
        | {source_account(source_id) for source_id in state.sources}
        | {SINK_ACCOUNT}
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

    negatives = (
        [f"actor {actor_id}" for actor_id, amount in balances.items() if amount < 0]
        + [f"source {source_id}" for source_id, stock in stocks.items() if stock < 0]
        + (["the consumption sink"] if consumed < 0 else [])
    )
    if negatives:
        raise IntegrityError(f"settlement would leave a negative balance: {negatives}")

    next_state = WorldState(
        tick=state.tick + 1,
        balances=balances,
        sources={
            source_id: Source(stock=stocks[source_id], authorised=source.authorised)
            for source_id, source in state.sources.items()
        },
        consumed=consumed,
    )
    if next_state.total() != state.total():
        raise IntegrityError(
            f"settlement did not conserve the declared total: {state.total()} became {next_state.total()}"
        )
    if next_state.roster != state.roster:
        raise IntegrityError("settlement changed the roster, which slice 1a does not do")
    return next_state
