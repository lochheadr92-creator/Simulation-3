"""Recover a cut or broken sealed world run (slice 1c, declaration item 7).

A world's state is the kernel ledger plus the overlay, both stored in full on
every sealed tick line, and every later proposal comes from a decision the
live code makes from them. Recovery therefore restores both from the last
sealed tick and continues through `world_step`, the same path a run takes,
with the stream's file functions. This lives in world/ because the stream
never imports the world.
"""

from __future__ import annotations

import time
from pathlib import Path

from kernel import Engine

from stream.recover import (RecoveryError, RecoveryResult, recovery_result, restored_state, resume_writer,
                            sealed_prefix)
from world.config import WorldConfig
from world.overlay import Overlay
from world.run import world_step


def recover_world(source: Path, out: Path) -> RecoveryResult:
    """Recover a world run into the new file `out`."""
    prefix = sealed_prefix(source)
    if "world" not in prefix.header:
        raise RecoveryError(f"{source} is not a world run; recover it with stream.run --recover")
    try:
        config = WorldConfig.from_describe(prefix.header.get("scenario"))
    except ValueError as exc:
        raise RecoveryError(f"{source} does not describe this world: {exc}") from exc
    last = prefix.ticks[-1] if prefix.ticks else None
    engine = Engine(restored_state(prefix.header, last))
    overlay = Overlay.from_canonical(last["world"] if last else prefix.header["world"])
    if overlay.digest() != (last["world_digest"] if last else prefix.header["world_digest"]):
        raise RecoveryError("the restored overlay does not match its stored digest")
    holds = len(engine.state.reservations)
    with resume_writer(out, prefix) as writer:
        for _ in range(prefix.remaining):
            started = time.perf_counter_ns()
            step = world_step(engine, overlay, config)
            cost = time.perf_counter_ns() - started
            writer.record(step.record, step.committed, inputs=step.proposals, elapsed_ns=cost, **step.line_fields())
            overlay, engine = step.processed.overlay, step.engine
        trail = writer.close()
    return recovery_result(prefix, out, trail, writer.seal, holds)
