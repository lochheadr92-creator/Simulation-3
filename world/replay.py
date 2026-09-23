"""Replay a sealed world run against its own file (slice 1c, declaration item 6).

A world run's proposals are not external input: every one comes from a
decision the live code makes from the run's own state. Replay therefore
rebuilds the configuration and genesis from the header and recomputes
observations, decisions, proposals, settlement and the world processes tick
by tick through `world_step`, the same path a run takes, comparing every tick
line with the file, byte for byte without its seal.

This lives in world/ because the stream never imports the world; it uses the
stream's file functions and comparison.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from kernel import Engine

from stream.replay import ReplayError, ReplayResult, compare, genesis_differs, sealed_run
from stream.run_file import tick_payload
from world.config import WorldConfig, genesis
from world.run import world_step


def replay_world(path: Path) -> ReplayResult:
    """Replay a world run from its header configuration and genesis, recomputing
    every decision with the live code, and compare every tick line with the file."""
    run = sealed_run(path)
    if not run.has_world:
        raise ReplayError(f"{path} is not a world run; replay it with stream.run --replay")
    try:
        config = WorldConfig.from_describe(run.header.get("scenario"))
    except ValueError as exc:
        raise ReplayError(f"{path} does not describe this world: {exc}") from exc
    ledger, overlay = genesis(config)
    if ledger.canonical() != run.header.get("genesis") or overlay.canonical() != run.header.get("world"):
        return genesis_differs(run)

    def payloads() -> Iterator[dict[str, Any]]:
        engine, current = Engine(ledger), overlay
        for _ in run.ticks:
            step = world_step(engine, current, config)
            yield tick_payload(step.record, step.committed, inputs=step.proposals, **step.line_fields())
            engine, current = step.engine, step.processed.overlay

    return compare(run, payloads())
