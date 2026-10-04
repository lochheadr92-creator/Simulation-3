"""Index events for graves, collected belongings and news of a death, from recorded values only.

A collection is a saved death record gaining a taker; learning of a death is a saved belief of kind death that is new
to somebody, with who told them. The cause and the witnesses are in the saved record and are shown to the reader of
the run, not to the people in it.
"""

from __future__ import annotations

from typing import Any, Mapping


def aftermath_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "aftermath" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []
    for k in range(1, len(run.ticks) + 1):
        before = {d[0]: d for d in (worlds[k - 1].get("things") or {}).get("deaths", [])}
        now = {d[0]: d for d in (worlds[k].get("things") or {}).get("deaths", [])}
        for person, d in sorted(now.items()):
            was = before.get(person)
            if was is None:
                out.append({"k": k, "cat": "life", "kind": "grave", "who": person,
                            "text": f"{person} was laid to rest at ({d[2]}, {d[3]}): {d[5]}"
                                    + (f"; in sight: {', '.join(d[6])}" if d[6] else "; nobody saw it")})
            elif d[8] and not was[8]:
                things = ", ".join(f"{n} {r}" for r, n in d[7]) or "nothing"
                out.append({"k": k, "cat": "life", "kind": "collected", "who": d[8], "other": person,
                            "text": f"{d[8]} collected what {person} left ({things})"})
        pb, pw = (worlds[k - 1].get("persona") or {}).get("beliefs") or {}, (worlds[k].get("persona") or {}).get("beliefs") or {}
        for actor, entries in sorted(pw.items()):
            known = {(e[0], e[1]) for e in pb.get(actor, [])}
            for kind, subject, x, y, seen, learned, via in entries:
                if kind == "death" and (kind, subject) not in known:
                    out.append({"k": k, "cat": "life", "kind": "learned_death", "who": actor, "other": subject,
                                "text": f"{actor} learned that {subject} had died" + (f", from {via}" if via else ", seeing the grave")})
    return out
