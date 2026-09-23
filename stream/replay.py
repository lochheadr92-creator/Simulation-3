"""Replay a sealed run against its own file (slice 1c, declaration item 6).

Replay is the independent check ROADMAP asks for: it re-executes from the
header's genesis with the declared inputs and compares every tick line the
file holds, byte for byte without its seal, with what the live code produces.
It is not `--twice`, which compares a second run with the first; it checks
the file against the engine.

Kernel-only (scenario) runs are replayed here by resubmitting each tick's
recorded inputs. World runs recompute their decisions from their own state and
are replayed by world/replay.py with the comparison below, because the stream
never imports the world.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel import Engine, WorldState, canonical_bytes

from stream.run_file import Run, code_identity, decode_input, read_run, tick_payload, without_seal
from stream.scenario import Scenario


class ReplayError(Exception):
    """A run file cannot be replayed: incomplete, unsealed, or the wrong kind of run."""


@dataclass(frozen=True)
class ReplayResult:
    path: Path
    ticks: int                      # tick lines compared
    identical: bool
    divergent_tick: int | None      # the first tick whose replayed line differs
    divergent_field: str | None     # its first differing top-level field, or "genesis"
    code_identity_matches: bool     # the live code identity equals the header's


def sealed_run(path: Path) -> Run:
    """Read `path` and refuse anything but a complete run sealed through its last tick."""
    run = read_run(Path(path))
    if not run.sealed:
        raise ReplayError(f"{path} is format {run.header.get('format')!r}, not a sealed run file")
    if not run.complete:
        raise ReplayError(f"{path} does not verify: {run.problems[0] if run.problems else 'incomplete'}")
    if run.ticks and run.last_sealed_tick != run.ticks[-1].get("tick"):
        raise ReplayError(f"{path} is not sealed through its last tick")
    return run


def code_matches(run: Run) -> bool:
    return (run.header.get("code_identity") or {}).get("digest") == code_identity()["digest"]


# Tick-line fields in the order a tick produces them, so the first difference
# reported is the earliest in the causal chain rather than the first alphabetically.
FIELD_ORDER = ("kind", "tick", "observations", "decisions", "inputs", "record", "record_digest", "state",
               "state_digest", "availability", "production", "produced_state_digest", "world", "world_digest")


def first_difference(stored: dict[str, Any], replayed: dict[str, Any]) -> str | None:
    """The first top-level field, in tick order, where a stored tick line and a
    replayed payload differ once seals are set aside; None when byte-identical."""
    left, right = without_seal(stored), without_seal(replayed)
    if canonical_bytes(left) == canonical_bytes(right):
        return None
    keys = set(left) | set(right)
    for key in [name for name in FIELD_ORDER if name in keys] + sorted(keys - set(FIELD_ORDER)):
        if key not in left or key not in right or canonical_bytes(left[key]) != canonical_bytes(right[key]):
            return key
    return "(line)"


def compare(run: Run, replayed: Iterator[dict[str, Any]]) -> ReplayResult:
    """Compare every tick line of `run`, in order, with the replayed payloads."""
    matches = code_matches(run)
    compared = 0
    for stored in run.ticks:
        payload = next(replayed)
        compared += 1
        field = first_difference(stored, payload)
        if field is not None:
            return ReplayResult(run.path, compared, False, stored.get("tick"), field, matches)
    return ReplayResult(run.path, compared, True, None, None, matches)


def genesis_differs(run: Run) -> ReplayResult:
    return ReplayResult(run.path, 0, False, None, "genesis", code_matches(run))


def replay_scenario(path: Path) -> ReplayResult:
    """Replay a kernel-only scenario run from its header genesis, resubmitting
    each tick's recorded inputs, and compare every tick line with the file."""
    run = sealed_run(path)
    if run.has_world:
        raise ReplayError(f"{path} is a world run; replay it with world.run --replay")
    try:
        scenario = Scenario.from_describe(run.header.get("scenario"))
    except ValueError as exc:
        raise ReplayError(f"{path} does not describe a known scenario: {exc}") from exc
    genesis = WorldState.from_canonical(run.header["genesis"])
    if scenario.genesis().digest() != genesis.digest():
        return genesis_differs(run)

    def payloads() -> Iterator[dict[str, Any]]:
        engine = Engine(genesis)
        for stored in run.ticks:
            proposals = [decode_input(entry) for entry in stored["inputs"]]
            record = engine.tick(proposals)
            yield tick_payload(record, engine.state, inputs=proposals)

    return compare(run, payloads())


def replay_lines(result: ReplayResult) -> list[str]:
    lines = [
        f"file: {result.path}",
        f"ticks compared: {result.ticks}",
        f"code identity: {'same as the header' if result.code_identity_matches else 'DIFFERENT from the header'}",
    ]
    if result.identical:
        lines.append("replay: identical")
    elif result.divergent_field == "genesis":
        lines.append("replay: DIFFERENT, the header genesis is not what its configuration produces")
    else:
        lines.append(f"replay: DIFFERENT at tick {result.divergent_tick}, field {result.divergent_field}")
    return lines
