"""Tiredness and sleep: a fourth need that nobody dies of directly.

Fatigue rises every awake tick and faster on work ticks. At `tired_at` a person
wants to sleep; sleeping at home rests fastest. Asleep, they stay asleep until
rested unless another need becomes urgent, which is judged by the time the
remedy takes: a need is urgent when the ticks before it turns critical are no
more than the ticks to reach and finish relief, plus a small margin. At
`collapse_at` they fall asleep wherever they stand. Nobody dies of tiredness,
but a person asleep in the open is cold, thirsty and hungry like anybody else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from world.feature import Feature
from world.traits import DILIGENCE, CAUTION, caution_ticks, trait_lean

if TYPE_CHECKING:
    from world.config import WorldConfig

SLEEP, GO_SLEEP, COLLAPSE = "sleep", "go_sleep", "collapse"
WORK_KINDS = frozenset({"build", "claim", "fish", "gather_wood", "help", "gather_stone", "craft"})    # ticks of physical work

FATIGUE_LEVERS = (("fatigue_rate", 1), ("work_fatigue", 1), ("tired_at", 60), ("collapse_at", 100),
                  ("collapse_recovery", 10), ("rest_home", 4), ("rest_open", 2), ("wake_at", 8), ("urgent_margin", 3))

SLEEP_FEATURE = Feature(
    name="sleep",
    summary="Fatigue is a fourth need: people go home to sleep, and collapse if they do not.",
    rule=(
        "Fatigue rises by fatigue_rate each awake tick and by work_fatigue more on a tick spent on physical "
        "work (building, claiming food or wood, casting a line). At genesis it is spread across the roster "
        "like hunger, a newborn starts at nought. At tired_at, shifted by (diligence - 50) // 5 up and "
        "(caution - 50) // 10 down, a person who is not otherwise occupied goes home to sleep; at home they "
        "sleep. Sleeping lowers fatigue by rest_home a tick at home and rest_open elsewhere, and a sleeper "
        "stays asleep until fatigue is at most wake_at. Fatigue competes with hunger, thirst and cold by the "
        "same least-slack rule, where its slack is (collapse_at - fatigue) // fatigue_rate. A sleeper wakes "
        "early only for an urgent need: one whose slack is no more than the ticks to reach and finish its "
        "remedy plus urgent_margin. A tired person is also not allowed to start sleeping while such a need "
        "is urgent or has reached its emergency level, and finishes a food or water errand first "
        "when fatigue leaves time for it and for getting home; somebody already on an errand needs 8 more "
        "ticks of reason to turn back, and somebody already heading to bed 8 more to turn aside. "
        "At collapse_at a person falls asleep where they stand and cannot do anything else until fatigue has "
        "fallen collapse_recovery below it, except to eat or drink what they already hold when that need is "
        "at its emergency level. "
        "Sleepers see only their own cell; others see that they are asleep. Nobody dies of tiredness."),
    levers=FATIGUE_LEVERS,
)


def rest_rate(config: "WorldConfig", at_home: bool) -> int:
    return config.lever("rest_home" if at_home else "rest_open")


def tired_threshold(config: "WorldConfig", traits: tuple[int, ...], sky: Any = None) -> int:
    """Fatigue at which this person starts looking for sleep. Diligent people
    work on through more of it; cautious people turn in earlier; night brings bedtime forward."""
    base = config.lever("tired_at") + trait_lean(traits, DILIGENCE) // 5 - caution_ticks(traits)
    if sky is not None and sky.night:
        base -= config.lever("night_tired")
    return max(20, min(config.lever("collapse_at") - 10, base))


def fatigue_slack(config: "WorldConfig", fatigue: int) -> int:
    rate = config.lever("fatigue_rate")
    return (config.lever("collapse_at") - fatigue) // rate if rate > 0 else 10 ** 9
