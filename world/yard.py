"""Shared wood yards: seeing a neighbour's shelter short of wood, building a
small yard nearby, and taking wood from a yard for one's own shelter.

A yard is a kernel source of wood open to everyone. It appears only when its
builder finishes the work, through a production entry. Its position is then
known to all (like a home cache); its stock is known only in sight. An
unfinished yard belongs to its builder and is dropped if they die.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping

from kernel import Source, TickRecord, WorldState
from kernel.state import actor_account, sink_account, source_account
from world.materials import (BUILD_YARD, GATHER_WOOD, GO_WOOD, GO_YARD, TAKE_WOOD, WAIT_WOOD, WOOD, WOOD_PACK,
                             YARD_RANGE, YARD_WORK, remaining_wood, remaining_yard_wood, wood_pack, yard_cost, yard_id)
from world.storage import withdraw_amount

if TYPE_CHECKING:
    from world.config import WorldConfig
    from world.decide import Decision
    from world.observe import Observation
    from world.overlay import Overlay

Position = tuple[int, int]


def steps(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _in_view(origin: Position, target: Position, radius: int) -> bool:
    return max(abs(origin[0] - target[0]), abs(origin[1] - target[1])) <= radius


def demand_in_view(actor: str, origin: Position, overlay: "Overlay", config: "WorldConfig",
                   available: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    """Unfinished shelters whose home cell is in sight, with the wood their
    remaining work still needs. The owner's carried wood counts against it
    only when the owner is in sight too; unseen wood is not guessed."""
    radius = config.perception_radius
    shelters = set(overlay.shelters)
    found = []
    for owner in overlay.living:
        if owner == actor:
            continue
        home = overlay.homes[owner]
        if home in shelters or not _in_view(origin, home, radius):
            continue
        if config.childhood_on and overlay.age.get(owner, config.adult_at) < config.adult_at:
            continue
        need = remaining_wood(overlay.built.get(owner, 0), config.build_ticks)
        if _in_view(origin, overlay.positions[owner], radius):
            need -= available[actor_account(owner, WOOD)]
        if need > 0:
            found.append((owner, need))
    return tuple(sorted(found, key=lambda item: (steps(origin, overlay.homes[item[0]]), item[0])))


def yard_site_option(actor: str, origin: Position, overlay: "Overlay", config: "WorldConfig",
                     demand: tuple[tuple[str, int], ...]) -> Position | None:
    """The visible free cell nearest the first observed demand that could hold
    a yard: not rough, not a shelter spot, not a source, home, shelter or yard."""
    if not demand:
        return None
    radius = config.perception_radius
    rough, spots = config.terrain()
    taken = (set(rough) | set(spots) | set(config.all_source_positions()) | set(overlay.homes.values())
             | set(overlay.shelters) | set(overlay.yards.values())
             | {site for site, _ in overlay.yard_work.values()})
    goal = overlay.homes[demand[0][0]]
    cells = [(x, y) for y in range(max(0, origin[1] - radius), min(config.height, origin[1] + radius + 1))
             for x in range(max(0, origin[0] - radius), min(config.width, origin[0] + radius + 1))
             if (x, y) not in taken]
    if not cells:
        return None
    return min(cells, key=lambda c: (steps(c, goal), c[1], c[0]))


def yard_view(actor: str, origin: Position, overlay: "Overlay", config: "WorldConfig",
              available: Mapping[str, int]) -> dict[str, Any]:
    """The yard-related observation fields for one person."""
    radius = config.perception_radius
    yards = tuple((sid, pos, available[source_account(sid)] if _in_view(origin, pos, radius) else None)
                  for sid, pos in sorted(overlay.yards.items(), key=lambda item: (steps(origin, item[1]), item[0])))
    own = overlay.yard_work.get(actor)
    demand = demand_in_view(actor, origin, overlay, config, available)
    goal = overlay.homes[demand[0][0]] if demand else origin
    nearby = (own is not None
              or any(steps(goal, pos) <= YARD_RANGE for _, pos in overlay.yards.items())
              or any(steps(goal, site) <= YARD_RANGE and _in_view(origin, site, radius)
                     for who, (site, _) in overlay.yard_work.items() if who != actor))
    adult = not config.childhood_on or overlay.age.get(actor, config.adult_at) >= config.adult_at
    home_built = overlay.homes[actor] in set(overlay.shelters)
    option = (yard_site_option(actor, origin, overlay, config, demand)
              if adult and home_built and demand and not nearby and actor not in overlay.supply_tasks else None)
    from world.config import wood_sites
    groves_seen = tuple((sid, available[source_account(sid)]) for sid, pos in wood_sites(config)
                        if _in_view(origin, pos, radius))
    return {"yards": yards, "yard_demand": demand, "yard_nearby": nearby, "yard_site_option": option,
            "yard_site": own, "supply_task": overlay.supply_tasks.get(actor), "groves_seen": groves_seen,
            "yard_crowd": sum(1 for other in overlay.living if other != actor
                              and any(overlay.positions[other] == pos for _, pos in overlay.yards.items()
                                      if _in_view(origin, pos, radius)))}


def _with(choice: "Decision", kind: str, reason: str, **fields: Any) -> "Decision":
    from world.decide import Decision
    options = choice.candidates + ((kind,) if kind not in choice.candidates else ())
    scores = choice.scores + ((kind, (0, 1)),) if choice.scores is not None and kind not in dict(choice.scores) else choice.scores
    return Decision(choice.actor, kind, reason, options, scores=scores, **fields)


def fetch_wood(observation: "Observation", config: "WorldConfig", choice: "Decision", need: int,
               why: str, **fields: Any) -> "Decision":
    """Walk to the observed grove and gather up to `need` wood by hand."""
    from world.decide import route_step
    site = observation.wood_source
    if site is None:
        raise ValueError("yard work requires an observed grove landmark")
    kind = GO_WOOD if observation.position != site else GATHER_WOOD if observation.wood_stock else WAIT_WOOD
    amount = min(wood_pack(observation.has_axe), need, observation.wood_stock or 0) if kind == GATHER_WOOD else 0
    words = {GO_WOOD: f"walking to {observation.wood_source_id}",
             GATHER_WOOD: (f"gathering {amount} wood at {observation.wood_source_id} with the axe" if observation.has_axe
                           else f"gathering wood at {observation.wood_source_id}"),
             WAIT_WOOD: f"waiting at empty {observation.wood_source_id}"}[kind]
    return _with(choice, kind, f"{why}; {words}", amount=amount, target=observation.wood_source_id,
                 step=route_step(observation, site, config) if kind == GO_WOOD else None, **fields)


def yard_decision(observation: "Observation", config: "WorldConfig", choice: "Decision") -> "Decision | None":
    """Continue an unfinished yard, or start one where a shortage was seen."""
    from world.decide import route_step
    if observation.yard_site is not None:
        site, done = observation.yard_site
        start: dict[str, Any] = {}
        why = f"yard work at {site} needs wood"
    elif observation.yard_site_option is not None:
        site, done = observation.yard_site_option, 0
        start = {"yard_site": site}
        owner, need = observation.yard_demand[0]
        why = f"saw {owner}'s unfinished shelter short of {need} wood and no yard nearby; starting a yard at {site}"
    else:
        return None
    cost = yard_cost(done)
    if observation.wood < cost:
        return fetch_wood(observation, config, choice, remaining_yard_wood(done) - observation.wood, why, **start)
    if observation.position != site:
        return _with(choice, GO_YARD, f"{why}; walking to the yard site" if start else f"walking to the yard site at {site}",
                     target=yard_id(site), step=route_step(observation, site, config), **start)
    due = f"{cost} wood due for this work tick" if cost else "no wood due this tick"
    return _with(choice, BUILD_YARD, f"building a wood yard at {site}, work tick {done + 1} of {YARD_WORK}; {due}",
                 amount=cost, target=yard_id(site), **start)


def shelter_wood_from_yard(observation: "Observation", config: "WorldConfig", choice: "Decision") -> "Decision | None":
    """For one's own shelter: take wood from a yard seen with stock, or head for
    a known yard nearer than the grove. At an empty yard, None: use the grove."""
    from world.decide import route_step
    need = remaining_wood(observation.work_done, config.build_ticks) - observation.wood
    stocked = [(sid, pos, stock) for sid, pos, stock in observation.yards if stock]
    if stocked:
        sid, pos, stock = stocked[0]
        if observation.position == pos:
            return _with(choice, TAKE_WOOD, f"shelter work needs wood; taking wood from {sid}",
                         amount=withdraw_amount(WOOD_PACK, need, stock), target=sid)
        return _with(choice, GO_YARD, f"shelter work needs wood; {sid} has {stock} in sight, walking there",
                     target=sid, step=route_step(observation, pos, config))
    unseen = [(sid, pos) for sid, pos, stock in observation.yards if stock is None]
    if unseen and observation.wood_source is not None:
        sid, pos = unseen[0]
        if steps(observation.position, pos) < steps(observation.position, observation.wood_source):
            return _with(choice, GO_YARD, f"shelter work needs wood; {sid} is nearer than {observation.wood_source_id}, trying it first",
                         target=sid, step=route_step(observation, pos, config))
    return None


def apply_yards(overlay: "Overlay", ledger: WorldState, decisions: Mapping[str, "Decision"],
                record: TickRecord, config: "WorldConfig") -> tuple["Overlay", WorldState, list[dict[str, Any]]]:
    """Yard work progresses only when a due payment settled. A finished yard
    becomes a wood source through a production entry. A dead builder's
    unfinished yard is dropped."""
    from world.process import _consumed
    work = dict(overlay.yard_work)
    yards = dict(overlay.yards)
    sources = dict(ledger.sources)
    production: list[dict[str, Any]] = []
    spent = _consumed(record, sink_account(WOOD))
    for actor in sorted(decisions):
        decision = decisions[actor]
        if actor in overlay.died_at:
            continue
        if decision.yard_site is not None and actor not in work:
            work[actor] = (decision.yard_site, 0)
        if decision.kind == BUILD_YARD and actor in work:
            site, done = work[actor]
            if spent.get(actor, 0) >= yard_cost(done):
                done += 1
            if done < YARD_WORK:
                work[actor] = (site, done)
                continue
            work.pop(actor)
            sid = yard_id(site)
            if sid not in sources:
                sources[sid] = Source(stock=0, authorised=frozenset(ledger.roster), resource=WOOD)
                yards[sid] = site
                production.append({"source_created": sid, "resource": WOOD})
    for dead in overlay.died_at:
        work.pop(dead, None)
    return (replace(overlay, yards=yards, yard_work=work), replace(ledger, sources=sources), production)
