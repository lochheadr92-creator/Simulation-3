"""Re-evaluation and steadiness of recurring work: tasks end when the yard in
sight shows the need is met, keep their yard and grove across interruptions,
and time out from the last collection rather than the start."""
from dataclasses import replace

from kernel import Engine, Source
from world.config import WorldConfig, genesis, wood_sites
from world.decide import decide
from world.materials import GO_WOOD, STONE, WOOD, yard_id
from world.observe import observe
from world.run import world_step
from world.work import FETCH

YARD = (1, 6)
SID = yard_id(YARD)


def scene(stock=0, **changes):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True, stone_on=True, axe_on=True, actors=3, terrain_on=False,
                      water_on=False, births_on=False, offers_on=False, hunger_rate=0, **changes)
    ledger, overlay = genesis(cfg)
    sources = dict(ledger.sources)
    sources[SID] = Source(stock=stock, authorised=frozenset(ledger.roster), resource=WOOD)
    ledger = replace(ledger, sources=sources)
    overlay = replace(overlay, yards={SID: YARD}, shelters=(overlay.homes['p02'],),
                      built={p: (12 if p == 'p02' else 0) for p in overlay.roster},
                      positions={**overlay.positions, 'p02': (1, 5)})
    return cfg, ledger, overlay


def test_fetch_ends_when_the_yard_in_sight_covers_the_seen_need_or_no_need_is_seen():
    cfg, ledger, overlay = scene(stock=3, warmth_on=False)
    # the task last acted at tick 0; at tick 5 the person is idle again after something else
    fetching = replace(overlay, tick=5, supply_tasks={'p02': (FETCH, SID, 'wood', 3, 0, 0, 0)})
    ledger = replace(ledger, tick=5)
    choice = decide(observe('p02', ledger, fetching, cfg), cfg)
    assert choice.supply_end == 'demand met' and 'holds 3 and the shelters in sight need 3' in choice.reason
    done = replace(fetching, shelters=(overlay.homes['p01'], overlay.homes['p02']))
    choice = decide(observe('p02', replace(ledger, sources={**ledger.sources, SID: replace(ledger.sources[SID], stock=0)}), done, cfg), cfg)
    assert choice.supply_end == 'demand met' and 'no shelter in sight needs wood' in choice.reason
    s = world_step(Engine(ledger), fetching, cfg)
    assert not s.processed.overlay.supply_tasks
    # a task that acted last tick is not looked at again, so a one-step change of view cannot flip it
    steady = replace(fetching, supply_tasks={'p02': (FETCH, SID, 'wood', 3, 0, 0, 4)})
    assert decide(observe('p02', ledger, steady, cfg), cfg).supply_end is None


def test_no_re_evaluation_out_of_sight_and_deliver_phase_is_unchanged():
    cfg, ledger, overlay = scene(stock=3, warmth_on=False)
    grove, site = wood_sites(cfg)[1]                      # wood2 at (9,9): the yard is out of sight
    away = replace(overlay, tick=5, positions={**overlay.positions, 'p02': (8, 9)},
                   supply_tasks={'p02': (FETCH, SID, grove, 3, 0, 0, 0)})
    choice = decide(observe('p02', replace(ledger, tick=5), away, cfg), cfg)
    assert choice.supply_end is None and choice.kind == GO_WOOD and choice.target == grove
    carrying = replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 3}})
    delivering = replace(overlay, positions={**overlay.positions, 'p02': YARD},
                         supply_tasks={'p02': ('deliver', SID, 'wood', 3, 0, 0, 0)})
    choice = decide(observe('p02', carrying, delivering, cfg), cfg)
    assert choice.kind == 'deposit_wood' and choice.amount == 3


