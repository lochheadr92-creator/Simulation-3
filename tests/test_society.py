"""Relationships: talk, friendship, news passed on, grudges, quarrels, apologies, loneliness.

The bond store and each social rule are checked on their own with hand-built situations. Then what a
person can know: they decide from their own bonds and what they see, never from how somebody else feels.
Then whole saved worlds: every change to a bond traces to something the run recorded (two people who
both chose to talk, a refused claim, a kept unit, a gift), and replay, recovery and the ledger audit agree.
"""

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from kernel import Engine
from kernel.proposals import claim, transfer
from stream.run_file import read_run
from tests.ledger_audit import audit_run
from world.belief import advance_beliefs
from world.config import WorldConfig, genesis
from world.decide import Decision, decide, someone_to_help
from world.observe import Observation, SeenPerson, observe
from world.overlay import Overlay
from world.persona import Persona
from world.process import advance
from world.recover import recover_world
from world.replay import replay_world
from world.run import run_world
from world.sky import Sky
from world.society import (CHAT, CONFRONT, GO_VISIT, advance_society, check_bond, find, grudge_of, put, trust_in)
from world.viewer import render_html
from world.viewer_index import build_index

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ("beliefs", "bonds", "explain", "personality", "sky", "sleep", "steady")
DAY = Sky("day", "clear", 14, 20)
NIGHT = Sky("night", "clear", 7, 100)


def cfg(**changes):
    return WorldConfig(**{**dict(seed=7, features=FEATURES), **changes})


def bond(other, level=0, trust=50, grudge=0, last=0, why="", grieved=0, tone=""):
    return (other, level, trust, grudge, last, why, grieved, tone)


# --- configuration and storage ---------------------------------------------------------------

def test_header_round_trips_and_the_social_settings_are_validated():
    config = cfg()
    assert WorldConfig.from_describe(config.describe()) == config
    assert "bonds" in config.describe()["feature_rules"]
    with pytest.raises(ValueError):
        WorldConfig(seed=7, features=("bonds",))                              # bonds need beliefs
    for bad in ((("talk_range", 0),), (("chat_at", 30),), (("grudge_gain", 50),), (("lonely_max", 5),), (("retry_after", 0),)):
        with pytest.raises(ValueError):
            cfg(feature_levers=bad)


def test_a_bond_changes_one_entry_at_a_time_and_stays_between_nought_and_a_hundred():
    held = put((), "p02", bond=40, last=5, tone="warm")
    assert held == (bond("p02", 40, last=5, tone="warm"),)
    again = put(held, "p02", bond=150, trust=-5)
    assert again[0][1] == 100 and again[0][2] == 0                                  # clamped
    both = put(again, "p01", grudge=9, why="quarrel", grieved=7)
    assert [e[0] for e in both] == ["p01", "p02"]                                   # a fixed order
    healed = put(both, "p01", grudge=0)
    assert find(healed, "p01")[5:7] == ("", 0)                                      # no grudge, no cause and no date
    assert grudge_of(both, "p01") == 9 and grudge_of(both, "p09") == 0 and trust_in(both, "p09") == 50


@pytest.mark.parametrize("entry", [
    bond("p1"), ("p2", 1, 2, 3, 4, "", 0),                                          # a person with themselves; too short
    bond("p9"), bond("p2", 101), bond("p2", 1, -1), bond("p2", 1, 50, 0, 99),         # unknown; out of range; dated in the future
    bond("p2", 1, 50, 5, 1, "", 1), bond("p2", 1, 50, 0, 1, "quarrel", 1),            # a grudge with no cause, a cause with no grudge
    bond("p2", 1, 50, 5, 1, "spite", 1), bond("p2", 1, 50, 0, 1, "", 0, "shouting"),  # an unknown cause, an unknown tone
])
def test_a_bond_in_a_saved_run_is_checked_strictly(entry):
    with pytest.raises(ValueError):
        check_bond("p1", entry, {"p1", "p2"}, 50)
    assert check_bond("p1", bond("p2", 5, 50, 4, 3, "quarrel", 3, "quarrel"), {"p1", "p2"}, 50)


def test_bonds_loneliness_and_talk_survive_the_canonical_form_and_are_validated():
    persona = Persona(bonds={"p1": (bond("p3", 9), bond("p2", 40, grudge=6, why="kept_food", grieved=4))},
                      lonely={"p1": 7}, talking={"p1": ("p2", 3), "p2": ("p1", 3)})
    again = Persona.from_canonical(json.loads(json.dumps(persona.canonical())))
    assert again == persona and [e[0] for e in again.bonds["p1"]] == ["p2", "p3"]
    persona.check({"p1", "p2", "p3"}, 50)
    with pytest.raises(ValueError):
        persona.check({"p1", "p2"}, 50)                                             # a bond with somebody the world does not know
    with pytest.raises(ValueError):
        Persona(talking={"p1": ("p1", 3)}).check({"p1"}, 50)                        # nobody talks to themselves
    with pytest.raises(ValueError):
        Persona(bonds={"p1": (bond("p2"), bond("p2", 5))})                          # two bonds with one person


