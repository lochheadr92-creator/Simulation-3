"""What people know of the ground and the walking it causes: patches seen and forgotten, rough ground remembered and
forgotten, the curious going to look, worn paths, and wells believed in once seen. Each rule on its own, the knowledge
boundary on constructed scenes, and a saved world re-derived from nothing but where people stood."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from tests.test_pledges import CLEAR_DAY, NIGHT, STORM, give, play
from world.config import WorldConfig, genesis, well_sites
from world.decide import _route_plan, decide, route_step
from world.ground import EXPLORE, Ground, patch_centre, patch_grid, patch_of, patches_in_view, refresh_ground
from world.observe import observe
from world.overlay import Overlay
from world.paths import advance_paths, worn
from world.replay import replay_world
from world.run import run_world, world_step
from world.sky import Sky, sight
from world.structures import Struct, well_id
from world.things import Things

FEATURES = ("beliefs", "exploration", "paths", "personality", "sky", "steady")
WELLS = FEATURES + ("structures",)


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


def scene(config=None, traits=(60, 50, 50, 50, 80), at=None, sky=CLEAR_DAY, tick=200, **overlay):
    """p01 at home (or `at`), curious, fed and watered; everybody else far from them and from each other."""
    config = config or cfg()
    ledger, world = genesis(config)
    positions = dict(world.positions)
    for who, spot in zip(("p02", "p03", "p04", "p05", "p06"), ((11, 11), (11, 0), (0, 11), (10, 6), (6, 11))):
        positions[who] = spot
    if at is not None:
        positions["p01"] = at
    persona = replace(world.persona, traits={a: (60, 50, 50, 50, 50) for a in world.roster} | {"p01": traits}, lonely={})
    world = replace(world, positions=positions, sky=sky, tick=tick, persona=persona, shelters=(world.homes["p01"],),
                    thirst={a: 0 for a in world.roster}, hunger={a: 0 for a in world.roster}, cold={a: 0 for a in world.roster},
                    **overlay)
    return config, replace(give(ledger, "p01", food=3, water=3), tick=tick), world


def cell_at(config, rough, distance, avoid=()):
    """A free, open cell exactly `distance` (Chebyshev) from `rough` and from nobody's home."""
    homes = set(genesis(config)[1].homes.values()) | set(config.all_source_positions()) | set(config.terrain()[0]) | set(config.terrain()[1])
    for y in range(config.height):
        for x in range(config.width):
            if max(abs(x - rough[0]), abs(y - rough[1])) == distance and (x, y) not in homes and (x, y) not in avoid:
                return (x, y)
    raise AssertionError("no such cell")


# --- storage and settings ------------------------------------------------------------------------

