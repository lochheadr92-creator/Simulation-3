# Stage 1b independent review — 2026-09-21

**Verdict: kernel PASS on every slice-1b claim; repository NOT READY TO COMMIT
until two integration defects are fixed.** The reservation lifecycle is correct
as read and as probed: every recorded claim reproduced, and nine
reviewer-authored probes (including a 300-tick lifecycle fuzz run twice with
different collection orders) found no defect. But the working tree fails the
repository's own evidence verification, and the checkout contains a stale
tooling file that kills any bare `pytest` run. Neither is a kernel fault; both
were invisible to the builder's 14-file test selection. Stage 1 exit is not
claimed; 1c and 1d are unbuilt.

## Reviewer, target and method

- Reviewer: Claude (`claude-fable-5-1`; serving model may differ), Claude
  desktop link on `theweapon` as `RJLoc`. Builder: Codex (OD-008), a different
  model.
- Target: the **uncommitted** working tree of `C:/dev/03-Living-World-V3`
  (HEAD `b915aa0`, branch `codex/kernel-first-slice`), snapshotted at 01:41
  ([snapshot.json](snapshot.json), 189 files) and verified unchanged at the end
  of the review. All 12 `after` entries of `slice-1b/FILE_MANIFEST.json` match
  the snapshot. Nothing in the original checkout was modified.
- Read in full: OD-008, the ROADMAP banner change, the Stage 1b card and
  declarations, the complete working-tree diff against `b915aa0`
  ([patch](working-tree-vs-b915aa0.patch), 769 lines: `state.py`,
  `settlement.py`, `proposals.py`, `outcomes.py`, `reasons.py`, `version.py`,
  `__init__.py`), and `tests/test_reservations.py` (64 cases).
- Runtime: Python 3.12.14 (validation venv over the native runtime), pytest
  9.1.1, no bytecode, no cache, fresh basetemps.

## Claims rerun

| Claim | Result | Artifact |
|---|---|---|
| Final kernel run: 212 passed (14 files) | 212 passed, 0 failed, 1.03 s | [suite.txt](suite.txt), [suite.xml](suite.xml) |
| `fixture_digests.py` output = `slice-1b/fixtures-stage1b.txt` (engine 0.2.0-stage1b, schema v3.kernel.1b.1) | byte-identical | [fixture_digests.txt](fixture_digests.txt) |
| Eight legacy fixture ticks: economic content unchanged from 1a after removing the declared additions | reviewer capture identical to the builder's; after stripping only `schema_version`, `engine_version`, empty `reservations`, null `action_id`/`reservation` and derived digests, identical to `repair-1/fixtures-repaired.json`; all 32 digest fields changed, as declared | [fixtures-review.json](fixtures-review.json) |
| "No failing test run" | true for the 14 selected files; **not true for the whole tree** (see F1, F2) | [bare-pytest-snapshot.txt](bare-pytest-snapshot.txt), [mutations-attempt-1-baseline-blocked/](mutations-attempt-1-baseline-blocked/) |

## Design read (settlement.py, state.py)

- Holds encumber tick-start stock without moving it: `WorldState.availability()`
  = balance/stock minus all holds; `__post_init__` rejects any state where a
  hold exceeds its account, so a held unit is unspendable by ordinary
  proposals by construction, not by bookkeeping. Conserved total counts held
  units once.
- Phases: cancel (0) → complete (1) → new work (2), then rotated rank, then
  dense sequence. Cancellation of an action always precedes its completion
  regardless of the owner's declared order (roadmap step 3). `available` is
  captured before any release, so cancelled or completed stock is not free
  until the next tick (roadmap: released reservations spendable at next tick
  start).
- Completion settles exactly the frozen effects against its own hold, never
  against free availability; it is exactly-once because the action is removed
  from the tick-local reservation map on the first accepted close and later
  requests see `denied_unknown_action`. Same-tick completion of a new hold is
  impossible because validation reads tick-start reservations only.
- Action IDs are `action:` + digest(tick, actor, dense sequence): deterministic,
  unique per tick, never reused across ticks; owner checked before any close.
- Rails retained; `_commit` additionally converts reservation-state
  `ValueError`s into `IntegrityError`.

## Reviewer probes (9 passed on attempt 2)

[test_review_probes_1b.py](test_review_probes_1b.py),
[probes-attempt-2.txt](probes-attempt-2.txt). Attempt 1
([probes-attempt-1.txt](probes-attempt-1.txt)) failed only the fuzz's own
coverage floor: nothing produces units in this slice, so a four-unit economy
drained and later ticks were all denials; the economy was deepened, no kernel
behaviour changed. Established:

- An actor's declared order cannot put its spend ahead of its own completion;
  held units stay unspendable; phase precedes sequence in the record.
- A hold survives 24 ticks of other actors' activity with the owner's free
  balance at zero, then completes.
- Two actors reserving the last source unit at ticks 0–3, both orders: exactly
  one hold, decided by rotation.
- A cross-actor cancel alongside the attacker's own valid completion:
  unauthorised and accepted respectively; the victim's hold survives.
- Nested `reserve` and reserved terminal operations leave no hold; extra keys
  in the inner plan are tolerated exactly as 1a's expanders tolerate them.
- Held units count once in `total()` and `availability()`; two holds
  overcommitting one account are rejected at state construction.
- A reserved transfer credits the recipient only at completion, and that
  credit is spendable only the tick after.
- Action IDs are stable across engines and change with tick, actor and dense
  sequence (a preceding proposal by the same actor shifts them).
- Fuzz, 300 ticks × 2 runs with different collection orders, four actors, two
  sources, random reserve/complete/cancel/claim/transfer/consume with bad
  amounts, ghosts, duplicates and bogus action IDs: conserved total; no
  negative availability; one reason per submission; each accepted close
  matches its frozen plan and happens exactly once ever; phase-2 debits never
  exceed tick-start free stock; unclosed holds persist unchanged; identical
  digest trails across both runs (>60 holds created, >40 closed, >20 completed).

## Verdict per slice-1b claim (RECORD.md card, Claim row)

| Claim | Verdict |
|---|---|
| Reserved units cannot be spent twice | PASS |
| Atomic acquisition and settlement (multi-source all-or-none) | PASS |
| Owner-only cancellation/completion | PASS |
| Cancellation wins same-boundary races | PASS |
| Completion/release happens at most once | PASS |
| Credits and released holds spendable only next tick | PASS |
| Ordering, immutable observation and conservation remain valid | PASS |
| Legacy (no-action) behaviour unchanged | PASS |

## Findings

**F1 — Blocking before commit. The working tree fails the repository's own evidence verification.**
`automation/verify_evidence.py --root .` returns ERROR with three
`manifest_hash_mismatch` errors for `kernel/proposals.py`, `settlement.py`
and `version.py` against `repair-1/FILE_MANIFEST.json` (contract
`stage-01-repair-1`, role historical), and `preflight.py` lists the same three
inconsistencies ([verify-evidence-on-1b-tree.txt](verify-evidence-on-1b-tree.txt),
[preflight-on-1b-tree.txt](preflight-on-1b-tree.txt)). Three tooling tests
fail (`tests/test_verify_evidence.py`, 247 passed / 3 failed with the stale
file set aside). The orchestrator treats these inconsistencies as blockers.
Cause: a historical packet's file manifest is compared against the live tree,
so any later kernel change breaks it; 1b is such a change. Options, owner's
choice: (a) make the verifier compare a historical manifest against the
contract's `recorded_revision` blobs (`git show rev:path`) rather than the
working tree, or (b) add a Stage 1b contract and manifest and re-scope
`stage-01-repair-1`'s manifest check. (a) fixes the class; (b) fixes the
instance. Either way the three tests must pass on the committed tree.

**F2 — Blocking for any bare `pytest` in this checkout. Stale orchestrator kills the test runner.**
The untracked, pre-freeze `automation/orchestrator.py` (reviewed NEEDS FIXES,
F4) probes lock liveness with `os.kill(pid, 0)`, which on Windows terminates
the target process. Its own untracked test writes the pytest PID into the lock
file, so `pytest` with default collection dies silently at 23%
([bare-pytest-snapshot.txt](bare-pytest-snapshot.txt),
[legacy-test_orchestrator-alone.txt](legacy-test_orchestrator-alone.txt)).
Consequences: the 1a mutation instrument cannot run in this checkout; the
registered `py -3 -m pytest` gate would be killed. The repaired orchestrator
lives on `codex/orchestrator-phase4-repair` (+ repair 2). Recommendation: an
owner direction to remove these two stale files from the main checkout (or
land the repaired branch), independent of any further orchestrator work.

**F3 — Mutation instrument is stale for 1b (recommended, not blocking).**
With F2's files and the verifier test set aside, the 1a instrument ran three
mutations (rotation 9, credit-spendable 5, authority 7 tests noticed, all more
than in 1a) and then stopped: the `order-by-arrival` anchor no longer exists in
the phased sort ([mutations/mutation-output.txt](mutations/mutation-output.txt)).
The instrument needs its anchors updated and, per doctrine 7, reservation-rule
mutations added (completion checked against free stock, release spendable
same tick, close without removing the hold, owner check off, phase order off).

**Observations (non-blocking)**
1. `ROADMAP.md`'s status banner was amended under a two-word direction. The
   amendment is scope-only and consistent with OD-008; the owner should
   confirm it is intended as part of the same commit.
2. This checkout's register jumps OD-004 → OD-008; OD-005–007 exist on other
   branches / a published revision `810ab25` not present locally. Reconcile
   the register when branches merge.
3. `WorldView.reservations` exposes every actor's frozen plan. Declared as the
   whole-boundary view of slice 1a; Stage 2 must bound it (doctrine 6).
4. All state digests changed with the schema, including states with no
   reservations. Declared; 1c's sealed evidence must carry schema version per
   record (it already does).
5. The 1a review's proposed record entry (2026-09-21) is not yet in RECORD.md;
   the 1b card now sits above the retained 1a record.

## Limits

Slice 1b only, same host as the builder, uncommitted target. No claim about
1c/1d, worlds, capacity, replay or acceptance. Thread-safety not claimed or
tested. No automatic cancellation cause exists in this slice, as declared.

## Proposed stage-record entry (owner to append)

> ### Independent review of slice 1b — 2026-09-21
> Reviewer: Claude (`claude-fable-5-1`). Snapshot of the uncommitted tree on
> `b915aa0`; 212 kernel tests and both fixture claims reproduced; nine
> reviewer probes including a 300-tick lifecycle fuzz passed. Kernel verdict
> PASS on every 1b claim. Not ready to commit until the evidence-verifier
> manifest mismatch (3 errors) is resolved and the stale untracked
> `automation/orchestrator.py`/`tests/test_orchestrator.py` are removed.
> Mutation instrument to be updated for 1b. Stage 1 exit not claimed.

## Artifacts

`stage1b-review-20260921/` in the review workspace, hashed in
[artifact-sha256.json](artifact-sha256.json). Snapshots:
`work/stage1b-review-snapshot-20260921` (no `.git`) and
`work/stage1b-review-snapshot2-20260921` (with `.git`; stale files and the
verifier test moved to `_review_set_aside/` for the mutation run).