# --- the social rules, one at a time ---------------------------------------------------------

def scene(config=None, near=((5, 5), (5, 6)), **changes):
    """Two people side by side (the rest far away), and everything every person observes."""
    config = config or cfg(starting_food=3)
    ledger, world = genesis(config)
    positions = dict(world.positions)
    positions["p01"], positions["p02"] = near
    for i, who in enumerate(("p03", "p04", "p05", "p06")):
        positions[who] = (0 + i, 11)
    world = replace(world, positions=positions, sky=DAY, tick=40, **changes)
    return config, replace(ledger, tick=40), world


def observed(config, ledger, world):
    available = ledger.availability()
    return {a: observe(a, ledger, world, config, available) for a in world.living}


def talk(a, b, kind=CHAT):
    return Decision(a, kind, "", (), target=b)


def has_a_word(a, b):
    return Decision(a, "rest", "", (), confronted=(b,))


def hello(a, *others):
    return Decision(a, "rest", "", (), greeted=tuple(others))


def settle(config, ledger, world, proposals=()):
    engine = Engine(ledger)
    record = engine.tick(list(proposals))
    return record, replace(world, tick=world.tick + 1)


def run_society(config, ledger, world, decisions, proposals=(), views=None):
    record, after = settle(config, ledger, world, proposals)
    views = views or observed(config, ledger, world)
    return advance_society(world, after, decisions, views, record, config)


def test_two_people_who_both_chose_it_talk_and_each_comes_to_like_the_other():
    config, ledger, world = scene()
    bonds, lonely, talking, failed = run_society(config, ledger, world, {"p01": talk("p01", "p02"), "p02": talk("p02", "p01")})
    gain = config.lever("chat_gain") + (1 if all(world.persona.traits[p][1] >= 50 for p in ("p01", "p02")) else 0)
    for one, other in (("p01", "p02"), ("p02", "p01")):
        entry = find(bonds[one], other)
        assert entry[1] == gain and entry[2] == 51 and entry[4] == 40 and entry[7] == "warm"
    assert talking == {"p01": ("p02", 40), "p02": ("p01", 40)} and failed == []
    # a conversation that began earlier keeps its start
    ongoing = replace(world, persona=replace(world.persona, talking={"p01": ("p02", 37), "p02": ("p01", 37)}))
    assert run_society(config, ledger, ongoing, {"p01": talk("p01", "p02"), "p02": talk("p02", "p01")})[2]["p01"] == ("p02", 37)


def test_a_word_with_nobody_listening_changes_nothing_and_is_remembered_as_an_attempt():
    config, ledger, world = scene()
    bonds, _, talking, failed = run_society(config, ledger, world, {"p01": talk("p01", "p02"),
                                                                    "p02": Decision("p02", "rest", "", ())})
    assert bonds == {} and talking == {} and failed == [("p01", CHAT, "p02", 40, 0)]
    far, ledger, world = scene(near=((2, 2), (6, 6)))
    assert run_society(far, ledger, world, {"p01": talk("p01", "p02"), "p02": talk("p02", "p01")})[0] == {}     # not within reach
    config, ledger, world = scene()
    asleep = replace(world, persona=replace(world.persona, asleep={"p02": 30}))
    assert run_society(config, ledger, asleep, {"p01": talk("p01", "p02"), "p02": talk("p02", "p01")})[0] == {}   # one is asleep


def test_loneliness_rises_while_alone_stops_at_the_top_and_falls_with_talk():
    config, ledger, world = scene()
    every, top = config.lever("lonely_every"), config.lever("lonely_max")
    world = replace(world, persona=replace(world.persona, lonely={"p01": 5, "p02": top}))
    rose = [run_society(config, replace(ledger, tick=t), replace(world, tick=t), {})[1] for t in range(40, 40 + every)]
    assert sum(1 for r in rose if r.get("p01", 5) == 6) == 1                       # exactly one tick in lonely_every adds a point
    assert all(r["p02"] == top for r in rose)                                      # never above the top
    chatting = run_society(config, ledger, world, {"p01": talk("p01", "p02"), "p02": talk("p02", "p01")})[1]
    assert chatting["p01"] == 5 - config.lever("chat_relief")                      # talk eases it, and does not add a point


def test_a_gift_adds_to_a_bond_and_takes_something_off_a_grudge():
    config, ledger, world = scene()
    world = replace(world, persona=replace(world.persona, bonds={"p02": (bond("p01", 10, 40, 14, 30, "quarrel", 30),)}))
    bonds, *_ = run_society(config, ledger, world, {}, proposals=[transfer("t40-p01", "p01", 0, to="p02", amount=1)])
    got = find(bonds["p02"], "p01")
    assert got[1:5] == (14, 45, 8, 40) and got[7] == "gift"                         # +4 bond, +5 trust, -6 grudge
    assert find(bonds["p01"], "p02")[1] == 1                                       # and the giver is a little fonder


def test_a_refused_claim_is_held_against_the_person_in_view_whose_claim_was_taken_but_once_in_a_while():
    config, ledger, world = scene(near=((5, 5), (5, 6)))
    proposals = [claim("t40-p02", "p02", 0, sources={"food": 3}), claim("t40-p01", "p01", 0, sources={"food": 3})]
    record, after = settle(config, ledger, world, proposals)                      # the patch holds 4: only the first in order gets 3
    views = observed(config, ledger, world)
    decisions = {"p01": Decision("p01", "claim", "", (), amount=3), "p02": Decision("p02", "claim", "", (), amount=3)}
    losers = [o.actor for o in record.outcomes if not o.accepted]
    assert len(losers) == 1 and [o.reason for o in record.outcomes if not o.accepted] == ["denied_insufficient_source"]
    bonds, *_ = advance_society(world, after, decisions, views, record, config)
    loser = losers[0]
    winner = "p01" if loser == "p02" else "p02"
    entry = find(bonds[loser], winner)
    assert entry[3] == config.lever("grudge_gain") and entry[5] == "beat_to_it" and entry[6] == 40
    assert entry[2] == 45 and entry[1] == 0                                       # five less trust; a bond cannot fall below nothing
    assert winner not in bonds                                                    # the one who won holds nothing against anybody for it
    # the same grievance again straight away adds nothing; after the gap it adds more
    held = replace(world, persona=replace(world.persona, bonds={loser: bonds[loser]}))
    again, *_ = advance_society(held, after, decisions, views, record, config)
    assert find(again[loser], winner)[3] == config.lever("grudge_gain")
    later = replace(held, tick=40 + config.lever("grievance_gap"))
    assert find(advance_society(later, replace(later, tick=later.tick + 1), decisions, views, record, config)[0][loser], winner)[3] \
        == 2 * config.lever("grudge_gain")


def kept_food_scene(**changes):
    config, ledger, world = scene()
    world = replace(world, hunger=dict(world.hunger, p01=config.emergency_at + 5))
    views = observed(config, ledger, world)
    decisions = {"p01": Decision("p01", "go", "", ()), "p02": Decision("p02", "rest", "", ())}
    return config, ledger, world, views, decisions


def test_somebody_starving_resents_a_free_person_with_spare_food_who_saw_them_and_did_not_offer():
    config, ledger, world, views, decisions = kept_food_scene()
    assert views["p02"].food >= 2 and any(s.actor == "p01" and s.starving for s in views["p02"].others)
    bonds, *_ = run_society(config, ledger, world, decisions, views=views)
    entry = find(bonds["p01"], "p02")
    assert entry[3] == config.lever("grudge_gain") and entry[5] == "kept_food" and entry[2] == 45 and entry[1] == 0
    # not when they offered, when they were busy, when they had only one unit, or when they were starving too
    offered = {**decisions, "p02": Decision("p02", "offer", "", (), target="p01")}
    assert run_society(config, ledger, world, offered, views=views)[0].get("p01") is None
    busy = {**decisions, "p02": Decision("p02", "go_water", "", ())}
    assert run_society(config, ledger, world, busy, views=views)[0].get("p01") is None
    poor = replace(views["p02"], hunger=config.emergency_at)
    assert run_society(config, ledger, world, decisions, views={**views, "p02": poor})[0].get("p01") is None
    unseen = replace(views["p02"], others=())
    assert run_society(config, ledger, world, decisions, views={**views, "p02": unseen})[0].get("p01") is None   # they did not see them


def test_somebody_resented_who_is_generous_apologises_and_the_grudge_eases():
    config, ledger, world = scene()
    traits = dict(world.persona.traits)
    traits["p02"] = (80, 50, 50, 50, 50)
    world = replace(world, persona=replace(world.persona, traits=traits, bonds={"p01": (bond("p02", 12, 40, 25, 30, "kept_food", 30),)}))
    bonds, *_, tried = run_society(config, ledger, world, {"p01": has_a_word("p01", "p02")})
    mended = find(bonds["p01"], "p02")
    assert tried == [("p01", CONFRONT, "p02", 40, 1)]                              # remembered, so they do not have it out again at once
    assert mended[3] == 25 - config.lever("apology_relief") and mended[1] == 14 and mended[7] == "apology"
    assert find(bonds["p02"], "p01")[7] == "apology"


def test_somebody_resented_who_is_not_generous_quarrels_and_both_lose_something():
    config, ledger, world = scene()
    traits = dict(world.persona.traits)
    traits["p02"] = (20, 50, 50, 50, 50)
    world = replace(world, persona=replace(world.persona, traits=traits, bonds={"p01": (bond("p02", 12, 40, 25, 30, "kept_food", 30),)}))
    bonds, *_ = run_society(config, ledger, world, {"p01": has_a_word("p01", "p02")})
    mine, theirs = find(bonds["p01"], "p02"), find(bonds["p02"], "p01")
    cost, gain = config.lever("quarrel_cost"), config.lever("grudge_gain")
    assert mine[1] == 12 - cost and mine[3] == 27 and mine[5] == "kept_food" and mine[7] == "quarrel"
    assert theirs[3] == gain and theirs[5] == "quarrel" and theirs[7] == "quarrel"          # they now hold something against the one who confronted them
    assert theirs[1] == 0                                                                     # a bond cannot fall below nothing


def test_a_grudge_fades_by_one_every_grudge_fade_ticks():
    config, ledger, world = scene()
    world = replace(world, persona=replace(world.persona, bonds={"p01": (bond("p02", 10, 50, 5, 30, "quarrel", 30),)}))
    fade = config.lever("grudge_fade")
    quiet = [find(run_society(config, replace(ledger, tick=t), replace(world, tick=t), {})[0].get("p01", ()), "p02") for t in range(40, 40 + fade)]
    assert [e[3] for e in quiet].count(4) == 1 and [e[3] for e in quiet].count(5) == fade - 1


def test_a_greeting_needs_two_and_is_not_repeated_until_greet_every_ticks_have_passed():
    config, ledger, world = scene()
    both = {"p01": hello("p01", "p02"), "p02": hello("p02", "p01")}
    bonds, lonely, *_ = run_society(config, ledger, world, both)
    for one, other in (("p01", "p02"), ("p02", "p01")):
        entry = find(bonds[one], other)
        assert entry[1] == config.lever("greet_gain") and entry[7] == "greeting" and entry[4] == 40
    assert {a: lonely.get(a, 0) for a in ("p01", "p02")} == {a: world.persona.lonely.get(a, 0) for a in ("p01", "p02")}   # a hello does not ease it
    assert run_society(config, ledger, world, {"p01": hello("p01", "p02")})[0] == {}                   # nobody said it back
    asleep = replace(world, persona=replace(world.persona, asleep={"p02": 30}))
    assert run_society(config, ledger, asleep, both)[0] == {}
    recent = replace(world, persona=replace(world.persona, bonds={"p01": (bond("p02", 5, last=38, tone="greeting"),),
                                                                   "p02": (bond("p01", 5, last=38, tone="greeting"),)}))
    assert run_society(config, ledger, recent, both)[0] == dict(recent.persona.bonds)                    # too soon: nothing changes
    later = replace(recent, tick=38 + config.lever("greet_every"))
    after = run_society(config, replace(ledger, tick=later.tick), later, both)[0]
    assert find(after["p01"], "p02")[1] == 5 + config.lever("greet_gain")


# --- what a person decides ---------------------------------------------------------------------

def idle_view(config, **changes):
    """Idle at home with nothing calling, in daylight: the state in which people look for company."""
    base = dict(position=(2, 2), home=(2, 2), home_built=True, hunger=0, food=1, thirst=0, water=1, cold=0,
                fatigue=0, lonely=0, sky=DAY, tick=40, traits=(50, 50, 50, 50, 50))
    return replace(Observation(actor="p01", alive=True, source=(9, 9), source_food=None, water_source=(3, 3), water_stock=None,
                               **{k: v for k, v in base.items() if k in ("tick", "position", "home", "hunger", "food")}),
                   **{**{k: v for k, v in base.items() if k not in ("tick", "position", "home", "hunger", "food")}, **changes})


def near_person(who="p02", at=(2, 3), **changes):
    return SeenPerson(who, at, 0, **changes)


