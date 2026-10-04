"""Day and night, weather, temperature and what being out in them costs.

The sky is fixed by the seed and the tick. These tests check its shape, then each
effect on warmth, sight, travel, work and tiredness, then whole saved worlds: the
recorded sky matches the rule at every tick, replay and recovery agree, and the
ledger audit still explains every account.
"""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from world.config import WorldConfig, genesis
from world.decide import cold_slack, decide, errand_holds, shelter_trip_due, slack
from world.observe import Observation, observe
from world.overlay import Overlay
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.rest import tired_threshold
from world.run import run_world, world_step
from world.sky import (SKY_LEVERS, TRANSITIONS, Sky, exposure, front_weather, phase_of, sight, sky_at,
                       storm_hold)
from world.viewer import render_html
from world.viewer_index import build_index

FEATURES = ("explain", "sky", "sleep", "steady")
WITHOUT_STEADY = ("explain", "sky", "sleep")


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


# --- the shape of the sky ------------------------------------------------------------------

def test_header_round_trips_and_levers_are_validated():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert dict(SKY_LEVERS)["day_length"] == config.lever("day_length")
    for bad in (dict(feature_levers=(("night_length", 110),)), dict(feature_levers=(("twilight", 0),)),
                dict(feature_levers=(("front_ticks", 0),)), dict(feature_levers=(("day_length", 30),))):
        with pytest.raises(ValueError):
            cfg(**bad)


def test_every_day_has_dawn_day_dusk_and_night_in_order_and_of_the_declared_lengths():
    config = cfg()
    length, night, twilight = config.lever("day_length"), config.lever("night_length"), config.lever("twilight")
    phases = [phase_of(config, moment) for moment in range(length)]
    assert phases[0] == "dawn" and phases[-1] == "night"
    assert phases.count("dawn") == phases.count("dusk") == twilight and phases.count("night") == night
    order = [p for i, p in enumerate(phases) if i == 0 or p != phases[i - 1]]
    assert order == ["dawn", "day", "dusk", "night"]
    assert sky_at(config, 0).phase == "dawn" and sky_at(config, length).phase == "dawn"      # the next day begins at dawn


def test_weather_is_fixed_by_the_seed_and_follows_the_table():
    chain = [front_weather(7, front) for front in range(400)]
    assert chain == [front_weather(7, front) for front in range(400)]
    assert chain != [front_weather(8, front) for front in range(400)]
    assert chain[0] == "clear"
    for before, after in zip(chain, chain[1:]):
        assert after in {weather for weather, _ in TRANSITIONS[before]}
    assert {"clear", "overcast", "rain", "storm"} <= set(chain)                               # all of it happens in time
    assert all(sum(weight for _, weight in row) == 100 for row in TRANSITIONS.values())
    assert ("storm", "clear") not in set(zip(chain, chain[1:])) or True                      # a storm may break to clear
    assert "storm" not in {w for w, _ in TRANSITIONS["clear"]}                                # but never out of a clear sky


def test_temperature_is_the_base_plus_the_hour_the_weather_and_a_lean_season():
    config = cfg()
    for tick in range(0, 480, 7):
        sky = sky_at(config, tick)
        hour = {"dawn": -2, "day": 2, "dusk": 0, "night": -5}[sky.phase]
        weather = {"clear": 0, "overcast": -1, "rain": -3, "storm": -5}[sky.weather]
        assert sky.temp == config.lever("base_temp") + hour + weather
    seasonal = cfg(seasons_on=True)
    lean = next(t for t in range(0, 480) if sky_at(seasonal, t).moment == sky_at(config, t).moment
                and sky_at(seasonal, t).temp != sky_at(config, t).temp)
    assert sky_at(seasonal, lean).temp == sky_at(config, lean).temp - 3


