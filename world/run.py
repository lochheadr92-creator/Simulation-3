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
  5. the tick line records the kernel record and state, the proposals
     submitted, the overlay, every decision, every observation, and any
     production, sealed (v3.stream.3); a timing line records wall-clock cost

Steps 1-4 are `world_step`, the one path both a run and its replay take.
    py -3 -B -m world.run --replay runs/<file>.jsonl   # slice 1c: replay against the file
    py -3 -B -m world.run --recover runs/<cut>.jsonl --out runs/<new>.jsonl   # slice 1c: recovery

Output goes to runs/<run_id>.jsonl (and .html). runs/ is ignored by git: a
run file is a saved world you can replay and watch.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel import Engine, Proposal, TickRecord, WorldState, claim, consume

from stream.run_file import RunFileError, RunWriter, read_run
from world.config import FOOD_SOURCE, WATER, WATER_SOURCE, WorldConfig, genesis
from world.decide import CLAIM, DRAW, DRINK, EAT, Decision, decide
from world.observe import Observation, observe
from world.overlay import Overlay

from world.process import Processed, advance

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def run_id_for(config: WorldConfig, ticks: int) -> str:
    mode = "on" if config.yield_on else "off"
    return f"{config.name}-seed{config.seed}-ticks{ticks}-yield{mode}" + ("-scoringon" if config.scoring_on else "") + ("-wateron" if config.water_on else "") + ("-warmthon" if config.warmth_on else "")


def proposals_for(decisions: dict[str, Decision], tick: int) -> list[Proposal]:
    out: list[Proposal] = []
    for actor in sorted(decisions):
        decision = decisions[actor]
        pid = f"t{tick}-{actor}"
        if decision.kind == EAT:
            out.append(consume(pid, actor, 0, amount=decision.amount))
        elif decision.kind == CLAIM:
            out.append(claim(pid, actor, 0, sources={decision.target or FOOD_SOURCE: decision.amount}))
        elif decision.kind == DRINK:
            out.append(consume(pid, actor, 0, amount=decision.amount, resource=WATER))
        elif decision.kind == DRAW:
            out.append(claim(pid, actor, 0, sources={decision.target or WATER_SOURCE: decision.amount},
                             resource=WATER))
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


@dataclass(frozen=True)
class WorldStep:
    """One tick of the world loop, before anything is written."""

    views: dict[str, Observation]
    decisions: dict[str, Decision]
    proposals: list[Proposal]
    record: TickRecord
    committed: WorldState          # what settlement committed
    processed: Processed           # the world processes applied after it
    engine: Engine                 # the engine the next tick runs on

    def line_fields(self) -> dict[str, Any]:
        """The world blocks of this tick's line, as the writer and replay take them."""
        return {
            "world": self.processed.overlay.canonical(),
            "decisions": {actor: d.canonical() for actor, d in self.decisions.items()},
            "observations": {actor: view.compact() for actor, view in self.views.items()},
            "production": list(self.processed.production) or None,
            "produced_state": self.processed.ledger,
        }


def world_step(engine: Engine, overlay: Overlay, config: WorldConfig) -> WorldStep:
    """Observe, decide, settle, process: one tick from `engine`'s state and `overlay`."""
    state = engine.state
    available = state.availability()
    views = {actor: observe(actor, state, overlay, config, available) for actor in overlay.living}
    decisions = {actor: decide(views[actor], config) for actor in overlay.living}
    proposals = proposals_for(decisions, state.tick)
    record = engine.tick(proposals)
    committed = engine.state
    processed = advance(overlay, decisions, record, committed, config)
    next_engine = Engine(processed.ledger) if processed.production else engine
    return WorldStep(views=views, decisions=decisions, proposals=proposals, record=record,
                     committed=committed, processed=processed, engine=next_engine)


