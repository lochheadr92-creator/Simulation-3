"""Safe runner for an explicitly selected recorded Stage 1a command (Phase 3).

Lifecycle: preflight → validate gate → capture before-state → run authorised
command → capture output → additional declared checks → capture after-state →
package evidence → verify evidence → report.

It does not invent milestone commands, does not commit, does not stash, does not
rewrite historical evidence, and does not declare a scientific milestone proven.

Run from the repository root:

    py -3 automation/run_gate.py --list
    py -3 automation/run_gate.py --gate stage-01a-fixture-digests
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from automation.preflight import (  # noqa: E402
    collect as preflight_collect,
    discover_root,
    display_root,
    render as preflight_render,
    sha256_file,
)
from automation.verify_evidence import (  # noqa: E402
    FORMAT as CONTRACT_FORMAT,
    render as verify_render,
    verify as verify_evidence,
)
from automation.controller_io import SafetyError  # noqa: E402
from automation.runtime_policy import bind_gate_runtime, recheck_runtime  # noqa: E402

REGISTRY_REL = Path("automation") / "gate_registry.json"
RUNS_REL = Path("evidence") / "automation-runs"
REGISTRY_FORMAT = "v3.gate.registry.1"
PROTECTED_PREFIXES = (
    "kernel/",
    "evidence/stage-01/",
    "AGENTS.md",
    "DOCTRINE.md",
    "ROADMAP.md",
    "automation/gate_registry.json",
    "automation/evidence_contracts/",
)
UNPROVEN = "no"
EXIT_OK = 0
EXIT_EXECUTION_FAILURE = 1
EXIT_REFUSED = 2
EXIT_INCOMPLETE = 3


class RunGateError(Exception):
    """Refused before the authorised command started."""


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") or text == "" else text + "\n", encoding="utf-8")


def posix(path: str) -> str:
    return path.replace("\\", "/")


def is_protected(rel: str) -> bool:
    rel = posix(rel)
    for prefix in PROTECTED_PREFIXES:
        if prefix.endswith("/"):
            if rel.startswith(prefix) or rel == prefix[:-1]:
                return True
        elif rel == prefix:
            return True
    return False


def kernel_hashes(root: Path) -> dict[str, str]:
    kernel = root / "kernel"
    if not kernel.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(kernel.glob("*.py")):
        out[f"kernel/{path.name}"] = sha256_file(path)
    return out


def load_registry(root: Path, registry_path: Path | None) -> dict[str, Any]:
    path = registry_path if registry_path is not None else root / REGISTRY_REL
    if not path.is_file():
        raise RunGateError(f"error: gate registry not found: {path.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunGateError(f"error: malformed gate registry: {exc}") from exc
    if data.get("format") != REGISTRY_FORMAT:
        raise RunGateError(f"error: gate registry format must be {REGISTRY_FORMAT}")
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise RunGateError("error: gate registry has no gates")
    seen: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict) or not gate.get("id"):
            raise RunGateError("error: gate registry entry missing id")
        if gate["id"] in seen:
            raise RunGateError(f"error: duplicate gate id {gate['id']}")
        if gate.get("acceptance_claimed") is True:
            raise RunGateError(
                f"error: gate {gate['id']} claims acceptance; the registry cannot accept a milestone"
            )
        seen.add(str(gate["id"]))
    return data


def get_gate(registry: dict[str, Any], gate_id: str) -> dict[str, Any]:
    for gate in registry["gates"]:
        if gate["id"] == gate_id:
            return gate
    known = ", ".join(sorted(g["id"] for g in registry["gates"]))
    raise RunGateError(f"error: unknown gate {gate_id!r}; known: {known}")


def dirty_names(preflight: dict[str, Any]) -> list[str]:
    names = list(preflight.get("dirty_files") or []) + list(preflight.get("untracked_files") or [])
    return [posix(name) for name in names]


def allocate_run_dir(root: Path, gate_id: str, head: str, controller_run_id: str | None = None) -> Path:
    base = root / RUNS_REL / gate_id
    if controller_run_id is not None:
        if not re.fullmatch('[0-9a-f]{32}', controller_run_id):
            raise RunGateError('error: invalid controller run identity')
        path = base / controller_run_id
        path.mkdir(parents=True, exist_ok=False)
        return path
    prefix = (head if head and head != "UNKNOWN" else "unknown")[:12]
    seq = 1
    while True:
        path = base / f"{prefix}-{seq:03d}"
        if not path.exists():
            path.mkdir(parents=True, exist_ok=False)
            return path
        seq += 1
        if seq > 999:
            raise RunGateError("error: run directory sequence exhausted")


def set_status(run_dir: Path, status: str) -> None:
    write_text(run_dir / "STATUS", status)


def capture_git_state(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "branch": preflight.get("branch", "UNKNOWN"),
        "head": preflight.get("head", "UNKNOWN"),
        "dirty_files": list(preflight.get("dirty_files") or []),
        "untracked_files": list(preflight.get("untracked_files") or []),
        "git_status": list(preflight.get("git_status") or []),
    }


def unexpected_protected_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    run_dir: Path,
    root: Path,
) -> list[str]:
    before_names = set(map(posix, dirty_names(before)))
    after_names = set(map(posix, dirty_names(after)))
    run_rel = posix(run_dir.resolve().relative_to(root.resolve()).as_posix())
    added = sorted(after_names - before_names)
    flagged: list[str] = []
    for name in added:
        if name == run_rel or name.startswith(run_rel + "/"):
            continue
        if is_protected(name):
            flagged.append(name)
    before_hashes = before.get("kernel_hashes") or {}
    after_hashes = after.get("kernel_hashes") or {}
    if before_hashes != after_hashes:
        flagged.append("kernel/* hashes changed")
    return flagged


def build_run_contract(
    gate: dict[str, Any],
    head: str,
    run_rel: str,
    required_files: list[str],
) -> dict[str, Any]:
    return {
        "format": CONTRACT_FORMAT,
        "packet_id": f"run-{gate['id']}-{Path(run_rel).name}",
        "milestone": gate.get("milestone", "UNKNOWN"),
        "gate": gate.get("gate", "none"),
        "acceptance_claimed": False,
        "role": "current",
        "recorded_revision": head,
        "must_match_current_head": True,
        "stage_record": "evidence/stage-01/RECORD.md",
        "required_files": required_files,
        "receipts": {
            "test_suite": [f"{run_rel}/command/stdout.txt"],
            "determinism": [],
            "mutation": [],
            "replay": [],
        },
        "replay_required": False,
        "command_phrases": [phrase for phrase in [gate.get("recorded_command")] if phrase],
        "recorded_seeds": [],
        "recorded_horizons": [
            {
                "id": "whole_world_executions_authorised",
                "phrase": "Whole-world executions authorised: 0",
                "in": "evidence/stage-01/RECORD.md",
            }
        ],
    }


def launch_error_record(exc: OSError) -> dict[str, Any]:
    """Structured record of a failed process creation. Nothing was executed."""
    return {
        "type": type(exc).__name__,
        "errno": exc.errno,
        "winerror": getattr(exc, "winerror", None),
        "strerror": exc.strerror,
        "filename": None if exc.filename is None else str(exc.filename),
        "message": str(exc),
    }


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _decode(data: Any) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data or ""


def run_command(root: Path, argv: list[str], timeout_s: int, sink: dict[str, Any] | None = None) -> dict[str, Any]:
    """Standalone mode. Process creation is separated from command outcome:
    ``command_started`` is true only after ``Popen`` returned a process. A caller
    may pass ``sink`` so partial facts survive an interruption."""
    outcome: dict[str, Any] = sink if sink is not None else {}
    outcome.update({
        "argv": argv, "dispatch_attempted": True, "command_started": False, "pid": None,
        "launch_error": None, "exit_code": None, "timed_out": False, "stdout": "", "stderr": "",
    })
    try:
        proc = subprocess.Popen(
            argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=_command_env(), shell=False,
        )
    except OSError as exc:
        outcome["launch_error"] = launch_error_record(exc)
        outcome["stderr"] = f"error: failed to start command: {exc}\n"
        return outcome
    outcome["command_started"] = True
    outcome["pid"] = proc.pid
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        late_out, late_err = proc.communicate()
        outcome["timed_out"] = True
        outcome["stdout"] = _decode(exc.stdout) + _decode(late_out)
        outcome["stderr"] = _decode(exc.stderr) + _decode(late_err) + "\nerror: command timed out\n"
        return outcome
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    outcome["exit_code"] = proc.returncode
    outcome["stdout"] = _decode(stdout)
    outcome["stderr"] = _decode(stderr)
    return outcome


def run_streamed_command(root: Path, argv: list[str], timeout_s: int, directory: Path,
                         sink: dict[str, Any] | None = None) -> dict[str, Any]:
    """Controller mode preserves output even if the worker is forcibly stopped."""
    directory.mkdir(parents=True, exist_ok=True)
    outcome: dict[str, Any] = sink if sink is not None else {}
    outcome.update({
        'argv': argv, 'dispatch_attempted': True, 'command_started': False, 'pid': None,
        'launch_error': None, 'exit_code': None, 'timed_out': False,
    })
    error = ''
    with (directory / 'stdout.txt').open('xb') as stdout, (directory / 'stderr.txt').open('xb') as stderr:
        try:
            try:
                proc = subprocess.Popen(argv, cwd=root, stdout=stdout, stderr=stderr,
                                        env=_command_env(), shell=False)
            except OSError as exc:
                # Process creation failed: nothing ran. Record it structurally,
                # never as a dispatched command with a missing exit code.
                outcome['launch_error'] = launch_error_record(exc)
                error = f'error: failed to start command: {exc}\n'
            else:
                outcome['command_started'] = True
                outcome['pid'] = proc.pid
                try:
                    outcome['exit_code'] = proc.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    outcome['timed_out'] = True
                    error = '\nerror: command timed out\n'
                    proc.kill()
                    proc.wait()
                except BaseException:
                    # Interruption keeps subprocess.run's guarantee: the started
                    # child is killed before the exception propagates.
                    proc.kill()
                    proc.wait()
                    raise
        finally:
            if error:
                stderr.write(error.encode('utf-8'))
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())
    outcome['stdout'] = (directory / 'stdout.txt').read_text(encoding='utf-8', errors='replace')
    outcome['stderr'] = (directory / 'stderr.txt').read_text(encoding='utf-8', errors='replace')
    return outcome


def list_gates(root: Path, registry_path: Path | None) -> str:
    registry = load_registry(root, registry_path)
    lines = [
        "V3 gate registry",
        "================",
        "milestone_acceptance_inferred: no",
        "capability_proven: no",
        "reachability_proven: no",
        "measurement_proven: no",
        registry.get("note", ""),
    ]
    for gate in sorted(registry["gates"], key=lambda item: str(item["id"])):
        unsafe = ",".join(gate.get("unsafe") or []) or "(none)"
        lines.extend(
            [
                f"gate {gate['id']}",
                f"  milestone: {gate.get('milestone')}",
                f"  gate: {gate.get('gate')}",
                f"  acceptance_claimed: {gate.get('acceptance_claimed')}",
                f"  recorded_command: {gate.get('recorded_command')}",
                f"  source: {gate.get('source')}",
                f"  unsafe: {unsafe}",
            ]
        )
    return "\n".join(lines) + "\n"


def refuse(
    run_dir: Path | None,
    reason: str,
    preflight: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
    gate_id: str = "UNKNOWN",
    allow_dirty: bool = False,
) -> dict[str, Any]:
    head = "UNKNOWN" if preflight is None else str(preflight.get("head") or "UNKNOWN")
    branch = "UNKNOWN" if preflight is None else str(preflight.get("branch") or "UNKNOWN")
    run_rel = None
    if run_dir is not None and root is not None:
        run_rel = posix(run_dir.relative_to(root).as_posix())
    elif run_dir is not None:
        run_rel = posix(run_dir.as_posix())
    result = {
        "execution": "REFUSED",
        "evidence": "INCOMPLETE",
        "milestone_acceptance_inferred": UNPROVEN,
        "capability_proven": UNPROVEN,
        "reachability_proven": UNPROVEN,
        "measurement_proven": UNPROVEN,
        "reason": reason,
        "gate_id": gate_id,
        "run_dir": run_rel,
        "head": head,
        "branch": branch,
        "command_exit_code": None,
        "dispatch_attempted": False,
        "command_started": False,
        "launch_error": None,
        "allow_dirty": allow_dirty,
    }
    if run_dir is not None:
        set_status(run_dir, "REFUSED")
        dump_json(run_dir / "run.json", result)
        write_text(run_dir / "REPORT.txt", render_result(result))
        if preflight is not None:
            write_text(run_dir / "before" / "preflight.txt", preflight_render(preflight))
    return result


def render_result(result: dict[str, Any]) -> str:
    lines = [
        "V3 run_gate",
        "===========",
        f"execution: {result.get('execution')}",
        f"evidence: {result.get('evidence')}",
        f"milestone_acceptance_inferred: {result.get('milestone_acceptance_inferred', UNPROVEN)}",
        f"capability_proven: {result.get('capability_proven', UNPROVEN)}",
        f"reachability_proven: {result.get('reachability_proven', UNPROVEN)}",
        f"measurement_proven: {result.get('measurement_proven', UNPROVEN)}",
        f"gate_id: {result.get('gate_id', 'UNKNOWN')}",
        f"run_dir: {result.get('run_dir')}",
        f"head: {result.get('head', 'UNKNOWN')}",
        f"branch: {result.get('branch', 'UNKNOWN')}",
        f"command_exit_code: {result.get('command_exit_code')}",
        f"dispatch_attempted: {result.get('dispatch_attempted', False)}",
        f"command_started: {result.get('command_started', False)}",
        f"launch_error: {json.dumps(result.get('launch_error'), sort_keys=True)}",
        f"runtime_policy: {(result.get('runtime') or {}).get('command', {}).get('policy', '(none)')}",
        f"allow_dirty: {result.get('allow_dirty', False)}",
    ]
    if result.get("reason"):
        lines.append(f"reason: {result['reason']}")
    if result.get("unexpected_mutations"):
        lines.append("unexpected_mutations:")
        for item in result["unexpected_mutations"]:
            lines.append(f"  - {item}")
    lines.append(
        "note: execution success packages a recorded command; "
        "it does not accept a milestone or prove capability, reachability, or measurement"
    )
    return "\n".join(lines) + "\n"


def run(
    root: Path,
    gate_id: str,
    *,
    allow_dirty: bool = False,
    registry_path: Path | None = None,
    controller_run_id: str | None = None,
    before_command=None,
    registry_snapshot: dict[str, Any] | None = None,
    runtime_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    preflight = preflight_collect(root)
    # The controller worker supplies the registry bytes it hashed and validated.
    # Its callback rechecks identity before each command. Standalone behavior is
    # unchanged; there is no CLI option for a controller snapshot or callback.
    registry = registry_snapshot if registry_snapshot is not None else load_registry(root, registry_path)
    gate = get_gate(registry, gate_id)
    if gate.get("unsafe"):
        run_dir = allocate_run_dir(root, gate_id, str(preflight.get("head") or "unknown"), controller_run_id)
        set_status(run_dir, "IN_PROGRESS")
        return refuse(
            run_dir,
            (
                f"gate {gate_id} is registered as unsafe: "
                + ",".join(gate["unsafe"])
                + "; the runner will not execute it"
            ),
            preflight,
            root=root,
            gate_id=gate_id,
            allow_dirty=allow_dirty,
        )
    dirt = dirty_names(preflight)
    if dirt and not allow_dirty:
        run_dir = allocate_run_dir(root, gate_id, str(preflight.get("head") or "unknown"), controller_run_id)
        set_status(run_dir, "IN_PROGRESS")
        return refuse(
            run_dir,
            "dirty or untracked files make evidence ambiguous; pass --allow-dirty to record them and continue",
            preflight,
            root=root,
            gate_id=gate_id,
            allow_dirty=allow_dirty,
        )
    if preflight.get("blocking_failures"):
        run_dir = allocate_run_dir(root, gate_id, str(preflight.get("head") or "unknown"), controller_run_id)
        set_status(run_dir, "IN_PROGRESS")
        return refuse(
            run_dir,
            "preflight blocking failures: " + "; ".join(preflight["blocking_failures"]),
            preflight,
            root=root,
            gate_id=gate_id,
            allow_dirty=allow_dirty,
        )

    argv = gate.get("argv")
    if not isinstance(argv, list) or not all(isinstance(item, str) and item for item in argv):
        raise RunGateError(f"error: gate {gate_id} has invalid argv")
    # Explicit runtime policy: the registry argv stays as provenance; a `py -3`
    # prefix resolves to this runner's native base interpreter and nothing else.
    # The controller passes the binding it recorded in the request; any
    # difference refuses before a run directory exists.
    try:
        runtime = bind_gate_runtime(gate)
    except SafetyError as exc:
        raise RunGateError(f"error: gate {gate_id} refused by runtime policy: {exc}") from exc
    if runtime_binding is not None and runtime_binding != runtime:
        raise RunGateError(f"error: gate {gate_id} runtime binding differs from the controller request")
    timeout_s = int(gate.get("timeout_s") or 300)
    head = str(preflight.get("head") or "UNKNOWN")
    run_dir = allocate_run_dir(root, gate_id, head, controller_run_id)
    set_status(run_dir, "IN_PROGRESS")
    run_rel = posix(run_dir.relative_to(root).as_posix())

    before = capture_git_state(preflight)
    before["kernel_hashes"] = kernel_hashes(root)
    write_text(run_dir / "before" / "preflight.txt", preflight_render(preflight))
    dump_json(run_dir / "before" / "git.json", capture_git_state(preflight))
    dump_json(run_dir / "before" / "kernel-hashes.json", before["kernel_hashes"])
    write_text(run_dir / "before" / "head.txt", head)
    write_text(run_dir / "before" / "branch.txt", str(preflight.get("branch") or "UNKNOWN"))
    if dirt:
        write_text(run_dir / "before" / "dirty.txt", "\n".join(dirt))

    command: dict[str, Any] | None = None
    additional: list[dict[str, Any]] = []
    # Filled in place by the launcher so an interruption still records whether
    # dispatch was attempted and whether the process had actually been created.
    progress: dict[str, Any] = {"dispatch_attempted": False, "command_started": False,
                                "launch_error": None, "exit_code": None}

    def launch_record(outcome: dict[str, Any]) -> dict[str, Any]:
        return {
            "dispatch_attempted": outcome["dispatch_attempted"],
            "command_started": outcome["command_started"],
            "pid": outcome["pid"],
            "launch_error": outcome["launch_error"],
            "exit_code": outcome["exit_code"],
            "timed_out": outcome["timed_out"],
        }

    try:
        if before_command is not None:
            before_command()
        # Recheck the bound runtime immediately before the actual dispatch:
        # the interpreter file hash and resolved argv must still match.
        recheck_runtime(runtime["command"])
        resolved_argv = list(runtime["command"]["resolved_argv"])
        command = (run_streamed_command(root, resolved_argv, timeout_s, run_dir / 'command', progress)
                   if controller_run_id else run_command(root, resolved_argv, timeout_s, progress))
        write_text(run_dir / "command" / "stdout.txt", command["stdout"])
        write_text(run_dir / "command" / "stderr.txt", command["stderr"])
        dump_json(
            run_dir / "command" / "argv.json",
            {"argv": command["argv"], "registry_argv": list(argv),
             "runtime": runtime["command"], "timed_out": command["timed_out"]},
        )
        dump_json(run_dir / "command" / "launch.json", launch_record(command))
        write_text(
            run_dir / "command" / "exit_code.txt",
            "" if command["exit_code"] is None else str(command["exit_code"]),
        )
        for index, check_argv in enumerate(gate.get("required_checks") or []):
            if not isinstance(check_argv, list):
                continue
            if before_command is not None:
                before_command()
            check_runtime = runtime["checks"][index]
            recheck_runtime(check_runtime)
            check_resolved = list(check_runtime["resolved_argv"])
            extra = (run_streamed_command(root, check_resolved, timeout_s, run_dir / 'checks' / f'{index:02d}')
                     if controller_run_id else run_command(root, check_resolved, timeout_s))
            additional.append(extra)
            extra_dir = run_dir / "checks" / f"{index:02d}"
            write_text(extra_dir / "stdout.txt", extra["stdout"])
            write_text(extra_dir / "stderr.txt", extra["stderr"])
            dump_json(extra_dir / "argv.json", {"argv": extra["argv"], "registry_argv": list(check_argv),
                                               "runtime": check_runtime, "timed_out": extra["timed_out"]})
            dump_json(extra_dir / "launch.json", launch_record(extra))
            write_text(
                extra_dir / "exit_code.txt",
                "" if extra["exit_code"] is None else str(extra["exit_code"]),
            )
        after_preflight = preflight_collect(root)
        after = capture_git_state(after_preflight)
        after["kernel_hashes"] = kernel_hashes(root)
        dump_json(run_dir / "after" / "git.json", capture_git_state(after_preflight))
        dump_json(run_dir / "after" / "kernel-hashes.json", after["kernel_hashes"])
        mutations = unexpected_protected_changes(before, after, run_dir, root)
    except KeyboardInterrupt:
        set_status(run_dir, "INTERRUPTED")
        result = {
            "execution": "INTERRUPTED",
            "evidence": "INCOMPLETE",
            "milestone_acceptance_inferred": UNPROVEN,
            "capability_proven": UNPROVEN,
            "reachability_proven": UNPROVEN,
            "measurement_proven": UNPROVEN,
            "gate_id": gate_id,
            "run_dir": run_rel,
            "head": head,
            "branch": preflight.get("branch"),
            "command_exit_code": progress.get("exit_code"),
            "dispatch_attempted": bool(progress.get("dispatch_attempted")),
            "command_started": bool(progress.get("command_started")),
            "launch_error": progress.get("launch_error"),
            "runtime": runtime,
            "allow_dirty": allow_dirty,
            "reason": "interrupted",
        }
        dump_json(run_dir / "run.json", result)
        write_text(run_dir / "REPORT.txt", render_result(result))
        return result

    execution_success = (
        command is not None
        and command.get("command_started") is True
        and command.get("exit_code") == 0
        and not command.get("timed_out")
        and all(item.get("command_started") is True and item.get("exit_code") == 0
                and not item.get("timed_out") for item in additional)
    )
    packaged_files = [
        f"{run_rel}/STATUS",
        f"{run_rel}/before/preflight.txt",
        f"{run_rel}/before/git.json",
        f"{run_rel}/before/kernel-hashes.json",
        f"{run_rel}/before/head.txt",
        f"{run_rel}/command/stdout.txt",
        f"{run_rel}/command/stderr.txt",
        f"{run_rel}/command/exit_code.txt",
        f"{run_rel}/command/argv.json",
        f"{run_rel}/command/launch.json",
        f"{run_rel}/after/git.json",
        f"{run_rel}/after/kernel-hashes.json",
        f"{run_rel}/contract.json",
        f"{run_rel}/run.json",
        f"{run_rel}/REPORT.txt",
    ]
    result = {
        "execution": "SUCCESS" if execution_success else "FAILURE",
        "evidence": "INCOMPLETE",
        "milestone_acceptance_inferred": UNPROVEN,
        "capability_proven": UNPROVEN,
        "reachability_proven": UNPROVEN,
        "measurement_proven": UNPROVEN,
        "gate_id": gate_id,
        "recorded_command": gate.get("recorded_command"),
        "source": gate.get("source"),
        "run_dir": run_rel,
        "head": head,
        "branch": preflight.get("branch"),
        "command_exit_code": None if command is None else command.get("exit_code"),
        "timed_out": bool(command and command.get("timed_out")) or any(item.get("timed_out") for item in additional),
        "dispatch_attempted": True,
        "command_started": bool(command and command.get("command_started")),
        "launch_error": None if command is None else command.get("launch_error"),
        "required_checks": [launch_record(item) for item in additional],
        "runtime": runtime,
        "allow_dirty": allow_dirty,
        "unexpected_mutations": mutations,
        "verify_ok": False,
        "acceptance_claimed": False,
    }
    contract = build_run_contract(gate, head, run_rel, packaged_files)
    dump_json(run_dir / "contract.json", contract)
    dump_json(run_dir / "run.json", result)
    write_text(run_dir / "REPORT.txt", render_result(result))
    verify_ok = False
    try:
        verify_data = verify_evidence(root, run_dir / "contract.json")
        verify_ok = verify_data.get("evidence_verification") == "OK"
        write_text(run_dir / "verify" / "verify_evidence.txt", verify_render(verify_data))
    except Exception as exc:  # noqa: BLE001 — packaging must record verifier failure
        write_text(run_dir / "verify" / "verify_evidence.txt", f"error: evidence verification failed: {exc}\n")
    evidence_complete = verify_ok and not mutations and command is not None
    result["verify_ok"] = verify_ok
    result["evidence"] = "COMPLETE" if evidence_complete else "INCOMPLETE"
    dump_json(run_dir / "run.json", result)
    write_text(run_dir / "REPORT.txt", render_result(result))
    if not execution_success:
        set_status(run_dir, "EXECUTION_FAILURE")
    elif evidence_complete:
        set_status(run_dir, "EVIDENCE_COMPLETE")
    else:
        set_status(run_dir, "EVIDENCE_INCOMPLETE")
    return result


def process_exit_code(result: dict[str, Any]) -> int:
    execution = result.get("execution")
    if execution == "REFUSED":
        return EXIT_REFUSED
    if execution == "INTERRUPTED":
        return EXIT_INCOMPLETE
    if result.get("evidence") != "COMPLETE":
        if execution == "FAILURE":
            code = result.get("command_exit_code")
            return EXIT_EXECUTION_FAILURE if code in (None, 0) else int(code)
        return EXIT_INCOMPLETE
    if execution == "SUCCESS":
        return EXIT_OK
    code = result.get("command_exit_code")
    return EXIT_EXECUTION_FAILURE if code in (None, 0) else int(code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one recorded Stage 1a command and package evidence (Phase 3)."
    )
    parser.add_argument("--gate", help="Registry id to run. Required unless --list.")
    parser.add_argument("--list", action="store_true", help="List registered commands and exit.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Record dirty/untracked files and continue. Does not stash, commit, or clean.",
    )
    parser.add_argument("--root", default=None, help="Repository root.")
    parser.add_argument("--registry", default=None, help="Alternate registry path (tests).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else discover_root(Path.cwd())
        if not root.is_dir():
            raise RunGateError(f"error: repository root is not a directory: {display_root(root)}")
        registry_path = Path(args.registry) if args.registry else None
        if registry_path is not None and not registry_path.is_absolute():
            registry_path = root / registry_path
        if args.list:
            sys.stdout.write(list_gates(root, registry_path))
            return 0
        if not args.gate:
            raise RunGateError("error: --gate is required (no default gate; nothing is auto-selected)")
        result = run(
            root,
            args.gate,
            allow_dirty=bool(args.allow_dirty),
            registry_path=registry_path,
        )
    except RunGateError as exc:
        sys.stderr.write(str(exc).rstrip() + "\n")
        return EXIT_REFUSED
    sys.stdout.write(render_result(result))
    return process_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
