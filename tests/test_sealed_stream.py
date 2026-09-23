"""Slice 1c: the sealed evidence stream, v3.stream.3 (declaration items 1-4).

A sealed file vouches for itself. The header and every tick line are chained
by seals; the reader names the first line that fails any check and reports
the last tick that line and every line before it still vouch for. These are
focused transaction tests on the kernel-only scenario and small worlds; they
are not runs and not behavioural evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kernel import Engine, WorldState, canonical_bytes, consume, digest
from kernel.proposals import Proposal
from stream.run import run_scenario
from stream.run_file import (STREAM_FORMAT, RunFileError, RunWriter, code_identity, decode_input, encode_input,
                             header_seal, read_run, tick_seal)
from stream.scenario import ProposalGenerator, Scenario
from world.config import WorldConfig
from world.run import run_world


def lines_of(path: Path) -> list[bytes]:
    return path.read_bytes().splitlines(keepends=True)


def tick_indexes(lines: list[bytes]) -> list[int]:
    return [index for index, line in enumerate(lines) if b'"kind":"tick"' in line]


@pytest.fixture
def scenario_file(tmp_path: Path) -> Path:
    path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 30, path)
    return path


# --- a fresh file ----------------------------------------------------------------

def test_a_fresh_scenario_run_is_sealed_through_its_last_tick(scenario_file: Path):
    run = read_run(scenario_file)
    assert run.complete and run.sealed and run.problems == ()
    assert run.header["format"] == STREAM_FORMAT == "v3.stream.3"
    assert run.last_sealed_tick == 29 and run.first_break_line is None
    assert run.header["seal"] == header_seal(run.header)
    previous = run.header["seal"]
    for tick in run.ticks:
        assert tick["seal"] == tick_seal(previous, tick)
        previous = tick["seal"]
    assert run.end["final_seal"] == previous
    assert run.end["ticks"] == run.header["horizon"] == 30


def test_a_fresh_world_run_is_sealed_through_its_last_tick(tmp_path: Path):
    path = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=7, width=7, height=7, actors=4), 30, path)
    run = read_run(path)
    assert run.complete and run.sealed and run.last_sealed_tick == 29
    assert all("inputs" in tick and "seal" in tick for tick in run.ticks)


def test_the_header_names_code_configuration_and_horizon_and_nothing_host_specific(scenario_file: Path):
    header = read_run(scenario_file).header
    assert header["code_identity"] == code_identity()
    files = header["code_identity"]["files"]
    assert {"kernel/state.py", "stream/run_file.py", "stream/replay.py", "world/run.py"} <= set(files)
    assert all(name.split("/")[0] in {"kernel", "stream", "world"} for name in files)
    assert header["code_identity"]["digest"] == digest(files)
    assert header["config_identity"] == digest(header["scenario"])
    assert header["horizon"] == 30
    assert header["engine_version"] == "0.2.0-stage1b" and header["schema_version"] == "v3.kernel.1b.1"
    assert not [key for key in header if any(word in key for word in ("git", "host", "time", "clock"))]


def test_code_identity_reads_crlf_as_lf(tmp_path: Path):
    for text in (b"x = 1\n", b"x = 1\r\n"):
        root = tmp_path / ("crlf" if b"\r" in text else "lf")
        for package in ("kernel", "stream", "world"):
            (root / package).mkdir(parents=True)
            (root / package / "m.py").write_bytes(text)
    assert code_identity(tmp_path / "lf") == code_identity(tmp_path / "crlf")


# --- inputs ------------------------------------------------------------------------

def test_inputs_are_the_proposals_the_runner_submitted_in_order(tmp_path: Path):
    scenario = Scenario(seed=7)
    engine = Engine(scenario.genesis())
    generator = ProposalGenerator(scenario)
    submitted: list[list[Proposal]] = []
    path = tmp_path / "inputs.jsonl"
    with RunWriter(path, run_id="inputs", genesis=engine.state, scenario=scenario.describe(), horizon=120) as writer:
        for _ in range(120):
            live = {action: held.actor for action, held in engine.state.reservations.items()}
            proposals = generator.tick(engine.state.tick, live)
            submitted.append(proposals)
            record = engine.tick(proposals)
            writer.record(record, engine.state, inputs=proposals)
    run = read_run(path)
    assert run.complete
    assert [[decode_input(entry) for entry in tick["inputs"]] for tick in run.ticks] == submitted


def test_empty_ticks_and_params_without_a_canonical_form_round_trip(tmp_path: Path):
    genesis = WorldState.genesis(balances={"A": 3, "B": 0})
    engine = Engine(genesis)
    ticks = [
        [],
        [Proposal("t1-0", "A", 0, "consume", {"amount": True}),
         Proposal("t1-1", "A", 1, "transfer", {"to": "B", "amount": 1})],
        [Proposal("t2-0", "B", 0, "consume", {"amount": 1.0}),
         Proposal("t2-1", "A", 0, "claim", {"sources": {1: 2}}),
         Proposal("t2-2", "A", 1, "dance", {"steps": [1, "two", None], "nested": {"k": (True, 3)}})],
    ]
    path = tmp_path / "typed.jsonl"
    with RunWriter(path, run_id="typed", genesis=genesis, scenario={"name": "hand-built"}, horizon=len(ticks)) as writer:
        for proposals in ticks:
            record = engine.tick(proposals)
            writer.record(record, engine.state, inputs=proposals)
    run = read_run(path)
    assert run.complete and run.last_sealed_tick == 2
    assert [[decode_input(entry) for entry in tick["inputs"]] for tick in run.ticks] == ticks
    assert run.ticks[0]["inputs"] == []
    typed = {entry["proposal_id"] for tick in run.ticks for entry in tick["inputs"] if "params_typed" in entry}
    assert typed == {"t1-0", "t2-0", "t2-1", "t2-2"}
    assert run.ticks[1]["inputs"][1]["params"] == {"amount": 1, "to": "B"}
    assert encode_input(ticks[1][0])["params_typed"] == ["map", [[["str", "amount"], ["bool", 1]]]]


def test_the_writer_refuses_inputs_it_cannot_encode_or_the_record_did_not_settle(tmp_path: Path):
    genesis = WorldState.genesis(balances={"A": 1})
    engine = Engine(genesis)
    odd = Proposal("x", "A", 0, "consume", {"amount": {1, 2}})
    record = engine.tick([odd])
    writer = RunWriter(tmp_path / "w.jsonl", run_id="w", genesis=genesis, scenario={}, horizon=1)
    with pytest.raises(RunFileError, match="no declared input encoding"):
        writer.record(record, engine.state, inputs=[odd])
    with pytest.raises(RunFileError, match="not the proposals"):
        writer.record(record, engine.state, inputs=[])
    with pytest.raises(RunFileError, match="not the proposals"):
        writer.record(record, engine.state, inputs=[consume("y", "A", 0, amount=1)])
    writer.abort()
    assert read_run(tmp_path / "w.jsonl").end is None


# --- stopping early ----------------------------------------------------------------

def test_a_run_closed_or_stopped_before_its_horizon_has_no_end_line(tmp_path: Path):
    genesis = WorldState.genesis(balances={"A": 3})
    closed = tmp_path / "closed.jsonl"
    writer = RunWriter(closed, run_id="c", genesis=genesis, scenario={}, horizon=3)
    engine = Engine(genesis)
    writer.record(engine.tick([]), engine.state, inputs=[])
    with pytest.raises(RunFileError, match="1 of 3"):
        writer.close()
    stopped = tmp_path / "stopped.jsonl"
    engine = Engine(genesis)
    with pytest.raises(RuntimeError):
        with RunWriter(stopped, run_id="s", genesis=genesis, scenario={}, horizon=3) as writer:
            writer.record(engine.tick([]), engine.state, inputs=[])
            raise RuntimeError("stopped")
    for path in (closed, stopped):
        run = read_run(path)
        assert run.end is None and not run.complete
        assert run.last_sealed_tick == 0 and run.first_break_line is None


def test_the_writer_refuses_ticks_out_of_order_or_past_the_horizon(tmp_path: Path):
    genesis = WorldState.genesis(balances={"A": 3})
    engine = Engine(genesis)
    first = engine.tick([])
    second = engine.tick([])
    writer = RunWriter(tmp_path / "w.jsonl", run_id="w", genesis=genesis, scenario={}, horizon=1)
    with pytest.raises(RunFileError, match="expected a record for tick 0"):
        writer.record(second, engine.state, inputs=[])
    replay = Engine(genesis)
    writer.record(replay.tick([]), replay.state, inputs=[])
    with pytest.raises(RunFileError, match="horizon"):
        writer.record(replay.tick([]), replay.state, inputs=[])
    writer.close()
    assert first.tick == 0 and read_run(tmp_path / "w.jsonl").complete


# --- damage --------------------------------------------------------------------------

def damage(path: Path, how: str, target: int) -> int:
    """Damage the line of tick `target` and return the 1-based number of the
    first line the reader should find broken."""
    lines = lines_of(path)
    ticks = tick_indexes(lines)
    index = ticks[target]
    first_broken = index + 1
    if how == "edit-content":
        payload = json.loads(lines[index])
        account = sorted(payload["availability"])[0]
        payload["availability"][account] += 1
        lines[index] = canonical_bytes(payload) + b"\n"
    elif how == "edit-seal-byte":
        line = bytearray(lines[index])
        at = line.index(b'"seal":"') + len(b'"seal":"')
        line[at] = ord("1") if line[at] == ord("0") else ord("0")
        lines[index] = bytes(line)
    elif how == "delete":
        first_broken = ticks[target + 1]   # the next tick line moves up one place
        del lines[index]
    elif how == "swap":
        lines[index], lines[ticks[target + 1]] = lines[ticks[target + 1]], lines[index]
    elif how == "cut-mid-line":
        lines = lines[:index] + [lines[index][: len(lines[index]) // 2]]
    else:
        raise AssertionError(how)
    path.write_bytes(b"".join(lines))
    return first_broken


@pytest.mark.parametrize("how", ["edit-content", "edit-seal-byte", "delete", "swap", "cut-mid-line"])
def test_damage_breaks_the_chain_at_its_line_and_nothing_after_it_counts(scenario_file: Path, how: str):
    first_broken = damage(scenario_file, how, 12)
    run = read_run(scenario_file)
    assert not run.complete
    assert run.first_break_line == first_broken
    assert run.last_sealed_tick == 11


def test_an_edited_header_breaks_every_seal(scenario_file: Path):
    lines = lines_of(scenario_file)
    header = json.loads(lines[0])
    header["run_id"] = "renamed"
    lines[0] = canonical_bytes(header) + b"\n"
    scenario_file.write_bytes(b"".join(lines))
    run = read_run(scenario_file)
    assert run.first_break_line == 1 and run.last_sealed_tick == -1
    assert any("header seal does not verify" in problem for problem in run.problems)


def test_the_end_line_must_carry_the_final_seal(scenario_file: Path):
    lines = lines_of(scenario_file)
    end = json.loads(lines[-1])
    end["final_seal"] = "0" * 64
    lines[-1] = canonical_bytes(end) + b"\n"
    scenario_file.write_bytes(b"".join(lines))
    run = read_run(scenario_file)
    assert not run.complete and run.first_break_line == len(lines)
    assert run.last_sealed_tick == 29


def test_v3_stream_2_files_stay_readable_without_seal_checks(scenario_file: Path, tmp_path: Path):
    """Strip the 1c additions from a sealed file and label it v3.stream.2: the
    earlier rules still verify it, and no seal is looked for."""
    trail = hashlib.sha256()
    out: list[bytes] = []
    for raw in lines_of(scenario_file):
        payload = json.loads(raw)
        if payload["kind"] == "header":
            for key in ("seal", "horizon", "code_identity", "config_identity"):
                payload.pop(key)
            payload["format"] = "v3.stream.2"
        elif payload["kind"] == "tick":
            payload.pop("seal")
            payload.pop("inputs")
            raw = canonical_bytes(payload) + b"\n"
            trail.update(raw)
            out.append(raw)
            continue
        elif payload["kind"] == "end":
            payload.pop("final_seal")
            payload["trail_digest"] = trail.hexdigest()
        out.append(canonical_bytes(payload) + b"\n")
    old = tmp_path / "old.jsonl"
    old.write_bytes(b"".join(out))
    run = read_run(old)
    assert run.complete and not run.sealed and run.last_sealed_tick is None
