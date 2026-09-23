"""Slice 1c: recovery through the last verified sealed tick (declaration item 7)
and private instance isolation (item 8).

Recovery keeps only what the seal chain vouches for and continues from the
state the last sealed tick left. The check is the strongest one available:
the recovered file's content lines (header, ticks, end, seals included) must
equal an uninterrupted run's, with only timing lines allowed to differ. World
runs are the declaration's optional targets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import stream.recover as recover_module
from kernel import canonical_bytes, digest
from stream.recover import RecoveryError, recover_scenario, restore_engine
from stream.run import main as stream_main
from stream.run import run_scenario
from stream.run_file import decode_input, header_seal, read_run, tick_seal
from stream.scenario import Scenario
from world.config import WorldConfig
from world.recover import recover_world
from world.run import main as world_main
from world.run import run_world


def content(path: Path) -> list[bytes]:
    """Every line except timing lines: what recovery must reproduce byte for byte."""
    return [line for line in path.read_bytes().splitlines(keepends=True) if b'"kind":"timing"' not in line]


def index_of_tick(lines: list[bytes], tick: int) -> int:
    return next(i for i, line in enumerate(lines) if b'"kind":"tick"' in line and json.loads(line)["tick"] == tick)


def cut_after(source: Path, tick: int, dest: Path) -> Path:
    """A copy of `source` that stops right after tick `tick`'s line, as if the
    writing process died there."""
    lines = source.read_bytes().splitlines(keepends=True)
    dest.write_bytes(b"".join(lines[: index_of_tick(lines, tick) + 1]))
    return dest


def reseal(path: Path) -> None:
    """Recompute every seal (and any end line) after an edit, as a forger would."""
    out: list[bytes] = []
    trail = hashlib.sha256()
    seal = None
    for raw in path.read_bytes().splitlines(keepends=True):
        payload = json.loads(raw)
        if payload["kind"] == "header":
            payload["seal"] = header_seal(payload)
            seal = payload["seal"]
        elif payload["kind"] == "tick":
            payload["seal"] = tick_seal(seal, payload)
            seal = payload["seal"]
            raw = canonical_bytes(payload) + b"\n"
            trail.update(raw)
            out.append(raw)
            continue
        elif payload["kind"] == "end":
            payload["trail_digest"], payload["final_seal"] = trail.hexdigest(), seal
        out.append(canonical_bytes(payload) + b"\n")
    path.write_bytes(b"".join(out))


def declared_cut(path: Path) -> int:
    """The declaration's cut rule: the first tick at or after 40 whose state
    holds at least one live reservation."""
    return next(t["tick"] for t in read_run(path).ticks if t["tick"] >= 40 and t["state"]["reservations"])


@pytest.fixture(scope="module")
def uninterrupted(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("recovery") / "scenario-seed7.jsonl"
    run_scenario(Scenario(seed=7), 120, path)
    return path


@pytest.fixture(scope="module")
def uninterrupted_world(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("recovery-world") / "world-seed7.jsonl"
    run_world(WorldConfig(seed=7), 120, path)
    return path


# --- recovery: scenario runs (essential) --------------------------------------------

def test_recovery_from_a_cut_with_live_reservations_matches_the_uninterrupted_run(uninterrupted, tmp_path):
    cut_tick = declared_cut(uninterrupted)
    cut = cut_after(uninterrupted, cut_tick, tmp_path / "cut.jsonl")
    assert read_run(cut).last_sealed_tick == cut_tick and not read_run(cut).complete
    result = recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == cut_tick and result.live_holds_at_cut >= 1
    assert result.resumed == (cut_tick + 1, 119)
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)
    assert read_run(tmp_path / "recovered.jsonl").complete
    assert result.final_seal == read_run(uninterrupted).end["final_seal"]


def test_recovery_from_a_line_cut_in_half(uninterrupted, tmp_path):
    lines = uninterrupted.read_bytes().splitlines(keepends=True)
    index = index_of_tick(lines, 61)
    cut = tmp_path / "half.jsonl"
    cut.write_bytes(b"".join(lines[:index]) + lines[index][: len(lines[index]) // 2])
    result = recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == 60
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)


def test_recovery_from_a_broken_last_seal_resumes_from_the_tick_before_it(uninterrupted, tmp_path):
    cut = cut_after(uninterrupted, 70, tmp_path / "cut.jsonl")
    lines = cut.read_bytes().splitlines(keepends=True)
    last = json.loads(lines[-1])
    last["seal"] = "0" * 64
    lines[-1] = canonical_bytes(last) + b"\n"
    cut.write_bytes(b"".join(lines))
    assert read_run(cut).last_sealed_tick == 69
    result = recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == 69
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)


def test_recovery_never_uses_an_unsealed_line(uninterrupted, tmp_path):
    """An edited line and everything after it are dropped, not carried forward."""
    lines = uninterrupted.read_bytes().splitlines(keepends=True)
    index = index_of_tick(lines, 80)
    edited = json.loads(lines[index])
    actor = sorted(edited["state"]["balances"])[0]
    edited["state"]["balances"][actor] += 5
    lines[index] = canonical_bytes(edited) + b"\n"
    broken = tmp_path / "broken.jsonl"
    broken.write_bytes(b"".join(lines[:-1]))
    assert read_run(broken).last_sealed_tick == 79
    result = recover_scenario(broken, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == 79
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)


def test_recovery_from_the_header_alone_starts_at_genesis(uninterrupted, tmp_path):
    cut = tmp_path / "header.jsonl"
    cut.write_bytes(uninterrupted.read_bytes().splitlines(keepends=True)[0])
    result = recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == -1 and result.resumed == (0, 119)
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)


def test_recovery_of_a_file_cut_only_before_its_end_line(uninterrupted, tmp_path):
    cut = cut_after(uninterrupted, 119, tmp_path / "cut.jsonl")
    result = recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == 119 and result.resumed is None
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted)


def test_recovery_refuses_what_it_cannot_trust(uninterrupted, tmp_path, monkeypatch):
    with pytest.raises(RecoveryError, match="complete"):
        recover_scenario(uninterrupted, tmp_path / "a.jsonl")
    cut = cut_after(uninterrupted, 50, tmp_path / "cut.jsonl")
    lines = cut.read_bytes().splitlines(keepends=True)
    header = json.loads(lines[0])
    header["run_id"] = "renamed"
    bad_header = tmp_path / "bad-header.jsonl"
    bad_header.write_bytes(canonical_bytes(header) + b"\n" + b"".join(lines[1:]))
    with pytest.raises(RecoveryError, match="header"):
        recover_scenario(bad_header, tmp_path / "b.jsonl")
    live = recover_module.code_identity()
    monkeypatch.setattr(recover_module, "code_identity", lambda: {**live, "digest": "0" * 64})
    with pytest.raises(RecoveryError, match="other code"):
        recover_scenario(cut, tmp_path / "c.jsonl")
    monkeypatch.undo()
    world = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=7, width=7, height=7, actors=4), 30, world)
    with pytest.raises(RecoveryError, match="world run"):
        recover_scenario(cut_after(world, 10, tmp_path / "world-cut.jsonl"), tmp_path / "d.jsonl")
    with pytest.raises(RecoveryError, match="not a world run"):
        recover_world(cut, tmp_path / "e.jsonl")
    assert not [name for name in "abcde" if (tmp_path / f"{name}.jsonl").exists()]


def test_recovery_refuses_when_the_generator_does_not_reproduce_the_sealed_inputs(uninterrupted, tmp_path):
    cut = cut_after(uninterrupted, 30, tmp_path / "cut.jsonl")
    lines = cut.read_bytes().splitlines(keepends=True)
    target = next(t["tick"] for t in read_run(cut).ticks if t["tick"] >= 12 and t["inputs"])
    index = index_of_tick(lines, target)
    payload = json.loads(lines[index])
    payload["inputs"][0]["order"] += 7          # the record still settles the same identities
    lines[index] = canonical_bytes(payload) + b"\n"
    cut.write_bytes(b"".join(lines))
    reseal(cut)
    assert read_run(cut).last_sealed_tick == 30, "the resealed prefix verifies; only the generator check can catch it"
    with pytest.raises(RecoveryError, match=f"sealed inputs of tick {target}"):
        recover_scenario(cut, tmp_path / "recovered.jsonl")
    assert not (tmp_path / "recovered.jsonl").exists()


# --- recovery: world runs (optional targets) ---------------------------------------

@pytest.mark.parametrize("production", [True, False])
def test_world_recovery_matches_the_uninterrupted_run(uninterrupted_world, tmp_path, production: bool):
    cut_tick = next(t["tick"] for t in read_run(uninterrupted_world).ticks
                    if t["tick"] >= 30 and ("production" in t) == production)
    cut = cut_after(uninterrupted_world, cut_tick, tmp_path / "cut.jsonl")
    result = recover_world(cut, tmp_path / "recovered.jsonl")
    assert result.last_sealed_tick == cut_tick and result.resumed == (cut_tick + 1, 119)
    assert content(tmp_path / "recovered.jsonl") == content(uninterrupted_world)


# --- isolation --------------------------------------------------------------------

def test_two_engines_restored_from_one_sealed_tick_share_no_mutable_state(uninterrupted):
    tick = declared_cut(uninterrupted)
    a, b = restore_engine(uninterrupted, tick), restore_engine(uninterrupted, tick)
    assert a is not b and a.state is not b.state and a.state.digest() == b.state.digest()
    assert a.state.reservations, "the declared cut holds live reservations"
    for name in ("balances", "sources", "reservations"):
        assert getattr(a.state, name) is not getattr(b.state, name)
    assert all(a.state.sources[s] is not b.state.sources[s] for s in a.state.sources)
    assert all(a.state.reservations[r] is not b.state.reservations[r] for r in a.state.reservations)
    before = b.state.digest()
    following = next(t for t in read_run(uninterrupted).ticks if t["tick"] == tick + 1)
    proposals = [decode_input(entry) for entry in following["inputs"]]

    a.tick(proposals)
    assert a.state.digest() == following["state_digest"]      # a continues the run exactly
    assert b.state.digest() == before                         # b is untouched

    copy = a.state.canonical()
    copy["balances"][sorted(copy["balances"])[0]] += 100
    copy["reservations"].clear()
    copy["sources"][sorted(copy["sources"])[0]]["authorised"].append("intruder")
    assert a.state.digest() == following["state_digest"] and b.state.digest() == before
    with pytest.raises(TypeError):
        a.state.balances["p1"] = 0

    b.tick(proposals)
    assert b.state.digest() == a.state.digest()               # same inputs, same result, independently


def test_restore_refuses_a_tick_the_file_does_not_vouch_for(uninterrupted, tmp_path):
    cut = cut_after(uninterrupted, 20, tmp_path / "cut.jsonl")
    assert restore_engine(cut, 20).state.tick == 21
    with pytest.raises(RecoveryError):
        restore_engine(cut, 21)
    assert digest(restore_engine(cut, 0).state.canonical()) == read_run(cut).ticks[0]["state_digest"]


# --- commands ------------------------------------------------------------------------

def test_the_runner_commands_recover(uninterrupted, uninterrupted_world, tmp_path, capsys):
    cut = cut_after(uninterrupted, 45, tmp_path / "cut.jsonl")
    assert stream_main(["--recover", str(cut), "--out", str(tmp_path / "r.jsonl")]) == 0
    out = capsys.readouterr().out
    assert "last sealed tick: 45" in out and "file_verifies: yes" in out
    assert content(tmp_path / "r.jsonl") == content(uninterrupted)
    assert stream_main(["--recover", str(cut)]) == 2
    assert stream_main(["--recover", str(cut), "--out", str(tmp_path / "r.jsonl")]) == 2   # never overwrites
    world_cut = cut_after(uninterrupted_world, 20, tmp_path / "world-cut.jsonl")
    assert world_main(["--recover", str(world_cut), "--out", str(tmp_path / "wr.jsonl")]) == 0
    assert content(tmp_path / "wr.jsonl") == content(uninterrupted_world)
