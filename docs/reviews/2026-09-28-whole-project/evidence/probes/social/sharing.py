"""Attack the knowledge-sharing rules with direct fixtures."""
from dataclasses import replace
from kernel import Engine
from world.config import WorldConfig, genesis
from world.decide import decide
from world.foraging import usable_reports, update_reports, remember_sightings
from world.observe import observe
from world.overlay import Overlay
from world.run import world_step

def house(**cfgchanges):
    cfg = WorldConfig(seed=7, actors=3, source_memory_on=True, knowledge_sharing_on=True,
                      terrain_on=False, water_on=False, warmth_on=False, births_on=False,
                      offers_on=False, building_on=False,
                      renewal_every=1000, stagger_start=False, **({"perception_radius":1}|cfgchanges))
    ledger, world = genesis(cfg)
    source = cfg.source_position
    home = (source[0]-2, source[1])
    homes = {p: home for p in world.roster}
    ledger = replace(ledger, balances={p: 0 for p in world.roster},
                     sources={s: replace(v, stock=0) if s=='food' else v for s,v in ledger.sources.items()})
    world = replace(world, homes=homes, positions=dict(homes, p01=(source[0]-1, source[1]), p03=(0,0)),
                    hunger={p: 0 for p in world.roster}, held={p: 0 for p in world.roster})
    return cfg, ledger, world

print("== A: relay attempt A->B->C")
cfg, ledger, world = house()
src = cfg.source_position
# p01 sees food empty at tick 0 (adjacent to home where p02 stands). p03 far away.
s1 = world_step(Engine(ledger), world, cfg)
print(" after tick1 reports:", dict(s1.processed.overlay.source_reports))
# now move p02 next to p03, both at home; p01 far away
ov = replace(s1.processed.overlay, positions={"p01": (0,0), "p02": world.homes["p02"], "p03": (world.homes["p03"][0]-1, world.homes["p03"][1])})
s2 = world_step(s1.engine, ov, cfg)
print(" p02 decision source_report:", s2.decisions["p02"].source_report, "listeners", s2.views["p02"].report_listeners)
print(" p03 reports after relay attempt:", s2.processed.overlay.source_reports.get("p03"))

print("== B: speaker HEARD only (no firsthand) -> can they speak? via injected reports & empty food_sightings")
ov = replace(world, tick=3, positions={"p01": (0,0), "p02": world.homes["p02"], "p03": (world.homes["p03"][0]-1, world.homes["p03"][1])},
             source_reports={"p02": (("food","p01",0,1),)})
lg = replace(ledger, tick=3)
s = world_step(Engine(lg), ov, cfg)
print(" p02 source_report:", s.decisions["p02"].source_report, "-> p03 got:", s.processed.overlay.source_reports.get("p03"))

print("== C: expiry off-by-one. sighting tick 0, report (food,p01,0,1). Check ticks 19,20,21")
rep = (("food","p01",0,1),)
for t in (19,20,21):
    print(f" tick {t}: usable={usable_reports(rep, (), t)}")
print(" firsthand sighting at 0 remembered at tick 19/20:", remember_sightings((("food",0,0),),(),19), remember_sightings((("food",0,0),),(),20))
print(" empty_sources memory (source-memory) same rule: from foraging.remember_empty")
from world.foraging import remember_empty
print("  ", remember_empty((("food",0),),(),19), remember_empty((("food",0),),(),20))

print("== D: listener's own sighting same tick as report (who wins)")
print(" own sighting at 0 (stocked), report seen 0:", usable_reports(rep, (("food",1,0),), 1))
print(" own sighting at 0 (empty), report seen 0:", usable_reports(rep, (("food",0,0),), 1))

print("== E: hearing at tick t where listener saw source stocked THIS tick")
# p02 at source cell (stock>0), p01 adjacent with old firsthand empty sighting of food, tick 3
cfg2, lg2, w2 = house()
lg2 = replace(lg2, tick=3, sources={s: replace(v, stock=2) for s,v in lg2.sources.items()})
w2 = replace(w2, tick=3, homes={p: src for p in w2.roster} , positions={"p01": (src[0]-1, src[1]), "p02": src, "p03": (0,0)},
             food_sightings={"p01": (("food",0,2),)})
s = world_step(Engine(lg2), w2, cfg2)
print(" p01 speaks:", s.decisions["p01"].source_report, "to", s.decisions["p01"].report_to)
print(" p01 own view sightings now:", s.views["p01"].food_sightings)
print(" p02 reports next:", s.processed.overlay.source_reports.get("p02"), "p02 sightings:", s.processed.overlay.food_sightings.get("p02"))

