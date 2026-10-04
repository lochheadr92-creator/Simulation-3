/* Temperament, skills, tiredness and sleep (features: personality, skills, sleep, explain).
 *
 * Spliced into viewer.js where its parts marker stands, so it runs inside that closure and uses its helpers.
 * Everything drawn or listed here is a value the run recorded (the persona block of the saved
 * world, the decision's set-aside list) or a declared table from the run header. It decides nothing. */
(function personaPart() {
  const L = C.feature_levers || {};
  const persona = w => (w && w.persona) || {};

  if (HAS('sleep')) {
    NEEDS.push({
      key: 'fatigue', label: 'Fatigue', at: L.tired_at, max: L.collapse_at, color: '#b7a6f0', word: 'tired',
      get: (w, p) => (persona(w).fatigue || {})[p],
      glyph: (g, x, y) => { g.font = '700 5.4px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('z', x, y + 2); },
    });
    EXT.poseOf.sleep = 'sleeping'; EXT.poseOf.collapse = 'collapsed';
    // a sleeper lies on the ground, head to the right, with little z's drifting up
    EXT.poses.sleeping = EXT.poses.collapsed = (g, p, st, now, col, dark, i) => {
      const collapsed = st.pose === 'collapsed';
      if (st.sheltered && !collapsed) return;      // asleep indoors: the z's are drawn above the roof by the standing hook
      g.save(); g.translate(-3, -2); g.rotate(-Math.PI / 2 * 0.94);
      g.fillStyle = col; g.strokeStyle = dark; g.lineWidth = 0.9; rrect(g, -4.3, -17.5, 8.6, 11.5, 3.6); g.fill(); g.stroke();
      g.strokeStyle = dark; g.lineWidth = 2.2; g.lineCap = 'round'; line(g, -1.8, -7, -1.8, -1); line(g, 1.8, -7, 1.8, -1);
      g.beginPath(); g.arc(0, -21, 3.8, 0, Math.PI * 2); g.fillStyle = '#f2e5d0'; g.fill(); g.strokeStyle = 'rgba(0,0,0,0.35)'; g.lineWidth = 0.7; g.stroke();
      g.restore();
      if (collapsed) { g.fillStyle = '#ff9483'; g.font = '800 9px system-ui, sans-serif'; g.textAlign = 'center'; g.fillText('!', 4, -19); }
      else {
        g.fillStyle = '#d8ceff'; g.textAlign = 'center';
        for (let j = 0; j < 3; j++) {
          const ph = REDUCED ? j / 3 : ((now * 0.0006 + j / 3 + i * 0.13) % 1);
          g.globalAlpha = 0.95 * (1 - ph); g.font = `700 ${(5 + ph * 4).toFixed(1)}px system-ui, sans-serif`;
          g.fillText('z', 5 + ph * 6, -14 - ph * 14);
        }
        g.globalAlpha = 1;
      }
    };
  }

  if (HAS('sleep')) EXT.standing.push(({ g, k, w, t, now, items, sheltersNow }) => {
    const asleep = persona(w).asleep || {};
    for (const p in asleep) {
      if (!present(w, p) || deadIn(w, p) || !sheltersNow.has(w.positions[p].join(','))) continue;
      const place = placeOf(p, t); if (!place) continue;
      const i = PIDX[p] || 0;
      items.push({ z: place.gx + place.gy + 1.6, draw: () => {
        g.fillStyle = '#d8ceff'; g.textAlign = 'center';
        for (let j = 0; j < 3; j++) {
          const ph = REDUCED ? j / 3 : ((now * 0.0006 + j / 3 + i * 0.13) % 1);
          g.globalAlpha = 0.95 * (1 - ph); g.font = `700 ${(6 + ph * 4).toFixed(1)}px system-ui, sans-serif`;
          g.fillText('z', place.x + 6 + ph * 7, place.y - 36 - ph * 16);
        }
        g.globalAlpha = 1;
      } });
    }
  });

  const TRAIT_NOTE = {
    generosity: 'under 35 keeps the last unit from a stranger; 75 and over hands water to the parched',
    sociability: 'draws and inherited from birth; acts through conversation when that is on',
    caution: 'sets off earlier for food, water and home, and goes to bed earlier',
    diligence: 'works on through more tiredness; stocks the shared cache sooner',
    curiosity: 'drawn and inherited from birth; acts through exploration when that is on',
  };
  const word = x => x < 35 ? 'low' : x > 65 ? 'high' : 'middling';
  const STEPS = TABLES.skill_steps || [], LEVEL = pts => { let l = 0; for (let i = 0; i < STEPS.length; i++) if (pts >= STEPS[i]) l = i; return l; };

  if (HAS('personality')) EXT.sections.push({
    after: 'needs',
    html: ({ w, p }) => {
      const t = (persona(w).traits || {})[p]; if (!t) return '';
      const names = TABLES.traits || [];
      return '<div class="sec"><h4>Temperament</h4>' + names.map((nm, i) =>
        `<div class="trait"><span class="lab">${esc(nm)}</span><span class="track"><span class="fill" style="width:${t[i]}%"></span><span class="mid"></span></span><span class="val">${t[i]} · ${word(t[i])}</span></div>`
        + `<div class="trait-note">${esc(TRAIT_NOTE[nm] || '')}</div>`).join('') + '</div>';
    },
  });

  if (HAS('skills')) EXT.sections.push({
    after: 'needs',
    html: ({ w, p }) => {
      const pts = (persona(w).skills || {})[p]; if (!pts) return '';
      const names = TABLES.skills || [];
      return '<div class="sec"><h4>Skills</h4>' + names.map((nm, i) => {
        const lv = LEVEL(pts[i]), next = STEPS[lv + 1];
        return `<div class="skill"><span class="lab">${esc(nm)}</span><span class="lv">level ${lv}<small>${pts[i]} practice${next !== undefined ? ' · next at ' + next : ' · highest'}</small></span></div>`;
      }).join('') + '</div>';
    },
  });

  if (HAS('explain')) EXT.sections.push({
    after: 'tick',
    html: ({ w, p, k }) => {
      const tried = (persona(w).tried || {})[p] || []; if (!tried.length) return '';
      return '<div class="sec"><h4>Remembers trying</h4>' + tried.map(([kind, target, tick, ok]) =>
        `<div class="attempt"><button class="linkbtn" type="button" data-tick="${tick + 1}">tick ${tick}</button> ${esc(LABEL[kind] || kind)}${target ? ' at ' + esc(target) : ''} — <span class="${ok ? 'ok' : 'no'}">${ok ? 'worked' : 'refused'}</span></div>`).join('')
        + '<div class="hint">A person remembers their last four distinct attempts.</div></div>';
    },
  });
})();