def test_the_sky_of_a_tick_survives_its_canonical_form_and_is_validated():
    sky = Sky("night", "rain", -2, 90)
    assert Sky.from_canonical(sky.canonical()) == sky
    for bad in ({"phase": "noon", "weather": "rain", "temp": 1, "moment": 1}, {"phase": "day"},
                {"phase": "day", "weather": "hail", "temp": 1, "moment": 1},
                {"phase": "day", "weather": "rain", "temp": 1.5, "moment": 1}):
        with pytest.raises(ValueError):
            Sky.from_canonical(bad)


# --- what being out in it costs --------------------------------------------------------------

def test_exposure_is_the_chill_plus_the_wet_and_nothing_under_a_finished_shelter():
    config = cfg()
    warm = Sky("day", "clear", 14, 20)
    cold_clear = Sky("night", "clear", 7, 100)           # (8 - 7 + 2) // 3 = 1
    rain = Sky("night", "rain", 4, 100)                  # (8 - 4 + 2) // 3 = 2, plus 1 for the rain
    storm = Sky("night", "storm", -1, 100)               # (8 + 1 + 2) // 3 = 3, plus 2 for the storm
    assert [exposure(config, s, False) for s in (warm, cold_clear, rain, storm)] == [0, 1, 3, 5]
    assert all(exposure(config, s, True) == 0 for s in (warm, cold_clear, rain, storm))
    assert exposure(config, None, False) == 0


def test_sight_shrinks_at_night_and_in_a_storm_but_never_below_one():
    config = cfg()
    day, night, storm, both = (Sky("day", "clear", 14, 20), Sky("night", "clear", 7, 100),
                               Sky("day", "storm", 9, 20), Sky("night", "storm", 2, 100))
    assert [sight(config, s, 3) for s in (day, night, storm, both)] == [3, 2, 2, 1]
    assert sight(config, both, 1) == 1 and sight(config, both, 0) == 0 and sight(config, None, 3) == 3


def test_people_see_less_at_night_than_by_day():
    config = cfg()
    ledger, world = genesis(config)
    near = world.positions["p01"]
    positions = dict(world.positions, p02=(min(config.width - 1, near[0] + 3), near[1]))
    if positions["p02"] == near:
        positions["p02"] = (near[0] - 3, near[1])
    by_day = replace(world, positions=positions, sky=Sky("day", "clear", 14, 20))
    at_night = replace(by_day, sky=Sky("night", "clear", 7, 100))
    assert any(p.actor == "p02" for p in observe("p01", ledger, by_day, config).others)
    assert all(p.actor != "p02" for p in observe("p01", ledger, at_night, config).others)


def advance_one(config, world, decisions, ledger=None):
    engine = Engine(ledger or genesis(config)[0])
    record = engine.tick([])
    return advance(world, decisions, record, engine.state, config)


def test_the_cold_a_person_pays_depends_on_the_sky_and_on_what_is_over_their_head():
    config = cfg(terrain_on=False, building_on=True, births_on=False)
    ledger, world = genesis(config)
    home = world.homes["p01"]
    away = (home[0] + 1, home[1]) if home[0] + 1 < config.width else (home[0] - 1, home[1])
    away_world = replace(world, positions=dict(world.positions, p01=away),
                         cold=dict(world.cold, p01=30), sky=Sky("night", "rain", 4, 100))     # exposure 3
    at_home = replace(world, cold=dict(world.cold, p01=30), sky=Sky("night", "rain", 4, 100))
    sheltered = replace(at_home, shelters=(home,))
    other_roof = replace(away_world, shelters=(away,))
    results = {name: advance_one(config, w, {}, ledger).overlay.cold["p01"]
               for name, w in (("away", away_world), ("home", at_home), ("roof", sheltered), ("other", other_roof))}
    assert results["away"] == 30 + config.cold_rate + 3                       # out in the rain at night
    assert results["home"] == 30 - (config.warming - 3) if config.warming > 3 else results["home"] == 29
    assert results["roof"] == 30 - config.warming                             # under a roof: the full warming
    assert results["other"] == 30 + config.cold_rate                          # a stranger's roof: dry, but no warming


