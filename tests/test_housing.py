"""Grown children walk to visible homes; housing and caches survive saved runs."""

import json
from collections import Counter
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import RunFileError, apply_production, read_run
from world.config import WorldConfig, genesis
from world.decide import Decision, decide
from world.housing import GO_SETTLE, SETTLE, choose_site, site_available
from world.observe import observe
from world.overlay import Overlay
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html, render_text
from world.viewer_index import build_index, stock_at


def family(**changes):
    cfg = WorldConfig(seed=11, actors=4, homes_on=True, stores_on=True, terrain_on=False,
                      water_on=False, warmth_on=False, births_on=False, offers_on=False, **changes)
    ledger, overlay = genesis(cfg)
    homes = {"p01": (2,2), "p02": (3,2), "p03": (4,2), "p04": (5,2)}
    overlay = replace(overlay, homes=homes, positions=homes, hunger={p:0 for p in homes},
                      age={p:cfg.adult_at for p in homes}, parent={"p02":"p01", "p03":"p01", "p04":"p01"},
                      shelters=((2,2),), built={p:cfg.build_ticks if p == "p01" else 0 for p in homes},
                      home_caches={f"store-{p}":pos for p,pos in homes.items()})
    return cfg, replace(ledger, balances={p:3 for p in homes}), overlay


def settle_at(cfg, ledger, overlay, actors, site):
    overlay = replace(overlay, positions=dict(overlay.positions) | {p:site for p in actors})
    choices = {p:Decision(p, SETTLE, "arrived", (SETTLE,), home_site=site) for p in actors}
    engine = Engine(ledger)
    record = engine.tick([])
    return advance(overlay, choices, record, engine.state, cfg), record


def test_child_and_founder_do_not_choose_a_home_and_needs_interrupt_adult():
    cfg, ledger, overlay = family()
    assert not observe("p01", ledger, overlay, cfg).choosing_home
    child = replace(overlay, age=dict(overlay.age, p02=cfg.adult_at-1))
    assert not observe("p02", ledger, child, cfg).choosing_home
    view = observe("p02", ledger, overlay, cfg)
    assert view.choosing_home and decide(view, cfg).kind == GO_SETTLE
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    thirsty = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=thirsty.thirsty_at, water=1,
                          water_source=(1,1)), thirsty).kind == "drink"
    cold = replace(cfg, warmth_on=True)
    assert decide(replace(view, cold=cold.cold_at), cold).kind == "warm"


def test_home_changes_only_after_arrival_and_old_food_stays_put():
    cfg, ledger, overlay = family()
    sources = dict(ledger.sources)
    sources["store-p02"] = replace(sources["store-p02"], stock=2)
    ledger = replace(ledger, sources=sources)
    view = observe("p02", ledger, overlay, cfg)
    choice = decide(view, cfg)
    assert choice.home_site == (2,2) and choice.step == (2,2)
    engine = Engine(ledger)
    record = engine.tick([])
    moved = advance(overlay, {"p02":choice}, record, engine.state, cfg)
    assert moved.overlay.positions["p02"] == (2,2)
    assert moved.overlay.homes["p02"] == (3,2)
    assert moved.overlay.home_targets["p02"] == (2,2)
    view = observe("p02", moved.ledger, moved.overlay, cfg)
    assert decide(view, cfg).kind == SETTLE
    joined, _ = settle_at(cfg, moved.ledger, moved.overlay, ["p02"], (2,2))
    assert joined.overlay.homes["p02"] == (2,2)
    assert joined.overlay.home_settled["p02"] == 2
    assert not observe("p02", joined.ledger, joined.overlay, cfg).choosing_home
    assert joined.ledger.sources["store-p02"].stock == 2
    assert joined.ledger.totals() == ledger.totals()
    assert joined.overlay.built["p02"] == cfg.build_ticks
    assert joined.overlay.parent["p02"] == "p01"
    assert observe("p02", joined.ledger, joined.overlay, cfg).home_store_id == "store-p01"


