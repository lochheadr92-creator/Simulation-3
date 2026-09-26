"""Render a run file as a self-contained HTML page or as text.

    py -3 -B -m stream.viewer runs/<run>.jsonl            # writes runs/<run>.html
    py -3 -B -m stream.viewer runs/<run>.jsonl --text 12  # print tick 12

The page embeds the run's records and reads nothing else: no network, no
scripts from elsewhere, no live engine. Every number shown is a value the
engine committed (balances, stocks, reservations, outcomes, its own
availability map) or a count of those values. It is a way to look, not a
second scorer.
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
:root { --bg:#f7f7f4; --fg:#1d1d1b; --muted:#6b6b66; --line:#d9d9d2; --panel:#ffffff;
        --ok:#2f7d4f; --okbg:#e3f3e8; --no:#a63d2f; --nobg:#f8e6e2; --hold:#8a5a00; --holdbg:#fbefd6; --acc:#2f5f9f; }
@media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#ecece6; --muted:#9a9a92; --line:#33332f; --panel:#1f1f1c;
        --ok:#7fd39a; --okbg:#1f3427; --no:#f09a8a; --nobg:#3a221e; --hold:#e2b25a; --holdbg:#3a2f18; --acc:#8ab4f0; } }
* { box-sizing:border-box; } body { margin:0; padding:16px; background:var(--bg); color:var(--fg);
  font:14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { font-size:18px; margin:0 0 4px; } h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:18px 0 6px; }
.meta { color:var(--muted); font-size:12px; word-break:break-all; }
.controls { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:12px 0; position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:2; }
.controls input[type=range] { flex:1 1 240px; } button { font:inherit; padding:4px 10px; border:1px solid var(--line); background:var(--panel); color:var(--fg); border-radius:6px; cursor:pointer; }
.tick { font-variant-numeric:tabular-nums; font-weight:600; min-width:9ch; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:12px; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 12px; overflow:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; } th, td { text-align:left; padding:3px 14px 3px 0; border-bottom:1px solid var(--line); vertical-align:top; white-space:nowrap; }
th { color:var(--muted); font-weight:500; font-size:12px; } td.num, th.num { text-align:right; padding-right:14px; }
.ok { color:var(--ok); background:var(--okbg); border-radius:4px; padding:0 5px; } .no { color:var(--no); background:var(--nobg); border-radius:4px; padding:0 5px; }
.hold { color:var(--hold); background:var(--holdbg); border-radius:4px; padding:0 5px; } .mono { font-family:ui-monospace, Consolas, monospace; font-size:12px; }
svg { width:100%; height:120px; display:block; } .problem { color:var(--no); }
.legend { font-size:12px; color:var(--muted); } .legend span { display:inline-block; margin-right:12px; }
"""

