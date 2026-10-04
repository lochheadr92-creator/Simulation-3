"""Asking for help and keeping a word: requests, promises backed by kernel reservations, building together, news.

The stored pledges and each rule are checked on their own with hand-built situations that run through the
real tick (`world_step`): who hears a request, how a person answers, what a promise holds, how it ends and what
that does to the people in it. Then what a person can know (they decide from what they see and remember, never from
what is stored about somebody else), and whole saved worlds: every ending is recorded once, every reservation the
kernel holds belongs to a promise, every hand-over is a settled outcome, and replay, recovery and the ledger audit agree.
"""

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from kernel import Engine, reserve
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from world.config import WorldConfig, genesis
from world.decide import HOST, Decision, decide
from world.observe import observe
from world.overlay import Overlay
from world.persona import Persona
from world.pledges import GO_HELP, HELP, KINDS, Closed, Pledge, Pledges, REASONS, advance_pledges, views
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world, world_step
from world.sky import Sky
from world.society import find
from world.things import Things
from world.wolves import Wolf
from world.viewer import render_html
from world.viewer_index import build_index

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ("beliefs", "bonds", "explain", "personality", "pledges", "skills", "sky", "steady", "wolves")
RAIN_NIGHT = Sky("night", "rain", 3, 100)
CLEAR_DAY = Sky("day", "clear", 14, 20)
STORM = Sky("night", "storm", 1, 100)
NIGHT = Sky("night", "clear", 7, 100)


def cfg(**changes):
    base = dict(seed=7, features=FEATURES, starting_water=2, building_on=False)
    return WorldConfig(**{**base, **changes})


def bond(other, level=0, trust=50, grudge=0, last=0, why="", grieved=0, tone=""):
    return (other, level, trust, grudge, last, why, grieved, tone)


def give(ledger, actor, food=None, water=None, wood=None):
    balances = dict(ledger.balances)
    holdings = {resource: dict(held) for resource, held in ledger.holdings.items()}
    if food is not None:
        balances[actor] = food
    if water is not None:
        holdings["water"][actor] = water
    if wood is not None and "wood" in holdings:
        holdings["wood"][actor] = wood
    return replace(ledger, balances=balances, holdings=holdings)


def scene(config=None, sky=RAIN_NIGHT, tick=40, at=((1, 7), (1, 6)), thirst=30, cold=20, water=(0, 2), food=(3, 3),
          traits=None, bonds=None, beliefs=None, wood=(0, 0), **overlay):
    """p01 and p02 side by side at p01's door (the rest far away). p01 is thirsty with no water and the rain keeps them in."""
    config = config or cfg()
    ledger, world = genesis(config)
    positions = dict(world.positions)
    positions["p01"], positions["p02"] = at
    for who, spot in zip(("p03", "p04", "p05", "p06"), ((8, 8), (0, 1), (6, 1), (9, 11))):
        positions[who] = spot
    temperament = {actor: (60, 50, 50, 50, 50) for actor in world.roster}
    temperament.update(traits or {})
    persona = replace(world.persona, traits=temperament, bonds=bonds or {}, beliefs=beliefs or {}, lonely={})
    world = replace(world, positions=positions, sky=sky, tick=tick, persona=persona,
                    thirst={**world.thirst, "p01": thirst}, cold={**world.cold, "p01": cold}, **overlay)
    for actor, w, f, d in zip(("p01", "p02"), water, food, wood):
        ledger = give(ledger, actor, food=f, water=w, wood=d)
    return config, replace(ledger, tick=tick), world


def play(config, ledger, world, ticks, sky=None, edit=None):
    """Run the real tick `ticks` times; `sky` is imposed again each tick, `edit(world)` may change the world between ticks."""
    engine, steps = Engine(ledger), []
    for _ in range(ticks):
        step = world_step(engine, world, config)
        steps.append(step)
        world, engine = step.processed.overlay, step.engine
        if sky is not None:
            world = replace(world, sky=sky)
        if edit is not None:
            world = edit(world)
    return steps


def available(step, actor, resource="water"):
    key = f"actor@{resource}:{actor}" if resource else f"actor:{actor}"
    return step.committed.availability()[key]


def pledges_of(step):
    return step.processed.overlay.pledges


def ended(step):
    return [(c.kind, c.asker, c.helper, c.outcome, c.reason) for c in pledges_of(step).closed]


# --- configuration and storage ---------------------------------------------------------------

