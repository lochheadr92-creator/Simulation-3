from dataclasses import replace
from kernel import Engine
from world.config import WorldConfig, genesis
from world.observe import observe
from world.run import world_step
from world.storage import FOOD_EXPECT_TICKS, food_expectation

def house():
    cfg = WorldConfig(seed=7, actors=2, stores_on=True, homes_on=True,
                      provisioning_on=True, coordination_on=True, terrain_on=False,
                      water_on=False, births_on=False, offers_on=False, renewal_every=1000)
    ledger, world = genesis(cfg)
    source = cfg.food_positions()[0]
    home = (source[0]-2, source[1])
    homes = {p: home for p in world.roster}
    ledger = replace(ledger, balances={p: 1 for p in world.roster})
    world = replace(world, homes=homes, positions=homes, shelters=(home,),
                    home_caches={"store-p01": home}, hunger={p: 0 for p in homes}, cold={"p01": 0, "p02": 3})
    return cfg, ledger, world

print("== 1: expectation timer: heard at 1; check ticks 12,13 with no other evidence")
mem = ("p01", 1)
for t in (12, 13, 14):
    print(f"  tick {t}: {food_expectation(mem, t, (0,0), (), None)}")

print("== 2: speaker dies during trip: expectation cleared?")
cfg, ledger, world = house()
first = world_step(Engine(ledger), world, cfg)
print("  after tick1:", dict(first.processed.overlay.food_expected))
dead = replace(first.processed.overlay, died_at={"p01": 1})
second = world_step(first.engine, dead, cfg)
print("  p01 dead ->", dict(second.processed.overlay.food_expected), "p02 decision:", second.decisions["p02"].kind, second.decisions["p02"].waiting_for_food)
# keep going: does p02 keep waiting until timer runs out?
ov, eng = second.processed.overlay, second.engine
for i in range(12):
    s = world_step(eng, ov, cfg)
    if s.decisions["p02"].waiting_for_food is None:
        print("  p02 stopped waiting at tick", ov.tick, "reason:", s.views['p02'].food_expectation_end); break
    ov, eng = s.processed.overlay, s.engine

print("== 3: 'two meals in cache ends expectation' uses observed (at-home) or true stock?")
cfg, ledger, world = house()
first = world_step(Engine(ledger), world, cfg)
# secretly stock p01's cache to 5; p02 away from home (cannot see cache)
stocked = replace(first.engine.state, sources={s: replace(v, stock=5) if s=="store-p01" else v for s,v in first.engine.state.sources.items()})
home = world.homes["p02"]
away = replace(first.processed.overlay, positions=dict(first.processed.overlay.positions, p02=(home[0], home[1]-2)))
v_away = observe("p02", stocked, away, cfg)
v_home = observe("p02", stocked, first.processed.overlay, cfg)
print("  away: expected", v_away.food_expected, v_away.food_expectation_end, "| at home:", v_home.food_expected, v_home.food_expectation_end)

print("== 4: announce without departing (trip denied)? provisioning decision 'gather' at home when source is adjacent? kind could be WAIT/CLAIM if standing on site; here GO. Can decision be GO with step==position?")
# case: p01 at home, cache low, food<=1, source in view but empty -> provision_source? kind GO with step. If cold>0 -> WARM (no announce). ok.
# Try: p01 is a child?  is_child returns choice before announce. Try: p01 standing ON the source cell as home (homes cannot be on source). Skip.
# Try: p01 home cache low but p01 itself in emergency hunger and target other: _provision_decision is applied how?
import inspect, world.decide as d
src = inspect.getsource(d._decide)
i = src.find("_provision_decision"); print("  _provision_decision call context:\n   ", src[max(0,i-400):i+120].replace("\n","\n    "))

print("== 5: listener moves home during expectation -> cleared? (homes_on: home change)")
cfg, ledger, world = house()
first = world_step(Engine(ledger), world, cfg)
moved = replace(first.processed.overlay, homes=dict(first.processed.overlay.homes, p02=(0,0)))
s = world_step(first.engine, moved, cfg)
print("  ", dict(s.processed.overlay.food_expected))

print("== 6: speaker returns home WITH food but does not deposit yet (food>1) -> expectation continues; returns with food<=1 -> ends. What if speaker returns with 2 food, listener sees 'housemate returned' nothing; fine. Speaker announces and is then interrupted by thirst for 12 ticks -> expectation expires; ok by design.")

print("== 7: listener also announces -> two housemates both waiting for each other?")
cfg, ledger, world = house()
# both p01 and p02 empty-handed... start_provisioning requires food<=1 and cache <2 -> both qualify at tick 0 if both cold==0
w = replace(world, cold={"p01": 0, "p02": 0})
s = world_step(Engine(ledger), w, cfg)
print("  decisions:", {p: (d.kind, d.announced_to, d.waiting_for_food) for p, d in s.decisions.items()})
print("  expected after:", dict(s.processed.overlay.food_expected))
s2 = world_step(s.engine, s.processed.overlay, cfg)
print("  tick2:", {p: (d.kind, d.provisioning, d.waiting_for_food) for p, d in s2.decisions.items()})
