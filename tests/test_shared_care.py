"""Both recorded birth parents use the existing local caregiving contracts."""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import RunWriter, read_run
from world.config import WorldConfig, genesis
from world.decide import decide
from world.housing import can_relocate, MOVE_COOLDOWN, DIFFICULT_OUTINGS
from world.observe import observe
from world.overlay import Overlay
from world.process import _births
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index


def birth_scene(shared=True):
    cfg = WorldConfig(seed=7, actors=2, shared_care_on=shared, birth_spacing=30,
                      together_ticks=1, water_on=False, warmth_on=False, terrain_on=False)
    ledger, world = genesis(cfg)
    homes = {"p01": (1, 1), "p02": (2, 1)}
    world = replace(world, homes=homes, positions=homes, hunger={p: 0 for p in homes},
                    shelters=tuple(homes.values()), built={p: cfg.build_ticks for p in homes})
    return cfg, ledger, world


def family():
    cfg, ledger, world = birth_scene()
    step = world_step(Engine(ledger), world, cfg)
    assert step.processed.production == ({"born": "p03"},)
    world = step.processed.overlay
    # Both adults alongside the child, with the same local opportunities.
    positions = {"p01": (1, 1), "p02": (2, 1), "p03": (1, 1)}
    return cfg, step.engine.state, replace(world, positions=positions)


def test_birth_records_both_distinct_parents_without_changing_home_or_creating_food():
    cfg, ledger, world = birth_scene()
    step = world_step(Engine(ledger), world, cfg)
    after = step.processed.overlay
    assert after.parent == {"p03": "p01"}
    assert after.second_parent == {"p03": "p02"}
    assert after.children_of("p01") == after.children_of("p02") == frozenset({"p03"})
    assert not world.parent and not world.second_parent
    assert step.engine.state.balances["p03"] == 0
    assert step.engine.state.totals() == ledger.totals()
    old = world_step(Engine(ledger), world, replace(cfg, shared_care_on=False))
    assert old.processed.overlay.homes == after.homes
    assert "second_parent" not in old.processed.overlay.canonical()


def test_both_can_transfer_in_the_same_tick_and_child_spends_only_next_tick():
    cfg, ledger, world = family()
    world = replace(world, hunger=dict(world.hunger, p03=cfg.hungry_at))
    step = world_step(Engine(ledger), world, cfg)
    for actor in ("p01", "p02"):
        assert step.views[actor].dependents == frozenset({"p03"})
        assert step.decisions[actor].kind == "offer"
        assert step.decisions[actor].target == "p03"
        assert next(o for o in step.record.outcomes if o.actor == actor).accepted
        assert step.committed.balances[actor] == ledger.balances[actor] - 1
    assert step.committed.balances["p03"] == 2
    assert step.decisions["p03"].kind != "eat"
    assert step.engine.state.totals() == ledger.totals()
    following = world_step(step.engine, step.processed.overlay, cfg)
    assert following.decisions["p03"].kind == "eat"
    assert following.committed.balances["p03"] == 1
    assert following.processed.overlay.hunger["p03"] < step.processed.overlay.hunger["p03"]
    assert all(following.decisions[p].kind != "offer" for p in ("p01", "p02"))


@pytest.mark.parametrize("unavailable", ["away", "dead", "hungry", "empty"])
def test_second_parent_can_help_when_first_cannot(unavailable):
    cfg, ledger, world = family()
    if unavailable == "away":
        world = replace(world, positions=dict(world.positions, p01=(8, 8)))
    elif unavailable == "dead":
        world = replace(world, died_at={"p01": world.tick})
    elif unavailable == "hungry":
        world = replace(world, hunger=dict(world.hunger, p01=cfg.hungry_at))
    else:
        ledger = replace(ledger, balances=dict(ledger.balances, p01=0))
    step = world_step(Engine(ledger), world, cfg)
    assert step.decisions["p02"].kind == "offer"
    assert step.decisions["p02"].target == "p03"
    assert step.committed.balances["p02"] == ledger.balances["p02"] - 1
    assert "p01" not in step.decisions or step.decisions["p01"].kind != "offer"
    view = step.views["p02"]
    without_relationship = replace(view, children=frozenset(), dependents=frozenset())
    assert decide(without_relationship, cfg).kind != "offer"