def test_visible_sites_and_remembered_destination_do_not_know_hidden_changes():
    cfg, ledger, overlay = family(perception_radius=1)
    view = observe("p02", ledger, overlay, cfg)
    assert all(max(abs(pos[0]-3), abs(pos[1]-2)) <= 1 for pos,_ in view.home_options)
    assert choose_site(replace(view, home_target=(10,10)), cfg) == (10,10)
    assert choose_site(replace(view, home_target=(4,2)), cfg) != (4,2)  # visible occupied unbuilt site
    hungry = replace(view, hunger=cfg.hungry_at, home_target=(2,2))
    assert decide(hungry, cfg).kind == "eat"
    assert choose_site(replace(hungry, hunger=0), cfg) == (2,2)


def test_simultaneous_arrivals_respect_capacity_in_rotated_order():
    cfg, ledger, overlay = family()
    result, record = settle_at(cfg, ledger, overlay, ["p02","p03","p04"], (2,2))
    winner = next(p for p in record.rotated_roster if p != "p01")
    assert set(result.overlay.home_settled) == {winner}
    assert sum(result.overlay.homes[p] == (2,2) for p in result.overlay.living) == 2
    assert all(result.overlay.homes[p] == overlay.homes[p] for p in ("p02","p03","p04") if p != winner)
    # Sharing a finished shelter gives both residents the existing home warmth.
    warm_cfg = replace(cfg, warmth_on=True)
    warm_overlay = replace(result.overlay, cold={p:30 for p in result.overlay.roster})
    engine = Engine(result.ledger)
    record = engine.tick([])
    warm = advance(warm_overlay, {}, record, engine.state, warm_cfg)
    assert warm.overlay.cold["p01"] == warm.overlay.cold[winner] == 27


def test_new_home_has_empty_cache_then_can_build_and_store_food():
    cfg, ledger, overlay = family()
    result, _ = settle_at(cfg, ledger, overlay, ["p02"], (8,8))
    assert result.overlay.home_caches["home-8-8"] == (8,8)
    assert result.ledger.sources["home-8-8"].stock == 0
    assert result.ledger.totals() == ledger.totals()
    assert result.production == ({"source_created":"home-8-8"},)
    committed = replace(ledger, tick=1)
    assert apply_production(committed.canonical(), list(result.production)) == result.ledger.canonical()
    assert result.overlay.built["p02"] == 0
    current, engine = result.overlay, Engine(result.ledger)
    for _ in range(cfg.build_ticks+1):
        step = world_step(engine, current, cfg)
        current, engine = step.processed.overlay, step.engine
    assert (8,8) in current.shelters
    assert engine.state.sources["home-8-8"].stock > 0
    assert engine.state.balances["p02"] >= 1


def test_invalid_and_full_sites_death_and_underage_arrivals_do_not_settle():
    cfg, ledger, overlay = family()
    for site in ((-1,2), cfg.food_positions()[0], (4,2)):
        assert not site_available("p02", site, overlay.homes, overlay.living, overlay.shelters, cfg)
    child = replace(overlay, age=dict(overlay.age, p02=cfg.adult_at-1))
    result, _ = settle_at(cfg, ledger, child, ["p02"], (8,8))
    assert not result.overlay.home_settled
    dying = replace(overlay, hunger=dict(overlay.hunger, p02=cfg.death_at-1))
    result, _ = settle_at(cfg, ledger, dying, ["p02"], (8,8))
    assert not result.overlay.home_settled and "p02" in result.overlay.died_at
    assert "home-8-8" not in result.ledger.sources


@pytest.mark.parametrize("entry", [None, [], {"source_created":""}, {"source_created":2},
    {"source_created":"food"}, {"source_created":"new", "amount":3}])
def test_empty_source_creation_cannot_overwrite_or_smuggle_stock(entry):
    _, ledger, _ = family()
    with pytest.raises(RunFileError):
        apply_production(ledger.canonical(), [entry])


def test_source_creation_and_birth_share_authority_and_reject_duplicates():
    _, ledger, _ = family()
    produced = apply_production(ledger.canonical(), [{"source_created":"new"}, {"born":"child"}])
    assert produced["sources"]["new"]["stock"] == 0
    assert "child" in produced["sources"]["new"]["authorised"]
    with pytest.raises(RunFileError):
        apply_production(ledger.canonical(), [{"source_created":"new"}, {"source_created":"new"}])


