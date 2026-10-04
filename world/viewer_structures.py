"""Index events for shelters, fires and wells, from recorded values only.

A shelter collapses when its saved condition entry disappears while the shelter list shrinks; a repair is its condition
rising; a fire is lit when a saved fire appears or its fuel rises; a well begins when a saved well appears and is
finished when its saved flag turns on. Nothing here predicts anything.
"""

from __future__ import annotations

from typing import Any, Mapping


def structure_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "structures" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []

    def event(k: int, kind: str, text: str, who: str) -> None:
        out.append({"k": k, "cat": "build", "kind": kind, "who": who, "text": text})

    for k in range(1, len(run.ticks) + 1):
        before = {(s[0], s[1]): s for s in (worlds[k - 1].get("things") or {}).get("structures", [])}
        now = {(s[0], s[1]): s for s in (worlds[k].get("things") or {}).get("structures", [])}
        for (kind, owner), s in sorted(now.items()):
            was = before.get((kind, owner))
            if kind == "fire" and (was is None or s[4] > was[4]):
                event(k, "fire_lit", f"{owner} {'lit' if was is None or was[4] == 0 else 'fed'} their fire", owner)
            elif kind == "shelter" and was is not None and s[4] > was[4] + 5:
                event(k, "repaired", f"{owner} mended their shelter ({was[4]} → {s[4]})", owner)
            elif kind == "well" and was is None:
                event(k, "well_begun", f"{owner} began digging a well", owner)
            elif kind == "well" and was is not None and not was[5] and s[5]:
                event(k, "well_done", f"{owner}'s well was finished", owner)
        for (kind, owner), s in sorted(before.items()):
            if kind == "shelter" and (kind, owner) not in now:
                event(k, "collapsed", f"{owner}'s shelter fell down at condition {s[4]}", owner)
    return out
