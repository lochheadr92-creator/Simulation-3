/* Simulation 3 map viewer: a saved run drawn as an isometric diorama.
 *
 * world/viewer.py inlines this into the page. It reads two embedded blocks and
 * nothing else:
 *   run-data    the saved run: header and every tick line, as recorded
 *   view-index  what world/viewer_index.py read out of it once: events,
 *               request threads, counts per view
 * Every figure, marker, badge and line stands for a recorded value. Animation
 * only moves the picture between two recorded views; it never decides,
 * predicts or changes anything, and the page runs no world rules.
 *
 * View k is the world after k ticks (view 0 is genesis), shown with the
 * decisions and outcomes of the tick that produced it.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- data --
  const $ = id => document.getElementById(id);
  const RUN = JSON.parse($('run-data').textContent);
  const IDX = JSON.parse($('view-index').textContent);
  const H = RUN.header, C = H.scenario || {}, ticks = RUN.ticks; let n = ticks.length;
  const TICK0 = (window.LIVE || {}).base || 0;   // live mode: view 0 shows the world at this tick
  const GW = C.width || 12, GH = C.height || 12;
  const people = IDX.people;
  const PIDX = {}; people.forEach((p, i) => { PIDX[p] = i; });
  const FOOD = IDX.food || [], WELLS = IDX.water || [];
  const ROUGH = new Set((C.rough || []).map(c => c.join(',')));
  const SPOTS = new Set((C.shelter_spots || []).map(c => c.join(',')));
  const SOURCE_AT = new Map();
  FOOD.forEach(s => SOURCE_AT.set(s.position.join(','), { kind: 'food', id: s.id, position: s.position, fishing: !!s.fishing, store: !!s.store, resident: s.resident, cap: s.fishing ? C.fishing_rules.cap : s.store ? C.store_target : C.source_cap }));
  WELLS.forEach(s => SOURCE_AT.set(s.position.join(','), { kind: 'water', id: s.id, position: s.position, cap: C.water_cap }));
  (IDX.wood || []).forEach(s => SOURCE_AT.set(s.position.join(','), { kind: 'wood', id: s.id, position: s.position, yard: !!s.yard, cap: s.yard ? (C.yard_rules || {}).capacity : C.wood_rules.cap }));
  (IDX.stone || []).forEach(s => SOURCE_AT.set(s.position.join(','), { kind: 'stone', id: s.id, position: s.position, cap: (C.stone_rules || {}).stock }));
  const SOURCE_BY_ID = {}; SOURCE_AT.forEach(s => { SOURCE_BY_ID[s.id] = s; });
  const PHRASE = IDX.phrases || {}, LABEL = IDX.labels || {};
  const MOVES = new Set(IDX.moves || []);
  const BUILD_TICKS = C.build_ticks || 0;
  const EVENTS = IDX.events || [];
  const COUNTS = IDX.counts || {};
  const BORN = IDX.born || {}, DIED = IDX.died || {};
  const THREADS = IDX.threads || [];
  const ADULT_AT = IDX.adult_at || null;           // set only when the run records childhood
  const PARENT = IDX.parent || {};                 // child -> parent, as recorded at birth
  const SECOND_PARENT = IDX.second_parent || {};
  const parentsOf = p => [PARENT[p], SECOND_PARENT[p]].filter(Boolean);
  const CHILDREN = {};
  for (const kid in PARENT) for (const p of parentsOf(kid)) (CHILDREN[p] = CHILDREN[p] || []).push(kid);
  function ageOf(w, p) { const a = (w.age || {})[p]; return a === undefined ? null : a; }
  function isChild(w, p) { const a = ageOf(w, p); return ADULT_AT !== null && a !== null && a < ADULT_AT; }
  const media = q => (window.matchMedia ? window.matchMedia(q).matches : false);
  const REDUCED = media('(prefers-reduced-motion: reduce)');

  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, t) => a + (b - a) * t;

  // in live sample mode some ticks are gaps (null) until fetched; fall back to the nearest earlier held tick
  function held(k) { let i = k - 1; while (i >= 0 && ticks[i] === null) i--; return i >= 0 ? ticks[i] : null; }
  function world(k) { if (k <= 0) return H.world; const t = held(k); return t ? t.world : H.world; }
  function decisions(k) { if (k <= 0) return {}; const t = ticks[k - 1]; return t ? (t.decisions || {}) : {}; }
  function observations(k) { if (k <= 0) return {}; const t = ticks[k - 1]; return t ? (t.observations || {}) : {}; }
  const OUTCOMES = new Array(n + 1);
  function outcomes(k) {
    if (k <= 0) return {};
    if (!OUTCOMES[k]) {
      const m = {};
      for (const o of (((ticks[k - 1] || {}).record || {}).outcomes || [])) if (!(o.actor in m)) m[o.actor] = o;
      OUTCOMES[k] = m;
    }
    return OUTCOMES[k];
  }
  function outcomeOf(k, p) { return outcomes(k)[p] || null; }
  const present = (w, p) => !!(w.positions && p in w.positions);
  const deadIn = (w, p) => !!(w.died_at && p in w.died_at);
  function food(k, p) {
    if (k === 0) return ((H.genesis || {}).balances || {})[p] || 0;
    const t = held(k) || {}; const a = (t.availability || {})['actor:' + p];
    const b = a === undefined ? ((t.state || {}).balances || {})[p] : a; return b === undefined ? 0 : b;
  }
  function waterHeld(k, p) {
    if (k === 0) return (((H.genesis || {}).holdings || {}).water || {})[p] || 0;
    const t = held(k) || {}; const a = (t.availability || {})['actor@water:' + p];
    const h = a === undefined ? ((((t.state || {}).holdings) || {}).water || {})[p] : a; return h === undefined ? 0 : h;
  }
  function stockOf(k, id) {
    try {
      if (k === 0) return H.genesis.sources[id].stock;
      const t = held(k);
      if ((t.production || []).some(e => e.source_created === id)) return 0;
      let s = t.state.sources[id].stock;
      for (const e of (t.production || [])) if (e.source === id) s += e.amount;
      return s;
    } catch (err) { return null; }
  }
  function woodHeld(k, p) {
    const state = k === 0 ? H.genesis : (held(k) || {}).state || H.genesis;
    return ((state.holdings || {}).wood || {})[p] || 0;
  }
  function stoneHeld(k, p) {
    const state = k === 0 ? H.genesis : (held(k) || {}).state || H.genesis;
    return ((state.holdings || {}).stone || {})[p] || 0;
  }
  const sourceLabel = s => s.fishing ? 'fishing spot' : s.store ? 'home cache' : s.kind === 'food' ? 'food source' : s.yard ? 'wood yard' : s.kind === 'wood' ? 'wood grove' : s.kind === 'stone' ? 'stone outcrop' : 'well';
  const sourceColor = s => s.fishing ? '#75ddd1' : s.kind === 'food' ? '#f2a65e' : s.yard ? '#d9b27c' : s.kind === 'wood' ? '#bc9967' : s.kind === 'stone' ? '#a9a5a0' : '#72c8ea';
  function drawStone(g, x, y, stock) {
    g.fillStyle = '#8d8983'; poly(g, [[x - 16, y], [x - 8, y - 14], [x + 4, y - 18], [x + 16, y - 6], [x + 12, y]]); g.fill();
    g.fillStyle = '#b5b1aa'; poly(g, [[x - 8, y - 14], [x + 4, y - 18], [x + 8, y - 8], [x - 4, y - 6]]); g.fill();
    g.fillStyle = '#e6e2dc';
    for (let j = 0; j < Math.min(stock || 0, 8); j++) { g.beginPath(); g.arc(x - 12 + j * 3.4, y + 4, 1.6, 0, Math.PI * 2); g.fill(); }
  }
  function drawYard(g, x, y, stock) {
    g.fillStyle = '#6b4b2a'; g.fillRect(x - 14, y - 4, 28, 4);
    g.fillStyle = '#c9a26b';
    for (let j = 0; j < Math.min(stock || 0, 6); j++) { g.beginPath(); g.arc(x - 10 + (j % 3) * 10, y - 8 - Math.floor(j / 3) * 7, 3.5, 0, Math.PI * 2); g.fill(); }
    if (!stock) { g.strokeStyle = '#c9a26b'; g.lineWidth = 1; g.strokeRect(x - 12, y - 14, 24, 10); }
  }
  function drawWood(g, x, y, stock) {
    g.fillStyle = '#896340'; g.fillRect(x - 3, y - 31, 6, 29);
    if (stock > 0) {
      g.fillStyle = '#4f7851';
      poly(g, [[x, y - 55], [x + 20, y - 18], [x - 20, y - 18]]); g.fill();
      g.fillStyle = '#71965e';
      poly(g, [[x, y - 55], [x, y - 18], [x - 20, y - 18]]); g.fill();
      g.fillStyle = '#bc9967';
      for (let i=0; i<Math.min(stock,4); i++) g.fillRect(x+7, y-3-i*3, 14, 2);
    }
  }
  function stockText(s, k) {
    const stock = stockOf(k, s.id);
    if (stock === null) return 'not created yet';
    return s.store ? `${stock} food; refill target ${s.cap}` : `${stock} of ${s.cap} units`;
  }
  const NEEDS = [{ key: 'hunger', label: 'Hunger', at: C.hungry_at, em: C.emergency_at, max: C.death_at, color: '#f2a65e', word: 'hungry' }];
  if (C.water === 'on') NEEDS.push({ key: 'thirst', label: 'Thirst', at: C.thirsty_at, em: C.thirst_emergency_at, max: C.thirst_death_at, color: '#72c8ea', word: 'thirsty' });
  if (C.warmth === 'on') NEEDS.push({ key: 'cold', label: 'Cold', at: C.cold_at, em: C.cold_emergency_at, max: C.cold_death_at, color: '#b9dcff', word: 'cold' });
  function needLevel(w, p, need) { const m = w[need.key]; return m && p in m ? m[p] : null; }
  function needState(w, p) {
    let worst = 'fine';
    for (const need of NEEDS) {
      const x = needLevel(w, p, need); if (x === null) continue;
      if (need.em !== undefined && x >= need.em) return 'emergency';
      if (need.at !== undefined && x >= need.at) worst = 'needy';
    }
    return worst;
  }
  function homeOf(w, p) { return (w.homes || {})[p] || (H.world.homes || {})[p] || null; }
  function ownerOfCell(key, k = v) {
    const w = world(k), residents = people.filter(p => present(w, p) && homeOf(w, p)?.join(',') === key);
    return residents.find(p => !deadIn(w, p)) || residents[0] || null;
  }

  // events: sorted by view, indexed once
  const EV_FIRST = new Int32Array(n + 2);
  { let i = 0; for (let k = 0; k <= n + 1; k++) { while (i < EVENTS.length && EVENTS[i].k < k) i++; EV_FIRST[k] = i; } }
  const EV_OF = {}, EV_AT_SRC = {};
  EVENTS.forEach((e, i) => {
    for (const p of [e.who, e.other]) if (p) (EV_OF[p] = EV_OF[p] || []).push(i);
    if (e.src) (EV_AT_SRC[e.src] = EV_AT_SRC[e.src] || []).push(i);
  });
  function eventsAt(k) { return k < 0 || k > n ? [] : EVENTS.slice(EV_FIRST[k], EV_FIRST[k + 1]); }

  // colours: one per person, distinct but quiet
  const COLOR = {}, DARK = {};
  people.forEach((p, i) => {
    const h = (i * 137.508 + 24) % 360;
    COLOR[p] = `hsl(${h.toFixed(1)}, 50%, 62%)`; DARK[p] = `hsl(${h.toFixed(1)}, 42%, 30%)`;
  });

  // -------------------------------------------------------- presentation --
  const LAYERS = {
    wood: true, stone: true,
    people: true, names: true, needs: true, food: true, water: true, homes: true, shelters: true,
    rough: true, spots: true, trails: true, perception: 'selected', links: true, deaths: true, stock: true, moments: true,
    family: true, memory: true,
  };
  let v = 0;                       // the view on screen
  let anim = { from: 0, to: 0, start: 0, dur: 0 };
  let playing = false, acc = 0, tps = 4;
  let selected = null;             // {type:'person', id} | {type:'place', id}
  let hovered = null;
  let follow = false, drift = false;
  let needsDraw = true;

  // ------------------------------------------------------------ geometry --
  const TW = 64, TH = 32, BASE = 16;
  const isoX = (gx, gy) => (gx - gy) * TW / 2;
  const isoY = (gx, gy) => (gx + gy) * TH / 2;
  function hash2(x, y, s) {
    let h = Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263) ^ Math.imul((s | 0) + 97, 2246822519);
    h = Math.imul(h ^ (h >>> 13), 3266489917); h ^= h >>> 16; return (h >>> 0) / 4294967296;
  }
  const SEED = (C.seed | 0) % 1000;
  function field(x, y) {
    return 0.5 + 0.28 * Math.sin(x * 0.63 + SEED * 0.37) * Math.cos(y * 0.51 - SEED * 0.21)
      + 0.22 * Math.sin((x + y) * 0.31 + SEED * 0.13);
  }
  const ELEV = new Float32Array(GW * GH);
  function computeElevation() {
    for (let y = 0; y < GH; y++) for (let x = 0; x < GW; x++) {
      const key = x + ',' + y;
      let e = 1.5 + 4 * field(x * 0.8, y * 0.8);
      if (SOURCE_AT.has(key)) e = Math.min(e, 2.5);
      else if (LAYERS.rough && ROUGH.has(key)) e += 5 + 2.5 * hash2(x, y, 1);
      else if (LAYERS.spots && SPOTS.has(key)) e += 1;
      ELEV[y * GW + x] = e;
    }
  }
  computeElevation();
  const elev = (x, y) => (x >= 0 && y >= 0 && x < GW && y < GH) ? ELEV[y * GW + x] : 0;
  const MAX_ELEV = 16;
  const BOUNDS = { x0: isoX(0, GH) - 8, x1: isoX(GW, 0) + 8, y0: -MAX_ELEV - 60, y1: isoY(GW, GH) + BASE + 8 };

  function rgb(hex) { const v2 = parseInt(hex.slice(1), 16); return [(v2 >> 16) & 255, (v2 >> 8) & 255, v2 & 255]; }
  function mix(a, b, t) { return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)]; }
  function css(c, f = 1, a = 1) { return `rgba(${Math.round(clamp(c[0] * f, 0, 255))},${Math.round(clamp(c[1] * f, 0, 255))},${Math.round(clamp(c[2] * f, 0, 255))},${a})`; }
  const SAND = rgb('#c9b07a'), MOSS = rgb('#77955a'), MOSS2 = rgb('#5f8450'), SLATE = rgb('#6d7682'), STONE = rgb('#a8a08a');
  const SOIL = rgb('#8a6844'), COBBLE = rgb('#9a958a'), EARTH = rgb('#5a4431'), EARTH2 = rgb('#46362a');

  function tileKind(x, y) {
    const key = x + ',' + y, s = SOURCE_AT.get(key);
    if (s && !s.store) return s.kind === 'water' ? 'cobble' : 'soil';
    if (LAYERS.rough && ROUGH.has(key)) return 'rough';
    if (LAYERS.spots && SPOTS.has(key)) return 'spot';
    return 'ground';
  }
  function tileColour(x, y, kind) {
    const j = 1 + (hash2(x, y, 7) - 0.5) * 0.10;
    if (kind === 'rough') return mix(SLATE, rgb('#5b636d'), hash2(x, y, 3)).map(c => c * j);
    if (kind === 'spot') return STONE.map(c => c * j);
    if (kind === 'soil') return SOIL;
    if (kind === 'cobble') return COBBLE;
    const m = clamp((field(x * 1.4 + 5, y * 1.2 - 3) - 0.38) * 2.4, 0, 1);
    return mix(SAND, mix(MOSS, MOSS2, hash2(x, y, 5)), m).map(c => c * j);
  }

  // ------------------------------------------------------------- terrain --
  function poly(g, pts) { g.beginPath(); g.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]); g.closePath(); }
  function ell(g, x, y, rx, ry) { g.beginPath(); g.ellipse(x, y, Math.max(0.01, rx), Math.max(0.01, ry), 0, 0, Math.PI * 2); }
  function corners(x, y, e) {
    return [[isoX(x, y), isoY(x, y) - e], [isoX(x + 1, y), isoY(x + 1, y) - e],
      [isoX(x + 1, y + 1), isoY(x + 1, y + 1) - e], [isoX(x, y + 1), isoY(x, y + 1) - e]];
  }
  function drawTile(g, x, y) {
    const e = elev(x, y), kind = tileKind(x, y), top = tileColour(x, y, kind);
    const [T, R, B, L] = corners(x, y, e), d = e + BASE;
    // sides: a thin band of the surface, then earth; interior sides are hidden by the tiles in front
    const band = kind === 'rough' ? 5 : 3;
    poly(g, [L, B, [B[0], B[1] + d], [L[0], L[1] + d]]); g.fillStyle = css(EARTH, 1.05); g.fill();
    poly(g, [B, R, [R[0], R[1] + d], [B[0], B[1] + d]]); g.fillStyle = css(EARTH2, 0.95); g.fill();
    poly(g, [L, B, [B[0], B[1] + band], [L[0], L[1] + band]]); g.fillStyle = css(top, 0.72); g.fill();
    poly(g, [B, R, [R[0], R[1] + band], [B[0], B[1] + band]]); g.fillStyle = css(top, 0.55); g.fill();
    if (x === GW - 1 || y === GH - 1) {           // strata on the diorama's front skirt
      g.strokeStyle = 'rgba(0,0,0,0.18)'; g.lineWidth = 0.8;
      for (const f of [0.45, 0.72]) {
        if (y === GH - 1) { g.beginPath(); g.moveTo(L[0], L[1] + d * f); g.lineTo(B[0], B[1] + d * f); g.stroke(); }
        if (x === GW - 1) { g.beginPath(); g.moveTo(B[0], B[1] + d * f); g.lineTo(R[0], R[1] + d * f); g.stroke(); }
      }
    }
    if (kind === 'rough') {
      // broken edge: the top is a jagged plate, a notch or two chipped out of it
      const pts = [];
      const edges = [[T, R], [R, B], [B, L], [L, T]];
      edges.forEach(([a, b], i) => {
        pts.push(a);
        for (const f of [0.33, 0.66]) {
          const cut = 1.5 + 3.5 * hash2(x * 4 + i, y * 4 + f * 10, 11);
          const mx = lerp(a[0], b[0], f), my = lerp(a[1], b[1], f);
          const cx = (T[0] + B[0]) / 2, cy = (T[1] + B[1]) / 2;
          const len = Math.hypot(cx - mx, cy - my) || 1;
          pts.push([mx + (cx - mx) / len * cut, my + (cy - my) / len * cut * 0.9]);
        }
      });
      poly(g, pts); g.fillStyle = css(top, 1); g.fill();
      g.strokeStyle = 'rgba(20,24,30,0.45)'; g.lineWidth = 0.9; g.stroke();
      // cracks
      g.strokeStyle = 'rgba(25,28,34,0.5)'; g.lineWidth = 0.8; g.beginPath();
      const cx = (T[0] + B[0]) / 2, cy = (T[1] + B[1]) / 2;
      g.moveTo(cx - 12 + 6 * hash2(x, y, 21), cy - 2); g.lineTo(cx - 2, cy + 1 + 2 * hash2(x, y, 22)); g.lineTo(cx + 9, cy - 3);
      g.moveTo(cx - 2, cy + 1); g.lineTo(cx + 1, cy + 7);
      g.stroke();
      // scree
      for (let i = 0; i < 3; i++) {
        const rx = cx + (hash2(x, y, 30 + i) - 0.5) * 30, ry = cy + (hash2(x, y, 40 + i) - 0.5) * 12;
        const s = 2.2 + 2.6 * hash2(x, y, 50 + i);
        poly(g, [[rx - s, ry], [rx - s * 0.4, ry - s * 0.9], [rx + s * 0.8, ry - s * 0.6], [rx + s, ry + s * 0.2], [rx, ry + s * 0.5]]);
        g.fillStyle = css(SLATE, 1.25 + 0.2 * hash2(x, y, 60 + i)); g.fill();
        g.strokeStyle = 'rgba(0,0,0,0.3)'; g.lineWidth = 0.6; g.stroke();
      }
      return;
    }
    poly(g, [T, R, B, L]); g.fillStyle = css(top, 1); g.fill();
    g.strokeStyle = 'rgba(0,0,0,0.10)'; g.lineWidth = 0.8; g.stroke();
    // top-left edge highlight
    g.strokeStyle = 'rgba(255,255,240,0.10)'; g.beginPath(); g.moveTo(L[0], L[1]); g.lineTo(T[0], T[1]); g.lineTo(R[0], R[1]); g.stroke();
    const cx = (T[0] + B[0]) / 2, cy = (T[1] + B[1]) / 2;
    if (kind === 'ground') {
      const mossy = tileColour(x, y, kind)[1] > 150 ? false : true;
      for (let i = 0; i < 6; i++) {
        const px = cx + (hash2(x, y, 70 + i) - 0.5) * 36, py = cy + (hash2(x, y, 80 + i) - 0.5) * 16;
        if (Math.abs(px - cx) / 32 + Math.abs(py - cy) / 16 > 0.85) continue;
        if (mossy && i % 2 === 0) {
          g.strokeStyle = 'rgba(40,70,35,0.55)'; g.lineWidth = 0.8; g.beginPath();
          g.moveTo(px - 1.6, py); g.lineTo(px - 0.6, py - 3); g.moveTo(px, py); g.lineTo(px + 0.2, py - 3.6); g.moveTo(px + 1.5, py); g.lineTo(px + 1.9, py - 2.6);
          g.stroke();
        } else {
          ell(g, px, py, 0.9 + hash2(x, y, 90 + i), 0.6); g.fillStyle = i % 3 ? 'rgba(60,45,25,0.28)' : 'rgba(255,245,220,0.22)'; g.fill();
        }
      }
    } else if (kind === 'spot') {
      // a flat hearthstone with a windbreak of two standing stones and a moss rim
      poly(g, [[cx, cy - 10], [cx + 20, cy], [cx, cy + 10], [cx - 20, cy]]);
      g.fillStyle = css(STONE, 1.12); g.fill(); g.strokeStyle = 'rgba(70,60,45,0.45)'; g.lineWidth = 0.8; g.stroke();
      g.strokeStyle = 'rgba(90,120,70,0.55)'; g.lineWidth = 1.6; g.beginPath(); g.moveTo(L[0] + 6, L[1]); g.lineTo(T[0], T[1] + 3); g.lineTo(R[0] - 6, R[1]); g.stroke();
      for (const [sx, sy, hgt] of [[cx - 13, cy - 5, 11], [cx + 11, cy - 6, 9]]) {
        poly(g, [[sx - 3.5, sy], [sx - 2.6, sy - hgt], [sx + 1.8, sy - hgt - 1.5], [sx + 3.4, sy - 0.5]]);
        g.fillStyle = css(STONE, 0.92); g.fill(); g.strokeStyle = 'rgba(40,35,28,0.5)'; g.lineWidth = 0.7; g.stroke();
        poly(g, [[sx + 1.8, sy - hgt - 1.5], [sx + 3.4, sy - 0.5], [sx + 5, sy - 1.5], [sx + 3.8, sy - hgt - 2.4]]);
        g.fillStyle = css(STONE, 0.7); g.fill();
      }
    } else if (kind === 'soil') {
      g.strokeStyle = 'rgba(50,34,20,0.45)'; g.lineWidth = 1;
      for (let i = -2; i <= 2; i++) { g.beginPath(); g.moveTo(cx - 16 + i * 7, cy - 4 + i * 3.5 + 8); g.lineTo(cx + 4 + i * 7, cy - 14 + i * 3.5 + 8 + 6); g.stroke(); }
    } else if (kind === 'cobble') {
      for (let i = 0; i < 9; i++) {
        const px = cx + (hash2(x, y, 100 + i) - 0.5) * 34, py = cy + (hash2(x, y, 110 + i) - 0.5) * 15;
        if (Math.abs(px - cx) / 32 + Math.abs(py - cy) / 16 > 0.82) continue;
        ell(g, px, py, 3.2, 1.7); g.fillStyle = css(COBBLE, 0.85 + 0.3 * hash2(x, y, 120 + i)); g.fill();
        g.strokeStyle = 'rgba(0,0,0,0.25)'; g.lineWidth = 0.5; g.stroke();
      }
    }
  }
  function drawTerrain(g) {
    for (let s = 0; s <= GW + GH - 2; s++) {
      for (let x = Math.max(0, s - GH + 1); x <= Math.min(GW - 1, s); x++) drawTile(g, x, s - x);
    }
  }
  let terrainCache = null, terrainScale = 0, terrainDirty = true;
  function terrainLayer(scale) {
    const bw = BOUNDS.x1 - BOUNDS.x0, bh = BOUNDS.y1 - BOUNDS.y0;
    const want = Math.min(scale, 4096 / Math.max(bw, bh));
    if (!terrainDirty && terrainCache && want <= terrainScale * 1.08 && want >= terrainScale / 1.35) return terrainCache;
    const c = terrainCache || document.createElement('canvas');
    c.width = Math.max(1, Math.ceil(bw * want)); c.height = Math.max(1, Math.ceil(bh * want));
    const g = c.getContext('2d');
    g.setTransform(want, 0, 0, want, -BOUNDS.x0 * want, -BOUNDS.y0 * want);
    g.clearRect(BOUNDS.x0, BOUNDS.y0, bw, bh);
    drawTerrain(g);
    terrainCache = c; terrainScale = want; terrainDirty = false;
    return c;
  }

  // --------------------------------------------------------------- stage --
  const stage = $('map'), canvas = $('world'), ctx = canvas.getContext('2d');
  let cw = 1, ch = 1, dpr = 1;
  const cam = { x: 0, y: 0, z: 1 };
  let userMoved = false;
  function resize() {
    const r = stage.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    cw = Math.max(1, r.width); ch = Math.max(1, r.height);
    canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
    if (!userMoved) fit(false);
    needsDraw = true;
  }
  function fitView() {
    const bw = BOUNDS.x1 - BOUNDS.x0, bh = BOUNDS.y1 - BOUNDS.y0 + 40;
    const top = cw < 640 ? 50 : 90, bottom = cw < 640 ? 20 : 40, side = cw < 640 ? 12 : 40;
    const z = clamp(Math.min((cw - side) / bw, (ch - top - bottom) / bh), 0.25, 6);
    return { x: (BOUNDS.x0 + BOUNDS.x1) / 2, y: (BOUNDS.y0 + BOUNDS.y1) / 2 - (top - bottom) / 2 / z + 10, z };
  }
  let camTarget = null;
  function fit(smooth) { const f = fitView(); if (smooth && !REDUCED) camTarget = f; else { Object.assign(cam, f); camTarget = null; } userMoved = false; needsDraw = true; }
  function toScreen(ix, iy) { return [(ix - cam.x - driftX) * cam.z + cw / 2, (iy - cam.y - driftY) * cam.z + ch / 2]; }
  function toIso(sx, sy) { return [(sx - cw / 2) / cam.z + cam.x + driftX, (sy - ch / 2) / cam.z + cam.y + driftY]; }
  function toGrid(ix, iy) { const a = ix / (TW / 2), b = iy / (TH / 2); return [(a + b) / 2, (b - a) / 2]; }
  function zoomAt(sx, sy, factor) {
    const [ix, iy] = toIso(sx, sy);
    cam.z = clamp(cam.z * factor, 0.25, 8);
    cam.x = ix - (sx - cw / 2) / cam.z - driftX; cam.y = iy - (sy - ch / 2) / cam.z - driftY;
    userMoved = true; camTarget = null; needsDraw = true;
  }
  function centreOn(ix, iy, z) {
    camTarget = { x: ix, y: iy, z: z || Math.max(cam.z, fitView().z * 1.6) };
    if (REDUCED) { Object.assign(cam, camTarget); camTarget = null; }
    userMoved = true; needsDraw = true;
  }
  let driftX = 0, driftY = 0;

  // -------------------------------------------------------- view helpers --
  function easeT(now) {
    if (anim.dur <= 0) return 1;
    const t = clamp((now - anim.start) / anim.dur, 0, 1);
    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  }
  const GROUPS = new Map();
  function groupsAt(k) {
    // living people sharing a cell stand in a small ring, in roster order
    if (GROUPS.has(k)) return GROUPS.get(k);
    const w = world(k), at = {}, off = {};
    for (const p of people) { if (!present(w, p) || deadIn(w, p)) continue; const key = w.positions[p].join(','); (at[key] = at[key] || []).push(p); }
    for (const key in at) {
      const list = at[key], m = list.length;
      list.forEach((p, i) => {
        if (m === 1) { off[p] = [0, 0]; return; }
        const ring = m <= 7 ? 0 : (i < 7 ? 0 : 1), idx = ring ? i - 7 : i, count = ring ? m - 7 : Math.min(m, 7);
        const a = (idx / count) * Math.PI * 2 + (ring ? 0.4 : 0.2), r = ring ? 0.36 : 0.13 + 0.03 * Math.min(count, 7);
        off[p] = [Math.cos(a) * r, Math.sin(a) * r];
      });
    }
    if (GROUPS.size > 6) GROUPS.delete(GROUPS.keys().next().value);
    GROUPS.set(k, off); return off;
  }
  const SHELTER_SETS = new Map();
  function sheltersAt(k) {
    if (!SHELTER_SETS.has(k)) { if (SHELTER_SETS.size > 6) SHELTER_SETS.delete(SHELTER_SETS.keys().next().value); SHELTER_SETS.set(k, new Set((world(k).shelters || []).map(c => c.join(',')))); }
    return SHELTER_SETS.get(k);
  }
  // where a person stands on screen this frame, in iso units (feet)
  function placeOf(p, t) {
    const wa = world(anim.from), wb = world(anim.to);
    const b = wb.positions && wb.positions[p]; if (!b) return null;
    const a = (wa.positions && wa.positions[p]) || b;
    const oa = (groupsAt(anim.from)[p]) || (groupsAt(anim.to)[p]) || [0, 0], ob = groupsAt(anim.to)[p] || oa;
    const u = anim.from === anim.to ? 1 : t;
    let gx = lerp(a[0], b[0], u) + 0.5 + lerp(oa[0], ob[0], u), gy = lerp(a[1], b[1], u) + 0.5 + lerp(oa[1], ob[1], u);
    const onShelter = sheltersAt(anim.to).has(b.join(',')) && LAYERS.shelters;
    if (onShelter && u >= 1) { gx += 0.2; gy += 0.2; }           // stand at the door, not inside the walls
    const e = lerp(elev(a[0], a[1]), elev(b[0], b[1]), u);
    return { gx, gy, x: isoX(gx, gy), y: isoY(gx, gy) - e, e };
  }
  function cellCentre(x, y) { return { x: isoX(x + 0.5, y + 0.5), y: isoY(x + 0.5, y + 0.5) - elev(x, y) }; }
  function roughMemory(w, p) {
    const cells = ((w.terrain_memory || {})[p]) || [];
    return cells.map(c => Array.isArray(c) ? c : null).filter(Boolean);
  }

  // ------------------------------------------------------------- drawing --
  function line(g, x1, y1, x2, y2) { g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke(); }
  function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function droplet(g, x, y, r) { g.beginPath(); g.moveTo(x, y - r * 1.6); g.bezierCurveTo(x + r * 1.1, y - r * 0.3, x + r, y + r, x, y + r); g.bezierCurveTo(x - r, y + r, x - r * 1.1, y - r * 0.3, x, y - r * 1.6); g.closePath(); }
  function flake(g, x, y, r) { g.beginPath(); for (let i = 0; i < 3; i++) { const a = i * Math.PI / 3; g.moveTo(x - Math.cos(a) * r, y - Math.sin(a) * r); g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); } }

  function drawBush(g, s, cx, cy, stock, condition) {
    const empty = !stock;
    const worn = condition !== undefined && condition < C.patch_rules.full_growth_at;
    const fullness = condition === undefined ? 1 : 0.55 + 0.45 * condition / C.patch_rules.condition_max;
    g.fillStyle = 'rgba(0,0,0,0.28)'; ell(g, cx + 2, cy + 1, 16, 7); g.fill();
    const shades = (condition === undefined ? empty : worn) ? ['#5a5a3c', '#6b6a45', '#7b7850'] : ['#2f5a33', '#3f7440', '#56904f'];
    const blobs = [[-8, -6, 8, 0], [7, -6, 8, 0], [0, -12, 9, 1], [-3, -3, 7, 1], [4, -2, 7, 2], [0, -17, 6, 2]];
    for (const [dx, dy, r, sh] of blobs) { g.beginPath(); g.arc(cx + dx, cy + dy, r * fullness, 0, Math.PI * 2); g.fillStyle = shades[sh]; g.fill(); }
    g.fillStyle = empty ? 'rgba(255,240,200,0.08)' : 'rgba(210,255,190,0.16)'; g.beginPath(); g.arc(cx - 3, cy - 16, 4, 0, Math.PI * 2); g.fill();
    if (empty) {
      g.strokeStyle = '#4a3a26'; g.lineWidth = 1.1;
      line(g, cx - 4, cy - 8, cx - 9, cy - 20); line(g, cx + 3, cy - 9, cx + 8, cy - 21); line(g, cx, cy - 10, cx + 1, cy - 24);
      return;
    }
    const shown = Math.min(stock, 18);
    for (let i = 0; i < shown; i++) {
      const a = hash2(i, 3, 17) * Math.PI * 2, r = 3 + 8 * hash2(i, 5, 19);
      const bx = cx + Math.cos(a) * r * 1.15, by = cy - 9 + Math.sin(a) * r * 0.75;
      g.beginPath(); g.arc(bx, by, 1.9, 0, Math.PI * 2); g.fillStyle = i % 3 === 2 ? '#f0a04a' : '#e2553e'; g.fill();
      g.fillStyle = 'rgba(255,255,255,0.55)'; g.beginPath(); g.arc(bx - 0.6, by - 0.6, 0.55, 0, Math.PI * 2); g.fill();
    }
  }
  function drawWell(g, s, cx, cy, stock, now) {
    const cap = Math.max(1, s.cap || 12), level = clamp((stock || 0) / cap, 0, 1);
    g.fillStyle = 'rgba(0,0,0,0.3)'; ell(g, cx + 2, cy + 2, 17, 8); g.fill();
    // stone drum
    g.fillStyle = '#6e6a61'; ell(g, cx, cy, 14, 7); g.fill();
    g.fillRect(cx - 14, cy - 6, 28, 6);
    g.fillStyle = '#9d988c'; ell(g, cx, cy - 6, 14, 7); g.fill();
    g.strokeStyle = 'rgba(0,0,0,0.3)'; g.lineWidth = 0.7;
    for (let i = -2; i <= 2; i++) line(g, cx + i * 5.5, cy - 1 + Math.abs(i) * 0.6 * -1 + 1, cx + i * 5.5, cy + 5 - Math.abs(i) * 1.2);
    // water
    const wet = [lerp(26, 70, level), lerp(52, 165, level), lerp(66, 205, level)];
    ell(g, cx, cy - 6, 10.5, 5); g.fillStyle = stock ? css(wet) : '#3a3026'; g.fill();
    if (stock) {
      const still = REDUCED;
      for (let i = 0; i < 2; i++) {
        const r = still ? 0.45 + i * 0.3 : ((now * 0.00045 + i * 0.5) % 1);
        g.strokeStyle = `rgba(220,245,255,${(0.55 * (1 - r)).toFixed(3)})`; g.lineWidth = 0.8;
        ell(g, cx, cy - 6, 1.5 + 8 * r, 0.7 + 3.8 * r); g.stroke();
      }
      g.fillStyle = 'rgba(255,255,255,0.25)'; ell(g, cx - 4, cy - 7.5, 3, 0.9); g.fill();
    } else {
      g.strokeStyle = 'rgba(20,14,8,0.6)'; g.lineWidth = 0.7;
      line(g, cx - 6, cy - 6, cx - 1, cy - 5); line(g, cx - 1, cy - 5, cx + 3, cy - 7); line(g, cx - 1, cy - 5, cx + 1, cy - 3);
    }
    // frame, rope and bucket
    g.strokeStyle = '#5b4330'; g.lineWidth = 1.8;
    line(g, cx - 12, cy - 8, cx - 11, cy - 27); line(g, cx + 12, cy - 8, cx + 11, cy - 27);
    g.lineWidth = 2; line(g, cx - 13, cy - 26, cx + 13, cy - 26);
    g.strokeStyle = '#d9c9a8'; g.lineWidth = 0.6; line(g, cx + 2, cy - 26, cx + 2, cy - 17);
    g.fillStyle = '#7a5a3a'; rrect(g, cx - 0.5, cy - 18, 5, 4, 1); g.fill();
  }
  function hutParts(cx, cy) {
    const hw = TW / 2 * 0.6, hh = TH / 2 * 0.6;
    return { T: [cx, cy - hh], R: [cx + hw, cy], B: [cx, cy + hh], L: [cx - hw, cy], hw, hh };
  }
  function facePoint(a, b, u, h) { return [lerp(a[0], b[0], u), lerp(a[1], b[1], u) - h]; }
  function drawHut(g, cx, cy, owner, occupied, ownerDead, now) {
    const { T, R, B, L } = hutParts(cx, cy), wall = 14, roof = 13;
    g.fillStyle = 'rgba(0,0,0,0.3)'; poly(g, [[T[0] + 6, T[1] + 3], [R[0] + 8, R[1] + 3], [B[0] + 4, B[1] + 3], [L[0] + 4, L[1] + 2]]); g.fill();
    const up = p => [p[0], p[1] - wall];
    poly(g, [L, B, up(B), up(L)]); g.fillStyle = '#a07a52'; g.fill();
    poly(g, [B, R, up(R), up(B)]); g.fillStyle = '#7c5b3b'; g.fill();
    g.strokeStyle = 'rgba(40,25,12,0.35)'; g.lineWidth = 0.6;
    for (let h = 3.5; h < wall; h += 3.5) { line(g, L[0], L[1] - h, B[0], B[1] - h); line(g, B[0], B[1] - h, R[0], R[1] - h); }
    // door on the front-left wall, window on the front-right
    poly(g, [facePoint(L, B, 0.38, 0), facePoint(L, B, 0.66, 0), facePoint(L, B, 0.66, 9), facePoint(L, B, 0.38, 9)]);
    g.fillStyle = '#2f2016'; g.fill();
    const lit = occupied && !ownerDead;
    poly(g, [facePoint(B, R, 0.36, 5), facePoint(B, R, 0.62, 5), facePoint(B, R, 0.62, 10), facePoint(B, R, 0.36, 10)]);
    g.fillStyle = lit ? '#ffd27a' : '#2a221c'; g.fill();
    if (lit) {
      const [wx, wy] = facePoint(B, R, 0.49, 7.5);
      const glow = g.createRadialGradient(wx, wy, 0, wx, wy, 16); glow.addColorStop(0, 'rgba(255,205,110,0.45)'); glow.addColorStop(1, 'rgba(255,205,110,0)');
      g.fillStyle = glow; g.beginPath(); g.arc(wx, wy, 16, 0, Math.PI * 2); g.fill();
    }
    // roof: four thatched slopes, eaves overhanging the walls
    const top = [cx, cy - wall - roof], k = 1.22, mid = [cx, cy - wall];
    const eave = p => [mid[0] + (p[0] - cx) * k, mid[1] + (p[1] - cy) * k + 1];
    const eT = eave(T), eR = eave(R), eB = eave(B), eL = eave(L);
    poly(g, [eT, eL, top]); g.fillStyle = '#b98d4f'; g.fill();
    poly(g, [eT, eR, top]); g.fillStyle = '#9c7440'; g.fill();
    poly(g, [eL, eB, top]); g.fillStyle = '#d6aa62'; g.fill();
    poly(g, [eB, eR, top]); g.fillStyle = '#ab8047'; g.fill();
    g.strokeStyle = 'rgba(60,38,14,0.45)'; g.lineWidth = 0.7;
    for (let i = 1; i < 4; i++) { const f = i / 4; line(g, lerp(eL[0], top[0], f), lerp(eL[1], top[1], f), lerp(eB[0], top[0], f), lerp(eB[1], top[1], f)); line(g, lerp(eB[0], top[0], f), lerp(eB[1], top[1], f), lerp(eR[0], top[0], f), lerp(eR[1], top[1], f)); }
    // chimney smoke while somebody is inside
    if (lit) {
      const sx = cx + 7, sy = cy - wall - 8;
      g.fillStyle = '#5b4a3c'; g.fillRect(sx - 2, sy - 5, 4, 6);
      for (let i = 0; i < 3; i++) {
        const t = REDUCED ? 0.3 + i * 0.25 : ((now * 0.00035 + i / 3) % 1);
        g.fillStyle = `rgba(215,225,225,${(0.38 * (1 - t)).toFixed(3)})`;
        g.beginPath(); g.arc(sx + Math.sin(t * 5 + i) * 2 + t * 5, sy - 7 - t * 20, 2 + t * 4, 0, Math.PI * 2); g.fill();
      }
    }
    // the owner's flag on a pole at the ridge
    if (owner) {
      const fx = top[0], fy = top[1];
      g.strokeStyle = '#3c2a1a'; g.lineWidth = 1; line(g, fx, fy, fx, fy - 11);
      const wave = REDUCED ? 0 : Math.sin(now * 0.004 + PIDX[owner]) * 1.5;
      g.beginPath(); g.moveTo(fx, fy - 11); g.quadraticCurveTo(fx + 4, fy - 12 + wave, fx + 8, fy - 10 + wave * 0.5); g.lineTo(fx, fy - 6.5); g.closePath();
      g.globalAlpha = ownerDead ? 0.4 : 1; g.fillStyle = COLOR[owner]; g.fill(); g.globalAlpha = 1;
    }
  }
  function drawSite(g, cx, cy, frac, abandoned) {
    const { T, R, B, L } = hutParts(cx, cy), wall = 14 * Math.max(0.25, frac);
    g.save(); if (abandoned) g.globalAlpha = 0.45;
    g.fillStyle = 'rgba(0,0,0,0.18)'; poly(g, [T, R, B, L]); g.fill();
    g.strokeStyle = '#b58f61'; g.lineWidth = 1.4;
    for (const p of [T, R, B, L]) line(g, p[0], p[1], p[0], p[1] - 14 * Math.max(0.45, frac));
    poly(g, [L, B, [B[0], B[1] - wall], [L[0], L[1] - wall]]); g.fillStyle = '#c9a473'; g.fill();
    poly(g, [B, R, [R[0], R[1] - wall], [B[0], B[1] - wall]]); g.fillStyle = '#a8845a'; g.fill();
    g.strokeStyle = 'rgba(70,45,20,0.45)'; g.lineWidth = 0.6;
    for (let h = 3.5; h < wall; h += 3.5) { line(g, L[0], L[1] - h, B[0], B[1] - h); line(g, B[0], B[1] - h, R[0], R[1] - h); }
    // a small pile of planks
    g.fillStyle = '#d8b988'; for (let i = 0; i < 3; i++) { rrect(g, R[0] - 2, R[1] + 2 - i * 1.6, 11, 1.8, 0.6); g.fill(); }
    g.restore();
  }
  function drawHomeMark(g, x, y, p, dead) {
    const { x: cx, y: cy } = cellCentre(x, y);
    g.save(); g.setLineDash([3, 2.5]); g.lineWidth = 1.2;
    g.strokeStyle = dead ? 'rgba(200,195,185,0.35)' : COLOR[p]; g.globalAlpha = dead ? 1 : 0.7;
    poly(g, [[cx, cy - 10.5], [cx + 21, cy], [cx, cy + 10.5], [cx - 21, cy]]); g.stroke();
    g.restore();
    g.fillStyle = dead ? 'rgba(200,195,185,0.4)' : COLOR[p]; g.globalAlpha = dead ? 1 : 0.85;
    g.fillRect(cx - 12.5, cy - 10, 1.6, 8); g.beginPath(); g.arc(cx - 11.7, cy - 10.5, 1.8, 0, Math.PI * 2); g.fill();
    g.globalAlpha = 1;
  }
  function drawStone(g, x, y, s) {
    g.fillStyle = 'rgba(0,0,0,0.3)'; ell(g, x + 1, y + 0.5, 4.5 * s, 2 * s); g.fill();
    g.beginPath(); g.moveTo(x - 3.2 * s, y); g.lineTo(x - 3.2 * s, y - 5 * s); g.quadraticCurveTo(x, y - 9 * s, x + 3.2 * s, y - 5 * s); g.lineTo(x + 3.2 * s, y); g.closePath();
    g.fillStyle = '#8f8a82'; g.fill(); g.strokeStyle = 'rgba(30,30,28,0.55)'; g.lineWidth = 0.6; g.stroke();
    g.fillStyle = 'rgba(255,255,255,0.18)'; g.fillRect(x - 2.4 * s, y - 5 * s, 1.1 * s, 4 * s);
  }

  function poseOf(d, moved, held) {
    const kind = d ? d.kind : null;
    if (!kind) return 'idle';
    if (held) return 'held';
    if (MOVES.has(kind) && moved) return 'walk';
    if (MOVES.has(kind)) return kind === 'ask' ? 'ask' : 'idle';
    return { fish: 'fish', build: 'build', build_yard: 'build', craft_axe: 'build', gather_wood: 'gather', wait_wood: 'wait', take_wood: 'gather', deposit_wood: 'give', gather_stone: 'gather', claim: 'gather', draw: 'draw', eat: 'eat', drink: 'drink', offer: 'give', agree: 'agree', wait: 'wait', wait_water: 'wait', yield: 'yield', warm: 'warm', rest: 'rest', dead: 'idle' }[kind] || 'idle';
  }
  function drawPerson(g, p, x, y, st, now) {
    const col = COLOR[p], dark = DARK[p], i = PIDX[p] || 0;
    const scale = st.scale || 1;
    g.save(); g.translate(x, y); g.scale(scale, scale);
    g.globalAlpha = st.alpha === undefined ? 1 : st.alpha;
    g.fillStyle = 'rgba(0,0,0,0.33)'; ell(g, 0, 0, 7.5, 3.4); g.fill();
    if (st.emergency && LAYERS.needs) {
      const pulse = REDUCED ? 0.6 : 0.5 + 0.5 * Math.sin(now * 0.008 + i);
      g.strokeStyle = `rgba(255,120,100,${(0.45 + 0.4 * pulse).toFixed(3)})`; g.lineWidth = 1.4; ell(g, 0, 0, 10 + pulse * 1.5, 4.6 + pulse * 0.7); g.stroke();
    }
    if (st.pose === 'yield') { g.save(); g.setLineDash([2, 2]); g.strokeStyle = 'rgba(192,168,244,0.95)'; g.lineWidth = 1.3; ell(g, 0, 0, 12, 5.5); g.stroke(); g.restore(); }
    if (st.selected) { g.strokeStyle = 'rgba(255,227,163,0.95)'; g.lineWidth = 1.6; ell(g, 0, 0, 13.5, 6.2); g.stroke(); }
    else if (st.hovered) { g.strokeStyle = 'rgba(255,255,255,0.6)'; g.lineWidth = 1.2; ell(g, 0, 0, 12.5, 5.8); g.stroke(); }
    const walking = st.pose === 'walk' && !REDUCED && st.stride;
    const ph = now * 0.014 + i * 1.7;
    const swing = walking ? Math.sin(ph) : st.pose === 'walk' ? 0.55 : 0;   // a held stride when paused
    const bob = walking ? Math.abs(Math.cos(ph)) * 1.1 : (REDUCED ? 0 : Math.sin(now * 0.002 + i) * 0.3);
    const lean = st.pose === 'held' ? -0.18 : 0;
    g.rotate(lean);
    // legs
    g.strokeStyle = dark; g.lineWidth = 2.2; g.lineCap = 'round';
    line(g, -1.8, -7 - bob, -1.8 + swing * 2.6, -0.9); line(g, 1.8, -7 - bob, 1.8 - swing * 2.6, -0.9);
    // body
    rrect(g, -4.3, -17.5 - bob, 8.6, 11.5, 3.6); g.fillStyle = col; g.fill(); g.strokeStyle = dark; g.lineWidth = 0.9; g.stroke();
    // arms, by what they are doing
    g.strokeStyle = dark; g.lineWidth = 1.8;
    const sh = -15 - bob;
    const pose = st.pose;
    if (pose === 'build') {
      const hit = REDUCED ? 0 : Math.sin(now * 0.018 + i) * 2.4;
      line(g, 3.4, sh, 7.5, sh - 5 + hit); g.fillStyle = '#6d6d6d'; g.fillRect(6.2, sh - 8 + hit, 4.2, 2.4);
      g.strokeStyle = '#7a5530'; g.lineWidth = 1.1; line(g, 7.5, sh - 5 + hit, 8.3, sh - 7 + hit);
      g.strokeStyle = dark; g.lineWidth = 1.8; line(g, -3.4, sh, -5.5, sh + 5);
    } else if (pose === 'gather' || pose === 'draw') {
      line(g, 3.4, sh, 7.5, sh + 7); line(g, -3.4, sh, -1, sh + 8);
      if (pose === 'draw') { g.fillStyle = '#7a5a3a'; rrect(g, 6, sh + 6.5, 4.5, 3.6, 0.8); g.fill(); }
      else { g.fillStyle = '#b8894e'; g.beginPath(); g.arc(8, sh + 8.5, 2.6, 0, Math.PI); g.fill(); }
    } else if (pose === 'eat' || pose === 'drink') {
      line(g, 3.4, sh, 2.6, sh - 4.8);
      if (pose === 'eat') { g.fillStyle = '#f0a04a'; g.beginPath(); g.arc(2.8, sh - 6, 1.7, 0, Math.PI * 2); g.fill(); }
      else { g.fillStyle = '#8fd3f0'; g.fillRect(1.4, sh - 7.2, 3, 3.2); }
      line(g, -3.4, sh, -4.5, sh + 6);
    } else if (pose === 'give' || pose === 'agree') {
      const dir = st.towards || 1;
      line(g, 3.4 * dir, sh, 8 * dir, sh + 1.5); line(g, -3.4 * dir, sh, -4 * dir, sh + 6);
      if (pose === 'give') { g.fillStyle = '#e8a45a'; rrect(g, 7.5 * dir - 2, sh - 1, 4.5, 3.6, 1); g.fill(); }
    } else if (pose === 'warm') {
      line(g, 3.4, sh, 5.5, sh + 4); line(g, -3.4, sh, -5.5, sh + 4);
    } else {
      line(g, 3.4, sh, 4.5 + swing * -1.6, sh + 6); line(g, -3.4, sh, -4.5 + swing * 1.6, sh + 6);
    }
    // head
    g.beginPath(); g.arc(0, -21 - bob, 3.8, 0, Math.PI * 2); g.fillStyle = '#f2e5d0'; g.fill(); g.strokeStyle = 'rgba(0,0,0,0.35)'; g.lineWidth = 0.7; g.stroke();
    // what they carry, from the kernel's balances
    if (st.food > 0) { g.fillStyle = '#e39a4f'; g.beginPath(); g.arc(-5.2, -12 - bob, 2.5, 0, Math.PI * 2); g.fill(); g.strokeStyle = '#7a4b1f'; g.lineWidth = 0.6; g.stroke(); }
    if (st.water > 0) { g.fillStyle = '#7cc8ea'; rrect(g, 3.8, -13.5 - bob, 3, 4.5, 1); g.fill(); g.strokeStyle = '#2d5d74'; g.lineWidth = 0.6; g.stroke(); }
    if (st.pose === 'fish') { g.strokeStyle = '#d1b48b'; g.lineWidth = 1.5; line(g, 3, -9, 17, -24); g.strokeStyle = '#d8f6ef'; line(g, 17, -24, 23, 0); }
    if (st.wood > 0) { g.strokeStyle = '#bd9461'; g.lineWidth = 2; for (let j=0;j<Math.min(st.wood,3);j++) line(g, -7+j*2, -8-bob, -2+j*2, -3-bob); }
    if (st.stone > 0) { g.fillStyle = '#c9c5be'; g.beginPath(); g.arc(5.5, -7 - bob, 2.2, 0, Math.PI * 2); g.fill(); }
    if (st.axe) { g.strokeStyle = '#8b6a45'; g.lineWidth = 1.6; line(g, 6, -6 - bob, 12, -20 - bob); g.fillStyle = '#b8b3ab'; poly(g, [[10, -21 - bob], [15, -19 - bob], [13, -14 - bob]]); g.fill(); }
    g.rotate(-lean);
    // little signs above the head
    const gy = -30 - bob;
    if (pose === 'wait') {
      g.fillStyle = 'rgba(250,246,232,0.95)'; rrect(g, 5, gy - 7, 11, 8, 3); g.fill();
      g.beginPath(); g.moveTo(7, gy + 1); g.lineTo(6, gy + 3.5); g.lineTo(9.5, gy + 1); g.fill();
      g.fillStyle = '#3a3a32'; g.font = '700 6.5px system-ui, sans-serif'; g.textAlign = 'center';
      g.fillText('…', 10.5, gy - 0.8);
    }
    if (pose === 'warm') {
      const f = REDUCED ? 1 : 0.85 + 0.15 * Math.sin(now * 0.02 + i);
      g.fillStyle = 'rgba(255,170,70,0.9)'; droplet(g, 8, -3, 2.2 * f); g.fill();
      g.fillStyle = 'rgba(255,230,140,0.95)'; droplet(g, 8, -2.6, 1.1 * f); g.fill();
    }
    if (pose === 'held') { g.fillStyle = 'rgba(200,190,170,0.6)'; for (let k = 0; k < 3; k++) { g.beginPath(); g.arc(-4 + k * 4, -0.5, 1.2 + (k % 2) * 0.5, 0, Math.PI * 2); g.fill(); } }
    if (LAYERS.needs && st.badges.length) {
      const w = st.badges.length * 8;
      st.badges.forEach((b, j) => {
        const bx = -w / 2 + 4 + j * 8 - (pose === 'wait' ? 5 : 0), by = gy - 2;
        g.fillStyle = 'rgba(10,20,22,0.8)'; g.beginPath(); g.arc(bx, by, 3.7, 0, Math.PI * 2); g.fill();
        g.fillStyle = b.em ? '#ff7a66' : b.color; g.strokeStyle = b.em ? '#ff7a66' : b.color; g.lineWidth = 1;
        if (b.key === 'hunger') { g.beginPath(); g.arc(bx, by, 2.1, 0, Math.PI * 2); g.fill(); }
        else if (b.key === 'thirst') { droplet(g, bx, by + 0.3, 1.5); g.fill(); }
        else { flake(g, bx, by, 2.4); g.stroke(); }
      });
    }
    g.restore();
  }

  // somebody who died on this tick: lying where they fell, fading as the tick plays
  function drawFallen(g, p, x, y, st, t) {
    g.save(); g.translate(x, y);
    g.fillStyle = 'rgba(0,0,0,0.3)'; ell(g, 1, 0, 10, 3.6); g.fill();
    if (st.selected) { g.strokeStyle = 'rgba(255,227,163,0.95)'; g.lineWidth = 1.6; ell(g, 0, 0, 14, 6.4); g.stroke(); }
    const lie = REDUCED ? 1 : Math.min(1, 0.25 + t * 1.2);
    g.globalAlpha = 0.85;
    g.rotate(-Math.PI / 2 * lie * 0.92);
    g.fillStyle = COLOR[p]; g.strokeStyle = DARK[p]; g.lineWidth = 0.9;
    rrect(g, -4.3, -17.5, 8.6, 11.5, 3.6); g.fill(); g.stroke();
    g.strokeStyle = DARK[p]; g.lineWidth = 2.2; g.lineCap = 'round'; line(g, -1.8, -7, -1.8, -1); line(g, 1.8, -7, 1.8, -1);
    g.beginPath(); g.arc(0, -21, 3.8, 0, Math.PI * 2); g.fillStyle = '#d9d0c2'; g.fill();
    g.restore();
    g.globalAlpha = 1;
  }

  // ---------------------------------------------------------- the frame --
  let hits = [];
  function frameState(now) {
    const t = easeT(now);
    const k = anim.to, w = world(k), d = decisions(k);
    const before = world(Math.max(0, k - 1));
    return { t, k, w, d, before };
  }
  function draw(now) {
    const g = ctx;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);
    const s = cam.z * dpr;
    const tx = (cw / 2 - (cam.x + driftX) * cam.z) * dpr, ty = (ch / 2 - (cam.y + driftY) * cam.z) * dpr;
    g.setTransform(s, 0, 0, s, tx, ty);
    // island glow and terrain
    const glow = g.createRadialGradient(0, isoY(GW / 2, GH / 2), 10, 0, isoY(GW / 2, GH / 2), (GW + GH) * 26);
    glow.addColorStop(0, 'rgba(120,190,170,0.16)'); glow.addColorStop(1, 'rgba(120,190,170,0)');
    g.fillStyle = glow; g.fillRect(BOUNDS.x0 - 200, BOUNDS.y0 - 200, BOUNDS.x1 - BOUNDS.x0 + 400, BOUNDS.y1 - BOUNDS.y0 + 400);
    const layer = terrainLayer(s);
    g.drawImage(layer, BOUNDS.x0, BOUNDS.y0, BOUNDS.x1 - BOUNDS.x0, BOUNDS.y1 - BOUNDS.y0);

    const { t, k, w, d, before } = frameState(now);
    const sheltersNow = sheltersAt(k);
    const selP = selected && selected.type === 'person' ? selected.id : null;

    // ground decals: shelter-spot warmth, homes, perception, trails
    if (LAYERS.spots) for (const key of SPOTS) {
      const [x, y] = key.split(',').map(Number), c = cellCentre(x, y);
      const pulse = REDUCED ? 0.7 : 0.75 + 0.25 * Math.sin(now * 0.0016 + x + y);
      const gr = g.createRadialGradient(c.x, c.y, 2, c.x, c.y, 26);
      gr.addColorStop(0, `rgba(255,196,110,${(0.30 * pulse).toFixed(3)})`); gr.addColorStop(1, 'rgba(255,196,110,0)');
      g.fillStyle = gr; ell(g, c.x, c.y, 26, 13); g.fill();
    }
    if (LAYERS.memory && selP && present(w, selP)) {
      const nowSeen = new Set();
      const radius2 = C.perception_radius;
      if (typeof radius2 === 'number' && !deadIn(w, selP)) {
        const [px, py] = w.positions[selP];
        for (const key of ROUGH) {
          const [rx, ry] = key.split(',').map(Number);
          if (Math.max(Math.abs(rx - px), Math.abs(ry - py)) <= radius2) nowSeen.add(key);
        }
      }
      for (const cell of roughMemory(w, selP)) {
        const key = cell.join(',');
        const c = cellCentre(cell[0], cell[1]);
        g.save();
        g.globalAlpha = nowSeen.has(key) ? 0.22 : 0.42;
        poly(g, [[c.x, c.y - 12], [c.x + 24, c.y], [c.x, c.y + 12], [c.x - 24, c.y]]);
        g.fillStyle = 'rgba(255,227,163,0.12)'; g.fill();
        g.setLineDash([4, 3]); g.strokeStyle = 'rgba(255,227,163,0.65)'; g.lineWidth = 1.1; g.stroke();
        g.restore();
      }
    }
    if (LAYERS.homes && w.homes) for (const p of people) {
      if (!present(w, p)) continue;
      const hm = w.homes[p]; if (!hm) continue;
      if (LAYERS.shelters && sheltersNow.has(hm.join(','))) continue;
      if (LAYERS.shelters && BUILD_TICKS && ((w.built || {})[p] || 0) > 0) continue;
      drawHomeMark(g, hm[0], hm[1], p, deadIn(w, p));
    }
    if (LAYERS.homes && selP && (w.home_targets || {})[selP] && present(w, selP)) {
      const target = w.home_targets[selP], there = cellCentre(target[0], target[1]);
      const here = placeOf(selP, t);
      g.save(); g.strokeStyle = '#f0c578'; g.lineWidth = 1.7; g.setLineDash([5, 4]);
      if (here) line(g, here.x, here.y, there.x, there.y);
      ell(g, there.x, there.y, 19, 9); g.stroke(); g.restore();
    }
    const radius = C.perception_radius;
    if (LAYERS.perception !== 'off' && typeof radius === 'number') {
      const whose = LAYERS.perception === 'everyone' ? people.filter(p => present(w, p) && !deadIn(w, p)) : (selP && present(w, selP) && !deadIn(w, selP) ? [selP] : []);
      for (const p of whose) {
        const [x, y] = w.positions[p];
        const x0 = Math.max(0, x - radius), y0 = Math.max(0, y - radius), x1 = Math.min(GW - 1, x + radius) + 1, y1 = Math.min(GH - 1, y + radius) + 1;
        const lift = -4;
        const pts = [[isoX(x0, y0), isoY(x0, y0) + lift], [isoX(x1, y0), isoY(x1, y0) + lift], [isoX(x1, y1), isoY(x1, y1) + lift], [isoX(x0, y1), isoY(x0, y1) + lift]];
        poly(g, pts); g.fillStyle = whose.length > 1 ? 'rgba(255,227,163,0.035)' : 'rgba(255,227,163,0.08)'; g.fill();
        g.save(); g.setLineDash([6, 5]); g.strokeStyle = whose.length > 1 ? 'rgba(255,227,163,0.22)' : 'rgba(255,227,163,0.6)'; g.lineWidth = 1.2; g.stroke(); g.restore();
      }
    }
    if (LAYERS.trails && k > 0) {
      for (const p of people) {
        if (!present(w, p) || (deadIn(w, p) && w.died_at[p] < k)) continue;
        const span = p === selP ? 40 : 12, pts = [];
        for (let j = Math.max(0, k - span); j < k; j++) { const c = (world(j).positions || {})[p]; if (c) pts.push(cellCentre(c[0], c[1])); }
        const here = placeOf(p, t); if (here) pts.push({ x: here.x, y: here.y });
        if (pts.length < 2) continue;
        g.lineCap = 'round'; g.lineJoin = 'round';
        for (let j = 1; j < pts.length; j++) {
          const a = j / pts.length;
          g.strokeStyle = COLOR[p]; g.globalAlpha = (p === selP ? 0.85 : 0.45) * a * a; g.lineWidth = p === selP ? 2.6 : 1.8;
          line(g, pts[j - 1].x, pts[j - 1].y, pts[j].x, pts[j].y);
        }
        g.globalAlpha = 1;
      }
    }

    // Family links come only from the saved birth relationships.
    if (LAYERS.family && selP && ADULT_AT !== null && present(w, selP)) {
      const kin = [...parentsOf(selP), ...(CHILDREN[selP] || [])].filter(q => q && present(w, q) && !deadIn(w, q));
      const me = placeOf(selP, t);
      if (me) for (const q of kin) {
        const other = placeOf(q, t); if (!other) continue;
        g.save(); g.strokeStyle = 'rgba(236,178,214,0.8)'; g.lineWidth = 1.5; g.setLineDash([1, 3.5]); g.lineCap = 'round';
        g.beginPath(); g.moveTo(me.x, me.y); g.lineTo(other.x, other.y); g.stroke(); g.restore();
        g.fillStyle = 'rgba(236,178,214,0.9)'; g.beginPath(); g.arc(other.x, other.y, 2.2, 0, Math.PI * 2); g.fill();
      }
    }

    // standing things and people, back to front
    const items = [];
    for (const src of SOURCE_AT.values()) {
      if (src.store && stockOf(k, src.id) === null) continue;
      if (!LAYERS[src.kind]) continue;
      if (src.store && !sheltersNow.has(src.position.join(','))) continue;
      const [x, y] = src.position; items.push({ z: x + y + (src.store ? 1.2 : 1), draw: () => { const c = cellCentre(x, y);
        if (src.store) {
          const count = stockOf(k, src.id) || 0;
          g.fillStyle = '#795336'; g.fillRect(c.x + 12, c.y - 4, 16, 10);
          g.strokeStyle = '#cea875'; g.lineWidth = 1; g.strokeRect(c.x + 12, c.y - 4, 16, 10);
          g.fillStyle = '#f2bb64';
          for (let i = 0; i < Math.min(count, 6); i++) { g.beginPath(); g.arc(c.x + 15 + (i % 3) * 5, c.y - 2 + Math.floor(i / 3) * 4, 1.7, 0, Math.PI * 2); g.fill(); }
        }
        else if (src.fishing) {
          g.fillStyle = '#237f96'; g.beginPath(); g.ellipse(c.x, c.y, 20, 10, 0, 0, Math.PI*2); g.fill();
          g.strokeStyle = '#8de0df'; g.lineWidth = 1; g.stroke();
          g.fillStyle = '#bd996e'; g.fillRect(c.x-20, c.y-3, 13, 5);
          g.fillStyle = '#d5f7ed';
          for (let j=0;j<Math.min(stockOf(k,src.id)||0,6);j++) { g.beginPath(); g.ellipse(c.x-3+(j%3)*6,c.y-3+Math.floor(j/3)*6,2.5,1.2,-0.3,0,Math.PI*2); g.fill(); }
        }
        else if (src.kind === 'food') drawBush(g, src, c.x, c.y, stockOf(k, src.id), (w.patch_condition || {})[src.id]);
        else if (src.kind === 'wood' && src.yard) { if (stockOf(k, src.id) !== null) drawYard(g, c.x, c.y, stockOf(k, src.id)); }
        else if (src.kind === 'wood') drawWood(g, c.x, c.y, stockOf(k, src.id));
        else if (src.kind === 'stone') drawStone(g, c.x, c.y, stockOf(k, src.id));
        else drawWell(g, src, c.x, c.y, stockOf(k, src.id), now);
      } });
    }
    if (LAYERS.shelters) {
      for (const key of sheltersNow) {
        const [x, y] = key.split(',').map(Number), owner = ownerOfCell(key, k);
        const occupied = people.some(p => present(w, p) && !deadIn(w, p) && w.positions[p][0] === x && w.positions[p][1] === y);
        items.push({ z: x + y + 1, draw: () => { const c = cellCentre(x, y); drawHut(g, c.x, c.y, owner, occupied, owner ? deadIn(w, owner) : false, now); } });
      }
      if (BUILD_TICKS) for (const p of people) {
        const work = (w.built || {})[p] || 0; if (!work || !present(w, p)) continue;
        const hm = w.homes[p]; if (!hm || sheltersNow.has(hm.join(','))) continue;
        items.push({ z: hm[0] + hm[1] + 1, draw: () => { const c = cellCentre(hm[0], hm[1]); drawSite(g, c.x, c.y, work / BUILD_TICKS, deadIn(w, p)); } });
      }
    }
    if (LAYERS.deaths) {
      const byCell = {};
      for (const p of people) if (present(w, p) && deadIn(w, p) && w.died_at[p] < k) { const key = w.positions[p].join(','); (byCell[key] = byCell[key] || []).push(p); }
      for (const key in byCell) {
        const [x, y] = key.split(',').map(Number), list = byCell[key];
        items.push({ z: x + y + 0.9, draw: () => {
          const c = cellCentre(x, y);
          if (selP && list.includes(selP)) { g.strokeStyle = 'rgba(255,227,163,0.95)'; g.lineWidth = 1.6; ell(g, c.x - 2, c.y - 4, 17, 7.8); g.stroke(); }
          const m = Math.min(list.length, 5);
          for (let j = 0; j < m; j++) drawStone(g, c.x - 10 + j * 5, c.y - 6 + (j % 2) * 2.5, 0.8);
        } });
      }
    }
    hits = [];
    if (LAYERS.people) for (const p of people) {
      if (!present(w, p)) continue;
      const diedNow = deadIn(w, p) && w.died_at[p] === k;
      if (deadIn(w, p) && !diedNow) continue;
      const place = placeOf(p, t); if (!place) continue;
      const dec = d[p];
      // what this tick did, from the two saved views either side of it
      const a = (before.positions || {})[p], b = w.positions[p];
      const moved = !!(a && (a[0] !== b[0] || a[1] !== b[1]));
      const held = !!(dec && dec.step && !moved && a);
      const pose = poseOf(dec, moved, held);
      const badges = [];
      for (const need of NEEDS) {
        const x = needLevel(w, p, need); if (x === null || need.at === undefined) continue;
        if (x >= need.at) badges.push({ key: need.key, color: need.color, em: need.em !== undefined && x >= need.em });
      }
      const bornNow = BORN[p] === k && anim.from !== anim.to;
      let towards = 1;
      if (dec && dec.target && w.positions[dec.target]) towards = isoX(w.positions[dec.target][0], w.positions[dec.target][1]) >= isoX(b[0], b[1]) ? 1 : -1;
      const st = {
        pose, badges, towards, food: food(k, p), water: waterHeld(k, p), wood: woodHeld(k, p), stone: stoneHeld(k, p), axe: (w.axes || []).includes(p),
        emergency: badges.some(x => x.em) && !diedNow, selected: p === selP, hovered: hovered === p, stride: anim.from !== anim.to || playing,
        scale: (bornNow ? 0.35 + 0.65 * t : 1) * (isChild(w, p) ? 0.72 : 1), alpha: diedNow ? Math.max(0.25, 1 - t * 0.75) : 1,
      };
      if (diedNow) {
        // lying at the front of the cell they died on, so a crowd there does not hide it
        const fx = b[0] + 0.78, fy = b[1] + 0.78, fe = elev(b[0], b[1]);
        items.push({ z: b[0] + b[1] + 1.9, draw: () => drawFallen(g, p, isoX(fx, fy), isoY(fx, fy) - fe, st, anim.from === anim.to ? 1 : t) });
        continue;
      }
      items.push({ z: place.gx + place.gy + 0.05, draw: () => {
        if (diedNow) drawFallen(g, p, place.x, place.y, st, anim.from === anim.to ? 1 : t);
        else drawPerson(g, p, place.x, place.y, st, now);
      } });
      if (!diedNow) hits.push({ p, x: place.x, y: place.y - 11, r: 13 });
    }
    items.sort((A, B) => A.z - B.z);
    for (const it of items) it.draw();

    // what passed between people, and moments in the world
    drawLinks(g, w, k, t, now);
    drawMoments(g, k, t, now);

    // screen-space labels
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawLabels(g, w, k, t);
    needsDraw = false;
  }

  function headOf(p, t) { const pl = placeOf(p, t); return pl ? { x: pl.x, y: pl.y - 22 } : null; }
  function arc(g, a, b, lift) {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 - lift;
    g.beginPath(); g.moveTo(a.x, a.y); g.quadraticCurveTo(mx, my, b.x, b.y);
    return { mx, my };
  }
  function along(a, b, m, u) { const q = 1 - u; return { x: q * q * a.x + 2 * q * u * m.mx + u * u * b.x, y: q * q * a.y + 2 * q * u * m.my + u * u * b.y }; }
  function bubble(g, x, y, text, fill, ink) {
    g.fillStyle = fill; rrect(g, x - 6, y - 6, 12, 10, 3.5); g.fill();
    g.beginPath(); g.moveTo(x - 2, y + 4); g.lineTo(x - 3.5, y + 7); g.lineTo(x + 1.5, y + 4); g.fill();
    g.fillStyle = ink; g.font = '700 7.5px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, x, y - 0.8);
    g.textBaseline = 'alphabetic';
  }
  function drawLinks(g, w, k, t, now) {
    if (!LAYERS.links) return;
    const march = REDUCED ? 0 : -(now * 0.02) % 14;
    // errands standing in the world state: a helper who agreed, and the person waiting on them
    for (const helper in (w.promises || {})) {
      const asker = w.promises[helper];
      if (!present(w, helper) || !present(w, asker) || deadIn(w, helper) || deadIn(w, asker)) continue;
      const a = headOf(helper, t), b = headOf(asker, t); if (!a || !b) continue;
      g.save(); g.setLineDash([2, 5]); g.lineDashOffset = march; g.strokeStyle = 'rgba(241,197,110,0.85)'; g.lineWidth = 1.6; g.lineCap = 'round';
      arc(g, { x: a.x, y: a.y + 10 }, { x: b.x, y: b.y + 10 }, 10); g.stroke(); g.restore();
    }
    // a request waiting for its answer
    for (const asker in (w.requests || {})) {
      const asked = w.requests[asker];
      if (!present(w, asker) || !present(w, asked)) continue;
      const a = headOf(asker, t), b = headOf(asked, t); if (!a || !b) continue;
      g.save(); g.setLineDash([5, 4]); g.lineDashOffset = march * 0.6; g.strokeStyle = 'rgba(255,214,140,0.75)'; g.lineWidth = 1.3;
      const m = arc(g, a, b, 16 + Math.hypot(a.x - b.x, a.y - b.y) * 0.15); g.stroke(); g.restore();
      const tip = along(a, b, m, 0.98); g.fillStyle = 'rgba(255,214,140,0.9)'; g.beginPath(); g.arc(tip.x, tip.y, 2, 0, Math.PI * 2); g.fill();
    }
    for (const e of eventsAt(k)) {
      if (e.cat !== 'help' || !e.who || !e.other) continue;
      const a = headOf(e.who, t), b = headOf(e.other, t); if (!a || !b) continue;
      const lift = 16 + Math.hypot(a.x - b.x, a.y - b.y) * 0.15;
      if (e.kind === 'agree') {
        g.strokeStyle = 'rgba(159,220,170,0.9)'; g.lineWidth = 1.6; arc(g, a, b, lift); g.stroke();
        bubble(g, a.x + 9, a.y - 10, '✓', 'rgba(159,220,170,0.95)', '#123a1c');
      } else if (e.kind === 'unanswered') {
        g.save(); g.setLineDash([1.5, 4]); g.strokeStyle = `rgba(200,200,190,${(0.7 * (1 - 0.5 * t)).toFixed(3)})`; g.lineWidth = 1.2; arc(g, a, b, lift); g.stroke(); g.restore();
        bubble(g, a.x + 9, a.y - 10, '…', 'rgba(210,210,200,0.9)', '#2a2a24');
      } else if (e.kind === 'delivered' || e.kind === 'gave' || e.kind === 'fed_child') {
        const m = arc(g, a, b, lift); g.strokeStyle = 'rgba(241,197,110,0.45)'; g.lineWidth = 1.2; g.stroke();
        const u = REDUCED ? 1 : t, q = along(a, b, m, u);
        g.fillStyle = '#e8a45a'; rrect(g, q.x - 3.5, q.y - 3, 7, 6, 1.5); g.fill(); g.strokeStyle = '#6b4520'; g.lineWidth = 0.7; g.stroke();
        if (u > 0.85) { g.fillStyle = '#ffe3a3'; g.font = '700 8px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('+1', b.x, b.y - 12 - 6 * (u - 0.85) / 0.15); }
      } else if (e.kind === 'refused') {
        const m = arc(g, a, b, lift); g.strokeStyle = 'rgba(255,148,131,0.6)'; g.lineWidth = 1.2; g.stroke();
        const q = along(a, b, m, 0.5); g.strokeStyle = '#ff7a66'; g.lineWidth = 2; line(g, q.x - 4, q.y - 4, q.x + 4, q.y + 4); line(g, q.x + 4, q.y - 4, q.x - 4, q.y + 4);
      } else if (e.kind === 'ask') {
        bubble(g, a.x + 9, a.y - 10, '?', 'rgba(255,236,190,0.95)', '#3b2a08');
      } else if (e.kind === 'too_late') {
        g.save(); g.setLineDash([2, 3]); g.strokeStyle = 'rgba(200,190,180,0.5)'; g.lineWidth = 1; arc(g, a, b, lift); g.stroke(); g.restore();
      }
    }
  }
  function drawMoments(g, k, t, now) {
    const fade = anim.from === anim.to ? 1 : t;
    for (const e of eventsAt(k)) {
      if (e.kind === 'birth' && e.who && LAYERS.people && LAYERS.moments) {
        const pl = placeOf(e.who, t); if (!pl) continue;
        const r = REDUCED ? 14 : 6 + 18 * fade;
        g.strokeStyle = `rgba(159,220,170,${(0.9 * (1 - 0.6 * fade)).toFixed(3)})`; g.lineWidth = 1.6; ell(g, pl.x, pl.y, r, r * 0.46); g.stroke();
        for (let j = 0; j < 6; j++) { const a2 = j / 6 * Math.PI * 2 + now * 0.001; g.fillStyle = 'rgba(210,255,215,0.8)'; g.beginPath(); g.arc(pl.x + Math.cos(a2) * r * 0.9, pl.y - 12 + Math.sin(a2) * r * 0.5, 1.1, 0, Math.PI * 2); g.fill(); }
      } else if (e.kind === 'death' && e.who && LAYERS.deaths) {
        const pl = placeOf(e.who, 1); if (!pl) continue;
        const r = REDUCED ? 16 : 6 + 20 * fade;
        g.strokeStyle = `rgba(20,10,10,${(0.55 * (1 - 0.5 * fade)).toFixed(3)})`; g.lineWidth = 2.2; ell(g, pl.x, pl.y, r, r * 0.46); g.stroke();
        g.strokeStyle = `rgba(255,148,131,${(0.6 * (1 - 0.5 * fade)).toFixed(3)})`; g.lineWidth = 1; ell(g, pl.x, pl.y, r * 0.7, r * 0.32); g.stroke();
      } else if ((e.kind === 'claim' || e.kind === 'draw') && e.who && e.amount && LAYERS.moments) {
        const pl = placeOf(e.who, t); if (!pl) continue;
        g.fillStyle = e.kind === 'claim' ? '#f2a65e' : '#8fd3f0'; g.font = '700 8.5px system-ui, sans-serif'; g.textAlign = 'center';
        g.globalAlpha = REDUCED ? 1 : Math.min(1, 1.6 - fade); g.fillText('+' + e.amount, pl.x + 8, pl.y - 30 - 10 * fade); g.globalAlpha = 1;
      } else if ((e.kind === 'food_out' || e.kind === 'water_out') && e.src && SOURCE_BY_ID[e.src] && LAYERS.moments) {
        const [x, y] = SOURCE_BY_ID[e.src].position, c = cellCentre(x, y);
        for (let j = 0; j < 5; j++) { const r = 3 + 12 * fade; g.fillStyle = `rgba(190,170,140,${(0.4 * (1 - fade * 0.7)).toFixed(3)})`; g.beginPath(); g.arc(c.x + Math.cos(j * 1.3) * r, c.y - 4 + Math.sin(j * 1.3) * r * 0.4, 2.5, 0, Math.PI * 2); g.fill(); }
      }
    }
    if (!LAYERS.moments || k < 1) return;
    for (const e of ((ticks[k - 1] || {}).production || [])) {
      if (!e.source || !SOURCE_BY_ID[e.source]) continue;
      const src = SOURCE_BY_ID[e.source];
      if (!LAYERS[src.kind]) continue;
      const c = cellCentre(src.position[0], src.position[1]);
      for (let j = 0; j < 5; j++) {
        const a2 = j * 1.26 + (REDUCED ? 0 : now * 0.002), rise = REDUCED ? 8 : 4 + 16 * fade;
        g.fillStyle = src.kind === 'food' ? `rgba(200,255,170,${(0.9 * (1 - fade * 0.6)).toFixed(3)})` : `rgba(190,235,255,${(0.9 * (1 - fade * 0.6)).toFixed(3)})`;
        const sx = c.x + Math.cos(a2) * 11, sy = c.y - 10 - rise + Math.sin(a2) * 4;
        g.beginPath(); g.moveTo(sx, sy - 2.2); g.lineTo(sx + 0.7, sy - 0.7); g.lineTo(sx + 2.2, sy); g.lineTo(sx + 0.7, sy + 0.7); g.lineTo(sx, sy + 2.2); g.lineTo(sx - 0.7, sy + 0.7); g.lineTo(sx - 2.2, sy); g.lineTo(sx - 0.7, sy - 0.7); g.closePath(); g.fill();
      }
    }
  }
  let labelPx = 11;
  function pill(g, x, y, text, bg, fg, border) {
    g.font = `600 ${labelPx}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    const w = g.measureText(text).width + labelPx + 1, h = labelPx + 6;
    g.fillStyle = bg; rrect(g, x - w / 2, y - h / 2, w, h, 8.5); g.fill();
    if (border) { g.strokeStyle = border; g.lineWidth = 1; g.stroke(); }
    g.fillStyle = fg; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, x, y + 0.5); g.textBaseline = 'alphabetic';
    return { x0: x - w / 2, x1: x + w / 2, y0: y - h / 2, y1: y + h / 2 };
  }
  function drawLabels(g, w, k, t) {
    const placed = [];
    labelPx = Math.round(clamp(11 * Math.sqrt(cam.z / 1.1), 8, 11));
    const overlaps = r => placed.some(q => r.x0 < q.x1 + 2 && r.x1 > q.x0 - 2 && r.y0 < q.y1 + 1 && r.y1 > q.y0 - 1);
    if (LAYERS.stock) for (const [, src] of SOURCE_AT) {
      if (src.store && stockOf(k, src.id) === null) continue;
      if (!LAYERS[src.kind]) continue;
      if (src.store && !(w.shelters || []).some(cell => cell.join(',') === src.position.join(','))) continue;
      const c = cellCentre(src.position[0], src.position[1]);
      const [sx, sy] = toScreen(c.x, c.y + 13);
      const st = stockOf(k, src.id);
      const text = (FOOD.length + WELLS.length + (IDX.wood || []).length > 2 ? src.id + ' ' : '') + (st === null ? '?' : st) + (src.cap ? '/' + src.cap : '');
      placed.push(pill(g, sx, sy, text, 'rgba(8,22,25,0.82)', sourceColor(src), sourceColor(src)));
    }
    if (!LAYERS.people) return;
    const selP = selected && selected.type === 'person' ? selected.id : null;
    const order = people.filter(p => present(w, p) && !deadIn(w, p));
    order.sort((a, b) => (b === selP) - (a === selP) || (b === hovered) - (a === hovered));
    const small = (order.length > 24 && cam.z < 1.2) || cam.z < 0.7;
    for (const p of order) {
      if (!(p === selP || p === hovered || (LAYERS.names && !small))) continue;
      const pl = placeOf(p, t); if (!pl) continue;
      const [sx, sy] = toScreen(pl.x, pl.y - 36);
      g.font = `600 ${labelPx}px system-ui, sans-serif`;
      const wid = g.measureText(p).width + labelPx + 1, half = (labelPx + 6) / 2;
      const r = { x0: sx - wid / 2, x1: sx + wid / 2, y0: sy - half, y1: sy + half };
      if (p !== selP && p !== hovered && overlaps(r)) continue;
      placed.push(pill(g, sx, sy, p, p === selP ? 'rgba(255,227,163,0.95)' : 'rgba(8,22,25,0.78)', p === selP ? '#1d1606' : '#e7f0ea', p === selP ? null : COLOR[p]));
    }
  }

  // ------------------------------------------------------------- the UI --
  const slider = $('slider'), tickEl = $('tick'), playBtn = $('play');
  slider.max = n;
  function setPlaying(on) {
    playing = on && n > 0;
    playBtn.setAttribute('aria-pressed', playing ? 'true' : 'false');
    playBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
    playBtn.innerHTML = playing ? ICON.pause : ICON.play;
    if (playing && v >= n) show(0);
    acc = 0; needsDraw = true;
  }
  const ICON = {
    play: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 4l10 6-10 6z" fill="currentColor"/></svg>',
    pause: '<svg viewBox="0 0 20 20" aria-hidden="true"><rect x="5" y="4" width="3.4" height="12" rx="1" fill="currentColor"/><rect x="11.6" y="4" width="3.4" height="12" rx="1" fill="currentColor"/></svg>',
  };
  function tweenDur(stepping) { return REDUCED ? 0 : window.liveTweenMs ? Math.max(120, window.liveTweenMs) : stepping ? 220 : Math.min(700, 0.92 * 1000 / tps); }
  function show(k, opts) {
    opts = opts || {};
    k = clamp(Math.round(Number(k) || 0), 0, n);
    const prev = v; v = k;
    if (window.liveFill) { window.liveFill(k); if (opts.tween && Math.abs(k - prev) === 1) window.liveFill(prev); }
    if (opts.tween && Math.abs(k - prev) === 1 && !REDUCED && ticks[Math.min(k, prev) - 1] !== null) anim = { from: prev, to: k, start: performance.now(), dur: tweenDur(opts.stepping) };
    else anim = { from: k, to: k, start: 0, dur: 0 };
    slider.value = v;
    slider.setAttribute('aria-valuetext', `tick ${v} of ${n}`);
    tickEl.innerHTML = `World tick ${v + TICK0} <small>/ ${n + TICK0}</small>`;
    updateHud(); updateSummary(); markEvents(); updateFocusCard(); if (typeof pinChip === 'function') pinChip();
    if (tabNow === 'inspector') renderInspector();
    if ($('deep').open) updateDeep();
    needsDraw = true;
  }
  window.show = show;
  // Live mode hooks: place a recorded tick (by its world tick number; gaps stay null until
  // filled from /ticks) and its index increment; nothing is recomputed here.
  window.liveAppend = (tick, inc) => {
    const k = tick.tick - TICK0 + 1;            // view index of this tick
    if (k < 1) return;
    while (ticks.length < k - 1) ticks.push(null);
    ticks[k - 1] = tick; n = ticks.length;
    if (inc) {
      RUN.details[k] = inc.details || {};
      for (const key in (inc.counts || {})) (COUNTS[key] = COUNTS[key] || [])[k] = inc.counts[key];
      for (const e of inc.events || []) { EVENTS.push(e); const i = EVENTS.length - 1; (EV_OF[e.who] = EV_OF[e.who] || []).push(i); if (e.src) (EV_AT_SRC[e.src] = EV_AT_SRC[e.src] || []).push(i); }
      if (inc.wood) for (const s of inc.wood) if (!SOURCE_AT.has(s.position.join(','))) SOURCE_AT.set(s.position.join(','), { kind: 'wood', id: s.id, position: s.position, yard: !!s.yard, cap: s.yard ? (C.yard_rules || {}).capacity : C.wood_rules.cap });
    } else if (!RUN.details[k]) RUN.details[k] = {};
    slider.max = n; needsDraw = true;
    if (typeof renderEvents === 'function') renderEvents();
    if (typeof drawStrip === 'function') drawStrip();
  };
  window.liveHasTick = k => k <= 0 || (k <= n && ticks[k - 1] != null);
  window.liveTickCount = () => n;
  window.liveView = () => v;
  window.liveShow = (k, tween) => show(k, { tween: !!tween });
  window.liveTweening = () => anim.dur > 0 && performance.now() - anim.start < anim.dur;
  window.liveAnimState = () => ({ view: v, from: anim.from, to: anim.to, t: easeT(performance.now()), people: hits.map(h => ({ id: h.p, x: h.x, y: h.y })) });
  // Read-only: where each living person is presented right now, in grid units (cell + 0.5 is a cell centre).
  window.livePositions = () => {
    const now = performance.now(), t = easeT(now), wb = world(anim.to), wa = world(anim.from), out = {};
    for (const p of people) {
      if (!present(wb, p) || deadIn(wb, p)) continue;
      const pl = placeOf(p, t); if (!pl) continue;
      out[p] = { gx: pl.gx, gy: pl.gy, from: (wa.positions || {})[p] || null, to: wb.positions[p] };
    }
    return { view: v, from: anim.from, to: anim.to, t, tweening: anim.dur > 0 && now - anim.start < anim.dur, people: out };
  };
  // Read-only view of what is on screen, for scripted checks of the page (tools/*.js).
  window.viewerState = () => ({
    view: v, ticks: n, playing, selected: selected ? Object.assign({}, selected) : null, tab: tabNow,
    camera: { x: cam.x, y: cam.y, z: cam.z },
    people: hits.map(h => { const [sx, sy] = toScreen(h.x, h.y); return { id: h.p, x: sx, y: sy }; }),
  });

  function aliveAt(k) { return (COUNTS.alive || [])[k] ?? 0; }
  function updateHud() {
    const w = world(v);
    $('hud-tick').innerHTML = `World tick ${v + TICK0}<small>of ${n + TICK0}</small>`;
    const bits = [`<span>alive <b>${aliveAt(v)}</b></span>`];
    if (w.season) bits.push(`<span>season <b>${esc(w.season)}</b></span>`);
    if ((COUNTS.born || [])[n]) bits.push(`<span>born <b>${COUNTS.born[v]}</b></span>`);
    bits.push(`<span>died <b>${(COUNTS.dead || [])[v] ?? Object.keys(w.died_at || {}).length}</b></span>`);
    if (BUILD_TICKS) bits.push(`<span>shelters <b>${(COUNTS.shelters || [])[v] ?? 0}</b></span>`);
    if (ADULT_AT !== null) bits.push(`<span>children <b>${(COUNTS.children || [])[v] ?? 0}</b></span>`);
    $('hud-line').innerHTML = bits.join('');
    canvas.setAttribute('aria-label', `Isometric map of the world at tick ${v} of ${n}: ${aliveAt(v)} alive.`);
    if (!playing) $('live').textContent = `World tick ${v}. ${aliveAt(v)} alive.`;
  }
  function updateSummary() {
    const w = world(v), c = COUNTS;
    const dead = (c.dead || [])[v] ?? 0, deadAll = (c.dead || [])[n] ?? 0;
    const stats = [
      ['Seed', esc(C.seed ?? '–')],
      ['World', `${GW} × ${GH}`],
      ['Tick', `${v} <small>/ ${n}</small>`],
      ['Living', `${aliveAt(v)} <small>/ ${(c.people || [])[v] ?? Object.keys(w.positions || {}).length}</small>`],
      ['Deaths', `${dead} <small>/ ${deadAll} total</small>`],
    ];
    if ((c.born || [])[n]) stats.push(['Births', `${c.born[v]} <small>/ ${c.born[n]} total</small>`]);
    else stats.push(['Births', '0']);
    if (BUILD_TICKS) stats.push(['Shelters', `${(c.shelters || [])[v] ?? 0} <small>built</small>`]);
    if (C.wood === 'on') {
      const state = v === 0 ? H.genesis : (held(v) || {}).state || H.genesis;
      stats.push(['Wood used', `${(state.consumed_by || {}).wood || 0} <small>in construction</small>`]);
    }
    if (ADULT_AT !== null) stats.push(['Children', `${(c.children || [])[v] ?? 0} <small>growing up</small>`]);
    $('stats').innerHTML = stats.map(([k2, val]) => `<div class="stat"><div class="k">${k2}</div><div class="v">${val}</div></div>`).join('');
    const rows = [];
    if (w.season) rows.push(`<div class="hint"><b>${esc(w.season)} season</b> — food growth allowance ${C.season_growth[w.season]} before patch wear. Seasons change every ${C.season_ticks} ticks.</div>`);
    for (const [, src] of SOURCE_AT) {
      const st = stockOf(v, src.id), cap = src.cap || 1;
      if (src.store && st === null) continue;
      const colour = sourceColor(src);
      rows.push(`<div class="src"><span class="name">${esc(src.id)}</span><span class="bar"><i style="width:${clamp(100 * (st || 0) / cap, 0, 100).toFixed(1)}%;background:${colour}"></i></span><span class="n">${st ?? '?'} / ${src.cap ?? '?'}${src.store ? ' target' : ''}</span></div>`);
      const condition = (w.patch_condition || {})[src.id];
      if (condition !== undefined) rows.push(`<div class="hint">${esc(src.id)} condition ${condition}/${C.patch_rules.condition_max} — ${condition < C.patch_rules.full_growth_at ? 'worn patch' : 'healthy patch'}</div>`);
    }
    $('sources').innerHTML = rows.join('');
    const help = [];
    if ((c.asked || [])[n] || C.requests === 'on') {
      help.push(`<span>asked <b>${c.asked[v]}</b></span>`, `<span>agreed <b>${c.agreed[v]}</b></span>`, `<span>unanswered <b>${c.unanswered[v]}</b></span>`, `<span>delivered <b>${c.delivered[v]}</b></span>`);
    }
    if ((c.handed || [])[n]) help.push(`<span>food handed over <b>${c.handed[v]}</b></span>`);
    if ((c.fed_children || [])[n]) help.push(`<span>to their own children <b>${c.fed_children[v]}</b></span>`);
    if ((c.refused || [])[n]) help.push(`<span>refused <b>${c.refused[v]}</b></span>`);
    $('helpline').innerHTML = help.join('');
    $('helpline').hidden = !help.length;
  }

  // ------------------------------------------------------------ events --
  const list = $('events');
  const catOn = {}; (IDX.categories || []).forEach(([key]) => { catOn[key] = true; });
  let onlySelected = false;
  let rows = [];
  function renderEvents() {
    if (!EVENTS.length) { list.innerHTML = '<p class="empty">Nothing of note happened in this run.</p>'; return; }
    list.innerHTML = EVENTS.map((e, i) => `<button class="event${e.kind === 'death' ? ' death' : ''}" type="button" data-i="${i}"><span class="evtick">t${e.k}</span><span class="dot c-${e.cat}"></span><span>${esc(e.text)}</span></button>`).join('');
    rows = Array.from(list.children);
    const counts = {}; EVENTS.forEach(e => { counts[e.cat] = (counts[e.cat] || 0) + 1; });
    const chips = (IDX.categories || []).filter(([key]) => counts[key]).map(([key, label]) =>
      `<button class="cat" type="button" data-cat="${key}" aria-pressed="true" title="${esc(label)}"><i class="c-${key}"></i>${esc(label)} <small>${counts[key]}</small></button>`);
    chips.push('<button class="cat only" type="button" id="only-sel" aria-pressed="false" title="Only events involving the selected person or place">Selected only</button>');
    $('cats').innerHTML = chips.join('');
    $('ev-count').textContent = EVENTS.length;
  }
  function involves(e) {
    if (!selected) return true;
    if (selected.type === 'person') return e.who === selected.id || e.other === selected.id;
    return e.src === selected.id;
  }
  function applyFilter() {
    rows.forEach((row, i) => { const e = EVENTS[i]; row.hidden = !(catOn[e.cat] !== false && (!onlySelected || involves(e))); });
    lastBoundary = -1; markEvents();
  }
  let lastBoundary = -1, lastNow = [0, 0];
  function markEvents() {
    if (!rows.length) return;
    const b = EV_FIRST[v + 1];
    if (lastBoundary < 0) rows.forEach((row, i) => row.classList.toggle('future', i >= b));
    else if (b > lastBoundary) for (let i = lastBoundary; i < b; i++) rows[i].classList.remove('future');
    else for (let i = b; i < lastBoundary; i++) rows[i].classList.add('future');
    lastBoundary = b;
    for (let i = lastNow[0]; i < lastNow[1]; i++) rows[i].classList.remove('now');
    lastNow = [EV_FIRST[v], b];
    for (let i = lastNow[0]; i < lastNow[1]; i++) rows[i].classList.add('now');
    // keep the latest visible line in view, scrolling only the list itself
    let target = null;
    for (let i = b - 1; i >= 0; i--) if (!rows[i].hidden) { target = rows[i]; break; }
    if (!target && tabNow === 'events') { list.scrollTop = 0; return; }
    if (target && tabNow === 'events') {
      const top = target.offsetTop - list.offsetTop, bottom = top + target.offsetHeight;
      if (top < list.scrollTop + 4 || bottom > list.scrollTop + list.clientHeight - 4) list.scrollTop = Math.max(0, bottom - list.clientHeight * 0.66);
    }
  }
  list.addEventListener('click', ev => {
    const row = ev.target.closest('button.event'); if (!row) return;
    const e = EVENTS[Number(row.dataset.i)];
    setPlaying(false);
    show(e.k);
    if (e.who) { select({ type: 'person', id: e.who }, false); focusPerson(e.who); }
    else if (e.src) { select({ type: 'place', id: e.src }, false); const s = SOURCE_BY_ID[e.src]; if (s) { const c = cellCentre(s.position[0], s.position[1]); centreOn(c.x, c.y - 10); } }
  });
  $('cats').addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    if (b.id === 'only-sel') { onlySelected = !onlySelected; b.setAttribute('aria-pressed', String(onlySelected)); applyFilter(); return; }
    const key = b.dataset.cat; catOn[key] = !(catOn[key] !== false); b.setAttribute('aria-pressed', String(catOn[key])); applyFilter();
  });

  // --------------------------------------------------------- selection --
  function select(sel, openInspector) {
    selected = sel;
    if (onlySelected) applyFilter();
    updateFocusCard();
    if (openInspector) setTab('inspector'); else if (tabNow === 'inspector') renderInspector();
    needsDraw = true;
  }
  function focusPerson(p) {
    const w = world(v); if (!present(w, p)) return;
    const pl = placeOf(p, 1); if (pl) centreOn(pl.x, pl.y - 14);
  }
  // ------------------------------------------------------------- pinning --
  // One pinned person: the camera zooms in and follows their presented position
  // every frame; the Inspector opens on them. Selecting somebody else shows that
  // person but leaves the pin alone. Survives reload within the same run: it is
  // kept in the URL hash (#pin=p04&run=<run id>), never in browser storage.
  let pinned = null;
  const PIN_RUN = String(H.run_id || 'static');
  function pinHash(p) {
    const url = new URL(location.href);
    url.hash = p ? `pin=${encodeURIComponent(p)}&run=${encodeURIComponent(PIN_RUN)}` : '';
    history.replaceState(null, '', url);
  }
  function pinFromHash() {
    const q = new URLSearchParams(location.hash.replace(/^#/, ''));
    return q.get('run') === PIN_RUN ? q.get('pin') : null;
  }
  const PIN_ZOOM = 2.5;
  const chip = document.createElement('div');
  chip.id = 'pin-chip'; chip.hidden = true;
  chip.innerHTML = `<span id="pin-text" data-testid="pin-text"></span><button type="button" id="pin-unpin" data-testid="pin-unpin">Unpin</button><button type="button" id="pin-full" data-testid="pin-full-map">Full map</button>`;
  (document.getElementById('live-bar') || document.querySelector('header.top') || document.body).append(chip);
  const fullBtn = document.createElement('button');
  fullBtn.type = 'button'; fullBtn.id = 'full-map'; fullBtn.textContent = 'Full map'; fullBtn.dataset.testid = 'full-map';
  fullBtn.title = 'Back to the default framing';
  (document.getElementById('live-bar') || document.querySelector('header.top') || document.body).append(fullBtn);
  function pinChip() {
    chip.hidden = !pinned; fullBtn.hidden = !!pinned;
    if (!pinned) return;
    const w = world(v), dead = present(w, pinned) && deadIn(w, pinned);
    $('pin-text').textContent = `Following ${pinned}` + (dead ? ` · died at tick ${w.died_at[pinned]}` : '');
  }
  function pin(p) {
    pinned = p; pinHash(p);
    follow = false; $('follow').setAttribute('aria-pressed', 'false');
    select({ type: 'person', id: p }, true);
    pinChip(); needsDraw = true;
  }
  function unpin(refit) {
    pinned = null; pinHash(null);
    pinChip(); if (refit) fit(true); needsDraw = true;
    if (tabNow === 'inspector') renderInspector();
  }
  $('pin-unpin').onclick = () => unpin(true);
  $('pin-full').onclick = () => unpin(true);
  fullBtn.onclick = () => fit(true);
  window.viewerPin = () => ({ pinned, cam: { x: cam.x, y: cam.y, z: cam.z }, target: camTarget && { x: camTarget.x, y: camTarget.y, z: camTarget.z },
    screen: pinned ? (() => { const pl = placeOf(pinned, easeT(performance.now())); return pl ? toScreen(pl.x, pl.y - 14) : null; })() : null, centre: [cw / 2, ch / 2] });
  window.viewerDeaths = () => Object.entries(world(n).died_at || {}).sort((a, b) => a[1] - b[1]);
  function describeAction(p, k) {
    const w = world(k), d = decisions(k)[p];
    if (!present(w, p)) return `not born yet — arrives at tick ${BORN[p]}`;
    if (deadIn(w, p)) return `${DIED[p] ? DIED[p].cause : 'died'} at tick ${w.died_at[p]}`;
    if (!d) return k === 0 ? 'at the start: nothing decided yet' : 'nothing recorded this tick';
    return (PHRASE[d.kind] || d.kind) + (d.target && !SOURCE_BY_ID[d.target] ? ` → ${d.target}` : d.target ? ` (${d.target})` : '');
  }
  function updateFocusCard() {
    const card = $('focus');
    if (!selected) { card.classList.remove('on'); return; }
    card.classList.add('on');
    if (selected.type === 'person') {
      const p = selected.id, w = world(v);
      $('focus-sw').style.background = COLOR[p];
      $('focus-who').textContent = p;
      const needs = present(w, p) && !deadIn(w, p) ? NEEDS.map(nd => `${nd.label.toLowerCase()} ${needLevel(w, p, nd) ?? '–'}`).join(' · ') : '';
      $('focus-what').textContent = describeAction(p, v) + (needs ? '  —  ' + needs : '');
      $('follow').hidden = false;
    } else {
      const s = SOURCE_BY_ID[selected.id];
      $('focus-sw').style.background = s ? sourceColor(s) : '#72c8ea';
      $('focus-who').textContent = selected.id;
      $('focus-what').textContent = s ? `${sourceLabel(s)} — ${stockText(s, v)}` : '';
      $('follow').hidden = true;
    }
  }
  $('focus-close').addEventListener('click', () => { follow = false; $('follow').setAttribute('aria-pressed', 'false'); select(null, false); });
  $('focus-more').addEventListener('click', () => setTab('inspector'));
  $('follow').addEventListener('click', () => { follow = !follow; $('follow').setAttribute('aria-pressed', String(follow)); if (follow && selected && selected.type === 'person') focusPerson(selected.id); });

  // ---------------------------------------------------------- inspector --
  let tabNow = 'events';
  function setTab(name) {
    tabNow = name;
    for (const t of ['events', 'inspector']) {
      $('tab-' + t).setAttribute('aria-selected', String(t === name));
      $('panel-' + t).classList.toggle('on', t === name);
    }
    if (name === 'inspector') renderInspector();
    if (name === 'events') { lastBoundary = -1; markEvents(); }
  }
  $('tab-events').addEventListener('click', () => setTab('events'));
  $('tab-inspector').addEventListener('click', () => setTab('inspector'));
  function personLink(p) { return `<button class="plink" type="button" data-person="${esc(p)}"><span class="swatch" style="background:${COLOR[p] || '#999'}"></span>${esc(p)}</button>`; }
  function needBar(need, x) {
    const max = need.max || 100, pct = v2 => clamp(100 * v2 / max, 0, 100).toFixed(1);
    const colour = x >= (need.em ?? Infinity) ? '#ff7a66' : x >= (need.at ?? Infinity) ? need.color : 'rgba(231,240,234,0.55)';
    return `<div class="need"><span class="lab">${need.label}</span><span class="track"><span class="fill" style="width:${pct(x)}%;background:${colour}"></span>`
      + (need.at !== undefined ? `<span class="mark" style="left:${pct(need.at)}%" title="${need.word} at ${need.at}"></span>` : '')
      + (need.em !== undefined ? `<span class="mark em" style="left:${pct(need.em)}%" title="emergency at ${need.em}"></span>` : '')
      + `</span><span class="val">${x} / ${max}</span></div>`;
  }
  function renderInspector() {
    const box = $('inspector');
    if (!selected) {
      box.innerHTML = `<div class="hint"><p>Click somebody on the map, or a line in <b>Happenings</b>, to follow one person through time.</p><p>Everything shown about a person is what the saved run recorded for them at this tick: where they stood, their needs, what they held, what they chose, why, and what else they could have done.</p></div>`;
      return;
    }
    if (selected.type === 'place') { renderPlace(box); return; }
    const p = selected.id, k = v, w = world(k), d = decisions(k)[p], o = outcomeOf(k, p), ob = observations(k)[p];
    const alive = present(w, p) && !deadIn(w, p);
    const state = !present(w, p) ? ['not born yet', ''] : deadIn(w, p) ? ['dead', 'dead'] : needState(w, p) === 'emergency' ? ['in an emergency', 'emergency'] : needState(w, p) === 'needy' ? ['in need', ''] : ['doing fine', ''];
    let h = `<div class="ins-head"><span class="swatch" style="background:${COLOR[p]};width:18px;height:18px"></span><span class="name">${esc(p)}</span><span class="state ${state[1]}">${state[0]}</span></div>`;
    h += `<div class="ins-nav"><button class="linkbtn" type="button" data-jump="prev">← their last event</button><button class="linkbtn" type="button" data-jump="next">their next event →</button><button class="linkbtn" type="button" data-jump="centre">show on map</button><button class="linkbtn" type="button" data-pin="${esc(p)}" data-testid="inspector-pin">${pinned === p ? 'Unpin' : 'Pin · follow with the camera'}</button></div>`;
    if (!present(w, p)) {
      h += `<div class="hint"><p>${esc(p)} is born at tick ${BORN[p]}.</p><p><button class="linkbtn" type="button" data-tick="${BORN[p]}">Go to tick ${BORN[p]}</button></p></div>`;
      box.innerHTML = h; return;
    }
    // what they did this tick
    h += '<div class="sec"><h4>This tick</h4><div class="action">';
    if (deadIn(w, p) && w.died_at[p] < k) h += `<div class="what">Died at tick ${w.died_at[p]}${DIED[p] ? ' — ' + esc(DIED[p].cause) : ''}</div><div class="why">A stone marks where it happened.</div>`;
    else if (d) {
      h += `<div class="what">${esc(describeAction(p, k))}</div><div class="why">“${esc(d.reason || '')}”</div>`;
      if (d.helped_at !== undefined) h += `<button class="linkbtn" type="button" data-tick="${d.helped_at}">See the earlier gift at tick ${d.helped_at}</button>`;
      if (d.candidates && d.candidates.length) {
        h += '<div class="alts" title="What else was open to them this tick, as recorded">' + d.candidates.map(c => {
          const sc = d.scores && d.scores[c] ? `<span class="sc">${d.scores[c].join(',')}</span>` : '';
          return `<span class="alt${c === d.kind ? ' on' : ''}">${esc(LABEL[c] || c)}${sc}</span>`;
        }).join('') + '</div>';
      }
      if (o) h += `<div class="outcome">Kernel: ${esc(o.operation)} <span class="${o.accepted ? 'ok' : 'no'}">${o.accepted ? 'accepted' : 'refused'}</span>${o.accepted ? '' : ' (' + esc(o.reason) + ')'}</div>`;
      if (deadIn(w, p)) h += `<div class="outcome no">Died at the end of this tick — ${esc(DIED[p] ? DIED[p].cause : '')}</div>`;
    } else h += `<div class="why">${k === 0 ? 'The world has just begun; nobody has decided anything yet.' : 'No decision recorded this tick.'}</div>`;
    h += '</div></div>';
    const sourceReports = (w.source_reports || {})[p] || [];
    if (sourceReports.length) h += '<div class="sec"><h4>Food reports heard</h4>' + sourceReports.map(([sid, speaker, seen, heard]) => `<div>${personLink(speaker)} saw ${esc(sid)} empty at tick ${seen}; heard at tick ${heard}. Expires at tick ${seen + C.empty_source_ticks}.</div>`).join('') + '</div>';
    const emptyMemory = (w.empty_sources || {})[p] || [];
    const provisionTrip = (w.provision_trips || {})[p];
    const expectedFood = (w.food_expected || {})[p];
    if (expectedFood) h += `<div class="sec"><h4>Expecting food</h4><div>${personLink(expectedFood[0])} said they were getting food at tick ${expectedFood[1]}.</div><div class="hint">${Math.max(0, expectedFood[1] + C.food_expect_ticks - w.tick)} ticks before the expectation expires. Only a new optional cache trip is postponed; their own needs and helping still come first.</div></div>`;
    if (ob?.witnessed_deaths?.length) {
      h += `<div class="sec"><h4>Witnessed deaths</h4><div class="people-links">${ob.witnessed_deaths.map(personLink).join('')}</div>`;
      if (ob.food_expectation_end) h += `<div class="hint">Stopped expecting food: ${esc(ob.food_expectation_end)}.</div>`;
      h += '</div>';
    }
    if (provisionTrip) h += '<div class="sec"><h4>Food for home</h4><div>' + (provisionTrip === 'gather' ? 'Gathering for a low shared cache' : 'Returning after collecting food') + '</div><div class="hint">Own needs and helping can interrupt this outing. Spare food is deposited after reaching home.</div></div>';
    const savedReason = d && d.reason ? `<div class="hint">Saved reason: “${esc(d.reason)}”</div>` : '';
    const yardWork = (w.yard_work || {})[p];
    if (yardWork) h += `<div class="sec"><h4>Wood yard under construction</h4><div>Site (${yardWork[0]}, ${yardWork[1]}): work tick ${yardWork[2]} of ${(C.yard_rules || {}).work || '?'} done; carrying ${woodHeld(k, p)} wood.</div>${savedReason}<div class="hint">Wood is paid through settlement before work ticks 0 and 2. Needs and helping come first; if the builder dies the unfinished yard is dropped.</div></div>`;
    const supplyTask = (w.supply_tasks || {})[p];
    if (supplyTask) h += `<div class="sec"><h4>Wood supply task</h4><div>${supplyTask[0] === 'fetch' ? `Fetching up to ${supplyTask[3]} wood from ${esc(supplyTask[2])}` : `Carrying ${woodHeld(k, p)} wood to ${esc(supplyTask[1])}`}; for ${esc(supplyTask[1])}, started tick ${supplyTask[4]}${supplyTask[5] ? '; retried another grove' : ''}.</div>${savedReason}<div class="hint">The task keeps its yard and grove. Needs, helping and housing come first; it ends on the deposit, on empty groves, at a full yard or at death.</div></div>`;
    const axeWork = (w.axe_work || {})[p];
    if (axeWork) h += `<div class="sec"><h4>Axe crafting ${axeWork[0]}/${(C.axe_rules || {}).work || 3}</h4><div>Planned at tick ${axeWork[1]}; carrying ${woodHeld(k, p)} wood, ${stoneHeld(k, p)} stone.</div>${savedReason}<div class="hint">1 wood is paid before craft tick 0 and 1 stone before craft tick 1, at the crafter's own shelter. A refused payment gives no progress.</div></div>`;
    if ((w.axes || []).includes(p)) h += `<div class="sec"><h4>Tools</h4><div>axe — gathers up to ${(C.axe_rules || {}).wood_pack || 5} wood per claim instead of ${(C.axe_rules || {}).hand_pack || 3}.</div><div class="hint">No durability or repair. It stays with its owner, even in death.</div></div>`;
    if (C.yard === 'on') {
      const WORK_KINDS = new Set(['yard_started', 'yard_finished', 'yard_payment_refused', 'supply_start', 'supply_end', 'yard_deposit', 'yard_deposit_refused', 'yard_take', 'yard_take_refused', 'stone_taken', 'stone_refused', 'axe_planned', 'axe_given_up', 'axe_payment', 'axe_payment_refused', 'axe_made', 'axe_gather']);
      const work = (EV_OF[p] || []).filter(i => EVENTS[i].k <= k && WORK_KINDS.has(EVENTS[i].kind)).map(i => EVENTS[i]);
      const count = kind => work.filter(e => e.kind === kind).length;
      const summary = `${(w.deliveries || {})[p] || 0} deliver${((w.deliveries || {})[p] || 0) === 1 ? 'y' : 'ies'}, ${count('yard_take')} withdrawal${count('yard_take') === 1 ? '' : 's'}, ${count('yard_finished')} yard${count('yard_finished') === 1 ? '' : 's'} built, ${count('axe_made')} axe${count('axe_made') === 1 ? '' : 's'}, ${count('supply_end')} task${count('supply_end') === 1 ? '' : 's'} ended`;
      let current = '';
      if (supplyTask) current = `<div><b>Supply task</b> — ${esc(supplyTask[0])} phase; to ${esc(supplyTask[1])} from ${esc(supplyTask[2])}; wanted ${supplyTask[3]}; carrying ${woodHeld(k, p)} wood.</div>`;
      else if (yardWork) current = `<div><b>Yard construction</b> — site (${yardWork[0]}, ${yardWork[1]}); progress ${yardWork[2]}/${(C.yard_rules || {}).work || 4}; carrying ${woodHeld(k, p)} wood.</div>`;
      else if (axeWork) current = `<div><b>Axe plan</b> — craft ${axeWork[0]}/${(C.axe_rules || {}).work || 3}; carrying ${woodHeld(k, p)} wood, ${stoneHeld(k, p)} stone.</div>`;
      else if (C.building === 'on' && (w.built || {})[p] !== undefined && (w.built || {})[p] < C.build_ticks) current = `<div><b>Shelter construction</b> — progress ${(w.built || {})[p]}/${C.build_ticks}; carrying ${woodHeld(k, p)} wood.</div>`;
      else current = '<div class="hint">No task under way.</div>';
      h += `<div class="sec"><h4>Work</h4><div class="hint">${summary}</div>${current}${savedReason}<h4>Work history</h4>` +
        (work.length ? work.slice(-30).map(e => `<button class="mini-ev" type="button" data-tick="${e.k}"><span class="evtick">t${e.k}</span><span>${esc(e.text)}</span></button>`).join('') : '<div class="hint">Nothing recorded yet.</div>') +
        '<div class="hint">Counted from recorded decisions and outcomes only. Wood is fungible: who later used deposited wood is shown in the yard\'s own ledger, not here.</div></div>';
    }
    if ((w.deliveries || {})[p]) h += `<div class="sec"><h4>Wood delivered</h4><div>${w.deliveries[p]} deposit${w.deliveries[p] === 1 ? '' : 's'} into yards so far.</div></div>`;
    if (emptyMemory.length) h += '<div class="sec"><h4>Empty food remembered</h4>' + emptyMemory.map(([sid, when]) => `<div>${esc(sid)}: empty at tick ${when}; ${Math.max(0, C.empty_source_ticks - ((w.tick || 0) - when))} ticks until forgotten without another sighting</div>`).join('') + '</div>';
    // needs
    h += '<div class="sec"><h4>Needs</h4>' + NEEDS.map(nd => { const x = needLevel(w, p, nd); return x === null ? '' : needBar(nd, x); }).join('') + '</div>';
    // facts
    const pos = w.positions[p], home = homeOf(w, p), key = pos.join(','), homeKey = home ? home.join(',') : '';
    const ground = [];
    if (ROUGH.has(key)) ground.push('rough ground' + (((w.held || {})[p]) ? ': the next step waits a tick' : ''));
    if (SPOTS.has(key)) ground.push('a shelter spot');
    if (sheltersAt(k).has(key)) ground.push('under a shelter');
    if (key === homeKey) ground.push('at home');
    const work = (w.built || {})[p] || 0;
    const homeState = sheltersAt(k).has(homeKey) ? 'a finished shelter stands there' : work ? `shelter ${work} of ${BUILD_TICKS} ticks built` : BUILD_TICKS ? 'no shelter yet' : '';
    const facts = [
      ['Standing', `(${pos.join(', ')})${ground.length ? ' — ' + ground.join(', ') : ''}`],
      ['Home', home ? `(${home.join(', ')})${homeState ? ' — ' + homeState : ''}` : '–'],
      ['Carrying', `${food(k, p)} food${C.water === 'on' ? `, ${waterHeld(k, p)} water` : ''}${C.wood === 'on' ? `, ${woodHeld(k, p)} wood` : ''}${C.stone === 'on' ? `, ${stoneHeld(k, p)} stone` : ''}`],
    ];
    const trait = ((w.yield_at || {})[p]);
    if (trait !== undefined) facts.push(['Crowd trait', `stands back from a crowd of ${trait}`]);
    const knownRough = roughMemory(w, p).length;
    if (knownRough) facts.push(['Map memory', `${knownRough} rough cell${knownRough === 1 ? '' : 's'} remembered`]);
    if (BORN[p]) facts.push(['Born', `tick ${BORN[p]}`]);
    const lived = ageOf(w, p);
    if (C.birth_spacing) {
      const remaining = Math.max(0, ((w.birth_ready || {})[p] || 0) - w.tick);
      facts.push(['Birth recovery', remaining ? remaining + ' ticks remaining' : 'not recovering']);
    }
    if (ADULT_AT !== null && lived !== null) facts.push(['Age', lived < ADULT_AT ? `a child: ${lived} of the ${ADULT_AT} ticks it takes to grow up` : 'grown']);
    h += '<div class="sec"><h4>Facts</h4><div class="kv">' + facts.map(([a, b]) => `<span class="k">${a}</span><span>${esc(b)}</span>`).join('') + '</div></div>';
    // errands and company, straight from the world state
    const links = [];
    if (C.homes === 'on') {
      const housemates = people.filter(other => other !== p && present(w, other) && !deadIn(w, other) && homeOf(w, other)?.join(',') === homeKey);
      if (housemates.length) links.push(`Shares home with ${housemates.map(personLink).join(', ')}`);
      if ((w.home_targets || {})[p]) links.push(`Chosen home at (${w.home_targets[p].join(', ')})`);
      if ((w.home_settled || {})[p]) links.push(`Settled into this home at tick ${w.home_settled[p]}`);
      if (C.relocation === 'on') {
        links.push(`Home strain: ${(w.home_strain || {})[p] || 0} / ${C.relocation_rules.difficult_outings} costly outings`);
        links.push(`Supply effort this outing: ${(w.home_trip_ticks || {})[p] || 0} ticks`);
        const known = (w.shelter_memory || {})[p] || [];
        if (known.length) links.push(`Shelters remembered with room: ${known.map(pos => '(' + pos.join(', ') + ')').join(', ')}; distant places may have filled`);
      }
    }
    const req = (w.requests || {})[p]; if (req) links.push(`Asked ${personLink(req)} for food — the answer comes next tick`);
    for (const a in (w.requests || {})) if (w.requests[a] === p) links.push(`${personLink(a)} asked them for food`);
    const owes = (w.promises || {})[p];
    if (owes) links.push(deadIn(w, p) || deadIn(w, owes)
      ? `Inactive promise to ${personLink(owes)}: ${deadIn(w, p) ? 'helper' : 'recipient'} died`
      : `Agreed to bring ${personLink(owes)} food`);
    for (const hlp in (w.promises || {})) if (w.promises[hlp] === p) links.push(deadIn(w, hlp) || deadIn(w, p)
      ? `Inactive promise from ${personLink(hlp)}: ${deadIn(w, hlp) ? 'helper' : 'recipient'} died`
      : `${personLink(hlp)} agreed to bring them food`);
    for (const pair in (w.together || {})) {
      const [a, b] = pair.split('|'); if (a !== p && b !== p) continue;
      const cnt = w.together[pair]; if (!cnt) continue;
      links.push(`Beside ${personLink(a === p ? b : a)} for ${cnt} tick${cnt === 1 ? '' : 's'} running`);
    }
    const kidsOf = CHILDREN[p] || [];
    if (PARENT[p] || kidsOf.length) {
      const fam = [];
      if (PARENT[p]) fam.push(`${SECOND_PARENT[p] ? 'Parents' : 'Parent'} ` + parentsOf(p).map(q => personLink(q) + (deadIn(w, q) ? ' (died)' : '')).join(' and '));
      const born = kidsOf.filter(q => present(w, q));
      if (born.length) fam.push('Children ' + born.map(q => personLink(q) + (deadIn(w, q) ? ' (died)' : isChild(w, q) ? ' (a child)' : '')).join(' '));
      h += '<div class="sec"><h4>Family</h4>' + fam.map(x => `<div style="margin:4px 0">${x}</div>`).join('') + '</div>';
    }
    const foodMemories = (w.food_memory || {})[p] || [];
    if (foodMemories.length) {
      h += '<div class="sec"><h4>People who fed me</h4>' + foodMemories.map(([donor, tick]) =>
        `<div style="margin:4px 0">${personLink(donor)}${deadIn(w, donor) ? ' (died)' : ''} — gave food at <button class="linkbtn" type="button" data-tick="${tick}">tick ${tick}</button></div>`
      ).join('') + '<div class="hint">Up to four recent helpers. Remembering someone does not reveal where they are.</div></div>';
    }
    if (links.length) h += '<div class="sec"><h4>With others</h4>' + links.map(x => `<div style="margin:4px 0">${x}</div>`).join('') + '</div>';
    if (ob && alive) {
      const seen = (ob.sees || (ob.others || []).map(x => x.id)) || [];
      const stocks = ob.seen_stock ? Object.entries(ob.seen_stock).map(([id, s]) => `${id} ${s}`) : [];
      if (!ob.seen_stock && ob.source_food !== undefined) stocks.push(`food ${ob.source_food}`);
      if (!ob.seen_stock && ob.water_stock !== undefined) stocks.push(`water ${ob.water_stock}`);
      h += `<div class="sec"><h4>Could see at the start of the tick</h4><div class="people-links">${seen.length ? seen.map(personLink).join('') : '<span class="hint">nobody</span>'}</div>${stocks.length ? `<div class="hint" style="margin-top:6px">stock in view: ${esc(stocks.join(', '))}</div>` : ''}</div>`;
    }
    // needs over their life
    h += '<div class="sec"><h4>Needs over the run</h4><canvas id="life" aria-label="Needs over the run"></canvas></div>';
    // errands they were part of
    const mine = THREADS.filter(th => (th.asker === p || th.helper === p) && th.asked <= k);
    if (mine.length) {
      h += '<div class="sec"><h4>Asking for food</h4>' + mine.slice(-6).reverse().map(th => {
        const who = th.asker === p ? `asked <b>${esc(th.helper)}</b>` : `<b>${esc(th.asker)}</b> asked them`;
        let end = '';
        if (th.answer === 'interrupted') end = th.ended <= k ? `${esc(th.end)} t${th.ended}` : 'waiting';
        else if (th.answer === 'no answer') end = th.answered <= k ? `no answer${th.busy ? ' (' + esc(th.busy) + ')' : ''}` : 'waiting';
        else if (th.answer === 'agreed') end = th.answered <= k ? (th.ended && th.ended <= k ? `agreed t${th.answered}, ${esc(th.end)} t${th.ended}` : `agreed t${th.answered}, on the way`) : 'waiting';
        else end = 'waiting';
        return `<div class="thread">t${th.asked}: ${who} — ${end}${th.detours ? `, turned aside ${th.detours}×` : ''}</div>`;
      }).join('') + '</div>';
    }
    // recent events
    const mineEv = (EV_OF[p] || []).filter(i => EVENTS[i].k <= k).slice(-10).reverse();
    h += '<div class="sec"><h4>Recently</h4>' + (mineEv.length ? mineEv.map(i => { const e = EVENTS[i]; return `<button class="mini-ev" type="button" data-tick="${e.k}"><span class="evtick">t${e.k}</span><span>${esc(e.text)}</span></button>`; }).join('') : '<div class="hint">Nothing recorded about them yet.</div>') + '</div>';
    box.innerHTML = h;
    drawLife(p);
  }
  function renderPlace(box) {
    const s = SOURCE_BY_ID[selected.id]; if (!s) { box.innerHTML = ''; return; }
    const w = world(v), st = stockOf(v, s.id);
    if (s.store && st === null) { box.innerHTML = '<div class="hint">This home cache has not been created yet.</div>'; return; }
    if (s.yard && st === null) { box.innerHTML = '<div class="hint">This wood yard has not been finished yet.</div>'; return; }
    const here = people.filter(p => present(w, p) && !deadIn(w, p) && w.positions[p][0] === s.position[0] && w.positions[p][1] === s.position[1]);
    let h = `<div class="ins-head"><span class="swatch" style="background:${sourceColor(s)};width:18px;height:18px"></span><span class="name">${esc(s.id)}</span><span class="state">${sourceLabel(s)}</span></div>`;
    const condition = (w.patch_condition || {})[s.id];
    const allowance = w.season ? C.season_growth[w.season] : C.renewal_amount;
    const renewal = s.fishing ? `+${C.fishing_rules.renewal} every ${C.fishing_rules.renewal_every} ticks in either season; cast then catch` : s.store ? 'None — food must be carried here' : s.yard ? 'None — wood must be carried here' : s.kind === 'stone' ? 'None — stone does not renew' : s.kind === 'wood' ? `+${C.wood_rules.renewal} every ${C.wood_rules.renewal_every} ticks` : s.kind === 'food' ? `Up to +${allowance} every ${C.renewal_every} ticks${w.season ? ` in the ${esc(w.season)} season` : ''}${condition !== undefined ? '; half when worn, rounded up' : ''}` : `+${C.water_renewal_amount} every ${C.water_renewal_every} ticks`;
    h += `<div class="sec"><div class="kv"><span class="k">Where</span><span>(${s.position.join(', ')})</span><span class="k">Stock now</span><span>${stockText(s, v)}</span><span class="k">Renews</span><span>${renewal}</span></div></div>`;
    if (condition !== undefined) h += `<div class="sec"><h4>Patch condition</h4><div>${condition} / ${C.patch_rules.condition_max} — ${condition < C.patch_rules.full_growth_at ? 'worn patch' : 'healthy patch'}</div><div class="hint">Each food harvested costs ${C.patch_rules.wear_per_unit} condition. A tick without a harvest restores ${C.patch_rules.recovery_per_tick}. Full growth returns at ${C.patch_rules.full_growth_at}.</div></div>`;
    if (s.store) h += `<div class="sec"><h4>Shared home cache</h4><div>${C.homes === 'on' ? 'Residents put' : personLink(s.resident) + ' puts'} spare food here after building their shelter, keeping one meal. Nearby people can walk here and collect it. Deposited food becomes available next tick.</div></div>`;
    if (s.yard) {
      const ledger = (EV_AT_SRC[s.id] || []).filter(i => EVENTS[i].k <= v && (EVENTS[i].kind === 'yard_deposit' || EVENTS[i].kind === 'yard_take')).map(i => EVENTS[i]);
      let running = 0;
      const rows = ledger.map(e => { running += e.kind === 'yard_deposit' ? e.amount : -e.amount; return `<div class="kv"><span class="k">t${e.k}</span><span>${personLink(e.who)} ${e.kind === 'yard_deposit' ? 'put in' : 'took'} ${e.amount} → ${running}</span></div>`; }).join('');
      h += `<div class="sec"><h4>Yard ledger</h4>${rows || '<div class="hint">No deposits or withdrawals yet.</div>'}<div class="hint">Every accepted deposit and withdrawal in tick order, with the running stock. Same-tick deposits may overshoot the capacity of ${(C.yard_rules || {}).capacity || 6} by one pack each.</div></div>`;
    }
    h += `<div class="sec"><h4>Standing here</h4><div class="people-links">${here.length ? here.map(personLink).join('') : '<span class="hint">nobody</span>'}</div></div>`;
    const evs = (EV_AT_SRC[s.id] || []).filter(i => EVENTS[i].k <= v).slice(-12).reverse();
    h += '<div class="sec"><h4>Recently</h4>' + (evs.length ? evs.map(i => { const e = EVENTS[i]; return `<button class="mini-ev" type="button" data-tick="${e.k}"><span class="evtick">t${e.k}</span><span>${esc(e.text)}</span></button>`; }).join('') : '<div class="hint">Nothing yet.</div>') + '</div>';
    box.innerHTML = h;
  }
  function drawLife(p) {
    const c = $('life'); if (!c) return;
    const r = c.getBoundingClientRect(), s = Math.min(window.devicePixelRatio || 1, 2);
    c.width = Math.max(1, Math.round(r.width * s)); c.height = Math.max(1, Math.round(r.height * s));
    const g = c.getContext('2d'); g.setTransform(s, 0, 0, s, 0, 0);
    const W2 = r.width, H2 = r.height, pad = 4;
    const xs = k => pad + (W2 - 2 * pad) * (n ? k / n : 0);
    const top = Math.max(...NEEDS.map(nd => nd.max || 1));
    const ys = val => H2 - pad - (H2 - 2 * pad) * clamp(val / top, 0, 1);
    for (const nd of NEEDS) if (nd.em !== undefined) { g.strokeStyle = 'rgba(255,122,102,0.25)'; g.setLineDash([2, 3]); line(g, pad, ys(nd.em), W2 - pad, ys(nd.em)); g.setLineDash([]); break; }
    for (const nd of NEEDS) {
      g.strokeStyle = nd.color; g.lineWidth = 1.3; g.beginPath(); let pen = false;
      for (let k = 0; k <= n; k++) {
        const w = world(k); if (!present(w, p)) { pen = false; continue; }
        const x = needLevel(w, p, nd); if (x === null) continue;
        if (pen) g.lineTo(xs(k), ys(x)); else { g.moveTo(xs(k), ys(x)); pen = true; }
        if (deadIn(w, p)) break;
      }
      g.stroke();
    }
    g.strokeStyle = '#ffe3a3'; g.lineWidth = 1.2; line(g, xs(v), 2, xs(v), H2 - 2);
  }
  $('inspector').addEventListener('click', ev => {
    const b = ev.target.closest('button'); if (!b) return;
    if (b.dataset.pin) { if (pinned === b.dataset.pin) unpin(true); else pin(b.dataset.pin); return; }
    if (b.dataset.person) { select({ type: 'person', id: b.dataset.person }, true); focusPerson(b.dataset.person); return; }
    if (b.dataset.tick !== undefined) { setPlaying(false); show(Number(b.dataset.tick)); return; }
    if (b.dataset.jump && selected && selected.type === 'person') {
      const list2 = EV_OF[selected.id] || [];
      if (b.dataset.jump === 'centre') { focusPerson(selected.id); return; }
      setPlaying(false);
      if (b.dataset.jump === 'next') { const i = list2.find(j => EVENTS[j].k > v); if (i !== undefined) show(EVENTS[i].k); }
      else { let pick; for (const j of list2) if (EVENTS[j].k < v) pick = j; if (pick !== undefined) show(EVENTS[pick].k); }
      if (follow) focusPerson(selected.id);
    }
  });

  // ------------------------------------------------------------- layers --
  function bindLayers() {
    $('layers').addEventListener('change', ev => {
      const el = ev.target; const key = el.dataset.layer; if (!key) return;
      LAYERS[key] = el.type === 'checkbox' ? el.checked : el.value;
      if (key === 'rough' || key === 'spots') { computeElevation(); terrainDirty = true; }
      needsDraw = true;
    });
    $('layers-btn').addEventListener('click', () => {
      const on = !$('layers').classList.contains('on');
      $('layers').classList.toggle('on', on); $('layers-btn').setAttribute('aria-pressed', String(on)); $('layers-btn').setAttribute('aria-expanded', String(on));
    });
  }

  // ------------------------------------------------------ pointer input --
  const tip = $('tip');
  let drag = null; const pointers = new Map(); let pinch = null;
  function pick(sx, sy) {
    const [ix, iy] = toIso(sx, sy);
    let best = null, bd = Infinity;
    for (const hh of hits) { const dd = Math.hypot(hh.x - ix, (hh.y - iy) * 1.1); if (dd < hh.r && dd < bd) { bd = dd; best = hh.p; } }
    if (best) return { type: 'person', id: best };
    const [gx, gy] = toGrid(ix, iy + 3);
    const x = Math.floor(gx), y = Math.floor(gy);
    if (x < 0 || y < 0 || x >= GW || y >= GH) return null;
    return { type: 'cell', x, y, key: x + ',' + y };
  }
  function tipFor(hit) {
    const w = world(v);
    if (hit.type === 'person') {
      const p = hit.id, needs = NEEDS.map(nd => `${nd.label.toLowerCase()} ${needLevel(w, p, nd) ?? '–'}`).join(' · ');
      const carry = `carrying ${food(v, p)} food` + (C.water === 'on' ? `, ${waterHeld(v, p)} water` : '') + (C.wood === 'on' ? `, ${woodHeld(v, p)} wood` : '');
      const kin = (isChild(w, p) ? 'a child' : '') + (PARENT[p] ? (isChild(w, p) ? ' of ' : 'child of ') + parentsOf(p).join(' and ') : '');
      return `<b>${esc(p)}</b> — ${esc(describeAction(p, v))}\n${esc(needs)}\n${esc(carry)}${kin ? '\n' + esc(kin) : ''}`;
    }
    const out = [], key = hit.key;
    const src = SOURCE_AT.get(key);
    if (src && stockOf(v, src.id) !== null) out.push(`<b>${esc(src.id)}</b> — ${sourceLabel(src)}, ${stockText(src, v)}`);
    if (sheltersAt(v).has(key)) { const o = ownerOfCell(key); out.push(`A shelter${o ? ' at the home of ' + esc(o) : ''}: hunger and thirst rise slower here`); }
    else { const o = ownerOfCell(key); if (o && present(w, o)) out.push(`Home of ${esc(o)}${(w.built || {})[o] ? ` — shelter ${(w.built || {})[o]} of ${BUILD_TICKS} ticks built` : ''}`); }
    if (ROUGH.has(key)) out.push('Rough ground: an extra tick to cross');
    if (SPOTS.has(key)) out.push('Shelter spot: hunger and thirst rise slower here');
    const dead = people.filter(p => present(w, p) && deadIn(w, p) && w.died_at[p] < v && w.positions[p].join(',') === key);
    if (dead.length) out.push(`${dead.map(esc).join(', ')} died here`);
    return out.join('\n');
  }
  canvas.addEventListener('pointerdown', ev => {
    canvas.setPointerCapture(ev.pointerId);
    pointers.set(ev.pointerId, { x: ev.offsetX, y: ev.offsetY });
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), z: cam.z }; drag = null; return; }
    drag = { x: ev.offsetX, y: ev.offsetY, cx: cam.x, cy: cam.y, moved: false };
  });
  canvas.addEventListener('pointermove', ev => {
    if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, { x: ev.offsetX, y: ev.offsetY });
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()], d2 = Math.hypot(a.x - b.x, a.y - b.y);
      zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, (pinch.z * d2 / pinch.d) / cam.z); return;
    }
    if (drag) {
      const dx = ev.offsetX - drag.x, dy = ev.offsetY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.moved) { cam.x = drag.cx - dx / cam.z; cam.y = drag.cy - dy / cam.z; userMoved = true; camTarget = null; needsDraw = true; canvas.classList.add('dragging'); tip.classList.remove('on'); return; }
    }
    const hit = pick(ev.offsetX, ev.offsetY);
    const hp = hit && hit.type === 'person' ? hit.id : null;
    if (hp !== hovered) { hovered = hp; needsDraw = true; }
    const html = hit ? tipFor(hit) : '';
    canvas.classList.toggle('pointing', !!hp);
    if (html) {
      tip.innerHTML = html; tip.classList.add('on');
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = clamp(ev.offsetX + 14, 6, cw - tw - 6) + 'px'; tip.style.top = clamp(ev.offsetY + 14, 6, ch - th - 6) + 'px';
    } else tip.classList.remove('on');
  });
  function endPointer(ev) {
    pointers.delete(ev.pointerId);
    if (pointers.size < 2) pinch = null;
    canvas.classList.remove('dragging');
    if (drag && !drag.moved && ev.type === 'pointerup') {
      const hit = pick(ev.offsetX, ev.offsetY);
      if (hit && hit.type === 'person') select({ type: 'person', id: hit.id }, true);
      else if (hit && SOURCE_AT.has(hit.key)) select({ type: 'place', id: SOURCE_AT.get(hit.key).id }, true);
      else if (hit) { const o = ownerOfCell(hit.key); if (o && present(world(v), o)) select({ type: 'person', id: o }, true); else select(null, false); }
      else select(null, false);
    }
    drag = null;
  }
  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('pointerleave', () => { tip.classList.remove('on'); if (hovered) { hovered = null; needsDraw = true; } });
  canvas.addEventListener('wheel', ev => { ev.preventDefault(); zoomAt(ev.offsetX, ev.offsetY, Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0016))); }, { passive: false });

  $('zoom-in').addEventListener('click', () => zoomAt(cw / 2, ch / 2, 1.25));
  $('zoom-out').addEventListener('click', () => zoomAt(cw / 2, ch / 2, 0.8));
  $('fit').addEventListener('click', () => fit(true));
  $('reset').addEventListener('click', () => { follow = false; $('follow').setAttribute('aria-pressed', 'false'); drift = false; $('drift').setAttribute('aria-pressed', 'false'); fit(true); });
  $('drift').addEventListener('click', () => { drift = !drift && !REDUCED; $('drift').setAttribute('aria-pressed', String(drift)); });
  if (REDUCED) { $('drift').disabled = true; $('drift').title = 'Off: your system asks for reduced motion'; }

  // ----------------------------------------------------------- timeline --
  slider.addEventListener('input', () => { show(Number(slider.value)); });
  playBtn.addEventListener('click', () => setPlaying(!playing));
  $('prev').addEventListener('click', () => { setPlaying(false); show(v - 1, { tween: true, stepping: true }); });
  $('next').addEventListener('click', () => { setPlaying(false); show(v + 1, { tween: true, stepping: true }); });
  $('start').addEventListener('click', () => { setPlaying(false); show(0); });
  $('end').addEventListener('click', () => { setPlaying(false); show(n); });
  $('speed').addEventListener('change', ev => { tps = Number(ev.target.value) || 4; });
  document.addEventListener('keydown', ev => {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const el = ev.target, tag = el && el.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable) || (tag === 'INPUT' && el.type !== 'range' && el.type !== 'checkbox')) return;
    const onRange = tag === 'INPUT' && el.type === 'range', onButton = tag === 'BUTTON' || (tag === 'INPUT' && el.type === 'checkbox');
    if (ev.key === ' ' || ev.key === 'Spacebar') { if (onButton) return; ev.preventDefault(); setPlaying(!playing); return; }
    if (onRange) return;
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); setPlaying(false); show(v - 1, { tween: true, stepping: true }); }
    else if (ev.key === 'ArrowRight') { ev.preventDefault(); setPlaying(false); show(v + 1, { tween: true, stepping: true }); }
    else if (ev.key === 'Home') { ev.preventDefault(); setPlaying(false); show(0); }
    else if (ev.key === 'End') { ev.preventDefault(); setPlaying(false); show(n); }
    else if (ev.key === 'Escape' && selected) { select(null, false); }
  });
  function drawStrip() {
    const c = $('strip'), r = c.getBoundingClientRect(), s = Math.min(window.devicePixelRatio || 1, 2);
    c.width = Math.max(1, Math.round(r.width * s)); c.height = Math.max(1, Math.round(r.height * s));
    const g = c.getContext('2d'); g.setTransform(s, 0, 0, s, 0, 0);
    const W2 = r.width, H2 = r.height, xs = k => 2 + (W2 - 4) * (n ? k / n : 0);
    g.fillStyle = 'rgba(255,255,255,0.035)'; rrect(g, 0, 0, W2, H2, 8); g.fill();
    const alive = COUNTS.alive || [], peak = Math.max(1, ...(COUNTS.people || [1]));
    const grad = g.createLinearGradient(0, 0, 0, H2); grad.addColorStop(0, 'rgba(110,200,170,0.45)'); grad.addColorStop(1, 'rgba(110,200,170,0.05)');
    g.beginPath(); g.moveTo(xs(0), H2);
    for (let k = 0; k <= n; k++) g.lineTo(xs(k), H2 - 4 - (H2 - 12) * (alive[k] || 0) / peak);
    g.lineTo(xs(n), H2); g.closePath(); g.fillStyle = grad; g.fill();
    g.strokeStyle = 'rgba(140,220,190,0.8)'; g.lineWidth = 1; g.beginPath();
    for (let k = 0; k <= n; k++) { const y = H2 - 4 - (H2 - 12) * (alive[k] || 0) / peak; if (k) g.lineTo(xs(k), y); else g.moveTo(xs(k), y); }
    g.stroke();
    for (const e of EVENTS) {
      if (e.kind === 'death') { g.fillStyle = 'rgba(255,148,131,0.9)'; g.fillRect(xs(e.k) - 0.5, H2 - 7, 1.5, 6); }
      else if (e.kind === 'birth') { g.fillStyle = 'rgba(159,220,170,0.95)'; g.fillRect(xs(e.k) - 0.5, 1, 1.5, 6); }
      else if (e.kind === 'delivered' || e.kind === 'gave' || e.kind === 'agree' || e.kind === 'fed_child') { g.fillStyle = 'rgba(241,197,110,0.95)'; g.beginPath(); g.arc(xs(e.k), H2 / 2, 1.6, 0, Math.PI * 2); g.fill(); }
    }
  }

  // ------------------------------------------------------ under the hood --
  // The detailed record the earlier viewer showed, kept for anyone checking a
  // tick by hand: the people table, the scored choices, the kernel's
  // settlement, and the run-wide counts. Computed the first time it is opened.
  let deepReady = false, series = null, totals = null, traitKeys = [];
  function traitOf(p) { const t2 = (world(n).yield_at || {})[p]; return t2 === undefined ? null : t2; }
  function hungerBand(h, dead) { return dead ? 'dead' : h >= C.death_at ? 'dead' : h >= C.emergency_at ? 'emergency' : h >= C.hungry_at ? 'hungry' : 'fed'; }
  function prepareDeep() {
    series = { stock: [], hunger: {}, crowd: [] }; for (const p of people) series.hunger[p] = [];
    totals = { claimsOk: 0, claimsNo: 0, eats: 0, emergencyTicks: 0, deaths: [], sawOther: 0, sawSource: 0, yields: 0, emergencyBy: {}, deathsBy: {}, yieldTicks: [] };
    const foodCells = new Set(FOOD.map(f => f.position.join(',')));
    for (let k = 0; k <= n; k++) {
      const w = world(k); let s = 0; for (const f of FOOD) s += stockOf(k, f.id) || 0; series.stock.push(s);
      let crowd = 0;
      for (const p of people) {
        if (!present(w, p)) { series.hunger[p].push(null); continue; }
        const dead = deadIn(w, p); series.hunger[p].push(dead ? null : w.hunger[p]);
        if (!dead && foodCells.has(w.positions[p].join(','))) crowd++;
        if (k < n && !dead && w.hunger[p] >= C.emergency_at) { totals.emergencyTicks++; const tr = traitOf(p); if (tr !== null) totals.emergencyBy[tr] = (totals.emergencyBy[tr] || 0) + 1; }
      }
      series.crowd.push(crowd);
      if (k >= 1) {
        for (const o of ((ticks[k - 1] || {}).record || {}).outcomes || []) { if (o.operation === 'claim') { if (o.accepted) totals.claimsOk++; else totals.claimsNo++; } else if (o.operation === 'consume' && o.accepted) totals.eats++; }
        const block = (ticks[k - 1] || {}).observations || {};
        for (const p of Object.keys(block)) { if ((block[p].sees || block[p].others || []).length) totals.sawOther++; if (Object.prototype.hasOwnProperty.call(block[p], 'source_food')) totals.sawSource++; }
        let anyYield = false; const ds = decisions(k); for (const p in ds) if (ds[p].kind === 'yield') { totals.yields++; anyYield = true; }
        if (anyYield) totals.yieldTicks.push(k);
      }
    }
    const last = world(n);
    for (const p of people) if (present(last, p) && deadIn(last, p)) { totals.deaths.push([p, last.died_at[p]]); const tr = traitOf(p); if (tr !== null) totals.deathsBy[tr] = (totals.deathsBy[tr] || 0) + 1; }
    totals.deaths.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
    traitKeys = [...new Set(people.map(traitOf).filter(x => x !== null))].sort((a, b) => a - b);
    const fmtBy = map => traitKeys.map(x => x + ':' + (map[x] || 0)).join(', ') || 'none';
    $('chart').innerHTML = drawChart();
    $('totals').innerHTML = `<span>whole run:</span><span>claims accepted <b>${totals.claimsOk}</b></span><span>claims denied <b>${totals.claimsNo}</b></span><span>units eaten or drunk <b>${totals.eats}</b></span><span>yield events <b>${totals.yields}</b></span><span>emergency person-ticks <b>${totals.emergencyTicks}</b>${traitKeys.length ? ' (by yield_at ' + fmtBy(totals.emergencyBy) + ')' : ''}</span><span>person-ticks with another in view <b>${totals.sawOther}</b></span><span>person-ticks with source in view <b>${totals.sawSource}</b></span><span>deaths <b>${totals.deaths.length}</b>${totals.deaths.length ? ' (' + totals.deaths.slice(0, 40).map(x => esc(x[0]) + ' t' + x[1]).join(', ') + (totals.deaths.length > 40 ? ', …' : '') + ')' : ''}${traitKeys.length ? '; by yield_at ' + fmtBy(totals.deathsBy) : ''}</span>`;
    deepReady = true;
  }
  function drawChart() {
    const W2 = 900, H2 = 170, pad = 30, maxH = Math.max(C.death_at || 1, (C.source_cap || 0) * FOOD.length, people.length, 1);
    const xs = k => pad + (W2 - pad - 8) * (n ? k / n : 0), ys = x => H2 - 18 - (H2 - 30) * x / maxH;
    let s = `<svg class="chart" viewBox="0 0 ${W2} ${H2}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Hunger per person, food stock, crowd on source, yield events and deaths over the run">`;
    for (const [lvl, name, colour] of [[C.hungry_at, 'hungry', '#f2a65e'], [C.emergency_at, 'emergency', '#ff9483'], [C.death_at, 'dead', '#cfc6bb']]) {
      if (lvl === undefined) continue;
      s += `<line x1="${pad}" x2="${W2 - 8}" y1="${ys(lvl)}" y2="${ys(lvl)}" stroke="${colour}" stroke-dasharray="2 4" stroke-opacity="0.6"/><text x="${W2 - 6}" y="${ys(lvl) + 4}" font-size="9" fill="#a2b8b1" text-anchor="end">${name} ${lvl}</text>`;
    }
    for (const p of people) { let d = '', pen = false; series.hunger[p].forEach((h, k) => { if (h === null) { pen = false; return; } d += (pen ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(h).toFixed(1); pen = true; }); if (d) s += `<path d="${d}" fill="none" stroke="#e7f0ea" stroke-opacity="0.22" stroke-width="1"/>`; }
    let d = ''; series.stock.forEach((st, k) => { d += (k ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(st).toFixed(1); }); s += `<path d="${d}" fill="none" stroke="#72c8ea" stroke-width="2"/>`;
    d = ''; series.crowd.forEach((c, k) => { d += (k ? 'L' : 'M') + xs(k).toFixed(1) + ' ' + ys(c).toFixed(1); }); s += `<path d="${d}" fill="none" stroke="#c0a8f4" stroke-width="2" stroke-dasharray="4 3"/>`;
    for (const k of totals.yieldTicks) s += `<circle cx="${xs(k)}" cy="${ys(series.crowd[k])}" r="2.5" fill="#c0a8f4"/>`;
    for (const [p, t] of totals.deaths) s += `<line x1="${xs(t)}" x2="${xs(t)}" y1="8" y2="${H2 - 18}" stroke="#cfc6bb" stroke-opacity="0.35" stroke-dasharray="3 3"><title>${esc(p)} dies at tick ${t}</title></line>`;
    s += `<line id="cursor" x1="${xs(v)}" x2="${xs(v)}" y1="4" y2="${H2 - 18}" stroke="#f1c56e"/>`;
    s += `<text x="${pad}" y="${H2 - 4}" font-size="10" fill="#a2b8b1">tick 0</text><text x="${W2 - 8}" y="${H2 - 4}" font-size="10" fill="#a2b8b1" text-anchor="end">tick ${n}</text>`;
    return s + '</svg>';
  }
  function updateDeep() {
    if (!deepReady) prepareDeep();
    const w = world(v), t = v >= 1 ? ticks[v - 1] : null; let out = '';
    const water = C.water === 'on', warmth = C.warmth === 'on';
    for (const p of people) {
      if (!present(w, p)) continue;
      const dead = deadIn(w, p), b = hungerBand(w.hunger[p], dead), d = decisions(v)[p], o = outcomeOf(v, p), ob = observations(v)[p];
      let sees = '';
      if (ob) { const names = ob.sees ? ob.sees.slice() : (ob.others || []).map(x => x.id); if (ob.seen_stock) { for (const [id, st] of Object.entries(ob.seen_stock)) names.push(id + '=' + st); } else if (Object.prototype.hasOwnProperty.call(ob, 'source_food')) names.push('S'); sees = names.join(', '); }
      const ya = traitOf(p);
      const kindCell = d ? esc(d.kind) + (d.amount ? ' ' + d.amount : '') + (d.target ? ' → ' + esc(d.target) : '') + ' <span class="meta">' + esc(d.reason) + '</span>' : '';
      out += `<tr><td>${esc(p)} <button class="linkbtn pin-row" type="button" data-pin="${esc(p)}" data-testid="people-pin-${esc(p)}">${pinned === p ? 'unpin' : 'pin'}</button></td><td class="num">${ya === null ? '' : ya}</td><td>${w.positions[p].join(',')}</td><td class="num b-${b}">${w.hunger[p]}</td>${water ? '<td class="num">' + (w.thirst || {})[p] + '</td>' : ''}${warmth ? '<td class="num">' + (w.cold || {})[p] + (homeOf(w, p) && w.positions[p].join(',') === homeOf(w, p).join(',') ? ' ⌂' : '') + '</td>' : ''}<td class="b-${b}">${dead ? 'dead (t' + w.died_at[p] + ')' : b}</td><td class="num">${food(v, p)}</td>${water ? '<td class="num">' + waterHeld(v, p) + '</td>' : ''}<td>${esc(sees)}</td><td>${kindCell}</td><td>${o ? `<span class="${o.accepted ? 'ok' : 'no'}">${esc(o.reason)}</span>` : ''}</td></tr>`;
    }
    $('people').innerHTML = out;
    $('people').onclick = ev => { const b = ev.target.closest('button[data-pin]'); if (!b) return; if (pinned === b.dataset.pin) unpin(true); else pin(b.dataset.pin); };
    $('selection').textContent = RUN.details[v].selection;
    $('settlement').textContent = RUN.details[v].settlement;
    const cur = document.getElementById('cursor');
    if (cur) { const x = 30 + (900 - 38) * (n ? v / n : 0); cur.setAttribute('x1', x); cur.setAttribute('x2', x); }
    $('timing').textContent = t && RUN.timings[String(t.tick)] !== undefined ? `tick ${t.tick} took ${(RUN.timings[String(t.tick)] / 1e6).toFixed(3)} ms to run` : '';
  }
  $('deep').addEventListener('toggle', () => { if ($('deep').open) updateDeep(); });
  for (const name of ['scored', 'crossover', 'contested']) {
    const views = (RUN.checkpoints || {})[name] || [];
    const b = $(name); b.disabled = !views.length;
    b.title = views.length ? 'ticks ' + views.slice(0, 30).join(', ') + (views.length > 30 ? ', …' : '') : 'absent from this saved run';
    b.addEventListener('click', () => { setPlaying(false); show(views.find(k => k > v) ?? views[0]); });
  }
  if (C.water !== 'on') document.querySelectorAll('.water-col').forEach(e => e.remove());
  if (C.warmth !== 'on') document.querySelectorAll('.warmth-col').forEach(e => e.remove());

  // --------------------------------------------------------------- loop --
  let lastFrame = performance.now(), lastPaint = 0;
  function loop(now) {
    const dt = Math.min(250, now - lastFrame); lastFrame = now;
    if (playing) {
      acc += dt; const step = 1000 / tps;
      while (acc >= step) { acc -= step; if (v >= n) { setPlaying(false); break; } show(v + 1, { tween: true }); }
    }
    let moving = false;
    const followed = pinned && present(world(anim.to), pinned) ? pinned : (follow && selected && selected.type === 'person' ? selected.id : null);
    if (followed && !drag) {
      const pl = placeOf(followed, easeT(now));
      const z = pinned ? fitView().z * PIN_ZOOM : cam.z;
      if (pl) { if (!camTarget || Math.hypot(camTarget.x - pl.x, camTarget.y - pl.y + 14) > 0.5 || Math.abs(camTarget.z - z) > 0.01) camTarget = { x: pl.x, y: pl.y - 14, z }; }
    }
    if (camTarget) {
      const f = REDUCED ? 1 : 1 - Math.pow(0.001, dt / 700);
      cam.x = lerp(cam.x, camTarget.x, f); cam.y = lerp(cam.y, camTarget.y, f); cam.z = lerp(cam.z, camTarget.z, f);
      if (Math.abs(cam.x - camTarget.x) + Math.abs(cam.y - camTarget.y) < 0.3 && Math.abs(cam.z - camTarget.z) < 0.002) { Object.assign(cam, camTarget); camTarget = null; }
      moving = true;
    }
    const drifting = drift && playing && !REDUCED;
    if (drifting) { driftX = Math.sin(now * 0.00013) * 22; driftY = Math.sin(now * 0.00009 + 1) * 9; moving = true; }
    else if (driftX || driftY) { driftX *= 0.9; driftY *= 0.9; if (Math.abs(driftX) + Math.abs(driftY) < 0.05) { driftX = 0; driftY = 0; } moving = true; }
    const tweening = anim.dur > 0 && now - anim.start < anim.dur + 30;
    const ambient = !REDUCED && now - lastPaint > 33;    // water, smoke and flags at a gentle frame rate
    if (needsDraw || moving || tweening || playing || ambient) { draw(now); lastPaint = now; }
    requestAnimationFrame(loop);
  }

  // --------------------------------------------------------------- start --
  renderEvents();
  bindLayers();
  if (window.ResizeObserver) new ResizeObserver(() => { resize(); drawStrip(); }).observe(stage);
  window.addEventListener('resize', () => { resize(); drawStrip(); });
  resize(); drawStrip();
  $('speed').value = String(tps);
  setPlaying(false);
  show(0);
  setTab('events');
  { const saved = pinFromHash(); if (saved && people.includes(saved)) pin(saved); }
  requestAnimationFrame(loop);
})();
