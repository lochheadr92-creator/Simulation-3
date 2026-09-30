"""Stone and the basic stone axe.

Stone comes from one finite outcrop, gathered one unit per claim and only
while an axe is planned. An axe is a personal possession recorded in the saved
world, not a kernel resource: its wood and stone leave the ledger through
explicit consumes attributed to the crafter and tick. It has no durability,
repair or tiers. A dead person's axe stays recorded on them and is unusable.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping

from kernel import TickRecord
from kernel.proposals import OP_CLAIM
from kernel.state import actor_account, sink_account
from world.materials import (AXE_TIMEOUT, AXE_WORK, CRAFT_AXE, GATHER_STONE, GATHER_WOOD, GO_STONE, GO_WOOD, STONE,
                             STONE_PACK, WAIT_WOOD, WOOD, axe_cost)

if TYPE_CHECKING:
    from world.config import WorldConfig
    from world.decide import Decision
    from world.observe import Observation
    from world.overlay import Overlay

Position = tuple[int, int]
# kinds a plan issues itself; a gap in them means something else took a turn
PLAN_KINDS = frozenset({GO_WOOD, GATHER_WOOD, WAIT_WOOD, GO_STONE, GATHER_STONE, CRAFT_AXE, "home"})


def tools_view(actor: str, origin: Position, overlay: "Overlay", config: "WorldConfig",
               available: Mapping[str, int]) -> dict[str, Any]:
    from world.config import stone_sites
    from world.observe import target_source
    sid, site, stock = target_source(origin, stone_sites(config), config.perception_radius, available)
    return {"stone": available[actor_account(actor, STONE)], "stone_source_id": sid, "stone_source": site,
            "stone_stock": stock, "has_axe": actor in overlay.axes, "axe_plan": overlay.axe_work.get(actor),
            "deliveries": overlay.deliveries.get(actor, 0)}


def axe_worthwhile(observation: "Observation", config: "WorldConfig") -> bool:
    """Only somebody who has already delivered wood to a yard, and now sees a
    yard and shelters short of wood again, expects to gather enough to repay an axe."""
    return (config.axe_on and not observation.has_axe and observation.axe_plan is None
            and observation.deliveries >= 1 and bool(observation.yard_demand)
            and any(stock is not None for _, _, stock in observation.yards)
            and observation.stone_source is not None)


def axe_decision(observation: "Observation", config: "WorldConfig", choice: "Decision") -> "Decision | None":
    """Carry on a planned axe: wood in hand, then stone, then three craft ticks at home."""
    from world.decide import HOME, route_step
    from world.yard import _with, fetch_wood
    if observation.axe_plan is not None:
        done, since, acted = observation.axe_plan
        start: dict[str, Any] = {}
    elif axe_worthwhile(observation, config):
        done, since, acted, start = 0, observation.tick, observation.tick, {"axe_start": True}
    else:
        return None
    resumed = not start and observation.tick - acted > 1
    label = f"axe plan (craft tick {done} of {AXE_WORK})"
    if start:
        label = (f"planning an axe: {observation.deliveries} wood deliver{'y' if observation.deliveries == 1 else 'ies'} made "
                 f"and {observation.yard_demand[0][0]}'s shelter still short of wood")
    cost = axe_cost(done)
    needs_wood = cost is not None and cost[0] == WOOD and observation.wood < cost[1]
    needs_stone = done <= 1 and observation.stone < 1
    nothing_yet = done == 0 and observation.wood == 0 and observation.stone == 0
    if resumed and nothing_yet and not observation.yard_demand and any(stock is not None for _, _, stock in observation.yards):
        return replace(choice, reason="giving up the axe plan before collecting anything: the yard is in sight and no shelter in sight needs wood",
                       axe_end="no demand")
    if (needs_wood or needs_stone) and not start and observation.tick - since >= AXE_TIMEOUT:
        last = "since it started" if nothing_yet else "since the last material was collected"
        return replace(choice, reason=f"giving up the axe plan: no material collected in the {observation.tick - since} ticks {last}",
                       axe_end="timeout")
    if needs_wood:
        return fetch_wood(observation, config, choice, 1 - observation.wood, f"{label}; needs 1 wood", **start)
    if needs_stone:
        site = observation.stone_source
        if observation.position != site:
            return _with(choice, GO_STONE, f"{label}; walking to {observation.stone_source_id} for 1 stone",
                         target=observation.stone_source_id, step=route_step(observation, site, config), **start)
        if observation.stone_stock:
            return _with(choice, GATHER_STONE, f"{label}; taking 1 stone at {observation.stone_source_id}",
                         amount=min(STONE_PACK, 1 - observation.stone, observation.stone_stock), target=observation.stone_source_id, **start)
        return replace(choice, reason=f"giving up the axe plan: {observation.stone_source_id} is bare and stone does not renew",
                       axe_end="no stone")
    if observation.position != observation.home:
        return _with(choice, HOME, f"{label}; carrying the materials home to craft",
                     step=route_step(observation, observation.home, config), **start)
    due = f"{cost[1]} {cost[0]} due" if cost else "nothing due"
    return _with(choice, CRAFT_AXE, f"{label}; crafting at home, {due} this tick",
                 amount=cost[1] if cost else 0, resource=cost[0] if cost else None, **start)


def apply_tools(overlay: "Overlay", decisions: Mapping[str, "Decision"], record: TickRecord) -> "Overlay":
    """Craft progress needs the due payment settled. Finishing records the axe.
    A dead crafter's plan is dropped; paid materials stay consumed."""
    from world.process import _consumed
    work = dict(overlay.axe_work)
    axes = set(overlay.axes)
    spent = {res: _consumed(record, sink_account(res)) for res in (WOOD, STONE)}
    collected = {out.actor for out in record.outcomes if out.accepted and out.operation == OP_CLAIM}
    now = overlay.tick - 1   # the tick these decisions were made in
    for actor in sorted(decisions):
        decision = decisions[actor]
        if actor in overlay.died_at:
            continue
        if decision.axe_start and actor not in work:
            work[actor] = (0, now, now)
        if decision.axe_end is not None:
            work.pop(actor, None)
        if actor in work and decision.kind in PLAN_KINDS:
            work[actor] = (work[actor][0], work[actor][1], now)
        if actor in work and decision.kind in (GATHER_WOOD, GATHER_STONE) and actor in collected:
            work[actor] = (work[actor][0], now, now)          # a material collected: the timeout starts again
        if decision.kind == CRAFT_AXE and actor in work:
            done, since, acted = work[actor]
            cost = axe_cost(done)
            if cost is None or spent[cost[0]].get(actor, 0) >= cost[1]:
                done += 1
            if done >= AXE_WORK:
                work.pop(actor)
                axes.add(actor)
            else:
                work[actor] = (done, since, acted)
    for dead in overlay.died_at:
        work.pop(dead, None)
    return replace(overlay, axe_work=work, axes=tuple(sorted(axes)))
