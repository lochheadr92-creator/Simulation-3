"""World cost workload: 50 people who all live, deterministic, fully sealed, replayable."""

from __future__ import annotations

from pathlib import Path

from stream.run_file import read_run
from world.bench import bench_config, run_world_benchmark
from world.replay import replay_world


def test_the_world_benchmark_keeps_50_people_alive_and_is_deterministic(tmp_path: Path):
    a = run_world_benchmark(bench_config(), 40, tmp_path / "a.jsonl")
    b = run_world_benchmark(bench_config(), 40, tmp_path / "b.jsonl")
    assert a["trail_digest"] == b["trail_digest"]
    assert a["survivors"] == 50 and a["deaths"] == 0
    run = read_run(tmp_path / "a.jsonl")
    assert run.complete and len(run.ticks) == 40


def test_the_world_benchmark_file_replays(tmp_path: Path):
    run_world_benchmark(bench_config(seed=2), 30, tmp_path / "run.jsonl")
    result = replay_world(tmp_path / "run.jsonl")
    assert result.identical and result.ticks == 30