def test_header_round_trips_and_the_settings_are_validated():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert "pledges" in config.describe()["feature_rules"]
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("beliefs", "pledges"))                      # pledges need bonds
    with pytest.raises(ValueError):
        cfg(requests_on=True)                                                    # one way of asking, not two
    for bad in ((("ask_wait", 0),), (("promise_span", 0),), (("ask_wait", 50),), (("accept_trust", 101),),
                (("help_range", 0),), (("build_ask", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)
    assert cfg(feature_levers=(("place_wait", 9),)).lever("place_wait") == 9


def pledge(**changes):
    base = dict(kind="water", asker="p01", helper="p02", state="asked", made=5, due=8, amount=1, place=(1, 7))
    return Pledge(**{**base, **changes})


def test_pledges_survive_the_canonical_form_and_are_validated():
    ask = pledge()
    promised = pledge(asker="p03", helper="p04", state="promised", held=1, action="action:abc", heard=1, arrived=7,
                      done=0, due=45)
    block = Pledges(open=(ask, promised), closed=(Closed("food", "p05", "p06", "declined", "busy", 9),),
                    release=(("p02", "action:old"),))
    again = Pledges.from_canonical(json.loads(json.dumps(block.canonical())))
    assert again == block
    block.check({"p01", "p02", "p03", "p04", "p05", "p06"}, 10)
    assert not Pledges() and Pledges().canonical() == {}


@pytest.mark.parametrize("changes", [
    dict(kind="gold"), dict(state="done"), dict(asker="p09"), dict(helper="p01"), dict(made=99), dict(due=2),
    dict(amount=0), dict(held=2), dict(held=1), dict(action="action:x"),               # units without a reservation and the reverse
    dict(heard=1), dict(arrived=3), dict(done=1),                                      # an unanswered request has none of these
    dict(state="promised", kind="news"), dict(state="promised", held=2, action="a"),    # news is never promised; held more than asked
    dict(state="promised", kind="build", held=1, action="a"),                          # work holds no units
])
def test_a_pledge_in_a_saved_run_is_checked_strictly(changes):
    with pytest.raises(ValueError):
        Pledges(open=(pledge(**changes),)).check({"p01", "p02"}, 10)


def test_nobody_has_two_open_requests_or_two_promises_and_endings_must_be_known():
    roster = {"p01", "p02", "p03", "p04"}
    with pytest.raises(ValueError):
        Pledges(open=(pledge(), pledge(helper="p03", made=6))).check(roster, 10)                     # one asker, two requests
    held = dict(state="promised", held=1, action="a")
    with pytest.raises(ValueError):
        Pledges(open=(pledge(**held), pledge(asker="p03", **held))).check(roster, 10)              # one helper, two promises
    for bad in (Closed("water", "p01", "p02", "won", "busy", 5), Closed("water", "p01", "p02", "declined", "spite", 5),
                Closed("water", "p01", "p01", "declined", "busy", 5), Closed("water", "p01", "p02", "declined", "busy", 99)):
        with pytest.raises(ValueError):
            Pledges(closed=(bad,)).check(roster, 10)
    with pytest.raises(ValueError):
        Pledges(release=(("p09", "a"),)).check(roster, 10)
    with pytest.raises(ValueError):
        Pledges.from_canonical({"open": [], "extra": 1})


def test_the_overlay_carries_pledges_and_refuses_an_unknown_person_in_one():
    config, ledger, world = scene()
    block = Pledges(open=(pledge(),))
    held = replace(world, pledges=block)
    assert Overlay.from_canonical(json.loads(json.dumps(held.canonical()))) == held
    with pytest.raises(ValueError):
        replace(world, pledges=Pledges(open=(pledge(helper="p99"),)))
    assert "pledges" not in world.canonical()                                                     # nothing open: nothing written


# --- what each person can know of a request ---------------------------------------------------

def test_only_the_one_asked_hears_a_request_and_only_while_the_asker_is_in_sight():
    config, ledger, world = scene()
    open_ = Pledges(open=(pledge(made=40, due=43),))
    world = replace(world, pledges=open_)
    near = observe("p02", ledger, world, config)
    assert near.pledge_requests == (("p01", "water", 1, 1, 7),) and near.pledge_asked == ()
    asker = observe("p01", ledger, world, config)
    assert asker.pledge_requests == () and asker.pledge_asked == (("p01@40", "water", "p02", "asked", 40, 43),)
    bystander = observe("p05", ledger, world, config)
    assert bystander.pledge_requests == () and bystander.pledge_asked == () and bystander.pledge_owed == ()
    far = replace(world, positions={**world.positions, "p02": (8, 2)})            # out of sight: the request is lost on them
    assert observe("p02", ledger, far, config).pledge_requests == ()


def test_a_promise_is_the_helpers_own_memory_and_the_asker_knows_it_only_once_they_have_heard_it():
    config, ledger, world = scene()
    promised = pledge(made=40, due=80, state="promised", held=1, action="action:abc", heard=0)
    world = replace(world, pledges=Pledges(open=(promised,)))
    helper = observe("p02", ledger, world, config)
    assert helper.pledge_owed[0][:4] == ("p01@40", "water", "p01", 1) and helper.pledge_owed[0][7:9] == (1, "action:abc")
    assert observe("p01", ledger, world, config).pledge_asked[0][3] == "asked"      # not heard: still waiting to be told
    heard = replace(world, pledges=Pledges(open=(replace(promised, heard=1),)))
    assert observe("p01", ledger, heard, config).pledge_asked[0][3] == "promised"
    assert observe("p02", ledger, heard, config).pledge_requests == ()               # a promise is no longer a question


def test_what_is_carried_in_sight_is_seen_but_a_promise_held_back_is_not_free_to_use():
    config, ledger, world = scene()
    assert observe("p01", ledger, world, config).others[0].water == 2
    engine = Engine(give(ledger, "p02", water=2))
    engine.tick([reserve("hold", "p02", 0, operation="transfer", params={"to": "p01", "amount": 1, "resource": "water"})])
    state = engine.state
    mine = observe("p02", state, replace(world, tick=state.tick), config)
    assert mine.water == 1                                                               # the reserved unit is not theirs to drink or give
    assert observe("p01", state, replace(world, tick=state.tick), config).others[0].water == 1


# --- answering --------------------------------------------------------------------------------

def helper_view(config, ledger, world, kind="water", amount=1, **overrides):
    request = Pledges(open=(pledge(kind=kind, amount=amount, made=world.tick, due=world.tick + 3),))
    world = replace(world, pledges=request, **overrides)
    return observe("p02", ledger, world, config), world


def answer_of(config, ledger, world, kind="water", amount=1, **overrides):
    view, _ = helper_view(config, ledger, world, kind, amount, **overrides)
    return decide(view, config).answered


def test_a_helper_with_water_to_spare_says_yes_and_reserves_the_unit():
    config, ledger, world = scene()
    (asker, kind, verdict, reason, held), = answer_of(config, ledger, world)
    assert (asker, kind, verdict, held) == ("p01", "water", "yes", 1)


@pytest.mark.parametrize("why, make", [
    ("no_trust", lambda w: replace(w, persona=replace(w.persona, bonds={"p02": (bond("p01", 30, 50, 15, 30, "quarrel", 30),)}))),
    ("no_trust", lambda w: replace(w, persona=replace(w.persona, bonds={"p02": (bond("p01", 30, 10),)}))),         # trust below the line
    ("unwilling", lambda w: replace(w, persona=replace(w.persona, traits={**w.persona.traits, "p02": (10, 50, 50, 50, 50)}))),
    ("unfit", lambda w: replace(w, sky=STORM)),
])
def test_a_helper_says_no_and_gives_the_reason(why, make):
    config, ledger, world = scene()
    world = make(world)
    (_, _, verdict, reason, held), = answer_of(config, ledger, world)
    assert (verdict, reason, held) == ("no", why, 0)


def test_a_helper_too_far_away_to_bother_says_so():
    config, ledger, world = scene(cfg(feature_levers=(("help_range", 1),)), at=((1, 7), (1, 5)))
    (_, _, verdict, reason, held), = answer_of(config, ledger, world)
    assert (verdict, reason, held) == ("no", "too_far", 0)


def test_with_nothing_to_spare_a_helper_says_so_and_a_generous_one_keeps_nothing_back():
    config, ledger, world = scene(water=(0, 1))
    stingy = replace(world, persona=replace(world.persona, traits={**world.persona.traits, "p02": (60, 50, 50, 50, 50)}))
    assert answer_of(config, ledger, stingy)[0][2:4] == ("no", "nothing_to_spare")           # one unit and not generous: they keep it
    generous = replace(world, persona=replace(world.persona, traits={**world.persona.traits, "p02": (80, 50, 50, 50, 50)}))
    assert answer_of(config, ledger, generous)[0][2:4] == ("yes", "agreed")
    config2, ledger2, world2 = scene(water=(0, 0))
    assert answer_of(config2, ledger2, world2)[0][2:4] == ("no", "nothing_to_spare")


def test_a_helper_whose_own_need_cannot_wait_says_no():
    config, ledger, world = scene()
    parched = replace(world, thirst={**world.thirst, "p02": 76})                         # almost dead of thirst: not the time
    assert answer_of(config, ledger, parched)[0][2:4] == ("no", "need_it_myself")


def test_a_helper_already_promised_to_somebody_is_busy_so_nobody_has_two_promises():
    config, ledger, world = scene()
    view, world = helper_view(config, ledger, world)
    busy = replace(view, pledge_owed=(("p03@30", "food", "p03", 1, 8, 8, 70, 1, "action:x", 0, 0),))
    assert decide(busy, config).answered[0][2:4] == ("no", "busy")
    two = replace(view, pledge_requests=view.pledge_requests + (("p03", "water", 1, 8, 8),))
    verdicts = [a[2] for a in decide(two, config).answered]
    assert verdicts.count("yes") == 1                                                      # two at once: one yes at most


def test_a_friend_is_helped_by_somebody_stingy_when_a_stranger_would_not_be():
    config, ledger, world = scene(traits={"p02": (10, 50, 50, 50, 50)})
    friend = replace(world, persona=replace(world.persona, bonds={"p02": (bond("p01", 40),)}))
    assert answer_of(config, ledger, friend)[0][2] == "yes"                                 # stingy, but a friend


def test_wood_in_hand_is_spare_only_beyond_what_their_own_shelter_still_needs():
    config = cfg(wood_on=True, building_on=True)
    config, ledger, world = scene(config, sky=CLEAR_DAY, thirst=0, cold=0, wood=(0, 2))
    assert answer_of(config, ledger, world, "wood")[0][2:4] == ("no", "nothing_to_spare")    # unhoused and saving it
    housed = replace(world, shelters=tuple(sorted(set(world.shelters) | {world.homes["p02"]})))
    assert answer_of(config, ledger, housed, "wood")[0][2:5] == ("yes", "agreed", 1)
    empty_handed = give(ledger, "p02", wood=0)
    assert answer_of(config, empty_handed, housed, "wood")[0][2:5] == ("yes", "agreed", 0)   # housed and free: will fetch it


def test_news_is_given_only_when_the_helper_knows_something_fresher_than_the_ask_assumes():
    config, ledger, world = scene(sky=CLEAR_DAY, thirst=0, cold=0)
    fresh = replace(world, persona=replace(world.persona, beliefs={"p02": (("wolf", "w1", 4, 4, 38, 38, ""),)}))
    stale = replace(world, persona=replace(world.persona, beliefs={"p02": (("wolf", "w1", 4, 4, 5, 5, ""),)}))
    assert answer_of(config, ledger, fresh, "news")[0][2:4] == ("yes", "told")
    assert answer_of(config, ledger, stale, "news")[0][2:4] == ("no", "nothing_known")
    assert answer_of(config, ledger, world, "news")[0][2:4] == ("no", "nothing_known")
    view, w = helper_view(config, ledger, fresh, "news")
    told = decide(view, config)
    assert told.told_to == ("p01",) and told.told == (("wolf", "w1", 4, 4, 38),)               # the original date, not today's


# --- asking -----------------------------------------------------------------------------------

def asks(config, ledger, world, who="p01"):
    view = observe(who, ledger, world, config)
    return decide(view, config).asked


def test_somebody_held_in_by_the_rain_and_short_of_water_asks_the_one_who_carries_some():
    config, ledger, world = scene()
    assert asks(config, ledger, world) == (("p02", "water", 1),)
    assert asks(*scene(water=(0, 0))) == ()                                                  # nobody in sight carries any
    assert asks(*scene(sky=CLEAR_DAY)) == ()                                                 # nothing holds them: they go themselves
    assert asks(*scene(sky=STORM)) == ()                                                     # nobody sets out in a storm
    far = scene(at=((1, 7), (1, 1)))
    assert asks(*far) == ()                                                                  # beyond help_range


def test_the_person_asked_is_the_best_liked_and_never_somebody_resented_or_asked_a_moment_ago():
    config, ledger, world = scene()
    positions = {**world.positions, "p03": (2, 7)}
    ledger = give(ledger, "p03", water=2)
    world = replace(world, positions=positions)
    assert asks(config, ledger, world)[0][0] == "p02"                                         # the nearer of two strangers
    liked = replace(world, persona=replace(world.persona, bonds={"p01": (bond("p03", 40),)}))
    assert asks(config, ledger, liked)[0][0] == "p03"                                         # a friend first
    resented = replace(world, persona=replace(world.persona, bonds={"p01": (bond("p02", 40, grudge=15, why="quarrel", grieved=3),)}))
    assert asks(config, ledger, resented)[0][0] == "p03"
    lately = replace(world, persona=replace(world.persona, tried={"p01": (("ask", "p02", 36, 0),)}))
    assert asks(config, ledger, lately)[0][0] == "p03"
    both = replace(lately, persona=replace(lately.persona, bonds={"p01": (bond("p03", 0, grudge=15, why="quarrel", grieved=3),)}))
    assert asks(config, ledger, both) == ()


def test_nobody_has_two_open_requests_and_nobody_asks_asleep_or_away_from_home():
    config, ledger, world = scene()
    open_ = replace(world, pledges=Pledges(open=(pledge(made=40, due=43),)))
    assert asks(config, ledger, open_) == ()
    asleep = replace(world, persona=replace(world.persona, asleep={"p01": 35}))
    assert asks(config, ledger, asleep) == ()
    away = replace(world, positions={**world.positions, "p01": (2, 7), "p02": (2, 6)})
    assert asks(config, ledger, away) == ()                                                  # only from home: that is where they said they would be


# --- a promise, kept ---------------------------------------------------------------------------

def handed_over(steps):
    """The step on which a promised hand-over was settled (a `complete` of the helper's reservation)."""
    return next(i for i, step in enumerate(steps) if any(p.operation == "complete" for p in step.proposals))


def test_a_request_is_answered_a_promise_reserves_the_unit_and_it_is_handed_over():
    config, ledger, world = scene()
    steps = play(config, ledger, world, 10, sky=RAIN_NIGHT)
    first, second = steps[0], steps[1]
    assert first.decisions["p01"].asked == (("p02", "water", 1),)
    assert [(p.state, p.helper) for p in pledges_of(first).open] == [("asked", "p02")]
    assert second.decisions["p02"].answered[0][2] == "yes"
    promised, = pledges_of(second).open
    assert promised.state == "promised" and promised.held == 1 and promised.heard == 1
    assert promised.action in second.committed.reservations                                    # a real kernel reservation
    assert available(second, "p02") == 1 and second.committed.holdings["water"]["p02"] == 2   # still theirs, but not free
    assert "reserve" in [p.operation for p in second.proposals if p.actor == "p02"]
    at = handed_over(steps)
    give_step = steps[at]
    assert give_step.decisions["p02"].kind == "offer" and give_step.decisions["p02"].keeping == promised.id
    assert [p.operation for p in give_step.proposals if p.actor == "p02"] == ["complete"]
    assert ended(give_step) == [("water", "p01", "p02", "kept", "handed_over")]
    assert pledges_of(give_step).open == () and give_step.committed.reservations == {}
    assert give_step.committed.holdings["water"]["p01"] == 1 and give_step.committed.holdings["water"]["p02"] == 1
    assert sum(1 for step in steps for e in ended(step) if e[3] == "kept") == 1               # kept once, never twice


def test_the_hand_over_is_a_gift_so_the_asker_comes_to_think_better_of_the_helper():
    config, ledger, world = scene()
    steps = play(config, ledger, world, 10, sky=RAIN_NIGHT)
    at = handed_over(steps)
    before = find(steps[at - 1].processed.overlay.persona.bonds.get("p01", ()), "p02")
    mine = find(steps[at].processed.overlay.persona.bonds["p01"], "p02")
    assert mine[1] >= (before[1] if before else 0) + 4 and mine[2] >= (before[2] if before else 50) + 5


def test_a_reserved_unit_cannot_be_drunk_by_the_helper_until_the_promise_ends():
    config, ledger, world = scene(water=(0, 1), traits={"p02": (80, 50, 50, 50, 50)})
    world = replace(world, thirst={**world.thirst, "p02": 21})                                 # thirsty two ticks on, with exactly the promised unit
    steps = play(config, ledger, world, 6, sky=RAIN_NIGHT)
    assert steps[1].decisions["p02"].answered[0][2] == "yes"
    assert available(steps[1], "p02") == 0
    after = observe("p02", steps[1].committed, steps[1].processed.overlay, config)
    assert after.water == 0                                                                    # their own view: nothing to drink
    until = handed_over(steps)
    for step in steps[1:until]:
        assert not any(p.operation == "consume" and p.params.get("resource") == "water" for p in step.proposals if p.actor == "p02")
    assert pledges_of(steps[until]).open == () and ended(steps[until])[0][3] == "kept"


def test_a_helper_in_a_thirst_emergency_gives_the_reservation_up_and_says_so():
    config, ledger, world = scene(water=(0, 1), traits={"p02": (80, 50, 50, 50, 50)})
    steps = play(config, ledger, world, 2, sky=RAIN_NIGHT)
    assert pledges_of(steps[1]).open[0].state == "promised"
    desperate = replace(steps[1].processed.overlay, thirst={**steps[1].processed.overlay.thirst, "p02": config.thirst_emergency_at})
    engine = steps[1].engine
    step = world_step(engine, replace(desperate, sky=RAIN_NIGHT), config)
    choice = step.decisions["p02"]
    assert choice.gave_up == pledges_of(steps[1]).open[0].id and choice.action
    assert [p.operation for p in step.proposals if p.actor == "p02"][-1] == "cancel"
    assert ended(step) == [("water", "p01", "p02", "failed", "gave_it_up")]
    assert step.committed.reservations == {}                                                  # given back on the same tick
    assert available(step, "p02") == 1                                                         # theirs to use again
    after = world_step(step.engine, replace(step.processed.overlay, sky=RAIN_NIGHT), config)
    assert after.decisions["p02"].kind == "drink"                                              # and they do, the very next tick
    grudge = find(step.processed.overlay.persona.bonds["p01"], "p02")
    assert grudge is not None and grudge[3] > 0 and grudge[5] == "broke_promise"


def test_a_promise_that_runs_out_of_time_is_returned_and_held_against_the_helper():
    config, ledger, world = scene(cfg(feature_levers=(("promise_span", 3),)))
    far_away = lambda w: replace(w, positions={**w.positions, "p02": (1, 1)}) if w.tick == 42 else w
    steps = play(config, ledger, world, 8, sky=RAIN_NIGHT, edit=far_away)
    reasons = [e for step in steps for e in ended(step)]
    assert reasons == [("water", "p01", "p02", "expired", "ran_out_of_time")]
    last = steps[-1]
    assert last.committed.reservations == {} and available(last, "p02") == 2                 # the reservation went back
    grudge = find(last.processed.overlay.persona.bonds["p01"], "p02")
    assert grudge is not None and grudge[3] > 0 and grudge[5] == "broke_promise"


# --- an ending, whichever way it comes -----------------------------------------------------------

def promised_scene(**changes):
    config, ledger, world = scene(**changes)
    steps = play(config, ledger, world, 2, sky=RAIN_NIGHT)
    return config, steps[-1], steps[-1].processed.overlay


def test_a_helper_who_dies_has_the_promise_end_and_the_reservation_returned():
    config, step, world = promised_scene(food=(2, 0))                                          # the helper has nothing to eat
    assert world.pledges.open[0].action in step.committed.reservations
    dying = replace(world, hunger={**world.hunger, "p02": config.death_at - 1}, sky=RAIN_NIGHT)
    one = world_step(step.engine, dying, config)
    assert "p02" in one.processed.overlay.died_at
    assert ended(one) == [("water", "p01", "p02", "interrupted", "helper_died")]
    assert one.processed.overlay.pledges.release and one.committed.reservations              # handed back on the next tick
    two = world_step(one.engine, replace(one.processed.overlay, sky=RAIN_NIGHT), config)
    assert two.committed.reservations == {}
    assert [o.operation for o in two.record.outcomes if o.actor == "p02"] == ["cancel"]


def test_an_asker_who_dies_ends_the_promise_and_the_helper_keeps_the_water():
    config, step, world = promised_scene(food=(0, 2))
    dying = replace(world, hunger={**world.hunger, "p01": config.death_at - 1}, sky=RAIN_NIGHT)
    one = world_step(step.engine, dying, config)
    assert ended(one) == [("water", "p01", "p02", "interrupted", "asker_died")]
    two = world_step(one.engine, replace(one.processed.overlay, sky=RAIN_NIGHT), config)
    assert two.committed.reservations == {} and two.committed.holdings["water"]["p02"] == 2   # nothing went to the dead


def test_a_helper_who_runs_from_a_wolf_has_the_promise_cut_short_and_not_counted_against_them():
    config, step, world = promised_scene()
    x, y = world.positions["p02"]
    chased = replace(world, things=Things(wolves=(Wolf("w1", (x + 1, y + 1)),)), sky=RAIN_NIGHT)
    one = world_step(step.engine, chased, config)
    assert one.decisions["p02"].kind == "flee"
    assert ended(one) == [("water", "p01", "p02", "interrupted", "ran_from_wolf")]
    two = world_step(one.engine, replace(one.processed.overlay, sky=RAIN_NIGHT), config)
    assert two.committed.reservations == {}                                                  # the unit went back to the helper
    held = find(two.processed.overlay.persona.bonds.get("p01", ()), "p02")
    assert held is None or held[3] == 0                                                      # nobody blames somebody for running


def test_without_the_helper_ever_answering_the_request_lapses():
    config, ledger, world = scene()
    gone = lambda w: replace(w, positions={**w.positions, "p02": (8, 2)}) if w.tick == 41 else w
    steps = play(config, ledger, world, 6, sky=RAIN_NIGHT, edit=gone)
    outcomes = [e for step in steps for e in ended(step)]
    assert ("water", "p01", "p02", "expired", "no_answer") in outcomes
    assert all(step.committed.reservations == {} for step in steps)


def test_a_refusal_to_somebody_in_need_is_held_against_a_stingy_person_but_a_plain_no_is_not():
    config, ledger, world = scene(traits={"p02": (10, 50, 50, 50, 50)}, thirst=48)           # in need by the time they are answered
    steps = play(config, ledger, world, 3, sky=RAIN_NIGHT)
    assert [e for step in steps for e in ended(step)] == [("water", "p01", "p02", "declined", "unwilling")]
    grudge = find(steps[-1].processed.overlay.persona.bonds["p01"], "p02")
    assert grudge is not None and grudge[3] > 0 and grudge[5] == "refused"
    config2, ledger2, world2 = scene(water=(0, 0), thirst=48)
    plain = play(config2, ledger2, world2, 3, sky=RAIN_NIGHT)
    assert asks(config2, ledger2, world2) == ()                                              # nobody in sight carries any: no ask at all
    held = find(plain[-1].processed.overlay.persona.bonds.get("p01", ()), "p02")
    assert held is None or held[3] == 0
    config3, ledger3, world3 = scene(water=(0, 1), thirst=48)                                 # not generous, one unit: keeps it, civilly
    civil = play(config3, ledger3, world3, 3, sky=RAIN_NIGHT)
    assert [e for step in civil for e in ended(step)] == [("water", "p01", "p02", "declined", "nothing_to_spare")]
    held = find(civil[-1].processed.overlay.persona.bonds.get("p01", ()), "p02")
    assert held is None or held[3] == 0


# --- building together -------------------------------------------------------------------------

def building_scene(work_done, wood=3, amount=4, helping=True, pledges=True):
    """p01 is building at home with p02 at their door, who has promised to help."""
    config = cfg(wood_on=True, building_on=True) if pledges else WorldConfig(
        seed=7, features=tuple(f for f in FEATURES if f != "pledges"), starting_water=2, wood_on=True, building_on=True)
    config, ledger, world = scene(config, sky=CLEAR_DAY, thirst=0, cold=0, at=((1, 7), (1, 7)), wood=(wood, 0),
                                  water=(2, 2))
    helper = Pledge("build", "p01", "p02", "promised", 40, 80, amount, (1, 7), heard=1) if helping else None
    built = {actor: 0 for actor in world.roster}
    built["p01"] = work_done
    world = replace(world, built=built, pledges=Pledges(open=(helper,) if helping else ()))
    skills = {**world.persona.skills, "p01": (0, 0, 0, 0, 0), "p02": (0, 0, 0, 0, 0)}
    world = replace(world, persona=replace(world.persona, skills=skills))
    return config, ledger, world


@pytest.mark.parametrize("before, gain", [(1, 2), (2, 2), (3, 1), (5, 2), (7, 1), (9, 2), (10, 2), (11, 1)])
def test_a_helper_at_the_door_adds_one_tick_of_work_but_never_past_a_wood_payment_or_the_finish(before, gain):
    config, ledger, world = building_scene(before)
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p01"].kind == "build" and step.decisions["p02"].kind == "help"
    after = step.processed.overlay
    assert after.built["p01"] == before + gain                                             # 2 on a tick that starts no group of four unpaid
    paid = sum(o.effects[0].delta for o in step.record.outcomes if o.actor == "p01" and o.operation == "consume")
    assert paid in (0, -1)                                                                  # only the owner's own tick ever pays
    assert not any(o.actor == "p02" and o.operation == "consume" for o in step.record.outcomes)   # the helper never pays


def test_helping_lets_a_shelter_stand_sooner_and_costs_exactly_the_wood_it_needs():
    config, ledger, world = building_scene(0)
    alone_config, alone_ledger, alone_world = building_scene(0, helping=False, pledges=False)
    helped = play(config, ledger, world, 16)
    alone = play(alone_config, alone_ledger, alone_world, 16)
    when = lambda steps: next(i for i, s in enumerate(steps) if s.processed.overlay.homes["p01"] in s.processed.overlay.shelters)
    assert when(helped) < when(alone)
    spent = lambda steps: sum(-e.delta for s in steps for o in s.record.outcomes if o.accepted
                              for e in o.effects if e.account == "actor@wood:p01" and e.delta < 0)
    assert spent(helped) == spent(alone) == 3                                               # 12 ticks of work, a wood for each four
    done, = [e for step in helped for e in ended(step) if e[0] == "build"]
    assert done[3:] == ("kept", "work_done")                                                # asked for four, and the shelter stood


def test_a_helper_earns_building_practice_only_for_ticks_that_really_added_work():
    config, ledger, world = building_scene(1)
    step = world_step(Engine(ledger), world, config)
    assert step.processed.overlay.persona.skills["p02"][2] == 1 and step.processed.overlay.persona.skills["p01"][2] == 1
    config, ledger, world = building_scene(3)                                              # the payment tick: no credit for the helper
    step = world_step(Engine(ledger), world, config)
    assert step.processed.overlay.persona.skills["p02"][2] == 0


def test_a_shelter_finished_before_the_helper_lifted_a_hand_ends_the_promise_as_not_needed():
    config, ledger, world = building_scene(11, amount=4)                                    # the owner's tick finishes it
    world = replace(world, positions={**world.positions, "p02": (1, 6)})                    # the helper is a step away, not yet there
    step = world_step(Engine(ledger), world, config)
    assert step.processed.overlay.homes["p01"] in step.processed.overlay.shelters
    assert ended(step) == [("build", "p01", "p02", "expired", "not_needed")]


def test_a_helper_who_finds_nobody_at_the_door_gives_up_after_the_wait():
    config, ledger, world = building_scene(0)
    gone = lambda w: replace(w, positions={**w.positions, "p01": (1, 1)}) if w.tick >= 41 else w
    steps = play(config, ledger, world, 12, edit=gone)                                       # the builder is away, out of sight
    assert [e for s in steps for e in ended(s) if e[0] == "build"] == [("build", "p01", "p02", "failed", "not_there")]
    wait = config.lever("place_wait")
    arrived = next(p for s in steps for p in pledges_of(s).open if p.kind == "build" and p.arrived).arrived
    failed_at = next(i for i, s in enumerate(steps) if ("build", "p01", "p02", "failed", "not_there") in ended(s))
    assert steps[failed_at].processed.overlay.tick - arrived == wait                        # exactly place_wait ticks, not more


def test_somebody_asks_for_a_hand_only_while_there_is_enough_left_to_build():
    config = cfg(wood_on=True, building_on=True)
    config, ledger, world = scene(config, sky=CLEAR_DAY, thirst=0, cold=0, at=((1, 7), (1, 6)), wood=(3, 0))
    assert asks(config, ledger, world) == (("p02", "build", 4),)
    late = replace(world, built={**{a: 0 for a in world.roster}, "p01": 9})
    assert asks(config, ledger, late) == ()                                                 # three ticks left: not worth the walk
    busy = replace(world, persona=replace(world.persona, doing={"p02": "claim"}))
    assert asks(config, ledger, busy) == ()                                                 # the other is visibly occupied


# --- news --------------------------------------------------------------------------------------

def news_scene(trust=50):
    """p01 stays in on an old rumour of a wolf at the well; p02 saw it somewhere else a moment ago."""
    config = cfg()
    old = ("wolf", "w1", 3, 8, 20, 20, "")                                    # by the well they would go to, 20 ticks before: stale
    fresh = ("wolf", "w1", 9, 9, 38, 38, "")
    bonds = {"p01": (bond("p02", 20, trust),)}
    return scene(config, sky=NIGHT, thirst=40, cold=0, bonds=bonds, water=(0, 0), beliefs={"p01": (old,), "p02": (fresh,)})


def test_somebody_staying_in_on_an_old_rumour_asks_for_news():
    config, ledger, world = news_scene()
    view = observe("p01", ledger, world, config)
    assert view.danger                                                                        # the old report still keeps them in
    assert decide(view, config).asked == (("p02", "news", 1),)


def test_the_news_they_are_told_replaces_the_stale_belief_with_its_own_date_and_teller():
    config, ledger, world = news_scene()
    steps = play(config, ledger, world, 3, sky=NIGHT)
    assert ended(steps[1]) == [("news", "p01", "p02", "kept", "told")]
    belief, = steps[1].processed.overlay.persona.beliefs["p01"]
    assert belief[:5] == ("wolf", "w1", 9, 9, 38) and belief[6] == "p02"                       # fresher, and not any younger for being told
    assert belief[5] == 41                                                                    # learned when it was said
    assert steps[1].committed.reservations == {}                                              # news reserves nothing


def test_news_from_somebody_they_do_not_trust_is_heard_but_not_believed():
    config, ledger, world = news_scene(trust=10)
    steps = play(config, ledger, world, 3, sky=NIGHT)
    assert ended(steps[1]) == [("news", "p01", "p02", "kept", "told")]                       # they were told...
    belief, = steps[-1].processed.overlay.persona.beliefs["p01"]
    assert belief[:5] == ("wolf", "w1", 3, 8, 20)                                             # still the old one


# --- hosting -----------------------------------------------------------------------------------

def host_scene(**kw):
    config, ledger, world = scene(sky=CLEAR_DAY, thirst=0, cold=0, at=((1, 7), (1, 6)), food=(3, 0), water=(2, 2),
                                  bonds={"p01": (bond("p02", 2),)}, **kw)
    return config, ledger, world


def test_a_host_with_food_to_spare_feeds_a_guest_at_their_door_who_has_none():
    config, ledger, world = host_scene()
    step = world_step(Engine(ledger), world, config)
    d = step.decisions["p01"]
    assert d.kind == HOST and d.target == "p02" and "my door" in d.reason
    assert step.committed.balances["p02"] == 1 and step.committed.balances["p01"] == 2     # a real transfer, accounted
    assert [o.operation for o in step.record.outcomes if o.actor == "p01"] == ["transfer"]


@pytest.mark.parametrize("change", ["short", "resented", "stranger", "away", "fed"])
def test_a_host_does_not_feed_when_they_are_short_the_guest_is_resented_or_unknown_or_has_food(change):
    config, ledger, world = host_scene()
    if change == "short":
        ledger = give(ledger, "p01", food=2)                                                   # below host_at: they keep what they have
    elif change == "resented":
        world = replace(world, persona=replace(world.persona, bonds={"p01": (bond("p02", 20, grudge=12, why="quarrel", grieved=3),)}))
    elif change == "stranger":
        world = replace(world, persona=replace(world.persona, bonds={}))
    elif change == "away":
        world = replace(world, positions={**world.positions, "p02": (1, 4)})
    else:
        ledger = give(ledger, "p02", food=1)
    step = world_step(Engine(ledger), world, config)
    assert step.decisions["p01"].kind != HOST


# --- what a person can know --------------------------------------------------------------------

def test_what_a_bystander_decides_does_not_depend_on_somebody_elses_requests():
    config, ledger, world = scene()
    plain = observe("p05", ledger, world, config)
    with_pledge = observe("p05", ledger, replace(world, pledges=Pledges(open=(pledge(made=40, due=43),))), config)
    assert plain == with_pledge                                                              # a request between others is invisible to them
    assert decide(plain, config) == decide(with_pledge, config)


def test_a_helper_decides_the_same_whether_or_not_the_asker_was_ever_out_of_sight_before():
    config, ledger, world = scene()
    asked = replace(world, pledges=Pledges(open=(pledge(made=40, due=43),)))
    near = decide(observe("p02", ledger, asked, config), config)
    far = decide(observe("p02", ledger, replace(asked, positions={**asked.positions, "p02": (8, 2)}), config), config)
    assert near.answered and not far.answered                                                # out of sight: nothing was heard, nothing answered


def test_the_one_asked_cannot_see_the_askers_need_only_what_is_visible_of_them():
    config, ledger, world = scene()
    low = observe("p02", ledger, replace(world, thirst={**world.thirst, "p01": 30}), config)
    high = observe("p02", ledger, replace(world, thirst={**world.thirst, "p01": 45}), config)
    assert low.others == high.others                                                         # thirst below the emergency level does not show


# --- no pledges, no records --------------------------------------------------------------------

def test_without_the_feature_nothing_is_asked_answered_or_written(tmp_path):
    config = cfg(feature_levers=())
    config = WorldConfig(seed=7, features=tuple(f for f in FEATURES if f != "pledges"), starting_water=2)
    path = tmp_path / "plain.jsonl"
    run_world(config, 120, path)
    run = read_run(path)
    for tick in run.ticks:
        assert "pledges" not in tick["world"]
        assert not any(k in d for d in tick["decisions"].values() for k in ("asked", "answered", "keeping", "gave_up"))
        assert not any(o["operation"] in ("reserve", "complete", "cancel") for o in tick["record"]["outcomes"])


# --- whole worlds ------------------------------------------------------------------------------

ALL = tuple(sorted(set(FEATURES) | {"sleep"}))


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("pledges") / "run.jsonl"
    config = WorldConfig(seed=14, features=ALL, wood_on=True)
    run_world(config, 450, path)
    return config, path, read_run(path)


def overlays(run):
    return [run.header["world"]] + [tick["world"] for tick in run.ticks]


def open_of(world):
    return [tuple(p) for p in (world.get("pledges") or {}).get("open", [])]


def endings_of(world):
    return [tuple(c) for c in (world.get("pledges") or {}).get("closed", [])]


@pytest.mark.long_run
def test_a_pledging_world_audits_replays_and_recovers_from_a_cut_with_a_promise_in_flight(saved, tmp_path):
    _, path, run = saved
    assert run.complete and audit_run(run) == []
    assert replay_world(path).identical
    worlds = overlays(run)
    flying = next(k for k in range(1, len(worlds)) if any(p[3] == "promised" and p[9] for p in open_of(worlds[k]))
                  and run.ticks[k - 1]["state"]["reservations"])
    lines = path.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines)
               if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == worlds[flying]["tick"])
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks                                           # the held units came back with the state


