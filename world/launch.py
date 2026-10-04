"""Start, watch and resume worlds from a browser page on this machine.

    python -m world.launch            serves http://127.0.0.1:8731 and lists the saved runs
    python -m world.launch --port 9000 --runs some/folder

The page offers the named scenes, a seed, a length and the features with their rules, runs the world here, and shows the
viewer for it. While a world is still running the viewer shows the part of the run that is already saved and refreshes
itself, keeping the tick and the person you were looking at. A run that was cut short (the machine stopped, the process
was killed) can be resumed: that is the stream's own recovery, which restores the last sealed tick and carries on to the
run's planned length in a new file. A saved run is never overwritten. The server listens on this machine only and asks
for a token the page was given, so another web page cannot start runs here.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import secrets
import sys
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from stream.recover import RecoveryError
from stream.run_file import RunFileError, read_run
from world.config import WorldConfig
from world.presets import SCENES, make_config
from world.registry import FEATURES, LEVER_DEFAULTS, cross_checks, feature_problems
from world.run import DEFAULT_RUNS_DIR, run_id_for, run_world
from world.viewer import render_html

MAX_TICKS = 5000
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,200}\.jsonl$")
SPEC_KEYS = {"seed", "ticks", "features", "levers", "width", "height", "actors"}
BOUNDS = {"width": (3, 40), "height": (3, 40), "actors": (1, 40)}


class Refused(ValueError):
    """The request is not one this launcher will act on; the message is for the person who made it."""


@dataclass
class Job:
    name: str
    horizon: int
    error: str = ""
    done: bool = False
    resumed_from: str = ""


class Launcher:
    def __init__(self, runs: Path) -> None:
        self.runs = Path(runs)
        self.runs.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.threads: list[threading.Thread] = []
        self.cache: dict[tuple[str, int, int], dict[str, Any]] = {}

    # ---- what can be asked for ---------------------------------------------------------------------------
    def options(self) -> dict[str, Any]:
        return {
            "features": [{"name": name, "summary": f.summary, "rule": f.rule, "needs": list(f.needs),
                          "levers": [[k, v] for k, v in f.levers]} for name, f in sorted(FEATURES.items())],
            "scenes": [{"name": s.name, "summary": s.summary, "seed": s.seed, "ticks": s.ticks, "features": list(s.features),
                        "levers": [[k, v] for k, v in s.levers], "width": s.options.get("width", 12),
                        "height": s.options.get("height", 12), "actors": s.options.get("actors", 6)} for s in SCENES],
            "limits": {"max_ticks": MAX_TICKS, **{k: list(v) for k, v in BOUNDS.items()}},
        }

    def config_from(self, spec: Any) -> tuple[WorldConfig, int]:
        """A validated configuration and length from what the page sent, or a refusal saying why not."""
        if not isinstance(spec, dict) or set(spec) - SPEC_KEYS:
            raise Refused(f"a request holds only {', '.join(sorted(SPEC_KEYS))}")
        seed, ticks = spec.get("seed"), spec.get("ticks")
        if type(seed) is not int or not 0 <= seed < 2 ** 31:
            raise Refused("the seed must be a whole number from 0 to 2147483647")
        if type(ticks) is not int or not 1 <= ticks <= MAX_TICKS:
            raise Refused(f"the length must be a whole number of ticks from 1 to {MAX_TICKS}")
        features = spec.get("features", [])
        if not isinstance(features, list) or any(not isinstance(f, str) for f in features):
            raise Refused("features must be a list of names")
        unknown = sorted(set(features) - set(FEATURES))
        if unknown:
            raise Refused(f"unknown feature{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}")
        levers = spec.get("levers", {})
        if not isinstance(levers, dict) or any(type(v) is not int for v in levers.values()):
            raise Refused("settings must be names with whole-number values")
        unknown = sorted(set(levers) - set(LEVER_DEFAULTS))
        if unknown:
            raise Refused(f"unknown setting{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}")
        options: dict[str, Any] = {}
        for key, (low, high) in BOUNDS.items():
            if key in spec:
                if type(spec[key]) is not int or not low <= spec[key] <= high:
                    raise Refused(f"{key} must be a whole number from {low} to {high}")
                options[key] = spec[key]
        names, pairs = tuple(sorted(set(features))), tuple(sorted(levers.items()))
        problems = feature_problems(names, pairs) or cross_checks(names, pairs)       # say which rule is broken, not just that one is
        if problems:
            raise Refused("; ".join(problems))
        try:
            return make_config(seed, names, levers, options), ticks
        except ValueError as exc:
            raise Refused(str(exc)) from exc

    # ---- running and resuming -------------------------------------------------------------------------------
    def fresh_path(self, stem: str) -> Path:
        path = self.runs / f"{stem}.jsonl"
        number = 1
        while path.exists() or path.name in self.jobs:                          # a name a running job holds is taken too
            number += 1
            path = self.runs / f"{stem}-{number}.jsonl"
        return path

    def start(self, spec: Any) -> dict[str, Any]:
        config, ticks = self.config_from(spec)
        with self.lock:
            path = self.fresh_path(run_id_for(config, ticks))
            job = self.jobs[path.name] = Job(path.name, ticks)                  # the name is held from here on

        def work() -> None:
            try:
                run_world(config, ticks, path)
            except Exception as exc:                                            # shown to the person watching
                job.error = f"{type(exc).__name__}: {exc}"
            job.done = True
        self._spawn(work)
        return {"name": path.name, "ticks": ticks}

    def resume(self, name: str) -> dict[str, Any]:
        from world.recover import recover_world
        source = self.path_of(name)
        with self.lock:
            if name in self.jobs and not self.jobs[name].done:
                raise Refused("that run is still being written")
        try:
            run = read_run(source)
        except (RunFileError, ValueError) as exc:
            raise Refused(f"{name} cannot be read: {exc}") from exc
        if run.complete:
            raise Refused(f"{name} is complete; there is nothing to resume")
        with self.lock:
            target = self.fresh_path(source.stem + "-resumed")
            job = self.jobs[target.name] = Job(target.name, int(run.header.get("horizon", 0)), resumed_from=name)

        def work() -> None:
            try:
                recover_world(source, target)
            except (RecoveryError, RunFileError, ValueError, OSError) as exc:
                job.error = str(exc)
            job.done = True
        self._spawn(work)
        return {"name": target.name, "ticks": job.horizon}

    def _spawn(self, work: Any) -> None:
        thread = threading.Thread(target=work, daemon=True)
        self.threads.append(thread)
        thread.start()

    def wait(self, timeout: float = 120.0) -> None:
        for thread in list(self.threads):
            thread.join(timeout)

    # ---- what is saved ----------------------------------------------------------------------------------------
    def path_of(self, name: str) -> Path:
        if not NAME.match(name or ""):
            raise Refused("that is not the name of a saved run")
        path = (self.runs / name).resolve()
        if path.parent != self.runs.resolve() or not path.is_file():
            raise Refused("no such saved run")
        return path

    def status(self, name: str) -> dict[str, Any]:
        job = self.jobs.get(name)
        if job is not None and NAME.match(name) and not (self.runs / name).is_file():       # started, nothing written yet
            return {"name": name, "ticks": 0, "horizon": job.horizon, "complete": False, "running": not job.done,
                    "error": job.error, "cut": False, "resumed_from": job.resumed_from}
        path = self.path_of(name)
        key = (name, path.stat().st_mtime_ns, path.stat().st_size)
        if not (job and not job.done) and key in self.cache:                    # a file that has not changed reads the same
            return {**self.cache[key], "error": job.error if job else "", "resumed_from": job.resumed_from if job else ""}
        try:
            run = read_run(path)
        except (RunFileError, ValueError, OSError) as exc:
            return {"name": name, "ticks": 0, "horizon": job.horizon if job else 0, "complete": False,
                    "running": bool(job and not job.done), "error": (job.error if job else "") or f"not readable yet: {exc}",
                    "cut": False}
        horizon = int(run.header.get("horizon", len(run.ticks)))
        running = bool(job and not job.done)
        out = {"name": name, "ticks": len(run.ticks), "horizon": horizon, "complete": run.complete, "running": running,
               "error": job.error if job else "", "cut": not run.complete and not running,
               "resumed_from": job.resumed_from if job else "", "seed": (run.header.get("scenario") or {}).get("seed"),
               "features": len((run.header.get("scenario") or {}).get("features") or [])}
        if not running:
            self.cache[key] = out
        return out

    def listing(self) -> list[dict[str, Any]]:
        names = sorted((p.name for p in self.runs.glob("*.jsonl") if NAME.match(p.name)), key=lambda n: -(self.runs / n).stat().st_mtime)
        return [self.status(n) for n in names[:60]]

    def page_for(self, name: str) -> str:
        path = self.path_of(name)
        try:
            run = read_run(path)
        except (RunFileError, ValueError) as exc:
            raise Refused(f"{name} cannot be read yet: {exc}") from exc
        if not run.ticks:
            raise Refused("nothing is saved yet; try again in a moment")
        return render_html(run)


def launcher_page(token: str) -> str:
    return _PAGE.replace("@@TOKEN@@", html.escape(token, quote=True))


class Handler(BaseHTTPRequestHandler):
    server_version = "Sim3Launcher"
    launcher: Launcher
    token: str

    def log_message(self, *args: Any) -> None:                                  # quiet by default
        return

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, json.dumps(value).encode("utf-8"), "application/json; charset=utf-8")

    def _local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def do_GET(self) -> None:
        if not self._local():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "this launcher answers on this machine only"})
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/":
                return self._send(200, launcher_page(self.token).encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/options":
                return self._json(200, self.launcher.options())
            if path == "/api/runs":
                return self._json(200, self.launcher.listing())
            if path.startswith("/api/run/"):
                return self._json(200, self.launcher.status(path[len("/api/run/"):]))
            if path.startswith("/view/"):
                return self._send(200, self.launcher.page_for(path[len("/view/"):]).encode("utf-8"), "text/html; charset=utf-8")
        except Refused as exc:
            return self._json(HTTPStatus.NOT_FOUND if "no such" in str(exc) or "not the name" in str(exc) else HTTPStatus.CONFLICT,
                              {"error": str(exc)})
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._local():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "this launcher answers on this machine only"})
        if not secrets.compare_digest(self.headers.get("X-Launch-Token") or "", self.token):
            return self._json(HTTPStatus.FORBIDDEN, {"error": "missing or wrong token; reload the launcher page"})
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 20000:
                raise Refused("that request is too large")
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, Refused) as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc) if isinstance(exc, Refused) else "the request is not JSON"})
        try:
            if path == "/api/run":
                return self._json(200, self.launcher.start(body))
            if path.startswith("/api/resume/"):
                return self._json(200, self.launcher.resume(path[len("/api/resume/"):]))
        except Refused as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def make_server(runs: Path, port: int = 8731) -> tuple[ThreadingHTTPServer, Launcher, str]:
    launcher, token = Launcher(runs), secrets.token_urlsafe(18)
    handler = type("BoundHandler", (Handler,), {"launcher": launcher, "token": token})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    return server, launcher, token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start, watch and resume worlds from a browser page on this machine.")
    parser.add_argument("--port", type=int, default=8731)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS_DIR, help="folder for saved runs (default: runs/)")
    args = parser.parse_args(argv)
    server, _, _ = make_server(args.runs, args.port)
    sys.stdout.write(f"Simulation 3 launcher: http://127.0.0.1:{server.server_address[1]}/   (saved runs in {args.runs})\nCtrl-C stops it.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("stopped\n")
    return 0


_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>Simulation 3 — start a world</title>
<style>
:root { --bg:#0b1c20; --panel:#10272c; --line:rgba(170,214,200,.2); --fg:#e7f0ea; --muted:#9db4ad; --gold:#f1c56e; --bad:#ff9483; --ok:#9fdcaa; color-scheme: dark; }
* { box-sizing: border-box; } body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
.wrap { display:grid; grid-template-columns: 340px minmax(0,1fr); gap:12px; height:100vh; padding:12px; }
.col { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px; overflow:auto; }
h1 { font-size:16px; margin:0 0 8px; } h2 { font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--gold); margin:14px 0 6px; font-weight:600; }
label { display:block; margin:6px 0 2px; color:var(--muted); font-size:12px; } input, select, textarea { width:100%; background:#0b1c20; color:var(--fg); border:1px solid var(--line); border-radius:8px; padding:6px 8px; font:inherit; }
.row { display:flex; gap:8px; } .row > * { flex:1; }
.feat { display:flex; gap:6px; align-items:flex-start; margin:3px 0; } .feat input { width:auto; margin-top:3px; } .feat small { color:var(--muted); display:block; }
button { background:transparent; color:var(--fg); border:1px solid var(--gold); border-radius:8px; padding:7px 12px; cursor:pointer; font:inherit; } button:hover { background:rgba(241,197,110,.12); }
button.quiet { border-color:var(--line); } .msg { min-height:20px; margin-top:8px; font-size:13px; } .msg.bad { color:var(--bad); } .msg.ok { color:var(--ok); }
.scene { border:1px solid var(--line); border-radius:8px; padding:6px 8px; margin:4px 0; cursor:pointer; } .scene:hover { border-color:var(--gold); } .scene b { color:var(--fg); } .scene small { color:var(--muted); display:block; }
#stage { display:grid; grid-template-rows:auto minmax(0,1fr) auto; gap:8px; min-width:0; } iframe { width:100%; height:100%; border:1px solid var(--line); border-radius:10px; background:#081619; }
.runs div { display:flex; gap:8px; align-items:center; padding:4px 0; border-bottom:1px solid var(--line); font-size:12.5px; } .runs span.n { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tag { font-size:11px; border:1px solid var(--line); border-radius:999px; padding:0 7px; color:var(--muted); } .tag.cut { color:var(--bad); border-color:var(--bad); } .tag.live { color:var(--gold); border-color:var(--gold); }
@media (max-width: 900px) { .wrap { grid-template-columns:1fr; height:auto; } iframe { height:70vh; } }
</style></head><body>
<div class="wrap">
<div class="col" id="left">
  <h1>Simulation 3</h1>
  <div class="msg">Pick a scene or set your own, then start. Everything runs on this machine.</div>
  <h2>Scenes</h2><div id="scenes"></div>
  <h2>World</h2>
  <div class="row"><div><label for="seed">Seed</label><input id="seed" type="number" min="0" max="2147483647" value="7"></div>
    <div><label for="ticks">Ticks</label><input id="ticks" type="number" min="1" value="300"></div></div>
  <div class="row"><div><label for="width">Width</label><input id="width" type="number" value="12"></div>
    <div><label for="height">Height</label><input id="height" type="number" value="12"></div>
    <div><label for="actors">People</label><input id="actors" type="number" value="6"></div></div>
  <h2>Features</h2><div id="features"></div>
  <h2>Settings</h2>
  <label for="levers">One per line, name=number (each feature lists its own)</label><textarea id="levers" rows="3" placeholder="wolves=2"></textarea>
  <div class="row" style="margin-top:10px"><button id="go">Start the world</button><button class="quiet" id="again">Another seed</button></div>
  <label><input id="live" type="checkbox" checked style="width:auto"> Watch while it runs</label>
  <div class="msg" id="msg" role="status"></div>
  <h2>Saved runs</h2><div class="runs" id="runs"></div>
</div>
<div class="col" id="stage"><div class="msg" id="status">Nothing is running. Start a world, or open a saved run.</div><iframe id="view" title="The world" hidden></iframe><div class="msg" style="color:var(--muted)">The page keeps the tick and the person you are following when it refreshes. Every saved run opens on its own as a file in the runs folder.</div></div>
</div>
<script>
(function () {
  const TOKEN = "@@TOKEN@@", $ = id => document.getElementById(id);
  let options = null, current = null, timer = null, shown = 0;
  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'X-Launch-Token': TOKEN, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
  }
  const say = (t, cls) => { $('msg').textContent = t; $('msg').className = 'msg' + (cls ? ' ' + cls : ''); };
  function setScene(s) {
    $('seed').value = s.seed; $('ticks').value = s.ticks; $('width').value = s.width; $('height').value = s.height; $('actors').value = s.actors;
    document.querySelectorAll('#features input').forEach(b => { b.checked = s.features.includes(b.value); });
    $('levers').value = s.levers.map(([k, v]) => k + '=' + v).join('\n');
  }
  function spec() {
    const levers = {}; for (const line of $('levers').value.split('\n')) { const t = line.trim(); if (!t) continue; const [k, v] = t.split('='); if (!/^-?\d+$/.test((v || '').trim())) throw new Error('settings are name=number, one per line: ' + t); levers[k.trim()] = Number(v); }
    return { seed: Number($('seed').value), ticks: Number($('ticks').value), width: Number($('width').value), height: Number($('height').value), actors: Number($('actors').value),
      features: [...document.querySelectorAll('#features input:checked')].map(b => b.value), levers };
  }
  function open(name, live) {
    current = name; shown = 0; const f = $('view'); f.hidden = false; f.src = '/view/' + encodeURIComponent(name);
    clearInterval(timer); timer = setInterval(() => tick(live), 2500); tick(live, true);
  }
  async function tick(live, first) {
    if (!current) return; let s;
    try { s = await api('/api/run/' + encodeURIComponent(current)); } catch (e) { $('status').textContent = e.message; return; }
    $('status').textContent = s.error ? 'Stopped: ' + s.error : s.running ? `Running: ${s.ticks} of ${s.horizon} ticks saved` + (live ? ' — the view refreshes itself' : '') : s.complete ? `Finished: ${s.ticks} ticks, file verifies` : `Cut short at ${s.ticks} of ${s.horizon} ticks`;
    if (s.running && live && s.ticks > 0 && !first && s.ticks !== shown) {
      const f = $('view'); let hash = ''; try { hash = f.contentWindow.location.hash; } catch (e) { /* not loaded yet */ }
      shown = s.ticks; f.src = '/view/' + encodeURIComponent(current) + '?n=' + s.ticks + hash;
    }
    if (!s.running && !first) { clearInterval(timer); if (live && s.complete) { const f = $('view'); let hash = ''; try { hash = f.contentWindow.location.hash; } catch (e) {} f.src = '/view/' + encodeURIComponent(current) + '?done=1' + hash; } loadRuns(); }
  }
  async function loadRuns() {
    const runs = await api('/api/runs'), box = $('runs'); box.innerHTML = '';
    for (const r of runs) {
      const d = document.createElement('div'), n = document.createElement('span'); n.className = 'n'; n.textContent = r.name; n.title = r.name; d.appendChild(n);
      const tag = document.createElement('span'); tag.className = 'tag' + (r.cut ? ' cut' : r.running ? ' live' : ''); tag.textContent = r.running ? 'running' : r.complete ? r.ticks + ' ticks' : 'cut at ' + r.ticks + ' of ' + r.horizon; d.appendChild(tag);
      const o = document.createElement('button'); o.className = 'quiet'; o.textContent = 'Open'; o.onclick = () => open(r.name, r.running); d.appendChild(o);
      if (r.cut) { const b = document.createElement('button'); b.className = 'quiet'; b.textContent = 'Resume'; b.onclick = async () => { try { const j = await api('/api/resume/' + encodeURIComponent(r.name), {}); say('Resuming from the last sealed tick as ' + j.name, 'ok'); open(j.name, true); } catch (e) { say(e.message, 'bad'); } }; d.appendChild(b); }
      box.appendChild(d);
    }
  }
  $('go').onclick = async () => {
    try { const j = await api('/api/run', spec()); say('Started ' + j.name, 'ok'); open(j.name, $('live').checked); loadRuns(); } catch (e) { say(e.message, 'bad'); }
  };
  $('again').onclick = () => { $('seed').value = Math.floor(Math.random() * 100000); };
  (async function start() {
    options = await api('/api/options');
    const sc = $('scenes'); for (const s of options.scenes) { const d = document.createElement('div'); d.className = 'scene'; d.innerHTML = '<b></b><small></small>'; d.firstChild.textContent = s.name; d.lastChild.textContent = s.summary; d.onclick = () => { setScene(s); say('Scene "' + s.name + '" filled in. Change anything, then start.'); }; sc.appendChild(d); }
    const fb = $('features'); for (const f of options.features) { const l = document.createElement('label'); l.className = 'feat'; l.innerHTML = '<input type="checkbox"><span><b></b><small></small></span>'; l.firstChild.value = f.name; l.querySelector('b').textContent = f.name; l.querySelector('small').textContent = f.summary + (f.needs.length ? ' (needs ' + f.needs.join(', ') + ')' : '') + (f.levers.length ? ' Settings: ' + f.levers.map(([k, v]) => k + '=' + v).join(', ') : ''); l.title = f.rule; fb.appendChild(l); }
    setScene(options.scenes[0]); loadRuns();
  })().catch(e => say(e.message, 'bad'));
})();
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
