"""Wolves, injuries, and what people believe about them.

The belief store is checked as a unit (merging, forgetting, hearsay keeping its date, strict
validation). Wolf rules are checked one at a time. Then knowledge: what a person observes
and decides depends only on what they can see and what they believe, never on a wolf out of
sight. Then decisions, the process that applies bites and healing, and whole saved worlds:
every belief in a saved run traces to a sighting or a telling the run recorded, and replay,
recovery and the ledger audit still agree.
"""

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from world.belief import advance_beliefs, check_belief, confidence, file_beliefs
from world.config import WorldConfig, genesis
from world.decide import (Decision, _danger_plan, decide, errand_holds, flee_step, risk_note, route_step)
from world.observe import Observation, observe
from world.overlay import Overlay
from world.persona import Persona
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world
from world.sky import Sky
from world.things import Things
from world.viewer import render_html
from world.viewer_index import build_index
from world.wolves import (Wolf, advance_wolves, choose_den, danger_cells, hunting_hours, is_active, mend, spawn)

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ("beliefs", "explain", "sky", "sleep", "steady", "wolves")
DAY = Sky("day", "clear", 14, 20)
DUSK = Sky("dusk", "clear", 12, 80)
NIGHT = Sky("night", "clear", 7, 100)


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


# --- configuration -------------------------------------------------------------------------

