/* What people know of the ground and the paths they wear (features: exploration, paths). The paths drawn are the saved
 * wear; the section lists what the run recorded this person had in sight and remembered. It decides nothing. */
(function groundPart() {
  if (!HAS('paths') && !HAS('exploration')) return;
  const L = C.feature_levers || {};
  const WORN = L.worn_at || 8, SIDE = L.patch || 3, STALE = L.stale_after || 150;
  EXT.poseOf.explore = 'walk';
  if (HAS('paths')) EXT.standing.push(({ g, w, items }) => {
    for (const [x, y, wear] of ((w && w.things) || {}).paths || []) {
      if (wear < 2) continue;
      items.push({ z: x + y - 0.5, draw: () => {
        const c = cellCentre(x, y), a = Math.min(0.5, 0.1 + wear / (WORN * 2) * 0.35);
        g.save(); g.globalAlpha = a;
        g.beginPath(); g.moveTo(c.x, c.y - 10); g.lineTo(c.x + 20, c.y); g.lineTo(c.x, c.y + 10); g.lineTo(c.x - 20, c.y); g.closePath();
        g.fillStyle = wear >= WORN ? '#6e4d2a' : '#85673f'; g.fill(); g.restore();
      } });
    }
  });
  EXT.sections.push({
    after: 'end',
    html: ({ w, p, k }) => {
      let h = '';
      const seen = ((w.ground || {})[p] || []);
      if (HAS('exploration') && (seen.length || (w.positions || {})[p])) {
        const across = Math.ceil((C.width || 0) / SIDE), down = Math.ceil((C.height || 0) / SIDE), total = across * down;
        const lately = seen.filter(([, t]) => k - t < STALE).length;
        const rough = ((w.terrain_memory || {})[p] || []).length;
        const wells = (((w.persona || {}).beliefs || {})[p] || []).filter(e => e[0] === 'well');
        h += '<div class="sec"><h4>What they know of the ground</h4>'
          + `<div class="bond">Has had ${lately} of ${total} map patches in sight in the last ${STALE} ticks</div>`
          + `<div class="bond">Remembers ${rough} rough cell${rough === 1 ? '' : 's'}; forgets them when their patch goes unseen for ${L.terrain_span || 240} ticks</div>`
          + wells.map(([kind, owner, x, y, s, l, via]) => `<div class="bond">Knows of ${esc(owner)}'s well at (${x}, ${y})${via ? ', told by ' + esc(via) : ''}</div>`).join('')
          + '</div>';
      }
      return h;
    },
  });
})();
