"""Food carried to homes stays accounted for and is useful to nearby people."""

import json
from dataclasses import replace

import pytest

from kernel import Engine, Proposal, Source, WorldState, claim, consume, deposit, reserve
from kernel import reasons
from stream.run_file import read_run
from world.config import WorldConfig, genesis, store_sites
from world.decide import decide
from world.observe import SeenPerson, observe
from world.process import _births, advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, proposals_for, run_id_for, run_world
from world.viewer import render_html
from world.viewer_index import build_index


def cache_ledger():
    return WorldState.genesis(balances={"a": 3, "b": 0},
                             sources={"cache": Source(0, frozenset({"a", "b"}))})


def test_deposit_is_conserved_and_cannot_be_spent_in_same_tick():
    before = cache_ledger()
    engine = Engine(before)
    record = engine.tick([deposit("put", "a", 0, source="cache", amount=2),
                          claim("take", "b", 0, sources={"cache": 1})])
    verdict = {o.proposal_id: o for o in record.outcomes}
    assert verdict["put"].accepted
    assert verdict["take"].reason == reasons.DENIED_INSUFFICIENT_SOURCE
    assert engine.state.balances == {"a": 1, "b": 0}
    assert engine.state.sources["cache"].stock == 2
    assert engine.state.totals() == before.totals()
    assert before.sources["cache"].stock == 0
    assert engine.tick([claim("later", "b", 0, sources={"cache": 2})]).outcomes[0].accepted
    assert engine.state.balances["b"] == 2


@pytest.mark.parametrize("params,reason", [
    ({"source": "cache", "amount": 4}, reasons.DENIED_INSUFFICIENT_BALANCE),
    ({"source": "missing", "amount": 1}, reasons.DENIED_UNKNOWN_SOURCE),
    ({"source": "", "amount": 1}, reasons.DENIED_MALFORMED_PARAMS),
    ({"amount": 1}, reasons.DENIED_MALFORMED_PARAMS),
    ({"source": "cache", "amount": True}, reasons.DENIED_NON_INTEGER_AMOUNT),
    ({"source": "cache", "amount": 0}, reasons.DENIED_NON_POSITIVE_AMOUNT),
    ({"source": "cache", "amount": -1}, reasons.DENIED_NON_POSITIVE_AMOUNT),
    ({"source": "cache", "amount": 1, "resource": "wood"}, reasons.DENIED_UNKNOWN_RESOURCE),
])
def test_bad_deposit_changes_no_balances(params, reason):
    before = cache_ledger()
    engine = Engine(before)
    outcome = engine.tick([Proposal("bad", "a", 0, "deposit", params)]).outcomes[0]
    assert outcome.reason == reason
    assert engine.state.balances == before.balances and engine.state.sources == before.sources


def test_named_resource_is_not_converted_into_food_and_reservation_is_explicitly_unsupported():
    state = WorldState.genesis(balances={"a": 3}, sources={"well": Source(0, frozenset({"a"}), "water")},
                              holdings={"water": {"a": 2}}, consumed_by={"water": 0})
    engine = Engine(state)
    record = engine.tick([deposit("wrong", "a", 0, source="well", amount=1),
                          deposit("right", "a", 1, source="well", amount=2, resource="water"),
                          reserve("held", "a", 2, operation="deposit", params={"source": "well", "amount": 1})])
    verdict = {o.proposal_id: o for o in record.outcomes}
    assert verdict["wrong"].reason == reasons.DENIED_RESOURCE_MISMATCH
    assert verdict["right"].accepted
    assert verdict["held"].reason == reasons.DENIED_UNKNOWN_OPERATION
    assert engine.state.totals() == state.totals()


