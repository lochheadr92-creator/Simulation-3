"""Index events for friendships, quarrels and talk, from recorded values only.

A conversation starts on the tick somebody's saved `talking` first names a partner. A friendship is a saved
bond rising across the declared friend level; a grudge, a quarrel, an apology and a forgiveness are saved
grudges, tones and levels changing. News passed on is a saved belief with somebody else's name on it. The
run recorded who was told what, and by whom; nothing here asks who could have heard.
"""

from __future__ import annotations

from typing import Any, Mapping


def _event(k: int, kind: str, text: str, who: str | None = None, other: str | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {"k": k, "cat": "social", "kind": kind, "text": text}
    if who:
        event["who"] = who
    if other:
        event["other"] = other
    return event


def society_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "bonds" not in set(cfg.get("features") or []):
        return []
    levers = cfg.get("feature_levers") or {}
    friend_at = levers.get("friend_at")
    reasons = (cfg.get("feature_tables") or {}).get("grievances") or {}
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        before, world = worlds[k - 1], worlds[k]
        pb, pw = before.get("persona") or {}, world.get("persona") or {}
        talking_before, talking_now = pb.get("talking") or {}, pw.get("talking") or {}
        for actor, (partner, since) in sorted(talking_now.items()):
            began = actor not in talking_before or talking_before[actor][0] != partner
            if began and actor < partner:
                out.append(_event(k, "talked", f"{actor} and {partner} stopped to talk", who=actor, other=partner))
        old_bonds, new_bonds = pb.get("bonds") or {}, pw.get("bonds") or {}
        for actor, entries in sorted(new_bonds.items()):
            earlier = {e[0]: e for e in old_bonds.get(actor, [])}
            for other, bond, trust, grudge, last, why, grieved, tone in entries:
                was = earlier.get(other)
                was_bond, was_grudge = (was[1], was[3]) if was else (0, 0)
                fresh = last == k - 1
                if was is None and tone == "greeting" and actor < other:
                    out.append(_event(k, "met", f"{actor} and {other} said hello for the first time", who=actor, other=other))
                if friend_at is not None and was_bond < friend_at <= bond:
                    out.append(_event(k, "friends", f"{actor} came to think of {other} as a friend", who=actor, other=other))
                if grudge and not was_grudge:
                    out.append(_event(k, "grudge", f"{actor} resents {other}, who {reasons.get(why, why)}", who=actor, other=other))
                if was_grudge and not grudge:
                    out.append(_event(k, "forgave", f"{actor} no longer holds anything against {other}", who=actor, other=other))
                if fresh and tone == "quarrel" and actor < other and (was is None or was[7] != "quarrel" or was[4] != last):
                    out.append(_event(k, "quarrel", f"{actor} and {other} quarrelled", who=actor, other=other))
                if fresh and tone == "apology" and grudge < was_grudge:
                    out.append(_event(k, "apology", f"{other} apologised to {actor}; the grudge eased", who=other, other=actor))
        old_beliefs, new_beliefs = pb.get("beliefs") or {}, pw.get("beliefs") or {}
        for actor, entries in sorted(new_beliefs.items()):
            known = {(e[0], e[1]) for e in old_beliefs.get(actor, [])}
            for kind, subject, x, y, seen, learned, via in entries:
                if kind == "home" and via and (kind, subject) not in known:
                    out.append(_event(k, "learned_home", f"{actor} learned where {subject} lives, from {via}", who=actor, other=via))
    return out