JS = r"""
const RUN = JSON.parse(document.getElementById('run-data').textContent);
const ticks = RUN.ticks, n = ticks.length;
let i = 0, timer = null;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const short = s => s && s.length > 20 ? s.slice(0, 14) + '…' : (s || '');
function heldBy(state) {
  const held = {};
  for (const r of Object.values(state.reservations || {})) for (const e of r.effects) if (e.delta < 0) held[e.account] = (held[e.account] || 0) - e.delta;
  return held;
}
function view(k) {  // k = 0 shows genesis; k >= 1 shows the state after tick ticks[k-1]
  if (k === 0) { const g = RUN.header.genesis; const held = heldBy(g); const avail = {};
    for (const [a, b] of Object.entries(g.balances)) avail['actor:' + a] = b - (held['actor:' + a] || 0);
    for (const [s, src] of Object.entries(g.sources)) avail['source:' + s] = src.stock - (held['source:' + s] || 0);
    return { label: 'genesis (before tick ' + g.tick + ')', state: g, avail, record: null, timing: null }; }
  const t = ticks[k - 1];
  return { label: 'after tick ' + t.tick, state: t.state, avail: t.availability, record: t.record, timing: RUN.timings[t.tick] };
}
function render() {
  const v = view(i); const s = v.state; const held = heldBy(s);
  $('tick-label').textContent = v.label; $('slider').value = i;
  let rows = '';
  for (const [a, b] of Object.entries(s.balances)) { const h = held['actor:' + a] || 0; rows += `<tr><td>${esc(a)}</td><td class=num>${b}</td><td class=num>${v.avail['actor:' + a]}</td><td class=num>${h ? `<span class=hold>${h}</span>` : '0'}</td></tr>`; }
  $('actors').innerHTML = `<tr><th>actor</th><th class=num>balance</th><th class=num>free</th><th class=num>held</th></tr>${rows}`;
  rows = '';
  for (const [name, src] of Object.entries(s.sources)) { const h = held['source:' + name] || 0; rows += `<tr><td>${esc(name)}</td><td class=num>${src.stock}</td><td class=num>${v.avail['source:' + name]}</td><td class=num>${h ? `<span class=hold>${h}</span>` : '0'}</td><td class=mono>${esc(src.authorised.join(' '))}</td></tr>`; }
  $('sources').innerHTML = `<tr><th>source</th><th class=num>stock</th><th class=num>free</th><th class=num>held</th><th>authorised</th></tr>${rows}`;
  $('consumed').textContent = s.consumed; $('total').textContent = Object.values(s.balances).reduce((x, y) => x + y, 0) + Object.values(s.sources).reduce((x, y) => x + y.stock, 0) + s.consumed;
  rows = '';
  for (const r of Object.values(s.reservations || {})) rows += `<tr><td class=mono title="${esc(r.action_id)}">${esc(short(r.action_id))}</td><td>${esc(r.actor)}</td><td>${esc(r.operation)}</td><td class=num>${r.created_tick}</td><td class=mono>${r.effects.map(e => `${esc(e.account)} ${e.delta > 0 ? '+' : ''}${e.delta}`).join('<br>')}</td></tr>`;
  $('reservations').innerHTML = rows ? `<tr><th>action</th><th>owner</th><th>plan</th><th class=num>since</th><th>effects</th></tr>${rows}` : '<tr><td class=meta>no open reservations</td></tr>';
  rows = '';
  if (v.record) for (const o of v.record.outcomes) rows += `<tr><td class=mono>${esc(o.proposal_id)}</td><td>${esc(o.actor)}</td><td class=num>${o.sequence}</td><td>${esc(o.operation)}</td><td><span class="${o.accepted ? 'ok' : 'no'}">${esc(o.reason)}</span></td><td class=mono>${o.effects.map(e => `${esc(e.account)} ${e.delta > 0 ? '+' : ''}${e.delta}`).join('<br>')}${o.action_id ? `<br><span title="${esc(o.action_id)}">→ ${esc(short(o.action_id))}</span>` : ''}</td></tr>`;
  $('outcomes').innerHTML = v.record ? (rows ? `<tr><th>proposal</th><th>actor</th><th class=num>seq</th><th>op</th><th>reason</th><th>effects</th></tr>${rows}` : '<tr><td class=meta>no proposals this tick</td></tr>') : '<tr><td class=meta>genesis has no record</td></tr>';
  $('record-meta').textContent = v.record ? `rotated roster ${v.record.rotated_roster.join(' ')} · record ${v.record.next_state_digest.slice(0, 12)}… · tick cost ${v.timing == null ? 'n/a' : (v.timing / 1e6).toFixed(3) + ' ms'}` : '';
  $('cursor').setAttribute('x', (i / Math.max(n, 1)) * 100 + '%');
}
function go(k) { i = Math.max(0, Math.min(n, k)); render(); }
$('slider').max = n; $('slider').oninput = e => go(+e.target.value);
$('prev').onclick = () => go(i - 1); $('next').onclick = () => go(i + 1); $('first').onclick = () => go(0); $('last').onclick = () => go(n);
$('play').onclick = () => { if (timer) { clearInterval(timer); timer = null; $('play').textContent = 'play'; } else { $('play').textContent = 'pause'; timer = setInterval(() => { if (i >= n) { clearInterval(timer); timer = null; $('play').textContent = 'play'; } else go(i + 1); }, 250); } };
document.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') go(i - 1); if (e.key === 'ArrowRight') go(i + 1); });
$('timeline').onclick = e => { const r = e.currentTarget.getBoundingClientRect(); go(Math.round((e.clientX - r.left) / r.width * n)); };
(function timeline() {
  const W = 1000, H = 120, maxBar = Math.max(1, ...ticks.map(t => t.record.outcomes.length));
  const maxC = Math.max(1, ...ticks.map(t => t.state.consumed));
  let bars = '', line = '';
  ticks.forEach((t, k) => { const x = (k / n) * W, w = Math.max(1, W / n - 0.5);
    const acc = t.record.outcomes.filter(o => o.accepted).length, den = t.record.outcomes.length - acc;
    const ha = acc / maxBar * (H - 20), hd = den / maxBar * (H - 20);
    bars += `<rect x="${x}" y="${H - ha}" width="${w}" height="${ha}" fill="var(--ok)"/><rect x="${x}" y="${H - ha - hd}" width="${w}" height="${hd}" fill="var(--no)" opacity=".7"/>`;
    line += `${k ? 'L' : 'M'}${x + w / 2},${H - t.state.consumed / maxC * (H - 20)} `; });
  $('timeline').innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${bars}<path d="${line}" fill="none" stroke="var(--acc)" stroke-width="2"/><rect id="cursor" x="0" y="0" width="2" height="${H}" fill="var(--fg)"/></svg>`;
})();
render();
"""


def render_html(run: Run) -> str:
    header = run.header
    scenario = header.get("scenario") or {}
    problems = "".join(f"<li class=problem>{html.escape(p)}</li>" for p in run.problems)
    data = json.dumps({"header": header, "ticks": list(run.ticks), "timings": {str(k): v for k, v in run.timings.items()}},
                      separators=(",", ":")).replace("<", "\\u003c")
    status = "verifies" if run.complete else "DOES NOT VERIFY"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(run.run_id or 'run')} · V3 checkpoint</title><style>{CSS}</style></head>
