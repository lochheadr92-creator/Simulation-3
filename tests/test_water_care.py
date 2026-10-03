"""Parents bring water to children who are born out of reach of it.

Before this rule, a child born further from water than the child leash could not
fetch it and nobody else brought any: in 36 saved 400-tick worlds every one of
the 33 children who died as children died of thirst, and 0 of 68 born within
the leash of water died. The option is off by default.
"""

import json
from dataclasses import replace

import pytest

from kernel import Engine
from stream.run_file import read_run
from world.config import WorldConfig, genesis
from world.decide import decide, stranded_from_water
from world.observe import Observation, SeenPerson
from world.recover import recover_world
from world.replay import replay_world
from world.run import build_parser, config_from, run_id_for, run_world, world_step
from world.viewer import render_html
from world.viewer_index import build_index

FAR_HOME = (10, 10)     # 8 steps from the nearer well at (3, 9); the leash is 5
NEAR_HOME = (4, 4)      # 2 steps from the well at (3, 3)


def config(**changes):
    return WorldConfig(seed=24, water_care_on=True, warmth_on=False, **changes)


def parent(cfg, **changes):
    child = SeenPerson("p02", (10, 11), 0, water=0)
    base = Observation(actor="p01", tick=10, alive=True, position=FAR_HOME, home=FAR_HOME,
                       hunger=0, food=0, source=(6, 6), source_food=0,
                       thirst=0, water=1, water_source=(3, 9), water_stock=None,
                       dependents=frozenset({"p02"}), others=(child,))
    return replace(base, **changes)


def test_geometry_decides_who_is_stranded_not_the_childs_thirst():
    cfg = config()
    assert stranded_from_water(parent(cfg), cfg)
    assert not stranded_from_water(parent(cfg, home=NEAR_HOME), cfg)
    assert not stranded_from_water(parent(cfg, dependents=frozenset()), cfg)
    assert not stranded_from_water(parent(cfg), replace(cfg, child_leash=8))


def test_off_by_default_changes_nothing():
    cfg = config()
    off = replace(cfg, water_care_on=False)
    view = parent(cfg, others=(SeenPerson("p02", (10, 11), 0, parched=True, water=0),))
    assert decide(view, cfg).resource == "water"
    assert decide(view, off).resource is None
    assert "resource" not in decide(view, off).canonical()


def test_parent_hands_one_water_to_a_visibly_parched_child_alongside():
    cfg = config()
    view = parent(cfg, others=(SeenPerson("p02", (10, 11), 0, parched=True, water=0),))
    made = decide(view, cfg)
    assert (made.kind, made.target, made.amount, made.resource) == ("offer", "p02", 1, "water")
    assert "parched" in made.reason
    assert made.kind in made.candidates


def test_parent_hands_water_to_a_stranded_child_holding_none_before_it_is_parched():
    cfg = config()
    made = decide(parent(cfg), cfg)
    assert (made.kind, made.target, made.resource) == ("offer", "p02", "water")
    assert "out of reach of water" in made.reason
    holding = parent(cfg, others=(SeenPerson("p02", (10, 11), 0, water=1),))
    assert decide(holding, cfg).resource is None            # already has some
    near = parent(cfg, home=NEAR_HOME, position=NEAR_HOME, others=(SeenPerson("p02", (4, 5), 0, water=0),))
    assert decide(near, cfg).resource is None               # it can fetch its own


def test_a_non_stranded_child_is_only_helped_when_visibly_parched():
    cfg = config()
    base = parent(cfg, home=NEAR_HOME, position=NEAR_HOME)
    fine = replace(base, others=(SeenPerson("p02", (4, 5), 0, water=0),))
    parched = replace(base, others=(SeenPerson("p02", (4, 5), 0, parched=True, water=0),))
    assert decide(fine, cfg).resource is None
    assert decide(parched, cfg).resource == "water"


def test_a_distant_parched_child_is_walked_to_and_parched_comes_before_stranded():
    cfg = config()
    far = parent(cfg, others=(SeenPerson("p02", (10, 13), 0, parched=True, water=0),))
    made = decide(far, cfg)
    assert made.kind == "go_offer" and made.resource == "water" and made.step is not None
    two = parent(cfg, dependents=frozenset({"p02", "p03"}),
                 others=(SeenPerson("p02", (10, 11), 0, water=0),
                         SeenPerson("p03", (10, 12), 0, parched=True, water=0)))
    assert decide(two, cfg).target == "p03"


def test_the_parents_own_death_comes_first_when_it_is_close():
    cfg = config()
    view = parent(cfg, others=(SeenPerson("p02", (10, 11), 0, parched=True, water=0),))
    dying = replace(view, thirst=78)                   # 1 tick of slack; holds water
    assert decide(dying, cfg).kind == "drink"
    cold = replace(cfg, warmth_on=True)
    outside = replace(view, position=(10, 9), others=(SeenPerson("p02", (10, 10), 0, parched=True, water=0),))
    assert decide(outside, cold).resource == "water"        # warm enough to spare the tick
    freezing = replace(outside, cold=cold.cold_death_at - 2)
    assert decide(freezing, cold).resource is None          # 2 ticks in hand, not enough


