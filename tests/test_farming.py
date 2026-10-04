"""Fields, crops and spoiled grain: a seed is spent, a crop is added by recorded growth, harvested by a claim, soil wears,
standing crops rot and stored grain spoils, each as a recorded entry the independent audit can account for."""

from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import RunFileError, apply_production, read_run
from tests.ledger_audit import audit_run
from tests.test_crafting import holder
from tests.test_pledges import CLEAR_DAY, play
from world.config import WorldConfig, field_sites, genesis
from world.decide import decide
from world.farming import GRAIN, Plot, advance_farming, field_id
from world.observe import observe
from world.replay import replay_world
from world.run import run_world, world_step
from world.sky import Sky
from world.things import Things

FEATURES = ("beliefs", "bonds", "crafting", "explain", "farming", "personality", "skills", "sky", "steady", "wolves")


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES, wood_on=True), **changes})


def farmer(plot_state="bare", grown=0, soil=100, cared=0, grain=1, hoe=False, sky=CLEAR_DAY, fertile=True, **kw):
    """p01 at home with a field beside it in the given condition, well fed."""
    config, ledger, world = holder(cfg(), wood=0, stone=0, tools=("hoe",) if hoe else (), shelter=True)
    (owner, cell), = [s for s in field_sites(config) if s[0] == "p01"]
    plots = tuple(Plot("p01", cell[0], cell[1], plot_state, grown, 0, soil, cared) if p.owner == "p01" else p
                  for p in world.things.plots)
    positions = {**world.positions, "p01": cell}
    holdings = {r: dict(m) for r, m in ledger.holdings.items()}
    holdings["grain"]["p01"] = grain
    return config, replace(ledger, holdings=holdings), replace(world, things=Things(plots=plots), positions=positions, sky=sky, **kw)


def plot_of(step, owner="p01"):
    return next(p for p in step.processed.overlay.things.plots if p.owner == owner)


# --- the world ---------------------------------------------------------------------------------

def test_header_round_trips_and_every_founder_has_a_field_a_source_and_a_seed():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    ledger, world = genesis(config)
    assert [p.owner for p in world.things.plots] == [f"p0{i}" for i in range(1, 7)]
    homes = set(world.homes.values())
    assert all(p.cell not in homes and p.state == "bare" and p.soil == 100 for p in world.things.plots)
    assert len({p.cell for p in world.things.plots}) == 6                                       # one field each, no two on a cell
    for p in world.things.plots:
        assert ledger.sources[field_id(p.owner)].stock == 0 and ledger.sources[field_id(p.owner)].resource == GRAIN
    assert set(ledger.holdings[GRAIN].values()) == {1} and ledger.consumed_by[GRAIN] == 0
    with pytest.raises(ValueError):
        cfg(feature_levers=(("grow_ticks", 0),))
    assert field_sites(WorldConfig(seed=7, features=("beliefs",))) == ()


def test_plots_survive_the_canonical_form_and_are_validated():
    from world.overlay import Overlay
    import json
    config, ledger, world = farmer("growing", grown=5, cared=2)
    again = Overlay.from_canonical(json.loads(json.dumps(world.canonical())))
    assert again.things == world.things and again.canonical() == world.canonical()
    for bad in (["p01", 1, 1, "wilted", 0, 0, 100, 0], ["p01", 1, 1, "bare", 0, 0, 101, 0], ["p01", -1, 1, "bare", 0, 0, 100, 0],
                ["p01", 1, 1, "bare"]):
        with pytest.raises(ValueError):
            Plot.from_canonical(bad)
    with pytest.raises(ValueError):
        Things(plots=(Plot("p01", 1, 1), Plot("p01", 2, 2)))


def test_spoilage_and_rot_are_checked_strictly():
    state = {"balances": {"p01": 1}, "sources": {"field-p01": {"stock": 3, "authorised": ["p01"], "resource": "grain"}},
             "holdings": {"grain": {"p01": 4}}, "consumed_by": {"grain": 0}}
    out = apply_production(state, [{"spoiled": "p01", "item": "grain", "amount": 1}, {"rotted": "field-p01", "amount": 3}])
    assert out["holdings"]["grain"]["p01"] == 3 and out["sources"]["field-p01"]["stock"] == 0 and out["consumed_by"]["grain"] == 4
    for bad in ({"spoiled": "p01", "item": "grain", "amount": 5}, {"spoiled": "p09", "item": "grain", "amount": 1},
                {"rotted": "field-p01", "amount": 4}, {"rotted": "nowhere", "amount": 1}, {"spoiled": "p01", "item": "grain"}):
        with pytest.raises(RunFileError):
            apply_production(state, [bad])


# --- the work ----------------------------------------------------------------------------------

