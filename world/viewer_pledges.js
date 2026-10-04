/* Asking and promising (feature: pledges).
 *
 * Spliced into viewer.js where its parts marker stands. Everything shown is saved: the open pledges in each tick's
 * world, and the events the index derived from the endings the run recorded. It decides nothing. */
(function pledgesPart() {
  if (!HAS('pledges')) return;
  const REASON = TABLES.reasons || {};
  const pledgesOf = w => (w && w.pledges) || {};
  const WHAT = { water: 'water', food: 'food', wood: 'wood', build: 'help building', news: 'news of the wolf' };
  EXT.poseOf.help = 'build'; EXT.poseOf.host = 'give';

  // open pledges as threads: a request waiting for its answer, and a promise being kept
  EXT.standing.push(({ g, k, w, t, items }) => {
    if (!LAYERS.links) return;
    for (const p of pledgesOf(w).open || []) {
      const [kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, done] = p;
      if (!present(w, asker) || !present(w, helper) || deadIn(w, asker) || deadIn(w, helper)) continue;
      items.push({ z: 0.1, draw: () => {
        const a = headOf(helper, t), b = headOf(asker, t); if (!a || !b) return;
        g.save(); g.lineCap = 'round';
        if (state === 'promised') {
          g.setLineDash([2, 5]); g.lineDashOffset = REDUCED ? 0 : -(performance.now() * 0.02) % 14;
          g.strokeStyle = kind === 'build' ? 'rgba(168,214,160,0.9)' : 'rgba(241,197,110,0.9)'; g.lineWidth = 1.7;
        } else { g.setLineDash([1.5, 4]); g.strokeStyle = 'rgba(230,230,215,0.65)'; g.lineWidth = 1.2; }
        arc(g, { x: a.x, y: a.y + 8 }, { x: b.x, y: b.y + 8 }, 12 + Math.hypot(a.x - b.x, a.y - b.y) * 0.12); g.stroke(); g.restore();
      } });
    }
  });

  const wordOfPledge = (me, [kind, asker, helper, state, made, due, amount, x, y, held, action, heard, arrived, done]) => {
    const what = kind === 'build' ? `${esc(amount)} ticks of help building` : kind === 'news' ? 'news of the wolf' : `${esc(amount)} ${esc(kind)}`;
    if (asker === me) {
      return state === 'promised'
        ? (heard ? `${esc(helper)} promised ${what}; due by tick ${esc(due)}` : `waiting to hear from ${esc(helper)} about ${what}`)
        : `asked ${esc(helper)} for ${what}; no answer yet`;
    }
    if (state === 'promised') {
      const how = kind === 'build' ? (arrived ? `at ${esc(asker)}'s door since tick ${esc(arrived)}; ${esc(done)} of ${esc(amount)} ticks done` : `on the way to ${esc(asker)}'s door`)
        : held ? `${esc(held)} reserved to hand over` : kind === 'wood' ? 'going to fetch it' : 'on the way';
      return `promised ${esc(asker)} ${what}: ${how}; due by tick ${esc(due)}`;
    }
    return `${esc(asker)} asked for ${what}; deciding`;
  };

  EXT.sections.push({
    after: 'needs',
    html: ({ w, p, k }) => {
      const open = (pledgesOf(w).open || []).filter(q => q[1] === p || q[2] === p);
      const mine = EVENTS.filter(e => e.pledge && e.k <= k && (e.who === p || e.other === p));
      if (!open.length && !mine.length) return '';
      const count = (stage, role) => mine.filter(e => e.stage === stage && e[role] === p).length;
      const promised = count('promised', 'who'), kept = count('kept', 'who'), broken = count('broken', 'who'), cut = count('cut_short', 'who');
      const asked = count('asked', 'who'), helped = count('kept', 'other'), refused = count('declined', 'other');
      const tally = [];
      if (promised || broken || kept) tally.push(`Promised ${promised}, kept ${kept}, broken ${broken}${cut ? `, cut short ${cut}` : ''}`);
      if (asked) tally.push(`Asked ${asked} times, helped ${helped}, refused ${refused}`);
      const rows = open.map(q => `<div class="bond">${wordOfPledge(p, q)}</div>`).join('');
      const recent = mine.slice(-3).reverse().map(e => `<div class="bond-note">tick ${e.k}: ${esc(e.text)}</div>`).join('');
      return '<div class="sec"><h4>Asking and promising</h4>' + rows
        + (tally.length ? `<div class="bond">${tally.join(' · ')}</div>` : '') + recent
        + '<div class="hint">Promises reserve the units in the helper\'s own account until they are handed over or given back.</div></div>';
    },
  });
})();
