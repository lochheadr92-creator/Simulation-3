"""Presentation track (OD-012): the world view is generated from a saved run
file alone, embeds that file verbatim with its digest, references nothing
outside itself, refuses shapes it does not recognise, and stays inside a
declared size and per-frame cost on a synthetic 50-person, 2,000-tick input.

The synthetic run below is a test input in the run-file shape. It is written
to a temporary directory, never under `runs/`, and is not a world execution.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys

import pytest

from viewer import world_view
from viewer.world_view import WorldViewError, load_run, render_html

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE_SIZE_BOUND = 64 * 1024 * 1024  # declared in the OD-012 card
FRAME_MS_BOUND = 4.0  # mean interpolation step on the 50 x 2,000 fixture, headless, excluding drawing

EXTERNAL_REFERENCE = re.compile(r"https?://|\bsrc=|\bhref=|url\(|@import|\bfetch\(|\bimport\(", re.IGNORECASE)


def _line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_synthetic_run(path: pathlib.Path, *, people: int, width: int, height: int, ticks: int, seed: int) -> None:
    """A run file in the recognised shape, with people who walk, eat, claim,
    yield and sometimes die. Digests are not written: this view never checks
    them, and the stream reader is the instrument that does."""
    rng = random.Random(seed)
    ids = [f"p{i + 1:02d}" for i in range(people)]
    src = [width // 2, height // 2]
    homes = {p: [rng.randrange(width), rng.randrange(height)] for p in ids}
    positions = {p: list(homes[p]) for p in ids}
    hunger = {p: 0 for p in ids}
    balances = {p: 1 for p in ids}
    yield_at = {p: rng.choice([1, 2, 3]) for p in ids}
    died_at: dict[str, int] = {}
    stock = 4
    scenario = {"name": "synthetic-50", "seed": seed, "width": width, "height": height, "actors": people,
                "source": "food", "source_position": src, "source_cap": 8, "source_stock": 4,
                "hungry_at": 5, "emergency_at": 10, "death_at": 16, "perception_radius": 3, "yield": "on",
                "scoring": "on"}
    genesis = {"tick": 0, "balances": dict(balances), "consumed": 0, "reservations": {},
               "schema_version": "v3.kernel.1b.1",
               "sources": {"food": {"authorised": list(ids), "stock": stock}}}

    def world() -> dict:
        return {"tick": 0, "positions": {p: list(v) for p, v in positions.items()}, "homes": homes,
                "hunger": dict(hunger), "died_at": dict(died_at), "yield_at": yield_at}

    lines = [_line({"kind": "header", "format": "v3.stream.2", "run_id": f"synthetic-50-seed{seed}-ticks{ticks}",
                    "engine_version": "0.2.0-stage1b", "schema_version": "v3.kernel.1b.1", "scenario": scenario,
                    "genesis": genesis, "genesis_digest": "0" * 64, "world": world(), "world_digest": "0" * 64})]
    consumed = 0
    for t in range(ticks):
        decisions, outcomes, observations = {}, [], {}
        roster = ids[t % people:] + ids[:t % people]
        living = [p for p in ids if p not in died_at]
        for p in living:
            x, y = positions[p]
            others = [{"id": q, "at": positions[q], "food": balances[q]} for q in living
                      if q != p and max(abs(positions[q][0] - x), abs(positions[q][1] - y)) <= 3]
            obs = {"others": others}
            if max(abs(src[0] - x), abs(src[1] - y)) <= 3:
                obs["source_food"] = stock
            observations[p] = obs
            h = hunger[p]
            if h >= 5 and balances[p] > 0:
                decisions[p] = {"kind": "eat", "amount": 1, "reason": f"hungry, holding {balances[p]}", "candidates": ["eat", "go"],
                                "scores": {"eat": [2, 0], "go": [0, 2 * (h - 5) + 1]}}
            elif h >= 5 and [x, y] == src:
                decisions[p] = {"kind": "claim", "amount": 2, "reason": "hungry, at source", "candidates": ["claim"], "scores": {"claim": [1, 0]}}
            elif h >= 5 and h < 10 and len(others) >= yield_at[p] and rng.random() < 0.15:
                decisions[p] = {"kind": "yield", "reason": f"hungry, saw {len(others)} near, yield_at {yield_at[p]}",
                                "candidates": ["go", "yield"], "scores": {"go": [0, 2 * (h - 5) + 1], "yield": [0, 2 * (len(others) - yield_at[p] + 1)]}}
            elif h >= 5:
                decisions[p] = {"kind": "go", "reason": "hungry, walking to source", "candidates": ["go"], "scores": {"go": [0, 2 * (h - 5) + 1]}}
            elif [x, y] == homes[p]:
                decisions[p] = {"kind": "rest", "reason": "fed, at home", "candidates": ["rest"], "scores": {"rest": [0, 0]}}
            else:
                decisions[p] = {"kind": "home", "reason": "fed, walking home", "candidates": ["home"], "scores": {"home": [0, 0]}}
        # settle in roster order: eats always succeed, claims while stock lasts
        for p in roster:
            d = decisions.get(p)
            if not d:
                continue
            if d["kind"] == "eat":
                balances[p] -= 1
                consumed += 1
                outcomes.append({"proposal_id": f"t{t}-{p}", "actor": p, "operation": "consume", "accepted": 1, "reason": "accepted",
                                 "effects": [{"account": f"actor:{p}", "delta": -1}, {"account": "sink:consumed", "delta": 1}], "sequence": 0})
                hunger[p] = max(0, hunger[p] - 6)
            elif d["kind"] == "claim":
                if stock >= 2:
                    stock -= 2
                    balances[p] += 2
                    outcomes.append({"proposal_id": f"t{t}-{p}", "actor": p, "operation": "claim", "accepted": 1, "reason": "accepted",
                                     "effects": [{"account": f"actor:{p}", "delta": 2}, {"account": "source:food", "delta": -2}], "sequence": 0})
                else:
                    outcomes.append({"proposal_id": f"t{t}-{p}", "actor": p, "operation": "claim", "accepted": 0,
                                     "reason": "denied_insufficient_source", "effects": [], "sequence": 0})
        # movement, hunger, death
        for p in living:
            d = decisions[p]
            target = src if d["kind"] in ("go",) else homes[p] if d["kind"] == "home" else None
            if target is not None:
                x, y = positions[p]
                if abs(target[0] - x) >= abs(target[1] - y) and target[0] != x:
                    x += 1 if target[0] > x else -1
                elif target[1] != y:
                    y += 1 if target[1] > y else -1
                positions[p] = [x, y]
            if d["kind"] != "eat":
                hunger[p] += 1
            if hunger[p] >= 16:
                died_at[p] = t + 1
        state = {"tick": t + 1, "balances": dict(balances), "consumed": consumed, "reservations": {},
                 "schema_version": "v3.kernel.1b.1", "sources": {"food": {"authorised": list(ids), "stock": stock}}}
        availability = {f"actor:{p}": balances[p] for p in ids}
        availability["source:food"] = stock
        availability["sink:consumed"] = consumed
        tick = {"kind": "tick", "tick": t, "record": {"tick": t, "prior_state_digest": "0" * 64, "next_state_digest": "0" * 64,
                                                       "rotated_roster": roster, "outcomes": outcomes},
                "record_digest": "0" * 64, "state": state, "state_digest": "0" * 64, "availability": availability,
                "world": {**world(), "tick": t + 1}, "world_digest": "0" * 64, "decisions": decisions, "observations": observations}
        if t % 3 == 2 and stock < 8:
            grant = min(2, 8 - stock)
            stock += grant
            tick["production"] = [{"source": "food", "amount": grant}]
            tick["produced_state_digest"] = "0" * 64
        lines.append(_line(tick))
        lines.append(_line({"kind": "timing", "tick": t, "elapsed_ns": 100000 + rng.randrange(50000)}))
    lines.append(_line({"kind": "end", "ticks": ticks, "trail_digest": "0" * 64}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def small_run(tmp_path_factory) -> pathlib.Path:
    path = tmp_path_factory.mktemp("world_view") / "small.jsonl"
    write_synthetic_run(path, people=6, width=12, height=12, ticks=40, seed=7)
    return path


@pytest.fixture(scope="module")
def large_run(tmp_path_factory) -> pathlib.Path:
    path = tmp_path_factory.mktemp("world_view_large") / "synthetic-50-2000.jsonl"
    write_synthetic_run(path, people=50, width=40, height=20, ticks=2000, seed=1)
    return path


def embedded_text(page: str) -> str:
    match = re.search(r'<script id="run-jsonl" type="application/json">(.*?)</script>', page, re.DOTALL)
    assert match, "page has no embedded run data"
    return json.loads(match.group(1))


def test_embedded_run_data_is_the_file_verbatim_and_carries_its_digest(small_run):
    run = load_run(small_run)
    page = render_html(run)
    file_digest = hashlib.sha256(small_run.read_bytes()).hexdigest()
    assert run.sha256 == file_digest
    assert f'<meta name="source-sha256" content="{file_digest}">' in page
    assert hashlib.sha256(embedded_text(page).encode("utf-8")).hexdigest() == file_digest


def test_page_references_nothing_outside_itself(small_run):
    page = render_html(load_run(small_run))
    assert not EXTERNAL_REFERENCE.search(page), EXTERNAL_REFERENCE.search(page).group(0)
    assert page.count("<script") == 3  # run data, core, ui: all inline


def test_generator_refuses_unrecognised_headers(tmp_path, small_run):
    lines = small_run.read_text(encoding="utf-8").split("\n")
    header = json.loads(lines[0])

    def variant(name: str, mutate) -> pathlib.Path:
        h = json.loads(json.dumps(header))
        mutate(h)
        p = tmp_path / f"{name}.jsonl"
        p.write_text("\n".join([_line(h), *lines[1:]]), encoding="utf-8")
        return p

    cases = {
        "format": lambda h: h.__setitem__("format", "v3.stream.9"),
        "schema": lambda h: h.__setitem__("schema_version", "v4.kernel.0"),
        "no-world": lambda h: h.pop("world"),
        "no-homes": lambda h: h["world"].pop("homes"),
        "no-thresholds": lambda h: h["scenario"].pop("emergency_at"),
        "no-source": lambda h: h["genesis"]["sources"].pop("food"),
        "not-header": lambda h: h.__setitem__("kind", "tick"),
    }
    for name, mutate in cases.items():
        with pytest.raises(WorldViewError) as info:
            load_run(variant(name, mutate))
        assert "unrecognised" in str(info.value), name
    cut = tmp_path / "cut.jsonl"
    cut.write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8")
    with pytest.raises(WorldViewError, match="no end record"):
        load_run(cut)
    assert world_view.main([str(cut)]) == 2


def test_cli_writes_the_page_beside_the_run(small_run, capsys):
    assert world_view.main([str(small_run)]) == 0
    out = small_run.with_name("small.world.html")
    assert out.is_file()
    assert "wrote" in capsys.readouterr().out
    # bytes on both sides: the page embeds the file verbatim, CRLF included if the file has it
    assert embedded_text(out.read_bytes().decode("utf-8")) == small_run.read_bytes().decode("utf-8")


def test_viewer_package_imports_nothing_from_kernel_world_or_stream():
    import ast
    for path in (ROOT / "viewer").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                names.extend(alias.name.split(".")[0] for alias in node.names)
            assert not set(names) & {"kernel", "world", "stream"}, (path.name, names)


def test_synthetic_50_by_2000_renders_inside_the_declared_size(large_run):
    run = load_run(large_run)
    assert len(run.header["world"]["positions"]) == 50 and run.tick_count == 2000
    page = render_html(run)
    size = len(page.encode("utf-8"))
    assert size < PAGE_SIZE_BOUND, f"page is {size} bytes"
    assert not EXTERNAL_REFERENCE.search(page)
    (large_run.parent / "size.txt").write_text(f"{size}\n")


NODE_HARNESS = r"""
const core = require(process.argv[2]);
const text = require('fs').readFileSync(process.argv[3], 'utf8');
const parsed = core.parseLines(text);
const m = core.buildModel(parsed.header, parsed.ticks);
const out = core.newFrame(m.P);
// exactness: at progress 0 the frame is the recorded state
for (const t of [0, 1, 777, m.n]) { core.frame(m, t, 0, out); for (let i = 0; i < m.P; i++) {
  if (Math.abs(out.x[i] - out.x[i]) > 0) throw new Error('nan');
  const k = t * m.P + i; if (Math.abs((out.x[i] - m.ox[k]) - m.px[k]) > 1e-6 || Math.abs((out.y[i] - m.oy[k]) - m.py[k]) > 1e-6) throw new Error('frame at progress 0 is not the recorded state'); } }
