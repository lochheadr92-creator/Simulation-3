"""Seasons change recorded food production, not accounting or people's knowledge."""

import json
from dataclasses import replace

import pytest

from kernel import Engine, claim
from stream.run_file import apply_production, read_run
from world.config import WorldConfig, genesis
from world.ecology import season_at, seasonal_growth
from world.overlay import Overlay
from world.process import _births, advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world
from world.viewer import render_html
from world.viewer_index import build_index


@pytest.mark.parametrize("tick,expected", [(0, "plentiful"), (119, "plentiful"),
    (120, "lean"), (239, "lean"), (240, "plentiful"), (360, "lean"), (480, "plentiful")])
def test_season_boundaries(tick, expected):
    assert season_at(tick) == expected


@pytest.mark.parametrize("normal,rich,lean", [(0, 0, 0), (1, 2, 0), (2, 3, 1), (3, 5, 1), (4, 6, 2)])
def test_season_rounding(normal, rich, lean):
    assert seasonal_growth(normal, "plentiful") == rich
    assert seasonal_growth(normal, "lean") == lean


@pytest.mark.parametrize("completed,regrowth,expected", [(105, True, 3), (120, True, 1),
    (240, True, 3), (105, False, 5), (120, False, 1), (240, False, 5)])
def test_boundary_renewal_after_harvest_and_wear(completed, regrowth, expected):
    cfg = WorldConfig(seed=7, actors=2, seasons_on=True, regrowth_on=regrowth,
                      source_stock=8, source_cap=16, renewal_amount=3, births_on=False)
    ledger, overlay = genesis(cfg)
    engine = Engine(replace(ledger, tick=completed - 1))
    overlay = replace(overlay, tick=completed - 1, season=season_at(completed - 1))
    record = engine.tick([claim("a", "p01", 0, sources={"food": 3}),
                          claim("b", "p02", 0, sources={"food": 3})])
    result = advance(overlay, {}, record, engine.state, cfg)
    assert result.overlay.season == season_at(completed)
    assert result.ledger.sources["food"].stock == 2 + expected
    assert result.ledger.sources["food2"].stock == 8 + (5 if completed != 120 else 1)
    assert result.ledger.sources["water"].stock == engine.state.sources["water"].stock + 3
    assert apply_production(engine.state.canonical(), list(result.production)) == result.ledger.canonical()
    assert engine.state.sources["food"].stock == 2
    assert overlay.season == season_at(completed - 1)


def test_caps_zero_growth_and_nonrenewal_ticks():
    for amount, tick, stock in [(3, 105, 16), (0, 105, 15), (3, 106, 15)]:
        cfg = WorldConfig(seed=7, seasons_on=True, source_stock=15, source_cap=16,
                          renewal_amount=amount, births_on=False)
        ledger, overlay = genesis(cfg)
        engine = Engine(replace(ledger, tick=tick - 1))
        overlay = replace(overlay, tick=tick - 1)
        record = engine.tick([])
        result = advance(overlay, {}, record, engine.state, cfg)
        assert result.ledger.sources["food"].stock == stock


def test_birth_keeps_the_world_season():
    cfg = WorldConfig(seed=7, actors=2, seasons_on=True, together_ticks=1,
                      water_on=False, warmth_on=False, terrain_on=False)
    ledger, overlay = genesis(cfg)
    positions = {"p01": (0, 0), "p02": (1, 0)}
    overlay = replace(overlay, season="lean", homes=positions, positions=positions,
                      shelters=tuple(positions.values()), hunger={p: 0 for p in positions},
                      held={p: 0 for p in positions}, built={p: cfg.build_ticks for p in positions})
    result, _, born = _births(overlay, ledger, cfg)
    assert born and result.season == "lean"
    assert Overlay.from_canonical(result.canonical()).digest() == result.digest()


def test_config_cli_and_old_state_compatibility():
    parser = build_parser()
    old = config_from(parser.parse_args(["--seed", "7"]))
    cfg = config_from(parser.parse_args(["--seed", "7", "--seasons", "on"]))
    assert not old.seasons_on and cfg.seasons_on
    assert "seasons" not in old.describe()
    assert WorldConfig.from_describe(old.describe()) == old
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    assert run_id_for(old, 250) != run_id_for(cfg, 250)
    _, overlay = genesis(old)
    assert "season" not in overlay.canonical()
    assert Overlay.from_canonical(overlay.canonical()).season is None
    for bad in (1, "winter", {}, []):
        with pytest.raises(ValueError):
            replace(overlay, season=bad)
    with pytest.raises(ValueError):
        replace(cfg, seasons_on=1)
    for key, value in (("season_ticks", 1), ("season_growth", {}), ("seasons", True)):
        described = cfg.describe()
        described[key] = value
        with pytest.raises(ValueError):
            WorldConfig.from_describe(described)


def test_saved_seasons_replay_recover_and_supply_viewer_events(tmp_path):
    cfg = WorldConfig(seed=7, seasons_on=True, regrowth_on=True,
                      source_stock=8, source_cap=16, renewal_amount=3)
    path = tmp_path / "seasons.jsonl"
    result = run_world(cfg, 250, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    events = [e for e in build_index(run)["events"] if e["kind"] == "season_changed"]
    assert [(e["k"], e["text"]) for e in events] == [
        (120, "The lean season begins"), (240, "The plentiful season begins")]
    assert run.header["world"]["season"] == "plentiful"
    assert all(t["world"]["season"] == season_at(k) for k, t in enumerate(run.ticks, 1))
    assert "season" not in run.ticks[0]["observations"]["p01"]
    page = render_html(run)
    assert "season_changed" in page and "Seasons change every" in page
    lines = path.read_bytes().splitlines(keepends=True)
    cut_at = next(i for i, raw in enumerate(lines) if json.loads(raw).get("kind") == "tick"
                  and json.loads(raw).get("tick") == 118)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:cut_at + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
    assert replay_world(restored).identical
    assert run_world(cfg, 250, tmp_path / "repeat.jsonl").trail_digest == result.trail_digest
