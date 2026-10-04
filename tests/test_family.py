"""Couples, pregnancy, growing old, orphans, grief and travellers: stored strictly, each rule on its own, and the whole thing
on saved worlds where every birth, couple, adoption, grief and arrival traces to something recorded."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from tests.test_crafting import holder
from tests.test_pledges import CLEAR_DAY, bond, play
from world.config import WorldConfig, genesis
from world.decide import decide
from world.family import Family, are_kin, lifespan, stage
from world.observe import observe
from world.overlay import Overlay
from world.replay import replay_world
from world.run import run_world, world_step

FEATURES = ("beliefs", "bonds", "explain", "family", "personality", "skills", "sky", "steady", "wolves")


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


def adults(config=None, ages=None, **overlay):
    """Six adults, p01 and p02 side by side at p01's door and the rest far away."""
    config = config or cfg()
    ledger, world = genesis(config)
    positions = dict(world.positions)
    positions["p01"], positions["p02"] = (1, 7), (1, 6)
    for who, spot in zip(("p03", "p04", "p05", "p06"), ((8, 8), (0, 1), (6, 1), (9, 11))):
        positions[who] = spot
    persona = replace(world.persona, lonely={}, traits={a: (60, 50, 50, 50, 50) for a in world.roster})
    age = {a: config.adult_at + 10 for a in world.roster}
    age.update(ages or {})
    world = replace(world, positions=positions, sky=CLEAR_DAY, tick=40, persona=persona, age=age, **overlay)
    return config, replace(ledger, tick=40), world


def talking(world, a="p01", b="p02", fond=18, trust=55):
    persona = replace(world.persona, talking={a: (b, 38), b: (a, 38)},
                      bonds={a: (bond(b, fond, trust),), b: (bond(a, fond, trust),)})
    return replace(world, persona=persona)


# --- storage and settings ------------------------------------------------------------------------

