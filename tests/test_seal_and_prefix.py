"""The seal chain and the recovery prefix, checked against their definitions
rather than the helpers that produce them (review findings F3 and F4).

Seal chain: the header seal is sha256 of the canonical header without its
seal; each tick seal is sha256 of canonical {"prev": previous seal, "tick":
sha256 of the canonical tick without its seal}; the end line's final seal is
the last tick's. Recovery keeps the source's bytes exactly through the last
sealed tick line and nothing after it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kernel import canonical_bytes
from stream.recover import recover_scenario, sealed_prefix
from stream.run import run_scenario
from stream.run_file import read_run
from stream.scenario import Scenario


def sha(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def unsealed(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "seal"}


def tick_index(lines: list[bytes], tick: int) -> int:
    return next(i for i, line in enumerate(lines) if b'"kind":"tick"' in line and json.loads(line)["tick"] == tick)


@pytest.fixture(scope="module")
def run_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("seal") / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 60, path)
    return path


def test_every_seal_follows_the_declared_chain(run_file):
    lines = [json.loads(line) for line in run_file.read_bytes().splitlines()]
    header = lines[0]
    assert header["seal"] == sha(unsealed(header))
    previous = header["seal"]
    ticks = [line for line in lines if line["kind"] == "tick"]
    assert len(ticks) == 60
    for tick in ticks:
        assert tick["seal"] == sha({"prev": previous, "tick": sha(unsealed(tick))}), tick["tick"]
        previous = tick["seal"]
    assert lines[-1]["kind"] == "end" and lines[-1]["final_seal"] == previous


def test_the_reader_rejects_a_seal_that_leaves_out_the_previous_seal(run_file, tmp_path):
    lines = run_file.read_bytes().splitlines(keepends=True)
    index = tick_index(lines, 20)
    payload = json.loads(lines[index])
    payload["seal"] = sha({"tick": sha(unsealed(payload))})
    lines[index] = canonical_bytes(payload) + b"\n"
    forged = tmp_path / "forged.jsonl"
    forged.write_bytes(b"".join(lines))
    run = read_run(forged)
    assert run.last_sealed_tick == 19 and run.first_break_line == index + 1


@pytest.mark.parametrize("keep_timing_line", [False, True])
def test_the_recovery_prefix_ends_exactly_at_the_last_sealed_tick_line(run_file, tmp_path, keep_timing_line):
    lines = run_file.read_bytes().splitlines(keepends=True)
    index = tick_index(lines, 30)
    if keep_timing_line:
        assert json.loads(lines[index + 1])["kind"] == "timing"
    cut = tmp_path / "cut.jsonl"
    cut.write_bytes(b"".join(lines[: index + (2 if keep_timing_line else 1)]))
    expected = b"".join(lines[: index + 1])

    assert sealed_prefix(cut).prefix == expected
    recover_scenario(cut, tmp_path / "recovered.jsonl")
    recovered = (tmp_path / "recovered.jsonl").read_bytes()
    assert recovered.startswith(expected)
    following = json.loads(recovered[len(expected):].split(b"\n", 1)[0])
    assert following["kind"] == "tick" and following["tick"] == 31
