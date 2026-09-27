"""Received food can change a later choice, without creating help or resources."""

import json
from dataclasses import replace

import pytest

from kernel import Engine, WorldState, transfer
from world.config import WorldConfig
from world.decide import decide, someone_to_help
from world.observe import Observation, SeenPerson, observe
from world.overlay import Overlay
from world.social import remember_food
from world.run import run_world
from world.replay import replay_world
from world.recover import recover_world
from world.viewer import render_html
from world.viewer_index import build_index
from stream.run_file import read_run


def family():
    positions = {p: (i, 1) for i, p in enumerate("abcdef")}
    return Overlay(tick=10, homes=positions, positions=positions,
                   hunger={p: 0 for p in positions}, yield_at={p: 1 for p in positions})


def test_only_received_food_is_remembered_and_input_stays_immutable():
    ov = family()
    ledger = WorldState.genesis(tick=10, balances={p: 2 for p in ov.roster},
                               holdings={"water": {p: 2 for p in ov.roster}}, consumed_by={"water": 0})
    engine = Engine(ledger)
    record = engine.tick([transfer("food", "a", 0, to="b", amount=1),
                          transfer("water", "c", 0, to="b", amount=1, resource="water"),
                          transfer("refused", "d", 0, to="b", amount=20)])
    assert remember_food(ov, record) == {"b": (("a", 11),)}
    assert ov.food_memory == {} and ledger.balances["a"] == 2
    assert engine.state.balances["a"] == 1 and engine.state.balances["b"] == 3


def test_four_distinct_donors_refresh_without_duplicate_and_round_trip():
    ov = replace(family(), food_memory={"f": (("a", 1), ("b", 2), ("c", 3), ("d", 4))})
    def give(donor):
        engine = Engine(WorldState.genesis(tick=10, balances={p: 2 for p in ov.roster}))
        record = engine.tick([transfer("gift", donor, 0, to="f", amount=1)])
        return remember_food(ov, record)
    assert give("e")["f"] == (("e", 11), ("d", 4), ("c", 3), ("b", 2))
    assert give("a")["f"] == (("a", 11), ("d", 4), ("c", 3), ("b", 2))
    after = replace(ov, tick=11, food_memory=give("e"))
    assert Overlay.from_canonical(after.canonical()).digest() == after.digest()
    with pytest.raises(TypeError):
        after.food_memory["f"] = ()
    with pytest.raises(TypeError):
        after.food_memory["f"][0][1] = 5
    assert Overlay.from_canonical(family().canonical()).food_memory == {}


@pytest.mark.parametrize("memory", [
    {"unknown": (("a", 1),)}, {"a": (("unknown", 1),)}, {"a": (("a", 1),)},
    {"a": (("b", 11),)}, {"a": (("b", True),)}, {"a": (("b", 0),)},
    {"a": (("b", 1), ("b", 2))}, {"a": tuple((p, 1) for p in "bcdef")}, [],
])
def test_invalid_memories_are_rejected(memory):
    with pytest.raises(ValueError):
        replace(family(), food_memory=memory)


def choice():
    cfg = WorldConfig(seed=1, water_on=False, warmth_on=False, plan_trips=False)
    view = Observation(actor="a", tick=11, alive=True, position=(1, 1), home=(1, 1),
                       hunger=0, food=1, source=(6, 6), source_food=None,
                       others=(SeenPerson("b", (2, 1), 0, starving=True),
                               SeenPerson("c", (3, 1), 0, starving=True)),
                       food_memory=(("c", 8),))
    return cfg, view


def test_real_choice_changes_and_records_the_prior_gift():
    cfg, view = choice()
    assert someone_to_help(replace(view, food_memory=()), cfg) == "b"
    decision = decide(view, cfg)
    assert decision.target == "c" and decision.kind == "go_offer"
    assert decision.helped_at == 8 and decision.canonical()["helped_at"] == 8
    assert "gave me food at tick 8" in decision.reason
    assert decide(view, replace(cfg, social_memory_on=False)).target == "b"


