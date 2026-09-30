"""Checkpoint bookmarks: fast resume of a live run from its own tick lines.

Every tick line already holds the full `state` and `world`, so a checkpoint is
a *verified bookmark* into the run file, kept in a small sidecar next to it
(`<run>.jsonl.checkpoints.json`): the byte offsets of a tick line plus its seal
and digests. Resume seeks there, checks that one line against the bookmark,
validates the seal chain from it to the end of the file (at most one interval
of ticks), drops a torn trailing line, and continues **in the same file**.

Trust: resume trusts the bookmark for everything before it. `stream_check()`
(`python3 -m world.live --check FILE`) is the full, streaming, bounded-memory
verification of a whole file.

Truncation rule: before appending, exactly one `end` line (verified against the
chain) and/or the torn bytes after the last newline are removed. A sealed tick
line is never removed or modified.

Trail digest: `end.trail_digest` is sha256 over the raw bytes of every tick
line, so it cannot be continued from a bookmark alone. It is rebuilt in a
background thread that streams the file line by line (bounded memory); ticks
written meanwhile are folded in, in order, when it finishes, and `close()`
waits for it before writing the `end` line. Old files stay verifiable as before.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stream.recover import RecoveryError, restored_state
from stream.run_file import (RunWriter, apply_production, canonical_bytes, chained_from, code_identity, digest,
                             tick_seal)
from world.overlay import Overlay

KEEP = 2                 # bookmarks kept, newest first
SPARSE_EVERY = 100       # tick offsets stored in the sidecar for /ticks beyond the ring


def sidecar_path(run: Path) -> Path:
    return run.with_name(run.name + ".checkpoints.json")


def read_sidecar(run: Path) -> dict[str, Any] | None:
    try:
        return json.loads(sidecar_path(run).read_bytes())
    except (OSError, ValueError):
        return None


def bookmark_of(payload: dict[str, Any], line_offset: int, next_offset: int, header: dict[str, Any]) -> dict[str, Any]:
    return {"tick": payload["tick"], "line_offset": line_offset, "next_offset": next_offset, "seal": payload["seal"],
            "record_digest": payload["record_digest"], "state_digest": payload["state_digest"],
            "world_digest": payload.get("world_digest"), "produced_state_digest": payload.get("produced_state_digest"),
            "code_identity_digest": header["code_identity"]["digest"], "config_identity": header["config_identity"],
            "run_id": header["run_id"], "written_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}


def write_sidecar(run: Path, header: dict[str, Any], bookmark: dict[str, Any], sparse: list[list[int]]) -> None:
    """Atomic: temp file beside the sidecar, fsync, then os.replace. Keeps the newest KEEP bookmarks."""
    previous = read_sidecar(run) or {}
    entries = [e for e in previous.get("bookmarks", []) if e.get("run_id") == header["run_id"] and e["tick"] != bookmark["tick"]]
    body = {"run_id": header["run_id"], "bookmarks": ([bookmark] + entries)[:KEEP], "sparse_every": SPARSE_EVERY,
            "offsets": sparse}
    target = sidecar_path(run)
    tmp = target.with_name(target.name + ".tmp")
    with tmp.open("wb") as fh:
        fh.write(json.dumps(body, separators=(",", ":")).encode())
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def read_header(run: Path) -> dict[str, Any]:
    with run.open("rb") as fh:
        header = json.loads(fh.readline())
    if header.get("kind") != "header" or digest(header.get("genesis")) != header.get("genesis_digest"):
        raise RecoveryError(f"{run}: the header does not verify")
    return header


def code_matches(header: dict[str, Any]) -> bool:
    """As today, live resume does not refuse a file written by other code; the
    difference is reported (world.run --recover keeps its strict check)."""
    return (header.get("code_identity") or {}).get("digest") == code_identity()["digest"]


class Resumed:
    """What a bookmark resume yields: the writer positioned to append, the state to
    continue from, the ticks for the ring, and offsets of the ticks it read."""

    def __init__(self, header, writer, last, prior, offsets, sparse, trail_thread, reason):
        self.header, self.writer, self.last, self.prior = header, writer, last, prior
        self.offsets, self.sparse, self.trail_thread, self.reason = offsets, sparse, trail_thread, reason


def _tail_layout(run: Path) -> tuple[int, bytes | None]:
    """(size after dropping torn bytes, the last complete line) from the tail only."""
    size = run.stat().st_size
    with run.open("rb") as fh:
        fh.seek(max(0, size - 4_000_000))
        chunk = fh.read()
    cut = chunk.rfind(b"\n")
    if cut < 0:
        return size, None
    good = size - (len(chunk) - cut - 1)
    body = chunk[:cut]
    prev = body.rfind(b"\n")
    return good, body[prev + 1:] + b"\n"


def resume_from_bookmark(run: Path) -> Resumed:
    """The fast path. Raises RecoveryError with the reason when the slow path is needed."""
    header = read_header(run)
    side = read_sidecar(run)
    if not side or side.get("run_id") != header["run_id"]:
        raise RecoveryError("no checkpoint sidecar for this run")
    size = run.stat().st_size
    usable = [b for b in side.get("bookmarks", []) if b.get("next_offset", size + 1) <= size]
    if not usable:
        raise RecoveryError("every bookmark points beyond the end of the file")
    bm = usable[0]
    with run.open("rb") as fh:
        fh.seek(bm["line_offset"])
        raw = fh.readline()
    try:
        payload = json.loads(raw)
    except ValueError:
        raise RecoveryError("the bookmarked line is not readable")
    if (payload.get("kind") != "tick" or payload.get("tick") != bm["tick"] or payload.get("seal") != bm["seal"]
            or payload.get("state_digest") != bm["state_digest"] or payload.get("record_digest") != bm["record_digest"]
            or digest(payload.get("state")) != bm["state_digest"] or bm["line_offset"] + len(raw) != bm["next_offset"]):
        raise RecoveryError("the bookmarked line does not match its bookmark")
    if bm.get("code_identity_digest") != header["code_identity"]["digest"]:
        raise RecoveryError("the bookmark was written by other code")
    # chain-validate from the bookmark to the end of the file
    good_size, last_line = _tail_layout(run)
    seal, prev_chain, last, count = payload["seal"], chained_from(payload), payload, bm["tick"] + 1
    offsets = {payload["tick"]: bm["line_offset"]}
    prior = [payload]
    truncate_at = good_size if good_size != size else None
    end_line = None
    with run.open("rb") as fh:
        fh.seek(bm["next_offset"])
        pos = bm["next_offset"]
        while pos < good_size:
            line = fh.readline()
            if not line.endswith(b"\n"):
                break
            start, pos = pos, pos + len(line)
            if b'"kind":"tick"' in line:
                t = json.loads(line)
                if t.get("kind") != "tick":
                    continue
                if (canonical_bytes(t) + b"\n" != line or t.get("tick") != count or tick_seal(seal, t) != t.get("seal")
                        or digest(t.get("state")) != t.get("state_digest") or t["record"].get("prior_state_digest") != prev_chain
                        or ("world" in t and digest(t["world"]) != t.get("world_digest"))):
                    raise RecoveryError(f"tick line after the bookmark does not verify (tick {t.get('tick')}); "
                                        "the file was changed after it was written")
                seal, prev_chain, last, count = t["seal"], chained_from(t), t, count + 1
                offsets[t["tick"]] = start
                prior.append(t)
            elif line.startswith(b'{"kind":"end"') or b'"kind":"end"' in line:
                end_line = (start, json.loads(line))
    if end_line is not None:
        start, end = end_line
        if end.get("final_seal") != seal or end.get("ticks") != count - header["genesis"]["tick"]:
            raise RecoveryError("the end line does not match the sealed ticks before it")
        truncate_at = start          # exactly the end line (and any torn bytes after it) go
    # the older bookmark (if any) gives the ring more history, without re-validation: it is before the trust point
    older = [b for b in usable[1:] if b["tick"] < bm["tick"]]
    if older:
        o = older[0]
        with run.open("rb") as fh:
            fh.seek(o["line_offset"])
            pos = o["line_offset"]
            earlier = []
            while pos < bm["line_offset"]:
                line = fh.readline()
                start, pos = pos, pos + len(line)
                if b'"kind":"tick"' in line:
                    t = json.loads(line)
                    if t.get("kind") == "tick":
                        earlier.append(t)
                        offsets[t["tick"]] = start
        prior = earlier + prior
    writer = RunWriter.append_to(run, header=header, seal=seal, next_tick=count, ticks=count - header["genesis"]["tick"],
                                 truncate_at=truncate_at)
    trail_thread = start_trail(writer, run)
    note = "" if code_matches(header) else "; note: the file was written by other code (code identity differs)"
    return Resumed(header, writer, last, prior, offsets, side.get("offsets", []), trail_thread,
                   f"resumed from bookmark at tick {bm['tick']} (validated {count - bm['tick'] - 1} ticks after it){note}")


def start_trail(writer: RunWriter, run: Path) -> threading.Thread:
    """Background: sha256 over every tick line's bytes from the start of the file to
    where the writer began appending, streaming line by line; then the writer takes over."""
    begin = writer._handle.tell()

    def build():
        h = hashlib.sha256()
        with run.open("rb") as fh:
            pos = 0
            while pos < begin:
                line = fh.readline()
                if not line:
                    break
                pos += len(line)
                if b'"kind":"tick"' in line and json.loads(line).get("kind") == "tick":
                    h.update(line)
        writer.adopt_trail(h)
    thread = threading.Thread(target=build, name="trail", daemon=True)
    thread.start()
    return thread


def restore(resumed: Resumed):
    """Engine state and overlay from the last validated tick line."""
    from kernel import Engine
    last = resumed.last
    engine = Engine(restored_state(resumed.header, last))
    overlay = Overlay.from_canonical(last["world"] if last else resumed.header["world"])
    return engine, overlay


# ------------------------------------------------------------ full check --
def stream_check(path: Path) -> list[str]:
    """Verify a whole run file line by line with bounded memory: header, canonical
    bytes, digests, seal chain, tick numbering, prior-state chaining, trail and end."""
    problems: list[str] = []
    header = None
    seal = None
    expected = None
    prev_chain = None
    trail = hashlib.sha256()
    ticks = 0
    end = None
    with path.open("rb") as fh:
        for number, raw in enumerate(fh, start=1):
            if not raw.endswith(b"\n"):
                problems.append(f"line {number}: incomplete (no newline)")
                break
            try:
                payload = json.loads(raw)
            except ValueError:
                problems.append(f"line {number}: not JSON")
                continue
            kind = payload.get("kind")
            if end is not None:
                problems.append(f"line {number}: event after end")
            if kind == "header":
                if header is not None:
                    problems.append(f"line {number}: second header"); continue
                header = payload
                if digest(header.get("genesis")) != header.get("genesis_digest"):
                    problems.append(f"line {number}: genesis digest does not match content")
                if "world" in header and digest(header["world"]) != header.get("world_digest"):
                    problems.append(f"line {number}: world genesis digest does not match content")
                seal, expected, prev_chain = header.get("seal"), int(header["genesis"]["tick"]), header.get("genesis_digest")
            elif kind == "tick":
                if header is None:
                    problems.append(f"line {number}: tick before header"); continue
                if canonical_bytes(payload) + b"\n" != raw:
                    problems.append(f"line {number}: tick line is not canonical bytes")
                if digest(payload.get("record")) != payload.get("record_digest"):
                    problems.append(f"line {number}: record digest does not match content")
                if digest(payload.get("state")) != payload.get("state_digest"):
                    problems.append(f"line {number}: state digest does not match content")
                if "world" in payload and digest(payload["world"]) != payload.get("world_digest"):
                    problems.append(f"line {number}: world digest does not match content")
                if "production" in payload and digest(apply_production(payload["state"], payload["production"])) != payload.get("produced_state_digest"):
                    problems.append(f"line {number}: produced state digest does not verify")
                if payload.get("tick") != expected:
                    problems.append(f"line {number}: expected tick {expected}, found {payload.get('tick')}")
                if (payload.get("record") or {}).get("prior_state_digest") != prev_chain:
                    problems.append(f"line {number}: prior state digest does not chain")
                if tick_seal(seal, payload) != payload.get("seal"):
                    problems.append(f"line {number}: seal does not verify")
                seal, prev_chain, expected = payload.get("seal"), chained_from(payload), payload.get("tick") + 1
                trail.update(raw); ticks += 1
            elif kind == "end":
                end = payload
                if payload.get("ticks") != ticks:
                    problems.append(f"line {number}: end declares {payload.get('ticks')} ticks, file has {ticks}")
                if payload.get("trail_digest") != trail.hexdigest():
                    problems.append(f"line {number}: trail digest does not match the tick lines")
                if payload.get("final_seal") != seal:
                    problems.append(f"line {number}: final seal is not the last tick's seal")
            elif kind != "timing":
                problems.append(f"line {number}: unknown event kind {kind!r}")
    if header is None:
        problems.append("no header")
    if end is None:
        problems.append("no end record (run did not finish, or the file was cut)")
    return problems
