"""Every optional rich-world feature, in one place, and the rules for combining them."""

from __future__ import annotations

from world.explain import EXPLAIN
from world.feature import Feature
from world.persona import PERSONALITY, SKILLS_FEATURE
from world.rest import SLEEP_FEATURE
from world.sky import SKY_FEATURE
from world.steady import STEADY

FEATURES: dict[str, Feature] = {feature.name: feature for feature in (
    EXPLAIN, PERSONALITY, SKILLS_FEATURE, SKY_FEATURE, SLEEP_FEATURE, STEADY,
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
    if "sky" in features:
        if v("twilight") < 1 or v("front_ticks") < 1 or min(v("night_sight"), v("storm_sight")) < 0:
            problems.append("sky needs twilight and front_ticks of at least 1")
        if v("night_length") < 1 or v("night_length") + 2 * v("twilight") >= v("day_length"):
            problems.append("sky needs night_length of at least 1 and night_length + 2 * twilight below day_length")
        if v("chill_below") < 0 or v("night_tired") >= v("tired_at") - 15 and "sleep" in features:
            problems.append("sky needs night_tired well below tired_at when sleep is on")
    return problems
