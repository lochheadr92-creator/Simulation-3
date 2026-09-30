# Testing and proof limits

## Live runtime — 2026-09-30

`python3 -B -m world.live --seed N --preset crafting [flags] --out runs/live/NAME.jsonl [--port 8000] [--no-open]`
runs a world that advances while you watch (starts paused, 1 tick/s); `--resume runs/live/NAME.jsonl`
continues a stopped or killed one into `NAME.r1.jsonl`. Controls: Pause, Resume, Step, Speed
(0.1 … 10 ticks/s, unthrottled), Stop & save; any tab may use them. Persistence: every tick is
flushed to the OS as written, fsynced on pause/stop and every 5 s. Limits: `read_run` parses the
whole file on resume (a 20,000-tick file is ~1 GB), and the page carries the last 600 ticks only.
Tests: `tests/test_live.py` (equal state however driven, pause/step precision, kill -9 + resume,
open-ended header, HTTP reconnect). Details: top WORLD_DIRECTIONS entry.


## Current browser security prerequisite — 2026-09-29

`tests/test_viewer_security.py` requires Node, the locked Playwright
development dependency and an available browser. Missing prerequisites
fail this security test explicitly; it never silently skips. Install
pytest in an isolated Python environment, run `npm ci` in the source
checkout, and on Linux/macOS run `npx playwright install chromium`.
Windows uses installed Edge by default. `V3_BROWSER_CHANNEL` can select
another installed Playwright channel. The test opens the generated page,
expands the deep section and checks the actual DOM and script marker.
The existing older Node syntax tests may still skip without Node; the
new mandatory test prevents a full-suite pass in that environment.

Fresh repair checks and their exact scope are recorded in
[repair validation](../reviews/2026-09-29-repair/VALIDATION.md).

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: pytest configuration, test/CLI source and attributed evidence records.
- Refresh trigger: when verification methodology, commands or evidence scope changes.

## Organization and status

[pyproject.toml](../../pyproject.toml) points pytest at `tests/` with the repository root on the import path. Tests cover kernel contracts, world behaviour, serialization, replay/recovery, reference fixtures, dependency direction and viewer output. Some feature tests exercise a complete saved-world lifecycle rather than a single function.

**RECORDED TEST RESULT:** [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md) reports 677 passes for the coordination work. **FRESHLY EXECUTED TEST RESULT:** none during reconnaissance or knowledge-pack creation. Documentation path/content checks do not refresh this result.

Historical artifacts in `evidence/` are not current process authority, but some are test inputs. For example, [test_reference_results.py](../../tests/test_reference_results.py) executes the recorded fixture instrument and compares the retained output. Do not delete “historical” artifacts without checking their consumers.

## What PASS establishes

| Method | Establishes within its scope | Does not establish |
| --- | --- | --- |
| Focused/unit contract test | Its asserted rule on the supplied fixtures | All configurations, population behaviour or good modelling choices |
| Integration/system test | The exercised chain across components | Untested interruptions, every saved format or broad robustness |
| File verification, read_run | Serialized digest/seal/chain checks and stored production/input consistency; semantic state reconstruction requires the reconstruction, replay or recovery paths | Historical authenticity after malicious resealing, or good world rules |
| Repeat run / --twice | Reproducible simulation trail for tested inputs/code | Rule correctness or equality of timing bytes |
| World replay | Live world_step reproduces saved tick content from configuration/genesis | Independent implementation agreement or desirable behaviour |
| Recovery comparison | Tested prefix restoration/continuation matches its reference | Every corruption pattern or compatibility with changed code |
| Viewer assertions | Tested index/rendered content is present and consistent | Successful browser playback or visual quality everywhere |
| Browser inspection | Observed scene, playback and inspector behaviour | Complete algorithmic correctness |
| Benchmark | Measured cost for the stated revision, machine and workload | Current all-feature scale or survival quality |
| Independent review | Findings within the review's pinned scope | Current HEAD validity after later changes or owner acceptance |

World replay recomputes decisions; kernel-scenario replay resubmits recorded proposals. Recovery requires compatible saved rules and matching code identity. Ordinary replay reports code-identity agreement separately from tick-content agreement. A readable legacy file is not automatically replay-compatible.

