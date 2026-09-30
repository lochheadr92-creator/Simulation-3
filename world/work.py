"""Wood supply tasks: seeing a yard short of the wood that visible shelters
need, fetching one pack from a grove and putting it in that yard.

A task keeps its yard and grove. It persists through interruptions like a
provisioning trip: needs, helping and housing take their turn first, and the
task continues when the person is idle again. It ends when the deposit
settles, when both known groves turn out empty, when the yard is seen full
(the wood stays with the carrier), or when the person dies (the wood stays
with the dead, conserved in the ledger).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping

from kernel import TickRecord
from kernel.proposals import OP_CLAIM, OP_DEPOSIT
from world.materials import DEPOSIT_WOOD, GATHER_WOOD, GO_WOOD, GO_YARD, YARD_CAPACITY, wood_pack
from world.storage import deposit_room

if TYPE_CHECKING:
    from world.config import WorldConfig
    from world.decide import Decision
    from world.observe import Observation
    from world.overlay import Overlay

FETCH = "fetch"
DELIVER = "deliver"
PHASES = (FETCH, DELIVER)
SUPPLY_TIMEOUT = 60   # a fetch with no wood collected for this long (since starting or the last collection) is given up

# a task: (phase, yard id, grove id, wanted units, tick of start or last collection, groves retried,
#          tick the task last acted — a gap means an interruption, after which the need is looked at again)
Task = tuple[str, str, str, int, int, int, int]
TASK_KINDS = frozenset({GO_WOOD, GATHER_WOOD, GO_YARD, DEPOSIT_WOOD})


def start_supply(observation: "Observation", config: "WorldConfig") -> Task | None:
    """Only with a yard in sight whose stock is below the shelter need in sight."""
    if not observation.yard_demand or observation.wood_source_id is None:
        return None
    demand = sum(need for _, need in observation.yard_demand)
    short = [(sid, stock) for sid, _, stock in observation.yards if stock is not None and stock < demand]
    if not short:
        return None
    sid, stock = short[0]
    wanted = min(wood_pack(observation.has_axe), demand - stock - observation.wood)
    if wanted <= 0 and observation.wood == 0:
        return None
    phase = DELIVER if observation.wood > 0 else FETCH
    return (phase, sid, observation.wood_source_id, max(wanted, 0), observation.tick, 0, observation.tick)


def supply_decision(observation: "Observation", config: "WorldConfig", choice: "Decision") -> "Decision | None":
    from world.config import wood_sites
    from world.decide import route_step
    from world.yard import _with, steps
    task = observation.supply_task
    fields: dict[str, Any] = {}
    if task is None:
        task = start_supply(observation, config)
        if task is None:
            return None
        fields["supply"] = task
    phase, yard, grove, wanted, since, retried, acted = task
    resumed = not fields and observation.tick - acted > 1   # idle again after something else took a turn
    yards = {sid: (pos, stock) for sid, pos, stock in observation.yards}
    groves = dict(wood_sites(config))
    if yard not in yards or grove not in groves:
        return replace(choice, reason=f"ending wood supply for {yard}: it is no longer known", supply_end="unknown")
    label = f"wood supply for {yard}"
    if phase == FETCH:
        if observation.tick - since >= SUPPLY_TIMEOUT:
            return replace(choice, reason=f"ending {label}: no wood collected in the {observation.tick - since} ticks since it started",
                           supply_end="timeout")
        stock_seen = yards[yard][1]
        if stock_seen is not None and resumed:
            demand = sum(need for _, need in observation.yard_demand)
            if demand == 0 or stock_seen >= demand:
                what = "no shelter in sight needs wood" if demand == 0 else f"the yard holds {stock_seen} and the shelters in sight need {demand}"
                return replace(choice, reason=f"ending {label}: demand met, {what}", supply_end="demand met")
        site = groves[grove]
        if observation.position != site:
            return _with(choice, GO_WOOD, f"{label}; walking to {grove}", target=grove,
                         step=route_step(observation, site, config), **fields)
        stock = dict(observation.groves_seen).get(grove, 0)
        if stock > 0:
            amount = min(wanted, stock, wood_pack(observation.has_axe))
            tool = " with the axe" if observation.has_axe else ""
            return _with(choice, GATHER_WOOD, f"{label}; gathering {amount} wood at {grove}{tool}",
                         amount=amount, target=grove, **fields)
        others = sorted((steps(site, pos), sid) for sid, pos in groves.items() if sid != grove)
        if retried == 0 and others:
            other = others[0][1]
            return _with(choice, GO_WOOD, f"{label}; {grove} has no wood left, trying {other}", target=other,
                         step=route_step(observation, groves[other], config),
                         supply=(FETCH, yard, other, wanted, since, 1, observation.tick))
        return replace(choice, reason=f"ending {label}: {grove} has no wood left and no other grove to try",
                       supply_end="empty groves")
    pos, stock = yards[yard]
    if observation.position != pos:
        return _with(choice, GO_YARD, f"{label}; carrying {observation.wood} wood to the yard", target=yard,
                     step=route_step(observation, pos, config), **fields)
    if observation.wood == 0:
        return replace(choice, reason=f"ending {label}: nothing left to deliver", supply_end="empty-handed")
    room = deposit_room(observation.wood, stock or 0, YARD_CAPACITY)
    if room == 0:
        return replace(choice, reason=f"ending {label}: the yard holds {stock}, its capacity; keeping the wood",
                       supply_end="yard full")
    return _with(choice, DEPOSIT_WOOD, f"{label}; putting {room} wood in the yard (it holds {stock})",
                 amount=room, target=yard, **fields)


def update_supply(previous: "Overlay", current: "Overlay", decisions: Mapping[str, "Decision"],
                  record: TickRecord) -> tuple[dict[str, Task], dict[str, int]]:
    """Next tasks, and the per-person count of completed wood deliveries."""
    tasks = dict(previous.supply_tasks)
    deliveries = dict(previous.deliveries)
    accepted = {(out.actor, out.operation) for out in record.outcomes if out.accepted}
    for actor, decision in decisions.items():
        if decision.supply is not None:
            tasks[actor] = decision.supply
        if decision.supply_end is not None:
            tasks.pop(actor, None)
        if decision.kind == DEPOSIT_WOOD and (actor, OP_DEPOSIT) in accepted:
            deliveries[actor] = deliveries.get(actor, 0) + 1
    for actor in list(tasks):
        decision = decisions.get(actor)
        if not current.alive(actor):
            tasks.pop(actor)
        elif decision is not None and decision.kind == DEPOSIT_WOOD and (actor, OP_DEPOSIT) in accepted:
            tasks.pop(actor)
        elif (decision is not None and decision.kind == GATHER_WOOD and (actor, OP_CLAIM) in accepted
              and tasks[actor][0] == FETCH):
            tasks[actor] = (DELIVER,) + tuple(tasks[actor][1:4]) + (current.tick - 1,) + tuple(tasks[actor][5:6]) + (current.tick - 1,)
        elif decision is not None and decision.kind in TASK_KINDS:
            tasks[actor] = tuple(tasks[actor][:6]) + (current.tick - 1,)
    return tasks, deliveries
