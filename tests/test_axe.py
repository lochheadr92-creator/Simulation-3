"""The basic stone axe: planned only after a delivery with demand still in
sight, paid in stages through settlement, recorded as a possession, and
gathering five wood per claim instead of three."""
import json
from dataclasses import replace

from kernel import Engine, Source
from stream.run_file import read_run
from world.config import WorldConfig, genesis, stone_sites, wood_sites
from world.decide import Decision, decide
from world.materials import (AXE_WOOD_PACK, CRAFT_AXE, GATHER_STONE, GATHER_WOOD, GO_STONE, STONE, WOOD, WOOD_PACK,
                             axe_cost, yard_id)
from world.observe import observe
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, proposals_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index

YARD = (1, 6)
SID = yard_id(YARD)


def scene(stock=0, deliveries=1, **changes):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True, stone_on=True, axe_on=True, actors=3, terrain_on=False,
                      water_on=False, warmth_on=False, births_on=False, offers_on=False, hunger_rate=0, **changes)
    ledger, overlay = genesis(cfg)
    sources = dict(ledger.sources)
    sources[SID] = Source(stock=stock, authorised=frozenset(ledger.roster), resource=WOOD)
    ledger = replace(ledger, sources=sources)
    # p02's shelter is finished; p02 stands at (1,5) with the yard and p01's unbuilt home (0,7) in sight
    overlay = replace(overlay, yards={SID: YARD}, shelters=(overlay.homes['p02'],),
                      built={p: (12 if p == 'p02' else 0) for p in overlay.roster},
                      positions={**overlay.positions, 'p02': (1, 5)},
                      deliveries={'p02': deliveries} if deliveries else {})
    return cfg, ledger, overlay


def holding(ledger, who='p02', **units):
    holdings = dict(ledger.holdings)
    for res, n in units.items():
        holdings[res] = {**holdings[res], who: n}
    return replace(ledger, holdings=holdings)


def run(engine, overlay, cfg, ticks, until=None):
    trace = []
    for _ in range(ticks):
        s = world_step(engine, overlay, cfg)
        engine, overlay = s.engine, s.processed.overlay
        trace.append(s)
        if until and until(engine, overlay):
            break
    return engine, overlay, trace


def test_plan_needs_a_past_delivery_and_demand_still_in_sight():
    cfg, ledger, overlay = scene(stock=3)      # the yard covers the seen demand: no supply task competes
    choice = decide(observe('p02', ledger, overlay, cfg), cfg)
    assert choice.axe_start and 'planning an axe: 1 wood delivery made' in choice.reason and choice.kind == 'go_wood'
    never = scene(stock=3, deliveries=0)
    assert not decide(observe('p02', never[1], never[2], cfg), cfg).axe_start
    built = replace(overlay, shelters=(overlay.homes['p01'], overlay.homes['p02']))
    assert not decide(observe('p02', ledger, built, cfg), cfg).axe_start
    away = replace(overlay, positions={**overlay.positions, 'p02': (7, 1)})
    assert not decide(observe('p02', ledger, away, cfg), cfg).axe_start
    owned = replace(overlay, axes=('p02',))
    assert not decide(observe('p02', ledger, owned, cfg), cfg).axe_start
    # with a delivery behind them, planning comes before another supply trip; a started plan comes first of all
    short = scene(stock=0)
    assert decide(observe('p02', short[1], short[2], cfg), cfg).axe_start
    busy = replace(short[2], supply_tasks={'p02': ('fetch', SID, 'wood', 3, 0, 0)})
    assert not decide(observe('p02', short[1], busy, cfg), cfg).axe_start
    started = replace(short[2], axe_work={'p02': (0, 0)})
    assert 'axe plan' in decide(observe('p02', short[1], started, cfg), cfg).reason