## Commands available in source

Run from the repository root with Python and pytest available. These are supported command forms, **not commands executed for this pack**. Choose fresh output filenames; do not overwrite an existing run. Commands that generate runs/viewers write artifacts.

```powershell
py -3 -B -m pytest
py -3 -B -m pytest tests/test_coordination.py tests/test_provisioning.py
py -3 -B -m pytest tests/test_replay.py tests/test_recovery.py tests/test_damaged_suffix.py
py -3 -B -m world.run --seed 7 --ticks 300 --twice --html
py -3 -B -m world.run --seed 23 --ticks 480 --stores on --homes on --provisioning on --coordination on --out runs/new-coordination.jsonl --html
py -3 -B -m world.run --replay runs/example.jsonl
py -3 -B -m world.run --recover runs/cut.jsonl --out runs/new-recovered.jsonl
py -3 -B -m world.viewer runs/example.jsonl
py -3 -B -m world.viewer runs/example.jsonl --text 40
```

The compact coordination command demonstrates switches, not reproduction of the reported 480-tick feature comparison: those examples also use other configured extensions/levers. Read the saved header or the exact fixture/configuration before claiming to reproduce a report.

The source entries are [world/run.py](../../world/run.py), [world/viewer.py](../../world/viewer.py) and pytest configuration. A focused dependency/feature selection can be obtained from [system map](03_SYSTEM_MAP.md). No separate CI workflow was found in reconnaissance.

## Causal fixtures, comparisons and regression

Controlled tests establish opportunities, choices, accepted/refused settlement, later effects and interruption paths. For example, [coordination tests](../../tests/test_coordination.py) exercise local hearing, simultaneous departures, expiry, unseen events, a delivery-to-meal chain and recovery with an active expectation. Their saved-run test checks events, replay and repeated trail digest.

The direction notes use matched seeds/configurations with a feature toggled. Trace what changed and use appropriate denominators when trajectories diverge: an announcement is not a delivery; a reroute event is not a unique successful trip; more survivors with different births is not isolated survival improvement.

Preserve reference results. For an intentional behaviour change, identify the changed rule and expected divergence; do not rewrite an old baseline to manufacture PASS. Verify new serialized state through normal running, replay, recovery and birth/structural reconstruction where relevant. Native observations, decisions, outcomes and effects are the trace; avoid a second decision implementation in analysis tooling.

## Historical benchmark scope

- [Kernel cost record](../../evidence/stage-01/slice-1d/README.md): 2026-09-25, workload `v3.bench.kernel.1`, 50 synthetic actors, seed 1, mixed claims/transfers/consumes/reservations; 1,000/10,000 ticks. Evidence was committed in `74283e3`; the exact executed source Git revision is **UNKNOWN from the inspected summary**, so that filing commit is not asserted as the execution revision. Machine: Windows 11, Core Ultra 9 285K, CPython 3.12.10. Tick cost includes settlement and evidence writing, excludes proposal generation.
- [World cost record](../../evidence/stage-02/world-cost/README.md): measured at `986a276`, 50 people, 9x9 grid, seed 1, one food source, raised food supplies, no water and historical short-range settings; same named reference machine. Tick cost includes the whole world step plus writing. Current [world.bench](../../world/bench.py) retains a one-source food-only workload. The historical README's statement about “new defaults” must not be read as measuring the current all-feature aquarium.

Both records report their targets met. Neither was rerun for this pack. The large benchmark run files were not committed. Supported future command forms are `py -3 -B -m stream.bench --ticks 10000 --out FILE --result FILE.json` and the analogous `world.bench`.

## Local artifacts and review history

`runs/` is ignored. Coordination example files existed locally during reconnaissance but are not guaranteed in a clean clone and were not freshly verified here. Recover exact configuration from a present saved header; do not invent omitted settings.

[CLAUDE_REVIEW.md](../../CLAUDE_REVIEW.md) is an attributed summary of a review of `c1d13cb`, not a review of this source HEAD. Later repairs and regression tests exist; WORLD_DIRECTIONS warns that some pre-repair quantitative results were not rerun. Historical recovery failures have subsequent repair/test records. Preserve original failures without relabelling them as current failures or assuming all later code is certified.
