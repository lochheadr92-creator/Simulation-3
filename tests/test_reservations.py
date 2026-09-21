"""Stage 1b: exercise the native reservation lifecycle and its boundaries."""

from dataclasses import FrozenInstanceError, replace
from itertools import permutations, product

import pytest

from kernel import (
    Engine, Effect, IntegrityError, Proposal, Reason, Reservation, Source, WorldState,
    cancel, claim, complete, consume, reserve, settlement, transfer,
)
from tests.support import reason_of


def world(*, tick=0, balance=2, stock=2):
    return WorldState.genesis(tick=tick, balances={"A": balance, "B": 0},
                              sources={"S": Source(stock, {"A", "B"})})


def hold(engine, operation="transfer", params=None):
    params = {"to": "B", "amount": 1} if params is None else params
    record = engine.tick([reserve("hold", "A", 0, operation=operation, params=params)])
    outcome = record.outcomes[0]
    assert outcome.accepted
    assert outcome.action_id in engine.state.reservations
    return outcome.action_id, record


def test_two_tick_transfer_then_next_tick_spend():
    engine = Engine(world(balance=1, stock=0))
    action, first = hold(engine)
    assert engine.state.balances == {"A": 1, "B": 0}
    assert engine.state.total() == 1
    assert first.outcomes[0].effects == ()
    assert first.outcomes[0].reservation == engine.state.reservations[action]
    assert engine.view_for("A").own_balance == 1
    assert engine.view_for("A").own_available == 0
    second = engine.tick([consume("early", "B", 0, amount=1),
                          complete("finish", "A", 0, action_id=action)])
    assert [o.proposal_id for o in second.outcomes] == ["finish", "early"]
    assert reason_of(second, "finish") == Reason.ACCEPTED
    assert reason_of(second, "early") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert engine.state.balances == {"A": 0, "B": 1}
    assert not engine.state.reservations
    assert second.outcomes[0].action_id == action
    assert second.outcomes[0].effects == first.outcomes[0].reservation.effects
    third = engine.tick([consume("later", "B", 0, amount=1)])
    assert third.outcomes[0].accepted
    assert engine.state.consumed == engine.state.total() == 1


@pytest.mark.parametrize("operation,params,expected", [
    ("claim", {"sources": {"S": 2}}, ({"A": 4, "B": 0}, 0, 0)),
    ("consume", {"amount": 2}, ({"A": 0, "B": 0}, 2, 2)),
])
def test_claim_and_consumption_complete_frozen_plan(operation, params, expected):
    engine = Engine(world())
    action, _ = hold(engine, operation, params)
    assert engine.state.total() == 4
    record = engine.tick([complete("finish", "A", 0, action_id=action)])
    assert record.outcomes[0].accepted
    balances, stock, consumed = expected
    assert engine.state.balances == balances
    assert engine.state.sources["S"].stock == stock
    assert engine.state.consumed == consumed
    assert engine.state.total() == 4


@pytest.mark.parametrize("terminal", [complete, cancel])
def test_repeated_terminal_requests_close_once_in_and_across_ticks(terminal):
    engine = Engine(world(balance=1, stock=0))
    action, _ = hold(engine)
    record = engine.tick([terminal("second", "A", 10, action_id=action),
                          terminal("first", "A", 2, action_id=action)])
    assert reason_of(record, "first") == Reason.ACCEPTED
    assert reason_of(record, "second") == Reason.DENIED_UNKNOWN_ACTION
    balances = dict(engine.state.balances)
    for request in (complete, cancel):
        later = engine.tick([request("replay", "A", 0, action_id=action)])
        assert later.outcomes[0].reason == Reason.DENIED_UNKNOWN_ACTION
        assert engine.state.balances == balances
        assert not engine.state.reservations
        assert engine.state.total() == 1


def test_cancellation_wins_completion_regardless_of_order_or_collection():
    for complete_order, cancel_order in ((0, 1), (1, 0)):
        results = set()
        for order in permutations(("complete", "cancel", "spend")):
            engine = Engine(world(balance=1, stock=0))
            action, _ = hold(engine)
            requests = {
                "complete": complete("finish", "A", complete_order, action_id=action),
                "cancel": cancel("stop", "A", cancel_order, action_id=action),
                "spend": consume("spend", "A", 2, amount=1),
            }
            record = engine.tick([requests[name] for name in order])
            assert reason_of(record, "stop") == Reason.ACCEPTED
            assert reason_of(record, "finish") == Reason.DENIED_UNKNOWN_ACTION
            assert reason_of(record, "spend") == Reason.DENIED_INSUFFICIENT_BALANCE
            assert engine.state.balances == {"A": 1, "B": 0}
            assert not engine.state.reservations
            assert record.outcomes[0].effects == ()
            results.add(record.digest())
            assert engine.tick([consume("next", "A", 0, amount=1)]).outcomes[0].accepted
        assert len(results) == 1


