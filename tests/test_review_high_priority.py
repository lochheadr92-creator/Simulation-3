"""Regressions reconstructed from Claude's review of c1d13cb (H1 and H2)."""

from dataclasses import replace
import json

import pytest

from world.config import WorldConfig
from world.decide import decide, route_step, steps_to
from world.observe import Observation, SeenPerson
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world


@pytest.mark.parametrize("terrain", [False, True])
@pytest.mark.parametrize("routing", [False, True])
def test_routing_switch_round_trips(terrain, routing):
    config = WorldConfig(seed=7, terrain_on=terrain, route_around=routing)
    assert WorldConfig.from_describe(config.describe()) == config


def test_routing_off_run_replays_and_recovers(tmp_path):
    full, cut, recovered = (tmp_path / name for name in ("full.jsonl", "cut.jsonl", "recovered.jsonl"))
    run_world(WorldConfig(seed=7, route_around=False), 25, full)
    assert replay_world(full).identical
    lines = full.read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines)
                 if json.loads(line).get("kind") == "tick" and i > 10)
    cut.write_bytes(b"".join(lines[:index]) + lines[index][:20])
    recover_world(cut, recovered)
    assert replay_world(recovered).identical
    content = lambda path: [line for line in path.read_bytes().splitlines()
                            if json.loads(line)["kind"] != "timing"]
    assert content(full) == content(recovered)


def child():
    config = WorldConfig(seed=7, water_on=False, warmth_on=False, child_leash=2,
                         offers_on=False, requests_on=True)
    view = Observation(actor="p01", tick=0, alive=True, position=(2, 2), home=(2, 2),
                       hunger=config.hungry_at - 1, food=0, source=(8, 2), source_food=None,
                       age=0, others=(SeenPerson("p02", (3, 2), 2),))
    return config, view


def test_child_does_not_start_early_food_trip_outside_leash():
    config, view = child()
    decision = decide(view, config)
    assert decision.kind == "rest" and decision.step is None


def test_child_can_ask_without_walking_toward_unreachable_food():
    config, view = child()
    decision = decide(replace(view, hunger=config.hungry_at), config)
    assert decision.kind == "ask"
    assert decision.step in (None, view.home)


def test_child_route_detour_cannot_leave_home_leash():
    config, view = child()
    view = replace(view, position=(2, 0), source=(3, 1),
                   rough_in_view=frozenset({(2, 1), (3, 0)}))
    assert steps_to(view.home, route_step(view, view.source, config)) <= config.child_leash


def test_adult_can_make_the_same_early_trip():
    config, view = child()
    assert decide(replace(view, age=config.adult_at), config).kind == "go"
