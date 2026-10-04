"""Staying with the need one was serving.

Water, food and warmth compete by the least time left. Left alone, two needs a tick or
two apart in urgency trade places as the walk changes what each leaves, and a person
steps out of the door and back in. With this feature, whatever the person was doing
last tick counts as `commitment` ticks more urgent when the choice is made, so a
need has to be clearly more pressing before they give up what they had started.
"""

from __future__ import annotations

from world.feature import Feature

STEADY = Feature(
    name="steady",
    summary="People stay with the need they were serving unless another is clearly more urgent.",
    rule=(
        "Water, food and warmth still compete by the least time left before they kill, but the one a "
        "person was serving last tick (walking to it, taking it, or waiting at it) counts as commitment "
        "ticks more urgent when the choice is made. A need with more than commitment fewer ticks left "
        "still wins at once. Sleep has its own, separate, reluctance to turn back from an errand."),
    levers=(("commitment", 8),),
)
