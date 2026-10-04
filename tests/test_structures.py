"""Shelters that wear and are mended or fall, fires that burn wood, wells that are dug and found: each effect is a saved
structure the run can be checked against, and every unit of wood or water involved passes through the kernel or a recorded entry."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from tests.test_crafting import holder
from tests.test_pledges import CLEAR_DAY, NIGHT, RAIN_NIGHT, STORM, ended, give, play
from world.config import WorldConfig, genesis, well_sites
from world.decide import decide
from world.observe import observe
from world.overlay import Overlay
from world.pledges import Pledge, Pledges
from world.replay import replay_world
from world.run import run_world, world_step
from world.sky import Sky
from world.structures import Struct, burning, lit_cells, well_id
from world.things import Things
from world.wolves import Wolf

FEATURES = ("beliefs", "bonds", "crafting", "explain", "personality", "pledges", "skills", "sky", "steady", "structures", "wolves")
RAIN = Sky("day", "rain", 8, 20)


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES, wood_on=True), **changes})


def house(structs=(), wood=2, cond=100, shelter=True, sky=CLEAR_DAY, lazy=True, **kw):
    """p01 at home with a standing shelter of the given condition; everyone else far away."""
    config, ledger, world = holder(cfg(), wood=wood, stone=0, shelter=shelter, **kw)
    if lazy:                                                                          # not diligent: no well, no tools
        traits = {**world.persona.traits, "p01": (60, 50, 50, 10, 50)}
        world = replace(world, persona=replace(world.persona, traits=traits))
    cell = world.homes["p01"]
    structs = tuple(structs) + ((Struct("shelter", "p01", cell[0], cell[1], cond),) if shelter else ())
    return config, ledger, replace(world, things=Things(structures=structs), sky=sky)


def struct(step, kind, owner="p01"):
    return next((s for s in step.processed.overlay.things.structures if (s.kind, s.owner) == (kind, owner)), None)


# --- storage and settings -----------------------------------------------------------------------

def test_header_round_trips_the_settings_are_validated_and_wells_need_water_and_wood():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert len(config.describe()["well_sites"]) == 6
    for bad in ((("wear_every", 0),), (("repair_at", 0),), (("leak_below", 101),), (("well_ticks", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("structures",))
    ledger, world = genesis(config)
    assert all(ledger.sources[well_id(o)].stock == 0 and ledger.sources[well_id(o)].resource == "water" for o, _ in well_sites(config))
    assert world.things.structures == ()


def test_structures_survive_the_canonical_form_and_are_validated():
    config, ledger, world = house((Struct("fire", "p01", 1, 7, 5), Struct("well", "p01", 2, 8, 3, 0)))
    again = Overlay.from_canonical(json.loads(json.dumps(world.canonical())))
    assert again.things == world.things
    for bad in (["boiler", "p01", 1, 1, 0, 0], ["fire", "p01", 1, 1, 0, 2], ["shelter", "p01", 1, 1, 101, 0], ["fire", "p01", -1, 1, 0, 0]):
        with pytest.raises(ValueError):
            Struct.from_canonical(bad)
    with pytest.raises(ValueError):
        Things(structures=(Struct("fire", "p01", 1, 1), Struct("fire", "p01", 2, 2)))


# --- shelters ------------------------------------------------------------------------------------

def test_a_finished_shelter_gets_a_condition_and_wears_by_the_declared_arithmetic():
    config, ledger, world = house(shelter=False)
    world = replace(world, shelters=(world.homes["p01"],))
    first = world_step(Engine(replace(ledger, tick=41)), replace(world, tick=41), config)             # 42 is a multiple of 6
    assert struct(first, "shelter").a == 99
    config, ledger, world = house(cond=50, tick=40)
    quiet = world_step(Engine(ledger), world, config)
    assert struct(quiet, "shelter").a == 50                                                           # tick 41 is not a wear tick
    storm = world_step(Engine(ledger), replace(world, sky=STORM), config)
    assert struct(storm, "shelter").a == 49                                                           # a storm tick takes one more


def test_somebody_free_at_home_with_wood_mends_a_worn_shelter_through_the_kernel():
    config, ledger, world = house(cond=30, wood=2)
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p01"].kind == "repair"
    assert [(o.operation, e.account, e.delta) for o in step.record.outcomes if o.actor == "p01" for e in o.effects if e.delta < 0] == \
        [("consume", "actor@wood:p01", -1)]
    assert struct(step, "shelter").a == 55                                                            # +25
    fine = house(cond=80, wood=2)
    assert decide(observe("p01", fine[1], fine[2], fine[0]), fine[0]).kind != "repair"                # not worn enough


def test_a_neighbour_at_the_door_adds_the_same_again_to_a_repair():
    config, ledger, world = house(cond=30, wood=2)
    pledge = Pledge("repair", "p01", "p02", "promised", 40, 80, 3, world.homes["p01"], heard=1)
    world = replace(world, pledges=Pledges(open=(pledge,)), positions={**world.positions, "p02": world.homes["p01"]})
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p02"].kind == "help" and struct(step, "shelter").a == 30 + 50
    assert step.processed.overlay.pledges.open[0].done == 1


def test_a_shelter_that_falls_to_nothing_collapses_and_its_owner_must_build_again():
    config, ledger, world = house(cond=1, wood=0)
    world = replace(world, built={a: (12 if a == "p01" else 0) for a in world.roster}, tick=41)
    step = world_step(Engine(replace(ledger, tick=41)), world, config)                                 # tick 42 is a wear tick: 1 -> 0
    overlay = step.processed.overlay
    assert struct(step, "shelter") is None and world.homes["p01"] not in overlay.shelters
    assert overlay.built["p01"] == 0


def test_a_leaking_shelter_gives_no_shelter_from_the_rain_a_sound_one_does():
    results = {}
    for label, cond in (("sound", 90), ("leaking", 20)):
        config, ledger, world = house(cond=cond, wood=1, sky=RAIN)
        world = replace(world, cold={a: 20 for a in world.roster})
        step = world_step(Engine(ledger), world, config)
        results[label] = step.processed.overlay.cold["p01"]
    assert results["leaking"] > results["sound"]


# --- fire ----------------------------------------------------------------------------------------

def test_somebody_at_home_at_night_with_wood_lights_a_fire_that_burns_down_and_warms_them():
    config, ledger, world = house(wood=1, sky=NIGHT)
    world = replace(world, cold={a: 10 for a in world.roster})
    steps = play(config, ledger, world, 18, sky=NIGHT)
    assert steps[0].decisions["p01"].kind == "light"
    assert [(o.operation, e.account, e.delta) for o in steps[0].record.outcomes if o.actor == "p01" for e in o.effects if e.delta < 0] == \
        [("consume", "actor@wood:p01", -1)]
    fire = struct(steps[0], "fire")
    assert fire is not None and fire.a == config.lever("fire_burn") - 1 and fire.cell == world.homes["p01"]
    fuel = [struct(s, "fire").a if struct(s, "fire") else None for s in steps]
    assert fuel[:3] == [13, 12, 11] and fuel[config.lever("fire_burn") - 1] == 0
    assert struct(steps[-1], "fire") is None                                                          # burnt out and gone
    colder = house(wood=0, sky=NIGHT)
    cold_world = replace(colder[2], cold={a: 10 for a in colder[2].roster})
    without = world_step(Engine(colder[1]), cold_world, colder[0])
    with_fire = world_step(Engine(ledger), replace(world, things=Things(structures=world.things.structures + (
        Struct("fire", "p01", *world.homes["p01"], 5),))), config)
    assert with_fire.processed.overlay.cold["p01"] == without.processed.overlay.cold["p01"] - config.lever("fire_warmth")


def test_firelight_pushes_back_the_dark_and_wolves_do_not_bite_within_a_cell_of_a_fire():
    config, ledger, world = house(wood=0, sky=NIGHT)
    home = world.homes["p01"]
    fire = Struct("fire", "p01", home[0], home[1], 8)
    lit = replace(world, things=Things(structures=world.things.structures + (fire,)))
    third = (home[0], home[1] - 3)                                                                     # three cells off: past night sight
    world = replace(world, positions={**world.positions, "p02": third})
    lit = replace(lit, positions={**lit.positions, "p02": third})
    dark = observe("p01", ledger, world, config)
    bright = observe("p01", ledger, lit, config)
    assert bright.lit and not dark.lit
    assert [s.actor for s in dark.others] == [] and [s.actor for s in bright.others] == ["p02"]       # firelight shows the person
    assert lit_cells((fire,), 1) >= {home, (home[0] + 1, home[1])} and burning((fire,)) == [fire]
    outside = (home[0] + 1, home[1])
    for structures, bitten in ((world.things.structures, True), (lit.things.structures, False)):
        stuck = {a: (1 if a == "p01" else 0) for a in world.roster}                                       # still climbing out of rough ground
        w = replace(world, things=Things(wolves=(Wolf("w1", (outside[0] + 1, outside[1])),), structures=structures),
                    positions={**world.positions, "p01": outside}, held=stuck)
        step = world_step(Engine(ledger), w, config)
        assert (step.processed.overlay.persona.hurt.get("p01", 0) > 0) == bitten


# --- wells ---------------------------------------------------------------------------------------

def test_a_well_is_paid_for_once_dug_over_many_ticks_and_then_gives_water_by_recorded_production():
    config, ledger, world = house(wood=4, sky=CLEAR_DAY, lazy=False)
    site = next(pos for o, pos in well_sites(config) if o == "p01")
    world = replace(world, positions={**world.positions, "p01": site})
    steps = play(config, ledger, world, 30, sky=CLEAR_DAY)
    digs = [i for i, s in enumerate(steps) if s.decisions["p01"].kind == "dig"]
    assert len(digs) >= config.lever("well_ticks")
    first = steps[digs[0]]
    assert first.decisions["p01"].amount == 4 and [o.operation for o in first.record.outcomes if o.actor == "p01"] == ["consume"]
    assert all(steps[i].decisions["p01"].amount == 0 for i in digs[1:])                                 # paid for once
    done = next(i for i, s in enumerate(steps) if (struct(s, "well") and struct(s, "well").b))
    assert struct(steps[done], "well").a == config.lever("well_ticks")
    water = [(s.processed.overlay.tick, e) for s in steps[done:] for e in s.processed.production if e.get("source") == well_id("p01")]
    assert water and all(tick % config.lever("well_every") == 0 for tick, _ in water)
    assert steps[done - 1].committed.sources[well_id("p01")].stock == 0                                 # nothing before it was finished


def test_a_finished_well_is_unknown_until_it_has_been_seen():
    config, ledger, world = house(wood=0)
    site = next(pos for o, pos in well_sites(config) if o == "p03")
    done = Struct("well", "p03", site[0], site[1], config.lever("well_ticks"), 1)
    sources = dict(ledger.sources)
    sources[well_id("p03")] = replace(sources[well_id("p03")], stock=4)
    ledger = replace(ledger, sources=sources)
    near = replace(world, things=Things(structures=world.things.structures + (done,)), thirst={a: 30 for a in world.roster},
                   positions={**world.positions, "p01": (site[0] + 1, site[1])})
    far = replace(near, positions={**near.positions, "p01": world.homes["p01"]})
    assert observe("p01", ledger, near, config).water_source_id == well_id("p03")
    assert observe("p01", ledger, far, config).water_source_id in config.water_source_ids()


# --- asking a neighbour to help mend ------------------------------------------------------------------

def test_somebody_mending_asks_a_free_neighbour_for_a_hand_and_the_help_ends_when_it_is_done():
    config, ledger, world = house(cond=30, wood=3)
    world = replace(world, positions={**world.positions, "p02": (world.homes["p01"][0], world.homes["p01"][1] - 1)})
    d = decide(observe("p01", ledger, world, config), config)
    assert d.kind == "repair" and d.asked == (("p02", "repair", 3),)
    steps = play(config, ledger, world, 12, sky=CLEAR_DAY)
    endings = [e for s in steps for e in ended(s) if e[0] == "repair"]
    assert endings and endings[0][3] in ("kept", "expired")


# --- whole worlds --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("structures") / "run.jsonl"
    config = WorldConfig(seed=23, features=tuple(sorted(set(FEATURES) | {"farming", "sleep"})), wood_on=True)
    run_world(config, 600, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_a_world_that_builds_and_keeps_up_audits_replays_and_every_change_has_a_recorded_cause(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]
    seen = {"collapse": 0, "repair": 0, "fire": 0, "well": 0}
    for k in range(1, len(worlds)):
        before = {(s[0], s[1]): s for s in (worlds[k - 1].get("things") or {}).get("structures", [])}
        now = {(s[0], s[1]): s for s in (worlds[k].get("things") or {}).get("structures", [])}
        decisions = run.ticks[k - 1]["decisions"]
        for key, s in now.items():
            was = before.get(key)
            if key[0] == "shelter" and was is not None and s[4] > was[4]:
                assert decisions[key[1]]["kind"] == "repair"; seen["repair"] += 1             # only mending raises condition
            if key[0] == "fire" and (was is None or s[4] > was[4]):
                assert decisions[key[1]]["kind"] == "light"; seen["fire"] += 1                # only lighting adds fuel
            if key[0] == "well" and was is not None and s[4] > was[4]:
                assert decisions[key[1]]["kind"] == "dig"; seen["well"] += 1
        for key, was in before.items():
            if key[0] == "shelter" and key not in now:
                assert was[4] <= 7; seen["collapse"] += 1                                      # worn to nothing: one tick of storm or wear
                assert [tuple(c) for c in worlds[k - 1]["shelters"]] != [tuple(c) for c in worlds[k]["shelters"]]
    assert seen["repair"] >= 1 and seen["fire"] >= 1 and seen["well"] >= 1