@pytest.mark.long_run
def test_every_request_ends_exactly_once_and_nothing_is_left_open_without_being_open(saved):
    _, _, run = saved
    worlds = overlays(run)
    seen = {}
    for k in range(1, len(worlds)):
        now, before = open_of(worlds[k]), open_of(worlds[k - 1])
        for kind, asker, helper, state, made, *_ in now:
            seen.setdefault((asker, made), (kind, helper))
            assert seen[(asker, made)] == (kind, helper)                                      # one request is one thing, start to end
        askers = [p[1] for p in now]
        assert len(askers) == len(set(askers))                                                # nobody has two open requests
        promised = [p[2] for p in now if p[3] == "promised"]
        assert len(promised) == len(set(promised))                                            # nobody has made two promises
        still = {(p[1], p[4]) for p in now}
        for kind, asker, helper, outcome, reason, tick in endings_of(worlds[k]):
            assert tick == k and reason in REASONS
            match = [p for p in before if (p[0], p[1], p[2]) == (kind, asker, helper)]
            assert len(match) == 1 and (asker, match[0][4]) not in still                       # it was open, and now it is not
    ended_ids = set()
    for k in range(1, len(worlds)):
        before = open_of(worlds[k - 1])
        for kind, asker, helper, *_ in endings_of(worlds[k]):
            made = next(p[4] for p in before if (p[0], p[1], p[2]) == (kind, asker, helper))
            assert (asker, made) not in ended_ids
            ended_ids.add((asker, made))
    last = {(p[1], p[4]) for p in open_of(worlds[-1])}
    assert set(seen) == ended_ids | last                                                      # every request ended once or is still open
    assert len(seen) > 40 and len(ended_ids) > 30


