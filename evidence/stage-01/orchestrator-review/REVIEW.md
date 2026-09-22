# Orchestrator Phases 1-3 verification and safety review

Date: 2026-09-20. Authority: AGENTS.md OD-005.
Base: `b915aa0c179d4e19c954f8b05eb107c4cd34d475`.
Branch: `codex/orchestrator-phases-1-3-freeze`.
Reviewer: Codex, in-session code review and direct test execution. This is not
an independent different-model scientific review or a Stage 1a acceptance.

## Scope and isolation

The original `C:/dev/03-Living-World-V3` checkout had advanced to uncommitted
Phase 4 execution code between the earlier status check and this instruction.
Its orchestrator, tests, local audit, and receipts were preserved without edits.
This worktree starts from the frozen automation foundation. Read-only source
and tests were extracted from a captured copy of the newer files; execution,
locking, and audit-writing functions and Phase 4 tests were excluded here.
Bare `--run` refusal was restored and tested before preflight can start.
The original checkout was neither reset nor committed by this task.

This commit adds only the read-only orchestrator and tests, its package
description, the owner-direction entry, and this tooling record, with a narrow
Git attributes rule preserving the verification outputs' byte identities. It does not
change the existing preflight, runner, evidence verifier, registry, kernel,
doctrine, roadmap, SIM3_STATE, historical evidence, or evidence contracts.

## Findings and corrections

| Finding | Demonstration | Correction |
|---|---|---|
| Alternate inspection root selected executable preflight code | A temporary root's replacement preflight wrote a marker | Always invoke the preflight adjacent to this orchestrator, using isolated Python and UTF-8; `--root` selects inspection data only |
| Falsey unsafe metadata and non-boolean acceptance values were permissive | Empty string/object, zero, null or false unsafe values; null/zero/string-false acceptance | Require a list for unsafe metadata and explicit boolean false for acceptance; unknown values are ineligible |
| Malformed registry data crashed or resolved ambiguously | Non-object JSON, invalid UTF-8, duplicate IDs, non-string/path/shell IDs, malformed argv/timeouts/checks | Reject ambiguous IDs/JSON keys and invalid shapes; validate execution metadata without executing it |
| Preflight PASS masked authority/integrity problems | Reported milestone/acceptance/manifest contradictions and UNKNOWN milestone still resolved | Shared resolver blocks unknown identity/milestone and substantive preflight inconsistencies; only the two named historical wording notes remain informational |
| Receipts could crash inspection or fail to block future execution | Empty/invalid/multiline STATUS; IN_PROGRESS plus `--allow-dirty` | Report malformed receipts without changing them; unresolved receipts block future execution even with a dirty-tree override |
| Windows output depended on parent encoding | UTF-8 decoding failed when the parent requested cp1252 | Explicit UTF-8 CLI output and pinned preflight output |
| Tests relied on development dirt and included a vacuous assertion | Dirty-tree case used the actual checkout; an acceptance assertion ended in `or True` | Test clean/dirty temporary repositories and assert actual unchanged acceptance output |

The baseline read-only extraction passed 37 focused tests. The first expanded
regression run recorded 44 failures and 40 passes. Five of those failures were
a test guard's incorrect subprocess argument index, corrected before retesting;
they are not product defects. The other failures reproduced the cases above.
An initial preparation run also had a dry-run extraction error and a missing
temporary parent directory, both corrected before the 37-test baseline.
After the product repairs, one prior error-message assertion failed; its
existing CLI message was restored. No invariant assertion was weakened.
Raw regression output is preserved alongside this record.

## Boundary review

- The orchestrator has one subprocess call: its pinned read-only preflight.
  All inspection modes are guarded in-process to prove that call boundary.
- `--status`, `--explain`, and `--next` never dispatch a registered gate.
- `--dry-run --run ID` uses the same action classifier as `--next` and resolves
  only `python -B automation/run_gate.py --gate ID`, plus an explicit
  `--allow-dirty` when requested. The resolved operation is never invoked.
- Bare `--run`, ambiguous mode combinations, arbitrary extra arguments,
  unsupported overrides, and abbreviated options refuse before inspection.
- Dirty-tree permission does not bypass unsafe metadata, authority conflicts,
  malformed registry entries, or unresolved receipt conditions.
- Local receipts have no scientific authority. COMPLETE cannot accept a gate,
  clear independent review, or authorise Slice 1b. No kernel module is imported.
- No lock, audit write, receipt creation, registry update, or Git mutation is
  reachable through the orchestrator. Existing runner tests exercise synthetic
  commands in disposable repositories, not the project registry's real gates.

## Verification

The focused suite passes **97 tests**, including a run with `PYTHONUTF8=0` and
`PYTHONIOENCODING=cp1252`. The full suite passes **283 tests**. Preflight passes
with all 9 manifest-subset files matching; the evidence verifier reports OK for
2 historical packets with 0 errors. Every inspection/dry-run command returns
its expected status; bare, unsafe, and unknown run requests refuse with exit 2.
Repository file bytes, Git status, and receipt paths/bytes are unchanged across
the complete stack. Exact argv, source hashes, and comparisons are recorded in
`verification.json` and accompanying output files. **PHASES 1-3 PASS**, limited
to the tooling scope and boundary conditions described here.

The source hashes describe the as-tested working files. The repository's existing
`text=auto eol=lf` rule normalizes Python source line endings in Git; staged source
content is checked against the tested files with only CRLF-to-LF normalization.
Raw verification artifacts retain their exact bytes and are checked against the
staged blobs. Whitespace lint applies to source and authored documentation, not
to those preserved terminal captures.

Reproduction from this branch with a Python interpreter containing pytest:

```text
python -B automation/preflight.py
python -B automation/verify_evidence.py
python -B -m pytest -q -p no:cacheprovider --tb=short --basetemp=<fresh-temp-directory>
python -B automation/orchestrator.py --status
python -B automation/orchestrator.py --explain
python -B automation/orchestrator.py --next
python -B automation/orchestrator.py --dry-run --run stage-01a-reference-suite
python -B automation/orchestrator.py --dry-run --run stage-01a-fixture-digests
python -B automation/orchestrator.py --dry-run --run stage-01a-fixture-digests --allow-dirty
python -B automation/orchestrator.py --run stage-01a-fixture-digests
```

The last command must return 2 without inspection or execution. The frozen
preflight/verifier test harness expects UTF-8 subprocess output, so use
`PYTHONUTF8=1` for the full suite. The orchestrator itself is separately tested
without that setting. Python's `py` launcher is absent in this Codex shell;
verification records the actual existing interpreter used.

## Limits and rollback

Phase 4 execution, locking, audit writes, interruption recovery, and execution
time identity revalidation are not implemented by this freeze. A dry-run exit
code of zero means resolution completed; read `future_execution_blocked` and
`currently_executable` separately. All commands remain currently non-executable.
The historical phase labels in status (1), next (2), and dry-run (3) identify
their interfaces; they do not claim execution capability.

Authority detection consumes the existing preflight's explicit reports. This
does not establish a general semantic authority interpreter or trust arbitrary
modifications to the orchestrator's own trusted installation. Future execution
requires a separate contract and renewed validation at dispatch time.

To withdraw the freeze, revert this commit on its isolated branch after checking
for later work. Its change list is the rollback boundary. Preserve this evidence
and OD-005 as history if incorporating any later rollback into another branch.
Do not reset the original checkout or delete its Phase 4 work or local receipts.
Stage 1a independent review remains pending; no scientific acceptance is claimed.
