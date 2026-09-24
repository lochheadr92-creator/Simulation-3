"""Slice 1d workload: deterministic, fully sealed, replayable, and a real mix."""

from __future__ import annotations

from pathlib import Path

from kernel import Engine, WorldState
from stream.bench import Workload, run_benchmark
from stream.run_file import decode_input, read_run


def test_the_benchmark_run_is_deterministic_and_fully_sealed(tmp_path: Path):
    a = run_benchmark(Workload(), 60, tmp_path / "a.jsonl")
    b = run_benchmark(Workload(), 60, tmp_path / "b.jsonl")
    assert a["trail_digest"] == b["trail_digest"] and a["final_state_digest"] == b["final_state_digest"]
    run = read_run(tmp_path / "a.jsonl")
    assert run.complete and len(run.ticks) == 60 and run.last_sealed_tick == 59


def test_the_benchmark_file_replays_from_its_genesis_and_inputs(tmp_path: Path):
    run_benchmark(Workload(seed=3), 40, tmp_path / "run.jsonl")
    run = read_run(tmp_path / "run.jsonl")
    engine = Engine(WorldState.from_canonical(run.header["genesis"]))
    for tick in run.ticks:
        engine.tick([decode_input(entry) for entry in tick["inputs"]])
        assert engine.state.digest() == tick["state_digest"], tick["tick"]


def test_the_workload_is_one_proposal_per_actor_with_accepts_and_denials(tmp_path: Path):
    result = run_benchmark(Workload(), 60, tmp_path / "run.jsonl")
    run = read_run(tmp_path / "run.jsonl")
    for tick in run.ticks:
        actors = [entry["actor"] for entry in tick["inputs"]]
        assert len(actors) == len(set(actors)) <= 50
    outcomes = [outcome for tick in run.ticks for outcome in tick["record"]["outcomes"]]
    assert any(o["accepted"] for o in outcomes) and not all(o["accepted"] for o in outcomes)
    operations = {entry["operation"] for tick in run.ticks for entry in tick["inputs"]}
    assert {"claim", "transfer", "consume", "reserve", "complete", "cancel"} <= operations
    assert 30 <= result["proposals_per_tick"] <= 50
    assert run.ticks[-1]["state"]["sources"]["scarce"]["stock"] == 0      # the contested source ran dry
