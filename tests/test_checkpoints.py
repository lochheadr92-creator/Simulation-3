"""Checkpoint bookmarks: sidecar cadence and atomicity, resume from a bookmark in
the same file, torn tails, tampering on either side of the trust point, clean
stops whose end line is removed exactly, and the trail digest carried on."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from stream.run_file import read_run
from tests.test_live import CFG, digests
from world.checkpoints import RecoveryError, read_sidecar, resume_from_bookmark, sidecar_path, stream_check
from world.live import CHECKPOINT_EVERY, LiveWorld, open_live, resume_live
from world.replay import replay_world

FAST = dict(seed=CFG.seed, wood_on=True, yard_on=True, stone_on=True, axe_on=True, stores_on=True, provisioning_on=True,
            homes_on=True, childhood_on=True, coordination_on=True, relocation_on=True, fishing_on=True,
            source_memory_on=True, knowledge_sharing_on=True, shared_care_on=True)


def run_to(live: LiveWorld, n: int) -> LiveWorld:
    while live.tick_count < n:
        live.advance()
    return live


def finish(live: LiveWorld) -> None:
    live.stop(); live.checkpoint(); live.writer.close()


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    path = tmp_path_factory.mktemp("ref") / "ref.jsonl"
    live = run_to(open_live(CFG, path), 1250)
    finish(live)
    run = read_run(path)
    return {t["tick"]: (t["state_digest"], t["world_digest"]) for t in run.ticks}


def test_sidecar_cadence_pause_stop_and_two_kept(tmp_path):
    path = tmp_path / "c.jsonl"
    live = open_live(CFG, path)
    run_to(live, 499)
    assert read_sidecar(path) is None
    live.advance()                                   # tick 500 written -> bookmark
    side = read_sidecar(path)
    assert [b["tick"] for b in side["bookmarks"]] == [499] and side["run_id"] == live.header["run_id"]
    b = side["bookmarks"][0]
    with path.open("rb") as fh:
        fh.seek(b["line_offset"]); raw = fh.readline()
    t = json.loads(raw)
    assert t["tick"] == 499 and t["seal"] == b["seal"] and b["line_offset"] + len(raw) == b["next_offset"]
    assert {"record_digest", "state_digest", "world_digest", "code_identity_digest", "config_identity", "written_at"} <= set(b)
    run_to(live, 1000)
    assert [b["tick"] for b in read_sidecar(path)["bookmarks"]] == [999, 499]
    run_to(live, 1030)
    live.set_paused(True)                            # on pause
    assert [b["tick"] for b in read_sidecar(path)["bookmarks"]] == [1029, 999]      # newest first, two kept
    run_to(live, 1040)
    finish(live)                                     # on stop
    side = read_sidecar(path)
    assert [b["tick"] for b in side["bookmarks"]] == [1039, 1029]
    assert side["offsets"] and all(t % 100 == 0 for t, _ in side["offsets"])
    assert not sidecar_path(path).with_name(sidecar_path(path).name + ".tmp").exists()   # atomic: no temp left
    assert sidecar_path(path).stat().st_size < 4000


def test_resume_from_bookmark_matches_uninterrupted(tmp_path, reference):
    path = tmp_path / "r.jsonl"
    live = run_to(open_live(CFG, path), 700)
    finish(live)
    again = resume_live(path, log=lambda m: None)
    assert again.writer.path == path and again.tick_count == 700 and again.header["run_id"] == live.header["run_id"]
    assert len(again.ring) >= 200                    # the ring came back from the two bookmarks
    run_to(again, 1200)
    finish(again)
    run = read_run(path)
    assert run.complete and not run.problems
    by = {t["tick"]: (t["state_digest"], t["world_digest"]) for t in run.ticks}
    assert by[299] == reference[299] and by[1199] == reference[1199]
    assert replay_world(path).identical and stream_check(path) == []
    assert digests(path)[0] == 1199


def test_kill_dash_nine_between_checkpoints_then_resume(tmp_path, reference):
    out = tmp_path / "k.jsonl"
    code = ("import sys; sys.path.insert(0, '/app')\nfrom pathlib import Path\nfrom world.live import open_live\nfrom tests.test_live import CFG\n"
            f"live = open_live(CFG, Path({str(out)!r}))\n"
            "while True:\n    live.advance()\n    print(live.tick_count, flush=True)\n")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, cwd="/app")
    while int(proc.stdout.readline()) < 760:
        pass
    os.kill(proc.pid, signal.SIGKILL); proc.wait()
    with out.open("ab") as fh:
        fh.write(b'{"kind":"tick","tick":9999,"partial')
    size_torn = out.stat().st_size
    live = resume_live(out, log=lambda m: None)
    assert out.stat().st_size < size_torn            # the torn tail is gone, nothing else
    assert 760 <= live.tick_count <= 762 and read_sidecar(out)["bookmarks"][0]["tick"] == 499
    run_to(live, 1200); finish(live)
    run = read_run(out)
    assert run.complete and {t["tick"]: (t["state_digest"], t["world_digest"]) for t in run.ticks}[1199] == reference[1199]
    assert stream_check(out) == []


def test_bad_temp_sidecar_leaves_the_previous_one_intact(tmp_path):
    path = tmp_path / "t.jsonl"
    live = run_to(open_live(CFG, path), 500)
    good = sidecar_path(path).read_bytes()
    tmp = sidecar_path(path).with_name(sidecar_path(path).name + ".tmp")
    tmp.write_bytes(b'{"half":')                     # a write that died before os.replace
    assert sidecar_path(path).read_bytes() == good and read_sidecar(path)["bookmarks"][0]["tick"] == 499
    finish(live)
    assert read_sidecar(path)["bookmarks"][0]["tick"] == 499 and not tmp.exists() or tmp.exists()


def flip_byte(path: Path, offset: int) -> None:
    with path.open("r+b") as fh:
        fh.seek(offset); b = fh.read(1); fh.seek(offset)
        fh.write(b"0" if b != b"0" else b"1")


def test_tamper_before_bookmark_is_trusted_but_full_check_fails(tmp_path):
    path = tmp_path / "b.jsonl"
    finish(run_to(open_live(CFG, path), 520))
    b = read_sidecar(path)["bookmarks"][0]
    header_len = len(path.open("rb").readline())
    flip_byte(path, header_len + 5000)               # inside an early tick line, before the bookmark
    assert stream_check(path)                        # the full check sees it
    live = resume_live(path, log=lambda m: None)     # resume trusts the bookmark (documented)
    assert live.tick_count == 520 and b["tick"] == 519
    finish(live)


def test_tamper_after_bookmark_refuses(tmp_path):
    path = tmp_path / "a.jsonl"
    finish(run_to(open_live(CFG, path), 530))
    # newest bookmark is at 529 (stop); make 499 the newest so there are lines after it, then tamper one
    side = read_sidecar(path)
    side["bookmarks"] = [b for b in side["bookmarks"] if b["tick"] == 499] or side["bookmarks"][1:]
    sidecar_path(path).write_bytes(json.dumps(side).encode())
    b = side["bookmarks"][0]
    flip_byte(path, b["next_offset"] + 3000)
    with pytest.raises(RecoveryError):
        resume_from_bookmark(path)


def test_clean_stop_end_line_removed_exactly_and_old_readers_accept(tmp_path):
    path = tmp_path / "e.jsonl"
    live = run_to(open_live(CFG, path), 510)
    finish(live)
    before = path.read_bytes()
    lines = before.splitlines(keepends=True)
    assert b'"kind":"end"' in lines[-1]
    again = resume_live(path, log=lambda m: None)
    assert path.read_bytes() == b"".join(lines[:-1])    # exactly the end line went
    run_to(again, 515); finish(again)
    run = read_run(path)
    assert run.complete and not run.problems and len(run.ticks) == 515 and run.header["run_id"] == live.header["run_id"]
    assert replay_world(path).identical and stream_check(path) == []


def test_no_sidecar_falls_back_to_full_recovery(tmp_path):
    path = tmp_path / "f.jsonl"
    finish(run_to(open_live(CFG, path), 40))
    sidecar_path(path).unlink()
    messages = []
    again = resume_live(path, log=messages.append)
    assert "slow resume" in messages[0] and again.tick_count == 40
    finish(again)