def test_header_round_trips_and_the_wolf_settings_are_validated():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert "wolves" in config.describe()["feature_rules"] and "beliefs" in config.describe()["feature_rules"]
    for features in (("wolves",), ("beliefs", "wolves"), ("sky", "wolves")):
        with pytest.raises(ValueError):
            WorldConfig(seed=7, features=features)                       # wolves need beliefs and the sky
    for bad in ((("wolves", 0),), (("limp_at", 100),), (("bite", 100),), (("heal_every", 0),), (("memory_span", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)


# --- beliefs -----------------------------------------------------------------------------

def belief(subject="w1", x=4, y=5, seen=10, learned=10, via="", kind="wolf"):
    return (kind, subject, x, y, seen, learned, via)


def test_the_later_sighting_replaces_the_earlier_and_first_hand_wins_a_tie():
    config = cfg()
    held = (belief(seen=10, learned=10),)
    assert file_beliefs(held, (belief(x=6, seen=14, learned=14),), 20, config) == (belief(x=6, seen=14, learned=14),)
    assert file_beliefs(held, (belief(x=6, seen=8, learned=12, via="p02"),), 20, config) == held       # older news never replaces
    told = belief(x=9, seen=10, learned=12, via="p02")
    assert file_beliefs((told,), (belief(x=3, seen=10, learned=10),), 20, config) == (belief(x=3, seen=10, learned=10),)
    assert file_beliefs((belief(x=3, seen=10, learned=10),), (told,), 20, config) == (belief(x=3, seen=10, learned=10),)


def test_beliefs_fade_after_the_memory_span_and_only_the_freshest_slots_are_kept():
    config = cfg(feature_levers=(("memory_span", 50), ("memory_slots", 3)))
    old = belief(subject="w1", seen=10, learned=10)
    assert file_beliefs((old,), (), 60, config) == (old,)                      # exactly the span: still there
    assert file_beliefs((old,), (), 61, config) == ()                          # one tick more and it is forgotten
    many = tuple(belief(subject=f"w{i}", seen=40 + i, learned=40 + i) for i in range(1, 6))
    kept = file_beliefs((), many, 60, config)
    assert [b[1] for b in kept] == ["w3", "w4", "w5"]                          # the three most recently seen, in a fixed order


def test_confidence_falls_with_age_and_hearsay_counts_for_three_quarters():
    first, heard = belief(seen=100), belief(seen=100, learned=110, via="p02")
    assert confidence(first, 100, 200) == 100 and confidence(first, 150, 200) == 75 and confidence(first, 300, 200) == 0
    assert confidence(heard, 100, 200) == 75 and confidence(heard, 150, 200) == 75 * 3 // 4       # 75 fresh, then three quarters of it


@pytest.mark.parametrize("entry", [
    ("wolf", "w1", 1, 2, 3, 4),                                   # too short
    ("bear", "w1", 1, 2, 3, 4, ""),                               # not a kind of thing
    ("wolf", "", 1, 2, 3, 4, ""),                                 # nothing identified
    ("wolf", "w1", -1, 2, 3, 4, ""), ("wolf", "w1", 1, 2.5, 3, 4, ""), ("wolf", "w1", 1, 2, True, 4, ""),
    ("wolf", "w1", 1, 2, 5, 4, ""),                               # learned before it was seen
    ("wolf", "w1", 1, 2, 3, 99, ""),                              # learned after the overlay's tick
    ("wolf", "w1", 1, 2, 3, 4, "p9"), ("wolf", "w1", 1, 2, 3, 4, "p1"),     # told by a stranger, or by themselves
])
def test_a_belief_in_a_saved_run_is_checked_strictly(entry):
    with pytest.raises(ValueError):
        check_belief("p1", entry, {"p1", "p2"}, 50)
    assert check_belief("p1", ("wolf", "w1", 1, 2, 3, 4, "p2"), {"p1", "p2"}, 50) == ("wolf", "w1", 1, 2, 3, 4, "p2")


def test_beliefs_and_hurt_survive_the_canonical_form_and_are_validated_against_the_roster():
    persona = Persona(beliefs={"p1": (belief(subject="w2"), belief(subject="w1", via="p2", learned=12))},
                      hurt={"p1": 25, "p2": 0})
    again = Persona.from_canonical(json.loads(json.dumps(persona.canonical())))
    assert again == persona and [b[1] for b in again.beliefs["p1"]] == ["w1", "w2"]
    persona.check({"p1", "p2"}, 50)
    with pytest.raises(ValueError):
        persona.check({"p2"}, 50)                                           # beliefs of somebody the world does not know
    with pytest.raises(ValueError):
        Persona(beliefs={"p1": (belief(), belief(x=7))})                    # the same thing twice
    with pytest.raises(ValueError):
        Persona(hurt={"p1": -1})


def overlays(config=None, **changes):
    config = config or cfg()
    ledger, world = genesis(config)
    return config, ledger, replace(world, **changes)


def test_an_overlay_with_wolves_beliefs_and_hurt_survives_its_canonical_form():
    config, ledger, world = overlays()
    full = replace(world, tick=60, things=Things(wolves=(Wolf("w1", (3, 4), 2, 5, (0, 3)), Wolf("w2", (9, 9)))),
                   persona=replace(world.persona, hurt={"p01": 25}, beliefs={"p02": (belief(seen=50, learned=52, via="p01"),)}))
    again = Overlay.from_canonical(json.loads(json.dumps(full.canonical())))
    assert again == full and again.digest() == full.digest()
    assert again.things.wolves[0].den == (0, 3) and again.things.wolves[1].den == (9, 9)
    with pytest.raises(ValueError):
        Overlay.from_canonical({**full.canonical(), "things": {"wolves": [["w1", 1, 2, 0, 0]]}})      # a wolf without its den
    with pytest.raises(ValueError):
        Things(wolves=(Wolf("w1", (1, 1)), Wolf("w1", (2, 2))))                                       # two wolves with one name


def test_hearsay_keeps_the_date_of_the_sighting_and_never_gets_fresher():
    config, ledger, world = overlays()
    first = replace(world, tick=30)
    nxt = replace(world, tick=31)
    told = Decision("p01", "rest", "", (), told_to=("p02",), told=(("wolf", "w1", 4, 5, 22),))
    # p01 saw the wolf at tick 22 and is only passing it on at tick 30
    after = advance_beliefs(first, nxt, {"p01": told}, {}, config)
    assert after["p02"] == (("wolf", "w1", 4, 5, 22, 30, "p01"),)           # seen 22, learned 30, told by p01
    held = replace(first, persona=replace(first.persona, beliefs={"p02": after["p02"]}))
    again = advance_beliefs(held, replace(world, tick=32), {"p03": replace(told, told_to=("p02",))}, {}, config)
    assert again["p02"][0][4] == 22                                         # a second telling of the same news does not freshen it


def test_a_sighting_is_dated_to_the_tick_it_was_seen_and_the_dead_are_not_told():
    config, ledger, world = overlays()
    view = Observation(actor="p01", tick=40, alive=True, position=(2, 2), home=(2, 2), hunger=0, food=1,
                       source=(6, 6), source_food=None, wolves_seen=(("w1", (4, 4)),))
    prev, nxt = replace(world, tick=40), replace(world, tick=41, died_at={"p02": 41})
    told = Decision("p01", "rest", "", (), told_to=("p02", "p03"), told=(("wolf", "w1", 4, 4, 40),))
    out = advance_beliefs(prev, nxt, {"p01": told}, {"p01": view}, config)
    assert out["p01"] == (("wolf", "w1", 4, 4, 40, 40, ""),)                # first-hand: seen and learned on the same tick
    assert out["p03"] == (("wolf", "w1", 4, 4, 40, 40, "p01"),) and "p02" not in out


# --- the wolves ----------------------------------------------------------------------------

def test_wolves_arrive_once_at_their_dens_on_the_edge_and_the_dens_are_fixed_by_the_seed():
    config = cfg(feature_levers=(("wolves", 3),))
    arrival = config.lever("wolf_arrival")
    assert advance_wolves(config, arrival - 1, (), {}, set(), set(), DAY)[0] == ()
    wolves, bites = advance_wolves(config, arrival, (), {}, set(), set(), DAY)
    assert bites == {} and [w.id for w in wolves] == ["w1", "w2", "w3"] and wolves == spawn(config)
    for wolf in wolves:
        x, y = wolf.position
        assert wolf.position == wolf.den and (x in (0, config.width - 1) or y in (0, config.height - 1))
    assert len({w.den for w in wolves}) == 3                                             # no two share a den
    assert spawn(config) == spawn(cfg(feature_levers=(("wolves", 3),)))
    assert [w.position for w in spawn(replace(config, seed=8))] != [w.position for w in wolves]


def test_a_den_is_never_a_home_or_a_source():
    config = cfg(feature_levers=(("wolves", 3),))
    ledger, world = genesis(config)
    taken = set(world.homes.values()) | set(config.all_source_positions())
    first = spawn(config)
    blocked = spawn(config, {w.den for w in first} | taken)
    assert all(w.den not in taken | {f.den for f in first} for w in blocked)
    assert choose_den(config, 0, set()) == first[0].den and choose_den(config, 0, {first[0].den}) != first[0].den
    wolves, _ = advance_wolves(config, config.lever("wolf_arrival"), (), {}, set(), set(), DAY, taken)
    assert not {w.den for w in wolves} & taken


def stand(wolf_at, person_at, config=None, sky=NIGHT, covered=(), pause=0, chase=0):
    config = config or cfg()
    wolf = Wolf("w1", wolf_at, pause, chase)
    return advance_wolves(config, 100, (wolf,), {"p01": person_at}, {"p01"}, set(covered), sky)


def test_a_hunting_wolf_beside_somebody_in_the_open_bites_and_then_rests():
    config = cfg()
    (wolf,), bites = stand((5, 5), (5, 6), config)
    assert bites == {"p01": config.lever("bite")} and wolf.pause == config.lever("bite_pause") and wolf.position == (5, 5)
    assert stand((5, 5), (5, 5), config)[1] == {"p01": config.lever("bite")}               # the same cell is beside it too
    assert stand((5, 5), (5, 6), config, sky=DUSK)[1] == {"p01": config.lever("bite")}      # dusk is hunting time as well


def test_nobody_is_bitten_by_day_or_under_a_finished_shelter_or_by_a_wolf_that_is_resting():
    config = cfg()
    assert stand((5, 5), (5, 6), config, sky=DAY)[1] == {}
    assert stand((5, 5), (5, 6), config, covered=[(5, 6)])[1] == {}
    assert stand((5, 5), (5, 6), config, pause=3)[1] == {}
    assert not hunting_hours(DAY) and hunting_hours(DUSK) and hunting_hours(NIGHT)
    assert is_active(Wolf("w1", (1, 1), 2), NIGHT) and is_active(Wolf("w1", (1, 1)), NIGHT)     # at night a pause looks like a stalk
    assert not is_active(Wolf("w1", (1, 1)), DAY)


def test_a_hunting_wolf_steps_towards_the_nearest_person_within_its_sense_and_ignores_the_rest():
    config = cfg()
    near, far = (5, 9), (11, 9)
    wolves = (Wolf("w1", (5, 5)),)
    moved, bites = advance_wolves(config, 100, wolves, {"p01": near, "p02": far}, {"p01", "p02"}, set(), NIGHT)
    assert bites == {} and moved[0].position == (5, 6) and moved[0].chase == 1           # one step towards p01, four away
    ignored, _ = advance_wolves(config, 100, wolves, {"p02": far}, {"p02"}, set(), NIGHT)
    assert ignored[0].chase == 0 and manhattan(ignored[0].position, (5, 5)) <= 1          # nobody in sense: it prowls


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def test_a_chase_that_goes_nowhere_ends_and_the_wolf_goes_back_to_its_den_to_rest():
    config = cfg()
    limit = config.lever("chase_limit")
    (gave_up,), bites = stand((5, 5), (5, 9), config, chase=limit)
    assert bites == {} and gave_up.pause == config.lever("giveup_pause") and gave_up.chase == 0
    den = (2, 6)
    wolf = Wolf("w1", (6, 6), pause=3, den=den)
    for _ in range(3):
        (wolf,), _ = advance_wolves(config, 100, (wolf,), {}, set(), set(), NIGHT)
    assert wolf.pause == 0 and wolf.position == (3, 6)                                   # one step towards the den a tick, resting
    (by_day,), _ = advance_wolves(config, 100, (Wolf("w1", (6, 6), den=den),), {"p01": (6, 7)}, {"p01"}, set(), DAY)
    assert by_day.position == (5, 6)                                                     # by day it goes home, bites nobody
    (home,), _ = advance_wolves(config, 100, (Wolf("w1", den),), {"p01": den}, {"p01"}, set(), DAY)
    assert home.position == den


def test_prowling_is_deterministic_and_stays_on_the_map():
    config = cfg()
    walk = [Wolf("w1", (0, 0))]
    cells = []
    for tick in range(300):
        walk = list(advance_wolves(config, tick, tuple(walk), {}, set(), set(), NIGHT)[0])
        cells.append(walk[0].position)
        assert 0 <= walk[0].position[0] < config.width and 0 <= walk[0].position[1] < config.height
    again = [Wolf("w1", (0, 0))]
    for tick in range(300):
        again = list(advance_wolves(config, tick, tuple(again), {}, set(), set(), NIGHT)[0])
    assert again[0].position == cells[-1] and len(set(cells)) > 10


def test_hurt_mends_faster_at_rest_at_home_and_the_dead_keep_what_they_died_of():
    config = cfg()
    hurt = {"p01": 30, "p02": 30, "p03": 90}
    on_a_heal_tick = config.lever("heal_every") * 4
    out = mend(hurt, {"p01", "p02"}, {"p01"}, on_a_heal_tick, config)
    assert out == {"p01": 30 - config.lever("heal_rest"), "p02": 29, "p03": 90}
    assert mend(hurt, {"p01", "p02"}, set(), on_a_heal_tick + 1, config) == {"p01": 30, "p02": 30, "p03": 90}
    assert mend({"p01": 1}, {"p01"}, {"p01"}, 1, config) == {}                           # healed: no entry left


# --- what a person observes ------------------------------------------------------------------

def world_with_wolf(config, wolf_at, person_at, sky=NIGHT, **wolf_state):
    ledger, world = genesis(config)
    positions = dict(world.positions, p01=person_at)
    return ledger, replace(world, positions=positions, sky=sky, tick=100,
                           things=Things(wolves=(Wolf("w1", wolf_at, **wolf_state),)))


def test_a_person_sees_a_wolf_only_inside_their_sight_which_shrinks_at_night_and_in_sleep():
    config = cfg()
    day = world_with_wolf(config, (5, 8), (5, 5), DAY)
    night = world_with_wolf(config, (5, 8), (5, 5), NIGHT)
    assert observe("p01", *day, config).wolves_seen == (("w1", (5, 8)),)                  # three away: seen by day
    assert observe("p01", *night, config).wolves_seen == ()                              # night sight is two
    sleeper = replace(night[1], persona=replace(night[1].persona, asleep={"p01": 90}))
    assert observe("p01", night[0], sleeper, config).wolves_seen == ()
    on_top = world_with_wolf(config, (5, 5), (5, 5), NIGHT)
    asleep_on_top = replace(on_top[1], persona=replace(on_top[1].persona, asleep={"p01": 90}))
    assert observe("p01", on_top[0], asleep_on_top, config).wolves_seen == (("w1", (5, 5)),)   # a sleeper notices only their own cell


def test_what_they_see_includes_whether_the_wolf_looks_dangerous():
    config = cfg()
    stalking = observe("p01", *world_with_wolf(config, (5, 6), (5, 5), NIGHT), config)
    quiet_by_day = observe("p01", *world_with_wolf(config, (5, 6), (5, 5), DAY), config)
    backing_off = observe("p01", *world_with_wolf(config, (5, 6), (5, 5), NIGHT, pause=4), config)
    assert stalking.wolves_active == {"w1"} and not quiet_by_day.wolves_active
    assert backing_off.wolves_active == {"w1"}                                           # at night nobody can tell the difference
    assert stalking.compact()["wolves_seen"] == [["w1", 5, 6, 1]] and quiet_by_day.compact()["wolves_seen"] == [["w1", 5, 6, 0]]


def test_a_wolf_out_of_sight_changes_neither_what_a_person_observes_nor_what_they_decide():
    config = cfg()
    base = world_with_wolf(config, (5, 11), (5, 2), NIGHT)                    # nine rows away
    elsewhere = world_with_wolf(config, (11, 11), (5, 2), NIGHT)
    one, two = observe("p01", *base, config), observe("p01", *elsewhere, config)
    assert one == two and decide(one, config) == decide(two, config)
    assert one.wolves_seen == () and one.danger == frozenset()


def test_danger_is_only_what_they_saw_or_were_told_and_only_while_wolves_hunt():
    config = cfg()
    beliefs = (belief(subject="w1", x=5, y=5, seen=90, learned=90), belief(subject="w2", x=1, y=1, seen=40, learned=40))
    now = 100
    around = danger_cells(beliefs, (), now, config, NIGHT)
    assert (5, 5) in around and (7, 7) in around and (8, 8) not in around                # radius two about a fresh sighting
    assert all(abs(x - 1) > 2 or abs(y - 1) > 2 for x, y in around - {(x, y) for x in range(3, 8) for y in range(3, 8)})
    assert (1, 1) not in around                                                           # seen 60 ticks ago: stale
    assert danger_cells(beliefs, (), now, config, DAY) == frozenset()                     # by day nowhere is dangerous
    assert (3, 3) in danger_cells((), (("w9", (3, 3)),), now, config, NIGHT)              # a wolf in sight counts as well


# --- what they decide --------------------------------------------------------------------------

def view(config, sky=NIGHT, **changes):
    base = Observation(actor="p01", tick=100, alive=True, position=(5, 5), home=(2, 2), hunger=0, food=1,
                       source=(9, 9), source_food=None, thirst=0, water=1, water_source=(3, 3), water_stock=None,
                       fatigue=0, home_built=True, sky=sky, cold=0)
    return replace(base, **changes)


def stalked(config, wolf_at=(5, 7), **changes):
    return view(config, wolves_seen=(("w1", wolf_at),), wolves_active=frozenset({"w1"}), **changes)


def test_somebody_in_the_open_runs_from_a_stalking_wolf_within_alarm_and_says_which():
    config = cfg()
    away = decide(stalked(config), config)
    assert away.kind == "flee" and "w1 is 2 steps away" in away.reason and away.step is not None
    assert decide(stalked(config, wolf_at=(5, 9)), config).kind != "flee"                  # four steps: past the alarm
    quiet = view(config, wolves_seen=(("w1", (5, 7)),))
    assert decide(quiet, config).kind != "flee"                                           # a wolf lying quiet is nothing to run from
    sheltered = decide(stalked(config, position=(2, 2)), config)
    assert sheltered.kind != "flee"                                                       # under their own finished roof


def test_a_person_runs_for_a_built_home_and_away_from_the_wolf_when_home_is_not_built():
    config = cfg()
    built = stalked(config, wolf_at=(5, 7))
    assert flee_step(built, config) in ((4, 5), (5, 4))                                   # towards home at (2, 2), not towards the wolf
    unbuilt = replace(built, home_built=False)
    assert flee_step(unbuilt, config)[1] <= 5                                             # away from a wolf to the south
    beside = stalked(config, wolf_at=(4, 5))
    step = flee_step(beside, config)
    assert manhattan(step, (4, 5)) > 1                                                    # never onto a cell beside the wolf when another is free
    cornered = stalked(config, position=(0, 0), wolf_at=(1, 0), home_built=False)
    assert flee_step(cornered, config) == (0, 1)


def test_a_need_that_runs_out_first_comes_before_running_and_the_choice_is_recorded():
    config = cfg()
    parched = stalked(config, wolf_at=(5, 7), thirst=78, water=1)                         # one drink from death, wolf two away
    assert decide(parched, config).kind == "drink"
    assert any(r[0] == "safety" and r[1] == "less_urgent" for r in decide(parched, config).rejected)
    fine = stalked(config, wolf_at=(5, 7), thirst=30, water=1)
    assert decide(fine, config).kind == "flee"
    assert any(r[0] == "water" and r[1] == "less_urgent" for r in decide(fine, config).rejected)


def test_seeing_a_new_wolf_calls_it_out_to_everybody_awake_in_view_and_only_once():
    config = cfg()
    from world.observe import SeenPerson
    neighbours = (SeenPerson("p02", (5, 4), 0), SeenPerson("p03", (4, 5), 0, asleep=True))
    first = decide(stalked(config, others=neighbours), config)
    assert first.told_to == ("p02",) and first.told == (("wolf", "w1", 5, 7, 100),)       # the sleeper is not called to
    known = (belief(subject="w1", x=5, y=7, seen=99, learned=99),)
    again = decide(stalked(config, others=neighbours, beliefs=known), config)
    assert again.told_to == () and again.told == ()                                        # they saw it last tick as well: already said
    alone = decide(stalked(config), config)
    assert alone.told_to == ()
    assert decide(view(config, wolves_seen=(("w1", (5, 7)),), others=neighbours), config).told_to == ()   # nothing to say of a quiet wolf


def thirsty_at_home(config, sky=NIGHT, **changes):
    base = dict(position=(2, 2), home=(2, 2), thirst=30, water=0, water_source=(3, 3), home_built=True,
                danger=frozenset((x, y) for x in range(1, 6) for y in range(1, 6)),
                beliefs=(belief(subject="w1", x=3, y=4, seen=96, learned=96),))
    return view(config, sky, **{**base, **changes})


def test_somebody_puts_off_an_errand_to_a_place_a_wolf_was_lately_near_and_says_why():
    config = cfg()
    held = decide(thirsty_at_home(config), config)
    assert held.kind in ("rest", "build") and "go_water" not in held.candidates
    assert [tuple(r[:2]) for r in held.rejected if r[1] == "dangerous"] == [("go_water", "dangerous")]
    assert "a wolf was seen within 2 steps of the well, 4 ticks ago" in held.reason
    told = decide(thirsty_at_home(config, beliefs=(belief(subject="w1", x=3, y=4, seen=96, learned=98, via="p02"),)), config)
    assert "was reported by p02" in " ".join(r[2] for r in told.rejected)                 # hearsay is used, with its teller named
    stale = decide(thirsty_at_home(config, beliefs=(belief(subject="w1", x=3, y=4, seen=40, learned=40),),
                                   danger=frozenset()), config)
    assert stale.kind == "go_water"                                                       # news a long time old holds nobody back
    assert decide(thirsty_at_home(config, DAY, danger=frozenset()), config).kind == "go_water"   # by day nobody waits for wolves


def test_a_need_that_cannot_wait_sends_them_out_anyway_and_the_reason_says_it_was_a_risk():
    config = cfg()
    emergency = decide(thirsty_at_home(config, thirst=50), config)
    assert emergency.kind == "go_water" and "taking the risk: a wolf was seen within 2 steps of the well" in emergency.reason
    last_moment = decide(thirsty_at_home(config, thirst=56), config)                       # (80 - 56) // 2 = 12 ticks, 3 + 2 + margin 6
    assert last_moment.kind == "go_water" and risk_note(thirsty_at_home(config, thirst=56), config, last_moment)
    assert errand_holds(thirsty_at_home(config, thirst=56), config, "water") == ()
    assert errand_holds(thirsty_at_home(config), config, "water")[0][0] == "dangerous"


def test_a_hurt_person_at_home_stays_in_while_the_need_can_wait_and_does_not_build():
    config = cfg()
    limp = config.lever("limp_at")
    hurt = decide(thirsty_at_home(config, DAY, danger=frozenset(), beliefs=(), hurt=limp), config)
    assert hurt.kind in ("rest", "build") and any(r[1] == "hurt" for r in hurt.rejected)
    assert decide(thirsty_at_home(config, DAY, danger=frozenset(), beliefs=(), hurt=limp - 1), config).kind == "go_water"
    idle = view(config, DAY, position=(2, 2), home_built=False, hurt=limp)
    assert decide(idle, config).kind == "rest"                                            # hurt people do not put up a shelter
    assert decide(replace(idle, hurt=0), config).kind == "build"


def walk(observation, config, target, limit=60):
    """Follow the planned route step by step, with the same beliefs at every cell."""
    here, route = observation.position, [observation.position]
    for _ in range(limit):
        if here == target:
            return route
        here = route_step(replace(observation, position=here), target, config)
        route.append(here)
    return route


def test_a_planned_route_goes_round_believed_danger_when_that_is_cheaper_and_never_dithers():
    config = cfg()
    wall = frozenset((x, y) for x in (5, 6) for y in range(0, 9))                        # a believed wall of danger, open at the south end
    origin, target = (2, 4), (9, 4)
    plain = view(config, position=origin, danger=frozenset())
    cautious = view(config, position=origin, danger=wall)
    assert len(walk(plain, config, target)) == 8
    path = walk(cautious, config, target)
    assert path[-1] == target and not wall & set(path)                                   # round the south end: 17 steps beats 7 plus 2 * 6
    assert len(path) == len(set(path))                                                   # never back over a cell, never dithering
    assert _danger_plan(cautious, target, config, (3, 4))[1] > _danger_plan(plain, target, config, (3, 4))[1]


def test_when_every_way_is_dangerous_the_cheapest_still_gets_there():
    config = cfg()
    all_of_it = frozenset((x, y) for x in range(config.width) for y in range(config.height))
    path = walk(view(config, position=(2, 4), danger=all_of_it), config, (9, 4))
    assert path[-1] == (9, 4) and len(path) == 8


# --- what happens to them --------------------------------------------------------------------

def advance_one(config, world, decisions, ledger=None, observations=None):
    ledger = ledger or genesis(config)[0]
    engine = Engine(replace(ledger, tick=world.tick))        # the kernel and the overlay must be at the same tick
    record = engine.tick([])
    return advance(world, decisions, record, engine.state, config, observations)


def standing_beside(config, hurt=0, sky=NIGHT, covered=False):
    ledger, world = genesis(config)
    home = world.homes["p01"]
    near = (home[0] + 1, home[1]) if home[0] + 1 < config.width else (home[0] - 1, home[1])
    wolf = (near[0], near[1] + 1 if near[1] + 1 < config.height else near[1] - 1)
    world = replace(world, positions=dict(world.positions, p01=near), sky=sky, tick=100,
                    persona=replace(world.persona, hurt={"p01": hurt} if hurt else {}),
                    shelters=(near,) if covered else (), things=Things(wolves=(Wolf("w1", wolf),)))
    return ledger, world, near


def test_a_bite_adds_hurt_and_the_wolf_backs_off_and_shelter_makes_it_harmless():
    config = cfg()
    ledger, world, near = standing_beside(config)
    after = advance_one(config, world, {}, ledger).overlay
    assert after.persona.hurt == {"p01": config.lever("bite")} and after.things.wolves[0].pause == config.lever("bite_pause")
    ledger, covered, _ = standing_beside(config, covered=True)
    assert advance_one(config, covered, {}, ledger).overlay.persona.hurt == {}
    ledger, day, _ = standing_beside(config, sky=DAY)
    assert advance_one(config, day, {}, ledger).overlay.persona.hurt == {}


def test_enough_bites_kill_and_the_dead_keep_their_wounds():
    config = cfg()
    lethal = config.lever("lethal_hurt")
    ledger, world, _ = standing_beside(config, hurt=lethal - config.lever("bite"))
    out = advance_one(config, world, {}, ledger)
    assert "p01" in out.died and out.overlay.died_at["p01"] == 101
    assert out.overlay.persona.hurt["p01"] == lethal
    assert out.overlay.persona.hurt["p01"] == lethal                                     # the record still says what killed them


def test_a_limp_costs_a_tick_on_every_step():
    config = cfg()
    ledger, world, near = standing_beside(config, hurt=config.lever("limp_at"), sky=DAY)
    step = (near[0], max(0, near[1] - 1))
    walking = type("D", (), {"kind": "go", "step": step, "target": None, "reason": "", "candidates": ()})()
    assert advance_one(config, world, {"p01": walking}, ledger).overlay.held["p01"] == 1
    ledger, fit, near = standing_beside(config, sky=DAY)
    assert advance_one(config, fit, {"p01": walking}, ledger).overlay.held.get("p01", 0) == 0


def test_wolves_and_beliefs_leave_every_ledger_account_alone():
    config = cfg()
    ledger, world, _ = standing_beside(config)
    out = advance_one(config, world, {}, ledger)
    assert out.ledger.balances == ledger.balances and out.production == ()


# --- whole worlds ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("wolves") / "run.jsonl"
    config = WorldConfig(seed=11, features=FEATURES)
    run_world(config, 300, path)
    return config, path, read_run(path)


@pytest.mark.long_run
def test_a_wolf_world_audits_replays_and_recovers(saved, tmp_path):
    config, path, run = saved
    assert run.complete and audit_run(run) == []
    assert replay_world(path).identical
    lines = path.read_bytes().splitlines(keepends=True)
    chosen = next(i for i, t in enumerate(run.ticks) if t["world"].get("things", {}).get("wolves")
                  and any(t["world"]["persona"].get("hurt", {}).values())) + 1
    end = next(i for i, line in enumerate(lines)
               if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == chosen - 1)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks


@pytest.mark.long_run
def test_the_world_the_run_recorded_has_wolves_that_move_and_do_harm_only_in_hunting_hours(saved):
    config, _, run = saved
    wolves = [t["world"]["things"]["wolves"] for t in run.ticks if t["world"].get("things")]
    assert wolves and all(len(w) == config.lever("wolves") for w in wolves)
    first = next(i for i, t in enumerate(run.ticks) if t["world"].get("things"))
    assert first + 1 == config.lever("wolf_arrival")                                      # they appear on the arrival tick
    before, bites = run.header["world"], 0
    for tick in run.ticks:
        hurt_before = (before["persona"] or {}).get("hurt", {})
        for actor, level in (tick["world"]["persona"].get("hurt") or {}).items():
            if level > hurt_before.get(actor, 0):
                bites += 1
                assert before["sky"]["phase"] in ("dusk", "night")                        # never bitten by day
                assert tuple(tick["world"]["positions"][actor]) not in {tuple(c) for c in tick["world"].get("shelters", [])}
        before = tick["world"]
    assert bites > 0


@pytest.mark.long_run
def test_every_first_hand_belief_in_a_saved_run_was_a_sighting_the_run_recorded(saved):
    _, _, run = saved
    before, checked = run.header["world"], 0
    for tick in run.ticks:
        for actor, entries in ((tick["world"]["persona"].get("beliefs")) or {}).items():
            old = {(e[0], e[1]): e for e in ((before["persona"].get("beliefs") or {}).get(actor) or [])}
            for kind, subject, x, y, seen, learned, via in entries:
                if via or old.get((kind, subject)) == [kind, subject, x, y, seen, learned, via]:
                    continue
                seen_then = tick["observations"][actor]["wolves_seen"]                    # what they observed that tick
                assert [subject, x, y] in [entry[:3] for entry in seen_then] and seen == tick["tick"] and learned == seen
                checked += 1
        before = tick["world"]
    assert checked > 5


@pytest.mark.long_run
def test_every_hearsay_belief_traces_to_a_telling_the_run_recorded(saved):
    _, _, run = saved
    before, checked = run.header["world"], 0
    for tick in run.ticks:
        for actor, entries in ((tick["world"]["persona"].get("beliefs")) or {}).items():
            old = {(e[0], e[1]): e for e in ((before["persona"].get("beliefs") or {}).get(actor) or [])}
            for kind, subject, x, y, seen, learned, via in entries:
                if not via or old.get((kind, subject)) == [kind, subject, x, y, seen, learned, via]:
                    continue
                speaker = tick["decisions"][via]
                assert actor in speaker["told_to"] and ["wolf", subject, x, y, seen] in speaker["told"]
                assert learned == tick["tick"] and seen <= learned
                assert actor in tick["observations"][via]["sees"]                            # the speaker could see the listener
                checked += 1
        before = tick["world"]
    assert checked > 3


@pytest.mark.long_run
def test_every_flight_followed_a_stalking_wolf_the_person_saw_within_alarm(saved):
    config, _, run = saved
    flights = 0
    for tick in run.ticks:
        for actor, decision in tick["decisions"].items():
            if decision["kind"] != "flee":
                continue
            where = tick["observations"][actor]["wolves_seen"]
            at = {a: tuple(p) for a, p in run.ticks[tick["tick"] - 1]["world"]["positions"].items()}.get(actor) \
                if tick["tick"] else tuple(run.header["world"]["positions"][actor])
            assert any(active and abs(x - at[0]) + abs(y - at[1]) <= config.lever("alarm") for _, x, y, active in where)
            flights += 1
    assert flights > 3


@pytest.mark.long_run
def test_the_page_draws_wolves_and_the_index_tells_the_story(saved):
    _, _, run = saved
    assert "wolvesPart" in render_html(run)
    kinds = {e["kind"] for e in build_index(run)["events"]}
    assert {"wolves_arrive", "wolf_sighted", "warned", "bitten", "ran", "held_back"} <= kinds
    deaths = [e for e in build_index(run)["events"] if e["kind"] == "death"]
    assert deaths


@pytest.mark.long_run
def test_the_browser_shows_what_somebody_believes_about_wolves_and_how_they_know(saved, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Rich viewer test requires Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    _, _, run = saved
    event = next(e for e in build_index(run)["events"] if e["kind"] == "warned" and e["k"] > 3)
    page = tmp_path / "wolves.html"
    page.write_text(render_html(run), encoding="utf-8")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/rich_viewer.cjs"), page.as_uri(),
                             str(event["k"] + 1), event["who"]], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout)
    assert shown["errors"] == []
    text = shown["inspector"].lower()
    for expected in ("knows about wolves", f"told by {event['other']}", "only what they saw or were told", "hurt"):
        assert expected in text, expected
    assert {"wolves", "beliefs", "sky"} <= set(shown["chips"])
    assert "Wolves and danger" in " ".join(shown["eventCategories"])
    assert "feature: wolves" in shown["rules"]


def test_the_cause_of_a_death_by_wolf_is_read_from_the_recorded_hurt():
    from world.viewer_index import _cause_of_death
    cfg_header = {"feature_levers": {"lethal_hurt": 100}, "death_at": 80}
    assert _cause_of_death({"persona": {"hurt": {"p1": 100}}, "hunger": {"p1": 3}}, "p1", cfg_header) == "was killed by a wolf"
    assert _cause_of_death({"persona": {"hurt": {"p1": 99}}, "hunger": {"p1": 3}}, "p1", cfg_header) == "died"
    assert _cause_of_death({"persona": {"hurt": {"p1": 100}}, "hunger": {"p1": 80}}, "p1", cfg_header) == "starved"


def test_without_the_wolves_feature_nothing_about_them_is_recorded(tmp_path):
    path = tmp_path / "plain.jsonl"
    run_world(WorldConfig(seed=7, features=("beliefs", "sky")), 120, path)
    run = read_run(path)
    assert all("things" not in t["world"] for t in run.ticks)
    assert all("wolves_seen" not in obs for t in run.ticks for obs in t["observations"].values())
    assert all("told" not in d for t in run.ticks for d in t["decisions"].values())
