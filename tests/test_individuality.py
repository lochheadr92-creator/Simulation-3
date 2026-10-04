"""Traits, skills and sleep: what each one changes, and that none of it leaks or breaks accounting.

The rules are in world/persona.py, world/rest.py and the decide/process hooks. These tests
build observations by hand where a single rule is the question, and run real worlds where
the question is whether the saved state survives births, replay and recovery.
"""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from world.config import WorldConfig, genesis, homes_for
from world.decide import decide, pack_size
from world.observe import Observation, SeenPerson, observe
from world.overlay import Overlay
from world.persona import Persona, draw_traits, inherit_traits
from world.recover import recover_world
from world.replay import replay_world
from world.rest import tired_threshold
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.traits import (CAUTION, DILIGENCE, GENEROSITY, SKILL_STEPS, build_goal, level_of, provision_low)

RICH = ("explain", "personality", "skills", "sleep")


def cfg(**changes):
    return WorldConfig(seed=7, features=RICH, **changes)


def traits(generosity=50, sociability=50, caution=50, diligence=50, curiosity=50):
    return (generosity, sociability, caution, diligence, curiosity)


def view(config, **changes):
    base = Observation(actor="p01", tick=40, alive=True, position=(2, 2), home=(2, 2), hunger=0, food=1,
                       source=(6, 6), source_food=None, thirst=0, water=1, water_source=(3, 3), water_stock=None,
                       traits=traits(), skills=(0,) * 5, fatigue=0, home_built=True)
    return replace(base, **changes)


# --- configuration ------------------------------------------------------------------------

def test_features_are_validated_and_round_trip_through_the_header():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert config.describe()["features"] == sorted(RICH)
    tuned = cfg(feature_levers=(("tired_at", 50), ("rest_home", 4)))      # 4 is the default: not stored
    assert tuned.feature_levers == (("tired_at", 50),)
    assert WorldConfig.from_describe(tuned.describe()) == tuned
    assert tuned.lever("tired_at") == 50 and tuned.lever("collapse_at") == 100
    assert "features" not in WorldConfig(seed=7).describe()


@pytest.mark.parametrize("bad", [
    dict(features=("nonsense",)), dict(features=("sleep", "explain")), dict(features=("sleep", "sleep")),
    dict(features=("sleep",), feature_levers=(("tired_at", -1),)),
    dict(features=("sleep",), feature_levers=(("wake_at", 70),)),          # wake_at must stay under tired_at
    dict(features=("sleep",), feature_levers=(("rest_home", 0),)),
    dict(features=("explain",), feature_levers=(("tired_at", 50),)),       # a setting of a feature that is off
    dict(features=("sleep",), scoring_on=True, water_on=False, warmth_on=False),
])
def test_bad_feature_configurations_are_refused(bad):
    with pytest.raises(ValueError):
        WorldConfig(seed=7, **bad)


def test_the_header_cannot_claim_features_the_rules_do_not_write():
    described = cfg().describe()
    for tamper in (dict(features=["sleep", "ghosts"]), dict(feature_levers={"tired_at": "60"}),
                   dict(feature_rules={"sleep": "people never tire"})):
        with pytest.raises(ValueError):
            WorldConfig.from_describe(dict(described, **tamper))


def test_cli_accepts_features_and_levers():
    config = config_from(build_parser().parse_args(
        ["--seed", "7", "--features", "sleep,personality", "--lever", "tired_at=45"]))
    assert config.features == ("personality", "sleep") and config.lever("tired_at") == 45
    plain = config_from(build_parser().parse_args(["--seed", "7", "--features", "sleep,personality"]))
    assert "personality+sleep" in run_id_for(plain, 100)                  # few features: named
    assert run_id_for(config, 100) != run_id_for(plain, 100)              # a different setting is a different run
    with pytest.raises(ValueError):
        config_from(build_parser().parse_args(["--seed", "7", "--features", "sleep", "--lever", "tired_at=x"]))


# --- the persona state --------------------------------------------------------------------

