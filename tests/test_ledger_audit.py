"""The ledger audit explains every account change, and notices when one is not explained."""

import copy
from dataclasses import replace

import pytest

from stream.run_file import read_run
from tests.ledger_audit import audit_run, resource_totals
from world.config import WorldConfig
from world.run import run_world

CONFIGS = {
    "defaults": (WorldConfig(seed=23), 160),
    "stores-homes-wood": (WorldConfig(seed=7, stores_on=True, homes_on=True, wood_on=True), 160),
    "fishing-provisioning": (WorldConfig(seed=11, fishing_on=True, stores_on=True, provisioning_on=True), 160),
    "asking-and-children": (WorldConfig(seed=24, requests_on=True, adjacent_requests=True, water_care_on=True), 160),
}


@pytest.fixture(scope="module", params=sorted(CONFIGS))
def saved(request, tmp_path_factory):
    cfg, ticks = CONFIGS[request.param]
    path = tmp_path_factory.mktemp(request.param) / "run.jsonl"
    run_world(cfg, ticks, path)
    run = read_run(path)
    assert run.complete
    return run


def test_real_runs_have_every_account_change_explained(saved):
    assert audit_run(saved) == []


def test_the_audited_runs_actually_exercise_the_ledger(saved):
    accepted = [o for tick in saved.ticks for o in tick["record"]["outcomes"] if o["accepted"]]
    assert accepted, "a run with no accepted transactions proves nothing"
    assert any(tick.get("production") for tick in saved.ticks)


def _tampered(run, edit):
    ticks = [copy.deepcopy(tick) for tick in run.ticks]
    edit(ticks)
    return replace(run, ticks=tuple(ticks))


def _first_accepted(ticks):
    for index, tick in enumerate(ticks):
        for outcome in tick["record"]["outcomes"]:
            if outcome["accepted"] and outcome["effects"]:
                return index, outcome
    raise AssertionError("no accepted outcome to tamper with")


def test_a_balance_that_changed_without_a_transaction_is_found(saved):
    def edit(ticks):
        index, _ = _first_accepted(ticks)
        actor = sorted(ticks[index]["state"]["balances"])[0]
        ticks[index]["state"]["balances"][actor] += 1
    assert any("differs from the accepted effects" in p for p in audit_run(_tampered(saved, edit)))


def test_an_accepted_transaction_whose_effect_vanished_is_found(saved):
    def edit(ticks):
        _, outcome = _first_accepted(ticks)
        outcome["effects"] = outcome["effects"][:-1]
    problems = audit_run(_tampered(saved, edit))
    assert problems


def test_a_refused_outcome_that_still_moved_units_is_found(saved):
    def edit(ticks):
        _, outcome = _first_accepted(ticks)
        outcome["accepted"], outcome["reason"] = 0, "denied_insufficient_balance"
    assert any("refused" in p for p in audit_run(_tampered(saved, edit)))


def test_a_total_that_changed_by_settlement_is_found(saved):
    def edit(ticks):
        index, _ = _first_accepted(ticks)
        ticks[index]["state"]["consumed"] += 1
    assert any("resource total" in p or "sink:consumed" in p for p in audit_run(_tampered(saved, edit)))


def test_inflated_production_is_found_by_the_following_tick(saved):
    def edit(ticks):
        for index, tick in enumerate(ticks[:-1]):
            for entry in tick.get("production") or []:
                if "amount" in entry:
                    entry["amount"] += 1
                    return
        raise AssertionError("no renewal to inflate")
    assert audit_run(_tampered(saved, edit))


def test_totals_count_held_stocked_and_consumed_units_once():
    state = {"balances": {"p01": 2}, "consumed": 3,
             "sources": {"food": {"stock": 4, "authorised": ["p01"]},
                         "well": {"stock": 5, "authorised": ["p01"], "resource": "water"}},
             "holdings": {"water": {"p01": 1}}, "consumed_by": {"water": 2}}
    assert resource_totals(state) == {None: 2 + 3 + 4, "water": 1 + 2 + 5}
