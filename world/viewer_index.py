"""What the map viewer shows, read out of a saved run once.

The page (world/viewer.js) draws; this module reads. It turns a saved run into
the things a person watching wants to find: who was born, who died and of
what, who asked whom for food and what came of it, who carried what to whom,
when a shelter went up, when a source ran out. It is built once when the page
is written, so the page never has to rescan the whole run while you scrub.

Everything here is a value the run recorded, or a plain comparison between
recorded values and the thresholds the run's own header declares ("hunger 52
is past emergency_at 50"). No world rule is run again: nothing here imports
decide, observe or process, nothing predicts what somebody would have done,
and a run that did not record something (an old file with no asking, no
water, no terrain) simply has none of it in the index.

View k is the world after k ticks: view 0 is genesis, and view k carries the
decisions and outcomes of the tick that produced it (tick line k - 1).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

# What each recorded decision kind looks like in plain words. The page uses the
# same table, so a new kind the world grows shows up as its own name until a
# phrase is added here.
ACTION_PHRASES: dict[str, str] = {
    "eat": "eating",
    "claim": "gathering food",
    "wait": "waiting at an empty food source",
    "yield": "standing back from a crowded source",
    "go": "walking to food",
    "home": "walking home",
    "rest": "resting at home",
    "build": "building a shelter",
    "offer": "handing over food",
    "go_offer": "carrying food to somebody",
    "ask": "asking for food while walking on",
    "agree": "agreeing to bring somebody food",
    "drink": "drinking",
    "draw": "drawing water",
    "wait_water": "waiting at a dry well",
    "go_water": "walking to water",
    "warm": "warming up at home",
    "go_shelter": "heading home to get warm",
    "dead": "dead",
}

# Short labels for the alternatives a person had, as chips in the inspector.
ACTION_LABELS: dict[str, str] = {
    "eat": "eat", "claim": "take food", "wait": "wait for food", "yield": "stand back",
    "go": "go to food", "home": "go home", "rest": "rest", "build": "build",
    "offer": "hand over food", "go_offer": "carry food over", "ask": "ask for food",
    "agree": "agree to help", "drink": "drink", "draw": "draw water",
    "wait_water": "wait for water", "go_water": "go to water", "warm": "warm up",
    "go_shelter": "go home to warm", "dead": "dead",
}

# Event categories, in the order the page lists its filters.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("life", "Births and deaths"),
    ("help", "Asking and helping"),
    ("need", "Emergencies"),
    ("build", "Shelters"),
    ("food", "Food"),
    ("water", "Water"),
    ("source", "Sources running out"),
    ("crowd", "Standing back"),
)

MOVES = frozenset({"go", "home", "go_offer", "go_water", "go_shelter", "ask"})


def food_sources(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every food source a header declares: `food_sources` when there are
    several (from 2026-09-26), else the one `source`."""
    listed = cfg.get("food_sources")
    if listed:
        return [dict(entry) for entry in listed]
    if "source" in cfg and "source_position" in cfg:
        return [{"id": cfg["source"], "position": cfg["source_position"]}]
    return []