def test_somebody_lonely_and_idle_talks_to_a_free_person_within_reach_and_says_so():
    config = cfg()
    keen = decide(idle_view(config, lonely=4, others=(near_person(),)), config)
    assert keen.kind == CHAT and keen.target == "p02" and "talking with p02, somebody new" in keen.reason
    assert decide(idle_view(config, lonely=2, others=(near_person(),)), config).kind == CHAT         # half the need is enough to talk back
    assert decide(idle_view(config, lonely=1, others=(near_person(),)), config).kind != CHAT
    assert decide(idle_view(config, lonely=0, others=(near_person(),)), config).kind != CHAT


def test_nobody_is_asked_to_talk_who_is_busy_asleep_resented_or_was_tried_lately():
    config = cfg()
    lonely = dict(lonely=8)
    assert decide(idle_view(config, **lonely, others=(near_person(busy=True),)), config).kind != CHAT
    assert decide(idle_view(config, **lonely, others=(near_person(asleep=True),)), config).kind != CHAT
    cross = (bond("p02", 20, 50, 15, 30, "kept_food", 30),)
    assert decide(idle_view(config, **lonely, others=(near_person(),), bonds=cross), config).kind != CHAT
    snubbed = (("chat", "p02", 37, 0),)                                           # they talked to p02 three ticks ago and got no answer
    assert decide(idle_view(config, **lonely, others=(near_person(),), tried=snubbed), config).kind != CHAT
    long_ago = (("chat", "p02", 30, 0),)
    assert decide(idle_view(config, **lonely, others=(near_person(),), tried=long_ago), config).kind == CHAT


def test_a_conversation_goes_on_for_chat_len_ticks_and_then_they_give_it_a_rest():
    config = cfg()
    length, rest = config.lever("chat_len"), config.lever("retry_after")
    keen = dict(lonely=3, others=(near_person(),))
    for since, expected in ((40 - 1, CHAT), (40 - length + 1, CHAT)):
        talking = idle_view(config, **keen, talking=("p02", since), bonds=(bond("p02", 9, last=39, tone="warm"),))
        assert decide(talking, config).kind == expected
    over = idle_view(config, **keen, talking=("p02", 40 - length), bonds=(bond("p02", 9, last=39, tone="warm"),))
    assert decide(over, config).kind != CHAT                                       # four ticks is enough
    later = idle_view(config, **keen, bonds=(bond("p02", 9, last=40 - rest - 1, tone="warm"),))
    assert decide(later, config).kind == CHAT                                      # and after a rest they talk again


def test_somebody_lonely_with_nobody_in_reach_walks_to_company_or_to_a_friends_home_or_the_well():
    config = cfg()
    far = near_person(at=(2, 5))                                                   # three away: in view, not in reach
    over = decide(idle_view(config, lonely=12, others=(far,)), config)
    assert over.kind == GO_VISIT and over.target == "p02" and over.step in ((2, 3),) and "walking over to talk with p02" in over.reason
    friend = (bond("p03", 40, last=10),)
    home = (("home", "p03", 2, 7, 20, 20, "p03"),)                                  # told by p03 where they live: five steps off
    call = decide(idle_view(config, lonely=14, bonds=friend, beliefs=home), config)
    assert call.kind == GO_VISIT and call.target == "p03" and "whose home they know" in call.reason
    well = decide(idle_view(config, lonely=14), config)
    assert well.kind == GO_VISIT and "to the well" in well.reason
    at_the_well = decide(idle_view(config, lonely=14, position=(3, 3)), config)
    assert at_the_well.kind == "rest" and "waiting at the well" in at_the_well.reason
    assert decide(idle_view(config, lonely=11), config).kind != GO_VISIT          # not lonely enough to go out of their way


def test_nobody_goes_visiting_at_night_in_a_storm_or_when_hurt_and_a_busy_person_is_never_social():
    config = cfg(feature_levers=())
    lonely = dict(lonely=14, others=(near_person(at=(2, 5)),))
    assert decide(idle_view(config, **lonely, sky=NIGHT), config).kind != GO_VISIT
    assert decide(idle_view(config, **lonely, sky=Sky("day", "storm", 9, 20)), config).kind != GO_VISIT
    assert decide(idle_view(config, **lonely, thirst=40, water=0), config).kind in ("go_water", "draw", "rest")   # a need is calling
    thirsty = decide(idle_view(config, **lonely, thirst=40, water=0), config)
    assert thirsty.kind != GO_VISIT and thirsty.kind != CHAT


