"""Warmth, the third need, and shelter, the place that meets it (2026-09-27).

Warmth is the one need with no resource behind it. Food and water are kernel
resources that people claim, carry and consume; cold is a level that rises on
every tick ending away from a person's own home cell and falls on every tick
ending on it. Nothing is produced, moved or conserved, so the kernel is not
involved at all: shelter is a place, not a stock.

Warmth is on by default from 2026-09-27; off leaves the world exactly as it
was before it existed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import (DRINK, EAT, GO, GO_SHELTER, GO_WATER, HOME, WARM, decide, shelter_trip_due, slack,
                          warmth_candidates)
from world.observe import Observation
from world.overlay import Overlay
from world.process import advance
from world.replay import replay_world
from world.run import run_id_for, run_world


def warm_cfg(**changes) -> WorldConfig:
    """Warmth on, water off, so the warmth rules can be read on their own."""
    base = dict(seed=7, water_on=False, warmth_on=True)
    base.update(changes)
    return WorldConfig(**base)


def ob(**changes) -> Observation:
    base = dict(actor="p01", tick=0, alive=True, position=(0, 0), home=(0, 0), hunger=0, food=0,
                source=(6, 6), source_food=None, cold=0)
    base.update(changes)
    return Observation(**base)


# --- off is off ----------------------------------------------------------------

def test_warmth_off_leaves_the_world_as_it_was():
    cfg = WorldConfig(seed=7, warmth_on=False)   # warmth is on by default from 2026-09-27
    assert not cfg.warmth_on
    assert "warmth" not in cfg.describe() and not run_id_for(cfg, 10).endswith("-warmthon")
    _, overlay = genesis(cfg)
    assert "cold" not in overlay.canonical() and not overlay.cold


def test_warmth_on_genesis_and_round_trip():
    cfg = warm_cfg()
    _, overlay = genesis(cfg)
    assert dict(overlay.cold) == {actor: 0 for actor in cfg.actor_ids()}
    assert overlay.canonical()["cold"] == dict(overlay.cold)
    described = cfg.describe()
    assert described["warmth"] == "on" and described["cold_death_at"] == cfg.cold_death_at
    assert WorldConfig.from_describe(described) == cfg
    assert run_id_for(cfg, 10).endswith("-warmthon")
    with_water = WorldConfig(seed=7, warmth_on=True)          # alongside water, the default
    assert WorldConfig.from_describe(with_water.describe()) == with_water


def test_scoring_has_no_warmth_actions_so_the_two_are_refused_together():
    with pytest.raises(ValueError):
        WorldConfig(seed=7, water_on=False, warmth_on=True, scoring_on=True)


# --- the rule ------------------------------------------------------------------

def test_shelter_is_the_persons_own_home_cell():
    assert ob(position=(2, 2), home=(2, 2)).sheltered
    assert not ob(position=(2, 3), home=(2, 2)).sheltered


def test_warm_at_shelter_walk_to_it_when_cold_and_nothing_when_warm_enough():
    cfg = warm_cfg()
    assert warmth_candidates(ob(cold=0), cfg) == ()                       # at home, not cold: nothing to do
    assert warmth_candidates(ob(cold=cfg.cold_at), cfg) == (WARM,)
    away = dict(position=(4, 0), home=(0, 0))
    walking = decide(ob(cold=cfg.cold_at, **away), cfg)
    assert walking.kind == GO_SHELTER and walking.step == (3, 0)          # one step toward home
    warming = decide(ob(cold=cfg.cold_at), cfg)
    assert warming.kind == WARM and warming.step is None                  # warming is staying put


def test_leaving_in_time_for_shelter():
    """4 steps from home at cold_rate 1: due at cold 21, so arrival is at cold_at."""
    cfg = warm_cfg()
    away = dict(position=(4, 0), home=(0, 0))
    assert shelter_trip_due(ob(cold=21, **away), cfg) and not shelter_trip_due(ob(cold=20, **away), cfg)
    assert decide(ob(cold=21, **away), cfg).kind == GO_SHELTER
    assert not shelter_trip_due(ob(cold=21), cfg)                         # already sheltered
    assert not shelter_trip_due(ob(cold=21, **away), warm_cfg(plan_trips=False))


def test_a_person_who_is_not_sheltered_keeps_getting_colder_whatever_they_chose():
    """DOCTRINE 1: the need does not pause because the person is busy elsewhere."""
    cfg = warm_cfg(width=7, height=7, actors=2)
    ledger, overlay = genesis(cfg)
    engine = Engine(ledger)
    resting = advance(overlay, {}, engine.tick([]), engine.state, cfg)    # everyone starts at home
    assert all(value == 0 for value in resting.overlay.cold.values())     # floored: 0 - warming is 0
    moved = {a: (overlay.homes[a][0] + 1, overlay.homes[a][1]) for a in cfg.actor_ids()}
    away = Overlay(tick=0, homes=overlay.homes, positions=moved, hunger=dict(overlay.hunger),
                   yield_at=overlay.yield_at, cold={a: 10 for a in cfg.actor_ids()})
    engine = Engine(ledger)
    out = advance(away, {}, engine.tick([]), engine.state, cfg)
    assert all(value == 10 + cfg.cold_rate for value in out.overlay.cold.values())


def test_cold_falls_at_shelter_floored_at_zero_and_kills_at_its_lethal_level():
    cfg = warm_cfg(width=7, height=7, actors=1, hungry_at=9_000, emergency_at=9_500, death_at=10_000)
    ledger, overlay = genesis(cfg)
    home = overlay.homes["p01"]
    chilled = Overlay(tick=0, homes=overlay.homes, positions={"p01": home}, hunger={"p01": 0},
                      yield_at=overlay.yield_at, cold={"p01": 2})
    engine = Engine(ledger)
    assert advance(chilled, {}, engine.tick([]), engine.state, cfg).overlay.cold["p01"] == 0   # 2 - 3 floors
    freezing = Overlay(tick=0, homes=overlay.homes, positions={"p01": (home[0] + 1, home[1])},
                       hunger={"p01": 0}, yield_at=overlay.yield_at,
                       cold={"p01": cfg.cold_death_at - cfg.cold_rate})
    engine = Engine(ledger)
    out = advance(freezing, {}, engine.tick([]), engine.state, cfg)
    assert out.died == ("p01",) and out.overlay.cold["p01"] == cfg.cold_death_at


# --- three needs ---------------------------------------------------------------

def three_need_view(**changes) -> dict:
    view = dict(water_source=(3, 3), water_stock=None, water=1, position=(4, 0), home=(0, 0), food=1)
    view.update(changes)
    return view


def test_the_need_with_the_least_slack_wins_with_thirst_then_cold_then_hunger_on_ties():
    """Slack is (lethal - level) // rate: the ticks a need leaves at the rate it
    rises. Thirst rises twice as fast, so the same level buys half the time."""
    cfg = WorldConfig(seed=1, warmth_on=True)      # water on too: all three needs live
    held = three_need_view()
    assert slack(40, cfg.thirst_death_at, cfg.thirst_rate) == 20           # thirst 40 at 2 a tick
    assert slack(60, cfg.cold_death_at, cfg.cold_rate) == 20               # cold 60 at 1 a tick
    assert slack(60, cfg.death_at, cfg.hunger_rate) == 20                  # hunger 60 at 1 a tick
    assert decide(ob(thirst=40, cold=60, hunger=60, **held), cfg).kind == DRINK        # all 20: thirst first
    assert decide(ob(thirst=0, cold=60, hunger=60, **held), cfg).kind == GO_SHELTER    # then cold
    assert decide(ob(thirst=0, cold=0, hunger=60, **held), cfg).kind == EAT            # then hunger
    # a need that is not calling never wins, however the other levels stand
    idle = decide(ob(thirst=0, cold=0, hunger=0, **held), cfg)
    assert idle.kind == HOME and GO_SHELTER not in idle.candidates


def test_a_need_with_time_in_hand_does_not_outrank_one_about_to_kill():
    """The seed 3 lesson (ROADMAP): ranking by level sent p02 to shelter it did
    not need and it died of thirst. Cold has the higher level here, thirst the
    nearer death, because thirst rises twice as fast."""
    cfg = WorldConfig(seed=1, warmth_on=True)
    walk = three_need_view(water=0)
    assert slack(50, cfg.thirst_death_at, cfg.thirst_rate) == 15           # thirst: 15 ticks
    assert slack(56, cfg.cold_death_at, cfg.cold_rate) == 24               # cold: 24, though its level is higher
    assert decide(ob(thirst=50, cold=56, hunger=30, **walk), cfg).kind == GO_WATER


def test_slack_ignores_how_far_the_remedy_is_so_nobody_thrashes():
    """Subtracting the steps to the remedy oscillated: a step towards food
    shortened the way to food and lengthened the way to shelter, so the two
    swapped places every tick and people reached neither and starved."""
    cfg = WorldConfig(seed=1, warmth_on=True)
    near = decide(ob(thirst=0, cold=40, hunger=40, **three_need_view(position=(1, 0))), cfg)
    far = decide(ob(thirst=0, cold=40, hunger=40, **three_need_view(position=(9, 0))), cfg)
    assert near.kind == far.kind        # the same needs, the same choice, wherever they stand


def test_the_candidate_block_records_every_open_action_food_then_water_then_warmth():
    cfg = WorldConfig(seed=1, warmth_on=True)
    d = decide(ob(thirst=30, cold=30, hunger=30, **three_need_view()), cfg)
    assert d.candidates == (EAT, GO, DRINK, GO_WATER, GO_SHELTER)


def test_warmth_off_and_on_reach_the_same_two_need_decisions_until_cold_calls():
    """Off, the two-need rule is untouched; on, it only differs once cold bites."""
    off, on = WorldConfig(seed=1, warmth_on=False), WorldConfig(seed=1, warmth_on=True)
    view = three_need_view()
    for level in (0, 10, 20):      # 21 and up is a due shelter trip at 4 steps out
        assert (decide(ob(hunger=30, cold=level, **view), off).kind
                == decide(ob(hunger=30, cold=level, **view), on).kind)
    assert decide(ob(hunger=30, cold=30, **view), off).kind == EAT
    assert decide(ob(hunger=30, cold=30, **view), on).kind == GO_SHELTER


# --- a whole run ---------------------------------------------------------------

def test_a_warmth_world_is_sealed_replays_and_actually_shelters_people(tmp_path: Path):
    cfg = WorldConfig(seed=7, warmth_on=True)
    run_world(cfg, 400, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete and replay_world(tmp_path / "w.jsonl").identical
    kinds = [d["kind"] for tick in run.ticks for d in tick["decisions"].values()]
    assert kinds.count(WARM) > 0 and kinds.count(GO_SHELTER) > 0        # the need is not inert
    colds = [c for tick in run.ticks for c in tick["world"]["cold"].values()]
    assert min(colds) == 0                                              # people do get warm again
    # cold can kill: a shelter slows thirst at home, so people set out later with less margin and
    # somebody can be caught out on the way. It does not carry off the whole world.
    assert len(run.ticks[-1]["world"]["died_at"]) < cfg.actors


def kinds_of(path: Path) -> list[str]:
    run = read_run(path)
    return [tick["decisions"][actor]["kind"] for tick in run.ticks for actor in sorted(tick["decisions"])]


def test_warmth_changes_what_people_do(tmp_path: Path):
    """DOCTRINE 1: a need that changed no decision would be a stored field, not a need."""
    run_world(WorldConfig(seed=7, warmth_on=False), 200, tmp_path / "plain.jsonl")
    run_world(WorldConfig(seed=7, warmth_on=True), 200, tmp_path / "warm.jsonl")
    assert kinds_of(tmp_path / "plain.jsonl") != kinds_of(tmp_path / "warm.jsonl")
