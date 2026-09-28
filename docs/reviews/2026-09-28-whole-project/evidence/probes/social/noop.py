import tempfile, pathlib
from world.config import WorldConfig
from world.run import run_world
from stream.run_file import read_run
for seed in (11, 23):
    cfg = WorldConfig(seed=seed, source_memory_on=True, knowledge_sharing_on=True)  # homes_on default False
    p = pathlib.Path(tempfile.mkdtemp()) / "x.jsonl"
    run_world(cfg, 300, p); run = read_run(p)
    reports = sum(1 for t in run.ticks if t["world"].get("source_reports"))
    sightings = sum(1 for t in run.ticks if t["world"].get("food_sightings"))
    homes = run.ticks[-1]["world"]["homes"]
    print(f"seed {seed} homes_on=False: ticks_with_reports={reports} ticks_with_sightings={sightings} distinct_homes={len(set(map(tuple,homes.values())))}/{len(homes)}")
