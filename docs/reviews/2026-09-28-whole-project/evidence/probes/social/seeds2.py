import sys, tempfile, pathlib
from world.config import WorldConfig
from world.run import run_world
from stream.run_file import read_run
seed = int(sys.argv[1]); horizon = int(sys.argv[2])
cfg = WorldConfig(seed=seed)
tmp = pathlib.Path(tempfile.mkdtemp()); path = tmp / f"s{seed}.jsonl"
run_world(cfg, horizon, path)
run = read_run(path)
offers = 0; offers_to_donor = 0; multi_starving = 0; starving_seen_by_holder_with_memory = 0
for t in run.ticks:
    w = t["world"]; mem = w.get("food_memory", {})
    hunger = w["hunger"]; died = w.get("died_at", {})
    for a, d in t.get("decisions", {}).items():
        if d["kind"] in ("offer", "go_offer"):
            offers += 1
            if d.get("target") in dict(mem.get(a, [])):
                offers_to_donor += 1
    for a, obs in t.get("observations", {}).items():
        sees = obs.get("sees", [])
        starving = [o for o in sees if hunger.get(o, 0) >= cfg.emergency_at]
        if len(starving) >= 2: multi_starving += 1
        if mem.get(a) and any(o in dict(mem[a]) for o in starving): starving_seen_by_holder_with_memory += 1
print(f"seed={seed}: offer/go_offer decisions={offers} to_remembered_donor={offers_to_donor} obs_with_2+_starving_in_view={multi_starving} obs_where_a_remembered_donor_is_starving_in_view={starving_seen_by_holder_with_memory}")
