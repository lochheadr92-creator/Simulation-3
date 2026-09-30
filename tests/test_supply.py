"""Wood supply tasks: started on seen demand and shortage, kept through
interruptions, ended on the deposit, on empty groves or at death."""
from dataclasses import replace

from kernel import Engine, Source
from world.config import WorldConfig, genesis, wood_sites
from world.decide import decide
from world.materials import DEPOSIT_WOOD, GATHER_WOOD, GO_WOOD, GO_YARD, WOOD, yard_id
from world.observe import observe
from world.run import world_step
from world.work import DELIVER, FETCH

YARD = (1, 6)
SID = yard_id(YARD)


def scene(stock=0, **changes):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True, actors=3, terrain_on=False, water_on=False,
                      warmth_on=False, births_on=False, offers_on=False, hunger_rate=0, **changes)
    ledger, overlay = genesis(cfg)
    sources = dict(ledger.sources)
    sources[SID] = Source(stock=stock, authorised=frozenset(ledger.roster), resource=WOOD)
    ledger = replace(ledger, sources=sources)
    # p02's shelter is finished; p02 idles at (1,5) with the yard and p01's unbuilt home (0,7) in sight
    overlay = replace(overlay, yards={SID: YARD}, shelters=(overlay.homes['p02'],),
                      built={p: (12 if p == 'p02' else 0) for p in overlay.roster}, positions={**overlay.positions, 'p02': (1, 5)})
    return cfg, ledger, overlay


def groves(ledger, **stocks):
    return replace(ledger, sources={s: replace(v, stock=stocks.get(s, v.stock)) if v.resource == WOOD and s != SID else v
                                    for s, v in ledger.sources.items()})


def test_task_starts_only_on_seen_demand_and_shortage():
    cfg, ledger, overlay = scene()
    choice = decide(observe('p02', ledger, overlay, cfg), cfg)
    assert choice.kind == GO_WOOD and choice.supply == (FETCH, SID, 'wood', 3, 0, 0, 0)
    assert 'wood supply for yard-1-6' in choice.reason
    covered = decide(observe('p02', groves(ledger), replace(overlay, yards={SID: YARD}), cfg), cfg)
    assert covered.supply is not None
    assert decide(observe('p02', ledger, replace(overlay, shelters=(overlay.homes['p01'], overlay.homes['p02'])), cfg), cfg).supply is None
    full = scene(stock=3)
    assert decide(observe('p02', full[1], full[2], cfg), cfg).supply is None
    partial = scene(stock=1)
    assert decide(observe('p02', partial[1], partial[2], cfg), cfg).supply[3] == 2
    out_of_sight = replace(overlay, positions={**overlay.positions, 'p02': (7, 1)})
    assert decide(observe('p02', ledger, out_of_sight, cfg), cfg).supply is None
    carrying = replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 2}})
    choice = decide(observe('p02', carrying, overlay, cfg), cfg)
    assert choice.kind == GO_YARD and choice.supply[0] == DELIVER


def test_task_is_recorded_survives_hunger_and_resumes_then_ends_on_the_deposit():
    cfg, ledger, overlay = scene()
    engine = Engine(ledger)
    s = world_step(engine, overlay, cfg)
    engine, overlay = s.engine, s.processed.overlay
    assert overlay.supply_tasks == {'p02': (FETCH, SID, 'wood', 3, 0, 0, 0)}
    hungry = replace(overlay, hunger={**overlay.hunger, 'p02': cfg.hungry_at})
    choice = decide(observe('p02', engine.state, hungry, cfg), cfg)
    assert choice.kind == 'eat' and choice.supply is None
    s = world_step(engine, hungry, cfg)
    engine, overlay = s.engine, s.processed.overlay
    assert overlay.supply_tasks['p02'][0] == FETCH
    for _ in range(30):
        choice = decide(observe('p02', engine.state, overlay, cfg), cfg)
        s = world_step(engine, overlay, cfg)
        engine, overlay = s.engine, s.processed.overlay
        if choice.kind == GATHER_WOOD:
            assert choice.amount == 3 and overlay.supply_tasks['p02'][0] == DELIVER
        if choice.kind == DEPOSIT_WOOD:
            break
    assert choice.kind == DEPOSIT_WOOD and engine.state.sources[SID].stock == 3
    assert not overlay.supply_tasks and engine.state.holdings[WOOD]['p02'] == 0
    assert engine.state.totals() == ledger.totals()


def test_empty_groves_retry_once_then_end_with_a_reason():
    cfg, ledger, overlay = scene()
    grove, site = wood_sites(cfg)[0]
    empty = groves(ledger, wood=0, wood2=0)
    at_grove = replace(overlay, positions={**overlay.positions, 'p02': site},
                       supply_tasks={'p02': (FETCH, SID, grove, 3, 0, 0, 0)})
    choice = decide(observe('p02', empty, at_grove, cfg), cfg)
    assert choice.kind == GO_WOOD and choice.target == 'wood2' and choice.supply == (FETCH, SID, 'wood2', 3, 0, 1, 0)
    retried = replace(at_grove, supply_tasks={'p02': (FETCH, SID, grove, 3, 0, 1, 0)})
    choice = decide(observe('p02', empty, retried, cfg), cfg)
    assert choice.supply_end == 'empty groves' and 'no wood left' in choice.reason
    s = world_step(Engine(empty), retried, cfg)
    assert not s.processed.overlay.supply_tasks
    stale = replace(overlay, supply_tasks={'p02': (FETCH, SID, grove, 3, 0, 0, 0)}, tick=60)
    choice = decide(observe('p02', replace(ledger, tick=60), stale, cfg), cfg)
    assert choice.supply_end == 'timeout' and '60 ticks since it started' in choice.reason


def test_full_yard_keeps_the_wood_and_death_ends_the_task():
    cfg, ledger, overlay = scene(stock=6)
    carrying = replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 3}})
    at_yard = replace(overlay, positions={**overlay.positions, 'p02': YARD},
                      supply_tasks={'p02': (DELIVER, SID, 'wood', 3, 0, 0, 0)})
    choice = decide(observe('p02', carrying, at_yard, cfg), cfg)
    assert choice.supply_end == 'yard full' and choice.kind != DEPOSIT_WOOD
    s = world_step(Engine(carrying), at_yard, cfg)
    assert not s.processed.overlay.supply_tasks and s.engine.state.holdings[WOOD]['p02'] == 3
    dying = replace(at_yard, hunger={**overlay.hunger, 'p02': cfg.death_at})
    starved = replace(carrying, balances={**carrying.balances, 'p02': 0})
    s = world_step(Engine(starved), dying, cfg)
    assert 'p02' in s.processed.overlay.died_at and not s.processed.overlay.supply_tasks
    assert s.engine.state.holdings[WOOD]['p02'] == 3 and s.engine.state.totals() == starved.totals()


def test_overlay_round_trips_tasks_and_yard_work():
    cfg, ledger, overlay = scene()
    full = replace(overlay, supply_tasks={'p02': (FETCH, SID, 'wood', 3, 0, 0, 0)}, yard_work={'p03': ((5, 5), 1)})
    canon = full.canonical()
    assert canon['supply_tasks'] == {'p02': [FETCH, SID, 'wood', 3, 0, 0, 0]} and canon['yard_work'] == {'p03': [5, 5, 1]}
    assert type(full).from_canonical(canon) == full
    assert 'yards' not in replace(overlay, yards={}).canonical()
