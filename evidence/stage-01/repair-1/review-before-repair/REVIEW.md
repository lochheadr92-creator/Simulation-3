# Stage 1a adversarial review

**Date:** 2026-09-20. **Verdict: CHANGES REQUIRED.**

Reviewed revision: `fa8be6083b31ead3c7e6aae844c0fd749927e6d0`, branch
`codex/kernel-first-slice`, from `C:\dev\03-Living-World-V3`.

This review reproduced the committed suite and instruments in a disposable local
clone, then tested additional boundary cases. It changes no accepted project state
and does not claim the Stage 1 exit gate. No fixes were applied to the original.

## Findings

### R1 — P1: Reentrant ticks break settlement history and diagnostics inertness

Location: `kernel/engine.py:41–52`; the publication callback is invoked at line 60.

`Engine.tick()` captures its boundary before consuming the proposal iterable, and
has no guard against another tick starting before the first call returns. There
are two reproduced entry points, both using the public API without monkeypatching
kernel code or mutating private fields:

1. A proposal generator starts an inner tick claiming the sole source unit, then
   yields an outer claim. Both returned records report tick 0 and accepted credits
   of one unit. Their credited total is two, while final state contains one unit
   and advances only to tick 1: the outer commit overwrites the inner transition.
   This is duplicated acceptance and lost history, not a demonstrated final balance
   of two or a negative source balance.
2. A diagnostic sink holding an engine reference calls its public `tick()` once
   during publication. Without that sink, the outer empty tick ends at tick 1 with
   A holding two units. With it, the engine ends at tick 2 with A holding one unit.
   The returned outer record is identical, but its `next_state_digest` no longer
   matches the engine's state when the call returns.

Existing tests corrupt only the copied diagnostic payload. That validates payload
isolation, but not this callback/reentry boundary. Normal generators and hostile
payload-only sinks pass the independent controls.

**Required correction:** prevent a second tick from entering the same engine during
the entire transition, including proposal collection and publication; release the
guard reliably on failure. Add both regression cases. This does not require a new
scheduler, a world, or a sandbox for arbitrary Python code.

### R2 — P2: Rejected proposals can produce arrival-dependent canonical records

Location: `kernel/settlement.py:198–205`.

Two proposals from `GHOST_A` and `GHOST_B`, both outside the roster, share proposal
ID `duplicate`, sequence 0, and operation `consume`. Both are correctly denied as
duplicates. However, unknown actors all receive the same `unranked` sorting value,
and the outcome key omits actor identity. All remaining key components tie, so
Python's stable sort preserves their input order.

Reversing the collection leaves state identical but changes the record digest:

- `0975e95625be270496202c76287d35c5ece4c39abfd41afb823f31a75f06f733`
- `57aca93f71ab89d5d0acfb8b45c01a8717e8a1a602c01ae43fafc50bbe5e0852`

**Required correction:** provide deterministic ordering for distinct rejected
outcomes too. Preserve every duplicate's denial; do not collapse records or relax
the identity rule. Extend permutation checks to rejected, unknown-actor inputs.

### R3 — P2: The mutation harness can report detection when no test ran to failure

Location: `evidence/stage-01/instrument/mutation_check.py:228–249`.

The harness treats an ordinary mutant's nonzero process exit as detection without
requiring an executed failing test. An independent negative control supplied exit
2 with no failed test IDs, while baseline and restoration succeeded. The harness
returned 0 and printed that one mutation was detected by at least one test, despite
printing `noticed 0 test(s)` immediately above.

**Required correction:** distinguish a test's detection from runner, collection,
interruption, or environment failure. Such failures cannot be counted as a kill;
classify them UNKNOWN and retain the raw output. Include this negative control.

This flaw does **not** invalidate the 14 kills reproduced in this review: their
raw outputs were separately checked, each had exit 1 and identified failing tests.
The independent classifier also rejects exits 2 and 5 without failed test nodes.
It is preserved in `verify_evidence.py`; the original harness is unchanged.

### R4 — P2: Accepted unbounded quantities can make an otherwise empty tick fail

Locations: `kernel/units.py:24`, `kernel/canonical.py:45`, and the record's numeric
declaration that balances have no upper bound.

Genesis accepts `10 ** 5000` as a valid balance. An empty tick then raises Python's
integer-to-decimal conversion `ValueError` while computing the prior-state digest:
the active conversion limit is 4,300 digits. The engine remains at tick 0, so this
is an accepted-state/serialization mismatch, not a partial commit. A smaller large
integer control passes.

**Required correction:** align the accepted numeric domain with canonical encoding.
Either make the declared domain serializable or explicitly reconcile the numeric
contract and validation. Do not silently rely on a process-global setting. This is
an extreme-input defect, not evidence that ordinary food quantities are affected.

### R5 — P2: Proposal-sequence ownership differs from the adopted specification

Locations: `ROADMAP.md:99–102`, `kernel/proposals.py:46–49`, and the stage record's
proposal-sequence declaration.

The roadmap requires an engine-assigned actor-local sequence. The implementation
accepts caller-selected sequences and validates uniqueness; the tests explicitly
allow arbitrary gaps. The stage record documents this choice but cannot amend the
roadmap. This is a source-confirmed specification deviation, not an additional
reproduced overdraw case.

