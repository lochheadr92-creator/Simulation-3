# Whole-project review report

**Status: REVIEWED — verdict FAIL (bounded; see reason)**

## Identity and scope

- Reviewed source commit: `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`
- Expected source tree: `f17ceeec11372b4ff4ec1a6db82d80423d8a7466`
- Actual revision / source manifest verification: portable packet `source/` verified against `review/SOURCE_MANIFEST.json`: 609/609 files present, 609/609 SHA-256 matches, 0 missing, 0 mismatched. Extra files on disk after review are only `__pycache__`/`.pytest_cache` created by execution. Git tree identity not independently checked (no `.git` in the packet).
- Packet ZIP SHA-256: `9b63d8f436b90762729353ac7e350ca94da5b097badb0263032e7351c2e3e746` (`ce7969e0-simulation-3-whole-project-81c10b7.zip`)
- Review location and whether source was modified: extracted copy in a cloud Linux sandbox; `source/` not modified. Probes live in `probes/` and generated runs in `runs/`, both outside `source/`.
- Reviewer agent name: Claude (Claude Code harness inside the Claude app)
- Provider / model / version: Anthropic; session configured as `claude-fable-5-1` (serving model may differ). An earlier partial pass in the same session ran as `claude-haiku-4-5` and produced an INCOMPLETE draft; this report supersedes it entirely.
- Task or session identifier: `session_01DKAbAh7rjEW6jDds7rBanK`
- Review started / finished (UTC): 2026-09-28 12:31 → 2026-09-28 13:20 (approx.)
- Independence: none. I did not build, patch or advise on any of the reviewed code. Three sub-agents assisted with probing (social/sharing rules; viewer/config/tests/deps; a third for world accounting was declined by the user and I performed that part myself). Every sub-agent finding reported here was independently re-executed or source-verified by me before inclusion.
- OS, Python, pytest, Node and browser versions used: Linux 6.18 (x86_64); Python 3.11.15; pytest 9.1.1; Node v22.22.2; Chromium (Playwright build 1194, headless) for viewer checks.

## Verdict

- Verdict: **FAIL**
- Reason: The kernel, stream, replay/recovery and world accounting survive every attack tried (details below) — that core would PASS on its own. Two substantiated findings block acceptance of the project *as presented*: (F1) the recent terrain-aware departure change removed every live activation of the "remembered donor changes a recipient" rule from ordinary default worlds (0 activations in 37 seeds up to 780 ticks, versus 3 and 7 activations in seeds 14/26 under the previous departure timing), and the replacement replay test is vacuous in both seeds — its assertion loop body never executes. The builder's claim that the replacement coverage is adequate is not supported. (F2) A reproduced stored-XSS in the current viewer: an actor id from a run file is written unescaped via `innerHTML`, and because seals are unkeyed SHA-256 a forged file both executes script and displays "file verifies".
- Blocking finding IDs: F1, F2
- Essential checks not completed: interrupted multi-tick cast/build accounting probed only through the suite and the accounting sweep, not by a dedicated counterexample; browser interaction checks were headless (no human visual acceptance). Neither gap changes the verdict.

## Coverage