def test_competing_deposits_and_spending_do_not_overdraw():
    proposals = [deposit("one", "a", 0, source="cache", amount=2),
                 consume("eat", "a", 1, amount=2),
                 deposit("two", "a", 2, source="cache", amount=1)]
    a, b = Engine(cache_ledger()), Engine(cache_ledger())
    ra, rb = a.tick(proposals), b.tick(reversed(proposals))
    assert a.state == b.state
    assert [(o.proposal_id, o.accepted) for o in ra.outcomes] == [(o.proposal_id, o.accepted) for o in rb.outcomes]
    assert a.state.balances["a"] == 0 and a.state.sources["cache"].stock == 3
    # Two claimants still cannot both get the last unit.
    state = replace(cache_ledger(), sources={"cache": Source(1, frozenset({"a", "b"}))})
    engine = Engine(state)
    record = engine.tick([claim("a", "a", 0, sources={"cache": 1}), claim("b", "b", 0, sources={"cache": 1})])
    assert sum(o.accepted for o in record.outcomes) == 1
    assert engine.state.totals() == state.totals()


def resident(food_sources=2):
    cfg = WorldConfig(seed=7, actors=2, stores_on=True, source_stock=0,
                      terrain_on=False, water_on=False, warmth_on=False, births_on=False,
                      food_sources=food_sources)
    ledger, overlay = genesis(cfg)
    home = overlay.homes["p01"]
    ledger = replace(ledger, balances={"p01": 3, "p02": 0})
    overlay = replace(overlay, hunger={"p01": 0, "p02": 0}, shelters=(home,))
    return cfg, ledger, overlay, observe("p01", ledger, overlay, cfg)


@pytest.mark.parametrize("food_sources", [1, 2])
def test_resident_puts_spare_food_in_store_then_neighbour_takes_it(food_sources):
    cfg, ledger, overlay, view = resident(food_sources)
    choice = decide(view, cfg)
    assert (choice.kind, choice.amount, choice.target) == ("deposit", 2, "store-p01")
    engine = Engine(ledger)
    record = engine.tick(proposals_for({"p01": choice}, 0))
    result = advance(overlay, {"p01": choice}, record, engine.state, cfg)
    assert result.ledger.balances["p01"] == 1
    assert result.ledger.sources["store-p01"].stock == 2
    assert result.ledger.totals() == ledger.totals()
    visitor = replace(result.overlay, positions=dict(result.overlay.positions, p02=view.home),
                      hunger={"p01": 0, "p02": cfg.hungry_at})
    seen = observe("p02", result.ledger, visitor, cfg)
    take = decide(seen, cfg)
    assert (take.kind, take.target, take.amount) == ("claim", "store-p01", 2)
    assert seen.home_store_food is None
    engine = Engine(result.ledger)
    assert engine.tick(proposals_for({"p02": take}, 1)).outcomes[0].accepted
    assert engine.state.balances["p02"] == 2


def test_needs_help_childhood_and_storage_target_keep_their_priorities():
    cfg, _, _, view = resident()
    assert decide(replace(view, hunger=cfg.hungry_at), cfg).kind == "eat"
    assert decide(replace(view, food=1), cfg).kind == "rest"
    assert decide(replace(view, home_store_food=6), cfg).kind == "rest"
    assert decide(replace(view, home_store_food=5), cfg).amount == 1
    assert decide(replace(view, home_store_food=None), cfg).kind == "rest"
    assert decide(replace(view, home_built=False), cfg).kind == "build"
    assert decide(replace(view, age=0), cfg).kind == "rest"
    helped = replace(view, others=(SeenPerson("p02", view.position, 0, starving=True),))
    assert decide(helped, cfg).kind == "offer"
    water_cfg = replace(cfg, water_on=True)
    assert decide(replace(view, thirst=water_cfg.thirsty_at, water=1,
                          water_source=view.home, water_stock=0), water_cfg).kind == "drink"
    warm_cfg = replace(cfg, warmth_on=True)
    assert decide(replace(view, cold=warm_cfg.cold_at), warm_cfg).kind == "warm"


