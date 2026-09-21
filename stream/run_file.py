"""Append-only run files: one JSON line per event, canonical bytes for content.

Line kinds:
  header  run identity, engine/schema versions, scenario, genesis state
  tick    the tick record, the committed state, the engine's own availability
  timing  wall-clock cost of that tick (excluded from every digest)
  end     tick count and the trail digest over all tick lines

Content lines are canonical JSON (sorted keys, integers and strings only), so
two runs of the same scenario produce byte-identical content lines. Timing
lines are the only non-deterministic bytes and are kept separate on purpose.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel import ENGINE_VERSION, SCHEMA_VERSION, TickRecord, WorldState, canonical_bytes, digest

STREAM_FORMAT = "v3.stream.1"


class RunFileError(Exception):
    """A run file is missing, malformed, or does not verify."""


def _line(payload: dict[str, Any]) -> bytes:
    return canonical_bytes(payload) + b"\n"


class RunWriter:
    """Write one run. Refuses to overwrite; every line is flushed as written."""

    def __init__(self, path: Path, *, run_id: str, genesis: WorldState, scenario: dict[str, Any]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("xb")
        self._ticks = 0
        self._trail = hashlib.sha256()
        self._closed = False
        self._write({
            "kind": "header",
            "format": STREAM_FORMAT,
            "run_id": run_id,
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "scenario": scenario,
            "genesis": genesis.canonical(),
            "genesis_digest": genesis.digest(),
        })

    def _write(self, payload: dict[str, Any]) -> bytes:
        raw = _line(payload)
        self._handle.write(raw)
        self._handle.flush()
        return raw

    def record(self, record: TickRecord, next_state: WorldState, *, elapsed_ns: int | None = None) -> None:
        if self._closed:
            raise RunFileError("run file already closed")
        if record.next_state_digest != next_state.digest():
            raise RunFileError("committed state does not match the record's next_state_digest")
        raw = self._write({
            "kind": "tick",
            "tick": record.tick,
            "record": record.canonical(),
            "record_digest": record.digest(),
            "state": next_state.canonical(),
            "state_digest": next_state.digest(),
            "availability": next_state.availability(),
        })
        self._trail.update(raw)
        self._ticks += 1
        if elapsed_ns is not None:
            self._write({"kind": "timing", "tick": record.tick, "elapsed_ns": int(elapsed_ns)})

    def close(self) -> str:
        if self._closed:
            return self._trail.hexdigest()
        trail = self._trail.hexdigest()
        self._write({"kind": "end", "ticks": self._ticks, "trail_digest": trail})
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self._closed = True
        return trail

    def __enter__(self) -> "RunWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@dataclass(frozen=True)
class Run:
    path: Path
    header: dict[str, Any]
    ticks: tuple[dict[str, Any], ...]
    timings: dict[int, int]
    end: dict[str, Any] | None
    trail_digest: str
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def run_id(self) -> str:
        return str(self.header.get("run_id", ""))

    @property
    def complete(self) -> bool:
        return self.end is not None and not self.problems


def read_run(path: Path) -> Run:
    """Read and verify a run file. Every stored digest is recomputed from the
    stored content; a run with problems is still returned so a viewer can show
    what exists, but `complete` is false."""
    path = Path(path)
    if not path.is_file():
        raise RunFileError(f"no run file at {path}")
    header: dict[str, Any] | None = None
    ticks: list[dict[str, Any]] = []
    timings: dict[int, int] = {}
    end: dict[str, Any] | None = None
    problems: list[str] = []
    trail = hashlib.sha256()
    expected_tick = None
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.endswith(b"\n"):
                problems.append(f"line {number}: incomplete (no newline)")
                break
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                problems.append(f"line {number}: not JSON ({exc.msg})")
                continue
            if not isinstance(payload, dict) or "kind" not in payload:
                problems.append(f"line {number}: not an event")
                continue
            if end is not None:
                problems.append(f"line {number}: event after end")
            kind = payload["kind"]
            if kind == "header":
                if header is not None:
                    problems.append(f"line {number}: second header")
                header = payload
                if payload.get("format") != STREAM_FORMAT:
                    problems.append(f"line {number}: unsupported format {payload.get('format')!r}")
                elif digest(payload.get("genesis")) != payload.get("genesis_digest"):
                    problems.append(f"line {number}: genesis digest does not match content")
                else:
                    expected_tick = int(payload["genesis"]["tick"])
            elif kind == "tick":
                if header is None:
                    problems.append(f"line {number}: tick before header")
                if canonical_bytes(payload) + b"\n" != raw:
                    problems.append(f"line {number}: tick line is not canonical bytes")
                if digest(payload.get("record")) != payload.get("record_digest"):
                    problems.append(f"line {number}: record digest does not match content")
                if digest(payload.get("state")) != payload.get("state_digest"):
                    problems.append(f"line {number}: state digest does not match content")
                record = payload.get("record") or {}
                if record.get("next_state_digest") != payload.get("state_digest"):
                    problems.append(f"line {number}: record and state disagree")
                if expected_tick is not None and payload.get("tick") != expected_tick:
                    problems.append(f"line {number}: expected tick {expected_tick}, found {payload.get('tick')}")
                if ticks and ticks[-1]["state_digest"] != record.get("prior_state_digest"):
                    problems.append(f"line {number}: prior state digest does not chain")
                if not ticks and header is not None and header.get("genesis_digest") != record.get("prior_state_digest"):
                    problems.append(f"line {number}: first tick does not start from genesis")
                trail.update(raw)
                ticks.append(payload)
                expected_tick = int(payload.get("tick", -1)) + 1
            elif kind == "timing":
                timings[int(payload.get("tick", -1))] = int(payload.get("elapsed_ns", 0))
            elif kind == "end":
                end = payload
                if payload.get("ticks") != len(ticks):
                    problems.append(f"line {number}: end declares {payload.get('ticks')} ticks, file has {len(ticks)}")
                if payload.get("trail_digest") != trail.hexdigest():
                    problems.append(f"line {number}: trail digest does not match the tick lines")
            else:
                problems.append(f"line {number}: unknown event kind {kind!r}")
    if header is None:
        problems.append("no header")
        header = {}
    if end is None:
        problems.append("no end record (run did not finish, or the file was cut)")
    return Run(path=path, header=header, ticks=tuple(ticks), timings=timings, end=end,
               trail_digest=trail.hexdigest(), problems=tuple(problems))
