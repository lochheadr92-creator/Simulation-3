"""World processes: the rules applied after settlement, in a fixed order.

  1. movement   a person who decided to step is now on that cell
  2. hunger     hunger' = max(0, hunger + rate - satiation * units eaten);
                only units the kernel actually settled as consumed count
  3. death      hunger' >= death_at ends the person at this tick; hunger and
                position freeze, their held units stay in the ledger
  4. renewal    every `renewal_every` ticks the source gains `renewal_amount`
                up to `source_cap`; this is the one production rule, and it
                is recorded on the tick line and re-checked by the reader

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

from world.config import FOOD_SOURCE, WATER, WATER_SOURCE, WorldConfig
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
    died_at = dict(overlay.died_at)
    died: list[str] = []
    for actor in overlay.roster:
        if not overlay.alive(actor):
            continue
        decision = decisions.get(actor)
        if decision is not None and decision.step is not None:
            positions[actor] = decision.step
        hunger[actor] = max(0, hunger[actor] + config.hunger_rate - config.satiation * eaten.get(actor, 0))
        if config.water_on:
            thirst[actor] = max(0, thirst[actor] + config.thirst_rate - config.quench * drunk.get(actor, 0))
        if hunger[actor] >= config.death_at or (config.water_on and thirst[actor] >= config.thirst_death_at):
            died_at[actor] = settled.tick
            died.append(actor)
    next_overlay = Overlay(tick=settled.tick, homes=overlay.homes, positions=positions, hunger=hunger,
                           yield_at=overlay.yield_at, died_at=died_at, thirst=thirst)

    production: list[dict[str, Any]] = []
    ledger = settled
    if config.renewal_amount > 0 and settled.tick % config.renewal_every == 0:
        source = settled.sources[FOOD_SOURCE]
        amount = min(config.renewal_amount, config.source_cap - source.stock)
        if amount > 0:
            production.append({"source": FOOD_SOURCE, "amount": amount})
            sources = dict(settled.sources)
            sources[FOOD_SOURCE] = replace(source, stock=source.stock + amount)
            ledger = replace(settled, sources=sources)
    if config.water_on and config.water_renewal_amount > 0 and settled.tick % config.water_renewal_every == 0:
        well = ledger.sources[WATER_SOURCE]
        amount = min(config.water_renewal_amount, config.water_cap - well.stock)
        if amount > 0:
            production.append({"source": WATER_SOURCE, "amount": amount})
            sources = dict(ledger.sources)
            sources[WATER_SOURCE] = replace(well, stock=well.stock + amount)
            ledger = replace(ledger, sources=sources)
    return Processed(overlay=next_overlay, ledger=ledger, production=tuple(production),
                     eaten=eaten, died=tuple(died))
