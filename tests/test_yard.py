"""Shared wood yards: built where a shortage was seen, paid through settlement,
created by a production entry, and used by shelter builders."""
import json
from dataclasses import replace

import pytest

from kernel import Engine, Source
from stream.run_file import RunFileError, apply_production, read_run
from world.config import WorldConfig, genesis, wood_sites
from world.decide import Decision, decide
from world.materials import (BUILD_YARD, DEPOSIT_WOOD, GO_WOOD, GO_YARD, TAKE_WOOD, WOOD, YARD_WORK,
                             remaining_yard_wood, yard_cost, yard_id)
from world.observe import observe
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, proposals_for, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index

YARD = (1, 6)
SID = yard_id(YARD)


def quiet(**changes):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True, actors=3, terrain_on=False, water_on=False,
                      warmth_on=False, births_on=False, offers_on=False, hunger_rate=0, **changes)
    ledger, overlay = genesis(cfg)
    # p01 home (0,7), p02 home (2,3), p03 home (7,8); groves at (3,6) and (9,9)
    return cfg, ledger, overlay


def with_wood(ledger, **units):
    return replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], **units}})


def with_yard(ledger, overlay, stock=0):
    sources = dict(ledger.sources)
    sources[SID] = Source(stock=stock, authorised=frozenset(ledger.roster), resource=WOOD)
    return replace(ledger, sources=sources), replace(overlay, yards={SID: YARD})


def finished(overlay, *who):
    return replace(overlay, shelters=tuple(sorted(overlay.homes[p] for p in who)),
                   built={p: (12 if p in who else 0) for p in overlay.roster})


def step(engine, overlay, cfg):
    s = world_step(engine, overlay, cfg)
    return s.engine, s.processed.overlay, s


def test_yard_costs_two_wood_paid_at_work_ticks_0_and_2():
    assert [yard_cost(n) for n in range(YARD_WORK)] == [1, 0, 1, 0]
    assert remaining_yard_wood(0) == 2 and remaining_yard_wood(2) == 1 and remaining_yard_wood(3) == 0


def test_construction_pays_through_settlement_and_creates_the_source():
    cfg, ledger, overlay = quiet()
    overlay = finished(overlay, 'p02')
    overlay = replace(overlay, positions={**overlay.positions, 'p02': YARD}, yard_work={'p02': (YARD, 0)})
    ledger = with_wood(ledger, p02=2)
    engine = Engine(ledger)
    paid, created = [], None
    for _ in range(YARD_WORK):
        choice = decide(observe('p02', engine.state, overlay, cfg), cfg)
        assert choice.kind == BUILD_YARD and choice.target == SID
        before = engine.state.consumed_by[WOOD]
        engine, overlay, s = step(engine, overlay, cfg)
        if engine.state.consumed_by[WOOD] > before:
            paid.append(before)
        created = created or next((e for e in s.processed.production if 'source_created' in e), None)
    assert paid == [0, 1] and created == {'source_created': SID, 'resource': WOOD}
    assert engine.state.sources[SID] == Source(0, frozenset(ledger.roster), WOOD)
    assert overlay.yards == {SID: YARD} and 'p02' not in overlay.yard_work
    assert engine.state.holdings[WOOD]['p02'] == 0 and engine.state.totals() == ledger.totals()


def test_refused_payment_leaves_yard_work_unchanged():
    cfg, ledger, overlay = quiet()
    overlay = replace(finished(overlay, 'p02'), yard_work={'p02': (YARD, 2)})
    decision = Decision('p02', BUILD_YARD, 'pay', (BUILD_YARD,), amount=1, target=SID)
    engine = Engine(ledger)
    record = engine.tick(proposals_for({'p02': decision}, ledger.tick))
    assert not record.outcomes[0].accepted
    result = advance(overlay, {'p02': decision}, record, engine.state, cfg)
    assert result.overlay.yard_work == {'p02': (YARD, 2)} and not result.overlay.yards and not result.production
    # the unpaid work tick after a paid one needs no wood and still progresses
    unpaid = replace(overlay, yard_work={'p02': (YARD, 1)})
    decision = Decision('p02', BUILD_YARD, 'work', (BUILD_YARD,), target=SID)
    result = advance(unpaid, {'p02': decision}, Engine(ledger).tick([]), replace(ledger, tick=1), cfg)
    assert result.overlay.yard_work == {'p02': (YARD, 2)}


