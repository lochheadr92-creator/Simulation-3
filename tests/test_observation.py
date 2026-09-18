"""A7 - observers cannot mutate live or previously observed state.

Inspection is inert. Every published object refuses mutation, and a view or a
record taken earlier keeps reporting what it reported when it was taken.
"""

from __future__ import annotations

import dataclasses

import pytest

from kernel import Engine, Source, WorldState, claim, consume, transfer

from tests.support import balances_of, genesis, source


def live_world():
    return genesis(
        balances={"A": 2, "B": 0},
        sources={"S": source(3, "A", "B")},
    )


def test_state_mappings_refuse_mutation():
    state = live_world()

    with pytest.raises(TypeError):
        state.balances["A"] = 99
    with pytest.raises(TypeError):
        del state.balances["A"]
    with pytest.raises(AttributeError):
        state.balances.clear()
    with pytest.raises(AttributeError):
        state.sources.update({"S": Source(stock=99)})

    assert balances_of(state) == {"A": 2, "B": 0}
    assert state.sources["S"].stock == 3


def test_state_objects_are_frozen():
    state = live_world()

    with pytest.raises(dataclasses.FrozenInstanceError):
        state.tick = 99
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.consumed = 99
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.sources["S"].stock = 99

    assert state.tick == 0
    assert state.consumed == 0
    assert state.sources["S"].stock == 3


def test_a_sources_authorised_set_refuses_new_members():
    state = live_world()

    with pytest.raises(AttributeError):
        state.sources["S"].authorised.add("GHOST")

    assert "GHOST" not in state.sources["S"].authorised


def test_a_view_refuses_mutation():
    engine = Engine(live_world())
    view = engine.view_for("A")

    with pytest.raises(dataclasses.FrozenInstanceError):
        view.tick = 99
    with pytest.raises(TypeError):
        view.balances["A"] = 99
    with pytest.raises(AttributeError):
        view.sources.clear()
    with pytest.raises(TypeError):
        view.roster[0] = "GHOST"

    assert view.balances["A"] == 2
    assert view.roster == ("A", "B")


def test_a_view_is_handed_a_copy_rather_than_a_handle_on_the_world():
    """Containment, not only immutability.

    While state objects are replaced rather than edited, sharing the world's own
    mapping with an observer is unobservable. It is still the wrong shape: the
    view is the boundary an actor decides against, and it must not be a handle
    on the live world that a later slice could make mutable.
    """
    engine = Engine(live_world())
    view = engine.view_for("A")

    assert view.balances is not engine.state.balances
    assert view.sources is not engine.state.sources
    assert view.sources["S"] is not engine.state.sources["S"]
    assert dict(view.balances) == dict(engine.state.balances)
    assert view.sources["S"].stock == engine.state.sources["S"].stock


def test_two_views_do_not_share_one_mapping():
    engine = Engine(live_world())

    first = engine.view_for("A")
    second = engine.view_for("B")

    assert first.balances is not second.balances
    assert first.sources is not second.sources


def test_a_view_cannot_reach_the_live_state_it_was_built_from():
    engine = Engine(live_world())
    view = engine.view_for("A")

    copied = dict(view.balances)
    copied["A"] = 99

    assert engine.state.balances["A"] == 2
    assert view.balances["A"] == 2


def test_a_view_taken_earlier_does_not_change_when_the_world_advances():
    engine = Engine(live_world())
    before = engine.view_for("A")
    before_balance = before.balances["A"]
    before_stock = before.sources["S"].stock

    engine.tick([consume("eat", "A", 0, amount=2), claim("take", "B", 0, sources={"S": 3})])

    assert engine.state.balances["A"] == 0
    assert engine.state.sources["S"].stock == 0
    assert before.tick == 0
    assert before.balances["A"] == before_balance == 2
    assert before.sources["S"].stock == before_stock == 3


