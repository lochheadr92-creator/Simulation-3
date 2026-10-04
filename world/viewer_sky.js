/* Day, night and weather (feature: sky).
 *
 * Spliced into viewer.js where its parts marker stands, so it runs inside that closure and uses its helpers.
 * The tint, the rain and the clock line are drawn from the sky each saved tick records (phase, weather,
 * temperature, moment of the day). Nothing here decides anything or changes any number: the dimming only
 * maps a recorded moment of the day to a darkness, and the streaks are decoration. */
(function skyPart() {
  if (!HAS('sky')) return;
  const L = C.feature_levers || {};
  const skyOf = w => (w && w.sky) || null;
  const PHASE_WORD = { dawn: 'dawn', day: 'day', dusk: 'dusk', night: 'night' };
  const WEATHER_WORD = { clear: 'clear', overcast: 'overcast', rain: 'raining', storm: 'storm' };

  // clock and weather in the corner of the map
  EXT.hud.push(w => {
    const s = skyOf(w); if (!s) return '';
    return `<span title="Recorded sky: ${esc(s.phase)}, ${esc(s.weather)}">${esc(PHASE_WORD[s.phase] || s.phase)} · <b>${esc(WEATHER_WORD[s.weather] || s.weather)}</b> · ${s.temp}°</span>`;
  });

  // How dark the world looks at a (possibly fractional) moment of the day. Maps the recorded moment onto the
  // declared dawn/day/dusk/night lengths; it adds no information of its own.
  function darkness(moment) {
    const len = L.day_length, night = L.night_length, tw = L.twilight;
    const max = 0.5;
    if (moment < tw) return max * (1 - moment / tw);                       // dawn: from dark to light
    if (moment < len - night - tw) return 0;                              // day
    if (moment < len - night) return max * (moment - (len - night - tw)) / tw;   // dusk: light to dark
    return max;                                                           // night
  }
  function momentAt(k, t) {
    const a = skyOf(world(Math.max(0, k - 1))), b = skyOf(world(k));
    if (!b) return null;
    if (!a || anim.from === anim.to) return b.moment;
    let m0 = a.moment, m1 = b.moment; if (m1 < m0) m1 += L.day_length;    // across midnight into the next dawn
    return (m0 + (m1 - m0) * t) % L.day_length;
  }
  const rainDrops = [];
  for (let i = 0; i < 320; i++) rainDrops.push([((i * 7919) % 1000) / 1000, ((i * 104729) % 1000) / 1000, 0.6 + ((i * 31) % 10) / 12]);

  EXT.overlays.push(({ g, k, w, t, now, width, height }) => {
    const s = skyOf(w); if (!s) return;
    const m = momentAt(k, t);
    const dark = m === null ? 0 : darkness(m);
    const grey = s.weather === 'overcast' ? 0.06 : s.weather === 'rain' ? 0.12 : s.weather === 'storm' ? 0.22 : 0;
    if (dark + grey > 0) {
      g.fillStyle = `rgba(8, 14, 38, ${(dark + grey).toFixed(3)})`; g.fillRect(0, 0, width, height);
    }
    if (s.weather === 'rain' || s.weather === 'storm') {
      const count = s.weather === 'storm' ? 320 : 130, slant = s.weather === 'storm' ? 0.35 : 0.12;
      g.save(); g.strokeStyle = s.weather === 'storm' ? 'rgba(190, 215, 255, 0.55)' : 'rgba(170, 200, 235, 0.42)'; g.lineWidth = 1;
      const drift = REDUCED ? 0 : (now * 0.00075) % 1;
      g.beginPath();
      for (let i = 0; i < count; i++) {
        const d = rainDrops[i], x = ((d[0] + drift * slant * d[2]) % 1) * width, y = ((d[1] + drift * d[2]) % 1) * height;
        g.moveTo(x, y); g.lineTo(x - slant * 14, y + 14);
      }
      g.stroke(); g.restore();
      // a flash now and then in a storm, chosen from the recorded tick so it is the same on every viewing
      if (s.weather === 'storm' && !REDUCED && (k * 7919) % 9 === 0 && (now % 700) < 90) { g.fillStyle = 'rgba(230,240,255,0.16)'; g.fillRect(0, 0, width, height); }
    }
  });
})();