@pytest.mark.long_run
def test_the_kernel_holds_exactly_the_units_that_promises_hold_and_hands_back_the_rest(saved):
    _, _, run = saved
    worlds = overlays(run)
    holds = 0
    for k in range(1, len(worlds)):
        world = worlds[k]
        wanted = {p[10] for p in open_of(world) if p[10]}
        wanted |= {action for _, action in (world.get("pledges") or {}).get("release", [])}
        held = set(run.ticks[k - 1]["state"]["reservations"])
        assert held == wanted, (k, held ^ wanted)                                              # no reservation is left behind or made up
        holds += bool(held)
    assert holds > 20


@pytest.mark.long_run
def test_every_promise_that_holds_units_was_a_reservation_the_kernel_accepted(saved):
    _, _, run = saved
    worlds = overlays(run)
    reserved = 0
    for k in range(1, len(worlds)):
        before = {(p[1], p[4]): p for p in open_of(worlds[k - 1])}
        for kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, done in open_of(worlds[k]):
            was = before.get((asker, made))
            if state == "promised" and was is not None and was[3] == "asked" and held:
                outcome = next(o for o in run.ticks[k - 1]["record"]["outcomes"]
                               if o["operation"] == "reserve" and o["actor"] == helper)
                assert outcome["accepted"] and outcome["action_id"] == action
                gives = {e["account"]: e["delta"] for e in outcome["reservation"]["effects"]}
                resource = {"food": None, "water": "water", "wood": "wood"}[kind]
                from kernel.state import actor_account
                assert gives == {actor_account(helper, resource): -held, actor_account(asker, resource): held}
                assert any(a[0] == asker and a[2] == "yes" and a[4] == held for a in
                           [tuple(x_) for x_ in run.ticks[k - 1]["decisions"][helper].get("answered", [])])
                reserved += 1
    assert reserved > 3