def test_axe_plan_ends_before_any_material_when_the_yard_in_sight_shows_no_need():
    cfg, ledger, overlay = scene(stock=3, warmth_on=False)
    planned = replace(overlay, tick=5, axe_work={'p02': (0, 0, 0)}, deliveries={'p02': 1},
                      shelters=(overlay.homes['p01'], overlay.homes['p02']))
    ledger = replace(ledger, tick=5)
    choice = decide(observe('p02', ledger, planned, cfg), cfg)
    assert choice.axe_end == 'no demand'
    with_wood = replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 1}})
    choice = decide(observe('p02', with_wood, planned, cfg), cfg)
    assert choice.axe_end is None and 'axe plan' in choice.reason        # sunk cost: carry on
    far = replace(planned, positions={**planned.positions, 'p02': (8, 9)})
    assert decide(observe('p02', ledger, far, cfg), cfg).axe_end is None
    steady = replace(planned, axe_work={'p02': (0, 0, 4)})       # acted last tick: no re-evaluation
    assert decide(observe('p02', ledger, steady, cfg), cfg).axe_end is None


def test_timeouts_count_from_the_last_collection():
    cfg, ledger, overlay = scene(stock=0, warmth_on=False)
    stale = replace(overlay, tick=70, axe_work={'p02': (0, 10, 10)}, deliveries={'p02': 1})
    choice = decide(observe('p02', replace(ledger, tick=70), stale, cfg), cfg)
    assert choice.axe_end == 'timeout' and 'since it started' in choice.reason
    with_wood = replace(ledger, tick=70, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 1}})
    choice = decide(observe('p02', with_wood, stale, cfg), cfg)
    assert choice.axe_end == 'timeout' and 'since the last material was collected' in choice.reason
    fresh = replace(stale, axe_work={'p02': (0, 40, 40)})
    assert decide(observe('p02', with_wood, fresh, cfg), cfg).axe_end is None
    # collecting the wood for the plan restarts the clock
    grove, site = wood_sites(cfg)[0]
    at_grove = replace(overlay, tick=50, positions={**overlay.positions, 'p02': site}, axe_work={'p02': (0, 10, 49)}, deliveries={'p02': 1})
    s = world_step(Engine(replace(ledger, tick=50)), at_grove, cfg)
    assert s.decisions['p02'].kind == 'gather_wood' and s.processed.overlay.axe_work == {'p02': (0, 50, 50)}


def test_cold_people_at_home_warm_first_then_start_and_a_task_never_flaps():
    cfg, ledger, overlay = scene(stock=0)
    home = overlay.homes['p02']
    cold = replace(overlay, positions={**overlay.positions, 'p02': (1, 5)}, cold={**overlay.cold, 'p02': 3})
    away = decide(observe('p02', ledger, cold, cfg), cfg)
    assert away.supply is not None                                   # away from home: cold does not delay the start
    at_home = replace(cold, positions={**overlay.positions, 'p02': home}, homes={**overlay.homes, 'p02': home})
    at_home = replace(at_home, shelters=(home,), positions={**at_home.positions, 'p01': (1, 4)}, homes={**at_home.homes, 'p01': (0, 5)})
    view = observe('p02', ledger, at_home, cfg)
    if view.yard_demand and any(stock is not None for _, _, stock in view.yards):
        choice = decide(view, cfg)
        assert choice.kind == 'warm' and choice.reason.startswith('warming up before starting work: wood supply')
    engine, ov = Engine(ledger), replace(overlay, supply_tasks={'p02': (FETCH, SID, 'wood', 3, 0, 0, 0)},
                                         hunger={**overlay.hunger, 'p02': cfg.hungry_at})
    seen, ends, starts = [], 0, 0
    for _ in range(25):
        s = world_step(engine, ov, cfg)
        engine, ov = s.engine, s.processed.overlay
        d = s.decisions['p02']
        starts += d.supply is not None and d.supply[5] == 0
        ends += d.supply_end is not None
        if 'p02' in ov.supply_tasks:
            seen.append(ov.supply_tasks['p02'][1:3])
    assert set(seen) == {(SID, 'wood')} and starts == 0 and ends <= 1
