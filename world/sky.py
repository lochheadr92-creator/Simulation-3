"""The sky: time of day, weather and temperature, and what being out in them costs.

All of it is fixed by the seed and the tick, so nothing is hidden and nothing needs
saving to be reproduced. It is nevertheless written into every tick's overlay, so the
viewer reads recorded values instead of re-deriving them and replay can confirm them.

A day has four phases. Weather changes in fronts: every `front_ticks` ticks the next
front follows from the last by a fixed table, so a storm builds through rain and does
not appear out of a clear sky. Temperature is the day's base plus the hour, the weather
and, when seasons are on, the season. Being out in it costs warmth (`exposure`), and
sight shrinks at night and in storms. A finished shelter is out of all of it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from world.draw import draw
from world.feature import Feature

if TYPE_CHECKING:
    from world.config import WorldConfig

PHASES = ("dawn", "day", "dusk", "night")
WEATHER = ("clear", "overcast", "rain", "storm")

# next front's weather given this one: (weather, weight out of 100)
TRANSITIONS: dict[str, tuple[tuple[str, int], ...]] = {
    "clear": (("clear", 55), ("overcast", 35), ("rain", 10)),
    "overcast": (("clear", 30), ("overcast", 25), ("rain", 40), ("storm", 5)),
    "rain": (("overcast", 30), ("rain", 35), ("storm", 25), ("clear", 10)),
    "storm": (("rain", 55), ("overcast", 35), ("clear", 10)),
}
HOUR_WARMTH = {"dawn": -2, "day": 2, "dusk": 0, "night": -5}
WEATHER_WARMTH = {"clear": 0, "overcast": -1, "rain": -3, "storm": -5}
LEAN_SEASON_WARMTH = -3

SKY_LEVERS = (("day_length", 120), ("night_length", 36), ("twilight", 8), ("front_ticks", 30),
              ("base_temp", 12), ("chill_below", 8), ("night_sight", 1), ("storm_sight", 1),
              ("night_tired", 20), ("night_fatigue", 1), ("night_rest", 1), ("weather_margin", 6))

SKY_FEATURE = Feature(
    name="sky",
    summary="Day and night, weather and temperature, and what being out in them costs.",
    rule=(
        "A day lasts day_length ticks and begins at dawn: dawn for twilight ticks, day, dusk for twilight "
        "ticks, then night for the last night_length ticks. Every front_ticks ticks a new weather front "
        "begins; the first is clear and each next one follows from the last by a fixed table (clear stays "
        "clear 55, turns overcast 35 or rainy 10 out of 100; overcast clear 30, overcast 25, rain 40, "
        "storm 5; rain overcast 30, rain 35, storm 25, clear 10; storm rain 55, overcast 35, clear 10), "
        "chosen by a deterministic draw from the seed and the front's number, so a storm never comes out of "
        "a clear sky. Temperature is base_temp "
        "plus the hour (dawn -2, day +2, dusk 0, night -5), plus the weather (overcast -1, rain -3, storm "
        "-5), minus 3 in a lean season when seasons are on. Anybody not on a finished shelter pays extra "
        "cold each tick: (chill_below - temperature + 2) // 3 when that is positive, plus 1 in rain and 2 "
        "in a storm. At their own home cell that extra reduces the warming (never below 1) unless a "
        "finished shelter stands there; on any other finished shelter it is not paid. Sight shrinks by "
        "night_sight at night and storm_sight in a storm, to at least 1. In a storm, stepping onto rough "
        "ground holds the next step back one tick more, and nobody starts building a shelter or an "
        "optional outing (a cache trip, wood, a move of home). People plan with the cold rate of the sky "
        "they are in: the time cold has left to kill, and when to start for shelter, use cold_rate plus the "
        "extra cold of being out in it now. Somebody at home does not set out on a food or water errand "
        "when the round trip (out, two ticks to take it, back, plus any caution ticks) would at that rate "
        "carry their cold past cold_emergency_at, unless that need is at its emergency level or has no "
        "more than the ticks to reach and finish relief plus weather_margin left: they stay in and warm up "
        "and look again next tick. With sleep on, being awake at night adds "
        "night_fatigue, sleeping at night adds night_rest, and the tired threshold is night_tired lower. "
        "The sky of each tick is written into the saved world."),
    levers=SKY_LEVERS,
    tables={"phases": list(PHASES), "weather": list(WEATHER)},
)


@dataclass(frozen=True)
class Sky:
    phase: str
    weather: str
    temp: int          # degrees; may be below zero
    moment: int        # tick within the day

    def __post_init__(self) -> None:
        if self.phase not in PHASES or self.weather not in WEATHER:
            raise ValueError("a sky needs a known phase and weather")
        if type(self.temp) is not int or type(self.moment) is not int or self.moment < 0:
            raise ValueError("a sky needs an integer temperature and a moment of zero or more")

    @property
    def night(self) -> bool:
        return self.phase == "night"

    @property
    def storm(self) -> bool:
        return self.weather == "storm"

    def canonical(self) -> dict[str, Any]:
        return {"phase": self.phase, "weather": self.weather, "temp": self.temp, "moment": self.moment}

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Sky":
        if not isinstance(data, Mapping) or set(data) != {"phase", "weather", "temp", "moment"}:
            raise ValueError("a canonical sky has phase, weather, temp and moment")
        return cls(data["phase"], data["weather"], data["temp"], data["moment"])


def phase_of(config: "WorldConfig", moment: int) -> str:
    length, night, twilight = config.lever("day_length"), config.lever("night_length"), config.lever("twilight")
    if moment < twilight:
        return "dawn"
    if moment < length - night - twilight:
        return "day"
    if moment < length - night:
        return "dusk"
    return "night"


_CHAINS: dict[int, list[str]] = {}


def front_weather(seed: int, front: int) -> str:
    """The weather of one front. Front 0 is clear; each later one follows from the one before."""
    chain = _CHAINS.setdefault(seed, ["clear"])
    while len(chain) <= front:
        roll, index = draw(seed, "front", len(chain)) % 100, 0
        for weather, weight in TRANSITIONS[chain[-1]]:
            index += weight
            if roll < index:
                chain.append(weather)
                break
    return chain[front]


def sky_at(config: "WorldConfig", tick: int) -> Sky:
    """The sky at the start of `tick`."""
    from world.ecology import season_at
    moment = tick % config.lever("day_length")
    phase = phase_of(config, moment)
    weather = front_weather(config.seed, tick // config.lever("front_ticks"))
    temp = config.lever("base_temp") + HOUR_WARMTH[phase] + WEATHER_WARMTH[weather]
    if config.seasons_on and season_at(tick) == "lean":
        temp += LEAN_SEASON_WARMTH
    return Sky(phase, weather, temp, moment)


def exposure(config: "WorldConfig", sky: Sky | None, covered: bool) -> int:
    """Extra cold per tick from being out in this sky; nothing under a finished shelter."""
    if sky is None or covered:
        return 0
    chill = max(0, (config.lever("chill_below") - sky.temp + 2) // 3)
    return chill + {"rain": 1, "storm": 2}.get(sky.weather, 0)


def sight(config: "WorldConfig", sky: Sky | None, base: int) -> int:
    """How far somebody can see in this sky: less at night and in a storm, never below 1."""
    if sky is None or base <= 0:
        return base
    cut = (config.lever("night_sight") if sky.night else 0) + (config.lever("storm_sight") if sky.storm else 0)
    return max(1, base - cut)


def storm_hold(sky: Sky | None) -> int:
    """Extra ticks lost climbing onto rough ground in a storm."""
    return 1 if sky is not None and sky.storm else 0