@pytest.mark.parametrize("change", ["out_of_sight", "grown", "dead", "fed"])
def test_relationship_does_not_create_a_visible_dependent_opportunity(change):
    cfg, ledger, world = family()
    if change == "out_of_sight":
        world = replace(world, positions=dict(world.positions, p03=(8, 8)))
    elif change == "grown":
        world = replace(world, age=dict(world.age, p03=cfg.adult_at))
    elif change == "dead":
        world = replace(world, died_at={"p03": world.tick})
    else:
        ledger = replace(ledger, balances=dict(ledger.balances, p03=1))
    view = observe("p02", ledger, world, cfg)
    assert "p03" in view.children
    assert decide(view, cfg).kind not in ("offer", "go_offer")


def test_second_parent_keeps_personal_need_priority_and_relocation_responsibility():
    cfg, ledger, world = family()
    view = observe("p02", ledger, world, cfg)
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    water = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=water.thirsty_at, water=1,
                          water_source=(6, 4)), water).kind == "drink"
    warmth = replace(cfg, warmth_on=True)
    assert decide(replace(view, cold=warmth.cold_at, home=(8, 8)), warmth).kind == "go_shelter"
    moved = replace(world, tick=MOVE_COOLDOWN, homes=dict(world.homes, p02=(7, 7)),
                    home_strain={"p02": DIFFICULT_OUTINGS})
    housing = replace(cfg, homes_on=True, relocation_on=True)
    assert not can_relocate("p02", moved, housing)
    assert can_relocate("p02", replace(moved, age=dict(moved.age, p03=cfg.adult_at)), housing)
    assert can_relocate("p02", replace(moved, died_at={"p03": moved.tick}), housing)
    assert moved.children_of("p02") == frozenset({"p03"})


def test_links_are_immutable_round_trip_and_survive_a_later_birth():
    cfg, ledger, world = family()
    source = {"p03": "p02"}
    world = replace(world, second_parent=source)
    source.clear()
    assert world.second_parent == {"p03": "p02"}
    with pytest.raises(TypeError):
        world.second_parent["p03"] = "p01"
    assert Overlay.from_canonical(world.canonical()).canonical() == world.canonical()
    later, _, born = _births(replace(world, tick=32), replace(ledger, tick=32), cfg)
    assert born and later.second_parent["p03"] == "p02"
    assert later.second_parent[born[0]] == "p02"
    legacy = replace(world, second_parent={}).canonical()
    assert "second_parent" not in legacy
    assert Overlay.from_canonical(legacy).canonical() == legacy


@pytest.mark.parametrize("links", [None, [], {"p03": "p01"}, {"p03": "p03"},
                                  {"p03": "missing"}, {"p02": "p01"}, {"missing": "p02"}])
def test_invalid_second_parent_links_fail(links):
    _, _, world = family()
    with pytest.raises(ValueError):
        replace(world, second_parent=links)


def test_config_cli_and_legacy_descriptions():
    cfg = config_from(build_parser().parse_args(["--seed", "7", "--shared-care", "on"]))
    assert cfg.shared_care_on and "shared-care" in run_id_for(cfg, 50)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    off = replace(cfg, shared_care_on=False)
    assert "shared_care" not in off.describe()
    assert WorldConfig.from_describe(off.describe()) == off
    with pytest.raises(ValueError):
        replace(cfg, childhood_on=False)
    for value in (True, None, "yes", 1):
        with pytest.raises(ValueError):
            WorldConfig.from_describe(dict(cfg.describe(), shared_care=value))
    altered = dict(cfg.describe(), decision=off.describe()["decision"])
    with pytest.raises(ValueError):
        WorldConfig.from_describe(altered)


