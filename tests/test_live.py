"""The live runtime: equal state at equal tick counts however the loop was
driven, pause and step precision, resume after stop and after kill -9, and
the open-ended run file that old readers still understand."""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from stream.run_file import read_run
from world.config import WorldConfig
from world.live import LIVE_HORIZON, RING, LiveWorld, make_handler, open_live, resume_live
from world.replay import replay_world

CFG = WorldConfig(seed=23, wood_on=True, yard_on=True, stone_on=True, axe_on=True, stores_on=True, provisioning_on=True,
                  homes_on=True, childhood_on=True, coordination_on=True, relocation_on=True, fishing_on=True,
                  source_memory_on=True, knowledge_sharing_on=True, shared_care_on=True)


def digests(path):
    run = read_run(path)
    last = run.ticks[-1]
    return last["tick"], last["state_digest"], last["world_digest"]


def drive(live: LiveWorld, plan):
    """Run the owner loop in a thread and apply (delay, action) controls, like tabs would."""
    thread = threading.Thread(target=live.run_forever, daemon=True)
    thread.start()
    for wait, action in plan:
        time.sleep(wait)
        action(live)
    live.stop()
    thread.join(20)


def until(live, count):
    while live.tick_count < count:
        time.sleep(0.01)


def test_equal_state_at_tick_300_however_driven(tmp_path):
    a = open_live(CFG, tmp_path / "a.jsonl")
    for _ in range(300):
        a.advance()
    a.writer.close()
    b = open_live(CFG, tmp_path / "b.jsonl")
    drive(b, [(0, lambda l: l.set_speed(0)), (0.5, lambda l: l.set_speed(10)), (0.3, lambda l: l.set_speed(0)),
              (0, lambda l: l.set_paused(False)), (0, lambda l: until(l, 300)), (0, lambda l: l.set_paused(True))])
    c = open_live(CFG, tmp_path / "c.jsonl")
    plan = [(0, lambda l: l.set_speed(0)), (0, lambda l: l.set_paused(False)), (0.2, lambda l: l.set_paused(True))]
    plan += [(0.05, lambda l: l.step())] * 3 + [(0.2, lambda l: l.set_paused(False)), (0.2, lambda l: l.set_paused(True)),
                                               (0.05, lambda l: l.step()), (0.1, lambda l: l.set_paused(False)), (0, lambda l: until(l, 300)), (0, lambda l: l.set_paused(True))]
    drive(c, plan)
    for live in (b, c):
        while live.tick_count < 300:      # the plans above stop at or past 300; top up deterministically if short
            live.advance()
    d = open_live(CFG, tmp_path / "d.jsonl")
    for _ in range(150):
        d.advance()
    d.stop(); d.fsync(); d.writer.close()
    d2 = resume_live(tmp_path / "d.jsonl")
    while d2.tick_count < 300:
        d2.advance()
    d2.writer.close()
    ref = digests(tmp_path / "a.jsonl")
    for name, path in (("speed changes", tmp_path / "b.jsonl"), ("pause/step", tmp_path / "c.jsonl"), ("stop/resume", tmp_path / "d.jsonl")):
        run = read_run(path)
        tick = next(t for t in run.ticks if t["tick"] == 299)
        assert (tick["state_digest"], tick["world_digest"]) == ref[1:], name
    assert replay_world(tmp_path / "a.jsonl").identical and replay_world(tmp_path / "d.jsonl").identical
    assert read_run(tmp_path / "a.jsonl").complete and read_run(tmp_path / "d.jsonl").complete


def test_pause_stops_the_world_and_step_adds_exactly_one(tmp_path):
    live = open_live(CFG, tmp_path / "p.jsonl")
    thread = threading.Thread(target=live.run_forever, daemon=True)
    thread.start()
    live.set_speed(10); live.set_paused(False)
    time.sleep(0.6)
    live.set_paused(True)
    time.sleep(0.15)                        # a tick already in progress may finish
    frozen = live.tick_count
    assert frozen >= 3
    time.sleep(1.0)
    assert live.tick_count == frozen
    live.step(); time.sleep(0.3)
    assert live.tick_count == frozen + 1
    live.step(); live.step(); time.sleep(0.4)
    assert live.tick_count == frozen + 3
    live.stop(); thread.join(10)
    assert read_run(tmp_path / "p.jsonl").complete


