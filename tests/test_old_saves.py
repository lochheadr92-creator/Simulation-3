"""A run saved by the baseline code (commit 02af86b, before any rich-world feature existed) still opens, verifies, renders and
replays to the same world under the current code. Resuming it does not work, by design: recovery refuses a file written by other code."""

import json
import shutil
from pathlib import Path

import pytest

from stream.recover import RecoveryError
from stream.run_file import read_run
from world.config import WorldConfig
from world.launch import Launcher
from world.overlay import Overlay
from world.recover import recover_world
from world.replay import replay_world
from world.viewer import render_html

OLD = Path(__file__).resolve().parent / "fixtures" / "baseline-02af86b-seed7-ticks120.jsonl"


def test_a_baseline_run_opens_verifies_and_keeps_its_header_and_world_blocks_unchanged():
    run = read_run(OLD)
    assert run.complete and not run.problems and len(run.ticks) == 120
    config = WorldConfig.from_describe(run.header["scenario"])
    assert config.features == () and WorldConfig.from_describe(config.describe()) == config
    assert all(Overlay.from_canonical(t["world"]).digest() == t["world_digest"] for t in run.ticks)    # the canonical form did not move
    assert Overlay.from_canonical(run.header["world"]).digest() == run.header["world_digest"]
    assert not {"things", "family", "ground", "pledges", "persona"} & set(run.ticks[-1]["world"])      # new blocks are absent when empty


def test_a_baseline_run_renders_in_the_viewer_and_shows_in_the_launcher(tmp_path):
    run = read_run(OLD)
    page = render_html(run)
    assert 'id="run-data"' in page and "observerPart" in page and "file verifies" in page
    runs = tmp_path / "runs"
    runs.mkdir()
    shutil.copy(OLD, runs / "old.jsonl")
    status = Launcher(runs).status("old.jsonl")
    assert status["complete"] and status["ticks"] == 120 and not status["cut"]


def test_the_current_code_replays_a_baseline_run_to_the_same_world_tick_for_tick():
    result = replay_world(OLD)
    assert result.identical


def test_resuming_a_cut_baseline_run_is_refused_because_other_code_wrote_it(tmp_path):
    lines, kept, count = OLD.read_bytes().splitlines(keepends=True), [], 0
    for line in lines:
        payload = json.loads(line)
        if payload.get("kind") == "tick":
            if count == 50:
                break
            count += 1
        elif payload.get("kind") == "end":
            break
        kept.append(line)
    cut = tmp_path / "cut.jsonl"
    cut.write_bytes(b"".join(kept))
    with pytest.raises(RecoveryError, match="other code"):
        recover_world(cut, tmp_path / "resumed.jsonl")
    assert not (tmp_path / "resumed.jsonl").exists()
