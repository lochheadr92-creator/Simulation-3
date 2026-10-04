"""The page for a rich world shows traits, skills, tiredness and set-aside options from the saved run.

Needs Node, Playwright and a browser, like tests/test_viewer_security.py, and fails
explicitly rather than skipping when they are missing.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stream.run_file import read_run
from world.config import WorldConfig
from world.run import run_world
from world.viewer import JS_PARTS, PARTS_MARKER, render_html
from world.viewer_index import build_index

ROOT = Path(__file__).resolve().parent.parent
RICH = ("explain", "personality", "skills", "sleep")


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("page") / "run.jsonl"
    run_world(WorldConfig(seed=11, features=RICH), 120, path)
    return path, read_run(path)


def test_the_page_splices_its_parts_and_leaves_no_marker(saved):
    _, run = saved
    page = render_html(run)
    assert PARTS_MARKER not in page and "personaPart" in page
    plain = render_html(read_run(_plain_run(saved[0].parent)))
    assert "personaPart" not in plain and PARTS_MARKER not in plain        # an ordinary run's page is unchanged


def _plain_run(directory):
    path = directory / "plain.jsonl"
    if not path.exists():
        run_world(WorldConfig(seed=11), 30, path)
    return path


def test_the_index_derives_sleep_waking_and_learning_from_recorded_values(saved):
    _, run = saved
    index = build_index(run)
    kinds = {event["kind"] for event in index["events"]}
    assert {"fell_asleep", "woke"} <= kinds
    assert [k for k in (e["k"] for e in index["events"])] == sorted(e["k"] for e in index["events"])
    assert "go_sleep" in index["moves"] and index["phrases"]["sleep"] == "sleeping"
    assert any(name == "rest" for name, _ in index["categories"])
    # every sleep event names a person the run records, and sits on a tick that records the sleep
    for event in (e for e in index["events"] if e["kind"] == "fell_asleep"):
        decisions = run.ticks[event["k"] - 1]["decisions"]
        assert decisions[event["who"]]["kind"] in ("sleep", "collapse")


def test_an_ordinary_run_gains_no_rich_events(tmp_path):
    path = tmp_path / "plain.jsonl"
    run_world(WorldConfig(seed=11), 60, path)
    index = build_index(read_run(path))
    assert not {"fell_asleep", "woke", "skill_up", "withheld"} & {e["kind"] for e in index["events"]}


def test_the_browser_shows_a_sleeper_and_their_temperament(saved, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Rich viewer test requires Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    path, run = saved
    index = build_index(run)
    event = next(e for e in index["events"] if e["kind"] == "fell_asleep" and e["k"] > 3)
    page = tmp_path / "rich.html"
    page.write_text(render_html(run), encoding="utf-8")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/rich_viewer.cjs"), page.as_uri(),
                             str(event["k"] + 1), event["who"]], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout)
    assert shown["errors"] == []
    text = shown["inspector"].lower()                 # headings are uppercased by the stylesheet
    for expected in ("fatigue", "temperament", "generosity", "skills", "gathering", "sleeping"):
        assert expected in text, expected
    assert {"personality", "skills", "sleep", "explain"} <= set(shown["chips"])
    assert "Sleep and tiredness" in " ".join(shown["eventCategories"])
    assert "feature: sleep" in shown["rules"]
