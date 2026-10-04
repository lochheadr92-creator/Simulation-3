"""What the rich-world features add to the page's index: events, phrases and labels.

Like `viewer_index`, this reads a saved run and nothing else. An event here is a
recorded value changing (a person's sleep state, a skill's practice points) or a
recorded decision field (a set-aside option), described in words. It runs no world
rule and predicts nothing: if the run did not record it, there is no event.

Each feature that adds events contributes one function to `DERIVERS`.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from world.traits import level_of

PHRASES: dict[str, str] = {
    "sleep": "sleeping", "go_sleep": "heading home to sleep", "collapse": "collapsed from exhaustion",
}
LABELS: dict[str, str] = {"sleep": "sleep", "go_sleep": "go home to sleep", "collapse": "collapse"}
MOVES: tuple[str, ...] = ("go_sleep",)
CATEGORIES: tuple[tuple[str, str], ...] = (("rest", "Sleep and tiredness"), ("skill", "Learning"))


def _event(k: int, cat: str, kind: str, text: str, who: str | None = None, other: str | None = None,
           **extra: Any) -> dict[str, Any]:
    event: dict[str, Any] = {"k": k, "cat": cat, "kind": kind, "text": text}
    if who:
        event["who"] = who
    if other:
        event["other"] = other
    event.update(extra)
    return event


def _persona_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Sleep, waking, collapse, skill levels and withheld help, from the saved persona and decisions."""
    features = set(cfg.get("features") or [])
    tables = cfg.get("feature_tables") or {}
    wake_at = (cfg.get("feature_levers") or {}).get("wake_at")
    steps, names = tables.get("skill_steps") or [], tables.get("skills") or []
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        tick = run.ticks[k - 1]
        before, world = worlds[k - 1], worlds[k]
        decisions: Mapping[str, Any] = tick.get("decisions") or {}
        earlier: Mapping[str, Any] = (run.ticks[k - 2].get("decisions") or {}) if k >= 2 else {}
        pb, pw = before.get("persona") or {}, world.get("persona") or {}
        if "sleep" in features:
            asleep_before = pb.get("asleep") or {}
            for actor in sorted(decisions):
                decision = decisions[actor]
                kind = decision.get("kind")
                at = world.get("positions", {}).get(actor)
                tired = (pb.get("fatigue") or {}).get(actor)
                if kind in ("sleep", "collapse") and actor not in asleep_before:
                    if kind == "collapse":
                        out.append(_event(k, "rest", "collapsed",
                                          f"{actor} collapsed from exhaustion at {tuple(at)}", who=actor))
                    else:
                        home = at is not None and at == world.get("homes", {}).get(actor)
                        out.append(_event(k, "rest", "fell_asleep",
                                          f"{actor} fell asleep {'at home' if home else 'at ' + str(tuple(at))} "
                                          f"(fatigue {tired})", who=actor))
                elif (actor in asleep_before and kind not in ("sleep", "collapse")
                      and actor not in (world.get("died_at") or {})):
                    slept = k - 1 - asleep_before[actor]
                    if wake_at is not None and tired is not None and tired <= wake_at:
                        out.append(_event(k, "rest", "woke", f"{actor} woke rested after {slept} ticks (fatigue {tired})",
                                          who=actor))
                    else:
                        out.append(_event(k, "rest", "woke_early",
                                          f"{actor} woke early (fatigue {tired}): {decision.get('reason', kind)}",
                                          who=actor))
        if "skills" in features and steps:
            for actor, now in sorted((pw.get("skills") or {}).items()):
                was = (pb.get("skills") or {}).get(actor)
                if was is None:
                    continue
                for index, (a, b) in enumerate(zip(was, now)):
                    if b > a and level_of(b) > level_of(a):
                        out.append(_event(k, "skill", "skill_up",
                                          f"{actor}'s {names[index]} reached level {level_of(b)} ({b} practice points)",
                                          who=actor))
        if "explain" in features:
            for actor in sorted(decisions):
                held = [r for r in decisions[actor].get("rejected", []) if r[:2] == ["offer", "unwilling"]]
                was = [r for r in (earlier.get(actor) or {}).get("rejected", []) if r[:2] == ["offer", "unwilling"]]
                if held and not was:
                    out.append(_event(k, "help", "withheld", f"{actor}: {held[0][2]}", who=actor))
    return out


DERIVERS: tuple[Callable[[Any, list[Mapping[str, Any]], Mapping[str, Any]], list[dict[str, Any]]], ...] = (
    _persona_events,
)


def rich_index(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extra index content for a run that records rich-world features, else None."""
    if not cfg.get("features"):
        return None
    events: list[dict[str, Any]] = []
    for derive in DERIVERS:
        events.extend(derive(run, worlds, cfg))
    return {"events": events, "phrases": PHRASES, "labels": LABELS, "moves": list(MOVES),
            "categories": [list(pair) for pair in CATEGORIES]}