def run_world(config: WorldConfig, ticks: int, path: Path) -> WorldRun:
    ledger, overlay = genesis(config)
    engine = Engine(ledger)
    elapsed: list[int] = []
    with RunWriter(path, run_id=run_id_for(config, ticks), genesis=ledger, scenario=config.describe(),
                   world=overlay.canonical(), horizon=ticks) as writer:
        for _ in range(ticks):
            started = time.perf_counter_ns()
            step = world_step(engine, overlay, config)
            cost = time.perf_counter_ns() - started
            elapsed.append(cost)
            writer.record(step.record, step.committed, inputs=step.proposals, elapsed_ns=cost,
                          **step.line_fields())
            overlay, engine = step.processed.overlay, step.engine
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
          "perception_radius", "food_sources", "water_sources")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a seeded grid world and write its record stream.")
    parser.add_argument("--seed", type=int, default=None, help="Required unless --replay is given.")
    parser.add_argument("--ticks", type=int, default=300)
    for lever in LEVERS:
        parser.add_argument(f"--{lever.replace('_', '-')}", type=int, default=None, help=f"world lever (default from WorldConfig)")
    parser.add_argument("--yield", dest="yield_mode", choices=("on", "off"), default="on",
                        help="crowd-yield trait on (default) or off (every yield_at = actors+1)")
    parser.add_argument("--out", default=None, help="Run file path. Default: runs/<run_id>.jsonl")
    parser.add_argument("--scoring", choices=("on", "off"), default="off",
                        help="score eligible personal actions (opt in); food allocation is unchanged")
    parser.add_argument("--water", choices=("on", "off"), default=None,
                        help="water and thirst as a second need (default on; off with --scoring on, "
                             "since scoring has no water actions yet)")
    parser.add_argument("--warmth", choices=("on", "off"), default=None,
                        help="cold as a third need, met by sheltering at home (default on; never with "
                             "--scoring on, since scoring has no warmth actions yet)")
    parser.add_argument("--terrain", choices=("on", "off"), default="on",
                        help="rough ground and shelter spots over the grid (default on)")
    parser.add_argument("--stagger", choices=("on", "off"), default="on",
                        help="spread starting hunger and thirst across the roster (default on) so people do "
                             "not all reach a need on the same tick")
    parser.add_argument("--trips", choices=("on", "off"), default="on",
                        help="leave for the source in time when holding no food (default on)")
    parser.add_argument("--twice", action="store_true", help="Run again to a second file and compare trail digests.")
    parser.add_argument("--html", action="store_true", help="Render the map viewer next to the run file.")
    parser.add_argument("--replay", default=None, metavar="FILE",
                        help="Replay a sealed world run from its header, recomputing every decision, "
                             "checked against the file (slice 1c).")
    parser.add_argument("--recover", default=None, metavar="FILE",
                        help="Recover a cut or broken sealed world run through its last sealed tick "
                             "into the new file given by --out (slice 1c).")
    return parser


def recover_main(path: Path, out: str | None) -> int:
    from stream.recover import RecoveryError, recovery_lines
    from world.recover import recover_world
    if not out:
        sys.stderr.write("error: --recover needs --out for the recovered file\n")
        return 2
    try:
        result = recover_world(path, Path(out))
    except (RecoveryError, RunFileError, ValueError, FileExistsError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    checked = read_run(Path(out))
    sys.stdout.write("\n".join(recovery_lines(result) + [f"file_verifies: {'yes' if checked.complete else 'no'}"]) + "\n")
    return 0 if checked.complete else 1


def replay_main(path: Path) -> int:
    from stream.replay import ReplayError, replay_lines
    from world.replay import replay_world
    try:
        result = replay_world(path)
    except (ReplayError, RunFileError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    sys.stdout.write("\n".join(replay_lines(result)) + "\n")
    return 0 if result.identical else 1


def config_from(args: argparse.Namespace) -> WorldConfig:
    levers: dict[str, Any] = {lever: getattr(args, lever) for lever in LEVERS if getattr(args, lever) is not None}
    levers["yield_on"] = args.yield_mode == "on"
    levers["scoring_on"] = args.scoring == "on"
    levers["plan_trips"] = args.trips == "on"
    levers["stagger_start"] = args.stagger == "on"
    levers["terrain_on"] = args.terrain == "on"
    water = args.water if args.water is not None else ("off" if args.scoring == "on" else "on")
    levers["water_on"] = water == "on"
    warmth = args.warmth if args.warmth is not None else ("off" if args.scoring == "on" else "on")
    levers["warmth_on"] = warmth == "on"
    return WorldConfig(seed=args.seed, **levers)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.recover:
        return recover_main(Path(args.recover), args.out)
    if args.replay:
        return replay_main(Path(args.replay))
    if args.seed is None:
        sys.stderr.write("error: --seed is required unless --replay or --recover is given\n")
        return 2
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
        f"yield: {config.describe()['yield']}",
        f"scoring: {config.describe()['scoring']}",
        f"yield_events: {sum(1 for tick in checked.ticks for d in tick.get('decisions', {}).values() if d.get('kind') == 'yield')}",
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
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if checked.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