def test_a_greeting_and_a_word_cost_nothing_and_go_to_the_right_people():
    config = cfg()
    cross = (bond("p03", 20, 50, 15, 30, "kept_food", 30),)
    others = (near_person("p02", (2, 3)), near_person("p03", (3, 2)), near_person("p04", (1, 2), asleep=True), near_person("p05", (2, 5)))
    seen = decide(idle_view(config, others=others, bonds=cross), config)
    assert seen.greeted == ("p02",) and seen.confronted == ("p03",)                # not the sleeper, not the one three away
    known = (bond("p02", 5, last=38),)
    assert decide(idle_view(config, others=others, bonds=known + cross), config).greeted == ()          # dealt with two ticks ago
    tried = (("confront", "p03", 35, 1),)
    assert decide(idle_view(config, others=others, bonds=cross, tried=tried), config).confronted == ()   # had it out five ticks ago
    working = decide(idle_view(config, others=others, thirst=40, water=0), config)
    assert working.kind in ("go_water", "draw") and working.greeted == ("p02", "p03")                    # even somebody busy says hello


def test_what_they_say_when_they_talk_is_their_home_and_the_wolf_news_they_hold_with_its_dates():
    config = cfg(features=FEATURES + ("wolves",))
    news = (("wolf", "w1", 6, 6, 30, 30, ""), ("wolf", "w2", 7, 7, 5, 5, ""))      # one seen ten ticks ago, one long ago
    said = decide(idle_view(config, lonely=5, others=(near_person(),), beliefs=news), config)
    assert said.kind == CHAT and said.told_to == ("p02",)
    assert said.told == (("home", "p01", 2, 2, 40), ("wolf", "w1", 6, 6, 30))       # home, then news no older than danger_span, original date kept
    plain = decide(idle_view(cfg(), lonely=5, others=(near_person(),)), cfg())
    assert plain.told == (("home", "p01", 2, 2, 40),)


def starving_pair(config, **changes):
    here = (5, 5)
    return view_for_help(config, here, (SeenPerson("p02", (5, 7), 0, starving=True), SeenPerson("p03", (5, 6), 0, starving=True)), **changes)


def view_for_help(config, here, others, **changes):
    return replace(idle_view(config, position=here, home=here, others=others), food=2, **changes)


def test_friends_come_first_when_somebody_chooses_whom_to_help_and_nobody_helps_one_they_resent():
    config = cfg()
    base = starving_pair(config)
    assert someone_to_help(base, config) == "p03"                                   # the nearer
    friends = replace(base, bonds=(bond("p02", 45, last=10),))
    assert someone_to_help(friends, config) == "p02"                                # a friend before a stranger who is nearer
    resented = replace(base, bonds=(bond("p03", 10, 50, 15, 30, "kept_food", 30),))
    assert someone_to_help(resented, config) == "p02"
    only_resented = replace(resented, others=(SeenPerson("p03", (5, 6), 0, starving=True),))
    assert someone_to_help(only_resented, config) is None
    own_child = replace(only_resented, dependents=frozenset({"p03"}))
    assert someone_to_help(own_child, config) == "p03"                              # their own child is fed regardless


def test_a_stingy_person_gives_their_last_unit_to_a_friend_but_not_to_a_stranger():
    config = cfg()
    stingy = (20, 50, 50, 50, 50)
    last_unit = replace(starving_pair(config, traits=stingy), food=1)
    assert someone_to_help(last_unit, config) is None
    assert someone_to_help(replace(last_unit, bonds=(bond("p02", 45, last=10),)), config) == "p02"


# --- who is believed -------------------------------------------------------------------------

def chat_world():
    config, ledger, world = scene()
    return config, replace(world, tick=40)


def tellings(decisions, bonds=None):
    config, world = chat_world()
    after = replace(world, tick=41)
    prior = replace(world, persona=replace(world.persona, bonds=bonds or {}))
    return advance_beliefs(prior, after, decisions, {}, config)


def test_a_quiet_word_is_heard_only_by_somebody_who_chose_to_talk_back():
    said = (("home", "p01", 5, 5, 40),)
    talking = Decision("p01", CHAT, "", (), target="p02", told_to=("p02",), told=said)
    answering = Decision("p02", CHAT, "", (), target="p01")
    assert tellings({"p01": talking, "p02": answering})["p02"] == (("home", "p01", 5, 5, 40, 40, "p01"),)
    assert "p02" not in tellings({"p01": talking, "p02": Decision("p02", "rest", "", ())})
    assert "p02" not in tellings({"p01": talking, "p02": Decision("p02", CHAT, "", (), target="p03")})
    alarm = Decision("p01", "flee", "", (), told_to=("p02",), told=(("wolf", "w1", 4, 4, 40),))
    assert tellings({"p01": alarm, "p02": Decision("p02", "rest", "", ())})["p02"][0][1] == "w1"     # a shout needs no answer


