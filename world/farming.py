"""Fields, crops and spoiled grain.

Everybody founding the world has a field beside their home: an empty kernel source of grain and a plot that says
what stands on it. Planting spends a seed (grain) through the kernel. The crop grows by a recorded production entry
when the plot ripens (faster in rain), and is harvested by an ordinary claim from the field's source. Soil wears with
each harvest and mends while it lies bare; a crop left standing rots and the loss is recorded; grain in somebody's hands
spoils a little at a time into a named sink. Grain feeds like food and keeps less well. Nothing here moves a unit
except settlement and a production entry the file records.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kernel.proposals import OP_CLAIM, OP_CONSUME
from kernel.state import actor_account, source_account
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

GRAIN = "grain"
GO_FIELD, PLANT, TEND, HARVEST = "go_field", "plant", "tend", "harvest"
FARM_KINDS = frozenset({GO_FIELD, PLANT, TEND, HARVEST})
STATES = ("bare", "growing", "ripe")
FARM_LEVERS = (("grow_ticks", 30), ("base_yield", 3), ("tend_max", 3), ("fallow_every", 8), ("harvest_wear", 20),
               ("rot_after", 40), ("spoil_every", 25), ("grain_satiation", 36), ("starting_grain", 1), ("farm_margin", 8),
               ("min_soil", 20))

FARMING = Feature(
    name="farming",
    summary="Everybody has a field: seed is planted, tended and harvested, soil wears, and stored grain spoils.",
    rule=(
        "Each founder has a field beside their home with soil of 100. Somebody idle and fit (not a child, not in a "
        "storm, with their own needs margin farm_margin ticks beyond the walk) who has grain plants a bare field "
        "whose soil is at least min_soil, spending one grain; tends a growing one until it has been tended tend_max "
        "times; and harvests a ripe one. A planted field grows one tick at a time, two in rain or a storm, and "
        "ripens after grow_ticks, when it gains base_yield grain, plus one for soil of 60 or more, minus one for "
        "soil under 30, plus one for tending, plus one for the farmer holding a hoe, never fewer than one. "
        "Harvesting takes everything standing; the soil loses harvest_wear and a bare field regains one soil "
        "point every fallow_every ticks. A crop left standing for rot_after ticks rots, and the loss is recorded. "
        "Every spoil_every ticks anybody holding three or more grain loses a third of it to spoilage, "
        "recorded as moving into a spoilage sink. Hungry people with no other food eat grain, which relieves "
        "grain_satiation hunger a unit. Everybody starts with starting_grain seed. Planting, tending and "
        "harvesting count as farming practice."),
    levers=FARM_LEVERS,
    tables={"states": list(STATES)},
)


@dataclass(frozen=True)
class Plot:
    owner: str
    x: int
    y: int
    state: str = "bare"
    grown: int = 0              # ticks of growth so far
    since: int = 0              # the tick it ripened
    soil: int = 100
    cared: int = 0              # times it has been tended this crop

    @property
    def cell(self) -> tuple[int, int]:
        return (self.x, self.y)

    @property
    def source(self) -> str:
        return field_id(self.owner)

    def canonical(self) -> list[Any]:
        return [self.owner, self.x, self.y, self.state, self.grown, self.since, self.soil, self.cared]

    @classmethod
    def from_canonical(cls, data: Any) -> "Plot":
        if not isinstance(data, (list, tuple)) or len(data) != 8:
            raise ValueError(f"a plot is owner, x, y, state, grown, since, soil, cared: {data!r}")
        owner, x, y, state, grown, since, soil, cared = data
        if (not isinstance(owner, str) or state not in STATES
                or any(type(n) is not int or n < 0 for n in (x, y, grown, since, cared)) or type(soil) is not int
                or not 0 <= soil <= 100):
            raise ValueError(f"a plot is not valid: {data!r}")
        return cls(owner, x, y, state, grown, since, soil, cared)


def field_id(owner: str) -> str:
    return f"field-{owner}"


def plot_of(plots: tuple[Plot, ...], owner: str) -> Plot | None:
    return next((p for p in plots if p.owner == owner), None)


def _spend(ledger: Any, resource: str, actor: str, units: int) -> Any:
    holdings = {r: dict(held) for r, held in ledger.holdings.items()}
    holdings[resource][actor] -= units
    consumed = dict(ledger.consumed_by)
    consumed[resource] += units
    return replace(ledger, holdings=holdings, consumed_by=consumed)


def advance_farming(previous: Any, current: Any, decisions: Mapping[str, Any], record: Any, ledger: Any,
                    config: "WorldConfig") -> tuple[tuple[Plot, ...], Any, list[dict[str, Any]]]:
    """The plots after one tick, the ledger after growth, rot and spoilage, and the production entries that say why."""
    now = previous.tick + 1
    tend_max, wear = config.lever("tend_max"), config.lever("harvest_wear")
    ok: dict[tuple[str, str], bool] = {}
    for outcome in record.outcomes:
        if outcome.operation in (OP_CONSUME, OP_CLAIM):
            ok[(outcome.actor, outcome.operation)] = outcome.accepted
    raining = previous.sky is not None and previous.sky.weather in ("rain", "storm")
    production: list[dict[str, Any]] = []
    plots: list[Plot] = []
    for p in previous.things.plots:
        d = decisions.get(p.owner)
        here = d is not None and previous.positions.get(p.owner) == p.cell
        if p.state == "bare" and here and d.kind == PLANT and ok.get((p.owner, OP_CONSUME)):
            p = replace(p, state="growing", grown=0, cared=0)
        elif p.state == "growing" and here and d.kind == TEND:
            p = replace(p, cared=min(tend_max, p.cared + 1))
        elif p.state == "ripe" and here and d.kind == HARVEST and ok.get((p.owner, OP_CLAIM)):
            p = replace(p, state="bare", grown=0, cared=0, soil=max(0, p.soil - wear))
        if p.state == "growing":
            p = replace(p, grown=p.grown + 1 + int(raining))
            if p.grown >= config.lever("grow_ticks"):
                hoe = ledger.holdings.get("hoe", {}).get(p.owner, 0) >= 1
                units = max(1, config.lever("base_yield") + (p.soil >= 60) - (p.soil < 30) + (p.cared >= tend_max)
                            + int(hoe))
                sources = dict(ledger.sources)
                sources[p.source] = replace(sources[p.source], stock=sources[p.source].stock + units)
                ledger = replace(ledger, sources=sources)
                production.append({"source": p.source, "amount": units})
                p = replace(p, state="ripe", since=now)
        elif p.state == "ripe" and now - p.since >= config.lever("rot_after"):
            left = ledger.sources[p.source].stock
            if left > 0:
                sources = dict(ledger.sources)
                sources[p.source] = replace(sources[p.source], stock=0)
                consumed = dict(ledger.consumed_by)
                consumed[GRAIN] += left
                ledger = replace(ledger, sources=sources, consumed_by=consumed)
                production.append({"rotted": p.source, "amount": left})
            p = replace(p, state="bare", grown=0, cared=0)
        elif p.state == "bare" and now % config.lever("fallow_every") == 0:
            p = replace(p, soil=min(100, p.soil + 1))
        plots.append(p)
    every = config.lever("spoil_every")
    for index, actor in enumerate(sorted(current.living)):
        units = ledger.holdings[GRAIN].get(actor, 0)
        if units >= 3 and (now + index) % every == 0:
            lose = units // 3
            ledger = _spend(ledger, GRAIN, actor, lose)
            production.append({"spoiled": actor, "item": GRAIN, "amount": lose})
    return tuple(plots), ledger, production
