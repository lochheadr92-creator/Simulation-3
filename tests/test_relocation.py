"""Experience, bounded knowledge, physical moves, and saved relocation runs."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import Decision, decide
from world.housing import (GO_RELOCATE, RELOCATE, LONG_OUTING, DIFFICULT_OUTINGS,
                           MOVE_COOLDOWN, choose_relocation, update_experience)
from world.observe import observe
from world.overlay import Overlay
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world
from world.viewer import render_html
from world.viewer_index import build_index


def household():
    cfg=WorldConfig(seed=11, actors=3, homes_on=True, relocation_on=True, stores_on=True,
                    terrain_on=False, water_on=False, warmth_on=False, births_on=False, offers_on=False)
    ledger, overlay=genesis(cfg)
    # The primary food landmark is (6,6); (5,6) is a seen shelter four steps nearer.
    homes={'p01':(1,6),'p02':(5,6),'p03':(1,8)}
    overlay=replace(overlay,tick=MOVE_COOLDOWN,homes=homes,positions=dict(homes,p01=(3,6)),
                    hunger={p:0 for p in homes},shelters=((1,6),(5,6)),
                    built={p:cfg.build_ticks for p in homes},home_strain={'p01':DIFFICULT_OUTINGS},
                    home_caches={f'store-{p}':pos for p,pos in homes.items()})
    return cfg,replace(ledger,tick=MOVE_COOLDOWN),overlay


def test_only_completed_supply_outings_raise_strain_and_short_ones_ease_it():
    cfg,ledger,overlay=household()
    current=replace(overlay,home_strain={},home_trip_ticks={})
    for outing in range(DIFFICULT_OUTINGS):
        for _ in range(LONG_OUTING):
            previous=current
            current=update_experience(previous,replace(current,tick=current.tick+1),
                {'p01':Decision('p01','go','food',('go',))},{},cfg)
        assert current.home_strain.get('p01',0)==outing
        returned=replace(current,tick=current.tick+1,positions=dict(current.positions,p01=(1,6)))
        current=update_experience(current,returned,{'p01':Decision('p01','home','return',('home',))},{},cfg)
        assert current.home_strain['p01']==outing+1
        current=replace(current,positions=dict(current.positions,p01=(3,6)))
    # A short supply outing is relief; simply resting or helping is not supply effort.
    short=replace(current,home_trip_ticks={'p01':1})
    returned=replace(short,positions=dict(short.positions,p01=(1,6)))
    assert update_experience(short,returned,{}, {},cfg).home_strain['p01']==2
    helping=update_experience(current,current,{'p01':Decision('p01','go_offer','help',('go_offer',))},{},cfg)
    assert not helping.home_trip_ticks


def test_strain_alone_cannot_reveal_unseen_homes_or_hidden_occupancy():
    cfg,ledger,overlay=household()
    view=observe('p01',ledger,overlay,cfg)
    assert view.relocating and choose_relocation(view,cfg)==(5,6)
    far=replace(overlay,positions=dict(overlay.positions,p01=(0,0)))
    assert choose_relocation(observe('p01',ledger,far,cfg),cfg) is None
    remembered=replace(far,shelter_memory={'p01':((5,6),)})
    assert choose_relocation(observe('p01',ledger,remembered,cfg),cfg)==(5,6)
    full=replace(remembered,homes=dict(remembered.homes,p03=(5,6)))
    assert (5,6) in observe('p01',ledger,full,cfg).known_homes  # still outside sight
    visible=replace(full,positions=dict(full.positions,p01=(3,6)))
    assert (5,6) not in observe('p01',ledger,visible,cfg).known_homes
    visible=replace(visible,home_targets={'p01':(5,6)})
    refreshed=update_experience(visible,visible,{}, {'p01':observe('p01',ledger,visible,cfg)},cfg)
    assert 'p01' not in refreshed.home_targets


@pytest.mark.parametrize('change', ['child','dependent','cooldown','low_strain','first_home'])
def test_relocation_waits_for_eligibility(change):
    cfg,ledger,overlay=household()
    if change=='child': overlay=replace(overlay,age=dict(overlay.age,p01=cfg.adult_at-1))
    if change=='dependent': overlay=replace(overlay,parent={'p03':'p01'},age=dict(overlay.age,p03=0))
    if change=='cooldown': overlay=replace(overlay,home_settled={'p01':overlay.tick-1})
    if change=='low_strain': overlay=replace(overlay,home_strain={'p01':2})
    if change=='first_home': overlay=replace(overlay,parent={'p01':'p02'})
    assert not observe('p01',ledger,overlay,cfg).relocating


def test_needs_interrupt_but_a_destination_is_remembered():
    cfg,ledger,overlay=household()
    view=observe('p01',ledger,overlay,cfg)
    choice=decide(view,cfg)
    assert choice.kind==GO_RELOCATE and choice.home_site==(5,6)
    hungry=replace(view,hunger=cfg.hungry_at,food=1,home_target=(5,6))
    assert decide(hungry,cfg).kind=='eat'
    assert choose_relocation(replace(hungry,hunger=0),cfg)==(5,6)
    assert choose_relocation(replace(view,known_homes=((0,6),)),cfg) is None


def test_warm_before_departure_and_use_nearer_finished_shelter_for_warmth():
    cfg,ledger,overlay=household()
    cfg=replace(cfg,warmth_on=True)
    overlay=replace(overlay,cold={p:10 for p in overlay.roster},
                    positions=dict(overlay.positions,p01=(1,6)),shelter_memory={'p01':((5,6),)})
    view=observe('p01',ledger,overlay,cfg)
    assert decide(view,cfg).kind=='warm'
    assert decide(replace(view,cold=0),cfg).kind==GO_RELOCATE
    # Need-driven warmth can use the new shelter once it is the nearer remedy.
    away=replace(view,position=(4,6),cold=cfg.cold_at,home_target=(5,6))
    assert decide(away,cfg).kind==GO_RELOCATE
    assert decide(replace(away,position=(5,6)),cfg).kind==RELOCATE
    assert decide(replace(away,position=(2,6)),cfg).kind=='go_shelter'
    assert decide(replace(away,hunger=cfg.death_at-2,food=1),cfg).kind=='eat'


def test_arrival_resets_effort_but_keeps_old_food_shelter_and_family_links():
    cfg,ledger,overlay=household()
    sources=dict(ledger.sources)
    sources['store-p01']=replace(sources['store-p01'],stock=4)
    ledger=replace(ledger,sources=sources)
    overlay=replace(overlay,positions=dict(overlay.positions,p01=(5,6)),home_trip_ticks={'p01':11},
                    home_targets={'p01':(5,6)},parent={'p03':'p01'},
                    together={'p01|p02':2})  # p03 is grown; the family link remains
    engine=Engine(ledger); record=engine.tick([])
    result=advance(overlay,{'p01':decide(observe('p01',ledger,overlay,cfg),cfg)},record,engine.state,cfg)
    assert result.overlay.homes['p01']==(5,6)
    assert result.overlay.home_settled['p01']==overlay.tick+1
    assert not result.overlay.home_strain and not result.overlay.home_trip_ticks
    assert not result.overlay.home_targets and not result.overlay.together
    assert result.overlay.parent==overlay.parent and result.overlay.shelters==overlay.shelters
    assert result.ledger.sources['store-p01'].stock==4 and result.ledger.totals()==ledger.totals()
    assert observe('p01',result.ledger,result.overlay,cfg).home_store_id=='store-p02'
    assert not result.production


def test_last_place_contention_and_death_cannot_teleport_or_move_food():
    cfg,ledger,overlay=household()
    overlay=replace(overlay,positions=dict(overlay.positions,p01=(5,6),p03=(5,6)),
                    home_strain={'p01':3,'p03':3})
    choices={p:Decision(p,RELOCATE,'arrived',(RELOCATE,),home_site=(5,6)) for p in ('p01','p03')}
    engine=Engine(ledger); record=engine.tick([])
    result=advance(overlay,choices,record,engine.state,cfg)
    winner=next(p for p in record.rotated_roster if p in choices)
    assert set(result.overlay.home_settled)=={winner}
    assert sum(result.overlay.homes[p]==(5,6) for p in result.overlay.living)==2
    dying=replace(overlay,hunger=dict(overlay.hunger,p01=cfg.death_at-1))
    result=advance(dying,{'p01':choices['p01']},record,engine.state,cfg)
    assert 'p01' in result.overlay.died_at and 'p01' not in result.overlay.home_settled
    away=replace(overlay,positions=dict(overlay.positions,p01=(3,6)))
    result=advance(away,{'p01':choices['p01']},record,engine.state,cfg)
    assert result.overlay.homes['p01']==(1,6)


def test_state_config_and_cli_round_trip_without_changing_old_shapes():
    cfg,ledger,overlay=household()
    overlay=replace(overlay,shelter_memory={'p01':((5,6),)},home_trip_ticks={'p01':4})
    assert Overlay.from_canonical(overlay.canonical())==overlay
    assert WorldConfig.from_describe(cfg.describe())==cfg
    old=replace(cfg,relocation_on=False)
    assert 'relocation' not in old.describe() and WorldConfig.from_describe(old.describe())==old
    assert run_id_for(cfg,480)!=run_id_for(old,480)
    assert not any(k in genesis(old)[1].canonical() for k in ('home_trip_ticks','home_strain','shelter_memory'))
    with pytest.raises(ValueError): replace(cfg,homes_on=False)
    with pytest.raises(ValueError): replace(overlay,home_strain={'p01':-1})
    with pytest.raises(ValueError): replace(overlay,shelter_memory={'missing':((1,1),)})
    with pytest.raises(TypeError): overlay.shelter_memory['p01']=()
    args=build_parser().parse_args(['--seed','11','--homes','on','--relocation','on'])
    assert config_from(args).relocation_on


def test_recorded_move_repeats_and_recovers_mid_journey(tmp_path):
    cfg=WorldConfig(seed=7,homes_on=True,relocation_on=True,stores_on=True,seasons_on=True,
                    regrowth_on=True,source_stock=8,source_cap=16,renewal_amount=3)
    path=tmp_path/'relocation.jsonl'
    result=run_world(cfg,300,path)
    run=read_run(path)
    assert run.complete and replay_world(path).identical
    events=build_index(run)['events']
    moves=[e for e in events if e['kind']=='relocated']
    journeys=[e for e in events if e['kind']=='relocation_journey']
    assert moves and journeys
    event=moves[0]; k=event['k']; person=event['who']
    before,after=run.ticks[k-2]['world'],run.ticks[k-1]['world']
    assert before['homes'][person]!=after['homes'][person]
    assert before['positions'][person]==after['homes'][person]  # actual arrival before moving home
    assert after.get('home_strain',{}).get(person,0)==0
    assert not any(e.get('amount',0) for e in run.ticks[k-1].get('production',[])
                   if e.get('source','').startswith(('store-','home-')))
    page=render_html(run)
    assert 'Home strain:' in page and 'go_relocate' in page
    journey=journeys[0]['k']
    assert run.ticks[journey-1]['world']['home_targets']
    lines=path.read_bytes().splitlines(keepends=True)
    cut_at=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick'
                and json.loads(line).get('tick')==journey-1)
    cut,restored=tmp_path/'cut.jsonl',tmp_path/'restored.jsonl'
    cut.write_bytes(b''.join(lines[:cut_at+1]))
    recover_world(cut,restored)
    assert read_run(restored).ticks==run.ticks and replay_world(restored).identical
    assert run_world(cfg,300,tmp_path/'repeat.jsonl').trail_digest==result.trail_digest
