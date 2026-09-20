# Verified orchestrator publication — 2026-09-21

Authority: AGENTS.md OD-007, the owner's instruction "Commit and push".
This publication contains the verified Phase 1–4 automation, both Phase 4
repairs, focused regressions and their verification records. It changes no
kernel behaviour, registry command or scientific acceptance state.

## Source and publication identity

The source is the actual uncommitted tree from
`work/orchestrator-phase4-repair2`, based on local commit
`6591629029ac5cfedbb16279e2c62888894fb44b`. Every tested Python file was checked
against the [as-tested manifest](prior-tests/final-source.json) before copying.
The source checkout, earlier repair, baseline, both failed pilots, successful
pilot and all historical evidence remain preserved.

GitHub's existing `codex/kernel-first-slice` branch ends at
`53f42de1229401db1eeca2ca52390c3356c2a30f`. The intervening local Phase 1–3
automation commits `b915aa0c179d4e19c954f8b05eb107c4cd34d475` and
`6591629029ac5cfedbb16279e2c62888894fb44b` had not been published there.
This publication imports their final automation content and the completed
repairs as one new snapshot commit atop that remote parent. It does not rewrite
the existing remote history; the original local commits remain intact.

Publication is prepared in
`work/orchestrator-publication-20260921` and uses the connected GitHub API.
This task's filesystem permissions do not allow updating the checkout at
`C:/dev/03-Living-World-V3`; that local checkout therefore still needs a
separate, preservation-aware synchronisation after publication. Its original
uncommitted Phase 4 files must not be discarded by a blind pull or reset.

No generated `evidence/automation-runs/` package is committed. The existing
ignore rule remains in effect. The published test logs below are verification
outputs, not accepted scientific evidence.

## Verified behaviour and evidence

Repair 1 restores strict validation, pinned helpers, repository binding,
kernel-owned locks, Windows Job Object cleanup, actual-receipt verification and
append-only audit provenance. Repair 2 explicitly resolves recorded `py -3`
commands to the controller's native interpreter and distinguishes dispatch
attempted, command started and command outcome, including structured launch
errors. The [execution contract](../../../automation/ORCHESTRATOR_EXECUTION.md)
defines the supported boundary.

The final repair-2 evidence records:

- [191 focused tests passed](prior-tests/fourth.txt), with [JUnit](prior-tests/fourth.xml).
- [365 whole-tree tests passed](prior-tests/fifth.txt), with [JUnit](prior-tests/fifth.xml).
- One real `stage-01a-fixture-digests` pilot, run
  `b07c6bec612c44a091afa4e314c6b57b`, succeeded with verified evidence.
  Its original local receipt and audit remain under
  `work/orchestrator-phase4-pilot2-20260920/evidence/automation-runs/`.
  Its full report is preserved in `phase4-pilot2-20260920/REPORT.md`.

The [prior verification record](prior-tests/final-verification.json) describes
those tests and pilot. These are recorded earlier measurements. The source
Python bytes in this publication match that tested source; the new edits are
publication documentation and evidence packaging. Publication-time verification
is appended below after its run.

**Correction to the historical repair/pilot reports:** the fixture output
matches the repaired reference after CRLF/LF normalization. It is not literally
byte-identical: the pilot output is 2,816 bytes with 55 CRLF endings; the
reference is 2,761 bytes with LF endings. The content, outcomes and digest text
agree. Historical reports and receipts were not rewritten.

## Limits

The successful pilot demonstrates one bounded read-only fixture through the
controller. It ran in the RJLoc Windows user context; it does not establish the
cause of the earlier sandbox access-denied failures. No additional real project
gate is part of this publication sitting.

The native runtime used for that pilot did not have pytest installed. The
registered reference-suite gate resolves to that native interpreter and is
therefore not demonstrated runnable in that environment. The passing test
suite used the existing validation virtual environment, whose interpreter and
command are recorded in the logs/reports. No runtime dependency was installed.

Windows Job Objects cover ordinary inherited descendants, not work launched
through unrelated services or remote systems. Power loss, hostile local users
and large stress workloads remain outside the demonstrated result. Mechanical
success and evidence packaging do not establish scientific acceptance.

Stage 1a independent acceptance remains pending; Stage 1 is incomplete;
Slice 1b remains unauthorised. No merge or force push is authorised.

## Publication verification

The assembled publication checkout passed **365 tests**, zero failures, errors
or skips. [Raw output](publication-tests/publication-tests.txt),
[JUnit](publication-tests/publication-tests.xml),
[exact invocation](publication-tests/test-invocation.json), and
[duration/result](publication-tests/test-result.json) are retained. The run
used the existing validation virtual environment, disabled bytecode/cache
writes, and used a fresh disposable pytest directory. The tests use harmless
execution fixtures; no registered real project gate was invoked.

After testing, only this result entry and copies of its evidence were added.
All tested Python source bytes are still identical to the repair-2 manifest.