def water_sources(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if cfg.get("water") != "on":
        return []
    listed = cfg.get("water_sources")
    if listed:
        return [dict(entry) for entry in listed]
    return [{"id": cfg["water_source"], "position": cfg["water_position"]}]


def worlds_of(run: Any) -> list[dict[str, Any]]:
    """The overlay at every view. A damaged tick line with no world block keeps
    the last world the file did record, rather than inventing one."""
    out = [run.header.get("world") or {}]
    for tick in run.ticks:
        out.append(tick.get("world") or out[-1])
    return out


def stock_at(run: Any, view: int, source_id: str) -> int | None:
    """Stock of one source at a view: what settlement left plus any renewal
    recorded on the same tick line (the file's own production entries)."""
    try:
        if view == 0:
            return int(run.header["genesis"]["sources"][source_id]["stock"])
        tick = run.ticks[view - 1]
        stock = int(tick["state"]["sources"][source_id]["stock"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return stock + sum(entry.get("amount", 0) for entry in (tick.get("production") or [])
                       if entry.get("source") == source_id)


def settled_stock(run: Any, view: int, source_id: str) -> int | None:
    """Stock straight after settlement at a view, before any renewal."""
    if view == 0:
        return stock_at(run, 0, source_id)
    try:
        return int(run.ticks[view - 1]["state"]["sources"][source_id]["stock"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _gained(outcome: Mapping[str, Any], account: str) -> int:
    return sum(effect.get("delta", 0) for effect in outcome.get("effects", [])
               if effect.get("account") == account and effect.get("delta", 0) > 0)


def _plain_refusal(reason: str) -> str:
    return {
        "denied_insufficient_source": "there was nothing left",
        "denied_insufficient_balance": "there was nothing in hand to give",
        "denied_unauthorised": "they were not allowed to take from it",
        "denied_self_transfer": "you cannot hand something to yourself",
    }.get(reason, reason.replace("denied_", "").replace("_", " "))


def _cause_of_death(world: Mapping[str, Any], actor: str, cfg: Mapping[str, Any]) -> str:
    """Which recorded need stood at or past its declared lethal level."""
    if "death_at" in cfg and world.get("hunger", {}).get(actor, -1) >= cfg["death_at"]:
        return "starved"
    if "thirst_death_at" in cfg and world.get("thirst", {}).get(actor, -1) >= cfg["thirst_death_at"]:
        return "died of thirst"
    if "cold_death_at" in cfg and world.get("cold", {}).get(actor, -1) >= cfg["cold_death_at"]:
        return "froze to death"
    return "died"


def _phrase(decision: Mapping[str, Any] | None) -> str:
    if not decision:
        return "doing nothing recorded"
    return ACTION_PHRASES.get(decision.get("kind", ""), str(decision.get("kind", "")))


def build_index(run: Any) -> dict[str, Any]:
    """Read a saved world run once into everything the page lists, links and
    counts. Pure: the same run always gives the same index."""
    cfg = run.header.get("scenario", {}) or {}
    ticks = run.ticks
    n = len(ticks)
    worlds = worlds_of(run)
    people = sorted({actor for world in worlds for actor in world.get("positions", {})})
    food = food_sources(cfg)
    water = water_sources(cfg)
    build_ticks = cfg.get("build_ticks")

    events: list[dict[str, Any]] = []
    born: dict[str, int] = {}
    died: dict[str, dict[str, Any]] = {}
    threads: list[dict[str, Any]] = []
    open_threads: dict[str, dict[str, Any]] = {}      # helper -> the agreed thread they are carrying
    waiting: dict[str, dict[str, Any]] = {}           # asker -> the thread waiting on an answer

    def add(k: int, cat: str, kind: str, text: str, who: str | None = None,
            other: str | None = None, src: str | None = None, amount: int | None = None) -> None:
        event: dict[str, Any] = {"k": k, "cat": cat, "kind": kind, "text": text}
        if amount is not None:
            event["amount"] = amount
        if who:
            event["who"] = who
        if other:
            event["other"] = other
        if src:
            event["src"] = src
        events.append(event)

    adult_at = cfg.get("adult_at") if cfg.get("childhood") == "on" else None

    def children_in(world: Mapping[str, Any]) -> int:
        """Living people the run records as not yet grown."""
        if adult_at is None:
            return 0
        ages, dead = world.get("age", {}), world.get("died_at", {})
        return sum(1 for actor, lived in ages.items() if lived < adult_at and actor not in dead)

    counts = {name: [0] * (n + 1) for name in
              ("alive", "people", "dead", "born", "shelters", "asked", "agreed", "unanswered",
               "delivered", "handed", "refused", "claims", "draws", "children", "fed_children")}
    first = worlds[0]
    counts["people"][0] = len(first.get("positions", {}))
    counts["alive"][0] = counts["people"][0] - len(first.get("died_at", {}))
    counts["dead"][0] = len(first.get("died_at", {}))
    counts["shelters"][0] = len(first.get("shelters", []))
    counts["children"][0] = children_in(first)

    for k in range(1, n + 1):
        tick = ticks[k - 1]
        world, before = worlds[k], worlds[k - 1]
        decisions: Mapping[str, Any] = tick.get("decisions") or {}
        earlier: Mapping[str, Any] = (ticks[k - 2].get("decisions") or {}) if k >= 2 else {}
        outcomes: dict[str, dict[str, Any]] = {}
        for outcome in (tick.get("record") or {}).get("outcomes", []):
            outcomes.setdefault(outcome.get("actor"), outcome)
        positions = world.get("positions", {})
        died_at, died_before = world.get("died_at", {}), before.get("died_at", {})
        promises_before = before.get("promises", {}) or {}
        promises_now = world.get("promises", {}) or {}
        parent_of = world.get("parent", {}) or {}         # child -> parent, recorded from birth on
        tally = {name: 0 for name in counts}

        # answers first: a request made last tick is answered, or lapses, on this one
        for asker, asked in sorted((before.get("requests") or {}).items()):
            thread = waiting.pop(asker, None)
            answer = decisions.get(asked)
            if answer and answer.get("kind") == "offer" and answer.get("target") == asker:
                if thread is not None:
                    thread.update(answer="agreed", answered=k, direct=True)
                    open_threads[asked] = thread
                add(k, "help", "handoff", f"{asked} answered {asker} with a direct handoff", who=asked, other=asker)
                tally["agreed"] += 1
                continue
            if answer and answer.get("kind") == "agree" and answer.get("target") == asker:
                if thread is not None:
                    thread.update(answer="agreed", answered=k)
                    open_threads[asked] = thread
                add(k, "help", "agree", f"{asked} agreed to bring {asker} food", who=asked, other=asker)
                tally["agreed"] += 1
                continue
            if asked in died_before:
                why = f"{asked} had died"
            elif answer is None:
                why = f"{asked} could not answer"
            else:
                why = f"{asked} was {_phrase(answer)}"
            if thread is not None:
                thread.update(answer="no answer", answered=k, end="no answer", ended=k, busy=_phrase(answer))
            add(k, "help", "unanswered", f"{asked} didn't answer {asker} ({why})", who=asker, other=asked)
            tally["unanswered"] += 1

        for actor in sorted(positions):
            if actor not in before.get("positions", {}):
                continue                                   # born at the end of this tick: no decision yet
            if actor in died_before:
                continue
            decision = decisions.get(actor) or {}
            kind = decision.get("kind")
            target = decision.get("target")
            outcome = outcomes.get(actor)
            if kind == "ask" and target:
                thread = {"asker": actor, "helper": target, "asked": k, "answer": "waiting"}
                threads.append(thread)
                waiting[actor] = thread
                add(k, "help", "ask", f"{actor} asked {target} for food", who=actor, other=target)
                tally["asked"] += 1
            elif kind == "yield":
                where = target or cfg.get("source", "the source")
                add(k, "crowd", "yield", f"{actor} stood back from the crowd at {where}", who=actor, src=where)
            elif kind in ("claim", "draw") and outcome is not None:
                resource, account = ("food", f"actor:{actor}") if kind == "claim" else ("water", f"actor@water:{actor}")
                where = target or (cfg.get("source") if kind == "claim" else cfg.get("water_source"))
                if outcome.get("accepted"):
                    got = _gained(outcome, account)
                    verb = "took" if kind == "claim" else "drew"
                    add(k, resource, kind, f"{actor} {verb} {got} {resource} at {where}", who=actor, src=where, amount=got)
                    tally["claims" if kind == "claim" else "draws"] += 1
                else:
                    add(k, resource, kind + "_refused",
                        f"{actor} came away from {where} empty-handed: {_plain_refusal(outcome.get('reason', ''))}",
                        who=actor, src=where)
            elif kind in ("eat", "drink") and outcome is not None and outcome.get("accepted"):
                need = "hunger" if kind == "eat" else "thirst"
                was, now = before.get(need, {}).get(actor), world.get(need, {}).get(actor)
                verb = "ate" if kind == "eat" else "drank"
                change = f" ({need} {was} → {now})" if was is not None and now is not None else ""
                add(k, "food" if kind == "eat" else "water", kind, f"{actor} {verb}{change}", who=actor)
            elif kind == "offer" and target and outcome is not None:
                dependent = (parent_of.get(target) == actor and adult_at is not None
                             and before.get("age", {}).get(target, adult_at) < adult_at)
                direct = (before.get("requests") or {}).get(target) == actor
                promised = promises_before.get(actor) == target or direct
                if outcome.get("accepted"):
                    if dependent:
                        tally["fed_children"] += 1
                    if promised:
                        add(k, "help", "delivered", f"{actor} delivered the food {target} asked for",
                            who=actor, other=target)
                        tally["delivered"] += 1
                        thread = open_threads.pop(actor, None)
                        if thread is not None:
                            thread.update(end="delivered", ended=k)
                    elif dependent:
                        add(k, "help", "fed_child", f"{actor} fed their child {target}", who=actor, other=target)
                    else:
                        add(k, "help", "gave", f"{actor} handed {target} a unit of food", who=actor, other=target)
                    tally["handed"] += 1
                else:
                    add(k, "help", "refused",
                        f"{actor} tried to hand {target} food, but it was refused: "
                        f"{_plain_refusal(outcome.get('reason', ''))}", who=actor, other=target)
                    tally["refused"] += 1
                    if direct:
                        thread = open_threads.pop(actor, None)
                        if thread is not None:
                            thread.update(end="refused", ended=k)
            was = earlier.get(actor) or {}
            if kind == "go_offer" and target and not (was.get("kind") == "go_offer" and was.get("target") == target):
                if promises_before.get(actor) == target:
                    add(k, "help", "set_out", f"{actor} set off with food for {target}", who=actor, other=target)
                elif parent_of.get(target) == actor:
                    add(k, "help", "set_out", f"{actor} set off with food for their child {target}",
                        who=actor, other=target)
                else:
                    add(k, "help", "set_out", f"{actor} set off to help {target}, who looked to be starving",
                        who=actor, other=target)
            if was.get("kind") == "go_offer" and kind not in ("go_offer", "offer", None) and actor not in died_at:
                if promises_before.get(actor) == was.get("target"):
                    thread = open_threads.get(actor)
                    if thread is not None:
                        thread["detours"] = thread.get("detours", 0) + 1
                    add(k, "help", "turned_aside",
                        f"{actor} turned aside from bringing {was.get('target')} food: {_phrase(decision)}",
                        who=actor, other=was.get("target"))
                else:
                    add(k, "help", "turned_aside",
                        f"{actor} stopped heading for {was.get('target')} and is {_phrase(decision)}",
                        who=actor, other=was.get("target"))
            if kind == "build":
                done, had = world.get("built", {}).get(actor, 0), before.get("built", {}).get(actor, 0)
                if had == 0 and done > 0:
                    add(k, "build", "build_start", f"{actor} started building a shelter at home", who=actor)
                if build_ticks and done >= build_ticks > had:
                    add(k, "build", "build_done", f"{actor} finished a shelter ({done} ticks of work)", who=actor)
            if actor in died_at and actor not in died_before:
                continue                                    # the death line says it all
            if adult_at is not None:
                lived, had_lived = world.get("age", {}).get(actor), before.get("age", {}).get(actor)
                if lived is not None and had_lived is not None and lived >= adult_at > had_lived:
                    add(k, "life", "grew_up", f"{actor} grew up", who=actor)
            for need, level, words in (("hunger", "emergency_at", "is starving"),
                                       ("thirst", "thirst_emergency_at", "is parched"),
                                       ("cold", "cold_emergency_at", "is freezing")):
                if level not in cfg or need not in world:
                    continue
                now, was_level = world[need].get(actor), before.get(need, {}).get(actor)
                if now is not None and was_level is not None and now >= cfg[level] > was_level:
                    add(k, "need", need, f"{actor} {words} ({need} {now})", who=actor)

        for actor in sorted(died_at):
            if actor in died_before or actor not in positions:
                continue
            cause = _cause_of_death(world, actor, cfg)
            died[actor] = {"k": k, "cause": cause, "at": list(positions[actor])}
            add(k, "life", "death", f"{actor} {cause}", who=actor)
            carrying = open_threads.pop(actor, None)
            if carrying is not None:
                carrying.update(end="helper died", ended=k)
            for helper, owed in sorted(promises_before.items()):
                if owed == actor and helper not in (promises_now or {}):
                    thread = open_threads.pop(helper, None)
                    if thread is not None:
                        thread.update(end="asker died", ended=k)
                    add(k, "help", "too_late", f"{actor} died before {helper} arrived with food",
                        who=helper, other=actor)

        for asker, thread in list(waiting.items()):
            helper = thread["helper"]
            if asker in died_at or helper in died_at:
                reason = "asker died" if asker in died_at else "helper died"
                thread.update(answer="interrupted", end=reason, ended=k)
                waiting.pop(asker)
                add(k, "help", "request_ended", f"Request from {asker} to {helper} ended: {reason}",
                    who=asker, other=helper)

        for helper, thread in list(open_threads.items()):
            asker = thread["asker"]
            if helper in died_at or asker in died_at or promises_now.get(helper) != asker:
                reason = "helper died" if helper in died_at else "asker died" if asker in died_at else "errand ended without delivery"
                thread.update(end=reason, ended=k)
                open_threads.pop(helper)
                add(k, "help", "errand_ended", f"{helper}'s errand for {asker} ended: {reason}",
                    who=helper, other=asker)

        for entry in tick.get("production") or []:
            if "born" in entry:
                born[entry["born"]] = k
                mother = parent_of.get(entry["born"])
                add(k, "life", "birth", f"{entry['born']} was born" + (f" to {mother}" if mother else ""),
                    who=entry["born"], other=mother)
                tally["born"] += 1

        for source, word_out, word_back, kind in [(s, "was picked clean", "is growing back", "food") for s in food] + \
                                                 [(s, "ran dry", "is filling again", "water") for s in water]:
            sid = source["id"]
            now, was_stock = settled_stock(run, k, sid), stock_at(run, k - 1, sid)
            if now == 0 and was_stock:
                add(k, "source", kind + "_out", f"{sid} {word_out}", src=sid)
            grew = sum(entry.get("amount", 0) for entry in (tick.get("production") or [])
                       if entry.get("source") == sid)
            if grew and now == 0:
                add(k, "source", kind + "_back", f"{sid} {word_back} (+{grew})", src=sid)

        counts["people"][k] = len(positions)
        counts["dead"][k] = len(died_at)
        counts["alive"][k] = len(positions) - len(died_at)
        counts["shelters"][k] = len(world.get("shelters", []))
        counts["children"][k] = children_in(world)
        for name in ("born", "asked", "agreed", "unanswered", "delivered", "handed", "refused", "claims", "draws",
                     "fed_children"):
            counts[name][k] = counts[name][k - 1] + tally[name]

    for thread in threads:
        if "end" not in thread:
            thread["end"] = "still carrying at the end" if thread.get("answer") == "agreed" else "waiting at the end"

    return {
        "people": people,
        "born": born,
        "died": died,
        "events": events,
        "threads": threads,
        "counts": counts,
        "categories": [list(pair) for pair in CATEGORIES],
        "phrases": ACTION_PHRASES,
        "labels": ACTION_LABELS,
        "moves": sorted(MOVES),
        "food": food,
        "water": water,
        "adult_at": adult_at,
        "parent": dict(worlds[-1].get("parent", {}) or {}),
    }


def events_for(index: Mapping[str, Any], actor: str) -> Iterable[dict[str, Any]]:
    """Every event naming this person, on either side."""
    return (event for event in index["events"] if actor in (event.get("who"), event.get("other")))
