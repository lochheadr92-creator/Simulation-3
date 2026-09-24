"""Recover a cut or broken sealed run through its last verified sealed tick
(slice 1c, declaration item 7), and restore private engines from sealed ticks
(item 8).

Recovery trusts only what the seal chain vouches for. It keeps the source's
bytes through the last sealed tick line, rebuilds the state that tick left from
its stored canonical content, and continues to the declared horizon in a new
file; nothing past that line is read or used. The result's content lines
(header, ticks, end, seals included) equal an uninterrupted run's, and only
timing lines may differ.

A kernel-only scenario's input generator is not in the file, so it is rebuilt
from the header and run through the sealed ticks, and it must reproduce every
sealed tick's recorded inputs before it generates the rest. World runs are
recovered by world/recover.py with these functions, because the stream never
imports the world.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel import Engine, WorldState, canonical_bytes

from stream.run_file import RunWriter, apply_production, code_identity, encode_input, read_run
from stream.scenario import ProposalGenerator, Scenario


class RecoveryError(Exception):
    """A run file cannot be recovered: unsealed, complete, untrustworthy, or written by other code."""


@dataclass(frozen=True)
class SealedPrefix:
    source: Path
    source_sha256: str
    header: dict[str, Any]
    ticks: tuple[dict[str, Any], ...]      # the sealed tick lines, parsed
    tick_lines: tuple[bytes, ...]          # the same lines, as written
    prefix: bytes                          # the source's bytes through the last sealed tick line

    @property
    def last_sealed_tick(self) -> int:
        return self.ticks[-1]["tick"] if self.ticks else -1

    @property
    def seal(self) -> str:
        return self.ticks[-1]["seal"] if self.ticks else self.header["seal"]

    @property
    def next_tick(self) -> int:
        return self.header["genesis"]["tick"] + len(self.ticks)

    @property
    def remaining(self) -> int:
        return self.header["horizon"] - len(self.ticks)


def sealed_prefix(path: Path) -> SealedPrefix:
    """The part of a cut or broken sealed run that its seals vouch for."""
    path = Path(path)
    run = read_run(path)
    if not run.sealed:
        raise RecoveryError(f"{path} is format {run.header.get('format')!r}, not a sealed run file")
    if run.first_break_line == 1 or run.last_sealed_tick is None:
        raise RecoveryError(f"{path}: the header does not verify, so nothing in the file can be trusted")
    if run.complete:
        raise RecoveryError(f"{path} is complete; there is nothing to recover")
    if (run.header.get("code_identity") or {}).get("digest") != code_identity()["digest"]:
        raise RecoveryError(f"{path} was written by other code (its code identity differs from the live "
                            "code), so continuing it here would not continue the same run")
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    if not lines or json.loads(lines[0]) != run.header:
        raise RecoveryError(f"{path}: the first line is not the header the reader verified")
    wanted = run.last_sealed_tick - run.header["genesis"]["tick"] + 1
    kept = [lines[0]]
    ticks: list[dict[str, Any]] = []
    tick_lines: list[bytes] = []
    for line in lines[1:]:
        if len(ticks) == wanted:
            break
        kept.append(line)
        payload = json.loads(line)
        if payload.get("kind") == "tick":
            ticks.append(payload)
            tick_lines.append(line)
    if len(ticks) != wanted or (ticks and ticks[-1]["tick"] != run.last_sealed_tick):
        raise RecoveryError(f"{path}: the last sealed tick line could not be located")
    return SealedPrefix(source=path, source_sha256=hashlib.sha256(raw).hexdigest(), header=run.header,
                        ticks=tuple(ticks), tick_lines=tuple(tick_lines), prefix=b"".join(kept))


def restored_state(header: dict[str, Any], tick: dict[str, Any] | None) -> WorldState:
    """The state a sealed tick left for the next one: the produced state when
    the tick recorded production, else the committed state, or the genesis when
    no tick is given. Rebuilt from stored canonical content and checked against
    its stored digest."""
    if tick is None:
        canonical, expected = header["genesis"], header["genesis_digest"]
    elif "production" in tick:
        canonical, expected = apply_production(tick["state"], tick["production"]), tick["produced_state_digest"]
    else:
        canonical, expected = tick["state"], tick["state_digest"]
    state = WorldState.from_canonical(canonical)
    if state.digest() != expected:
        raise RecoveryError("a restored state does not match its stored digest")
    return state


def restore_engine(path: Path, tick: int) -> Engine:
    """A private engine on the state sealed tick `tick` left (declaration item 8).
    Every call builds its own state from the file, so two engines restored from
    one tick share nothing mutable."""
    run = read_run(Path(path))
    genesis_tick = (run.header.get("genesis") or {}).get("tick", 0)
    if not run.sealed or run.last_sealed_tick is None or not genesis_tick <= tick <= run.last_sealed_tick:
        raise RecoveryError(f"tick {tick} is not sealed in {path}")
    return Engine(restored_state(run.header, run.ticks[tick - genesis_tick]))


def resume_writer(out: Path, prefix: SealedPrefix) -> RunWriter:
    return RunWriter.resume(out, header=prefix.header, prefix=prefix.prefix, tick_lines=prefix.tick_lines,
                            seal=prefix.seal, next_tick=prefix.next_tick)


@dataclass(frozen=True)
class RecoveryResult:
    source: Path
    source_sha256: str
    last_sealed_tick: int
    live_holds_at_cut: int              # reservations in the state recovery resumed from
    resumed: tuple[int, int] | None     # first and last tick recovery wrote, None when none were left
    out: Path
    trail_digest: str
    final_seal: str


def recovery_result(prefix: SealedPrefix, out: Path, trail: str, final_seal: str, holds: int) -> RecoveryResult:
    first = prefix.next_tick
    last = prefix.header["genesis"]["tick"] + prefix.header["horizon"] - 1
    return RecoveryResult(source=prefix.source, source_sha256=prefix.source_sha256,
                          last_sealed_tick=prefix.last_sealed_tick, live_holds_at_cut=holds,
                          resumed=(first, last) if first <= last else None, out=Path(out),
                          trail_digest=trail, final_seal=final_seal)


def recover_scenario(source: Path, out: Path) -> RecoveryResult:
    """Recover a kernel-only scenario run into the new file `out`."""
    prefix = sealed_prefix(source)
    if "world" in prefix.header:
        raise RecoveryError(f"{source} is a world run; recover it with world.run --recover")
    try:
        scenario = Scenario.from_describe(prefix.header.get("scenario"))
    except ValueError as exc:
        raise RecoveryError(f"{source} does not describe a known scenario: {exc}") from exc
    generator = ProposalGenerator(scenario)
    previous = prefix.header["genesis"]
    for payload in prefix.ticks:
        live = {action: held["actor"] for action, held in previous["reservations"].items()}
        proposals = generator.tick(payload["tick"], live)
        if canonical_bytes([encode_input(p) for p in proposals]) != canonical_bytes(payload["inputs"]):
            raise RecoveryError(f"the scenario generator does not reproduce the sealed inputs of tick {payload['tick']}")
        previous = apply_production(payload["state"], payload["production"]) if "production" in payload else payload["state"]
    engine = Engine(restored_state(prefix.header, prefix.ticks[-1] if prefix.ticks else None))
    holds = len(engine.state.reservations)
    with resume_writer(out, prefix) as writer:
        for _ in range(prefix.remaining):
            live = {action: held.actor for action, held in engine.state.reservations.items()}
            proposals = generator.tick(engine.state.tick, live)
            started = time.perf_counter_ns()
            record = engine.tick(proposals)
            writer.record(record, engine.state, inputs=proposals, elapsed_ns=time.perf_counter_ns() - started)
        trail = writer.close()
    return recovery_result(prefix, out, trail, writer.seal, holds)


def recovery_lines(result: RecoveryResult) -> list[str]:
    resumed = f"ticks {result.resumed[0]} to {result.resumed[1]}" if result.resumed else "no ticks (end line only)"
    return [
        f"source: {result.source}",
        f"source sha256: {result.source_sha256}",
        f"last sealed tick: {result.last_sealed_tick} (live holds at the cut: {result.live_holds_at_cut})",
        f"resumed: {resumed}",
        f"written: {result.out}",
        f"trail_digest: {result.trail_digest}",
        f"final_seal: {result.final_seal}",
    ]
