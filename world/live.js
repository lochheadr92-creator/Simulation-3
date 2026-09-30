// Live mode: subscribe to the server's tick stream and append recorded ticks to
// the viewer. Everything shown is what the server wrote; nothing is predicted.
//
// Two ways of following. STREAM: every tick payload arrives over SSE and is
// appended (speeds up to 2 tick/s, or faster while the tab keeps up). SAMPLE:
// the SSE carries tick numbers only; at most SAMPLE_HZ times a second the tab
// fetches the latest tick it will actually present and jumps to it. Ticks it
// never saw stay as gaps until the slider asks for them (filled from /ticks).
(() => {
  const L = window.LIVE;
  if (!L) return;
  const SAMPLE_HZ = 4, STREAM_MAX_SPEED = 2, BEHIND_LIMIT = 4;
  const $ = id => document.getElementById(id);
  const bar = document.createElement('div');
  bar.id = 'live-bar';
  bar.innerHTML = `
    <span id="live-status" class="live-status" data-testid="live-status">connecting…</span>
    <span id="live-ticks" class="live-ticks" data-testid="live-ticks"></span>
    <span id="live-mode" class="live-mode" data-testid="live-mode" title="stream: every tick is received; sample: the tab shows the latest tick a few times a second"></span>
    <button id="live-pause" type="button" data-testid="live-pause">Pause</button>
    <button id="live-resume" type="button" data-testid="live-resume">Resume</button>
    <button id="live-step" type="button" data-testid="live-step">Step</button>
    <label>Speed <select id="live-speed" data-testid="live-speed">
      <option value="0.1">0.1 (one tick every 10 s)</option>
      <option value="0.25">0.25 (one every 4 s)</option>
      <option value="0.5">0.5 (one every 2 s)</option>
      <option value="1">1 tick/s</option>
      <option value="2">2 ticks/s</option>
      <option value="5">5 ticks/s</option>
      <option value="10">10 ticks/s</option>
      <option value="0">unthrottled</option>
    </select></label>
    <label><input id="live-follow" type="checkbox" checked data-testid="live-follow"> follow live</label>
    <button id="live-stop" type="button" data-testid="live-stop">Stop &amp; save</button>`;
  document.body.prepend(bar);
  const post = body => fetch('/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  $('live-pause').onclick = () => post({ action: 'pause' });
  $('live-resume').onclick = () => post({ action: 'resume' });
  $('live-step').onclick = () => post({ action: 'step' });
  $('live-stop').onclick = () => { if (confirm('Stop the world and save? Restart later with --resume.')) post({ action: 'stop' }); };
  $('live-speed').onchange = e => post({ action: 'speed', speed: Number(e.target.value) });

  let worldTick = L.tick, paused = L.paused, speed = L.speed, stopping = false;
  let latest = L.base + window.liveTickCount();   // next tick number the stream should deliver
  let mode = 'stream', es = null, sampleTimer = null;
  const following = () => $('live-follow').checked;

  function control(s) {
    worldTick = s.tick; paused = s.paused; speed = s.speed; stopping = !!s.stopping;
    $('live-status').textContent = stopping ? 'stopped — saved; restart with --resume' : paused ? 'paused' : `running at ${speed === 0 ? 'unthrottled' : speed + ' tick/s'}`;
    $('live-speed').value = String(speed);
    $('live-pause').disabled = paused; $('live-resume').disabled = !paused || stopping;
    $('live-step').disabled = !paused || stopping;
    window.liveTweenMs = speed > 0 ? 1000 / speed : 0;
    choose();
    indicators();
  }
  function indicators() {
    const view = L.base + window.liveView();
    $('live-ticks').textContent = view === worldTick ? `world tick ${worldTick}` : `viewing tick ${view} · world at tick ${worldTick}`;
    $('live-ticks').classList.toggle('behind', view !== worldTick);
    $('live-mode').textContent = mode === 'sample' ? 'sampling latest' : 'streaming every tick';
  }
  window.liveIndicators = indicators;

  // fetch ticks [from, to) synchronously and place them; the viewer needs them before it can draw
  function fetchTicks(from, to) {
    if (from >= to) return;
    const xhr = new XMLHttpRequest(); xhr.open('GET', `/ticks?from=${from}&to=${to}`, false); xhr.send();
    for (const t of JSON.parse(xhr.responseText).ticks) window.liveAppend(t, null);
  }
  // the viewer asks for a view index it does not hold yet (scrubbing into a gap)
  window.liveFill = k => { if (!window.liveHasTick(k)) fetchTicks(L.base + k - 1, L.base + k); };

  // ---------------------------------------------------------------- stream --
  function onTick(msg) {
    const k = msg.tick.tick;
    if (k < latest) return;
    if (k > latest) fetchTicks(latest, k);
    latest = k + 1;
    window.liveAppend(msg.tick, msg.index);
    control(msg.control);
    if (mode !== 'stream') return;
    if (following()) {
      const n = window.liveTickCount(), behind = n - window.liveView();
      if (behind > 2) window.liveShow(n, false);   // drop to latest: never a growing backlog
      else if (behind >= 1) window.liveShow(window.liveView() + 1, true);
    }
  }

  // ---------------------------------------------------------------- sample --
  function sample() {
    if (mode !== 'sample' || !following() || document.hidden) return;
    const shown = L.base + window.liveView();
    if (worldTick <= shown) return;
    fetchTicks(worldTick - 1, worldTick);          // only the tick we are about to show
    latest = Math.max(latest, worldTick);
    window.liveShow(window.liveTickCount(), false);
    indicators();
  }

  // ------------------------------------------------------------------ policy --
  function choose() {
    const behind = window.liveTickCount() - window.liveView();
    let want = mode;
    if (speed === 0 || speed > STREAM_MAX_SPEED && behind > BEHIND_LIMIT) want = 'sample';
    else if (speed > 0 && speed <= STREAM_MAX_SPEED) want = 'stream';
    if (paused && mode === 'sample' && speed > 0) want = 'stream';
    if (want !== mode) { mode = want; connect(); }
  }
  function connect() {
    if (es) { es.close(); es = null; }
    if (sampleTimer) { clearInterval(sampleTimer); sampleTimer = null; }
    if (stopping) return;
    if (mode === 'sample') {
      es = new EventSource('/events?light=1');
      es.onmessage = ev => { const msg = JSON.parse(ev.data); if (msg.kind === 'tickn') { worldTick = msg.n; control(msg.control); } else control(msg); };
      sampleTimer = setInterval(sample, 1000 / SAMPLE_HZ);
    } else {
      latest = Math.max(latest, worldTick);     // after sampling, continue from the world's tick; the gap fills on scrub
      es = new EventSource(`/events?since=${latest}`);
      es.onmessage = ev => { const msg = JSON.parse(ev.data); if (msg.kind === 'tick') onTick(msg); else control(msg); };
    }
    es.onerror = () => { $('live-status').textContent = 'reconnecting…'; es.close(); es = null; setTimeout(() => { if (!es) connect(); }, 1500); };
  }
  control(L);
  if (!es) connect();
  // when the viewer's own animation reaches the latest confirmed tick but more have arrived, keep going
  setInterval(() => {
    if (mode === 'stream' && following() && !document.hidden) { const n = window.liveTickCount(); if (window.liveView() < n && !window.liveTweening()) window.liveShow(window.liveView() + 1, true); }
    indicators();
  }, 100);
})();
