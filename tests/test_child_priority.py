"""Visible hunger emergencies can change which dependent receives scarce food."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import decide, someone_to_help
from world.observe import Observation, SeenPerson, observe
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index


def competing_children():
    cfg = WorldConfig(seed=24, care_by_need_on=True, water_on=False, warmth_on=False)
    view = Observation(actor="p01", tick=10, alive=True, position=(5, 5), home=(5, 5),
                       hunger=0, food=1, source=(6, 6), source_food=0,
                       dependents=frozenset({"p02", "p03"}),
                       others=(SeenPerson("p02", (5, 6), 0),
                               SeenPerson("p03", (5, 3), 0, starving=True)))
    return cfg, view


def test_visible_emergency_changes_recipient_without_requiring_shared_care():
    cfg, view = competing_children()
    old = decide(view, replace(cfg, care_by_need_on=False))
    new = decide(view, cfg)
    assert (old.kind, old.target) == ("offer", "p02")
    assert (new.kind, new.target) == ("go_offer", "p03")
    assert "visibly starving" in new.reason
    assert not cfg.shared_care_on


@pytest.mark.parametrize("starving", [False, True])
def test_equal_visible_need_uses_distance_then_id_regardless_of_roster_order(starving):
    cfg, view = competing_children()
    children = (SeenPerson("p03", (5, 4), 0, starving=starving),
                SeenPerson("p02", (5, 6), 0, starving=starving))
    assert someone_to_help(replace(view, others=children), cfg) == "p02"
    assert someone_to_help(replace(view, others=children[::-1]), cfg) == "p02"
    closer = replace(children[0], position=(5, 5))
    assert someone_to_help(replace(view, others=(closer, children[1])), cfg) == "p03"


@pytest.mark.parametrize("change", ["food", "absent", "grown", "thirst_only"])
def test_priority_requires_visible_empty_handed_dependent_in_hunger_emergency(change):
    cfg, view = competing_children()
    young, urgent = view.others
    if change == "food":
        view = replace(view, others=(young, replace(urgent, food=1)))
    elif change == "absent":
        view = replace(view, others=(young,))
    elif change == "grown":
        view = replace(view, dependents=frozenset({"p02"}))
    else:
        view = replace(view, others=(young, replace(urgent, starving=False, parched=True)))
    assert decide(view, cfg).target == "p02"


def test_observation_exposes_only_emergency_and_never_absent_hunger():
    cfg = WorldConfig(seed=7, actors=3, care_by_need_on=True)
    ledger, world = genesis(cfg)
    ledger = replace(ledger, balances={"p01": 1, "p02": 0, "p03": 0})
    world = replace(world, positions={"p01": (5, 5), "p02": (5, 6), "p03": (5, 3)},
                    parent={"p02": "p01", "p03": "p01"},
                    age={"p01": cfg.adult_at, "p02": 5, "p03": 5},
                    hunger={"p01": 0, "p02": cfg.emergency_at, "p03": cfg.death_at-1})
    first = observe("p01", ledger, world, cfg)
    changed = observe("p01", ledger, replace(world, hunger={"p01": 0,
                      "p02": cfg.death_at-1, "p03": cfg.emergency_at}), cfg)
    assert first.others == changed.others  # exact hunger does not leave its owner
    assert someone_to_help(first, cfg) == someone_to_help(changed, cfg) == "p02"
    distant = replace(world, positions=dict(world.positions, p03=(0, 0)))
    assert all(p.actor != "p03" for p in observe("p01", ledger, distant, cfg).others)


def test_personal_needs_still_interrupt_and_no_food_means_no_transfer():
    cfg, view = competing_children()
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    assert decide(replace(view, food=0), cfg).kind not in ("offer", "go_offer")
    water = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=water.thirsty_at, water=1,
                          water_source=(3, 3)), water).kind == "drink"
    warmth = replace(cfg, warmth_on=True)
    assert decide(replace(view, home=(0, 0), cold=warmth.cold_at), warmth).kind == "go_shelter"


def test_distant_emergency_does_not_extend_the_nearby_handoff_exception():
    cfg, view = competing_children()
    cfg = replace(cfg, warmth_on=True)
    view = replace(view, home=(5, 8), cold=cfg.cold_at-1)
    assert decide(view, replace(cfg, care_by_need_on=False)).kind == "offer"
    assert decide(view, cfg).kind == "go_shelter"
    # If the selected starving child is itself alongside, the existing exception applies.
    nearby = replace(view.others[1], position=(5, 4))
    choice = decide(replace(view, others=(view.others[0], nearby)), cfg)
    assert (choice.kind, choice.target) == ("offer", "p03")
    assert "before heading home" in choice.reason


def test_config_cli_and_legacy_descriptions():
    cfg = config_from(build_parser().parse_args(["--seed", "24", "--care-by-need", "on"]))
    assert cfg.care_by_need_on and "care-by-need" in run_id_for(cfg, 400)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    off = replace(cfg, care_by_need_on=False)
    assert "care_by_need" not in off.describe()
    assert WorldConfig.from_describe(off.describe()) == off
    with pytest.raises(ValueError):
        replace(cfg, childhood_on=False)
    for value in (True, None, "yes", 1):
        with pytest.raises(ValueError):
            WorldConfig.from_describe(dict(cfg.describe(), care_by_need=value))
    with pytest.raises(ValueError):
        WorldConfig.from_describe(dict(cfg.describe(), decision=off.describe()["decision"]))


def test_ordinary_seed24_choice_transfer_meal_and_sibling_consequence():
    cfg = WorldConfig(seed=24, shared_care_on=True, care_by_need_on=True)
    ledger, world = genesis(cfg)
    engine = Engine(ledger)
    for tick in range(262):
        before = engine.state
        step = world_step(engine, world, cfg)
        if tick == 244:
            view = step.views["p04"]
            assert view.food == 1 and {"p19", "p23"} <= view.dependents
            old = decide(view, replace(cfg, care_by_need_on=False))
            assert (old.kind, old.target) == ("offer", "p23")
            assert (step.decisions["p04"].kind, step.decisions["p04"].target) == ("go_offer", "p19")
        if tick == 246:
            assert (step.decisions["p04"].kind, step.decisions["p04"].target) == ("offer", "p19")
            assert next(o for o in step.record.outcomes if o.actor == "p04").accepted
            assert (step.committed.balances["p04"], step.committed.balances["p19"]) == (0, 1)
            assert step.committed.totals() == before.totals()
            assert (before.balances["p04"], before.balances["p19"]) == (1, 0)
            assert step.decisions["p19"].kind != "eat"  # incoming credit waits a tick
        if tick == 247:
            assert step.decisions["p19"].kind == "eat"
            assert (world.hunger["p19"], step.processed.overlay.hunger["p19"]) == (56, 27)
        if tick == 261:
            assert step.decisions["p23"].kind == "eat"
            assert world.hunger["p23"] == 28 and step.processed.overlay.hunger["p23"] == 0
        engine, world = step.engine, step.processed.overlay


def test_saved_ordinary_scene_replays_recovers_repeats_and_explains_the_choice(tmp_path):
    cfg = WorldConfig(seed=24, shared_care_on=True, care_by_need_on=True)
    path = tmp_path / "siblings.jsonl"
    result = run_world(cfg, 265, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    assert run_world(cfg, 265, tmp_path / "repeat.jsonl").trail_digest == result.trail_digest
    events = build_index(run)["events"]
    assert any(e["kind"] == "fed_child" and e["who"] == "p04" and e["other"] == "p19"
               and e["k"] == 247 for e in events)
    assert "visibly starving, prioritised" in render_html(run)
    lines = path.read_bytes().splitlines(keepends=True)
    for completed in (244, 246, 247):
        end = next(i for i, line in enumerate(lines)
                   if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == completed-1)
        cut, restored = tmp_path / f"cut-{completed}.jsonl", tmp_path / f"restored-{completed}.jsonl"
        cut.write_bytes(b"".join(lines[:end+1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks
