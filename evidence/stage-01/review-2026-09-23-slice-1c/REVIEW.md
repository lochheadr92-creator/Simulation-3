# Independent executing review — Simulation 3, Stage 1 Slice 1c

**[RERUN] Verdict: FAIL for Slice 1c at `d14decec50d285395febb97c06d8eb7d94930b88`.** The intact references, declared recovery cuts, replay, isolation and compatibility checks reproduce. Two additional probes demonstrate defects in the required handling of broken files: malformed suffixes prevent recovery of a valid sealed prefix, and a later unsealed header controls recovery. Findings: **2 blocking, 1 should fix, 2 observations**. No repository fix was made.

**[READ] Scope:** owner-requested independent Slice 1c review only. The earlier summary-only PASS is superseded and supplies no evidentiary support here. The current request supersedes the card's restriction on the timing of a separate 1c review. OD-013's Stage 1 exit-review timing remains unchanged. **Stage 1 exit: not claimed.** Slice 1d capacity acceptance, later-stage behavior and publication are outside this verdict.

## Reviewer, environment and evidence labels

- **[READ] Reviewer:** Codex, based on GPT-6, using the Codex desktop execution tools and reviewer-authored Python probes. I did not build Slice 1c and did not access the builder's session. I read the supplied conversation and package instructions as context, then assessed the archive and fresh executions. The builder is recorded as Claude, configured `claude-opus-5-5`; this reviewer is a different model family.
- **[UNKNOWN] Exact serving-model identifier:** not exposed in this session. No more specific model identifier is asserted. The builder's actual serving model likewise cannot be independently established from this archive.
- **[RERUN] Execution environment:** Windows 11, build 10.0.26200; CPython 3.12.10, MSC v.1943 64-bit AMD64; pytest 9.1.1 already installed; Git available, version 2.55.0.windows.5. Review began 2026-09-23 at 12:04:11 UTC / 22:04:11 Australia/Brisbane. Exact command completion timestamps are in `outputs/*.command.json`.
- **[RERUN] Isolation of work:** two separate extractions under the review workspace, `work/pristine/` and `work/run/`. Runs used `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1` and Python `-B`; tests disabled pytest's cache and used fresh temporary directories. Repository commands ran from the working repository root. Reviewer scripts and generated files live outside the repository. Only P8 temporarily changed repository source, one fault at a time, with restoration after each.
- **[RERUN] Preservation:** all 835 pristine archive files, including `.git` and wheels, match the archive; all 268 working-tree files match the original extraction at completion. Final HEAD remains pinned, Git status is empty, and strict fsck passes. Frozen references were never overwritten. See `outputs/final-preservation.json`.
- **[UNKNOWN] Cross-platform behavior:** this review ran on Windows, like the reported reference-generation environment. Six separate-process comparisons were executed; Linux/macOS reproducibility was not. The instruction's assumption of a different OS does not apply here.

**[READ] Labels:** RERUN means I executed a check or calculated a quantity from the supplied bytes; READ means source/document inspection or an interpretation of the stated contract; UNKNOWN means evidence was unavailable or execution did not establish the claim. Historical execution is not promoted to RERUN merely because a fresh comparable run passed. A PASS below applies only to the named bounded claim.

## Target identity

**[RERUN]** The conversation attachment was resolved to a local Windows file; `/mnt/data` was not available. Before extraction or repository execution, its size was **4,580,061 bytes** and its SHA-256 was:

`3ad56ed18a3b05f32dcb3b6c9596879f8954326ab5f2eccc5e9b66d2b095f80b`

**[RERUN]** `git rev-parse HEAD`, clean `git status --short`, `git fsck --full --strict`, and the first-parent log verified the following chain. Evidence: `outputs/identity.json`, `outputs/initial-file-manifest.json`.

| Classification | Commit | Role read from the packet and history |
|---|---|---|
| RERUN | `6f500408b59e69f6f9c0da2be14172bb2f30a993` | OD-015/base |
| RERUN | `56d3c3fe746f22ca58f4219a9ac0aa3b16293623` | Pre-code declaration |
| RERUN | `028ffa8da78a9cd1ba95f06556d12a54fe5286ab` | Commit A |
| RERUN | `d14decec50d285395febb97c06d8eb7d94930b88` | Commit B/review target |

**[RERUN]** Declaration items 1–13 are identical between `56d3c3f` and the target after newline normalization; SHA-256 of the compared declaration text is `279bdc87e7b1e480c08b168b21ac95dd006eab5e960dab9ef36b163ab3fac880`. The complete base-to-target diff is saved in `outputs/P9-full-diff.stdout.txt`.

## Material read

**[READ]** AGENTS.md Exit review and OD-013–015; ROADMAP Stage 1, tick algorithm and Evidence and foundation checks; DOCTRINE; RECORD status, active card, declaration, departures, commit A and results; the earlier 1a and 1b review reports and relevant recorded limitations. I read the seven requested stream/world writer, runner, replay and recovery files in full; the changed reconstruction/configuration/viewer code; all five new/extended 1c test files and the requested existing-test changes. I additionally inspected engine ownership, proposals, outcomes, observation/reservation tests, native scoring capture and the reference reproducer. `outputs/read-index.json` indexes the principal reads; `outputs/inspected-source.txt` retains numbered source/document text; P9 retains the entire change set.

**[READ]** Earlier review reports are historical evidence only. They report 1a PASS and 1b kernel PASS with then-existing integration findings. This review does not independently rerun those historical snapshots or silently erase their findings; current compatibility and integrity tests were executed at the pinned 1c target.

## Required checks R1–R7

| Check | Classification | Result | Evidence |
|---|---|---|---|
| R1, complete suite in one invocation | RERUN | **559 passed, 35 setup errors, 71.93 s**. Simulation partition: **372/372 passed**, 24 files. Automation partition: **187 passed, 35 setup errors**, 7 files. | `outputs/R1-suite.stdout.txt`, `.stderr.txt`, `.command.json`, `R1-junit.xml`, `R1-partition.json` |
| R1 error classification | RERUN | All 35 require absent sibling `work/run/orchestrator-freeze`: audit 8, execution 20, runtime/startup 7. No simulation failures and no additional OS-related failure observed. | `outputs/R1-error-classification.json`, full per-test errors in `R1-partition.json` |
| R2 reference reproducer | RERUN | **12 of 12 checks passed**. | `outputs/R2-reproduce.stdout.txt` |
| R3 fixture digests | RERUN | Raw output differs because stdout uses CRLF; exact equality after CRLF→LF, with no stripping of other whitespace. | `outputs/R3-fixture.stdout.txt`, `R3-comparison.json` |
| R4 scenario and world replay | RERUN | Both compare 120 ticks, report identical, and report code identity equal to header. | `outputs/R4-scenario.stdout.txt`, `R4-world.stdout.txt` |
| R5 scenario cut after tick 40 | RERUN | 11 live reservations; resumes 41–119; every non-timing content line equals the reference. | `outputs/R5-scenario.stdout.txt`, `R5-scenario-comparison.json`, `artifacts/R5-scenario-*.jsonl` |
| R5 world cut after tick 60 | RERUN | 0 live reservations; resumes 61–119; every non-timing content line equals the reference. | `outputs/R5-world.stdout.txt`, `R5-world-comparison.json` |
| R6 preflight | RERUN | PASS; the two disclosed informational inconsistencies remain: `record_rollback_describes_no_remote`, `stage_card_review_status_stale`. | `outputs/R6-preflight.stdout.txt` |
| R7 quantitative inventory | RERUN / READ / UNKNOWN | Enumerated below. Fresh results are distinguished from historical builder executions. | `outputs/P1-P2-R7-independent.json`, `R7-weighted-shares.json`, `R7-seed-matrix.json` |

**[READ]** The missing sibling errors reproduce the archive dry-run disclosure. They are an archive reproducibility limitation, not evidence of a new simulation defect. Automation remained parked: no repair, extension or substantive audit was performed.