def test_free_stock_can_be_used_while_cancelled_stock_waits_until_next_tick():
    engine = Engine(world(balance=0, stock=2))
    action, _ = hold(engine, "claim", {"sources": {"S": 1}})
    assert engine.view_for("A").sources["S"].available_stock == 1
    record = engine.tick([cancel("stop", "A", 0, action_id=action),
                          claim("free", "B", 0, sources={"S": 1}),
                          claim("released", "B", 1, sources={"S": 1})])
    assert reason_of(record, "free") == Reason.ACCEPTED
    assert reason_of(record, "released") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert engine.state.sources["S"].stock == 1
    assert engine.tick([claim("next", "B", 0, sources={"S": 1})]).outcomes[0].accepted


@pytest.mark.parametrize("mode", ["complete", "cancel", "empty"])
def test_held_source_cannot_be_stolen_by_new_transactions(mode):
    engine = Engine(world(balance=0, stock=1))
    action, _ = hold(engine, "claim", {"sources": {"S": 1}})
    requests = [claim("steal", "B", 0, sources={"S": 1})]
    if mode != "empty":
        requests.append((complete if mode == "complete" else cancel)("end", "A", 0, action_id=action))
    record = engine.tick(requests)
    assert reason_of(record, "steal") == Reason.DENIED_INSUFFICIENT_SOURCE
    assert engine.state.total() == 1
    assert engine.state.balances["B"] == 0


def test_reservation_contends_with_new_transactions_in_same_phase():
    for tick in (0, 1):
        for requests in permutations([
            reserve("hold", "A", 0, operation="claim", params={"sources": {"S": 1}}),
            claim("take", "B", 0, sources={"S": 1}),
        ]):
            engine = Engine(world(tick=tick, balance=0, stock=1))
            record = engine.tick(requests)
            accepted = [outcome for outcome in record.outcomes if outcome.accepted]
            assert len(accepted) == 1
            assert accepted[0].actor == ("A" if tick == 0 else "B")
            assert engine.state.total() == 1


@pytest.mark.parametrize("terminal", [complete, cancel])
def test_non_owner_cannot_close_an_action(terminal):
    engine = Engine(world())
    action, _ = hold(engine)
    record = engine.tick([terminal("attack", "B", 0, action_id=action)])
    assert record.outcomes[0].reason == Reason.DENIED_UNAUTHORISED
    assert action in engine.state.reservations
    assert engine.tick([complete("owner", "A", 0, action_id=action)]).outcomes[0].accepted


@pytest.mark.parametrize("invalid", ["unauthorised", "malformed", "duplicate"])
def test_invalid_cancellation_cannot_suppress_completion(invalid):
    engine = Engine(world())
    action, _ = hold(engine)
    requests = [complete("finish", "A", 0, action_id=action)]
    if invalid == "unauthorised":
        requests.append(cancel("stop", "B", 0, action_id=action))
    elif invalid == "malformed":
        requests.append(Proposal("stop", "A", 1, "cancel", {"action_id": action, "extra": 1}))
    else:
        requests.extend([cancel("stop", "A", 1, action_id=action), cancel("stop", "A", 2, action_id=action)])
    record = engine.tick(requests)
    assert reason_of(record, "finish") == Reason.ACCEPTED
    assert not any(outcome.accepted for outcome in record.outcomes if outcome.operation == "cancel")
    assert engine.state.balances == {"A": 1, "B": 1}


@pytest.mark.parametrize("duplicate", ["id", "order"])
def test_duplicate_reservations_are_all_denied_without_holding_stock(duplicate):
    engine = Engine(world())
    record = engine.tick([
        reserve("hold", "A", 0, operation="consume", params={"amount": 1}),
        reserve("hold" if duplicate == "id" else "other", "A", 1 if duplicate == "id" else 0,
                operation="consume", params={"amount": 1}),
    ])
    assert len(record.outcomes) == 2
    assert not any(outcome.accepted for outcome in record.outcomes)
    assert not engine.state.reservations
    assert engine.view_for("A").own_available == 2


def test_duplicate_terminal_identity_leaves_reservation_intact():
    engine = Engine(world())
    action, _ = hold(engine)
    request = complete("finish", "A", 0, action_id=action)
    record = engine.tick([request, request])
    assert all(outcome.reason == Reason.DENIED_DUPLICATE_PROPOSAL_ID for outcome in record.outcomes)
    assert action in engine.state.reservations


