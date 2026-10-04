/* Friends, talk, grudges and loneliness (feature: bonds).
 *
 * Spliced into viewer.js where its parts marker stands, so it runs inside that closure and uses its helpers.
 * Everything shown is a saved value: each person's bonds (level, trust, grudge with its cause, when they
 * last dealt with each other and in what tone), their loneliness and who they are talking to. It decides
 * nothing. */
(function societyPart() {
  if (!HAS('bonds')) return;
  const L = C.feature_levers || {};
  const persona = w => (w && w.persona) || {};
  const GRIEVE = TABLES.grievances || {};
  const bondsOf = (w, p) => (persona(w).bonds || {})[p] || [];

  NEEDS.push({
    key: 'lonely', label: 'Company', at: L.lonely_at, max: L.lonely_max, color: '#8fd3c1', word: 'lonely',
    get: (w, p) => (persona(w).lonely || {})[p] || 0,
    glyph: (g, x, y) => { g.font = '800 6px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('?', x, y + 2.2); },
  });
  EXT.poseOf.chat = 'chat'; EXT.poseOf.go_visit = 'walk';

  // above a talking head: a little speech bubble
  EXT.marks.push((g, p, st, now, gy) => {
    if (st.pose === 'chat') {
      const ph = REDUCED ? 0 : Math.floor(now / 380) % 3;
      bubble(g, 8, gy + 1, ['.', '..', '…'][ph], 'rgba(222,246,236,0.96)', '#18332c');
    }
  });

  const standing = (g, k, w, t, items) => {
    const sel = selected && selected.type === 'person' ? selected.id : null;
    // a thread between the two who are talking, green for a friendly word, red for a quarrel
    const pairs = new Set();
    for (const p in persona(w).talking || {}) {
      const q = persona(w).talking[p][0]; if (!present(w, p) || !present(w, q) || deadIn(w, p) || deadIn(w, q)) continue;
      const key = [p, q].sort().join('|'); if (pairs.has(key)) continue; pairs.add(key);
      items.push({ z: 0.1, draw: () => {
        const a = headOf(p, t), b = headOf(q, t); if (!a || !b) return;
        g.save(); g.strokeStyle = 'rgba(143,211,193,0.85)'; g.lineWidth = 1.4; g.setLineDash([2, 3]);
        arc(g, a, b, 8 + Math.hypot(a.x - b.x, a.y - b.y) * 0.1); g.stroke(); g.restore();
      } });
    }
    // words in passing this tick, from the saved tones: a sharp one in red, an apology in gold
    for (const p in persona(w).bonds || {}) for (const [other, bond, trust, grudge, last, why, grieved, tone] of bondsOf(w, p)) {
      if (last !== k - 1 || (tone !== 'quarrel' && tone !== 'apology') || p > other) continue;
      if (!present(w, p) || !present(w, other) || deadIn(w, p) || deadIn(w, other)) continue;
      items.push({ z: 0.1, draw: () => {
        const a = headOf(p, t), b = headOf(other, t); if (!a || !b) return;
        g.save(); g.lineWidth = 1.8; g.strokeStyle = tone === 'quarrel' ? 'rgba(255,110,90,0.9)' : 'rgba(241,197,110,0.9)';
        arc(g, a, b, 10 + Math.hypot(a.x - b.x, a.y - b.y) * 0.1); g.stroke(); g.restore();
        bubble(g, (a.x + b.x) / 2, Math.min(a.y, b.y) - 12, tone === 'quarrel' ? '!' : '♥', tone === 'quarrel' ? 'rgba(255,170,150,0.97)' : 'rgba(255,233,170,0.97)', '#2b1409');
      } });
    }
    // the selected person's ties to everybody in sight: friends in green, resented people in red
    if (!sel || !present(w, sel) || deadIn(w, sel)) return;
    for (const [other, bond, trust, grudge] of bondsOf(w, sel)) {
      if (!present(w, other) || deadIn(w, other)) continue;
      const friend = bond >= (L.friend_at || 30), resent = grudge >= (L.grudge_at || 20);
      if (!friend && !resent) continue;
      items.push({ z: 0.1, draw: () => {
        const a = headOf(sel, t), b = headOf(other, t); if (!a || !b) return;
        g.save(); g.lineWidth = 1 + Math.min(2.2, bond / 40); g.lineCap = 'round';
        g.strokeStyle = resent ? 'rgba(255,128,110,0.7)' : 'rgba(159,220,170,0.7)'; if (resent) g.setLineDash([5, 4]);
        arc(g, a, b, 14 + Math.hypot(a.x - b.x, a.y - b.y) * 0.12); g.stroke(); g.restore();
      } });
    }
  };
  EXT.standing.push(({ g, k, w, t, items }) => standing(g, k, w, t, items));

  const wordOf = (bond, grudge) => grudge >= (L.grudge_at || 20) ? 'resents' : bond >= (L.friend_at || 30) ? 'friend' : bond > 0 ? 'acquaintance' : 'barely met';
  EXT.sections.push({
    after: 'needs',
    html: ({ w, p, k }) => {
      const mine = bondsOf(w, p), talking = (persona(w).talking || {})[p];
      if (!mine.length && !talking) return '';
      const rows = mine.slice().sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([other, bond, trust, grudge, last, why, grieved, tone]) => {
        const ago = k - 1 - last;
        const note = grudge ? `<div class="bond-note">holds a grudge (${grudge}) since tick ${grieved}: ${esc(GRIEVE[why] || why)}</div>` : '';
        return `<div class="bond"><b>${esc(other)}</b> — ${wordOf(bond, grudge)}`
          + `<span class="track"><span class="fill ${grudge >= (L.grudge_at || 20) ? 'bad' : 'good'}" style="width:${bond}%"></span></span>`
          + `<span class="val">bond ${bond} · trust ${trust} · ${ago <= 0 ? 'just now' : 'last dealt ' + ago + ' ticks ago'}${tone ? ' (' + esc(tone) + ')' : ''}</span>${note}</div>`;
      }).join('');
      const now = talking ? `<div class="bond">Talking with <b>${esc(talking[0])}</b> since tick ${talking[1]}.</div>` : '';
      return '<div class="sec"><h4>Relationships</h4>' + now + rows
        + '<div class="hint">Only what this person has seen and been through: a bond is their view of the other, and the other may see it differently.</div></div>';
    },
  });
})();