### Quantitative claim inventory

| Claim in the results / requested quantitative checks | Classification | Observed result | Evidence |
|---|---|---|---|
| Format/versions | RERUN | `v3.stream.3`, `0.2.0-stage1b`, `v3.kernel.1b.1`; versions unchanged in protected source | P1/P2, P9, reference headers |
| 29 Python source files and code identity | RERUN | 29; `5c250fd164cecbdd98fcd412db58ee2b1d4e548a174047ed36882fdad44be8ad`; both header maps/digests agree | P1/P2 |
| Scenario file size/SHA | RERUN | 658,524 bytes; `ad6aa0b23045cd7f30906c439c773963b56a980ca39cd3d07c1229a0a27ea6d2` | P1/P2 |
| World file size/SHA | RERUN | 313,187 bytes; `8573efa7d2b0dad457d00e11ec2df63a11777e37b0fd19719457cffb51887c8c` | P1/P2 |
| Scenario final seal | RERUN | `62cb2d489122d37791fd077e8edd4e55b93f6776579c3c5191a0c1ce08c46549` | Independent P1 calculation |
| World final seal | RERUN | `2db221dcaa15076212ee692e79e680893a0252c6d8835040f512a49f8d857b97` | Independent P1 calculation |
| Scenario trail digest | RERUN | `f9414d0099af3c1c5cf30f951d4c26a9f5899ad3bb266a0806fd1144067fbe9d` | Independent P1 calculation |
| World trail digest | RERUN | `ddfeec26a28909311d437a089783b5f29c8c19684aab362606d9912d904a7134` | Independent P1 calculation |
| Tick counts / horizons | RERUN | Both have 120 tick lines, 120 timing lines and end count 120; 121 seals each including header | P1/P2 |
| Scenario cut source | RERUN | 170,147 bytes; `b91069fbfb89a5b9c83b844d15afca9f0fe8df7bd6bc1df2de53169ba9d0f35a`; tick 40, 11 holds, resumes 41–119 | R5 |
| World cut source | RERUN | 178,216 bytes; `2d168e8eccaf0aabfe45add8c67960c7f8a6a303f5f7297c7345c49679770aea`; tick 60, 0 holds, resumes 61–119 | R5 |
| Scenario seeds 7, 11, 23, each 120 ticks | RERUN | All 3 replay test cases pass at target | R1 XML, `R7-seed-matrix.json` |
| World seeds × yield × scoring, 120 ticks | RERUN | All 12 combinations pass at target | R1 XML, `R7-seed-matrix.json` |
| Both reference replays and reproducibility | RERUN | Identical; reproducer 12/12; independent process content comparisons 6/6 | R2, R4, P7 |
| Approx. 5.5 KB/scenario tick, 2.6 KB/world tick | RERUN | Whole-file bytes / 120 = 5,487.700 and 2,609.892 bytes; mean tick-line bytes = 5,408.917 and 2,512.708 | P1/P2 |
| Approx. 63% ledger, 22% record, 8% inputs | RERUN | Scenario weighted byte shares: **62.513%, 21.443%, 7.972%**. Arithmetic means of each tick's ratios: **61.079%, 22.024%, 7.819%**. Broad approximations reproduce, but “each tick” is not a fixed share. | `R7-weighted-shares.json`, P1/P2 |
| Frozen timing means 0.28 ms / 0.17 ms | RERUN | Recomputed from stored timing values: **0.2797825 ms / 0.165501667 ms** | P1/P2 |
| Timing measures engine tick/world step, excludes write | READ | Confirmed placement of timer boundaries in both runners. This is not a fresh performance measurement. | `stream/run.py`, `world/run.py` |
| Rejected “holds never expire” explanation | RERUN | 24 distinct reservation IDs disappear between successive recorded states; maximum live holds 16 | P1/P2 |
| 472 inputs, 3 typed inputs, 16 empty scenario ticks | RERUN | Same counts in the final frozen scenario reference | P1/P2 |
| 1b fixtures and head-b305783 decisions | RERUN | Fixture equality after newline normalization; both perception/yield compatibility tests pass; protected files unchanged | R3, R1, P9 |
| Builder's original 594-pass invocation | READ | Stated in RECORD; this archive freshly produces 559 passes + 35 disclosed setup errors | RECORD, R1 |
| Whether the original 594-pass process actually ran as reported | UNKNOWN | Historical process not independently observable from the retained archive alone | No fresh historical execution claimed |
| Earlier commit A: 581 passes, 658,351 / 313,009 bytes | READ | Historical commit A entry inspected; those executions and timing-dependent file sizes were not rerun | RECORD commit A |
| 50 actors / 64 KiB per tick ceiling | READ | ROADMAP requirement, not a measured 1c result | ROADMAP Stage 1d |
| Achievement of capacity ceilings | UNKNOWN | Not tested; Slice 1d outside scope | None |