// timing: 600 frames spread over the run at 10 t/s, 60 fps
const frames = 600; const t0 = process.hrtime.bigint();
for (let f = 0; f < frames; f++) { const pos = (f / frames) * m.n; core.frame(m, Math.min(m.n - 1, Math.floor(pos)), pos - Math.floor(pos), out); }
const ms = Number(process.hrtime.bigint() - t0) / 1e6 / frames;
console.log(JSON.stringify({ people: m.P, ticks: m.n, frame_ms_mean: ms }));
"""


def test_frame_step_is_exact_at_progress_zero_and_cheap_on_the_large_fixture(large_run, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; headless frame timing not run")
    core = tmp_path / "core.js"
    core.write_text(world_view.JS_CORE, encoding="utf-8")
    harness = tmp_path / "harness.js"
    harness.write_text(NODE_HARNESS, encoding="utf-8")
    subprocess.run([node, "--check", str(core)], check=True)
    result = subprocess.run([node, str(harness), str(core), str(large_run)], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["people"] == 50 and report["ticks"] == 2000
    assert report["frame_ms_mean"] < FRAME_MS_BOUND, report
    (large_run.parent / "frame.txt").write_text(json.dumps(report) + "\n")


def test_page_scripts_parse_under_node(small_run, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; JavaScript syntax check not run")
    page = render_html(load_run(small_run))
    scripts = re.findall(r"<script>(.*?)</script>", page, re.DOTALL)
    assert len(scripts) == 2
    for i, body in enumerate(scripts):
        js = tmp_path / f"script{i}.js"
        js.write_text(body, encoding="utf-8")
        subprocess.run([node, "--check", str(js)], check=True)
