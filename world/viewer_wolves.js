/* Wolves, injuries and what people believe about them (features: wolves, beliefs).
 *
 * Spliced into viewer.js where its parts marker stands, so it runs inside that closure and uses its helpers.
 * The wolves drawn are the positions each saved tick recorded; the rings for the selected person are their
 * saved beliefs, with the age and teller the run recorded. The map shows you the wolves; the person only
 * knows what they saw or were told. Nothing here decides anything. */
(function wolvesPart() {
  if (!HAS('wolves')) return;
  const L = C.feature_levers || {};
  const persona = w => (w && w.persona) || {};
  const wolvesOf = w => (w && w.things && w.things.wolves) || [];

  NEEDS.push({
    key: 'hurt', label: 'Hurt', at: L.limp_at, max: L.lethal_hurt, color: '#ff7a6b', word: 'hurt',
    get: (w, p) => (persona(w).hurt || {})[p] || 0,
    glyph: (g, x, y) => { g.font = '800 6.2px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('+', x, y + 2.2); },
  });
  EXT.poseOf.flee = 'walk';

  // where a wolf is on screen this frame, moving smoothly between the two saved ticks
  function wolfPlace(id, t) {
    const b = wolvesOf(world(anim.to)).find(x => x[0] === id); if (!b) return null;
    const a = wolvesOf(world(anim.from)).find(x => x[0] === id) || b;
    const u = anim.from === anim.to ? 1 : t;
    const gx = lerp(a[1], b[1], u) + 0.5, gy = lerp(a[2], b[2], u) + 0.5;
    const e = lerp(elev(a[1], a[2]), elev(b[1], b[2]), u);
    const dir = isoX(b[1], b[2]) >= isoX(a[1], a[2]) ? 1 : -1;
    return { gx, gy, x: isoX(gx, gy), y: isoY(gx, gy) - e, dir };
  }

  function drawWolf(g, x, y, wolf, place, now) {
    const resting = wolf[3] > 0, chasing = wolf[4] > 0, idx = wolf[0].charCodeAt(wolf[0].length - 1);
    const d = place.dir, stride = REDUCED || resting ? 0 : Math.sin(now * 0.016 + idx);
    g.save(); g.translate(x, y); g.scale(d, 1);
    g.fillStyle = 'rgba(0,0,0,0.3)'; ell(g, 0, 0, 11, 4); g.fill();
    const low = resting ? 3 : chasing ? 1 : 0;                         // a resting wolf lies down, a hunting one is low
    g.strokeStyle = '#4c5057'; g.lineWidth = 1.8; g.lineCap = 'round';
    for (const [lx, ph] of [[-6, 0], [-3.2, Math.PI], [3.4, Math.PI], [6.2, 0]]) {
      const s = stride * 2.2 * Math.cos(ph);
      line(g, lx, -7 + low, lx + s, -0.4);
    }
    g.fillStyle = '#8b9199'; g.strokeStyle = '#3d4147'; g.lineWidth = 0.9;
    g.beginPath(); g.ellipse(0, -9 + low, 8.8, 4.2, 0, 0, Math.PI * 2); g.fill(); g.stroke();       // body
    g.beginPath(); g.moveTo(-7.5, -10 + low); g.quadraticCurveTo(-13.5, -9 + low - stride, -12, -4.5 + low); g.lineWidth = 2.4; g.stroke();   // tail
    g.lineWidth = 0.9;
    g.beginPath(); g.ellipse(8.4, -12 + low, 3.9, 3.3, 0, 0, Math.PI * 2); g.fillStyle = '#9aa0a8'; g.fill(); g.stroke();                  // head
    g.beginPath(); g.moveTo(11, -12.6 + low); g.lineTo(14.8, -11 + low); g.lineTo(11, -10.2 + low); g.closePath(); g.fillStyle = '#767c85'; g.fill(); g.stroke();   // snout
    g.fillStyle = '#767c85'; g.beginPath(); g.moveTo(6.6, -14.4 + low); g.lineTo(7.5, -18 + low); g.lineTo(9.2, -14.6 + low); g.closePath(); g.fill(); g.stroke();   // ear
    g.fillStyle = chasing ? '#ff6b5e' : '#f5d97a'; g.beginPath(); g.arc(9.4, -12.6 + low, 0.9, 0, Math.PI * 2); g.fill();                  // eye
    g.restore();
    g.fillStyle = 'rgba(235,238,240,0.92)'; g.font = '700 6.5px system-ui, sans-serif'; g.textAlign = 'center';
    g.fillText(wolf[0], x, y - 21 + low);
  }

  EXT.standing.push(({ g, k, w, t, now, items }) => {
    for (const wolf of wolvesOf(w)) {
      const place = wolfPlace(wolf[0], t); if (!place) continue;
      items.push({ z: place.gx + place.gy + 0.06, draw: () => drawWolf(g, place.x, place.y, wolf, place, now) });
    }
    // what the selected person believes: a ring at each remembered wolf, fainter the older and the less certain
    const sel = selected && selected.type === 'person' ? selected.id : null;
    if (!sel || !HAS('beliefs')) return;
    const span = L.memory_span || 240, r = (L.danger_radius || 2) + 0.5;
    for (const [kind, subject, x, y, seen, learned, via] of (persona(w).beliefs || {})[sel] || []) {
      if (kind !== 'wolf') continue;
      const age = Math.max(0, k - seen), conf = Math.max(0, 100 - Math.floor(100 * age / span)) * (via ? 0.75 : 1) / 100;
      const fresh = age <= (L.danger_span || 30);
      items.push({ z: x + y + 0.02, draw: () => {
        const c = cellCentre(x, y);
        g.save(); g.setLineDash([4, 3]); g.lineWidth = 1.4;
        g.strokeStyle = fresh ? `rgba(255,120,100,${(0.35 + 0.5 * conf).toFixed(3)})` : `rgba(190,190,200,${(0.2 + 0.4 * conf).toFixed(3)})`;
        ell(g, c.x, c.y - 4, r * TW / 2, r * TH / 2); g.stroke(); g.setLineDash([]);
        g.fillStyle = fresh ? 'rgba(255,150,130,0.95)' : 'rgba(205,205,214,0.85)'; g.font = '700 6.4px system-ui, sans-serif'; g.textAlign = 'center';
        g.fillText(`${subject} ${age ? age + ' ago' : 'now'}${via ? ' · ' + via : ''}`, c.x, c.y - 4 - r * TH / 2 - 2);
        g.restore();
      } });
    }
  });

  if (HAS('beliefs')) EXT.sections.push({
    after: 'needs',
    html: ({ w, p, k }) => {
      const mine = (persona(w).beliefs || {})[p] || [], hurt = (persona(w).hurt || {})[p] || 0;
      const span = L.memory_span || 240;
      const rows = mine.map(([kind, subject, x, y, seen, learned, via]) => {
        const age = Math.max(0, k - seen), base = Math.max(0, 100 - Math.floor(100 * age / span)), conf = via ? Math.floor(base * 3 / 4) : base;
        const how = via ? `told by ${esc(via)} at tick ${learned}` : 'seen first-hand';
        return `<div class="belief"><b>${esc(kind)} ${esc(subject)}</b> near (${x}, ${y}) — ${age ? age + ' ticks ago' : 'just now'}, ${how}`
          + `<span class="conf" title="how much weight it deserves: it fades with age, and hearsay counts for less"><span style="width:${conf}%"></span></span></div>`;
      }).join('');
      const hurtRow = hurt ? `<div class="belief hurt-note">Hurt ${hurt} of ${L.lethal_hurt}${hurt >= L.limp_at ? ' — limping' : ''}</div>` : '';
      if (!rows && !hurtRow) return '';
      return '<div class="sec"><h4>Knows about wolves</h4>' + hurtRow + (rows || '<div class="hint">Has not seen or heard of one lately.</div>')
        + '<div class="hint">Only what they saw or were told, with its age. The map shows you every wolf; it does not show them.</div></div>';
    },
  });
})();
