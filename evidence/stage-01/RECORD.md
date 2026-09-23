# Stage 1 record — kernel only

## Status after OD-014 — 2026-09-23

Owner direction OD-014 accepts checkpoint C and closes OD-009 Revision 3.
Obtain and eat remain separate actions (OD-013; the owner's rationale is
OD-014). No same-tick obtain-and-eat. No exploration leg 7. No kernel or
world change. Stage 1 exit unclaimed. The leg-6 card below is the historical
pre-acceptance card and is not amended. The first unmet ratification
requirement, and why it is not executed in this sitting, is recorded under
"OD-014 recorded".

## Active card — exploration leg 6, revised 2026-09-22 before code

| Field | Contents |
|---|---|
| State | OD-011 revised owner direction; leg 6 implemented and checkpoint C generated from saved files. Demonstrations and comparison recorded below. Browser visual inspection blocked; no owner acceptance, ratification, leg 7 or Stage exit. |
| Scope | world decision/config/CLI/viewer, focused checks, this record and snapshot. Kernel, observations, overlay, process.py, latency and world levers fixed. |
| Identity | Inspected branch codex/kernel-first-slice at 768a454951bb2ec82ceb224a9065ecb785b31516. Only pre-existing changes: OD-011 and preceding card, preserved below. |
| Claim | Saved native GO/YIELD scored choice, recorded rotating contested settlement, saved-file HTML/text checkpoint, fixed comparison and determinism. Actual GO-over-YIELD occurrence is a separate reported result; no survival/fairness claim. |
| Definitions | OD-011 integer pairs. GO wins against eligible YIELD iff hunger >= hungry_at + seen_crowd - yield_at + 1; configured hunger >= seen_crowd - yield_at + 6. Equal pressure increment 2 for one hunger point and one seen person is an authored assumption. GO odd, YIELD even, never equal; no additional tie policy. Full kernel roster rotation includes inactive ledger actors. |
| Instrument | One live selector records actual pairs; viewer reads native scores and settlement. Focused boundary/parity, EAT/emergency, bounded/dead, order, score-tamper, atomic/roster and viewer checks; old suite/expectations intact. Previous agent's baseline report below: 308 passed in 19.06s, not rerun by this agent yet. |
| Budget and attempt | Maximum 3 whole-world runs; 3 used, 0 remaining at delivery. Seed 7, 300 ticks, yield ON: scoring ON, identical ON, OFF. Exact pre-execution declaration and attempt ledger below. Focused fixtures are not exploration runs. No tuning, additional seeds, horizon, capacity runs or reset of prior stage budgets. |
| Evidence and rollback | Append attempts/results below; preserve old files. Local commit plus push only to verified private origin under revised authority. Existing origin https://github.com/lochheadr92-creator/Simulation-3.git was reported public by GitHub get_repo on 2026-09-22: push blocked, no visibility change. Revert bounded implementation only while retaining this history. Immediate follow-up after C: owner decision on claim-then-eat latency before ratification. |

Possible crossover is not an observed finding. Scoring may shorten a yield
episode with other conditions fixed; feedback may increase or decrease whole-run
yields. Counting uses tick-start living people with hunger >= emergency_at,
native denied claim outcomes, selected yields, and saved death identities/ticks.
Timings are separate from behaviour; digest changes are not behavioural evidence.

### Leg 6 fixed execution declaration — 2026-09-22, before any exploration run

Configuration: seed 7; horizon 300; width/height 12/12; 6 people;
starting food 1 each; source at (6,6), stock 4, cap 8; renew 2 every 3 ticks;
claim at most 2; hunger +1/tick; satiation 6; hungry/emergency/death 5/10/16;
Chebyshev perception radius 3; yield ON, trait set (1,2,3), existing
homes-uniform-v1+yield-v1 generator. No lever changes between arms. Claiming
and eating remain separate actions across tick boundaries. Only scoring varies.

Budget immediately before execution: **0 of 3 used; 3 remaining**. In the exact
order below, each invocation consumes one slot, even if it fails. Existing stage
budgets stay as recorded; these commands are not confirmation or capacity work.
Fresh paths must not exist. All old files and all new attempts are retained.

Working directory for every command: `C:/dev/03-Living-World-V3`.

```powershell
py -3 -B -m world.run --seed 7 --ticks 300 --yield on --scoring on --out runs/leg6-20260922-seed7-300-on.jsonl
py -3 -B -m world.run --seed 7 --ticks 300 --yield on --scoring on --out runs/leg6-20260922-seed7-300-on-repeat.jsonl
py -3 -B -m world.run --seed 7 --ticks 300 --yield on --scoring off --out runs/leg6-20260922-seed7-300-off.jsonl
```

Read-only analysis/render commands (no execution slots):

```powershell
py -3 -B -m evidence.stage-01.leg6_compare
py -3 -B -m world.viewer runs/leg6-20260922-seed7-300-on.jsonl
py -3 -B -m world.viewer runs/leg6-20260922-seed7-300-on.jsonl --text VIEW
```

Compare OFF to `runs/one-source-grid-seed7-ticks300-yieldon.jsonl` (leg 5).
Canonical ON equality excludes only timing lines, including header and end.
Physical comparison covers genesis, world, ledger, availability, production,
observations and native settlement records; decisions compare exact shape/values.
Read-only comparison code is `leg6_compare.py`, a bounded saved-file calculation,
not a selector or a new evidence platform. It reports all scored GO/YIELD choices,
contested claim ticks and fatal accepted claims. No replacement scores are computed.
Timings use recorded tick costs, excluding stream writes, and are not a benchmark.

Focused validation before runs: first `py -3 -B -m pytest tests/test_scoring.py -q`
reported **1 failed, 14 passed (0.43s)**. The new permutation fixture left its
temporary candidates installed for the next case. Resetting that fixture between
cases fixed it without changing product code or weakening assertions. Second run:
**15 passed (0.34s)**; full unchanged reference suite plus additions:
`py -3 -B -m pytest -q`, **323 passed (19.20s)**. After adding the read-only
comparison and its known-input counting check: focused **16 passed (0.10s)**;
full result recorded below. These are focused correctness fixtures, including
existing short seeded reference tests, not the three 300-tick exploration runs.
The bundled interpreter lacked pytest; testing uses the installed `py -3`
Python 3.12 interpreter. No dependencies or reference expectations were changed.

### Leg 6 results — 2026-09-22

**Implementation and validation.** One selector ranks existing eligible actions
and records its actual score pairs in `decisions[actor].scores` only when ON.
Default/OFF retains the prior decision block. Headers declare the formula, scale
coupling, both inequalities, eligibility/tie boundaries and independent food
allocation. The viewer uses saved scores and outcomes and labels tick-start
inputs separately from post-tick consequences. HTML and text share native-field
formatting; no replacement scorer. The viewer's emergency aggregate now explicitly
counts tick-start boundaries (excludes final post-tick state); the known fixture
checks initial emergency, dead exclusion and final-boundary exclusion.

Final commands/results on Python 3.12.10:

| Command | Result |
|---|---|
| `py -3 -B -m pytest tests/test_scoring.py -q` | 16 passed, 0.10s |
| `py -3 -B -m pytest -q` | 324 passed, 18.45s (308 existing + 16 additions) |
| `git diff --check` | pass |
| `git diff --name-only -- kernel world/observe.py world/overlay.py world/process.py tests/fixtures` | empty; all preserved |
| `py -3 -B -m evidence.stage-01.leg6_compare` | all four equality checks true; required scored choice and contested tick present |
| `py -3 -B -m world.viewer runs/leg6-20260922-seed7-300-on.jsonl` | HTML generated from saved file; file verifies |
| `py -3 -B -m world.viewer runs/leg6-20260922-seed7-300-on.jsonl --text 39` | scored choice and native consequences rendered |
| Same text command with `--text 28` | contested claims, rotation, accepts/denial and effects rendered |
| `node --check runs/leg6-20260922-viewer.js` | pass (viewer JS extracted directly from world.viewer.JS) |

No old tests or reference files changed. Focused tests directly cover boundary
and parity throughout the six-person eligible domain at four hungry thresholds;
EAT/emergency; bounded/dead observations; candidate permutations; native scores;
score-block tamper detection via the existing trail; atomic multi-source denial;
full-roster rotation with inactive actors; unchanged fatal claim latency; native
HTML/text content; and counting boundaries. Tamper detection is existing stream
integrity, not adversarial authenticity or ratification of slice 1c.

**Execution ledger.** All invocations completed, all saved files verify, and
all attempts remain in `runs/`. Exactly three 300-tick executions used; no retries.

| Slot | Saved file in runs/ | Mode | Remaining |
|---|---|---|---:|
| 1 | leg6-20260922-seed7-300-on.jsonl | ON | 2 |
| 2 | leg6-20260922-seed7-300-on-repeat.jsonl | ON identical repetition | 1 |
| 3 | leg6-20260922-seed7-300-off.jsonl | OFF, yield remains ON | 0 |

**Control and reproducibility.** OFF decisions (shape and values), genesis and
physical trajectory exactly equal the saved leg-5 seed-7 yield-ON file. Both ON
files have byte-identical canonical content after excluding timing lines only.
These checks inspect native values; digest changes do not establish behaviour.
For file identification only, ON/repeat trail is
`14728773fec785f4e8802a730049cfa606c0dbd32352a034240881f2d8d2b8de`;
OFF/leg-5 trail is
`9405ee6f63146e034dcc4bb63f68b1072ffafba14f7b96ae4c0efe46ffbb070a`.

| Measure, 300 ticks | Scoring ON (repeat identical) | Scoring OFF / leg 5 |
|---|---|---|
| Survivors | 3: p01, p02, p05 | 3: p01, p03, p05 |
| Death identities / saved died_at boundary | p04:22, p06:46, p03:58 | p04:22, p02:46, p06:58 |
| Denied food claims | 6 | 5 |
| Living tick-start emergency person-ticks | 144 | 106 |
| Selected yield events | 0 | 5 |
| GO selected with YIELD still eligible | 5 | Not scored |

**Crossover occurred.** Twelve person-ticks record both GO and YIELD pairs;
five select GO, seven select higher-tier EAT. GO selections are p02 and p06 at
tick 38, p01 at ticks 50 and 51, and p02 at tick 62. At tick 38 / view 39,
p02 and p06 each start with hunger 8, yield_at 1, seen crowd 2 and source stock 0.
The configured boundary is hunger >= 7. Recorded GO `(0,7)` beats YIELD `(0,4)`.
p02 moves (4,4) -> (5,4); p06 moves (6,8) -> (6,7); both end at hunger 9.
They submit no food claim on that tick. No stock or hunger consequence is
inferred from score magnitude. At tick 17, p03 instead selects EAT `(2,0)` over
GO `(0,1)` and YIELD `(0,4)`, demonstrating the tier distinction in this run.

**Contention example.** Tick 27 / view 28 begins with source stock 4. p01, p05
and p06 each request 2 and record personal CLAIM `(1,0)`. The recorded full
rotation is p04 -> p05 -> p06 -> p01 -> p02 -> p03. p04 died at boundary 22,
remains in the kernel roster and submits nothing. p05 and p06 are accepted,
each with actor +2 and source -2. p01 is explicitly denied_insufficient_source
with no effects. Post-settlement stock is 0; no renewal that tick. There is no
claimant ranking by hunger/pressure and no winner reconstructed by the viewer.