def test_housing_without_stores_creates_no_sources():
    cfg, ledger, overlay = family()
    cfg = replace(cfg, stores_on=False)
    ledger = replace(ledger, sources={sid:s for sid,s in ledger.sources.items() if not sid.startswith("store-")})
    overlay = replace(overlay, home_caches={})
    result, _ = settle_at(cfg, ledger, overlay, ["p02"], (8,8))
    assert result.overlay.homes["p02"] == (8,8)
    assert not result.overlay.home_caches and not result.production
    assert result.ledger.sources == ledger.sources


def test_shared_residents_can_both_deposit_without_creating_food():
    cfg, ledger, overlay = family()
    joined, _ = settle_at(cfg, ledger, overlay, ["p02"], (2,2))
    sources = dict(joined.ledger.sources)
    sources["store-p01"] = replace(sources["store-p01"], stock=5)
    before = replace(joined.ledger, sources=sources)
    result = world_step(Engine(before), joined.overlay, cfg).processed
    assert result.ledger.sources["store-p01"].stock == 7  # refill target, not a hard cap
    assert result.ledger.balances["p01"] == result.ledger.balances["p02"] == 2
    assert result.ledger.totals() == before.totals()


def test_config_overlay_round_trips_and_old_shapes_stay_unchanged():
    cfg, ledger, overlay = family()
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    old = replace(cfg, homes_on=False)
    assert "homes" not in old.describe()
    assert WorldConfig.from_describe(old.describe()) == old
    old_overlay = genesis(old)[1]
    assert not any(key in old_overlay.canonical() for key in ("home_targets", "home_settled", "home_caches"))
    assert Overlay.from_canonical(overlay.canonical()) == overlay
    with pytest.raises(TypeError):
        overlay.home_caches["bad"] = (1,1)
    with pytest.raises(ValueError):
        replace(overlay, home_settled={"p02":1})
    with pytest.raises(ValueError):
        replace(overlay, home_targets={"missing":(1,1)})
    with pytest.raises(ValueError):
        replace(cfg, childhood_on=False)
    parser = build_parser()
    assert config_from(parser.parse_args(["--seed","11","--homes","on"])).homes_on
    assert not config_from(parser.parse_args(["--seed","11"])).homes_on
    assert run_id_for(cfg,300) != run_id_for(old,300)


@pytest.mark.long_run
def test_saved_housing_replays_recovers_and_viewer_follows_new_homes(tmp_path):
    cfg = WorldConfig(seed=11, homes_on=True, stores_on=True, seasons_on=True, regrowth_on=True,
                      source_stock=8, source_cap=16, renewal_amount=3)
    path = tmp_path / "homes.jsonl"
    result = run_world(cfg, 360, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    index = build_index(run)
    events = [e for e in index["events"] if e["kind"] == "home_settled"]
    assert events
    for k, tick in enumerate(run.ticks, 1):
        for entry in tick.get("production", []):
            if "source_created" in entry:
                sid = entry["source_created"]
                assert stock_at(run, k-1, sid) is None
                assert stock_at(run, k, sid) == 0
                assert sid in render_text(run, k)
    for tick in run.ticks:
        w = tick["world"]
        occupancy = Counter(tuple(pos) for p,pos in w["homes"].items() if p not in w["died_at"])
        assert max(occupancy.values()) <= 2
        assert all(sid in tick["state"]["sources"] or {"source_created":sid} in (tick.get("production") or [])
                   for sid in w.get("home_caches", {}))
    page = render_html(run)
    assert "Shares home with" in page and "home_settled" in page
    lines = path.read_bytes().splitlines(keepends=True)
    cut_at = next(i for i,raw in enumerate(lines) if json.loads(raw).get("kind") == "tick"
                  and json.loads(raw).get("tick") == events[0]["k"]-1)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:cut_at+1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
    assert replay_world(restored).identical
    assert run_world(cfg,360,tmp_path / "repeat.jsonl").trail_digest == result.trail_digest
