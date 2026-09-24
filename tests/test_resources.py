"""Named resources in the kernel (2026-09-25): water beside the base resource.

A world that declares no named resource keeps exactly its earlier canonical
form (the 1a/1b fixtures and every earlier run file pin that). A declared
resource gets its own accounts, `actor@<r>:<id>` and `sink@<r>:consumed`,
sources say which resource they hold, and every transaction must balance per
resource.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import Engine, Source, WorldState, reasons
from kernel.proposals import cancel, claim, complete, consume, reserve, transfer
from kernel.state import actor_account, is_resource_name, resource_of, sink_account
from stream.run_file import RunWriter, decode_input, read_run

AB = frozenset({"a", "b"})


def world(water=3, food=2, well=5, field=5) -> WorldState:
    return WorldState.genesis(
        balances={"a": food, "b": food},
        holdings={"water": {"a": water, "b": water}},
        consumed_by={"water": 0},
        sources={"field": Source(field, AB), "well": Source(well, AB, resource="water")},
    )


def reason(record, proposal_id: str) -> str:
    return next(o.reason for o in record.outcomes if o.proposal_id == proposal_id)


def test_account_names_and_resource_names():
    assert actor_account("p1") == "actor:p1" and actor_account("p1", "water") == "actor@water:p1"
    assert sink_account() == "sink:consumed" and sink_account("water") == "sink@water:consumed"
    assert resource_of("actor@water:p1") == "water" and resource_of("actor:p1") is None
    assert resource_of("actor:@water:p1") is None          # an odd actor id stays a base account
    assert is_resource_name("water") and is_resource_name("salt_2")
    assert not any(is_resource_name(x) for x in ("", "Water", "2water", "wa:ter", None, 5))


def test_a_world_without_named_resources_keeps_its_canonical_form():
    state = WorldState.genesis(balances={"a": 1}, sources={"s": Source(2, frozenset({"a"}))})
    assert set(state.canonical()) == {"schema_version", "tick", "balances", "sources", "consumed", "reservations"}
    assert set(state.canonical()["sources"]["s"]) == {"stock", "authorised"}


def test_a_named_resource_state_round_trips():
    state = world()
    canonical = state.canonical()
    assert canonical["holdings"] == {"water": {"a": 3, "b": 3}} and canonical["consumed_by"] == {"water": 0}
    assert canonical["sources"]["well"]["resource"] == "water"
    assert WorldState.from_canonical(canonical).digest() == state.digest()
    assert state.totals() == {None: 9, "water": 11}


def test_claiming_water_credits_only_the_water_account():
    engine = Engine(world())
    record = engine.tick([claim("p", "a", 0, sources={"well": 2}, resource="water")])
    assert reason(record, "p") == reasons.ACCEPTED
    after = engine.state
    assert after.holdings["water"]["a"] == 5 and after.balances["a"] == 2 and after.sources["well"].stock == 3
    assert after.totals() == world().totals()


@pytest.mark.parametrize("proposal", [
    claim("p", "a", 0, sources={"well": 1}),                                   # water into the food account
    claim("p", "a", 0, sources={"field": 1}, resource="water"),               # food into the water account
    claim("p", "a", 0, sources={"field": 1, "well": 1}, resource="water"),    # mixed sources
])
def test_a_transaction_that_mixes_resources_is_refused_whole(proposal):
    start = world()
    engine = Engine(start)
    record = engine.tick([proposal])
    assert reason(record, "p") == reasons.DENIED_RESOURCE_MISMATCH
    after = engine.state
    assert dict(after.balances) == dict(start.balances)
    assert {r: dict(m) for r, m in after.holdings.items()} == {r: dict(m) for r, m in start.holdings.items()}
    assert {k: v.stock for k, v in after.sources.items()} == {k: v.stock for k, v in start.sources.items()}


def test_water_transfers_and_consumption_stay_in_water():
    engine = Engine(world())
    record = engine.tick([transfer("t", "a", 0, to="b", amount=2, resource="water"),
                          consume("c", "b", 0, amount=1, resource="water")])
    assert reason(record, "t") == reason(record, "c") == reasons.ACCEPTED
    after = engine.state
    assert dict(after.holdings["water"]) == {"a": 1, "b": 4} and after.consumed_by["water"] == 1
    assert dict(after.balances) == {"a": 2, "b": 2} and after.consumed == 0


def test_water_overdraw_is_refused_even_with_food_to_spare():
    engine = Engine(world(water=1, food=50))
    record = engine.tick([consume("c", "a", 0, amount=2, resource="water")])
    assert reason(record, "c") == reasons.DENIED_INSUFFICIENT_BALANCE


@pytest.mark.parametrize("resource, expected", [
    ("oil", reasons.DENIED_UNKNOWN_RESOURCE),
    ("Water!", reasons.DENIED_MALFORMED_PARAMS),
])
def test_unknown_and_malformed_resources_are_refused(resource, expected):
    engine = Engine(world())
    record = engine.tick([consume("c", "a", 0, amount=1, resource=resource)])
    assert reason(record, "c") == expected


def test_a_reserved_water_plan_holds_water_until_it_completes():
    engine = Engine(world(water=3))
    first = engine.tick([reserve("r", "a", 0, operation="consume", params={"amount": 3, "resource": "water"})])
    assert reason(first, "r") == reasons.ACCEPTED
    action = next(o.action_id for o in first.outcomes if o.proposal_id == "r")
    view = engine.state.view_for("a")
    assert view.own_available_of("water") == 0 and view.own_available_of() == 2
    second = engine.tick([complete("k", "a", 0, action_id=action),
                          consume("c", "a", 1, amount=1, resource="water")])
    assert reason(second, "k") == reasons.ACCEPTED
    assert reason(second, "c") == reasons.DENIED_INSUFFICIENT_BALANCE        # held water was not free
    assert engine.state.holdings["water"]["a"] == 0 and engine.state.consumed_by["water"] == 3


def test_cancelling_a_water_hold_frees_it_next_tick():
    engine = Engine(world(water=2))
    first = engine.tick([reserve("r", "a", 0, operation="transfer",
                                 params={"to": "b", "amount": 2, "resource": "water"})])
    action = next(o.action_id for o in first.outcomes if o.proposal_id == "r")
    engine.tick([cancel("x", "a", 0, action_id=action)])
    record = engine.tick([consume("c", "a", 0, amount=2, resource="water")])
    assert reason(record, "c") == reasons.ACCEPTED


def test_two_claimants_for_the_last_unit_of_water_one_wins():
    engine = Engine(world(well=1))
    record = engine.tick([claim("pa", "a", 0, sources={"well": 1}, resource="water"),
                          claim("pb", "b", 0, sources={"well": 1}, resource="water")])
    assert sorted([reason(record, "pa"), reason(record, "pb")]) == sorted(
        [reasons.ACCEPTED, reasons.DENIED_INSUFFICIENT_SOURCE])
    assert engine.state.sources["well"].stock == 0
    assert engine.state.totals()["water"] == world(well=1).totals()["water"]


def test_the_state_refuses_bad_named_resource_shapes():
    with pytest.raises(ValueError):
        WorldState.genesis(balances={"a": 1, "b": 1}, holdings={"water": {"a": 1}}, consumed_by={"water": 0})
    with pytest.raises(ValueError):
        WorldState.genesis(balances={"a": 1}, holdings={"water": {"a": 1}}, consumed_by={})
    with pytest.raises(ValueError):
        WorldState.genesis(balances={"a": 1}, sources={"well": Source(1, frozenset({"a"}), resource="water")})
    with pytest.raises(ValueError):
        WorldState.genesis(balances={"a": 1}, holdings={"Water": {"a": 1}}, consumed_by={"Water": 0})
    with pytest.raises(ValueError):
        Source(1, frozenset(), resource="Water")


def test_a_sealed_run_with_water_verifies_and_replays(tmp_path: Path):
    engine = Engine(world())
    path = tmp_path / "water.jsonl"
    ticks = [
        [claim("p0", "a", 0, sources={"well": 2}, resource="water"), claim("q0", "b", 0, sources={"field": 1})],
        [transfer("p1", "a", 0, to="b", amount=1, resource="water"), consume("q1", "b", 0, amount=1)],
        [consume("p2", "b", 0, amount=2, resource="water")],
    ]
    with RunWriter(path, run_id="water-test", genesis=engine.state, scenario={"name": "water-test"},
                   horizon=len(ticks)) as writer:
        for proposals in ticks:
            record = engine.tick(proposals)
            writer.record(record, engine.state, inputs=proposals, elapsed_ns=0)
        writer.close()
    run = read_run(path)
    assert run.complete and len(run.ticks) == 3
    replay = Engine(WorldState.from_canonical(run.header["genesis"]))
    for tick in run.ticks:
        replay.tick([decode_input(entry) for entry in tick["inputs"]])
        assert replay.state.digest() == tick["state_digest"]
    assert replay.state.consumed_by["water"] == 2 and replay.state.consumed == 1