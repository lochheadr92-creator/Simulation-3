"""Render a world run as a place you can watch: a self-contained HTML page, or text.

    py -3 -B -m world.viewer runs/<run>.jsonl            # writes runs/<run>.html
    py -3 -B -m world.viewer runs/<run>.jsonl --text 40  # print the map at view 40
    py -3 -B -m world.run --seed 11 --ticks 300 --html   # run a world and write its page

The page is an isometric diorama of the saved run: terrain, sources and their
stock, homes and the shelters people build, people with their needs and what
they are doing, and the asking, answering and handing over that passes
between them. A timeline plays, steps and scrubs through it; a list of what
happened jumps to any moment; an inspector follows one person through time.

It embeds the run file's content and reads nothing else: no network, no
scripts or fonts from elsewhere, no live engine. world/viewer_index.py reads
the saved run once into the events, request threads and counts the page
lists; world/viewer.js and world/viewer.css are the drawing, inlined into the
page. Every number shown is a value the run recorded or a count of them, and
animation only moves the picture between two recorded ticks. It is a way to
look, not a second simulation.

View k shows the world after tick k-1 (view 0 is genesis) together with the
decisions and outcomes of tick k-1, the ones that produced it.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from stream.run_file import Run, read_run
from world.viewer_index import build_index, food_sources, stock_at

HERE = Path(__file__).resolve().parent
CSS_FILE = HERE / "viewer.css"
JS_FILE = HERE / "viewer.js"


def _checkpoints(run: Run) -> dict[str, list[int]]:
    """Index saved native choices/outcomes, never reconstruct a score or winner."""
    found: dict[str, list[int]] = {"scored": [], "crossover": [], "contested": []}
    for view, tick in enumerate(run.ticks, 1):
        choices = [d for d in tick.get("decisions", {}).values()
                   if "go" in d.get("scores", {}) and "yield" in d.get("scores", {})]
        if choices:
            found["scored"].append(view)
        if any(d["kind"] == "go" for d in choices):
            found["crossover"].append(view)
        if sum(o["operation"] == "claim" for o in tick["record"]["outcomes"]) >= 2:
            found["contested"].append(view)
    return found


def _seen_ids(observation: dict) -> list[str]:
    """Who an observation saw: `sees` (identities) in current files, `others`
    (identity, position, food per person) in files written before 2026-09-25."""
    if "sees" in observation:
        return list(observation["sees"])
    return [entry["id"] for entry in observation.get("others", [])]


def _seen_positions(observation: dict, start_world: dict) -> list:
    """Tick-start positions of the people an observation saw."""
    if "sees" in observation:
        return [start_world["positions"][actor] for actor in observation["sees"]]
    return [entry["at"] for entry in observation.get("others", [])]


def _food_sources(cfg: dict) -> list[dict]:
    """Every food source a header declares: `food_sources` when there are
    several (from 2026-09-26), else the one `source`."""
    return (cfg.get("food_sources") or [{"id": cfg["source"], "position": cfg["source_position"]}]) + cfg.get("food_stores", [])


def _water_sources(cfg: dict) -> list[dict]:
    if cfg.get("water") != "on":
        return []
    return cfg.get("water_sources") or [{"id": cfg["water_source"], "position": cfg["water_position"]}]


def _tick_details(run: Run, view: int) -> dict[str, str]:
    """Shared HTML/text presentation of native fields, with boundary labels."""
    if not view:
        return {"selection": "Genesis: no decisions yet.", "settlement": "Genesis: no settlement yet."}
    tick = run.ticks[view - 1]
    prior = run.header["world"] if view == 1 else run.ticks[view - 2]["world"]
    cfg = run.header["scenario"]
    source_at = {entry["id"]: entry["position"] for entry in food_sources(cfg, prior) + _water_sources(cfg) + cfg.get("wood_sources", [])}
    selection = [f"Decision tick {tick['tick']} — personal selection from tick-start inputs"]
    for actor, d in sorted(tick.get("decisions", {}).items()):
        ob = tick.get("observations", {}).get(actor, {})
        water_action = d.get("kind") in ("drink", "draw", "wait_water", "go_water")
        wood_action = d.get("kind") in ("gather_wood", "go_wood", "wait_wood")
        source_id = d.get("target") or cfg.get("water_source" if water_action else "source")
        aimed = source_at.get(source_id)
        crowd = sum(position == aimed for position in _seen_positions(ob, prior))
        stock = ob.get("seen_stock", {}).get(source_id, ob.get("wood_stock" if wood_action else "water_stock" if water_action else "source_food", "not observed"))
        scores = d.get("scores")
        pairs = "; ".join(f"{action} {tuple(scores[action])}" if scores is not None and action in scores
                          else f"{action} (score not recorded)" for action in d["candidates"])
        selection.append(
            f"{actor}: tick-start at {tuple(prior['positions'][actor])}, hunger {prior['hunger'][actor]}, "
            + (f"thirst {prior['thirst'][actor]}, " if "thirst" in prior else "")
            + (f"cold {prior['cold'][actor]}, " if "cold" in prior else "")
            + f"yield_at {prior.get('yield_at', {}).get(actor, 'not recorded')}, "
            f"seen crowd {crowd}, seen source stock {stock}"
            + (f", seen stocks {ob['seen_stock']}" if "seen_stock" in ob else "")
            + f"; eligible: {pairs}; selected {d['kind']}"
            + (f" -> {d['target']}" if "target" in d else "")
        )
    settlement = [f"Decision tick {tick['tick']} — kernel settlement (personal scores confer no priority)",
                  "Recorded rotation: " + " -> ".join(tick["record"]["rotated_roster"])]
    for actor, d in sorted(tick.get("decisions", {}).items()):
        if d["kind"] == "claim":
            settlement.append(f"Food claim request: {actor}, {d['amount']} from {d.get('target', cfg['source'])}")
        elif d["kind"] == "draw":
            settlement.append(f"Water draw request: {actor}, {d['amount']} from {d.get('target', cfg.get('water_source'))}")
    for o in tick["record"]["outcomes"]:
        effects = ", ".join(f"{e['account']} {e['delta']:+d}" for e in o["effects"]) or "none"
        settlement.append(f"{o['proposal_id']}: {o['actor']} {o['operation']} "
                          f"{'accepted' if o['accepted'] else 'denied'} ({o['reason']}); effects: {effects}")
    if not tick["record"]["outcomes"]:
        settlement.append("No kernel transactions this tick.")
    sources = tick["state"]["sources"]
    stocks = (f"source stock {sources[cfg['source']]['stock']}" if len(sources) == 1 else
              "source stocks " + ", ".join(f"{sid} {entry['stock']}" for sid, entry in sources.items()))
    settlement.append(f"After settlement: {stocks}; subsequent renewal: {tick.get('production', [])}")
    settlement.append("Post-tick positions, hunger, deaths and food appear in the map/people view. "
                      "Claimed food becomes available at the next tick; it was not eaten by claiming.")
    return {"selection": "\n".join(selection), "settlement": "\n".join(settlement)}


def _run_payload(run: Run) -> dict[str, Any]:
    return {
        "header": run.header,
        "ticks": [dict(tick) for tick in run.ticks],
        "timings": {str(tick): ns for tick, ns in run.timings.items()},
        "end": run.end,
        "problems": list(run.problems),
        "checkpoints": _checkpoints(run),
        "details": [_tick_details(run, view) for view in range(len(run.ticks) + 1)],
    }


def _embed(value: Any) -> str:
    """JSON for a <script type="application/json"> block: nothing in it can close the tag."""
    return json.dumps(value, separators=(",", ":")).replace("<", "\\u003c")


def _asset(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "</script" in text.lower() or "</style" in text.lower():
        raise ValueError(f"{path.name} must not close its own tag")
    return text


ICONS = {
    "start": '<path d="M5 4v12M16 4l-8 6 8 6z" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    "prev": '<path d="M13 4l-7 6 7 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "next": '<path d="M7 4l7 6-7 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "end": '<path d="M15 4v12M4 4l8 6-8 6z" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    "play": '<path d="M6 4l10 6-10 6z" fill="currentColor"/>',
    "plus": '<path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "minus": '<path d="M4 10h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "fit": '<path d="M3 7V3h4M13 3h4v4M17 13v4h-4M7 17H3v-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "reset": '<path d="M4 10a6 6 0 1 0 2-4.5M4 3v3.5h3.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "drift": '<path d="M2 12c3-4 5-4 8 0s5 4 8 0M2 7c3-4 5-4 8 0s5 4 8 0" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "layers": '<path d="M10 3l7 4-7 4-7-4zM3 10.5l7 4 7-4M3 14l7 4 7-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    "follow": '<circle cx="10" cy="10" r="3" fill="currentColor"/><path d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" stroke-width="1.4"/>',
}


def _svg(name: str) -> str:
    return f'<svg viewBox="0 0 20 20" aria-hidden="true">{ICONS[name]}</svg>'


# Legend swatches, drawn the way the map draws them.
LEGEND = (
    ('<circle cx="10" cy="5" r="2.6" fill="#f2e5d0"/><rect x="7" y="7.5" width="6" height="6.5" rx="2.4" fill="#7fb3d9"/>'
     '<path d="M8.5 14v2.5M11.5 14v2.5" stroke="#2c4a5e" stroke-width="1.4"/>', "a person, in their own colour"),
    ('<circle cx="5" cy="8" r="2.4" fill="#f2a65e"/><path d="M10 5.5c1.6 2 1.6 3.6 0 4.6-1.6-1-1.6-2.6 0-4.6z" fill="#72c8ea"/>'
     '<path d="M14 6l3 4M17 6l-3 4M13.4 8h4.2" stroke="#b9dcff" stroke-width="1.1"/>',
     "hungry, thirsty, cold; red when it is an emergency"),
    ('<circle cx="7" cy="9" r="4.5" fill="#3f7440"/><circle cx="13" cy="9" r="4.5" fill="#56904f"/>'
     '<circle cx="7" cy="8" r="1.3" fill="#e2553e"/><circle cx="12" cy="10" r="1.3" fill="#f0a04a"/>',
     "food source: its berries are its stock"),
    ('<ellipse cx="10" cy="11" rx="8" ry="4" fill="#9d988c"/><ellipse cx="10" cy="10.5" rx="5.5" ry="2.4" fill="#3f9fc7"/>',
     "well: water (stock) shows as the water level"),
    ('<path d="M4 9l6-5 6 5v6H4z" fill="#a07a52"/><path d="M3 9.5l7-6.5 7 6.5" fill="#d6aa62"/>'
     '<rect x="12" y="10" width="2.5" height="2.5" fill="#ffd27a"/>',
     "a shelter somebody built; a lit window means somebody is home"),
    ('<path d="M3 10l7-4 7 4-7 4z" fill="none" stroke="#9fd0c0" stroke-dasharray="2 1.6"/>', "a home with no shelter yet"),
    ('<path d="M3 10l7-4 7 4-7 4z" fill="#6d7682"/><path d="M6 10l2-1.5 2 1 3-1.5" stroke="#2a2e34" fill="none"/>',
     "rough ground: an extra tick to cross"),
    ('<path d="M3 10l7-4 7 4-7 4z" fill="#ffe3a3" fill-opacity=".16" stroke="#ffe3a3" stroke-dasharray="2 1.5"/>',
     "remembered rough ground for the selected person"),
    ('<path d="M3 10l7-4 7 4-7 4z" fill="#a8a08a"/><circle cx="10" cy="10" r="4" fill="#ffc46e" fill-opacity=".35"/>',
     "shelter spot: hunger and thirst rise slower"),
    ('<path d="M2 12q8-9 16 0" fill="none" stroke="#ffd68c" stroke-dasharray="3 2"/>', "asked for food, waiting on the answer"),
    ('<path d="M2 12q8-9 16 0" fill="none" stroke="#f1c56e" stroke-width="1.6" stroke-dasharray="1 3" stroke-linecap="round"/>',
     "agreed to bring food, on the way"),
    ('<circle cx="6" cy="6" r="2.4" fill="#f2e5d0"/><rect x="3.5" y="8" width="5" height="6" rx="2" fill="#7fb3d9"/>'
     '<circle cx="14" cy="9" r="1.8" fill="#f2e5d0"/><rect x="12.2" y="10.6" width="3.6" height="4.2" rx="1.5" fill="#d99a7f"/>'
     '<path d="M8.5 13l3.5-1" stroke="#ecb2d6" stroke-dasharray="1 1.6"/>',
     "a child is smaller until grown; dotted pink joins the selected person to their parent and children"),
    ('<path d="M7 15v-6q3-4 6 0v6z" fill="#8f8a82"/>', "somebody died here"),
    ('<path d="M3 10l7-4 7 4-7 4z" fill="#ffe3a3" fill-opacity=".08" stroke="#ffe3a3" stroke-dasharray="3 2"/>',
     "Chebyshev perception: the square a person can see"),
)


def _layer(key: str, label: str, note: str = "", checked: bool = True) -> str:
    return (f'<label class="layer"><input type="checkbox" data-layer="{key}"{" checked" if checked else ""}>'
            f'<span>{html.escape(label)}</span><small>{html.escape(note)}</small></label>')


def render_html(run: Run) -> str:
    if not run.has_world:
        raise ValueError("this run has no world overlay; use stream.viewer for a kernel-only run")
    prefix_notice = ""
    if not run.complete and run.last_sealed_tick is not None:
        count = max(0, run.last_sealed_tick + 1)
        prefix_notice = f"Showing only the verified prefix: {count} ticks. Later records are not displayed."
        run = replace(run, ticks=run.ticks[:count], end=None,
                      problems=run.problems + (f"Showing only the verified prefix: {count} ticks.",))
    scenario = run.header.get("scenario", {})
    data = _embed(_run_payload(run))
    index = _embed(build_index(run))
    problems = "".join(f'<li class="problem">{html.escape(p)}</li>' for p in run.problems)
    name = run.run_id or run.path.name
    status = "verifies" if run.complete else "DOES NOT VERIFY"
    water = scenario.get("water") == "on"
    warmth = scenario.get("warmth") == "on"
    terrain = scenario.get("terrain") == "on"
    building = scenario.get("building") == "on"
    childhood = scenario.get("childhood") == "on"
    levers = ", ".join(f"{k} {v}" for k, v in scenario.items() if isinstance(v, int) and k != "seed")
    switches = [key for key in ("water", "warmth", "terrain", "building", "offers", "requests", "births",
                                "childhood", "trips", "regrowth", "seasons", "stores", "homes", "relocation", "wood", "fishing", "source_memory", "provisioning", "coordination", "remembered_contribution", "knowledge_sharing")
                if scenario.get(key) == "on"]
    rules = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in scenario.items()
                    if isinstance(v, str) and len(v) > 24)
    layers = "".join([
        "<h3>On the map</h3>",
        _layer("people", "People"), _layer("names", "Names"), _layer("needs", "Need badges"),
        _layer("trails", "Trails", "last 12 ticks"),
        _layer("memory", "Remembered rough", "selected person") if terrain else "",
        _layer("links", "Requests and handovers"),
        _layer("family", "Family", "for the selected person") if childhood else "",
        _layer("deaths", "Where people died"),
        _layer("moments", "Moments", "births, renewals, gathering"),
        '<label class="layer"><span></span><span>Perception radius</span><select data-layer="perception" '
        'aria-label="Perception radius"><option value="off">off</option><option value="selected" selected>'
        'selected person</option><option value="everyone">everyone</option></select></label>',
        "<h3>Places</h3>",
        _layer("food", "Food sources"),
        _layer("water", "Wells") if water else "",
        _layer("wood", "Wood groves") if scenario.get("wood") == "on" else "",
        _layer("stock", "Stock labels"), _layer("homes", "Homes"),
        _layer("shelters", "Shelters") if building else "",
        _layer("rough", "Rough ground") if terrain else "",
        _layer("spots", "Shelter spots") if terrain else "",
        '<h3>Legend</h3><div class="legend">',
        "".join(f'<div><svg viewBox="0 0 20 20" aria-hidden="true">{art}</svg><span>{html.escape(text)}</span></div>'
                for art, text in LEGEND
                if (water or "well" not in text) and (terrain or ("rough" not in text and "shelter spot" not in text))
                and (building or "built" not in text) and (childhood or "child" not in text)),
        "</div>",
    ])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{html.escape(name)} — Simulation 3</title><style>{_asset(CSS_FILE)}</style></head>
<body>
<div class="app">
<header class="top">
  <div class="brand"><svg class="mark" viewBox="0 0 22 22" aria-hidden="true"><path d="M11 2l9 5-9 5-9-5z" fill="#77955a"/><path d="M2 7v5l9 5v-5z" fill="#5a4431"/><path d="M20 7v5l-9 5v-5z" fill="#46362a"/><circle cx="11" cy="7" r="1.8" fill="#f1c56e"/></svg>
    <span class="kicker">Simulation 3</span><h1 title="{html.escape(name)}">{html.escape(name)}</h1></div>
  <div class="chips">
    <span class="chip">seed <b>{html.escape(str(scenario.get('seed', '')))}</b></span>
    <span class="chip"><b>{html.escape(str(scenario.get('width', '')))} × {html.escape(str(scenario.get('height', '')))}</b> grid</span>
    <span class="chip"><b>{len(run.ticks)}</b> ticks</span>
    {''.join(f'<span class="chip switch">{html.escape(s)}</span>' for s in switches)}
    <span class="chip{'' if run.complete else ' bad'}" title="{html.escape(str(run.header.get('format', '')))} · engine {html.escape(str(run.header.get('engine_version', '')))}">file {status} (consistency only)</span>
  </div>
  {f'<div class="problem" role="alert" style="flex-basis:100%">{prefix_notice}</div>' if prefix_notice else ''}
</header>

<section id="map" aria-label="The world">
  <canvas id="world" role="img" aria-label="Isometric map of the world"></canvas>
  <div class="hud hud-tl">
    <div class="clock" aria-hidden="true"><div class="big num" id="hud-tick"></div><div class="line" id="hud-line"></div></div>
  </div>
  <div class="hud hud-tr">
    <div class="toolbar" role="toolbar" aria-label="Camera">
      <button class="tool" id="zoom-in" type="button" aria-label="Zoom in" title="Zoom in">{_svg('plus')}</button>
      <button class="tool" id="zoom-out" type="button" aria-label="Zoom out" title="Zoom out">{_svg('minus')}</button>
      <button class="tool" id="fit" type="button" aria-label="Fit the world" title="Fit the world">{_svg('fit')}</button>
      <button class="tool" id="reset" type="button" aria-label="Reset the view" title="Reset the view">{_svg('reset')}</button>
      <button class="tool" id="drift" type="button" aria-pressed="false" aria-label="Drift gently while playing" title="Drift gently while playing">{_svg('drift')}</button>
      <button class="tool wide" id="layers-btn" type="button" aria-pressed="false" aria-expanded="false" aria-controls="layers" aria-label="Layers and legend">{_svg('layers')}<span class="word">Layers</span></button>
    </div>
    <div class="layers" id="layers" role="group" aria-label="Layers and legend">{layers}</div>
  </div>
  <div class="hud hud-bl">
    <div class="focus-card" id="focus" role="status">
      <span class="swatch" id="focus-sw"></span>
      <div class="grow"><div class="who" id="focus-who"></div><div class="what" id="focus-what"></div></div>
      <button class="tool" id="follow" type="button" aria-pressed="false" aria-label="Follow with the camera" title="Follow with the camera">{_svg('follow')}</button>
      <button class="linkbtn" id="focus-more" type="button">Inspect</button>
      <button class="x" id="focus-close" type="button" aria-label="Clear the selection">×</button>
    </div>
  </div>
  <div class="tip" id="tip" role="tooltip"></div>
</section>

<section class="timeline" aria-label="Timeline">
  <div class="transport">
    <button class="tool" id="start" type="button" aria-label="Jump to the start" title="Start (Home)">{_svg('start')}</button>
    <button class="tool" id="prev" type="button" aria-label="Previous tick" title="Previous tick (←)">{_svg('prev')}</button>
    <button class="tool play" id="play" type="button" aria-pressed="false" aria-label="Play" title="Play or pause (Space)">{_svg('play')}</button>
    <button class="tool" id="next" type="button" aria-label="Next tick" title="Next tick (→)">{_svg('next')}</button>
    <button class="tool" id="end" type="button" aria-label="Jump to the end" title="End (End)">{_svg('end')}</button>
  </div>
  <span id="tick" class="tick" aria-live="off"></span>
  <div class="scrub"><canvas id="strip" aria-hidden="true"></canvas>
    <input id="slider" type="range" min="0" max="0" value="0" step="1" aria-label="Tick"></div>
  <label class="speed">Speed <select id="speed" aria-label="Playback speed">
    <option value="1">1 tick/s</option><option value="2">2 ticks/s</option><option value="4">4 ticks/s</option>
    <option value="8">8 ticks/s</option><option value="16">16 ticks/s</option><option value="32">32 ticks/s</option></select></label>
  <span class="keys">Space play · ← → step · Home / End</span>
</section>

<aside class="side">
  <section class="card summary" aria-label="Run summary">
    <h2>This run</h2>
    <div class="sgrid" id="stats"></div>
    <div class="sources" id="sources"></div>
    <div class="helpline" id="helpline"></div>
  </section>
  <section class="card tabs-card">
    <div class="tabs" role="tablist">
      <button class="tab" id="tab-events" role="tab" type="button" aria-selected="true" aria-controls="panel-events">Happenings<span class="count" id="ev-count"></span></button>
      <button class="tab" id="tab-inspector" role="tab" type="button" aria-selected="false" aria-controls="panel-inspector">Inspector</button>
    </div>
    <div class="tabpanel on" id="panel-events" role="tabpanel" aria-labelledby="tab-events">
      <div class="cats" id="cats" aria-label="Show or hide kinds of event"></div>
      <div id="events" aria-label="What happened, in order; click a line to go there"></div>
    </div>
    <div class="tabpanel" id="panel-inspector" role="tabpanel" aria-labelledby="tab-inspector"><div id="inspector"></div></div>
  </section>
</aside>
</div>
<p class="sr" id="live" aria-live="polite"></p>

<details class="deep" id="deep">
  <summary>Under the hood — the saved record for this tick, and whole-run counts</summary>
  <div class="deep-body">
    <div class="meta">{html.escape(scenario.get('name', ''))} · seed {html.escape(str(scenario.get('seed', '')))} · {len(run.ticks)} ticks · engine {html.escape(str(run.header.get('engine_version', '')))} · {html.escape(str(run.header.get('format', '')))} · file {status} (consistency only) · <span id="timing"></span></div>
    <p class="meta">File checks detect accidental corruption; they do not authenticate the author. World tick k shows the completed result of decision tick k−1; world tick 0 is genesis.</p>
    <div class="meta">{html.escape(levers)}</div>
    {f'<ul>{problems}</ul>' if problems else ''}
    <div class="checks">
      <button id="scored" type="button">Next GO/YIELD scored choice</button>
      <button id="crossover" type="button">Next GO over eligible YIELD</button>
      <button id="contested" type="button">Next contested food claim</button>
    </div>
    <div class="box"><h2>People after this tick</h2>
      <table><thead><tr><th>person</th><th class="num">yield_at</th><th>at</th><th class="num">hunger</th><th class="num water-col">thirst</th><th class="num warmth-col">cold</th><th>state</th><th class="num">food</th><th class="num water-col">water</th><th>sees (tick before)</th><th>decided (tick before)</th><th>kernel outcome</th></tr></thead><tbody id="people"></tbody></table>
      <p class="meta">Decision, observation and outcome are those of the tick that produced this view. Food is the kernel's free balance. Sees lists other people (and S for the source) inside the perception radius at tick start.{' Cold rises away from home and falls at home; ⌂ marks somebody sheltered at home.' if warmth else ''} yield_at is the person's own crowd-yield trait.</p></div>
    <div class="box"><h2>Over time: hunger per person (grey), food stock in all food sources (blue), crowd on source (purple dashed), yield events (dots), deaths</h2><div id="chart"></div><div class="stats" id="totals" style="margin-top:8px"></div></div>
    <div class="box"><h2>Personal selection — tick-start inputs and recorded scores</h2><pre id="selection"></pre></div>
    <div class="box"><h2>Resource settlement — recorded kernel order and effects</h2><pre id="settlement"></pre></div>
    <div class="box"><h2>The rules these people follow, as the run declares them</h2><dl class="rules">{rules}</dl>
      <p class="meta">Scoring: {html.escape(str(scenario.get('scoring', 'off (legacy file)')))}. Everything on this page is read straight from the saved run: the page never recalculates what the world decided.</p></div>
  </div>
</details>
<script id="run-data" type="application/json">{data}</script>
<script id="view-index" type="application/json">{index}</script>
<script>{_asset(JS_FILE)}</script>
</body></html>
"""