def test_persona_round_trips_and_is_strictly_validated():
    ledger, overlay = genesis(cfg())
    again = Overlay.from_canonical(overlay.canonical())
    assert again.canonical() == overlay.canonical() and again.persona == overlay.persona
    for bad in ({"traits": {"p01": [1, 2, 3]}}, {"traits": {"p01": [1, 2, 3, 4, 101]}}, {"fatigue": {"p01": -1}},
                {"skills": {"p01": [0, 0, 0, 0, -1]}}, {"asleep": {"p01": "now"}},
                {"tried": {"p01": [["claim", "food", 3, 2]]}}, {"unknown": {}}):
        with pytest.raises(ValueError):
            Persona.from_canonical(bad)
    canonical = overlay.canonical()
    canonical["persona"] = dict(canonical["persona"], traits={"p01": [50] * 5})        # not everybody
    with pytest.raises(ValueError):
        Overlay.from_canonical(canonical)
    canonical = overlay.canonical()
    canonical["persona"] = dict(canonical["persona"], asleep={"p01": 99})              # after the overlay's tick
    with pytest.raises(ValueError):
        Overlay.from_canonical(canonical)


def test_traits_come_from_their_own_generator_and_never_move_a_home():
    base = WorldConfig(seed=7)
    rich = cfg()
    assert homes_for(base) == homes_for(rich)
    assert genesis(base)[1].homes == genesis(rich)[1].homes
    assert genesis(base)[1].yield_at == genesis(rich)[1].yield_at
    assert draw_traits(7, rich.actor_ids()) == draw_traits(7, rich.actor_ids())
    assert draw_traits(7, rich.actor_ids()) != draw_traits(8, rich.actor_ids())
    assert all(10 <= v <= 90 for values in draw_traits(7, rich.actor_ids()).values() for v in values)