def test_kill_dash_nine_then_resume_matches_the_uninterrupted_world(tmp_path):
    ref = open_live(CFG, tmp_path / "ref.jsonl")
    for _ in range(300):
        ref.advance()
    ref.writer.close()
    out = tmp_path / "k.jsonl"
    code = ("import sys; sys.path.insert(0, '/app')\n"
            "from pathlib import Path\nfrom world.live import open_live\nfrom tests.test_live import CFG\n"
            f"live = open_live(CFG, Path({str(out)!r}))\n"
            "import sys\n"
            "for i in range(10_000):\n    live.advance()\n    print(live.tick_count, flush=True)\n")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, cwd="/app")
    while True:
        line = proc.stdout.readline()
        if int(line) >= 150:
            break
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    with out.open("ab") as fh:
        fh.write(b'{"kind":"tick","tick":9999,"partial')
    live = resume_live(out)
    assert 150 <= live.tick_count <= 152
    while live.tick_count < 300:
        live.advance()
    live.writer.close()
    assert digests(out)[1:] == digests(tmp_path / "ref.jsonl")[1:]
    assert replay_world(out).identical


def test_open_ended_header_and_http_reconnect(tmp_path):
    live = open_live(CFG, tmp_path / "h.jsonl")
    assert live.header["horizon"] == LIVE_HORIZON and live.header["open_ended"] == 1
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(live))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    thread = threading.Thread(target=live.run_forever, daemon=True)
    thread.start()

    def control(body):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/control", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    def stream(since, want):
        seen = []
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/events?since={since}") as resp:
            for raw in resp:
                if raw.startswith(b"data:"):
                    msg = json.loads(raw[5:])
                    if msg["kind"] == "tick":
                        seen.append(msg["tick"]["tick"])
                        if len(seen) >= want:
                            break
        return seen

    status = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/status").read())
    assert status["paused"] and status["speed"] == 1 and status["tick"] == 0
    control({"action": "speed", "speed": 0}); control({"action": "resume"})
    first = stream(0, 20)
    assert first == list(range(20))
    # "refresh": a second client subscribes from where the first stopped; nothing is duplicated or missed
    second = stream(first[-1] + 1, 10)
    assert second == list(range(20, 30))
    older = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/ticks?from=5&to=8").read())["ticks"]
    assert [t["tick"] for t in older] == [5, 6, 7]
    page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
    assert "window.LIVE" in page and "live-pause" in page
    control({"action": "pause"})
    time.sleep(0.3)
    frozen = live.tick_count
    time.sleep(0.5)
    assert live.tick_count == frozen
    control({"action": "stop"}); thread.join(10); server.shutdown()
    run = read_run(tmp_path / "h.jsonl")
    assert run.complete and len(run.ticks) == frozen and replay_world(tmp_path / "h.jsonl").identical


def test_light_stream_and_ticks_by_offset(tmp_path):
    live = open_live(CFG, tmp_path / "l.jsonl")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(live))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(RING + 20):
        live.advance()
    assert len(live.writer.index.exact) == RING + 20
    # ticks older than the ring come from disk by offset, in order, byte-identical to what was written
    got = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/ticks?from=3&to=6").read())["ticks"]
    assert [t["tick"] for t in got] == [3, 4, 5] and got[0]["tick"] < live.tick_count - RING
    tick_lines = [l for l in (tmp_path / "l.jsonl").read_bytes().splitlines() if b'"kind":"tick"' in l]
    assert got[0] == json.loads(tick_lines[3])
    # the light stream carries tick numbers only
    thread = threading.Thread(target=live.run_forever, daemon=True)
    thread.start()
    live.set_speed(0); live.set_paused(False)
    seen = []
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/events?light=1") as resp:
        for raw in resp:
            if raw.startswith(b"data:"):
                msg = json.loads(raw[5:])
                if msg["kind"] == "tickn":
                    assert "tick" not in msg and msg["n"] > RING
                    seen.append(msg["n"])
                    if len(seen) >= 5:
                        break
    assert seen == sorted(seen)
    live.stop(); thread.join(10); server.shutdown()
    assert read_run(tmp_path / "l.jsonl").complete