def save_birth_scene(path):
    """A controlled initial arrangement; all later births/actions are native."""
    cfg, ledger, world = birth_scene()
    # The first parent starts without food. The second has the usual supply,
    # so the child's first delivery must come from that parent. No later edits.
    ledger = replace(ledger, balances=dict(ledger.balances, p01=0))
    engine = Engine(ledger)
    with RunWriter(path, run_id="controlled-shared-care", genesis=ledger,
                   scenario=cfg.describe(), world=world.canonical(), horizon=40) as writer:
        for _ in range(40):
            step = world_step(engine, world, cfg)
            writer.record(step.record, step.committed, inputs=step.proposals, **step.line_fields())
            engine, world = step.engine, step.processed.overlay
        return writer.close()


def test_saved_birth_recovery_before_and_after_birth_and_viewer(tmp_path):
    path = tmp_path / "controlled.jsonl"
    trail = save_birth_scene(path)
    run = read_run(path)
    assert run.complete and run.ticks[0]["world"]["second_parent"] == {"p03": "p02"}
    index = build_index(run)
    assert index["second_parent"] == run.ticks[-1]["world"]["second_parent"]
    assert any(e["kind"] == "birth" and "p01 and p02" in e["text"] for e in index["events"])
    assert any(e["kind"] == "fed_child" and e["who"] == "p02" for e in index["events"])
    assert "SECOND_PARENT" in render_html(run)
    lines = path.read_bytes().splitlines(keepends=True)
    for count in (0, 1, 2, 20):
        end = 0 if count == 0 else next(i for i, line in enumerate(lines)
                   if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == count - 1)
        cut, restored = tmp_path / f"cut-{count}.jsonl", tmp_path / f"restored-{count}.jsonl"
        cut.write_bytes(b"".join(lines[:end + 1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks
    assert save_birth_scene(tmp_path / "repeat.jsonl") == trail


def test_generated_world_replay_repeat_and_actual_second_parent_care(tmp_path):
    cfg = WorldConfig(seed=7, shared_care_on=True)
    path = tmp_path / "ordinary.jsonl"
    # At 240 ticks the second parent had only started interrupted errands.
    # The inspected 400-tick world contains a completed second-parent handoff.
    first = run_world(cfg, 400, path)
    second = run_world(cfg, 400, tmp_path / "repeat.jsonl")
    assert first.trail_digest == second.trail_digest
    assert replay_world(path).identical
    run = read_run(path)
    index = build_index(run)
    assert any(e["kind"] == "fed_child" and index["second_parent"].get(e["other"]) == e["who"]
               for e in index["events"])


def test_seed11_second_parent_delivery_changes_the_choice_and_leads_to_a_meal():
    cfg = WorldConfig(seed=11, shared_care_on=True)
    ledger, world = genesis(cfg)
    engine = Engine(ledger)
    for _ in range(42):
        step = world_step(engine, world, cfg)
        engine, world = step.engine, step.processed.overlay
    assert world.parent["p08"] == "p03" and world.second_parent["p08"] == "p06"
    assert step.decisions["p03"].kind == "go" and step.views["p03"].food == 0
    donor = step.views["p06"]
    assert step.decisions["p06"].kind == "offer" and step.decisions["p06"].target == "p08"
    primary_children = frozenset(k for k, p in world.parent.items() if p == "p06")
    without_second_parent_role = replace(donor, children=primary_children,
                                        dependents=donor.dependents & primary_children)
    assert decide(without_second_parent_role, cfg).target != "p08"
    assert next(o for o in step.record.outcomes if o.actor == "p06").accepted
    assert (donor.food, step.committed.balances["p06"], step.committed.balances["p08"]) == (2, 1, 1)
    following = world_step(engine, world, cfg)
    assert following.decisions["p08"].kind == "eat"
    assert following.processed.overlay.hunger["p08"] < world.hunger["p08"]
