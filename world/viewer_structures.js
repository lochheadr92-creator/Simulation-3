/* Shelters that wear, fires and wells (feature: structures). The things drawn are the saved ones. It decides nothing. */
(function structuresPart() {
  if (!HAS('structures')) return;
  const L = C.feature_levers || {};
  const structsOf = w => (w && w.things && w.things.structures) || [];
  EXT.poseOf.repair = 'build'; EXT.poseOf.dig = 'build'; EXT.poseOf.light = 'warm';
  EXT.standing.push(({ g, k, w, now, items }) => {
    const night = w.sky && w.sky.phase === 'night';
    for (const [kind, owner, x, y, a, b] of structsOf(w)) {
      if (kind === 'fire' && a > 0) {
        items.push({ z: x + y + 0.9, draw: () => {
          const c = cellCentre(x, y), flick = REDUCED ? 0 : Math.sin(now * 0.02 + x * 3) * 1.2;
          g.save();
          if (night) { const grad = g.createRadialGradient(c.x, c.y - 3, 2, c.x, c.y - 3, 38); grad.addColorStop(0, 'rgba(255,190,90,0.38)'); grad.addColorStop(1, 'rgba(255,190,90,0)'); g.fillStyle = grad; g.fillRect(c.x - 40, c.y - 44, 80, 80); }
          g.fillStyle = '#6b4a2a'; g.fillRect(c.x - 5, c.y + 1, 10, 2);
          g.fillStyle = '#f59a3a'; g.beginPath(); g.moveTo(c.x - 4, c.y + 1); g.quadraticCurveTo(c.x - 3, c.y - 7, c.x + flick, c.y - 11); g.quadraticCurveTo(c.x + 4, c.y - 5, c.x + 4, c.y + 1); g.closePath(); g.fill();
          g.fillStyle = '#ffd36b'; g.beginPath(); g.moveTo(c.x - 2, c.y + 1); g.quadraticCurveTo(c.x - 1, c.y - 4, c.x + flick * 0.5, c.y - 7); g.quadraticCurveTo(c.x + 2, c.y - 3, c.x + 2, c.y + 1); g.closePath(); g.fill();
          g.restore();
        } });
      } else if (kind === 'well') {
        items.push({ z: x + y + 0.3, draw: () => {
          const c = cellCentre(x, y), frac = b ? 1 : Math.min(1, a / (L.well_ticks || 12));
          g.save(); g.strokeStyle = '#8a7358'; g.lineWidth = 2; g.fillStyle = b ? '#72c8ea' : '#4b3a28';
          g.beginPath(); g.ellipse(c.x, c.y, 7 * Math.max(0.35, frac), 3.4 * Math.max(0.35, frac), 0, 0, Math.PI * 2); g.fill(); g.stroke();
          if (!b) { g.fillStyle = 'rgba(255,255,255,0.8)'; g.font = '700 6.5px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText(`${a}/${L.well_ticks || 12}`, c.x, c.y - 7); }
          g.restore();
        } });
      } else if (kind === 'shelter' && a < (L.leak_below || 50)) {
        items.push({ z: x + y + 1.6, draw: () => {
          const c = cellCentre(x, y); g.save(); g.strokeStyle = 'rgba(60,40,20,0.8)'; g.lineWidth = 1.2;
          g.beginPath(); g.moveTo(c.x - 4, c.y - 14); g.lineTo(c.x - 1, c.y - 9); g.lineTo(c.x - 3, c.y - 5); g.moveTo(c.x + 3, c.y - 15); g.lineTo(c.x + 5, c.y - 10); g.stroke(); g.restore();
        } });
      }
    }
  });
  EXT.sections.push({
    after: 'needs',
    html: ({ w, p }) => {
      const mine = structsOf(w).filter(s => s[1] === p); if (!mine.length) return '';
      const rows = mine.map(([kind, owner, x, y, a, b]) => kind === 'shelter'
        ? `Shelter condition ${a} of 100${a < (L.repair_at || 45) ? ' — needs mending' : ''}${a < (L.leak_below || 50) ? ' (leaks in rain)' : ''}`
        : kind === 'fire' ? `Fire at (${x}, ${y}): ${a > 0 ? a + ' ticks of fuel left' : 'burnt out'}`
        : `Well at (${x}, ${y}): ${b ? 'finished' : 'dug ' + a + ' of ' + (L.well_ticks || 12) + ' ticks'}`).map(t => `<div class="bond">${esc(t)}</div>`).join('');
      return '<div class="sec"><h4>What they have built</h4>' + rows + '<div class="hint">A finished well is used only once somebody has seen it.</div></div>';
    },
  });
})();
