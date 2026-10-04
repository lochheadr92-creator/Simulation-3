"""Every inspector section the rich features add really appears in a real browser for somebody in a real rich world, and the page
raises no errors while visiting every person every few ticks."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stream.run_file import read_run
from world.presets import rich_world
from world.run import run_world
from world.viewer import render_html

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = ("Asking and promising", "Death record (for the reader of the run)", "Family", "Field", "Knows about wolves",
            "Knows of deaths", "Relationships", "Skills", "Stone and tools", "Temperament", "What they have built",
            "What they know of the ground")


@pytest.mark.long_run
def test_each_feature_section_shows_up_for_somebody_in_a_rich_world_and_the_page_stays_clean(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("The inspector test needs Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    path = tmp_path / "rich.jsonl"
    run_world(rich_world(23), 300, path)
    page = tmp_path / "rich.html"
    page.write_text(render_html(read_run(path)), encoding="utf-8")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/inspector_sections.cjs"), str(page), "25"], cwd=ROOT,
                            capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout)
    assert shown["errors"] == []
    missing = [h for h in EXPECTED if h not in shown["headings"]]
    assert not missing, f"sections never shown: {missing}"
