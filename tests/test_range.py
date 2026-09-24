"""Range: people can live far from food (2026-09-25).

Before, hunger ran from 5 (seek food) to 16 (dead) and people only set off
once hungry, so anyone more than about 8 steps from the source starved on
the way. Now the survival window is five times longer, a claim takes a pack
of up to 3 units, and a person holding no food leaves in time to arrive just
as they get hungry.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from kernel import Source, WorldState
from stream.run_file import read_run
from world.config import FOOD_SOURCE, SHORT_RANGE_LEVERS, WorldConfig
from world.decide import GO, HOME, REST, candidates, decide, trip_due
from world.observe import Observation
from world.overlay import Overlay
from world.run import run_world


def view(position=(0, 1), hunger=0, food=0, home=(0, 1), source=(60, 1)) -> Observation:
    return Observation(actor="p01", tick=0, alive=True, position=position, home=home, hunger=hunger,
                       food=food, source=source, source_food=None)


def test_a_person_with_no_food_leaves_in_time_and_stays_due_on_the_way():
    cfg = WorldConfig(seed=1)
    assert not trip_due(view(hunger=0, source=(20, 1)), cfg)            # 0 + 20 < 25: rest
    assert candidates(view(hunger=0, source=(20, 1)), cfg) == (REST,)
    assert trip_due(view(hunger=5, source=(20, 1)), cfg)                # 5 + 20 = 25: leave
    d = decide(view(hunger=5, source=(20, 1)), cfg)
    assert d.kind == GO and d.step == (1, 1) and "leaving in time" in d.reason
    assert trip_due(view(position=(1, 1), hunger=6, source=(20, 1)), cfg)   # one step later: still due
    assert not trip_due(view(hunger=5, food=1, source=(20, 1)), cfg)    # carrying food: no trip yet
    assert candidates(view(position=(5, 1), hunger=0, source=(20, 1)), cfg) == (HOME,)
    off = WorldConfig(seed=1, plan_trips=False)
    assert not trip_due(view(hunger=24, source=(60, 1)), off)


def test_a_claim_takes_up_to_a_pack_of_three():
    cfg = WorldConfig(seed=1)
    at_source = Observation(actor="p01", tick=0, alive=True, position=(6, 6), home=(0, 0), hunger=30,
                            food=0, source=(6, 6), source_food=5)
    assert decide(at_source, cfg).amount == 3
    assert decide(Observation(**{**at_source.__dict__, "source_food": 2}), cfg).amount == 2


def far_home_genesis(cfg):
    ledger = WorldState.genesis(balances={"p01": cfg.starting_food},
                                sources={FOOD_SOURCE: Source(cfg.source_stock, frozenset({"p01"}))})
    overlay = Overlay(tick=0, homes={"p01": (0, 1)}, positions={"p01": (0, 1)}, hunger={"p01": 0},
                      yield_at={"p01": 2}, died_at={})
    return ledger, overlay


@pytest.mark.parametrize("trips", [True, False])
def test_a_home_60_steps_from_food_is_survivable_only_by_leaving_in_time(tmp_path: Path, monkeypatch, trips: bool):
    module = importlib.import_module("world.run")
    monkeypatch.setattr(module, "genesis", far_home_genesis)
    cfg = WorldConfig(seed=1, width=121, height=3, actors=1, plan_trips=trips)   # source at (60, 1)
    assert cfg.source_position == (60, 1)
    run_world(cfg, 400, tmp_path / "far.jsonl")
    run = read_run(tmp_path / "far.jsonl")
    assert run.complete
    final = run.ticks[-1]["world"]
    eaten = sum(1 for tick in run.ticks if tick["decisions"].get("p01", {}).get("kind") == "eat")
    if trips:
        assert "p01" not in final["died_at"] and eaten >= 4
    else:
        assert final["died_at"].get("p01") is not None and final["died_at"]["p01"] < 120


def test_the_old_short_range_defaults_are_still_reachable():
    old = WorldConfig(seed=7, **SHORT_RANGE_LEVERS)
    assert (old.hungry_at, old.death_at, old.satiation, old.claim_amount, old.plan_trips) == (5, 16, 6, 2, False)
    assert "trips" not in old.describe()
    assert WorldConfig.from_describe(old.describe()) == old
    new = WorldConfig(seed=7)
    assert new.describe()["trips"] == "on" and WorldConfig.from_describe(new.describe()) == new