def test_somebody_at_their_bare_field_with_a_seed_plants_it_and_the_seed_is_spent():
    config, ledger, world = farmer("bare", grain=1)
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p01"].kind == "plant"
    assert [(o.operation, e.account, e.delta) for o in step.record.outcomes if o.actor == "p01" for e in o.effects if e.delta < 0] == \
        [("consume", "actor@grain:p01", -1)]
    assert plot_of(step).state == "growing" and plot_of(step).grown == 1
    assert step.processed.ledger.consumed_by[GRAIN] == 1 and step.processed.overlay.persona.skills["p01"][3] == 1


def test_without_seed_or_with_worn_soil_nothing_is_planted_and_in_a_storm_nobody_goes_out():
    for kw in (dict(grain=0), dict(soil=10), dict(sky=Sky("night", "storm", 1, 100))):
        config, ledger, world = farmer("bare", **kw)
        assert decide(observe("p01", ledger, world, config), config).kind not in ("plant", "go_field")


def test_somebody_away_from_their_field_walks_to_it_before_working():
    config, ledger, world = farmer("growing", grown=3)
    cell = next(c for owner, c in field_sites(config) if owner == "p01")
    home = world.homes["p01"]
    assert abs(cell[0] - home[0]) + abs(cell[1] - home[1]) >= 1
    world = replace(world, positions={**world.positions, "p01": home})
    d = decide(observe("p01", ledger, world, config), config)
    assert d.kind == "go_field" and d.step is not None and "walking" in d.reason


def test_a_growing_crop_is_tended_up_to_the_limit_and_ripens_by_a_recorded_production_entry():
    config, ledger, world = farmer("growing", grown=28, cared=3)
    first = world_step(Engine(ledger), world, config)
    assert plot_of(first).state == "growing" and plot_of(first).grown == 29
    second = world_step(first.engine, replace(first.processed.overlay, sky=CLEAR_DAY), config)
    assert plot_of(second).state == "ripe" and plot_of(second).since == second.processed.overlay.tick
    assert second.processed.production == ({"source": "field-p01", "amount": 5},)               # 3 base +1 soil +1 tended
    assert second.processed.ledger.sources["field-p01"].stock == 5
    tended = farmer("growing", grown=5, cared=0)
    step = world_step(Engine(tended[1]), tended[2], tended[0])
    assert step.decisions["p01"].kind == "tend" and plot_of(step).cared == 1


def test_rain_ripens_a_crop_a_tick_sooner_and_a_hoe_adds_a_unit():
    rain = Sky("day", "rain", 8, 20)
    config, ledger, world = farmer("growing", grown=28, cared=0, sky=rain, hoe=True)
    step = world_step(Engine(ledger), world, config)
    assert plot_of(step).state == "ripe"                                                        # +2 in rain: 28 -> 30
    assert step.processed.production == ({"source": "field-p01", "amount": 5},)               # 3 base +1 soil +1 hoe, untended... +1 tended? no: 3+1+1
    dry = farmer("growing", grown=28, cared=0)
    step2 = world_step(Engine(dry[1]), dry[2], dry[0])
    assert plot_of(step2).state == "growing" and plot_of(step2).grown == 29                     # one tick in the dry


def test_worn_soil_gives_less_and_a_crop_never_gives_less_than_one():
    for soil, expected in ((100, 4), (50, 3), (10, 2)):
        config, ledger, world = farmer("growing", grown=29, soil=soil, cared=1)
        step = world_step(Engine(ledger), world, config)
        assert step.processed.production[0]["amount"] == expected
    config, ledger, world = farmer("growing", grown=29, soil=0, cared=0)
    low = cfg(feature_levers=(("base_yield", 1),))
    step = world_step(Engine(ledger), world, low)
    assert step.processed.production[0]["amount"] == 1                                          # 1 - 1 for the soil, floored at one


def ripe_scene(stock=4, since=40, **kw):
    config, ledger, world = farmer("ripe", **kw)
    sources = dict(ledger.sources)
    sources["field-p01"] = replace(sources["field-p01"], stock=stock)
    return config, replace(ledger, sources=sources), replace(world, tick=since + 1)


def test_a_ripe_crop_is_harvested_by_a_claim_and_the_soil_wears():
    config, ledger, world = ripe_scene(stock=4, since=39)
    step = world_step(Engine(ledger), world, config)
    d = step.decisions["p01"]
    assert d.kind == "harvest" and d.amount == 4 and d.target == "field-p01"
    assert sorted((o.operation, e.account, e.delta) for o in step.record.outcomes if o.actor == "p01" for e in o.effects) == \
        [("claim", "actor@grain:p01", 4), ("claim", "source:field-p01", -4)]
    assert step.committed.holdings[GRAIN]["p01"] == 5 and step.committed.sources["field-p01"].stock == 0
    p = plot_of(step)
    assert p.state == "bare" and p.soil == 80 and p.cared == 0


def test_a_bare_field_mends_slowly():
    config, ledger, world = farmer("bare", grain=0, soil=50, tick=39)
    step = world_step(Engine(replace(ledger, tick=39)), replace(world, tick=39), config)
    assert plot_of(step).soil == 51                                                              # tick 40 is a multiple of fallow_every


