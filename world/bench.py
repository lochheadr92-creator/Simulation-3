"""Cost check for the world layer at 50 people.

The same measurements as stream/bench.py (tick cost including the sealed
evidence write, memory, evidence size), for a full world tick: observe,
decide, settle and process. The world's rules are unchanged; only the food
levers are raised and the grid kept small enough (every home within 8 steps
of the source) that 50 people can live. This is a cost
workload, not a behaviour result.

It stays the world it was recorded with (evidence/stage-02/world-cost/): one
food source and no water (`ONE_SOURCE_FOOD_ONLY`). The default world gained a
second food source and water on 2026-09-26, and at 50 people with default
water levers most would die of thirst, which is not this workload.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from kernel import Engine
from stream.bench import GIB, KIB, MIB, TARGETS, machine, memory
from stream.run_file import RunWriter
from world.config import ONE_SOURCE_FOOD_ONLY, WorldConfig
from world.run import genesis, run_id_for, world_step

BENCH_LEVERS = {"width": 9, "height": 9, "actors": 50, "starting_food": 3, "source_stock": 200,
                "source_cap": 400, "renewal_every": 1, "renewal_amount": 12, **ONE_SOURCE_FOOD_ONLY}


def bench_config(seed: int = 1) -> WorldConfig:
    return WorldConfig(seed=seed, **BENCH_LEVERS)


def run_world_benchmark(config: WorldConfig, ticks: int, path: Path, checkpoint: int = 1000) -> dict[str, Any]:
    ledger, overlay = genesis(config)
    engine = Engine(ledger)
    tick_ns: list[int] = []
    step_ns = 0
    at_checkpoint: int | None = None
    living_min = len(overlay.living)
    with RunWriter(Path(path), run_id=run_id_for(config, ticks), genesis=ledger, scenario=config.describe(),
                   world=overlay.canonical(), horizon=ticks) as writer:
        for _ in range(ticks):
            started = time.perf_counter_ns()
            step = world_step(engine, overlay, config)
            stepped = time.perf_counter_ns()
            writer.record(step.record, step.committed, inputs=step.proposals, elapsed_ns=stepped - started,
                          **step.line_fields())
            written = time.perf_counter_ns()
            overlay, engine = step.processed.overlay, step.engine
            step_ns += stepped - started
            tick_ns.append(written - started)
            living_min = min(living_min, len(overlay.living))
            if len(tick_ns) == checkpoint:
                at_checkpoint = memory()[0]
        flush_started = time.perf_counter_ns()
        trail = writer.close()
        flush_ns = time.perf_counter_ns() - flush_started
    current, peak = memory()
    size = Path(path).stat().st_size
    ordered = sorted(tick_ns) or [0]
    result: dict[str, Any] = {
        "config": config.describe(),
        "ticks": ticks,
        "trail_digest": trail,
        "survivors": len(overlay.living),
        "deaths": len(overlay.died_at),
        "living_min": living_min,
        "tick_ms_mean": sum(ordered) / len(ordered) / 1e6,
        "tick_ms_p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] / 1e6,
        "tick_ms_max": ordered[-1] / 1e6,
        "step_ms_mean": step_ns / max(ticks, 1) / 1e6,
        "final_flush_ms": flush_ns / 1e6,
        "evidence_bytes": size,
        "evidence_kib_per_tick": size / max(ticks, 1) / KIB,
        "evidence_gib_per_10000_ticks": size / max(ticks, 1) * 10000 / GIB,
        "peak_memory_mib": peak / MIB,
        "memory_at_tick_1000_mib": None if at_checkpoint is None else at_checkpoint / MIB,
        "memory_at_end_mib": None if current is None else current / MIB,
        "memory_growth_mib": (None if at_checkpoint is None or current is None or ticks <= checkpoint
                              else (current - at_checkpoint) / MIB),
        "machine": machine(),
    }
    checks = {
        "mean_tick_ms": result["tick_ms_mean"], "p95_tick_ms": result["tick_ms_p95"],
        "peak_memory_mib": result["peak_memory_mib"], "evidence_kib_per_tick": result["evidence_kib_per_tick"],
        "evidence_gib_per_10000_ticks": result["evidence_gib_per_10000_ticks"],
        "memory_growth_mib": result["memory_growth_mib"],
    }
    result["within_targets"] = {name: (None if value is None else value <= TARGETS[name]) for name, value in checks.items()}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cost check for the world layer at 50 people.")
    parser.add_argument("--ticks", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True, help="run file to write; must not exist")
    parser.add_argument("--result", type=Path, help="also write the result JSON here")
    args = parser.parse_args(argv)
    result = run_world_benchmark(bench_config(args.seed), args.ticks, args.out)
    text = json.dumps(result, indent=2)
    print(text)
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
