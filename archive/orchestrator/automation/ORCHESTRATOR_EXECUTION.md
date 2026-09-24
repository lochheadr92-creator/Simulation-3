# Phase 4 execution contract

This tooling contract does not authorise a project run or scientific acceptance.
Inspection and dry-run remain read-only. Execution requires exactly one explicit
registry ID and separate dirty-tree permission when needed. Registry values are
data, not permission to change scope or claim acceptance.

## Trust and identity

Preflight, the controller worker, runner, verifier and bootstrap come from the
controller installation. --root selects repository data, never helper scripts.
The child uses the native interpreter beneath any virtual-environment redirector,
isolated Python and explicit UTF-8. The bootstrap additionally disables site
initialisation before job assignment. The public controller has no
command, interpreter, registry-path or runner-path override.

Strict registry validation and the baseline authority/receipt checks apply before
execution. Whole-registry ambiguity or malformed metadata blocks dispatch.
The controller records exact root, Git directory, branch, HEAD, index entries,
tracked/unignored file hashes, registry bytes and trusted Python source hashes.
It rechecks after acquiring ownership, immediately before dispatch, in the worker
and before each actual registered command or required check. The runner consumes
the validated registry snapshot. The request is read once and checked against a
digest passed separately by the parent. Postflight failure or changed identity prevents
an overall SUCCESS even if the command itself returned zero.

## Registered command runtime

A registry entry's `recorded_command` and `argv` are provenance and are never
rewritten. The runner applies one explicit policy (`automation/runtime_policy.py`):
an argv beginning exactly `py -3` resolves to the controller's own native base
interpreter, the same file whose path and SHA-256 the identity snapshot records;
no PATH search, launcher shim or installed software is involved. Any other `py`
launcher form is refused before dispatch. An argv that does not start with `py`
runs verbatim. There is no command, interpreter or executable-path input on the
public controller or in a request; the binding is derived from the validated
registry bytes and the running interpreter alone.

The dry-run shows the resolution. The controller records it in the request; the
worker recomputes it from the registry snapshot and the identity snapshot and
refuses on any difference; the runner rechecks the interpreter hash and resolved
argv immediately before each actual command or required check. Receipts keep the
registry argv, the resolved argv, the interpreter path and hash
(`command/argv.json`, `run.json`), and the controller report and audit records
carry the same binding.

These checks coordinate cooperative controllers and detect external edits; they
are not a filesystem snapshot or security sandbox against a hostile local owner.
Installed Python, Git, standard libraries, OS, and the controller installation
remain trusted. Registry commands must themselves be authorised and reviewed.

## Ownership and recovery

The persistent orchestrator.guard file is protected by a kernel file lock. It is
never unlinked or reclaimed based on a PID. A process holds only its own handle;
closing that handle releases its lease. A separate kernel lock serialises audit
appends. An existing legacy orchestrator.lock.json is preserved and refused for
review, regardless of recorded PID. No liveness call signals any process.

Each attempt has a unique _orchestrator/<UUID> receipt. IN_PROGRESS, INTERRUPTED,
EVIDENCE_INCOMPLETE, malformed receipts or unmatched audit starts prevent a new
run. There is no automatic retry, stale-lock removal or receipt-clearing option.
A future recovery action needs an explicit reviewed disposition preserving the
old attempt. Mixed old/new controllers against one root are not supported.

## Process lifetime

Actual dispatch currently supports Windows Job Objects. Other platforms refuse
execution. A pinned bootstrap waits for controller input until it has been
assigned to a private kill-on-close job with breakaway disabled. All ordinary
CreateProcess descendants inherit the job. Timeout, interruption and controller
death terminate that owned tree. No unrelated PID is selected for termination.

Worker output and each actual command/check stream directly to preserved files,
including before an outer timeout or controller crash. Ownership remains held while the job is
terminated and drained. Unexpected surviving descendants invalidate the result.
Cleanup uncertainty leaves a blocking receipt. The job controls ordinary process
descendants; it does not contain arbitrary services, remote jobs or WMI-launched
work. Such commands are outside this controlled-execution contract.

The job behavior follows [Microsoft's Job Object contract](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

## Result and evidence

The worker supplies a versioned response bound to the request hash, controller
UUID, registry ID and a new receipt directory. The controller compares it with the
actual run.json, STATUS and complete file-hash inventory, then independently runs
the existing evidence verifier before reporting new evidence COMPLETE. Integer
process exit codes are transport information, not evidence of refusal or
interruption: failed command codes 2 and 3 remain mechanical FAILURE.

overall_result controls the CLI exit (SUCCESS=0, FAILURE=1, REFUSED=2,
INTERRUPTED=3). mechanical_execution reports the observed command outcome;
evidence and review_required remain separate. No receipt or outcome accepts
Stage 1a, supplies independent scientific review, or authorises Slice 1b.

Historical packages are retained and checked for readable, consistent records
and required artifacts. Controller-issued package hashes are checked against the
append-only audit seal on subsequent runs. Their original revision remains historical; an old
current-head contract is not silently rewritten to match a new HEAD. Historical
inspection alone does not make a fresh evidence-complete claim.

## Audit and failure finalisation

An fsynced START record containing source identity is required before worker
dispatch. A TERMINAL record includes actual start status, outcome and receipt
hashes; it is appended while execution ownership is held. Only then is the
controller receipt marked terminal. Records are appended under a separate lock,
never rewritten. Incomplete or malformed historical audit lines block execution.

Three startup facts are kept apart: `dispatch_attempted` (the worker reached the
launch boundary after its fresh checks), `command_started` (process creation
returned a process; `gate_dispatched` means exactly this), and the command
outcome (exit code, timeout, mutations). Failed process creation is recorded as
`command_started=false` with a structured `launch_error` (type, errno,
winerror, strerror, filename, message), a null exit code and mechanical
FAILURE; it is never reported as a started command. The runner result, worker
response, controller report, receipt (`command/launch.json`, `run.json`) and
audit TERMINAL record must agree, or the attempt requires review. If final audit persistence
fails, the caller receives failure and the attempt remains IN_PROGRESS, blocking
retry. Its saved report describes the observed outcome before finalisation;
STATUS plus the audit terminal record determine whether finalisation completed.
Power-loss durability depends on the filesystem; no power-loss guarantee is
claimed beyond explicit file flush/fsync and refusal on incomplete records.
