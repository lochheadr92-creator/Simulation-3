import sys, tempfile, pathlib
from world.config import WorldConfig
from world.run import run_world
from stream.run_file import read_run
horizon = int(sys.argv[1])
for seed in map(int, sys.argv[2:]):
    tmp = pathlib.Path(tempfile.mkdtemp()); path = tmp / f"s{seed}.jsonl"
    run_world(WorldConfig(seed=seed), horizon, path)
    run = read_run(path)
    hits = [(t["tick"], a, d["target"], d["helped_at"]) for t in run.ticks for a, d in t.get("decisions", {}).items() if d.get("helped_at") is not None]
    print(f"seed={seed} helped_at_decisions={len(hits)} first={hits[:3]}", flush=True)
