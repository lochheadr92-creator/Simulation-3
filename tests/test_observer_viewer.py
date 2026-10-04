"""The observer tools in the page: the minimap, the knowledge fog, headings, a link that remembers the view, and a ring where
an event happened. Driven in a real browser through the page's own controls. They read recorded values and change nothing:
what the page shows for a tick does not depend on speed or camera."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stream.run_file import read_run
from world.config import WorldConfig
from world.run import run_world
from world.viewer import render_html

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ("aftermath", "beliefs", "bonds", "explain", "family", "personality", "skills", "sky", "sleep", "steady", "wolves")


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("observer") / "run.jsonl"
    run_world(WorldConfig(seed=23, features=FEATURES), 260, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_the_observer_tools_work_in_a_real_browser_and_change_nothing_about_the_record(saved, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("The observer viewer test needs Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    _, run = saved
    page = tmp_path / "page.html"
    page.write_text(render_html(run), encoding="utf-8")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/observer_viewer.cjs"), str(page), "was laid to rest"], cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    out = json.loads(result.stdout)
    assert out["errors"] == []
    assert out["opened"]["view"] == 60 and out["opened"]["selected"] == {"type": "person", "id": "p01"}          # the link restored the view
    assert out["minimap"] == {"moved": True, "sameView": True, "sameSelection": True}
    assert out["speedIndependent"] is True
    assert out["layers"] == {"fog": True, "heading": True}
    assert out["eventClicked"] is True and out["place"] is not None
    # the fog, counted by the page, equals the same count made here from the saved positions, sky and sleep state
    assert out["fogAt40"] == fog_counts(run, "p01", 40) and out["fogAt150"] == fog_counts(run, "p01", 150)
    assert out["fogAt40"]["unseen"] > 0 and out["fogAt150"]["remembered"] > out["fogAt40"]["remembered"] - 1


def fog_counts(run, who, view):
    """How many cells are in sight now, seen before, or never seen, by view `view`, from recorded values alone."""
    config = run.header["scenario"]
    width, height, base = config["width"], config["height"], config["perception_radius"]
    levers = config.get("feature_levers") or {}
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]

    def radius(world):
        if who in (world.get("persona") or {}).get("asleep", {}):
            return 0
        sky = world.get("sky")
        if not sky or base <= 0:
            return base
        cut = (levers.get("night_sight", 0) if sky["phase"] == "night" else 0) + (levers.get("storm_sight", 0) if sky["weather"] == "storm" else 0)
        return max(1, base - cut)

    def window(world):
        x, y = world["positions"][who]
        r = radius(world)
        return {(a, b) for a in range(max(0, x - r), min(width - 1, x + r) + 1) for b in range(max(0, y - r), min(height - 1, y + r) + 1)}
    seen = set()
    for j in range(view):
        if who in worlds[j]["positions"] and who not in worlds[j].get("died_at", {}):
            seen |= window(worlds[j])
    now = window(worlds[view])
    return {"now": len(now), "remembered": len(seen - now), "unseen": width * height - len(now | seen)}


def test_events_that_have_a_place_carry_the_recorded_cell(saved):
    from world.viewer_index import build_index
    _, run = saved
    index = build_index(run)
    placed = [e for e in index["events"] if e["kind"] in ("grave", "collected")]
    assert placed, "this world should lay somebody to rest"
    for event in placed:
        record = {d[0]: d for d in run.ticks[event["k"] - 1]["world"]["things"]["deaths"]}
        person = event["who"] if event["kind"] == "grave" else event["other"]
        assert event["cell"] == [record[person][2], record[person][3]]          # where the record says they died


def test_the_page_holds_the_observer_part_for_every_run_and_still_runs_no_world_rules(saved):
    _, run = saved
    page = render_html(run)
    assert "observerPart" in page and 'data-layer="fog"' in page and 'data-layer="heading"' in page
    for banned in ("localStorage", "sessionStorage", "fetch(", "WebSocket", "XMLHttpRequest", "url("):
        assert banned not in page, banned
