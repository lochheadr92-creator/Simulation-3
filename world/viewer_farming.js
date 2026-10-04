/* Fields and crops (feature: farming). The plots drawn are the saved ones; the section reads the saved holdings.
 * It decides nothing. */
(function farmingPart() {
  if (!HAS('farming')) return;
  const plotsOf = w => (w && w.things && w.things.plots) || [];
  const STATE = ['bare', 'growing', 'ripe'];
  const holdings = k => (k === 0 ? H.genesis : ticks[k - 1].state).holdings || {};
  EXT.poseOf.plant = 'gather'; EXT.poseOf.harvest = 'gather'; EXT.poseOf.tend = 'draw';
  EXT.standing.push(({ g, k, w, items }) => {
    for (const [owner, x, y, state, grown, since, soil, cared] of plotsOf(w)) {
      items.push({ z: x + y + 0.02, draw: () => {
        const c = cellCentre(x, y), s = 11;
        g.save();
        g.fillStyle = soil >= 60 ? '#7a5a3a' : soil >= 30 ? '#8c7050' : '#a39078';
        g.beginPath(); g.moveTo(c.x, c.y - s * 0.5); g.lineTo(c.x + s, c.y); g.lineTo(c.x, c.y + s * 0.5); g.lineTo(c.x - s, c.y); g.closePath(); g.fill();
        g.strokeStyle = 'rgba(40,25,10,0.5)'; g.lineWidth = 0.8;
        for (let i = -2; i <= 2; i++) { g.beginPath(); g.moveTo(c.x + i * 3.4 - 6, c.y + i * 1.6 - 3); g.lineTo(c.x + i * 3.4 + 6, c.y + i * 1.6 + 3); g.stroke(); }
        if (state !== 'bare') {
          const frac = state === 'ripe' ? 1 : Math.min(1, grown / ((C.feature_levers || {}).grow_ticks || 30));
          const n = 5;
          for (let i = 0; i < n; i++) {
            const px = c.x - 7 + i * 3.5, py = c.y - 1 + (i % 2) * 2.2, h = 2 + 9 * frac;
            g.strokeStyle = state === 'ripe' ? '#d9b640' : '#6fae59'; g.lineWidth = 1.5;
            g.beginPath(); g.moveTo(px, py); g.lineTo(px, py - h); g.stroke();
            if (state === 'ripe') { g.fillStyle = '#e8c85a'; g.beginPath(); g.ellipse(px, py - h, 1.4, 2.4, 0, 0, Math.PI * 2); g.fill(); }
          }
        }
        g.restore();
      } });
    }
  });
  EXT.sections.push({
    after: 'needs',
    html: ({ w, p, k }) => {
      const mine = plotsOf(w).find(q => q[0] === p); if (!mine) return '';
      const [owner, x, y, state, grown, since, soil, cared] = mine, grain = (holdings(k).grain || {})[p] || 0;
      const L = C.feature_levers || {};
      const status = state === 'bare' ? `bare, soil ${soil}` : state === 'growing' ? `growing: ${grown} of ${L.grow_ticks || 30} ticks, tended ${cared} of ${L.tend_max || 3} times`
        : `ripe since tick ${since}`;
      return '<div class="sec"><h4>Field</h4>' + `<div class="bond">At (${x}, ${y}): ${esc(status)}</div>`
        + `<div class="bond">Carrying ${grain} grain${grain >= 3 ? ' (a third spoils every ' + (L.spoil_every || 25) + ' ticks)' : ''}</div>`
        + '<div class="hint">Soil wears with each harvest and mends while the field lies bare.</div></div>';
    },
  });
})();
