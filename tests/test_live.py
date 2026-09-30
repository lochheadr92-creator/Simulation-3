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
    d2 = resume_live(tmp_path / "d.jsonl", tmp_path / "d2.jsonl")
    while d2.tick_count < 300:
        d2.advance()
    d2.writer.close()
    ref = digests(tmp_path / "a.jsonl")
    for name, path in (("speed changes", tmp_path / "b.jsonl"), ("pause/step", tmp_path / "c.jsonl"), ("stop/resume", tmp_path / "d2.jsonl")):
        run = read_run(path)
        tick = next(t for t in run.ticks if t["tick"] == 299)
        assert (tick["state_digest"], tick["world_digest"]) == ref[1:], name
    assert replay_world(tmp_path / "a.jsonl").identical and replay_world(tmp_path / "d2.jsonl").identical
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
    live = resume_live(out, tmp_path / "k2.jsonl")
    assert 150 <= live.tick_count <= 152
    while live.tick_count < 300:
        live.advance()
    live.writer.close()
    assert digests(tmp_path / "k2.jsonl")[1:] == digests(tmp_path / "ref.jsonl")[1:]
    assert replay_world(tmp_path / "k2.jsonl").identical


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
    assert len(live.writer.offsets) == RING + 20
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
    live.stop(); live.fsync(); live.writer.close()
    again = resume_live(tmp_path / "o.jsonl", tmp_path / "o2.jsonl")
    assert len(again.writer.offsets) == 40
    again.advance()
    assert len(again.writer.offsets) == 41
    from world.live import read_ticks
    ticks = read_ticks(tmp_path / "o2.jsonl", again.writer.offsets, 38, 41)
    assert [t["tick"] for t in ticks] == [38, 39, 40]
    again.writer.close()
