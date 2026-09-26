"""Several sources of a kind (2026-09-26): two food sources and, with water
on, two water sources by default.

A person heads for the nearest source (steps, then id) they can see with free
stock; if none in view has stock, the nearest. A source out of view never
attracts anyone, so nobody walks back and forth at the edge of their sight.
Claims and draws take from that source, and the decision records it as its
target. With one source of each kind nothing changes: the one-source world
writes exactly what it wrote before (the b305783 fixtures pin its decisions).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import Engine, Source, WorldState
from stream.run_file import apply_production, read_run
from world.config import FOOD_SOURCE, ONE_SOURCE_FOOD_ONLY, WATER, WATER_SOURCE, WorldConfig, genesis
from world.decide import CLAIM, GO, GO_WATER, WAIT, WAIT_WATER, decide
from world.observe import chebyshev, observe, target_source
from world.overlay import Overlay
from world.process import advance
from world.replay import replay_world
from world.run import build_parser, config_from, proposals_for, run_world
from world.viewer import render_html, render_text


def test_the_default_world_has_two_food_and_two_water_sources():
    cfg = WorldConfig(seed=7)
    assert cfg.food_source_ids() == ("food", "food2") and cfg.water_source_ids() == ("water", "water2")
    assert cfg.food_positions() == ((6, 6), (9, 3)) and cfg.water_positions() == ((3, 3), (3, 9))
    ledger, overlay = genesis(cfg)
    assert {sid: s.stock for sid, s in ledger.sources.items()} == {"food": 4, "food2": 4, "water": 6, "water2": 6}
    assert {sid: s.resource for sid, s in ledger.sources.items()} == {
        "food": None, "food2": None, "water": WATER, "water2": WATER}
    assert not set(overlay.homes.values()) & set(cfg.all_source_positions())
    described = cfg.describe()
    assert described["food_sources"] == [{"id": "food", "position": [6, 6]}, {"id": "food2", "position": [9, 3]}]
    assert described["water_sources"] == [{"id": "water", "position": [3, 3]}, {"id": "water2", "position": [3, 9]}]
    assert WorldConfig.from_describe(described) == cfg


def test_the_one_source_world_writes_nothing_new():
    old = WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY)
    described = old.describe()
    assert not {"food_sources", "water_sources", "water"} & set(described)
    assert "several sources" not in described["decision"] and "several sources" not in described["perception"]
    assert WorldConfig.from_describe(described) == old
    one_well = WorldConfig(seed=7, food_sources=1, water_sources=1)
    assert not {"food_sources", "water_sources"} & set(one_well.describe())


def test_source_counts_round_trip_and_bad_counts_are_refused():
    for cfg in (WorldConfig(seed=3, food_sources=1), WorldConfig(seed=3, water_sources=1),
                WorldConfig(seed=3, water_on=False)):
        assert WorldConfig.from_describe(cfg.describe()) == cfg
    for bad in (dict(food_sources=0), dict(food_sources=3), dict(water_sources=3)):
        with pytest.raises(ValueError):
            WorldConfig(seed=3, **bad)


KNOWN = (("a", (0, 0)), ("b", (6, 0)))


def free(**stock: int) -> dict[str, int]:
    return {f"source:{sid}": amount for sid, amount in stock.items()}


def test_the_target_is_the_nearest_seen_with_stock_else_the_nearest():
    assert target_source((2, 0), KNOWN, 6, free(a=1, b=1))[0] == "a"                  # both stocked: nearer
    assert target_source((2, 0), KNOWN, 6, free(a=0, b=1)) == ("b", (6, 0), 1)        # nearer seen empty
    assert target_source((2, 0), KNOWN, 6, free(a=0, b=0)) == ("a", (0, 0), 0)        # none stocked: nearest
    assert target_source((1, 0), KNOWN, 3, free(a=0, b=5)) == ("a", (0, 0), 0)        # an unseen one never attracts
    assert target_source((3, 5), KNOWN, 1, free(a=0, b=9)) == ("a", (0, 0), None)     # none in view: nearest, then id
    assert target_source((3, 0), KNOWN, 6, free(a=1, b=1))[0] == "a"                  # equal steps: lower id
    assert target_source((5, 0), KNOWN[:1], 1, free(a=0)) == ("a", (0, 0), None)      # one source: always it


def one_person(cfg: WorldConfig, at: tuple[int, int], stocks: dict[str, int], *, hunger: int = 0,
               thirst: int = 0) -> tuple[WorldState, Overlay]:
    ledger = WorldState.genesis(
        balances={"p01": 0},
        sources={sid: Source(stock, frozenset({"p01"}), resource=WATER if sid.startswith(WATER_SOURCE) else None)
                 for sid, stock in stocks.items()},
        **({"holdings": {WATER: {"p01": 0}}, "consumed_by": {WATER: 0}} if cfg.water_on else {}),
    )
    overlay = Overlay(tick=0, homes={"p01": (0, 0)}, positions={"p01": at}, hunger={"p01": hunger},
                      yield_at={"p01": 99}, died_at={}, thirst={"p01": thirst} if cfg.water_on else {})
    return ledger, overlay


def test_a_person_on_an_empty_source_walks_to_one_in_view_with_stock_or_waits():
    cfg = WorldConfig(seed=1, actors=1, water_on=False, warmth_on=False)   # food at (6, 6) and (9, 3), in view of each other
    ledger, overlay = one_person(cfg, (6, 6), {"food": 0, "food2": 3}, hunger=30)
    d = decide(observe("p01", ledger, overlay, cfg), cfg)
    assert (d.kind, d.target, d.step) == (GO, "food2", (7, 6))
    ledger, overlay = one_person(cfg, (6, 6), {"food": 0, "food2": 0}, hunger=30)
    d = decide(observe("p01", ledger, overlay, cfg), cfg)
    assert (d.kind, d.target, d.step) == (WAIT, "food", None)
    ledger, overlay = one_person(cfg, (9, 3), {"food": 0, "food2": 3}, hunger=30)
    d = decide(observe("p01", ledger, overlay, cfg), cfg)
    assert (d.kind, d.target, d.amount) == (CLAIM, "food2", 3)
    assert proposals_for({"p01": d}, 0)[0].params["sources"] == {"food2": 3}


def test_a_thirsty_person_at_an_empty_well_waits_rather_than_chase_one_out_of_sight():
    cfg = WorldConfig(seed=1, actors=1, warmth_on=False)                  # wells at (3, 3) and (3, 9): not in view of each other
    stocks = {"food": 4, "food2": 4, "water": 0, "water2": 5}
    ledger, overlay = one_person(cfg, (3, 3), stocks, thirst=30)
    d = decide(observe("p01", ledger, overlay, cfg), cfg)
    assert (d.kind, d.target) == (WAIT_WATER, "water")
    ledger, overlay = one_person(cfg, (3, 6), stocks, thirst=30)          # halfway both are in view: go to the stocked one
    d = decide(observe("p01", ledger, overlay, cfg), cfg)
    assert (d.kind, d.target, d.step) == (GO_WATER, "water2", (3, 7))


def test_each_source_renews_on_its_own_cadence_up_to_its_cap():
    cfg = WorldConfig(seed=3, width=7, height=7, actors=4, source_stock=4, source_cap=5, renewal_every=2,
                      renewal_amount=3, water_stock=10, water_cap=12, water_renewal_every=2, water_renewal_amount=5)
    ledger, overlay = genesis(cfg)
    engine = Engine(ledger)
    first = advance(overlay, {}, engine.tick([]), engine.state, cfg)
    assert first.production == ()
    engine = Engine(first.ledger)
    second = advance(first.overlay, {}, engine.tick([]), engine.state, cfg)
    assert second.production == ({"source": "food", "amount": 1}, {"source": "food2", "amount": 1},
                                 {"source": "water", "amount": 2}, {"source": "water2", "amount": 2})
    produced = apply_production(engine.state.canonical(), list(second.production))
    assert produced == second.ledger.canonical()
    assert second.ledger.totals() == {None: engine.state.totals()[None] + 2, WATER: engine.state.totals()[WATER] + 4}


def test_a_default_world_run_claims_from_its_targets_records_what_was_seen_and_replays(tmp_path: Path):
    cfg = WorldConfig(seed=7)
    run_world(cfg, 300, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    assert run.complete and replay_world(tmp_path / "w.jsonl").identical
    sc = run.header["scenario"]
    places = {entry["id"]: tuple(entry["position"]) for entry in sc["food_sources"] + sc["water_sources"]}
    radius = sc["perception_radius"]
    start_world, start_state = run.header["world"], run.header["genesis"]
    used = set()
    for tick in run.ticks:
        inputs = {entry["actor"]: entry for entry in tick["inputs"]}
        for actor, d in tick["decisions"].items():
            if d["kind"] in ("claim", "wait", "yield", "go", "draw", "wait_water", "go_water"):
                assert d["target"] in places
            if d["kind"] in ("claim", "draw"):
                assert inputs[actor]["params"]["sources"] == {d["target"]: d["amount"]}
                used.add(d["target"])
            origin = tuple(start_world["positions"][actor])
            seen = tick["observations"][actor]["seen_stock"] if "seen_stock" in tick["observations"][actor] else {}
            assert set(seen) == {sid for sid, at in places.items() if chebyshev(origin, at) <= radius}
            assert all(seen[sid] == start_state["sources"][sid]["stock"] for sid in seen)
        start_world = tick["world"]
        start_state = apply_production(tick["state"], tick.get("production", []))
    # every claim and draw named a source the header declares. Not every source gets used: six
    # people who have built shelters never get hungry enough to walk to the far food source.
    assert used and used <= set(places)
    assert len(run.ticks[-1]["world"]["died_at"]) < cfg.actors    # the world is hard, not lethal


def test_the_runner_defaults_and_switches():
    parser = build_parser()
    default = config_from(parser.parse_args(["--seed", "7"]))
    assert default.water_on and default.warmth_on and default.food_sources == 2 and default.water_sources == 2
    old = config_from(parser.parse_args(["--seed", "7", "--food-sources", "1", "--water", "off", "--warmth", "off",
                                        "--stagger", "off", "--terrain", "off", "--building", "off",
                                        "--offers", "off", "--births", "off", "--requests", "off"]))
    assert old == WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY)
    scoring = config_from(parser.parse_args(["--seed", "7", "--scoring", "on"]))
    assert scoring.scoring_on and not scoring.water_on and not scoring.warmth_on and not scoring.requests_on
    with pytest.raises(ValueError):
        config_from(parser.parse_args(["--seed", "7", "--scoring", "on", "--water", "on"]))


def test_the_viewer_shows_every_source(tmp_path: Path):
    run_world(WorldConfig(seed=7), 40, tmp_path / "w.jsonl")
    run = read_run(tmp_path / "w.jsonl")
    text = render_text(run, 40)
    assert "source S at (6, 6)" in text and "food2 S at (9, 3)" in text
    assert "water W at (3, 3)" in text and "water2 W at (3, 9)" in text
    page = render_html(run)
    assert "stockOf" in page and "water (stock)" in page
    old = WorldConfig(seed=7, **ONE_SOURCE_FOOD_ONLY)
    run_world(old, 10, tmp_path / "old.jsonl")
    old_text = render_text(read_run(tmp_path / "old.jsonl"), 10)
    assert "food2" not in old_text and " W at" not in old_text