**Timing, separately.** Recorded observation/selection/settlement/process costs
in milliseconds, excluding stream writes: ON mean 0.136776, p95 0.2122, max
0.4357; repeat mean 0.134973, p95 0.2178, max 0.2769; OFF mean 0.135635, p95
0.2088, max 0.2654. These are not capacity measurements or evidence of speedup.

**Checkpoint/artifacts.** HTML: `runs/leg6-20260922-seed7-300-on.html`.
Buttons cycle saved scored choices, GO-over-eligible-YIELD choices and contested
claims. Text views: `runs/leg6-20260922-view39-utf8.txt` (crossover),
`runs/leg6-20260922-view28-utf8.txt` (contention), and views 46/58 (fatal claims).
Full read-only comparison output: `runs/leg6-20260922-comparison.json`.
The initial PowerShell text captures (`...view39.txt`, `...view28.txt`) retained
a console encoding replacement for the em dash; they remain alongside fresh
UTF-8 exports written directly using render_text(...)/Path.write_text. No saved
run was modified or repeated. Raw runs and generated views remain local ignored
exploration output, following the existing repository policy; code, tests and
this result record are committed. They are not sealed ratification evidence.

Browser Use rejected opening the local HTML under its URL security policy.
No alternate browser surface or indirect workaround was used. HTML generation,
native-content tests and JavaScript syntax passed; actual browser visual/layout
inspection is not claimed. The saved file is available for owner inspection.

**Immediate owner decision: claim-then-eat latency, before ratification.**
In ON, p06 claims 2 at tick 45 with hunger 15, reaches hunger 16 and dies at
boundary 46 holding those 2 units. p03 repeats this at tick 57 / boundary 58.
OFF has the same pattern for p02 at 45/46 and p06 at 57/58. These are recorded
consequences of the unchanged rule, not proof of a policy improvement or of
what a counterfactual would do.

Bounded decision for the owner: retain separate claim then eat and explicitly
accept these boundary consequences, or authorise a separately scoped revision
that lets an accepted claim consume one acquired unit in the same tick. The
latter would require an explicit change to the current spendability boundary,
atomic settlement/conservation checks and new comparison authority/budget; a
world-side free credit or silent grace tick is not an implementation substitute.
Recommendation for the decision: consider the bounded same-tick obtain/eat
revision if arrival with a successful claim is intended to avert starvation.
No such change is authorised or implemented here. This decision is immediate
after C, not deferred into ratification or another behaviour leg.

**Standing and delivery.** Fixed-run demonstrations are present; no further
whole-world runs are allowed in leg 6. This is exploration delivery only, not
owner acceptance of C, general viability, fairness or survival improvement.
No orchestrator, social/memory work, leg 7, ratification or Stage exit opened.
Origin fetch/push URL remains
`https://github.com/lochheadr92-creator/Simulation-3.git`. GitHub get_repo was
checked again after the comparison: repository id 1377478590, visibility
**public**. Private push requirement is unmet; keep the bounded local commit,
do not push, merge, create a remote or change visibility.

**Changed files and rollback.** `world/config.py` owns mode/model declarations;
`world/decide.py` owns ranking and native pairs; `world/run.py` owns opt-in CLI
and distinct ON names; `world/viewer.py` owns saved-file presentation/navigation.
`tests/test_scoring.py` adds focused invariants; `leg6_compare.py` reads saved
comparisons; `AGENTS.md`, this record and `SIM3_STATE.md` preserve authority,
results and the immediate latency decision. Kernel/observation/overlay/process
and old tests are untouched. Operational rollback is `--scoring off` (default).
For source rollback, revert the leg-6 implementation files from its local commit
after checking for later work; retain the direction/result history and run files,
and update the snapshot rather than erasing declarations or evidence.

## Presentation track card — OD-012, 2026-09-22, before code

Not a leg. No behavioural objective. Does not move the active leg-6 card,
open leg 7, accept checkpoint C, or decide the claim-then-eat latency.

| Field | Contents |
|---|---|
| Objective | v1 world view: isometric 2:1 canvas render of a saved world run with smooth (interpolated) playback, per OD-012. A way to look; not an instrument, not evidence. |
| Files | `viewer/__init__.py`, `viewer/world_view.py` (generator: `.jsonl` in, `runs/<name>.world.html` out), the page template and script inside `viewer/world_view.py`, `tests/test_world_view.py`, one added test block in `tests/test_dependency_direction.py`. Nothing under `kernel/`, `world/`, `stream/` or `tests/fixtures/` changes; `world/viewer.py` is untouched. |
| Identity | Base `94523ae06957a549ffd2b98aacb3b12120f6b0f3` on `codex/kernel-first-slice`, clean tree at inspection. Inputs: `runs/leg6-20260922-seed7-300-on.jsonl` (trail `14728773…`) and `runs/leg6-20260922-seed7-300-off.jsonl` (trail `9405ee6f…`), read only. |
| Rules | OD-012 rules 1 to 5: saved files only; no import from `kernel/`, `world/` or `stream/`; one self-contained HTML per run, no external resource, no framework or install; interpolation is display only, events snap to recorded boundaries, paused/stepped frames are exact recorded state, inspect shows recorded values and band labels only; never cited for a behavioural or accounting claim, and does not verify run digests (the reader does). |
| Recognised input | Header `kind` `header`, `format` `v3.stream.2`, `schema_version` `v3.kernel.1b.1`, a `world` block with `positions`, `homes`, `hunger`, `died_at`, and a `scenario` with `width`, `height`, `source`, `source_position`, `source_cap`, `hungry_at`, `emergency_at`, `death_at`; an `end` line whose `ticks` equals the tick lines read, ticks contiguous from genesis. Anything else is refused with a message naming the field. |
| Tests | Embedded data SHA-256 equals the source file's SHA-256 (the page carries the digest); no external reference in the page (no `http`, `src=`, `href=`, `url(`, `@import`, `fetch`, `import(`); unrecognised header refused; `viewer/` imports nothing from `kernel`, `world` or `stream` (dependency-direction check extended); `node --check` on the extracted script when `node` is present, skipped with a message otherwise; synthetic 50-person, 2,000-tick fixture in the run-file shape renders and the page stays under 64 MiB; per-frame interpolation step timed headlessly in `node` on that fixture. Full suite must remain green with no reference expectation changed. |
| Budget | Zero whole-world executions. The synthetic fixture is a test input written to a temporary directory, never under `runs/`, never cited as a run. One sitting. |
| Unverifiable here | Browser layout, motion smoothness and frame rate on the owner's machine: inspected by the owner. The headless timing covers the interpolation arithmetic only, not canvas drawing. |
| Rollback | Delete `viewer/`, `tests/test_world_view.py`, the added block in `tests/test_dependency_direction.py`, and the two generated `runs/*.world.html` pages (ignored by git). Retain OD-012 and this card as history. Nothing else changes. |

### Presentation track v1 results — 2026-09-22

**Built.** `viewer/world_view.py`: generator (`py -3 -B -m viewer.world_view
runs/<run>.jsonl`, writes `runs/<run>.world.html`), a pure JS core
(`WorldViewCore`: parse lines, build typed arrays, compute one display frame)
and the page script (canvas 2D, 2:1 isometric tiles, depth-sorted sprites,
requestAnimationFrame playback with ease-in-out tween of position and hunger
colour, speed 1–20 t/s, integer scrubber, step, pan/zoom/fit, click-to-inspect
person or source, legend, footer). The page embeds the run file's complete
text as one JSON string (every less-than sign written as its JSON unicode
escape, so no byte sequence in the data can close the script element) and
carries the file's
SHA-256 in `<meta name="source-sha256">`. The generator recognises exactly
the header shape in the card and refuses anything else by name. Rule 4 as
implemented: at progress 0 the frame equals the recorded state (asserted in
`node` at ticks 0, 1, 777 and n on the synthetic fixture); the inspect panel
reads recorded positions, hunger, band label, food, trait, decision line,
scores and kernel outcomes for state/tick `t`, and re-renders on tick change
during playback, never on the tween; a person whose `died_at` is `k` stops at
boundary `k` and their marker fades over three ticks; yield rings follow the
recorded decision of tick `t`.

**Tests** (`py -3 -B -m pytest`, Python 3.12, node v24.19.0 present):

| Check | Result |
|---|---|
| `tests/test_world_view.py` + `tests/test_dependency_direction.py` | 15 passed |
| whole tree | **333 passed** in 22.89s (324 existing + 8 world-view + 1 dependency-direction), no reference expectation changed |
| embedded text SHA-256 = file SHA-256, page carries it | pass |
| page references nothing outside itself (`https?://`, `src=`, `href=`, `url(`, `@import`, `fetch(`, `import(` absent; exactly three inline scripts) | pass |
| unrecognised header refused (format, schema, no world, no homes, no thresholds, no source, not a header; cut file; CLI exit 2) | pass |
| `viewer/` imports nothing from `kernel`, `world`, `stream` (AST, both test files) | pass |
| `node --check` on the two page scripts | pass |
| synthetic 50 people × 2,000 ticks (40×20, temp dir, not a run): page 15,338,519 bytes vs bound 64 MiB; source 12.9 MB | pass |
| headless frame step on that fixture, 600 frames | mean 0.024 ms vs bound 4.0 ms |
| `git diff --check` | pass |

One test correction during the sitting: the CLI test compared the embedded
text with a newline-normalised read; on Windows the fixture has CRLF and the
page embeds it verbatim, so the comparison now reads bytes on both sides.
The generator writes the page with `newline="\n"` so page bytes are the same
on every platform. No product assertion was weakened.

**Pages** (ignored by git under `runs/`):
- `runs/leg6-20260922-seed7-300-on.world.html` — 836,900 bytes, source sha256 `5875f1038106fb94…`
- `runs/leg6-20260922-seed7-300-off.world.html` — 802,893 bytes, source sha256 `8d78bca1f78423b3…`

**Inspection.** The built-in browser refused `file://` paths (as Browser Use
did for Codex). The ON page was served from `runs/` over `127.0.0.1:8765` for
the check and the server stopped afterwards: page loads, no console output,
plays from tick 39 at 10 t/s (tick 64 after 2.5 s), 74 rAF/s in a 464×320
pane, tick 46 shows 4 alive, stock 0, and the fading marker for p06 at the
source. In the container, the synthetic 6-person page was screenshotted under
Playwright Chromium at 1400×900: layout, legend, inspect panel and playback at
61–62 rAF/s, no console errors. Full-window layout and motion smoothness on
the owner's machine remain the owner's inspection.

**Size note for the 50-person world.** The synthetic fixture came to 6.4 KB
per tick; the real leg-6 file is 2.3 KB per tick for six people, so a real
50-person 2,000-tick file may be larger than the fixture (observations scale
with neighbours in view). The page inlines the file verbatim by rule 3, so
a real 50 × 2,000 page could approach or exceed the 64 MiB bound. Recorded
as the known limit of v1; a compact projection would need a direction.

