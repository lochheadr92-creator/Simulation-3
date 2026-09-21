"""Run a seeded world, stream every tick, and check it reproduces.

    py -3 -B -m world.run --seed 7 --ticks 300
    py -3 -B -m world.run --seed 7 --ticks 300 --twice --html
    py -3 -B -m world.run --seed 7 --ticks 300 --renewal-every 2   # a different configuration

One tick:
  1. every living person observes (world/observe.py)
  2. every living person decides (world/decide.py); eat and claim become
     kernel proposals, moves are kept for the process step
  3. the kernel settles the proposals: this is the only place food moves
  4. world processes run (world/process.py): movement, hunger, death, renewal
  5. the tick line records the kernel record and state, the overlay, every
     decision, every observation, and any production; a timing line records
     wall-clock cost

Output goes to runs/<run_id>.jsonl (and .html). runs/ is ignored by git: a
checkpoint run is exploration output under OD-009, not evidence.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel import Engine, Proposal, claim, consume

from stream.run_file import RunWriter, read_run
from world.config import FOOD_SOURCE, WorldConfig, genesis
from world.decide import CLAIM, EAT, Decision, decide
from world.observe import observe

from world.process import advance

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def run_id_for(config: WorldConfig, ticks: int) -> str:
    return f"{config.name}-seed{config.seed}-ticks{ticks}"


def proposals_for(decisions: dict[str, Decision], tick: int) -> list[Proposal]:
    out: list[Proposal] = []
    for actor in sorted(decisions):
        decision = decisions[actor]
        pid = f"t{tick}-{actor}"
        if decision.kind == EAT:
            out.append(consume(pid, actor, 0, amount=decision.amount))
        elif decision.kind == CLAIM:
            out.append(claim(pid, actor, 0, sources={FOOD_SOURCE: decision.amount}))
    return out


@dataclass(frozen=True)
class WorldRun:
    path: Path
    ticks: int
    trail_digest: str
    final_state_digest: str
    final_overlay_digest: str
    survivors: int
    deaths: int
    tick_ms_mean: float
    tick_ms_p95: float
    tick_ms_max: float


def run_world(config: WorldConfig, ticks: int, path: Path) -> WorldRun:
    ledger, overlay = genesis(config)
    engine = Engine(ledger)
    elapsed: list[int] = []
    with RunWriter(path, run_id=run_id_for(config, ticks), genesis=ledger, scenario=config.describe(),
                   world=overlay.canonical()) as writer:
        for _ in range(ticks):
            started = time.perf_counter_ns()
            state = engine.state
            views = {actor: observe(actor, state, overlay, config) for actor in overlay.living}
            decisions = {actor: decide(views[actor], config) for actor in overlay.living}
            record = engine.tick(proposals_for(decisions, state.tick))
            processed = advance(overlay, decisions, record, engine.state, config)
            cost = time.perf_counter_ns() - started
            elapsed.append(cost)
            writer.record(
                record, engine.state, elapsed_ns=cost,
                world=processed.overlay.canonical(),
                decisions={actor: d.canonical() for actor, d in decisions.items()},
                observations={actor: view.compact() for actor, view in views.items()},
                production=list(processed.production) or None,
                produced_state=processed.ledger,
            )
            overlay = processed.overlay
            if processed.production:
                engine = Engine(processed.ledger)
        trail = writer.close()
    ordered = sorted(elapsed) or [0]
    return WorldRun(
        path=path, ticks=ticks, trail_digest=trail,
        final_state_digest=engine.state.digest(), final_overlay_digest=overlay.digest(),
        survivors=len(overlay.living), deaths=len(overlay.died_at),
        tick_ms_mean=sum(ordered) / len(ordered) / 1e6,
        tick_ms_p95=ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] / 1e6,
        tick_ms_max=ordered[-1] / 1e6,
    )


LEVERS = ("width", "height", "actors", "starting_food", "source_stock", "source_cap", "renewal_every",
          "renewal_amount", "claim_amount", "hunger_rate", "satiation", "hungry_at", "emergency_at", "death_at",
          "perception_radius")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a seeded one-source grid world and write its record stream.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--ticks", type=int, default=300)
    for lever in LEVERS:
        parser.add_argument(f"--{lever.replace('_', '-')}", type=int, default=None, help=f"world lever (default from WorldConfig)")
    parser.add_argument("--out", default=None, help="Run file path. Default: runs/<run_id>.jsonl")
    parser.add_argument("--twice", action="store_true", help="Run again to a second file and compare trail digests.")
    parser.add_argument("--html", action="store_true", help="Render the map viewer next to the run file.")
    return parser


def config_from(args: argparse.Namespace) -> WorldConfig:
    levers: dict[str, Any] = {lever: getattr(args, lever) for lever in LEVERS if getattr(args, lever) is not None}
    return WorldConfig(seed=args.seed, **levers)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ticks < 1:
        sys.stderr.write("error: ticks must be positive\n")
        return 2
    try:
        config = config_from(args)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    run_id = run_id_for(config, args.ticks)
    path = Path(args.out) if args.out else DEFAULT_RUNS_DIR / f"{run_id}.jsonl"
    if path.exists():
        sys.stderr.write(f"error: {path} exists; a run file is never overwritten\n")
        return 2
    result = run_world(config, args.ticks, path)
    checked = read_run(path)
    lines = [
        "V3 checkpoint run (world)",
        f"run_id: {run_id}",
        f"file: {path}",
        f"ticks: {result.ticks}",
        f"trail_digest: {result.trail_digest}",
        f"final_state_digest: {result.final_state_digest}",
        f"final_overlay_digest: {result.final_overlay_digest}",
        f"survivors: {result.survivors}  deaths: {result.deaths}",
        f"file_verifies: {'yes' if checked.complete else 'no'}",
        f"tick_ms_mean: {result.tick_ms_mean:.3f}",
        f"tick_ms_p95: {result.tick_ms_p95:.3f}",
        f"tick_ms_max: {result.tick_ms_max:.3f}",
    ]
    for problem in checked.problems:
        lines.append(f"problem: {problem}")
    if args.twice:
        second_path = path.with_name(path.stem + ".rerun" + path.suffix)
        if second_path.exists():
            sys.stderr.write(f"error: {second_path} exists\n")
            return 2
        second = run_world(config, args.ticks, second_path)
        identical = second.trail_digest == result.trail_digest
        lines.append(f"rerun_file: {second_path}")
        lines.append(f"determinism: {'identical' if identical else 'DIFFERENT'}")
        if not identical:
            sys.stdout.write("\n".join(lines) + "\n")
            return 1
    if args.html:
        from world.viewer import render_html
        html_path = path.with_suffix(".html")
        html_path.write_text(render_html(checked), encoding="utf-8")
        lines.append(f"viewer: {html_path}")
    lines.append("note: exploration output under OD-009; not evidence, not acceptance")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if checked.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
