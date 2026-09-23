"""World view: an isometric, smoothly played picture of a saved world run.

    py -3 -B -m viewer.world_view runs/<run>.jsonl            # writes runs/<run>.world.html
    py -3 -B -m viewer.world_view runs/<run>.jsonl -o out.html

Presentation track under OD-012. The page is generated from the run file
alone: the file's complete text is embedded verbatim (as one JSON string) and
its SHA-256 is written into the page. Nothing is fetched, nothing is live.

What the page shows is the recorded tick state. Between two recorded ticks it
tweens positions and hunger colour so playback is smooth; that motion is
display only. Events (claim, eat, yield, denial, death) snap to their recorded
tick boundary, paused or stepped frames are exact recorded states, and the
inspect panel prints recorded values and recorded band labels only.

This module imports nothing from `kernel`, `world` or `stream`. It does not
verify digests (the stream reader does that); it refuses a file whose header
it does not recognise rather than guessing at its shape.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RECOGNISED_FORMATS = ("v3.stream.2", "v3.stream.3")
RECOGNISED_SCHEMAS = ("v3.kernel.1b.1",)
REQUIRED_WORLD_KEYS = ("positions", "homes", "hunger", "died_at")
REQUIRED_SCENARIO_KEYS = ("width", "height", "source", "source_position", "source_cap",
                          "hungry_at", "emergency_at", "death_at")


class WorldViewError(Exception):
    """The run file is missing, cut, or not a shape this view recognises."""


@dataclass(frozen=True)
class LoadedRun:
    path: Path
    text: str
    sha256: str
    header: dict[str, Any]
    tick_count: int


def _require(mapping: Any, key: str, where: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise WorldViewError(f"unrecognised run file: {where} has no {key!r}")
    return mapping[key]


def check_header(header: Any) -> None:
    """Refuse anything that is not the run-file shape this view was written for."""
    if not isinstance(header, dict) or header.get("kind") != "header":
        raise WorldViewError("unrecognised run file: first line is not a header")
    fmt = _require(header, "format", "header")
    if fmt not in RECOGNISED_FORMATS:
        raise WorldViewError(f"unrecognised run file: format {fmt!r} (recognised: {', '.join(RECOGNISED_FORMATS)})")
    schema = _require(header, "schema_version", "header")
    if schema not in RECOGNISED_SCHEMAS:
        raise WorldViewError(f"unrecognised run file: schema_version {schema!r} (recognised: {', '.join(RECOGNISED_SCHEMAS)})")
    world = _require(header, "world", "header")
    for key in REQUIRED_WORLD_KEYS:
        _require(world, key, "header.world")
    scenario = _require(header, "scenario", "header")
    for key in REQUIRED_SCENARIO_KEYS:
        _require(scenario, key, "header.scenario")
    genesis = _require(header, "genesis", "header")
    _require(genesis, "balances", "header.genesis")
    sources = _require(genesis, "sources", "header.genesis")
    source = _require(sources, scenario["source"], "header.genesis.sources")
    _require(source, "stock", f"header.genesis.sources[{scenario['source']!r}]")
    for person in world["positions"]:
        if person not in world["hunger"] or person not in world["homes"]:
            raise WorldViewError(f"unrecognised run file: header.world lists {person!r} without hunger or home")


def load_run(path: Path) -> LoadedRun:
    """Read the file once, keep its text verbatim, and check only what the
    view needs: a recognised header, contiguous ticks, and a matching end."""
    path = Path(path)
    if not path.is_file():
        raise WorldViewError(f"no run file at {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorldViewError(f"run file is not UTF-8: {exc}") from exc
    header: dict[str, Any] | None = None
    expected_tick: int | None = None
    tick_count = 0
    end: dict[str, Any] | None = None
    for number, line in enumerate(text.split("\n"), start=1):
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorldViewError(f"line {number}: not JSON ({exc.msg})") from exc
        if not isinstance(payload, dict):
            raise WorldViewError(f"line {number}: not an event")
        kind = payload.get("kind")
        if header is None:
            check_header(payload)
            header = payload
            expected_tick = int(_require(header["genesis"], "tick", "header.genesis"))
            continue
        if end is not None:
            raise WorldViewError(f"line {number}: event after end")
        if kind == "tick":
            if payload.get("tick") != expected_tick:
                raise WorldViewError(f"line {number}: expected tick {expected_tick}, found {payload.get('tick')!r}")
            for key in ("record", "state", "world"):
                _require(payload, key, f"tick line {number}")
            _require(payload["record"], "outcomes", f"tick line {number} record")
            expected_tick = int(payload["tick"]) + 1
            tick_count += 1
        elif kind == "timing":
            continue
        elif kind == "end":
            end = payload
            if payload.get("ticks") != tick_count:
                raise WorldViewError(f"line {number}: end declares {payload.get('ticks')!r} ticks, file has {tick_count}")
        else:
            raise WorldViewError(f"line {number}: unknown event kind {kind!r}")
    if header is None:
        raise WorldViewError("unrecognised run file: empty")
    if end is None:
        raise WorldViewError("run file has no end record (run did not finish, or the file was cut)")
    return LoadedRun(path=path, text=text, sha256=hashlib.sha256(raw).hexdigest(), header=header, tick_count=tick_count)


CSS = r"""
:root { --bg:#14161a; --panel:#1c1f25; --line:#2c313a; --fg:#e8e6df; --muted:#8f949c; --accent:#d9a441;
        --fed:#5db26f; --hungry:#e0a23a; --emergency:#d4523c; --dead:#7d8189; --source:#4f8fd6; --yield:#b48ede; }
* { box-sizing:border-box; }
html, body { margin:0; height:100%; background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
body { display:grid; grid-template-rows:auto 1fr auto auto; grid-template-columns:1fr 340px; grid-template-areas:"head head" "stage side" "ctrl side" "foot foot"; height:100vh; gap:0; }
header { grid-area:head; display:flex; align-items:baseline; gap:14px; padding:10px 16px; border-bottom:1px solid var(--line); flex-wrap:wrap; }
header h1 { font-size:16px; margin:0; font-weight:600; }
header .meta { color:var(--muted); font-size:12px; }
header .meta code { font-family:ui-monospace, Consolas, monospace; font-size:11px; }
#stage { grid-area:stage; position:relative; min-height:320px; overflow:hidden; background:radial-gradient(ellipse at 50% 40%, #1b2028 0%, #14161a 70%); }
#stage canvas { position:absolute; inset:0; width:100%; height:100%; display:block; cursor:grab; touch-action:none; }
#stage canvas.dragging { cursor:grabbing; }
#hud { position:absolute; left:12px; top:10px; font-variant-numeric:tabular-nums; font-size:22px; font-weight:600; pointer-events:none; text-shadow:0 1px 2px #000; }
#hud small { display:block; font-size:11px; font-weight:400; color:var(--muted); }
#legend { position:absolute; right:12px; top:10px; font-size:12px; color:var(--muted); background:rgba(20,22,26,.72); padding:8px 10px; border-radius:8px; pointer-events:none; line-height:1.7; }
#legend i { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:-1px; }
#legend i.ring { background:none; border:2px solid var(--yield); }
#legend i.sq { border-radius:2px; }
#ctrl { grid-area:ctrl; display:flex; align-items:center; gap:10px; padding:10px 16px; border-top:1px solid var(--line); background:var(--panel); flex-wrap:wrap; }
#ctrl button { font:inherit; padding:5px 12px; border:1px solid var(--line); background:#242830; color:var(--fg); border-radius:6px; cursor:pointer; min-width:40px; }
#ctrl button:hover { border-color:var(--accent); }
#ctrl button.primary { background:var(--accent); color:#1a1a1a; border-color:var(--accent); font-weight:600; min-width:72px; }
#scrub { flex:1 1 200px; accent-color:var(--accent); }
#ctrl label { font-size:12px; color:var(--muted); display:flex; align-items:center; gap:6px; }
#ctrl input[type=range].small { width:110px; accent-color:var(--accent); }
#ctrl .count { font-variant-numeric:tabular-nums; min-width:11ch; text-align:right; }
aside { grid-area:side; border-left:1px solid var(--line); background:var(--panel); padding:12px 14px; overflow:auto; }
aside h2 { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 8px; }
aside .empty { color:var(--muted); font-size:13px; }
aside dl { display:grid; grid-template-columns:auto 1fr; gap:3px 12px; margin:0 0 12px; font-size:13px; }
aside dt { color:var(--muted); white-space:nowrap; } aside dd { margin:0; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
aside .b-fed { color:var(--fed); } aside .b-hungry { color:var(--hungry); } aside .b-emergency { color:var(--emergency); font-weight:600; } aside .b-dead { color:var(--dead); }
aside .ok { color:var(--fed); } aside .no { color:var(--emergency); }
aside ul { margin:0 0 12px; padding-left:16px; font-size:13px; } aside li { margin:2px 0; }
aside .mono { font-family:ui-monospace, Consolas, monospace; font-size:12px; }
aside .note { color:var(--muted); font-size:12px; border-top:1px solid var(--line); padding-top:8px; margin-top:8px; }
footer { grid-area:foot; padding:8px 16px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }
@media (max-width: 860px) { body { grid-template-columns:1fr; grid-template-areas:"head" "stage" "ctrl" "side" "foot"; grid-template-rows:auto 55vh auto auto auto; height:auto; } aside { border-left:none; border-top:1px solid var(--line); } }
"""

# The pure part: builds typed arrays from the parsed run and computes one
# frame. No DOM. The test suite runs this under node against the synthetic
# 50 x 2,000 fixture and times `frame`.
JS_CORE = r"""
'use strict';
const WorldViewCore = (() => {
  const BANDS = ['fed', 'hungry', 'emergency', 'dead'];
  function bandOf(h, dead, C) { return dead ? 3 : h >= C.death_at ? 3 : h >= C.emergency_at ? 2 : h >= C.hungry_at ? 1 : 0; }
  function parseLines(text) {
    const header = { value: null }, ticks = [], timings = {}; let end = null;
    let start = 0;
    while (start < text.length) {
      let nl = text.indexOf('\n', start); if (nl < 0) nl = text.length;
      if (nl > start) {
        const p = JSON.parse(text.slice(start, nl));
        if (p.kind === 'header') header.value = p;
        else if (p.kind === 'tick') ticks.push(p);
        else if (p.kind === 'timing') timings[p.tick] = p.elapsed_ns;
        else if (p.kind === 'end') end = p;
      }
      start = nl + 1;
    }
    return { header: header.value, ticks, timings, end };
  }
  // Recorded state at index t: t = 0 is genesis, t = k is the world after k ticks.
  function buildModel(header, ticks) {
    const C = header.scenario, W0 = header.world, people = Object.keys(W0.positions).sort();
    const P = people.length, n = ticks.length, N = n + 1, src = C.source;
    const idx = {}; people.forEach((p, i) => { idx[p] = i; });
    const px = new Float32Array(N * P), py = new Float32Array(N * P), hunger = new Int16Array(N * P);
    const band = new Uint8Array(N * P), alive = new Uint8Array(N * P), ox = new Float32Array(N * P), oy = new Float32Array(N * P);
    const stock = new Int32Array(N), crowd = new Int32Array(N), aliveCount = new Int32Array(N);
    const diedAt = new Int32Array(P).fill(-1);
    const yieldAt = W0.yield_at ? new Int32Array(P) : null;
    if (yieldAt) people.forEach((p, i) => { yieldAt[i] = W0.yield_at[p]; });
    const key = C.source_position[0] + ',' + C.source_position[1];
    const groups = new Map();
    for (let t = 0; t < N; t++) {
      const w = t === 0 ? W0 : ticks[t - 1].world;
      let s = t === 0 ? header.genesis.sources[src].stock : ticks[t - 1].state.sources[src].stock;
      if (t > 0 && ticks[t - 1].production) for (const e of ticks[t - 1].production) s += e.amount;
      stock[t] = s;
      groups.clear();
      let c = 0, a = 0;
      for (let i = 0; i < P; i++) {
        const p = people[i], pos = w.positions[p], dead = p in w.died_at, k = t * P + i;
        px[k] = pos[0]; py[k] = pos[1]; hunger[k] = w.hunger[p]; alive[k] = dead ? 0 : 1;
        band[k] = bandOf(w.hunger[p], dead, C);
        if (dead && diedAt[i] < 0) diedAt[i] = w.died_at[p];
        if (!dead) { a++; if (pos[0] + ',' + pos[1] === key) c++; }
        const gk = pos[0] * 4096 + pos[1]; let g = groups.get(gk); if (!g) { g = []; groups.set(gk, g); } g.push(i);
      }
      crowd[t] = c; aliveCount[t] = a;
      // people sharing a cell stand in a small ring so each stays visible; offsets are display only
      for (const g of groups.values()) {
        const m = g.length; if (m === 1) { ox[t * P + g[0]] = 0; oy[t * P + g[0]] = 0; continue; }
        const r = Math.min(0.32, 0.12 + 0.05 * m);
        for (let j = 0; j < m; j++) { const ang = (2 * Math.PI * j) / m - Math.PI / 2; ox[t * P + g[j]] = r * Math.cos(ang); oy[t * P + g[j]] = r * Math.sin(ang); }
      }
    }
    return { header, ticks, C, people, idx, P, n, N, px, py, hunger, band, alive, ox, oy, stock, crowd, aliveCount, diedAt, yieldAt, BANDS };
  }
  function ease(p) { return p < 0.5 ? 2 * p * p : 1 - ((-2 * p + 2) ** 2) / 2; }
  function newFrame(P) { return { t: 0, progress: 0, x: new Float32Array(P), y: new Float32Array(P), band0: new Uint8Array(P), band1: new Uint8Array(P), deathAlpha: new Float32Array(P), yielding: new Uint8Array(P), depth: new Float32Array(P), order: new Int32Array(P) }; }
  // One display frame: recorded state t tweened toward t + 1 by `progress` in [0, 1).
  // At progress 0 the frame is exactly the recorded state t. Nothing here is written back.
  function frame(m, t, progress, out) {
    const P = m.P, t1 = t < m.n ? t + 1 : t, e = t < m.n ? ease(progress) : 0, base0 = t * P, base1 = t1 * P;
    out.t = t; out.progress = progress;
    const dec = t < m.n ? m.ticks[t].decisions : null;
    for (let i = 0; i < P; i++) {
      const k0 = base0 + i, k1 = base1 + i;
      out.x[i] = m.px[k0] + m.ox[k0] + (m.px[k1] + m.ox[k1] - m.px[k0] - m.ox[k0]) * e;
      out.y[i] = m.py[k0] + m.oy[k0] + (m.py[k1] + m.oy[k1] - m.py[k0] - m.oy[k0]) * e;
      out.band0[i] = m.band[k0]; out.band1[i] = m.band[k1];
      const d = m.diedAt[i];
      out.deathAlpha[i] = d < 0 || t < d ? 0 : Math.max(0, 1 - (t + progress - d) / 3);
      let yl = 0; if (dec) { const di = dec[m.people[i]]; if (di && di.kind === 'yield') yl = 1; }
      out.yielding[i] = yl;
      out.depth[i] = out.x[i] + out.y[i];
      out.order[i] = i;
    }
    // insertion sort by depth, farther first; P is small and this allocates nothing
    const o = out.order, dp = out.depth;
    for (let i = 1; i < P; i++) { const v = o[i], dv = dp[v]; let j = i - 1; while (j >= 0 && dp[o[j]] > dv) { o[j + 1] = o[j]; j--; } o[j + 1] = v; }
    return out;
  }
  return { parseLines, buildModel, frame, newFrame, ease, bandOf, BANDS };
})();
if (typeof module !== 'undefined') module.exports = WorldViewCore;
"""

JS_UI = r"""
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const text = JSON.parse($('run-jsonl').textContent);
  const parsed = WorldViewCore.parseLines(text);
  const m = WorldViewCore.buildModel(parsed.header, parsed.ticks);
  const C = m.C, P = m.P, n = m.n;
  const COL = { fed: [93, 178, 111], hungry: [224, 162, 58], emergency: [212, 82, 60], dead: [125, 129, 137] };
  const BANDRGB = [COL.fed, COL.hungry, COL.emergency, COL.dead];
  const TW = 64, TH = 32; // 2:1 diamond
  const isoX = (x, y) => (x - y) * (TW / 2), isoY = (x, y) => (x + y) * (TH / 2);
  const canvas = $('view'), ctx = canvas.getContext('2d');
  const cam = { x: 0, y: 0, z: 1 }; let dpr = 1, cw = 0, ch = 0;
  const fr = WorldViewCore.newFrame(P);
  let t = 0, progress = 0, playing = false, tps = 10, lastTs = 0, selected = null; // selected: {kind:'person', i} | {kind:'source'}
  const ground = new Path2D(), groundAlt = new Path2D(), homes = new Path2D(), homeRoofs = new Path2D();
  for (let y = 0; y < C.height; y++) for (let x = 0; x < C.width; x++) {
    const p = (x + y) % 2 ? groundAlt : ground;
    p.moveTo(isoX(x, y), isoY(x, y)); p.lineTo(isoX(x + 1, y), isoY(x + 1, y)); p.lineTo(isoX(x + 1, y + 1), isoY(x + 1, y + 1)); p.lineTo(isoX(x, y + 1), isoY(x, y + 1)); p.closePath();
  }
  for (const p of m.people) {
    const [hx, hy] = m.header.world.homes[p], cx = isoX(hx + 0.5, hy + 0.5), cy = isoY(hx + 0.5, hy + 0.5);
    homes.moveTo(cx - 16, cy); homes.lineTo(cx, cy - 8); homes.lineTo(cx + 16, cy); homes.lineTo(cx, cy + 8); homes.closePath();
    homeRoofs.moveTo(cx - 16, cy); homeRoofs.lineTo(cx, cy - 24); homeRoofs.lineTo(cx + 16, cy); homeRoofs.closePath();
  }
  function fit() {
    const minX = isoX(0, C.height), maxX = isoX(C.width, 0), minY = 0, maxY = isoY(C.width, C.height) + 30;
    const z = Math.min(cw / (maxX - minX + 60), ch / (maxY - minY + 60));
    cam.z = z; cam.x = cw / 2 - z * (minX + maxX) / 2; cam.y = ch / 2 - z * (minY + maxY) / 2;
  }
  function resize() {
    dpr = window.devicePixelRatio || 1; const r = canvas.getBoundingClientRect();
    const prevW = cw, prevH = ch; cw = r.width; ch = r.height;
    canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
    if (!prevW) fit(); else { cam.x += (cw - prevW) / 2; cam.y += (ch - prevH) / 2; }
    draw();
  }
  function rgb(a, b, e) { return 'rgb(' + Math.round(a[0] + (b[0] - a[0]) * e) + ',' + Math.round(a[1] + (b[1] - a[1]) * e) + ',' + Math.round(a[2] + (b[2] - a[2]) * e) + ')'; }
  function draw() {
    WorldViewCore.frame(m, t, progress, fr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cw, ch);
    ctx.setTransform(dpr * cam.z, 0, 0, dpr * cam.z, dpr * cam.x, dpr * cam.y);
    ctx.fillStyle = '#3b4a3a'; ctx.fill(ground); ctx.fillStyle = '#41523f'; ctx.fill(groundAlt);
    ctx.strokeStyle = 'rgba(0,0,0,0.25)'; ctx.lineWidth = 1; ctx.stroke(ground); ctx.stroke(groundAlt);
    ctx.fillStyle = '#6b5a45'; ctx.fill(homes); ctx.fillStyle = 'rgba(201,180,143,0.35)'; ctx.fill(homeRoofs); ctx.strokeStyle = '#c9b48f'; ctx.lineWidth = 2; ctx.stroke(homeRoofs);
    // source cell: fill by recorded stock at state t, numeral, crowd badge
    const [sx, sy] = C.source_position, scx = isoX(sx + 0.5, sy + 0.5), scy = isoY(sx + 0.5, sy + 0.5);
    const st = m.stock[t], frac = C.source_cap > 0 ? Math.min(1, st / C.source_cap) : 0;
    ctx.beginPath(); ctx.moveTo(isoX(sx, sy), isoY(sx, sy)); ctx.lineTo(isoX(sx + 1, sy), isoY(sx + 1, sy)); ctx.lineTo(isoX(sx + 1, sy + 1), isoY(sx + 1, sy + 1)); ctx.lineTo(isoX(sx, sy + 1), isoY(sx, sy + 1)); ctx.closePath();
    ctx.fillStyle = 'rgba(79,143,214,' + (0.25 + 0.65 * frac).toFixed(3) + ')'; ctx.fill(); ctx.strokeStyle = '#8ab4f0'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#eaf2ff'; ctx.font = '600 14px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(st), scx, scy + 1);
    if (m.crowd[t] > 0) { ctx.fillStyle = 'rgba(20,22,26,0.85)'; ctx.beginPath(); ctx.arc(scx - 30, scy + 14, 9, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#8ab4f0'; ctx.font = '600 10px system-ui, sans-serif'; ctx.fillText('×' + m.crowd[t], scx - 30, scy + 14.5); }
    // people, farther first
    for (let oi = 0; oi < P; oi++) {
      const i = fr.order[oi], cx = isoX(fr.x[i] + 0.5, fr.y[i] + 0.5), cy = isoY(fr.x[i] + 0.5, fr.y[i] + 0.5);
      const da = fr.deathAlpha[i];
      if (m.diedAt[i] >= 0 && t >= m.diedAt[i]) {
        if (da <= 0) continue;
        ctx.globalAlpha = da; ctx.strokeStyle = '#9aa0a8'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cx - 8, cy - 8); ctx.lineTo(cx + 8, cy + 8); ctx.moveTo(cx + 8, cy - 8); ctx.lineTo(cx - 8, cy + 8); ctx.stroke();
        ctx.fillStyle = '#c4c8ce'; ctx.font = '10px system-ui, sans-serif'; ctx.fillText(m.people[i], cx, cy - 16); ctx.globalAlpha = 1; continue;
      }
      const e = fr.band0[i] === fr.band1[i] ? 0 : WorldViewCore.ease(progress);
      const col = rgb(BANDRGB[fr.band0[i]], BANDRGB[fr.band1[i]], e);
      const sel = selected && selected.kind === 'person' && selected.i === i;
      ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(cx, cy + 2, 13, 6, 0, 0, Math.PI * 2); ctx.fill();
      if (fr.yielding[i]) { ctx.strokeStyle = '#b48ede'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.ellipse(cx, cy + 1, 20, 10, 0, 0, Math.PI * 2); ctx.stroke(); }
      if (sel) { ctx.strokeStyle = '#d9a441'; ctx.lineWidth = 2; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.ellipse(cx, cy + 1, 24, 12, 0, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }
      ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(cx - 9, cy - 27, 18, 27, 6); ctx.fill();
      ctx.fillStyle = '#f2e6d3'; ctx.beginPath(); ctx.arc(cx, cy - 34, 7.5, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.45)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(cx - 9, cy - 27, 18, 27, 6); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = '600 11px system-ui, sans-serif'; ctx.fillText(m.people[i].replace(/^p0?/, ''), cx, cy - 13);
      if (m.yieldAt) { ctx.fillStyle = '#d9a441'; ctx.font = '600 10px system-ui, sans-serif'; ctx.fillText(String(m.yieldAt[i]), cx + 14, cy - 37); }
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    $('tick').textContent = 'tick ' + t;
    $('hudsub').textContent = 'of ' + n + ' · alive ' + m.aliveCount[t] + '/' + P + ' · stock ' + m.stock[t];
    $('count').textContent = t + ' / ' + n;
    if (Number($('scrub').value) !== t) $('scrub').value = t;
  }
  // recorded-only inspect panel; values are the recorded state t and the recorded decision/outcomes of tick t
  function bandLabel(i) { return WorldViewCore.BANDS[m.band[t * P + i]]; }
  function foodOf(p) { if (t === 0) return m.header.genesis.balances[p]; const tk = m.ticks[t - 1]; const a = tk.availability && tk.availability['actor:' + p]; return a === undefined ? tk.state.balances[p] : a; }
  function renderInspect() {
    const box = $('inspect');
    if (!selected) { box.innerHTML = '<p class="empty">Click a person or the source. Values shown are the recorded state at the current tick.</p>'; return; }
    const tk = t < n ? m.ticks[t] : null;
    let h = '';
    if (selected.kind === 'person') {
      const i = selected.i, p = m.people[i], w = t === 0 ? m.header.world : m.ticks[t - 1].world, b = bandLabel(i), dead = p in w.died_at;
      h += '<h2>' + esc(p) + ' · recorded state ' + t + '</h2><dl>';
      h += '<dt>at</dt><dd class="mono">' + w.positions[p].join(', ') + '</dd>';
      h += '<dt>hunger</dt><dd class="b-' + b + '">' + w.hunger[p] + ' (' + b + (dead ? ', died at boundary ' + w.died_at[p] : '') + ')</dd>';
      h += '<dt>food held</dt><dd>' + foodOf(p) + '</dd>';
      if (m.yieldAt) h += '<dt>yield_at</dt><dd>' + m.yieldAt[i] + '</dd>';
      h += '<dt>home</dt><dd class="mono">' + m.header.world.homes[p].join(', ') + '</dd></dl>';
      if (tk) {
        const d = tk.decisions && tk.decisions[p];
        h += '<h2>decided at tick ' + t + '</h2>';
        if (d) { h += '<dl><dt>action</dt><dd>' + esc(d.kind) + (d.amount ? ' ' + d.amount : '') + '</dd><dt>reason</dt><dd>' + esc(d.reason || '') + '</dd>';
          if (d.scores) h += '<dt>recorded scores</dt><dd class="mono">' + esc(Object.keys(d.scores).sort().map(k => k + ' (' + d.scores[k].join(',') + ')').join('; ')) + '</dd>';
          h += '</dl>'; } else h += '<p class="empty">no decision recorded (not living at tick start)</p>';
        const outs = tk.record.outcomes.filter(o => o.actor === p);
        if (outs.length) { h += '<h2>kernel outcome, tick ' + t + '</h2><ul>'; for (const o of outs) h += '<li>' + esc(o.operation) + ' <span class="' + (o.accepted ? 'ok' : 'no') + '">' + (o.accepted ? 'accepted' : 'denied') + '</span> · ' + esc(o.reason) + '</li>'; h += '</ul>'; }
      } else h += '<p class="empty">final state; no further tick recorded</p>';
    } else {
      h += '<h2>source · recorded state ' + t + '</h2><dl><dt>stock</dt><dd>' + m.stock[t] + ' / ' + C.source_cap + '</dd><dt>people on cell</dt><dd>' + m.crowd[t] + '</dd></dl>';
      if (tk) {
        const claims = tk.record.outcomes.filter(o => o.operation === 'claim');
        h += '<h2>claims settled at tick ' + t + '</h2>';
        if (claims.length) { h += '<ul>'; for (const o of claims) { const fx = (o.effects || []).map(e => e.account + ' ' + (e.delta > 0 ? '+' : '') + e.delta).join(', '); h += '<li>' + esc(o.actor) + ' <span class="' + (o.accepted ? 'ok' : 'no') + '">' + (o.accepted ? 'accepted' : 'denied') + '</span> · ' + esc(o.reason) + (fx ? ' <span class="mono">' + esc(fx) + '</span>' : '') + '</li>'; } h += '</ul>'; }
        else h += '<p class="empty">none</p>';
        h += '<dl><dt>rotation</dt><dd class="mono">' + esc((tk.record.rotated_roster || []).join(' → ')) + '</dd>';
        h += '<dt>renewal after tick</dt><dd>' + (tk.production ? tk.production.map(e => '+' + e.amount + ' ' + esc(e.source)).join(', ') : 'none') + '</dd></dl>';
      }
    }
    h += '<p class="note">Recorded values only. No score, winner or count here is recomputed by this page.</p>';
    box.innerHTML = h;
  }
  function setTick(k, keepPlaying) { t = Math.max(0, Math.min(n, k)); progress = 0; if (!keepPlaying) stop(); draw(); renderInspect(); }
  function stop() { playing = false; $('play').textContent = 'play'; }
  function play() { if (t >= n) setTick(0); playing = true; $('play').textContent = 'pause'; lastTs = 0; requestAnimationFrame(loop); }
  function loop(ts) {
    if (!playing) return;
    let moved = false;
    if (lastTs) { progress += (ts - lastTs) / 1000 * tps; while (progress >= 1 && t < n) { progress -= 1; t += 1; moved = true; } if (t >= n) { t = n; progress = 0; stop(); } }
    lastTs = ts; draw();
    if (moved && selected) renderInspect(); // the panel follows the recorded tick, never the tween
    if (playing) requestAnimationFrame(loop); else renderInspect();
  }
  function pick(mx, my) {
    // hit-test against the current display frame; the panel then shows recorded values
    const wx = (mx - cam.x) / cam.z, wy = (my - cam.y) / cam.z; let best = null, bd = 22 * 22;
    for (let i = 0; i < P; i++) { const cx = isoX(fr.x[i] + 0.5, fr.y[i] + 0.5), cy = isoY(fr.x[i] + 0.5, fr.y[i] + 0.5) - 18; const d = (cx - wx) ** 2 + (cy - wy) ** 2; if (d < bd) { bd = d; best = { kind: 'person', i }; } }
    if (!best) { const [sx, sy] = C.source_position; const cx = isoX(sx + 0.5, sy + 0.5), cy = isoY(sx + 0.5, sy + 0.5); if ((cx - wx) ** 2 + (cy - wy) ** 2 < 24 * 24) best = { kind: 'source' }; }
    return best;
  }
  let drag = null;
  canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: false }; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; canvas.classList.add('dragging'); } cam.x = drag.cx + dx; cam.y = drag.cy + dy; if (drag.moved) draw(); });
  canvas.addEventListener('pointerup', e => { if (!drag) return; if (!drag.moved) { const r = canvas.getBoundingClientRect(); selected = pick(e.clientX - r.left, e.clientY - r.top); draw(); renderInspect(); } drag = null; canvas.classList.remove('dragging'); });
  canvas.addEventListener('wheel', e => { e.preventDefault(); const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top; const f = Math.exp(-e.deltaY * 0.0015), z = Math.max(0.2, Math.min(6, cam.z * f)); cam.x = mx - (mx - cam.x) * (z / cam.z); cam.y = my - (my - cam.y) * (z / cam.z); cam.z = z; draw(); }, { passive: false });
  $('play').addEventListener('click', () => playing ? (stop(), draw(), renderInspect()) : play());
  $('back').addEventListener('click', () => setTick(t - 1));
  $('fwd').addEventListener('click', () => setTick(t + 1));
  $('start').addEventListener('click', () => setTick(0));
  $('end').addEventListener('click', () => setTick(n));
  $('fit').addEventListener('click', () => { fit(); draw(); });
  $('scrub').max = n; $('scrub').addEventListener('input', e => setTick(Number(e.target.value)));
  $('speed').addEventListener('input', e => { tps = Number(e.target.value); $('speedv').textContent = tps + ' t/s'; });
  document.addEventListener('keydown', e => { if (e.target.tagName === 'INPUT') return; if (e.key === ' ') { e.preventDefault(); playing ? (stop(), draw(), renderInspect()) : play(); } else if (e.key === 'ArrowLeft') setTick(t - 1); else if (e.key === 'ArrowRight') setTick(t + 1); else if (e.key === 'Home') setTick(0); else if (e.key === 'End') setTick(n); else if (e.key === 'f') { fit(); draw(); } });
  window.addEventListener('resize', resize);
  $('speedv').textContent = tps + ' t/s';
  resize(); renderInspect();
})();
"""


def render_html(run: LoadedRun) -> str:
    header = run.header
    scenario = header["scenario"]
    world = header["world"]
    run_id = str(header.get("run_id", run.path.name))
    # The file text goes in as one JSON string. `<` is written as < so no
    # byte sequence in the data can close the script element; JSON.parse in the
    # page (and json.loads in the tests) gives back the exact file text.
    data = json.dumps(run.text, ensure_ascii=True).replace("<", "\\u003c")
    title = f"{run_id} — world view"
    people = len(world["positions"])
    levers = f"{scenario['width']}×{scenario['height']} grid · {people} people · {run.tick_count} ticks · seed {scenario.get('seed', '?')} · yield {scenario.get('yield', '?')} · scoring {scenario.get('scoring', 'off')}"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="source-file" content="{html.escape(run.path.name)}"><meta name="source-sha256" content="{run.sha256}">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body>
<header><h1>{html.escape(run_id)}</h1><span class="meta">{html.escape(levers)}</span><span class="meta">source <code>{html.escape(run.path.name)}</code> sha256 <code>{run.sha256[:16]}…</code></span></header>
<div id="stage"><canvas id="view"></canvas>
  <div id="hud"><span id="tick">tick 0</span><small id="hudsub"></small></div>
  <div id="legend"><div><i style="background:var(--fed)"></i>fed</div><div><i style="background:var(--hungry)"></i>hungry</div><div><i style="background:var(--emergency)"></i>emergency</div><div><i style="background:var(--dead)"></i>dead (fades over 3 ticks)</div><div><i class="ring"></i>yielding this tick</div><div><i class="sq" style="background:var(--source)"></i>source, stock and ×crowd</div><div><i class="sq" style="background:#6b5a45"></i>home</div><div>small gold number: yield_at</div><div>drag to pan · wheel to zoom · space plays · ← → step</div></div>
</div>
<aside><div id="inspect"></div></aside>
<div id="ctrl">
  <button id="start" title="genesis">⏮</button><button id="back" title="step back">◀</button><button id="play" class="primary">play</button><button id="fwd" title="step forward">▶</button><button id="end" title="final state">⏭</button>
  <input id="scrub" type="range" min="0" max="0" step="1" value="0">
  <span class="count" id="count">0 / 0</span>
  <label>speed <input id="speed" class="small" type="range" min="1" max="20" step="1" value="10"><span id="speedv"></span></label>
  <button id="fit">fit</button>
</div>
<footer>Motion between ticks is interpolated for display. All values shown are the recorded tick state. Presentation track under OD-012; not an instrument, not evidence, not owner acceptance of any checkpoint.</footer>
<script id="run-jsonl" type="application/json">{data}</script>
<script>{JS_CORE}</script>
<script>{JS_UI}</script>
</body></html>
"""


def default_output(run_path: Path) -> Path:
    return run_path.with_name(run_path.stem + ".world.html")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a saved world run as an isometric, smoothly played world view.")
    parser.add_argument("run", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        run = load_run(args.run)
    except WorldViewError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    out = args.out or default_output(args.run)
    page = render_html(run)
    out.write_text(page, encoding="utf-8", newline="\n")  # same bytes on every platform
    sys.stdout.write(f"wrote {out} ({len(page.encode('utf-8'))} bytes; source sha256 {run.sha256})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
