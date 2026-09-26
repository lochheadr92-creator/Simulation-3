"""Stage 2 first step: position, movement, one renewable source, hunger.

What is checked here is the part OD-009 keeps for every leg: seeded runs
reproduce byte for byte, the run file verifies and detects tampering with the
new blocks, the kernel is still the only place food moves, the world rules do
what their declarations say, and the viewer renders from the file alone.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from kernel import Engine, claim
from stream.run_file import RunFileError, RunWriter, apply_production, read_run
from world.config import FOOD_SOURCE, ONE_SOURCE_FOOD_ONLY, WorldConfig, genesis, homes_for
from world.decide import CLAIM, EAT, GO, HOME, REST, WAIT, candidates, decide, step_toward
from world.observe import Observation, observe
from world.overlay import Overlay
from world.process import advance
from world.run import run_world
from world.viewer import render_html, render_text

ROOT = Path(__file__).resolve().parent.parent


def small(**levers) -> WorldConfig:
    base = dict(seed=3, width=7, height=7, actors=4)
    base.update(levers)
    return WorldConfig(**base)


def obs(**fields) -> Observation:
    base = dict(actor="p01", tick=0, alive=True, position=(0, 0), home=(0, 0), hunger=0, food=0, source=(3, 3), source_food=4)
    base.update(fields)
    return Observation(**base)


# --- genesis and configuration -------------------------------------------------

def test_genesis_is_seeded_saved_and_identity_neutral():
    a, b = genesis(small()), genesis(small())
    assert a[0].digest() == b[0].digest() and a[1].digest() == b[1].digest()
    assert genesis(small(seed=4))[1].digest() != a[1].digest()
    homes = homes_for(small())
    assert len(set(homes.values())) == len(homes) and small().source_position not in homes.values()
    ledger, overlay = a
    assert overlay.positions == overlay.homes and all(h == 0 for h in overlay.hunger.values())
    assert set(overlay.yield_at) == set(overlay.homes) and all(v >= 1 for v in overlay.yield_at.values())
    assert ledger.sources[FOOD_SOURCE].authorised == frozenset(ledger.roster)


@pytest.mark.parametrize("bad", [dict(actors=49), dict(source_cap=1, source_stock=4), dict(death_at=5, emergency_at=10),
                                 dict(claim_amount=0), dict(renewal_every=0), dict(satiation=0),
                                 dict(perception_radius=-1), dict(yield_set=()), dict(yield_set=(0, 1))])
def test_configuration_rejects_incoherent_levers(bad):
    with pytest.raises(ValueError):
        small(**bad)


# --- decisions -----------------------------------------------------------------

def test_step_toward_moves_one_cell_along_the_longer_axis_x_on_ties():
    assert step_toward((0, 0), (3, 1)) == (1, 0)
    assert step_toward((0, 0), (1, 3)) == (0, 1)
    assert step_toward((0, 0), (2, 2)) == (1, 0)
    assert step_toward((5, 5), (2, 5)) == (4, 5)
    assert step_toward((2, 2), (2, 2)) == (2, 2)


def test_selection_rule_follows_the_declared_priority():
    cfg = small()
    d = decide(obs(hunger=cfg.hungry_at, food=2, position=(3, 3)), cfg)
    assert d.kind == EAT and d.amount == 1 and CLAIM in d.candidates
    d = decide(obs(hunger=cfg.hungry_at, food=0, position=(3, 3), source_food=1), cfg)
    assert d.kind == CLAIM and d.amount == 1                      # never asks for more than it saw
    d = decide(obs(hunger=cfg.emergency_at, food=0, position=(3, 3), source_food=0), cfg)
    assert d.kind == WAIT and d.reason.startswith("emergency")
    d = decide(obs(hunger=cfg.hungry_at, food=0, position=(0, 0)), cfg)
    assert d.kind == GO and d.step == (1, 0)
    # carrying food, so not due to leave for the source yet (tests/test_range.py covers leaving in time)
    d = decide(obs(hunger=cfg.hungry_at - 1, food=1, position=(1, 0), home=(0, 0)), cfg)
    assert d.kind == HOME and d.step == (0, 0)
    d = decide(obs(hunger=0, food=0), cfg)
    assert d.kind == REST and d.step is None
    assert candidates(obs(alive=False, hunger=99), cfg) == () and decide(obs(alive=False), cfg).kind == "dead"


# --- processes -----------------------------------------------------------------

def test_hunger_rises_every_tick_only_settled_eating_lowers_it_and_death_freezes():
    cfg = small(hunger_rate=2, satiation=6, death_at=8, emergency_at=7, hungry_at=3, starting_food=1,
                **ONE_SOURCE_FOOD_ONLY)   # one food total; water production would enter the sums
    ledger, overlay = genesis(cfg)
    engine = Engine(ledger)
    # nobody proposes: hunger rises by the rate for everyone
    processed = advance(overlay, {}, engine.tick([]), engine.state, cfg)
    assert all(h == 2 for h in processed.overlay.hunger.values()) and not processed.died
    # p01 eats one unit: hunger falls by satiation, floored at zero; the rest keep rising
    overlay = processed.overlay
    d = decide(obs(actor="p01", hunger=4, food=1, position=overlay.positions["p01"], home=overlay.homes["p01"]), cfg)
    assert d.kind == EAT
    from world.run import proposals_for
    record = engine.tick(proposals_for({"p01": d}, 1))
    assert record.outcomes[0].accepted
    processed = advance(overlay, {"p01": d}, record, engine.state, cfg)
    assert processed.overlay.hunger["p01"] == 0 and processed.overlay.hunger["p02"] == 4 and processed.eaten == {"p01": 1}
    # a rejected eat (no food) counts for nothing: hunger keeps rising
    overlay = processed.overlay
    record = engine.tick(proposals_for({"p01": d}, 2))
    assert not record.outcomes[0].accepted
    processed = advance(overlay, {"p01": d}, record, engine.state, cfg)
    assert processed.overlay.hunger["p01"] == 2 and processed.overlay.hunger["p02"] == 6
    # one more tick kills p02..p04 at death_at; their hunger and positions freeze and the ledger keeps their units
    overlay = processed.overlay
    processed = advance(overlay, {}, engine.tick([]), engine.state, cfg)
    assert set(processed.died) == {"p02", "p03", "p04"} and processed.overlay.hunger["p02"] == 8
    frozen = processed.overlay
    later = advance(frozen, {}, engine.tick([]), engine.state, cfg)
    assert later.overlay.hunger["p02"] == 8 and later.overlay.died_at["p02"] == 4 and later.overlay.living == ("p01",)
    assert engine.state.balances["p02"] == 1 and engine.state.total() == later.ledger.total() - sum(e["amount"] for e in later.production)


def test_renewal_is_the_only_production_and_respects_cap_and_cadence():
    cfg = small(source_stock=4, source_cap=5, renewal_every=2, renewal_amount=3,
                **ONE_SOURCE_FOOD_ONLY)   # one source; several are in test_sources.py
    ledger, overlay = genesis(cfg)
    engine = Engine(ledger)
    first = advance(overlay, {}, engine.tick([]), engine.state, cfg)      # tick 1: no renewal
    assert first.production == () and first.ledger.digest() == engine.state.digest()
    engine = Engine(first.ledger)
    second = advance(first.overlay, {}, engine.tick([]), engine.state, cfg)  # tick 2: capped to +1
    assert second.production == ({"source": FOOD_SOURCE, "amount": 1},)
    assert second.ledger.sources[FOOD_SOURCE].stock == 5 and second.ledger.total() == engine.state.total() + 1
    assert second.ledger.balances == engine.state.balances and second.ledger.tick == engine.state.tick
    engine = Engine(second.ledger)
    third = advance(second.overlay, {}, engine.tick([]), engine.state, cfg)
    engine = Engine(third.ledger)
    fourth = advance(third.overlay, {}, engine.tick([]), engine.state, cfg)
    assert third.production == () and fourth.production == ()                # at cap: nothing produced


def test_movement_takes_one_cell_per_tick_and_contention_is_settled_by_the_kernel(tmp_path: Path):
    cfg = small(seed=11, starting_food=0, source_stock=1, renewal_amount=0, hungry_at=0, death_at=60, emergency_at=30,
                **ONE_SOURCE_FOOD_ONLY)   # one unit at one source: exactly one claim can win
    run_world(cfg, 12, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete
    previous = run.header["world"]["positions"]
    for tick in run.ticks:
        for actor, pos in tick["world"]["positions"].items():
            assert abs(pos[0] - previous[actor][0]) + abs(pos[1] - previous[actor][1]) <= 1
        previous = tick["world"]["positions"]
    accepted = [o for t in run.ticks for o in t["record"]["outcomes"] if o["operation"] == "claim" and o["accepted"]]
    denied = [o for t in run.ticks for o in t["record"]["outcomes"] if o["operation"] == "claim" and not o["accepted"]]
    assert len(accepted) == 1 and all(o["reason"] == "denied_insufficient_source" for o in denied)
    assert run.ticks[-1]["state"]["sources"][FOOD_SOURCE]["stock"] == 0
    # once the source is empty, a hungry person standing on it waits rather than claiming, and hunger keeps rising
    waited = [(a, d) for t in run.ticks for a, d in t["decisions"].items() if d["kind"] == "wait"]
    assert waited and all(d["reason"].endswith("source empty") for _, d in waited)
    assert all(h > 0 for h in run.ticks[-1]["world"]["hunger"].values())


# --- run files -----------------------------------------------------------------

def test_two_runs_of_one_seed_are_byte_identical_apart_from_timing(tmp_path: Path):
    cfg = small()
    a = run_world(cfg, 80, tmp_path / "a.jsonl")
    b = run_world(cfg, 80, tmp_path / "b.jsonl")
    assert a.trail_digest == b.trail_digest and a.final_overlay_digest == b.final_overlay_digest
    strip = lambda p: [l for l in p.read_bytes().splitlines() if b'"kind":"timing"' not in l]
    assert strip(tmp_path / "a.jsonl") == strip(tmp_path / "b.jsonl")
    assert run_world(small(seed=5), 80, tmp_path / "c.jsonl").trail_digest != a.trail_digest


def test_world_run_file_verifies_and_chains_through_production(tmp_path: Path):
    cfg = small(renewal_every=1, renewal_amount=1, source_cap=9)
    run_world(cfg, 30, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete and run.has_world and run.header["world_digest"]
    produced = [t for t in run.ticks if "production" in t]
    assert produced, "a renewal every tick must show up"
    for earlier, later in zip(run.ticks, run.ticks[1:]):
        expected = earlier["produced_state_digest"] if "production" in earlier else earlier["state_digest"]
        assert later["record"]["prior_state_digest"] == expected
    # every decision belongs to a person who was alive when the tick started
    living_before = set(run.header["world"]["positions"]) - set(run.header["world"]["died_at"])
    for tick in run.ticks:
        assert set(tick["decisions"]) == living_before
        living_before = set(tick["world"]["positions"]) - set(tick["world"]["died_at"])


def test_writer_refuses_production_that_did_not_happen(tmp_path: Path):
    cfg = small()
    ledger, overlay = genesis(cfg)
    engine = Engine(ledger)
    record = engine.tick([])
    writer = RunWriter(tmp_path / "w.jsonl", run_id="x", genesis=ledger, scenario=cfg.describe(),
                       world=overlay.canonical(), horizon=1)
    with pytest.raises(RunFileError):
        writer.record(record, engine.state, inputs=[], production=[{"source": FOOD_SOURCE, "amount": 1}],
                      produced_state=engine.state)
    with pytest.raises(RunFileError):
        writer.record(record, engine.state, inputs=[], production=[{"source": FOOD_SOURCE, "amount": 1}])
    writer.record(record, engine.state, inputs=[])
    writer.close()
    with pytest.raises(RunFileError):
        apply_production(engine.state.canonical(), [{"source": "nowhere", "amount": 1}])
    with pytest.raises(RunFileError):
        apply_production(engine.state.canonical(), [{"source": FOOD_SOURCE, "amount": 0}])


@pytest.mark.parametrize("damage", ["world", "production", "produced_digest", "decision"])
def test_tampering_with_world_blocks_does_not_verify(tmp_path: Path, damage: str):
    cfg = small(renewal_every=1, renewal_amount=1, source_cap=9)
    run_world(cfg, 10, tmp_path / "w.jsonl")
    lines = (tmp_path / "w.jsonl").read_bytes().splitlines(keepends=True)
    index = next(i for i, l in enumerate(lines) if b'"kind":"tick"' in l and b'"production"' in l)
    tick = json.loads(lines[index])
    if damage == "world":
        actor = sorted(tick["world"]["hunger"])[0]
        tick["world"]["hunger"][actor] += 1
    elif damage == "production":
        tick["production"][0]["amount"] += 1
    elif damage == "produced_digest":
        tick["produced_state_digest"] = "0" * 64
    else:
        actor = sorted(tick["decisions"])[0]
        tick["decisions"][actor]["kind"] = "eat"
    from kernel import canonical_bytes
    lines[index] = canonical_bytes(tick) + b"\n"
    (tmp_path / "w.jsonl").write_bytes(b"".join(lines))
    run = read_run(tmp_path / "w.jsonl")
    assert not run.complete and any("trail" in p for p in run.problems)
    if damage == "world":
        assert any("world digest" in p for p in run.problems)
    if damage in {"production", "produced_digest"}:
        assert any("production rule" in p for p in run.problems)


# --- ownership -----------------------------------------------------------------

def test_world_is_downstream_of_the_kernel_and_the_kernel_knows_nothing_of_it():
    def imports(module: Path) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
        return names
    for module in (ROOT / "kernel").glob("*.py"):
        assert not imports(module) & {"world", "stream"}, module.name
    for module in (ROOT / "stream").glob("*.py"):
        assert "world" not in imports(module), module.name
    for module in (ROOT / "world").glob("*.py"):
        assert not imports(module) & {"automation", "tests"}, module.name
    # only run.py talks to the engine and the run file; observe/decide/process are pure rules
    for name in ("observe", "decide", "process", "overlay", "config"):
        assert "stream" not in imports(ROOT / "world" / f"{name}.py"), name
    observe_tree = ast.parse((ROOT / "world" / "observe.py").read_text(encoding="utf-8"))
    observe_modules = {
        node.module for node in ast.walk(observe_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(observe_tree) if isinstance(node, ast.Import) for alias in node.names
    }
    assert "stream" not in {name.split(".")[0] for name in observe_modules}
    assert "world.run" not in observe_modules and "run" not in observe_modules


def test_food_only_moves_through_the_kernel(tmp_path: Path):
    """Every change in a person's balance or the source stock between two
    stored states is explained by accepted kernel effects or recorded production."""
    cfg = small(renewal_every=2)
    run_world(cfg, 60, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    before = run.header["genesis"]
    for tick in run.ticks:
        delta: dict[str, int] = {}
        for o in tick["record"]["outcomes"]:
            if o["accepted"]:
                for e in o["effects"]:
                    delta[e["account"]] = delta.get(e["account"], 0) + e["delta"]
        after = tick["state"]
        for actor in after["balances"]:
            assert after["balances"][actor] - before["balances"][actor] == delta.get(f"actor:{actor}", 0)
        assert after["sources"][FOOD_SOURCE]["stock"] - before["sources"][FOOD_SOURCE]["stock"] == delta.get(f"source:{FOOD_SOURCE}", 0)
        before = apply_production(after, tick.get("production", []))


# --- viewer --------------------------------------------------------------------

def test_viewer_renders_from_the_file_with_no_external_resources(tmp_path: Path):
    cfg = small()
    run_world(cfg, 25, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    page = render_html(run)
    assert "file verifies" in page and 'id="run-data"' in page
    assert not re.search(r'(src|href)\s*=\s*["\']?(https?:)?//', page)
    assert "<script src" not in page and "@import" not in page and "<link" not in page
    embedded = json.loads(re.search(r'<script id="run-data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert len(embedded["ticks"]) == 25 and embedded["header"]["world"] == run.header["world"]
    text = render_text(run, 25)
    assert "source S at" in text
    assert "view 25/25" in text
    with pytest.raises(ValueError):
        render_text(run, 26)
