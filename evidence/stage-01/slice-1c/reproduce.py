"""Reproduce the slice 1c frozen references and checks (the reviewer's command).

    py -3 -B evidence/stage-01/slice-1c/reproduce.py

Run it from a checkout of the commit that added this folder. It writes only
into a new temporary folder, prints each check, and exits 0 only when all hold:
  1. SHA256SUMS.txt matches the two frozen files;
  2. each frozen file verifies, is sealed through its last tick, and names the
     live code's identity;
  3. each frozen file replays identically against the live code;
  4. running each configuration again gives identical content lines (header,
     ticks and end, seals included; timing lines excluded);
  5. the scenario reference cut at the declared tick (the first tick at or
     after 40 holding at least one live reservation) recovers to identical
     content lines, and so does the world reference cut after tick 60.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from stream.recover import recover_scenario  # noqa: E402
from stream.replay import replay_scenario  # noqa: E402
from stream.run import run_scenario  # noqa: E402
from stream.run_file import code_identity, read_run  # noqa: E402
from stream.scenario import Scenario  # noqa: E402
from world.config import WorldConfig  # noqa: E402
from world.recover import recover_world  # noqa: E402
from world.replay import replay_world  # noqa: E402
from world.run import run_world  # noqa: E402

HERE = Path(__file__).resolve().parent
SCENARIO = HERE / "scenario-seed7-ticks120.jsonl"
WORLD = HERE / "world-seed7-ticks120.jsonl"
WORLD_CUT = 60


def content(path: Path) -> list[bytes]:
    """Every line except timing lines."""
    return [line for line in path.read_bytes().splitlines(keepends=True) if b'"kind":"timing"' not in line]


def cut_after(source: Path, tick: int, dest: Path) -> Path:
    lines = source.read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if b'"kind":"tick"' in line and json.loads(line)["tick"] == tick)
    dest.write_bytes(b"".join(lines[: index + 1]))
    return dest


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="sim3-1c-reproduce-"))
    results: list[bool] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))

    sums = {}
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        value, name = line.split(maxsplit=1)
        sums[name.strip().lstrip("*")] = value
    for path in (SCENARIO, WORLD):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        check(f"sha256 {path.name}", sums.get(path.name) == actual, actual)

    live = code_identity()["digest"]
    for path in (SCENARIO, WORLD):
        run = read_run(path)
        sealed = run.complete and run.sealed and bool(run.ticks) and run.last_sealed_tick == run.ticks[-1]["tick"]
        check(f"verifies and is sealed through its last tick: {path.name}", sealed,
              f"final_seal {run.end['final_seal'] if run.end else None}")
        check(f"code identity is the live code's: {path.name}", run.header["code_identity"]["digest"] == live, live)

    for path, replay in ((SCENARIO, replay_scenario), (WORLD, replay_world)):
        result = replay(path)
        check(f"replay identical: {path.name}", result.identical and result.ticks == 120, f"{result.ticks} ticks")

    again_scenario = work / "scenario-again.jsonl"
    run_scenario(Scenario(seed=7), 120, again_scenario)
    again_world = work / "world-again.jsonl"
    run_world(WorldConfig(seed=7), 120, again_world)
    for frozen, again in ((SCENARIO, again_scenario), (WORLD, again_world)):
        check(f"run again, content lines identical: {frozen.name}", content(frozen) == content(again),
              f"final_seal {read_run(again).end['final_seal']}")

    cut_tick = next(t["tick"] for t in read_run(SCENARIO).ticks if t["tick"] >= 40 and t["state"]["reservations"])
    result = recover_scenario(cut_after(SCENARIO, cut_tick, work / "scenario-cut.jsonl"),
                              work / "scenario-recovered.jsonl")
    check("scenario recovery, content lines identical",
          content(work / "scenario-recovered.jsonl") == content(SCENARIO),
          f"cut after tick {cut_tick}, live holds at the cut {result.live_holds_at_cut}, resumed {result.resumed}")
    result = recover_world(cut_after(WORLD, WORLD_CUT, work / "world-cut.jsonl"), work / "world-recovered.jsonl")
    check("world recovery, content lines identical", content(work / "world-recovered.jsonl") == content(WORLD),
          f"cut after tick {WORLD_CUT}, resumed {result.resumed}")

    print(f"{sum(results)} of {len(results)} checks passed; work folder {work}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