def test_a_tick_record_taken_earlier_does_not_change_when_the_world_advances():
    engine = Engine(genesis(balances={"A": 2, "B": 0}))

    first = engine.tick([transfer("give", "A", 0, to="B", amount=1)])
    first_digest = first.digest()
    first_outcomes = tuple((o.proposal_id, o.reason) for o in first.outcomes)

    engine.tick([transfer("give", "A", 0, to="B", amount=1)])

    assert first.tick == 0
    assert first.digest() == first_digest
    assert tuple((o.proposal_id, o.reason) for o in first.outcomes) == first_outcomes


def test_a_tick_record_refuses_mutation():
    engine = Engine(genesis(balances={"A": 1, "B": 0}))
    record = engine.tick([transfer("give", "A", 0, to="B", amount=1)])

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.tick = 99
    with pytest.raises(TypeError):
        record.outcomes[0] = None
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.outcomes[0].reason = "accepted"
    with pytest.raises(TypeError):
        record.outcomes[0].effects[0] = None
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.outcomes[0].effects[0].delta = 99


def test_the_canonical_copy_handed_out_is_not_the_records_own_state():
    engine = Engine(genesis(balances={"A": 1, "B": 0}))
    record = engine.tick([transfer("give", "A", 0, to="B", amount=1)])
    digest_before = record.digest()

    handed_out = record.canonical()
    handed_out["tick"] = 99
    handed_out["outcomes"].clear()

    assert record.digest() == digest_before
    assert record.canonical()["tick"] == 0
    assert len(record.canonical()["outcomes"]) == 1


def test_the_canonical_copy_of_a_state_is_not_the_states_own_state():
    state = live_world()
    digest_before = state.digest()

    handed_out = state.canonical()
    handed_out["balances"]["A"] = 99

    assert state.digest() == digest_before
    assert state.balances["A"] == 2


def test_mutating_the_genesis_input_maps_afterwards_changes_nothing():
    balances = {"A": 2, "B": 0}
    authorised = ["A", "B"]
    sources = {"S": Source(stock=3, authorised=authorised)}

    state = WorldState.genesis(tick=0, balances=balances, sources=sources)
    digest_before = state.digest()

    balances["A"] = 99
    balances["GHOST"] = 5
    authorised.append("GHOST")
    sources["T"] = Source(stock=7)

    assert state.digest() == digest_before
    assert balances_of(state) == {"A": 2, "B": 0}
    assert set(state.sources) == {"S"}
    assert "GHOST" not in state.sources["S"].authorised


def test_mutating_a_proposals_parameter_map_afterwards_changes_nothing():
    wanted = {"S": 1}
    proposal = claim("take", "A", 0, sources=wanted)

    wanted["S"] = 99
    wanted["OTHER"] = 5

    engine = Engine(genesis(balances={"A": 0}, sources={"S": source(3, "A")}))
    record = engine.tick([proposal])

    assert record.outcomes[0].reason == "accepted"
    assert balances_of(engine.state) == {"A": 1}
    assert engine.state.sources["S"].stock == 2


def test_refused_observer_mutation_leaves_the_canonical_identity_unchanged():
    engine = Engine(live_world())
    digest_before = engine.state.digest()
    view = engine.view_for("A")

    for attempt in (
        lambda: view.balances.__setitem__("A", 99),
        lambda: engine.state.balances.__setitem__("A", 99),
        lambda: engine.state.sources.__setitem__("S", Source(stock=0)),
        lambda: setattr(engine.state, "consumed", 99),
        lambda: setattr(engine.state.sources["S"], "stock", 0),
    ):
        with pytest.raises((TypeError, AttributeError, dataclasses.FrozenInstanceError)):
            attempt()

    assert engine.state.digest() == digest_before


def test_the_engine_does_not_hand_out_its_own_mutable_working_state():
    engine = Engine(live_world())
    first = engine.state
    first_digest = first.digest()

    engine.tick([consume("eat", "A", 0, amount=1)])

    assert engine.state is not first
    assert first.digest() == first_digest
    assert first.balances["A"] == 2