**Not done.** No push (see below). `SIM3_STATE.md` not updated (snapshot
only; the card did not list it). No kernel, world, stream, fixture or
`world/viewer.py` change. No whole-world execution.

**Origin visibility.** `git ls-remote origin` succeeds with the owner's
credentials (`codex/kernel-first-slice` at `810ab25f`); the anonymous GitHub
API returns 404 for `lochheadr92-creator/Simulation-3`, which is the
response for a private repository (Codex saw it public at 00:54 the same
day). `gh` is not installed, so no authenticated visibility field was read.
Left for the owner: say push, or not.

## Preceding card — exploration leg 6, 2026-09-21 (preserved pre-code declaration)

| Field | Contents |
|---|---|
| State | OD-011, scored existing actions and visual checkpoint C. Owner delegated the design after opening the next leg. No Stage exit or checkpoint acceptance. |
| Scope | world decision/config/CLI/viewer and focused tests; unchanged kernel, observation, overlay and world processes. |
| Identity | Base 768a454951bb2ec82ceb224a9065ecb785b31516; formula and mode declared in OD-011 and each run header. |
| Claim | Native scores drive a GO/YIELD choice; existing source contention is displayed with its actual rotating order and settlement. Authored policy, not a survival/fairness claim. |
| Definitions | OD-011 score pairs; eligibility unchanged; actor-count rotation uses the kernel roster. No new scientific counting predicate. |
| Instrument | One live selector; scores recorded at selection; viewer reads native decisions and kernel outcomes. Baseline measured this session: 308 passed in 19.06s. |
| Budget and attempt | At most 3 whole-world executions: seed 7, 300 ticks, scoring ON twice and OFF once, yield ON throughout. No tuning or additional seeds. Existing stage budgets are not renewed. |
| Evidence and rollback | Append results below. Keep leg-5 files. Revert only OD-011 implementation and its snapshot changes; preserve this record. Leg 7 remains closed. |

## Active card — Stage 1b, 2026-09-21

| Field | Contents |
|---|---|
| State | Stage 1, slice 1b under AGENTS.md OD-008. Add two-tick reservations and exactly-once completion/cancellation to the repaired 1a kernel. Stage 1 exit and independent post-repair acceptance remain pending. |
| Scope | Immutable reservation state, reserve/complete/cancel proposals, settlement phases, native lifecycle outcomes, focused kernel tests. No orchestrator work, replay/recovery, world, scheduler, capacity run or later slice. |
| Identity | Actual checkout C:/dev/03-Living-World-V3, base b915aa0c179d4e19c954f8b05eb107c4cd34d475. Kernel version advances from 0.1.1-stage1a to 0.2.0-stage1b; schema from v3.kernel.1a.1 to v3.kernel.1b.1. |
| Claim | Reserved units cannot be spent twice; atomic acquisition and settlement; owner-only cancellation/completion; cancellation wins same-boundary races; completion/release happens at most once; credits and released holds become ordinarily spendable only next tick; ordering, immutable observation and conservation remain valid. |
| Definitions | See the preregistered Stage 1b declarations immediately below. No scientific counting predicate or budget changes. |
| Instrument | Native state, reservations and tick outcomes. Existing kernel reference/review tests, explicit lifecycle negatives, exhaustive small permutations, diagnostics controls and conservation checks. Baseline before changes: 148 passed. |
| Budget and attempt | Focused deterministic correctness tests only. Whole-world and capacity runs: 0 authorised, 0 used. No exploration or confirmation run. |
| Evidence and rollback | Results and exact commands appended below; raw outputs and file identities in slice-1b/. Restore only this slice's listed files after checking for later work; retain its evidence and unrelated dirty tooling. |

### Stage 1b declarations — fixed before implementation

- `reserve` wraps one existing `claim`, `transfer` or `consume` operation. The
  existing shape, authority, balanced-effect and affordability checks apply to
  its whole frozen plan. Nested reservations and arbitrary effects are excluded.
- A hold encumbers the plan's debit accounts without moving their stock.
  Balances/source stocks include held units; the conserved total counts each
  unit once. Free availability is tick-start stock minus all existing holds.
  Accepting a new reservation immediately reduces remaining free availability.
- Settlement assigns each accepted reservation an action ID from the canonical
  digest of its creation tick, actor and engine-assigned sequence. Callers use
  the returned ID for completion/cancellation. IDs cannot be reused at later
  ticks. There is no unbounded collection of completed-action tombstones.
- A reservation created at T is first eligible for completion/cancellation at
  T+1. It remains held until its owner explicitly completes or cancels it;
  empty ticks do not invent an action or timeout. The sole cancellation cause
  in this slice is the owner's explicit request. No death/interrupt scheduler.
- Validate every submitted identity/order and authority first. Then process
  cancellations, completions, and new transactions/reservations in that order.
  Within each phase use rotated actor rank and dense actor-local sequence.
  Malformed/unauthorised cancellations cannot suppress a valid completion.
- Completion commits exactly the frozen balanced effects against its own hold,
  never against ordinary free availability. Cancellation removes only its hold.
  Neither returns debit availability to ordinary proposals during that tick.
  Completion credits and released stock are spendable at the next tick start.
- Duplicate proposal IDs/orders retain the existing deny-all rule. Distinct
  terminal requests for one action resolve in phase/sequence order; after the
  first valid close, further requests are denied as `denied_unknown_action`.
  A rejected unrelated transaction cannot cancel a reservation. New holds
  cannot be completed in their creation tick, even with a guessed action ID.
- State/views include immutable reservations. Accepted reserve outcomes expose
  the frozen plan and ID; terminal outcomes carry its ID and committed effects
  (none for cancellation). Every submission retains an explicit outcome.
- The new schema adds reservation state and action fields. Legacy no-action
  balances, effects, reasons and priority must remain unchanged. Canonical
  digests intentionally change with the schema; historical references remain
  intact and no new accepted baseline is inferred from self-verification.

### Stage 1b result — 2026-09-21

Implemented in the main simulation checkout at `C:/dev/03-Living-World-V3`,
as uncommitted changes on `codex/kernel-first-slice` based on `b915aa0`.
There is no new isolated implementation checkout to synchronize. Existing
dirty automation files, historical evidence and receipts were preserved.

`kernel/state.py` owns immutable reservations and free-stock observation;
`proposals.py` supplies reserve/complete/cancel requests; `settlement.py` owns
validation, phased resolution, hold acquisition/release and atomic effects.
`outcomes.py` records the generated action ID and frozen plan at reservation,
and the target ID and effects on closure. Ordinary account totals include held
units once. No action history accumulates after closure.

| Check | Measured result | Evidence |
|---|---|---|
| Before changes | 148 existing kernel/reference/review tests passed | [baseline.txt](slice-1b/baseline.txt) |
| First implementation run | 209 tests passed | [first.txt](slice-1b/first.txt) |
| Final kernel run | 212 passed, 0 failures/errors/skips; includes 64 lifecycle cases and all prior 148 tests | [final.txt](slice-1b/final.txt), [JUnit](slice-1b/final.xml) |
| Prior no-action fixtures | Eight ticks retain identical economic state, effects, reasons, actor sequence and ordering after removing only the declared schema/version additions and their derived digests | [current capture](slice-1b/fixtures-stage1b.json), [retained 1a capture](repair-1/fixtures-repaired.json) |
| Preservation and diff | 164 pre-existing files outside the declared edit set unchanged, including tooling and receipts; HEAD unchanged; nothing staged; whitespace check passed | [verification](slice-1b/verification.json), [source hashes](slice-1b/FILE_MANIFEST.json) |

The new tests exercise both terminal paths, repeat requests within/across ticks,
cancellation precedence, invalid cancellations, duplicate identities/orders,
owner checks, atomic multi-source acquisition and completion, source/holding
contention, next-tick release/credit rules, multiple simultaneous holds, frozen
observation, diagnostics failures, interrupted collection, commit failure,
unbounded integers and permuted input collections. No assertion or expected
historical result was weakened. The dependency declaration adds only the
lower-level canonical digest helper for engine-generated action IDs; settlement
still cannot import diagnostics or the engine.

