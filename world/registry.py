"""Every optional rich-world feature, in one place, and the rules for combining them."""

from __future__ import annotations

from world.belief import BELIEFS
from world.crafting import CRAFTING
from world.explain import EXPLAIN
from world.farming import FARMING
from world.feature import Feature
from world.persona import PERSONALITY, SKILLS_FEATURE
from world.pledges import PLEDGES
from world.rest import SLEEP_FEATURE
from world.sky import SKY_FEATURE
from world.society import SOCIETY
from world.steady import STEADY
from world.structures import STRUCTURES
from world.wolves import WOLVES

FEATURES: dict[str, Feature] = {feature.name: feature for feature in (
    BELIEFS, CRAFTING, EXPLAIN, FARMING, PERSONALITY, PLEDGES, SKILLS_FEATURE, SKY_FEATURE, SLEEP_FEATURE, SOCIETY, STEADY, STRUCTURES, WOLVES,
)}

LEVER_DEFAULTS: dict[str, int] = {}
for _feature in FEATURES.values():
    for _name, _default in _feature.levers:
        if _name in LEVER_DEFAULTS:
            raise RuntimeError(f"lever {_name!r} is declared by two features")
        LEVER_DEFAULTS[_name] = _default


def lever_defaults(features: tuple[str, ...]) -> dict[str, int]:
    """The settings of exactly the features that are on."""
    return {name: default for feature in features if feature in FEATURES
            for name, default in FEATURES[feature].levers}


def feature_problems(features: tuple[str, ...], levers: tuple[tuple[str, int], ...]) -> list[str]:
    """Why a combination of features and lever overrides is not allowed."""
    problems: list[str] = []
    if list(features) != sorted(set(features)) or any(not isinstance(name, str) for name in features):
        problems.append("features must be strings, sorted, each once")
    allowed = lever_defaults(features)
    for name in features:
        if name not in FEATURES:
            problems.append(f"unknown feature {name!r}")
            continue
        problems.extend(f"{name} needs {need}" for need in FEATURES[name].needs if need not in features)
    for name, value in levers:
        if name not in allowed:
            problems.append(f"setting {name!r} belongs to no feature that is on")
        elif type(value) is not int or value < 0:
            problems.append(f"setting {name!r} must be an integer of zero or more")
    return problems


def lever_value(levers: tuple[tuple[str, int], ...], name: str) -> int:
    for key, value in levers:
        if key == name:
            return value
    return LEVER_DEFAULTS[name]


def cross_checks(features: tuple[str, ...], levers: tuple[tuple[str, int], ...]) -> list[str]:
    """Relations between settings a feature requires, checked after the shape is valid."""
    problems: list[str] = []

    def v(name: str) -> int:
        return lever_value(levers, name)

    if "sleep" in features:
        if not (v("wake_at") < v("tired_at") < v("collapse_at")):
            problems.append("sleep needs wake_at < tired_at < collapse_at")
        if min(v("fatigue_rate"), v("rest_home"), v("rest_open")) < 1:
            problems.append("sleep needs fatigue_rate, rest_home and rest_open of at least 1")
        if v("tired_at") < 20 or v("collapse_at") < 30:
            problems.append("sleep needs tired_at of at least 20 and collapse_at of at least 30")
        if not 1 <= v("collapse_recovery") < v("collapse_at") - v("tired_at"):
            problems.append("sleep needs collapse_recovery between 1 and collapse_at - tired_at")
    if "beliefs" in features and (v("memory_span") < 1 or v("memory_slots") < 1):
        problems.append("beliefs need memory_span and memory_slots of at least 1")
    if "bonds" in features:
        if min(v("talk_range"), v("chat_len"), v("lonely_every"), v("chat_at"), v("friend_at"), v("grudge_gain"),
               v("grudge_fade"), v("retry_after"), v("grievance_gap")) < 1:
            problems.append("bonds need talk_range, chat_len, lonely_every, chat_at, friend_at, grudge_gain, grudge_fade, "
                            "retry_after and grievance_gap of at least 1")
        if not v("chat_at") <= v("lonely_at") < v("lonely_max") or v("grudge_gain") > v("grudge_at") or v("believe_at") > 100:
            problems.append("bonds need chat_at <= lonely_at < lonely_max, and grudge_gain <= grudge_at")
    if "structures" in features:
        if min(v("wear_every"), v("repair_gain"), v("fire_burn"), v("well_ticks"), v("well_wood"), v("well_every"),
               v("well_cap")) < 1 or not 1 <= v("repair_at") <= v("repair_to") <= 100 or v("leak_below") > 100:
            problems.append("structures need wear_every, repair_gain, fire_burn, well_ticks, well_wood, well_every and "
                            "well_cap of at least 1, repair_at from 1 up to repair_to up to 100, and leak_below of 100 or less")
    if "farming" in features:
        if min(v("grow_ticks"), v("base_yield"), v("tend_max"), v("fallow_every"), v("rot_after"), v("spoil_every"),
               v("grain_satiation")) < 1 or v("min_soil") > 100:
            problems.append("farming needs grow_ticks, base_yield, tend_max, fallow_every, rot_after, spoil_every and "
                            "grain_satiation of at least 1, and min_soil of 100 or less")
    if "crafting" in features:
        if min(v("stone_hand"), v("stone_pack")) < 1 or v("stone_hand") > v("stone_pack") or v("axe_saves") < 1:
            problems.append("crafting needs stone_hand of at least 1 up to stone_pack, and axe_saves of at least 1")
    if "pledges" in features:
        if min(v("ask_wait"), v("promise_span"), v("place_wait"), v("ask_again"), v("help_range"), v("build_ask")) < 1:
            problems.append("pledges need ask_wait, promise_span, place_wait, ask_again, help_range and build_ask of at least 1")
        if v("accept_trust") > 100 or v("ask_wait") > v("promise_span"):
            problems.append("pledges need accept_trust of 100 or less and ask_wait of promise_span or less")
    if "wolves" in features:
        if min(v("wolves"), v("wolf_arrival"), v("wolf_sense"), v("bite"), v("heal_every"), v("alarm")) < 1:
            problems.append("wolves need wolves, wolf_arrival, wolf_sense, bite, heal_every and alarm of at least 1")
        if not 1 <= v("limp_at") < v("lethal_hurt") or v("bite") >= v("lethal_hurt"):
            problems.append("wolves need limp_at below lethal_hurt, and one bite below lethal_hurt")
    if "sky" in features:
        if v("twilight") < 1 or v("front_ticks") < 1 or min(v("night_sight"), v("storm_sight")) < 0:
            problems.append("sky needs twilight and front_ticks of at least 1")
        if v("night_length") < 1 or v("night_length") + 2 * v("twilight") >= v("day_length"):
            problems.append("sky needs night_length of at least 1 and night_length + 2 * twilight below day_length")
        if v("chill_below") < 0 or v("night_tired") >= v("tired_at") - 15 and "sleep" in features:
            problems.append("sky needs night_tired well below tired_at when sleep is on")
    return problems