def test_a_newborn_inherits_its_two_adults_with_a_bounded_deterministic_offset():
    first, second = traits(20, 30, 40, 50, 60), traits(60, 70, 80, 90, 94)
    child = inherit_traits(7, "p09", first, second)
    assert child == inherit_traits(7, "p09", first, second)
    assert child != inherit_traits(7, "p10", first, second)
    for index in range(5):
        assert abs(child[index] - (first[index] + second[index]) // 2) <= 15 or child[index] in (5, 95)
        assert 5 <= child[index] <= 95


# --- what traits change -------------------------------------------------------------------

def test_a_stingy_person_keeps_their_last_unit_from_a_stranger_but_feeds_their_own_child():
    config = cfg()
    stranger = SeenPerson("p05", (2, 3), 0, starving=True)
    child = SeenPerson("p06", (2, 3), 0, starving=True)
    for generosity, expect in ((20, "rest"), (50, "offer"), (90, "offer")):
        made = decide(view(config, traits=traits(generosity=generosity), others=(stranger,), food=1), config)
        assert made.kind == expect, generosity
    stingy = view(config, traits=traits(generosity=20), others=(stranger,), food=1)
    assert any(r[:2] == ("offer", "unwilling") for r in decide(stingy, config).rejected)
    assert decide(replace(stingy, food=2), config).kind == "offer"                      # holding two: spares one
    own = view(config, traits=traits(generosity=20), others=(child,), food=1, dependents=frozenset({"p06"}),
               children=frozenset({"p06"}))
    assert decide(own, replace(config, childhood_on=True)).kind == "offer"


def test_a_generous_person_hands_water_to_somebody_visibly_parched_and_others_do_not():
    config = cfg()
    parched = SeenPerson("p05", (2, 3), 0, parched=True)
    for generosity, kind in ((90, "offer"), (60, "rest"), (10, "rest")):
        made = decide(view(config, traits=traits(generosity=generosity), others=(parched,), water=2), config)
        assert made.kind == kind, generosity
    gift = decide(view(config, traits=traits(generosity=90), others=(parched,), water=2), config)
    assert (gift.target, gift.resource, gift.amount) == ("p05", "water", 1)
    assert decide(view(config, traits=traits(generosity=90), others=(parched,), water=1), config).kind != "offer"
    far = SeenPerson("p05", (2, 5), 0, parched=True)
    walking = decide(view(config, traits=traits(generosity=90), others=(far,), water=2), config)
    assert walking.kind == "go_offer" and walking.resource == "water" and walking.step is not None


def test_a_cautious_person_sets_off_earlier_than_a_bold_one():
    config = cfg()
    base = dict(food=0, hunger=17, position=(2, 2), source=(7, 2))        # five steps from food, hunger 17
    kinds = {}
    for caution in (10, 50, 90):
        kinds[caution] = decide(view(config, traits=traits(caution=caution), **base), config).kind
    assert kinds == {10: "rest", 50: "rest", 90: "go"}
    assert decide(view(config, traits=(), **base), config).kind == "rest"        # no traits: unchanged
    thirsty = dict(water=0, thirst=11, position=(2, 2), water_source=(6, 2))
    assert decide(view(config, traits=traits(caution=90), **thirsty), config).kind == "go_water"
    assert decide(view(config, traits=traits(caution=10), **thirsty), config).kind != "go_water"


def test_diligence_and_caution_move_when_somebody_goes_to_bed():
    config = cfg()
    assert tired_threshold(config, traits()) == 60
    assert tired_threshold(config, traits(diligence=100)) == 70
    assert tired_threshold(config, traits(diligence=0)) == 50
    assert tired_threshold(config, traits(caution=100)) == 55
    assert tired_threshold(config, ()) == 60
    at_home = dict(position=(2, 2), home=(2, 2), fatigue=62)
    assert decide(view(config, traits=traits(diligence=95), **at_home), config).kind == "rest"      # works on
    assert decide(view(config, traits=traits(diligence=5), **at_home), config).kind == "sleep"


def test_diligence_changes_what_counts_as_a_low_shared_cache():
    assert (provision_low(2, traits(diligence=80)), provision_low(2, traits(diligence=50)),
            provision_low(2, traits(diligence=10)), provision_low(2, ())) == (3, 2, 1, 2)
    assert provision_low(1, traits(diligence=10)) == 1


# --- sleep -------------------------------------------------------------------------------

def test_tired_people_sleep_at_home_and_walk_home_first_otherwise():
    config = cfg()
    home = decide(view(config, fatigue=70), config)
    assert home.kind == "sleep" and home.step is None and "tired" in home.reason
    away = decide(view(config, fatigue=70, position=(5, 2)), config)
    assert away.kind == "go_sleep" and away.step is not None
    assert abs(away.step[0] - 2) + abs(away.step[1] - 2) < 3 + 0                         # a step towards home
    assert decide(view(config, fatigue=30), config).kind == "rest"


def test_a_sleeper_stays_asleep_until_rested():
    config = cfg()
    keeps = decide(view(config, fatigue=40, asleep=True), config)
    assert keeps.kind == "sleep" and "asleep" in keeps.reason
    assert decide(view(config, fatigue=config.lever("wake_at"), asleep=True), config).kind != "sleep"


def test_a_sleeper_wakes_only_for_an_urgent_need_judged_by_the_time_to_reach_and_finish_it():
    config = cfg()
    far = dict(fatigue=40, asleep=True, water=0, water_source=(8, 2))     # eight steps to water, ten ticks to finish
    calm = decide(view(config, thirst=40, **far), config)                  # slack 20: not urgent yet
    assert calm.kind == "sleep"
    urgent = decide(view(config, thirst=60, **far), config)                # slack 10 <= 10 + margin: wake
    assert urgent.kind == "go_water"
    near = dict(fatigue=40, asleep=True, water=0, water_source=(3, 2))
    assert decide(view(config, thirst=60, **near), config).kind == "sleep"  # one step away: can wait
    assert decide(view(config, thirst=70, **near), config).kind in ("go_water", "draw")


def test_a_tired_person_is_not_allowed_to_start_sleeping_while_a_need_cannot_wait():
    config = cfg()
    thirsty = view(config, fatigue=80, water=0, water_source=(3, 2), thirst=72)       # slack 4, water 1 step + 2 to finish
    made = decide(thirsty, config)
    assert made.kind != "sleep"
    assert any(r[:2] == ("sleep", "too_late") for r in made.rejected)


def test_a_nearly_finished_errand_is_finished_before_sleep_when_there_is_time():
    config = cfg()
    en_route = view(config, fatigue=65, hunger=27, food=0, position=(6, 3), source=(7, 3), home=(2, 2))
    made = decide(en_route, config)
    assert made.kind in ("go", "claim")
    assert any(r[:2] == ("sleep", "less_urgent") for r in made.rejected)
    no_time = replace(en_route, fatigue=96)
    assert decide(no_time, config).kind in ("go_sleep", "sleep", "collapse")


def test_exhaustion_collapses_wherever_they_stand_and_nothing_else_is_possible():
    config = cfg()
    made = decide(view(config, fatigue=100, position=(9, 9), hunger=60, thirst=60, water=0, food=0), config)
    assert made.kind == "collapse" and made.step is None and "collapsed" in made.reason


def test_a_collapsed_person_stays_down_until_some_exhaustion_is_slept_off():
    config = cfg()
    down = view(config, fatigue=97, asleep=True, position=(9, 9), hunger=70, food=0)       # starving, but too weak to rise
    assert decide(down, config).kind == "collapse"
    assert decide(replace(down, fatigue=90), config).kind != "collapse"                     # now they can get up
    assert decide(view(config, fatigue=70, asleep=True), config).kind == "sleep"            # ordinary sleepers differ


def test_exhaustion_still_allows_one_bite_or_sip_when_a_need_is_at_its_emergency_level():
    config = cfg()
    eat = decide(view(config, fatigue=100, hunger=config.emergency_at, food=1), config)
    assert eat.kind == "eat"
    drink = decide(view(config, fatigue=100, thirst=config.thirst_emergency_at, water=1, food=0), config)
    assert drink.kind == "drink"
    assert decide(view(config, fatigue=100, hunger=config.emergency_at - 1, food=1), config).kind == "collapse"


def test_sleep_is_not_started_while_a_need_is_in_emergency_but_a_sleeper_is_not_jolted_awake_by_one():
    config = cfg()
    starving = view(config, fatigue=70, hunger=config.emergency_at, food=0, source=(3, 2), position=(2, 2))
    made = decide(starving, config)
    assert made.kind != "sleep" and any(r[:2] == ("sleep", "too_late") for r in made.rejected)
    asleep = view(config, fatigue=70, asleep=True, hunger=config.emergency_at, food=0, source=(9, 9))
    assert decide(asleep, config).kind == "sleep"            # far from food but not yet running out: stays down


def test_a_sleeper_sees_only_their_own_cell_and_others_can_see_they_sleep():
    config = cfg()
    ledger, world = genesis(config)
    near = {a: p for a, p in world.positions.items()}
    positions = dict(near, p02=(near["p01"][0] + 1, near["p01"][1]))
    persona = replace(world.persona, asleep={"p01": 0})
    asleep_world = replace(world, positions=positions, persona=persona)
    seen = observe("p01", ledger, asleep_world, config)
    assert seen.asleep and seen.others == ()
    assert seen.source_food is None and seen.water_stock is None          # no stock seen beyond their own cell
    other = observe("p02", ledger, asleep_world, config)
    sleeper = next(person for person in other.others if person.actor == "p01")
    assert sleeper.asleep


# --- skills ------------------------------------------------------------------------------

def test_skill_levels_follow_the_declared_steps():
    assert SKILL_STEPS == (0, 8, 24, 48, 80, 120)
    assert [level_of(p) for p in (0, 7, 8, 23, 24, 47, 48, 79, 80, 119, 120, 999)] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]


