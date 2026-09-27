"""A handoff beside a child may delay an early warmth trip, but no active need."""

from dataclasses import replace

import pytest

from kernel import Engine
from world.config import WorldConfig, genesis
from world.decide import OFFER, decide
from world.observe import Observation, SeenPerson
from world.run import world_step


def encounter():
    config = WorldConfig(seed=7)
    view = Observation(actor="p01", tick=218, alive=True, position=(1, 5),
                       home=(1, 7), hunger=24, thirst=16, cold=23, food=1,
                       water=2, water_source=(6, 4), source=(6, 6), source_food=None,
                       dependents=frozenset({"p07"}),
                       others=(SeenPerson("p07", (1, 4), 0),))
    return config, view


@pytest.mark.parametrize("position", [(1, 4), (1, 5)])
def test_finish_adjacent_or_same_cell_handoff_before_early_warmth_trip(position):
    config, view = encounter()
    view = replace(view, others=(SeenPerson("p07", position, 0),))
    decision = decide(view, config)
    assert decision.kind == OFFER and decision.target == "p07"
    assert decision.amount == 1 and decision.step is None
    assert decision.candidates == ("offer", "go_shelter")
    assert "before heading home" in decision.reason


@pytest.mark.parametrize("changes,expected", [
    ({"hunger": 25}, "eat"),
    ({"thirst": 25}, "drink"),
    ({"cold": 25}, "go_shelter"),
    ({"water": 0, "thirst": 24}, "go_water"),
    ({"food": 0}, "go"),
    ({"alive": False}, "dead"),
    ({"others": ()}, "go_shelter"),
    ({"others": (SeenPerson("p07", (1, 4), 1),)}, "go_shelter"),
    ({"others": (SeenPerson("p07", (1, 3), 0),)}, "go_shelter"),
    ({"dependents": frozenset(), "children": frozenset({"p07"}),
      "others": (SeenPerson("p07", (1, 4), 0, starving=True),)}, "go_shelter"),
])
def test_handoff_does_not_override_needs_or_extend_help(changes, expected):
    config, view = encounter()
    assert decide(replace(view, **changes), config).kind == expected


def test_starving_stranger_does_not_postpone_warmth_trip():
    config, view = encounter()
    view = replace(view, others=(SeenPerson("p08", (1, 4), 0, starving=True),))
    assert decide(view, config).kind == "go_shelter"


def test_seed7_parent_delivers_and_child_eats_through_normal_settlement():
    config = WorldConfig(seed=7)
    ledger, overlay = genesis(config)
    engine = Engine(ledger)
    for _ in range(218):
        step = world_step(engine, overlay, config)
        engine, overlay = step.engine, step.processed.overlay
    assert step.decisions["p01"].kind == "go_offer"
    assert "my child with no food" in step.decisions["p01"].reason
    before = engine.state
    step = world_step(engine, overlay, config)
    parent = step.views["p01"]
    assert (parent.position, parent.hunger, parent.thirst, parent.cold, parent.food) == (
        (1, 5), 24, 16, 23, 1)
    assert step.decisions["p01"].kind == OFFER
    assert step.decisions["p01"].target == "p07"
    outcome = next(o for o in step.record.outcomes if o.actor == "p01")
    assert outcome.accepted
    assert step.committed.balances["p01"] == before.balances["p01"] - 1
    assert step.committed.balances["p07"] == before.balances["p07"] + 1
    assert before.balances["p01"] == 1  # settlement did not mutate its input
    # The child is not hungry yet: keeps the food, returns home, then eats.
    for _ in range(7):
        previous = step
        step = world_step(step.engine, step.processed.overlay, config)
    assert step.views["p07"].tick == 225
    assert step.decisions["p07"].kind == "eat"
    assert step.processed.overlay.hunger["p07"] < previous.processed.overlay.hunger["p07"]


def test_new_rule_is_described_and_old_rule_is_not_replayed_as_new():
    config = WorldConfig(seed=7)
    described = config.describe()
    assert WorldConfig.from_describe(described) == config
    old = dict(described)
    old["decision"] = old["decision"].replace(
        "; before an early trip home for warmth, a parent hands one food to an "
        "empty-handed dependent already on the same or an adjacent cell, only "
        "while below every active need threshold and with no water trip due. "
        "This does not extend a walking errand", "")
    with pytest.raises(ValueError):
        WorldConfig.from_describe(old)