def test_payment_is_staged_and_never_charged_twice():
    cfg, ledger, overlay = scene(stock=3)
    home = overlay.homes['p02']
    at_home = replace(overlay, positions={**overlay.positions, 'p02': home}, axe_work={'p02': (0, 0)})
    ledger = holding(ledger, wood=1, stone=1)
    assert axe_cost(0) == (WOOD, 1) and axe_cost(1) == (STONE, 1) and axe_cost(2) is None
    first = decide(observe('p02', ledger, at_home, cfg), cfg)
    assert first.kind == CRAFT_AXE and first.amount == 1 and first.resource == WOOD
    engine, ov, trace = run(Engine(ledger), at_home, cfg, 1)
    assert ov.axe_work == {'p02': (1, 0)} and engine.state.holdings[WOOD]['p02'] == 0 and engine.state.holdings[STONE]['p02'] == 1
    second = decide(observe('p02', engine.state, ov, cfg), cfg)
    assert second.kind == CRAFT_AXE and second.resource == STONE
    # hunger interrupts between craft ticks; the plan waits and resumes with no second wood payment
    hungry = replace(ov, hunger={**ov.hunger, 'p02': cfg.hungry_at})
    assert decide(observe('p02', engine.state, hungry, cfg), cfg).kind == 'eat'
    engine, ov, _ = run(engine, hungry, cfg, 1)
    assert ov.axe_work == {'p02': (1, 0)}
    engine, ov, _ = run(engine, ov, cfg, 2)
    assert ov.axes == ('p02',) and 'p02' not in ov.axe_work
    assert engine.state.consumed_by[WOOD] == 1 and engine.state.consumed_by[STONE] == 1
    assert engine.state.totals() == ledger.totals()


def test_refused_payment_leaves_progress_and_nothing_completes_without_both_payments():
    cfg, ledger, overlay = scene(stock=3)
    home = overlay.homes['p02']
    at_home = replace(overlay, positions={**overlay.positions, 'p02': home}, axe_work={'p02': (1, 0)})
    decision = Decision('p02', CRAFT_AXE, 'pay', (CRAFT_AXE,), amount=1, resource=STONE)
    engine = Engine(ledger)                                   # no stone in hand
    record = engine.tick(proposals_for({'p02': decision}, 0))
    assert not record.outcomes[0].accepted
    result = advance(at_home, {'p02': decision}, record, engine.state, cfg)
    assert result.overlay.axe_work == {'p02': (1, 0)} and not result.overlay.axes
    # the rule itself sends them for stone rather than crafting unpaid
    choice = decide(observe('p02', ledger, at_home, cfg), cfg)
    assert choice.kind == GO_STONE and 'needs' not in choice.reason or choice.kind in (GO_STONE, GATHER_STONE)


def test_death_drops_the_plan_and_keeps_the_axe_recorded():
    cfg, ledger, overlay = scene(stock=3)
    home = overlay.homes['p02']
    ledger = holding(replace(ledger, balances={**ledger.balances, 'p02': 0}), stone=1)
    dying = replace(overlay, positions={**overlay.positions, 'p02': home}, axe_work={'p02': (1, 0)},
                    hunger={**overlay.hunger, 'p02': cfg.death_at})
    engine, ov, trace = run(Engine(ledger), dying, cfg, 1)
    assert 'p02' in ov.died_at and not ov.axe_work and not ov.axes
    assert engine.state.consumed_by[WOOD] == 0 and engine.state.holdings[STONE]['p02'] == 1
    assert engine.state.totals() == ledger.totals()
    owner = replace(dying, axe_work={}, axes=('p02',))
    engine, ov, _ = run(Engine(ledger), owner, cfg, 1)
    assert ov.axes == ('p02',) and 'p02' in ov.died_at
    assert not observe('p01', engine.state, ov, cfg).has_axe


