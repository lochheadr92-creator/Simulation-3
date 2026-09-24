"""Slice 1d: the 50-actor kernel cost check.

A seeded, fixed-mix synthetic workload drives the kernel and streams complete
sealed evidence while the run measures tick cost, memory and evidence size
against the targets in ROADMAP.md.

Workload v3.bench.kernel.1. Every actor makes at most one proposal per tick.
An actor holding a reservation closes one of them with probability 0.6
(complete 0.75, cancel 0.25). Otherwise it picks by weight: claim 35 (from
"plenty", "scarce", or both at once), transfer 20, consume 20, reserve 15 (of
a claim, transfer or consume), idle 10, with amounts of 1 to 3. "plenty" holds
10**9 units, so its claims keep succeeding for the whole run; "scarce" holds
40 and is fought over until it runs dry, after which claims on it are denied.
The kernel has no production, so that is the only stock contention it can
sustain; transfers and consumes beyond a balance add denials throughout. Holds
close quickly, so the live state stays bounded.

Tick cost is settlement plus that tick's sealed evidence write. Proposal
generation is timed separately and excluded, and the final flush is reported
on its own. The timing lines inside the run file carry settlement time only,
as in the other runners. A kernel-only run writes one evidence stream (tick
lines carrying the replay evidence); decision records come with the world.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel import Engine, Proposal, Source, WorldState
from stream.run_file import RunWriter

WORKLOAD_NAME = "kernel-bench"
WORKLOAD_VERSION = "v3.bench.kernel.1"
KIB, MIB, GIB = 1024, 1024 ** 2, 1024 ** 3

# ROADMAP.md, slice 1d
TARGETS = {
    "mean_tick_ms": 50.0,
    "p95_tick_ms": 100.0,
    "peak_memory_mib": 512.0,
    "evidence_kib_per_tick": 64.0,
    "evidence_gib_per_10000_ticks": 1.0,
    "memory_growth_mib": 64.0,          # between tick 1,000 and the end of a 10,000-tick run
}


@dataclass(frozen=True)
class Workload:
    seed: int = 1
    actors: int = 50
    plenty: int = 10 ** 9
    scarce: int = 40
    starting_balance: int = 5

    def describe(self) -> dict[str, Any]:
        return {"name": WORKLOAD_NAME, "version": WORKLOAD_VERSION, "seed": self.seed, "actors": self.actors,
                "plenty": self.plenty, "scarce": self.scarce, "starting_balance": self.starting_balance}

    def actor_ids(self) -> list[str]:
        return [f"a{index + 1:03d}" for index in range(self.actors)]

    def genesis(self) -> WorldState:
        actors = tuple(self.actor_ids())
        return WorldState.genesis(balances={actor: self.starting_balance for actor in actors},
                                  sources={"plenty": Source(self.plenty, actors), "scarce": Source(self.scarce, actors)})


class WorkloadGenerator:
    """Stateful only in its seeded PRNG; reads live holds from the tick-start state."""

    def __init__(self, workload: Workload) -> None:
        self.rng = random.Random(workload.seed)
        self.actors = workload.actor_ids()

    def tick(self, state: WorldState) -> list[Proposal]:
        rng = self.rng
        held: dict[str, list[str]] = {}
        for action, reservation in sorted(state.reservations.items()):
            held.setdefault(reservation.actor, []).append(action)
        proposals: list[Proposal] = []
        for actor in self.actors:
            proposal_id = f"t{state.tick}-{actor}"
            if held.get(actor) and rng.random() < 0.6:
                operation = "complete" if rng.random() < 0.75 else "cancel"
                proposals.append(Proposal(proposal_id, actor, 0, operation, {"action_id": rng.choice(held[actor])}))
                continue
            kind = rng.choices(["claim", "transfer", "consume", "reserve", "idle"], weights=[35, 20, 20, 15, 10])[0]
            if kind == "idle":
                continue
            inner = rng.choice(["claim", "transfer", "consume"]) if kind == "reserve" else kind
            amount = rng.randint(1, 3)
            if inner == "claim":
                roll = rng.random()
                if roll < 0.6:
                    params: dict[str, Any] = {"sources": {"plenty": amount}}
                elif roll < 0.85:
                    params = {"sources": {"scarce": amount}}
                else:
                    params = {"sources": {"plenty": amount, "scarce": 1}}
            elif inner == "transfer":
                params = {"to": rng.choice([other for other in self.actors if other != actor]), "amount": amount}
            else:
                params = {"amount": amount}
            if kind == "reserve":
                proposals.append(Proposal(proposal_id, actor, 0, "reserve", {"operation": inner, "params": params}))
            else:
                proposals.append(Proposal(proposal_id, actor, 0, inner, params))
        return proposals


def memory() -> tuple[int | None, int]:
    """(current, peak) memory of this process in bytes. Windows: working set.
    Elsewhere only the peak resident size is available."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return counters.WorkingSetSize, counters.PeakWorkingSetSize
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return None, peak * (1 if sys.platform == "darwin" else KIB)