def test_a_crop_left_standing_rots_and_the_loss_is_recorded_into_the_sink():
    config, ledger, world = ripe_scene(stock=4, since=0, grain=0)
    world = replace(world, tick=39, things=Things(plots=tuple(replace(p, since=0) if p.owner == "p01" else p for p in world.things.plots)))
    world = replace(world, positions={**world.positions, "p01": world.homes["p01"]})            # away: nobody harvests it
    ledger = replace(ledger, tick=39)
    step = world_step(Engine(ledger), replace(world, persona=replace(world.persona, doing={})), config)
    assert step.decisions["p01"].kind == "go_field"                                             # nobody was there to harvest it
    assert [e for e in step.processed.production if "rotted" in e] == [{"rotted": "field-p01", "amount": 4}]
    assert step.processed.ledger.consumed_by[GRAIN] == 4 and step.processed.ledger.sources["field-p01"].stock == 0
    assert plot_of(step).state == "bare"


# --- grain as food and spoilage ------------------------------------------------------------------

def test_somebody_hungry_with_grain_eats_it_and_it_relieves_more_than_a_berry():
    config, ledger, world = farmer("bare", grain=3)
    world = replace(world, hunger={**world.hunger, "p01": 40})
    step = world_step(Engine(ledger), world, config)
    d = step.decisions["p01"]
    assert d.kind == "eat" and d.resource == GRAIN
    assert step.processed.overlay.hunger["p01"] == 40 + 1 - config.lever("grain_satiation")
    assert step.processed.ledger.consumed_by[GRAIN] == 1 and step.processed.ledger.holdings[GRAIN]["p01"] == 2


def test_stored_grain_spoils_a_third_at_a_time_but_a_seed_or_two_keeps():
    config, ledger, world = farmer("bare", grain=6, soil=0)
    every = config.lever("spoil_every")
    tick = next(t for t in range(40, 200) if (t + 1 + 0) % every == 0)                            # p01 is first in the roster
    step = world_step(Engine(replace(ledger, tick=tick)), replace(world, tick=tick), config)
    assert {"spoiled": "p01", "item": GRAIN, "amount": 2} in step.processed.production
    assert step.processed.ledger.holdings[GRAIN]["p01"] == 4 and step.processed.ledger.consumed_by[GRAIN] == 2
    few = farmer("bare", grain=2, soil=0)
    step2 = world_step(Engine(replace(few[1], tick=tick)), replace(few[2], tick=tick), few[0])
    assert not any("spoiled" in e for e in step2.processed.production)


def test_wolves_moving_do_not_wipe_the_fields():
    config, ledger, world = farmer("growing", grown=3)
    from world.wolves import Wolf
    world = replace(world, things=Things(wolves=(Wolf("w1", (0, 0)),), plots=world.things.plots))
    step = world_step(Engine(ledger), world, config)
    assert len(step.processed.overlay.things.plots) == 6 and step.processed.overlay.things.wolves


# --- whole worlds --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("farming") / "run.jsonl"
    config = WorldConfig(seed=11, features=tuple(sorted(set(FEATURES) | {"pledges", "sleep"})), wood_on=True)
    run_world(config, 450, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_a_farming_world_audits_replays_and_its_grain_is_fully_accounted_for(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    grown = sum(e["amount"] for t in run.ticks for e in (t.get("production") or []) if str(e.get("source", "")).startswith("field-"))
    last = run.ticks[-1]["state"]
    held, standing = sum(last["holdings"][GRAIN].values()), sum(s["stock"] for k, s in last["sources"].items() if k.startswith("field-"))
    seeds = 6 * 1                                                                                 # genesis seed
    # every unit is somewhere: held, standing in a field, or consumed (eaten, planted, spoiled, rotted)
    assert held + standing + last["consumed_by"][GRAIN] == seeds + grown
    kinds = {k: sum(1 for t in run.ticks for d in t["decisions"].values() if d["kind"] == k) for k in ("plant", "tend", "harvest")}
    assert min(kinds.values()) >= 3
    spoiled = sum(e["amount"] for t in run.ticks for e in (t.get("production") or []) if "spoiled" in e)
    assert spoiled >= 1


@pytest.mark.long_run
def test_every_plot_change_in_a_saved_run_follows_a_recorded_decision_or_rule(saved):
    _, run = saved
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]
    for k in range(1, len(worlds)):
        before = {p[0]: p for p in (worlds[k - 1].get("things") or {}).get("plots", [])}
        decisions = run.ticks[k - 1]["decisions"]
        for owner, plot in {p[0]: p for p in (worlds[k].get("things") or {}).get("plots", [])}.items():
            was = before[owner]
            if was[3] == "bare" and plot[3] == "growing":
                assert decisions[owner]["kind"] == "plant"                                         # only planting starts a crop
            if was[3] == "ripe" and plot[3] == "bare" and plot[6] < was[6]:
                assert decisions[owner]["kind"] == "harvest"                                       # only a harvest wears the soil
            if plot[7] > was[7]:
                assert decisions[owner]["kind"] == "tend"
            assert plot[6] <= 100
