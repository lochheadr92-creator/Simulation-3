"""Append-only run files: one JSON line per event, canonical bytes for content.

Line kinds:
  header  run identity, engine/schema versions, scenario, genesis state
  tick    the tick record, the committed state, the engine's own availability
  timing  wall-clock cost of that tick (excluded from every digest)
  end     tick count and the trail digest over all tick lines

Content lines are canonical JSON (sorted keys, integers and strings only), so
two runs of the same scenario produce byte-identical content lines. Timing
lines are the only non-deterministic bytes and are kept separate on purpose.

Format v3.stream.2 adds optional blocks a world run needs, each verified by
the reader: a `world` overlay (positions, needs) with its own digest on the
header and on every tick; `decisions` (what each actor chose and why);
`observations` (what each living person saw at tick start: others inside the
perception radius, and source stock if the source cell is in view); and
`production`, the renewal applied to sources after the tick, with the digest
of the state that results. When production is present the next tick chains
from that produced state, and the reader recomputes it from the stored state
rather than trusting the digest. v3.stream.1 files remain readable.

STREAM_FORMAT stays v3.stream.2: `observations` is an optional block verified
the same way as `decisions` (canonical bytes of the tick line, in the trail).
That is not a new digest field and does not change the reader's rules.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel import ENGINE_VERSION, SCHEMA_VERSION, TickRecord, WorldState, canonical_bytes, digest

STREAM_FORMAT = "v3.stream.2"
READABLE_FORMATS = frozenset({"v3.stream.1", STREAM_FORMAT})


class RunFileError(Exception):
    """A run file is missing, malformed, or does not verify."""


def _line(payload: dict[str, Any]) -> bytes:
    return canonical_bytes(payload) + b"\n"


def apply_production(state: dict[str, Any], production: list[dict[str, Any]]) -> dict[str, Any]:
    """The production rule on a stored canonical state: each entry adds
    `amount` (a positive integer) to the stock of an existing source and
    nothing else changes. Pure, on plain JSON, so a reader can recompute the
    produced state without the kernel. Raises RunFileError on a bad entry."""
    produced = json.loads(json.dumps(state))
    sources = produced.get("sources")
    if not isinstance(sources, dict):
        raise RunFileError("production needs a state with sources")
    seen: set[str] = set()
    for entry in production:
        source = entry.get("source") if isinstance(entry, dict) else None
        amount = entry.get("amount") if isinstance(entry, dict) else None
        if not isinstance(source, str) or source not in sources:
            raise RunFileError(f"production names an unknown source {source!r}")
        if source in seen:
            raise RunFileError(f"production names {source!r} twice")
        if type(amount) is not int or amount <= 0:
            raise RunFileError(f"production of {source!r} must be a positive integer, got {amount!r}")
        seen.add(source)
        sources[source]["stock"] = int(sources[source]["stock"]) + amount
    return produced


class RunWriter:
    """Write one run. Refuses to overwrite; every line is flushed as written."""

    def __init__(self, path: Path, *, run_id: str, genesis: WorldState, scenario: dict[str, Any],
                 world: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("xb")
        self._ticks = 0
        self._trail = hashlib.sha256()
        self._closed = False
        header: dict[str, Any] = {
            "kind": "header",
            "format": STREAM_FORMAT,
            "run_id": run_id,
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "scenario": scenario,
            "genesis": genesis.canonical(),
            "genesis_digest": genesis.digest(),
        }
        if world is not None:
            header["world"] = world
            header["world_digest"] = digest(world)
        self._write(header)

    def _write(self, payload: dict[str, Any]) -> bytes:
        raw = _line(payload)
        self._handle.write(raw)
        self._handle.flush()
        return raw

    def record(self, record: TickRecord, next_state: WorldState, *, elapsed_ns: int | None = None,
               world: dict[str, Any] | None = None, decisions: dict[str, Any] | None = None,
               observations: dict[str, Any] | None = None,
               production: list[dict[str, Any]] | None = None, produced_state: WorldState | None = None) -> None:
        """Append one tick. `next_state` is what settlement committed. When a
        world process then produced stock, pass `production` (the rule's
        entries) and `produced_state` (the kernel state that resulted); the
        writer checks that the pure rule on the committed state gives exactly
        that state, so the file never records production that did not happen."""
        if self._closed:
            raise RunFileError("run file already closed")
        if record.next_state_digest != next_state.digest():
            raise RunFileError("committed state does not match the record's next_state_digest")
        payload: dict[str, Any] = {
            "kind": "tick",
            "tick": record.tick,
            "record": record.canonical(),
            "record_digest": record.digest(),
            "state": next_state.canonical(),
            "state_digest": next_state.digest(),
            "availability": next_state.availability(),
        }
        if world is not None:
            payload["world"] = world
            payload["world_digest"] = digest(world)
        if decisions is not None:
            payload["decisions"] = decisions
        if observations is not None:
            payload["observations"] = observations
        if production:
            if produced_state is None:
                raise RunFileError("production needs the produced state")
            expected = digest(apply_production(next_state.canonical(), production))
            if expected != produced_state.digest():
                raise RunFileError("produced state is not the production rule applied to the committed state")
            payload["production"] = production
            payload["produced_state_digest"] = produced_state.digest()
        elif produced_state is not None and produced_state.digest() != next_state.digest():
            raise RunFileError("state changed after settlement without production")
        raw = self._write(payload)
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

    @property
    def has_world(self) -> bool:
        return "world" in self.header


def chained_from(tick: dict[str, Any]) -> Any:
    """The state digest the next tick must start from: the produced state
    when a world process produced stock after this tick, else the committed one."""
    if "production" in tick:
        return tick.get("produced_state_digest")
    return tick.get("state_digest")


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
                if payload.get("format") not in READABLE_FORMATS:
                    problems.append(f"line {number}: unsupported format {payload.get('format')!r}")
                elif digest(payload.get("genesis")) != payload.get("genesis_digest"):
                    problems.append(f"line {number}: genesis digest does not match content")
                else:
                    expected_tick = int(payload["genesis"]["tick"])
                if "world" in payload and digest(payload.get("world")) != payload.get("world_digest"):
                    problems.append(f"line {number}: world genesis digest does not match content")
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
                if ticks and chained_from(ticks[-1]) != record.get("prior_state_digest"):
                    problems.append(f"line {number}: prior state digest does not chain")
                if not ticks and header is not None and header.get("genesis_digest") != record.get("prior_state_digest"):
                    problems.append(f"line {number}: first tick does not start from genesis")
                if "world" in payload and digest(payload.get("world")) != payload.get("world_digest"):
                    problems.append(f"line {number}: world digest does not match content")
                if "production" in payload:
                    try:
                        produced = digest(apply_production(payload.get("state") or {}, payload["production"]))
                    except RunFileError as exc:
                        problems.append(f"line {number}: {exc}")
                    else:
                        if produced != payload.get("produced_state_digest"):
                            problems.append(f"line {number}: produced state digest is not the production rule on the committed state")
                elif "produced_state_digest" in payload:
                    problems.append(f"line {number}: produced state without production")
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