**[READ]** The disclosed reference deletion/recreation, failed draft claims, and amendment from `75e7792` are build-history statements. **[UNKNOWN]** This pruned archive does not establish their full session chronology or permit verification that only RECORD changed in the discarded amendment. They are not used to support the verdict. The final bytes and final code identity were independently verified.

## Independent probes

| Probe | Classification | Method and result | Evidence |
|---|---|---|---|
| P1 | RERUN | Independently implemented item 3 using only kernel canonical bytes/digest, not stream seal helpers. Both header/tick chains, final seals, horizons and SHA-256 trails verify. Replacing all timing values leaves computed content identities unchanged. | `probes/probe_integrity.py`, `outputs/P1-P2-R7-independent.json` |
| P2 | RERUN | Independently hashed all 29 source files with CRLF normalization and recomputed map/config identities. Headers contain no Git/host/absolute-path/clock metadata; code file paths are relative. | Same script/output |
| P3 | RERUN | Seven required damage cases behave as declared; additional malformed-input cases expose F1. A second-header case exposes F2 after changing its horizon. | `outputs/P3-reader.json`, `extra-unsealed-header.json`, `minimal-findings.json` |
| P4 | RERUN | Changed tick 37 availability, independently resealed whole file: reader accepts; replay reports exactly tick 37, field `availability`. | `outputs/P4-forgery.json`, `P4-replay.stdout.txt`, forged file |
| P5 | RERUN | Reviewer-selected cuts 21, 33, 73 with 3, 10, 14 holds; tick 21 creates a hold; tick 33 has a hold closed at 34. Each resumes to identical non-timing content. Mid-file broken seal at tick 57 resumes from 56 identically. Tested refusals create no file; both runner overwrite attempts preserve sentinel bytes. | `outputs/P5-recovery.json`, CLI logs, source/recovered files |
| P6 | RERUN | Restore three engines at tick 33; traverse 71 mapping/dataclass objects per state, including nested effects and object dictionaries: no shared objects between A/B. Ordinary mutation attempts fail; canonical copies detach; advancing A leaves B/C unchanged; all three independent advances match stored tick 34. Even reflective edits to disposable A's Source/Reservation/Effect dictionaries leave B/C unchanged. | `probes/probe_isolation.py`, `outputs/P6-isolation.json` |
| P7 | RERUN | Six fresh subprocesses: both references at hash seed unset, 0, 4242, fixed simulation seed 7 and horizon 120. Every content line and final seal matches. | `probes/probe_processes.py`, `outputs/P7-process-determinism.json` |
| P7 platform extension | UNKNOWN | No different OS used. | Environment limitation |
| P8 | RERUN | Six sequential source mutations, baseline/restored test sets both 131/131. Four mutations detected, two survive; details below. Full file restoration verified after every fault. | `probes/probe_mutations.py`, `outputs/P8-*.patch`, `.xml`, `.stdout.txt`, restoration JSON |
| P9 | RERUN | Protected paths unchanged; state changes additive by AST comparison; declaration 1–13 identical; full history diff retained. | `probes/probe_rails.py`, `outputs/P9-rails.json` |
| P9 semantic scope | READ | No changed settlement/engine/proposal/version/decision implementation, lever default or generator randomness. The world loop was extracted into the shared step without a new policy. | Full diff and compatibility runs |