def test_a_storm_makes_rough_ground_cost_an_extra_tick():
    config = cfg()
    ledger, world = genesis(config)
    rough = next(iter(config.terrain()[0]))
    step = type("D", (), {"kind": "go", "step": rough, "target": None, "reason": "", "candidates": ()})()
    for sky, held in ((Sky("day", "clear", 14, 20), 1), (Sky("day", "storm", 9, 20), 1 + storm_hold(Sky("day", "storm", 9, 20)))):
        out = advance_one(config, replace(world, sky=sky), {"p01": step}, ledger).overlay
        assert out.held["p01"] == held
    assert storm_hold(Sky("day", "storm", 9, 20)) == 1 and storm_hold(Sky("day", "rain", 9, 20)) == 0


# --- decisions and tiredness -----------------------------------------------------------------

def view(config, sky=None, **changes):
    base = Observation(actor="p01", tick=40, alive=True, position=(2, 2), home=(2, 2), hunger=0, food=1,
                       source=(6, 6), source_food=None, thirst=0, water=1, water_source=(3, 3), water_stock=None,
                       fatigue=0, home_built=False, sky=sky)
    return replace(base, **changes)


def test_nobody_starts_building_in_a_storm_and_the_reason_is_recorded():
    config = cfg()
    calm = decide(view(config, Sky("day", "clear", 14, 20)), config)
    assert calm.kind == "build"
    stormy = decide(view(config, Sky("day", "storm", 9, 20)), config)
    assert stormy.kind == "rest" and "storm" in stormy.reason
    assert any(r[0] == "build" and r[1] == "unavailable" for r in stormy.rejected)
    assert decide(view(config, Sky("day", "rain", 11, 20)), config).kind == "build"          # rain alone does not stop work


# --- planning in the weather -----------------------------------------------------------------

RAINY_NIGHT = Sky("night", "rain", 4, 100)         # chill 2, plus 1 for the rain: 3 more cold a tick than the plain rate
CLEAR_DAY = Sky("day", "clear", 14, 20)


def seen_in(config, sky, **changes):
    """A person standing at home, in the given sky, with the chill that sky puts on the observation."""
    return view(config, sky, **{**dict(chill=exposure(config, sky, False), home_built=True, hunger=0, food=1), **changes})


def test_the_observation_carries_the_chill_everybody_feels():
    config = cfg()
    ledger, world = genesis(config)
    for sky in (CLEAR_DAY, RAINY_NIGHT, Sky("night", "storm", -1, 100)):
        assert observe("p01", ledger, replace(world, sky=sky), config).chill == exposure(config, sky, False)
    plain = WorldConfig(seed=7)
    assert observe("p01", *genesis(plain), plain).chill == 0


def test_planning_counts_cold_at_the_rate_of_the_sky_they_are_in():
    config = cfg()
    clear = seen_in(config, CLEAR_DAY, position=(8, 2), cold=10)           # six steps from home at (2, 2)
    wet = seen_in(config, RAINY_NIGHT, position=(8, 2), cold=10)
    assert not shelter_trip_due(clear, config) and shelter_trip_due(wet, config)    # 10 + 1 * 6 < 25 <= 10 + 4 * 6
    assert cold_slack(clear, config) == slack(10, config.cold_death_at, config.cold_rate)
    assert cold_slack(wet, config) == (config.cold_death_at - 10) // 4 - 6   # the sky's rate, less the walk back
    at_home = replace(wet, position=(2, 2))
    assert cold_slack(at_home, config) == (config.cold_death_at - 10) // 4    # nothing to walk back at home
    assert cold_slack(replace(wet, chill=0), config) == slack(10, config.cold_death_at, config.cold_rate)


def thirsty_at_home(config, sky, **changes):
    return seen_in(config, sky, **{**dict(thirst=30, water=0, water_source=(11, 2), cold=10), **changes})   # nine steps away


