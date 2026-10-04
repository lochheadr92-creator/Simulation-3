/* Stone and tools (feature: crafting): an inspector section from the saved holdings. It decides nothing. */
(function craftingPart() {
  if (!HAS('crafting')) return;
  const holdings = k => (k === 0 ? H.genesis : ticks[k - 1].state).holdings || {};
  const TOOLS = (TABLES.tools || []);
  EXT.sections.push({
    after: 'needs',
    html: ({ p, k }) => {
      const h = holdings(k), stone = (h.stone || {})[p] || 0;
      const tools = TOOLS.filter(t => ((h[t] || {})[p] || 0) > 0);
      const effect = { axe: 'builds a shelter faster', pick: 'digs stone faster', basket: 'carries more food', hoe: 'for working the soil' };
      const rows = tools.map(t => `<div class="bond"><b>${esc(t)}</b> — ${esc(effect[t] || '')}</div>`).join('');
      return '<div class="sec"><h4>Stone and tools</h4>' + `<div class="bond">Carrying ${stone} stone</div>`
        + (rows || '<div class="bond">No tools yet.</div>')
        + '<div class="hint">A tool is made at home from wood and stone the kernel saw spent; none appears otherwise.</div></div>';
    },
  });
})();
