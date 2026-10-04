"""Index events for wolves and what people believe about them, from recorded values only.

A wolf arrives when the saved things first list one. A sighting or a warning is a belief that is new or
fresher than the one before it; a bite is a rise in somebody's saved hurt; running, putting a trip off and
taking a risk are saved decision fields. Nothing here looks at a wolf's position to decide who could see it:
the run recorded who did.
"""

from __future__ import annotations

from typing import Any, Mapping

RESIGHT_AFTER = 6          # a wolf seen again after this many ticks is news again; in between it is the same sighting


def _event(k: int, kind: str, text: str, who: str | None = None, other: str | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {"k": k, "cat": "danger", "kind": kind, "text": text}
    if who:
        event["who"] = who
    if other:
        event["other"] = other
    return event


def wolf_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "wolves" not in set(cfg.get("features") or []):
        return []
    levers = cfg.get("feature_levers") or {}
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        tick = run.ticks[k - 1]
        before, world = worlds[k - 1], worlds[k]
        decisions: Mapping[str, Any] = tick.get("decisions") or {}
        earlier: Mapping[str, Any] = (run.ticks[k - 2].get("decisions") or {}) if k >= 2 else {}
        wb = {w[0]: w for w in (before.get("things") or {}).get("wolves", [])}
        wa = {w[0]: w for w in (world.get("things") or {}).get("wolves", [])}
        if wa and not wb:
            out.append(_event(k, "wolves_arrive", f"{len(wa)} wolves came in from the edge of the map"))
        limit = levers.get("chase_limit")
        for wid, now in sorted(wa.items()):
            was = wb.get(wid)
            if was is not None and limit is not None and was[4] >= limit and now[4] == 0 and now[3] > 0:
                out.append(_event(k, "wolf_gave_up", f"{wid} gave up the chase"))
        pb, pw = before.get("persona") or {}, world.get("persona") or {}
        for actor, entries in sorted((pw.get("beliefs") or {}).items()):
            old = {(e[0], e[1]): e for e in (pb.get("beliefs") or {}).get(actor, [])}
            for kind, subject, x, y, seen, learned, via in entries:
                prev = old.get((kind, subject))
                if prev is not None and (prev[4] >= seen or (via == "" and seen - prev[4] <= RESIGHT_AFTER)):
                    continue
                if via:
                    ago = learned - seen
                    out.append(_event(k, "warned", f"{via} warned {actor} of {subject} near {(x, y)}"
                                      + (f" (seen {ago} ticks before)" if ago else ""), who=actor, other=via))
                elif prev is None or seen - prev[4] > RESIGHT_AFTER:
                    out.append(_event(k, "wolf_sighted", f"{actor} saw {subject} near {(x, y)}", who=actor))
        hurt_before = pb.get("hurt") or {}
        died_before = before.get("died_at") or {}
        for actor, level in sorted((pw.get("hurt") or {}).items()):
            if level > hurt_before.get(actor, 0) and actor not in died_before:
                if actor in (world.get("died_at") or {}):
                    out.append(_event(k, "killed_by_wolf", f"{actor} was killed by a wolf", who=actor))
                else:
                    out.append(_event(k, "bitten", f"{actor} was bitten by a wolf (hurt {level})", who=actor))
        for actor in sorted(decisions):
            decision, last = decisions[actor], earlier.get(actor) or {}
            if decision.get("kind") == "flee" and last.get("kind") != "flee":
                out.append(_event(k, "ran", f"{actor}: {decision.get('reason', 'ran from a wolf')}", who=actor))
            held = [r for r in decision.get("rejected", []) if r[1] in ("dangerous", "hurt")]
            was = [r for r in last.get("rejected", []) if r[1] in ("dangerous", "hurt")]
            if held and not was:
                out.append(_event(k, "held_back", f"{actor} put off a trip: {held[0][2]}", who=actor))
            if "taking the risk" in decision.get("reason", "") and "taking the risk" not in last.get("reason", ""):
                out.append(_event(k, "risked", f"{actor} went anyway: {decision['reason'].split('taking the risk: ')[-1]}",
                                  who=actor))
    return out
