/* Family life (feature: family): couples, pregnancy, grief, guardians and life stage, from saved values only. */
(function familyPart() {
  if (!HAS('family')) return;
  const L = C.feature_levers || {};
  const famOf = w => (w && w.family) || {};
  NEEDS.push({
    key: 'grief', label: 'Grief', at: L.grief_at, max: 100, color: '#b9a3d9', word: 'grieving',
    get: (w, p) => (famOf(w).grief || {})[p] || 0,
    glyph: (g, x, y) => { g.font = '800 6px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('♥', x, y + 2.2); },
  });
  EXT.sections.push({
    after: 'needs',
    html: ({ w, p }) => {
      const f = famOf(w), age = (w.age || {})[p];
      const stage = age === undefined ? '' : age < (ADULT_AT || 60) ? 'a child' : age >= (L.elder_at || 300) ? 'an elder' : 'an adult';
      const rows = [];
      if (stage) rows.push(`${esc(stage)}, ${age} ticks lived${stage === 'an elder' ? ' (every third step costs an extra tick)' : ''}`);
      if ((f.partner || {})[p]) rows.push(`Partner: <b>${esc(f.partner[p])}</b>`);
      if ((f.pregnant || {})[p]) rows.push(`Expecting a child with ${esc(f.pregnant[p][1])}, due tick ${f.pregnant[p][0]}`);
      if ((f.guardian || {})[p]) rows.push(`Taken in by <b>${esc(f.guardian[p])}</b>`);
      const looks = Object.entries(f.guardian || {}).filter(([c, g]) => g === p).map(([c]) => c);
      if (looks.length) rows.push(`Looking after ${looks.map(esc).join(', ')}`);
      if (((f.grief || {})[p] || 0) >= (L.grief_at || 20)) rows.push(`Grieving (${f.grief[p]}): no chores until it eases`);
      if (!rows.length) return '';
      return '<div class="sec"><h4>Family</h4>' + rows.map(t => `<div class="bond">${t}</div>`).join('') + '</div>';
    },
  });
})();
