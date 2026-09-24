"""Leg 6 instrument checks: bounded synthetic fixtures, not exploration runs."""

from dataclasses import replace
from itertools import permutations
import importlib
import json
import re
import runpy
from pathlib import Path

import pytest

from kernel import Engine, Source, WorldState, canonical_bytes, claim
from stream.run_file import read_run
from world.config import FOOD_SOURCE, WorldConfig
from world.decide import action_score, candidates, crowd_on_source, decide
from world.observe import Observation, SeenPerson, observe
from world.overlay import Overlay
from world.process import advance
from world.run import build_parser, config_from, proposals_for, run_id_for, run_world
from world.viewer import render_html, render_text


def config(**changes):
    return replace(WorldConfig(seed=7, width=7, height=7, actors=4, scoring_on=True), **changes)


def observation(**changes):
    return replace(Observation(
        actor="p01", tick=0, alive=True, position=(2, 3), home=(0, 0),
        hunger=5, food=0, source=(3, 3), source_food=0, yield_at=2,
        others=tuple(SeenPerson(f"p{i:02d}", (3, 3), 0) for i in (2, 3, 4)),
    ), **changes)


@pytest.mark.parametrize("hungry_at", [0, 2, 5, 11])
def test_boundary_and_direct_parity_across_eligible_domain(hungry_at):
    # Exhaust every simultaneous GO/YIELD input in a six-person configuration:
    # all non-emergency hunger, possible seen crowd, trait, and low source stock.
    cfg = config(actors=6, hungry_at=hungry_at, emergency_at=hungry_at + 5, death_at=hungry_at + 11)
    boundaries = 0
    for crowd in range(1, cfg.actors):
        others = tuple(SeenPerson(f"p{i:02d}", (3, 3), 0) for i in range(2, crowd + 2))
        for trait in cfg.yield_set:
            for stock in range(crowd):
                for hunger in range(cfg.hungry_at, cfg.emergency_at):
                    ob = observation(others=others, yield_at=trait, source_food=stock, hunger=hunger)
                    if "yield" not in candidates(ob, cfg):
                        continue
                    go, yielding = action_score("go", ob, cfg), action_score("yield", ob, cfg)
                    assert go[0] == yielding[0] == 0
                    assert go[1] % 2 == 1 and yielding[1] % 2 == 0
                    assert go != yielding
                    boundary = hungry_at + crowd - trait + 1
                    assert (go > yielding) == (hunger >= boundary)
                    assert decide(ob, cfg).kind == ("go" if hunger >= boundary else "yield")
                    if hunger in (boundary - 1, boundary):
                        boundaries += 1
                        assert go[1] == yielding[1] + (1 if hunger == boundary else -1)
    assert boundaries > 0


def test_eat_priority_emergency_and_all_other_pairs():
    cfg = config()
    for hunger in (5, 7, 9, 10, 15):
        d = decide(observation(hunger=hunger, food=1), cfg)
        assert d.kind == "eat" and dict(d.scores)["eat"] == (2, 0)
        assert ("yield" in d.candidates) == (hunger < cfg.emergency_at)
    d = decide(observation(hunger=10), cfg)
    assert d.kind == "go" and "yield" not in d.candidates
    for stock, kind in ((0, "wait"), (1, "claim")):
        d = decide(observation(position=(3, 3), source_food=stock), cfg)
        assert d.kind == kind and d.canonical()["scores"] == {kind: [1, 0]}
    for position, kind in (((0, 0), "rest"), ((2, 3), "home")):
        d = decide(observation(hunger=0, position=position), cfg)
        assert d.kind == kind and d.canonical()["scores"] == {kind: [0, 0]}
    assert candidates(observation(alive=False), cfg) == ()


def test_candidate_order_cannot_change_selection_or_native_score_block(monkeypatch):
    module = importlib.import_module("world.decide")
    for ob in (observation(), observation(hunger=7), observation(food=1)):
        monkeypatch.setattr(module, "candidates", candidates)
        options = candidates(ob, config())
        expected = decide(ob, config()).canonical()
        for order in permutations(options):
            monkeypatch.setattr(module, "candidates", lambda *_args, order=order: order)
            assert decide(ob, config()).canonical() == expected


def test_off_keeps_exact_leg5_shape_values_and_default_cli():
    ob = observation(hunger=7)
    assert decide(ob, config(scoring_on=False)).canonical() == {
        "kind": "yield", "reason": "hungry, saw 3 on source, stock 0, yield_at 2",
        "candidates": ["yield", "go"],
    }
    parser = build_parser()
    default = config_from(parser.parse_args(["--seed", "7"]))
    explicit = config_from(parser.parse_args(["--seed", "7", "--scoring", "off"]))
    on = config_from(parser.parse_args(["--seed", "7", "--scoring", "on"]))
    assert default == explicit and not default.scoring_on and on.scoring_on
    assert run_id_for(default, 300) == "one-source-grid-seed7-ticks300-yieldon"
    assert run_id_for(on, 300).endswith("-scoringon")