def test_resumed_live_knows_offsets_of_the_copied_prefix(tmp_path):
    live = open_live(CFG, tmp_path / "o.jsonl")
    for _ in range(40):
        live.advance()
    live.stop(); live.checkpoint(); live.writer.close()
    again = resume_live(tmp_path / "o.jsonl")
    assert again.writer.path == tmp_path / "o.jsonl"          # same file, continued in place
    again.advance()
    assert 40 in again.writer.index.exact
    from world.live import read_ticks
    ticks = read_ticks(tmp_path / "o.jsonl", again.writer.index, 38, 41)
    assert [t["tick"] for t in ticks] == [38, 39, 40]
    again.writer.close()


def test_every_speed_option_maps_to_the_server_interval(tmp_path):
    """The page's <select> values are the server's SPEEDS, in ticks per second; the
    loop sleeps 1/speed between ticks (unthrottled: no sleep)."""
    import re
    from world.live import SPEEDS
    values = re.findall(r'<option value="([^"]+)">', Path("/app/world/live.js").read_text())
    assert [float(v) for v in values] == list(SPEEDS)
    live = open_live(CFG, tmp_path / "s.jsonl")
    expected = {"0.1": 10.0, "0.25": 4.0, "0.5": 2.0, "1": 1.0, "2": 0.5, "5": 0.2, "10": 0.1, "0": None}
    for value in values:
        live.set_speed(float(value))
        assert live.interval() == expected[value], value
    live.writer.close()


def test_control_bursts_do_not_speed_the_world_up(tmp_path):
    """Fifty speed/pause-status requests a second must not add ticks: the schedule is
    `last tick + interval`, a control change only re-evaluates it. Steps while
    running are ignored."""
    live = open_live(CFG, tmp_path / "burst.jsonl")
    thread = threading.Thread(target=live.run_forever, daemon=True)
    thread.start()
    live.set_speed(2); live.set_paused(False)
    time.sleep(0.2)
    start = live.tick_count
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        live.set_speed(2); live.step()          # the storm: same speed again, and steps that mean nothing while running
        time.sleep(0.02)
    ticks = live.tick_count - start
    assert 5 <= ticks <= 7, ticks                # 2 tick/s for 3 s
    live.set_paused(True)
    time.sleep(0.6)
    frozen = live.tick_count
    time.sleep(1.5)
    assert live.tick_count == frozen and live.steps == 0
    live.stop(); thread.join(10)
    assert read_run(tmp_path / "burst.jsonl").complete


# ------------------------------------------------------------ Phase 5: worlds --
def test_random_seed_is_drawn_once_and_recorded(tmp_path):
    from world.live import Session
    live = open_live(CFG, outdir=tmp_path)
    session = Session(live, tmp_path)
    first = session.new_world(None)
    seed = first["seed"]
    header = json.loads(Path(first["path"]).open("rb").readline())
    assert header["scenario"]["seed"] == seed and header["run_id"] == first["run_id"]
    assert Path(first["path"]).name.startswith(("19", "20")) and f"-seed{seed}-" in Path(first["path"]).name
    # pause, speed, step and reconnects never touch the seed
    session.live.set_speed(2); session.live.set_paused(True); session.live.step(); time.sleep(0.3)
    assert session.status()["seed"] == seed
    session.live.stop(); session.thread.join(10)
    events = [h["event"] for h in session.history]
    assert events == ["stop", "start"]      # the first (never started) world was stopped, the new one started