@pytest.mark.long_run
def test_every_promised_hand_over_was_settled_by_the_kernel_to_the_one_who_asked(saved):
    _, _, run = saved
    worlds = overlays(run)
    kept = 0
    for k in range(1, len(worlds)):
        for kind, asker, helper, outcome, reason, tick in endings_of(worlds[k]):
            if outcome != "kept" or kind not in ("water", "food", "wood"):
                continue
            decision = run.ticks[k - 1]["decisions"][helper]
            assert decision["kind"] == "offer" and decision["target"] == asker and decision.get("keeping")
            mine = [o for o in run.ticks[k - 1]["record"]["outcomes"] if o["actor"] == helper and o["operation"] in ("complete", "transfer")]
            assert len(mine) == 1 and mine[0]["accepted"]
            resource = {"food": None, "water": "water", "wood": "wood"}[kind]
            from kernel.state import actor_account
            assert any(e["account"] == actor_account(asker, resource) and e["delta"] > 0 for e in mine[0]["effects"])
            kept += 1
    assert kept >= 3


@pytest.mark.long_run
def test_every_request_was_spoken_to_somebody_in_sight_and_every_answer_to_a_request_heard(saved):
    _, _, run = saved
    worlds = overlays(run)
    asked = answered = 0
    for k in range(1, len(worlds)):
        tick = run.ticks[k - 1]
        for actor, d in tick["decisions"].items():
            for helper, kind, amount in d.get("asked", []):
                assert helper in tick["observations"][actor]["sees"]                           # only somebody they could see
                assert any(p[0:3] == (kind, actor, helper) and p[4] == k for p in open_of(worlds[k]))
                asked += 1
            for asker, kind, verdict, reason, held in d.get("answered", []):
                assert asker in tick["observations"][actor]["sees"]                            # and only while the asker was in sight
                assert any(p[0:3] == (kind, asker, actor) and p[3] == "asked" for p in open_of(worlds[k - 1]))
                assert verdict in ("yes", "no") and (verdict == "yes" or reason in REASONS)
                answered += 1
    assert asked > 40 and answered > 30