<body>
<h1>{html.escape(run.run_id or run.path.name)}</h1>
<div class="meta">engine {html.escape(str(header.get('engine_version')))} · schema {html.escape(str(header.get('schema_version')))} ·
scenario {html.escape(str(scenario.get('version')))} seed {html.escape(str(scenario.get('seed')))} · {len(run.ticks)} ticks · file {status} ·
trail {html.escape(run.trail_digest[:16])}… · genesis {html.escape(str(header.get('genesis_digest', ''))[:16])}…</div>
<div class="meta">Rendered from the saved run file alone. Every number here was recorded by the run.</div>
{f'<ul>{problems}</ul>' if problems else ''}
<div class="controls">
<button id="first">⏮</button><button id="prev">◀</button><button id="play">play</button><button id="next">▶</button><button id="last">⏭</button>
<input id="slider" type="range" min="0" max="0" value="0"><span class="tick" id="tick-label"></span></div>
<div id="timeline" class="panel" style="padding:4px"></div>
<div class="legend"><span><span class="ok">accepted</span> per tick</span><span><span class="no">denied</span> per tick</span><span>line: consumed total</span><span>click or use ← → to move</span></div>
<div class="grid">
<div class="panel"><h2>Actors</h2><table id="actors"></table></div>
<div class="panel"><h2>Sources</h2><table id="sources"></table><div class="meta" style="margin-top:6px">consumed <b id="consumed"></b> · conserved total <b id="total"></b></div></div>
<div class="panel" style="grid-column:1/-1"><h2>Open reservations</h2><table id="reservations"></table></div>
<div class="panel" style="grid-column:1/-1"><h2>Tick record</h2><div class="meta" id="record-meta"></div><table id="outcomes"></table></div>
</div>
<script id="run-data" type="application/json">{data}</script>
<script>{JS}</script>
</body></html>
"""


def render_text(run: Run, tick_index: int | None = None) -> str:
    """One tick as text (the last by default). Same values as the page."""
    if not run.ticks:
        return f"{run.run_id}: no ticks\n"
    entry = run.ticks[-1 if tick_index is None else tick_index]
    state, record = entry["state"], entry["record"]
    held: dict[str, int] = {}
    for reservation in (state.get("reservations") or {}).values():
        for effect in reservation["effects"]:
            if effect["delta"] < 0:
                held[effect["account"]] = held.get(effect["account"], 0) - effect["delta"]
    lines = [f"{run.run_id}  after tick {entry['tick']}  state {entry['state_digest'][:12]}…", "actors:"]
    for actor, balance in state["balances"].items():
        lines.append(f"  {actor:<8} balance {balance:>4}  free {entry['availability'].get('actor:' + actor, balance):>4}  held {held.get('actor:' + actor, 0):>4}")
    lines.append("sources:")
    for name, source in state["sources"].items():
        lines.append(f"  {name:<8} stock {source['stock']:>4}  free {entry['availability'].get('source:' + name, source['stock']):>4}  held {held.get('source:' + name, 0):>4}")
    lines.append(f"consumed {state['consumed']}")
    lines.append("reservations:" if state.get("reservations") else "reservations: none")
    for reservation in (state.get("reservations") or {}).values():
        effects = ", ".join(f"{e['account']} {e['delta']:+d}" for e in reservation["effects"])
        lines.append(f"  {reservation['action_id'][:20]}… {reservation['actor']} {reservation['operation']} since {reservation['created_tick']}: {effects}")
    lines.append("outcomes:" if record["outcomes"] else "outcomes: none")
    for outcome in record["outcomes"]:
        effects = ", ".join(f"{e['account']} {e['delta']:+d}" for e in outcome["effects"])
        lines.append(f"  {outcome['proposal_id']:<10} {outcome['actor']:<6} {outcome['operation']:<9} {outcome['reason']:<32} {effects}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a run file as HTML or text.")
    parser.add_argument("run", help="Path to a runs/<run>.jsonl file")
    parser.add_argument("-o", "--out", default=None, help="HTML output path (default: beside the run file)")
    parser.add_argument("--text", type=int, default=None, metavar="TICK_INDEX", help="Print one tick as text instead")
    args = parser.parse_args(argv)
    run = read_run(Path(args.run))
    if args.text is not None:
        sys.stdout.write(render_text(run, args.text))
        return 0 if run.complete else 1
    out = Path(args.out) if args.out else Path(args.run).with_suffix(".html")
    out.write_text(render_html(run), encoding="utf-8")
    sys.stdout.write(f"viewer: {out}\nfile_verifies: {'yes' if run.complete else 'no'}\n")
    for problem in run.problems:
        sys.stdout.write(f"problem: {problem}\n")
    return 0 if run.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
