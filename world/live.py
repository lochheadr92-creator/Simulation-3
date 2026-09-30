"""A world that advances while you watch.

One simulation thread owns the world and is its only writer: it waits for
permission (paused flag, step tokens, speed interval), runs `world_step`,
appends the tick through the existing `RunWriter`, and publishes an immutable
payload to browser subscribers over Server-Sent Events. HTTP threads only read
snapshots and set control flags. Wall-clock time never enters the tick path.

Persistence: every tick line is written and `flush()`ed to the OS as it is
recorded (RunWriter does that); the file is `fsync`ed on pause, on stop and
every FSYNC_SECONDS. A tick shown in the browser is therefore at least in the
OS buffer; after a power loss up to FSYNC_SECONDS of ticks may be lost, and
`--resume` recovers the sealed prefix and continues in a new file.

The header horizon is LIVE_HORIZON (a large integer, so old readers, replay
and recovery see an ordinary cut run); a stopped live file has no end line,
exactly like a recovered file cut mid-run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import secrets
import sys
import threading
import time
import webbrowser
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kernel import Engine
from stream.recover import SealedPrefix, resume_writer, sealed_prefix
from stream.recover import restored_state
from stream.run_file import Run, RunWriter
from world.config import WorldConfig, genesis
from world.overlay import Overlay
from world.run import DEFAULT_RUNS_DIR, build_parser as run_parser, config_from, random_seed, run_id_for, world_step
from world.checkpoints import (SPARSE_EVERY, RecoveryError, bookmark_of, read_sidecar, restore, resume_from_bookmark,
                               stream_check, write_sidecar)
from world.viewer import render_html
from world.viewer_index import build_index

LIVE_HORIZON = 1_000_000
RING = 600            # ticks kept in memory for new tabs: enough for 10 minutes at 1 tick/s, ~2 MB of JSON
FSYNC_SECONDS = 5.0
CHECKPOINT_EVERY = 500  # ticks between bookmarks (also on pause and on stop)
SPEEDS = (0.1, 0.25, 0.5, 1, 2, 5, 10, 0)   # 0 = unthrottled
QUEUE = 64            # per-subscriber queue; a slow client is skipped, never waited for


class LiveWorld:
    """The single owner of a live world. Drive it with `run_forever()` in a
    thread, or with `advance()` in tests."""

    def __init__(self, config: WorldConfig, engine: Engine, overlay: Overlay, writer: RunWriter,
                 header: dict[str, Any], prior: list[dict[str, Any]], tick_count: int | None = None):
        self.config, self.engine, self.overlay, self.writer, self.header = config, engine, overlay, writer, header
        self.paused = True
        self.speed = 1.0
        self.steps = 0
        self.stopping = False
        self.lock = threading.Lock()
        self.wake = threading.Condition(self.lock)
        self.subscribers: list[queue.Queue] = []
        self.ring: deque[dict[str, Any]] = deque(prior[-RING:], maxlen=RING)
        self.base_before = prior[-RING - 1] if len(prior) > RING else None
        self.tick_count = len(prior) if tick_count is None else tick_count   # `prior` may be only the tail of a long run
        self.last_tick = 0.0          # monotonic time of the last tick; only schedules the next one, never enters the tick
        self.last_fsync = time.monotonic()
        self.stopped = threading.Event()

    # ------------------------------------------------------------ control --
    def set_paused(self, paused: bool) -> None:
        with self.wake:
            self.paused = paused
            self.wake.notify_all()
        if paused:
            self.checkpoint()
        self.broadcast({"kind": "control", **self.status()})

    def step(self) -> None:
        with self.wake:
            if self.paused:                 # a step is one tick of a paused world; while running it means nothing
                self.steps += 1
            self.wake.notify_all()

    def interval(self) -> float | None:
        """Seconds between ticks at the current speed; None when unthrottled."""
        return None if self.speed == 0 else 1.0 / self.speed

    def set_speed(self, speed: float) -> None:
        if speed not in SPEEDS:
            raise ValueError(f"speed must be one of {SPEEDS}")
        with self.wake:
            self.speed = float(speed)
            self.wake.notify_all()
        self.broadcast({"kind": "control", **self.status()})

    def stop(self) -> None:
        with self.wake:
            self.stopping = True
            self.paused = True
            self.wake.notify_all()

    def status(self) -> dict[str, Any]:
        return {"tick": self.tick_count, "paused": self.paused, "speed": self.speed, "path": str(self.writer.path),
                "run_id": self.header["run_id"], "seed": self.header["scenario"]["seed"], "ring": RING, "stopping": self.stopping}

    def fsync(self) -> None:
        handle = getattr(self.writer, "_handle", None)
        if handle is not None and not handle.closed:
            handle.flush()
            os.fsync(handle.fileno())
        self.last_fsync = time.monotonic()

    # ------------------------------------------------------------ the tick --
    def advance(self) -> dict[str, Any]:
        """One simulation tick: step, write, publish. Only the owner thread calls this."""
        started = time.perf_counter_ns()
        step = world_step(self.engine, self.overlay, self.config)
        cost = time.perf_counter_ns() - started
        self.writer.record(step.record, step.committed, inputs=step.proposals, elapsed_ns=cost, **step.line_fields())
        self.overlay, self.engine = step.processed.overlay, step.engine
        payload = json.loads(self.writer.last_line) if hasattr(self.writer, "last_line") else None
        if payload is None:
            payload = json.loads(Path(self.writer.path).read_bytes().splitlines()[-2])
        self.tick_count += 1
        message = {"kind": "tick", "tick": payload, "index": self.index_delta(payload), "control": self.status()}
        with self.lock:
            if len(self.ring) == self.ring.maxlen:
                self.base_before = self.ring[0]
            self.ring.append(payload)
        if time.monotonic() - self.last_fsync >= FSYNC_SECONDS:
            self.fsync()
        if self.tick_count % CHECKPOINT_EVERY == 0:
            self.checkpoint()
        self.broadcast(message)
        return payload

    def checkpoint(self) -> None:
        """A bookmark to the last tick line, after it is on disk."""
        w = self.writer
        if getattr(w, "last_offset", None) is None or getattr(w, "_closed", False):
            return
        self.fsync()
        payload = json.loads(w.last_line)
        write_sidecar(Path(w.path), self.header, bookmark_of(payload, w.last_offset, w.last_next, self.header), w.index.sparse_list())

    def index_delta(self, payload: dict[str, Any]) -> dict[str, Any]:
        """The view index for the new tick alone, computed like build_index over
        the previous tick and this one, with event view indices rebased."""
        from world.viewer import _tick_details
        previous = self.ring[-1] if self.ring else None
        ticks = tuple(t for t in (previous, payload) if t is not None)
        run = self._run(ticks, before=self.base_before if previous is None else (self.ring[-2] if len(self.ring) > 1 else self.base_before))
        index = build_index(run)
        local = len(ticks)
        events = [dict(e, k=self.tick_count) for e in index["events"] if e["k"] == local]
        counts = {k: v[local] for k, v in (index.get("counts") or {}).items() if isinstance(v, list) and len(v) > local}
        return {"events": events, "wood": index.get("wood", []), "stone": index.get("stone", []),
                "details": _tick_details(run, local), "counts": counts}

    def _run(self, ticks: tuple[dict[str, Any], ...], before: dict[str, Any] | None) -> Run:
        header = dict(self.header)
        if before is not None:
            header["genesis"] = restored_state(self.header, before).canonical()
            header["world"] = before["world"]
        return Run(path=self.writer.path, header=header, ticks=ticks, timings={}, end=None, trail_digest="", problems=(),
                   last_sealed_tick=ticks[-1]["tick"] if ticks else None)

    def page_run(self) -> tuple[Run, int]:
        """A Run for the viewer covering the in-memory ring, and the tick its view 0 shows."""
        with self.lock:
            ticks = tuple(self.ring)
            before = self.base_before
        base = self.tick_count - len(ticks)
        return self._run(ticks, before), base

    def run_forever(self) -> None:
        """The owner loop. Ticks are due at `last_tick + interval`; a control change
        re-evaluates the schedule but never brings a tick forward, so a burst of
        control requests cannot speed the world up. A step is exactly one tick of a
        paused world."""
        try:
            while True:
                with self.wake:
                    while True:
                        if self.stopping:
                            return
                        if self.paused:
                            if self.steps > 0:
                                self.steps -= 1
                                self.last_tick = time.monotonic()
                                break
                            self.wake.wait()
                            continue
                        gap = self.interval()
                        now = time.monotonic()
                        if gap is None:
                            self.last_tick = now
                            break
                        wait = self.last_tick + gap - now
                        if wait <= 0:
                            # the next tick is due `gap` after this one was *scheduled*, so the
                            # tick's own cost does not slow the rate; after a long pause, restart from now
                            self.last_tick = max(self.last_tick + gap, now - gap)
                            break
                        self.wake.wait(timeout=wait)
                self.advance()
        finally:
            self.checkpoint()
            try:
                self.writer.close()      # the end line: an open-ended run may close at any tick
            except Exception:
                pass
            self.stopped.set()
            self.broadcast({"kind": "control", **self.status()})

    # -------------------------------------------------------- subscribers --
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=QUEUE)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def broadcast(self, message: dict[str, Any]) -> None:
        with self.lock:
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(message)
            except queue.Full:
                self.unsubscribe(q)   # a slow tab is dropped; it reconnects and catches up from /ticks


class TickIndex:
    """Byte offsets of tick lines: exact for every tick seen (written or read at
    resume), sparse (every SPARSE_EVERY ticks, from the sidecar) for the rest.
    A tick between sparse entries is found by a short linear scan from the
    nearest entry below it: no full-file scan on any request path."""

    def __init__(self, exact: dict[int, int] | None = None, sparse: list[list[int]] | None = None):
        self.exact = dict(exact or {})
        self.sparse = sorted((int(t), int(o)) for t, o in (sparse or []))

    def add(self, tick: int, offset: int) -> None:
        self.exact[tick] = offset
        if tick % SPARSE_EVERY == 0 and (not self.sparse or self.sparse[-1][0] < tick):
            self.sparse.append((tick, offset))

    def sparse_list(self) -> list[list[int]]:
        return [[t, o] for t, o in self.sparse]

    def locate(self, fh, k: int) -> int | None:
        """Offset of tick line k, scanning forward from the nearest known offset below it."""
        if k in self.exact:
            return self.exact[k]
        below = [(t, o) for t, o in self.sparse if t <= k] + [(t, o) for t, o in self.exact.items() if t <= k]
        if not below:
            return None
        pos = max(below)[1]
        fh.seek(pos)
        while True:
            line = fh.readline()
            if not line:
                return None
            if b'"kind":"tick"' in line:
                t = json.loads(line)
                if t.get("kind") == "tick":
                    self.exact[t["tick"]] = pos
                    if t["tick"] == k:
                        return pos
            pos += len(line)

    def read(self, path: Path, start: int, end: int) -> list[dict[str, Any]]:
        out = []
        with path.open("rb") as fh:
            for k in range(max(start, 0), end):
                pos = self.locate(fh, k)
                if pos is None:
                    break
                fh.seek(pos)
                t = json.loads(fh.readline())
                if t.get("tick") != k:
                    break
                out.append(t)
        return out


def _patched_writer(writer: RunWriter, index: TickIndex | None = None) -> RunWriter:
    """Remember the last tick line written (payload published byte-for-byte) and the
    byte offsets of tick lines for `/ticks` and for bookmarks."""
    original = writer._write
    writer.index = index if index is not None else TickIndex(_tick_offsets(Path(writer.path)))
    writer.last_offset = writer.last_next = None

    def _write(payload):
        if payload.get("kind") == "tick":
            start = writer._handle.tell()
        raw = original(payload)
        if payload.get("kind") == "tick":
            writer.last_line, writer.last_offset, writer.last_next = raw, start, start + len(raw)
            writer.index.add(payload["tick"], start)
        return raw
    writer._write = _write
    return writer


def _tick_offsets(path: Path) -> dict[int, int]:
    """Exact offsets of the tick lines already in a fresh or copied file (small files only)."""
    offsets, pos = {}, 0
    if path.exists():
        with path.open("rb") as fh:
            for line in fh:
                if b'"kind":"tick"' in line:
                    t = json.loads(line)
                    if t.get("kind") == "tick":
                        offsets[t["tick"]] = pos
                pos += len(line)
    return offsets


def read_ticks(path: Path, index: TickIndex, start: int, end: int) -> list[dict[str, Any]]:
    return index.read(path, start, end)


def run_identity(config: WorldConfig) -> tuple[str, str]:
    """A run id of its own for every live world (the deterministic scenario id plus
    a UTC stamp and a short token) and the file name that goes with it."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = secrets.token_hex(4)
    return f"{run_id_for(config, LIVE_HORIZON)}-live-{stamp}-{short}", f"{stamp}-seed{config.seed}-{short}.jsonl"