@pytest.mark.long_run
def test_every_grudge_over_a_refusal_or_a_broken_promise_follows_a_recorded_ending(saved):
    _, _, run = saved
    worlds = overlays(run)
    blamed = {("refused", "declined"), ("broke_promise", "failed"), ("broke_promise", "expired")}
    ends = {(asker, helper, outcome) for w in worlds[1:] for _, asker, helper, outcome, reason, _ in endings_of(w)}
    for k in range(1, len(worlds)):
        for owner, entries in (worlds[k]["persona"].get("bonds") or {}).items():
            for other, level, trust, grudge, last, why, grieved, tone in entries:
                if grudge and why in ("refused", "broke_promise"):
                    assert any((owner, other, outcome) in ends for w, outcome in blamed if w == why)


@pytest.mark.long_run
def test_helpers_who_walk_into_wolves_or_sleep_never_keep_a_promise_that_tick(saved):
    _, _, run = saved
    worlds = overlays(run)
    for k in range(1, len(worlds)):
        for kind, asker, helper, outcome, reason, tick in endings_of(worlds[k]):
            if outcome == "interrupted" and reason in ("ran_from_wolf", "collapsed"):
                assert run.ticks[k - 1]["decisions"][helper]["kind"] in ("flee", "collapse")
            if outcome == "kept":
                assert run.ticks[k - 1]["decisions"][helper]["kind"] not in ("flee", "collapse", "sleep")


