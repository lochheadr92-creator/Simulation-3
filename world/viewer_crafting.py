"""Index events for stone and tools, from recorded values only.

Digging stone is a saved decision whose claim the kernel accepted; a tool is a saved production entry. Nothing
here asks whether somebody could have made one.
"""

from __future__ import annotations

from typing import Any, Mapping


def crafting_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "crafting" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        tick = run.ticks[k - 1]
        decisions = tick.get("decisions") or {}
        outcomes = {}
        for outcome in (tick.get("record") or {}).get("outcomes", []):
            if outcome.get("operation") == "claim":
                outcomes.setdefault(outcome.get("actor"), outcome)
        for actor in sorted(decisions):
            d = decisions[actor]
            if d.get("kind") == "gather_stone" and outcomes.get(actor, {}).get("accepted"):
                got = sum(e["delta"] for e in outcomes[actor]["effects"] if e["account"] == f"actor@stone:{actor}")
                out.append({"k": k, "cat": "craft", "kind": "gather_stone", "who": actor,
                            "text": f"{actor} dug {got} stone at {d.get('target')}"})
        for entry in tick.get("production") or []:
            if "made" in entry:
                item = entry["item"]
                article = "an" if item[0] in "aeiou" else "a"
                out.append({"k": k, "cat": "craft", "kind": "made", "who": entry["made"],
                            "text": f"{entry['made']} made {article} {item}"})
    return out
