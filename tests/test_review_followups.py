"""Boundary and presentation checks around the independent review repairs."""

import json
from types import SimpleNamespace

import pytest

from kernel import Engine, WorldState, transfer
from world.config import WorldConfig
from world.decide import route_step, step_toward
from world.observe import Observation
from world.overlay import Overlay
from world.process import advance, free_cell_near
from world.run import run_world
from world.viewer import _tick_details, render_html
from world.viewer_index import build_index
from stream.run_file import read_run
from viewer.world_view import load_run, WorldViewError


@pytest.mark.parametrize("resource,remaining", [(None, False), ("water", True)])
def test_only_food_delivery_completes_food_promise(resource, remaining):
    config = WorldConfig(seed=1, actors=2, water_on=False, warmth_on=False,
                         births_on=False, terrain_on=False, childhood_on=False)
    pos = {"p01": (0, 0), "p02": (1, 0)}
    ov = Overlay(tick=0, homes=pos, positions=pos, hunger={p: 0 for p in pos},
                 yield_at={p: 1 for p in pos}, promises={"p01": "p02"})
    engine = Engine(WorldState.genesis(balances={"p01": 2, "p02": 0},
                                     holdings={"water": {"p01": 2, "p02": 0}}, consumed_by={"water": 0}))
    record = engine.tick([transfer("gift", "p01", 0, to="p02", amount=1, resource=resource)])
    assert record.outcomes[0].accepted
    out = advance(ov, {}, record, engine.state, config)
    assert ("p01" in out.overlay.promises) == remaining


def test_newborn_home_avoids_both_terrain_kinds():
    config = WorldConfig(seed=11)
    rough, spots = config.terrain()
    for cell in rough + spots:
        assert free_cell_near(cell, set(), config) not in set(rough + spots)


def test_irrelevant_rough_keeps_straight_step_in_all_directions():
    config = WorldConfig(seed=1)
    for target in ((3, 6), (6, 3), (1, 6), (6, 1), (1, 0), (0, 1)):
        view = Observation(actor="p01", tick=0, alive=True, position=(2, 2), home=(2, 2),
                           hunger=0, food=0, source=target, source_food=None,
                           rough_in_view=frozenset({(11, 11)}))
        assert route_step(view, target, config) == step_toward(view.position, target)


@pytest.mark.parametrize("age,expected", [(59, 1), (60, 0)])
def test_child_feeding_count_uses_recipient_age_at_tick_start(age, expected):
    before = {"positions": {"p01": [0, 0], "p02": [1, 0]}, "died_at": {},
              "age": {"p01": 100, "p02": age}, "parent": {"p02": "p01"}}
    after = dict(before, age={"p01": 101, "p02": age + 1})
    tick = {"world": after, "decisions": {"p01": {"kind": "offer", "target": "p02"}},
            "record": {"outcomes": [{"actor": "p01", "accepted": True, "effects": []}]}}
    run = SimpleNamespace(header={"scenario": {"childhood": "on", "adult_at": 60}, "world": before},
                          ticks=[tick])
    assert build_index(run)["counts"]["fed_children"][-1] == expected


def test_viewer_closes_disappearing_promises():
    base = {"positions": {"p01": [0, 0], "p02": [1, 0]}, "died_at": {}}
    run = SimpleNamespace(header={"scenario": {}, "world": base}, ticks=[
        {"world": dict(base, requests={"p01": "p02"}), "decisions": {"p01": {"kind": "ask", "target": "p02"}}},
        {"world": dict(base, promises={"p02": "p01"}), "decisions": {"p02": {"kind": "agree", "target": "p01"}}},
        {"world": base, "decisions": {}},
    ])
    thread = build_index(run)["threads"][0]
    assert thread["end"] == "errand ended without delivery" and thread["ended"] == 3


def test_viewer_closes_request_when_asker_dies_on_asking_tick():
    base = {"positions": {"p01": [0, 0], "p02": [1, 0]}, "died_at": {}}
    run = SimpleNamespace(header={"scenario": {}, "world": base}, ticks=[
        {"world": dict(base, died_at={"p01": 1}),
         "decisions": {"p01": {"kind": "ask", "target": "p02"}}},
    ])
    thread = build_index(run)["threads"][0]
    assert thread["answer"] == "interrupted" and thread["end"] == "asker died"
    assert thread["ended"] == 1


def test_water_details_count_the_water_source_crowd():
    prior = {"positions": {"p01": [1, 1], "p02": [2, 2], "p03": [3, 3]},
             "hunger": {"p01": 1}, "thirst": {"p01": 25}}
    cfg = {"source": "food", "source_position": [3, 3], "water": "on",
           "water_source": "water", "water_position": [2, 2]}
    tick = {"tick": 0, "decisions": {"p01": {"kind": "go_water", "candidates": ["go_water"]}},
            "observations": {"p01": {"sees": ["p02"], "source_food": 9, "water_stock": 2}},
            "record": {"outcomes": [], "rotated_roster": []}, "state": {"sources": {"food": {"stock": 9}}}}
    run = SimpleNamespace(header={"scenario": cfg, "world": prior}, ticks=[tick])
    assert "seen crowd 1, seen source stock 2" in _tick_details(run, 1)["selection"]


def test_damaged_viewer_embeds_only_verified_prefix_and_legacy_view_refuses_births(tmp_path):
    path = tmp_path / "run.jsonl"
    run_world(WorldConfig(seed=23), 120, path)
    with pytest.raises(WorldViewError, match="changing population"):
        load_run(path)
    lines = path.read_bytes().splitlines(keepends=True)
    for i, line in enumerate(lines):
        data = json.loads(line)
        if data.get("kind") == "tick" and data["tick"] == 50:
            del data["world"]
            lines[i] = (json.dumps(data) + "\n").encode()
            break
    damaged = tmp_path / "damaged.jsonl"
    damaged.write_bytes(b"".join(lines))
    run = read_run(damaged)
    page = render_html(run)
    assert "Showing only the verified prefix: 50 ticks." in page
    assert "DOES NOT VERIFY" in page
    import re
    payload = json.loads(re.search(r'id="run-data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert len(payload["ticks"]) == 50 and payload["end"] is None
    assert len(run.ticks) == 120  # rendering did not mutate or repair the file
