"""Graves, death records, belongings left behind and how news of a death travels: stored strictly, each rule on its own,
and on a saved world where every collection, grief and piece of news traces to something recorded."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from kernel import Engine
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from tests.test_pledges import CLEAR_DAY, bond, give, play
from world.aftermath import CAUSES, Death, cause_of, estate_of, heirs
from world.belief import advance_beliefs
from world.config import WorldConfig, genesis
from world.decide import decide
from world.family import Family, advance_family, lifespan
from world.observe import observe
from world.overlay import Overlay
from world.replay import replay_world
from world.run import run_world, world_step
from world.structures import Struct
from world.things import Things

FEATURES = ("aftermath", "beliefs", "bonds", "explain", "family", "personality", "skills", "sky", "steady", "wolves")


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


GRAVE = (8, 8)
DIED = 30


def buried(config=None, near=((8, 7),), kin=None, belief=True, at=GRAVE, died=DIED, tick=40, estate=(("food", 3), ("water", 1)),
           hunger=0, **overlay):
    """p03 died at `at` on tick `died`, leaving `estate`. The living stand at the cells in `near` (p01, p02, ...) and the
    rest are far away. When `belief` is true those who stand near also believe the death (as sighted at `tick`)."""
    config = config or cfg()
    ledger, world = genesis(config)
    spots = ("p01", "p02", "p04", "p05", "p06")
    far = ((0, 0), (11, 0), (0, 11), (11, 11), (11, 5))
    positions = dict(world.positions)
    for i, who in enumerate(spots):
        positions[who] = near[i] if i < len(near) else far[i]
    positions["p03"] = at
    record = Death("p03", died, at[0], at[1], 300, "starved", (), tuple(estate), "", "")
    things = Things(structures=(Struct("grave", "p03", at[0], at[1], died, 0),), deaths=(record,))
    beliefs = {who: (("death", "p03", at[0], at[1], died, tick - 1, ""),) for who in spots[:len(near)]} if belief else {}
    persona = replace(world.persona, traits={a: (60, 50, 50, 60, 50) for a in world.roster}, lonely={}, beliefs=beliefs)
    parents = {"p01": "p03"} if kin == "child" else {}
    ages = {a: config.adult_at + 10 for a in world.roster}
    world = replace(world, positions=positions, sky=CLEAR_DAY, tick=tick, persona=persona, things=things, died_at={"p03": died},
                    age=ages, thirst={a: 0 for a in world.roster}, hunger={a: 0 for a in world.roster},
                    cold={a: 0 for a in world.roster}, parent=parents, **overlay)
    ledger = give(ledger, "p03", food=dict(estate).get("food", 0), water=dict(estate).get("water", 0))
    return config, replace(ledger, tick=tick), world


def fed(ledger, who, food=2, water=2):
    return give(ledger, who, food=food, water=water)


# --- storage and settings ------------------------------------------------------------------------

def test_header_round_trips_and_the_rule_and_levers_are_written_down():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    rule = config.describe()["feature_rules"]["aftermath"]
    assert "heir_grace" in rule and "grave_range" in rule and "mourn_relief" in rule
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("aftermath",))                       # nobody could learn of a death without beliefs
    for bad in ((("grave_range", 0),), (("heir_grace", 0),), (("grave_margin", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)
    assert "died of old age" in CAUSES and WorldConfig.from_describe(cfg(feature_levers=(("heir_grace", 5),)).describe()).lever("heir_grace") == 5


def test_death_records_and_graves_are_stored_strictly():
    config, ledger, world = buried()
    again = Overlay.from_canonical(json.loads(json.dumps(world.canonical())))
    assert again.things == world.things and again.things.deaths[0].estate == (("food", 3), ("water", 1))
    assert Things().canonical() == {} and not Things()
    good = world.things.deaths[0].canonical()
    for index, bad in ((5, "was eaten by a bear"), (1, -1), (7, [["food", 0]]), (6, [5]), (8, 7), (2, "x")):
        data = list(good)
        data[index] = bad
        with pytest.raises(ValueError):
            Death.from_canonical(data)
    with pytest.raises(ValueError):
        Death.from_canonical(good[:-1])
    twice = world.things.deaths[0]
    with pytest.raises(ValueError):
        Things(deaths=(twice, twice))                                      # a person dies once
    for changes in (dict(died_at={}),                                      # a record for somebody who did not die
                    dict(died_at={"p03": DIED + 1}),                       # on the wrong tick
                    dict(things=Things(structures=(Struct("grave", "p03", 8, 8, DIED + 2, 0),), deaths=world.things.deaths)),    # grave dated wrongly
                    dict(things=Things(structures=(Struct("grave", "p04", 8, 8, DIED, 0),)))):                                   # grave of the living
        with pytest.raises(ValueError):
            replace(world, **changes)
    named = replace(twice, taker="p99")
    with pytest.raises(ValueError):
        replace(world, things=Things(structures=world.things.structures, deaths=(named,)))        # a taker nobody knows


# --- the record and the grave -----------------------------------------------------------------------

def test_a_death_makes_a_grave_and_a_record_of_when_where_how_old_who_saw_and_what_they_held():
    config, ledger, world = buried()
    world = replace(world, things=Things(), died_at={}, tick=40, age={**world.age, "p03": lifespan(config, "p03") - 1},
                    positions={**world.positions, "p03": (8, 8), "p06": (9, 10)})
    ledger = give(ledger, "p03", food=3, water=1)
    step = world_step(Engine(ledger), world, config)
    overlay = step.processed.overlay
    [death] = overlay.things.deaths
    assert (death.person, death.tick, death.cell, death.cause) == ("p03", overlay.tick, (8, 8), "died of old age")
    assert death.age == lifespan(config, "p03") and death.estate == (("food", 3), ("water", 1))
    assert set(death.witnesses) == {a for a in overlay.living if max(abs(overlay.positions[a][0] - 8), abs(overlay.positions[a][1] - 8)) <= config.perception_radius}
    assert "p06" in death.witnesses and "p03" not in death.witnesses
    [grave] = [s for s in overlay.things.structures if s.kind == "grave"]
    assert (grave.owner, grave.cell, grave.a, grave.b) == ("p03", (8, 8), overlay.tick, 0)
    assert overlay.died_at == {"p03": overlay.tick}


def test_each_way_of_dying_is_named_from_the_levels_recorded_at_the_end_of_the_tick():
    config, ledger, world = buried()
    ill = lambda **kw: SimpleNamespace(hunger={"p03": 0}, thirst={"p03": 0}, cold={"p03": 0}, age={"p03": 100},
                                       persona=SimpleNamespace(hurt={"p03": 0}), **kw)
    cases = [(dict(hunger={"p03": config.death_at}), "starved"), (dict(thirst={"p03": config.thirst_death_at}), "died of thirst"),
             (dict(cold={"p03": config.cold_death_at}), "froze to death"), (dict(age={"p03": lifespan(config, "p03")}), "died of old age"),
             (dict(persona=SimpleNamespace(hurt={"p03": config.lever("lethal_hurt")})), "was killed by a wolf"), ({}, "died")]
    for changes, expected in cases:
        current = ill()
        for key, value in changes.items():
            setattr(current, key, value)
        assert cause_of(config, None, current, "p03", lifespan) == expected
    assert set(c for _, c in cases) <= set(CAUSES)


def test_a_person_who_starved_in_a_real_run_is_recorded_as_starved():
    config, ledger, world = buried(estate=())
    world = replace(world, things=Things(), died_at={}, positions={**world.positions, "p03": (8, 8)},
                    hunger={**world.hunger, "p03": config.death_at - 1})
    ledger = give(ledger, "p03", food=0, water=0)
    steps = play(config, ledger, world, 6, sky=CLEAR_DAY)
    deaths = steps[-1].processed.overlay.things.deaths                                      # the record is kept from then on
    assert [d.person for d in deaths] == ["p03"] and deaths[0].cause == "starved"
    step = next(s for s in steps if s.processed.overlay.things.deaths)                       # what the account held when the tick ended
    assert deaths[0].estate == estate_of(step.engine.state, "p03") and deaths[0].tick == step.processed.overlay.tick


def test_the_estate_is_what_the_account_holds_free_of_holds():
    config, ledger, world = buried()
    assert estate_of(ledger, "p03") == (("food", 3), ("water", 1))
    assert estate_of(ledger, "p01") == tuple((r, n) for r, n in (("food", ledger.balances["p01"]),) + tuple(
        (res, ledger.holdings[res]["p01"]) for res in sorted(ledger.holdings)) if n > 0)


# --- who knows ---------------------------------------------------------------------------------------

def test_a_grave_is_seen_only_from_inside_sight_and_a_kin_flag_only_for_deaths_they_know_of():
    config, ledger, world = buried(near=((8, 7), (3, 3)), kin="child", belief=False)
    near, far = observe("p01", ledger, world, config), observe("p02", ledger, world, config)
    assert [g[0] for g in near.graves] == ["p03"] and far.graves == ()
    assert near.graves[0][4] == (("food", 3), ("water", 1)) and near.graves[0][5] == 1
    assert near.kin_dead == frozenset()                                    # a child who has not heard knows of no death
    believing = replace(world, persona=replace(world.persona, beliefs={"p01": (("death", "p03", 8, 8, DIED, 39, ""),)}))
    assert observe("p01", ledger, believing, config).kin_dead == frozenset({"p03"})
    assert heirs(world, world.things.deaths[0]) == {"p01"} and heirs(replace(world, parent={}), world.things.deaths[0]) == set()


def test_seeing_a_grave_files_a_belief_and_grief_follows_one_tick_later_and_only_for_those_who_saw():
    config, ledger, world = buried(near=((8, 7), (3, 3)), kin="child", belief=False,
                                   family=Family())
    steps = play(config, give(ledger, "p01", food=3, water=2), world, 3, sky=CLEAR_DAY)
    first = steps[0].processed.overlay
    beliefs = first.persona.beliefs
    assert any(b[0] == "death" and b[1] == "p03" for b in beliefs.get("p01", ()))
    assert not any(b[0] == "death" for b in beliefs.get("p02", ()))        # out of sight: nothing known
    assert "p01" in first.family.grief and "p02" not in first.family.grief
    assert first.family.grief["p01"] == config.lever("grief_kin")
    assert not any("p02" in s.processed.overlay.family.grief for s in steps)


def test_nobody_far_from_a_death_behaves_any_differently_for_it():
    config, ledger, world = buried(near=((1, 1),), kin="child", belief=False)
    bare = replace(world, things=Things(), died_at={"p03": DIED})
    ledger2 = give(ledger, "p03", food=3, water=1)
    for actor in world.living:
        one = decide(observe(actor, ledger2, world, config), config)
        other = decide(observe(actor, ledger2, bare, config), config)
        assert (one.kind, one.target, one.step) == (other.kind, other.target, other.step), actor


def test_being_told_files_the_belief_with_the_teller_and_only_for_a_listener_who_trusts_and_answers():
    config, ledger, world = buried(near=((3, 3), (3, 4)), belief=False)
    persona = replace(world.persona, bonds={"p02": (bond("p01", 20, 60),)},
                      beliefs={"p01": (("death", "p03", 8, 8, DIED, 39, ""),)})
    world = replace(world, persona=persona)
    told = (("death", "p03", 8, 8, DIED),)
    speak = SimpleNamespace(kind="chat", target="p02", told_to=("p02",), told=told)
    reply = SimpleNamespace(kind="chat", target="p01", told_to=(), told=())
    quiet = SimpleNamespace(kind="rest", target=None, told_to=(), told=())
    observations = {a: observe(a, ledger, world, config) for a in world.living}
    after = replace(world, tick=41)
    out = advance_beliefs(world, after, {"p01": speak, "p02": reply}, observations, config)
    [belief] = [b for b in out["p02"] if b[0] == "death"]
    assert belief[1:] == ("p03", 8, 8, DIED, 40, "p01")                    # kept the date of the death, the tick of telling, the teller
    assert not any(b[0] == "death" for b in advance_beliefs(world, after, {"p01": speak, "p02": quiet}, observations, config).get("p02", ()))
    stranger = replace(world, persona=replace(world.persona, bonds={"p02": (bond("p01", 0, 5),)}))
    assert not any(b[0] == "death" for b in advance_beliefs(stranger, after, {"p01": speak, "p02": reply}, observations, config).get("p02", ()))


def test_grief_comes_only_from_a_death_somebody_has_just_learned_of():
    config, ledger, world = buried(near=((8, 7), (8, 6)), kin="child", belief=False)
    parent_of_both = replace(world, parent={"p01": "p03", "p02": "p03"})
    before = replace(parent_of_both, family=Family())
    now = replace(parent_of_both, tick=41, persona=replace(parent_of_both.persona, beliefs={
        "p01": (("death", "p03", 8, 8, DIED, 40, ""),)}))                                  # only p01 learned it, and just now
    grieved = advance_family(before, now, config)
    assert grieved.grief == {"p01": config.lever("grief_kin")}                              # p02 is a child of the dead too, but heard nothing
    older = replace(now, persona=replace(now.persona, beliefs={"p01": (("death", "p03", 8, 8, DIED, 35, ""),)}))
    assert advance_family(before, older, config).grief == {}                               # learned some time ago: grief was then
    friend = replace(now, parent={}, persona=replace(now.persona, bonds={"p01": (bond("p03", 25),)}))
    assert advance_family(before, friend, config).grief == {"p01": config.lever("grief_friend")}


# --- collecting what was left -------------------------------------------------------------------------

def run_until_collected(config, ledger, world, limit=40):
    steps = play(config, ledger, world, limit, sky=CLEAR_DAY)
    for n, step in enumerate(steps):
        if any(d.taker for d in step.processed.overlay.things.deaths):
            return steps[:n + 1]
    return steps


def test_a_child_who_knows_walks_to_the_grave_and_collects_everything_by_transfers_in_the_dead_persons_name():
    config, ledger, world = buried(near=((5, 5),), kin="child")
    ledger = give(ledger, "p01", food=1, water=1)
    steps = run_until_collected(config, ledger, world)
    last = steps[-1]
    [death] = last.processed.overlay.things.deaths
    assert death.taker == "p01" and death.estate == (("food", 3), ("water", 1))              # the record keeps what was there
    moves = [o for s in steps for o in s.record.outcomes if o.operation == "transfer" and o.actor == "p03"]
    assert moves and all(o.accepted for o in moves)                                          # every unit moved by a kernel transfer from their account
    assert {e.account for o in moves for e in o.effects} <= {"actor:p03", "actor:p01", "actor@water:p03", "actor@water:p01"}
    final = last.engine.state
    assert final.balances["p03"] == 0 and final.holdings["water"]["p03"] == 0
    assert final.balances["p01"] == 1 + 3 and final.holdings["water"]["p01"] == 1 + 1
    assert [s for s in last.processed.overlay.things.structures if s.kind == "grave"][0].b == 1
    walked = [s.decisions["p01"].kind for s in steps]
    assert "go_grave" in walked and walked[-1] == "collect"
    assert steps[0].decisions["p01"].reason.startswith("walking")


def test_strangers_wait_out_the_grace_and_only_take_it_when_they_need_it():
    config, ledger, world = buried(near=((8, 8),))
    grace = config.lever("heir_grace")
    fed_ledger = give(ledger, "p01", food=2, water=2)
    hungry = give(ledger, "p01", food=0, water=2)
    early = replace(world, tick=DIED + grace - 1)
    late = replace(world, tick=DIED + grace)
    assert decide(observe("p01", replace(fed_ledger, tick=late.tick), late, config), config).kind != "collect"          # fed: no need
    assert decide(observe("p01", replace(hungry, tick=early.tick), early, config), config).kind != "collect"            # hungry, but too soon
    d = decide(observe("p01", replace(hungry, tick=late.tick), late, config), config)
    assert d.kind == "collect" and d.target == "p03" and d.estate == (("food", 3), ("water", 1))


def test_nobody_collects_from_a_grave_they_do_not_know_of_even_when_standing_on_it():
    config, ledger, world = buried(near=((8, 8),), belief=False)                              # on the cell: they see it, so they know
    late, empty = replace(world, tick=DIED + 200), replace(give(ledger, "p01", food=0, water=0), tick=DIED + 200)
    stepped = world_step(Engine(empty), late, config)
    assert any(b[0] == "death" for b in stepped.processed.overlay.persona.beliefs.get("p01", ()))      # standing there, they learn of it
    far_config, far_ledger, far_world = buried(near=((0, 0),), belief=False)
    for actor in far_world.living:
        starving = replace(give(far_ledger, actor, food=0, water=0), tick=DIED + 200)
        assert decide(observe(actor, starving, replace(far_world, tick=DIED + 200), far_config), far_config).kind != "collect"


def test_two_collectors_at_the_grave_in_one_tick_share_nothing_twice():
    config, ledger, world = buried(near=((8, 8), (8, 7)), kin="child")
    world = replace(world, parent={"p01": "p03", "p02": "p03"})
    ledger = give(give(ledger, "p01", food=0, water=0), "p02", food=0, water=0)
    steps = run_until_collected(config, ledger, world, limit=12)
    final = steps[-1].engine.state
    assert final.balances["p01"] + final.balances["p02"] == 3 and final.holdings["water"]["p01"] + final.holdings["water"]["p02"] == 1
    taker = steps[-1].processed.overlay.things.deaths[0].taker
    assert taker in ("p01", "p02")
    accepted = [o for s in steps for o in s.record.outcomes if o.operation == "transfer" and o.actor == "p03" and o.accepted]
    receivers = {next(e.account for e in o.effects if e.delta > 0) for o in accepted}
    assert f"actor:{taker}" in receivers


def test_a_gift_given_on_the_tick_somebody_dies_is_not_a_collection():
    from world.aftermath import advance_aftermath
    config, ledger, world = buried(near=((8, 8),), kin="child")
    effects = [SimpleNamespace(account="actor:p03", delta=-1), SimpleNamespace(account="actor:p01", delta=1)]
    record = SimpleNamespace(outcomes=[SimpleNamespace(operation="transfer", accepted=True, actor="p03", effects=effects)])
    before, dying = replace(world, died_at={}, things=Things()), replace(world, things=Things())
    # p03 gave a unit away in the very tick they died: the record names no taker and the grave is not marked collected
    deaths, structs = advance_aftermath(before, dying, {}, record, ledger, config)
    assert [d.taker for d in deaths] == [""] and [s.b for s in structs if s.kind == "grave"] == [0]
    # the same transfer on a later tick, from an account that was already dead, is the collection
    deaths, structs = advance_aftermath(world, replace(world, tick=world.tick + 1), {}, record, ledger, config)
    assert [d.taker for d in deaths] == ["p01"] and [s.b for s in structs if s.kind == "grave"] == [1]


def test_a_grave_with_nothing_left_has_nothing_to_collect():
    config, ledger, world = buried(near=((8, 8),), kin="child", estate=())
    d = decide(observe("p01", give(ledger, "p01", food=2, water=2), world, config), config)
    assert d.kind != "collect"


def test_somebody_who_has_seen_a_grave_with_nothing_left_in_it_does_not_walk_back_to_it():
    config, ledger, world = buried(near=((8, 7),), kin="child", estate=(), belief=False)
    ledger = give(ledger, "p01", food=3, water=3)
    step = world_step(Engine(ledger), world, config)
    beliefs = step.processed.overlay.persona.beliefs["p01"]
    assert {b[0] for b in beliefs} == {"death", "empty"}                                      # seen: the grave, and that it is empty
    far = replace(world, positions={**world.positions, "p01": (1, 1)}, persona=replace(world.persona, beliefs={"p01": beliefs}))
    assert decide(observe("p01", ledger, far, config), config).kind != "go_grave"
    # without the memory of having seen it empty, an heir within reach would go (the old behaviour: a shuttle between emptied graves)
    config2, ledger2, near = buried(near=((6, 8),), kin="child", belief=True)
    assert decide(observe("p01", give(ledger2, "p01", food=3, water=3), near, config2), config2).kind == "go_grave"
    emptied = replace(near, persona=replace(near.persona, beliefs={"p01": (("death", "p03", 8, 8, DIED, 39, ""), ("empty", "p03", 8, 8, 39, 39, ""))}))
    assert decide(observe("p01", give(ledger2, "p01", food=3, water=3), emptied, config2), config2).kind != "go_grave"


def test_a_grave_seen_long_after_the_death_is_still_believed_and_a_belief_fades_from_the_day_it_was_learned():
    config, ledger, world = buried(near=((8, 7),), kin="child", belief=False, tick=DIED + 400)
    ledger = give(ledger, "p01", food=3, water=3)
    after = world_step(Engine(ledger), world, config).processed.overlay
    assert any(b[:2] == ("death", "p03") for b in after.persona.beliefs.get("p01", ()))      # older than memory_span by the death date, new by the sighting
    from world.belief import file_beliefs
    span = config.lever("memory_span")
    old = (("death", "p03", 8, 8, DIED, DIED + 5, ""),)
    assert file_beliefs(old, (), DIED + 5 + span, config) == old and file_beliefs(old, (), DIED + 6 + span, config) == ()


def test_a_parent_does_not_know_a_far_childs_death_until_they_see_the_grave_or_are_told():
    config = cfg(births_on=True, childhood_on=True)
    config, ledger, world = buried(config=config, near=((0, 0),), belief=False)
    child = replace(world, parent={"p03": "p01"}, age={**world.age, "p03": 5})                 # p03 is p01's child, dead, 8 steps away and unseen
    alive = replace(child, died_at={}, things=Things())
    ledger = give(ledger, "p01", food=3, water=3)
    dead_view, alive_view = observe("p01", ledger, child, config), observe("p01", ledger, alive, config)
    assert dead_view.dependents == alive_view.dependents == frozenset({"p03"})               # the same to a parent who has not heard
    told = replace(child, persona=replace(child.persona, beliefs={"p01": (("death", "p03", 8, 8, DIED, 39, "p02"),)}))
    assert observe("p01", ledger, told, config).dependents == frozenset()                    # once they know, the child is no longer somebody to care for
    plain = cfg(features=tuple(f for f in FEATURES if f != "aftermath"), births_on=True, childhood_on=True)
    assert observe("p01", ledger, replace(child, things=Things(), persona=world.persona), plain).dependents == frozenset()   # without graves: the older rule, unchanged


# --- mourning -----------------------------------------------------------------------------------------

def test_somebody_grieving_goes_to_the_grave_and_stands_there_and_the_grief_lifts_faster():
    config, ledger, world = buried(near=((8, 7),), kin="child", estate=())
    world = replace(world, family=Family(grief={"p01": 60}))
    ledger = give(ledger, "p01", food=2, water=2)
    d = decide(observe("p01", ledger, world, config), config)
    assert d.kind == "go_grave" and "p03" in d.reason and d.step is not None                 # one step away: walks there first
    at = replace(world, positions={**world.positions, "p01": (8, 8)})
    assert decide(observe("p01", ledger, at, config), config).kind == "mourn"
    quiet = replace(at, tick=39)                                                              # a tick away from any fade step
    mourning = world_step(Engine(replace(ledger, tick=39)), quiet, config).processed.overlay.family.grief["p01"]
    elsewhere = replace(quiet, positions={**quiet.positions, "p01": (3, 8)})
    away = world_step(Engine(replace(ledger, tick=39)), elsewhere, config).processed.overlay.family.grief.get("p01", 0)
    assert mourning == away - config.lever("mourn_relief")


# --- whole worlds -------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("aftermath") / "run.jsonl"
    config = WorldConfig(seed=23, features=tuple(sorted(set(FEATURES) | {"pledges", "sleep", "structures", "crafting", "farming"})),
                         wood_on=True)
    run_world(config, 700, path)
    return path, read_run(path)


@pytest.mark.long_run
def test_a_world_with_graves_audits_and_replays_and_every_collection_is_a_recorded_kernel_transfer(saved):
    path, run = saved
    assert run.complete and audit_run(run) == [] and replay_world(path).identical
    last = run.ticks[-1]["world"]
    deaths = {d[0]: d for d in (last.get("things") or {}).get("deaths", [])}
    graves = {s[1]: s for s in (last.get("things") or {}).get("structures", []) if s[0] == "grave"}
    assert deaths and set(deaths) == set(graves) == set(last["died_at"])                      # a record and a marker for every death, no more
    taken = {}
    for k, tick in enumerate(run.ticks, start=1):
        for o in tick["record"]["outcomes"]:
            if o["operation"] == "transfer" and o["accepted"] and o["actor"] in deaths and k > deaths[o["actor"]][1]:     # not a gift made while alive
                to = next(e["account"].rsplit(":", 1)[-1] for e in o["effects"] if e["delta"] > 0)
                taken.setdefault(o["actor"], (k, to))
    assert {p for p, d in deaths.items() if d[8]} == set(taken)                                # a taker is named exactly where a transfer left the account
    for person, (k, to) in taken.items():
        assert deaths[person][8] == to and k >= deaths[person][1]                              # collected after the death, by who the record names
        assert graves[person][5] == 1
    assert taken, "this seed should see at least one collection"


@pytest.mark.long_run
def test_every_belief_of_a_death_was_seen_at_the_grave_or_told_and_every_grief_follows_news(saved):
    _, run = saved
    config = WorldConfig.from_describe(run.header["scenario"])
    worlds = [run.header["world"]] + [t["world"] for t in run.ticks]
    reach = config.perception_radius + (config.lever("fire_light") if config.on("structures") else 0)
    seen = told = 0
    for k in range(1, len(worlds)):
        before = worlds[k - 1]["persona"].get("beliefs") or {}
        now = worlds[k]["persona"].get("beliefs") or {}
        deaths = {d[0]: d for d in (worlds[k - 1].get("things") or {}).get("deaths", [])}
        for actor, entries in now.items():
            known = {(e[0], e[1]): e for e in before.get(actor, [])}
            for kind, subject, x, y, when, learned, via in entries:
                if kind != "death" or (kind, subject) in known:
                    continue
                assert subject in deaths and (x, y) == tuple(deaths[subject][2:4]) and when == deaths[subject][1]      # true: they died there then
                if via:
                    teller = {(e[0], e[1]) for e in before.get(via, [])}
                    assert ("death", subject) in teller or ("death", subject) in {(e[0], e[1]) for e in (worlds[k]["persona"].get("beliefs") or {}).get(via, [])}
                    told += 1
                else:
                    px, py = worlds[k - 1]["positions"][actor]
                    assert max(abs(px - x), abs(py - y)) <= reach                             # they were in sight of the grave
                    seen += 1
        fb, fw = (worlds[k - 1].get("family") or {}).get("grief") or {}, (worlds[k].get("family") or {}).get("grief") or {}
        for actor, level in fw.items():
            if level > fb.get(actor, 0):
                assert any(e[0] == "death" and e[5] == k - 1 and e[1] in worlds[k]["died_at"] for e in now.get(actor, [])), (k, actor)
    assert seen >= 3                                                                              # being told is rare in a world this quiet; the rule is tested above


@pytest.mark.long_run
def test_the_page_for_a_world_with_graves_shows_the_events_derived_from_the_record(saved):
    from world.viewer_index import build_index
    _, run = saved
    index = build_index(run)
    kinds = {e["kind"] for e in index["events"]}
    assert {"grave", "collected", "learned_death"} <= kinds
    for event in (e for e in index["events"] if e["kind"] == "collected"):
        record = {d[0]: d for d in run.ticks[event["k"] - 1]["world"]["things"]["deaths"]}
        assert record[event["other"]][8] == event["who"]
    plain_path = _plain(saved[0].parent)
    plain = {e["kind"] for e in build_index(read_run(plain_path))["events"]}
    assert not {"grave", "collected", "learned_death"} & plain                                  # an ordinary world gains none of it


def _plain(directory):
    path = directory / "plain.jsonl"
    if not path.exists():
        run_world(WorldConfig(seed=11), 60, path)
    return path


def test_the_index_names_old_age_only_when_nothing_else_was_near_killing_them():
    from world.viewer_family import family_events
    cfg = {"features": ["family"], "feature_levers": {"old_age_at": 480}, "death_at": 80, "thirst_death_at": 80, "cold_death_at": 80}
    before = {"positions": {"a": [0, 0]}, "hunger": {"a": 5}, "thirst": {"a": 5}, "cold": {"a": 0}, "age": {"a": 521}}
    after = {"positions": {"a": [0, 0]}, "died_at": {"a": 1}, "age": {"a": 521}}
    run = SimpleNamespace(ticks=[{"decisions": {}}])
    assert [e["kind"] for e in family_events(run, [before, after], cfg)] == ["old_age"]
    parched = {**before, "thirst": {"a": 79}}
    assert family_events(run, [parched, after], cfg) == []                                     # a thirst death at that age is not old age
    recorded = {**after, "things": {"deaths": [["a", 1, 0, 0, 521, "froze to death", [], [], "", ""]]}}
    assert family_events(run, [before, recorded], cfg) == []                                   # the run says what killed them
    recorded["things"]["deaths"][0][5] = "died of old age"
    assert [e["kind"] for e in family_events(run, [parched, recorded], cfg)] == ["old_age"]


def test_units_a_dead_helper_had_on_hold_are_part_of_the_estate_and_can_be_collected_once_released():
    from tests.test_pledges import RAIN_NIGHT, scene as pledge_scene
    from world.family import lifespan
    config = cfg(features=tuple(sorted(set(FEATURES) | {"pledges"})), childhood_on=True, births_on=True)
    config, ledger, world = pledge_scene(config, water=(0, 1), food=(2, 0), traits={"p02": (80, 50, 50, 50, 50)})
    world = replace(world, age={a: config.adult_at + 5 for a in world.roster})
    steps = play(config, ledger, world, 2, sky=RAIN_NIGHT)                                  # p02 has promised their one water to p01
    w = steps[-1].processed.overlay
    assert any(p.state == "promised" and p.action for p in w.pledges.open)
    w = replace(w, age={**w.age, "p02": lifespan(config, "p02") - 1}, sky=RAIN_NIGHT)       # and dies of old age with it still on hold
    step = world_step(steps[-1].engine, w, config)
    [death] = step.processed.overlay.things.deaths
    assert dict(death.estate).get("water") == 1                                             # the record counts the held unit
    engine, overlay = step.engine, step.processed.overlay
    for _ in range(3):
        later = world_step(engine, replace(overlay, sky=RAIN_NIGHT), config)
        engine, overlay = later.engine, later.processed.overlay
    assert not later.committed.reservations and later.committed.availability()["actor@water:p02"] == 1     # released: free to take
    view = observe("p01", later.committed, overlay, config)
    graves = [g for g in view.graves if g[0] == "p02"]                                      # p01 is two steps away: in sight
    assert graves and graves[0][4] == (("water", 1),) and graves[0][6] == 1                 # it lies there to take, and the grave is not empty
    assert not any(b[0] == "empty" for b in overlay.persona.beliefs.get("p01", ()))