def test_somebody_at_home_waits_out_weather_the_trip_would_not_survive_and_says_so():
    config = cfg()
    held = decide(thirsty_at_home(config, RAINY_NIGHT), config)
    assert held.kind == "rest" and "waiting out the rain at night" in held.reason
    assert "go_water" not in held.candidates
    assert [tuple(r[:2]) for r in held.rejected if r[1] == "weather"] == [("go_water", "weather")]
    assert [code for code, _ in errand_holds(thirsty_at_home(config, RAINY_NIGHT), config, "water")] == ["weather"]
    assert decide(thirsty_at_home(config, CLEAR_DAY), config).kind == "go_water"           # the same trip in fair weather


def test_a_need_that_cannot_wait_sends_them_out_whatever_the_weather():
    config = cfg()
    # thirst 48 leaves (80 - 48) // 2 = 16 ticks; the trip needs 9 + 2 plus the margin of 6
    assert decide(thirsty_at_home(config, RAINY_NIGHT, thirst=48), config).kind == "go_water"
    assert decide(thirsty_at_home(config, RAINY_NIGHT, thirst=50), config).kind == "go_water"   # an emergency never waits
    near = decide(thirsty_at_home(config, RAINY_NIGHT, water_source=(4, 2)), config)           # a short trip fits the budget
    assert near.kind == "go_water"
    warm_enough = decide(replace(thirsty_at_home(config, RAINY_NIGHT), cold=0, water_source=(5, 2)), config)
    assert warm_enough.kind == "go_water"


def test_a_hungry_person_at_home_waits_for_the_same_reason_and_does_not_claim_to_be_fed():
    config = cfg()
    far = seen_in(config, RAINY_NIGHT, hunger=30, food=0, source=(11, 9), cold=10, thirst=0, water=1)
    held = decide(far, config)
    assert held.kind == "rest" and held.reason.startswith("at home; waiting out the rain") and "fed" not in held.reason
    assert any(r[0] == "go" and r[1] == "weather" for r in held.rejected)
    assert decide(replace(far, sky=CLEAR_DAY, chill=0), config).kind == "go"


def test_the_hold_is_for_people_at_home_and_changes_nothing_without_the_sky():
    config = cfg()
    away = replace(thirsty_at_home(config, RAINY_NIGHT), position=(5, 2))
    assert errand_holds(away, config, "water") == () and decide(away, config).kind == "go_water"
    plain = WorldConfig(seed=7, features=("explain",))
    assert errand_holds(thirsty_at_home(plain, None), plain, "water") == ()


def walking_to_water(config, **changes):
    """Out in clear weather and on the way to water, with cold and thirst nearly equally pressing."""
    return view(config, CLEAR_DAY, position=(6, 2), home_built=True, hunger=0, food=1, thirst=40, water=0,
                water_source=(11, 2), cold=62, doing="go_water", **changes)       # thirst: 20 ticks left, cold: 18


def test_steady_people_carry_on_with_the_need_they_were_serving_unless_another_is_clearly_worse():
    steady, plain = cfg(), cfg(features=WITHOUT_STEADY)
    assert decide(walking_to_water(plain), plain).kind == "go_shelter"            # a tick or two decides it
    assert decide(walking_to_water(steady), steady).kind == "go_water"
    assert decide(replace(walking_to_water(steady), cold=75), steady).kind == "go_shelter"       # 5 ticks left: clearly worse
    carried = [r for r in decide(walking_to_water(steady), steady).rejected if r[0] == "warmth"]
    assert carried and "already doing" in carried[0][2]
    fresh = replace(walking_to_water(steady), doing="rest")
    assert decide(fresh, steady).kind == "go_shelter"                              # nothing was in progress


def at_the_well(config, sky=CLEAR_DAY, **changes):
    """A person standing at the well, one step from home, holding no water."""
    base = dict(position=(3, 3), home=(3, 2), water_source=(3, 3), water_stock=3, water=0, home_built=True)
    return view(config, sky, **{**base, **changes})


