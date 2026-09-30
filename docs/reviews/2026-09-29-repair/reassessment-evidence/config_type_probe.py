"""Reassessment probe: every int field x malformed types, every bool field x non-bool values."""
import sys; sys.path.insert(0,'.')
from dataclasses import fields, replace
from world.config import WorldConfig
base=WorldConfig(seed=7); acc=[]; rej=0
for f in fields(WorldConfig):
    if f.type in (int,"int"):
        for bad in (True, "7", 7.0, None):
            try: replace(base, **{f.name: bad}); acc.append((f.name, bad))
            except (ValueError, TypeError): rej+=1
    elif f.type=="bool":
        for bad in (1, "on", None):
            try: replace(base, **{f.name: bad}); acc.append((f.name, bad))
            except (ValueError, TypeError): rej+=1
for bad in ((True,), (1,"2"), "12", [1,2]):
    try: replace(base, yield_set=bad); acc.append(("yield_set", bad))
    except (ValueError, TypeError): rej+=1
print("rejected:", rej, "| still accepted:", acc)
for kw in (dict(seed=-1), dict(perception_radius=0), dict(hunger_rate=0), dict(seed=0)):
    c=replace(base, **kw); print("valid", kw, "round-trip:", WorldConfig.from_describe(c.describe())==c)
