"""Regression tests for the independent review of c1d13cb.

Each test states the documented contract it checks. Run from the repository
root with this directory on the path; at c1d13cb every test here fails, and
each failure is one reported defect.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from kernel import Engine, Source, WorldState, transfer
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import AGREE, GO, OFFER, Decision, decide, route_step, step_toward
from world.observe import Observation, SeenPerson, observe
from world.overlay import Overlay
from world.process import advance, free_cell_near
from world.replay import replay_world
from world.run import run_world
from world.viewer import render_html, render_text


# F1 - "a saved run replays to the same result"; --routing off is a supported switch.
def test_routing_off_run_replays(tmp_path):
    config = WorldConfig(seed=7, route_around=False)
    assert WorldConfig.from_describe(config.describe()) == config
    run_world(config, 20, tmp_path / "r.jsonl")
    assert replay_world(tmp_path / "r.jsonl").identical


def _child(**kw):
    base = dict(actor="p07", tick=100, alive=True, position=(0, 11), home=(0, 11), hunger=20, food=0,
                source=(6, 6), source_food=None, age=0)
    base.update(kw)
    return Observation(**base)


QUIET = dict(seed=1, water_on=False, warmth_on=False, offers_on=False)


# F2a - "A child will not go more than child_leash steps from home for food or water."
def test_fed_child_far_from_food_does_not_leave_in_time():
    config = WorldConfig(**QUIET)
    d = decide(_child(), config)            # 11 steps from the source, leash 5; hunger 20 + 11 >= 25
    assert d.kind != GO, d


# F2b - same contract, with asking on: the ask's walk must respect the leash too.
def test_hungry_child_asking_does_not_walk_past_leash():
    config = WorldConfig(**dict(QUIET, requests_on=True))
    child = _child(hunger=30, position=(5, 11), others=(SeenPerson("p01", (5, 10), 2),))   # at the leash edge
    d = decide(child, config)
    assert d.step is None or abs(d.step[0] - 0) + abs(d.step[1] - 11) <= config.child_leash, d


# F3 - header text: "the errand is then theirs until it is delivered or they lose sight of the asker".
def test_promise_lapses_when_helper_loses_sight():
    config = WorldConfig(seed=1, actors=2, requests_on=True, water_on=False, warmth_on=False,
                         terrain_on=False, births_on=False, childhood_on=False, building_on=False)
    ledger = WorldState.genesis(tick=5, balances={"p01": 0, "p02": 1},
                                sources={s: Source(4, frozenset({"p01", "p02"})) for s in config.food_source_ids()})
    ov = Overlay(tick=5, homes={"p01": (0, 0), "p02": (11, 11)}, positions={"p01": (0, 0), "p02": (11, 11)},
                 hunger={"p01": 0, "p02": 0}, yield_at={"p01": 1, "p02": 1}, promises={"p02": "p01"})
    views = {a: observe(a, ledger, ov, config) for a in ov.living}
    assert not any(s.actor == "p01" for s in views["p02"].others)       # out of sight
    decisions = {a: decide(v, config) for a, v in views.items()}
    engine = Engine(ledger)
    record = engine.tick([])
    out = advance(ov, decisions, record, engine.state, config, views)
    assert "p02" not in out.overlay.promises


# F4 - a dead helper cannot still be carrying food.
def test_dead_helpers_promise_is_cleared():
    config = WorldConfig(seed=1, actors=2, requests_on=True, water_on=False, warmth_on=False,
                         terrain_on=False, births_on=False, childhood_on=False, building_on=False)
    ledger = WorldState.genesis(tick=5, balances={"p01": 0, "p02": 1},
                                sources={s: Source(4, frozenset({"p01", "p02"})) for s in config.food_source_ids()})
    ov = Overlay(tick=5, homes={"p01": (0, 0), "p02": (1, 0)}, positions={"p01": (0, 0), "p02": (1, 0)},
                 hunger={"p01": 0, "p02": 80}, yield_at={"p01": 1, "p02": 1}, died_at={"p02": 5},
                 promises={"p02": "p01"})
    engine = Engine(ledger)
    record = engine.tick([])
    out = advance(ov, {"p01": decide(observe("p01", ledger, ov, config), config)}, record, engine.state, config)
    assert "p02" not in out.overlay.promises


# F5 - "held in the world state until the unit is handed over": a unit handed to somebody else is not that.
def test_promise_survives_a_handoff_to_somebody_else():
    config = WorldConfig(seed=1, actors=3, requests_on=True, water_on=False, warmth_on=False,
                         terrain_on=False, births_on=False, childhood_on=False, building_on=False)
    ledger = WorldState.genesis(tick=5, balances={"p01": 2, "p02": 0, "p03": 0},
                                sources={s: Source(4, frozenset({"p01", "p02", "p03"})) for s in config.food_source_ids()})
    pos = {"p01": (0, 0), "p02": (1, 0), "p03": (3, 0)}
    ov = Overlay(tick=5, homes=pos, positions=pos, hunger={p: 0 for p in pos}, yield_at={p: 1 for p in pos},
                 promises={"p01": "p03"})
    engine = Engine(ledger)
    record = engine.tick([transfer("t5-p01", "p01", 0, to="p02", amount=1)])
    d = Decision("p01", OFFER, "handing to p02", (OFFER,), amount=1, target="p02")
    out = advance(ov, {"p01": d}, record, engine.state, config)
    assert out.overlay.promises.get("p01") == "p03"


# F6 - "Sources and homes are always open ground" (header `ground`, WORLD_DIRECTIONS).
def test_newborn_home_is_never_rough_ground():
    config = WorldConfig(seed=11)
    rough = set(config.terrain()[0])
    origin = sorted(rough)[0]
    taken = set(config.all_source_positions())
    assert free_cell_near(origin, taken, config) not in rough


# F7 - childhood: "a parent ... takes a unit to their own child" - a child is somebody under adult_at.
def test_grown_offspring_are_not_fed_first():
    config = WorldConfig(seed=1, water_on=False, warmth_on=False, offers_on=True)
    parent = Observation(actor="p01", tick=300, alive=True, position=(2, 2), home=(2, 2), hunger=0, food=2,
                         source=(6, 6), source_food=None, age=300, children=frozenset({"p07"}),
                         dependents=frozenset(), others=(SeenPerson("p07", (3, 2), 0),))
    assert decide(parent, config).kind != OFFER


# F8 - route_step: "rank the first step so ties fall the way the plain rule would have gone".
def test_irrelevant_rough_does_not_change_the_first_step():
    config = WorldConfig(seed=1)
    view = Observation(actor="p01", tick=0, alive=True, position=(2, 2), home=(2, 2), hunger=0, food=0,
                       source=(6, 6), source_food=None, rough_in_view=frozenset({(0, 0)}))
    assert route_step(view, (3, 6), config) == step_toward((2, 2), (3, 6))


@pytest.fixture(scope="module")
def born_run(tmp_path_factory):
    path = tmp_path_factory.mktemp("born") / "r.jsonl"
    run_world(WorldConfig(seed=23), 120, path)
    run = read_run(path)
    assert len(run.ticks[-1]["world"]["positions"]) > 6          # somebody was born
    return path


# F9 - the text view must work on any view of a verified run.
def test_text_view_after_a_birth(born_run):
    run = read_run(born_run)
    render_text(run, len(run.ticks))


# F10 - read_run: "a run with problems is still returned so a viewer can show what exists".
def test_html_viewer_survives_a_damaged_tick_line(born_run, tmp_path):
    lines = born_run.read_bytes().splitlines(keepends=True)
    out = []
    for raw in lines:
        payload = json.loads(raw)
        if payload.get("kind") == "tick" and payload["tick"] == 50:
            del payload["world"]
            raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        out.append(raw)
    damaged = tmp_path / "damaged.jsonl"
    damaged.write_bytes(b"".join(out))
    run = read_run(damaged)
    assert not run.complete
    render_html(run)


# F11 - the header declares the rules a run follows; requests=on now includes direct handoffs.
def test_requests_on_rule_text_mentions_direct_handoff():
    text = WorldConfig(seed=1, requests_on=True).describe()["decision"]
    assert "handoff" in text or "hand over" in text


# F12 - hypothesis: a request from somebody who died that tick should not be agreed to.
def test_no_agreement_with_a_dead_asker():
    config = WorldConfig(seed=1, actors=2, requests_on=True, water_on=False, warmth_on=False, terrain_on=False,
                         births_on=False, childhood_on=False, building_on=False, stagger_start=False)
    ledger = WorldState.genesis(tick=10, balances={"p01": 0, "p02": 2},
                                sources={s: Source(4, frozenset({"p01", "p02"})) for s in config.food_source_ids()})
    ov = Overlay(tick=10, homes={"p01": (1, 1), "p02": (2, 1)}, positions={"p01": (1, 1), "p02": (2, 1)},
                 hunger={"p01": 80, "p02": 0}, yield_at={"p01": 1, "p02": 1}, died_at={"p01": 10},
                 requests={"p01": "p02"})
    assert decide(observe("p02", ledger, ov, config), config).kind != AGREE
