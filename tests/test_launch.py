"""The launcher: what it will and will not start, runs that finish and verify, never overwriting, watching a run while it is
written, and resuming a cut run through the stream's own recovery. The page is driven in a real browser once."""

import json
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from stream.run_file import read_run
from world.launch import make_server
from world.presets import SCENES, rich_world, scene_named
from world.registry import FEATURES

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def server(tmp_path):
    httpd, launcher, token = make_server(tmp_path / "runs", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield SimpleServer(base, launcher, token, tmp_path / "runs")
    httpd.shutdown()
    launcher.wait(60)
    httpd.server_close()


class SimpleServer:
    def __init__(self, base, launcher, token, runs):
        self.base, self.launcher, self.token, self.runs = base, launcher, token, runs

    def get(self, path, raw=False):
        try:
            with urllib.request.urlopen(self.base + path, timeout=60) as r:
                body = r.read()
                return r.status, (body if raw else json.loads(body))
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, (body if raw else json.loads(body))

    def post(self, path, body=None, token="right"):
        data = json.dumps(body if body is not None else {}).encode()
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Launch-Token"] = self.token if token == "right" else token
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def wait_done(self, name, limit=90):
        end = time.time() + limit
        while time.time() < end:
            _, status = self.get("/api/run/" + name)
            if not status["running"] and (status["complete"] or status["error"] or status.get("cut")):
                return status
            time.sleep(0.2)
        raise AssertionError("the run did not finish")


SMALL = {"seed": 7, "ticks": 40, "features": ["beliefs", "personality", "sky"]}


def test_the_options_list_every_feature_with_its_rule_and_every_scene_builds_a_valid_world(server):
    status, options = server.get("/api/options")
    assert status == 200
    assert [f["name"] for f in options["features"]] == sorted(FEATURES)
    assert all(f["summary"] and f["rule"] for f in options["features"])
    assert [s["name"] for s in options["scenes"]] == [s.name for s in SCENES] and options["limits"]["max_ticks"] > 0
    for scene in SCENES:
        assert scene.config().features == tuple(sorted(scene.features))                    # each scene is a valid configuration
    assert scene_named("explorers").config().width == 20 and rich_world(3).on("aftermath")
    with pytest.raises(ValueError):
        scene_named("nowhere")


def test_a_started_world_finishes_verifies_and_opens_in_the_viewer(server):
    status, started = server.post("/api/run", SMALL)
    assert status == 200 and started["name"].endswith(".jsonl")
    done = server.wait_done(started["name"])
    assert done["complete"] and done["ticks"] == 40 and not done["error"] and done["horizon"] == 40
    assert read_run(server.runs / started["name"]).complete
    code, page = server.get("/view/" + started["name"], raw=True)
    assert code == 200 and b'id="run-data"' in page and b"minimap" in page
    _, listing = server.get("/api/runs")
    assert [r["name"] for r in listing] == [started["name"]] and listing[0]["complete"]


def test_starting_the_same_world_twice_never_overwrites_the_first(server):
    _, first = server.post("/api/run", SMALL)
    server.wait_done(first["name"])
    before = (server.runs / first["name"]).read_bytes()
    _, second = server.post("/api/run", SMALL)
    server.wait_done(second["name"])
    assert second["name"] != first["name"] and (server.runs / first["name"]).read_bytes() == before     # the first file is untouched
    a, b = read_run(server.runs / first["name"]), read_run(server.runs / second["name"])
    assert [t["world_digest"] for t in a.ticks] == [t["world_digest"] for t in b.ticks]               # and the same seed gives the same world


@pytest.mark.parametrize("spec, fragment", [
    ({**SMALL, "seed": -1}, "seed"), ({**SMALL, "seed": "7"}, "seed"), ({**SMALL, "seed": 7.5}, "seed"),
    ({**SMALL, "ticks": 0}, "length"), ({**SMALL, "ticks": 10 ** 6}, "length"),
    ({**SMALL, "features": ["wolves"]}, "wolves needs"), ({**SMALL, "features": ["nonsense"]}, "unknown feature"),
    ({**SMALL, "features": "beliefs"}, "list"), ({**SMALL, "levers": {"couple_at": 20}}, "belongs to no feature"),
    ({**SMALL, "levers": {"nonsense": 1}}, "unknown setting"), ({**SMALL, "levers": {"wolves": "2"}}, "whole-number"),
    ({**SMALL, "width": 2}, "width"), ({**SMALL, "actors": 400}, "actors"), ({**SMALL, "cheat": 1}, "holds only"),
    ([1, 2], "holds only")])
def test_a_request_the_launcher_will_not_act_on_is_refused_with_a_reason_and_starts_nothing(server, spec, fragment):
    status, answer = server.post("/api/run", spec)
    assert status == 400 and fragment in answer["error"]
    assert not list(server.runs.glob("*.jsonl")) and not server.launcher.jobs


def test_a_request_without_the_token_or_from_another_host_is_refused(server):
    assert server.post("/api/run", SMALL, token=None)[0] == 403
    assert server.post("/api/run", SMALL, token="guess")[0] == 403
    request = urllib.request.Request(server.base + "/api/options", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=30)
    assert caught.value.code == 403
    assert not list(server.runs.glob("*.jsonl"))


@pytest.mark.parametrize("name", ["../x.jsonl", "..%2Fx.jsonl", "a/b.jsonl", "x.txt", "%00.jsonl", ".hidden.jsonl", "missing.jsonl"])
def test_only_saved_runs_in_the_runs_folder_can_be_asked_for(server, name):
    (server.runs.parent / "x.jsonl").write_text("{}")
    for path in ("/view/", "/api/run/"):
        status, _ = server.get(path + name, raw=True)
        assert status in (404, 400, 409) and status != 200


def test_a_world_that_needs_wood_gets_it_and_an_impossible_one_is_explained(server):
    for features in (["crafting"], ["structures"]):                                          # these switch wood on for themselves
        status, started = server.post("/api/run", {"seed": 7, "ticks": 20, "features": features})
        assert status == 200, started
        assert server.wait_done(started["name"])["complete"]
    status, answer = server.post("/api/run", {"seed": 7, "ticks": 20, "features": ["beliefs", "bonds", "family", "personality"], "width": 3, "height": 3, "actors": 9})
    assert status == 400 and "invalid world configuration" in answer["error"]               # a map too small for its people is explained


def test_a_run_can_be_watched_while_it_is_written_and_the_part_saved_so_far_verifies(server):
    _, started = server.post("/api/run", {"seed": 11, "ticks": 600, "features": ["beliefs", "personality", "sky", "sleep"]})
    seen = []
    end = time.time() + 90
    while time.time() < end:
        _, status = server.get("/api/run/" + started["name"])
        if status["ticks"] > 0:
            code, page = server.get("/view/" + started["name"], raw=True)
            seen.append((status["ticks"], status["running"], code, b'id="run-data"' in page))
        if status["complete"]:
            break
        time.sleep(0.1)
    assert seen and all(code == 200 and has for _, _, code, has in seen)
    assert seen[-1][0] == 600


def cut_copy(source: Path, target: Path, ticks: int) -> int:
    """A copy of a finished run cut after `ticks` tick lines, as if the machine had stopped there."""
    lines = source.read_bytes().splitlines(keepends=True)
    kept, count = [], 0
    for line in lines:
        payload = json.loads(line)
        if payload.get("kind") == "tick":
            if count == ticks:
                break
            count += 1
        elif payload.get("kind") == "end":
            break
        kept.append(line)
    target.write_bytes(b"".join(kept))
    return count


def test_a_cut_run_is_listed_as_cut_and_resumes_to_the_same_world_in_a_new_file(server):
    _, started = server.post("/api/run", {"seed": 7, "ticks": 80, "features": ["beliefs", "personality", "sky", "sleep", "wolves"]})
    server.wait_done(started["name"])
    whole = server.runs / started["name"]
    cut = server.runs / "cut-run.jsonl"
    assert cut_copy(whole, cut, 35) == 35
    _, listing = server.get("/api/runs")
    mine = next(r for r in listing if r["name"] == "cut-run.jsonl")
    assert mine["cut"] and not mine["complete"] and mine["ticks"] == 35 and mine["horizon"] == 80
    status, resumed = server.post("/api/resume/cut-run.jsonl")
    assert status == 200 and resumed["name"] == "cut-run-resumed.jsonl"
    done = server.wait_done(resumed["name"])
    assert done["complete"] and done["ticks"] == 80 and done["resumed_from"] == "cut-run.jsonl"
    original, again = read_run(whole), read_run(server.runs / resumed["name"])
    assert again.complete and [t["world_digest"] for t in again.ticks] == [t["world_digest"] for t in original.ticks]    # the same world, tick for tick
    assert cut.read_bytes() != b"" and len(read_run(cut).ticks) == 35                                                     # the cut file was left as it was
    assert server.post("/api/resume/" + started["name"])[0] == 400                                                        # a complete run has nothing to resume


def test_the_launcher_page_starts_a_world_and_shows_the_viewer_in_a_real_browser(server):
    node = shutil.which("node")
    if node is None:
        pytest.fail("The launcher test needs Node on PATH; see docs/ai/08_TESTING_AND_PROOFS.md")
    result = subprocess.run([node, str(ROOT / "tests/fixtures/launcher.cjs"), server.base], cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout)
    assert shown["errors"] == [] and shown["scenes"] == len(SCENES) and shown["features"] == len(FEATURES)
    assert "Finished" in shown["status"] and shown["viewerHasMinimap"] and shown["runs"] >= 1


def test_a_negative_length_is_refused_and_only_a_few_worlds_run_at_once(server):
    request = urllib.request.Request(server.base + "/api/run", data=b"{}", method="POST",
                                     headers={"X-Launch-Token": server.token, "Content-Length": "-1", "Content-Type": "application/json"})
    with pytest.raises((urllib.error.HTTPError, urllib.error.URLError, ConnectionError)):
        urllib.request.urlopen(request, timeout=10)                                  # refused (or the connection is dropped), never left hanging
    from world.launch import MAX_RUNNING, Job
    for i in range(MAX_RUNNING):
        server.launcher.jobs[f"busy-{i}.jsonl"] = Job(f"busy-{i}.jsonl", 10)          # worlds that are still being written
    status, answer = server.post("/api/run", SMALL)
    assert status == 400 and "already running" in answer["error"]
    assert not list(server.runs.glob("*.jsonl"))
    for job in server.launcher.jobs.values():
        job.done = True
    assert server.post("/api/run", SMALL)[0] == 200


def test_the_host_check_accepts_the_local_names_with_a_port_and_nothing_else(server):
    from world.launch import HOST
    for good in ("127.0.0.1", "127.0.0.1:8731", "localhost:9", "[::1]:8731"):
        assert HOST.fullmatch(good)
    assert not HOST.fullmatch("")
    for bad in ("evil.example", "127.0.0.1.evil.example", "localhost.evil.example:1"):
        request = urllib.request.Request(server.base + "/api/options", headers={"Host": bad})
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        assert caught.value.code == 403
