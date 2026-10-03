"""Patch condition follows settled harvests, and every new unit is recorded."""

import json
from dataclasses import replace

import pytest

from kernel import Engine, claim, consume
from stream.run_file import apply_production, read_run
from world.config import WorldConfig, genesis
from world.ecology import food_growth, recover_patches
from world.overlay import Overlay
from world.process import _births, advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world
from world.viewer import render_html
from world.viewer_index import build_index


def patches(**changes):
    cfg = WorldConfig(seed=7, actors=3, source_stock=8, source_cap=8, regrowth_on=True,
                      terrain_on=False, births_on=False, **changes)
    ledger, overlay = genesis(cfg)
    return cfg, ledger, overlay


def test_only_actual_harvest_wears_each_patch_once():
    cfg, ledger, overlay = patches()
    engine = Engine(ledger)
    record = engine.tick([
        claim("first", "p01", 0, sources={"food": 3}),
        claim("second", "p02", 0, sources={"food": 3}),
        claim("failed", "p03", 0, sources={"food2": 100}),
    ])
    assert sum(o.accepted for o in record.outcomes) == 2
    before = {"food": 100, "food2": 55}
    assert recover_patches(before, cfg.food_source_ids(), record) == {"food": 40, "food2": 56}
    assert before == {"food": 100, "food2": 55}
    assert overlay.patch_condition == {"food": 100, "food2": 100}


def test_water_claim_and_eating_do_not_wear_food_patches():
    cfg, ledger, _ = patches()
    engine = Engine(ledger)
    record = engine.tick([claim("water", "p01", 0, sources={"water": 2}, resource="water"),
                          consume("eat", "p02", 0, amount=1)])
    assert all(o.accepted for o in record.outcomes)
    assert recover_patches({"food": 20, "food2": 99}, cfg.food_source_ids(), record) == {
        "food": 21, "food2": 100}


@pytest.mark.parametrize("condition,normal,expected", [(49, 2, 1), (50, 2, 2), (0, 3, 2),
                                                       (0, 1, 1), (0, 0, 0), (100, 0, 0)])
def test_growth_boundary_and_rounding(condition, normal, expected):
    assert food_growth(normal, condition) == expected


def test_harvest_happens_before_same_tick_growth_and_water_is_unchanged():
    cfg, ledger, overlay = patches()
    engine = Engine(replace(ledger, tick=14))
    overlay = replace(overlay, tick=14, patch_condition={"food": 100, "food2": 49})
    record = engine.tick([claim("a", "p01", 0, sources={"food": 3}),
                          claim("b", "p02", 0, sources={"food": 3})])
    committed = engine.state
    result = advance(overlay, {}, record, committed, cfg)
    assert result.overlay.patch_condition == {"food": 40, "food2": 50}
    assert result.ledger.sources["food"].stock == 3  # 8 - 6 harvested + 1 grown
    assert result.ledger.sources["food2"].stock == 8  # full: no production
    assert result.production == ({"source": "food", "amount": 1},
                                 {"source": "water", "amount": 3},
                                 {"source": "water2", "amount": 3})
    assert apply_production(committed.canonical(), list(result.production)) == result.ledger.canonical()
    assert committed.sources["food"].stock == 2
    assert result.ledger.totals()[None] == committed.totals()[None] + 1
    assert result.ledger.totals()["water"] == committed.totals()["water"] + 6


def test_quiet_ticks_recover_but_do_not_produce_early_and_condition_is_bounded():
    cfg, ledger, overlay = patches()
    engine = Engine(ledger)
    overlay = replace(overlay, patch_condition={"food": 0, "food2": 100})
    result = advance(overlay, {}, engine.tick([]), engine.state, cfg)
    assert result.overlay.patch_condition == {"food": 1, "food2": 100}
    assert not result.production
    record = Engine(ledger).tick([claim("large", "p01", 0, sources={"food": 8})])
    assert recover_patches({"food": 1, "food2": 100}, cfg.food_source_ids(), record)["food"] == 0


@pytest.mark.parametrize("bad", [{"food": -1}, {"food": 101}, {"food": True}, {"food": 1.5}, {"": 1}, []])
def test_bad_condition_is_rejected(bad):
    _, _, overlay = patches()
    with pytest.raises(ValueError):
        replace(overlay, patch_condition=bad)


def test_condition_is_immutable_and_old_overlay_shape_survives():
    _, _, overlay = patches()
    assert Overlay.from_canonical(overlay.canonical()).digest() == overlay.digest()
    with pytest.raises(TypeError):
        overlay.patch_condition["food"] = 0
    old = replace(overlay, patch_condition={})
    assert "patch_condition" not in old.canonical()
    assert not Overlay.from_canonical(old.canonical()).patch_condition


def test_switch_and_saved_rules_round_trip_without_changing_defaults():
    parser = build_parser()
    old = config_from(parser.parse_args(["--seed", "7"]))
    new = config_from(parser.parse_args(["--seed", "7", "--regrowth", "on"]))
    assert not old.regrowth_on and new.regrowth_on
    assert "regrowth" not in old.describe()
    assert WorldConfig.from_describe(new.describe()) == new
    assert WorldConfig.from_describe(old.describe()) == old
    assert run_id_for(new, 400) != run_id_for(old, 400)
    with pytest.raises(ValueError):
        WorldConfig(seed=7, regrowth_on=1)
    bad = new.describe()
    bad["patch_rules"]["wear_per_unit"] = 1
    with pytest.raises(ValueError):
        WorldConfig.from_describe(bad)


def test_birth_preserves_both_patch_conditions():
    cfg = WorldConfig(seed=7, actors=2, regrowth_on=True, together_ticks=1,
                      water_on=False, warmth_on=False, terrain_on=False)
    ledger, overlay = genesis(cfg)
    positions = {"p01": (0, 0), "p02": (1, 0)}
    overlay = replace(overlay, homes=positions, positions=positions,
                      shelters=tuple(positions.values()), hunger={p: 0 for p in positions},
                      held={p: 0 for p in positions}, built={p: cfg.build_ticks for p in positions},
                      patch_condition={"food": 12, "food2": 90})
    after, _, born = _births(overlay, ledger, cfg)
    assert born and after.patch_condition == overlay.patch_condition
    assert Overlay.from_canonical(after.canonical()).digest() == after.digest()


@pytest.mark.long_run
def test_saved_run_replays_recovers_and_viewer_uses_recorded_condition(tmp_path):
    path = tmp_path / "patches.jsonl"
    cfg = WorldConfig(seed=7, regrowth_on=True)
    result = run_world(cfg, 400, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    assert run.ticks[40]["world"]["patch_condition"]["food"] == 48
    events = build_index(run)["events"]
    assert any(e["kind"] == "patch_worn" and e["k"] == 41 for e in events)
    assert any(e["kind"] == "patch_recovered" and e["k"] == 43 for e in events)
    page = render_html(run)
    assert "Patch condition" in page and "worn patch" in page
    assert "half when worn, rounded up" in page
    lines = path.read_bytes().splitlines(keepends=True)
    cut_at = next(i for i, raw in enumerate(lines) if json.loads(raw).get("kind") == "tick"
                  and json.loads(raw).get("tick") == 44)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:cut_at + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
    assert replay_world(restored).identical
    assert run_world(cfg, 400, tmp_path / "again.jsonl").trail_digest == result.trail_digest
