import random, json, dataclasses, itertools, sys
from world.config import WorldConfig

def try_cfg(label, **kw):
    try:
        c = WorldConfig(**kw)
        return f"ACCEPTED  {label}: {kw}"
    except Exception as e:
        return f"rejected  {label}: {type(e).__name__}: {str(e)[:90]}"

print("== forbidden combinations")
for label, kw in [
    ("provisioning w/o stores", dict(seed=1, provisioning_on=True)),
    ("coordination w/o provisioning", dict(seed=1, coordination_on=True, stores_on=True)),
    ("homes w/o childhood", dict(seed=1, homes_on=True, childhood_on=False)),
    ("relocation w/o homes", dict(seed=1, relocation_on=True)),
    ("knowledge_sharing w/o source_memory", dict(seed=1, knowledge_sharing_on=True)),
    ("wood w/o building", dict(seed=1, wood_on=True, building_on=False)),
    ("adjacent_requests w/o requests", dict(seed=1, adjacent_requests=True)),
    ("scoring + water", dict(seed=1, scoring_on=True)),
    ("scoring + warmth only", dict(seed=1, scoring_on=True, water_on=False)),
    ("scoring + requests", dict(seed=1, scoring_on=True, water_on=False, warmth_on=False, requests_on=True)),
    ("births w/o childhood", dict(seed=1, births_on=True, childhood_on=False)),
    ("childhood w/o births", dict(seed=1, births_on=False, childhood_on=True)),
    ("homes+stores w/o provisioning", dict(seed=1, homes_on=True, stores_on=True)),
    ("regrowth w/ renewal_amount=0", dict(seed=1, regrowth_on=True, renewal_amount=0)),
    ("seasons w/o regrowth", dict(seed=1, seasons_on=True)),
]:
    print(try_cfg(label, **kw))

print("== booleans where ints required")
for lever in ("seed", "width", "actors", "starting_food", "source_stock", "renewal_amount", "hunger_rate",
              "perception_radius", "birth_spacing", "cold_rate", "starting_water", "adult_at", "child_leash",
              "together_ticks", "build_ticks", "rough_pct", "shelter_relief", "food_sources"):
    kw = {"seed": 1}; kw[lever] = True
    print(try_cfg(f"{lever}=True", **kw))

print("== zero / negative / odd values")
for label, kw in [
    ("perception_radius=0", dict(seed=1, perception_radius=0)),
    ("hunger_rate=0", dict(seed=1, hunger_rate=0)),
    ("actors=0", dict(seed=1, actors=0)),
    ("width=1", dict(seed=1, width=1)),
    ("width=3 height=3 actors=6 (capacity)", dict(seed=1, width=3, height=3, actors=6)),
    ("adult_at=0", dict(seed=1, adult_at=0)),
    ("adult_at=-5", dict(seed=1, adult_at=-5)),
    ("child_leash=-1", dict(seed=1, child_leash=-1)),
    ("together_ticks=0", dict(seed=1, together_ticks=0)),
    ("together_ticks=-1", dict(seed=1, together_ticks=-1)),
    ("build_ticks=0 building on", dict(seed=1, build_ticks=0)),
    ("claim_amount=0", dict(seed=1, claim_amount=0)),
    ("seed=-1", dict(seed=-1)),
    ("seed='7'", dict(seed="7")),
    ("width='12'", dict(seed=1, width="12")),
    ("yield_set=[]", dict(seed=1, yield_set=())),
    ("yield_set=(0,)", dict(seed=1, yield_set=(0,))),
    ("food_sources=3", dict(seed=1, food_sources=3)),
    ("water_sources=0", dict(seed=1, water_sources=0)),
    ("hungry_at=death_at", dict(seed=1, hungry_at=80, emergency_at=80)),
    ("shelter_pct=0 rough_pct=90", dict(seed=1, rough_pct=90, shelter_pct=0)),
    ("cold_at > cold_emergency_at", dict(seed=1, cold_at=60, cold_emergency_at=50)),
    ("water_stock > water_cap", dict(seed=1, water_stock=20, water_cap=12)),
]:
    print(try_cfg(label, **kw))

print("== from_describe: unknown key, legacy header")
c = WorldConfig(seed=3)
d = c.describe(); d["extra_key"] = 1
try: WorldConfig.from_describe(d); print("unknown key ACCEPTED")
except Exception as e: print("unknown key rejected:", str(e)[:80])
d = c.describe(); d["perception_radius"] = True
try: WorldConfig.from_describe(d); print("perception_radius=true ACCEPTED")
except Exception as e: print("perception_radius=true rejected:", str(e)[:80])
# legacy: drop every key introduced by a switch
legacy = {k: v for k, v in WorldConfig(seed=3, **{f: False for f in ("water_on","warmth_on","terrain_on","building_on","offers_on","social_memory_on","births_on","childhood_on","stagger_start","plan_trips")}).describe().items()}
print("legacy keys:", sorted(legacy)[:6], "... n=", len(legacy))
c2 = WorldConfig.from_describe(legacy); print("legacy round trip ok:", c2.describe() == legacy)

print("== fuzz: from_describe(describe(cfg)) == cfg")
BOOLS = [f.name for f in dataclasses.fields(WorldConfig) if f.type == "bool"]
INTS = ["birth_spacing", "adult_at", "child_leash", "together_ticks", "build_ticks", "rough_pct", "shelter_pct",
        "shelter_relief", "cold_rate", "warming", "starting_water", "water_stock", "renewal_every", "perception_radius",
        "hungry_at", "food_sources", "water_sources", "actors", "width", "height"]
rng = random.Random(1)
ok = coll = built = 0; fails = {}
collisions = {}
for i in range(600):
    kw = {"seed": rng.randint(0, 999)}
    for b in BOOLS:
        if rng.random() < 0.5: kw[b] = rng.random() < 0.5
    for n in INTS:
        if rng.random() < 0.3: kw[n] = rng.randint(0, 40)
    try: c = WorldConfig(**kw)
    except ValueError: continue
    built += 1
    d = c.describe()
    try:
        back = WorldConfig.from_describe(json.loads(json.dumps(d)))
    except Exception as e:
        fails.setdefault("from_describe error", []).append((kw, str(e)[:100])); continue
    if back == c: ok += 1
    else:
        diff = {f.name: (getattr(c, f.name), getattr(back, f.name)) for f in dataclasses.fields(WorldConfig) if getattr(c, f.name) != getattr(back, f.name)}
        fails.setdefault("roundtrip !=", []).append(diff)
    key = json.dumps(d, sort_keys=True)
    if key in collisions and collisions[key] != c:
        coll += 1
    collisions[key] = c
print(f"built {built}, equal {ok}, from_describe errors {len(fails.get('from_describe error', []))}, roundtrip-unequal {len(fails.get('roundtrip !=', []))}, describe collisions {coll}")
for e in fails.get("from_describe error", [])[:5]: print("  ERR", e)
import collections
diffkeys = collections.Counter(k for d in fails.get("roundtrip !=", []) for k in d)
print("  levers lost in round trip:", dict(diffkeys))