def test_memory_does_not_create_eligibility_or_override_children_promises_or_needs():
    cfg, view = choice()
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    assert decide(replace(view, food=0), cfg).kind != "go_offer"
    assert decide(view, replace(cfg, offers_on=False)).kind != "go_offer"
    for changes in ({"dependents": frozenset({"b"})}, {"owed_to": "b"}):
        decision = decide(replace(view, **changes), cfg)
        assert decision.target == "b" and decision.helped_at is None
    for others in ((view.others[0],),
                   (view.others[0], replace(view.others[1], starving=False))):
        assert someone_to_help(replace(view, others=others), cfg) == "b"


def test_memory_stays_personal_and_does_not_reveal_absent_or_dead_donors():
    ov = replace(family(), food_memory={"a": (("f", 8),)}, died_at={"f": 9})
    ledger = WorldState.genesis(tick=10, balances={p: 1 for p in ov.roster})
    cfg = WorldConfig(seed=1, water_on=False, warmth_on=False, perception_radius=1)
    a = observe("a", ledger, ov, cfg)
    b = observe("b", ledger, ov, cfg)
    assert a.food_memory == (("f", 8),) and not b.food_memory
    assert all(p.actor != "f" for p in a.others)
    assert not observe("a", ledger, ov, replace(cfg, social_memory_on=False)).food_memory


def test_saved_memory_survives_births_replay_and_recovery(tmp_path):
    cfg = WorldConfig(seed=7)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    old = replace(cfg, social_memory_on=False)
    assert "social_memory" not in old.describe()
    assert WorldConfig.from_describe(old.describe()) == old
    path = tmp_path / "world.jsonl"
    run_world(cfg, 400, path)
    run = read_run(path)
    assert run.ticks[218]["world"]["food_memory"]["p07"] == [["p01", 219]]
    assert run.ticks[-1]["world"]["food_memory"]["p07"]
    assert len(run.ticks[-1]["world"]["parent"]) > 1
    assert replay_world(path).identical
    lines = path.read_bytes().splitlines(keepends=True)
    cut_at = next(i for i, line in enumerate(lines)
                  if json.loads(line).get("kind") == "tick" and json.loads(line).get("tick") == 219)
    cut, recovered = tmp_path / "cut.jsonl", tmp_path / "recovered.jsonl"
    cut.write_bytes(b"".join(lines[:cut_at+1]))
    recover_world(cut, recovered)
    assert read_run(recovered).ticks == run.ticks
    assert replay_world(recovered).identical
    page = render_html(run)
    assert "People who fed me" in page and "food_memory" in page


@pytest.mark.parametrize("seed,horizon,gift_tick,choice_tick,helper,recipient", [
    (14, 650, 534, 643, "p10", "p03"),
    (26, 780, 588, 774, "p22", "p02"),
])
def test_remembered_gift_changes_choice_and_is_visible(tmp_path, seed, horizon, gift_tick,
                                                     choice_tick, helper, recipient):
    path = tmp_path / "social.jsonl"
    run_world(WorldConfig(seed=seed), horizon, path)
    run = read_run(path)
    gift = run.ticks[gift_tick - 1]
    assert any(o["actor"] == recipient and o["operation"] == "transfer" and o["accepted"]
               and {"account": f"actor:{helper}", "delta": 1} in o["effects"]
               for o in gift["record"]["outcomes"])
    decision = run.ticks[choice_tick - 1]["decisions"][helper]
    assert decision["target"] == recipient and decision["helped_at"] == gift_tick
    if seed == 26:
        before = run.ticks[choice_tick - 2]
        state = WorldState.from_canonical(before.get("produced_state") or before["state"])
        ov = Overlay.from_canonical(before["world"])
        cfg = WorldConfig(seed=seed)
        view = observe(helper, state, ov, cfg)
        alternative = decide(replace(view, food_memory=()), cfg)
        assert alternative.target == "p06" and alternative.step == (8, 3)
        assert decision["step"] == [6, 3]
    index = build_index(run)
    event = next(e for e in index["events"] if e["kind"] == "remembered_helper" and e["k"] == choice_tick)
    assert (event["who"], event["other"], event["helped_at"]) == (helper, recipient, gift_tick)
    assert replay_world(path).identical
