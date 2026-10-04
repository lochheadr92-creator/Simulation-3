"""Index events for requests, promises and shared meals, from recorded values only.

A request is a saved pledge that first appears; a promise is that pledge turning from asked to promised; every
ending is a line the run saved for the tick it happened, with its reason. A hosted meal is a saved decision, and
a shared meal is two saved eating decisions on one cell in one tick. Nothing here asks who could have heard.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

# the kind of drawing the page already has for each ending
DRAWN = {"kept": "kept", "declined": "refused", "no_answer": "unanswered"}


def _what(kind: str, amount: int) -> str:
    return {"water": f"{amount} water", "food": f"{amount} food", "wood": f"{amount} wood",
            "build": f"{amount} ticks of help building", "news": "news of the wolf"}.get(kind, kind)


def _event(k: int, kind: str, stage: str, text: str, who: str, other: str, **extra: Any) -> dict[str, Any]:
    return {"k": k, "cat": "help", "kind": kind, "stage": stage, "pledge": 1, "text": text, "who": who, "other": other,
            **extra}


def pledge_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "pledges" not in set(cfg.get("features") or []):
        return []
    reasons = (cfg.get("feature_tables") or {}).get("reasons") or {}
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        before, world = worlds[k - 1], worlds[k]
        decisions = run.ticks[k - 1].get("decisions") or {}
        pb, pw = before.get("pledges") or {}, world.get("pledges") or {}
        was = {(p[1], p[4]): p for p in pb.get("open", [])}
        for p in pw.get("open", []):
            kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, done = p
            earlier = was.get((asker, made))
            if state == "asked" and earlier is None:
                text = (f"{asker} asked {helper} whether they had seen the wolf" if kind == "news"
                        else f"{asker} asked {helper} for {_what(kind, amount)}")
                out.append(_event(k, "ask", "asked", text, asker, helper, what=kind))
            elif state == "promised" and earlier is not None and earlier[3] == "asked":
                how = " (they will fetch it)" if kind == "wood" and not held else ""
                text = (f"{helper} agreed to help {asker} build" if kind == "build"
                        else f"{helper} promised {asker} {_what(kind, amount)}{how}")
                out.append(_event(k, "agree", "promised", text, helper, asker, what=kind))
        for kind, asker, helper, outcome, reason, tick in pw.get("closed", []):
            why = reasons.get(reason, reason)
            if outcome == "kept":
                text = (f"{helper} told {asker} what they knew of the wolf" if kind == "news"
                        else f"{helper} kept their word to {asker}: {why}")
                out.append(_event(k, "kept", "kept", text, helper, asker, what=kind, reason=reason))
            elif outcome == "declined":
                out.append(_event(k, "refused", "declined", f"{helper} told {asker} no: {why}", helper, asker,
                                  what=kind, reason=reason))
            elif outcome == "expired" and reason == "no_answer":
                out.append(_event(k, "unanswered", "no_answer", f"{asker}'s request to {helper} got no answer", asker, helper,
                                  what=kind, reason=reason))
            elif outcome == "expired" and reason == "not_needed":
                out.append(_event(k, "too_late", "not_needed", f"{helper}'s help for {asker} was not needed in the end",
                                  helper, asker, what=kind, reason=reason))
            elif outcome == "expired":
                out.append(_event(k, "too_late", "broken", f"{helper}'s promise to {asker} ran out of time", helper, asker,
                                  what=kind, reason=reason))
            elif outcome == "failed":
                out.append(_event(k, "too_late", "broken", f"{helper} broke their promise to {asker}: {why}", helper, asker,
                                  what=kind, reason=reason))
            else:
                out.append(_event(k, "too_late", "cut_short", f"{helper}'s promise to {asker} was cut short: {why}", helper, asker,
                                  what=kind, reason=reason))
        eating: dict[tuple[int, int], list[str]] = defaultdict(list)
        for actor in sorted(decisions):
            d = decisions[actor]
            if d.get("kind") == "host" and d.get("target"):
                out.append({"k": k, "cat": "help", "kind": "gave", "stage": "hosted", "pledge": 1, "who": actor,
                            "other": d["target"], "text": f"{actor} shared a meal with {d['target']} at their door"})
            if d.get("kind") == "eat" and actor in (before.get("positions") or {}) and actor not in (before.get("died_at") or {}):
                eating[tuple(before["positions"][actor])].append(actor)
        for cell, people in sorted(eating.items()):
            if len(people) >= 2:
                out.append({"k": k, "cat": "help", "kind": "meal", "stage": "meal", "who": people[0], "other": people[1],
                            "text": f"{' and '.join(people)} ate together at {cell}"})
    return out
