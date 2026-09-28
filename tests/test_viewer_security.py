"""Untrusted saved strings must stay text in the rendered browser DOM.

This file requires Node, locked Playwright dependencies and a browser. Missing
prerequisites fail explicitly: this security regression must never silently skip.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kernel import Engine, WorldState
from stream.run_file import RunWriter, read_run
from world.config import WorldConfig, genesis
from world.overlay import Overlay
from world.run import world_step
from world.viewer import render_html

ROOT = Path(__file__).resolve().parent.parent
ATTACK_ID = '<img src=x onerror="window.__viewer_xss=7">'


def test_verified_run_actor_id_is_text_in_rendered_dom(tmp_path):
    node = shutil.which('node')
    if node is None:
        pytest.fail('Viewer security test requires Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md')

    def rename(value):
        if isinstance(value, dict):
            return {rename(k): rename(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rename(v) for v in value]
        return ATTACK_ID if value == 'p01' else value

    cfg = WorldConfig(seed=1, actors=2, starting_food=0, source_stock=0,
                      source_cap=0, renewal_amount=0, hungry_at=0,
                      emergency_at=1, death_at=2, stagger_start=False,
                      water_on=False, warmth_on=False, terrain_on=False,
                      building_on=False, births_on=False)
    ledger, world = genesis(cfg)
    ledger = WorldState.from_canonical(rename(ledger.canonical()))
    world = Overlay.from_canonical(rename(world.canonical()))
    path = tmp_path / 'untrusted.jsonl'
    engine = Engine(ledger)
    with RunWriter(path, run_id='untrusted-actor', genesis=ledger,
                   scenario=cfg.describe(), world=world.canonical(), horizon=3) as writer:
        for _ in range(3):
            step = world_step(engine, world, cfg)
            writer.record(step.record, step.committed, inputs=step.proposals, **step.line_fields())
            engine, world = step.engine, step.processed.overlay
    run = read_run(path)
    assert run.complete and not run.problems  # hashes are not sender authentication
    assert ATTACK_ID in run.ticks[-1]['world']['died_at']
    page = render_html(run)
    # Always check the Python embedding boundary as well as the dynamic DOM.
    assert ATTACK_ID not in page
    html = tmp_path / 'untrusted.html'
    html.write_text(page, encoding='utf-8')
    result = subprocess.run([node, str(ROOT / 'tests/fixtures/viewer_security.cjs'),
                             html.as_uri(), ATTACK_ID], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    checked = json.loads(result.stdout)
    assert checked['literal_id_visible'] and checked['injected_elements'] == 0
    assert checked['executed'] is None and checked['page_errors'] == []
