"""Index events for fields, crops and spoilage, from recorded values only.

A crop is planted when a saved plot turns from bare to growing, ripens when it turns to ripe, is harvested when it
turns back with the farmer's claim accepted, and rots or spoils by a production entry. Nothing here predicts a crop.
"""

from __future__ import annotations

from typing import Any, Mapping


def farming_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "farming" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []

    def event(k: int, kind: str, text: str, who: str) -> None:
        out.append({"k": k, "cat": "farm", "kind": kind, "who": who, "text": text})

    for k in range(1, len(run.ticks) + 1):
        before = {p[0]: p for p in (worlds[k - 1].get("things") or {}).get("plots", [])}
        now = {p[0]: p for p in (worlds[k].get("things") or {}).get("plots", [])}
        tick = run.ticks[k - 1]
        for owner, plot in sorted(now.items()):
            was = before.get(owner)
            if was is None:
                continue
            if was[3] == "bare" and plot[3] == "growing":
                event(k, "planted", f"{owner} planted their field", owner)
            elif was[3] == "growing" and plot[3] == "ripe":
                event(k, "ripe", f"{owner}'s crop ripened", owner)
            elif was[3] == "ripe" and plot[3] == "bare" and plot[6] < was[6]:
                event(k, "harvested", f"{owner} harvested their field (soil {was[6]} → {plot[6]})", owner)
        for entry in tick.get("production") or []:
            if "rotted" in entry:
                owner = entry["rotted"].replace("field-", "")
                event(k, "rotted", f"{entry['amount']} grain rotted in {owner}'s field, left standing too long", owner)
            elif "spoiled" in entry:
                event(k, "spoiled", f"{entry['amount']} of {entry['spoiled']}'s {entry['item']} spoiled in store",
                      entry["spoiled"])
    return out