def test_axe_holder_gathers_five_bounded_by_stock_and_need_while_hands_gather_three():
    cfg, ledger, overlay = scene(stock=0, deliveries=0)
    grove, site = wood_sites(cfg)[0]
    at_grove = replace(overlay, axes=('p02',), positions={**overlay.positions, 'p02': site},
                       supply_tasks={'p02': ('fetch', SID, grove, 5, 0, 0)})
    choice = decide(observe('p02', ledger, at_grove, cfg), cfg)
    assert choice.kind == GATHER_WOOD and choice.amount == AXE_WOOD_PACK == 5 and 'with the axe' in choice.reason
    four = replace(ledger, sources={**ledger.sources, grove: replace(ledger.sources[grove], stock=4)})
    assert decide(observe('p02', four, at_grove, cfg), cfg).amount == 4
    two = replace(at_grove, supply_tasks={'p02': ('fetch', SID, grove, 2, 0, 0)})
    assert decide(observe('p02', ledger, two, cfg), cfg).amount == 2
    hands = replace(at_grove, axes=())
    assert decide(observe('p02', ledger, hands, cfg), cfg).amount == WOOD_PACK == 3
    # a shelter builder with an axe still takes only what the shelter needs
    builder = replace(overlay, axes=('p01',), positions={**overlay.positions, 'p01': site})
    assert decide(observe('p01', ledger, builder, cfg), cfg).amount == 3
    # an axe-assisted supply trip conserves wood end to end
    engine, ov, trace = run(Engine(ledger), at_grove, cfg, 40, until=lambda e, o: not o.supply_tasks)
    assert engine.state.sources[SID].stock == 5 and engine.state.holdings[WOOD]['p02'] == 0
    assert engine.state.totals()[WOOD] == ledger.totals()[WOOD] and ov.deliveries['p02'] == 1
    view = observe('p02', engine.state, ov, cfg)
    assert view.yard_demand and view.has_axe and not decide(view, cfg).axe_start   # one axe each; the yard now covers the seen need


def test_switches_preset_and_round_trip():
    cfg, ledger, overlay = scene()
    assert WorldConfig.from_describe(cfg.describe()) == cfg and 'axe_rule' in cfg.describe()
    off = replace(cfg, stone_on=False, axe_on=False)
    assert 'stone' not in off.describe() and 'axe' not in off.describe()
    for bad in ({'stone_on': True, 'wood_on': False}, {'axe_on': True, 'stone_on': False, 'yard_on': True, 'wood_on': True},
                {'axe_on': True, 'stone_on': True, 'yard_on': False, 'wood_on': True}):
        try:
            WorldConfig(seed=7, **bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    parsed = config_from(build_parser().parse_args(['--seed', '7', '--preset', 'crafting']))
    assert parsed.wood_on and parsed.yard_on and parsed.stone_on and parsed.axe_on
    parsed = config_from(build_parser().parse_args(['--seed', '7', '--preset', 'crafting', '--axe', 'off']))
    assert parsed.stone_on and not parsed.axe_on
    canon = replace(overlay, axes=('p02',), axe_work={'p01': (1, 4)}, deliveries={'p02': 2}).canonical()
    assert canon['axes'] == ['p02'] and canon['axe_work'] == {'p01': [1, 4]} and canon['deliveries'] == {'p02': 2}
    assert type(overlay).from_canonical(canon) == replace(overlay, axes=('p02',), axe_work={'p01': (1, 4)}, deliveries={'p02': 2})


def test_crafting_world_is_deterministic_replays_recovers_and_renders(tmp_path):
    cfg = WorldConfig(seed=23, wood_on=True, yard_on=True, stone_on=True, axe_on=True, stores_on=True, provisioning_on=True,
                      homes_on=True, childhood_on=True, coordination_on=True, relocation_on=True, fishing_on=True,
                      source_memory_on=True, knowledge_sharing_on=True, shared_care_on=True)
    path = tmp_path / 'axe.jsonl'
    result = run_world(cfg, 360, path)
    run_file = read_run(path)
    assert run_file.complete and replay_world(path).identical
    made = next(t['tick'] for t in run_file.ticks if t['world'].get('axes'))
    index = build_index(run_file)
    kinds = {e['kind'] for e in index['events']}
    assert {'axe_planned', 'stone_taken', 'axe_payment', 'axe_made'} <= kinds and index['stone']
    page = render_html(run_file)
    assert 'Stone outcrop' in page and 'Axe crafting' in page and 'Saved reason' in page
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines) if json.loads(line).get('kind') == 'tick' and json.loads(line)['tick'] == made)
    cut, restored = tmp_path / 'cut.jsonl', tmp_path / 'restored.jsonl'
    cut.write_bytes(b''.join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run_file.ticks and replay_world(restored).identical
    assert run_world(cfg, 360, tmp_path / 'repeat.jsonl').trail_digest == result.trail_digest
