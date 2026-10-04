"""Index events for exploring, finding wells and rough ground worn through, from recorded values only.

An exploring trip is a person's recorded decision changing to `explore`; finding a well is a saved belief of kind
well that is new to somebody; rough ground worn through is a saved path cell on rough ground reaching the wear that
makes it a path. Nothing here knows what a person could see.
"""

from __future__ import annotations

from typing import Any, Mapping


def ground_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    features = set(cfg.get("features") or [])
    if not ({"exploration", "paths"} & features):
        return []
    out: list[dict[str, Any]] = []
    rough = {tuple(c) for c in cfg.get("rough") or []}
    worn_at = (cfg.get("feature_levers") or {}).get("worn_at", 8)
    for k in range(1, len(run.ticks) + 1):
        decisions = run.ticks[k - 1].get("decisions") or {}
        earlier = (run.ticks[k - 2].get("decisions") or {}) if k >= 2 else {}
        if "exploration" in features:
            for actor in sorted(decisions):
                if decisions[actor].get("kind") == "explore" and (earlier.get(actor) or {}).get("kind") != "explore":
                    out.append({"k": k, "cat": "explore", "kind": "explore_start", "who": actor,
                                "text": f"{actor} set out to look at ground they had not seen for a long time"})
            pb, pw = (worlds[k - 1].get("persona") or {}).get("beliefs") or {}, (worlds[k].get("persona") or {}).get("beliefs") or {}
            for actor, entries in sorted(pw.items()):
                known = {(e[0], e[1]) for e in pb.get(actor, [])}
                for kind, owner, x, y, seen, learned, via in entries:
                    if kind == "well" and (kind, owner) not in known:
                        out.append({"k": k, "cat": "explore", "kind": "found_well", "who": actor, "other": owner,
                                    "text": f"{actor} found {owner}'s well at ({x}, {y})"})
        if "paths" in features and rough:
            before = {(x, y): w for x, y, w in (worlds[k - 1].get("things") or {}).get("paths", [])}
            for x, y, w in (worlds[k].get("things") or {}).get("paths", []):
                if (x, y) in rough and w >= worn_at > before.get((x, y), 0):
                    out.append({"k": k, "cat": "explore", "kind": "worn_through", "text": f"the rough ground at ({x}, {y}) has been walked into a path"})
    return out
