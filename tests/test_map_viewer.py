"""The isometric map viewer: it shows the saved run and nothing else.

world/viewer_index.py reads a saved run once into events, request threads and
counts; world/viewer.js draws them. These tests hold the reading to the file:
every asking, answering and handing over the page lists is in the saved
decisions and kernel outcomes, a run without asking lists none, older world
shapes still open, rendering leaves the run file alone, and the page reaches
for nothing outside itself.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from stream.run_file import read_run
from world.config import ONE_SOURCE_FOOD_ONLY, SHORT_RANGE_LEVERS, WorldConfig
from world.run import main as run_main
from world.run import run_world
from world.viewer import render_html, render_text
from world.viewer_index import build_index

ROOT = Path(__file__).resolve().parent.parent


def _block(page: str, block_id: str):
    found = re.search(rf'<script id="{block_id}" type="application/json">(.*?)</script>', page, re.S)
    assert found, f"no {block_id} block"
    return json.loads(found.group(1))


@pytest.fixture(scope="module")
def asking_run(tmp_path_factory):
    """A world with asking switched on, long enough for requests to be answered,
    ignored and delivered."""
    path = tmp_path_factory.mktemp("asking") / "asking.jsonl"
    run_world(WorldConfig(seed=23, requests_on=True), 90, path)
    return read_run(path)


def test_every_request_event_is_a_saved_decision_or_outcome(asking_run):
    index = build_index(asking_run)
    kinds = [event["kind"] for event in index["events"]]
    assert {"ask", "agree", "unanswered", "delivered"} <= set(kinds)
    for event in index["events"]:
        tick = asking_run.ticks[event["k"] - 1]
        decisions = tick["decisions"]
        if event["kind"] in ("ask", "agree"):
            assert decisions[event["who"]]["kind"] == event["kind"]
            assert decisions[event["who"]]["target"] == event["other"]
        elif event["kind"] == "unanswered":
            asker, asked = event["who"], event["other"]
            before = asking_run.ticks[event["k"] - 2]["world"]
            assert before["requests"][asker] == asked
            answer = decisions.get(asked)
            assert not (answer and answer["kind"] == "agree" and answer.get("target") == asker)
        elif event["kind"] in ("delivered", "gave"):
            outcome = next(o for o in tick["record"]["outcomes"] if o["actor"] == event["who"])
            assert outcome["operation"] == "transfer" and outcome["accepted"]
            assert {"account": f"actor:{event['other']}", "delta": 1} in outcome["effects"]


def test_request_threads_follow_the_saved_world_state(asking_run):
    index = build_index(asking_run)
    asks = sum(d["kind"] == "ask" for tick in asking_run.ticks for d in tick["decisions"].values())
    assert len(index["threads"]) == asks == index["counts"]["asked"][-1]
    for thread in index["threads"]:
        if thread["answer"] in ("agreed", "no answer"):
            assert thread["answered"] == thread["asked"] + 1
        if thread["answer"] == "agreed":
            promised = asking_run.ticks[thread["answered"] - 1]["world"]["promises"]
            assert promised[thread["helper"]] == thread["asker"]
        if thread.get("end") == "delivered":
            assert thread["ended"] > thread["answered"]
    counts = index["counts"]
    assert counts["agreed"][-1] + counts["unanswered"][-1] <= counts["asked"][-1]
    assert counts["delivered"][-1] <= counts["agreed"][-1]


def test_counts_are_the_saved_worlds(asking_run):
    index = build_index(asking_run)
    worlds = [asking_run.header["world"]] + [tick["world"] for tick in asking_run.ticks]
    for view, world in enumerate(worlds):
        assert index["counts"]["people"][view] == len(world["positions"])
        assert index["counts"]["dead"][view] == len(world["died_at"])
        assert index["counts"]["shelters"][view] == len(world.get("shelters", []))
    births = [e["born"] for tick in asking_run.ticks for e in tick.get("production") or [] if "born" in e]
    assert sorted(index["born"]) == sorted(births)
    assert sorted(index["died"]) == sorted(worlds[-1]["died_at"])


def test_a_world_without_asking_lists_no_requests(tmp_path: Path):
    run_world(WorldConfig(seed=23), 90, tmp_path / "quiet.jsonl")
    index = build_index(read_run(tmp_path / "quiet.jsonl"))
    assert index["threads"] == []
    assert not {"ask", "agree", "unanswered", "delivered", "too_late"} & {e["kind"] for e in index["events"]}


@pytest.mark.parametrize("levers", [ONE_SOURCE_FOOD_ONLY, SHORT_RANGE_LEVERS], ids=["one-source", "short-range"])
def test_older_world_shapes_still_open(tmp_path: Path, levers):
    run_world(WorldConfig(seed=7, **levers), 60, tmp_path / "old.jsonl")
    run = read_run(tmp_path / "old.jsonl")
    page = render_html(run)
    index = _block(page, "view-index")
    assert index["water"] == [] and len(index["food"]) == 1
    assert {e["cat"] for e in index["events"]} <= {"food", "need", "source", "life", "crowd"}
    for layer in ("water", "rough", "spots", "shelters"):          # no switch for what the run never had
        assert f'data-layer="{layer}"' not in page
    assert "view 60/60" in render_text(run, 60)


def test_rendering_leaves_the_run_file_and_the_run_alone(asking_run):
    before = hashlib.sha256(asking_run.path.read_bytes()).hexdigest()
    ticks_before = json.dumps(asking_run.ticks, sort_keys=True)
    page = render_html(asking_run)
    build_index(asking_run)
    assert hashlib.sha256(asking_run.path.read_bytes()).hexdigest() == before
    assert json.dumps(asking_run.ticks, sort_keys=True) == ticks_before
    assert _block(page, "view-index") == build_index(asking_run)
    assert _block(page, "run-data")["ticks"] == [dict(tick) for tick in asking_run.ticks]


def test_the_page_runs_no_world_rules(asking_run, monkeypatch):
    import world.decide
    import world.observe
    import world.process

    def forbidden(*_args, **_kwargs):
        raise AssertionError("the viewer ran a world rule")
    for module, name in ((world.decide, "decide"), (world.observe, "observe"), (world.process, "advance")):
        monkeypatch.setattr(module, name, forbidden)
    render_html(asking_run)
    for source in ("world/viewer.py", "world/viewer_index.py"):
        tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert not imported & {"world.decide", "world.observe", "world.process", "world.run", "world.config", "kernel"}, source


def test_the_page_is_self_contained(asking_run):
    page = render_html(asking_run)
    assert not re.search(r'(src|href)\s*=\s*["\']?(https?:)?//', page)
    for reach in ("<link", "<script src", "@import", "url(", "fetch(", "XMLHttpRequest", "WebSocket", "import("):
        assert reach not in page, reach
    assert "localStorage" not in page and "sessionStorage" not in page


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_script_parses_under_node(asking_run, tmp_path: Path):
    page = render_html(asking_run)
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert len(scripts) == 1
    (tmp_path / "page.js").write_text(scripts[0], encoding="utf-8")
    subprocess.run(["node", "--check", str(tmp_path / "page.js")], check=True, capture_output=True)


def test_the_run_command_still_writes_the_page_beside_the_run(tmp_path: Path, capsys):
    out = tmp_path / "viewer-test.jsonl"
    assert run_main(["--seed", "11", "--ticks", "30", "--html", "--out", str(out)]) == 0
    page = out.with_suffix(".html").read_text(encoding="utf-8")
    assert 'id="view-index"' in page and 'id="run-data"' in page and "file verifies" in page
    assert f"viewer: {out.with_suffix('.html')}" in capsys.readouterr().out


def test_family_is_shown_only_as_the_run_records_it(tmp_path: Path):
    run_world(WorldConfig(seed=11), 90, tmp_path / "kin.jsonl")
    run = read_run(tmp_path / "kin.jsonl")
    index = build_index(run)
    last = run.ticks[-1]["world"]
    assert index["parent"] == last["parent"] and index["adult_at"] == run.header["scenario"]["adult_at"]
    kinds = {event["kind"] for event in index["events"]}
    assert {"fed_child", "grew_up"} <= kinds
    for event in index["events"]:
        world, before = run.ticks[event["k"] - 1]["world"], (
            run.ticks[event["k"] - 2]["world"] if event["k"] >= 2 else run.header["world"])
        if event["kind"] == "fed_child":
            assert world["parent"][event["other"]] == event["who"]
        elif event["kind"] == "grew_up":
            assert world["age"][event["who"]] >= index["adult_at"] > before["age"][event["who"]]
    assert 'data-layer="family"' in render_html(run)
    run_world(WorldConfig(seed=11, childhood_on=False), 40, tmp_path / "nokin.jsonl")
    plain = read_run(tmp_path / "nokin.jsonl")
    assert build_index(plain)["parent"] == {} and build_index(plain)["adult_at"] is None
    assert 'data-layer="family"' not in render_html(plain)
