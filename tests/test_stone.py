"""Stone: one finite outcrop, placed after homes, taken one unit per claim only
for a planned axe, never renewed."""
from dataclasses import replace

from kernel import Engine
from world.config import WorldConfig, genesis, stone_sites, wood_sites
from world.decide import Decision, decide
from world.materials import GATHER_STONE, GO_STONE, STONE, STONE_STOCK, WOOD
from world.observe import observe
from world.run import proposals_for, world_step


def crafting(**changes):
    cfg = WorldConfig(seed=7, wood_on=True, yard_on=True, stone_on=True, axe_on=True, actors=3, terrain_on=False,
                      water_on=False, warmth_on=False, births_on=False, offers_on=False, hunger_rate=0, **changes)
    return (cfg, *genesis(cfg))


def planned(overlay, who='p02', done=0):
    return replace(overlay, shelters=(overlay.homes[who],), built={p: (12 if p == who else 0) for p in overlay.roster},
                   axe_work={who: (done, 0, 0)})


def test_outcrop_is_placed_after_homes_and_genesis_is_otherwise_unchanged():
    cfg, ledger, overlay = crafting()
    off = replace(cfg, stone_on=False, axe_on=False)
    off_ledger, off_overlay = genesis(off)
    assert overlay == off_overlay
    (sid, site), = stone_sites(cfg)
    assert sid == STONE and site not in set(overlay.homes.values()) | {pos for _, pos in wood_sites(cfg)} | set(cfg.food_positions())
    assert ledger.sources[STONE].stock == STONE_STOCK and ledger.sources[STONE].resource == STONE
    assert set(ledger.sources) - set(off_ledger.sources) == {STONE}
    assert replace(ledger, sources=off_ledger.sources, holdings={k: v for k, v in ledger.holdings.items() if k != STONE},
                   consumed_by={k: v for k, v in ledger.consumed_by.items() if k != STONE}) == off_ledger
    assert cfg.describe()["stone_rules"]["renewal"] == 0 and "does not renew" in cfg.describe()["stone_rule"]
    assert WorldConfig.from_describe(cfg.describe()) == cfg


def test_stone_is_a_known_landmark_with_stock_only_in_sight():
    cfg, ledger, overlay = crafting()
    (_, site), = stone_sites(cfg)
    far = replace(overlay, positions={**overlay.positions, 'p02': (0, 11)})
    view = observe('p02', ledger, far, cfg)
    assert view.stone_source == site and view.stone_stock is None and view.stone == 0
    near = replace(overlay, positions={**overlay.positions, 'p02': site})
    assert observe('p02', ledger, near, cfg).stone_stock == STONE_STOCK


def test_stone_is_gathered_only_for_a_planned_axe_and_never_renews():
    cfg, ledger, overlay = crafting()
    (_, site), = stone_sites(cfg)
    idle = replace(planned(overlay), axe_work={}, positions={**overlay.positions, 'p02': site})
    assert decide(observe('p02', ledger, idle, cfg), cfg).kind not in (GATHER_STONE, GO_STONE)
    wood = replace(ledger, holdings={**ledger.holdings, WOOD: {**ledger.holdings[WOOD], 'p02': 1}})
    plan = replace(planned(overlay), positions={**overlay.positions, 'p02': site})
    choice = decide(observe('p02', wood, plan, cfg), cfg)
    assert choice.kind == GATHER_STONE and choice.amount == 1 and choice.target == STONE
    engine = Engine(wood)
    s = world_step(engine, plan, cfg)
    assert s.engine.state.holdings[STONE]['p02'] == 1 and s.engine.state.sources[STONE].stock == STONE_STOCK - 1
    assert s.engine.state.totals() == wood.totals()
    drained = replace(ledger, sources={**ledger.sources, STONE: replace(ledger.sources[STONE], stock=0)})
    engine, ov = Engine(drained), overlay
    for _ in range(90):
        step = world_step(engine, ov, cfg)
        engine, ov = step.engine, step.processed.overlay
        assert engine.state.sources[STONE].stock == 0
        assert not any('stone' in str(e) for e in step.processed.production)


def test_two_crafters_claim_the_last_stone_and_one_is_refused():
    cfg, ledger, overlay = crafting()
    last = replace(ledger, sources={**ledger.sources, STONE: replace(ledger.sources[STONE], stock=1)})
    decisions = {p: Decision(p, GATHER_STONE, 'stone', (GATHER_STONE,), amount=1, target=STONE) for p in ('p01', 'p03')}
    engine = Engine(last)
    record = engine.tick(proposals_for(decisions, 0))
    assert sum(o.accepted for o in record.outcomes) == 1
    assert sorted(engine.state.holdings[STONE][p] for p in ('p01', 'p03')) == [0, 1]
    assert engine.state.sources[STONE].stock == 0 and engine.state.totals() == last.totals()