def open_live(config: WorldConfig, path: Path | None = None, outdir: Path | None = None) -> LiveWorld:
    ledger, overlay = genesis(config)
    run_id, name = run_identity(config)
    if path is None:
        path = (outdir or DEFAULT_RUNS_DIR / "live") / name
    writer = RunWriter(path, run_id=run_id, genesis=ledger,
                       scenario=config.describe(), world=overlay.canonical(), horizon=LIVE_HORIZON, open_ended=True)
    return LiveWorld(config, Engine(ledger), overlay, _patched_writer(writer), writer.header, [])


def _prefix(source: Path) -> SealedPrefix:
    """A cut or broken live file recovers through the ordinary sealed prefix; a
    cleanly stopped one is complete, so its prefix is everything before the end line."""
    from stream.run_file import read_run
    run = read_run(source)
    if not (run.complete and run.header.get("open_ended")):
        return sealed_prefix(source)
    raw = source.read_bytes()
    lines = raw.splitlines(keepends=True)
    tick_lines = tuple(line for line in lines if b'"kind":"tick"' in line)
    last = lines.index(tick_lines[-1]) if tick_lines else 0
    return SealedPrefix(source=source, source_sha256=hashlib.sha256(raw).hexdigest(), header=run.header,
                        ticks=run.ticks, tick_lines=tick_lines, prefix=b"".join(lines[:last + 1]))