Reproduction: [the exact final command](slice-1b/final-command.json) lists the
14 kernel test files and the existing Python 3.12 validation interpreter. Run
with `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, bytecode/cache writes disabled,
and a new writable `--basetemp`. The registered orchestrator gates and tooling
suite were not invoked. The eight native fixture ticks were captured with
`python -B evidence/stage-01/repair-1/capture_fixtures.py <repo> <fresh-output.json>`.
All actual raw results are retained; this sitting had no failing test run.

**Limits and review.** This is implemented and self-tested Stage 1b, not Stage 1
exit acceptance. Actor identity is still supplied by the caller. Cancellation
is an explicit owner request; there is no automatic deadline, death system or
scheduler. Plans may remain pending across empty ticks. Persistence, sealed
replay/recovery, capacity limits and independent acceptance remain untested or
pending in their declared later scope. Whole-world/capacity runs remain zero.
No Stage 1c work, orchestrator development, commit or push occurred.

**Rollback list, if separately requested.** Restore only the seven changed
kernel files (`__init__.py`, `state.py`, `proposals.py`, `settlement.py`,
`outcomes.py`, `reasons.py`, `version.py`) and
`tests/test_dependency_direction.py` from the recorded base, after checking
for later work. Archive the added `tests/test_reservations.py`. Retain the
OD-008 direction, this record and `slice-1b/` evidence with an appended rollback
status, and revise the roadmap's current-scope notice if needed. Do not reset
the repository or touch the pre-existing tooling changes. Nothing was reverted.

## Historical Stage 1a record (retained verbatim below)

Authority: owner direction OD-001 of 2026-09-19, recorded in `AGENTS.md`.
Only slice 1a is open. Slices 1b, 1c and 1d are not authorised, and the Stage 1
exit gate is not claimed.

**2026-09-20 update:** the adversarial review of `fa8be60` found R1–R5. Repair 1
below is authorised by OD-002. Earlier declarations, guarantees and results in
this record describe Attempt 1; they are retained as history, not a claim that the
reviewed defects passed. R1–R5 pass repair revalidation below; independent
post-repair review is pending and Stage 1 remains incomplete.

## Card

| Field | Contents |
|---|---|
| State | Stage 1, slice 1a. Objective: two authorised claimants contend for one shared resource unit, settled atomically and observed immutably. Consumer: the Stage 1b reservation slice, which needs a trustworthy availability boundary and settlement path before it can add two-tick actions. Prerequisites: none. Review status: no independent review requested or held; Stage 1 exit remains unclaimed. |
| Scope | In: immutable world state, per-actor read-only views, proposal validation, declared deterministic ordering, all-or-nothing settlement of balanced effects, immutable tick records with explicit outcome reasons, canonical serialization and digests, an inert diagnostics channel, focused deterministic tests. Owning modules: `kernel/`. Out: reservations, multi-tick or cancellable actions, replay and recovery, evidence streaming to disk, needs, movement, perception rules, memory, social behaviour, construction, viewers, plugins, a general scheduler, randomness, the six-person world and the 50-actor capacity workload. |
| Identity | Adoption revision `2bf08e9e4629022adb508b5c6db53a144bb355b4` on branch `codex/kernel-first-slice`, containing `AGENTS.md`, `DOCTRINE.md` and `ROADMAP.md` together. Declaration revision of this record, written before any kernel code existed: `bbbf142f1399c1642c567d3d9c78792610b2df0b`. Implementation revision: `b48542b3567bfba9f0fa7a831ab8ace0eb6ddc1f`. `ENGINE_VERSION = "0.1.0-stage1a"`; `SCHEMA_VERSION = "v3.kernel.1a.1"`. Owner-direction reference: OD-001. |
| Claim | Essential: one contested source unit yields exactly one credited unit and exactly one winner; an invalid or unauthorised transaction commits no part of itself; an indivisible transaction against insufficient stock is rejected without partial credit; results are independent of input-map and proposal-collection order; the declared rotation gives no permanent winner over equivalent contention at successive ticks; the roadmap's A to B transfer/consume fixture honours the next-tick availability boundary and prevents double spending; observers cannot mutate live or previously observed state; diagnostics on and off, and repeated identical execution, give identical canonical results. Integrity rails on every tick: no negative balance, conserved declared total, every committed transaction's effects sum to zero, every submitted proposal carries exactly one explicit outcome reason. Optional targets: none in this slice. |
| Definitions | See "Declarations" below: units and numeric rules, accounts and ownership, operations and balanced effects, proposal identity and the actor-local sequence, ordering and rotation, the availability boundary, outcome reasons, canonical form. |
| Instrument | The tests read the engine's own state objects and tick records through its public accessors; there is no second scorer or reconstructed ledger. Ordering is exercised by generating every permutation of the declared input maps and proposal collections, not by sampling. Null controls: an empty proposal collection, and an empty roster for the rotation rule. Known-negative controls: unauthorised claimant, insufficient source, insufficient balance, duplicate proposal identity, duplicate actor sequence, unbalanced effects, non-integer and non-positive amounts. Deliberate failure case: a diagnostics sink that attempts to mutate what it is handed. Validation result recorded under Results. |
| Budget and attempt | Focused deterministic fixtures only. Whole-world executions authorised: 0. Used: 0. Remaining: 0. Capacity runs authorised: 0. No exploration levers are declared, because this slice answers a correctness question, not a design question. |
| Evidence and rollback | Commands, results and rollback list recorded under Results and Rollback below. |

## Declarations

These are fixed before implementation. Changing any of them after a recorded
result creates a new attempt; it does not revise an existing one.

### Units and numeric rules

- One resource kind exists in this slice, named `unit`. It is abstract; it
  acquires meaning in Stage 2, not here.
- All quantities are Python integers. No floating-point value may enter state,
  a proposal, a tick record, or the canonical form; canonical serialization
  rejects them rather than formatting them.
- `bool` is rejected as a quantity even though Python treats it as an integer.
- Balances and source stocks are integers greater than or equal to zero, with no
  upper bound.
- A transaction amount is an integer greater than or equal to one. Zero and
  negative amounts are malformed, not no-ops.
- Units are indivisible: a transaction moves its exact declared amounts or
  nothing. There is no fractional or partial credit.
- Conserved total, asserted after every tick:
  `sum(source stocks) + sum(actor balances) + consumption sink`.

### Accounts and ownership

Three account kinds, addressed as `source:<id>`, `actor:<id>` and `sink:consumed`.

- `source:<id>` is a shared source holding a stock, with a fixed set of
  authorised claimant actor identities.
- `actor:<id>` is an actor's exclusive holding.
- `sink:consumed` is the single declared consumption sink. It is the explicit
  rule for loss: consumed units leave circulation but stay in the conserved
  total, so consumption can never be confused with leakage.

Authority is checked per debited account, for the whole transaction:

- debiting `actor:X` requires the proposing actor to be `X`;
- debiting `source:S` requires the proposing actor to be in `S`'s authorised set;
- debiting `sink:consumed` is never permitted;
- crediting requires no authority; an actor may be given units unasked.

No module outside `kernel/settlement.py` writes a balance. There is no public
mutator on any state object.

### Operations and balanced effects

A transaction is a list of balanced effects whose signed amounts sum to zero.
An operation is a named constructor for such a list. Three exist in this slice:

| Operation | Parameters | Effects |
|---|---|---|
| `claim` | `sources`: a mapping of one or more source identities to positive integer amounts | debit each named source by its amount; credit the proposing actor the total |
| `transfer` | `to`: an actor identity other than the proposer; `amount` | debit the proposer; credit `to` |
| `consume` | `amount` | debit the proposer; credit `sink:consumed` |

`claim` accepts several sources because a single-debit transaction cannot
demonstrate that a rejected transaction commits none of its parts. A two-source
claim is the smallest transaction that can prove all-or-nothing settlement, and
the roadmap already requires one global order for multi-resource transactions.
No other multi-effect operation is built.

An effect list is rejected before commit if its amounts do not sum to zero, so a
malformed operation cannot create or destroy units even if it passes every other
check.

### Proposal identity and the actor-local sequence

A proposal is `(proposal_id, actor, sequence, operation, params)`.

- `proposal_id` is a non-empty string, unique across the tick. If two or more
  proposals share an identity, all of them are rejected with
  `denied_duplicate_proposal_id`, regardless of which arrived first.
- `actor` must be present in the tick-start roster.
- `sequence` is the actor-local proposal sequence: a non-negative integer by
  which the actor declares the order of its own proposals within the tick. It is
  carried on the proposal rather than assigned from arrival order, because the
  roadmap's fixture depends on "A to B is A's first proposal" and ordering may
  not depend on collection order. The engine validates it: if one actor submits
  two proposals with the same sequence, all proposals sharing that `(actor,
  sequence)` are rejected with `denied_duplicate_actor_sequence`.

### Ordering and rotation

Resolution order is derived only from tick-start state and proposal content.

1. `roster` is the tick-start actor identities sorted by Unicode code point.
2. `k = tick mod len(roster)`; `rotated = roster[k:] + roster[:k]`. An empty
   roster resolves no actor transactions.
3. `actor_rank` is the actor's index in `rotated`.
4. The total order key is `(actor_rank, sequence)`.

The roadmap's key is `(phase, rotated actor rank, actor-local sequence)`. The
phase term is constant in this slice because reserved completions do not exist
until slice 1b; the key is therefore implemented without it, and 1b restores it.

Rotation is deterministic priority, not a fairness guarantee. It only removes a
permanent winner among claimants that are otherwise equivalent.

### The availability boundary

- At tick start, each account's available amount equals its tick-start balance.
- A transaction is validated against remaining availability for every account it
  debits, as one unit of work.
- Acceptance reduces that availability immediately. Rejection leaves it
  unchanged.
- Credits never raise availability within the tick. A unit credited at tick `T`
  becomes spendable at tick `T+1`.
- Accepted effects are staged and applied together at the end of the tick.

### Outcome reasons

Every submitted proposal appears in the tick record with exactly one reason.
Nothing disappears from the record.

`accepted`, `denied_unknown_actor`, `denied_unknown_source`,
`denied_unknown_operation`, `denied_malformed_params`,
`denied_non_integer_amount`, `denied_non_positive_amount`,
`denied_duplicate_proposal_id`, `denied_duplicate_actor_sequence`,
`denied_unauthorised`, `denied_insufficient_source`,
`denied_insufficient_balance`, `denied_unbalanced_effects`,
`denied_self_transfer`.

### Canonical form

Canonical bytes are UTF-8 JSON with sorted keys, `(",", ":")` separators and
escaped non-ASCII. Integers only; floats and booleans are refused at
serialization rather than formatted, so no platform number formatting can reach
an identity. A digest is the SHA-256 hexadecimal of those bytes. State identity
and tick-record identity are digests of the canonical form, so no incidental
object order, insertion order or wall-clock value can enter them.

### Diagnostics

The diagnostics channel receives already-canonical copies after each decision is
fixed. It returns nothing the engine reads and allocates no identity. This slice
allocates no identities at all, so the roadmap's stronger clause about
diagnostics never perturbing identity allocation is only partly exercised here;
that is recorded as a limitation, not a pass.

## Assertions

The eight owner-required checks, plus one check required by doctrine 9.

| # | Assertion | Test |
|---|---|---|
| A1 | Two valid claims on one unit produce exactly one winner, no negative balance and a conserved total. | `tests/test_contention.py` |
| A2 | An invalid or unauthorised transaction commits no part of itself. | `tests/test_atomicity.py` |
| A3 | Insufficient stock rejects an indivisible transaction without partial credit. | `tests/test_indivisibility.py` |
| A4 | Reordering input maps or the proposal collection leaves canonical results unchanged. | `tests/test_order_independence.py` |
| A5 | The declared rotation produces no permanent winner over equivalent contention at successive ticks. | `tests/test_rotation.py` |
| A6 | The A to B transfer/consume fixture honours next-tick availability and prevents double spending. | `tests/test_credit_boundary.py` |
| A7 | Observers cannot mutate live or previously observed state. | `tests/test_observation.py` |
| A8 | Diagnostics on and off, and repeated identical execution, give identical canonical results. | `tests/test_determinism.py` |
| A9 | Module dependency direction holds; lower layers do not import higher ones. | `tests/test_dependency_direction.py` |

Two further files were added during implementation, for rules the declarations
above already state but the original nine assertions did not reach:

| # | Assertion | Test | Why it was added |
|---|---|---|---|
| A10 | Proposals sharing an identity are all rejected, and so are proposals sharing an actor sequence, whichever arrived first. | `tests/test_proposal_identity.py` | The declared identity rules are what let resolution order come from content alone, so A4 rests on them, and nothing was checking them. |
| A11 | The settlement integrity rails refuse to commit when their precondition holds. | `tests/test_integrity_rails.py` | The mutation check found that switching the negative-balance rail off broke no test. |

## Attempt ledger

| Attempt | Revision | What changed | Result |
|---|---|---|---|
| Declaration | `bbbf142f1399c1642c567d3d9c78792610b2df0b` | This record, written before any kernel code existed. | n/a |
| 1 | `b48542b3567bfba9f0fa7a831ab8ace0eb6ddc1f` | First kernel implementation against the declarations above, with the focused tests for A1 to A9, then A10 and A11 after the instrument check. | 107 passed, 0 failed. See Results. |

Failed versions are preserved here rather than overwritten. The corrections made
during attempt 1, including one defect in the instrument itself, are recorded
under Results.

## Results

Machine: Windows 11 Pro 10.0.26200, CPython 3.12.10, pytest 9.1.1.
Working directory: the repository root, `C:\dev\03-Living-World-V3`.

### Commands and results

| Command | Result |
|---|---|
| `py -3 -m pytest` | 107 passed, 0 failed, 0 skipped, 0.22s. Full per-test output: `evidence/stage-01/instrument/pytest_verbose_output.txt` |
| `py -3 -m pytest -q` repeated twice | 107 passed both times |
| `py -3 evidence/stage-01/instrument/mutation_check.py` | exit 0. 14 of 15 deliberate defects detected; 1 confirmed structurally unreachable. Output: `mutation_check_output.txt`, raw pytest output per run under `instrument/runs/` |
| `py -3 evidence/stage-01/instrument/fixture_digests.py` | Canonical results for the declared fixtures. Output: `fixture_digests_output.txt` |

Test counts by file, from the verbose run: `test_atomicity` 16,
`test_contention` 10, `test_credit_boundary` 8, `test_dependency_direction` 6,
`test_determinism` 10, `test_indivisibility` 11, `test_integrity_rails` 9,
`test_observation` 16, `test_order_independence` 5, `test_proposal_identity` 8,
`test_rotation` 8.

### The declared fixtures, as the engine produced them

A1, one unit and two authorised claimants, at tick 0:

```
rotated roster   ('A', 'B')
outcomes         [('pA', 'accepted'), ('pB', 'denied_insufficient_source')]
balances         {'A': 1, 'B': 0}
source S         0
total before 1   total after 1
record digest    b3846dbf23d06285dd190122aedda39d8253f718aa47d4bd33a5687e7a1a5aa9
state digest     9b5e304618d0711c0bbd5da7dbca8e6622b717e433b6cb3871a468ac529d4ee8
```

The same contention at tick 1 reverses the winner, with rotated roster
`('B', 'A')`, outcomes `[('pB', 'accepted'), ('pA', 'denied_insufficient_source')]`
and record digest `7d4bb4ad63480a7916d63cd32cce5aad28594e3b261fed9c29989517d0639ae5`.

A6, the roadmap's credit fixture, starting at tick 0:

```
tick 0 outcomes  [('a_gives', 'accepted'),
                  ('a_spends_again', 'denied_insufficient_balance'),
                  ('b_spends_early', 'denied_insufficient_balance')]
