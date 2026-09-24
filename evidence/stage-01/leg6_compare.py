"""Read-only leg-6 comparison of the three declared files and leg-5 control.

Run from the repository root: py -3 -B -m evidence.stage-01.leg6_compare
No simulation, selection, scoring, tuning or new evidence format lives here.
"""

import json
from pathlib import Path

from stream.run_file import read_run


def counts(run):
    start = run.header["world"]
    emergency = denied = yields = 0
    choices = []
    contested = []
    fatal_claims = []
    source = run.header["scenario"]["source_position"]
    for tick in run.ticks:
        emergency += sum(h >= run.header["scenario"]["emergency_at"]
                         for actor, h in start["hunger"].items() if actor not in start["died_at"])
        yields += sum(d["kind"] == "yield" for d in tick["decisions"].values())
        claims = [o for o in tick["record"]["outcomes"] if o["operation"] == "claim"]
        denied += sum(not o["accepted"] for o in claims)
        if len(claims) >= 2:
            contested.append({"tick": tick["tick"], "view": tick["tick"] + 1,
                              "rotation": tick["record"]["rotated_roster"],
                              "requests": {o["actor"]: tick["decisions"][o["actor"]]["amount"] for o in claims},
                              "outcomes": claims})
        for actor, d in tick["decisions"].items():
            if "go" in d.get("scores", {}) and "yield" in d.get("scores", {}):
                ob = tick["observations"][actor]
                choices.append({"tick": tick["tick"], "view": tick["tick"] + 1, "actor": actor,
                                "hunger": start["hunger"][actor], "yield_at": start["yield_at"][actor],
                                # `sees` (identities; positions from the tick-start world) since
                                # 2026-09-25, `others` (with positions) in older files
                                "seen_crowd": (sum(start["positions"][q] == source for q in ob["sees"]) if "sees" in ob
                                               else sum(o["at"] == source for o in ob["others"])),
                                "observed_stock": ob.get("source_food"), "decision": d,
                                "from": start["positions"][actor], "to": tick["world"]["positions"][actor],
                                "hunger_after": tick["world"]["hunger"][actor]})
        for o in claims:
            actor = o["actor"]
            if o["accepted"] and actor not in start["died_at"] and actor in tick["world"]["died_at"]:
                fatal_claims.append({"actor": actor, "claim_tick": tick["tick"],
                                     "died_at": tick["world"]["died_at"][actor],
                                     "hunger_before": start["hunger"][actor],
                                     "food_after": tick["state"]["balances"][actor]})
        start = tick["world"]
    return {"survivors": sorted(set(start["positions"]) - set(start["died_at"])),
            "deaths": start["died_at"], "denied_claims": denied,
            "emergency_person_ticks": emergency, "yield_events": yields,
            "scored_choices": choices, "go_over_yield": sum(c["decision"]["kind"] == "go" for c in choices),
            "contested": contested, "fatal_accepted_claims": fatal_claims}


def content(path):
    return [line for line in path.read_bytes().splitlines() if json.loads(line)["kind"] != "timing"]


def main():
    paths = {mode: Path(f"runs/leg6-20260922-seed7-300-{mode}.jsonl") for mode in ("on", "on-repeat", "off")}
    paths["leg5"] = Path("runs/one-source-grid-seed7-ticks300-yieldon.jsonl")
    runs = {name: read_run(path) for name, path in paths.items()}
    assert all(run.complete and len(run.ticks) == 300 for run in runs.values())
    on, repeat, off, old = (runs[key] for key in ("on", "on-repeat", "off", "leg5"))
    # Physical values, native observations and settlement, not digest differences.
    trajectory_keys = ("world", "state", "availability", "production", "observations", "record")
    control = {
        "off_decisions_equal_leg5": [t["decisions"] for t in off.ticks] == [t["decisions"] for t in old.ticks],
        "off_trajectory_equal_leg5": all(a.get(key) == b.get(key) for a, b in zip(off.ticks, old.ticks) for key in trajectory_keys),
        "off_genesis_equal_leg5": all(off.header[key] == old.header[key] for key in ("genesis", "world")),
        "on_repeat_canonical_bytes_equal_excluding_timing": content(paths["on"]) == content(paths["on-repeat"]),
    }
    result = {"checks": control, "runs": {key: counts(run) for key, run in runs.items() if key != "on-repeat"}}
    result["timing_ms_excludes_stream_writes"] = {}
    for key, run in runs.items():
        timing = sorted(run.timings.values())
        result["timing_ms_excludes_stream_writes"][key] = {
            "mean": sum(timing) / len(timing) / 1e6,
            "p95": timing[min(len(timing) - 1, int(len(timing) * .95))] / 1e6,
            "max": timing[-1] / 1e6,
        }
    print(json.dumps(result, indent=2))
    assert all(control.values()), control
    assert result["runs"]["on"]["scored_choices"], "required scored choice absent; do not tune"
    assert result["runs"]["on"]["contested"], "required contention absent; do not tune"


if __name__ == "__main__":
    main()
