"""World processes: the rules applied after settlement, in a fixed order.

  0. errands    a request made this tick waits for an answer; one that was
                already waiting has now been answered or has lapsed, so it is
                gone. Agreeing takes on an errand, which lasts until the unit
                is handed over or the person who asked dies
  1. movement   a person who decided to step is now on that cell, unless the
                rough cell under them still owes a tick: rough ground costs an
                extra tick, so stepping onto it holds the next step back
  2. hunger     hunger' = max(0, hunger + rate - satiation * units eaten);
                only units the kernel actually settled as consumed count
  2a. shelter   anyone who decided to build now has a shelter on their home
                cell, for good; a tick that ends on a shelter spot or on any
                built shelter adds shelter_relief less hunger and thirst
  2b. cold      warmth on: a tick that ends on the person's own home cell
                (their shelter) takes `warming` off their cold, and any other
                tick adds `cold_rate`, whatever they decided; floored at zero
  3. death      hunger' >= death_at ends the person at this tick, as does
                thirst or cold reaching its own lethal level; the needs and
                the position freeze, their held units stay in the ledger
  4. renewal    every `renewal_every` ticks each food source gains
                `renewal_amount` up to `source_cap`, and with water on each
                water source does the same with the water levers (food
                sources first, then water, each in id order); this is the one
                production rule, and it is recorded on the tick line and
                re-checked by the reader

Needs never pause: a rejected claim or an empty source leaves hunger rising
(DOCTRINE 1). Production is the only way stock enters the world and it goes
through the kernel's own validated constructor, never a balance write.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from kernel import Source, TickRecord, WorldState
from kernel.proposals import OP_CONSUME, OP_TRANSFER
from kernel.state import SINK_ACCOUNT, sink_account

from world.config import WATER, WorldConfig
from world.decide import AGREE, ASK, BUILD, Decision
from world.overlay import Overlay


@dataclass(frozen=True)
class Processed:
    overlay: Overlay
    ledger: WorldState                       # the kernel state the next tick starts from
    production: tuple[dict[str, Any], ...]   # empty when nothing was produced
    eaten: Mapping[str, int]
    died: tuple[str, ...]


def _consumed(record: TickRecord, sink: str) -> dict[str, int]:
    """Units each person consumed into `sink` this tick, from accepted consume outcomes only."""
    out: dict[str, int] = {}
    for outcome in record.outcomes:
        if outcome.accepted and outcome.operation == OP_CONSUME:
            amount = sum(e.delta for e in outcome.effects if e.account == sink and e.delta > 0)
            if amount:
                out[outcome.actor] = out.get(outcome.actor, 0) + amount
    return out


def units_eaten(record: TickRecord) -> dict[str, int]:
    """Food eaten: consumption into the base sink only (drinking is not eating)."""
    return _consumed(record, SINK_ACCOUNT)


def units_drunk(record: TickRecord) -> dict[str, int]:
    return _consumed(record, sink_account(WATER))


def settled_pairs(overlay: Overlay, config: WorldConfig) -> list[tuple[str, str]]:
    """Pairs standing on adjacent cells who are both doing well: a finished
    shelter of their own, and no need calling."""
    homes_built = set(overlay.shelters)

    def well(actor: str) -> bool:
        if config.childhood_on and overlay.age.get(actor, config.adult_at) < config.adult_at:
            return False                                   # a child is nobody's partner
        return (overlay.alive(actor) and overlay.homes[actor] in homes_built
                and overlay.hunger[actor] < config.hungry_at
                and (not config.water_on or overlay.thirst[actor] < config.thirsty_at)
                and (not config.warmth_on or overlay.cold[actor] < config.cold_at))

    living = [actor for actor in overlay.roster if well(actor)]
    out = []
    for i, a in enumerate(living):
        for b in living[i + 1:]:
            (ax, ay), (bx, by) = overlay.positions[a], overlay.positions[b]
            if abs(ax - bx) + abs(ay - by) == 1:
                out.append((a, b))
    return out


def free_cell_near(origin: tuple[int, int], taken: set[tuple[int, int]], config: WorldConfig):
    """The nearest cell nobody lives on and no source occupies, by distance then
    row then column, so a birth always lands in the same place for a given world."""
    cells = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) not in taken]
    if not cells:
        return None
    return min(cells, key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c[1], c[0]))


def eased(rate: int, relief: int) -> int:
    """A need's rate under shelter. Never below 1 while the rate itself is at
    least 1: shelter makes a need slower, not survivable without eating."""
    return max(1, rate - relief) if rate >= 1 else rate


def advance(overlay: Overlay, decisions: Mapping[str, Decision], record: TickRecord,
            settled: WorldState, config: WorldConfig) -> Processed:
    if settled.tick != overlay.tick + 1:
        raise ValueError("settled ledger and overlay are not one tick apart")
    eaten = units_eaten(record)
    drunk = units_drunk(record)
    positions = dict(overlay.positions)
    hunger = dict(overlay.hunger)
    thirst = dict(overlay.thirst)
    cold = dict(overlay.cold)
    held = {actor: overlay.held.get(actor, 0) for actor in overlay.roster}   # full, or the overlay refuses it
    rough, shelter_spots = config.terrain()
    rough, shelter_spots = set(rough), set(shelter_spots)
    shelters = set(overlay.shelters)
    # a request is answered or lapses on the tick after it is made, so only
    # this tick's asking survives into the next one
    requests = {actor: d.target for actor, d in decisions.items() if d.kind == ASK and d.target}
    promises = dict(overlay.promises)
    promises.update({actor: d.target for actor, d in decisions.items() if d.kind == AGREE and d.target})
    for outcome in record.outcomes:
        if outcome.accepted and outcome.operation == OP_TRANSFER:
            promises.pop(outcome.actor, None)          # delivered, so the errand is over
    built = {actor: overlay.built.get(actor, 0) for actor in overlay.roster}
    age = {actor: overlay.age.get(actor, 0) for actor in overlay.roster} if config.childhood_on else {}
    died_at = dict(overlay.died_at)
    died: list[str] = []
    for actor in overlay.roster:
        if not overlay.alive(actor):
            continue
        decision = decisions.get(actor)
        owed = held.get(actor, 0)
        if owed > 0:
            # still climbing out of rough ground: the step waits a tick
            held[actor] = owed - 1
        elif decision is not None and decision.step is not None:
            positions[actor] = decision.step
            if decision.step in rough:
                held[actor] = 1
        if decision is not None and decision.kind == BUILD:
            built[actor] += 1                           # interrupted work is never lost
            if built[actor] >= config.build_ticks:
                shelters.add(overlay.homes[actor])      # permanent, and it shelters whoever stands there
        under = positions[actor]
        relief = config.shelter_relief if under in shelter_spots or under in shelters else 0
        # shelter slows a need, it never suspends one: a living person always gets
        # hungrier and thirstier, or a roof would be immortality.
        hunger[actor] = max(0, hunger[actor] + eased(config.hunger_rate, relief)
                            - config.satiation * eaten.get(actor, 0))
        if config.water_on:
            thirst[actor] = max(0, thirst[actor] + eased(config.thirst_rate, relief)
                                - config.quench * drunk.get(actor, 0))
        if config.childhood_on:
            age[actor] += 1
        if config.warmth_on:
            # Shelter is the person's own home cell, and this is where the tick left them.
            sheltered = positions[actor] == overlay.homes[actor]
            cold[actor] = max(0, cold[actor] - config.warming if sheltered else cold[actor] + config.cold_rate)
        if (hunger[actor] >= config.death_at
                or (config.water_on and thirst[actor] >= config.thirst_death_at)
                or (config.warmth_on and cold[actor] >= config.cold_death_at)):
            died_at[actor] = settled.tick
            died.append(actor)
    next_overlay = Overlay(tick=settled.tick, homes=overlay.homes, positions=positions, hunger=hunger,
                           yield_at=overlay.yield_at, died_at=died_at, thirst=thirst, cold=cold, held=held, built=built,
                           shelters=tuple(sorted(shelters)), together=dict(overlay.together),
                           age=age, parent=dict(overlay.parent),
                           requests=requests,
                           promises={who: owed for who, owed in promises.items() if owed not in died_at})

    production: list[dict[str, Any]] = []
    ledger = settled
    renewals = [(source_id, config.renewal_every, config.renewal_amount, config.source_cap)
                for source_id in config.food_source_ids()]
    renewals += [(source_id, config.water_renewal_every, config.water_renewal_amount, config.water_cap)
                 for source_id in config.water_source_ids()]
    for source_id, every, per_renewal, cap in renewals:
        if per_renewal > 0 and settled.tick % every == 0:
            source = ledger.sources[source_id]
            amount = min(per_renewal, cap - source.stock)
            if amount > 0:
                production.append({"source": source_id, "amount": amount})
                sources = dict(ledger.sources)
                sources[source_id] = replace(source, stock=source.stock + amount)
                ledger = replace(ledger, sources=sources)
    if config.births_on:
        next_overlay, ledger, born = _births(next_overlay, ledger, config)
        production.extend({"born": actor} for actor in born)

    return Processed(overlay=next_overlay, ledger=ledger, production=tuple(production),
                     eaten=eaten, died=tuple(died))


def _births(overlay: Overlay, ledger: WorldState, config: WorldConfig) -> tuple[Overlay, WorldState, list[str]]:
    """Count the ticks each settled pair spends side by side, and when one
    reaches together_ticks, add a person. The newcomer holds nothing: a birth
    is a mouth, not a meal, and no unit of anything is created by it."""
    adjacent = {f"{a}|{b}" for a, b in settled_pairs(overlay, config)}
    counts = {pair: overlay.together.get(pair, 0) + 1 for pair in adjacent}
    taken = set(overlay.homes.values()) | set(config.all_source_positions())
    homes, positions = dict(overlay.homes), dict(overlay.positions)
    hunger, yield_at = dict(overlay.hunger), dict(overlay.yield_at)
    thirst, cold = dict(overlay.thirst), dict(overlay.cold)
    held, built = dict(overlay.held), dict(overlay.built)
    age, parent = dict(overlay.age), dict(overlay.parent)
    born: list[str] = []
    roster_size = len(overlay.roster)
    for pair in sorted(counts):
        if counts[pair] < config.together_ticks:
            continue
        first = pair.split("|")[0]
        where = free_cell_near(overlay.homes[first], taken, config)
        if where is None:
            continue                                   # nowhere left to live
        counts[pair] = 0                               # they start counting again
        name = f"p{roster_size + len(born) + 1:02d}"
        born.append(name)
        taken.add(where)
        homes[name] = positions[name] = where
        hunger[name] = held[name] = built[name] = 0
        if config.childhood_on:
            age[name], parent[name] = 0, first
        yield_at[name] = (config.yield_set[len(overlay.roster) % len(config.yield_set)]
                          if config.yield_on else config.actors + 1)
        if config.water_on:
            thirst[name] = 0
        if config.warmth_on:
            cold[name] = 0
    if not born:
        return replace(overlay, together=counts), ledger, []
    sources = {sid: replace(source, authorised=frozenset(source.authorised) | set(born))
               for sid, source in ledger.sources.items()}
    balances = dict(ledger.balances) | {name: 0 for name in born}
    holdings = {resource: dict(held_map) | {name: 0 for name in born}
                for resource, held_map in ledger.holdings.items()}
    grown = replace(ledger, balances=balances, sources=sources, holdings=holdings)
    return (Overlay(tick=overlay.tick, homes=homes, positions=positions, hunger=hunger, yield_at=yield_at,
                    died_at=dict(overlay.died_at), thirst=thirst, cold=cold, held=held, built=built,
                    shelters=overlay.shelters, together=counts, age=age, parent=parent,
                    requests=dict(overlay.requests), promises=dict(overlay.promises)),
            grown, born)
