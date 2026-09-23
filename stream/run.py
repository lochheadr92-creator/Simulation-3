"""Run a seeded scenario, write its record stream, and check it reproduces.

    py -3 -B -m stream.run --seed 7 --ticks 200
    py -3 -B -m stream.run --seed 7 --ticks 200 --twice     # determinism check
    py -3 -B -m stream.run --seed 7 --ticks 200 --html      # also render the viewer
    py -3 -B -m stream.run --replay runs/<file>.jsonl        # slice 1c: replay against the file

Output goes to runs/<run_id>.jsonl (and .html). runs/ is ignored by git: a
checkpoint run is exploration output, not evidence. The per-tick timing lines
are the visible cost signal until slice 1d measures cost. Every run file is
sealed (v3.stream.3) and records the proposals submitted each tick.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from kernel import Engine

from stream.run_file import RunFileError, RunWriter, read_run
from stream.scenario import ProposalGenerator, Scenario

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def run_id_for(scenario: Scenario, ticks: int) -> str:
    return f"{scenario.describe()['name']}-seed{scenario.seed}-ticks{ticks}"


def run_scenario(scenario: Scenario, ticks: int, path: Path) -> dict:
    """Run `ticks` ticks from the scenario genesis, streaming every record."""
    engine = Engine(scenario.genesis())
    generator = ProposalGenerator(scenario)
    elapsed: list[int] = []
    with RunWriter(path, run_id=run_id_for(scenario, ticks), genesis=engine.state, scenario=scenario.describe(),
                   horizon=ticks) as writer:
        for _ in range(ticks):
            live = {action: reservation.actor for action, reservation in engine.state.reservations.items()}
            proposals = generator.tick(engine.state.tick, live)
            started = time.perf_counter_ns()
            record = engine.tick(proposals)
            cost = time.perf_counter_ns() - started
            elapsed.append(cost)
            writer.record(record, engine.state, inputs=proposals, elapsed_ns=cost)
        trail = writer.close()
    ordered = sorted(elapsed) or [0]
    return {
        "path": path, "trail_digest": trail, "ticks": ticks,
        "final_state_digest": engine.state.digest(),
        "tick_ms_mean": sum(ordered) / len(ordered) / 1e6,
        "tick_ms_p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] / 1e6,
        "tick_ms_max": ordered[-1] / 1e6,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a seeded checkpoint scenario and write its record stream.")
    parser.add_argument("--seed", type=int, default=None, help="Required unless --replay is given.")
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--actors", type=int, default=6)
    parser.add_argument("--sources", type=int, default=2)
    parser.add_argument("--out", default=None, help="Run file path. Default: runs/<run_id>.jsonl")
    parser.add_argument("--twice", action="store_true", help="Run again to a second file and compare trail digests.")
    parser.add_argument("--html", action="store_true", help="Render the viewer next to the run file.")
    parser.add_argument("--replay", default=None, metavar="FILE",
                        help="Replay a sealed scenario run from its header genesis and recorded inputs, "
                             "checked against the file (slice 1c).")
    return parser


def replay_main(path: Path) -> int:
    from stream.replay import ReplayError, replay_lines, replay_scenario
    try:
        result = replay_scenario(path)
    except (ReplayError, RunFileError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    sys.stdout.write("\n".join(replay_lines(result)) + "\n")
    return 0 if result.identical else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.replay:
        return replay_main(Path(args.replay))
    if args.seed is None:
        sys.stderr.write("error: --seed is required unless --replay is given\n")
        return 2
    if args.ticks < 1 or args.actors < 1 or args.sources < 1:
        sys.stderr.write("error: ticks, actors and sources must be positive\n")
        return 2
    scenario = Scenario(seed=args.seed, actors=args.actors, sources=args.sources)
    run_id = run_id_for(scenario, args.ticks)
    path = Path(args.out) if args.out else DEFAULT_RUNS_DIR / f"{run_id}.jsonl"
    if path.exists():
        sys.stderr.write(f"error: {path} exists; a run file is never overwritten\n")
        return 2
    result = run_scenario(scenario, args.ticks, path)
    checked = read_run(path)
    lines = [
        "V3 checkpoint run",
        f"run_id: {run_id}",
        f"file: {path}",
        f"ticks: {result['ticks']}",
        f"trail_digest: {result['trail_digest']}",
        f"final_state_digest: {result['final_state_digest']}",
        f"file_verifies: {'yes' if checked.complete else 'no'}",
        f"tick_ms_mean: {result['tick_ms_mean']:.3f}",
        f"tick_ms_p95: {result['tick_ms_p95']:.3f}",
        f"tick_ms_max: {result['tick_ms_max']:.3f}",
    ]
    for problem in checked.problems:
        lines.append(f"problem: {problem}")
    if args.twice:
        second_path = path.with_name(path.stem + ".rerun" + path.suffix)
        if second_path.exists():
            sys.stderr.write(f"error: {second_path} exists\n")
            return 2
        second = run_scenario(scenario, args.ticks, second_path)
        identical = second["trail_digest"] == result["trail_digest"]
        lines.append(f"rerun_file: {second_path}")
        lines.append(f"determinism: {'identical' if identical else 'DIFFERENT'}")
        if not identical:
            sys.stdout.write("\n".join(lines) + "\n")
            return 1
    if args.html:
        from stream.viewer import render_html
        html_path = path.with_suffix(".html")
        html_path.write_text(render_html(checked), encoding="utf-8")
        lines.append(f"viewer: {html_path}")
    lines.append("note: exploration output under OD-009; not evidence, not acceptance")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if checked.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