def test_somebody_who_is_not_trusted_is_not_believed():
    config, _ = chat_world()
    said = (("home", "p01", 5, 5, 40),)
    talking = Decision("p01", CHAT, "", (), target="p02", told_to=("p02",), told=said)
    answering = Decision("p02", CHAT, "", (), target="p01")
    wary = {"p02": (bond("p01", 10, config.lever("believe_at") - 1),)}
    assert "p02" not in tellings({"p01": talking, "p02": answering}, wary)
    willing = {"p02": (bond("p01", 10, config.lever("believe_at")),)}
    assert "p02" in tellings({"p01": talking, "p02": answering}, willing)
    assert trust_in(wary["p02"], "p01") == config.lever("believe_at") - 1


# --- whole worlds ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    path = tmp_path_factory.mktemp("society") / "run.jsonl"
    # Seed 11 held a quarrel until the optional-outing gate (a person does not set out on an optional outing that the leave-in-time
    # rule for warmth would turn round after one step) changed that world's course; quarrels are rare, so this is the first
    # seed from 11 up whose 300-tick world holds every kind of event the tests below look for. The assertions are unchanged.
    config = WorldConfig(seed=28, features=FEATURES)
    run_world(config, 300, path)
    return config, path, read_run(path)


def bonds_in(world):
    return (world["persona"].get("bonds") or {})


def changes(run):
    """Every bond that changed in a tick: (tick index, owner, other, old entry or None, new entry)."""
    before = run.header["world"]
    for index, tick in enumerate(run.ticks):
        old = {a: {e[0]: e for e in entries} for a, entries in bonds_in(before).items()}
        for actor, entries in bonds_in(tick["world"]).items():
            for entry in entries:
                was = old.get(actor, {}).get(entry[0])
                if was != list(entry) and was != entry:
                    yield index, actor, entry[0], was, entry
        before = tick["world"]


@pytest.mark.long_run
def test_a_social_world_audits_replays_and_recovers(saved, tmp_path):
    _, path, run = saved
    assert run.complete and audit_run(run) == []
    assert replay_world(path).identical
    lines = path.read_bytes().splitlines(keepends=True)
    chosen = next(i for i, c in enumerate(changes(run)) if c[4][7] == "quarrel")
    quarrel_tick = [c for c in changes(run) if c[4][7] == "quarrel"][0][0] + 2
    end = next(i for i, line in enumerate(lines)
               if json.loads(line).get("kind") == "tick" and json.loads(line)["tick"] == quarrel_tick - 1)
    cut, restored = tmp_path / "cut.jsonl", tmp_path / "restored.jsonl"
    cut.write_bytes(b"".join(lines[:end + 1]))
    recover_world(cut, restored)
    assert read_run(restored).ticks == run.ticks and chosen >= 0


@pytest.mark.long_run
def test_every_warm_word_and_hello_in_a_saved_run_was_chosen_by_both_people_in_reach(saved):
    config, _, run = saved
    reach, seen_warm, seen_hello = config.lever("talk_range"), 0, 0
    previous = run.header["world"]
    for index, tick in enumerate(run.ticks):
        positions = {a: tuple(p) for a, p in previous["positions"].items()}
        decisions = tick["decisions"]
        for actor, entries in bonds_in(tick["world"]).items():
            for other, level, trust, grudge, last, why, grieved, tone in entries:
                if last != index or tone not in ("warm", "greeting"):
                    continue
                near = max(abs(positions[actor][0] - positions[other][0]), abs(positions[actor][1] - positions[other][1])) <= reach
                assert near and actor not in (previous["persona"].get("asleep") or {}) and other not in (previous["persona"].get("asleep") or {})
                if tone == "warm":
                    assert decisions[actor]["kind"] == "chat" and decisions[actor]["target"] == other
                    assert decisions[other]["kind"] == "chat" and decisions[other]["target"] == actor
                    seen_warm += 1
                else:
                    assert other in decisions[actor].get("greeted", []) and actor in decisions[other].get("greeted", [])
                    seen_hello += 1
        previous = tick["world"]
    assert seen_warm > 10 and seen_hello > 50