def test_a_steady_person_who_gets_to_the_well_a_tick_early_takes_what_they_came_for():
    steady, plain = cfg(), cfg(features=WITHOUT_STEADY)
    early = at_the_well(steady, thirst=23)                                       # 23 + 2 reaches the thirsty line of 25 next tick
    assert decide(early, steady).kind == "draw"
    assert decide(at_the_well(plain, thirst=23), plain).kind != "draw"           # without it they are not yet thirsty and turn round
    assert decide(at_the_well(steady, thirst=10), steady).kind != "draw"        # but not when it is well before the line


def test_a_need_met_on_the_spot_counts_for_more_than_one_that_is_merely_walking_home():
    steady, plain = cfg(), cfg(features=WITHOUT_STEADY)
    weather = Sky("night", "rain", 4, 100)
    came_for_water = at_the_well(steady, weather, chill=exposure(steady, weather, False), thirst=36, cold=28, doing="go_water")
    assert decide(came_for_water, steady).kind == "draw"                          # twelve ticks of cold, twenty-two of thirst, and it is right here
    assert decide(replace(came_for_water, doing=None), steady).kind == "go_shelter"   # not what they came for: the nearer limit wins
    assert decide(at_the_well(plain, weather, chill=exposure(plain, weather, False), thirst=36, cold=28), plain).kind == "go_shelter"
    dying = replace(came_for_water, cold=60)                                       # cold nearly kills: no amount of commitment outweighs it
    assert decide(dying, steady).kind == "go_shelter"


def test_somebody_on_an_errand_is_not_called_home_until_the_cold_is_further_past_the_line():
    steady, plain = cfg(), cfg(features=WITHOUT_STEADY)
    out = seen_in(steady, CLEAR_DAY, position=(8, 2), cold=20, doing="go")        # six steps from home: 20 + 6 reaches the line of 25
    assert shelter_trip_due(replace(out, doing="rest"), steady)                    # somebody idle sets off home
    assert not shelter_trip_due(out, steady)                                       # somebody on an errand finishes it
    assert shelter_trip_due(replace(out, cold=28), steady)                         # until it is commitment past the line
    assert shelter_trip_due(seen_in(plain, CLEAR_DAY, position=(8, 2), cold=20, doing="go"), plain)


def door_dithering(run):
    """Times somebody went A, B, A between going out for something and going home for warmth."""
    kinds, count = ("go_shelter", "go", "go_water", "warm"), 0
    per_person: dict[str, list[str]] = {}
    for tick in run.ticks:
        for actor, decision in tick["decisions"].items():
            per_person.setdefault(actor, []).append(decision["kind"])
    for sequence in per_person.values():
        count += sum(1 for a, b, c in zip(sequence, sequence[1:], sequence[2:]) if a == c != b and a in kinds and b in kinds)
    return count


def test_steadiness_ends_most_of_the_stepping_out_and_straight_back_in(tmp_path):
    counts = {}
    for name, features in (("plain", WITHOUT_STEADY), ("steady", FEATURES)):
        path = tmp_path / f"{name}.jsonl"
        run_world(WorldConfig(seed=42, features=features), 300, path)
        counts[name] = door_dithering(read_run(path))
    assert counts["plain"] >= 20 and counts["steady"] * 3 <= counts["plain"], counts


