# Phase 4 repair 2 — explicit runtime and startup provenance

**Repair verification: PASS (191 focused, 365 whole-tree, zero failures).
Controlled pilot: one `stage-01a-fixture-digests` request through the
orchestrator returned SUCCESS with evidence COMPLETE.** Tooling result only:
Stage 1a acceptance remains pending; Slice 1b remains unauthorised; no commit,
merge or push occurred.

Authority: the owner's 2026-09-20 instruction to fix the two issues exposed by
the Phase 4 pilot (P1 runtime blocker, P2 execution-provenance gap), verify, and
conditionally run one controlled pilot. This is self-verification of tooling,
not independent scientific review.

## Identity

| Item | Identity |
|---|---|
| Base | `work/orchestrator-phase4-repair` candidate: branch `codex/orchestrator-phase4-repair`, HEAD `6591629029ac5cfedbb16279e2c62888894fb44b`, uncommitted repairs verified against the 168-test evidence before copying |
| This checkout | `work/orchestrator-phase4-repair2`: full copy including `.git` and the uncommitted repairs; same HEAD/branch/index |
| Changed against the candidate | `automation/run_gate.py`, `automation/orchestrator.py`, `automation/orchestrator_worker.py`, `automation/orchestrator_execution.py`, `automation/ORCHESTRATOR_EXECUTION.md`; new `automation/runtime_policy.py`, `tests/test_runtime_and_startup.py` |
| As-tested hashes and patch | `../../../../phase4-repair2-20260920/final-source.json`, `repair2-against-candidate.patch` |
| Trusted native Python | 3.12.14, SHA-256 `49c94f6b8326c4e5a1e2099f95a188a49be331ffa0bb7b7d179080f662daa6b5` |

Registry bytes, kernel, governing documents and the recorded commands are
unchanged. No launcher shim, PATH change, software installation or permission
bypass was made. The precise cause of the earlier `WinError 5` results is not
established; this sitting ran as a different Windows user with the `py`
launcher on PATH, and the repair removes the dependency on either.

## Repairs

1. **Explicit runtime policy** (`automation/runtime_policy.py`). Only a registered
   argv beginning exactly `py -3` resolves, to the controller's native base
   interpreter (`controller_io.python_executable()`), whose path and hash the
   identity snapshot already records. Other `py` forms refuse before dispatch;
   other argv run verbatim. The dry-run shows the resolution; the controller
   binds it into the request; the worker recomputes it from the registry
   snapshot and checks it against the identity snapshot; the runner rechecks the
   interpreter hash and resolved argv immediately before each `Popen`. Receipts
   keep `registry_argv`, resolved `argv`, interpreter path and hash.
2. **Startup provenance.** `dispatch_attempted`, `command_started` and the
   command outcome are separate facts in runner results, `command/launch.json`,
   `run.json`, the worker response, the controller report and the audit
   TERMINAL record. Failed process creation records `command_started=false`
   with a structured `launch_error` and a null exit code. `gate_dispatched` now
   means process creation. The controller refuses a response whose startup facts
   disagree with the receipt.

## Verification

Final focused run (`phase4-repair2-20260920/fourth.txt`): 191 passed. Whole
tree (`fifth.txt`): 365 passed. New tests dispatch through the real worker:
trusted-runtime success bound end to end; missing executable (WinError 2) and
directory-as-executable (WinError 5) recorded as not started with cleanup and
lock release; unsupported launcher forms refused before dispatch; altered
binding refused by the worker and by the runner; dry-run resolution; timeout
after start recorded as started; descendants of a trusted-runtime gate stopped
on outer timeout; standalone-runner failed start and interruption. Earlier
attempts (`first.txt` .. `third.txt`) are retained; none failed.

## Pilot

Disposable copy `work/orchestrator-phase4-pilot2-20260920`; run
`b07c6bec612c44a091afa4e314c6b57b`; controller exit 0 in 3.3 s; the fixture
ran on the native interpreter and its output is byte-identical to
`evidence/stage-01/repair-1/fixtures-repaired.txt` (engine 0.1.1-stage1a).
38 independent checks passed (`phase4-pilot2-20260920/verification.json`),
including a separate verifier process, audit seal, lock re-acquisition and
preservation of every earlier tree. Stopped after that single attempt.

Rollback is to leave this checkout unused; the candidate and both originals are
untouched.