def test_fetch_walks_to_water_draws_and_stops_when_the_well_is_dry():
    cfg = config()
    none = parent(cfg, water=0, others=())
    walking = decide(none, cfg)
    assert walking.kind == "go_water" and "cannot reach water" in walking.reason
    assert walking.step is not None
    at_well = replace(none, position=(3, 9), water_stock=5)
    drawing = decide(at_well, cfg)
    assert (drawing.kind, drawing.amount) == ("draw", cfg.draw_amount)
    assert "cannot reach water" in drawing.reason
    dry = replace(at_well, water_stock=0)
    assert decide(dry, cfg).kind != "draw"


@pytest.mark.parametrize("change", ["hungry", "own_thirst", "not_stranded", "no_dependents", "far_and_cold"])
def test_fetch_waits_for_everything_else(change):
    cfg = config()
    view = parent(cfg, water=0, others=())
    if change == "hungry":
        view = replace(view, hunger=cfg.hungry_at)
    elif change == "own_thirst":
        view = replace(view, thirst=cfg.thirsty_at)   # the ordinary water trip, not a care trip
    elif change == "not_stranded":
        view = replace(view, home=NEAR_HOME, position=NEAR_HOME)
    elif change == "no_dependents":
        view = replace(view, dependents=frozenset())
    else:
        cfg = replace(cfg, warmth_on=True)
        view = replace(view, cold=cfg.cold_death_at - 4, position=(10, 9))
    made = decide(view, cfg)
    assert "cannot reach water" not in made.reason


def test_config_cli_and_legacy_descriptions():
    cfg = config_from(build_parser().parse_args(["--seed", "24", "--water-care", "on"]))
    assert cfg.water_care_on and "water-care" in run_id_for(cfg, 400)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
    off = replace(cfg, water_care_on=False)
    assert "water_care" not in off.describe()
    assert WorldConfig.from_describe(off.describe()) == off
    with pytest.raises(ValueError):
        replace(cfg, childhood_on=False)
    with pytest.raises(ValueError):
        replace(cfg, water_on=False, warmth_on=False)
    for value in (True, None, "yes", 1):
        with pytest.raises(ValueError):
            WorldConfig.from_describe(dict(cfg.describe(), water_care=value))
    with pytest.raises(ValueError):
        WorldConfig.from_describe(dict(cfg.describe(), decision=off.describe()["decision"]))


SCENE = dict(seed=97805, shared_care_on=True, care_by_need_on=True, water_care_on=True)


def test_ordinary_water_handoff_settles_through_the_kernel_and_the_child_drinks():
    cfg = WorldConfig(**SCENE)
    ledger, world = genesis(cfg)
    engine = Engine(ledger)
    for tick in range(66):
        step = world_step(engine, world, cfg)
        if tick in (31, 63):
            made = step.decisions["p04"]
            assert (made.kind, made.target, made.resource) == ("offer", "p08", "water")
            outcome = next(o for o in step.record.outcomes if o.actor == "p04")
            assert outcome.accepted
            moved = {e.account: e.delta for e in outcome.effects}
            assert moved == {"actor@water:p04": -1, "actor@water:p08": 1}
        if tick == 64:
            assert step.decisions["p08"].kind == "drink"      # thirsty by now, so it drinks what it was given
        engine, world = step.engine, step.processed.overlay


@pytest.mark.long_run
def test_saved_water_scene_replays_recovers_repeats_and_shows_in_the_viewer(tmp_path):
    cfg = WorldConfig(**SCENE)
    path = tmp_path / "water.jsonl"
    result = run_world(cfg, 80, path)
    run = read_run(path)
    assert run.complete and replay_world(path).identical
    assert run_world(cfg, 80, tmp_path / "repeat.jsonl").trail_digest == result.trail_digest
    events = build_index(run)["events"]
    assert any(e["kind"] == "gave_water" and e["who"] == "p04" and e["other"] == "p08" for e in events)
    assert "handed their child p08 a unit of water" in render_html(run)
    lines = path.read_bytes().splitlines(keepends=True)
    for completed in (30, 31, 32):
        end = next(i for i, line in enumerate(lines)
                   if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == completed - 1)
        cut, restored = tmp_path / f"cut-{completed}.jsonl", tmp_path / f"restored-{completed}.jsonl"
        cut.write_bytes(b"".join(lines[:end + 1]))
        recover_world(cut, restored)
        assert read_run(restored).ticks == run.ticks


def child_thirst_deaths(path):
    ticks = read_run(path).ticks
    adult_at, deaths = WorldConfig(seed=1).adult_at, 0
    for index in range(1, len(ticks)):
        line, world, before = ticks[index], ticks[index]["world"], ticks[index - 1]["world"]
        for actor, died in world["died_at"].items():
            if died == line["tick"] and before.get("age", {}).get(actor, adult_at) < adult_at:
                needs = {"hunger": world["hunger"][actor], "thirst": world["thirst"][actor],
                         "cold": world.get("cold", {}).get(actor, 0)}
                deaths += max(needs, key=needs.get) == "thirst"
    return deaths


@pytest.mark.long_run
def test_children_born_out_of_reach_of_water_stop_dying_of_thirst(tmp_path):
    """Seed 97411, shared care and care by need on. Without water care the
    children born at far homes die of thirst; with it none does."""
    base = dict(seed=97411, shared_care_on=True, care_by_need_on=True)
    run_world(WorldConfig(**base), 400, tmp_path / "off.jsonl")
    run_world(WorldConfig(**base, water_care_on=True), 400, tmp_path / "on.jsonl")
    assert child_thirst_deaths(tmp_path / "off.jsonl") >= 3
    assert child_thirst_deaths(tmp_path / "on.jsonl") == 0