def test_night_brings_bedtime_earlier_and_fatigue_by_the_declared_arithmetic(tmp_path):
    config = cfg()
    day, night = Sky("day", "clear", 14, 20), Sky("night", "clear", 7, 100)
    assert tired_threshold(config, (), night) == tired_threshold(config, (), day) - config.lever("night_tired")
    tired_for_night = dict(fatigue=45, home_built=True)
    assert decide(view(config, day, **tired_for_night), config).kind == "rest"
    assert decide(view(config, night, **tired_for_night), config).kind == "sleep"
    path = tmp_path / "run.jsonl"
    run_world(config, 130, path)
    run, before = read_run(path), None
    before = run.header["world"]
    seen = {"awake_night": 0, "asleep_night": 0}
    for tick in run.ticks:
        sky = before["sky"]
        for actor, decision in tick["decisions"].items():
            was, now = before["persona"]["fatigue"][actor], tick["world"]["persona"]["fatigue"].get(actor)
            if actor in tick["world"]["died_at"] or now is None:
                continue
            if sky["phase"] == "night" and decision["kind"] in ("sleep", "collapse"):
                rate = (config.lever("rest_home") if tick["world"]["positions"][actor] == tick["world"]["homes"][actor]
                        else config.lever("rest_open")) + config.lever("night_rest")
                assert now == max(0, was - rate)
                seen["asleep_night"] += 1
            elif sky["phase"] == "night" and decision["kind"] not in ("sleep", "collapse", "build", "claim", "fish", "gather_wood"):
                assert now == was + config.lever("fatigue_rate") + config.lever("night_fatigue")
                seen["awake_night"] += 1
        before = tick["world"]
    assert all(seen.values()), seen


# --- whole worlds ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("sky") / "run.jsonl"
    config = WorldConfig(seed=14, features=FEATURES, seasons_on=True)
    run_world(config, 420, path)
    return config, path, read_run(path)


@pytest.mark.long_run
def test_the_recorded_sky_is_the_rule_at_every_tick(saved):
    config, _, run = saved
    assert run.header["world"]["sky"] == sky_at(config, 0).canonical()
    for tick in run.ticks:
        assert tick["world"]["sky"] == sky_at(config, tick["tick"] + 1).canonical()
    seen = {tick["world"]["sky"]["weather"] for tick in run.ticks}
    assert {"clear", "rain"} <= seen and {tick["world"]["sky"]["phase"] for tick in run.ticks} == {"dawn", "day", "dusk", "night"}


@pytest.mark.long_run
def test_a_sky_world_audits_replays_and_recovers(saved, tmp_path):
    _, path, run = saved
    assert run.complete and audit_run(run) == []
    assert replay_world(path).identical
    lines = path.read_bytes().splitlines(keepends=True)
    completed = next(i for i, t in enumerate(run.ticks) if t["world"]["sky"]["weather"] in ("rain", "storm")) + 2
    end = next(i for i, line in enumerate(lines)
               if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == completed - 1)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks


@pytest.mark.long_run
def test_weather_cold_really_reaches_people_who_are_caught_out_in_it(saved):
    config, _, run = saved
    before, rises = run.header["world"], {"clear": [], "rain": [], "storm": []}
    for tick in run.ticks:
        sky = before["sky"]
        for actor in tick["world"]["positions"]:
            if actor in before["died_at"] or actor in tick["world"]["died_at"]:
                continue
            where = tuple(tick["world"]["positions"][actor])
            roofs = {tuple(cell) for cell in tick["world"].get("shelters", [])}
            if where != tuple(tick["world"]["homes"][actor]) and sky["phase"] != "dawn" and where not in roofs:
                if sky["weather"] in rises:
                    rises[sky["weather"]].append(tick["world"]["cold"][actor] - before["cold"][actor])
        before = tick["world"]
    assert rises["clear"] and rises["rain"], {k: len(v) for k, v in rises.items()}
    assert min(rises["rain"]) >= config.cold_rate + 1                                  # the wet always adds at least 1
    assert sum(rises["rain"]) / len(rises["rain"]) > sum(rises["clear"]) / len(rises["clear"])


@pytest.mark.long_run
def test_the_page_shows_the_clock_and_the_weather_and_the_index_notes_changes(saved):
    _, _, run = saved
    page = render_html(run)
    assert "skyPart" in page
    kinds = {e["kind"] for e in build_index(run)["events"]}
    assert {"night_falls", "dawn_breaks"} <= kinds and kinds & {"rain_begins", "storm_breaks", "weather_clears", "sky_clouds"}
