"""Stone, tools and making things: the quarry, recipes spent through the kernel, tools that appear only by a recorded
production entry tied to that spending, and what each tool changes."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from kernel import Engine
from stream.run_file import RunFileError, apply_production, read_run
from tests.ledger_audit import audit_run
from tests.test_pledges import CLEAR_DAY, give, play
from world.config import WorldConfig, genesis, stone_sites
from world.crafting import CRAFT, RECIPES, TOOLS, apply_crafting, build_saves
from world.decide import Decision, decide, pack_size
from world.observe import observe
from world.replay import replay_world
from world.run import run_world, world_step
from world.traits import build_goal

FEATURES = ("beliefs", "bonds", "crafting", "explain", "personality", "skills", "sky", "steady", "wolves")


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES, wood_on=True), **changes})


def holder(config=None, wood=2, stone=2, tools=(), tick=40, work=0, shelter=False, **overlay):
    """p01 at home, idle and well, with some materials; p02..p06 far away."""
    config = config or cfg()
    ledger, world = genesis(config)
    positions = dict(world.positions)
    for who, spot in zip(("p02", "p03", "p04", "p05", "p06"), ((8, 8), (0, 1), (9, 11), (11, 0), (10, 5))):
        positions[who] = spot
    persona = replace(world.persona, traits={a: (60, 50, 50, 60, 50) for a in world.roster}, lonely={})
    shelters = tuple(sorted({world.homes["p01"]})) if shelter else ()
    built = {a: 0 for a in world.roster}
    built["p01"] = work
    world = replace(world, positions=positions, sky=CLEAR_DAY, tick=tick, persona=persona, shelters=shelters, built=built,
                    thirst={a: 0 for a in world.roster}, hunger={a: 0 for a in world.roster},
                    cold={a: 0 for a in world.roster}, **overlay)
    ledger = replace(give(ledger, "p01", food=2, water=2, wood=wood), tick=tick)
    holdings = {r: dict(m) for r, m in ledger.holdings.items()}
    holdings["stone"]["p01"] = stone
    for tool in tools:
        holdings[tool]["p01"] = 1
    return config, replace(ledger, holdings=holdings), world


# --- the world and its settings ----------------------------------------------------------------

def test_the_header_round_trips_and_crafting_needs_wood_and_building():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert config.describe()["stone_sources"] == [{"id": "stone", "position": list(stone_sites(config)[0][1])}]
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("crafting",))                              # no wood, no building: nothing to make tools from
    with pytest.raises(ValueError):
        cfg(feature_levers=(("stone_hand", 5),))                                  # by hand must not beat a pick
    assert "stone_sources" not in WorldConfig(seed=7, features=("beliefs",)).describe()


def test_a_quarry_stands_on_clear_ground_and_everybody_starts_with_no_stone_or_tools():
    config = cfg()
    ledger, world = genesis(config)
    (sid, spot), = stone_sites(config)
    assert spot not in set(world.homes.values()) | set(config.food_positions() + config.water_positions())
    assert ledger.sources["stone"].stock == 10 and ledger.sources["stone"].resource == "stone"
    for resource in ("stone",) + TOOLS:
        assert set(ledger.holdings[resource].values()) == {0} and ledger.consumed_by[resource] == 0
    assert stone_sites(WorldConfig(seed=7, features=("beliefs",))) == ()


def test_made_production_is_checked_strictly():
    state = {"balances": {"p01": 1}, "sources": {}, "holdings": {"axe": {"p01": 0}}, "consumed_by": {"axe": 0}}
    assert apply_production(state, [{"made": "p01", "item": "axe", "amount": 1}])["holdings"]["axe"]["p01"] == 1
    for bad in ({"made": "p09", "item": "axe", "amount": 1}, {"made": "p01", "item": "gold", "amount": 1},
                {"made": "p01", "item": "axe", "amount": 0}, {"made": "p01", "item": "axe", "amount": 1, "extra": 1}):
        with pytest.raises(RunFileError):
            apply_production(state, [bad])


# --- making --------------------------------------------------------------------------------------

def test_somebody_free_at_home_with_the_materials_makes_a_tool_and_pays_for_it_through_the_kernel():
    config, ledger, world = holder(wood=2, stone=0, shelter=True)
    step = world_step(Engine(ledger), world, config)
    d = step.decisions["p01"]
    assert d.kind == CRAFT and d.target == "basket"                              # a basket is wood alone
    ops = [(o.operation, e.account, e.delta) for o in step.record.outcomes if o.actor == "p01" for e in o.effects if e.delta < 0]
    assert ops == [("consume", "actor@wood:p01", -2)]
    assert step.processed.production == ({"made": "p01", "item": "basket", "amount": 1},)
    assert step.processed.ledger.holdings["basket"]["p01"] == 1 and step.processed.ledger.holdings["wood"]["p01"] == 0
    assert step.processed.overlay.persona.skills["p01"][4] == 1                    # crafting practice


def test_every_recipe_is_spent_in_full_and_a_tool_needs_every_input_accepted():
    config, ledger, world = holder(wood=1, stone=2, tools=("basket",), shelter=True)
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p01"].target == "pick"
    assert sorted((e.account, e.delta) for o in step.record.outcomes if o.actor == "p01" for e in o.effects if e.delta < 0) == \
        [("actor@stone:p01", -2), ("actor@wood:p01", -1)]
    # a tool is added only when every input was accepted
    decisions = {"p01": Decision("p01", CRAFT, "", (), target="pick")}
    partial = type("R", (), {"outcomes": tuple(o for o in step.record.outcomes if "stone" in "".join(e.account for e in o.effects))})()
    same, made = apply_crafting(ledger, decisions, partial, config)
    assert made == [] and same is ledger


def test_nobody_makes_a_tool_in_a_storm_while_a_child_or_too_far_from_the_materials():
    from world.sky import Sky
    config, ledger, world = holder(wood=2, stone=0, shelter=True)
    storm = replace(world, sky=Sky("night", "storm", 1, 100))
    assert decide(observe("p01", ledger, storm, config), config).kind != CRAFT
    lazy = replace(world, persona=replace(world.persona, traits={**world.persona.traits, "p01": (60, 50, 50, 10, 50)}))
    config2, ledger2, world2 = holder(wood=0, stone=0, shelter=True)
    lazy2 = replace(world2, persona=replace(world2.persona, traits={**world2.persona.traits, "p01": (60, 50, 50, 10, 50)}))
    assert decide(observe("p01", ledger2, lazy2, config2), config2).kind not in ("go_wood", "go_stone")     # not diligent enough to fetch


def test_somebody_missing_materials_fetches_them_a_pack_at_a_time():
    config, ledger, world = holder(wood=0, stone=0, shelter=True)
    steps = play(config, ledger, world, 90, sky=CLEAR_DAY)
    kinds = [s.decisions["p01"].kind for s in steps]
    assert "go_wood" in kinds and "gather_wood" in kinds and "craft" in kinds
    first = kinds.index("craft")
    assert kinds[first - 1] != "craft" and steps[first].processed.production[0]["made"] == "p01"
    claims = [o for s in steps for o in s.record.outcomes if o.actor == "p01" and o.operation == "claim" and o.accepted
              and any(e.account in ("source:wood", "source:wood2", "source:stone") for e in o.effects)]
    assert claims and all(abs(e.delta) <= 2 for o in claims for e in o.effects)               # a hand-sized pack, no more than the recipe needs


# --- what tools change ---------------------------------------------------------------------------

def test_an_axe_saves_building_ticks_but_never_below_four():
    assert build_goal(12, (0, 0, 0, 0, 0), 2) == 10 and build_goal(12, (0, 0, 24, 0, 0), 2) == 8
    assert build_goal(5, (0, 0, 120, 0, 0), 2) == 4 and build_goal(3, (0, 0, 0, 0, 0), 2) == 3
    config = cfg()
    assert build_saves(("axe",), config) == 2 and build_saves(("basket",), config) == 0


def test_a_shelter_stands_two_ticks_sooner_for_somebody_with_an_axe():
    ticks = {}
    for label, tools in (("axe", ("axe",)), ("none", ())):
        config, ledger, world = holder(wood=3, stone=0, tools=tools, work=0)
        steps = play(config, ledger, world, 14, sky=CLEAR_DAY)
        ticks[label] = next(i for i, s in enumerate(steps) if s.processed.overlay.homes["p01"] in s.processed.overlay.shelters)
    assert ticks["none"] - ticks["axe"] == 2


def test_a_basket_carries_more_food_and_a_pick_digs_stone_faster():
    config, ledger, world = holder(tools=("basket",))
    assert pack_size(observe("p01", ledger, world, config), config) == config.claim_amount + 2
    config, ledger, world = holder()
    assert pack_size(observe("p01", ledger, world, config), config) == config.claim_amount
    quarry = stone_sites(config)[0][1]
    for tools, wanted, units in ((("basket",), "pick", 1), (("basket", "pick"), "axe", 2)):
        c, l, w = holder(wood=1, stone=0, tools=tools, shelter=True)
        w = replace(w, positions={**w.positions, "p01": quarry})
        w = replace(w, persona=replace(w.persona, doing={"p01": "go_stone"}))
        step = world_step(Engine(l), w, c)
        d = step.decisions["p01"]
        assert d.kind == "gather_stone" and f"for a{'n' if wanted == 'axe' else ''} {wanted}" in d.reason
        assert d.amount == units                                                           # a hand takes one; a pick takes the whole two


# --- whole worlds --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("crafting") / "run.jsonl"
    config = WorldConfig(seed=11, features=tuple(sorted(set(FEATURES) | {"pledges", "sleep"})), wood_on=True)
    run_world(config, 400, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_a_crafting_world_audits_replays_and_every_tool_has_a_recorded_maker(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    made = {tool: 0 for tool in TOOLS}
    for tick in run.ticks:
        for entry in tick.get("production") or []:
            if "made" in entry:
                made[entry["item"]] += entry["amount"]
    last = run.ticks[-1]["state"]["holdings"]
    for tool in TOOLS:
        assert sum(last[tool].values()) == made[tool]                             # tools exist only because somebody made them
    assert sum(made.values()) >= 1
    spent_stone = sum(-e["delta"] for t in run.ticks for o in t["record"]["outcomes"] if o["accepted"] and o["operation"] == "consume"
                      for e in o["effects"] if e["account"].startswith("actor@stone:") and e["delta"] < 0)
    assert spent_stone == last_consumed(run)


def last_consumed(run):
    return run.ticks[-1]["state"]["consumed_by"]["stone"]


def test_the_audit_refuses_a_made_entry_no_recipe_could_have_produced_and_a_birth_with_extra_keys(tmp_path):
    import copy
    from dataclasses import replace as swap
    from stream.run_file import RunFileError, apply_production, read_run
    from tests.ledger_audit import audit_run
    path = tmp_path / "r.jsonl"
    run_world(WorldConfig(seed=7), 12, path)
    run = read_run(path)
    assert audit_run(run) == []

    def forged(entry, item):
        ticks = [copy.deepcopy(t) for t in run.ticks]
        ticks[3].setdefault("production", []).append(entry)
        for later in ticks[4:]:                                      # carry the forged units through every later state, as a forger would
            later["state"]["holdings"][item]["p01"] += entry["amount"]
        return swap(run, ticks=tuple(ticks))
    assert any("no recipe yields" in p for p in audit_run(forged({"made": "p01", "item": "water", "amount": 5}, "water")))
    state = run.ticks[3]["state"]
    with pytest.raises(RunFileError):
        apply_production(state, [{"born": "p99", "junk": 1}])