def machine() -> dict[str, Any]:
    return {"node": platform.node(), "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": platform.python_version(),
            "implementation": platform.python_implementation()}


def run_benchmark(workload: Workload, ticks: int, path: Path, checkpoint: int = 1000) -> dict[str, Any]:
    engine = Engine(workload.genesis())
    generator = WorkloadGenerator(workload)
    tick_ns: list[int] = []
    settle_ns = generate_ns = 0
    proposals_total = max_holds = 0
    at_checkpoint: int | None = None
    run_id = f"{WORKLOAD_NAME}-s{workload.seed}-a{workload.actors}-t{ticks}"
    with RunWriter(Path(path), run_id=run_id, genesis=engine.state, scenario=workload.describe(),
                   horizon=ticks) as writer:
        for _ in range(ticks):
            started = time.perf_counter_ns()
            proposals = generator.tick(engine.state)
            generated = time.perf_counter_ns()
            record = engine.tick(proposals)
            settled = time.perf_counter_ns()
            writer.record(record, engine.state, inputs=proposals, elapsed_ns=settled - generated)
            written = time.perf_counter_ns()
            generate_ns += generated - started
            settle_ns += settled - generated
            tick_ns.append(written - generated)
            proposals_total += len(proposals)
            max_holds = max(max_holds, len(engine.state.reservations))
            if len(tick_ns) == checkpoint:
                at_checkpoint = memory()[0]
        flush_started = time.perf_counter_ns()
        trail = writer.close()
        flush_ns = time.perf_counter_ns() - flush_started
    current, peak = memory()
    size = Path(path).stat().st_size
    ordered = sorted(tick_ns) or [0]
    result: dict[str, Any] = {
        "workload": workload.describe(),
        "ticks": ticks,
        "trail_digest": trail,
        "final_state_digest": engine.state.digest(),
        "tick_ms_mean": sum(ordered) / len(ordered) / 1e6,
        "tick_ms_p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] / 1e6,
        "tick_ms_max": ordered[-1] / 1e6,
        "settle_ms_mean": settle_ns / max(ticks, 1) / 1e6,
        "generate_ms_mean": generate_ns / max(ticks, 1) / 1e6,
        "final_flush_ms": flush_ns / 1e6,
        "proposals_per_tick": proposals_total / max(ticks, 1),
        "live_holds_max": max_holds,
        "live_holds_at_end": len(engine.state.reservations),
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
    parser = argparse.ArgumentParser(description="Slice 1d: the 50-actor kernel cost check.")
    parser.add_argument("--ticks", type=int, default=1000)
    parser.add_argument("--actors", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True, help="run file to write; must not exist")
    parser.add_argument("--result", type=Path, help="also write the result JSON here")
    args = parser.parse_args(argv)
    result = run_benchmark(Workload(seed=args.seed, actors=args.actors), args.ticks, args.out)
    text = json.dumps(result, indent=2)
    print(text)
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
