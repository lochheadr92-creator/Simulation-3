"""Index events for couples, pregnancy, grief, orphans and travellers, from recorded values only.

A couple is a saved partner link that appears; a pregnancy a saved due tick that appears; grief a saved level that
appears; a guardian a saved link that appears; a traveller a new person who has no recorded parent. Nothing here guesses.
"""

from __future__ import annotations

from typing import Any, Mapping


def family_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "family" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []

    def event(k: int, kind: str, text: str, who: str, other: str | None = None) -> None:
        e = {"k": k, "cat": "family", "kind": kind, "who": who, "text": text}
        if other:
            e["other"] = other
        out.append(e)

    old_age_at = (cfg.get("feature_levers") or {}).get("old_age_at", 480)
    for k in range(1, len(run.ticks) + 1):
        fb, fw = worlds[k - 1].get("family") or {}, worlds[k].get("family") or {}
        for a, b in sorted((fw.get("partner") or {}).items()):
            if a < b and (fb.get("partner") or {}).get(a) != b:
                event(k, "couple", f"{a} and {b} became a couple", a, b)
        for carrier, (due, other) in sorted((fw.get("pregnant") or {}).items()):
            if carrier not in (fb.get("pregnant") or {}):
                event(k, "pregnant", f"{carrier} is expecting a child with {other} (due tick {due})", carrier, other)
        for who, level in sorted((fw.get("grief") or {}).items()):
            if level > (fb.get("grief") or {}).get(who, 0) + 10:
                event(k, "grief", f"{who} is grieving", who)
        for child, adult in sorted((fw.get("guardian") or {}).items()):
            if (fb.get("guardian") or {}).get(child) != adult:
                event(k, "adopted", f"{adult} took in {child}, whose parents are gone", adult, child)
        new = set(worlds[k].get("positions", {})) - set(worlds[k - 1].get("positions", {}))
        for who in sorted(new):
            if who not in (worlds[k].get("parent") or {}):
                event(k, "arrived", f"{who} arrived, a traveller from outside", who)
        for who, tick in sorted((worlds[k].get("died_at") or {}).items()):
            if tick == k and (worlds[k].get("age") or {}).get(who, 0) >= old_age_at \
                    and (worlds[k - 1].get("hunger") or {}).get(who, 0) < cfg.get("death_at", 10 ** 9) - 2:
                event(k, "old_age", f"{who} died of old age", who)
    return out