def resume_live(source: Path, out: Path | None = None, log=print) -> LiveWorld:
    """Continue a saved live world in its own file. Fast path: the checkpoint
    bookmark. Fallback: the full sealed-prefix recovery (reads the whole file)
    when there is no usable bookmark; `out` (a new file) is honoured only there."""
    try:
        r = resume_from_bookmark(source)
    except RecoveryError as exc:
        log(f"slow resume of {source}: {exc}; reading and verifying the whole file")
        return _resume_full(source, out)
    log(r.reason)
    engine, overlay = restore(r)
    config = WorldConfig.from_describe(r.header["scenario"])
    writer = _patched_writer(r.writer, TickIndex(r.offsets, r.sparse))
    return LiveWorld(config, engine, overlay, writer, r.header, r.prior, tick_count=r.last["tick"] + 1 - r.header["genesis"]["tick"])


def _resume_full(source: Path, out: Path | None) -> LiveWorld:
    """The slow path: read and verify the whole file. Continues in the same file
    (the sealed prefix is kept byte for byte; an end line or torn tail after it is
    dropped) unless `out` names a new file."""
    prefix = _prefix(source)
    config = WorldConfig.from_describe(prefix.header["scenario"])
    last = prefix.ticks[-1] if prefix.ticks else None
    engine = Engine(restored_state(prefix.header, last))
    overlay = Overlay.from_canonical(last["world"] if last else prefix.header["world"])
    if out is None:
        writer = RunWriter.append_to(source, header=prefix.header, seal=prefix.seal, next_tick=prefix.next_tick,
                                     ticks=len(prefix.ticks), truncate_at=len(prefix.prefix))
        trail = hashlib.sha256()
        for line in prefix.tick_lines:
            trail.update(line)
        writer.adopt_trail(trail)
        offsets, pos = {}, 0
        for line in prefix.prefix.splitlines(keepends=True):
            if b'"kind":"tick"' in line:
                t = json.loads(line)
                if t.get("kind") == "tick":
                    offsets[t["tick"]] = pos
            pos += len(line)
        writer = _patched_writer(writer, TickIndex(offsets))
    else:
        writer = _patched_writer(resume_writer(out, prefix))
    return LiveWorld(config, engine, overlay, writer, prefix.header, list(prefix.ticks))