@pytest.mark.parametrize("second_source,reason", [
    (Source(0, {"A"}), Reason.DENIED_INSUFFICIENT_SOURCE),
    (Source(1, {"B"}), Reason.DENIED_UNAUTHORISED),
])
def test_multi_source_reservation_acquires_all_or_none(second_source, reason):
    engine = Engine(WorldState.genesis(balances={"A": 0, "B": 0},
                    sources={"S1": Source(1, {"A"}), "S2": second_source}))
    record = engine.tick([reserve("hold", "A", 0, operation="claim", params={"sources": {"S1": 1, "S2": 1}}),
                          claim("free", "A", 1, sources={"S1": 1})])
    assert reason_of(record, "hold") == reason
    assert reason_of(record, "free") == Reason.ACCEPTED
    assert not engine.state.reservations
    assert engine.state.sources["S2"] == second_source


def test_multi_source_completion_is_atomic_and_conserved():
    engine = Engine(WorldState.genesis(balances={"A": 0}, sources={
        "S1": Source(2, {"A"}), "S2": Source(3, {"A"})}))
    action, _ = hold(engine, "claim", {"sources": {"S2": 3, "S1": 2}})
    assert engine.state.total() == 5
    assert engine.state.availability()["source:S1"] == engine.state.availability()["source:S2"] == 0
    record = engine.tick([complete("finish", "A", 0, action_id=action)])
    assert record.outcomes[0].accepted
    assert engine.state.balances["A"] == 5
    assert all(source.stock == 0 for source in engine.state.sources.values())
    assert engine.state.total() == 5


def test_unrelated_denial_and_empty_ticks_do_not_cancel_or_complete():
    engine = Engine(world())
    action, _ = hold(engine)
    original = engine.state.reservations[action]
    denied = engine.tick([consume("too-much", "A", 0, amount=2)])
    assert denied.outcomes[0].reason == Reason.DENIED_INSUFFICIENT_BALANCE
    for _ in range(3):
        assert not engine.tick().outcomes
        assert engine.state.reservations[action] == original
    assert engine.tick([complete("finish", "A", 0, action_id=action)]).outcomes[0].accepted


def test_same_tick_completion_is_denied_even_with_predicted_identity():
    probe = Engine(world())
    predicted, _ = hold(probe)
    engine = Engine(world())
    record = engine.tick([reserve("hold", "A", 0, operation="transfer", params={"to": "B", "amount": 1}),
                          complete("early", "A", 1, action_id=predicted)])
    assert reason_of(record, "early") == Reason.DENIED_UNKNOWN_ACTION
    assert predicted in engine.state.reservations
    assert engine.state.balances == {"A": 2, "B": 0}


def test_reused_proposal_id_gets_new_action_id_and_old_request_cannot_close_it():
    engine = Engine(world())
    old, _ = hold(engine)
    engine.tick([cancel("stop", "A", 0, action_id=old)])
    new, _ = hold(engine)
    assert new != old
    record = engine.tick([complete("replay", "A", 0, action_id=old)])
    assert record.outcomes[0].reason == Reason.DENIED_UNKNOWN_ACTION
    assert new in engine.state.reservations


@pytest.mark.parametrize("operation,params,reason", [
    ("reserve", {}, Reason.DENIED_UNKNOWN_OPERATION),
    ("complete", {}, Reason.DENIED_UNKNOWN_OPERATION),
    ([], {}, Reason.DENIED_UNKNOWN_OPERATION),
    ("consume", None, Reason.DENIED_MALFORMED_PARAMS),
    ("consume", {1: 1}, Reason.DENIED_MALFORMED_PARAMS),
    ("consume", {"amount": True}, Reason.DENIED_NON_INTEGER_AMOUNT),
    ("consume", {"amount": 0}, Reason.DENIED_NON_POSITIVE_AMOUNT),
    ("transfer", {"to": "GHOST", "amount": 1}, Reason.DENIED_UNKNOWN_ACTOR),
    ("transfer", {"to": "A", "amount": 1}, Reason.DENIED_SELF_TRANSFER),
    ("claim", {"sources": {"missing": 1}}, Reason.DENIED_UNKNOWN_SOURCE),
])
def test_malformed_or_invalid_plans_leave_no_hold(operation, params, reason):
    engine = Engine(world())
    record = engine.tick([reserve("bad", "A", 0, operation=operation, params=params)])
    assert record.outcomes[0].reason == reason
    assert record.outcomes[0].effects == ()
    assert not engine.state.reservations
    assert engine.state.balances == {"A": 2, "B": 0}


