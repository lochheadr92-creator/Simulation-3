# Stage 1a independent post-repair review — 2026-09-21

**Verdict: PASS for every essential Stage 1a exit condition at
`fb5a8959fb6a7a23d6e3107fe32be8248cc19901`.** All recorded quantitative claims
were rerun and reproduced, R1–R5 are closed in the code as read, and 21
reviewer-authored probes found no defect. This is the independent post-repair
review named as `next_gate` in SIM3_STATE.md. It is **not** a Stage 1 exit
verdict: slices 1b, 1c and 1d are unbuilt, so Stage 1 remains incomplete and
its exit gate remains unclaimed.

## Reviewer and method

- Reviewer: Claude (configured model `claude-fable-5-1`; the serving model may
  differ), through the Claude desktop link on the owner's machine `theweapon`
  as user `RJLoc`. The builder and repairer of the slice was Codex, a different
  model, satisfying AGENTS.md "separate reviewer using a different model".
- Source: fresh `git clone --no-hardlinks --local` of `C:/dev/03-Living-World-V3`
  into `work/stage1a-review-fb5a895`, checked out at `fb5a895` (the repair-1
  commit; `53f42de` above it changes documentation only). All 56 entries of
  `evidence/stage-01/repair-1/FILE_MANIFEST.json` match. Working tree clean
  before and after every run. Nothing in the original repository was changed.
- Runtime: Python 3.12.14 (the bundled validation venv, base interpreter
  `codex-primary-runtime`), pytest 9.1.1, `PYTHONDONTWRITEBYTECODE=1`,
  `-p no:cacheprovider`, fresh `--basetemp` per run. Same machine as the
  builder; the 2026-09-19 read of the pre-repair source (`fa8be60`) ran on
  Linux/Python 3.10 and is retained as a separate artifact.
- Read in full: AGENTS.md, DOCTRINE.md, ROADMAP.md (Stage 1, tick algorithm,
  credit fixture), `evidence/stage-01/RECORD.md` (card, declarations, attempt
  ledger, results, repair-1 declaration and result), all twelve `kernel/*.py`
  modules, `repair-1/run_mutations.py`, the instrument's classification and
  runner sections. The 2026-09-19 independent read and the pre-repair
  adversarial findings R1–R5 were read for context.

## Claims rerun (all reproduced)

| Recorded claim | Reviewer result | Artifact |
|---|---|---|
| Full suite 148 passed, 0 failed | 148 passed, 0 failed, 0 skipped, 0.89 s | [suite.txt](suite.txt), [suite.xml](suite.xml) |
| `fixture_digests.py` output equals `repair-1/fixtures-repaired.txt` (engine 0.1.1-stage1a) | byte-identical after newline normalisation; A1 tick-0 record `ed5b3c31…`, state `9b5e3046…`; A6 tick-0 `d0a76556…`, tick-1 `b7933d76…` | [fixture_digests.txt](fixture_digests.txt) |
| State digests unchanged from Attempt 1 (engine 0.1.0), record digests differ only through `engine_version` | state digests and outcome lists identical to `instrument/fixture_digests_output.txt`; record digests differ | compared in the 2026-09-20 pilot checker and again here |
| Mutation instrument: 19 of 20 detected, conservation-rail-off declared unreachable, no runner failure counted | 19 of 20 detected; per-mutation detection counts identical to `repair-1/mutation-output.txt` (rotation 8, credit-spendable 5, authority 6, order-by-arrival 8, outcome-order 11, canonical-keys 8, mappings-writable 3, view-shares 2, one-leg 2, dup-identity 3, dup-sequence 2, unbalanced 1, fractional 3, negative-rail 2, reentry 4, unknown-actor-order 1, runner-errors 9, integer-encoding 5, caller-sequence 3, conservation 0); every mutated file and the whole clone restored byte-for-byte | [mutations/mutation-output.txt](mutations/mutation-output.txt), [mutations/mutation-restoration.json](mutations/mutation-restoration.json) |
| 2,592-case contention matrix, both proposal orders | runs inside the 148 (`test_review_regressions.py`) | suite.txt |

## Reviewer probes (new, not derived from the existing tests)

[test_review_probes.py](test_review_probes.py): 21 passed
([probes-attempt-2.txt](probes-attempt-2.txt)). The first attempt had five
failures, all reviewer errors (a `Settlement`/`TickRecord` attribute mix-up, a
record digest compared with a state digest, and a fuzz threshold set above the
observed accept count of 40); it is preserved as
[probes-attempt-1.txt](probes-attempt-1.txt). No probe failure implicated the
kernel.

What the probes establish beyond the packet:

- Namespace collisions: actors named `x`, `actor:x` and `sink:consumed`, plus a
  source named `x`, coexist without cross-crediting; a transfer to the literal
  sink address or to an unknown actor is denied with nothing debited.
- Atomicity with three sources where only the last is short: no leg commits.
- Availability boundary across a transfer chain A→B→C in one tick, at all six
  rotations and both collection orders: the forwarded credit is always denied
  and succeeds at the next tick.
- Duplicate identities across different actors deny both sharers while an
  unrelated proposal from one of them still settles.
- R5: sparse caller orders (7, 10^30) and dense orders (0, 1) produce the same
  record identity; output sequences are dense.
- 300 random shuffles of a nine-proposal tick (including an unknown actor and
  a cross-actor duplicate identity) with shuffled balance and source maps: one
  record digest, one state digest.
- R1: a hostile diagnostics sink that re-enters `tick` is refused inside the
  guard, counted once, and the outer tick commits exactly once; a proposal
  generator that re-enters raises and leaves state untouched; the guard is
  released and the engine is usable afterwards.