def _tail_tick(path: Path) -> int | None:
    """The last tick number in a run file, read from its tail only."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, size - 1_000_000))
        lines = fh.read().splitlines()
    for line in reversed(lines):
        if b'"kind":"tick"' in line:
            try:
                return json.loads(line)["tick"]
            except ValueError:
                continue
    return None


def list_worlds(outdir: Path, current: Path | None, stopped: bool = False) -> list[dict[str, Any]]:
    """Every live run file in the directory, cheaply: header line and tail only."""
    out = []
    for path in sorted(outdir.glob("*.jsonl")):
        try:
            with path.open("rb") as fh:
                header = json.loads(fh.readline())
        except (OSError, ValueError):
            continue
        if header.get("kind") != "header" or not header.get("open_ended"):
            continue
        last = _tail_tick(path)
        side = read_sidecar(path)
        out.append({"file": path.name, "run_id": header["run_id"], "seed": header["scenario"]["seed"],
                    "last_tick": last, "ticks": (last + 1) if last is not None else 0,
                    "bookmark": side["bookmarks"][0]["tick"] if side and side.get("bookmarks") else None,
                    "size_mb": round(path.stat().st_size / 1e6, 1), "current": path == current and not stopped})
    return out


class Session:
    """One live world at a time. New / replay / resume stop the running world
    through the ordinary stop path first (pause, fsync, end line, writer closed),
    wait for its owner thread to end, and only then start the next one."""

    def __init__(self, live: LiveWorld, outdir: Path):
        self.live, self.outdir = live, outdir
        self.thread: threading.Thread | None = None
        self.gate = threading.Lock()
        self.switching = False        # true while one world is being stopped and the next created
        self.history: list[dict[str, Any]] = []

    def start(self) -> None:
        assert self.thread is None or not self.thread.is_alive(), "a world is still running"
        self.thread = threading.Thread(target=self.live.run_forever, name="world", daemon=True)
        self.thread.start()
        self.note("start")

    def note(self, event: str) -> None:
        self.history.append({"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event,
                             "run_id": self.live.header["run_id"], "seed": self.live.header["scenario"]["seed"],
                             "file": str(self.live.writer.path), "tick": self.live.tick_count})

    def status(self) -> dict[str, Any]:
        return {**self.live.status(), "outdir": str(self.outdir), "history": self.history[-20:]}

    def _stop_current(self) -> None:
        self.live.stop()
        if self.thread is not None:
            self.thread.join(30)
            assert not self.thread.is_alive(), "the old world did not stop"
            self.live.stopped.wait(5)
        else:                       # never started: close the file through the same end-line path
            self.live.checkpoint()
            self.live.writer.close()
        self.note("stop")

    def switch(self, make) -> dict[str, Any]:
        """Stop, then create with `make()`, then start. Serialised; never two owners."""
        with self.gate:
            self.switching = True
            try:
                self._stop_current()
                self.live = make()
                self.start()
                return self.status()
            finally:
                self.switching = False

    def new_world(self, seed: int | None) -> dict[str, Any]:
        # every lever of the running world, only the seed replaced; nothing else is ever randomised
        config = replace(self.live.config, seed=random_seed() if seed is None else int(seed))
        return self.switch(lambda: open_live(config, outdir=self.outdir))

    def replay(self) -> dict[str, Any]:
        return self.new_world(self.live.header["scenario"]["seed"])

    def resume(self, name: str) -> dict[str, Any]:
        source = self.outdir / Path(name).name
        if not source.exists() or (source == Path(self.live.writer.path) and not self.live.stopping):
            raise ValueError(f"no saved world {name!r} to resume")
        return self.switch(lambda: resume_live(source))


# ------------------------------------------------------------------ HTTP --
def make_handler(session):
    """`session` is a Session, or a bare LiveWorld for tests of a single world."""
    if isinstance(session, LiveWorld):
        session = Session(session, Path(session.writer.path).parent)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):   # quiet
            pass

        def _json(self, code: int, body: Any) -> None:
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            live = session.live
            path, _, query = self.path.partition("?")
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if path == "/":
                run, base = live.page_run()
                page = render_html(run, live={"base": base, **live.status(), "outdir": str(session.outdir)})
                raw = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            elif path == "/status":
                self._json(200, {**session.status(), "scenario": live.header["scenario"]})
            elif path == "/worlds":
                self._json(200, {"outdir": str(session.outdir), "worlds": list_worlds(session.outdir, Path(live.writer.path), live.stopping)})
            elif path == "/ticks":
                start, end = int(params.get("from", 0)), int(params.get("to", live.tick_count))
                with live.lock:
                    ring = list(live.ring)
                first = live.tick_count - len(ring)
                out = [t for t in ring if start <= t["tick"] < end]
                if start < first:      # older ticks come from the run file on disk, by offset
                    out = read_ticks(Path(live.writer.path), live.writer.index, start, min(end, first)) + out
                self._json(200, {"run_id": live.header["run_id"], "ticks": out})
            elif path == "/events":
                since = int(params.get("since", live.tick_count))
                light = params.get("light") == "1"      # tick numbers only: the tab fetches what it will show
                q = live.subscribe()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                run_id = live.header["run_id"]
                try:
                    self._send({"kind": "control", **live.status()})
                    sent = since
                    if not light:
                        with live.lock:
                            missed = [t for t in live.ring if t["tick"] >= since]
                        for t in missed:
                            self._send({"kind": "tick", "run_id": run_id, "tick": t, "index": None, "control": live.status()})
                            sent = t["tick"] + 1
                    while True:
                        try:
                            msg = q.get(timeout=15)
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n"); self.wfile.flush()
                            continue
                        if msg.get("kind") == "tick":
                            if msg["tick"]["tick"] < sent:
                                continue          # already sent from the ring while catching up
                            sent = msg["tick"]["tick"] + 1
                            if light:
                                msg = {"kind": "tickn", "n": sent, "control": msg["control"]}
                        self._send({"run_id": run_id, **msg})
                        if msg.get("stopping") or (msg.get("control") or {}).get("stopping"):
                            break
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    live.unsubscribe(q)
            else:
                self._json(404, {"error": "not found"})

        def _send(self, msg: dict[str, Any]) -> None:
            self.wfile.write(b"data: " + json.dumps(msg).encode() + b"\n\n")
            self.wfile.flush()

        def do_POST(self):
            if self.path != "/control":
                return self._json(404, {"error": "not found"})
            live = session.live
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            action = body.get("action")
            try:
                if action == "pause":
                    live.set_paused(True)
                elif action == "resume":
                    live.set_paused(False)
                elif action == "step":
                    live.step()
                elif action == "speed":
                    live.set_speed(float(body.get("speed", 1)))
                elif action == "stop":
                    live.stop()
                elif action == "new":
                    seed = body.get("seed")
                    if seed is not None and (type(seed) is not int or seed < 0):
                        return self._json(400, {"error": "seed must be a non-negative integer"})
                    return self._json(200, session.new_world(seed))
                elif action == "replay":
                    return self._json(200, session.replay())
                elif action == "resume_saved":
                    return self._json(200, session.resume(str(body.get("file", ""))))
                else:
                    return self._json(400, {"error": f"unknown action {action!r}"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            self._json(200, session.status())
    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = run_parser()
    parser.description = "Run a world live in the browser: it advances while you watch."
    parser.add_argument("--resume", dest="resume_live", default=None, metavar="FILE",
                        help="continue a live world from its saved run (a new file is written next to it)")
    parser.add_argument("--out-dir", default=None, metavar="DIR",
                        help="directory for live run files (default runs/live); ignored when --out FILE is given")
    parser.add_argument("--check", default=None, metavar="FILE",
                        help="verify a whole run file line by line (bounded memory) and exit; resume trusts bookmarks, this is the full check")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    parser.add_argument("--host", default="127.0.0.1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        problems = stream_check(Path(args.check))
        for problem in problems:
            print(f"problem: {problem}")
        print(f"file_verifies: {'yes' if not problems else 'no'}")
        return 0 if not problems else 1
    if args.resume_live:
        live = resume_live(Path(args.resume_live))
    else:
        if args.seed is None:
            print("live worlds need --seed N or --seed random", file=sys.stderr)
            return 2
        if args.seed == "random":
            args.seed = random_seed()
            print(f"seed: {args.seed} (random, drawn once at launch)", flush=True)
        outdir = Path(args.out).parent if args.out else Path(args.out_dir) if args.out_dir else DEFAULT_RUNS_DIR / "live"
        live = open_live(config_from(args), Path(args.out) if args.out else None, outdir=outdir)
    session = Session(live, Path(live.writer.path).parent)
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(session))
    except OSError as exc:
        print(f"port {args.port} is not available ({exc}); choose another with --port", file=sys.stderr)
        live.writer._handle.close()
        if not args.resume_live:
            Path(live.writer.path).unlink(missing_ok=True)   # nothing was recorded; leave no header-only file behind
        return 3
    server.daemon_threads = True
    session.start()
    url = f"http://{args.host}:{args.port}/"
    print(f"live world at {url} (paused; seed {live.header['scenario']['seed']}; writing {live.writer.path})", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        while True:
            live = session.live
            if live.stopped.wait(0.5) and not session.switching and session.live is live:
                break               # stopped for good (not replaced by a new world)
    except KeyboardInterrupt:
        session.live.stop()
        session.live.stopped.wait(10)
    server.shutdown()
    live = session.live
    print(f"stopped at tick {live.tick_count}; resume with: python3 -B -m world.live --resume {live.writer.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
