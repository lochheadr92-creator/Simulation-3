"""Birth recovery belongs to both adults and survives saved world state."""

from dataclasses import replace

import pytest

from kernel import WorldState
from world.config import WorldConfig
from world.overlay import Overlay
from world.process import _births, settled_pairs
from world.run import run_world
from stream.run_file import read_run
from world.replay import replay_world


def family(spacing=4):
    config = WorldConfig(seed=23, actors=3, water_on=False, warmth_on=False,
                         together_ticks=2, birth_spacing=spacing)
    positions = {"p01": (1, 1), "p02": (2, 1), "p03": (1, 2)}
    overlay = Overlay(tick=10, homes=positions, positions=positions,
                      hunger={p: 0 for p in positions}, yield_at={p: 1 for p in positions},
                      held={p: 0 for p in positions}, built={p: config.build_ticks for p in positions},
                      age={p: config.adult_at for p in positions}, shelters=tuple(positions.values()),
                      together={"p01|p02": 1, "p01|p03": 1})
    return config, overlay, WorldState.genesis(balances={p: 2 for p in positions})


def test_both_adults_recover_and_cannot_switch_partners_in_same_tick():
    config, before, ledger = family()
    after, grown, born = _births(before, ledger, config)
    assert born == ["p04"]
    assert after.birth_ready == {"p01": 14, "p02": 14, "p03": 0, "p04": 0}
    assert not after.together
    assert sum(grown.balances.values()) == sum(ledger.balances.values())
    assert grown.balances["p04"] == 0
    assert before.birth_ready == {}
    assert Overlay.from_canonical(after.canonical()).digest() == after.digest()
    with pytest.raises(TypeError):
        after.birth_ready["p01"] = 0


def test_recovery_boundary_then_a_fresh_together_countdown():
    config, before, ledger = family()
    after, ledger, _ = _births(before, ledger, config)
    assert settled_pairs(replace(after, tick=13), config) == []
    assert ("p01", "p02") in settled_pairs(replace(after, tick=14), config)
    at_boundary, ledger, born = _births(replace(after, tick=14), ledger, config)
    assert not born and at_boundary.together["p01|p02"] == 1
    again, _, born = _births(replace(at_boundary, tick=15), ledger, config)
    assert born == ["p05"] and again.birth_ready["p01"] == 19


def test_zero_spacing_preserves_multiple_births_and_old_state_shape():
    config, before, ledger = family(0)
    after, _, born = _births(before, ledger, config)
    assert born == ["p04", "p05"]
    assert "birth_ready" not in after.canonical()
    assert "birth_spacing" not in config.describe()
    assert WorldConfig.from_describe(config.describe()) == config


@pytest.mark.parametrize("spacing", [-1, True, 1.5, "30"])
def test_invalid_spacing_is_rejected(spacing):
    with pytest.raises(ValueError):
        WorldConfig(seed=7, birth_spacing=spacing)


def test_failed_birth_does_not_start_recovery(monkeypatch):
    config, before, ledger = family()
    monkeypatch.setattr("world.process.free_cell_near", lambda *args: None)
    after, _, born = _births(before, ledger, config)
    assert not born and not after.birth_ready


def test_spacing_run_is_deterministic_saved_and_replayable(tmp_path):
    config = WorldConfig(seed=23, birth_spacing=30)
    assert WorldConfig.from_describe(config.describe()) == config
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first, second = run_world(config, 100, a), run_world(config, 100, b)
    assert first.trail_digest == second.trail_digest
    run = read_run(a)
    assert run.complete
    assert any(t["world"].get("birth_ready") for t in run.ticks)
    result = replay_world(a)
    assert result.identical