| Area | Coverage | Source inspected | Checks/evidence | Limits |
| --- | --- | --- | --- | --- |
| Kernel transactions, state and ordering | CHECKED | `kernel/settlement.py` (full), `kernel/proposals.py`, `kernel/state.py` (availability, totals, Reservation) | `probes/kernel/attack.py`: 33 attacks — negative/zero/bool/float/huge amounts, self-transfer, unknown actor/source/resource, overdraw, two spends > balance, credit-then-spend same tick, duplicate proposal id and actor order, contention for last unit, cross-resource mixing, deposit resource mismatch, sink debit, unknown op, reservation: spend-reserved, cancel+complete and complete+cancel same tick, foreign complete, double complete, cancel-then-spend, unknown/malformed action id, nested reserve; order independence over 20 shuffles; in-place mutation of state. All denied with a specific reason or raised at construction; totals conserved in every case. Plus suite files `test_integrity_rails/atomicity/credit_boundary/reservations/order_independence/rotation/determinism`. | Concurrency re-entry guard not exercised directly. |
| World tick ownership and resource accounting | CHECKED | `world/run.py`, `world/process.py` (advance), `stream/run_file.py` (`apply_production`, `tick_payload`) | `probes/world/accounting.py` over 4 fresh runs × 300 ticks (full-feature seeds 7, 11; defaults seed 23; wood/requests/relocation mix seed 5): per tick, recomputed totals of each resource from JSON: settlement conserves exactly; produced state digest recomputed independently from committed+production matches; births carry zero food/water; created caches have zero stock; no renewal > cap for food (8), water (12); sink monotone; no accepted proposal by a dead actor after death; no credit to a dead actor; no lingering reservations of the dead. | Noted (not a defect): units carried by people who die stay on the dead account forever — see F7. |
| Perception, needs, routes and terrain | CHECKED | `world/observe.py`, `world/decide.py` (`_route_plan`, `food_travel_ticks`, `trip_due`), `world/process.py:170-207` | `probes/social/terrain.py`: estimate vs actual arrival in open, one-rough, wall (seen and remembered), starting-on-rough, `held=1`, `hunger_rate=2`, unseen-rough cases — estimate equals actual arrival tick and arrival hunger equals `hungry_at` in every known-terrain case; unseen rough gives one-tick overshoot (documented). No double count of the cell underfoot. Dead people filtered from `others` (`observe.py:251`); knowledge fields validated `seen < heard <= tick`, witness in roster (`overlay.py:161-166`). | `held` field name is a semantic trap (means movement delay, not carried units) — F8. |
| Social memory, requests, offers and sharing | CHECKED | `world/foraging.py`, `world/social.py`, `world/storage.py`, `tests/test_social_memory.py:137-221`, `tests/test_knowledge_sharing.py` | `probes/social/sharing.py`: no relay, heard-only never spoken, expiry usable at +19 and gone at +20/+21, same-tick own sighting wins, competing same-tick reports resolved deterministically (newer wins, tie → lower id) independent of dict order, no report about a currently stocked source, repeated speech does not extend `heard`, newborns receive nothing, disabled mode writes no fields. `probes/social/seeds.py`, `sweep.py`: activation counts (F1). Causal scene trace (below). | — |
| Families, birth, death and caregiving | PARTIAL | `world/process.py` (birth/death paths), production entries | Covered through the accounting sweep (newborn zero holdings, no dead-actor activity) and suite; child-leash retargeting inspected in `_route_plan`. No dedicated caregiver-change or birth-recovery counterexample. | Dedicated probes not written. |
| Homes, stores, provisioning and coordination | CHECKED | `world/storage.py:19-27`, `world/observe.py:316-324`, `world/housing.py` | `probes/social/coord.py`: expectation timer heard+12 exact; cache check uses own visible cache only; simultaneous announcements do not deadlock; announce-without-departing impossible via decision path; expectation persists for a dead speaker (F6). Knowledge-sharing without homes is a silent no-op (F5). | — |
| Ecology, fishing, wood and construction | PARTIAL | `world/ecology.py`, `world/fishing.py`, `world/materials.py`, `process.py:183-187` | Renewal caps, seasonal renewal amounts and wood totals checked in the accounting sweep (wood total constant at 37 in the mix run; fish/food/water renewals within caps); suite `test_fishing/wood/regrowth/seasons`. | No dedicated interrupted-cast / interrupted-build counterexample. |
| Configuration, defaults and disabled modes | CHECKED | `world/config.py:147-197, 302-305, 767-772`, `world/run.py` CLI | `probes/viewer/config_probe.py`: all documented dependency rules rejected loudly; 17/18 integer levers accept `True`/`'7'` and fail late (F4); off-switch levers not serialised so `from_describe(describe())` ≠ original for 22/41 fuzzed configs but behaviourally inert (F9); several nonsensical edge values accepted silently (F9). | — |
| Streams, verification, replay and recovery | CHECKED | `stream/run_file.py`, `stream/recover.py`, `world/replay.py`, `world/recover.py` | `probes/stream_attack.py`, `probes/stream_attack2.py` on a fresh seed-7 full-feature run: truncated mid-line, invalid UTF-8 suffix, edited world field, flipped outcome, edited balance, duplicated/swapped/deleted tick line, second header, edited header config, missing end, no header, end moved early, empty file, CRLF, trailing blanks, splice of another seed's ticks from tick 200 — every one detected at the first broken boundary with a precise message; replay refused. Timing lines are outside seals (documented) — stripping or editing them leaves the run complete. Recovery from a clean cut at tick 150, a mid-line cut at tick 150, an invalid-UTF-8 suffix and an edited tick 100: all resume from the sealed prefix and reproduce the uninterrupted reference tick-for-tick; the recovered files replay identically. Cross-platform: my seed-11 sharing-on regeneration (Linux, Py 3.11) is tick-for-tick identical to the builder's Windows/Py 3.12 example including `code_identity`. | Seals are unkeyed hashes: they establish integrity against accident, not authenticity against a forger (F2 exploits this). |
| Current and older viewers, browser behaviour | CHECKED | `world/viewer.py`, `world/viewer.js`, `world/viewer_index.py`, `viewer/world_view.py` | Headless Chromium: defaults-only, full-feature 400-tick and builder seed-7/23 pages load with no console errors or page exceptions while stepping, scrubbing, playing, toggling layers, opening inspector and deep section. Injection: Python-side `html.escape` and JSON `\u003c` escaping hold everywhere except F2 (reproduced twice: sub-agent, then me — `window.__pwned === 7` after opening `#deep`). `--text N` agrees with the HTML and with `viewer.py:21`; inspector reason is native `d.reason` (`viewer.js:1250`). Two tick numberings on one page (F10). 400-tick full-feature HTML is 8.9 MB, self-contained. Older `viewer/world_view.py` refuses any run with births (every default run) — matches its stated narrower compatibility. | No human visual acceptance. |
| Tests, fixtures and independent counterexamples | CHECKED | `tests/` (all files listed), `tests/fixtures/` | Fresh full run: **729 passed, 0 skipped, 0 errors, 470 s** (`full_suite.log`). Without Node three tests would skip (`test_map_viewer.py:173`, `test_world_view.py:268,284`). No `xfail`. Three tests execute scripts under `evidence/` (documented in `08_TESTING_AND_PROOFS.md:19`). Fixture `head-b305783-seed7-ticks80-decisions.json` is consumed and compared, not regenerated. `test_dependency_direction.py` enforces kernel layering and kernel←stream←world direction and `viewer/` isolation. Vacuous loop in `test_social_memory.py:147-153` (F1); `test_claude_review_findings.py:145` has no assertion (F11); fixture uses world-unreachable `held=100` (F3). | — |
| Local operation, dependencies and helper tools | CHECKED | `pyproject.toml`, `package.json`, `package-lock.json`, `tools/` | No third-party imports in kernel/stream/world/viewer; tests need only pytest (not declared as a dependency — must be installed manually). Node only for `tools/*.js` and the `node --check` tests; `node_modules` absent until `npm install`. No hardcoded `C:\` paths in `tools/` or tests. `python -B -m world.run --help` works from the copy. No live code imports `archive/`. | — |
| Architecture, docs and historical artifact consumers | CHECKED | `docs/ai/01_ARCHITECTURE.md`, `02_INVARIANTS.md`, `05_CURRENT_STATE.md`, `06_CURRENT_SLICE.md`, `WORLD_DIRECTIONS.md`, `AGENTS.md`, `DOCTRINE.md` | Spot-checked true: Chebyshev sight (`observe.py:66`), four-neighbour steps (`decide.py:138`), default switch states and dependency rules vs `config.py`, code identity covers exactly kernel/stream/world `.py` (`run_file.py:55`). Stale: `05_CURRENT_STATE.md` still carries the "713 passed, 2 failed" account as history beside the superseding one (labelled, acceptable). `WORLD_DIRECTIONS.md:63-70` describes the replacement coverage as resolving the conflict; F1 disputes that. | — |
| Scale, ordinary-world behaviour and causal trace | CHECKED | — | Seed-11 sharing-on 360 ticks: tick p95 25.6 ms, max 60.8 ms, `--twice` determinism identical. Causal scene traced from native records (below). | Full-feature cost at larger populations not measured. |

## Findings

### [F1] [P1] Social memory no longer changes any choice in ordinary default worlds; replacement replay test is vacuous

- Classification: evidence gap / behavioural regression
- Blocking: yes — the change is presented as a clean handoff with adequate replacement coverage; the ordinary-world capability it displaced is now latent everywhere I looked and the test that replaced the fixed scenes cannot fail on that point.
- Confidence: reproduced
- Location: `tests/test_social_memory.py:141-153` (replacement test), `world/decide.py:233-252` (terrain-aware `food_travel_ticks` / `trip_due`), `world/decide.py:295+` (`someone_to_help`)
- Trigger and scope: `WorldConfig(seed=s)` defaults (terrain, routing and planned trips on) for any seed tried.
- Expected behaviour and contract: DOCTRINE principle 1 ("a positive capability claim still needs its stated successful causal chain") and principle 10 ("distinguish a demonstrated mechanism, its ordinary frequency, and its robustness"). `WORLD_DIRECTIONS.md:63-70` claims the replacement establishes the behaviour; `docs/ai/06_CURRENT_SLICE.md:22-25` says the conflict is resolved.
- Actual behaviour: seeds 7/11/23 (400 ticks), 14 (650), 26 (780) and a sweep of seeds 1–35 (400 ticks): **0** decisions with `helped_at` set and **0** `remembered_helper` events in every run, although person→person gifts (5–27 per run) and `food_memory` (populated on 509/650 ticks in seed 14) occur. Under the previous departure timing (`WorldConfig(seed=14, route_around=False)` and seed 26 likewise) the rule fires 3 and 7 times respectively. In `test_social_world_replays_with_terrain_aware_departures` the `for event in ...` loop at `:147-153` never enters its body for either seed, so the test only proves replay identity.
- Reproduction: `cd source && PYTHONPATH=. python -B ../probes/social/seeds.py 14 650` (and `26 780`); sweep outputs in `probes/social/sweep_*.out`; A/B in this report's transcript (`route_around=False`).
- Evidence: `probes/social/seed_14.out`, `seed_26.out`, `sweep_*.out`.
- Impact: the viewer never shows a remembered gift changing a choice in a default world; the encounter fixture (F3) is the only demonstration. "The world is more interesting to watch" lost a mechanism without that being stated.
- Introduced by recent changes: yes (terrain-aware departure) as far as the pinned seeds show; the ordinary frequency before the change is unknown beyond those two builder-selected scenes.
- Suggested smallest correction and regression check: either (a) state plainly in `WORLD_DIRECTIONS.md`/`06_CURRENT_SLICE.md` that social memory is currently latent in default worlds and add an assertion in the seed-14/26 test that the loop ran at least once *or* explicitly `pytest.skip`/mark it as replay-only, or (b) investigate why earlier departures suppress "two starving neighbours near one holder" encounters and decide whether that is wanted. Regression check: a seed-sweep count of `helped_at` decisions with a non-zero floor, or an honest zero recorded as a finding.

### [F2] [P2] Stored XSS in the current viewer's "Under the hood" totals; forged runs display "file verifies"

- Classification: defect (security / presentation integrity)
- Blocking: yes for acceptance of the viewer as safe to open on files from elsewhere; not an integrity failure of the simulation.
- Confidence: reproduced (twice, independently)
- Location: `world/viewer.js:1598` — `totals.deaths.slice(0, 40).map(x => x[0] + ' t' + x[1])` interpolated into `innerHTML` without `esc()`; every other run-derived string on the page is escaped.
- Trigger and scope: a run file whose actor id contains HTML (the writer never produces one, but the reader accepts any string). Seals are plain SHA-256 with no key, so a forged file can be resealed and `read_run(...).complete == True`.
- Expected behaviour and contract: all run-derived strings escaped; "file verifies" should not be readable as a tamper guarantee.
- Actual behaviour: `probes/viewer/forge.py` renames `p01` to `<img src=x onerror="window.__pwned=7">`, recomputes digests/seals; `python -m world.viewer forged.jsonl` renders and reports verifying; loading `forged.html` in headless Chromium and opening `<details id="deep">` sets `window.__pwned === 7`.
- Reproduction: `cd source && PYTHONPATH=. python -B ../probes/viewer/forge.py` then the Playwright snippet in the transcript (`probes/viewer/browse.py` has the equivalent).
- Evidence: `probes/viewer/forged.jsonl`, `probes/viewer/forged.html`.
- Impact: file:// origin, so the blast radius is the page itself (misrepresenting a run, defacement, misleading "verifies" label), not the filesystem.
- Introduced by recent changes: no (pre-existing deep-section code).
- Suggested smallest correction and regression check: `esc(x[0])` at `viewer.js:1598`; add a test rendering a run with an HTML-bearing actor id and asserting no raw `<` from ids in `RUN.details`/deep totals. Consider labelling verification as "integrity (unkeyed)" in the page.

### [F3] [P2] Encounter fixture relies on a world-unreachable state

- Classification: evidence gap
- Blocking: no on its own; contributes to F1.
- Confidence: source-demonstrated
- Location: `tests/test_social_memory.py:178` (`held={"p01":100,"p02":100}`); `world/process.py:181-182` is the only writer of `held` and sets it to exactly 1; `world/overlay.py:225` accepts any non-negative int.
- Expected/actual: the fixture pins two people for 100 ticks — a legal overlay but one the live world cannot produce. It does exercise the live `world_step` path (settlement → `remember_food` → `someone_to_help` tie-break → return transfer → viewer event → deterministic replay), so it is a valid unit+integration test of the rule, not evidence of emergence.
- Suggested correction: keep it, but rename/document it as a controlled rule test and pair it with F1's frequency assertion.

### [F4] [P3] `WorldConfig` accepts non-integer levers; failure is late or silent

- Classification: defect (validation)
- Blocking: no (CLI is protected by `type=int`; Python API callers are not).
- Confidence: reproduced
- Location: `world/config.py:147-197` type-checks only `birth_spacing` and `yield_set`.
- Actual: `seed=True`, `actors=True`, `perception_radius=True`, `hunger_rate=True`, etc. (17 of 18 integer levers) are accepted; the run then dies at `RunWriter` with `CanonicalError: booleans have no canonical form` (`kernel/canonical.py:27`) after genesis. `seed='7'` with terrain off writes a *verifying* file whose `run_id` equals seed 7's but whose homes differ (`random.Random('7')`), and `replay_world` then rejects it.
- Reproduction: `probes/viewer/config_probe.py`; `probes/viewer/strseed.jsonl`.
- Suggested correction: `type(v) is int` checks for all integer levers in `__post_init__`/`validate`; regression test parametrised over the lever list.

### [F5] [P3] `--knowledge-sharing on` without `--homes on` is a silent no-op

- Classification: modelling / usability concern
- Confidence: reproduced
- Location: `world/observe.py:320-322` (`report_listeners` requires identical `homes`); `world/config.py:767-772` samples distinct homes when homes are off; `world/process.py:314` gives newborns their own cell; validation at `config.py:156` requires only source memory.
- Actual: seeds 11 and 23, `source_memory_on=True, knowledge_sharing_on=True`, 300 ticks: `food_sightings` written on 282/300 ticks, `source_reports` on 0/300; 19/19 and 13/13 distinct homes.
- Suggested correction: require or document `homes_on`, or define "housemate" for the homes-off world.

### [F6] [P3] Listener keeps waiting for a dead announcer, even one who died in view

- Classification: modelling concern (pre-existing)
- Confidence: reproduced (`probes/social/coord.py` §2: p01 announces at tick 1 and dies at tick 1; p02 rests with `waiting_for_food=p01` until tick 13).
- Location: `world/storage.py:19-27` ends an expectation only on expiry, stocked cache, or the speaker seen at home empty-handed; deaths are invisible in observations (`observe.py:251`).
- Impact: low (12-tick cap). Out of sight this is consistent with "local evidence only"; in-view death is arguably local evidence.

### [F7] [P3] Units carried by the dead are stranded on the dead account

- Classification: modelling concern
- Confidence: reproduced (accounting sweep: seed 23 defaults, 15 deaths, 1 food left on the dead at tick 300; seed 5 mix, 2 food)
- Location: `world/process.py:203-207` records death; nothing moves the dead person's balance/holdings.
- Impact: conservation holds (totals include them) but there is no explicit rule for them, contrary to the spirit of DOCTRINE principle 5 ("loss [has] explicit rules"). Not an integrity defect.

### [F8] [P3] `held` is a semantic trap

- Classification: improvement
- Location: `world/observe.py:124` ("own remaining rough-ground movement delay"), `world/decide.py:245`.
- Note: `food_travel_ticks` correctly adds the current delay to the route cost (probed: estimates match arrivals). The field name reads as "carried units". Rename (e.g. `move_delay`) or comment at the use site.

### [F9] [P3] Config round-trip is not universal; some edge values accepted silently

- Classification: design / validation
- Confidence: reproduced (`probes/viewer/config_probe.py`)
- Actual: 22/41 fuzzed valid configs round-trip to a different dataclass because off-switch levers are not serialised; all uses are gated so replay cannot pick up wrong rules, and no `describe()` collision between behaviourally distinct configs was found. Accepted silently: `adult_at=0`/`-5`, `child_leash=-1`, `together_ticks=0`/`-1`, `seed=-1`, `perception_radius=0`, `hunger_rate=0`; `births_on` without `childhood_on`; `seasons_on` without `regrowth_on`.

### [F10] [P3] Two tick numberings on one viewer page

- Classification: presentation
- Location: HUD/slider show "Tick k" (overlay tick) while the deep section and `--text k` show "Tick k-1 — personal selection" (record tick). Consistent with `world/viewer.py:21` and with each other, but invites off-by-one reading of scenes described in `WORLD_DIRECTIONS.md`.

### [F11] [P3] Minor test/code hygiene

- `tests/test_claude_review_findings.py:145` `test_text_view_after_a_birth` has no assertion.
- `world/viewer.py:73` `_food_sources` is dead code.
- `RUN.details` (`viewer.py:145`) pre-renders text for every view: 1.7 MB of an 8.9 MB page duplicates `ticks`.
- Repeated speech: in seed 11 p09 emits the same report to p05 on eight consecutive ticks (130–137) and again 145–147. Rule-consistent (no expiry extension) but noisy in the viewer.

## Checks actually executed

| Command/check | Configuration and inputs | Exit/result, counts including skips | Evidence file | What it establishes |
| --- | --- | --- | --- | --- |
| SHA-256 of every `source/` file vs `review/SOURCE_MANIFEST.json` | packet `source/` | 609/609 match, 0 missing | transcript | Reviewed bytes are the pinned commit's tracked files |
| `python -m pytest tests/ -q -p no:cacheprovider --durations=15` | source root, Py 3.11.15, pytest 9.1.1, Node 22 on PATH | exit 0; 729 passed, 0 skipped, 0 errors, 470.41 s | `full_suite.log` | Fresh full-suite PASS in a second environment |
| `PYTHONPATH=. python -B ../probes/kernel/attack.py` | synthetic 3-actor ledger with food/water and one source | 33 attacks, all denied/raised, totals conserved; 20 shuffles order-independent | `probes/kernel/attack.py` | K1–K6 hold against direct kernel abuse |
| `python -B -m world.run --seed {7,11} --ticks 300 <full-feature flags>`, `--seed 23` defaults, `--seed 5` wood/requests/relocation mix | see transcript | 4 runs complete | `runs/*.jsonl` | Inputs for accounting and stream attacks |
| `PYTHONPATH=. python -B ../probes/world/accounting.py runs/*.jsonl` | the 4 runs | no accounting issues; renewals within caps; dead-holding notes | `probes/world/accounting.py` | Independent re-derivation of W1/K1 from saved JSON |
| `PYTHONPATH=. python -B ../probes/stream_attack.py`, `stream_attack2.py` | 25 damaged variants of `runs/full-7.jsonl`; `--replay`/`--recover` via CLI | every content/order/header attack detected; 4 recoveries identical to reference and replay identically | `runs/dmg/*` | W3/W4 hold; recovery resumes from the sealed prefix only |
| `python -B -m world.run --seed 11 --ticks 360 <builder flags> --twice --html` + tick-by-tick compare with `builder-examples/seed11-on.jsonl` | builder's exact configuration | determinism identical; 360/360 ticks, all state and world digests and `code_identity` equal | `runs/seed11-on.jsonl` | Cross-OS/Python determinism (Windows 3.12 vs Linux 3.11) |
| Causal trace of p05, ticks 127–150, from native decisions/observations/outcomes | `runs/seed11-on.jsonl` | see below | transcript | Builder's headline scene is native, not narrative |
| `PYTHONPATH=. python -B ../probes/social/seeds.py 14 650` (+ agent runs for 7/11/23/26 and sweep 1–35) | defaults | 0 `helped_at` decisions everywhere; 12 gifts in seed 14 | `probes/social/*.out` | F1 |
| A/B `WorldConfig(seed=14/26, route_around=False)` | previous departure timing | 3 and 7 `helped_at` decisions | transcript | F1 attribution |
| `probes/social/sharing.py`, `terrain.py`, `coord.py` | synthetic overlays | all sharing/terrain/coordination rules hold except F5/F6 | files | Negative results and F5/F6 |
| `probes/viewer/forge.py` + headless Chromium open of `#deep` | forged actor id | `window.__pwned === 7`, `read_run(...).complete == True` | `probes/viewer/forged.*` | F2 (reproduced by me after the sub-agent) |
| Headless Chromium load of defaults-only, full-feature 400-tick, builder seed-7/23 pages | step/scrub/play/layers/inspector/deep | 0 console errors, 0 page exceptions | `probes/viewer/browse.py` | Viewer loads and interacts cleanly on ordinary files |
| `probes/viewer/config_probe.py` | fuzzed configs | F4, F9 results | file | Validation coverage |

## Observed causal scene

Native record, `runs/seed11-on.jsonl` (seed 11, 360 ticks, sharing/source-memory/stores/homes/provisioning/coordination/fishing/regrowth/seasons on, birth spacing 30; identical to `builder-examples/seed11-on.jsonl`). Decision tick numbers below; the viewer frame is one higher.

- t128: p09 personally sees `food` empty (their `food_sightings` carry `['food', 0, 128]`).
- t130–133: p09 is p05's adjacent visible housemate and speaks each tick (`source_report` `['food', 128]`, `report_to ['p05']`). p05's `source_reports` first show `['food','p09',128,133]` in the tick-132 processed state (heard = 133). Speech accompanies p09's ordinary actions (returning, warming).
- t133: p05 `offer` → child p10 (accepted transfer −1/+1). t134: p05 starts a household `gather` trip, walking to `fish` (own memory: fish stocked at 135, food 122, food2 119). t135: casts at the bank (`source_food` 2).
- t136: own sighting `fish` 0 → reason "walking to food2; avoiding fish, remembered empty; p09 reported food empty at tick 128 (heard at 133)". This is the report changing the destination (builder frame 137).
- t138: p05's own sighting `['food', 1, 138]` — current sight overrides the report; `source_reports` cleared; reason "walking to food".
- t139–143: thirst interrupts (`go_water` at thirst 20/22/24, `draw` 3, `drink` 1 — accepted claim/consume).
- t144–147: hungry, walks to `store-p04`, claims 3 (accepted), eats 1 (accepted consume). t148: `home` (return phase). t149: `deposit` 1 into `store-p05` (accepted).
- Coordination cross-check: t137 p09 "p05 said they were getting food at tick 135; postponing my cache trip".

Interpretation (mine): the chain report → changed destination → own sight overriding → interrupt → collection → meal → deposit is fully native and consistent with the documented rules. It is a changed choice, not a rescue; the food actually eaten came from a cache, not from the redirected destination. Browser playback of this scene was not separately re-checked by me beyond the headless load tests; the builder's claim of inspector display is inherited.

## Counterexamples and negative results

- Kernel: 33 direct attacks, all denied with the correct reason; no partial commit; no same-tick reuse of credited or released units; reservation misuse (foreign complete, double complete, cancel+complete race) denied; order independence over shuffles; state objects immutable.
- Accounting: 1,200 ticks across four configurations re-derived from JSON with no total drift, no hidden production, no cap breach, no dead-actor activity.
- Streams: 25 damaged variants all detected at the first broken boundary; recovery reproduces the reference exactly from four different damage patterns. Timing lines are correctly outside seals.
- Sharing: relay, heard-only speech, off-by-one expiry, same-tick tie, dict-order dependence, stocked-source report, repeated-speech extension, newborn leakage, disabled-mode fields — none succeeded.
- Terrain estimate: matched actual arrival in every known-ground case, including `held=1` and `hunger_rate=2`.
- Coordination: timer exact, cache check local, mutual announcement no deadlock, no announce-without-departure.
- Viewer: Python-side and JSON escaping hold everywhere except `viewer.js:1598`; no console errors on ordinary files.
- Config: all documented dependency rules rejected; `birth_spacing=True`, `actors=0`, `width=1`, `claim_amount=0`, `food_sources=3`, `hungry_at==death_at` rejected.

## Unresolved limits and follow-up

- No human visual acceptance; browser checks were headless.
- No dedicated counterexample for interrupted casts/builds beyond the suite and the totals sweep.
- Frequency of social-memory activation before the departure change is known only from the two builder-pinned seeds plus my `route_around=False` A/B (which also changes movement paths, so it is not a pure reversion).
- Smallest useful next checks: (1) add a non-vacuous assertion or an explicit latent-behaviour statement for F1 and decide whether to keep the departure rule; (2) `esc(x[0])` at `viewer.js:1598` with a regression test; (3) integer type checks for all levers; (4) decide a rule for the holdings of the dead.
- Repair proposals above are proposals only; nothing under `source/` was changed.

## Reviewer signature

I attest that this report identifies the source I examined, distinguishes checks I performed from inherited claims, records known failures and incomplete coverage, and discloses my involvement in building the code. My typed name attributes this review to me; it is not a cryptographic signature or owner acceptance.

- Signed name / agent name: **Claude (Claude Code harness, with three assisting sub-agents whose findings I re-verified)**
- Provider / model (if known): Anthropic; session configured `claude-fable-5-1` (serving model may differ)
- Signed at (UTC): 2026-09-28 13:20
- Reviewed commit: `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`
- Final verdict: **FAIL** (bounded: kernel/stream/accounting core PASS in the checked scope; F1 and F2 block acceptance of the project as presented)
