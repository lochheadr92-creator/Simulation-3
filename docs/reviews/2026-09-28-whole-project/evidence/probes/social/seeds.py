import sys, tempfile, pathlib
from world.config import WorldConfig
from world.run import run_world
from world.viewer_index import build_index
from stream.run_file import read_run

seed = int(sys.argv[1]); horizon = int(sys.argv[2])
tmp = pathlib.Path(tempfile.mkdtemp())
path = tmp / f"s{seed}.jsonl"
run_world(WorldConfig(seed=seed), horizon, path)
run = read_run(path)
events = build_index(run)["events"]
helpers = [e for e in events if e["kind"] == "remembered_helper"]
helped = 0; gifts = 0; gift_ticks = []
memory_nonempty = 0
for t in run.ticks:
    for a, d in t.get("decisions", {}).items():
        if d.get("helped_at") is not None:
            helped += 1
    for o in t["record"]["outcomes"]:
        if o["operation"] == "transfer" and o["accepted"] and any(e["account"].startswith("actor:") and e["delta"] > 0 for e in o["effects"]):
            gifts += 1; gift_ticks.append(t["tick"])
    if t["world"].get("food_memory"):
        memory_nonempty += 1
alive = len([p for p in run.ticks[-1]["world"]["positions"] if p not in run.ticks[-1]["world"].get("died_at", {})])
print(f"seed={seed} horizon={horizon} remembered_helper_events={len(helpers)} helped_at_decisions={helped} accepted_person_gifts={gifts} ticks_with_food_memory={memory_nonempty} roster={len(run.ticks[-1]['world']['positions'])} alive={alive}")
print("gift ticks:", gift_ticks[:40])
for e in helpers[:10]: print("  ", e)
