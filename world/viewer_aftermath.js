/* Graves and death records (feature: aftermath). The markers and the record are saved values. A person's section lists
 * only the deaths they have learned of; the observer's record of a dead person shows what the run recorded. */
(function aftermathPart() {
  if (!HAS('aftermath')) return;
  const thingsOf = w => (w && w.things) || {};
  EXT.poseOf.mourn = 'rest'; EXT.poseOf.collect = 'gather';
  EXT.standing.push(({ g, w, items }) => {
    for (const [kind, owner, x, y, a, b] of thingsOf(w).structures || []) {
      if (kind !== 'grave') continue;
      items.push({ z: x + y + 0.4, draw: () => {
        const c = cellCentre(x, y); g.save();
        g.fillStyle = '#8f8a82'; g.strokeStyle = 'rgba(30,30,28,0.6)'; g.lineWidth = 0.8;
        g.beginPath(); g.moveTo(c.x - 4, c.y + 1); g.lineTo(c.x - 4, c.y - 8); g.quadraticCurveTo(c.x, c.y - 13, c.x + 4, c.y - 8); g.lineTo(c.x + 4, c.y + 1); g.closePath(); g.fill(); g.stroke();
        g.fillStyle = b ? 'rgba(235,238,240,0.5)' : 'rgba(235,238,240,0.92)'; g.font = '700 6px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText(owner, c.x, c.y - 15);
        g.restore();
      } });
    }
  });
  EXT.sections.push({
    after: 'end',
    html: ({ w, p, k }) => {
      const t = thingsOf(w), mine = (t.deaths || []).find(d => d[0] === p);
      const knows = (((w.persona || {}).beliefs || {})[p] || []).filter(e => e[0] === 'death');
      let h = '';
      if (mine) {
        const [person, tick, x, y, age, cause, witnesses, estate, taker, partner] = mine;
        h += '<div class="sec"><h4>Death record (for the reader of the run)</h4>'
          + `<div class="bond">${esc(cause)} at tick ${tick}, age ${age}, at (${x}, ${y})</div>`
          + `<div class="bond">In sight: ${witnesses.length ? witnesses.map(esc).join(', ') : 'nobody'}</div>`
          + `<div class="bond">Left: ${estate.length ? estate.map(([r, n]) => n + ' ' + esc(r)).join(', ') : 'nothing'}${taker ? ' — collected by ' + esc(taker) : ''}</div>`
          + '<div class="hint">The people in the world know none of this unless they saw the grave or were told.</div></div>';
      }
      if (knows.length) {
        h += '<div class="sec"><h4>Knows of deaths</h4>' + knows.map(([kind, subject, x, y, seen, learned, via]) =>
          `<div class="bond">${esc(subject)} died near (${x}, ${y}) at tick ${seen}; ${via ? 'told by ' + esc(via) : 'saw the grave'} at tick ${learned}</div>`).join('') + '</div>';
      }
      return h;
    },
  });
})();