def test_starting_a_yard_needs_seen_demand_a_finished_home_and_no_yard_in_range():
    cfg, ledger, overlay = quiet()
    overlay = replace(finished(overlay, 'p02'), positions={**overlay.positions, 'p02': (1, 5)})
    view = observe('p02', ledger, overlay, cfg)
    assert view.yard_demand == (('p01', 3),) and view.yard_site_option is not None
    choice = decide(view, cfg)
    assert choice.yard_site == view.yard_site_option and choice.kind == GO_WOOD
    assert "p01's unfinished shelter" in choice.reason
    # p01 seen carrying wood lowers the need it shows
    assert observe('p02', with_wood(ledger, p01=2), overlay, cfg).yard_demand == (('p01', 1),)
    # a finished shelter is no demand; an unfinished own home comes first
    assert not observe('p02', ledger, finished(overlay, 'p01', 'p02'), cfg).yard_demand
    unbuilt = replace(overlay, shelters=(), built={})
    assert decide(observe('p02', ledger, unbuilt, cfg), cfg).yard_site is None
    # a yard within range of the demand, or somebody's visible yard work, stops a second one
    ledger2, overlay2 = with_yard(ledger, overlay)
    assert observe('p02', ledger2, overlay2, cfg).yard_nearby and observe('p02', ledger2, overlay2, cfg).yard_site_option is None
    busy = replace(overlay, yard_work={'p03': ((1, 7), 1)})
    assert observe('p02', ledger, busy, cfg).yard_site_option is None
    # a child never starts one
    assert decide(replace(view, age=0), replace(cfg, childhood_on=True)).yard_site is None
    # starting is recorded; the builder then fetches wood by hand
    engine, overlay, s = step(Engine(ledger), overlay, cfg)
    assert overlay.yard_work == {'p02': (view.yard_site_option, 0)}


def test_dead_builder_drops_the_unfinished_yard():
    cfg, ledger, overlay = quiet()
    overlay = replace(finished(overlay, 'p02'), yard_work={'p02': (YARD, 3)},
                      positions={**overlay.positions, 'p02': YARD}, hunger={**overlay.hunger, 'p02': cfg.death_at})
    ledger = replace(ledger, balances={**ledger.balances, 'p02': 0})
    engine, overlay, s = step(Engine(ledger), overlay, cfg)
    assert 'p02' in overlay.died_at and not overlay.yard_work and not overlay.yards
    assert SID not in engine.state.sources and not s.processed.production


def test_deposit_and_withdrawal_move_wood_through_the_kernel_and_conserve_it():
    cfg, ledger, overlay = quiet()
    ledger, overlay = with_yard(ledger, overlay)
    ledger = with_wood(ledger, p02=3)
    overlay = replace(finished(overlay, 'p02'), positions={**overlay.positions, 'p02': YARD, 'p01': YARD},
                      supply_tasks={'p02': ('deliver', SID, 'wood', 3, 0, 0, 0)})
    supplier = decide(observe('p02', ledger, overlay, cfg), cfg)
    assert supplier.kind == DEPOSIT_WOOD and supplier.amount == 3 and supplier.target == SID
    builder = decide(observe('p01', ledger, overlay, cfg), cfg)
    assert builder.kind == GO_WOOD          # the yard is empty in sight: use the grove, do not wait
    engine, overlay, s = step(Engine(ledger), overlay, cfg)
    assert engine.state.sources[SID].stock == 3 and engine.state.holdings[WOOD]['p02'] == 0
    assert not overlay.supply_tasks and engine.state.totals() == ledger.totals()
    back = replace(overlay, positions={**overlay.positions, 'p01': YARD})
    builder = decide(observe('p01', engine.state, back, cfg), cfg)
    assert builder.kind == TAKE_WOOD and builder.amount == 3 and builder.target == SID
    engine, later, s = step(engine, back, cfg)
    assert engine.state.holdings[WOOD]['p01'] == 3 and engine.state.sources[SID].stock == 0
    assert engine.state.totals() == ledger.totals()
    # a known but unseen yard nearer than the grove is tried first
    far = replace(overlay, positions={**overlay.positions, 'p01': (0, 11)})
    choice = decide(observe('p01', ledger, far, cfg), cfg)
    assert choice.kind == GO_YARD and choice.target == SID


def test_two_builders_claim_the_last_wood_and_only_one_gets_it():
    cfg, ledger, overlay = quiet()
    ledger, overlay = with_yard(ledger, overlay, stock=2)
    overlay = replace(overlay, positions={**overlay.positions, 'p01': YARD, 'p03': YARD})
    decisions = {p: decide(observe(p, ledger, overlay, cfg), cfg) for p in ('p01', 'p03')}
    assert all(d.kind == TAKE_WOOD and d.amount == 2 for d in decisions.values())
    engine = Engine(ledger)
    record = engine.tick(proposals_for(decisions, 0))
    assert sum(o.accepted for o in record.outcomes) == 1
    result = advance(overlay, decisions, record, engine.state, cfg)
    assert sorted(engine.state.holdings[WOOD][p] for p in ('p01', 'p03')) == [0, 2]
    assert engine.state.sources[SID].stock == 0 and engine.state.totals() == ledger.totals()
    assert not any(result.overlay.built.get(p) for p in ('p01', 'p03'))