# --- fetching wood for somebody ----------------------------------------------------------------

def test_somebody_housed_and_free_fetches_wood_for_a_builder_who_waits_at_home():
    config = cfg(wood_on=True, building_on=True)
    config, ledger, world = scene(config, sky=CLEAR_DAY, thirst=0, cold=0, at=((1, 7), (1, 6)), water=(2, 2), wood=(0, 0))
    world = replace(world, shelters=tuple(sorted(set(world.shelters) | {world.homes["p02"]})))
    steps = play(config, ledger, world, 14)
    assert steps[0].decisions["p01"].asked == (("p02", "wood", 1),)
    assert steps[1].decisions["p02"].answered[0][2:] == ("yes", "agreed", 0)                 # nothing in hand: a promise to fetch, no reservation
    assert steps[1].committed.reservations == {}
    kept_at = next(i for i, s in enumerate(steps) if ("wood", "p01", "p02", "kept", "handed_over") in ended(s))
    seq = [steps[i].decisions["p02"].kind for i in range(2, kept_at + 1)]
    assert seq[0] == "go_wood" and "gather_wood" in seq and seq[-1] == "offer" and "go_offer" in seq
    gathered = next(s for s in steps if s.decisions["p02"].kind == "gather_wood")
    assert any(o.actor == "p02" and o.operation == "claim" and o.accepted for o in gathered.record.outcomes)
    final = steps[kept_at]
    assert [o.operation for o in final.record.outcomes if o.actor == "p02"] == ["transfer"]  # an ordinary accounted gift, no hold
    assert final.committed.holdings["wood"]["p01"] == 1 and final.committed.holdings["wood"]["p02"] == 0
    # the builder who asked did not go to the grove themselves while they waited
    assert all(s.decisions["p01"].kind not in ("go_wood", "gather_wood") for s in steps[: kept_at + 1])
