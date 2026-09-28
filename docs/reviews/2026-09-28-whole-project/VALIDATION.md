# Validation evidence and reproduction

## Evidence already reported by the builder

These results were recorded during implementation on 2026-09-28, before the source was committed as `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`. They are not an independent review and were not re-executed merely to package this documentation.

- Full suite: **729 passed in 211.54 seconds**. The recorded final output reported no skips. Earlier focused run: 96 passed, before one additional attribution test; the final full run includes it.
- Two prior fixed-scene social tests failed after terrain-aware departure changed behaviour. The user explicitly chose that behaviour and new causal tests. Seeds 14/26 keep full-horizon replay coverage; the former exact scenes are not asserted to recur. Review the replacement fixture critically.
- Six saved worlds (seeds 7, 11 and 23; sharing off/on; 360 ticks each) verified and replayed during implementation. Source memory, stores, homes, provisioning, coordination, fishing, regrowth and seasons were on; birth spacing was 30; other settings used defaults.
- Accepted report updates / changed food-decision ticks / living off-on: seed 7 = 8 / 0 / 18-18; seed 11 = 43 / 26 / 12-13; seed 23 = 12 / 1 / 19-21. Decision counts include consecutive ticks and early departures. They are not counts of unique trips, successful meals or isolated survival benefit.
- The seed-11 on example was inspected in a browser with p05 selected around ticks 133-150; playback and the native inspector worked without observed browser warnings/errors. This is one bounded browser check, not full visual acceptance.
- Fresh packet preparation checks cover publication, file identities, archive completeness and document consistency. They do not certify simulation correctness.

Runtime versions available during packaging: Python 3.12.14, pytest 9.1.1 and Node v24.19.0. These are the builder environment, not an established minimum-version compatibility range. `pyproject.toml` configures pytest but does not declare/install its dependency. `package-lock.json` pins the browser helper dependencies and declares Node >=20 for Playwright. Inspect source and report dependency/portability gaps rather than silently assuming all environments work.

The portable packet includes the six builder JSONL worlds, six self-contained HTML pages, their original README and summary under `builder-examples/`. These are supplementary builder artifacts, not part of the tracked source snapshot or fresh reviewer evidence. Their hashes and whether their saved Python code identity matches the pinned source are recorded in `EXAMPLE_MANIFEST.json`. The old README's localhost URL is a historical convenience, not a required server or guaranteed live link. Open the HTML directly or use your own local server.

## Establish the source and environment

Prefer a separate checkout at the full source SHA. A portable source archive contains all tracked files and required tracked historical fixtures, but no `.git`, ignored runs, installed dependencies or local environment. Verify its files against `SOURCE_MANIFEST.json`. The Git tree identity is a pin; a SHA-256 manifest establishes file-byte agreement, not the authenticity of an untrusted download by itself.

Run from the pinned source root. The following commands are a review starting point, not a complete review or commands already executed for this packet. `python` must refer to a working interpreter with pytest installed. If dependencies are missing, use your normal isolated environment and report the versions. Put Node on PATH before the suite; otherwise a viewer syntax test can skip. Browser automation is optional; if used, install locked development dependencies in your isolated copy with `npm ci` and use an available browser. Inspect helper scripts before running them.

```powershell
git rev-parse HEAD
git status --short
python --version
python -m pytest --version
node --version
python -B -m world.run --help
python -B -m pytest -q -rs -p no:cacheprovider
```

Skip Git commands for an extracted archive and use the manifest instead. Record test counts, skips, errors and exit status. Do not run tests in a shared checkout that another agent is changing. The suite selects `tests/`; it does not imply every archived script has been executed. Do not weaken tests to reach the builder's pass count.

## Targeted starting checks

Choose additional tests from `docs/ai/03_SYSTEM_MAP.md` and actual source. These groups are useful starting points, not whole-project coverage by themselves:

```powershell
python -B -m pytest -q -rs tests/test_integrity_rails.py tests/test_atomicity.py tests/test_credit_boundary.py tests/test_reservations.py tests/test_order_independence.py
python -B -m pytest -q -rs tests/test_replay.py tests/test_recovery.py tests/test_damaged_suffix.py tests/test_seal_and_prefix.py
python -B -m pytest -q -rs tests/test_travel_planning.py tests/test_social_memory.py tests/test_source_memory.py tests/test_knowledge_sharing.py tests/test_coordination.py tests/test_provisioning.py tests/test_map_viewer.py
```

Use independent probes for uncovered boundary conditions and interactions. A test named after a feature does not establish that every failure mode of that feature is covered. Inspect assertions, inputs and comparison paths.

## Generate ordinary worlds and inspect them

Use a new artifact directory or unused names; the commands write files. The example below reproduces the configuration of the sharing-on seed-11 builder example. Generate a paired off case by changing only `--knowledge-sharing off` and the output name. Seeds 7 and 23 are the other builder comparisons. Add deliberately chosen configurations for untested interactions and state why, rather than searching for a favourable scene.

```powershell
python -B -m world.run --seed 11 --ticks 360 --source-memory on --knowledge-sharing on --stores on --homes on --provisioning on --coordination on --fishing on --regrowth on --seasons on --birth-spacing 30 --out runs/review-seed11-on.jsonl --twice --html
python -B -m world.run --replay runs/review-seed11-on.jsonl
python -B -m world.viewer runs/review-seed11-on.jsonl --text 137
```

Open the generated HTML. For p05, the builder's reported scene hears a report at completed tick 133, feeds a child at 134, begins provisioning at 135 and changes destination at 137; thirst interrupts at 140, cache collection occurs at 147, eating at 148 and a home deposit at 150. Verify against native saved observations, decisions and outcomes; do not assume this narrative proves the causal claim. Explain decision tick versus completed-frame indexing.

Also exercise defaults and other feature combinations outside this sharing example. The whole-project review must assess existing behaviour, not just this recent addition. Check browser playback, timeline, selected-person inspector and console errors. A source/text assertion is not a browser interaction check.

## Recovery and adversarial files

Use a newly generated run from the pinned source, preserve its bytes, then make separate damaged copies. Start with the existing damaged-suffix and feature recovery tests to understand the seal boundary. Exercise cut points with meaningful active state, compare recovered tick contents with the uninterrupted reference, then replay the recovered result.

```powershell
python -B -m world.run --recover runs/review-cut.jsonl --out runs/review-recovered.jsonl
python -B -m world.run --replay runs/review-recovered.jsonl
```

`review-cut.jsonl` must be a deliberately created copy, not an assumed file. Document exactly how it was cut or corrupted. Distinguish expected rejection of an invalid header or incompatible rule/code identity from a defect. Do not reseal malformed inputs and call them original historical files.

Code identity hashes Python source under `kernel/`, `stream/` and `world/`, with CRLF normalized to LF; it does not depend on the Git commit or these review documents. A commit alone therefore does not change code identity. Compare a saved header's identity and rule descriptions before making replay/recovery claims. Readability, matching seals, identical replay and successful recovery are separate results.

## Honest stopping and reporting

Preserve failing output and identify the first broken boundary. Distinguish environment failure, expected rejection, actual defect and unknown cause. A whole-project PASS needs substantive coverage across the report table, including relevant execution. If tools or time prevent important checks, report INCOMPLETE or a substantiated FAIL with remaining gaps. Fill in the signature only after the report reflects work actually performed.
