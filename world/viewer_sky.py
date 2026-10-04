"""Events for the page from the sky each saved tick records: dusk, night, dawn and weather changes.

Read from recorded values only. If a run records no sky, there are no sky events.
"""

from __future__ import annotations

from typing import Any, Mapping

PHASE_TEXT = {"dusk": "Dusk falls", "night": "Night falls", "dawn": "Dawn breaks"}
PHASE_KIND = {"dusk": "dusk_falls", "night": "night_falls", "dawn": "dawn_breaks"}
WEATHER_TEXT = {
    "clear": ("weather_clears", "The sky clears"),
    "overcast": ("sky_clouds", "Cloud gathers"),
    "rain": ("rain_begins", "Rain begins"),
    "storm": ("storm_breaks", "A storm breaks"),
}


def sky_events(run: Any, worlds: list[Mapping[str, Any]], cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "sky" not in set(cfg.get("features") or []):
        return []
    out: list[dict[str, Any]] = []
    for k in range(1, len(worlds)):
        before, now = worlds[k - 1].get("sky"), worlds[k].get("sky")
        if not before or not now:
            continue
        if now["phase"] != before["phase"] and now["phase"] in PHASE_KIND:
            out.append({"k": k, "cat": "sky", "kind": PHASE_KIND[now["phase"]],
                        "text": f"{PHASE_TEXT[now['phase']]} ({now['temp']}°)"})
        if now["weather"] != before["weather"]:
            kind, text = WEATHER_TEXT[now["weather"]]
            if now["weather"] == "clear" and before["weather"] in ("rain", "storm"):
                text = "The rain stops and the sky clears"
            out.append({"k": k, "cat": "sky", "kind": kind, "text": f"{text} ({now['temp']}°)"})
    return out
