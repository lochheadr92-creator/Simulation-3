"""A nearby request can be answered through the existing kernel transfer."""

from dataclasses import replace

from kernel import Engine, WorldState
from world.config import WorldConfig
from world.decide import AGREE, EAT, OFFER, decide, someone_to_ask
from world.observe import Observation, SeenPerson
from world.run import proposals_for


def setup():
    config = WorldConfig(seed=7, requests_on=True, offers_on=False, water_on=False,
                         warmth_on=False, plan_trips=False)
    view = Observation(actor="p01", tick=0, alive=True, position=(2, 2),
                       home=(2, 2), hunger=0, food=2, source=(6, 6), source_food=None,
                       asked_by="p02", others=(SeenPerson("p02", (3, 2), 0),))
    return config, view


def test_adjacent_answer_transfers_food_without_agreement_or_walk():
    config, view = setup()
    decision = decide(view, config)
    assert decision.kind == OFFER and decision.target == "p02"
    assert decision.step is None
    engine = Engine(WorldState.genesis(balances={"p01": 2, "p02": 0}))
    record = engine.tick(proposals_for({"p01": decision}, 0))
    assert record.outcomes[0].accepted
    assert dict(engine.state.balances) == {"p01": 1, "p02": 1}


def test_own_hunger_wins_and_distant_request_still_requires_agreement():
    config, view = setup()
    assert decide(replace(view, hunger=config.hungry_at), config).kind == EAT
    distant = replace(view, others=(SeenPerson("p02", (4, 2), 0),))
    assert decide(distant, config).kind == AGREE
    assert decide(view, replace(config, requests_on=False)).kind != OFFER


def test_parent_can_answer_locally_but_empty_handed_child_comes_first():
    config, view = setup()
    parent = replace(view, children=frozenset({"p03"}), dependents=frozenset({"p03"}))
    assert decide(parent, config).target == "p02"
    with_child = replace(parent, others=parent.others + (SeenPerson("p03", (2, 3), 0),))
    assert decide(with_child, config).target == "p03"


def test_no_handoff_to_absent_or_already_supplied_asker():
    config, view = setup()
    for others in ((), (SeenPerson("p02", (3, 2), 1),)):
        assert decide(replace(view, others=others), config).kind != OFFER


def test_thirst_and_cold_take_priority_over_handoff():
    config, view = setup()
    water = replace(config, water_on=True)
    thirsty = replace(view, thirst=water.thirsty_at, water=1, water_source=(6, 6))
    assert decide(thirsty, water).kind == "drink"
    warmth = replace(config, warmth_on=True)
    assert decide(replace(view, cold=warmth.cold_at), warmth).kind == "warm"


def test_adjacent_mode_never_agrees_to_a_request_journey():
    config, view = setup()
    config = replace(config, adjacent_requests=True)
    assert decide(view, config).kind == OFFER
    distant = replace(view, others=(SeenPerson("p02", (4, 2), 0),))
    assert decide(distant, config).kind not in (AGREE, OFFER, "go_offer")


def test_adjacent_mode_asks_only_neighbours_and_round_trips():
    config, view = setup()
    config = replace(config, adjacent_requests=True)
    asker = replace(view, food=0, hunger=config.hungry_at, asked_by=None,
                    others=(SeenPerson("p02", (4, 2), 2),))
    assert someone_to_ask(asker, config) is None
    assert someone_to_ask(replace(asker, others=(SeenPerson("p02", (3, 2), 2),)), config) == "p02"
    assert WorldConfig.from_describe(config.describe()) == config