def synthetic_genesis(cfg):
    positions = {"p01": (2, 3), "p02": (3, 3), "p03": (3, 3), "p04": (3, 3)}
    ledger = WorldState.genesis(
        balances={actor: 0 for actor in positions},
        sources={FOOD_SOURCE: Source(1, frozenset(positions))},
    )
    overlay = Overlay(tick=0, homes=positions, positions=positions,
                      hunger={actor: 5 for actor in positions},
                      yield_at={actor: 2 for actor in positions}, died_at={"p04": 0})
    return ledger, overlay


@pytest.fixture
def native_run(tmp_path, monkeypatch):
    # Two synthetic ticks: a YIELD then GO choice and a contested one-unit claim.
    # Capture what the live selector returns, before writing, for native equality.
    module = importlib.import_module("world.run")
    captured = []

    def capture(ob, cfg):
        result = decide(ob, cfg)
        captured.append((ob.tick, ob.actor, result.canonical()))
        return result

    monkeypatch.setattr(module, "genesis", synthetic_genesis)
    monkeypatch.setattr(module, "decide", capture)
    path = tmp_path / "synthetic-two-ticks.jsonl"
    run_world(config(source_stock=1, renewal_amount=0), 2, path)
    return read_run(path), captured


def test_bounded_observations_and_dead_never_seen_counted_or_submitted(native_run):
    run, captured = native_run
    assert run.complete
    for tick in run.ticks:
        assert "p04" not in tick["decisions"] and "p04" not in tick["observations"]
        assert all(o["actor"] != "p04" for o in tick["record"]["outcomes"])
        assert all("p04" not in ob["sees"] for ob in tick["observations"].values())
    assert run.ticks[0]["decisions"]["p01"]["scores"]["yield"] == [0, 2]
    cfg = config(perception_radius=1)
    ledger, overlay = synthetic_genesis(cfg)
    overlay = replace(overlay, positions={**overlay.positions, "p01": (0, 0)})
    a = observe("p01", ledger, overlay, cfg)
    changed_ledger = replace(ledger, sources={FOOD_SOURCE: Source(8, frozenset(ledger.roster))})
    changed_overlay = replace(overlay, hunger={**overlay.hunger, "p02": 15},
                              positions={**overlay.positions, "p02": (6, 6)})
    b = observe("p01", changed_ledger, changed_overlay, cfg)
    assert a == b and a.source_food is None and crowd_on_source(a) == 0
    assert decide(a, cfg).canonical() == decide(b, cfg).canonical()
    assert "yield" not in decide(a, cfg).candidates


def test_native_pairs_equal_selection_time_and_header_declares_model(native_run):
    run, captured = native_run
    for tick, actor, actual in captured:
        assert run.ticks[tick]["decisions"][actor] == actual
        assert set(actual["scores"]) == set(actual["candidates"])
    first, second = (t["decisions"]["p01"] for t in run.ticks)
    assert first["scores"] == {"go": [0, 1], "yield": [0, 2]} and first["kind"] == "yield"
    assert second["scores"] == {"go": [0, 3], "yield": [0, 2]} and second["kind"] == "go"
    header = run.header["scenario"]
    assert header["scoring"] == "on" and set(header["scoring_formula"]) == {"eat", "claim", "wait", "go", "yield", "home", "rest"}
    assert "hungry_at + seen_crowd - yield_at + 1" in header["scoring_crossover"]
    assert "seen_crowd - yield_at + 6" in header["scoring_crossover_configured"]
    assert "modelling assumption" in header["scoring_scale"]


def test_saved_file_comparison_counts_known_fixture_boundaries(native_run):
    run, _ = native_run
    compare = runpy.run_path(str(Path(__file__).resolve().parents[1] / "evidence/stage-01/leg6_compare.py"))
    measured = compare["counts"](run)
    assert measured["survivors"] == ["p01", "p02", "p03"]
    assert measured["deaths"] == {"p04": 0} and measured["denied_claims"] == 1
    assert measured["emergency_person_ticks"] == 0 and measured["yield_events"] == 1
    assert measured["go_over_yield"] == 1 and len(measured["contested"]) == 1
    assert measured["fatal_accepted_claims"] == []
    # Count initial emergency, exclude a dead actor and the final post-tick view.
    run.header["world"]["hunger"]["p01"] = 10
    run.header["world"]["hunger"]["p04"] = 16
    run.ticks[-1]["world"]["hunger"]["p01"] = 10
    assert compare["counts"](run)["emergency_person_ticks"] == 1


