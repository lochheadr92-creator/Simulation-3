// Live mode: subscribe to the server's tick stream and append recorded ticks to
// the viewer. Everything shown is what the server wrote; nothing is predicted.
(() => {
  const L = window.LIVE;
  if (!L) return;
  const $ = id => document.getElementById(id);
  const bar = document.createElement('div');
  bar.id = 'live-bar';
  bar.innerHTML = `
    <span id="live-status" class="live-status" data-testid="live-status">connecting…</span>
    <span id="live-ticks" class="live-ticks" data-testid="live-ticks"></span>
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

  let worldTick = L.tick, paused = L.paused, speed = L.speed, latest = L.base + window.liveTickCount();
  function control(s) {
    worldTick = s.tick; paused = s.paused; speed = s.speed;
    $('live-status').textContent = s.stopping ? 'stopped — saved; restart with --resume' : paused ? 'paused' : `running at ${speed === 0 ? 'unthrottled' : speed + ' tick/s'}`;
    $('live-speed').value = String(speed);
    $('live-pause').disabled = paused; $('live-resume').disabled = !paused || s.stopping;
    $('live-step').disabled = !paused || s.stopping;
    window.liveTweenMs = speed > 0 ? 1000 / speed : 0;
    indicators();
  }
  function indicators() {
    const view = L.base + window.liveView();
    $('live-ticks').textContent = view === worldTick ? `world tick ${worldTick}` : `viewing tick ${view} · world at tick ${worldTick}`;
    $('live-ticks').classList.toggle('behind', view !== worldTick);
  }
  window.liveIndicators = indicators;
  let backlog = [];
  function onTick(msg) {
    if (msg.tick.tick !== latest) { if (msg.tick.tick < latest) return; missed(msg.tick.tick); }
    latest = msg.tick.tick + 1;
    window.liveAppend(msg.tick, msg.index);
    control(msg.control);
    if ($('live-follow').checked) {
      const n = window.liveTickCount();
      const behind = n - window.liveView();
      if (behind > 2 || speed === 0) window.liveShow(n, false);   // drop to latest: never a growing backlog
      else if (behind >= 1) window.liveShow(window.liveView() + 1, true);
    }
  }
  function missed(upto) {
    const xhr = new XMLHttpRequest(); xhr.open('GET', `/ticks?from=${latest}&to=${upto}`, false); xhr.send();
    for (const t of JSON.parse(xhr.responseText).ticks) { window.liveAppend(t, null); }
    latest = upto;
  }
  function connect() {
    const es = new EventSource(`/events?since=${latest}`);
    es.onmessage = ev => { const msg = JSON.parse(ev.data); if (msg.kind === 'tick') onTick(msg); else control(msg); };
    es.onerror = () => { $('live-status').textContent = 'reconnecting…'; es.close(); setTimeout(connect, 1500); };
  }
  control(L);
  connect();
  // when the viewer's own animation reaches the latest confirmed tick but more have arrived, keep going
  setInterval(() => { if ($('live-follow').checked && !document.hidden) { const n = window.liveTickCount(); if (window.liveView() < n && !window.liveTweening()) window.liveShow(window.liveView() + 1, true); } indicators(); }, 100);
})();