### P3 exact break reports

| Variant | Classification | Expected and observed last sealed tick / first break line |
|---|---|---|
| Flip seal byte at tick 57 | RERUN | 56 / 116 |
| Edit header | RERUN | -1 / 1 |
| Delete tick 57 | RERUN | 56 / 117, after the intervening timing line |
| Swap ticks 57/58 | RERUN | 56 / 116 |
| Cut tick 57 midway | RERUN | 56 / 116 |
| Edit numeric timing value | RERUN | 119 / none; remains complete |
| Junk after end | RERUN | 119 / 243; incomplete |
| Invalid UTF-8 byte in tick 57 | RERUN | Expected 56 / 116; exception instead (F1) |
| Non-integer timing after tick 57 | RERUN | Expected report retaining tick 57; exception instead (F1) |
| Nonempty list as record | RERUN | Expected break report retaining tick 56; AttributeError instead (F1) |

### P8 mutation results

| Injected fault | Classification | Result |
|---|---|---|
| Drop `prev` from tick seal | RERUN | **Survives: 131 passed** (F3) |
| Retain exactly one next raw line after verified tick | RERUN | **Survives: 131 passed**; that line is timing in tested recovery inputs (F4) |
| Share one restored balance mapping | RERUN | Detected: 2 failed, 129 passed |
| Skip scenario generator comparison | RERUN | Detected: 1 failed, 130 passed |
| Add timing line to trail hash | RERUN | Detected: 36 failed, 95 passed |
| Additionally retain next unsealed tick, skipping timing | RERUN | Detected: 3 failed, 128 passed |

**[RERUN]** Exact failing test names are saved in `outputs/P8-mutations.json`; failures were assertions, not collection/setup errors. The generator mutant specifically fails its refusal test; the extra-tick mutant fails half-line, broken-last-seal and never-use-unsealed-line tests. No assertion, reference or test was altered to make a check pass.

## Trust model and ROADMAP coverage

**[READ]** The seals are unkeyed digests. They detect accidental/tampered content when expected digests are retained; a forger can recompute them. They do not authenticate an author, prove a run actually occurred, or prove semantic correctness. The package SHA-256 is a separate owner-supplied identity anchor. P4 demonstrates why independent execution is needed.

**[READ]** Scenario replay executes the kernel from header genesis with the recorded ordered proposals; it does not regenerate the scenario proposal sequence. Recovery separately rebuilds that generator and checks recorded inputs before continuation. This satisfies ROADMAP's “genesis and declared inputs” wording for the synthetic kernel scenario: its proposals are the declared inputs. It does not establish that any arbitrary resealed input sequence came from the advertised generator. World replay recomputes decisions and inputs through live world code. No authenticator or independent second simulation implementation is claimed.

**[READ]** The record generally states this trust boundary correctly, including content equality excluding timing. Its broad broken-file recovery language is stronger than the implementation supports, as F1/F2 show. Passing reference replays do not rescue those defects.

