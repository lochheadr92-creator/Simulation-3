"""Existing behaviour must not move when the new rich-world options are off.

`tests/fixtures/baseline_digests.json` holds digests of fresh runs at baseline
commit 02af86b, before the rich-world work began. Each configuration below uses
only options that existed then. If one digest changes, an existing rule changed:
either undo that change or, when it was intended, say so and regenerate the
fixture from the new rule.

The content digest covers every tick line (decisions, observations, settlement,
overlay) without its seal. Seals chain from a hash of the source files, so a
whole-line digest would change with any code edit and prove nothing.
"""

import hashlib
import json
from pathlib import Path

import pytest

from kernel import canonical_bytes
from stream.run_file import read_run, without_seal
from world.config import WorldConfig
from world.run import run_world

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "baseline_digests.json").read_text(encoding="utf-8"))
ENTRIES = {entry["name"]: entry for entry in FIXTURE["configs"]}


def content_digest(run) -> str:
    digest = hashlib.sha256()
    for tick in run.ticks:
        digest.update(canonical_bytes(without_seal(tick)) + b"\n")
    return digest.hexdigest()


@pytest.mark.long_run
@pytest.mark.parametrize("name", sorted(ENTRIES))
def test_existing_options_reproduce_the_baseline_run(name, tmp_path):
    entry = ENTRIES[name]
    result = run_world(WorldConfig(**entry["config"]), entry["ticks"], tmp_path / "run.jsonl")
    run = read_run(tmp_path / "run.jsonl")
    assert run.complete
    assert content_digest(run) == entry["content_digest"]
    assert result.final_state_digest == entry["final_state_digest"]
    assert result.final_overlay_digest == entry["final_overlay_digest"]
    assert (result.survivors, result.deaths) == (entry["survivors"], entry["deaths"])