def test_same_seed_and_config_reproduce_and_resume_matches(tmp_path):
    from world.live import Session
    live = open_live(CFG, outdir=tmp_path)
    session = Session(live, tmp_path)
    session.start()
    made = session.new_world(None)
    seed = made["seed"]
    a = session.live
    for _ in range(200):
        a.advance()
    # recreate from the header's seed + describe(): same genesis, same digests
    described = a.header["scenario"]
    b = open_live(WorldConfig.from_describe(described), outdir=tmp_path)   # the header alone recreates the world
    assert b.header["genesis_digest"] == a.header["genesis_digest"] and b.header["world_digest"] == a.header["world_digest"]
    assert b.header["run_id"] != a.header["run_id"] and b.writer.path != a.writer.path
    for _ in range(200):
        b.advance()
    assert a.ring[-1]["state_digest"] == b.ring[-1]["state_digest"] and a.ring[-1]["world_digest"] == b.ring[-1]["world_digest"]
    b.writer.close()
    # stop a, resume it through the session, continue to 300; compare with an uninterrupted b2 at 300
    a_path = Path(a.writer.path)
    session.live.stop(); session.thread.join(10)
    assert read_run(a_path).complete
    session.thread = None
    resumed = session.resume(a_path.name)
    assert resumed["seed"] == seed and resumed["run_id"] == a.header["run_id"] and resumed["tick"] == 200
    r = session.live
    while r.tick_count < 300:
        r.advance()
    b2 = open_live(WorldConfig.from_describe(described), outdir=tmp_path)
    for _ in range(300):
        b2.advance()
    assert r.ring[-1]["state_digest"] == b2.ring[-1]["state_digest"]
    session.live.stop(); session.thread.join(10); b2.writer.close()
    assert replay_world(Path(r.writer.path)).identical
    assert digests(Path(r.writer.path))[1:] == digests(Path(b2.writer.path))[1:]


def test_two_new_worlds_and_listing(tmp_path):
    from world.live import Session, list_worlds
    live = open_live(CFG, outdir=tmp_path)
    session = Session(live, tmp_path)
    session.start()
    session.live.set_speed(0); session.live.set_paused(False)
    time.sleep(0.4)
    first = session.new_world(None)
    session.live.set_speed(0); session.live.set_paused(False)
    time.sleep(0.4)
    second = session.new_world(None)
    assert first["seed"] != second["seed"] and first["run_id"] != second["run_id"] and first["path"] != second["path"]
    assert read_run(Path(first["path"])).complete       # stopped with an end line, intact
    assert read_run(Path(live.writer.path)).complete
    events = [(h["event"], h["file"]) for h in session.history]
    assert [e for e, _ in events] == ["start", "stop", "start", "stop", "start"]
    for i in range(1, len(session.history)):           # the log is strictly ordered: no start before the previous stop
        assert session.history[i]["at"] >= session.history[i - 1]["at"]
    worlds = list_worlds(tmp_path, Path(second["path"]))
    assert len(worlds) == 3 and sum(w["current"] for w in worlds) == 1
    by = {w["file"]: w for w in worlds}
    assert by[Path(first["path"]).name]["seed"] == first["seed"] and by[Path(first["path"]).name]["ticks"] >= 1
    session.live.stop(); session.thread.join(10)


def test_control_new_replay_resume_over_http(tmp_path):
    from world.live import Session
    live = open_live(CFG, outdir=tmp_path)
    session = Session(live, tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(session))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    session.start()

    def control(body):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/control", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    def get(path):
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}").read())

    files = lambda: sorted(p.name for p in tmp_path.glob("*.jsonl"))
    before = get("/status")
    # a reconnect / refresh creates nothing
    urllib.request.urlopen(f"http://127.0.0.1:{port}/").read()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/events?since=0") as resp:
        resp.readline()
    assert get("/status")["run_id"] == before["run_id"] and len(files()) == 1
    new = control({"action": "new", "seed": None})
    assert new["run_id"] != before["run_id"] and new["seed"] != before["seed"] and len(files()) == 2
    specific = control({"action": "new", "seed": 23})
    assert specific["seed"] == 23 and len(files()) == 3
    replayed = control({"action": "replay"})
    assert replayed["seed"] == 23 and replayed["run_id"] != specific["run_id"] and len(files()) == 4
    control({"action": "step"})
    time.sleep(0.4)
    resumed = control({"action": "resume_saved", "file": Path(specific["path"]).name})
    assert resumed["run_id"] == specific["run_id"] and resumed["seed"] == 23 and len(files()) == 4   # same file, continued
    assert resumed["path"] == specific["path"]
    worlds = get("/worlds")["worlds"]
    assert len(worlds) == 4 and all(w["seed"] is not None for w in worlds)
    assert get("/ticks?from=0&to=1")["run_id"] == resumed["run_id"]
    control({"action": "stop"}); session.thread.join(10); server.shutdown()