| ROADMAP requirement | Classification | Coverage and evidence |
|---|---|---|
| Schema declared before writer | RERUN | Covered by 1c history/declaration equality (P9); chronology read from commits |
| Genesis and code/config/schema identities | RERUN | Covered by P1/P2, reconstruction/replay tests and headers |
| Ordered inputs and tick IDs | RERUN | Covered by `test_inputs_are_the_proposals_the_runner_submitted_in_order`, typed/empty cases, P1/P3 |
| Proposal/action IDs | RERUN | Inputs link to outcomes by proposal ID; earlier 1b lifecycle/identity tests rerun in R1 |
| Resolution reasons | RERUN | Native outcome records; atomicity/reservation tests and altered-outcome replay test pass |
| Balanced effects and reservation transitions | RERUN | Earlier 1a/1b test coverage retained and rerun; R3 digests unchanged; P5 cuts carry live obligations |
| State/event identities | RERUN | Stored state/record digests and tick IDs checked by reference suite; P1 chain and R4 replay |
| Complete-tick seal | RERUN | Declared chain verifies in both references; writer horizon/end tests pass; F1 limits reader failure handling |
| Actual immutable decision inputs/alternatives linked to outcomes | READ | At kernel scope, ordered frozen proposals plus referenced tick-start state and native outcomes capture the alternatives settled. Stream records actual submitted proposals, not reconstructed decisions. R1 input-capture tests exercise the link. Optional world records include actual observations/decisions/scores; `test_native_pairs_equal_selection_time_and_header_declares_model` passes. No later-stage social decision evidence inferred. |
| Diagnostic capture cannot change history/state/identity allocation | RERUN | Earlier `test_diagnostics_on_and_off_produce_identical_canonical_results`, hostile sink test, and 1b `test_diagnostics_cannot_change_lifecycle_or_identity` pass. The latter covers allocated action IDs. |
| Partial writes recover only through last verified sealed tick | RERUN | **Incomplete implementation: F1/F2 blocking.** Ordinary cut/half-line cases pass, but malformed suffixes can block recovery and an unsealed header can govern continuation. |
| Resume pending reservations equals uninterrupted execution | RERUN | Covered for declared tick 40 and independently selected ticks 21/33/73; broader damaged-file guarantee fails F1/F2 |
| Independent replay from genesis and declared inputs | RERUN | Covered within described trust model: R4, seed matrix and P4 |
| Input-map permutation | RERUN | Earlier determinism/input-order tests and `test_permutations_of_two_reservations_and_mixed_terminal_requests` rerun successfully |
| Repeated execution | RERUN | R2 and six fresh-process P7 comparisons |
| Unauthorised writes | RERUN | Earlier atomicity/authority tests and 1b owner-only completion/cancellation tests pass |
| Observer mutation of live/prior state | RERUN | Earlier observation tests and reservation immutability test pass; P6 adds restored-instance checks |
| Two restored instances isolated | RERUN | P6 and existing restore tests pass |
| Dependency direction | RERUN | All 8 dependency tests pass; protected-path/diff inspection agrees |
| Reference suite | RERUN | 372 simulation tests pass; R3 fixtures and recorded decision tests pass; 35 external automation setup cases unavailable (F5) |
| 50-person cost envelope after 1a–1c | READ | Assigned to 1d, not covered or accepted here |

**[READ] Declaration completeness:** the essential-claim row is a compact summary and does not restate every foundation check, but declaration items 1–13 plus retained 1a/1b checks cover those responsibilities. No additional undeclared ROADMAP requirement was found that must be deferred merely to pass 1c. The uncovered obligations are the demonstrated recovery/reader behaviors, not a license to move them into 1d.

**[READ] Declared departures from the build brief:** omitting Git fields preserves replayable identity while external commit pinning provides provenance; typed params preserve malformed submitted inputs; printing recovery provenance rather than modifying the header preserves content equality; reconstructing/checking the scenario generator meets continuation needs; placing world replay/recovery in world preserves dependency direction; recognizing the new format in the viewer is compatible; measured file sizes replace an unsupported estimate; optional world targets respect Stage 1's kernel-only scope. None inherently weakens a ROADMAP 1c requirement. Recovery still must satisfy its declared boundary despite these choices.

## Verdicts against essential claims

