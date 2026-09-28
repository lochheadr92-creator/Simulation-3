"""Estimate vs actual arrival under terrain-aware departure."""
from dataclasses import replace
from unittest import mock
from kernel import Engine
from world.config import WorldConfig, genesis
import world.config as wc
from world.decide import food_travel_ticks, decide
from world.observe import observe
from world.run import world_step

def cfg_for(**ch):
    return WorldConfig(seed=1, actors=1, width=9, height=9, food_sources=1,
        water_on=False, warmth_on=False, offers_on=False, births_on=False,
        childhood_on=False, building_on=False, stagger_start=False,
        shelter_pct=0, rough_pct=0, starting_food=0,
        claim_amount=1, source_stock=8, source_cap=8, renewal_every=5, **({"perception_radius":1}|ch))

def run_case(label, rough_cells, home, hunger0, terrain_memory=(), **ch):
    cfg = cfg_for(**ch)
    ledger, world = genesis(cfg)
    src = cfg.source_position
    world = replace(world, homes={"p01": home}, positions={"p01": home}, hunger={"p01": hunger0},
                    terrain_memory={"p01": tuple(terrain_memory)} if terrain_memory else {})
    with mock.patch.object(wc, "_terrain_of", lambda c: (tuple(rough_cells), ())):
        engine, ov = Engine(ledger), world
        left = None; est = None; arrive = None; hunger_at_arrival = None; path=[]
        for t in range(80):
            step = world_step(engine, ov, cfg)
            v = step.views["p01"]; d = step.decisions["p01"]
            if left is None and d.kind == "go":
                left = ov.tick; est = food_travel_ticks(v, cfg); hleft = v.hunger
            if left is not None and v.position == src and arrive is None:
                arrive = ov.tick; hunger_at_arrival = v.hunger
            path.append((ov.tick, v.position, v.hunger, d.kind, v.held))
            if arrive is not None: break
            ov, engine = step.processed.overlay, step.engine
    actual = None if arrive is None else arrive - left
    print(f"{label}: src={src} left@{left} hunger={hleft if left is not None else None} est={est} actual={actual} arrival_hunger={hunger_at_arrival} hungry_at={cfg.hungry_at}")
    return path

src = cfg_for().source_position
print("source at", src)
# Case 1: open ground, straight line
home = (src[0]-4, src[1])
run_case("open", [], home, 0)
# Case 2: one rough cell directly on path (unknown at departure, radius 1: seen only when adjacent)
run_case("1 rough unseen", [(src[0]-2, src[1])], home, 0)
# Case 3: same rough but remembered
run_case("1 rough remembered", [(src[0]-2, src[1])], home, 0, terrain_memory=[(src[0]-2, src[1])])
# Case 4: wall of 3 rough remembered -> detour
wall = [(src[0]-2, src[1]-1), (src[0]-2, src[1]), (src[0]-2, src[1]+1)]
run_case("wall remembered", wall, home, 0, terrain_memory=wall)
# Case 5: wall seen at departure (adjacent) but not remembered; radius 1; home right next to wall
run_case("wall adjacent seen", wall, (src[0]-3, src[1]), 0)
# Case 6: hunger_rate 2
run_case("open rate2", [], home, 0, hunger_rate=2)
run_case("1 rough remembered rate2", [(src[0]-2, src[1])], home, 0, terrain_memory=[(src[0]-2, src[1])], hunger_rate=2)
# Case 7: standing on rough cell at start (held 0)
home2 = (src[0]-3, src[1])
p = run_case("start on rough (unknown)", [home2], home2, 0)
# Case 8: start held=1 on rough
cfg = cfg_for(); ledger, world = genesis(cfg)

print("--- long wall (7 cells) remembered: detour expected")
wall7 = [(src[0]-2, y) for y in range(0, 8)]  # leaves only y=8 open
p = run_case("wall7 remembered r1", wall7, home, 0, terrain_memory=wall7)
print([x for x in p if x[3]=='go'][:12])
p = run_case("wall7 remembered r3", wall7, home, 0, terrain_memory=wall7, perception_radius=3)
p = run_case("wall7 seen r3 (not remembered)", wall7, home, 0, perception_radius=3)
print([x for x in p if x[3]=='go'][:12])
# partially remembered wall: only middle 3 known; detour route runs into unknown rough
p = run_case("wall7 partially remembered r1", wall7, home, 0, terrain_memory=wall7[2:5])
print([x for x in p if x[3]=='go'][:14])
# held at departure: person standing on rough with held=1
cfg = cfg_for(); ledger, world = genesis(cfg)
rough = [(src[0]-3, src[1])]
world = replace(world, homes={"p01": (src[0]-3, src[1])}, positions={"p01": (src[0]-3, src[1])}, hunger={"p01": 20}, held={"p01": 1})
with mock.patch.object(wc, "_terrain_of", lambda c: (tuple(rough), ())):
    v = observe("p01", ledger, world, cfg)
    print("held=1 on rough: est", food_travel_ticks(v, cfg), "decide", decide(v, cfg).kind, "hunger", v.hunger)
    engine, ov = Engine(ledger), world
    for t in range(10):
        s = world_step(engine, ov, cfg); v = s.views["p01"]
        print("  ", ov.tick, v.position, v.hunger, v.held, s.decisions["p01"].kind, food_travel_ticks(v,cfg))
        if v.position == src: break
        ov, engine = s.processed.overlay, s.engine