def test_header_round_trips_and_the_population_limits_are_in_it():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    rule = config.describe()["feature_rules"]["family"]
    assert "pop_cap" in rule and "max_arrivals" in rule and "old_age_at" in rule     # nothing silent: the limits are written down
    for bad in ((("gestation", 0),), (("elder_at", 500),), (("couple_at", 101),), (("pop_cap", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("beliefs", "bonds", "family"), births_on=False)       # no births, no family
    assert cfg().lever("old_age_at") > cfg().lever("elder_at")


def test_family_state_survives_the_canonical_form_and_is_validated():
    config, ledger, world = adults()
    family = Family(partner={"p01": "p02", "p02": "p01"}, pregnant={"p02": (70, "p01")}, grief={"p03": 40},
                    guardian={"p05": "p04"}, arrivals=2, last_arrival=30)
    held = replace(world, family=family)
    again = Overlay.from_canonical(json.loads(json.dumps(held.canonical())))
    assert again.family == family and Family().canonical() == {} and not Family()
    for bad in (dict(partner={"p01": "p02"}), dict(partner={"p01": "p01"}), dict(partner={"p01": "p09", "p09": "p01"}),
                dict(pregnant={"p02": (70, "p02")}), dict(grief={"p09": 5}), dict(guardian={"p05": "p05"}),
                dict(arrivals=1, last_arrival=99)):
        with pytest.raises(ValueError):
            replace(world, family=Family(**bad))
    with pytest.raises(ValueError):
        Family(grief={"p01": 101})


def test_a_lifespan_is_fixed_by_the_seed_and_the_name_and_inside_the_declared_range():
    config = cfg()
    spans = {a: lifespan(config, a) for a in ("p01", "p02", "p03", "p04")}
    assert spans == {a: lifespan(config, a) for a in spans} and len(set(spans.values())) > 1
    assert all(480 <= n <= 640 for n in spans.values())
    assert lifespan(cfg(seed=8), "p01") != lifespan(config, "p01") or lifespan(cfg(seed=9), "p01") != lifespan(config, "p01")
    assert [stage(config, a) for a in (10, 60, 299, 300, 700)] == ["child", "adult", "adult", "elder", "elder"]


# --- couples -------------------------------------------------------------------------------------

def step_family(config, ledger, world):
    return world_step(Engine(ledger), world, config).processed.overlay.family


def test_two_free_adults_talking_who_like_and_trust_each_other_become_a_couple():
    config, ledger, world = adults()
    # a couple forms from the tick's own conversation, so run the real tick with both choosing to talk
    world = talking(world)
    step = world_step(Engine(ledger), world, config)
    after = step.processed.overlay
    chatting = {a for a, d in step.decisions.items() if d.kind == "chat"}
    if {"p01", "p02"} <= chatting:
        assert after.family.partner == {"p01": "p02", "p02": "p01"}
    # the rule itself: given the saved conversation and bonds, the pair is made
    from world.family import advance_family
    held = replace(after, persona=replace(after.persona, talking={"p01": ("p02", 40), "p02": ("p01", 40)},
                                          bonds={"p01": (bond("p02", 18, 55),), "p02": (bond("p01", 18, 55),)}))
    made = advance_family(replace(after, family=Family()), held, config)
    assert made.partner == {"p01": "p02", "p02": "p01"}


@pytest.mark.parametrize("change", ["weak_bond", "wary", "child", "partnered", "kin", "one_sided", "not_talking"])
def test_no_couple_when_a_bond_is_weak_trust_is_low_somebody_is_a_child_taken_or_kin(change):
    from world.family import advance_family
    config, ledger, world = adults()
    held = talking(world)
    family = Family()
    if change == "weak_bond":
        held = talking(world, fond=17)
    elif change == "wary":
        held = talking(world, trust=49)
    elif change == "child":
        held = replace(held, age={**held.age, "p02": 10})
    elif change == "partnered":
        family = Family(partner={"p01": "p03", "p03": "p01"})
    elif change == "kin":
        held = replace(held, parent={"p02": "p01"})
    elif change == "one_sided":
        held = replace(held, persona=replace(held.persona, talking={"p01": ("p02", 38)}))
    else:
        held = replace(held, persona=replace(held.persona, talking={}))
    later = replace(held, tick=41, family=family)
    assert "p02" not in advance_family(replace(held, family=family), later, config).partner or change == "partnered" \
        and advance_family(replace(held, family=family), later, config).partner.get("p02") is None
    assert are_kin(replace(world, parent={"p02": "p01"}), "p01", "p02") and not are_kin(world, "p01", "p02")


# --- pregnancy and birth --------------------------------------------------------------------------

def side_by_side(config, world, together=2, partner=True):
    counts = {"p01|p02": together}
    family = Family(partner={"p01": "p02", "p02": "p01"}) if partner else Family()
    roster = {a: 0 for a in world.roster}
    housed = tuple(sorted({world.homes["p01"], world.homes["p02"]}))                              # each has a finished shelter
    return replace(world, together=counts, family=family, held=dict(roster), built=dict(roster), shelters=housed)


def births(config, ledger, world, tick):
    """The births step on its own, with nobody free to wander off: `world` is the overlay after the tick's movement."""
    from world.process import _births
    return _births(replace(world, tick=tick), ledger, config)


def test_a_couple_side_by_side_long_enough_makes_the_second_pregnant_and_is_not_yet_a_birth():
    config, ledger, world = adults()
    world = side_by_side(config, world, together=config.together_ticks - 1)
    overlay, grown, born = births(config, ledger, world, 41)
    assert overlay.family.pregnant == {"p02": (41 + config.lever("gestation"), "p01")}
    assert born == [] and len(overlay.roster) == 6
    other = side_by_side(config, adults()[2], together=config.together_ticks - 1, partner=False)
    assert births(config, ledger, other, 41)[0].family.pregnant == {}                            # not a couple: no child here


def test_a_pregnancy_ends_in_a_birth_beside_the_carrier_with_the_couple_as_parents():
    config, ledger, world = adults()
    world = side_by_side(config, world, together=0)
    world = replace(world, family=Family(partner={"p01": "p02", "p02": "p01"}, pregnant={"p02": (41, "p01")}))
    overlay, grown, born = births(config, ledger, world, 41)
    assert born == ["p07"] and overlay.parent["p07"] == "p02" and overlay.age["p07"] == 0
    assert overlay.family.pregnant == {} and overlay.positions["p07"] != overlay.positions["p02"]
    assert overlay.persona.traits["p07"]                                                            # traits inherited from the parents
    early = births(config, ledger, world, 40)
    assert early[2] == [] and early[0].family.pregnant == {"p02": (41, "p01")}                      # not due yet


def test_nobody_is_pregnant_past_the_population_limit_and_a_pregnant_carrier_is_hungrier():
    config, ledger, world = adults(cfg(feature_levers=(("pop_cap", 6),)))
    world = side_by_side(config, world, together=config.together_ticks - 1)
    assert births(config, ledger, world, 41)[0].family.pregnant == {}                               # six live: no room under the cap
    config, ledger, world = adults()
    world = replace(world, family=Family(partner={"p01": "p02", "p02": "p01"}, pregnant={"p02": (90, "p01")}), tick=44,
                    hunger={a: 10 for a in world.roster})
    step = world_step(Engine(replace(ledger, tick=44)), world, config)
    base = world_step(Engine(replace(ledger, tick=44)), replace(world, family=Family(), tick=44), config)
    assert step.processed.overlay.hunger["p02"] == base.processed.overlay.hunger["p02"] + 1      # tick 45 is a multiple of 3 away: +1 hunger


# --- ageing ---------------------------------------------------------------------------------------

def test_a_person_dies_of_old_age_at_their_own_fixed_age_and_not_before():
    config, ledger, world = adults()
    span = lifespan(config, "p01")
    young = replace(world, age={**world.age, "p01": span - 2})
    assert "p01" not in world_step(Engine(ledger), young, config).processed.overlay.died_at
    due = replace(world, age={**world.age, "p01": span - 1})
    step = world_step(Engine(ledger), due, config)
    assert step.processed.overlay.died_at == {"p01": step.processed.overlay.tick}                   # age reaches the span: they die
    assert step.processed.overlay.age["p01"] == span


def test_an_elder_loses_a_tick_on_every_third_step():
    from tests.test_pledges import give
    totals = {}
    for label, age in (("elder", 350), ("adult", 100)):
        config, ledger, world = adults(ages={"p01": age})
        thirsty = replace(world, thirst={**{a: 0 for a in world.roster}, "p01": 40})
        steps = play(config, give(ledger, "p01", water=0), thirsty, 14, sky=CLEAR_DAY)
        totals[label] = sum(1 for s in steps if s.processed.overlay.held["p01"] > 0)
    assert totals["adult"] == 0 and totals["elder"] >= 3                                             # about one step in three


# --- orphans and grief ----------------------------------------------------------------------------

def test_a_child_with_no_living_parent_is_taken_in_by_the_nearest_adult_who_can_see_them():
    from world.family import advance_family
    config, ledger, world = adults(ages={"p06": 10})
    kid = replace(world, parent={"p06": "p05"}, positions={**world.positions, "p06": (2, 7)},
                  died_at={"p05": 30})
    later = replace(kid, tick=41)
    taken = advance_family(kid, later, config)
    assert taken.guardian == {"p06": "p01"}                                                           # p01 stands next to the child
    far = replace(kid, positions={**kid.positions, "p06": (11, 3)})
    assert advance_family(far, replace(far, tick=41), config).guardian == {}                          # nobody in sight: nobody takes them in
    alive = replace(kid, died_at={})
    assert advance_family(alive, replace(alive, tick=41), config).guardian == {}                      # a parent still lives


def test_a_guardian_counts_as_a_parent_for_care():
    config, ledger, world = adults(ages={"p06": 10})
    held = replace(world, parent={"p06": "p05"}, died_at={"p05": 30}, positions={**world.positions, "p06": (2, 7)},
                   family=Family(guardian={"p06": "p01"}))
    assert observe("p01", ledger, held, config).dependents == frozenset({"p06"})
    assert observe("p02", ledger, held, config).dependents == frozenset()


def test_those_who_loved_the_dead_grieve_and_it_fades_and_keeps_them_from_chores():
    from world.family import advance_family
    config, ledger, world = adults()
    persona = replace(world.persona, bonds={"p01": (bond("p03", 25),), "p02": (bond("p03", 5),)})
    world = replace(world, persona=persona, parent={"p04": "p03"}, died_at={"p03": 40}, family=Family(partner={"p03": "p05", "p05": "p03"}))
    before = replace(world, died_at={})
    grieved = advance_family(before, replace(world, tick=41), config)
    assert grieved.grief == {"p01": 30, "p04": 60, "p05": 60}                                          # a friend, a child and a partner; p02 knew them too little
    assert grieved.partner == {}                                                                       # the bond ends with the death
    later = advance_family(replace(world, tick=42, family=grieved), replace(world, tick=43, family=grieved), config)
    assert later.grief["p05"] == 59                                                                    # one point every grief_fade ticks
    sad = replace(world, tick=40, family=Family(grief={"p01": 60}), died_at={})
    assert observe("p01", ledger, sad, config).grief == 60
    d = decide(observe("p01", ledger, sad, config), config)
    assert d.kind not in ("plant", "craft", "repair", "dig")


# --- travellers -----------------------------------------------------------------------------------

def arrive(config, world, ledger, tick):
    from world.process import _arrive
    roster = {a: 0 for a in world.roster}
    return _arrive(replace(world, tick=tick, held=dict(roster), built=dict(roster)), ledger, config)


def test_a_traveller_comes_only_when_few_are_left_after_a_wait_and_not_beyond_the_limit():
    config, ledger, world = adults(cfg(feature_levers=(("arrive_below", 7),)))
    after, grown, came = arrive(config, world, ledger, 130)
    assert came == ["p07"] and after.positions["p07"][0] <= 3 and after.age["p07"] == config.adult_at
    assert after.family.arrivals == 1 and after.family.last_arrival == 130 and grown.balances["p07"] == 0
    assert all(grown.holdings[r]["p07"] == 0 for r in grown.holdings)                                  # they bring nothing
    assert arrive(config, world, ledger, 100)[2] == []                                                 # too soon after the start
    crowded, _, none = arrive(cfg(feature_levers=(("arrive_below", 6),)), world, ledger, 130)
    assert none == []                                                                                  # six live: not few
    capped = replace(world, family=Family(arrivals=config.lever("max_arrivals"), last_arrival=0))
    assert arrive(config, capped, ledger, 400)[2] == []


# --- whole worlds ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("family") / "run.jsonl"
    config = WorldConfig(seed=14, features=tuple(sorted(set(FEATURES) | {"pledges", "sleep", "structures", "crafting", "farming"})),
                         wood_on=True)
    run_world(config, 700, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_a_world_with_family_life_audits_replays_and_every_change_has_a_recorded_cause(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]
    config = WorldConfig.from_describe(run.header["scenario"])
    lever = config.lever
    couples = births = old_age = adoptions = arrivals = 0
    for k in range(1, len(worlds)):
        fb, fw = worlds[k - 1].get("family") or {}, worlds[k].get("family") or {}
        persona = worlds[k]["persona"]
        for a, b in (fw.get("partner") or {}).items():
            if (fb.get("partner") or {}).get(a) != b:
                assert persona["talking"][a][0] == b and persona["talking"][b][0] == a                  # only a shared conversation
                assert worlds[k]["age"][a] >= config.adult_at and worlds[k]["age"][b] >= config.adult_at
                couples += 1
        newborn = set(worlds[k]["positions"]) - set(worlds[k - 1]["positions"])
        for who in newborn:
            parent = (worlds[k].get("parent") or {}).get(who)
            if parent:                                                                                  # a birth: from a recorded pregnancy
                assert parent in (fb.get("pregnant") or {}) and (fb["pregnant"][parent][0] <= k)
                births += 1
            else:                                                                                       # a traveller: few left, rarely
                living_before = len(worlds[k - 1]["positions"]) - len(worlds[k - 1].get("died_at", {}))
                assert living_before < lever("arrive_below") and fw["arrivals"][0] <= lever("max_arrivals")
                arrivals += 1
        for who, tick in (worlds[k].get("died_at") or {}).items():
            if tick == k and worlds[k]["age"].get(who, 0) >= lifespan(config, who):
                old_age += 1
        for child, adult in (fw.get("guardian") or {}).items():
            if (fb.get("guardian") or {}).get(child) != adult:
                parents = {worlds[k]["parent"].get(child), (worlds[k].get("second_parent") or {}).get(child)} - {None}
                assert parents and all(p in worlds[k]["died_at"] for p in parents)                      # only an orphan is taken in
                adoptions += 1
    assert arrivals >= 1 and old_age >= 1
    assert births <= couples


@pytest.mark.long_run
def test_nobody_outlives_their_own_lifespan_in_a_saved_world(saved):
    _, run = saved
    config = WorldConfig.from_describe(run.header["scenario"])
    last = run.ticks[-1]["world"]
    for who, age in (last.get("age") or {}).items():
        if who not in (last.get("died_at") or {}):
            assert age < lifespan(config, who)
