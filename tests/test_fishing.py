"""Fishing takes time, conserves food and stays productive in either season."""
import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, fishing_sites, genesis
from world.decide import Decision, decide
from world.fishing import FISH_SOURCE, FISH_STOCK
from world.observe import observe
from world.overlay import Overlay
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, proposals_for, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index


def at_bank(actors=1, **kwargs):
    cfg = WorldConfig(seed=23, actors=actors, fishing_on=True, terrain_on=False,
                      water_on=False, warmth_on=False, offers_on=False, births_on=False,
                      hunger_rate=0, **kwargs)
    ledger, world = genesis(cfg)
    bank = fishing_sites(cfg)[0][1]
    ledger = replace(ledger, balances={p: 0 for p in world.roster})
    world = replace(world, positions={p: bank for p in world.roster},
                    hunger={p: cfg.hungry_at for p in world.roster})
    return cfg, ledger, world


def test_layout_defaults_headers_and_cli():
    cfg = WorldConfig(seed=7, fishing_on=True, wood_on=True)
    old = replace(cfg, fishing_on=False)
    ledger, world = genesis(cfg)
    before, prior = genesis(old)
    assert world == prior and cfg.terrain() == old.terrain()
    assert ledger.balances == before.balances
    assert ledger.sources[FISH_SOURCE].stock == FISH_STOCK
    assert len(set(cfg.all_source_positions())) == len(cfg.all_source_positions())
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    assert WorldConfig.from_describe(old.describe()) == old
    assert 'fishing' not in old.describe() and FISH_SOURCE not in before.sources
    assert run_id_for(cfg, 100) != run_id_for(old, 100)
    assert config_from(build_parser().parse_args(['--seed', '7', '--fishing', 'on'])).fishing_on
    with pytest.raises(ValueError):
        replace(cfg, fishing_on=1)


def test_cast_catch_and_eat_are_separate_conserved_ticks():
    cfg, ledger, world = at_bank()
    first = world_step(Engine(ledger), world, cfg)
    assert first.decisions['p01'].kind == 'fish'
    assert 'fish' in first.decisions['p01'].candidates
    assert 'claim' not in first.decisions['p01'].candidates
    assert first.engine.state.balances['p01'] == 0
    assert first.processed.overlay.fishing_cast['p01'] == world.positions['p01']
    second = world_step(first.engine, first.processed.overlay, cfg)
    assert second.decisions['p01'].kind == 'claim'
    assert second.decisions['p01'].target == FISH_SOURCE
    assert second.engine.state.balances['p01'] == cfg.claim_amount
    assert second.engine.state.sources[FISH_SOURCE].stock == FISH_STOCK-cfg.claim_amount
    assert second.engine.state.totals() == ledger.totals()
    assert not second.processed.overlay.fishing_cast
    third = world_step(second.engine, second.processed.overlay, cfg)
    assert third.decisions['p01'].kind == 'eat'
    assert third.engine.state.totals() == ledger.totals()
    saved = first.processed.overlay.canonical()
    assert Overlay.from_canonical(saved).canonical() == saved
    with pytest.raises(TypeError):
        first.processed.overlay.fishing_cast['p01'] = (0, 0)


def test_interrupted_cast_starts_again_and_last_fish_is_not_duplicated():
    cfg, ledger, world = at_bank(2)
    ledger = replace(ledger, sources={sid: replace(s, stock=1 if sid == FISH_SOURCE else 0)
                                     for sid,s in ledger.sources.items()})
    first = world_step(Engine(ledger), world, cfg)
    assert all(d.kind == 'fish' for d in first.decisions.values())
    second = world_step(first.engine, first.processed.overlay, cfg)
    assert sum(o.accepted for o in second.record.outcomes) == 1
    assert sum(second.engine.state.balances.values()) == 1
    assert second.engine.state.totals() == ledger.totals()
    paused_engine = Engine(first.processed.ledger)
    paused_record = paused_engine.tick([])
    interrupted = advance(first.processed.overlay, {'p01': Decision('p01','rest','interrupted',())},
                          paused_record, paused_engine.state, cfg)
    assert not interrupted.overlay.fishing_cast
    assert decide(observe('p01', interrupted.ledger, interrupted.overlay, cfg), cfg).kind == 'fish'


@pytest.mark.parametrize('tick', [11, 119, 131, 239])
def test_renewal_is_explicit_capped_and_independent_of_season_and_patch_wear(tick):
    cfg, ledger, world = at_bank(seasons_on=True, regrowth_on=True, renewal_amount=0)
    for stock, expected in [(0, 2), (5, 1), (6, 0)]:
        initial = replace(ledger, tick=tick, sources={sid: replace(s, stock=stock) if sid==FISH_SOURCE else s
                                                    for sid,s in ledger.sources.items()})
        engine = Engine(initial); record = engine.tick([])
        result = advance(replace(world, tick=tick), {}, record, engine.state, cfg)
        assert result.ledger.sources[FISH_SOURCE].stock == stock+expected
        assert result.production == (({'source': FISH_SOURCE, 'amount': expected},) if expected else ())
        assert FISH_SOURCE not in result.overlay.patch_condition


def test_stock_stays_local_and_a_child_cannot_bypass_the_leash():
    cfg, ledger, world = at_bank()
    far = replace(world, positions={'p01': (11, 11)})
    view = observe('p01', ledger, far, cfg)
    assert FISH_SOURCE not in dict(view.seen_stock)
    child = replace(observe('p01', ledger, world, cfg), position=(11,11), home=(11,11), age=0)
    decision = decide(child, cfg)
    assert decision.kind not in ('fish','claim','go')


def test_scoring_records_the_cast_and_urgent_water_interrupts_it():
    cfg, ledger, world = at_bank(scoring_on=True)
    view = observe('p01', ledger, world, cfg)
    choice = decide(view, cfg)
    assert choice.kind == 'fish' and dict(choice.scores)['fish'] == (1, 0)
    wet = replace(cfg, scoring_on=False, water_on=True)
    interrupted = decide(replace(view, fishing_ready=True, thirst=wet.thirst_emergency_at,
                                 water=1, water_source=wet.water_positions()[0]), wet)
    assert interrupted.kind == 'drink'


def test_saved_run_replays_recovers_mid_cast_and_viewer_shows_fishing(tmp_path):
    cfg = WorldConfig(seed=23, fishing_on=True, wood_on=True, homes_on=True, stores_on=True,
                      relocation_on=True, seasons_on=True, regrowth_on=True,
                      source_stock=8, source_cap=16, renewal_amount=3)
    path = tmp_path/'fishing.jsonl'
    result = run_world(cfg, 180, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    cast = next(t['tick'] for t in run.ticks if t['world'].get('fishing_cast'))
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick'
               and json.loads(line).get('tick')==cast)
    cut, recovered = tmp_path/'cut.jsonl', tmp_path/'recovered.jsonl'
    cut.write_bytes(b''.join(lines[:end+1]))
    recover_world(cut, recovered)
    assert read_run(recovered).ticks == run.ticks and replay_world(recovered).identical
    assert run_world(cfg, 180, tmp_path/'repeat.jsonl').trail_digest == result.trail_digest
    index = build_index(run)
    assert any(s.get('fishing') for s in index['food'])
    assert any('caught' in e.get('text','') for e in index['events'])
    assert 'casting from the bank' in render_html(run) and 'fishing spot' in render_html(run)
