"""Render a world run as a map over time: a self-contained HTML page, or text.

    py -3 -B -m world.viewer runs/<run>.jsonl            # writes runs/<run>.html
    py -3 -B -m world.viewer runs/<run>.jsonl --text 40  # print the map at view 40

The page embeds the run file's content and reads nothing else: no network,
no scripts from elsewhere, no live engine. Every number shown is a value the
run recorded (positions, hunger, balances, stocks, decisions, observations,
outcomes) or a count of those values. It is a way to look, not a second scorer.

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
:root { --bg:#f7f7f4; --fg:#1d1d1b; --muted:#6b6b66; --line:#d9d9d2; --panel:#ffffff; --cell:#efefe9; --water:#2563eb;
        --fed:#2f7d4f; --hungry:#c98a1b; --emergency:#a63d2f; --dead:#7a7a74; --source:#2f5f9f; --sourcebg:#dbe7f7; --yield:#6b4c9a;
        --ok:#2f7d4f; --okbg:#e3f3e8; --no:#a63d2f; --nobg:#f8e6e2;
        --rough:#ddd6c6; --roughline:#b9ac90; --shelterbg:#dcecdc; --shelterline:#6f9a6f;
        --builtbg:#cfe3f0; --builtline:#3d7fa8; }
@media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#ecece6; --muted:#9a9a92; --line:#33332f; --panel:#1f1f1c; --cell:#242421; --water:#7aa7f7;
        --fed:#7fd39a; --hungry:#e2b25a; --emergency:#f09a8a; --dead:#8d8d86; --source:#8ab4f0; --sourcebg:#22314a; --yield:#c4a6ef;
        --ok:#7fd39a; --okbg:#1f3427; --no:#f09a8a; --nobg:#3a221e;
        --rough:#302c24; --roughline:#6f6450; --shelterbg:#20301f; --shelterline:#5d8a5d;
        --builtbg:#1d2c36; --builtline:#5e9dc4; } }
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
pre.native { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; margin:0; }
details.rules { margin:6px 0; } details.rules summary { cursor:pointer; }
details.rules summary:hover { color:var(--fg); } details.rules > div { margin-top:6px; }
#events { max-height:420px; overflow:auto; display:flex; flex-direction:column; gap:2px; }
button.event { text-align:left; border:1px solid transparent; background:none; padding:2px 6px; border-radius:5px;
  font:inherit; color:var(--fg); cursor:pointer; white-space:nowrap; }
button.event:hover { background:var(--cell); } button.event.now { border-color:var(--line); background:var(--cell); font-weight:600; }
.evtick { color:var(--muted); font-variant-numeric:tabular-nums; font-size:12px; margin-right:6px; }
.b-yield { color:var(--yield); }
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
const FOOD = C.food_sources || [{id: C.source, position: C.source_position}];
const WELLS = C.water === 'on' ? (C.water_sources || [{id: C.water_source, position: C.water_position}]) : [];
const foodCells = new Set(FOOD.map(f => f.position.join(',')));
const ROUGH = new Set((C.rough || []).map(c => c.join(',')));
const SHELTER = new Set((C.shelter_spots || []).map(c => c.join(',')));
function stockOf(k, id) { if (k === 0) return H.genesis.sources[id].stock; const t = ticks[k - 1]; let s = t.state.sources[id].stock; for (const e of (t.production || [])) if (e.source === id) s += e.amount; return s; }
function stock(k) { let s = 0; for (const f of FOOD) s += stockOf(k, f.id); return s; }
function waterHeld(k, p) { if (k === 0) return H.genesis.holdings.water[p]; const t = ticks[k - 1]; const a = (t.availability || {})['actor@water:' + p]; return a === undefined ? t.state.holdings.water[p] : a; }
function outcomeOf(t, p) { for (const o of t.record.outcomes) if (o.actor === p) return o; return null; }
function personTip(k, p) {
  const w = world(k), dead = p in w.died_at, t = k >= 1 ? ticks[k - 1] : null;
  const bits = [p + (dead ? ' (died tick ' + w.died_at[p] + ')' : ' - ' + band(w.hunger[p], false))];
  bits.push('hunger ' + w.hunger[p] + ' / ' + C.death_at + '   food held ' + food(k, p));
  if (C.water === 'on') bits.push('thirst ' + w.thirst[p] + ' / ' + C.thirst_death_at + '   water held ' + waterHeld(k, p));
  if (C.warmth === 'on') bits.push('cold ' + w.cold[p] + ' / ' + C.cold_death_at
    + (w.positions[p].join(',') === w.homes[p].join(',') ? '   sheltered' : '   out in the cold'));
  const ya = traitOf(p); if (ya !== null) bits.push('yields to a crowd of ' + ya);
  const here = w.positions[p].join(',');
  if (ROUGH.has(here)) bits.push('on rough ground' + ((w.held || {})[p] ? ' - held up this tick' : ''));
  if (SHELTER.has(here)) bits.push('on a shelter spot: needs rise slower here');
  if ((w.shelters || []).some(c => c.join(',') === here)) bits.push('under a shelter somebody built');
  const work = (w.built || {})[p] || 0;
  if (work && C.build_ticks && work < C.build_ticks) bits.push('shelter ' + work + '/' + C.build_ticks + ' built');
  const d = t && t.decisions && t.decisions[p];
  if (d) bits.push('chose: ' + d.kind + (d.target ? ' -> ' + d.target : '') + ' (' + d.reason + ')');
  return bits.join('\n');
}
function traitOf(p) { const t = (H.world.yield_at || {})[p]; return t === undefined ? null : t; }
function crowdAt(k) { const w = world(k); let c = 0; for (const p of people) if (!(p in w.died_at) && foodCells.has(w.positions[p].join(','))) c++; return c; }
const series = { stock: [], alive: [], hunger: {}, crowd: [] }; for (const p of people) series.hunger[p] = [];
const totals = { claimsOk: 0, claimsNo: 0, eats: 0, emergencyTicks: 0, deaths: [], sawOther: 0, sawSource: 0, yields: 0, emergencyBy: {}, deathsBy: {}, yieldTicks: [] };
for (let k = 0; k <= n; k++) {
  const w = world(k); series.stock.push(stock(k)); series.crowd.push(crowdAt(k)); let alive = 0;
  for (const p of people) { const dead = p in w.died_at; if (!dead) alive++; series.hunger[p].push(dead ? null : w.hunger[p]); if (k < n && !dead && w.hunger[p] >= C.emergency_at) { totals.emergencyTicks++; const tr = traitOf(p); if (tr !== null) totals.emergencyBy[tr] = (totals.emergencyBy[tr] || 0) + 1; } }
  series.alive.push(alive);
  if (k >= 1) { for (const o of ticks[k - 1].record.outcomes) { if (o.operation === 'claim') { if (o.accepted) totals.claimsOk++; else totals.claimsNo++; } else if (o.operation === 'consume' && o.accepted) totals.eats++; }
    const block = ticks[k - 1].observations || {};
    for (const p of Object.keys(block)) { if ((block[p].sees || block[p].others || []).length) totals.sawOther++; if (Object.prototype.hasOwnProperty.call(block[p], 'source_food')) totals.sawSource++; }
    let anyYield = false; for (const p of people) { const d = ticks[k - 1].decisions && ticks[k - 1].decisions[p]; if (d && d.kind === 'yield') { totals.yields++; anyYield = true; } }
    if (anyYield) totals.yieldTicks.push(k); }
}
for (const p of people) { const w = world(n); if (p in w.died_at) { totals.deaths.push([p, w.died_at[p]]); const tr = traitOf(p); if (tr !== null) totals.deathsBy[tr] = (totals.deathsBy[tr] || 0) + 1; } }
totals.deaths.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
const traitKeys = [...new Set(people.map(traitOf).filter(v => v !== null))].sort((a, b) => a - b);
function fmtBy(map) { return traitKeys.map(v => v + ':' + (map[v] || 0)).join(', ') || 'none'; }
const EVENTS = [];
for (let k = 1; k <= n; k++) {
  const w = world(k), before = world(k - 1), t = ticks[k - 1];
  for (const p of people) {
    if (p in w.died_at && !(p in before.died_at)) {
      const why = w.hunger[p] >= C.death_at ? 'starved'
        : (C.water === 'on' && w.thirst[p] >= C.thirst_death_at) ? 'died of thirst'
        : (C.warmth === 'on' && w.cold[p] >= C.cold_death_at) ? 'froze to death' : 'died';
      EVENTS.push({ k, who: p, band: 'dead', what: p + ' ' + why });
      continue;
    }
    if (p in w.died_at) continue;
    const d = t.decisions && t.decisions[p];
    if (d && d.kind === 'yield') EVENTS.push({ k, who: p, band: 'yield', what: p + ' stood back from the crowded source' });
    if (d && d.kind === 'offer') {
      const took = (t.record.outcomes || []).some(o => o.actor === p && o.operation === 'transfer' && o.accepted);
      EVENTS.push({ k, who: p, band: took ? 'fed' : 'emergency',
        what: took ? p + ' gave a unit of food to ' + d.target : p + ' offered food to ' + d.target + ', refused' });
    }
    const earlier = k >= 2 ? ticks[k - 2].decisions[p] : null;
    if (d && d.kind === 'go_offer' && !(earlier && earlier.kind === 'go_offer'))
      EVENTS.push({ k, who: p, band: 'hungry', what: p + ' set out to help ' + d.target });
    if (earlier && earlier.kind === 'go_offer' && d && d.kind !== 'go_offer' && d.kind !== 'offer')
      EVENTS.push({ k, who: p, band: 'emergency', what: p + ' turned back from helping ' + earlier.target });
    if (d && d.kind === 'build') {
      const done = (w.built || {})[p] || 0, was = (before.built || {})[p] || 0;
      if (was === 0) EVENTS.push({ k, who: p, band: 'fed', what: p + ' started building a shelter' });
      if (done >= (C.build_ticks || 1) && was < (C.build_ticks || 1))
        EVENTS.push({ k, who: p, band: 'fed', what: p + ' finished their shelter (' + done + ' ticks of work)' });
    }
    if (w.hunger[p] >= C.emergency_at && before.hunger[p] < C.emergency_at)
      EVENTS.push({ k, who: p, band: 'emergency', what: p + ' is starving (hunger ' + w.hunger[p] + ')' });
    if (C.water === 'on' && w.thirst[p] >= C.thirst_emergency_at && before.thirst[p] < C.thirst_emergency_at)
      EVENTS.push({ k, who: p, band: 'emergency', what: p + ' is parched (thirst ' + w.thirst[p] + ')' });
    if (C.warmth === 'on' && w.cold[p] >= C.cold_emergency_at && before.cold[p] < C.cold_emergency_at)
      EVENTS.push({ k, who: p, band: 'emergency', what: p + ' is freezing (cold ' + w.cold[p] + ')' });
  }
  for (const f of FOOD) if (stockOf(k, f.id) === 0 && stockOf(k - 1, f.id) > 0)
    EVENTS.push({ k, who: null, band: 'hungry', what: f.id + ' is picked clean' });
  for (const wl of WELLS) if (stockOf(k, wl.id) === 0 && stockOf(k - 1, wl.id) > 0)
    EVENTS.push({ k, who: null, band: 'hungry', what: wl.id + ' has run dry' });
}
function renderEvents() {
  if (!EVENTS.length) { $('events').innerHTML = '<p class="meta">Nothing dramatic happened: nobody starved, nobody stood back, no source ran out.</p>'; return; }
  $('events').innerHTML = EVENTS.map((e, i) =>
    `<button class="event" data-k="${e.k}" id="ev${i}"><span class="evtick">t${e.k}</span> <span class="b-${e.band}">${esc(e.what)}</span></button>`).join('');
  $('events').querySelectorAll('.event').forEach(b => b.addEventListener('click', () => show(Number(b.dataset.k))));
}
function markEvents(k) {
  const rows = $('events').querySelectorAll('.event'); let seen = null;
  rows.forEach(b => { const at = Number(b.dataset.k); b.classList.toggle('now', at === k); if (at <= k) seen = b; });
  if (seen) seen.scrollIntoView({ block: 'nearest' });
}
function drawMap(k) {
  const w = world(k), cell = 40, W = C.width * cell, Hh = C.height * cell;
  const builtNow = new Set((w.shelters || []).map(c => c.join(',')));
  let s = `<svg class="map" viewBox="0 0 ${W} ${Hh}" xmlns="http://www.w3.org/2000/svg">`;
  for (let y = 0; y < C.height; y++) for (let x = 0; x < C.width; x++) {
    const key = x + ',' + y, rough = ROUGH.has(key), shelterSpot = SHELTER.has(key), made = builtNow.has(key);
    const fill = made ? 'var(--builtbg)' : rough ? 'var(--rough)' : shelterSpot ? 'var(--shelterbg)' : 'var(--cell)';
    s += `<rect x="${x*cell}" y="${y*cell}" width="${cell}" height="${cell}" fill="${fill}" stroke="var(--bg)">`
       + (rough ? '<title>rough ground: crossing it costs an extra tick</title>'
        : shelterSpot ? '<title>shelter spot: hunger and thirst rise slower here</title>' : '') + '</rect>';
    if (rough) s += `<path d="M${x*cell+7} ${y*cell+cell-7} l6 -7 l5 5 l7 -9" fill="none" stroke="var(--roughline)" stroke-width="2"/>`;
    if (shelterSpot) s += `<path d="M${x*cell+9} ${y*cell+cell-10} l${cell/2-9} -8 l${cell/2-9} 8 z" fill="none" stroke="var(--shelterline)" stroke-width="2"/>`;
    if (made) s += `<path d="M${x*cell+6} ${y*cell+cell-6} l${cell/2-6} -11 l${cell/2-6} 11 z" fill="var(--builtline)" fill-opacity="0.85"><title>a shelter somebody built: hunger and thirst rise slower here</title></path>`;
  }
  for (const p of people) { const [hx, hy] = w.homes[p]; s += `<rect x="${hx*cell+4}" y="${hy*cell+4}" width="${cell-8}" height="${cell-8}" fill="none" stroke="var(--line)" stroke-dasharray="3 3"/>`; }
  const radius = C.perception_radius;
  if (typeof radius === 'number') for (const p of people) {
    if (p in w.died_at) continue;
    const [x, y] = w.positions[p];
    const x0 = Math.max(0, x - radius) * cell, y0 = Math.max(0, y - radius) * cell;
    const x1 = (Math.min(C.width - 1, x + radius) + 1) * cell, y1 = (Math.min(C.height - 1, y + radius) + 1) * cell;
    s += `<rect x="${x0+0.5}" y="${y0+0.5}" width="${x1-x0-1}" height="${y1-y0-1}" fill="none" stroke="var(--fg)" stroke-opacity="0.18"/>`;
  }
  const named = FOOD.length > 1 || WELLS.length > 1;
  const place = (src, fill, opacity, stroke, st) => { const [x, y] = src.position;
    s += `<rect x="${x*cell+2}" y="${y*cell+2}" width="${cell-4}" height="${cell-4}" fill="${fill}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="2"><title>${esc(src.id)}</title></rect>`;
    s += `<text x="${x*cell+cell/2}" y="${y*cell+cell/2+5}" text-anchor="middle" font-size="15" font-weight="600" fill="${stroke}">${st}</text>`;
    if (named) s += `<text x="${x*cell+cell/2}" y="${y*cell+cell-4}" text-anchor="middle" font-size="8" fill="${stroke}">${esc(src.id)}</text>`; };
  for (const f of FOOD) place(f, 'var(--sourcebg)', 1, 'var(--source)', stockOf(k, f.id));
  for (const wl of WELLS) place(wl, 'var(--water)', 0.15, 'var(--water)', stockOf(k, wl.id));
  if (trails && k > 0) for (const p of people) { const pts = []; for (let j = Math.max(0, k - 12); j <= k; j++) { const [x, y] = world(j).positions[p]; pts.push(`${x*cell+cell/2},${y*cell+cell/2}`); }
    s += `<polyline points="${pts.join(' ')}" fill="none" stroke="${colour(band(w.hunger[p], p in w.died_at))}" stroke-width="2" stroke-opacity="0.35"/>`; }
  const at = {}; for (const p of people) { const key = w.positions[p].join(','); (at[key] = at[key] || []).push(p); }
  for (const key in at) { const [x, y] = key.split(',').map(Number); const dead = at[key].filter(p => p in w.died_at), live = at[key].filter(p => !(p in w.died_at));
    // the dead lie along the top edge of the cell, small, so a stock number or a living person stays readable
    dead.forEach((p, i) => { const cx = x*cell+8+i*11, cy = y*cell+9;
      if (w.died_at[p] === k) s += `<circle cx="${x*cell+cell/2}" cy="${y*cell+cell/2}" r="${cell/2-2}" fill="none" stroke="var(--emergency)" stroke-width="3" stroke-opacity="0.9"/>`;
      s += `<text x="${cx}" y="${cy}" text-anchor="middle" font-size="11" fill="var(--dead)">&#215;</text><text x="${cx}" y="${cy+8}" text-anchor="middle" font-size="7" fill="var(--dead)">${p.slice(1)}</text>`; });
    const m = live.length; const tDec = k >= 1 ? ticks[k - 1] : null; live.forEach((p, i) => { const b = band(w.hunger[p], false); const off = m === 1 ? 0 : (i - (m - 1) / 2) * 12;
      const cx = x*cell+cell/2+off, cy = y*cell+cell/2 + (m > 3 ? (i % 2) * 10 - 5 : 0);
      const yielded = tDec && tDec.decisions && tDec.decisions[p] && tDec.decisions[p].kind === 'yield';
      if (yielded) s += `<circle cx="${cx}" cy="${cy}" r="${m === 1 ? 15 : 12}" fill="none" stroke="var(--yield)" stroke-width="2"/>`;
      s += `<circle cx="${cx}" cy="${cy}" r="${m === 1 ? 11 : 8}" fill="${colour(b)}" stroke="var(--panel)" stroke-width="2"><title>${esc(personTip(k, p))}</title></circle>`;
      s += `<text x="${cx}" y="${cy + (m === 1 ? 4 : 3)}" text-anchor="middle" font-size="${m === 1 ? 10 : 8}" fill="#fff" font-weight="600">${p.slice(1)}</text>`;
      const ya = traitOf(p); if (ya !== null) s += `<text x="${cx + (m === 1 ? 12 : 9)}" y="${cy - (m === 1 ? 8 : 6)}" font-size="8" fill="var(--muted)">${ya}</text>`; }); }
  return s + '</svg>';
}
function drawChart() {
  const W = 800, Hh = 150, pad = 28, maxH = Math.max(C.death_at, C.source_cap * FOOD.length, people.length, 1); const xs = k => pad + (W - pad - 8) * (n ? k / n : 0), ys = val => Hh - 18 - (Hh - 30) * val / maxH;
  let s = `<svg class="chart" viewBox="0 0 ${W} ${Hh}" xmlns="http://www.w3.org/2000/svg">`;
  for (const [lvl, name] of [[C.hungry_at, 'hungry'], [C.emergency_at, 'emergency'], [C.death_at, 'dead']]) s += `<line x1="${pad}" x2="${W-8}" y1="${ys(lvl)}" y2="${ys(lvl)}" stroke="${colour(name)}" stroke-dasharray="2 4" stroke-opacity="0.6"/><text x="${W-6}" y="${ys(lvl)+4}" font-size="9" fill="var(--muted)" text-anchor="end">${name} ${lvl}</text>`;
  for (const p of people) { let d = '', pen = false; series.hunger[p].forEach((h, k) => { if (h === null) { pen = false; return; } d += (pen ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(h).toFixed(1); pen = true; }); s += `<path d="${d}" fill="none" stroke="var(--fg)" stroke-opacity="0.35" stroke-width="1"/>`; }
  let d = ''; series.stock.forEach((st, k) => { d += (k ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(st).toFixed(1); }); s += `<path d="${d}" fill="none" stroke="var(--source)" stroke-width="2"/>`;
  d = ''; series.crowd.forEach((c, k) => { d += (k ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(c).toFixed(1); }); s += `<path d="${d}" fill="none" stroke="var(--yield)" stroke-width="2" stroke-dasharray="4 3"/>`;
  for (const k of totals.yieldTicks) s += `<circle cx="${xs(k)}" cy="${ys(series.crowd[k])}" r="3" fill="var(--yield)"/>`;
  for (const [p, t] of totals.deaths) s += `<line x1="${xs(t)}" x2="${xs(t)}" y1="8" y2="${Hh-18}" stroke="var(--dead)" stroke-dasharray="3 3"/><text x="${xs(t)+2}" y="14" font-size="9" fill="var(--dead)">${p} dies</text>`;
  s += `<line id="cursor" x1="${xs(v)}" x2="${xs(v)}" y1="4" y2="${Hh-18}" stroke="var(--fg)"/>`;
  s += `<text x="${pad}" y="${Hh-4}" font-size="10" fill="var(--muted)">view 0</text><text x="${W-8}" y="${Hh-4}" font-size="10" fill="var(--muted)" text-anchor="end">view ${n}</text>`;
  return s + '</svg>';
}
function show(k) {
  if (C.water !== 'on') document.querySelectorAll('.water-col').forEach(e => e.remove());
  if (C.warmth !== 'on') document.querySelectorAll('.warmth-col').forEach(e => e.remove());
  v = Math.max(0, Math.min(n, k)); $('slider').value = v; $('tick').textContent = `view ${v} / ${n}`; $('map').innerHTML = drawMap(v);
  markEvents(v);
  const w = world(v), t = v >= 1 ? ticks[v - 1] : null; let alive = 0; let rows = '';
  for (const p of people) { const dead = p in w.died_at; if (!dead) alive++; const b = band(w.hunger[p], dead); const d = t && t.decisions[p]; const o = t && outcomeOf(t, p);
    const ob = t && t.observations && t.observations[p];
    let sees = '';
    if (ob) { const names = ob.sees ? ob.sees.slice() : (ob.others || []).map(x => x.id);
      if (ob.seen_stock) { for (const [id, st] of Object.entries(ob.seen_stock)) names.push(id + '=' + st); }
      else if (Object.prototype.hasOwnProperty.call(ob, 'source_food')) names.push('S');
      sees = names.join(', '); }
    const ya = traitOf(p);
    const kindCell = d ? (d.kind === 'yield' ? `<span style="color:var(--yield)">&#9675; yield</span>` : esc(d.kind) + (d.amount ? ' ' + d.amount : '') + (d.target ? ' \u2192 ' + esc(d.target) : '')) + ' <span class="meta">' + esc(d.reason) + '</span>' : '';
    rows += `<tr><td>${p}</td><td class="num">${ya === null ? '' : ya}</td><td class="mono">${w.positions[p].join(',')}</td><td class="num b-${b}">${w.hunger[p]}</td>${C.water === 'on' ? '<td class="num">' + w.thirst[p] + '</td>' : ''}${C.warmth === 'on' ? '<td class="num">' + w.cold[p] + (w.positions[p].join(',') === w.homes[p].join(',') ? ' ⌂' : '') + '</td>' : ''}<td class="b-${b}">${dead ? 'dead (t' + w.died_at[p] + ')' : b}</td><td class="num">${food(v, p)}</td>${C.water === 'on' ? '<td class="num">' + waterHeld(v, p) + '</td>' : ''}`
          + `<td class="mono">${esc(sees)}</td>`
          + `<td>${kindCell}</td>`
          + `<td>${o ? `<span class="${o.accepted ? 'ok' : 'no'}">${esc(o.reason)}</span>` : ''}</td></tr>`; }
  $('people').innerHTML = rows;
  $('selection').textContent = RUN.details[v].selection;
  $('settlement').textContent = RUN.details[v].settlement;
  const prod = t && t.production ? t.production.map(e => `+${e.amount} ${e.source}`).join(', ') : '';
  $('summary').innerHTML = `<span>alive <b>${alive}</b>/${people.length}</span>${FOOD.length === 1 ? `<span>source stock <b>${stock(v)}</b>/${C.source_cap}</span>` : FOOD.map(f => `<span>${esc(f.id)} <b>${stockOf(v, f.id)}</b>/${C.source_cap}</span>`).join('')}${WELLS.map(wl => `<span>${esc(wl.id)} <b>${stockOf(v, wl.id)}</b>/${C.water_cap}</span>`).join('')}<span>consumed <b>${v ? t.state.consumed : H.genesis.consumed}</b></span>${WELLS.length ? `<span>drunk <b>${v ? t.state.consumed_by.water : H.genesis.consumed_by.water}</b></span>` : ''}<span>renewal this tick <b>${prod || 'none'}</b></span>`;
  const cur = document.getElementById('cursor'); if (cur) { const x = 28 + (800 - 36) * (n ? v / n : 0); cur.setAttribute('x1', x); cur.setAttribute('x2', x); }
  $('timing').textContent = t && RUN.timings[String(t.tick)] !== undefined ? `tick ${t.tick} cost ${(RUN.timings[String(t.tick)] / 1e6).toFixed(3)} ms` : '';
}
function play() { if (timer) { clearInterval(timer); timer = null; $('play').textContent = 'play'; return; } $('play').textContent = 'pause'; timer = setInterval(() => { if (v >= n) { play(); return; } show(v + 1); }, 120); }
$('slider').max = n; $('slider').addEventListener('input', e => show(Number(e.target.value)));
$('play').addEventListener('click', play); $('prev').addEventListener('click', () => show(v - 1)); $('next').addEventListener('click', () => show(v + 1));
$('trails').addEventListener('change', e => { trails = e.target.checked; show(v); });
for (const name of ['scored', 'crossover', 'contested']) {
  const views = RUN.checkpoints[name];
  $(name).disabled = !views.length;
  $(name).title = views.length ? 'views ' + views.join(', ') : 'absent from this saved run';
  $(name).addEventListener('click', () => show(views.find(k => k > v) || views[0]));
}
document.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') show(v - 1); else if (e.key === 'ArrowRight') show(v + 1); else if (e.key === ' ') { e.preventDefault(); play(); } else if (e.key === 'Home') show(0); else if (e.key === 'End') show(n); });
renderEvents();
$('chart').innerHTML = drawChart();
$('totals').innerHTML = `<span>whole run:</span><span>claims accepted <b>${totals.claimsOk}</b></span><span>claims denied <b>${totals.claimsNo}</b></span><span>units eaten <b>${totals.eats}</b></span><span>yield events <b>${totals.yields}</b></span><span>emergency person-ticks <b>${totals.emergencyTicks}</b>${traitKeys.length ? ' (by yield_at ' + fmtBy(totals.emergencyBy) + ')' : ''}</span><span>person-ticks with another in view <b>${totals.sawOther}</b></span><span>person-ticks with source in view <b>${totals.sawSource}</b></span><span>deaths <b>${totals.deaths.length}</b>${totals.deaths.length ? ' (' + totals.deaths.map(d => d[0] + ' t' + d[1]).join(', ') + ')' : ''}${traitKeys.length ? '; by yield_at ' + fmtBy(totals.deathsBy) : ''}</span>`;
show(0);
"""


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
    return cfg.get("food_sources") or [{"id": cfg["source"], "position": cfg["source_position"]}]


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
    food_at = {entry["id"]: entry["position"] for entry in _food_sources(cfg)}
    selection = [f"Tick {tick['tick']} — personal selection from tick-start inputs"]
    for actor, d in sorted(tick.get("decisions", {}).items()):
        ob = tick.get("observations", {}).get(actor, {})
        aimed = food_at.get(d.get("target"), cfg["source_position"])
        crowd = sum(position == aimed for position in _seen_positions(ob, prior))
        scores = d.get("scores")
        pairs = "; ".join(f"{action} {tuple(scores[action])}" if scores is not None and action in scores
                          else f"{action} (score not recorded)" for action in d["candidates"])
        selection.append(
            f"{actor}: tick-start at {tuple(prior['positions'][actor])}, hunger {prior['hunger'][actor]}, "
            + (f"thirst {prior['thirst'][actor]}, " if "thirst" in prior else "")
            + (f"cold {prior['cold'][actor]}, " if "cold" in prior else "")
            + f"yield_at {prior.get('yield_at', {}).get(actor, 'not recorded')}, "
            f"seen crowd {crowd}, seen source stock {ob.get('source_food', 'not observed')}"
            + (f", seen stocks {ob['seen_stock']}" if "seen_stock" in ob else "")
            + f"; eligible: {pairs}; selected {d['kind']}"
            + (f" -> {d['target']}" if "target" in d else "")
        )
    settlement = [f"Tick {tick['tick']} — kernel settlement (personal scores confer no priority)",
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
<details><summary>Scoring: {html.escape(str(scenario.get('scoring', 'off (legacy file)')))} — recorded model declarations</summary>
<pre class="native mono">{html.escape(json.dumps({k: v for k, v in scenario.items() if k.startswith('scoring') or k == 'food_allocation'}, indent=2))}</pre></details>
<details class="rules"><summary class="meta">How these people decide &mdash; the rules they all follow</summary>
<div class="meta">movement: {html.escape(str(scenario.get('movement', '')))}<br>decision: {html.escape(str(scenario.get('decision', '')))}<br>perception: {html.escape(str(scenario.get('distance_metric', '')))} radius {html.escape(str(scenario.get('perception_radius', '')))} ({html.escape(str(scenario.get('perception_boundary', '')))}) {html.escape(str(scenario.get('perception', '')))}<br>yield: {html.escape(str(scenario.get('yield', '')))} set {html.escape(str(scenario.get('yield_set', '')))} · {html.escape(str(scenario.get('dead_are_not_seen', '')))}</div></details>
{f'<ul>{problems}</ul>' if problems else ''}
<div class="controls">
  <button id="prev">&#8592;</button><button id="play">play</button><button id="next">&#8594;</button>
  <input id="slider" type="range" min="0" max="0" value="0"><span id="tick" class="tick"></span>
  <label class="toggle"><input id="trails" type="checkbox" checked> trails (last 12 views)</label>
  <span id="timing" class="meta"></span>
  <button id="scored">Next GO/YIELD scored choice</button>
  <button id="crossover">Next GO over eligible YIELD</button>
  <button id="contested">Next contested food claim</button>
</div>
<div class="stats" id="summary"></div>
<div class="grid">
  <div class="panel"><h2>Map</h2><div id="map"></div>
    <div class="legend"><span><b class="b-fed">&#9679;</b> fed</span><span><b class="b-hungry">&#9679;</b> hungry</span><span><b class="b-emergency">&#9679;</b> emergency</span><span><b class="b-dead">&#215;</b> dead</span><span style="color:var(--source)">&#9632; source (stock)</span>{'<span style="color:var(--water)">&#9632; water (stock)</span>' if scenario.get('water') == 'on' else ''}<span style="color:var(--yield)">&#9675; yield</span><span>dashed square: home</span><span>faint square: Chebyshev perception</span>{'<span style="color:var(--roughline)">rough ground (an extra tick to cross)</span><span style="color:var(--shelterline)">shelter spot (needs rise slower)</span>' if scenario.get('terrain') == 'on' else ''}{'<span style="color:var(--builtline)">&#9650; a shelter somebody built</span>' if scenario.get('building') == 'on' else ''}<span>small number: yield_at</span>{'<span>&#8962; in the cold column: sheltered at home this tick</span>' if scenario.get('warmth') == 'on' else ''}</div></div>
  <div class="panel"><h2>What happened</h2><div id="events"></div>
    <p class="meta">Every death, every time someone stood back from a crowded source, every time a need turned
    critical, and every time a source ran out. Click a line to jump to that tick.</p></div>
  <div class="panel"><h2>People after this tick</h2>
    <table><thead><tr><th>person</th><th class="num">yield_at</th><th>at</th><th class="num">hunger</th><th class="num water-col">thirst</th><th class="num warmth-col">cold</th><th>state</th><th class="num">food</th><th class="num water-col">water</th><th>sees (tick before)</th><th>decided (tick before)</th><th>kernel outcome</th></tr></thead><tbody id="people"></tbody></table>
    <p class="meta">Decision, observation and outcome are those of the tick that produced this view. Food is the kernel's free balance. Hunger is the world's value after the tick. Sees lists other people (and S for the source) inside the perception radius at tick start.{' Cold is the warmth need: it rises away from home and falls at home, the shelter each person has.' if scenario.get('warmth') == 'on' else ''} yield_at is the person's own crowd-yield trait.</p></div>
</div>
<div class="panel" style="margin-top:12px"><h2>Personal selection — tick-start inputs and recorded scores</h2><pre id="selection" class="native mono"></pre></div>
<div class="panel" style="margin-top:12px"><h2>Resource settlement — recorded kernel order and effects</h2><pre id="settlement" class="native mono"></pre></div>
<div class="panel" style="margin-top:12px"><h2>Over time: hunger per person (grey), food stock in all food sources (blue), crowd on source (purple dashed), yield events (dots), deaths</h2><div id="chart"></div><div class="stats" id="totals" style="margin-top:8px"></div></div>
<p class="meta">Emergency person-ticks count living people at tick start. Everything here is read straight from the saved run: the page never recalculates what the world decided.</p>
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
    def stock_of(source_id: str) -> int:
        if view == 0:
            return run.header["genesis"]["sources"][source_id]["stock"]
        tick_line = run.ticks[view - 1]
        return tick_line["state"]["sources"][source_id]["stock"] + sum(
            e["amount"] for e in tick_line.get("production", []) if e["source"] == source_id)
    stock = stock_of(cfg["source"])
    grid = [["." for _ in range(cfg["width"])] for _ in range(cfg["height"])]
    sx, sy = cfg["source_position"]
    extra = []
    for mark, entries in (("S", _food_sources(cfg)), ("W", _water_sources(cfg))):
        for entry in entries:
            x, y = entry["position"]
            grid[y][x] = mark
            if entry["id"] != cfg["source"]:
                extra.append(f"; {entry['id']} {mark} at ({x}, {y}) stock {stock_of(entry['id'])}")
    for actor in sorted(world["positions"]):
        x, y = world["positions"][actor]
        mark = "x" if actor in world["died_at"] else actor[-1]
        grid[y][x] = mark if grid[y][x] in ".SW" else "+"
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
                run.header["world"]["homes"][actor]) else "") if "cold" in world else "")
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
