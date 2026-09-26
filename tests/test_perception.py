"""Checkpoint 3: perception radius and bounded views.

These check the declared metric and boundary, that recorded observations
leak only the declared fields, that a radius large enough to see the whole
grid leaves decisions identical to HEAD b305783, and that observation
ownership and verification hold. They do not count opportunities.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kernel import Source, WorldState, canonical_bytes
from stream.run_file import apply_production, read_run
from world.config import (DISTANCE_METRIC, FOOD_SOURCE, ONE_SOURCE_FOOD_ONLY, PERCEPTION_BOUNDARY, SHORT_RANGE_LEVERS,
                          WorldConfig)
from world.decide import CLAIM, GO, candidates, decide
from world.observe import Observation, chebyshev, in_view, observe
from world.overlay import Overlay
from world.run import run_world
from world.viewer import render_html, render_text

ROOT = Path(__file__).resolve().parent.parent
HEAD_FIXTURE = ROOT / "tests" / "fixtures" / "head-b305783-seed7-ticks80-decisions.json"


def small(**levers) -> WorldConfig:
    base = dict(seed=3, width=7, height=7, actors=4)
    base.update(levers)
    return WorldConfig(**base)


def obs(**fields) -> Observation:
    base = dict(actor="p01", tick=0, alive=True, position=(0, 0), home=(0, 0), hunger=0, food=0,
                source=(3, 3), source_food=4, others=())
    base.update(fields)
    return Observation(**base)


def placed(positions: dict[str, tuple[int, int]], *, radius: int, stock: int = 4,
           food: dict[str, int] | None = None, died_at: dict[str, int] | None = None) -> tuple[WorldState, Overlay, WorldConfig]:
    actors = tuple(sorted(positions))
    cfg = WorldConfig(seed=0, width=7, height=7, actors=len(actors), perception_radius=radius,
                      starting_food=0, source_stock=stock, **ONE_SOURCE_FOOD_ONLY)   # the world built below
    held = food or {actor: 0 for actor in actors}
    ledger = WorldState.genesis(
        balances=held,
        sources={FOOD_SOURCE: Source(stock=stock, authorised=frozenset(actors))},
    )
    overlay = Overlay(
        tick=0,
        homes=positions,
        positions=positions,
        hunger={actor: 0 for actor in actors},
        yield_at={actor: 99 for actor in actors},
        died_at=died_at or {},
    )
    return ledger, overlay, cfg


def test_chebyshev_metric_and_inclusive_boundary():
    assert DISTANCE_METRIC == "chebyshev" and PERCEPTION_BOUNDARY == "distance <= radius"
    assert chebyshev((0, 0), (3, 1)) == 3
    assert chebyshev((2, 2), (2, 2)) == 0
    assert in_view((0, 0), (3, 3), 3) and not in_view((0, 0), (3, 4), 3)
    ledger, overlay, cfg = placed(
        {"p01": (0, 0), "p02": (3, 0), "p03": (4, 0)},
        radius=3,
        food={"p01": 1, "p02": 2, "p03": 3},
    )
    view = observe("p01", ledger, overlay, cfg)
    assert view.position == (0, 0)
    assert [seen.actor for seen in view.others] == ["p02"]
    assert view.others[0].position == (3, 0) and view.others[0].food == 2
    assert all(seen.actor != "p01" for seen in view.others)
    assert in_view(view.position, view.position, cfg.perception_radius)


def test_claim_requires_observed_stock_and_does_not_invent_actions():
    cfg = small()
    d = decide(obs(hunger=cfg.hungry_at, food=0, position=(3, 3), source_food=1), cfg)
    assert d.kind == CLAIM and d.amount == 1
    with pytest.raises(AssertionError):
        decide(obs(hunger=cfg.hungry_at, food=0, position=(3, 3), source_food=None), cfg)
    d = decide(obs(hunger=cfg.hungry_at, food=0, position=(0, 0), source_food=None), cfg)
    assert d.kind == GO and CLAIM not in d.candidates
    assert set(candidates(obs(hunger=cfg.hungry_at, food=0, position=(0, 0), source_food=None), cfg)) == {GO}


def test_recorded_sees_are_exactly_the_living_others_in_the_radius(tmp_path: Path):
    """The run file records who each person saw as identities only; their
    positions come from the tick-start world block in the same file."""
    cfg = small(perception_radius=2, **ONE_SOURCE_FOOD_ONLY)   # the one-source record; see test_sources.py
    run_world(cfg, 40, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete
    radius = run.header["scenario"]["perception_radius"]
    source = tuple(run.header["scenario"]["source_position"])
    start_world = run.header["world"]
    start_state = run.header["genesis"]
    for tick in run.ticks:
        positions = start_world["positions"]
        living = [p for p in sorted(positions) if p not in start_world["died_at"]]
        for actor, observation in tick["observations"].items():
            origin = tuple(positions[actor])
            assert set(observation) <= {"sees", "source_food"}
            expected = [q for q in living if q != actor and chebyshev(origin, tuple(positions[q])) <= radius]
            assert observation["sees"] == expected
            if "source_food" in observation:
                assert chebyshev(origin, source) <= radius
                assert observation["source_food"] == start_state["sources"][FOOD_SOURCE]["stock"]
            else:
                assert chebyshev(origin, source) > radius
        start_world = tick["world"]
        start_state = apply_production(tick["state"], tick.get("production", []))


def test_source_stock_absent_out_of_view_and_equal_when_in_view():
    far, overlay_far, cfg_far = placed({"p01": (0, 0), "p02": (6, 6)}, radius=2, stock=5, food={"p01": 1, "p02": 3})
    view = observe("p01", far, overlay_far, cfg_far)
    assert view.source == cfg_far.source_position and view.source_food is None
    near, overlay_near, cfg_near = placed({"p01": (3, 3), "p02": (0, 0)}, radius=2, stock=5, food={"p01": 1, "p02": 3})
    view = observe("p01", near, overlay_near, cfg_near)
    assert view.source_food == 5 == near.view_for("p01").sources[FOOD_SOURCE].available_stock
    assert view.at_source


def test_unrestricted_radius_decisions_match_head_b305783(tmp_path: Path):
    fixture = json.loads(HEAD_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["head"].startswith("b305783")
    # the fixture was captured under the pre-2026-09-25 defaults
    cfg = WorldConfig(seed=fixture["seed"], perception_radius=12, yield_on=False, **SHORT_RANGE_LEVERS)
    run_world(cfg, fixture["ticks"], tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    got = [tick["decisions"] for tick in run.ticks]
    if got != fixture["decisions"]:
        first = next(i for i, (a, b) in enumerate(zip(got, fixture["decisions"])) if a != b)
        raise AssertionError(f"decisions first differ at tick {first}: got {got[first]!r} expected {fixture['decisions'][first]!r}")
    assert len(got) == fixture["ticks"]


def test_two_runs_of_one_seed_are_byte_identical_apart_from_timing(tmp_path: Path):
    cfg = small(perception_radius=3)
    a = run_world(cfg, 50, tmp_path / "a.jsonl")
    b = run_world(cfg, 50, tmp_path / "b.jsonl")
    assert a.trail_digest == b.trail_digest
    strip = lambda p: [line for line in p.read_bytes().splitlines() if b'"kind":"timing"' not in line]
    assert strip(tmp_path / "a.jsonl") == strip(tmp_path / "b.jsonl")


def test_tampering_with_a_recorded_observation_does_not_verify(tmp_path: Path):
    run_world(small(perception_radius=3), 12, tmp_path / "w.jsonl")
    lines = (tmp_path / "w.jsonl").read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if b'"kind":"tick"' in line and b'"observations"' in line)
    tick = json.loads(lines[index])
    actor = sorted(tick["observations"])[0]
    tick["observations"][actor]["sees"] = list(tick["observations"][actor]["sees"]) + ["p99"]
    lines[index] = canonical_bytes(tick) + b"\n"
    (tmp_path / "w.jsonl").write_bytes(b"".join(lines))
    run = read_run(tmp_path / "w.jsonl")
    assert not run.complete and any("trail" in problem for problem in run.problems)


def test_observe_imports_nothing_from_stream_or_world_run_and_kernel_stays_upstream():
    def imported(module: Path) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        return names

    observe_names = imported(ROOT / "world" / "observe.py")
    assert "stream" not in {name.split(".")[0] for name in observe_names}
    assert "world.run" not in observe_names and not any(name == "run" or name.startswith("world.run") for name in observe_names)
    for module in (ROOT / "kernel").glob("*.py"):
        top = {name.split(".")[0] for name in imported(module)}
        assert not top & {"world", "stream"}, module.name


def test_viewer_shows_perception_and_stays_self_contained(tmp_path: Path):
    cfg = small(perception_radius=3)
    run_world(cfg, 20, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    page = render_html(run)
    assert "person-ticks with another in view" in page
    assert "person-ticks with source in view" in page
    assert "Chebyshev perception" in page
    assert "sees (tick before)" in page
    text = render_text(run, 1)
    assert "sees" in text and "person-ticks with another in view" in text


def test_seen_food_from_the_availability_map_equals_each_persons_own_view():
    """observe() reads others' free food from one availability map per tick;
    it must equal what each person's own kernel view reports, holds included."""
    from kernel import Engine
    from kernel.state import actor_account
    from stream.bench import Workload, WorkloadGenerator

    workload = Workload(seed=4, actors=12)
    engine, generator = Engine(workload.genesis()), WorkloadGenerator(workload)
    checked_with_holds = 0
    for _ in range(30):
        state = engine.state
        available = state.availability()
        for actor in workload.actor_ids():
            assert available[actor_account(actor)] == state.view_for(actor).own_available
        checked_with_holds += bool(state.reservations)
        engine.tick(generator.tick(state))
    assert checked_with_holds > 0