**Required resolution:** establish the intended ownership explicitly and align the
code and governing contract before depending on it in the lifecycle slice. Do not
claim engine-owned identities or authenticated proposal provenance from uniqueness
checks alone.

## Fresh execution results

| Check | Result in this review |
|---|---|
| Committed suite, unchanged | 107 passed |
| Declared fixture digests | Match committed output exactly after newline normalization |
| Fixture execution under hash seeds 0 and 17 | Identical output |
| Original mutation script | 14 detected; conservation-rail mutation survives and is excluded by declaration |
| Independent inspection of the 14 mutant runs | Exit 1 and named failing test bodies in every case |
| Independent adversarial suite | 5 failed, 6 passed; same observations reproduced under hash seed 17 |
| Additional ordinary contention matrix | 2,592 fixtures, each in both proposal orders: availability, nonnegative stock, conservation and record ordering pass |
| Kernel restoration after mutation | Byte-identical to the review's initial snapshot; no kernel CRLF bytes |
| Original repository after review | Same HEAD, clean working tree, every tracked file byte-identical to its initial snapshot |

The five failing assertions cover four executable defects: R1 has two reproductions.
R5 is established by reading the specification and implementation, not by a failing
runtime assertion. The small-state matrix is focused engineering coverage; it is
not a living-world run, capacity benchmark, or statistical confidence estimate.

The negative-balance mutation's tests fail because the later state constructors
still reject the negative values with `ValueError` rather than the expected
`IntegrityError`. Thus that kill proves the tests distinguish the rail/exception
path; it does not show that removing that one rail would allow negative state to
commit. The conservation assertion remains in the source as defence in depth.

## Requirement disposition

- Ordinary contested allocation, all-or-nothing settlement, next-tick credit
  availability, and the tested authority checks reproduce successfully.
- Full proposal-order independence fails on R2.
- Inert diagnostic capture fails on R1 when the callback reenters the public API.
- Repeated ordinary execution and frozen-object/payload controls pass the tested
  cases. They do not establish all observer isolation or transaction-history claims.
- No blanket closure of old F01/F03/F06 findings follows from this slice. In
  particular, ordinary gather accounting passes these fixtures while reentry can
  still duplicate accepted credits in history.
- The 50-actor target, numerical cost ceilings and rotating contention policy are
  already adopted. They are not missing owner decisions or placeholder rules.
- Sketching the native decision-record schema before reservations depend on its
  shape is sensible preparation for the next authorised slice. No such code or
  schema change was made here.

**Recommendation:** correct R1–R4 and reconcile R5 before accepting full Stage 1a
conformance or building reservations on its guarantees. Keep the existing passing
tests and preserved failures. Stage 1 remains incomplete; this is not its exit review.

## Reproduction and evidence

Review workspace: this directory. Reviewed clone: `checkout/` at the pinned commit.
Commands and interpreter paths are recorded verbatim in `reproduction.json` and
`adversarial-run.json`. The latter records the actual pytest exit code 1.

- `suite.txt`: baseline output.
- `fixture-digests-seed0.txt` and `fixture-digests-seed17.txt`: native fixture output.
- `mutation.txt` and `checkout/evidence/stage-01/instrument/runs/`: fresh mutation
  summaries and raw per-run results. `committed-evidence.zip` preserves the original
  committed evidence separately.
- `test_adversarial.py`: additional assertions and passing controls.
- `adversarial-pytest.txt`, `adversarial-confirmation.txt`, and
  `adversarial-observations.json`: failures and exact observed state/record values.
- `verification.json`: independent result classification and source preservation.
- `original-manifest-before.json` and `copy-manifest-before.json`: file hashes.

Environment: Windows, CPython 3.12.14, pytest 9.1.1. The original record reports
CPython 3.12.10, so this is a same-minor-version reproduction, not an identical
interpreter build. The named `py` launcher was unavailable; an existing Python
environment was reused read-only with bytecode writing disabled. No packages were
installed and no old-project simulation or oracle was run.

Two reviewer preflight assertions were repaired before their results were relied
on: raw clone equality was narrowed only after proving differences were CRLF/LF
in saved outputs and one test file, with kernel bytes identical; and mutant-result
inspection was corrected to include executed tests failing with the wrong exception,
not only literal `AssertionError` text. Controls then passed. These did not change
the kernel, original tests, original harness, or baselines.

This is an independently executed reviewer task. The builder's exact model is not
recorded in the supplied artifacts, so this report does not certify the separate
different-model requirement for a future Stage 1 exit.

## Changes and rollback

All new scripts, logs, this report and the disposable clone are contained in this
review directory. The original new-engine repository and the old simulation's
source and evidence were not edited. The mutation script temporarily changed only
the clone's kernel files and restored them byte for byte; its fresh result logs
remain in the clone. No fixes, commits, pushes, merges or pin changes were made.

There is no engine rollback to perform. To remove only this review, archive its
directory first, then remove that exact directory if explicitly requested. Do not
use the original report's repository-deletion suggestion as a routine rollback.
If the slice is later withdrawn, retain its evidence and mark it withdrawn.
