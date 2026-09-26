"""Water, the second need (2026-09-25).

Water is a kernel named resource: people draw it from a water source into
their own water holding and drink it into the water sink, and thirst rises
faster than hunger. When both needs call, a person serves the one nearer its
lethal level. Water is off by default, and off leaves the world exactly as it
was.
"""

from __future__ import annotations

from pathlib import Path

from stream.run_file import read_run
from world.config import ONE_SOURCE_FOOD_ONLY, WATER, WATER_SOURCE, WorldConfig, genesis, staggered
from world.decide import DRAW, DRINK, EAT, GO_WATER, WAIT_WATER, decide, water_trip_due
from world.observe import Observation
from world.replay import replay_world
from world.run import run_id_for, run_world


def test_water_off_leaves_the_world_as_it_was():
    cfg = WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY)   # water is on by default from 2026-09-26
    assert "water" not in cfg.describe() and not run_id_for(cfg, 10).endswith("-wateron")
    ledger, overlay = genesis(cfg)
    assert "holdings" not in ledger.canonical() and "thirst" not in overlay.canonical()
    assert WATER_SOURCE not in ledger.sources


def test_water_on_genesis():
    cfg = WorldConfig(seed=7, water_on=True)
    ledger, overlay = genesis(cfg)
    well = ledger.sources[WATER_SOURCE]
    assert well.resource == WATER and well.stock == cfg.water_stock
    assert dict(ledger.holdings[WATER]) == {actor: cfg.starting_water for actor in cfg.actor_ids()}
    # the roster starts spread out, so nobody gets thirsty in step with anyone else
    assert dict(overlay.thirst) == staggered(cfg, cfg.thirsty_at)
    assert sorted(overlay.thirst.values()) == [0, 4, 8, 12, 16, 20]
    homes = set(overlay.homes.values())
    assert cfg.water_position not in homes and cfg.source_position not in homes
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    assert "-wateron" in run_id_for(cfg, 10)


def ob(**changes) -> Observation:
    base = dict(actor="p01", tick=0, alive=True, position=(0, 0), home=(0, 0), hunger=0, food=0,
                source=(6, 6), source_food=None, thirst=0, water=0, water_source=(3, 3), water_stock=None)
    base.update(changes)
    return Observation(**base)


def test_the_two_need_rule():
    cfg = WorldConfig(seed=1, water_on=True)
    assert decide(ob(thirst=30, water=1), cfg).kind == DRINK
    drawn = decide(ob(thirst=30, position=(3, 3), water_stock=5), cfg)
    assert drawn.kind == DRAW and drawn.amount == 3
    assert decide(ob(thirst=30, position=(3, 3), water_stock=0), cfg).kind == WAIT_WATER
    walk = decide(ob(thirst=30), cfg)
    assert walk.kind == GO_WATER and walk.step == (1, 0)
    # both needs calling: the one nearer its lethal level wins, thirst on ties
    assert decide(ob(hunger=60, food=1, thirst=30, water=1), cfg).kind == EAT
    assert decide(ob(hunger=30, food=1, thirst=30, water=1), cfg).kind == DRINK
    # leave in time for water: 6 steps at thirst 2 per tick, so due at thirst 13
    assert water_trip_due(ob(thirst=13), cfg) and not water_trip_due(ob(thirst=12), cfg)
    assert decide(ob(thirst=13), cfg).kind == GO_WATER
    assert not water_trip_due(ob(thirst=13, water=1), cfg)


def test_a_water_world_is_sealed_replays_and_keeps_food_and_water_apart(tmp_path: Path):
    cfg = WorldConfig(seed=7, water_on=True)
    run_world(cfg, 400, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete
    kinds = [d["kind"] for tick in run.ticks for d in tick["decisions"].values()]
    assert kinds.count(DRINK) > 0 and kinds.count(DRAW) > 0
    final = run.ticks[-1]["state"]
    assert final["consumed"] == kinds.count(EAT)                  # drinking is never counted as eating
    assert final["consumed_by"][WATER] == kinds.count(DRINK)
    assert replay_world(tmp_path / "w.jsonl").identical


def test_without_water_everyone_dies_of_thirst_even_with_food(tmp_path: Path):
    cfg = WorldConfig(seed=7, water_on=True, starting_water=0, water_stock=0, water_renewal_amount=0,
                      starting_food=3, terrain_on=False)   # plain ground: this is about the thirst arithmetic
    run_world(cfg, 60, tmp_path / "dry.jsonl")
    died = read_run(tmp_path / "dry.jsonl").ticks[-1]["world"]["died_at"]
    # thirst 2 a tick reaches 80 at tick 40, sooner for those who started part way there
    assert len(died) == cfg.actors and set(died.values()) == {30, 32, 34, 36, 38, 40}