def test_skills_make_packs_bigger_and_shelters_quicker():
    config = cfg()
    novice, adept = view(config, skills=(0, 0, 0, 0, 0)), view(config, skills=(48, 80, 120, 0, 0))
    assert pack_size(novice, config) == config.claim_amount
    assert pack_size(adept, config) == config.claim_amount + 1                       # gathering level 3: one more
    assert pack_size(adept, config, "fish") == config.claim_amount + 2               # fishing level 4: two more
    assert (build_goal(12, (0, 0, 0, 0, 0)), build_goal(12, (0, 0, 120, 0, 0)), build_goal(12, ())) == (12, 7, 12)
    assert build_goal(3, (0, 0, 120, 0, 0)) == 3                                     # never below a short configured total


# --- whole worlds --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("rich") / "run.jsonl"
    config = WorldConfig(seed=11, features=RICH)
    run_world(config, 200, path)
    return config, path, read_run(path)


@pytest.mark.long_run
def test_a_rich_world_verifies_audits_replays_and_repeats(saved, tmp_path):
    config, path, run = saved
    assert run.complete and audit_run(run) == []
    assert replay_world(path).identical
    run_world(config, 200, tmp_path / "again.jsonl")
    assert read_run(tmp_path / "again.jsonl").ticks == run.ticks            # every line, seals included