tick 0 balances  {'A': 0, 'B': 1}
tick 1 outcomes  [('b_spends_later', 'accepted')]
tick 1 balances  {'A': 0, 'B': 0}, consumed 1
total before 1   total after 1
tick 0 digest    09a4e2527e217674905ef5c3e91d0a8585f8df409cbb308cce1a7765c0d87339
```

Starting the same fixture at tick 1 puts B ahead of A in the rotation. B's early
consume is still denied, A's transfer is still accepted, and A's second spend is
still denied, which is the roadmap's "regardless of resolver order".

A8, the same A1 fixture run with and without a diagnostics sink, produced
identical record and state digests with one event captured by the sink.

### Instrument validation

The suite passed on its first complete run. That is not evidence that it checks
anything, so `evidence/stage-01/instrument/mutation_check.py` breaks one declared
rule in the kernel at a time and records which tests notice. Results:

| Mutation | Tests that noticed |
|---|---:|
| rotation always starts at the sorted roster | 8 |
| a unit credited this tick becomes spendable this tick | 4 |
| authority over a debited account is never checked | 6 |
| resolution follows proposal arrival order | 7 |
| the record lists outcomes in arrival order | 3 |
| canonical bytes follow mapping insertion order | 1 |
| state hands out a live mutable mapping | 3 |
| a view points at the state's own mapping | 2 |
| only the first leg is checked against availability | 1 |
| proposals sharing an identity are resolved | 3 |
| one actor may reuse a sequence | 2 |
| a transaction may create or destroy units | 1 |
| an amount need not be a whole unit | 3 |
| the negative-balance rail is off | 2 |
| the conservation rail is off | 0, unreachable |

The conservation rail cannot be reached by any input: a committed transaction
must already have balanced effects and touch only accounts inside the world, and
those two together conserve the total by construction. It is defence in depth
against a future slice, and the harness records it as declared-unreachable
rather than as a pass.

### Corrections made during attempt 1, preserved

1. **The instrument was wrong before the kernel was.** The first mutation harness
   reported the `authority-not-checked` failures again for `order-by-arrival`.
   Both mutations change `kernel/settlement.py` by exactly 38 bytes, and both
   runs fell inside one filesystem mtime second, so CPython accepted the previous
   mutation's cached bytecode as current and the second run tested the first
   mutation's code. The harness now disables bytecode writing, removes every
   `__pycache__` before each run, and checks the mutated text is the text on
   disk. Caught by running one mutation by hand and reading pytest's own output
   instead of the harness summary.

2. **The instrument altered the repository.** The same harness wrote files in
   text mode, which converts LF to CRLF on Windows, so its "restore" was not byte
   for byte and four kernel files were left with changed line endings. The
   harness now reads and writes bytes and verifies the restore. The affected
   files were normalised back to LF before the implementation commit.

3. **Two real blind spots in the suite**, both found by the corrected harness and
   both fixed by adding tests rather than by dropping the mutation:
   `view-shares-the-live-mapping` was noticed by nothing, because handing an
   observer the world's own mapping is unobservable while state is immutable;
   `negative-balance-rail-off` was noticed by nothing, because the ordinary
   validation path never reaches that rail. The first is now checked as a
   containment property, the second by calling the commit step directly with the
   staged effects that trip it.

4. **A missing declared rule.** The original nine assertions never checked the
   duplicate-identity and duplicate-sequence rules, although the declarations
   state them and the roadmap requires the first. Added as A10.

No assertion was weakened and no expected result was replaced at any point.

### Guarantees demonstrated

- One contested unit produces exactly one winner and exactly one credit; the
  loser carries an explicit reason; balances stay at or above zero; the declared
  total is conserved.
- A transaction with an unauthorised, unknown or unaffordable leg commits none of
  its legs, including the legs that would have succeeded alone.
- An indivisible transaction against insufficient stock is denied outright. Zero,
  negative, fractional and boolean amounts are denied rather than rounded,
  reversed or treated as no-ops.
- Every permutation of the genesis balance map, source map, authorised set,
  claim source map and proposal collection gives one canonical result: 576
  orderings, one digest.
- The rotation gives no permanent winner over equivalent contention at
  successive ticks, for two and for three claimants, and a high-sorting identity
  wins as often as a low-sorting one.
- The roadmap's credit fixture holds at both resolver orders, and a unit credited
  this tick, whether transferred or claimed, is only spendable at the next tick.
- Views, states, sources, records, outcomes and effects all refuse mutation; a
  view or record taken earlier is unchanged after later ticks; the maps handed to
  the constructor and to a proposal can be edited afterwards with no effect.
- Diagnostics on and off give identical canonical results, a hostile sink that
  corrupts its payload and raises changes nothing and is counted, and settlement
  cannot import the diagnostics channel at all.

### Limitations

- **Stage 1 is not complete and its exit gate is not claimed.** Slices 1b, 1c and
  1d are not built: no reservations, no two-tick actions, no cancellation, no
  sealed evidence stream, no replay, no recovery, no instance isolation, no
  capacity benchmark.
- **No independent review has been requested, supplied or held.**
- The roadmap's clause that optional capture must not perturb identity allocation
  is only partly exercised, because this slice allocates no identity of its own:
  proposal identities are supplied by the caller. Slice 1c must satisfy it
  properly.
- The tick record is in memory only. It is not the sealed evidence schema, and it
  does not yet carry immutable copies of the inputs and alternatives a decision
  used. It records identity, reason and committed effects. Slice 1c specifies the
  schema and writes it.
- Contention over successive ticks is shown by sweeping the genesis tick, because
  nothing in this slice produces resources, so a depleted source cannot be
  refilled to contend over again inside one run. The engine's own tick-over-tick
  rotation is checked separately across four consecutive ticks.
- Rotation is deterministic priority. It is not a fairness result, and it says
  nothing about claimants whose opportunity or eligibility differ.
- `WorldView` gives every actor the whole boundary. Bounded perception is Stage 2.
- The conservation rail is unreachable by any current input, as recorded above.
- Amounts are unbounded Python integers. No overflow behaviour is defined,
  because none exists at this size.
- Nothing here is a world, a person or a behaviour. No claim is made about six
  people, fifty actors, performance, or any social or emergent property.

## Review

No independent review has been requested, supplied or held. Stage 1 has three
further slices and its exit gate is not claimed. Under `AGENTS.md`, progression
past Stage 1 additionally requires a separate reviewer using a different model,
which has not happened.

## Rollback

The work sits in four commits on `codex/kernel-first-slice` in a repository with
no remote. Nothing outside `C:\dev\03-Living-World-V3` was changed.

To undo the slice but keep the adopted documents, revert or reset to
`bbbf142f1399c1642c567d3d9c78792610b2df0b`. To undo everything including the
adoption, reset to before `2bf08e9e4629022adb508b5c6db53a144bb355b4`, or delete
the repository directory.

Exact files introduced by the slice, all of which may be deleted to remove it:

- `kernel/__init__.py`, `canonical.py`, `diagnostics.py`, `engine.py`,
  `ordering.py`, `outcomes.py`, `proposals.py`, `reasons.py`, `settlement.py`,
  `state.py`, `units.py`, `version.py`
- `tests/__init__.py`, `support.py`, `test_atomicity.py`, `test_contention.py`,
  `test_credit_boundary.py`, `test_dependency_direction.py`,
  `test_determinism.py`, `test_indivisibility.py`, `test_integrity_rails.py`,
  `test_observation.py`, `test_order_independence.py`,
  `test_proposal_identity.py`, `test_rotation.py`
- `evidence/stage-01/RECORD.md` and `evidence/stage-01/instrument/`
- `pyproject.toml`, `.gitignore`, `.gitattributes`

Configuration to revert: `pyproject.toml` holds the only configuration, the
pytest `pythonpath` and `testpaths` settings. There is no other configuration
file, no environment variable and no installed package.

## Repair 1 — declared before implementation, 2026-09-20

Base: `fa8be6083b31ead3c7e6aae844c0fd749927e6d0`. Authority: OD-002.
Scope: R1–R5 only. No reservations, worlds, new domains or stage progression.
Whole-world/capacity runs: zero. Original results and instrument outputs stay intact.

- R1: reject reentry for the complete engine tick, including collection and
  publication; release the guard on every exit. Verify both review triggers,
  ordinary iterators, independent engines and recovery after exceptions.
- R2: deterministically order rejected outcomes from distinct unknown actors while
  retaining every denial and preserving valid-actor allocation priority.
- R3: a mutant counts as detected only on an executed failing test, never runner
  failure or an empty failure list. Retain UNKNOWN output and test negative controls.
- R4: retain unbounded Python integers and the existing JSON byte representation.
  Encode integer digits locally without changing the interpreter's global limit;
  test large positive/negative values, ordinary JSON equivalence and global inertness.
- R5: input proposals carry an actor-local **order**, expressing intention such as
  giving before consuming. Settlement assigns dense engine-owned **sequence** values
  from sorted distinct orders within each actor at the boundary. Collection order
  is irrelevant. Duplicate input orders are all denied; they retain the existing
  `denied_duplicate_actor_sequence` reason for compatibility. Rejected proposals
  also receive deterministic sequence values. The caller cannot supply the output
  sequence. This implements the roadmap rather than amending its requirement.

Proposal helper positional calls retain their shape; the input keyword/attribute
`sequence` becomes `order`. There are no person/domain callers in Stage 1a. Outcomes
keep their existing `sequence` field. Proposal IDs remain caller-supplied in this
slice; sequence ownership is not a claim of authenticated actor provenance.

Code version advances to `0.1.1-stage1a`; output schema remains `v3.kernel.1a.1`.
Ordinary state identities must remain identical. Original fixture record payloads
must differ only in code version. Sparse input orders intentionally produce dense
output sequences; formerly ambiguous rejected records receive stable ordering.
Old expected results are retained, not replaced.

Validation: original suite; unchanged review assertions adapted only to locate the
repair checkout; new boundary controls; full mutation run with equivalent updated
anchors; native fixture comparison against the base; final changed-file inspection.
Repair implementation is not independent acceptance of its own results.

### Repair 1 result — 2026-09-20

**R1–R5 are resolved in the tested repair.** This is implementation and measured
revalidation, not independent acceptance. Stage 1 remains incomplete. No slice 1b,
world, capacity run, pin, merge or publication is opened.

The source base is `fa8be6083b31ead3c7e6aae844c0fd749927e6d0`.
The repair is delivered as working-tree changes on `codex/kernel-first-slice`.
File identities are in [repair-1/FILE_MANIFEST.json](repair-1/FILE_MANIFEST.json).
The preregistration above was written before the code changes in an isolated
repair copy. Original committed evidence and the original 107 test assertions
are retained. The original adversarial report, failing output and test source
are archived verbatim under [repair-1/review-before-repair/](repair-1/review-before-repair/).

| Finding and existing owner | Correction | Measured proof |
|---|---|---|
| R1: `Engine.tick` allowed nested transitions during collection and diagnostics publication, duplicating accepted claim history or advancing canonical state from a sink. | A nonblocking per-engine lock covers collection, settlement, commit and publication. Every exit releases it. Reentry raises; a diagnostics exception is counted through the existing sink-failure path. | Both original reproductions pass; generator failure leaves the original state intact; later ticks and separate engines work. Reintroducing reentry fails four tests. |
| R2: `settle` omitted actor identity from rejected-outcome ordering, so distinct unknown actors could tie. | Add actor identity after rotated rank in the outcome key. Preserve every denial and valid allocation priority. | Original unknown-actor duplicate-ID permutation regression passes. Removing this component fails that regression. |
| R3: `mutation_check.main` treated any nonzero runner exit as detection. | `classify_result` requires exit 1 with named failed tests and no collection/setup/teardown error. Other unsuccessful executions are UNKNOWN. | Runner/error negative controls pass; real failing-test and surviving-mutant controls pass. Reinstating the permissive rule fails nine tests. |
| R4: `canonical_bytes` delegated integer digits to the process-limited JSON conversion despite accepting unbounded quantities. | Local decimal chunk encoding preserves canonical JSON without changing the global interpreter limit. | Empty tick and claim/consume operations on a 5,001-digit quantity serialize; signed digit-boundary cases pass; ordinary JSON bytes match; the global limit is unchanged. Reinstating the old conversion fails five tests. |
| R5: `Proposal` accepted the output sequence from callers despite the roadmap assigning it to the engine. | Proposal carries intended `order`; `settle` assigns dense actor-local output `sequence` values. Duplicate input orders still deny all affected proposals. | Sparse and very large input orders, both collection orders, actor-local/reset boundaries and rejected input `sequence=` keyword pass. Copying caller order to output fails three tests. |

The ordering rotation, available-at-tick-start rule, transaction authority,
indivisibility, negative-balance rail and conservation assertion remain in place.
The guard is boundary exclusion, not a scheduler or support for nondeterministic
parallel simulation. Python reflection/private-field tampering is not a claimed
security boundary.

### Repair validation and evidence

Runtime measured here: Python 3.12.14, pytest 9.1.1. The interpreter was reused
read-only from the existing validation environment; bytecode writing and pytest's
cache provider were disabled. Test temporary directories were outside both actual
repositories. The repair was exercised in the isolated copy before application.

| Check | This repair's measured result | Raw evidence |
|---|---|---|
| Full reference plus review/boundary suite | 148 passed; original assertions retained | `repair-1/direct-suite-output.txt`; mutation `00-baseline.txt` and `99-restored.txt` |
| Original adversarial assertions | All 11 pass within the full suite; five previously failed | `tests/test_review_regressions.py`; original failing output archived |
| Ordinary contention matrix | 2,592 cases, each in both proposal orders; stock, conservation and record-order checks pass | Included in the adversarial regression test |
| Full mutation instrument | 19/20 detected; one declared unreachable conservation-rail mutation excluded; no invalid run counted as detection | `repair-1/mutation-output.txt`, `repair-1/mutation-runs/` |
| Mutation restoration | All targeted source files restored byte for byte; full suite again 148 passed | `repair-1/mutation-restoration.json` |
| Native original fixture comparison | Eight captured ticks: state payloads/digests unchanged; record payloads differ only in `engine_version` | `repair-1/fixtures-*.json`, `repair-1/fixture-comparison.json` |
| Hash-seed control | Repaired fixtures identical with hash seeds 0 and 17 | `repair-1/fixtures-repaired-seed17.json` |
| File/diff checks | No whitespace errors; original committed instrument outputs unchanged; kernel source has no CRLF bytes | File manifest and the final application verification |

Two environment failures were preserved/classified without behavioural inference:
the first direct suite attempt had 137 passes and 12 fixture/teardown errors
because pytest's default temporary directory was inaccessible (terminal summary
only retained). An explicit writable temp directory gave 148 passes. The first
mutation-wrapper attempt then had 137 passes and 11 fixture errors because
`PYTEST_ADDOPTS` consumed Windows backslashes. No mutation ran. Its raw output
is in `repair-1/invalid-mutation-wrapper-attempt/`. One wrapper correction to a
quoted forward-slash path produced the valid mutation run above. Neither invalid
attempt supports a pass, failure of kernel behaviour, or mutation detection.

The surviving conservation mutation remains an assertion in the kernel. Its
redundancy follows from balanced effects and account containment; survival alone
does not prove this. The negative-balance mutant still fails because constructors
reject the negative state with a different exception when that rail is removed.
That kill distinguishes the rail/error path; it does not demonstrate that removing
the rail alone permits negative state to commit.

### Identity, compatibility and limits

`ENGINE_VERSION` is now `0.1.1-stage1a`; schema stays `v3.kernel.1a.1`.
Record digests therefore change. Old digests are preserved as historical output,
not replaced as a new accepted baseline. Independent post-repair review is pending.

Input helpers retain positional call shape; callers using the `sequence=`
keyword or attribute must use `order`. Output records retain `sequence`.
Sparse orders now map to dense sequences; formerly ambiguous invalid submissions
produce deterministic records. Caller proposal IDs and actor claims are still
caller supplied: this repair does not establish authenticated provenance or full
closure of old F06.

R1's duplicated accepted credits and R2–R5's tested defects are corrected in this
new kernel. This is not a correction or oracle claim for old V1/V2/V3, Gifts,
scarcity, or request-food-outstanding. The old project and frozen identities were
not modified. No living-world/Gifts/scarcity counts were generated. Reservations,
cancellation/completion boundaries, sealed replay, native decision-input capture
and the 50-actor benchmark remain outside slice 1a and are not claimed complete.
A separate different-model review has not accepted the repaired source.

### Reproduction

Use a disposable copy containing these repaired files and a separate clean copy
of the base revision. The mutation script deliberately edits/restores files and
writes scratch outputs, so run it in the disposable copy, preserving this evidence.
No dependencies beyond Python and pytest are required.

The actual interpreter used was:
`C:/dev/02-Simulation-Sandbox/.worktrees/request-food-outstanding/sandbox/f01_validation_venv/Scripts/python.exe`.

From the disposable repaired copy, with Python available as `python` and a new
explicit temporary directory (the names below are placeholders):

```text
python -B -m pytest -q -p no:cacheprovider --tb=short --basetemp="<fresh-suite-temp>"
python -B evidence/stage-01/repair-1/run_mutations.py "<repair-copy>" "<fresh-mutation-temp>"
```

The second command sets `PYTHONDONTWRITEBYTECODE=1`, `PYTHONHASHSEED=0` and
a correctly quoted `PYTEST_ADDOPTS` temp path; it invokes the actual instrument,
retains every raw output and verifies restoration hashes.

Run `capture_fixtures.py "<base-copy>" "<output>/fixtures-base.json"` and
`capture_fixtures.py "<repair-copy>" "<output>/fixtures-repaired.json"` under
hash seed 0; repeat the repaired capture with seed 17 and the filename
`fixtures-repaired-seed17.json`. Then run `compare_fixtures.py "<output>"`.
Capture calls the existing native fixture functions and records public engine
state and tick records. The comparison strips only the declared engine-version
field; it does not reconstruct decisions or alter engine outputs.

### Repair rollback list

Rollback requires a separate owner instruction. Nothing was reverted here.
Restore only these existing files from base `fa8be60`, after checking for later
work:

- `kernel/engine.py`
- `kernel/settlement.py`
- `kernel/proposals.py`
- `kernel/canonical.py`
- `kernel/version.py`
- `evidence/stage-01/instrument/mutation_check.py`
- `tests/test_proposal_identity.py`

The added active tests are `tests/test_review_regressions.py` and
`tests/test_repair_boundaries.py`; archive them if withdrawing the repair.
Preserve `AGENTS.md` OD-002, this record's repair declaration/results, and the
entire `evidence/stage-01/repair-1/` evidence tree, adding a dated rollback status.
Do not reset or delete the repository, erase prior evidence, or touch the old
project. No configuration, dependencies, canonical identity files or world
definitions require rollback.

### Publication direction and committed repair — 2026-09-20

Owner direction OD-003 authorises committing and pushing all current new-V3 work
to [Simulation-3](https://github.com/lochheadr92-creator/Simulation-3) on the
existing `codex/kernel-first-slice` branch. No merge or stage progression follows.

The repair and evidence are committed at
`fb5a8959fb6a7a23d6e3107fe32be8248cc19901`.
Earlier statements that the repair was uncommitted describe delivery before
OD-003. The archived application verification likewise records that earlier state.

`repair-1/FILE_MANIFEST.json` identifies the files at this repair commit, before
this publication-only amendment to AGENTS.md and RECORD.md. Every manifest entry
was checked against its staged Git blob before the repair commit. The narrow
`.gitattributes` entry `evidence/stage-01/repair-1/** -text` preserves archived
evidence bytes, including terminal-output line endings, across checkout. Original
evidence, original expected results and the old project remain unchanged.

This follow-up changes only the owner-direction register and this publication
note. Engine/test content remains the validated repair. Independent post-repair
acceptance and Stage 1 completion remain pending. Publication does not change
that status.

### Bounded Phase 4 orchestrator repair — 2026-09-20

Owner direction OD-006 authorises repairing tooling findings F1-F9 in an isolated
checkout based on 6591629029ac5cfedbb16279e2c62888894fb44b. The original Phase 4
checkout and the verified read-only baseline remain preserved.

The final focused inspection/controller/runner regression run passed 168 tests.
Actual commands in those tests were harmless fixtures in disposable repositories;
no real registered project gate or pilot was run. Source identities, raw failures,
final results, contract decisions and limitations are recorded in
[the Phase 4 repair review](orchestrator-phase4-repair/REVIEW.md).

This is uncommitted tooling repair and self-verification, not independent
scientific acceptance. Stage 1a acceptance remains pending, Stage 1 remains
incomplete, and Slice 1b remains unauthorised. No kernel or scientific criterion
changed, and no merge or push occurred.

### Read-only orchestrator freeze — 2026-09-20

OD-005 authorises verification, demonstrated-defect repair, safety review, and
commit of orchestrator Phases 1-3. The result and reproduction commands are in
[`orchestrator-review/REVIEW.md`](orchestrator-review/REVIEW.md). This work is
isolated from newer uncommitted execution work in the original checkout.

No kernel, simulation rule, registry command, evidence contract, or scientific
acceptance state is changed. Whole-world executions used remain zero. This is
a tooling verification record, not independent post-repair acceptance of Stage
1a. Slice 1b remains unauthorised and the Stage 1 exit remains unclaimed.

### Phase 4 repair 2 and controlled pilot — 2026-09-20

The owner's instruction of 2026-09-20 authorised bounded repairs for the two
findings of the Phase 4 pilot (registered `py -3` runtime, startup provenance),
focused tests, and exactly one real registered gate through the orchestrator in
a disposable copy. Both repairs were made in an isolated copy of the Phase 4
repair candidate; 191 focused and 365 whole-tree tests passed; the single
`stage-01a-fixture-digests` request returned SUCCESS with evidence COMPLETE and
its output matches `repair-1/fixtures-repaired.txt`. Identities, tests, the
pilot receipt and limitations are recorded in
[orchestrator-phase4-repair2/REVIEW.md](orchestrator-phase4-repair2/REVIEW.md).

This is uncommitted tooling repair, self-verification and a mechanical pilot,
not independent scientific acceptance. Stage 1a acceptance remains pending,
Stage 1 remains incomplete, and Slice 1b remains unauthorised. No kernel,
registry command, scientific criterion, merge or push changed.

### Orchestrator publication - 2026-09-21

OD-007 authorises commit and publication of the verified automation snapshot.
See [the publication record](orchestrator-publication/RECORD.md) for source
identities, test evidence, runtime limitations and the correction that the
pilot fixture output matches the reference after newline normalization, not
byte-for-byte. Earlier uncommitted/no-publication statements describe their
original sittings and remain historical. Stage 1a scientific acceptance stays
pending; Slice 1b remains unauthorised. No additional real project gate ran.
### Independent post-repair review of slice 1a — 2026-09-21

Reviewer: Claude (`claude-fable-5-1`), a different model from the builder.
Source `fb5a8959fb6a7a23d6e3107fe32be8248cc19901` in a fresh clone; suite 148
passed, fixture digests and the 19/20 mutation result reproduced, 21 reviewer
probes passed. Verdict PASS on every essential slice 1a condition; R1–R5
closed. Stage 1 remains incomplete (1c–1d unbuilt); the exit gate is not
claimed. Evidence: [review-2026-09-21-slice-1a/REVIEW.md](review-2026-09-21-slice-1a/REVIEW.md).
Note: the "Proposal identity and the actor-local sequence" declaration above
describes Attempt 1 and is superseded by Repair 1 (R5): callers supply
`order`, the engine assigns `sequence`.

### Independent review of slice 1b — 2026-09-21

Reviewer: Claude (`claude-fable-5-1`). Snapshot of the uncommitted tree on
`b915aa0`; 212 kernel tests and both fixture claims reproduced; nine reviewer
probes including a 300-tick lifecycle fuzz passed. Kernel verdict PASS on
every 1b claim. Two integration findings before commit: F1, the repair-1
evidence contract compared its manifest against the live tree (three
`manifest_hash_mismatch` errors); F2, the stale untracked pre-freeze
orchestrator killed any bare `pytest` run. F3, the 1a mutation instrument's
anchors no longer match the phased settlement. Evidence:
[review-2026-09-21-slice-1b/REVIEW.md](review-2026-09-21-slice-1b/REVIEW.md).
Stage 1 exit not claimed.

### Slice 1b landed — 2026-09-21

F1 resolved in commit `1858e96` (historical manifests are checked at their
recorded revision; working-tree drift is reported as superseded). F2 resolved
in the same commit: the two stale files were removed from this checkout and
archived with SHA-256 (`947954d0…` orchestrator, `9a78d5a3…` test) in the
review workspace. Whole tree with plain `pytest`: 254 passed. F3 (mutation
instrument update for 1b) remains open and is not a blocker. This commit
contains the slice 1b kernel, tests, evidence and both review records. No
push, merge, acceptance or later slice.

### OD-009 recorded — 2026-09-21

Slice 1b is landed (`9d1542d`). Under OD-009, slice 1c is re-scoped to a
record stream plus a viewer that renders from the stream (checkpoint 1);
slice 1d is deferred with a per-tick timing line kept visible; Stage 2 opens in
checkpoint order once checkpoint 1 exists. Checkpoint output is exploration,
not evidence. Stage 1 exit remains unclaimed.

### Slice 1c (re-scoped) — checkpoint 1 — 2026-09-21

Record stream and viewer landed under OD-009. `stream/run_file.py` writes an
append-only JSONL run (`v3.stream.1`): a header, one canonical content line per
tick (record, next-state digest, chained), a separate timing line per tick,
and an end line carrying the trail digest; `read_run` recomputes every digest
and chain link and lists problems. `stream/scenario.py` is a seeded
contention-and-holds proposal generator over the 1b kernel; `stream/run.py`
runs it (`--twice` re-runs and byte-compares); `stream/viewer.py` renders a
self-contained HTML page (inline CSS/JS, no external resources) and a text
render from the run file alone. `tests/test_stream.py` adds ten tests
(determinism, verification, overwrite refusal, tamper detection, viewer
self-containment, kernel→stream import direction). Whole tree: 264 passed.

Checkpoint run: `py -3 -B -m stream.run --seed 7 --ticks 200 --twice --html`
→ 200 ticks, trail
`094e03795b77c6574c82baca33d3a0fe8d8f9daae5e24585e894f047bc90689b`, final
state `00076b2d…`, second run byte-identical; tick_ms mean 0.233 / p95 0.333 /
max 0.424. Run files live under `runs/` (gitignored); checkpoint output is
exploration, not evidence.

Observations from the viewer: reservations never expire (a 1b declaration),
so holds accumulate over a long run and availability drains even where stock
remains; the economy has no production, so it is a pure depletion picture.
Both are inputs to Stage 2 scoping, not defects.

Tooling notes: `automation/preflight.py` recognises the milestone line by
fixed phrases, so the updated `SIM3_STATE.md` snapshot reports
`sim3_state_milestone_mismatch` (and `sim3_state_head_mismatch`, because the
head line carries an annotation rather than a bare hash) as informational
inconsistencies alongside the two pre-existing ones; per OD-009 this is
recorded rather than fixed. The copied review evidence files under
`review-2026-09-21-slice-1a/` and `-1b/` were CRLF-normalised to LF on
commit, so their `artifact-sha256.json` hashes describe the workspace copies,
not the committed blobs. Stage 1 exit remains unclaimed; the first Stage 2 step
(position, movement, food source, hunger) is next.

### Stage 2, first step — checkpoint 2, a map over time — 2026-09-21

Position, movement, one renewable food source and hunger, under OD-009 point
4. New package `world/` composes the 1b kernel without changing it: the kernel
remains the only place food units move (claims, eating, contention); `world/`
holds what the kernel does not know (homes, positions, hunger, deaths) as an
immutable overlay beside the kernel state. One tick: observe (bounded
tick-start view: own position, hunger, free food, the source's place and free
stock) → decide (one live selection rule with the eligible candidates recorded
beside the choice) → kernel settles eat/claim proposals → world processes in a
fixed order: movement, hunger, death, renewal. Renewal is the only production
rule; it constructs the next kernel state through the kernel's validated
constructor and is written to the tick line, and the run reader recomputes it
from the stored state rather than trusting the digest. Stream format is now
`v3.stream.2` (optional `world`, `decisions`, `production` blocks; v3.stream.1
files still read). Genesis uses one named seeded generator
(`homes-uniform-v1`); nothing else in a run is random.

Declared levers (all in the run header; CLI flags on `world.run`): grid
12×12, six people, source at centre, starting food 1, source stock 4, cap 8,
renewal +2 every 3 ticks, claim up to 2, hunger +1 per tick, satiation 6 per
unit, hungry at 5, emergency at 10, death at 16. Movement one cell per tick
along the longer axis (x on ties), co-location allowed. Decision priority:
eat if hungry and holding; claim if hungry at the source; wait if hungry at an
empty source; walk to the source if hungry; else walk home and rest.

Checkpoint run: `py -3 -B -m world.run --seed 7 --ticks 300 --twice --html`
→ trail `d9f78325601a9a1f7745843f0517d7a6452a6f8d0eb261c9f3f1253596115f02`,
second run byte-identical; survivors 3, deaths 3 (p04 t22, p06 t46, p03
t58); 79 claims accepted, 6 denied (`denied_insufficient_source`), 160 units
eaten, 144 emergency person-ticks; tick_ms mean 0.099 / p95 0.143 / max
0.212. Viewer: `world/viewer.py` (map, people table with decision and kernel
outcome, hunger and stock over time). `tests/test_world.py` adds 22 tests;
whole tree 286 passed.

Observations, inputs to the next leg, not results:
- The world found a carrying capacity: three die in the first 60 ticks, then
  the remaining three hold a stable cycle (stock 2–6, hunger sawtooth to ~10).
  With these levers the source cannot feed six.
- Two of the three deaths happened at the source holding food: claim and eat
  are separate ticks, so a claim at hunger 15 cannot beat death at 16. That
  is the declared rule, and it is what "needs never pause" costs.
- The kernel's own contention rail is what decides who eats when several
  arrive together; the world layer never overrides a kernel outcome.
- Nobody sees anyone else yet; perception is the next checkpoint (OD-009).

Tooling note: `tests/test_preflight.py` now sets `PYTHONIOENCODING=utf-8`
for the preflight child process; the previous commit's em dash in a subject
line made the pipe's ANSI code page decode fail on Windows. No orchestrator,
no frozen hashes, no acceptance claimed. Stage 1 exit remains unclaimed.

### Stage 2, second step — checkpoint 3, perception radius and bounded views — 2026-09-21

Perception radius and bounded views, under OD-009 point 4. Each living person
now observes the tick-start world inside a Chebyshev radius: other living
people as identity, position and free food (not hunger, home or decision);
the source position remains a known landmark; source stock is present only
when the source cell is in view, otherwise absent, never stale and never
zero-as-unknown. Self is always in view. Observations are recorded per
person on the tick line in an optional `observations` block, verified the
same way as `decisions` (canonical bytes, in the trail). STREAM_FORMAT stays
`v3.stream.2`: adding that optional block does not change the reader's rules.
`world/process.py` is unchanged. CLAIM still requires standing on the source
(hence in view) and uses the observed stock, asserted rather than defaulted;
no new candidate kinds.

Declared values (in the run header via `WorldConfig.describe()`): distance
metric Chebyshev; default perception radius 3 (`--perception-radius`);
boundary inclusive (`distance <= radius`); others leak identity, position,
free food only; source stock only when the source cell is in view.

Checkpoint runs, seed 7, 300 ticks (`py -3 -B -m world.run`):
- radius 3 (default, `--twice --html`): trail
  `ac95126572ed0ce787042df116c4ec8715ad62d3939ff53af8995043bf89c43d`,
  second run byte-identical; survivors 3, deaths 3 (p04 t22, p06 t46, p03
  t58); tick_ms mean 0.127 / p95 0.201 / max 0.301; person-ticks with
  another in view 861, with source in view 836.
- radius 12 (whole grid): trail
  `1608c71acba9227310ba973f214a6c670e29ada8de986be9679460f14a3dc045`;
  survivors 3, deaths 3; tick_ms mean 0.135 / p95 0.221 / max 0.334;
  1026 / 1026 (every living person-tick).
- radius 1: trail
  `76886afdb38868f05d417ca823342d15cdd111bd4d637e2d34a52d78c8e96e38`;
  survivors 3, deaths 3; tick_ms mean 0.115 / p95 0.179 / max 0.263;
  433 / 481.

Radius-12 decisions matched HEAD `b305783` byte-for-byte on the 300-tick
seed-7 run (and on the 80-tick fixture in `tests/fixtures/`). Radius 1 and 3
produced the same decisions and the same deaths: the selection rule still
does not act on other people, and CLAIM only happens on the source cell,
which is always in view. `tests/test_perception.py` adds nine tests; whole
tree 296 passed. Viewer: Chebyshev squares on the map, a sees column, and
the two whole-run counts.

Observations, inputs to whatever comes next, not results:
- Bounded views are now native records, but they do not change who walks,
  who claims, or who dies. The world still looks like checkpoint 2 until
  someone can act on a person they can see.
- At radius 3 a person approaching from a home on the rim often cannot
  yet see source stock; they still walk to the landmark. At the source
  they see the crowd and still only eat, claim or wait.
- The claim-then-eat latency (two deaths at the source holding food)
  is unchanged; it remains the owner decision pending from checkpoint 2.

Tooling note: `automation/preflight.py` will report
`sim3_state_milestone_mismatch` and `sim3_state_head_mismatch` against the
updated snapshot; recorded, not fixed (OD-009). No orchestrator, no frozen
hashes, no acceptance claimed. Stage 1 exit remains unclaimed.

### OD-009 Revision 3 recorded — 2026-09-21

The owner opened the exploration lane and replaced remaining OD-009
sequencing. Legs 2–6 are not opened by this entry; each needs its own
direction and a pre-code declaration. Stage 3 re-entry is parked; Stage 4 is
blocked; slices 1c and 1d and the Stage 1 exit gate wait in the ratification
lane. Work already delivered under the original OD-009 stands (1b; stream
checkpoint 1; world checkpoint 2; perception checkpoint 3) as exploration,
not as a Stage exit. Mapped against the new order: leg 1 done; legs 2–4 have
corresponding delivered work (agents/presence, position/locality as visual
checkpoint A, decision-time observations); next undelivered item is leg 5
(inter-agent and population state, visual checkpoint B), which is not
authorised to start. No implementation in this sitting. Stage 1 exit remains
unclaimed.

### OD-010 recorded - 2026-09-21

The owner opened exploration leg 5 (inter-agent and population state, visual
checkpoint B) with the pre-code declaration OD-009 Revision 3 requires: a
seeded per-person trait `yield_at`; a crowd-yield rule that acts on the
checkpoint 3 observation of who is standing on the source; an OFF control
that must reproduce `9d354414` decisions byte-for-byte; tests; and a stop
condition. No social action, no retained facts, no kernel change. The
claim-then-eat latency rule is held constant for this leg. Nothing is
implemented by this entry. Stage 1 exit remains unclaimed.

### Exploration leg 5 — crowd-yield trait, visual checkpoint B — 2026-09-21

Crowd-yield under OD-010. Overlay gains immutable per-person `yield_at`,
drawn after the home sample from the same `random.Random(seed)` so seed-7
homes stay `p01 (11,6), p02 (2,3), p03 (6,8), p04 (0,1), p05 (6,1), p06
(6,11)`. Generator name `homes-uniform-v1+yield-v1`. Default set `{1,2,3}`;
`--yield off` assigns `actors+1`. Crowd is derived in `decide.py` from seen
others on the source cell; it is not stored. YIELD sits above GO and below
EAT/CLAIM/WAIT. A yield stays put and proposes nothing. `process.py` only
copies the trait onto the next overlay; no process rule changed. Kernel
untouched. STREAM_FORMAT unchanged. `dead people are neither seen nor
counted` is in `describe()`.

Declared: Chebyshev radius 3, yield set (1, 2, 3), yield on by default,
reason `hungry, saw {crowd} on source, stock {stock}, yield_at {n}`.

Checkpoint, 300 ticks, `--html` on the ON arms (`py -3 -B -m world.run`):

| seed | mode | survivors | deaths | denied claims | emergency person-ticks | yield events | trail |
|---|---|---:|---:|---:|---:|---:|---|
| 7 | on (twice identical) | 3 | 3 (p04 t22, p02 t46, p06 t58) | 5 | 106 (by yield_at 1:23, 2:40, 3:43) | 5 | `9405ee6f63146e034dcc4bb63f68b1072ffafba14f7b96ae4c0efe46ffbb070a` |
| 7 | off | 3 | 3 (p04 t22, p06 t46, p03 t58) | 6 | 144 | 0 | `ca4ac02841061007357893df5de580983698645811b12675472be53d0ec3eff4` |
| 3 | on | 3 | 3 (p05 t22, p03 t34, p04 t34) | 8 | 163 (1:15, 2:48, 3:100) | 3 | `44d4e974d7743da5…` |
| 3 | off | 3 | 3 (p05 t22, p03 t34, p06 t34) | 9 | 163 | 0 | `72c49fd877795101…` |
| 11 | on | 4 | 2 (p02 t22, p06 t22) | 2 | 271 (1:90, 2:136, 3:45) | 13 | `f1dc48ea06e6117c…` |
| 11 | off | 4 | 2 (p02 t22, p06 t22) | 2 | 245 | 0 | `a20797f1c66f43be…` |

Seed 7 ON tick_ms mean 0.135 / p95 0.212 / max 0.369. OFF 80-tick
decisions matched HEAD `b305783` / `9d354414` byte-for-byte.
`tests/test_yield.py` adds ten tests; whole tree 308 passed. Viewer:
yield_at on the marker and table, hollow ring for yield, crowd line and
yield dots, deaths and emergency broken down by trait.

Observations, a picture of a difference, not a claim:
- Seed 7 ON has five yields. First at tick 38: p02 and p06 (`yield_at` 1)
  hold at the rim because they saw 2 on the source with stock 0; p05
  (`yield_at` 3) keeps walking. Same survivor count as OFF, different
  deaths (p02/p06 die instead of p03).
- Seed 11 yields 13 times and still the same two deaths at t22. Yielding
  does not by itself rewrite the claim-then-eat latency (held constant).
- The trait is a model assumption (DOCTRINE 8). People notice a crowd on
  the source, not a particular person.

Stop condition met: checkpoint B renders from the run file; seed-7 ON has
yield events; ON/OFF is recorded here. Leg 6 is not opened. No
orchestrator, no frozen hashes, no acceptance claimed. Stage 1 exit remains
unclaimed.

### OD-013 recorded — ratification lane opened — 2026-09-23

Owner direction OD-013 (AGENTS.md) resolves the claim-then-eat latency
decision named under OD-011: separate obtain and eat actions are retained,
no same-tick obtain/eat revision is authorised, and the ratification lane
is opened. The decision changes no kernel or world code; leg 6 comparisons
remain the comparison authority under the existing latency.

Ratification cards opened by this entry:

- **Slice 1c — sealed evidence stream and replay (active).** Deliver a
  sealed stream whose canonical bytes can be replayed and verified against
  the kernel's canonical form, closing the ratification-lane 1c scope
  recorded in SIM3_STATE.md. Declarations precede implementation.
- **Slice 1d — 50-actor cost envelope.** Measure and record the bounded
  cost envelope at 50 actors, ratification scope, after 1c.

The Stage 1 exit review is requested from an independent reviewer only
once the 1c and 1d records are complete. Checkpoint C is not accepted by
this entry, exploration leg 7 is not opened, and the Stage 1 exit gate is
not claimed.

### OD-014 recorded — checkpoint C accepted; obtain and eat stay separate — 2026-09-23

Owner direction OD-014 (AGENTS.md) accepts checkpoint C as sufficient to
close the exploration question and, by the closure clause of OD-009
Revision 3, returns sequencing authority to ROADMAP.md. Exploration leg 7
is not opened. Obtain/claim and eat remain separate actions. No same-tick
obtain-and-eat revision is authorised, and no kernel or world change is
authorised. The owner's rationale is design authority: possession and
consumption are distinct causal events, and the held-food state is kept so
later systems can interact with it before consumption. This entry is not
experimental proof of capability, reachability, or measurement. It does not
amend OD-013, the leg-6 card, or the leg-6 results. An uncommitted draft of
this section had attributed an owner inspection at particular ticks and a
source-cap observation; that wording was not in the recorded direction at
the time and was not retained by the agent that wrote this paragraph. The
owner then supplied that basis directly on 2026-09-23 (world view inspected
at tick 135 OFF and tick 300 ON; source at cap while people hungry and away
from it, carried as an input), and it is recorded in OD-014 under
"Owner-supplied basis". Both steps are kept here so the provenance is
visible.

Tooling scope, stated once: orchestrator and evidence tooling work is in
scope for ratification-lane slices under OD-013 and out of scope for
exploration legs. First such change, in the OD-014 commit:
`automation/preflight.py` derives the milestone from ROADMAP.md's explicit
"Stage N continues at / is open at slice X" statement, falling back to the
historical slice-1a phrases only when no such statement exists. The two
prior snapshots had carried `current_milestone: Stage 1, slice 1a` to keep
the orchestrator's block-on-inconsistency from refusing every action; that
value was false and is corrected with this entry. The orchestrator's
blocking rule itself is unchanged.

First unmet ratification requirement: slice 1c, sealed evidence stream and
replay, then slice 1d, then an independent Stage 1 exit review. Slices 1a
and 1b have independent different-model PASS reviews on their kernel claims
(2026-09-21). Those reviews are not the Stage 1 exit. The exploration stream
(`stream/`, format `v3.stream.2`) already provides canonical per-tick content
lines, recomputed record and state digests, prior/next state chaining
including production, a trail digest, tamper detection and byte-identical
reruns. RECORD describes that stream as exploration, not a sealed
ratification schema.

ROADMAP "Evidence and foundation checks" and the slice 1c proof object still
require a specified evidence schema before its writer; a complete-tick seal
tied to code, configuration and schema identities; replay from genesis and
declared inputs checked against the file rather than against a second run;
recovery through the last verified sealed tick, including resume with pending
reservations; and isolation of two instances restored from the same state.
OD-013 names the opened 1c work as a sealed evidence stream and replay, and
names 1d as the 50-actor cost envelope. Recovery and instance isolation are
in the ROADMAP 1c proof object and are not named in that OD-013 sentence.
This entry does not choose that boundary and does not specify the schema.
Nothing of slice 1c is implemented or run here. Stage 1 exit remains unclaimed.
