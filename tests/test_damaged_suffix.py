"""A damaged tail must not stop recovery of the intact sealed part of a run file,
and nothing after the first broken line may steer recovery. Regression tests
for findings F1 and F2 of the 2026-09-23 slice 1c review.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel import canonical_bytes
from stream.recover import recover_scenario
from stream.run import run_scenario
from stream.run_file import read_run
from stream.scenario import Scenario
from world.config import WorldConfig
from world.recover import recover_world
from world.run import run_world

TICK = 57   # the review's damaged tick
FAULTS = ["invalid-utf8-in-seal", "timing-value-not-integer", "record-is-a-list",
          "second-header-with-new-horizon"]


def content(path: Path) -> list[bytes]:
    return [line for line in path.read_bytes().splitlines(keepends=True) if b'"kind":"timing"' not in line]


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> dict:
    folder = tmp_path_factory.mktemp("damaged")
    scenario, world = folder / "scenario.jsonl", folder / "world.jsonl"
    run_scenario(Scenario(seed=7), 120, scenario)
    run_world(WorldConfig(seed=7), 120, world)
    return {"scenario": (scenario, recover_scenario), "world": (world, recover_world)}


def damage(source: Path, fault: str, dest: Path) -> tuple[int, int]:
    """Copy `source` with one fault at tick TICK or its timing line. Returns the
    last tick that should still verify and the 1-based line of the break."""
    lines = source.read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines)
                 if b'"kind":"tick"' in line and json.loads(line)["tick"] == TICK)
    last, broken = TICK - 1, index + 1
    if fault == "invalid-utf8-in-seal":
        raw = bytearray(lines[index])
        raw[raw.index(b'"seal":"') + 8] = 0xFF
        lines[index] = bytes(raw)
    elif fault == "timing-value-not-integer":
        timing = json.loads(lines[index + 1])
        assert timing["kind"] == "timing" and timing["tick"] == TICK
        timing["elapsed_ns"] = "broken"
        lines[index + 1] = canonical_bytes(timing) + b"\n"
        last, broken = TICK, index + 2
    elif fault == "record-is-a-list":
        payload = json.loads(lines[index])
        payload["record"] = [1]
        lines[index] = canonical_bytes(payload) + b"\n"
    elif fault == "second-header-with-new-horizon":
        header = json.loads(lines[0])
        header["horizon"] = 121          # its copied seal no longer verifies
        lines[index] = canonical_bytes(header) + b"\n"
    dest.write_bytes(b"".join(lines))
    return last, broken


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("kind", ["scenario", "world"])
def test_a_damaged_tail_is_reported_and_the_sealed_prefix_recovers(runs, tmp_path, kind, fault):
    source, recover = runs[kind]
    damaged = tmp_path / "damaged.jsonl"
    last, broken = damage(source, fault, damaged)

    run = read_run(damaged)                                   # reports, never raises
    assert not run.complete
    assert run.last_sealed_tick == last and run.first_break_line == broken
    assert run.header == json.loads(source.read_bytes().splitlines()[0])   # the first header governs

    result = recover(damaged, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == last and result.resumed == (last + 1, 119)
    recovered = read_run(tmp_path / "recovered.jsonl")
    assert recovered.complete and len(recovered.ticks) == 120 and recovered.header["horizon"] == 120
    assert content(tmp_path / "recovered.jsonl") == content(source)