def test_header_round_trips_the_rules_are_written_down_and_the_features_need_what_they_use():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    rules = config.describe()["feature_rules"]
    assert "terrain_span" in rules["exploration"] and "stale_after" in rules["exploration"] and "worn_at" in rules["paths"]
    for features in (("exploration",), ("beliefs", "exploration"), ("personality", "exploration")):
        with pytest.raises(ValueError):
            WorldConfig(seed=7, features=features)                                  # curiosity needs personality, wells need beliefs
    for bad in ((("patch", 0),), (("terrain_span", 0),), (("roam", 0),), (("stale_after", 0),), (("explore_from", 101),),
                (("worn_at", 0),), (("recover_every", 0),), (("wear_cap", 3),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)
    with pytest.raises(ValueError):
        cfg(terrain_on=False)                                                       # nothing to remember or wear through


def test_ground_and_paths_are_stored_strictly_and_survive_the_canonical_form():
    config, ledger, world = scene(ground=Ground(seen={"p01": ((0, 190), (5, 200)), "p02": ((3, 10),)}),
                                  things=Things(paths=((1, 2, 3), (4, 4, 40))))
    again = Overlay.from_canonical(json.loads(json.dumps(world.canonical())))
    assert again.ground == world.ground and again.things.paths == world.things.paths and not Ground() and not Things()
    for bad in (dict(seen={"p09": ((0, 1),)}), dict(seen={"p01": ((0, 1), (0, 2))}), dict(seen={"p01": ((0, 999),)}),
                dict(seen={"p01": ((-1, 5),)})):
        with pytest.raises(ValueError):
            replace(world, ground=Ground(**bad))
    for bad in (((2, 2, 0),), ((4, 4, 1), (1, 2, 1)), ((1, 2, 1), (1, 2, 2)), ((-1, 2, 1),), ((1, 2),)):
        with pytest.raises(ValueError):
            Things(paths=bad)
    with pytest.raises(ValueError):
        Ground.from_canonical({"p01": [[1, 2, 3]]})


def test_patches_cut_the_map_into_squares_and_a_view_window_covers_those_it_touches():
    config = cfg()
    assert patch_grid(config) == (4, 4, 3)
    assert [patch_of(c, config) for c in ((0, 0), (2, 2), (3, 0), (0, 3), (11, 11))] == [0, 0, 1, 4, 15]
    assert patch_centre(0, config) == (1, 1) and patch_centre(15, config) == (10, 10)
    assert patches_in_view((0, 0), 3, config) == {0, 1, 4, 5}                   # a corner sees the four patches its window touches
    assert patches_in_view((5, 5), 1, config) == {5, 6, 9, 10}                  # 4..6 in both axes reaches into four patches
    assert patches_in_view((1, 1), 0, config) == {0}
    odd = cfg(width=10, height=10)
    assert patch_grid(odd) == (4, 4, 3) and patch_centre(15, odd) == (9, 9)       # the last patch is a short one: its middle is clipped


# --- what is known: sight, memory and forgetting ------------------------------------------------------

def test_rough_ground_is_known_only_from_sight_and_memory_and_a_seen_cell_is_remembered_after_leaving():
    config = cfg()
    rough = config.terrain()[0][0]
    radius = config.perception_radius
    near, far = cell_at(config, rough, 1), cell_at(config, rough, radius + 2)
    config, ledger, world = scene(at=far)
    unseen = observe("p01", ledger, world, config)
    assert rough not in unseen.rough_in_view and rough not in unseen.rough_seen_now         # out of sight and never seen: not known
    config, ledger, world = scene(at=near)
    seen = observe("p01", ledger, world, config)
    assert rough in seen.rough_seen_now and rough in seen.rough_in_view
    stepped = world_step(Engine(ledger), replace(world, positions={**world.positions, "p01": near}), config).processed.overlay
    assert rough in stepped.terrain_memory["p01"]                                            # written down from what the observation showed
    away = replace(stepped, positions={**stepped.positions, "p01": far})
    later = observe("p01", replace(ledger, tick=stepped.tick), away, config)
    assert rough in later.rough_in_view and rough not in later.rough_seen_now                # remembered, not current


def test_rough_ground_in_a_patch_not_seen_for_the_span_is_forgotten_and_seeing_it_again_brings_it_back():
    config = cfg()
    span = config.lever("terrain_span")
    rough = config.terrain()[0][0]
    patch = patch_of(rough, config)
    config, ledger, world = scene(terrain_memory={"p01": (rough,)}, ground=Ground(seen={"p01": ((patch, 100),)}), tick=100 + span)
    blind = SimpleNamespace(rough_seen_now=frozenset(), patches_seen_now=frozenset())
    sight_now = SimpleNamespace(rough_seen_now=frozenset({rough}), patches_seen_now=frozenset({patch}))
    for tick, expected in ((100 + span, True), (100 + span + 1, False)):
        memory = {"p01": {rough}}
        refresh_ground(replace(world, tick=tick), {"p01": blind}, memory, config)
        assert (rough in memory["p01"]) is expected, tick                                    # remembered for exactly terrain_span ticks
    memory = {"p01": {rough}}
    ground = refresh_ground(replace(world, tick=100 + span + 50), {"p01": sight_now}, memory, config)
    assert rough in memory["p01"] and dict(ground.seen["p01"])[patch] == 100 + span + 50     # in sight again: kept, and the patch re-stamped
    memory = {"p01": {rough}}
    held = refresh_ground(replace(world, tick=100 + span + 50), {"p01": blind}, memory, config)
    assert memory["p01"] == set() and dict(held.seen["p01"])[patch] == 100                   # an unseen patch keeps its old date


def test_the_ground_in_sight_is_stamped_with_the_tick_it_was_seen_and_the_dead_keep_nothing():
    config, ledger, world = scene(at=(5, 5), tick=77)
    step = world_step(Engine(ledger), world, config)
    seen = dict(step.processed.overlay.ground.seen["p01"])
    assert set(seen) == set(patches_in_view((5, 5), sight(config, CLEAR_DAY, config.perception_radius), config)) and set(seen.values()) == {77}
    assert set(step.processed.overlay.ground.seen) == set(world.living)
    gone = replace(world, died_at={"p06": 70})
    assert "p06" not in world_step(Engine(ledger), gone, config).processed.overlay.ground.seen


# --- curiosity -----------------------------------------------------------------------------------------

def seen_all_but(config, patch, when=190):
    across, down, _ = patch_grid(config)
    return Ground(seen={"p01": tuple((p, when) for p in range(across * down) if p != patch)})


def test_a_curious_free_person_walks_to_the_nearest_patch_near_home_that_they_have_not_seen_lately():
    config = cfg()
    home = genesis(config)[1].homes["p01"]
    near = min((p for p in range(16) if 0 < abs(patch_centre(p, config)[0] - home[0]) + abs(patch_centre(p, config)[1] - home[1]) <= config.lever("roam")),
               key=lambda p: (abs(patch_centre(p, config)[0] - home[0]) + abs(patch_centre(p, config)[1] - home[1]), p))
    config, ledger, world = scene(ground=seen_all_but(config, near))
    d = decide(observe("p01", ledger, world, config), config)
    centre = patch_centre(near, config)
    assert d.kind == EXPLORE and d.step is not None
    assert abs(d.step[0] - centre[0]) + abs(d.step[1] - centre[1]) < abs(home[0] - centre[0]) + abs(home[1] - centre[1])     # a step closer
    assert "curious" in d.reason


@pytest.mark.parametrize("change", ["not_curious", "child", "night", "storm", "danger", "hungry", "seen_lately", "too_far"])
def test_nobody_goes_exploring_when_they_are_not_curious_are_a_child_it_is_dark_or_stormy_a_wolf_is_near_they_are_short_or_nothing_is_stale(change):
    config = cfg()
    home = genesis(config)[1].homes["p01"]
    far = max(range(16), key=lambda p: abs(patch_centre(p, config)[0] - home[0]) + abs(patch_centre(p, config)[1] - home[1]))
    near = min((p for p in range(16) if abs(patch_centre(p, config)[0] - home[0]) + abs(patch_centre(p, config)[1] - home[1]) in range(1, 7)),
               key=lambda p: p)
    kwargs = {}
    target = near
    if change == "not_curious":
        kwargs["traits"] = (60, 50, 50, 50, config.lever("explore_from") - 1)
    elif change == "night":
        kwargs["sky"] = NIGHT
    elif change == "storm":
        kwargs["sky"] = STORM
    elif change == "too_far":
        target = far
    config2 = cfg(features=FEATURES + ("wolves",)) if change == "danger" else config
    if change == "danger":
        kwargs["sky"] = Sky("dusk", "clear", 9, 90)                                       # wolves are only feared when they hunt
    config2, ledger, world = scene(config2, ground=seen_all_but(config, target), **kwargs)
    if change == "seen_lately":
        world = replace(world, ground=Ground(seen={"p01": tuple((p, 199) for p in range(16))}))
    if change == "child":
        world = replace(world, age={**{a: config.adult_at + 5 for a in world.roster}, "p01": 5})
    if change == "danger":
        world = replace(world, persona=replace(world.persona, beliefs={"p01": (("wolf", "w1", home[0] + 1, home[1], 198, 198, ""),)}))
    if change == "hungry":
        world = replace(world, hunger={**world.hunger, "p01": config.death_at - 8})
    d = decide(observe("p01", ledger, world, config2), config2)
    assert d.kind != EXPLORE, change


def test_somebody_with_nothing_to_look_at_does_not_walk_and_a_patch_underfoot_is_not_a_target():
    config = cfg()
    config, ledger, world = scene(ground=Ground())                                     # nothing seen yet: every patch is stale
    d = decide(observe("p01", ledger, world, config), config)
    here = patch_of(world.positions["p01"], config)
    assert d.kind == EXPLORE and d.step != world.positions["p01"]
    mid = patch_centre(here, config)
    at_centre = replace(world, positions={**world.positions, "p01": mid})
    d2 = decide(observe("p01", ledger, at_centre, config), config)
    assert d2.kind != EXPLORE or d2.step != mid                                          # never "walks" to where they already stand


# --- desire paths ---------------------------------------------------------------------------------------

def test_wear_grows_with_each_step_onto_a_cell_is_capped_and_recovers_on_schedule():
    config, ledger, world = scene(things=Things(paths=((3, 3, 40), (4, 4, 1))))
    moved = {**world.positions, "p01": (3, 3), "p02": (4, 5)}
    wear = lambda tick, positions: dict(((x, y), w) for x, y, w in advance_paths(replace(world, tick=tick), positions, config))
    now = wear(3, moved)
    assert now[(3, 3)] == 40 and now[(4, 5)] == 1 and now[(4, 4)] == 1                      # a step adds one, never past the cap; standing adds nothing
    again = wear(3, {**world.positions})
    assert again == {(3, 3): 40, (4, 4): 1}                                                 # nobody moved: nothing worn, nothing lost off schedule
    every = config.lever("recover_every")
    recovered = wear(every - 1, {**world.positions})
    assert recovered == {(3, 3): 39} and (4, 4) not in recovered                           # on the schedule each cell loses one; a worn-away cell is dropped
    assert worn(((1, 1, config.lever("worn_at")), (2, 2, config.lever("worn_at") - 1)), config) == {(1, 1)}


def open_beside_rough(config):
    """A rough cell and an open cell next to it."""
    rough = set(config.terrain()[0])
    blocked = rough | set(config.terrain()[1]) | set(config.all_source_positions()) | set(genesis(config)[1].homes.values())
    for cell in sorted(rough):
        for nb in ((cell[0] + 1, cell[1]), (cell[0] - 1, cell[1]), (cell[0], cell[1] + 1), (cell[0], cell[1] - 1)):
            if 0 <= nb[0] < config.width and 0 <= nb[1] < config.height and nb not in blocked:
                return cell, nb
    raise AssertionError("no rough cell with an open neighbour")


def after_forced_step(config, ledger, world, cell):
    """The tick's processing with p01 stepping onto `cell`, everybody else deciding as they would."""
    from world.process import advance
    step = world_step(Engine(ledger), world, config)
    forced = replace(step.decisions["p01"], kind="go", step=cell)
    return advance(world, {**step.decisions, "p01": forced}, step.record, step.committed, config, step.views).overlay


def test_a_step_onto_rough_ground_costs_a_tick_unless_it_has_been_worn_through():
    config = cfg()
    rough, beside = open_beside_rough(config)
    worn_at = config.lever("worn_at")
    held = {}
    for label, paths in (("plain", ()), ("worn", ((rough[0], rough[1], worn_at),)), ("nearly", ((rough[0], rough[1], worn_at - 1),))):
        c, ledger, world = scene(at=beside, things=Things(paths=paths))
        out = after_forced_step(c, ledger, world, rough)
        assert out.positions["p01"] == rough
        held[label] = out.held["p01"]
    assert held["plain"] >= 1 and held["nearly"] >= 1 and held["worn"] == 0
    off = cfg(features=("beliefs", "personality", "sky", "steady"))                             # paths off: wear changes nothing
    c, ledger, world = scene(off, at=beside)
    assert after_forced_step(c, ledger, world, rough).held["p01"] >= 1


def test_between_two_equally_near_steps_somebody_takes_the_worn_one_they_can_see_and_never_a_longer_way():
    config = cfg(rough_pct=0)                                                             # open ground: the plain route is the only route
    x, y = 3, 3
    here, goal = (x + 1, y + 1), (x + 4, y + 4)
    right, down = (x + 2, y + 1), (x + 1, y + 2)
    config, ledger, world = scene(at=here)
    view = observe("p01", ledger, world, config)
    plain = replace(view, worn_in_view=frozenset())
    straight = route_step(plain, goal, config)
    assert straight == right                                                              # the plain rule: along x on a tie
    assert route_step(replace(view, worn_in_view=frozenset({down})), goal, config) == down
    assert route_step(replace(view, worn_in_view=frozenset({right})), goal, config) == right
    assert route_step(replace(view, worn_in_view=frozenset({(x, y + 1)})), goal, config) == straight    # a path that leads away is no reason to go that way
    assert route_step(replace(view, worn_in_view=frozenset({down}), danger=frozenset({(x + 4, y + 4)})), goal, config) in (right, down)
    assert route_step(replace(view, worn_in_view=frozenset({down})), (x + 1, y + 4), config) == down      # straight down: there is only one near step


def test_a_remembered_rough_cell_that_has_worn_through_still_looks_rough_until_it_is_seen_again():
    config = cfg()
    base = scene(at=(2, 5))[2]
    wall = frozenset({(4, y) for y in range(3, 8)})
    view = replace(observe("p01", scene(at=(2, 5))[1], base, config), rough_in_view=wall, worn_in_view=frozenset(), position=(2, 5))
    around = _route_plan(view, (7, 5), config)
    through = _route_plan(replace(view, worn_in_view=wall), (7, 5), config)
    assert around[1] > through[1] == 5                                                      # the wall is a detour while it is believed rough
    remembered_only = replace(view, worn_in_view=frozenset())                               # worn since, but out of sight: nothing says so
    assert _route_plan(remembered_only, (7, 5), config) == around
    assert route_step(replace(view, worn_in_view=wall), (7, 5), config) == (3, 5)


# --- wells ------------------------------------------------------------------------------------------------

def well_world(sky=CLEAR_DAY):
    """p01 stands beside p03's finished well, which is far from any natural water."""
    config = cfg(features=WELLS, wood_on=True)
    owner, cell = well_sites(config)[2]
    config, ledger, world = scene(config, sky=sky)
    world = replace(world, things=Things(structures=(Struct("well", owner, cell[0], cell[1], 12, 1),)),
                    positions={**world.positions, "p01": (max(0, cell[0] - 1), cell[1])})
    assert all(max(abs(cell[0] - w[0]), abs(cell[1] - w[1])) > config.perception_radius for w in config.water_positions())
    return config, ledger, world, owner, cell


def test_a_finished_well_in_sight_becomes_a_belief_and_one_not_finished_does_not():
    config, ledger, world, owner, cell = well_world()
    after = world_step(Engine(ledger), world, config).processed.overlay
    assert any(b[:2] == ("well", owner) and (b[2], b[3]) == cell and b[6] == "" for b in after.persona.beliefs.get("p01", ()))
    digging = replace(world, things=Things(structures=(Struct("well", owner, cell[0], cell[1], 5, 0),)))
    assert not any(b[0] == "well" for b in world_step(Engine(ledger), digging, config).processed.overlay.persona.beliefs.get("p01", ()))


def test_a_believed_well_is_used_from_out_of_sight_but_one_never_seen_is_not_and_a_dry_one_in_sight_is_passed_by():
    config, ledger, world, owner, cell = well_world()
    natural = config.water_positions()
    steps = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    blocked = set(config.terrain()[0]) | set(natural) | set(config.food_positions()) | set(world.homes.values()) | set(world.positions.values())
    far = next((x, y) for x in range(config.width) for y in range(config.height)
               if max(abs(x - cell[0]), abs(y - cell[1])) > config.perception_radius and (x, y) not in blocked
               and steps((x, y), cell) < min(steps((x, y), w) for w in natural)
               and all(max(abs(x - w[0]), abs(y - w[1])) > config.perception_radius for w in natural))
    wet = replace(ledger, sources={**ledger.sources, well_id(owner): replace(ledger.sources[well_id(owner)], stock=3)})
    from_afar = replace(world, positions={**world.positions, "p01": far})
    assert observe("p01", wet, from_afar, config).water_source_id != well_id(owner)         # never seen it, so it is not a landmark
    knows = replace(from_afar, persona=replace(from_afar.persona, beliefs={"p01": (("well", owner, cell[0], cell[1], 150, 150, ""),)}))
    believed = observe("p01", wet, knows, config)
    assert believed.water_source_id == well_id(owner) and believed.water_stock is None and believed.water_source == cell   # headed for it, stock unknown from here
    beside_it = replace(world, persona=replace(world.persona, beliefs={"p01": (("well", owner, cell[0], cell[1], 150, 150, ""),)}))
    assert observe("p01", wet, beside_it, config).water_source_id == well_id(owner)          # in sight with water in it: take it
    dry = observe("p01", ledger, beside_it, config)
    assert dry.water_source_id != well_id(owner)                                             # empty and in sight: not worth the trip


def test_without_the_exploration_feature_a_well_seen_is_not_remembered():
    config = WorldConfig(seed=7, features=("beliefs", "personality", "sky", "structures"), wood_on=True)
    owner, cell = well_sites(config)[2]
    config, ledger, world = scene(config)
    world = replace(world, things=Things(structures=(Struct("well", owner, cell[0], cell[1], 12, 1),)),
                    positions={**world.positions, "p01": (max(0, cell[0] - 1), cell[1])})
    after = world_step(Engine(ledger), world, config).processed.overlay
    assert not any(b[0] == "well" for b in after.persona.beliefs.get("p01", ()))


# --- whole worlds ---------------------------------------------------------------------------------------

RICH = ("beliefs", "bonds", "explain", "exploration", "paths", "personality", "skills", "sky", "sleep", "steady", "wolves")


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("ground") / "run.jsonl"
    run_world(WorldConfig(seed=7, features=RICH), 500, path)
    return path, read_run(path)


def disc(origin, radius):
    return {(x, y) for x in range(origin[0] - radius, origin[0] + radius + 1) for y in range(origin[1] - radius, origin[1] + radius + 1)}


@pytest.mark.long_run
def test_a_saved_world_audits_replays_and_what_people_know_of_the_ground_follows_from_where_they_stood(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    config = WorldConfig.from_describe(run.header["scenario"])
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]
    rough = set(map(tuple, config.terrain()[0]))
    span = config.lever("terrain_span")
    memory = {a: set() for a in worlds[0]["positions"]}
    last = {a: {} for a in worlds[0]["positions"]}
    wear = {}
    explored = 0
    for t in range(len(worlds) - 1):
        before, after = worlds[t], worlds[t + 1]
        sky = Sky.from_canonical(before["sky"])
        radius = sight(config, sky, config.perception_radius)
        for actor in sorted(before["positions"]):
            if actor in before.get("died_at", {}):
                continue
            reach = 0 if actor in (before["persona"].get("asleep") or []) else radius                # a sleeper sees only their own cell
            seen_cells = {c for c in disc(tuple(before["positions"][actor]), reach) if 0 <= c[0] < config.width and 0 <= c[1] < config.height}
            for patch in {patch_of(c, config) for c in seen_cells}:
                last[actor][patch] = t
            memory[actor] |= seen_cells & rough
            memory[actor] = {c for c in memory[actor] if c in seen_cells or t - last[actor][patch_of(c, config)] <= span}
            recorded = {tuple(c) for c in (after.get("terrain_memory") or {}).get(actor, [])}
            assert recorded == memory[actor], (t, actor)                                # what they remember, from where they stood
            recorded_ground = dict(map(tuple, (after.get("ground") or {}).get(actor, [])))
            assert recorded_ground == last[actor], (t, actor)                           # and when they last saw each patch
        for x, y, w in (before.get("things") or {}).get("paths", []):
            wear[(x, y)] = w
        step = run.ticks[t]["decisions"]
        moved = {a for a in after["positions"] if a in before["positions"] and before["positions"][a] != after["positions"][a]}
        expected = {tuple(c): w for c, w in wear.items()}
        for a in sorted(moved):
            c = tuple(after["positions"][a])
            expected[c] = min(config.lever("wear_cap"), expected.get(c, 0) + config.lever("wear_gain"))
        if (before["tick"] + 1) % config.lever("recover_every") == 0:
            expected = {c: w - 1 for c, w in expected.items()}
        expected = {c: w for c, w in expected.items() if w > 0}
        recorded_paths = {(x, y): w for x, y, w in (after.get("things") or {}).get("paths", [])}
        assert recorded_paths == expected, t                                            # the wear is the walking, step by step
        wear = recorded_paths
        for actor, d in step.items():
            if d["kind"] == EXPLORE:
                explored += 1
                assert before["persona"]["traits"][actor][4] >= config.lever("explore_from")
                assert not sky.night and not sky.storm
    assert explored >= 1
    assert max(w for w in wear.values()) >= 1


@pytest.mark.long_run
def test_an_ordinary_world_has_none_of_it(tmp_path):
    path = tmp_path / "plain.jsonl"
    run_world(WorldConfig(seed=7, features=("beliefs", "personality", "sky", "steady")), 120, path)
    run = read_run(path)
    assert all("ground" not in t["world"] and "paths" not in (t["world"].get("things") or {}) for t in run.ticks)
