/* Observer tools: a minimap, a knowledge fog for the selected person, arrows for where people are heading, a ring where an
 * event happened, and a link that remembers the tick and the person. Everything drawn comes from recorded values: the
 * saved positions, sky, sleep state, beliefs and decisions. The fog uses the recorded positions with the sight radius the
 * run declares (less at night and in a storm, none asleep); firelight is not counted. Nothing here decides anything. */
(function observerPart() {
  const GROUND = GW * GH;
  const LEV = C.feature_levers || {};

  // ---- what a person could see, rebuilt from where they stood ----------------------------------------------
  const FOG = {};
  function lastSeen(p, k) {
    // lastSeen[cell] = the latest view whose start window covered it, for views 0..k-1; -1 when never
    let f = FOG[p];
    if (!f || k < f.upTo) f = FOG[p] = { upTo: 0, last: new Int32Array(GROUND).fill(-1) };
    for (let j = f.upTo; j < k; j++) {
      const w = world(j), pos = (w.positions || {})[p];
      if (!pos || deadIn(w, p)) continue;
      const r = sightAt(w, p);
      for (let y = Math.max(0, pos[1] - r); y <= Math.min(GH - 1, pos[1] + r); y++)
        for (let x = Math.max(0, pos[0] - r); x <= Math.min(GW - 1, pos[0] + r); x++) f.last[y * GW + x] = j;
    }
    f.upTo = Math.max(f.upTo, k);
    return f.last;
  }
  function diamond(g, x, y) {
    const e = elev(x, y), a = [isoX(x, y), isoY(x, y) - e], b = [isoX(x + 1, y), isoY(x + 1, y) - e],
      c = [isoX(x + 1, y + 1), isoY(x + 1, y + 1) - e], d = [isoX(x, y + 1), isoY(x, y + 1) - e];
    poly(g, [a, b, c, d]);
  }
  const selectedPerson = () => selected && selected.type === 'person' ? selected.id : null;

  LAYERS.fog = false; LAYERS.heading = false;
  EXT.standing.push(({ g, k, w, items }) => {
    const p = selectedPerson();
    if (LAYERS.fog && p && present(w, p) && !deadIn(w, p)) {
      const last = lastSeen(p, k), pos = w.positions[p], r = sightAt(w, p);
      for (let y = 0; y < GH; y++) for (let x = 0; x < GW; x++) {
        const now = Math.abs(x - pos[0]) <= r && Math.abs(y - pos[1]) <= r, was = last[y * GW + x] >= 0;
        if (now) continue;
        items.push({ z: x + y - 0.6, draw: () => { diamond(g, x, y); g.fillStyle = was ? 'rgba(8,14,20,0.30)' : 'rgba(6,10,16,0.66)'; g.fill(); } });
      }
      // what they believe about places: first-hand in gold, told by somebody in blue
      for (const [kind, subject, x, y, seen, learned, via] of (((w.persona || {}).beliefs || {})[p] || [])) {
        items.push({ z: x + y + 0.35, draw: () => {
          const c = cellCentre(x, y);
          g.save(); g.setLineDash(via ? [3, 2] : []); g.lineWidth = 1.4; g.strokeStyle = via ? 'rgba(143,196,255,0.95)' : 'rgba(255,214,125,0.95)';
          diamond(g, x, y); g.stroke(); g.setLineDash([]); g.fillStyle = via ? 'rgba(143,196,255,0.95)' : 'rgba(255,214,125,0.95)';
          g.font = '600 6.5px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText(kind + (via ? ' (told)' : ''), c.x, c.y - 4); g.restore();
        } });
      }
    }
    if (LAYERS.heading && k < n) {
      const next = decisions(k + 1);
      for (const q of people) {
        const d = next[q]; if (!d || !present(w, q) || deadIn(w, q)) continue;
        const here = placeOf(q, 1); if (!here) continue;
        if (d.step) {
          const to = cellCentre(d.step[0], d.step[1]);
          items.push({ z: 1e4, draw: () => {
            g.save(); g.strokeStyle = COLOR[q]; g.fillStyle = COLOR[q]; g.lineWidth = q === p ? 2.2 : 1.4; g.globalAlpha = q === p ? 0.95 : 0.6;
            line(g, here.x, here.y - 2, to.x, to.y - 2);
            const ang = Math.atan2(to.y - here.y, to.x - here.x);
            g.beginPath(); g.moveTo(to.x, to.y - 2); g.lineTo(to.x - 7 * Math.cos(ang - 0.45), to.y - 2 - 7 * Math.sin(ang - 0.45)); g.lineTo(to.x - 7 * Math.cos(ang + 0.45), to.y - 2 - 7 * Math.sin(ang + 0.45)); g.closePath(); g.fill(); g.restore();
          } });
        }
        if (q === p) {
          const goal = destinationOf(d, w, q);
          if (goal) {
            const there = cellCentre(goal[0], goal[1]);
            items.push({ z: 1e4 + 1, draw: () => {
              g.save(); g.setLineDash([5, 4]); g.strokeStyle = COLOR[q]; g.lineWidth = 1.5; g.globalAlpha = 0.85; line(g, here.x, here.y - 2, there.x, there.y - 2);
              g.setLineDash([]); ell(g, there.x, there.y, 11, 5.5); g.stroke(); g.restore();
            } });
          }
        }
      }
    }
    if (PLACE_MARK && performance.now() < PLACE_MARK.until) {
      const c = cellCentre(PLACE_MARK.x, PLACE_MARK.y), pulse = REDUCED ? 1 : 0.7 + 0.3 * Math.sin(performance.now() * 0.008);
      items.push({ z: 1e4 + 2, draw: () => { g.save(); g.strokeStyle = 'rgba(255,227,163,' + pulse.toFixed(2) + ')'; g.lineWidth = 2.2; ell(g, c.x, c.y, 17 * pulse + 4, 8.5 * pulse + 2); g.stroke(); g.restore(); } });
      needsDraw = true;
    }
  });
  // where a recorded decision is taking somebody, when the record says: a source or a person they named, or home
  function destinationOf(d, w, p) {
    if (d.home_site) return d.home_site;
    if (d.target && SOURCE_BY_ID[d.target]) return SOURCE_BY_ID[d.target].position;
    if (d.target && w.positions && w.positions[d.target] && d.target !== p) return w.positions[d.target];
    if (['home', 'go_shelter', 'go_sleep', 'go_home'].includes(d.kind)) return homeOf(w, p);
    return null;
  }

  // ---- a ring where an event happened -----------------------------------------------------------------------
  let PLACE_MARK = null;
  list.addEventListener('click', ev => {
    const row = ev.target.closest('button.event'); if (!row) return;
    const e = EVENTS[Number(row.dataset.i)];
    if (e && e.cell) {
      const c = cellCentre(e.cell[0], e.cell[1]);
      PLACE_MARK = { x: e.cell[0], y: e.cell[1], until: performance.now() + 3500 };
      if (!e.who) centreOn(c.x, c.y - 10);
      needsDraw = true;
    }
  });

  // ---- a minimap --------------------------------------------------------------------------------------------
  const mini = document.createElement('canvas');
  mini.id = 'minimap'; mini.setAttribute('role', 'img'); mini.setAttribute('aria-label', 'Overview of the whole map. Click to move the camera.');
  stage.appendChild(mini);
  const MS = 132;
  function drawMinimap(w) {
    const s = Math.min(window.devicePixelRatio || 1, 2);
    if (mini.width !== MS * s) { mini.width = MS * s; mini.height = MS * s; }
    const g = mini.getContext('2d'); g.setTransform(s, 0, 0, s, 0, 0); g.clearRect(0, 0, MS, MS);
    const cell = Math.min((MS - 8) / GW, (MS - 8) / GH), ox = (MS - cell * GW) / 2, oy = (MS - cell * GH) / 2;
    g.fillStyle = 'rgba(95,128,90,0.55)'; g.fillRect(ox, oy, cell * GW, cell * GH);
    const sq = (x, y, f, inset) => { g.fillStyle = f; g.fillRect(ox + x * cell + (inset || 0), oy + y * cell + (inset || 0), cell - 2 * (inset || 0), cell - 2 * (inset || 0)); };
    for (const key of ROUGH) { const [x, y] = key.split(',').map(Number); sq(x, y, 'rgba(110,118,130,0.95)'); }
    for (const key of SPOTS) { const [x, y] = key.split(',').map(Number); sq(x, y, 'rgba(215,196,150,0.9)'); }
    const shelters = sheltersAt(v);
    for (const q of people) { if (!present(w, q)) continue; const h = homeOf(w, q); if (h) sq(h[0], h[1], shelters.has(h.join(',')) ? 'rgba(214,170,98,0.95)' : 'rgba(214,170,98,0.4)', cell * 0.22); }
    SOURCE_AT.forEach((s2, key) => { const [x, y] = key.split(',').map(Number); sq(x, y, sourceColor(s2), cell * 0.12); });
    const t = w.things || {};
    for (const [x, y, wear] of t.paths || []) if (wear >= (LEV.worn_at || 8)) sq(x, y, 'rgba(110,78,42,0.7)', cell * 0.3);
    for (const st of t.structures || []) if (st[0] === 'grave') sq(st[2], st[3], 'rgba(205,200,195,0.95)', cell * 0.3);
    for (const wolf of t.wolves || []) { const x = wolf[1], y = wolf[2]; if (typeof x === 'number') sq(x, y, 'rgba(255,110,96,0.95)', cell * 0.15); }
    for (const q of people) {
      if (!present(w, q) || (deadIn(w, q) && w.died_at[q] < v)) continue;
      const [x, y] = w.positions[q];
      g.fillStyle = COLOR[q]; g.beginPath(); g.arc(ox + (x + 0.5) * cell, oy + (y + 0.5) * cell, Math.max(2, cell * 0.28), 0, Math.PI * 2); g.fill();
      if (selectedPerson() === q) { g.strokeStyle = '#fff'; g.lineWidth = 1.4; g.stroke(); }
    }
    // the part of the map the camera shows, as the grid sees it
    const corners = [[0, 0], [cw, 0], [cw, ch], [0, ch]].map(([sx, sy]) => { const [ix, iy] = toIso(sx, sy), [gx, gy] = toGrid(ix, iy); return [ox + gx * cell, oy + gy * cell]; });
    g.save(); g.beginPath(); g.rect(0, 0, MS, MS); g.clip(); g.strokeStyle = 'rgba(255,227,163,0.95)'; g.lineWidth = 1.4;
    g.beginPath(); corners.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath(); g.stroke(); g.restore();
    mini._geo = { cell, ox, oy };
  }
  EXT.overlays.push(({ w }) => drawMinimap(w));
  function pointMini(ev) {
    const geo = mini._geo; if (!geo) return;
    const r = mini.getBoundingClientRect(), gx = ((ev.clientX - r.left) * (MS / r.width) - geo.ox) / geo.cell, gy = ((ev.clientY - r.top) * (MS / r.height) - geo.oy) / geo.cell;
    const x = clamp(gx, 0, GW - 0.01), y = clamp(gy, 0, GH - 0.01);
    cam.x = isoX(x, y); cam.y = isoY(x, y) - elev(Math.floor(x), Math.floor(y)); userMoved = true; camTarget = null; follow = false;
    $('follow').setAttribute('aria-pressed', 'false'); needsDraw = true;
  }
  let miniDrag = false;
  mini.addEventListener('pointerdown', ev => { miniDrag = true; mini.setPointerCapture(ev.pointerId); pointMini(ev); ev.stopPropagation(); });
  mini.addEventListener('pointermove', ev => { if (miniDrag) pointMini(ev); });
  mini.addEventListener('pointerup', () => { miniDrag = false; });
  mini.addEventListener('pointercancel', () => { miniDrag = false; });

  // read-only extras for scripted checks of the page
  function fogCounts() {
    const p = selectedPerson(), w = world(v); if (!p || !present(w, p) || deadIn(w, p)) return null;
    const last = lastSeen(p, v), pos = w.positions[p], r = sightAt(w, p); let now = 0, remembered = 0, unseen = 0;
    for (let y = 0; y < GH; y++) for (let x = 0; x < GW; x++) {
      if (Math.abs(x - pos[0]) <= r && Math.abs(y - pos[1]) <= r) now++; else if (last[y * GW + x] >= 0) remembered++; else unseen++;
    }
    return { now, remembered, unseen };
  }
  const baseState = window.viewerState;
  window.viewerState = () => Object.assign(baseState(), { fog: fogCounts(), layers: { fog: LAYERS.fog, heading: LAYERS.heading }, placeMark: PLACE_MARK ? { x: PLACE_MARK.x, y: PLACE_MARK.y } : null, hash: location.hash });

  // ---- a link that remembers where the viewer was ------------------------------------------------------------
  function currentHash() { const bits = ['v=' + v]; if (selectedPerson()) bits.push('p=' + selectedPerson()); return '#' + bits.join('&'); }
  function writeHash() {
    try { history.replaceState(null, '', currentHash()); } catch (err) { /* a page opened from a file may refuse */ }
  }
  const OPENED_WITH = location.hash || '';                    // read before the first view is shown and rewrites it
  EXT.onchange.push(writeHash);
  function restore(hash) {
    const m = {}; hash.replace(/^#/, '').split('&').forEach(kv => { const [a, b] = kv.split('='); if (a) m[a] = decodeURIComponent(b || ''); });
    if (m.v !== undefined && /^\d+$/.test(m.v)) { show(Number(m.v)); }
    if (m.p && people.includes(m.p)) { select({ type: 'person', id: m.p }, true); focusPerson(m.p); }
  }
  setTimeout(() => restore(OPENED_WITH), 0);
  window.addEventListener('hashchange', () => { if (location.hash !== currentHash()) restore(location.hash); });   // a link followed or edited in the page
})();