print("== F: speaker with stale firsthand empty sighting but who CURRENTLY sees it stocked: does decide() still emit a report?")
# p01 adjacent to source sees stock 2 this tick; but food_sightings previous says empty at 2. remember_sightings overwrites with stocked -> no report. check
v = s.views["p01"]
print(" p01 sightings:", v.food_sightings, " report:", s.decisions["p01"].source_report)

print("== G: report retained after speaker dies")
cfg3, lg3, w3 = house()
s1 = world_step(Engine(lg3), w3, cfg3)
ov = replace(s1.processed.overlay, died_at={"p01": 1})
s2 = world_step(s1.engine, ov, cfg3)
print(" p02 reports with p01 dead:", s2.processed.overlay.source_reports.get("p02"))
print(" viewer/overlay validation with dead speaker ok:", Overlay.from_canonical(s2.processed.overlay.canonical()).source_reports.get("p02"))

print("== H: conflicting reports same tick, dict order dependence -> also tie-break by speaker id vs roster order")
cfg4, lg4, w4 = house()
w4 = replace(w4, tick=5, positions=w4.homes, food_sightings={"p01": (("food",0,3),), "p03": (("food",0,3),)})
views = {p: observe(p, replace(lg4, tick=5), w4, cfg4) for p in w4.living}
ch = {p: decide(v, cfg4) for p, v in views.items()}
a = update_reports(w4, ch, views, {}, 6)[1]
b = update_reports(w4, dict(reversed(list(ch.items()))), dict(reversed(list(views.items()))), {}, 6)[1]
print(" same:", a == b, a["p02"])

print("== I: disabled mode writes no fields")
off = replace(cfg4, knowledge_sharing_on=False)
s = world_step(Engine(lg4), replace(w4, tick=0, food_sightings={}), off)
print(" sightings/reports:", dict(s.processed.overlay.food_sightings), dict(s.processed.overlay.source_reports),
      "obs compact keys with report:", [k for k in s.views["p01"].compact() if "report" in k or "sight" in k])

print("== J: newborn fields")
cfg5 = replace(cfg4, births_on=True, together_ticks=1, childhood_on=True)
from world.process import _births
home = w4.homes["p01"]
parents = replace(s1.processed.overlay, positions=dict(w4.homes, p01=(home[0]+1, home[1])),
                  built={p: cfg5.build_ticks for p in w4.roster}, shelters=(home,), hunger={p:0 for p in w4.roster}, held={p:0 for p in w4.roster})
born, lg_b, prod = _births(parents, s1.engine.state, cfg5)
newb = [p for p in born.roster if p not in parents.roster]
print(" born:", newb, "reports for newborn:", [born.source_reports.get(p) for p in newb], "sightings:", [born.food_sightings.get(p) for p in newb])

print("== K: can a listener hear from a housemate who is adjacent but whom the listener cannot SEE (radius 0)?")
cfg6, lg6, w6 = house(perception_radius=0)
# p01 stands ON food source (radius 0 => sees only own cell => sees food stock 0). p02 adjacent.
w6 = replace(w6, positions={"p01": src, "p02": (src[0]-1, src[1]), "p03": (0,0)})
s = world_step(Engine(lg6), w6, cfg6)
print(" p01 listeners:", s.views["p01"].report_listeners, "report:", s.decisions["p01"].source_report, "-> p02:", s.processed.overlay.source_reports.get("p02"))

print("== L: heard report about a source the listener remembers EMPTY personally but older -> which shows in avoided? both. fine. Now report about source listener saw STOCKED more recently than report sighting")
print(" usable:", usable_reports((("food","p01",2,3),), (("food",1,4),), 5))
print(" own stocked sighting older than report:", usable_reports((("food","p01",4,5),), (("food",1,2),), 6))

print("== M: report where seen==heard? update_reports: speaker sighting at tick T spoken at tick T -> entry (sid, speaker, T, T+1). fine. Try sighting tick == current tick via decide: p01 sees empty now at tick 5, speaks now -> heard 6.")
cfg7, lg7, w7 = house()
w7 = replace(w7, tick=5)
s = world_step(Engine(replace(lg7, tick=5)), w7, cfg7)
print(" ", s.decisions["p01"].source_report, s.processed.overlay.source_reports.get("p02"))

print("== N: repeated speech does not extend: p01 speaks at 1 and again at 2 with same sighting 0 -> heard tick updated?")
cfg8, lg8, w8 = house()
s1 = world_step(Engine(lg8), w8, cfg8)
# keep p01 adjacent to p02 but out of sight of source? radius 1: p01 at src-1 sees src. To retain sighting-0 not refreshed, move p01 to home (src-2), p02 at home too. They're on same cell.
ov = replace(s1.processed.overlay, positions=w8.homes)
s2 = world_step(s1.engine, ov, cfg8)
print(" tick2 p01 speaks:", s2.decisions["p01"].source_report, "p02 report:", s2.processed.overlay.source_reports.get("p02"))