def render_text(run: Run, view: int) -> str:
    if not run.has_world:
        raise ValueError("this run has no world overlay")
    if view < 0 or view > len(run.ticks):
        raise ValueError(f"view must be between 0 and {len(run.ticks)}")
    cfg = run.header["scenario"]
    world = run.header["world"] if view == 0 else run.ticks[view - 1]["world"]
    def stock_of(source_id: str) -> int:
        return stock_at(run, view, source_id)
    stock = stock_of(cfg["source"])
    grid = [["." for _ in range(cfg["width"])] for _ in range(cfg["height"])]
    sx, sy = cfg["source_position"]
    extra = []
    for mark, entries in (("S", food_sources(cfg, world)), ("W", _water_sources(cfg)), ("T", cfg.get("wood_sources", []))):
        for entry in entries:
            x, y = entry["position"]
            grid[y][x] = mark
            if entry["id"] != cfg["source"]:
                extra.append(f"; {entry['id']} {mark} at ({x}, {y}) stock {stock_of(entry['id'])}")
    for actor in sorted(world["positions"]):
        x, y = world["positions"][actor]
        mark = "x" if actor in world["died_at"] else actor[-1]
        grid[y][x] = mark if grid[y][x] in ".SWT" else "+"
    saw_other = saw_source = yields = 0
    for entry in run.ticks:
        for observation in entry.get("observations", {}).values():
            if _seen_ids(observation):
                saw_other += 1
            if "source_food" in observation:
                saw_source += 1
        yields += sum(1 for d in entry.get("decisions", {}).values() if d.get("kind") == "yield")
    traits = world.get("yield_at", run.header["world"].get("yield_at", {}))
    lines = [f"{run.run_id} view {view}/{len(run.ticks)}  source S at ({sx}, {sy}) stock {stock}" + "".join(extra),
             f"person-ticks with another in view {saw_other}; with source in view {saw_source}; yield events {yields}",
             *(" ".join(row) for row in grid), "",
             "positions and hunger after the tick; sees, decision and outcome are the tick's that produced them"]
    tick = run.ticks[view - 1] if view else None
    for actor in sorted(world["positions"]):
        decision = tick["decisions"].get(actor) if tick else None
        outcome = next((o for o in tick["record"]["outcomes"] if o["actor"] == actor), None) if tick else None
        dead = f" dead t{world['died_at'][actor]}" if actor in world["died_at"] else ""
        observation = tick.get("observations", {}).get(actor) if tick else None
        seen = ""
        if observation is not None:
            names = _seen_ids(observation)
            if "source_food" in observation:
                names.append(f"S={observation['source_food']}")
            seen = f"  sees {', '.join(names) if names else 'none'}"
        trait = traits.get(actor)
        needs = (f" thirst {world['thirst'][actor]}" if "thirst" in world else "") + (
            f" cold {world['cold'][actor]}" + (" sheltered" if tuple(world["positions"][actor]) == tuple(
                world["homes"][actor]) else "") if "cold" in world else "")
        lines.append(f"{actor} yield_at {trait} at {tuple(world['positions'][actor])} hunger {world['hunger'][actor]}"
                     + needs + dead
                     + seen
                     + (f"  {decision['kind']} ({decision['reason']})" if decision else "")
                     + (f"  -> {outcome['reason']}" if outcome else ""))
    lines.extend(["", f"Scoring: {cfg.get('scoring', 'off (legacy file)')}"])
    lines.extend(f"{key}: {value}" for key, value in cfg.items() if key.startswith("scoring_") or key == "food_allocation")
    lines.append("Navigation (view = tick + 1; use --text VIEW): " + "; ".join(
        f"{name} views {views or 'absent'}" for name, views in _checkpoints(run).items()))
    details = _tick_details(run, view)
    lines.extend(["", details["selection"], "", details["settlement"]])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a world run file as a map over time.")
    parser.add_argument("run", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=None)
    parser.add_argument("--text", type=int, default=None, metavar="VIEW", help="print the map at this view instead")
    args = parser.parse_args(argv)
    run = read_run(args.run)
    if args.text is not None:
        sys.stdout.write(render_text(run, args.text) + "\n")
        return 0 if run.complete else 1
    out = args.out or args.run.with_suffix(".html")
    out.write_text(render_html(run), encoding="utf-8")
    sys.stdout.write(f"wrote {out}\n")
    return 0 if run.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