@pytest.mark.long_run
def test_a_rich_world_recovers_from_a_cut_with_sleepers_and_newborns(saved, tmp_path):
    _, path, run = saved
    asleep_ticks = [i for i, t in enumerate(run.ticks) if t["world"].get("persona", {}).get("asleep")]
    births = [i for i, t in enumerate(run.ticks) if any("born" in e for e in (t.get("production") or []))]
    assert asleep_ticks and births, "the saved world must contain sleepers and births for this to prove anything"
    lines = path.read_bytes().splitlines(keepends=True)
    for completed in (asleep_ticks[len(asleep_ticks) // 2], births[0] + 1):
        end = next(i for i, line in enumerate(lines)
                   if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == completed - 1)
        cut, restored = tmp_path / f"cut-{completed}.jsonl", tmp_path / f"restored-{completed}.jsonl"
        cut.write_bytes(b"".join(lines[:end + 1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks


@pytest.mark.long_run
def test_inner_state_survives_births_and_covers_everyone(saved):
    _, _, run = saved
    last = run.ticks[-1]["world"]
    people = set(last["positions"])
    persona = last["persona"]
    assert set(persona["traits"]) == people and set(persona["skills"]) == people and set(persona["fatigue"]) == people
    newborn = next(e["born"] for t in run.ticks for e in (t.get("production") or []) if "born" in e)
    born_at = next(i for i, t in enumerate(run.ticks) if any(e.get("born") == newborn for e in (t.get("production") or [])))
    assert run.ticks[born_at]["world"]["persona"]["fatigue"][newborn] == 0
    assert run.ticks[born_at]["world"]["persona"]["skills"][newborn] == [0] * 5


@pytest.mark.long_run
def test_nobody_dies_of_tiredness_and_sleepers_are_never_the_dead(saved):
    config, _, run = saved
    for index, tick in enumerate(run.ticks):
        world = tick["world"]
        assert not (set(world["persona"].get("asleep", {})) & set(world["died_at"]))      # the dead are not asleep
        for actor in world["died_at"]:
            if world["died_at"][actor] == tick["tick"] + 1:
                hungry = world["hunger"][actor] >= config.death_at
                thirsty = world["thirst"][actor] >= config.thirst_death_at
                cold = world["cold"][actor] >= config.cold_death_at
                assert hungry or thirsty or cold                                         # fatigue is never the cause


@pytest.mark.long_run
def test_work_and_sleep_move_fatigue_by_the_declared_rates(saved):
    config, _, run = saved
    before = run.header["world"]
    checked = {"worked": 0, "slept_home": 0, "awake": 0}
    for tick in run.ticks:
        after = tick["world"]
        for actor, decision in tick["decisions"].items():
            if actor in after["died_at"] or actor not in before["persona"]["fatigue"]:
                continue
            was, now = before["persona"]["fatigue"][actor], after["persona"]["fatigue"][actor]
            kind = decision["kind"]
            if kind in ("sleep", "collapse"):
                rate = config.lever("rest_home") if after["positions"][actor] == after["homes"][actor] else config.lever("rest_open")
                assert now == max(0, was - rate)
                checked["slept_home"] += after["positions"][actor] == after["homes"][actor]
            elif kind in ("build", "claim", "fish", "gather_wood"):
                assert now == was + config.lever("fatigue_rate") + config.lever("work_fatigue")
                checked["worked"] += 1
            else:
                assert now == was + config.lever("fatigue_rate")
                checked["awake"] += 1
        before = after
    assert all(checked.values()), checked


# --- regressions found by watching ordinary worlds ---------------------------------------------

def test_a_cautious_person_who_arrives_early_stocks_up_instead_of_turning_round():
    """Cautious people set off early. Arriving before they were hungry they used to be unable to claim,
    walked home, set off again, and so on. Arriving within their own margin, they now collect."""
    config = cfg()
    at_source = dict(position=(7, 2), source=(7, 2), source_food=3, food=0, hunger=22)
    cautious = decide(view(config, traits=traits(caution=90), **at_source), config)
    assert cautious.kind == "claim" and "cautious" in cautious.reason and cautious.amount > 0
    for caution in (50, 10):
        assert decide(view(config, traits=traits(caution=caution), **at_source), config).kind != "claim"
    assert decide(view(config, traits=(), **at_source), config).kind != "claim"
    assert decide(view(config, traits=traits(caution=90), **dict(at_source, hunger=10)), config).kind != "claim"
    assert decide(view(config, traits=traits(caution=90), **dict(at_source, source_food=0)), config).kind != "claim"
    assert decide(view(config, traits=traits(caution=90), **dict(at_source, food=1)), config).kind != "claim"


def test_a_cautious_person_who_arrives_early_at_the_well_draws_water():
    config = cfg()
    at_well = dict(position=(3, 3), water_source=(3, 3), water_stock=5, water=0, thirst=20)
    made = decide(view(config, traits=traits(caution=90), **at_well), config)
    assert made.kind == "draw" and "cautious" in made.reason
    assert decide(view(config, traits=traits(caution=50), **at_well), config).kind != "draw"
    assert decide(view(config, traits=traits(caution=90), **dict(at_well, water=1)), config).kind != "draw"


def test_what_somebody_was_just_doing_decides_a_boundary_case_so_they_do_not_flip_flop():
    from world.decide import COMMITMENT, _relief_wait, _trip_home
    config = cfg()
    base = view(config, hunger=30, food=0, position=(4, 2), home=(2, 2), source=(7, 2), source_food=3)
    cost = _relief_wait(base, config, "food") + _trip_home(base, "food") + config.lever("urgent_margin")
    on_the_edge = replace(base, fatigue=config.lever("collapse_at") - cost)      # slack equals cost + margin exactly
    assert decide(on_the_edge, config).kind == "go_sleep"                        # no history: sleep wins the tie
    assert decide(replace(on_the_edge, doing="go"), config).kind == "go"          # on an errand: finish it
    assert decide(replace(on_the_edge, doing="go_sleep"), config).kind == "go_sleep"
    just_inside = replace(on_the_edge, fatigue=on_the_edge.fatigue - COMMITMENT - 1, doing="go_sleep")
    assert decide(just_inside, config).kind == "go"                               # but a clear gap still wins


def test_waiting_at_an_empty_source_does_not_postpone_sleep_for_ever():
    """An empty source may take a whole renewal period to give anything. Waiting for it postpones sleep only
    while that period, the walk home and the margin still fit before collapse."""
    config = cfg()
    waiting = view(config, hunger=30, food=0, position=(7, 2), source=(7, 2), source_food=0, home=(2, 2),
                   doing="wait")
    cost = config.renewal_every + 2 + 6 + config.lever("urgent_margin")           # period + walk home + lie down + margin
    assert decide(replace(waiting, fatigue=config.lever("collapse_at") - cost - 1), config).kind == "wait"
    assert decide(replace(waiting, fatigue=config.lever("collapse_at") - cost + 1), config).kind == "go_sleep"


@pytest.mark.long_run
def test_nobody_turns_round_every_tick_between_an_errand_and_bed(tmp_path):
    """Seed 14 over 300 ticks used to show people alternating go / go_sleep tick after tick."""
    for seed in (14, 64):
        path = tmp_path / f"s{seed}.jsonl"
        run_world(WorldConfig(seed=seed, features=RICH), 300, path)
        history = {}
        for tick in read_run(path).ticks:
            for actor, decision in tick["decisions"].items():
                last = history.setdefault(actor, [])
                last.append(decision["kind"])
                if len(last) >= 3 and last[-3] == last[-1] and last[-2] != last[-1]:
                    pair = {last[-3], last[-2]}
                    assert pair not in ({"go", "go_sleep"}, {"go_water", "go_sleep"}), (seed, actor, last[-3:])