def test_end_to_end_shortage_supply_withdrawal_and_completion():
    cfg, ledger, overlay = quiet()
    ledger, overlay = with_yard(ledger, overlay)
    overlay = finished(overlay, 'p02', 'p03')
    # p01 is hungry with no food and leaves for the patch; p02 idles at (1,5) and sees the shortage
    overlay = replace(overlay, positions={**overlay.positions, 'p02': (1, 5)},
                      hunger={**overlay.hunger, 'p01': cfg.hungry_at})
    ledger = replace(ledger, balances={**ledger.balances, 'p01': 0})
    engine = Engine(ledger)
    events = []
    for _ in range(90):
        tick = engine.state.tick
        engine, overlay, s = step(engine, overlay, cfg)
        for out in s.record.outcomes:
            kind = s.decisions[out.actor].kind
            if kind in (DEPOSIT_WOOD, TAKE_WOOD, 'gather_wood'):
                events.append((tick, out.actor, kind, out.accepted))
        if overlay.homes['p01'] in overlay.shelters:
            break
    deposits = [e for e in events if e[2] == DEPOSIT_WOOD and e[3]]
    takes = [e for e in events if e[2] == TAKE_WOOD and e[3]]
    assert deposits and deposits[0][1] == 'p02' and takes and takes[0][1] == 'p01'
    assert deposits[0][0] < takes[0][0]
    assert overlay.homes['p01'] in overlay.shelters and engine.state.totals()[WOOD] == ledger.totals()[WOOD]
    assert not overlay.supply_tasks


def test_legacy_and_named_source_creation_reconstruct_the_recorded_state():
    cfg, ledger, overlay = quiet()
    state = ledger.canonical()
    food = apply_production(state, [{"source_created": "home-1-1"}])
    assert food["sources"]["home-1-1"] == {"stock": 0, "authorised": sorted(ledger.balances)}
    wood = apply_production(state, [{"source_created": SID, "resource": WOOD}])
    assert wood["sources"][SID] == {"stock": 0, "authorised": sorted(ledger.balances), "resource": WOOD}
    sources = dict(ledger.sources)
    sources[SID] = Source(0, frozenset(ledger.roster), WOOD)
    assert wood == replace(ledger, sources=sources).canonical()
    with pytest.raises(RunFileError):
        apply_production(state, [{"source_created": SID, "resource": ""}])
    with pytest.raises(RunFileError):
        apply_production(state, [{"source_created": SID, "resource": WOOD, "stock": 3}])


def test_switch_preset_and_headers_round_trip():
    cfg, ledger, overlay = quiet()
    assert WorldConfig.from_describe(cfg.describe())== cfg and 'yard_rule' in cfg.describe()
    off = replace(cfg, yard_on=False)
    assert 'yard' not in off.describe() and WorldConfig.from_describe(off.describe()) == off
    assert off.describe() == replace(off, yard_on=False).describe()
    assert run_id_for(cfg, 100) != run_id_for(off, 100)
    with pytest.raises(ValueError):
        WorldConfig(seed=7, yard_on=True)
    parsed = config_from(build_parser().parse_args(['--seed', '7', '--preset', 'crafting']))
    assert parsed.wood_on and parsed.yard_on
    parsed = config_from(build_parser().parse_args(['--seed', '7', '--preset', 'crafting', '--yard', 'off', '--axe', 'off']))
    assert parsed.wood_on and not parsed.yard_on
    assert not config_from(build_parser().parse_args(['--seed', '7'])).wood_on
    assert genesis(cfg)[1] == genesis(off)[1]


def test_saved_yard_world_is_deterministic_replays_recovers_and_renders(tmp_path):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True)
    path = tmp_path / 'yard.jsonl'
    result = run_world(cfg, 300, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    created = [(t['tick'], e) for t in run.ticks for e in (t.get('production') or []) if 'resource' in e]
    assert created and created[0][1]['resource'] == WOOD
    index = build_index(run)
    kinds = {e['kind'] for e in index['events']}
    assert {'yard_started', 'yard_finished', 'supply_start', 'yard_deposit', 'yard_take'} <= kinds
    assert any(s.get('yard') for s in index['wood'])
    page = render_html(run)
    assert 'Wood groves and yards' in page and 'Wood supply task' in page
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines) if json.loads(line).get('kind') == 'tick'
               and json.loads(line).get('tick') == created[0][0] + 1)
    cut, restored = tmp_path / 'cut.jsonl', tmp_path / 'restored.jsonl'
    cut.write_bytes(b''.join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks and replay_world(restored).identical
    assert run_world(cfg, 300, tmp_path / 'repeat.jsonl').trail_digest == result.trail_digest
