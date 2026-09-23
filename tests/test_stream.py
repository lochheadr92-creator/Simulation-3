"""Record stream and viewer (slice 1c as re-scoped by OD-009).

These check that the stream is a faithful, verifiable, reproducible write-down
of what the engine did, and that the viewer renders from it alone. They are
not evidence of any world property; the scenario is exploration input.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from kernel import Engine, Source, WorldState, consume
from stream.run import run_scenario
from stream.run_file import STREAM_FORMAT, RunFileError, RunWriter, read_run
from stream.scenario import ProposalGenerator, Scenario
from stream.viewer import render_html, render_text

REPO_ROOT = Path(__file__).resolve().parent.parent


def content_lines(path: Path) -> list[bytes]:
    return [line for line in path.read_bytes().splitlines() if b'"kind":"timing"' not in line]


def test_two_runs_of_one_seed_are_byte_identical_apart_from_timing(tmp_path: Path):
    scenario = Scenario(seed=11, actors=4, sources=2)
    first = run_scenario(scenario, 60, tmp_path / "a.jsonl")
    second = run_scenario(scenario, 60, tmp_path / "b.jsonl")
    assert first["trail_digest"] == second["trail_digest"]
    assert first["final_state_digest"] == second["final_state_digest"]
    assert content_lines(tmp_path / "a.jsonl") == content_lines(tmp_path / "b.jsonl")
    assert Scenario(seed=12, actors=4, sources=2) != scenario
    third = run_scenario(Scenario(seed=12, actors=4, sources=2), 60, tmp_path / "c.jsonl")
    assert third["trail_digest"] != first["trail_digest"]


def test_run_file_verifies_and_reads_back_what_the_engine_committed(tmp_path: Path):
    scenario = Scenario(seed=3, actors=3, sources=1)
    path = tmp_path / "run.jsonl"
    result = run_scenario(scenario, 25, path)
    run = read_run(path)
    assert run.complete and run.problems == ()
    assert run.header["format"] == STREAM_FORMAT and run.header["scenario"]["seed"] == 3
    assert len(run.ticks) == 25 and run.end["ticks"] == 25
    assert run.trail_digest == result["trail_digest"] == run.end["trail_digest"]
    assert run.ticks[-1]["state_digest"] == result["final_state_digest"]
    assert [t["tick"] for t in run.ticks] == list(range(25))
    assert set(run.timings) == set(range(25))
    # the engine's own availability map is stored, never recomputed here
    for entry in run.ticks:
        state = WorldState.genesis(**{k: entry["state"][k] for k in ("tick", "balances", "consumed")},
                                   sources={k: Source(v["stock"], tuple(v["authorised"])) for k, v in entry["state"]["sources"].items()})
        if not entry["state"]["reservations"]:
            assert entry["availability"] == state.availability()


def test_writer_refuses_to_overwrite_and_checks_the_record_state_pair(tmp_path: Path):
    path = tmp_path / "run.jsonl"
    genesis = WorldState.genesis(balances={"A": 1})
    with RunWriter(path, run_id="x", genesis=genesis, scenario={}, horizon=1) as writer:
        engine = Engine(genesis)
        proposal = consume("p", "A", 0, amount=1)
        record = engine.tick([proposal])
        with pytest.raises(RunFileError):
            writer.record(record, genesis, inputs=[proposal])  # wrong state for this record
        writer.record(record, engine.state, inputs=[proposal])
    with pytest.raises(FileExistsError):
        RunWriter(path, run_id="x", genesis=genesis, scenario={}, horizon=1)
    assert read_run(path).complete


@pytest.mark.parametrize("damage", ["flip-balance", "drop-tick", "truncate", "reorder"])
def test_tampered_or_cut_run_files_do_not_verify(tmp_path: Path, damage: str):
    path = tmp_path / "run.jsonl"
    run_scenario(Scenario(seed=5, actors=3, sources=1), 12, path)
    lines = path.read_bytes().splitlines(keepends=True)
    ticks = [k for k, line in enumerate(lines) if b'"kind":"tick"' in line]
    if damage == "flip-balance":
        target = ticks[4]
        payload = json.loads(lines[target])
        actor = sorted(payload["state"]["balances"])[0]
        payload["state"]["balances"][actor] += 1
        lines[target] = (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode()
    elif damage == "drop-tick":
        del lines[ticks[3]]
    elif damage == "truncate":
        lines = lines[: ticks[6]]
    else:
        lines[ticks[2]], lines[ticks[3]] = lines[ticks[3]], lines[ticks[2]]
    path.write_bytes(b"".join(lines))
    run = read_run(path)
    assert not run.complete and run.problems, damage


def test_viewer_renders_every_tick_from_the_file_with_no_external_resources(tmp_path: Path):
    path = tmp_path / "run.jsonl"
    run_scenario(Scenario(seed=8, actors=4, sources=2), 30, path)
    run = read_run(path)
    page = render_html(run)
    assert page.count("<script") == 2 and "src=" not in page and "href=" not in page
    assert not re.search(r"https?://", page)
    embedded = json.loads(re.search(r'<script id="run-data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert len(embedded["ticks"]) == 30 and embedded["header"]["genesis_digest"] == run.header["genesis_digest"]
    assert "file verifies" in page and "not evidence" in page
    text = render_text(run, 10)
    assert "after tick 10" in text and "actors:" in text and "outcomes" in text
    for actor in run.ticks[10]["state"]["balances"]:
        assert actor in text


def test_stream_is_downstream_of_the_kernel():
    """The kernel must not know the stream exists; the stream reads kernel objects only."""
    def imports(module: Path) -> set[str]:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
        return names

    for module in (REPO_ROOT / "kernel").glob("*.py"):
        assert "stream" not in imports(module), module.name
    for module in (REPO_ROOT / "stream").glob("*.py"):
        assert not imports(module) & {"automation", "tests"}, module.name


def test_scenario_is_reproducible_and_produces_lifecycle_input():
    scenario = Scenario(seed=21, actors=5, sources=2)
    a, b = ProposalGenerator(scenario), ProposalGenerator(scenario)
    live = {"action:" + "a" * 64: "p1", "action:" + "b" * 64: "p2"}
    kinds = set()
    for tick in range(40):
        first, second = a.tick(tick, live), b.tick(tick, live)
        assert first == second
        kinds.update(p.operation for p in first)
    assert {"claim", "transfer", "consume", "reserve", "complete", "cancel"} <= kinds