- Observation: views, state mappings, source authorised sets and records refuse
  mutation; editing a `canonical()` copy leaves the record digest unchanged; a
  view taken before two ticks still reports the earlier balances.
- R4: canonical integer text equals `str()` for 500 random values up to 10^40
  and the nine-digit chunk boundaries; a 5,001-digit quantity serialises with
  the expected byte layout; booleans, floats, non-string keys and foreign
  objects are refused; a claim and consume of 10^5000 units conserve the total.
- Fuzz: 250 ticks of random proposals (bad amounts, unknown actors, duplicate
  orders and identities, bogus operations) run twice with different collection
  orders: conserved total, no negative holding, exactly one reason per
  proposal, every accepted transaction zero-sum, no account debited beyond its
  tick-start holding within a tick, identical digest trail across both runs.
- An empty roster denies everything and still advances the tick.

## Verdict per essential exit condition (RECORD.md card, Claim row)

| Condition | Verdict | Basis |
|---|---|---|
| One contested source unit → exactly one credited unit, exactly one winner | PASS | fixture digests reproduced; contention tests; rotation mutation detected by 8 tests; probes |
| Invalid or unauthorised transaction commits no part of itself | PASS | atomicity tests; authority mutation detected by 6; three-source probe; unauthorised-sibling probe |
| Indivisible transaction vs insufficient stock rejected without partial credit | PASS | indivisibility tests; one-leg mutation detected; probes |
| Results independent of input-map and proposal-collection order | PASS | 576-permutation test; 300-shuffle probe; both mutations detected; fuzz trail identical across orders |
| Declared rotation gives no permanent winner over equivalent contention | PASS | rotation tests; A1 tick 0/1 digests show pA then pB; chain probe at six rotations |
| A→B transfer/consume fixture honours next-tick availability, prevents double spend | PASS | credit-boundary tests; A6 digests at both resolver orders; chain probe; credit-spendable mutation detected by 5 |
| Observers cannot mutate live or previously observed state | PASS | observation tests; two mutations detected; observer probe |
| Diagnostics on/off and repeated identical execution give identical canonical results | PASS | determinism tests; A8 digests; hostile-sink probe; fuzz double run |
| Integrity rails: no negative balance, conserved total, zero-sum effects, one explicit reason per proposal | PASS | rails tests; fuzz invariants; conservation-rail-off unreachability confirmed by reading `_commit` (stray-account and zero-sum checks make the total change equal `sum(staged) = 0`) |
| R1–R5 (OD-002) | PASS | each has a detected mutation and a passing regression; probes above exercise R1, R4, R5 directly |

## Discrepancies and observations (none blocking)

1. **Superseded declaration left unmarked.** RECORD.md "Proposal identity and
   the actor-local sequence" still states the Attempt-1 contract (sequence
   carried on the proposal); Repair 1 (R5) replaced it with caller `order` +
   engine-assigned `sequence`, which resolves the roadmap discrepancy noted in
   the 2026-09-19 read. A one-line "superseded by Repair 1" note in the
   Declarations section would stop a reader of that section alone getting the
   old contract. Documentation only.
2. **RECORD.md Review section and SIM3_STATE.md** still say no independent
   review has been held. Both need the owner's update citing this review; I did
   not edit the repository.
3. **`Engine._publish` catches `Exception` only.** A sink raising a
   `BaseException` (e.g. `KeyboardInterrupt`) propagates after the state is
   already committed and the guard is released in `finally`; canonical history
   is unaffected. Acceptable; noted for slice 1c's evidence writer.
4. **Duplicate-identity outcomes with identical `(actor, order, operation)`**
   tie in the outcome sort and fall back to submission order, but their
   canonical outcomes are identical (same reason, no effects), so no
   collection-order dependence is observable. Confirmed by the 300-shuffle
   probe, which includes such a pair.
5. **Same-machine review.** Runtime independence is partial: different model,
   different clone and interpreter environment, same Windows host. The
   2026-09-19 Linux read covers the pre-repair source only.

## Limits of this review

Slice 1a only. It does not assess reservations, replay, sealed evidence,
instance isolation, the 50-actor cost envelope, any world or behaviour, or the
Phase 4 orchestrator. Thread-safety is not claimed by the kernel and was not
tested. No claim here advances Stage 1 or authorises slice 1b; that requires an
owner direction.

## Proposed stage-record entry (for the owner to append)

> ### Independent post-repair review — 2026-09-21
> Reviewer: Claude (`claude-fable-5-1`), a different model from the builder.
> Source `fb5a8959fb6a7a23d6e3107fe32be8248cc19901` in a fresh clone; suite
> 148 passed, fixture digests and the 19/20 mutation result reproduced, 21
> reviewer probes passed. Verdict PASS on every essential slice 1a condition;
> R1–R5 closed. Stage 1 remains incomplete (1b–1d unbuilt); the exit gate is
> not claimed. Evidence: `stage1a-review-20260921/` in the review workspace.

## Artifacts

All under `C:\Users\RJLoc\Documents\Codex\2026-09-20\how-the-orchestrator-looking\stage1a-review-20260921\`:
`suite.txt`, `suite.xml`, `fixture_digests.txt`, `run_mutations_review.py`,
`mutations/`, `test_review_probes.py`, `probes-attempt-1.txt`,
`probes-attempt-2.txt`, `probes.xml`, `artifact-sha256.json`. Pinned clone:
`work/stage1a-review-fb5a895` (disposable; branch `review/stage1a-fb5a895`).