def test_score_block_tampering_is_detected(native_run, tmp_path):
    run, _ = native_run
    lines = run.path.read_bytes().splitlines()
    index = next(i for i, line in enumerate(lines) if json.loads(line)["kind"] == "tick")
    tick = json.loads(lines[index])
    tick["decisions"]["p01"]["scores"]["go"][1] += 2
    lines[index] = canonical_bytes(tick)
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_bytes(b"\n".join(lines) + b"\n")
    checked = read_run(tampered)
    assert not checked.complete and any("trail" in p for p in checked.problems)


@pytest.mark.parametrize("reverse", [False, True])
def test_kernel_rotation_includes_inactive_actors_and_ignores_personal_hunger(reverse):
    cfg = config()
    ledger, overlay = synthetic_genesis(cfg)
    ledger = replace(ledger, tick=1)
    overlay = replace(overlay, tick=1, died_at={"p01": 0, "p04": 0},
                      hunger={**overlay.hunger, "p03": 15})
    decisions = {actor: decide(observe(actor, ledger, overlay, cfg), cfg) for actor in overlay.living}
    proposals = proposals_for(decisions, 1)
    engine = Engine(ledger)
    record = engine.tick(reversed(proposals) if reverse else proposals)
    assert record.rotated_roster == ("p02", "p03", "p04", "p01")
    # A living-only or claimant-only tick-1 rotation would put p03 first.
    assert [(o.actor, o.accepted) for o in record.outcomes] == [("p02", True), ("p03", False)]
    assert engine.state.balances["p02"] == 1 and engine.state.balances["p03"] == 0
    assert record.outcomes[1].effects == () and engine.state.total() == ledger.total()


def test_atomic_claim_rejects_whole_request_and_preserves_stock_for_next_actor():
    ledger = WorldState.genesis(balances={"a": 0, "b": 0}, sources={
        "food": Source(1, frozenset({"a", "b"})), "other": Source(0, frozenset({"a"})),
    })
    engine = Engine(ledger)
    record = engine.tick([claim("a", "a", 0, sources={"food": 1, "other": 1}),
                          claim("b", "b", 0, sources={"food": 1})])
    assert not record.outcomes[0].accepted and record.outcomes[0].effects == ()
    assert record.outcomes[1].accepted and engine.state.balances == {"a": 0, "b": 1}
    assert engine.state.total() == ledger.total()


def test_claim_then_eat_latency_is_unchanged_at_death_boundary():
    cfg = config()
    ledger, overlay = synthetic_genesis(cfg)
    overlay = replace(overlay, hunger={**overlay.hunger, "p02": 15})
    d = decide(observe("p02", ledger, overlay, cfg), cfg)
    engine = Engine(ledger)
    record = engine.tick(proposals_for({"p02": d}, 0))
    processed = advance(overlay, {"p02": d}, record, engine.state, cfg)
    assert d.kind == "claim" and record.outcomes[0].accepted
    assert processed.overlay.died_at["p02"] == 1 and processed.ledger.balances["p02"] == 1
    assert processed.ledger.consumed == 0


def test_viewer_shows_saved_scores_selected_action_requests_rotation_and_effects(native_run, monkeypatch):
    run, _ = native_run
    # Any viewer dependence on the live selector or scorer is a failure.
    module = importlib.import_module("world.decide")
    def forbidden(*_args):
        raise AssertionError("viewer attempted live scoring")
    monkeypatch.setattr(module, "action_score", forbidden)
    monkeypatch.setattr(module, "decide", forbidden)
    page = render_html(run)
    payload = json.loads(re.search(r'<script id="run-data" type="application/json">(.*?)</script>', page, re.S)[1])
    assert payload["checkpoints"] == {"scored": [1, 2], "crossover": [2], "contested": [1]}
    assert "Next GO/YIELD scored choice" in page and "Next contested food claim" in page
    for view in (1, 2):
        text = render_text(run, view)
        assert payload["details"][view]["selection"] in text
        assert payload["details"][view]["settlement"] in text
    text = render_text(run, 1)
    assert "eligible: go (0, 1); yield (0, 2); selected yield" in text
    assert "Recorded rotation: p01 -> p02 -> p03 -> p04" in text
    assert "Food claim request: p03, 1 from food" in text
    assert "p02 claim accepted" in text and "p03 claim denied" in text
    assert "actor:p02 +1" in text and "source:food -1" in text and "effects: none" in text
    assert "tick-start at (2, 3), hunger 5" in text
    assert "go (0, 3); yield (0, 2); selected go" in render_text(run, 2)
