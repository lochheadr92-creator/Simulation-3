"""Exploration leg 5: crowd-yield trait (OD-010, visual checkpoint B).

OFF must reproduce the HEAD decisions fixture. ON yields only when the
recorded observation satisfies the declared rule. No social action, no
kernel change, no retained facts.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kernel import canonical_bytes
from stream.run_file import read_run
from world.config import (DEFAULT_YIELD_SET, FOOD_SOURCE, ONE_SOURCE_FOOD_ONLY, SHORT_RANGE_LEVERS, WorldConfig, genesis,
                          homes_for, yield_at_for)
from world.decide import GO, WAIT, YIELD, candidates, crowd_on_source, decide, yield_eligible
from world.observe import Observation, SeenPerson
from world.run import run_world
from world.viewer import render_html, render_text

ROOT = Path(__file__).resolve().parent.parent
HEAD_FIXTURE = ROOT / "tests" / "fixtures" / "head-b305783-seed7-ticks80-decisions.json"
SEED7_HOMES = {
    "p01": (11, 6), "p02": (2, 3), "p03": (6, 8), "p04": (0, 1), "p05": (6, 1), "p06": (6, 11),
}


def small(**levers) -> WorldConfig:
    base = dict(seed=3, width=7, height=7, actors=4)
    base.update(levers)
    return WorldConfig(**base)


def obs(**fields) -> Observation:
    base = dict(actor="p01", tick=0, alive=True, position=(0, 0), home=(0, 0), hunger=5, food=0,
                source=(3, 3), source_food=2, yield_at=2, others=())
    base.update(fields)
    return Observation(**base)


def crowded(n: int, stock: int = 2) -> tuple[SeenPerson, ...]:
    return tuple(SeenPerson(f"p{i:02d}", (3, 3), 0) for i in range(2, 2 + n))


def test_seed_7_homes_match_head_fixture_genesis():
    # the fixture's world: one source cell excluded from the home draw
    assert homes_for(WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY)) == SEED7_HOMES
    assert homes_for(WorldConfig(seed=7, yield_on=False, **ONE_SOURCE_FOOD_ONLY)) == SEED7_HOMES
    assert genesis(WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY))[1].homes == SEED7_HOMES


def test_off_assigns_beyond_actor_count_and_on_draws_from_the_set():
    off = yield_at_for(WorldConfig(seed=7, yield_on=False))
    assert set(off.values()) == {7}
    on = yield_at_for(WorldConfig(seed=7))
    assert set(on) == set(SEED7_HOMES)
    assert set(on.values()) <= set(DEFAULT_YIELD_SET)
    assert yield_at_for(WorldConfig(seed=7)) == on
    assert yield_at_for(WorldConfig(seed=8)) != on
    header = genesis(WorldConfig(seed=7))[1].canonical()
    assert header["yield_at"] == on
    assert genesis(WorldConfig(seed=7)).__class__  # overlay is second
    _, overlay = genesis(WorldConfig(seed=7))
    assert overlay.canonical()["yield_at"] == on


def test_yield_rule_and_priority():
    cfg = small(**ONE_SOURCE_FOOD_ONLY)   # one source: decisions carry no target
    others = crowded(3, stock=2)
    view = obs(hunger=cfg.hungry_at, source_food=2, yield_at=2, others=others, position=(0, 0))
    assert crowd_on_source(view) == 3 and yield_eligible(view, cfg)
    d = decide(view, cfg)
    assert d.kind == YIELD and GO in d.candidates and d.step is None and d.amount == 0
    assert d.reason == "hungry, saw 3 on source, stock 2, yield_at 2"
    assert set(d.canonical()) == {"kind", "reason", "candidates"}
    # stock not strictly less than crowd
    assert not yield_eligible(obs(source_food=3, yield_at=2, others=others, position=(0, 0)), cfg)
    # crowd below trait
    assert not yield_eligible(obs(source_food=0, yield_at=3, others=crowded(2), position=(0, 0)), cfg)
    # on the source
    assert not yield_eligible(obs(position=(3, 3), source_food=2, yield_at=1, others=others), cfg)
    # source not in view
    assert not yield_eligible(obs(source_food=None, yield_at=1, others=others, position=(0, 0)), cfg)
    # eat still beats yield
    d = decide(obs(hunger=cfg.hungry_at, food=1, source_food=2, yield_at=1, others=others, position=(0, 0)), cfg)
    assert d.kind == "eat" and YIELD in d.candidates


def test_emergency_never_yields():
    cfg = small()
    others = crowded(3)
    view = obs(hunger=cfg.emergency_at, source_food=0, yield_at=1, others=others, position=(0, 0))
    assert not yield_eligible(view, cfg)
    d = decide(view, cfg)
    assert d.kind == GO and YIELD not in d.candidates
    d = decide(obs(hunger=cfg.emergency_at, food=0, position=(3, 3), source_food=0, others=others), cfg)
    assert d.kind == WAIT


def test_off_decisions_match_head_b305783(tmp_path: Path):
    fixture = json.loads(HEAD_FIXTURE.read_text(encoding="utf-8"))
    cfg = WorldConfig(seed=fixture["seed"], yield_on=False, **SHORT_RANGE_LEVERS)   # fixture's defaults
    run_world(cfg, fixture["ticks"], tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    got = [tick["decisions"] for tick in run.ticks]
    if got != fixture["decisions"]:
        first = next(i for i, (a, b) in enumerate(zip(got, fixture["decisions"])) if a != b)
        raise AssertionError(
            f"OFF decisions first differ at tick {first}: got {got[first]!r} expected {fixture['decisions'][first]!r}"
        )
    assert all(d["kind"] != YIELD for tick in run.ticks for d in tick["decisions"].values())
    assert run.header["scenario"]["yield"] == "off"
    assert run.header["world"]["yield_at"] == {f"p{i:02d}": 7 for i in range(1, 7)}


def test_recorded_yields_match_the_rule_and_dead_are_not_counted(tmp_path: Path):
    cfg = WorldConfig(seed=7, yield_on=True, **SHORT_RANGE_LEVERS)   # leg-5 calibration: crowds within 80 ticks
    run_world(cfg, 80, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    source = tuple(run.header["scenario"]["source_position"])
    hungry_at = run.header["scenario"]["hungry_at"]
    emergency_at = run.header["scenario"]["emergency_at"]
    start = run.header["world"]
    found = 0
    for tick in run.ticks:
        yield_at = start["yield_at"]
        hunger = start["hunger"]
        for actor, decision in tick["decisions"].items():
            observation = tick["observations"][actor]
            crowd = sum(1 for other in observation.get("sees", []) if tuple(start["positions"][other]) == source)
            stock = observation.get("source_food")
            should = (
                hunger[actor] >= hungry_at
                and hunger[actor] < emergency_at
                and tuple(start["positions"][actor]) != source
                and stock is not None
                and crowd >= yield_at[actor]
                and stock < crowd
            )
            if decision["kind"] == YIELD:
                assert should, (actor, tick["tick"], decision, observation)
                assert GO in decision["candidates"]
                found += 1
            else:
                assert not should or decision["kind"] in {"eat", "claim", "wait"}
            assert all(other not in start["died_at"] for other in observation.get("sees", []))
        start = tick["world"]
    assert found >= 1


def test_two_runs_are_byte_identical_apart_from_timing(tmp_path: Path):
    cfg = small(yield_on=True)
    a = run_world(cfg, 40, tmp_path / "a.jsonl")
    b = run_world(cfg, 40, tmp_path / "b.jsonl")
    assert a.trail_digest == b.trail_digest
    strip = lambda p: [line for line in p.read_bytes().splitlines() if b'"kind":"timing"' not in line]
    assert strip(tmp_path / "a.jsonl") == strip(tmp_path / "b.jsonl")


def test_tampering_with_yield_at_does_not_verify(tmp_path: Path):
    run_world(small(), 8, tmp_path / "w.jsonl")
    lines = (tmp_path / "w.jsonl").read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if b'"kind":"tick"' in line and b'"yield_at"' in line)
    tick = json.loads(lines[index])
    actor = sorted(tick["world"]["yield_at"])[0]
    tick["world"]["yield_at"][actor] += 1
    lines[index] = canonical_bytes(tick) + b"\n"
    (tmp_path / "w.jsonl").write_bytes(b"".join(lines))
    run = read_run(tmp_path / "w.jsonl")
    assert not run.complete
    assert any("world digest" in problem or "trail" in problem for problem in run.problems)


def test_kernel_still_imports_nothing_from_world_and_decide_is_observation_only():
    def imported(module: Path) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        return names

    for module in (ROOT / "kernel").glob("*.py"):
        assert not {name.split(".")[0] for name in imported(module)} & {"world", "stream"}, module.name
    decide_src = (ROOT / "world" / "decide.py").read_text(encoding="utf-8")
    assert "overlay.yield_at" not in decide_src
    decide_names = imported(ROOT / "world" / "decide.py")
    assert "world.run" not in decide_names
    assert "stream" not in {name.split(".")[0] for name in decide_names}


def test_viewer_shows_trait_and_yield(tmp_path: Path):
    run_world(WorldConfig(seed=7), 40, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    page = render_html(run)
    assert "yield_at" in page and "yield events" in page
    assert "crowd on source" in page
    assert "by yield_at" in page
    assert not __import__("re").search(r'(src|href)\s*=\s*["\']?(https?:)?//', page)
    text = render_text(run, 1)
    assert "yield_at" in text and "yield events" in text
