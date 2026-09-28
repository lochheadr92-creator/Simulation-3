# Reviewer probes — whole-project review of 81c10b7

Run from the pinned source root with `PYTHONPATH=. python -B <probe>`.

- `kernel/attack.py` — 33 direct kernel attacks + order-independence shuffle.
- `world/accounting.py <run.jsonl>...` — independent per-tick re-derivation of totals, production, caps, dead-actor activity.
- `stream_attack.py`, `stream_attack2.py` — build 25 damaged variants of `../runs/full-7.jsonl` and drive `--replay`/`--recover`; regenerate the source run with
  `python -B -m world.run --seed 7 --ticks 300 --source-memory on --knowledge-sharing on --stores on --homes on --provisioning on --coordination on --fishing on --regrowth on --seasons on --birth-spacing 30 --out ../runs/full-7.jsonl`.
- `social/seeds.py <seed> <horizon>`, `sweep.py` — F1 activation counts; `*.out` are the recorded results.
- `social/sharing.py`, `terrain.py`, `coord.py` — rule probes (negative results, F5, F6).
- `viewer/forge.py` — F2 forged run (`forged.jsonl` included; regenerate the HTML with `python -m world.viewer forged.jsonl`).
- `viewer/browse.py`, `inject.py`, `config_probe.py` — headless-Chromium interaction checks, injection sweep, config fuzz (F4, F9).

Large generated HTML/JSONL outputs are omitted; every one is reproducible from these scripts.
