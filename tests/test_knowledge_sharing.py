"""Firsthand sightings cross one local encounter and change later foraging."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import decide
from world.foraging import remember_sightings, usable_reports, update_reports
from world.observe import observe
from world.overlay import Overlay
from world.process import _births
from world.run import world_step, run_world, build_parser, config_from, run_id_for
from world.replay import replay_world
from world.recover import recover_world
from world.viewer import render_html
from world.viewer_index import build_index


def house():
    cfg = WorldConfig(seed=7, actors=3, source_memory_on=True, knowledge_sharing_on=True,
                      terrain_on=False, water_on=False, warmth_on=False, births_on=False,
                      offers_on=False, building_on=False, perception_radius=1,
                      renewal_every=1000, stagger_start=False)
    ledger, world = genesis(cfg)
    source = cfg.source_position
    home = (source[0]-2, source[1])
    homes = {p: home for p in world.roster}
    ledger = replace(ledger, balances={p: 0 for p in world.roster},
                     sources={s: replace(v, stock=0) if s=='food' else v for s,v in ledger.sources.items()})
    world = replace(world, homes=homes, positions=dict(homes, p01=(source[0]-1, source[1]), p03=(0,0)),
                    hunger={p: 0 for p in world.roster}, held={p: 0 for p in world.roster})
    return cfg, ledger, world


def test_actual_sighting_speech_later_choice_and_meal():
    cfg, ledger, world = house()
    first = world_step(Engine(ledger), world, cfg)
    silent = world_step(Engine(ledger), world, replace(cfg, knowledge_sharing_on=False))
    assert first.decisions['p01'].source_report == ('food', 0)
    assert first.decisions['p01'].report_to == ('p02',)
    assert first.decisions['p02'].target == silent.decisions['p02'].target
    assert first.record.canonical() == silent.record.canonical()
    assert first.processed.overlay.source_reports == {'p02': (('food','p01',0,1),)}
    assert 'p03' not in first.processed.overlay.source_reports
    later = replace(first.processed.overlay, hunger=dict(first.processed.overlay.hunger,p02=cfg.hungry_at))
    view = observe('p02', first.engine.state, later, cfg)
    actual = decide(view,cfg)
    counterfactual = decide(observe('p02', first.engine.state, later, replace(cfg,knowledge_sharing_on=False)),
                            replace(cfg,knowledge_sharing_on=False))
    assert actual.kind == counterfactual.kind == 'go'
    assert actual.target == 'food2' and counterfactual.target == 'food'
    assert 'p01 reported food empty at tick 0' in actual.reason
    assert not view.empty_sources  # hearing does not become a firsthand sighting
    step = world_step(first.engine, later, cfg)
    collected = ate = False
    for _ in range(25):
        collected |= step.decisions['p02'].kind == 'claim' and any(o.actor=='p02' and o.accepted for o in step.record.outcomes)
        ate |= collected and step.decisions['p02'].kind == 'eat'
        assert step.engine.state.totals() == ledger.totals()
        if ate: break
        step = world_step(step.engine,step.processed.overlay,cfg)
    assert collected and ate
    assert not world.source_reports and not world.food_sightings


@pytest.mark.parametrize('changes', [
    {'positions': {'p01':(5,6),'p02':(3,6),'p03':(0,0)}},
    {'homes': {'p01':(4,6),'p02':(0,0),'p03':(4,6)}},
    {'died_at': {'p01':0}},
])
def test_nonadjacent_nonhousemate_or_dead_speaker_cannot_tell(changes):
    cfg, ledger, world = house()
    step = world_step(Engine(ledger),replace(world,**changes),cfg)
    assert not step.processed.overlay.source_reports


def test_reports_cannot_be_relayed_and_repetition_does_not_refresh_age():
    cfg,ledger,world=house()
    first=world_step(Engine(ledger),world,cfg)
    ov=replace(first.processed.overlay,positions=world.homes)
    second=world_step(first.engine,ov,cfg)
    assert second.decisions['p02'].source_report is None
    assert second.processed.overlay.source_reports['p02']==(('food','p01',0,1),)
    assert not second.processed.overlay.empty_sources.get('p02')
    expired=observe('p02',replace(second.engine.state,tick=20),replace(ov,tick=20),cfg)
    assert not expired.source_reports and expired.source_id=='food'


def test_current_sight_and_newer_personal_sight_override_stale_report():
    cfg,ledger,world=house()
    report=(('food','p01',0,1),)
    world=replace(world,tick=2,source_reports={'p02':report},positions=dict(world.positions,p02=cfg.source_position))
    ledger=replace(ledger,tick=2,sources={s:replace(v,stock=2) for s,v in ledger.sources.items()})
    seen=observe('p02',ledger,world,cfg)
    assert seen.source_id=='food' and not seen.source_reports
    # Its own newer stocked sighting remains decisive after moving out of sight.
    assert not usable_reports(report,seen.food_sightings,3)
    assert not usable_reports(report,(('food',0,2),),3)
    assert usable_reports(report,(),3)==report
    assert remember_sightings((('food',1,2),),(),22)==()


def test_unseen_refill_or_speaker_death_supplies_no_remote_update():
    cfg,ledger,world=house()
    step=world_step(Engine(ledger),world,cfg)
    world=replace(step.processed.overlay,positions=dict(world.homes,p01=(0,0)))
    before=observe('p02',step.engine.state,world,cfg)
    hidden=replace(step.engine.state,sources={s:replace(v,stock=8) for s,v in step.engine.state.sources.items()})
    assert observe('p02',hidden,replace(world,died_at={'p01':1}),cfg)==before


def test_newer_reports_win_deterministically_without_rejuvenation():
    cfg,ledger,world=house()
    world=replace(world,tick=5,positions=world.homes,
                  food_sightings={'p01':(('food',0,2),),'p03':(('food',0,3),)})
    views={p:observe(p,replace(ledger,tick=5),world,cfg) for p in world.living}
    choices={p:decide(v,cfg) for p,v in views.items()}
    a=update_reports(world,choices,views,{},6)
    b=update_reports(world,dict(reversed(list(choices.items()))),views,{},6)
    assert a==b and a[1]['p02']==(('food','p03',3,6),)
    tied=replace(world,food_sightings={'p01':(('food',0,3),),'p03':(('food',0,3),)})
    views={p:observe(p,replace(ledger,tick=5),tied,cfg) for p in tied.living}
    assert update_reports(tied,{p:decide(v,cfg) for p,v in views.items()},views,{},6)[1]['p02']==(('food','p01',3,6),)


def test_child_limits_needs_and_all_empty_fallback_remain():
    cfg,ledger,world=house()
    step=world_step(Engine(ledger),world,cfg)
    view=observe('p02',step.engine.state,step.processed.overlay,cfg)
    assert decide(replace(view,food=1,hunger=cfg.hungry_at),cfg).kind=='eat'
    child=replace(view,age=0,hunger=cfg.hungry_at)
    assert decide(child,replace(cfg,child_leash=1)).kind=='rest'
    assert decide(replace(view,food=0,hunger=cfg.hungry_at,alive=False),cfg).source_report is None
    all_empty=replace(step.processed.overlay,source_reports={'p02':(('food','p01',0,1),('food2','p01',0,1))})
    assert observe('p02',step.engine.state,all_empty,cfg).source_id=='food'


def test_serialization_validation_births_and_deaths():
    cfg,ledger,world=house()
    step=world_step(Engine(ledger),world,cfg)
    ov=step.processed.overlay
    assert Overlay.from_canonical(ov.canonical()).canonical()==ov.canonical()
    with pytest.raises(TypeError): ov.source_reports['p02']=()
    for entry in [('food','p02',0,1),('food','ghost',0,1),('food','p01',1,1),('food','p01',0,2),('food','p01',True,1)]:
        with pytest.raises(ValueError): replace(ov,source_reports={'p02':(entry,)})
    for entry in [('food',True,0),('food',2,0),('food',0,2)]:
        with pytest.raises(ValueError): replace(ov,food_sightings={'p01':(entry,)})
    assert not Overlay.from_canonical(world.canonical()).source_reports
    home=world.homes['p01']
    parents=replace(ov,positions=dict(world.homes,p01=(home[0]+1,home[1])),
                    built={p:cfg.build_ticks for p in world.roster},shelters=(home,),
                    hunger={p:0 for p in world.roster},held={p:0 for p in world.roster})
    grown=replace(cfg,births_on=True,together_ticks=1)
    born,_,production=_births(parents,step.engine.state,grown)
    assert production and set(production) == set(born.roster) - set(parents.roster)
    assert born.source_reports==parents.source_reports and born.food_sightings==parents.food_sightings
    sightings,reports=update_reports(ov,{}, {}, {'p02':2},2)
    assert 'p02' not in reports


def test_cli_header_and_disabled_compatibility():
    cfg,_,_=house()
    assert WorldConfig.from_describe(cfg.describe())==cfg
    off=replace(cfg,knowledge_sharing_on=False)
    assert 'knowledge_sharing' not in off.describe()
    assert WorldConfig.from_describe(off.describe())==off
    assert genesis(cfg)==genesis(off) and run_id_for(cfg,10)!=run_id_for(off,10)
    parsed=config_from(build_parser().parse_args(['--seed','7','--source-memory','on','--knowledge-sharing','on']))
    assert parsed.knowledge_sharing_on
    with pytest.raises(ValueError): replace(cfg,source_memory_on=False)


def test_saved_reports_replay_recovery_and_viewer(tmp_path):
    cfg=WorldConfig(seed=23, source_memory_on=True,knowledge_sharing_on=True,
                    stores_on=True,homes_on=True,provisioning_on=True,coordination_on=True,
                    fishing_on=True,regrowth_on=True,seasons_on=True,birth_spacing=30)
    path=tmp_path/'knowledge.jsonl'
    run_world(cfg,360,path)
    run=read_run(path)
    active=next(t for t in run.ticks if t['world'].get('source_reports'))
    assert replay_world(path).identical
    again=tmp_path/'again.jsonl'; run_world(cfg,360,again)
    assert read_run(again).ticks==run.ticks
    lines=path.read_bytes().splitlines(keepends=True)
    cut_at=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick'
                and json.loads(line).get('tick')==active['tick'])
    cut=tmp_path/'cut.jsonl'; recovered=tmp_path/'recovered.jsonl'
    cut.write_bytes(b''.join(lines[:cut_at+1]))
    recover_world(cut,recovered)
    assert read_run(recovered).ticks==run.ticks
    assert replay_world(recovered).identical
    assert any(e['kind']=='source_report_heard' for e in build_index(run)['events'])
    assert 'Food reports heard' in render_html(run)


def test_report_attribution_after_personal_memory_already_ruled_out_another_source():
    cfg,ledger,world=house()
    cfg=replace(cfg,fishing_on=True,perception_radius=0)
    ledger,_=genesis(cfg)
    world=replace(world,tick=2,positions=world.homes,hunger={p:cfg.hungry_at for p in world.roster})
    ledger=replace(ledger,tick=2,balances={p:0 for p in world.roster})
    first=observe('p02',ledger,world,cfg).source_id
    own=replace(world,empty_sources={'p02':((first,0),)})
    second=observe('p02',ledger,own,cfg).source_id
    assert first!=second
    reported=replace(own,source_reports={'p02':((second,'p01',1,2),)})
    view=observe('p02',ledger,reported,cfg)
    assert view.source_id not in (first,second)
    assert view.food_choice_changed==first and view.report_food_avoided==second
    assert f'p01 reported {second} empty at tick 1' in decide(view,cfg).reason
    # Provisioning uses the same information and attributes its own source change.
    provision_cfg=replace(cfg,stores_on=True,provisioning_on=True)
    ledger,_=genesis(provision_cfg)
    ledger=replace(ledger,tick=2,balances={p:0 for p in world.roster})
    reported=replace(reported,shelters=(world.homes['p02'],),positions=world.homes,
                     hunger={p:0 for p in world.roster})
    # Use a real founding home cache for the controlled resident.
    from world.config import store_sites
    home=next(pos for sid,pos,resident in store_sites(provision_cfg) if resident=='p02')
    reported=replace(reported,homes=dict(reported.homes,p02=home),
                     positions=dict(reported.positions,p02=home),shelters=(home,))
    blank=replace(reported,empty_sources={},source_reports={})
    first=observe('p02',ledger,blank,provision_cfg).provision_source[0]
    own=replace(blank,empty_sources={'p02':((first,0),)})
    second=observe('p02',ledger,own,provision_cfg).provision_source[0]
    reported=replace(own,source_reports={'p02':((second,'p01',1,2),)})
    view=observe('p02',ledger,reported,provision_cfg)
    assert view.report_provision_avoided==second
    decision=decide(view,provision_cfg)
    assert decision.provisioning=='gather'
    assert f'p01 reported {second} empty at tick 1' in decision.reason