def test_caches_require_local_stock_and_finished_shelter_and_child_leash_stays():
    cfg, ledger, overlay, view = resident()
    sources = dict(ledger.sources)
    sources["store-p01"] = replace(sources["store-p01"], stock=2)
    ledger = replace(ledger, sources=sources)
    # At the stocked cache, a visitor sees it. With no shelter, only patches are targets.
    overlay = replace(overlay, positions=dict(overlay.positions, p02=view.home))
    assert observe("p02", ledger, overlay, cfg).source_id == "store-p01"
    assert observe("p02", ledger, replace(overlay, shelters=()), cfg).source_id in cfg.food_source_ids()
    far = max(((x,y) for x in range(cfg.width) for y in range(cfg.height)),
              key=lambda p: abs(p[0]-view.home[0])+abs(p[1]-view.home[1]))
    distant = replace(overlay, positions=dict(overlay.positions, p02=far))
    assert observe("p02", ledger, distant, cfg).source_id in cfg.food_source_ids()
    assert "store-p01" not in dict(observe("p02", ledger, distant, cfg).seen_stock)
    seen = observe("p02", ledger, overlay, cfg)
    child = replace(seen, age=0, food=0, hunger=cfg.hungry_at, home=far)
    # A destination outside the child's leash cannot produce a food journey.
    child = replace(child, position=far)
    assert decide(child, cfg).kind == "rest"


def test_stores_never_regrow_and_births_can_claim_existing_caches():
    cfg, ledger, overlay, _ = resident()
    cfg = replace(cfg, births_on=True, together_ticks=1, regrowth_on=True, seasons_on=True)
    homes = {"p01": (0,0), "p02": (1,0)}
    overlay = replace(overlay, tick=14, homes=homes, positions=homes, shelters=tuple(homes.values()),
                      built={p: cfg.build_ticks for p in homes}, held={p: 0 for p in homes})
    engine = Engine(replace(ledger, tick=14))
    record = engine.tick([])
    result = advance(overlay, {}, record, engine.state, cfg)
    born = set(result.ledger.balances) - set(ledger.balances)
    assert born
    assert not any(p.get("source", "").startswith("store-") for p in result.production)
    assert result.ledger.sources["store-p01"].stock == 0
    assert born <= result.ledger.sources["store-p01"].authorised


def test_switch_header_and_default_compatibility():
    parser = build_parser()
    old = config_from(parser.parse_args(["--seed", "7"]))
    new = config_from(parser.parse_args(["--seed", "7", "--stores", "on"]))
    assert not old.stores_on and new.stores_on
    assert "stores" not in old.describe() and not store_sites(old)
    assert WorldConfig.from_describe(old.describe()) == old
    assert WorldConfig.from_describe(new.describe()) == new
    assert run_id_for(old, 480) != run_id_for(new, 480)
    assert genesis(old)[0].totals() == genesis(new)[0].totals()
    with pytest.raises(ValueError):
        replace(new, stores_on=1)
    bad = new.describe()
    bad["store_target"] = 100
    with pytest.raises(ValueError):
        WorldConfig.from_describe(bad)


@pytest.mark.long_run
def test_run_replays_recovers_and_viewer_records_real_deposits(tmp_path):
    cfg = WorldConfig(seed=7, stores_on=True, regrowth_on=True, seasons_on=True,
                      source_stock=8, source_cap=16, renewal_amount=3)
    path = tmp_path / "stores.jsonl"
    result = run_world(cfg, 300, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    deposits = [e for e in build_index(run)["events"] if e["kind"] == "deposit"]
    assert deposits
    page = render_html(run)
    assert "Shared home cache" in page and "food must be carried here" in page
    for tick in run.ticks:
        assert not any(e.get("source", "").startswith("store-") for e in tick.get("production") or [])
        assert all(0 <= source["stock"] <= 6 for sid, source in tick["state"]["sources"].items() if sid.startswith("store-"))
    lines = path.read_bytes().splitlines(keepends=True)
    cut_at = next(i for i, raw in enumerate(lines) if json.loads(raw).get("kind") == "tick"
                  and json.loads(raw).get("tick") == deposits[0]["k"]-1)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:cut_at+1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks
    assert replay_world(restored).identical
    assert run_world(cfg, 300, tmp_path / "again.jsonl").trail_digest == result.trail_digest