@pytest.mark.parametrize("target", [None, "", 1, True, [], {}])
@pytest.mark.parametrize("terminal", [complete, cancel])
def test_malformed_terminal_targets_are_recorded_denials(target, terminal):
    engine = Engine(world())
    record = engine.tick([terminal("bad", "A", 0, action_id=target)])
    assert record.outcomes[0].reason == Reason.DENIED_MALFORMED_PARAMS


def test_different_targets_on_duplicate_proposals_have_stable_record_order():
    seen = set()
    for requests in permutations([cancel("same", "A", 0, action_id="b"), cancel("same", "A", 0, action_id="a")]):
        record = Engine(world()).tick(requests)
        assert [o.action_id for o in record.outcomes] == ["a", "b"]
        seen.add(record.digest())
    assert len(seen) == 1


def test_reservation_state_views_plans_and_records_are_immutable():
    params = {"to": "B", "amount": 1}
    request = reserve("hold", "A", 0, operation="transfer", params=params)
    params["amount"] = 99
    engine = Engine(world())
    first = engine.tick([request])
    action = first.outcomes[0].action_id
    boundary = engine.state
    view = engine.view_for("A")
    plan = boundary.reservations[action]
    original = (boundary.digest(), first.digest())
    assert view.reservations is not boundary.reservations
    with pytest.raises(TypeError): view.reservations[action] = None
    with pytest.raises(TypeError): boundary.reservations[action] = None
    with pytest.raises(FrozenInstanceError): plan.actor = "B"
    with pytest.raises(FrozenInstanceError): plan.effects[0].delta = 99
    copy = boundary.canonical()
    copy["reservations"][action]["effects"].clear()
    copy = first.canonical()
    copy["outcomes"][0]["reservation"]["effects"].clear()
    engine.tick([complete("finish", "A", 0, action_id=action)])
    assert engine.state.balances == {"A": 1, "B": 1}
    assert view.own_available == 1
    assert (boundary.digest(), first.digest()) == original


def test_diagnostics_cannot_change_lifecycle_or_identity():
    class Hostile:
        def record(self, event, payload):
            payload["outcomes"].clear()
            raise RuntimeError("observer failed")
    results = []
    for diagnostics in (None, Hostile()):
        engine = Engine(world(), diagnostics=diagnostics)
        action, first = hold(engine)
        second = engine.tick([complete("finish", "A", 0, action_id=action)])
        results.append((action, first.digest(), second.digest(), engine.state.digest()))
        assert engine.diagnostics_failures == (2 if diagnostics else 0)
    assert results[0] == results[1]


def test_permutations_of_two_reservations_and_mixed_terminal_requests():
    seen = set()
    for actors in permutations((("A", 1), ("B", 0))):
        for source_order in permutations(("S1", "S2")):
            for request_order in permutations((0, 1)):
                engine = Engine(WorldState.genesis(balances=dict(actors), sources={
                    key: Source(1, {"A", "B"}) for key in source_order}))
                requests = [reserve("rA", "A", 0, operation="transfer", params={"to": "B", "amount": 1}),
                            reserve("rB", "B", 0, operation="claim", params={"sources": {key: 1 for key in source_order}})]
                first = engine.tick([requests[i] for i in request_order])
                ids = {outcome.actor: outcome.action_id for outcome in first.outcomes}
                for terminal_order in permutations((0, 1, 2)):
                    fork = Engine(engine.state)
                    terminals = [complete("fA", "A", 0, action_id=ids["A"]),
                                 cancel("cB", "B", 0, action_id=ids["B"]),
                                 complete("fB", "B", 1, action_id=ids["B"])]
                    second = fork.tick([terminals[i] for i in terminal_order])
                    seen.add((first.digest(), second.digest(), fork.state.digest()))
    assert len(seen) == 1


def test_small_accounting_matrix_preserves_stock_and_exactly_once_effects():
    for stock, amount, close in product(range(4), range(1, 4), (complete, cancel)):
        engine = Engine(world(balance=0, stock=stock))
        record = engine.tick([reserve("r", "A", 0, operation="claim", params={"sources": {"S": amount}}),
                              claim("other", "B", 0, sources={"S": 1})])
        held = record.outcomes_for("r")[0]
        assert held.accepted == (amount <= stock)
        assert engine.state.total() == stock
        if held.accepted:
            before = dict(engine.state.balances)
            terminal = engine.tick([close("first", "A", 0, action_id=held.action_id),
                                    close("again", "A", 1, action_id=held.action_id)])
            assert sum(outcome.accepted for outcome in terminal.outcomes) == 1
            assert engine.state.balances["A"] == before["A"] + (amount if close is complete else 0)
        assert engine.state.total() == stock
        assert all(value >= 0 for value in engine.state.availability().values())


