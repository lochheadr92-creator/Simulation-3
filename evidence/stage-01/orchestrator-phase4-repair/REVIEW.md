# Phase 4 bounded repair and verification

**Repair verification: PASS. Candidate readiness: READY FOR A CONTROLLED PILOT using the tested Windows runtime. No pilot has been run.**

This verdict applies only to the isolated repair candidate identified below. The original C:/dev/03-Living-World-V3 checkout is preserved and still contains its earlier uncommitted Phase 4 files. The original review and its NEEDS FIXES verdict remain historical evidence.

Authority: AGENTS.md OD-006, recording the owner's “Fix issues” instruction following findings F1–F9. This is tooling repair and self-verification, not independent scientific acceptance. Stage 1a acceptance remains pending; Slice 1b remains unauthorised.

## Identities and isolation

| Source | Identity |
|---|---|
| Original Phase 4 | C:/dev/03-Living-World-V3; branch codex/kernel-first-slice; HEAD b915aa0c179d4e19c954f8b05eb107c4cd34d475 |
| Reviewed original orchestrator SHA-256 | 947954d0f91908797108895c0f70efbad641ac338365485090c7085135abe111 |
| Frozen baseline | Branch codex/orchestrator-phases-1-3-freeze; commit 6591629029ac5cfedbb16279e2c62888894fb44b |
| Repair checkout | C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair |
| Repair branch / HEAD | codex/orchestrator-phase4-repair / 6591629029ac5cfedbb16279e2c62888894fb44b, with uncommitted repairs |
| Final orchestrator SHA-256 | fc9439386ed7908e905863d970d18bdcb6b2dae29351e8dd901a06bf4ece82d3 |

The repair clone uses copied Git objects (--no-hardlinks). Neither original checkout was edited. The final code and tests match the [as-tested source manifest](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/ninth-source.json) and its adjacent source snapshot. This review and the appended stage-record entry were written after testing; they do not change the tested Python files.

The [prior review](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-review/REVIEW.md), its failing results and the frozen baseline remain preserved. [Final verification](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/final-verification.json) records source hashes, original-checkout preservation, Git identities and test counts. [Repair patch against the frozen baseline](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/repair-against-baseline.patch).

## Repairs against the findings

| Finding | Implemented repair | Demonstration |
|---|---|---|
| F1: root-selected executable code | Restored pinned preflight; the public controller uses an absolute pinned worker, runner and verifier under isolated Python. --root selects data. | Harmless replacement preflight/runner scripts in a disposable Git clone did not execute; the real pinned worker completed the harmless registered command. |
| F2: registry and authority regressions | Retained the baseline's strict IDs, duplicate-key/ID rejection, type validation and authority/integrity blockers; malformed entries elsewhere also block selection. | Baseline regressions and execution-boundary refusal tests passed. |
| F3: unresolved receipts | Empty, malformed, active, interrupted and incomplete receipts block execution; history is preserved. | Refusal tests assert unchanged receipt bytes. Corrupt historical completion records also prevent dispatch. |
| F4: stale-lock race and PID ownership | Replaced unlink/recreate and PID probing with a persistent kernel-locked file. Legacy lock JSON requires review and is never removed automatically. | Independent native Python processes could not overlap ownership; releasing an owned handle retained the same lock file. A legacy lock naming an unrelated owned test child neither signalled it nor changed the lock. |
| F5: timeout/interruption/cleanup | Native interpreter bootstrap waits for Job Object assignment before worker dispatch; kill-on-close contains ordinary descendants. Actual command/check output streams to files. | Delayed grandchildren were stopped on timeout and actual controller death; partial gate stdout remained; retry refused the unfinished receipt. KeyboardInterrupt was injected at the actual supervisor wait boundary. |
| F6: identity checks | Snapshot root/Git directory, branch, HEAD, index, source and registry bytes, native interpreter hash and trusted code hashes; recheck under ownership and at actual command boundaries. The worker reads a request once, verifies its separately passed digest and consumes the validated registry snapshot. | Registry changes during lock acquisition refused; dirty-file content changes invalidated success; postflight failure required review; rewriting the request to match an altered registry still did not dispatch. |
| F7: result/receipt provenance | Versioned response tied to request, UUID and gate; actual receipt JSON/status/file hashes plus independent verification determine evidence completeness. Overall result is separate from mechanical outcome. | Real harmless command exits 0, 1, 2, 3 and 7 were correctly classified; missing/corrupt/foreign receipts failed; command/check timeouts required review. |
| F8: audit accuracy | Serialized append-only audit; fsynced START precedes dispatch, TERMINAL precedes receipt finalisation; source and receipt hashes recorded. Failed/unknown starts are distinguished. | Start-write failure prevented dispatch; terminal-write failure left IN_PROGRESS and blocked retry; normal repeated runs preserved old lines and receipt bytes; malformed audit events refused. |
| F9: ambiguous CLI/tests | Restored exact mode parsing and disabled abbreviations. Dry-run describes the pinned worker plan. Tests observe the executing controller or actual child process, not only a parent mock. | Baseline inspection/no-spawn checks passed alongside child-process and CLI concurrency tests. |

