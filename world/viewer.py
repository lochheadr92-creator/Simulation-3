"""Render a world run as a map over time: a self-contained HTML page, or text.

    py -3 -B -m world.viewer runs/<run>.jsonl            # writes runs/<run>.html
    py -3 -B -m world.viewer runs/<run>.jsonl --text 40  # print the map at view 40

The page embeds the run file's content and reads nothing else: no network,
no scripts from elsewhere, no live engine. Every number shown is a value the
run recorded (positions, hunger, balances, stocks, decisions, outcomes) or a
count of those values. It is a way to look, not a second scorer.

View k shows the world after tick k-1 (view 0 is genesis) together with the
decisions and outcomes of tick k-1, the ones that produced it.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from stream.run_file import Run, read_run

CSS = """
:root { --bg:#f7f7f4; --fg:#1d1d1b; --muted:#6b6b66; --line:#d9d9d2; --panel:#ffffff; --cell:#efefe9;
        --fed:#2f7d4f; --hungry:#c98a1b; --emergency:#a63d2f; --dead:#7a7a74; --source:#2f5f9f; --sourcebg:#dbe7f7;
        --ok:#2f7d4f; --okbg:#e3f3e8; --no:#a63d2f; --nobg:#f8e6e2; }
@media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#ecece6; --muted:#9a9a92; --line:#33332f; --panel:#1f1f1c; --cell:#242421;
        --fed:#7fd39a; --hungry:#e2b25a; --emergency:#f09a8a; --dead:#8d8d86; --source:#8ab4f0; --sourcebg:#22314a;
        --ok:#7fd39a; --okbg:#1f3427; --no:#f09a8a; --nobg:#3a221e; } }
* { box-sizing:border-box; } body { margin:0; padding:16px; background:var(--bg); color:var(--fg);
  font:14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { font-size:18px; margin:0 0 4px; } h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:18px 0 6px; }
.meta { color:var(--muted); font-size:12px; word-break:break-all; }
.controls { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:12px 0; position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:2; }
.controls input[type=range] { flex:1 1 240px; } button { font:inherit; padding:4px 10px; border:1px solid var(--line); background:var(--panel); color:var(--fg); border-radius:6px; cursor:pointer; }
label.toggle { font-size:12px; color:var(--muted); } .tick { font-variant-numeric:tabular-nums; font-weight:600; min-width:9ch; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:12px; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 12px; overflow:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; } th, td { text-align:left; padding:3px 14px 3px 0; border-bottom:1px solid var(--line); vertical-align:top; white-space:nowrap; }
th { color:var(--muted); font-weight:500; font-size:12px; } td.num, th.num { text-align:right; padding-right:14px; }
.ok { color:var(--ok); background:var(--okbg); border-radius:4px; padding:0 5px; } .no { color:var(--no); background:var(--nobg); border-radius:4px; padding:0 5px; }
.b-fed { color:var(--fed); } .b-hungry { color:var(--hungry); } .b-emergency { color:var(--emergency); font-weight:600; } .b-dead { color:var(--dead); }
svg.map { width:100%; height:auto; display:block; max-height:70vh; } svg.chart { width:100%; height:auto; display:block; }
.legend { font-size:12px; color:var(--muted); } .legend span { display:inline-block; margin-right:12px; }
.mono { font-family:ui-monospace, Consolas, monospace; font-size:12px; } .problem { color:var(--no); }
.stats { display:flex; gap:18px; flex-wrap:wrap; font-size:13px; } .stats b { font-variant-numeric:tabular-nums; }
"""

JS = r"""
const RUN = JSON.parse(document.getElementById('run-data').textContent);
const H = RUN.header, C = H.scenario, ticks = RUN.ticks, n = ticks.length;
const people = Object.keys(H.world.positions).sort();
let v = 0, timer = null, trails = true;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const band = (h, dead) => dead ? 'dead' : h >= C.death_at ? 'dead' : h >= C.emergency_at ? 'emergency' : h >= C.hungry_at ? 'hungry' : 'fed';
const colour = b => `var(--${b})`;
function world(k) { return k === 0 ? H.world : ticks[k - 1].world; }
function food(k, p) { if (k === 0) return H.genesis.balances[p]; const a = ticks[k - 1].availability['actor:' + p]; return a === undefined ? ticks[k - 1].state.balances[p] : a; }
function stock(k) { if (k === 0) return H.genesis.sources[C.source].stock; const t = ticks[k - 1]; let s = t.state.sources[C.source].stock; for (const e of (t.production || [])) s += e.amount; return s; }
function outcomeOf(t, p) { for (const o of t.record.outcomes) if (o.actor === p) return o; return null; }
const series = { stock: [], alive: [], hunger: {} }; for (const p of people) series.hunger[p] = [];
const totals = { claimsOk: 0, claimsNo: 0, eats: 0, emergencyTicks: 0, deaths: [] };
for (let k = 0; k <= n; k++) {
  const w = world(k); series.stock.push(stock(k)); let alive = 0;
  for (const p of people) { const dead = p in w.died_at; if (!dead) alive++; series.hunger[p].push(dead ? null : w.hunger[p]); if (!dead && w.hunger[p] >= C.emergency_at) totals.emergencyTicks++; }
  series.alive.push(alive);
  if (k >= 1) { for (const o of ticks[k - 1].record.outcomes) { if (o.operation === 'claim') { if (o.accepted) totals.claimsOk++; else totals.claimsNo++; } else if (o.operation === 'consume' && o.accepted) totals.eats++; } }
}
for (const p of people) { const w = world(n); if (p in w.died_at) totals.deaths.push([p, w.died_at[p]]); }
totals.deaths.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
function drawMap(k) {
  const w = world(k), cell = 40, W = C.width * cell, Hh = C.height * cell;
  let s = `<svg class="map" viewBox="0 0 ${W} ${Hh}" xmlns="http://www.w3.org/2000/svg">`;
  for (let y = 0; y < C.height; y++) for (let x = 0; x < C.width; x++) s += `<rect x="${x*cell}" y="${y*cell}" width="${cell}" height="${cell}" fill="var(--cell)" stroke="var(--bg)"/>`;
  for (const p of people) { const [hx, hy] = w.homes[p]; s += `<rect x="${hx*cell+4}" y="${hy*cell+4}" width="${cell-8}" height="${cell-8}" fill="none" stroke="var(--line)" stroke-dasharray="3 3"/>`; }
  const [sx, sy] = C.source_position; const st = stock(k);
  s += `<rect x="${sx*cell+2}" y="${sy*cell+2}" width="${cell-4}" height="${cell-4}" fill="var(--sourcebg)" stroke="var(--source)" stroke-width="2"/>`;
  s += `<text x="${sx*cell+cell/2}" y="${sy*cell+cell/2+5}" text-anchor="middle" font-size="15" font-weight="600" fill="var(--source)">${st}</text>`;
  if (trails && k > 0) for (const p of people) { const pts = []; for (let j = Math.max(0, k - 12); j <= k; j++) { const [x, y] = world(j).positions[p]; pts.push(`${x*cell+cell/2},${y*cell+cell/2}`); }
    s += `<polyline points="${pts.join(' ')}" fill="none" stroke="${colour(band(w.hunger[p], p in w.died_at))}" stroke-width="2" stroke-opacity="0.35"/>`; }
  const at = {}; for (const p of people) { const key = w.positions[p].join(','); (at[key] = at[key] || []).push(p); }
  for (const key in at) { const [x, y] = key.split(',').map(Number); const dead = at[key].filter(p => p in w.died_at), live = at[key].filter(p => !(p in w.died_at));
    // the dead lie along the top edge of the cell, small, so a stock number or a living person stays readable
    dead.forEach((p, i) => { const cx = x*cell+8+i*11, cy = y*cell+9;
      s += `<text x="${cx}" y="${cy}" text-anchor="middle" font-size="11" fill="var(--dead)">&#215;</text><text x="${cx}" y="${cy+8}" text-anchor="middle" font-size="7" fill="var(--dead)">${p.slice(1)}</text>`; });
    const m = live.length; live.forEach((p, i) => { const b = band(w.hunger[p], false); const off = m === 1 ? 0 : (i - (m - 1) / 2) * 12;
      const cx = x*cell+cell/2+off, cy = y*cell+cell/2 + (m > 3 ? (i % 2) * 10 - 5 : 0);
      s += `<circle cx="${cx}" cy="${cy}" r="${m === 1 ? 11 : 8}" fill="${colour(b)}" stroke="var(--panel)" stroke-width="2"/>`;
      s += `<text x="${cx}" y="${cy + (m === 1 ? 4 : 3)}" text-anchor="middle" font-size="${m === 1 ? 10 : 8}" fill="#fff" font-weight="600">${p.slice(1)}</text>`; }); }
  return s + '</svg>';
}
function drawChart() {
  const W = 800, Hh = 150, pad = 28, maxH = Math.max(C.death_at, C.source_cap, 1); const xs = k => pad + (W - pad - 8) * (n ? k / n : 0), ys = val => Hh - 18 - (Hh - 30) * val / maxH;
  let s = `<svg class="chart" viewBox="0 0 ${W} ${Hh}" xmlns="http://www.w3.org/2000/svg">`;
  for (const [lvl, name] of [[C.hungry_at, 'hungry'], [C.emergency_at, 'emergency'], [C.death_at, 'dead']]) s += `<line x1="${pad}" x2="${W-8}" y1="${ys(lvl)}" y2="${ys(lvl)}" stroke="${colour(name)}" stroke-dasharray="2 4" stroke-opacity="0.6"/><text x="${W-6}" y="${ys(lvl)+4}" font-size="9" fill="var(--muted)" text-anchor="end">${name} ${lvl}</text>`;
  for (const p of people) { let d = '', pen = false; series.hunger[p].forEach((h, k) => { if (h === null) { pen = false; return; } d += (pen ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(h).toFixed(1); pen = true; }); s += `<path d="${d}" fill="none" stroke="var(--fg)" stroke-opacity="0.35" stroke-width="1"/>`; }
  let d = ''; series.stock.forEach((st, k) => { d += (k ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(st).toFixed(1); }); s += `<path d="${d}" fill="none" stroke="var(--source)" stroke-width="2"/>`;
  for (const [p, t] of totals.deaths) s += `<line x1="${xs(t)}" x2="${xs(t)}" y1="8" y2="${Hh-18}" stroke="var(--dead)" stroke-dasharray="3 3"/><text x="${xs(t)+2}" y="14" font-size="9" fill="var(--dead)">${p} dies</text>`;
  s += `<line id="cursor" x1="${xs(v)}" x2="${xs(v)}" y1="4" y2="${Hh-18}" stroke="var(--fg)"/>`;
  s += `<text x="${pad}" y="${Hh-4}" font-size="10" fill="var(--muted)">view 0</text><text x="${W-8}" y="${Hh-4}" font-size="10" fill="var(--muted)" text-anchor="end">view ${n}</text>`;
  return s + '</svg>';
}
function show(k) {
  v = Math.max(0, Math.min(n, k)); $('slider').value = v; $('tick').textContent = `view ${v} / ${n}`; $('map').innerHTML = drawMap(v);
  const w = world(v), t = v >= 1 ? ticks[v - 1] : null; let alive = 0; let rows = '';
  for (const p of people) { const dead = p in w.died_at; if (!dead) alive++; const b = band(w.hunger[p], dead); const d = t && t.decisions[p]; const o = t && outcomeOf(t, p);
    rows += `<tr><td>${p}</td><td class="mono">${w.positions[p].join(',')}</td><td class="num b-${b}">${w.hunger[p]}</td><td class="b-${b}">${dead ? 'dead (t' + w.died_at[p] + ')' : b}</td><td class="num">${food(v, p)}</td>`
          + `<td>${d ? esc(d.kind) + (d.amount ? ' ' + d.amount : '') + ' <span class="meta">' + esc(d.reason) + '</span>' : ''}</td>`
          + `<td>${o ? `<span class="${o.accepted ? 'ok' : 'no'}">${esc(o.reason)}</span>` : ''}</td></tr>`; }
  $('people').innerHTML = rows;
  const prod = t && t.production ? t.production.map(e => `+${e.amount} ${e.source}`).join(', ') : '';
  $('summary').innerHTML = `<span>alive <b>${alive}</b>/${people.length}</span><span>source stock <b>${stock(v)}</b>/${C.source_cap}</span><span>consumed <b>${v ? t.state.consumed : H.genesis.consumed}</b></span><span>renewal this tick <b>${prod || 'none'}</b></span>`;
  const cur = document.getElementById('cursor'); if (cur) { const x = 28 + (800 - 36) * (n ? v / n : 0); cur.setAttribute('x1', x); cur.setAttribute('x2', x); }
  $('timing').textContent = t && RUN.timings[String(t.tick)] !== undefined ? `tick ${t.tick} cost ${(RUN.timings[String(t.tick)] / 1e6).toFixed(3)} ms` : '';
}
function play() { if (timer) { clearInterval(timer); timer = null; $('play').textContent = 'play'; return; } $('play').textContent = 'pause'; timer = setInterval(() => { if (v >= n) { play(); return; } show(v + 1); }, 120); }
$('slider').max = n; $('slider').addEventListener('input', e => show(Number(e.target.value)));
$('play').addEventListener('click', play); $('prev').addEventListener('click', () => show(v - 1)); $('next').addEventListener('click', () => show(v + 1));
$('trails').addEventListener('change', e => { trails = e.target.checked; show(v); });
document.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') show(v - 1); else if (e.key === 'ArrowRight') show(v + 1); else if (e.key === ' ') { e.preventDefault(); play(); } else if (e.key === 'Home') show(0); else if (e.key === 'End') show(n); });
$('chart').innerHTML = drawChart();
$('totals').innerHTML = `<span>whole run:</span><span>claims accepted <b>${totals.claimsOk}</b></span><span>claims denied <b>${totals.claimsNo}</b></span><span>units eaten <b>${totals.eats}</b></span><span>emergency person-ticks <b>${totals.emergencyTicks}</b></span><span>deaths <b>${totals.deaths.length}</b>${totals.deaths.length ? ' (' + totals.deaths.map(d => d[0] + ' t' + d[1]).join(', ') + ')' : ''}</span>`;
show(0);
"""


def _run_payload(run: Run) -> dict[str, Any]:
    return {
        "header": run.header,
        "ticks": [dict(tick) for tick in run.ticks],
        "timings": {str(tick): ns for tick, ns in run.timings.items()},
        "end": run.end,
        "problems": list(run.problems),
    }


def render_html(run: Run) -> str:
    if not run.has_world:
        raise ValueError("this run has no world overlay; use stream.viewer for a kernel-only run")
    scenario = run.header.get("scenario", {})
    data = json.dumps(_run_payload(run), separators=(",", ":")).replace("<", "\\u003c")
    problems = "".join(f'<li class="problem">{html.escape(p)}</li>' for p in run.problems)
    title = f"{run.run_id or run.path.name} — map over time"
    levers = ", ".join(f"{k} {v}" for k, v in scenario.items() if isinstance(v, int) and k != "seed")
    status = "verifies" if run.complete else "DOES NOT VERIFY"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body>
<h1>{html.escape(run.run_id or run.path.name)}</h1>
<div class="meta">{html.escape(scenario.get('name', ''))} · seed {html.escape(str(scenario.get('seed', '')))} · {len(run.ticks)} ticks · engine {html.escape(str(run.header.get('engine_version', '')))} · {html.escape(str(run.header.get('format', '')))} · file {status}</div>
<div class="meta">{html.escape(levers)}</div>
<div class="meta">movement: {html.escape(str(scenario.get('movement', '')))}<br>decision: {html.escape(str(scenario.get('decision', '')))}</div>
{f'<ul>{problems}</ul>' if problems else ''}
<div class="controls">
  <button id="prev">&#8592;</button><button id="play">play</button><button id="next">&#8594;</button>
  <input id="slider" type="range" min="0" max="0" value="0"><span id="tick" class="tick"></span>
  <label class="toggle"><input id="trails" type="checkbox" checked> trails (last 12 views)</label>
  <span id="timing" class="meta"></span>
</div>
<div class="stats" id="summary"></div>
<div class="grid">
  <div class="panel"><h2>Map</h2><div id="map"></div>
    <div class="legend"><span><b class="b-fed">&#9679;</b> fed</span><span><b class="b-hungry">&#9679;</b> hungry</span><span><b class="b-emergency">&#9679;</b> emergency</span><span><b class="b-dead">&#215;</b> dead</span><span style="color:var(--source)">&#9632; source (stock)</span><span>dashed square: home</span></div></div>
  <div class="panel"><h2>People after this tick</h2>
    <table><thead><tr><th>person</th><th>at</th><th class="num">hunger</th><th>state</th><th class="num">food</th><th>decided (tick before)</th><th>kernel outcome</th></tr></thead><tbody id="people"></tbody></table>
    <p class="meta">Decision and outcome are those of the tick that produced this view. Food is the kernel's free balance. Hunger is the world's value after the tick.</p></div>
</div>
<div class="panel" style="margin-top:12px"><h2>Over time: hunger per person (grey), source stock (blue), deaths</h2><div id="chart"></div><div class="stats" id="totals" style="margin-top:8px"></div></div>
<p class="meta">Exploration output under OD-009. Rendered from the run file alone; nothing here is a second calculation of what the engine decided.</p>
<script id="run-data" type="application/json">{data}</script>
<script>{JS}</script>
</body></html>
"""


def render_text(run: Run, view: int) -> str:
    if not run.has_world:
        raise ValueError("this run has no world overlay")
    if view < 0 or view > len(run.ticks):
        raise ValueError(f"view must be between 0 and {len(run.ticks)}")
    cfg = run.header["scenario"]
    world = run.header["world"] if view == 0 else run.ticks[view - 1]["world"]
    stock = run.header["genesis"]["sources"][cfg["source"]]["stock"] if view == 0 else run.ticks[view - 1]["state"]["sources"][cfg["source"]]["stock"] + sum(e["amount"] for e in run.ticks[view - 1].get("production", []))
    grid = [["." for _ in range(cfg["width"])] for _ in range(cfg["height"])]
    sx, sy = cfg["source_position"]
    grid[sy][sx] = "S"
    for actor in sorted(world["positions"]):
        x, y = world["positions"][actor]
        mark = "x" if actor in world["died_at"] else actor[-1]
        grid[y][x] = mark if grid[y][x] in ".S" else "+"
    lines = [f"{run.run_id} view {view}/{len(run.ticks)}  source S at ({sx}, {sy}) stock {stock}", *(" ".join(row) for row in grid), "",
             "positions and hunger after the tick; decision and outcome are the tick's that produced them"]
    tick = run.ticks[view - 1] if view else None
    for actor in sorted(world["positions"]):
        decision = tick["decisions"].get(actor) if tick else None
        outcome = next((o for o in tick["record"]["outcomes"] if o["actor"] == actor), None) if tick else None
        dead = f" dead t{world['died_at'][actor]}" if actor in world["died_at"] else ""
        lines.append(f"{actor} at {tuple(world['positions'][actor])} hunger {world['hunger'][actor]}{dead}"
                     + (f"  {decision['kind']} ({decision['reason']})" if decision else "")
                     + (f"  -> {outcome['reason']}" if outcome else ""))
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
