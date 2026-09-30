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
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kernel import Engine
from stream.recover import SealedPrefix, resume_writer, sealed_prefix
from stream.recover import restored_state
from stream.run_file import Run, RunWriter
from world.config import WorldConfig, genesis
from world.overlay import Overlay
from world.run import build_parser as run_parser, config_from, run_id_for, world_step
from world.viewer import render_html
from world.viewer_index import build_index

LIVE_HORIZON = 1_000_000
RING = 600            # ticks kept in memory for new tabs: enough for 10 minutes at 1 tick/s, ~2 MB of JSON
FSYNC_SECONDS = 5.0
SPEEDS = (0.1, 0.25, 0.5, 1, 2, 5, 10, 0)   # 0 = unthrottled
QUEUE = 64            # per-subscriber queue; a slow client is skipped, never waited for


class LiveWorld:
    """The single owner of a live world. Drive it with `run_forever()` in a
    thread, or with `advance()` in tests."""

    def __init__(self, config: WorldConfig, engine: Engine, overlay: Overlay, writer: RunWriter,
                 header: dict[str, Any], prior: list[dict[str, Any]]):
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
        self.tick_count = len(prior)
        self.last_fsync = time.monotonic()
        self.stopped = threading.Event()

    # ------------------------------------------------------------ control --
    def set_paused(self, paused: bool) -> None:
        with self.wake:
            self.paused = paused
            self.wake.notify_all()
        if paused:
            self.fsync()
        self.broadcast({"kind": "control", **self.status()})

    def step(self) -> None:
        with self.wake:
            self.steps += 1
            self.wake.notify_all()

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
                "run_id": self.header["run_id"], "ring": RING, "stopping": self.stopping}

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
        self.broadcast(message)
        return payload

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
        try:
            while True:
                with self.wake:
                    while not self.stopping and self.paused and self.steps == 0:
                        self.wake.wait()
                    if self.stopping:
                        break
                    stepping = self.steps > 0
                    if stepping:
                        self.steps -= 1
                    speed = self.speed
                self.advance()
                if not stepping and speed > 0:
                    with self.wake:
                        self.wake.wait(timeout=1.0 / speed)
        finally:
            self.fsync()
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


def _patched_writer(writer: RunWriter) -> RunWriter:
    """Remember the last tick line written, so the payload is published byte-for-byte."""
    original = writer._write

    def _write(payload):
        raw = original(payload)
        if payload.get("kind") == "tick":
            writer.last_line = raw
        return raw
    writer._write = _write
    return writer


def open_live(config: WorldConfig, path: Path) -> LiveWorld:
    ledger, overlay = genesis(config)
    writer = RunWriter(path, run_id=run_id_for(config, LIVE_HORIZON) + "-live", genesis=ledger,
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



def resume_live(source: Path, out: Path | None = None) -> LiveWorld:
    prefix = _prefix(source)
    config = WorldConfig.from_describe(prefix.header["scenario"])
    last = prefix.ticks[-1] if prefix.ticks else None
    engine = Engine(restored_state(prefix.header, last))
    overlay = Overlay.from_canonical(last["world"] if last else prefix.header["world"])
    if out is None:
        k = 1
        while True:
            out = source.with_name(f"{source.stem}.r{k}.jsonl")
            if not out.exists():
                break
            k += 1
    writer = _patched_writer(resume_writer(out, prefix))
    return LiveWorld(config, engine, overlay, writer, prefix.header, list(prefix.ticks))


# ------------------------------------------------------------------ HTTP --
def make_handler(live: LiveWorld):
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
            path, _, query = self.path.partition("?")
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if path == "/":
                run, base = live.page_run()
                page = render_html(run, live={"base": base, **live.status()})
                raw = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            elif path == "/status":
                self._json(200, {**live.status(), "scenario": live.header["scenario"]})
            elif path == "/ticks":
                start, end = int(params.get("from", 0)), int(params.get("to", live.tick_count))
                with live.lock:
                    ring = list(live.ring)
                first = live.tick_count - len(ring)
                out = [t for t in ring if start <= t["tick"] < end]
                if start < first:      # older ticks come from the run file on disk
                    with Path(live.writer.path).open("rb") as fh:
                        for line in fh:
                            if b'"kind":"tick"' in line:
                                t = json.loads(line)
                                if start <= t["tick"] < min(end, first):
                                    out.append(t)
                    out.sort(key=lambda t: t["tick"])
                self._json(200, {"ticks": out})
            elif path == "/events":
                since = int(params.get("since", live.tick_count))
                q = live.subscribe()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self._send({"kind": "control", **live.status()})
                    with live.lock:
                        missed = [t for t in live.ring if t["tick"] >= since]
                    sent = since
                    for t in missed:
                        self._send({"kind": "tick", "tick": t, "index": None, "control": live.status()})
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
                        self._send(msg)
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
                else:
                    return self._json(400, {"error": f"unknown action {action!r}"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            self._json(200, live.status())
    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = run_parser()
    parser.description = "Run a world live in the browser: it advances while you watch."
    parser.add_argument("--resume", dest="resume_live", default=None, metavar="FILE",
                        help="continue a live world from its saved run (a new file is written next to it)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    parser.add_argument("--host", default="127.0.0.1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resume_live:
        live = resume_live(Path(args.resume_live))
    else:
        if not args.out:
            print("live worlds need --out FILE", file=sys.stderr)
            return 2
        live = open_live(config_from(args), Path(args.out))
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(live))
    except OSError as exc:
        print(f"port {args.port} is not available ({exc}); choose another with --port", file=sys.stderr)
        live.writer._handle.close()
        return 3
    server.daemon_threads = True
    thread = threading.Thread(target=live.run_forever, name="world", daemon=True)
    thread.start()
    url = f"http://{args.host}:{args.port}/"
    print(f"live world at {url} (paused; writing {live.writer.path})", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        while not live.stopped.wait(0.5):
            pass
    except KeyboardInterrupt:
        live.stop()
        live.stopped.wait(10)
    server.shutdown()
    print(f"stopped at tick {live.tick_count}; resume with: python3 -B -m world.live --resume {live.writer.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
