"""Foraging memory comes from local sight and can change a later journey."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis, fishing_sites
from world.decide import decide
from world.foraging import EMPTY_SOURCE_TICKS, remember_empty
from world.observe import observe
from world.overlay import Overlay
from world.process import advance, _births
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index


def quiet(**changes):
    cfg=WorldConfig(seed=23, actors=1, source_memory_on=True, terrain_on=False,
                    water_on=False, warmth_on=False, offers_on=False, births_on=False,
                    perception_radius=1, **changes)
    ledger, world=genesis(cfg)
    first=cfg.food_source_ids()[0]
    ledger=replace(ledger, balances={'p01':0}, sources={sid:replace(s,stock=0) if sid==first else s
                                                     for sid,s in ledger.sources.items()})
    world=replace(world,positions={'p01':cfg.food_positions()[0]},hunger={'p01':cfg.hungry_at})
    return cfg,ledger,world


def test_empty_sighting_changes_choice_and_survives_outside_sight():
    cfg,ledger,world=quiet()
    view=observe('p01',ledger,world,cfg)
    assert view.empty_sources == (('food',0),)
    assert view.source_id=='food2' and view.source_food is None
    assert view.food_choice_changed=='food'
    choice=decide(view,cfg)
    assert choice.kind=='go' and choice.target=='food2' and 'remembered empty' in choice.reason
    step=world_step(Engine(ledger),world,cfg)
    assert step.processed.overlay.empty_sources['p01']==(('food',0),)
    away=replace(step.processed.overlay,positions={'p01':(6,4)})
    later=observe('p01',step.processed.ledger,away,cfg)
    assert later.source_id=='food2' and later.empty_sources==( ('food',0), )
    # A hidden refill must not clear memory or alter observation.
    refilled=replace(step.processed.ledger,sources={sid:replace(s,stock=8) if sid=='food' else s
                                                   for sid,s in step.processed.ledger.sources.items()})
    assert observe('p01',refilled,away,cfg)==later
    assert observe('p01',ledger,world,replace(cfg,source_memory_on=False)).source_id=='food'


def test_fresh_stock_overrides_memory_and_expiry_allows_retry():
    cfg,ledger,world=quiet()
    world=replace(world,tick=5,empty_sources={'p01':(('food',0),)})
    ledger=replace(ledger,tick=5,sources={sid:replace(s,stock=2) for sid,s in ledger.sources.items()})
    view=observe('p01',ledger,world,cfg)
    assert view.source_id=='food' and not view.empty_sources
    away=replace(world,positions={'p01':(6,4)},tick=19)
    assert observe('p01',replace(ledger,tick=19),away,cfg).source_id=='food2'
    expired=observe('p01',replace(ledger,tick=20),replace(away,tick=20),cfg)
    assert expired.source_id=='food' and not expired.empty_sources
    assert remember_empty((('food',0),),(('food',0),),19)==(('food',19),)


def test_all_empty_fallback_one_source_and_fishing_are_usable():
    cfg,ledger,world=quiet()
    empty=replace(ledger,sources={sid:replace(s,stock=0) for sid,s in ledger.sources.items()})
    all_seen=replace(cfg,perception_radius=20)
    view=observe('p01',empty,world,all_seen)
    assert view.source_id=='food' and decide(view,all_seen).kind=='wait'
    single=replace(cfg,food_sources=1)
    assert decide(observe('p01',empty,world,single),single).kind=='wait'
    fish_cfg=replace(cfg,fishing_on=True)
    fish_ledger,fish_world=genesis(fish_cfg)
    sid,bank=fishing_sites(fish_cfg)[0]
    fish_ledger=replace(fish_ledger,sources={s:replace(v,stock=0) if s==sid else v for s,v in fish_ledger.sources.items()})
    fish_world=replace(fish_world,positions={'p01':bank})
    view=observe('p01',fish_ledger,fish_world,fish_cfg)
    assert (sid,0) in view.empty_sources and view.source_id!=sid


def test_memory_does_not_bypass_child_leash():
    cfg,ledger,world=quiet()
    world=replace(world,homes=world.positions,age={'p01':0})
    view=observe('p01',ledger,world,cfg)
    assert view.food_choice_changed=='food'
    choice=decide(view,cfg)
    assert choice.kind=='rest' and choice.step is None


def test_sparse_memory_is_immutable_validated_and_round_trips():
    _,_,world=quiet()
    world=replace(world,tick=3,empty_sources={'p01':[['food',0],['fish',2]]})
    assert Overlay.from_canonical(world.canonical()).canonical()==world.canonical()
    with pytest.raises(TypeError): world.empty_sources['p01']=()
    assert world.empty_sources['p01']==(('fish',2),('food',0))
    for entries in ((('food',4),),(('food',-1),),(('food',True),),(('food',0),('food',0))):
        with pytest.raises(ValueError): replace(world,empty_sources={'p01':entries})
    with pytest.raises(ValueError): replace(world,empty_sources={'ghost':(('food',0),)})


def test_config_cli_and_old_headers_remain_unchanged():
    cfg,_,_=quiet()
    assert WorldConfig.from_describe(cfg.describe())==cfg
    off=replace(cfg,source_memory_on=False)
    assert WorldConfig.from_describe(off.describe())==off and 'source_memory' not in off.describe()
    assert genesis(off)==genesis(cfg) and run_id_for(off,100)!=run_id_for(cfg,100)
    assert config_from(build_parser().parse_args(['--seed','7','--source-memory','on'])).source_memory_on
    assert cfg.describe()['empty_source_ticks']==EMPTY_SOURCE_TICKS


def test_process_without_new_observations_preserves_then_expires_memory():
    cfg,ledger,world=quiet()
    world=replace(world,tick=5,empty_sources={'p01':(('food',0),)})
    engine=Engine(replace(ledger,tick=5)); record=engine.tick([])
    result=advance(world,{},record,engine.state,cfg)
    assert result.overlay.empty_sources==world.empty_sources
    engine=Engine(replace(ledger,tick=20)); record=engine.tick([])
    result=advance(replace(world,tick=20),{},record,engine.state,cfg)
    assert not result.overlay.empty_sources


def test_birth_keeps_other_peoples_memories_and_fishing_casts():
    cfg=WorldConfig(seed=23,actors=3,source_memory_on=True,fishing_on=True,together_ticks=1,
                    water_on=False,warmth_on=False,terrain_on=False)
    ledger,world=genesis(cfg)
    bank=fishing_sites(cfg)[0][1]
    homes=dict(world.homes,p01=(4,4),p02=(4,5))
    world=replace(world,tick=1,homes=homes,positions=dict(homes,p03=bank),
                  hunger={p:0 for p in world.roster},shelters=((4,4),(4,5)),
                  held={p:0 for p in world.roster},built={p:0 for p in world.roster},
                  empty_sources={'p03':(('food',0),)},fishing_cast={'p03':bank})
    after,grown,born=_births(world,replace(ledger,tick=1),cfg)
    assert born and after.empty_sources==world.empty_sources
    assert after.fishing_cast==world.fishing_cast
    assert all(p not in after.empty_sources and p not in after.fishing_cast for p in born)
    assert grown.totals()==ledger.totals()


def test_saved_run_replays_and_recovers_with_memories_and_visible_reroutes(tmp_path):
    cfg=WorldConfig(seed=23,source_memory_on=True,fishing_on=True,wood_on=True,homes_on=True,
                    stores_on=True,relocation_on=True,seasons_on=True,regrowth_on=True,
                    source_stock=8,source_cap=16,renewal_amount=3)
    path=tmp_path/'memory.jsonl'; result=run_world(cfg,220,path)
    run=read_run(path)
    assert run.complete and replay_world(path).identical
    assert any(e['kind']=='food_reroute' for e in build_index(run)['events'])
    assert 'Empty food remembered' in render_html(run)
    remembered=next(t['tick'] for t in run.ticks if t['world'].get('empty_sources'))
    lines=path.read_bytes().splitlines(keepends=True)
    end=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick'
             and json.loads(line).get('tick')==remembered)
    cut,recovered=tmp_path/'cut.jsonl',tmp_path/'recovered.jsonl'
    cut.write_bytes(b''.join(lines[:end+1])); recover_world(cut,recovered)
    assert read_run(recovered).ticks==run.ticks and replay_world(recovered).identical
    assert run_world(cfg,220,tmp_path/'repeat.jsonl').trail_digest==result.trail_digest