def test_huge_quantities_and_tick_keep_local_integer_policy():
    amount = 10 ** 5000
    engine = Engine(world(tick=amount, balance=amount, stock=0))
    action, _ = hold(engine, "consume", {"amount": amount})
    assert engine.tick([complete("finish", "A", 0, action_id=action)]).outcomes[0].accepted
    assert engine.state.consumed == engine.state.total() == amount


def test_failed_collection_and_commit_preserve_existing_hold(monkeypatch):
    engine = Engine(world())
    action, _ = hold(engine)
    before = engine.state
    def broken_collection():
        yield cancel("stop", "A", 0, action_id=action)
        raise RuntimeError("collection interrupted")
    with pytest.raises(RuntimeError, match="collection interrupted"):
        engine.tick(broken_collection())
    assert engine.state is before
    def failed_commit(*args):
        raise IntegrityError("commit failed")
    with monkeypatch.context() as m:
        m.setattr(settlement, "_commit", failed_commit)
        with pytest.raises(IntegrityError, match="commit failed"):
            engine.tick([complete("finish", "A", 0, action_id=action)])
    assert engine.state is before
    assert engine.tick([complete("retry", "A", 0, action_id=action)]).outcomes[0].accepted


def test_reservation_commit_rail_prevents_spending_held_stock():
    engine = Engine(world(balance=1, stock=0))
    hold(engine)
    with pytest.raises(IntegrityError, match="reserved stock"):
        settlement._commit(engine.state, {"actor:A": -1, "sink:consumed": 1})


def test_cancelling_one_of_two_holds_releases_only_that_hold():
    engine = Engine(world(balance=2, stock=0))
    first = engine.tick([
        reserve("one", "A", 0, operation="consume", params={"amount": 1}),
        reserve("two", "A", 1, operation="transfer", params={"to": "B", "amount": 1}),
    ])
    one, two = (outcome.action_id for outcome in first.outcomes)
    assert engine.view_for("A").own_available == 0
    engine.tick([cancel("stop", "A", 0, action_id=one)])
    assert set(engine.state.reservations) == {two}
    assert engine.view_for("A").own_available == 1
    record = engine.tick([consume("free", "A", 0, amount=1),
                          complete("held", "A", 1, action_id=two)])
    assert all(outcome.accepted for outcome in record.outcomes)
    assert engine.state.balances == {"A": 0, "B": 1}
    assert engine.state.consumed == 1
    assert engine.state.total() == 2


@pytest.mark.parametrize("close", [complete, cancel])
def test_new_reservation_cannot_use_completed_credit_or_cancelled_hold_early(close):
    engine = Engine(world(balance=1, stock=0))
    action, _ = hold(engine)
    recipient = "B" if close is complete else "A"
    record = engine.tick([
        close("close", "A", 0, action_id=action),
        reserve("early", recipient, 1, operation="consume", params={"amount": 1}),
    ])
    assert reason_of(record, "close") == Reason.ACCEPTED
    assert reason_of(record, "early") == Reason.DENIED_INSUFFICIENT_BALANCE
    assert not engine.state.reservations
    next_record = engine.tick([reserve("next", recipient, 0, operation="consume", params={"amount": 1})])
    assert next_record.outcomes[0].accepted


@pytest.mark.parametrize("changes", [
    {"actor": "B"}, {"created_tick": 1},
    {"effects": (Effect("source:missing", -1), Effect("actor:A", 1))},
    {"effects": (Effect("sink:consumed", -1), Effect("actor:A", 1))},
    {"effects": (Effect("actor:A", -3), Effect("actor:B", 3))},
])
def test_world_state_rejects_invalid_or_overcommitted_reservations(changes):
    plan = Reservation("action", "A", 0, "transfer", (Effect("actor:A", -1), Effect("actor:B", 1)))
    with pytest.raises(ValueError):
        WorldState.genesis(tick=1, balances={"A": 2, "B": 0}, reservations={"action": replace(plan, **changes)})


def test_state_copies_caller_reservation_map_and_rejects_wrong_identity():
    plan = Reservation("action", "A", 0, "transfer", [Effect("actor:A", -1), Effect("actor:B", 1)])
    mapping = {"action": plan}
    state = WorldState.genesis(tick=1, balances={"A": 1, "B": 0}, reservations=mapping)
    mapping.clear()
    assert state.reservations["action"] == plan
    with pytest.raises(ValueError, match="identity"):
        replace(state, reservations={"wrong": plan})