| Claim | Classification | Verdict | Reason |
|---|---|---|---|
| (1) Header/ticks in one chain; reader names first break | RERUN | **FAIL** | Chains correct and ordinary tamper cases pass; F1 returns exceptions instead of required prefix/break information |
| (2) Genesis + recorded-input replay reproduces tick payloads | RERUN | **PASS** | R4, three-seed matrix, P4 divergence and independent P7 regeneration; bounded by trust model |
| (3) Cut/broken-file recovery through last sealed tick | RERUN | **FAIL** | Declared/live-hold cuts pass, but F1 prevents valid-prefix recovery and F2 uses unsealed suffix metadata |
| (4) Restored engines share no mutable object | RERUN | **PASS** | P6 object traversal/mutation/advancement and existing tests |
| (5) Canonical forms, 1b digests, head-b305783 decisions unchanged | RERUN | **PASS** | R3, compatibility tests, additive-only state change and protected files unchanged |
| (6) Dependency direction tested | RERUN | **PASS** | R1 dependency checks; no upward imports introduced in inspected change |
| 1a/1b integrity rails unchanged | RERUN | **PASS** | Protected implementation unchanged; prior canonical methods unchanged; current rails tests pass |
| Optional world (1), sealing/reader | RERUN | **FAIL** | Frozen chain passes; same malformed-byte/timing reader failures reproduced on world file |
| Optional world (2), replay | RERUN | **PASS** | 12 combinations, frozen replay, altered-decision test and P7 |
| Optional world (3), recovery | RERUN | **FAIL** | Declared/production cuts pass; F1/F2 also independently reproduced on world file |
| Stage 1 exit | READ | **Not claimed** | This is a bounded 1c review; 1d not assessed |

## Findings and minimal reproductions

### F1 — Blocking: malformed suffixes prevent recovery of an intact sealed prefix

**[RERUN]** In either frozen reference, replace one byte of tick 57's seal text with `0xff`, leaving every earlier byte intact. `read_run` raises `UnicodeDecodeError` instead of reporting last sealed tick 56 and break line 116; recovery also fails and writes nothing. Separately, changing the timing value after tick 57 to `"broken"` raises `ValueError`, though tick 57 is valid. A nonempty list as `record` raises `AttributeError`. CLI evidence is retained, including exit 2 for the malformed-byte/timing cases and a traceback for the malformed record.

**[READ] Cause/requirement:** `stream/run_file.py:499` catches `JSONDecodeError` but not byte decoding failures; `:536` assumes a mapping record; `:570` blindly converts timing values. `sealed_prefix` calls this full reader before it can retain the verified prefix. This violates declaration items 4/7 and ROADMAP's damaged/partial evidence recovery boundary. Handling an untrusted suffix must not require it to be semantically well formed.

**[RERUN] Minimal reproduction:** run `probes/reproduce_findings.py` with `SIM3_REVIEW_REPO` pointing to the unchanged target. It changes only new file copies and exercises both runners' underlying recovery APIs. The single-byte case is under `outputs/artifacts/minimal-findings-frfw9r03/`. Exact exceptions and expected prefix boundaries are in `outputs/minimal-findings.json`; original CLI cases are `outputs/P3-non-utf8.*`, `P3-timing-wrong-type.*`, `suffix-nonempty-record.*`. No fix applied.

### F2 — Blocking: a later unsealed header controls recovery

**[RERUN]** Replace the line for tick 57 with a copy of the original header whose horizon is 121, leaving its seal unchanged and invalid. The reader correctly flags a second header at line 116 and reports last sealed tick 56, **but returns the unsealed replacement as `run.header`**. Recovery resumes ticks 57–120, writes 121 ticks under the original horizon-120 header, and produces a file that fails verification. This occurs for both scenario and world files. The scenario CLI exits 1 after writing the invalid file; the recovery API returns a result rather than refusing.

**[READ] Cause/requirement:** `stream/run_file.py:513–531` overwrites header/expected tick even after detecting a second header; `stream/recover.py:65–93` uses that returned header for configuration/horizon. The kept prefix bytes still contain the original header, so output metadata and continuation disagree. Item 7 says no unsealed line is used; ROADMAP requires continuation from the verified boundary. A first-break report alone does not establish that recovery ignored everything after it.

**[RERUN] Minimal reproduction:** same `probes/reproduce_findings.py`, case `unsealed-header-horizon`, or `probes/probe_suffix.py`. Source and invalid recovered files are included; `outputs/minimal-findings.json` and `extra-unsealed-header.json` show original horizon 120, returned horizon 121, last sealed tick 56, and 121 output ticks. No fix applied.

### F3 — Should fix: the focused tests miss removal of seal chaining