Implementation references: [inspection and CLI](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/orchestrator.py:140), [execution boundary](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/orchestrator_execution.py:120), [receipt verification](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/orchestrator_execution.py:66), [worker](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/orchestrator_worker.py:19), [kernel locks and audit](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/controller_io.py:80), [owned process tree](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/owned_process.py:86), [streamed command output](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/run_gate.py:280).

The standalone runner's default interface remains available. Controller-only hooks bind its registry and receipt identity and recheck each command. No executable-path, arbitrary-command or registry override was added to the public orchestrator.

## Executed verification

**168 focused tests passed**, with zero failures, errors or skips in the final combined run. [Raw output](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/ninth.txt), [JUnit](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/ninth.xml).

The command was run from the repair checkout with PYTHONUTF8=1 and PYTHONDONTWRITEBYTECODE=1:

    C:/dev/02-Simulation-Sandbox/.worktrees/request-food-outstanding/sandbox/f01_validation_venv/Scripts/python.exe -B -m pytest tests/test_orchestrator.py tests/test_orchestrator_execution.py tests/test_orchestrator_audit.py tests/test_run_gate.py -q -p no:cacheprovider --tb=short --basetemp=../../repair-tmp/ninth --junitxml=../../phase4-repair-evidence/ninth.xml

Test interpreter: bundled Python 3.12.14. The controller supervises its native base interpreter at C:/Users/RJLoc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe. A dedicated test checks that this interpreter's reported PID equals the actual Popen process PID.

Actual execution tests used harmless commands and synthetic registries in disposable repositories. The full project/reference gate and real registered project gates were not run. Existing baseline/runner tests create small Git fixture commits inside their disposable test repositories; no implementation commit was made in the repair checkout or either original checkout.

Read-only preflight and historical evidence verification outputs are saved separately in the evidence folder. The final verification JSON records their exact results.

## Failed attempts retained and explained

All existing audit failures and repair-run outputs remain preserved. Repair attempts include:

- An initial output-directory preparation error, followed by nine fixture setup errors because the pytest temporary parent was absent. These were harness setup failures.
- The first supervisor implementation used Windows execv in its bootstrap, which let the bootstrap finish before the worker. It was replaced by an owned waiting parent.
- Normal process exit required a bounded job-accounting drain. Fixture commands also initially lacked their required recorded phrase in the disposable stage record; that fixture declaration was added, without relaxing the evidence verifier.
- Two Phase 3 CLI expectations were intentionally updated for authorised Phase 4 execution: ambiguous modes still refuse before inspection, while bare explicit --run is now supported. The old “execution not implemented” wording assertion now checks explicit execution and fresh-check wording. The frozen Phase 3 assertions remain in the baseline.
- A lock test tried to read a byte protected by Windows mandatory locking. It now checks file identity while locked and bytes after release. Subsequent testing exposed the Windows virtual-environment redirector PID problem; execution and the crash/lock tests now use the native interpreter. Earlier wrapper-only results are not relied on as proof of actual process termination.
- One test-module import used the wrong package path and failed collection; the import was corrected.

[First collected attempt](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/first.txt), [second](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/second.txt), [third](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/third.txt), [fourth](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/fourth.txt), [fifth](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/fifth.txt), [sixth](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/sixth.txt), [seventh](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/seventh.txt), [eighth](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/phase4-repair-evidence/eighth.txt). Source snapshots accompany attempts seven, eight and nine. No assertion of conservation, authority, receipt integrity, no-overlap or process cleanup was weakened to obtain a pass.

## Boundaries and next action

The [execution contract](C:/Users/RJLoc/Documents/Codex/2026-09-20/how-the-orchestrator-looking/work/orchestrator-phase4-repair/automation/ORCHESTRATOR_EXECUTION.md) specifies recovery, ownership and result semantics. A real pilot still requires a separate instruction. Apply/review this candidate as a coherent change before using it; the original checkout has not been patched.

Supported execution is Windows Job Objects on the tested native runtime. Unsupported platforms refuse. The user's separate installed Python runtime was not retested. No manual interactive Ctrl+C session, power-loss experiment, hostile local-user containment or large-scale stress campaign is claimed. The tests cover injected KeyboardInterrupt, actual controller process death and bounded concurrent requests.

OS jobs contain ordinary inherited descendants, not work launched through unrelated services, remote systems or WMI. This follows [Microsoft's Job Object behavior](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects). The contract excludes such commands. Snapshot checks detect changes and coordinate cooperating controllers; they do not freeze the filesystem against a hostile owner.

Legacy locks and unresolved receipts intentionally remain blockers. No automatic recovery/cleanup or scientific acceptance path was introduced. Historical evidence completeness remains distinct from a newly verified package.

Rollback is to leave this uncommitted repair checkout unused; neither original needs rollback. The patch and source manifest identify the bounded change set. Preserve this review and all failed evidence if later revising or withdrawing the candidate.

