"""Wood is gathered, carried and paid through settlement before shelter work."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis, wood_sites
from world.decide import Decision, decide
from world.materials import WOOD, GATHER_WOOD, GO_WOOD, WAIT_WOOD, WOOD_STOCK, wood_cost, remaining_wood
from world.observe import observe
from world.process import advance, free_cell_near
from world.run import build_parser, config_from, proposals_for, run_id_for, run_world, world_step
from world.replay import replay_world
from world.recover import recover_world
from world.viewer import render_html, render_text
from world.viewer_index import build_index


def quiet(**changes):
    cfg=WorldConfig(seed=7,wood_on=True,actors=1,terrain_on=False,water_on=False,warmth_on=False,
                    births_on=False,offers_on=False,hunger_rate=0,**changes)
    ledger,overlay=genesis(cfg)
    return cfg,ledger,overlay


def test_genesis_is_explicit_and_preserves_the_existing_world_layout():
    cfg=WorldConfig(seed=11,wood_on=True)
    old=replace(cfg,wood_on=False)
    ledger,overlay=genesis(cfg); before,prior=genesis(old)
    assert overlay==prior and cfg.terrain()==old.terrain()
    assert ledger.balances==before.balances and ledger.holdings['water']==before.holdings['water']
    assert all(n==0 for n in ledger.holdings[WOOD].values()) and ledger.consumed_by[WOOD]==0
    assert sum(s.stock for s in ledger.sources.values() if s.resource==WOOD)==len(wood_sites(cfg))*WOOD_STOCK
    rough,spots=cfg.terrain()
    assert not {p for _,p in wood_sites(cfg)} & (set(overlay.homes.values())|set(rough)|set(spots))
    assert len(set(cfg.all_source_positions()))==len(cfg.all_source_positions())
    assert free_cell_near(wood_sites(cfg)[0][1],set(cfg.all_source_positions()),cfg) not in cfg.all_source_positions()


@pytest.mark.parametrize('ticks,cost',[(1,1),(4,1),(5,2),(12,3),(13,4)])
def test_material_cost_matches_work_milestones(ticks,cost):
    assert sum(wood_cost(n) for n in range(ticks))==cost
    assert remaining_wood(0,ticks)==cost and remaining_wood(ticks,ticks)==0


def test_gather_carry_and_build_spends_exactly_three_wood():
    cfg,ledger,overlay=quiet()
    sid,site=wood_sites(cfg)[0]
    overlay=replace(overlay,positions={'p01':site})
    choice=decide(observe('p01',ledger,overlay,cfg),cfg)
    assert choice.kind==GATHER_WOOD and choice.amount==3
    step=world_step(Engine(ledger),overlay,cfg)
    assert step.processed.ledger.holdings[WOOD]['p01']==3
    assert step.processed.ledger.totals()==ledger.totals()
    assert step.processed.overlay.built.get('p01',0)==0
    engine,current=step.engine,step.processed.overlay
    paid=[]; seen_home_walk=False
    for _ in range(80):
        choice=decide(observe('p01',engine.state,current,cfg),cfg)
        if choice.kind=='home': seen_home_walk=True
        before=engine.state.consumed_by[WOOD]
        step=world_step(engine,current,cfg); engine,current=step.engine,step.processed.overlay
        if engine.state.consumed_by[WOOD]>before: paid.append(current.built['p01'])
        if current.homes['p01'] in current.shelters: break
    assert seen_home_walk and paid==[1,5,9]
    assert current.built['p01']==12 and engine.state.consumed_by[WOOD]==3
    assert engine.state.holdings[WOOD]['p01']==0
    assert engine.state.balances==ledger.balances  # wood never becomes a meal
    assert current.hunger==overlay.hunger


def test_refused_payment_gives_no_work_but_paid_partial_work_is_kept():
    cfg,ledger,overlay=quiet()
    decision=Decision('p01','build','pay',('build',),amount=1)
    engine=Engine(ledger); record=engine.tick(proposals_for({'p01':decision},ledger.tick))
    result=advance(overlay,{'p01':decision},record,engine.state,cfg)
    assert not record.outcomes[0].accepted and result.overlay.built['p01']==0
    assert not result.overlay.shelters and result.ledger.consumed_by[WOOD]==0
    # The next three ticks of a paid group do not demand the same wood again.
    paid=replace(overlay,built={'p01':1})
    assert decide(observe('p01',ledger,paid,cfg),cfg).kind=='build'
    result=world_step(Engine(ledger),paid,cfg).processed
    assert result.overlay.built['p01']==2 and result.ledger.consumed_by[WOOD]==0


def test_needs_and_children_do_not_gather_or_spend_wood():
    cfg,ledger,overlay=quiet()
    view=observe('p01',ledger,overlay,cfg)
    assert decide(replace(view,hunger=cfg.hungry_at,food=1),cfg).kind=='eat'
    assert decide(replace(view,age=0),cfg).kind=='rest'
    grown=replace(view,wood=1)
    assert decide(grown,cfg).kind=='build' and decide(grown,cfg).amount==1
    interrupted=replace(overlay,built={'p01':4},hunger={'p01':cfg.hungry_at})
    result=world_step(Engine(ledger),interrupted,cfg).processed
    assert result.overlay.built['p01']==4 and result.ledger.consumed_by[WOOD]==0


def test_local_stock_competition_empty_groves_and_separate_renewal():
    cfg=WorldConfig(seed=7,actors=2,wood_on=True,terrain_on=False,water_on=False,warmth_on=False,
                    births_on=False,offers_on=False,renewal_amount=0)
    ledger,overlay=genesis(cfg); sid,site=wood_sites(cfg)[0]
    sources={s:replace(v,stock=1 if s==sid else 0) if v.resource==WOOD else v for s,v in ledger.sources.items()}
    ledger=replace(ledger,sources=sources)
    overlay=replace(overlay,positions={p:site for p in overlay.roster},hunger={p:0 for p in overlay.roster})
    decisions={p:decide(observe(p,ledger,overlay,cfg),cfg) for p in overlay.roster}
    engine=Engine(ledger); record=engine.tick(proposals_for(decisions,0))
    assert sum(o.accepted for o in record.outcomes)==1
    assert sum(engine.state.holdings[WOOD].values())==1 and engine.state.sources[sid].stock==0
    assert engine.state.totals()==ledger.totals()
    empty=replace(ledger,sources={s:replace(v,stock=0) if v.resource==WOOD else v for s,v in sources.items()})
    assert decide(observe('p01',empty,overlay,cfg),cfg).kind==WAIT_WOOD
    far=replace(overlay,positions=dict(overlay.positions,p01=(11,0)))
    assert observe('p01',empty,far,cfg).wood_stock is None
    assert decide(observe('p01',empty,far,cfg),cfg).kind==GO_WOOD
    engine=Engine(replace(empty,tick=39)); record=engine.tick([])
    result=advance(replace(overlay,tick=39),{},record,engine.state,cfg)
    assert result.production==tuple({'source':s,'amount':1} for s,_ in wood_sites(cfg))
    assert all(result.ledger.sources[s].stock==1 for s,_ in wood_sites(cfg))
    full=replace(ledger,tick=39,sources={s:replace(v,stock=WOOD_STOCK) if v.resource==WOOD else v
                                       for s,v in ledger.sources.items()})
    engine=Engine(full); record=engine.tick([])
    assert not advance(replace(overlay,tick=39),{},record,engine.state,cfg).production


def test_switch_cli_and_old_headers_round_trip():
    cfg,ledger,overlay=quiet()
    assert WorldConfig.from_describe(cfg.describe())==cfg
    old=replace(cfg,wood_on=False)
    assert 'wood' not in old.describe() and WorldConfig.from_describe(old.describe())==old
    assert WOOD not in genesis(old)[0].holdings
    assert run_id_for(cfg,100)!=run_id_for(old,100)
    assert config_from(build_parser().parse_args(['--seed','7','--wood','on'])).wood_on
    with pytest.raises(ValueError): replace(cfg,building_on=False)


def test_saved_wood_world_replays_recovers_and_shows_the_material_chain(tmp_path):
    cfg=WorldConfig(seed=11,wood_on=True,homes_on=True,stores_on=True,relocation_on=True,
                    seasons_on=True,regrowth_on=True,source_stock=8,source_cap=16,renewal_amount=3)
    path=tmp_path/'wood.jsonl'; result=run_world(cfg,220,path)
    run=read_run(path)
    assert run.complete and replay_world(path).identical
    index=build_index(run); kinds={e['kind'] for e in index['events']}
    assert {'gather_wood','wood_used','build_done','birth'} <= kinds
    assert index['wood']==cfg.describe()['wood_sources']
    used=sum(e.get('amount',0) for e in index['events'] if e['kind']=='wood_used')
    assert used==run.ticks[-1]['state']['consumed_by'][WOOD]
    for tick in run.ticks:
        for e in tick.get('production',[]):
            if 'born' in e:
                assert e['born'] in tick['world']['positions']
    page=render_html(run)
    assert 'Wood groves' in page and 'woodHeld' in page and 'gather_wood' in page
    assert 'wood2 T at' in render_text(run,50)
    gathered=next(e['k'] for e in index['events'] if e['kind']=='gather_wood')
    lines=path.read_bytes().splitlines(keepends=True)
    end=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick'
             and json.loads(line).get('tick')==gathered-1)
    cut,restored=tmp_path/'cut.jsonl',tmp_path/'restored.jsonl'
    cut.write_bytes(b''.join(lines[:end+1])); recover_world(cut,restored)
    assert read_run(restored).ticks==run.ticks and replay_world(restored).identical
    assert run_world(cfg,220,tmp_path/'repeat.jsonl').trail_digest==result.trail_digest