**[RERUN]** P8 changed `tick_seal` from hashing both `prev` and the tick digest to hashing only the tick digest. All **131 focused tests passed**. Exact patch and command: `outputs/P8-drop-prev.patch`, `P8-drop-prev.command.json`; results: `P8-drop-prev.stdout.txt`, `.xml`.

**[READ] Significance:** the writer, reader and several seal tests use the same helper, so agreement between them does not independently prove declaration item 3. An independent known-vector or formula assertion is needed. This is a test-adequacy finding, not a claim that the unmodified target omits `prev`: P1 proves its frozen references obey the declared chain. R2's frozen-reference checks are additional protection, but were not part of the specified focused test mutation run.

**[RERUN] Minimal reproduction:** apply the one-line saved patch in a disposable working copy and execute the saved focused pytest command; restore from pristine afterwards. `probes/probe_mutations.py` automates the sequential fault/restore procedure used in this review.

### F4 — Observation: exact prefix byte-boundary mutation is not tested

**[RERUN]** Retaining the next raw line after the last verified tick also leaves **131 tests passing**. In the relevant inputs that next line is timing, which content comparisons intentionally exclude. Retaining the next unsealed *tick* instead causes three expected recovery failures. Both patches and logs are retained.

**[READ] Significance:** the suite checks the important canonical-content boundary but does not fully check item 7's exact byte-prefix wording. No additional canonical-state defect was demonstrated by this particular surviving timing-line mutation. Minimal reproduction: `P8-prefix-extra-line.patch` with its recorded command; compare with `P8-prefix-extra-tick.patch`.

### F5 — Observation: archive cannot reproduce the owner's whole-suite green result standalone

**[RERUN]** The 35 setup errors all arise while tests clone missing sibling `../orchestrator-freeze`. Minimal reproduction is the R1 whole-suite command in `outputs/R1-suite.command.json`. Every error is retained individually in `R1-partition.json`. **[READ]** This matches the supplied dry-run disclosure; packaging that sibling would be necessary to claim a standalone 594-pass rerun. It does not invalidate the 372 simulation passes or warrant changing parked automation in this review.

## Discrepancies, limitations and proposed record entry

**[RERUN]** Fresh archive result is 559 passes + 35 setup errors, not the owner's reported 594 passes. Declared frozen-file sizes, SHA values, final seals, trails, cut identities, replay matrix, live-hold count, normalized fixture output and stored timing means reproduce. The damaged-file recovery guarantee does not hold for F1/F2. The 63%/22%/8% size description is approximate and depends on aggregation; precise alternatives are above.

**[READ]** Time measurements exclude sealed writing and cannot establish the 1d cost envelope. Sealed-file identity is not authenticity. No general scalability, fairness, survival, social behavior, cross-version replay or Stage 1 acceptance follows from these runs.

**[UNKNOWN]** Different-OS reproducibility, the unavailable historical builder process, and full-suite execution with the missing sibling remain unestablished. These unknowns do not prevent the bounded FAIL: F1/F2 are independently reproduced at the verified target.

**[READ] Proposed append-only RECORD entry, eight lines; not applied:**

> ### Independent review of slice 1c - 2026-09-23
> [READ] Reviewer: Codex / GPT-6; exact serving identifier unavailable; independent of the Slice 1c builder.
> [RERUN] Target d14decec50d285395febb97c06d8eb7d94930b88; archive size/SHA and source identity verified.
> [RERUN] 372 simulation tests pass; whole suite 559 passed / 35 missing-sibling setup errors; reproduce 12/12.
> [RERUN] Reference replay, declared recovery cuts, independent seals, process determinism and isolation reproduce.
> [RERUN] Verdict FAIL: malformed suffixes block valid-prefix recovery; an unsealed later header governs continuation.
> [RERUN] Focused mutation tests miss removal of prev; source restored exactly. Evidence: sim3-review-1c-output.zip.
> [READ] Earlier summary-only PASS superseded. Slice 1c only; Stage 1 exit not claimed; Slice 1d not assessed.
