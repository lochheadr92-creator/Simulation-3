"""World processes: the rules applied after settlement, in a fixed order.

  1. movement   a person who decided to step is now on that cell, unless the
                rough cell under them still owes a tick: rough ground costs an
                extra tick, so stepping onto it holds the next step back
  2. hunger     hunger' = max(0, hunger + rate - satiation * units eaten);
                only units the kernel actually settled as consumed count
  2a. shelter   a tick that ends on a shelter spot adds shelter_relief less
                hunger and thirst than one that ends anywhere else
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

from kernel import TickRecord, WorldState
from kernel.proposals import OP_CONSUME
from kernel.state import SINK_ACCOUNT, sink_account

from world.config import WATER, WorldConfig
from world.decide import Decision
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
        relief = config.shelter_relief if positions[actor] in shelter_spots else 0
        hunger[actor] = max(0, hunger[actor] + max(0, config.hunger_rate - relief)
                            - config.satiation * eaten.get(actor, 0))
        if config.water_on:
            thirst[actor] = max(0, thirst[actor] + max(0, config.thirst_rate - relief)
                                - config.quench * drunk.get(actor, 0))
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
                           yield_at=overlay.yield_at, died_at=died_at, thirst=thirst, cold=cold, held=held)

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
    return Processed(overlay=next_overlay, ledger=ledger, production=tuple(production),
                     eaten=eaten, died=tuple(died))