@pytest.mark.long_run
def test_every_grudge_in_a_saved_run_grew_because_of_something_the_run_recorded(saved):
    config, _, run = saved
    causes = {"beat_to_it": 0, "kept_food": 0, "quarrel": 0}
    for index, owner, other, was, entry in changes(run):
        if entry[3] <= (was[3] if was else 0) or entry[6] != index:
            continue                                                               # the grudge did not grow on this tick
        tick = run.ticks[index]
        before = run.ticks[index - 1]["world"] if index else run.header["world"]
        outcomes = tick["record"]["outcomes"]
        sees = lambda a, b: b in tick["observations"][a]["sees"]
        beat = (any(o["actor"] == owner and o["operation"] == "claim" and o["reason"] == "denied_insufficient_source" for o in outcomes)
                and any(o["actor"] == other and o["operation"] == "claim" and o["accepted"] for o in outcomes) and sees(owner, other))
        kept = (before["hunger"][owner] >= config.emergency_at and sees(owner, other) and sees(other, owner)
                and tick["decisions"][other]["kind"] in ("rest", "home", "build") and before["hunger"][other] < config.emergency_at)
        words = owner in tick["decisions"][other].get("confronted", []) or other in tick["decisions"][owner].get("confronted", [])
        assert beat or kept or words, (index, owner, other, entry)
        for name, held in (("beat_to_it", beat), ("kept_food", kept), ("quarrel", words)):
            causes[name] += held
    assert causes["beat_to_it"] > 0 and sum(causes.values()) > 3


@pytest.mark.long_run
def test_every_home_somebody_learned_traces_to_a_conversation_the_run_recorded(saved):
    _, _, run = saved
    before, checked = run.header["world"], 0
    for index, tick in enumerate(run.ticks):
        old = {(a, e[0], e[1]): e for a, es in ((before["persona"].get("beliefs")) or {}).items() for e in es}
        for actor, entries in ((tick["world"]["persona"].get("beliefs")) or {}).items():
            for kind, subject, x, y, seen, learned, via in entries:
                if kind != "home" or old.get((actor, kind, subject)) == [kind, subject, x, y, seen, learned, via]:
                    continue
                assert via == subject                                                    # a person tells where they themselves live
                assert [x, y] == list(before["homes"][subject])                          # where they lived when they said so
                speaker, listener = tick["decisions"][via], tick["decisions"][actor]
                assert speaker["kind"] == "chat" and speaker["target"] == actor and listener["target"] == via
                assert actor in speaker["told_to"] and ["home", via, x, y, seen] in speaker["told"] and learned == index
                checked += 1
        before = tick["world"]
    assert checked > 3


@pytest.mark.long_run
def test_a_person_decides_from_their_own_bonds_and_never_from_how_somebody_else_feels(saved):
    config, _, run = saved
    ledger, world = genesis(config)
    world = replace(world, tick=40)
    others = {a: (bond("p01", 90, 5, 40, 30, "quarrel", 30),) for a in ("p02", "p03", "p04")}
    angry = replace(world, persona=replace(world.persona, bonds=others))
    ledger = replace(ledger, tick=40)
    for actor in ("p01", "p05"):
        calm_view, angry_view = observe(actor, ledger, world, config), observe(actor, ledger, angry, config)
        assert calm_view == angry_view and decide(calm_view, config) == decide(angry_view, config)


@pytest.mark.long_run
def test_the_page_shows_relationships_and_the_index_tells_the_story(saved):
    _, _, run = saved
    assert "societyPart" in render_html(run)
    kinds = {e["kind"] for e in build_index(run)["events"]}
    assert {"met", "talked", "friends", "grudge", "quarrel", "apology", "forgave", "learned_home"} <= kinds


@pytest.mark.long_run
def test_the_browser_shows_somebodys_friends_and_what_they_hold_against_people(saved, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Rich viewer test requires Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    _, _, run = saved
    event = next(e for e in build_index(run)["events"] if e["kind"] == "grudge" and e["k"] > 3)
    page = tmp_path / "society.html"
    page.write_text(render_html(run), encoding="utf-8")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/rich_viewer.cjs"), page.as_uri(),
                             str(event["k"]), event["who"]], cwd=ROOT, capture_output=True, text=True, timeout=90)   # the tick it began
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout)
    assert shown["errors"] == []
    text = shown["inspector"].lower()
    for expected in ("relationships", f"{event['other']}", "holds a grudge", "got the food or water i was after", "company",
                     "only what this person has seen"):
        assert expected in text, expected
    assert {"bonds", "beliefs"} <= set(shown["chips"]) and "Friends and quarrels" in " ".join(shown["eventCategories"])
    assert "feature: bonds" in shown["rules"]


def test_without_the_bonds_feature_nothing_social_is_recorded(tmp_path):
    path = tmp_path / "plain.jsonl"
    run_world(WorldConfig(seed=11, features=("beliefs", "sky")), 120, path)
    run = read_run(path)
    assert all(not {"greeted", "confronted"} & set(d) for t in run.ticks for d in t["decisions"].values())
    assert all(not (t["world"].get("persona") or {}).get("bonds") for t in run.ticks)
