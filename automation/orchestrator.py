"""Simulation 3 inspection and controlled execution (Phases 1-4).

Observes preflight, the gate registry, SIM3_STATE (as a snapshot), and local
automation-run receipts. Inspection and dry-run never dispatch a gate. Explicit
--run delegates through a pinned, supervised worker and verifies its receipt.
Mechanical execution never infers scientific acceptance.

    py -3 -B automation/orchestrator.py --status
    py -3 -B automation/orchestrator.py --explain
    py -3 -B automation/orchestrator.py --next
    py -3 -B automation/orchestrator.py --dry-run --run <registry-id>
    py -3 -B automation/orchestrator.py --run <registry-id>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

REGISTRY_REL = Path("automation") / "gate_registry.json"
REGISTRY_FORMAT = "v3.gate.registry.1"
PREFLIGHT_REL = Path("automation") / "preflight.py"
RUNS_REL = Path("evidence") / "automation-runs"
UNPROVEN = "no"
KNOWN_STATUS = {
    "IN_PROGRESS",
    "REFUSED",
    "INTERRUPTED",
    "EXECUTION_FAILURE",
    "EVIDENCE_INCOMPLETE",
    "EVIDENCE_COMPLETE",
}


class OrchestratorError(Exception):
    """A blocking read-only inspection failure."""


def posix(path: str) -> str:
    return path.replace("\\", "/")


def discover_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / ".git").exists():
            return candidate
    raise OrchestratorError(
        f"error: cannot locate repository root from {posix(str(start))}"
    )


def parse_report_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    current: str | None = None
    for raw in text.splitlines():
        if current and raw.startswith("  - "):
            fields[current].append(raw[4:])
            continue
        current = None
        if ":" not in raw:
            continue
        key, rest = raw.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest == "(none)":
            fields[key] = []
        elif rest == "":
            current = key
            fields[key] = []
        else:
            fields[key] = rest
    return fields


def spawn_preflight(root: Path) -> dict[str, Any]:
    # --root selects data to inspect, never executable code.
    script = _REPO_ROOT / PREFLIGHT_REL
    if not script.is_file():
        return {
            "ok": False,
            "exit_code": None,
            "fields": {},
            "raw": "",
            "error": "preflight script missing",
        }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["NoDefaultCurrentDirectoryInExePath"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", str(script), "--root", str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=60,
            check=False,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "exit_code": None,
            "fields": {},
            "raw": "",
            "error": f"preflight could not execute: {exc}",
        }
    fields = parse_report_fields(proc.stdout or "")
    return {
        "ok": proc.returncode == 0 and fields.get("preflight_result") == "PASS",
        "exit_code": proc.returncode,
        "fields": fields,
        "raw": proc.stdout or "",
        "error": (proc.stderr or "").strip() or None,
    }


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_registry(root: Path) -> dict[str, Any]:
    path = root / REGISTRY_REL
    result: dict[str, Any] = {
        "status": "UNKNOWN",
        "reason": None,
        "entries": [],
        "count": "UNKNOWN",
        "safe_count": "UNKNOWN",
        "unsafe_count": "UNKNOWN",
    }
    if not path.is_file():
        result["status"] = "BLOCKED"
        result["reason"] = "gate registry missing"
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json_object)
    except (OSError, UnicodeError, ValueError) as exc:
        result["status"] = "BLOCKED"
        result["reason"] = f"malformed registry: {exc}"
        return result
    if not isinstance(payload, dict) or payload.get("format") != REGISTRY_FORMAT:
        result["status"] = "BLOCKED"
        result["reason"] = "unsupported registry format"
        return result
    gates = payload.get("gates")
    if not isinstance(gates, list):
        result["status"] = "BLOCKED"
        result["reason"] = "registry gates is not a list"
        return result
    entries = []
    safe = 0
    unsafe = 0
    seen: set[str] = set()
    for item in gates:
        gate_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(gate_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", gate_id):
            result.update(status="BLOCKED", reason="invalid_registry_id")
            return result
        if gate_id in seen:
            result.update(status="BLOCKED", reason=f"duplicate_registry_id:{gate_id}")
            return result
        seen.add(gate_id)
        parsed = parse_registry_entry(item)
        entries.append(parsed)
        if parsed["future_orchestration_eligible"] == "yes":
            safe += 1
        elif parsed["malformed"]:
            pass
        else:
            unsafe += 1
    result.update(
        {
            "status": "OK",
            "entries": entries,
            "count": str(len(entries)),
            "safe_count": str(safe),
            "unsafe_count": str(unsafe),
        }
    )
    return result


def parse_registry_entry(item: Any) -> dict[str, str | bool]:
    parsed: dict[str, str | bool] = {
        "id": "UNKNOWN",
        "recorded_command": "UNKNOWN",
        "acceptance_claimed": "UNKNOWN",
        "unsafe": "UNKNOWN",
        "future_orchestration_eligible": "no",
        "future_orchestration_reason": "malformed_entry",
        "currently_executable": "no",
        "malformed": True,
    }
    if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
        return parsed
    unsafe_raw = item.get("unsafe", [])
    if not isinstance(unsafe_raw, list) or not all(isinstance(part, str) and part for part in unsafe_raw):
        parsed["id"] = str(item.get("id"))
        parsed["future_orchestration_reason"] = "malformed_unsafe_field"
        return parsed
    unsafe = [str(part) for part in unsafe_raw]
    claimed = item.get("acceptance_claimed")
    parsed.update(
        {
            "id": str(item["id"]),
            "recorded_command": str(item.get("recorded_command") or "UNKNOWN"),
            "acceptance_claimed": "true" if claimed is True else "false" if claimed is False else "UNKNOWN",
            "unsafe": ",".join(unsafe) if unsafe else "(none)",
            "currently_executable": "no",
            "malformed": False,
        }
    )
    if claimed is True:
        parsed["future_orchestration_eligible"] = "no"
        parsed["future_orchestration_reason"] = "acceptance_claimed_true"
        return parsed
    if claimed is not False:
        parsed["future_orchestration_eligible"] = "no"
        parsed["future_orchestration_reason"] = "acceptance_claimed_unreadable"
        parsed["malformed"] = True
        return parsed
    if unsafe:
        parsed["future_orchestration_eligible"] = "no"
        parsed["future_orchestration_reason"] = "unsafe:" + ",".join(unsafe)
        return parsed
    argv = item.get("argv")
    checks = item.get("required_checks", [])
    watched = item.get("watched_prefixes", [])
    timeout = item.get("timeout_s", 300)
    valid_argv = lambda value: isinstance(value, list) and bool(value) and all(
        isinstance(part, str) and bool(part) and "\x00" not in part for part in value
    )
    if (
        not valid_argv(argv)
        or type(timeout) is not int or timeout <= 0
        or not isinstance(checks, list) or not all(valid_argv(check) for check in checks)
        or not isinstance(watched, list) or not all(isinstance(part, str) and part for part in watched)
    ):
        parsed["future_orchestration_reason"] = "malformed_execution_metadata"
        parsed["malformed"] = True
        return parsed
    parsed["future_orchestration_eligible"] = "yes"
    parsed["future_orchestration_reason"] = (
        "mechanical eligibility only; not accepted; not a scientific gate; "
        "this phase cannot execute"
    )
    # Validated command metadata, kept only so dry-run/execution can bind the
    # runtime policy to exactly these registry values (never a CLI input).
    parsed["argv"] = [str(part) for part in argv]
    parsed["required_checks"] = [[str(part) for part in check] for check in checks]
    return parsed


def inspect_receipts(root: Path, ignore_receipts: set[Path] | None = None) -> dict[str, Any]:
    try:
        return _inspect_receipts(root, ignore_receipts or set())
    except OSError as exc:
        return {
            "exist": "UNKNOWN", "count": "UNKNOWN", "in_progress_visible": "UNKNOWN",
            "rows": [], "malformed": [f"receipt_inspection_failed:{exc}"],
            "authority": "none", "non_authoritative": "yes",
        }


def _inspect_receipts(root: Path, ignore_receipts: set[Path] | None = None) -> dict[str, Any]:
    base = root / RUNS_REL
    info: dict[str, Any] = {
        "exist": "no",
        "count": 0,
        "in_progress_visible": "no",
        "rows": [],
        "malformed": [],
        "authority": "none",
        "non_authoritative": "yes",
    }
    if not base.is_dir():
        return info
    rows: list[str] = []
    malformed: list[str] = []
    count = 0
    in_progress = False
    for command_dir in sorted(base.iterdir(), key=lambda p: p.name):
        if command_dir.name == "README.md" or not command_dir.is_dir():
            continue
        if command_dir.is_symlink() or (hasattr(command_dir, 'is_junction') and command_dir.is_junction()):
            malformed.append(f"{command_dir.name} linked_receipt_directory")
            continue
        children = sorted(command_dir.iterdir(), key=lambda p: p.name)
        run_dirs = [child for child in children if child.is_dir()]
        if not run_dirs and (command_dir / "STATUS").is_file():
            run_dirs = [command_dir]
        for run_dir in run_dirs:
            if run_dir in (ignore_receipts or set()):
                continue
            rel = posix(run_dir.relative_to(root).as_posix())
            status_path = run_dir / "STATUS"
            count += 1
            if (run_dir.is_symlink() or status_path.is_symlink()
                    or (hasattr(run_dir, 'is_junction') and run_dir.is_junction())):
                malformed.append(f"{rel} linked_receipt")
                continue
            if not status_path.is_file():
                malformed.append(f"{rel} missing_STATUS")
                rows.append(f"{rel} status=UNKNOWN (malformed local receipt; not accepted evidence)")
                continue
            try:
                status = status_path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                malformed.append(f"{rel} unreadable_STATUS")
                rows.append(f"{rel} status=UNKNOWN (malformed local receipt; not accepted evidence)")
                continue
            if status not in KNOWN_STATUS:
                malformed.append(f"{rel} unexpected_STATUS={status}")
                rows.append(
                    f"{rel} status=UNKNOWN (malformed local receipt; not accepted evidence)"
                )
                continue
            if status == "IN_PROGRESS":
                in_progress = True
            if status in {"INTERRUPTED", "EVIDENCE_INCOMPLETE"}:
                malformed.append(f"{rel} unresolved_{status}")
            rows.append(f"{rel} status={status} (local receipt; not accepted evidence)")
    info.update(
        {
            "exist": "yes" if count else "no",
            "count": count,
            "in_progress_visible": "yes" if in_progress else "no",
            "rows": rows,
            "malformed": malformed,
        }
    )
    return info


def field(fields: dict[str, Any], key: str, default: str = "UNKNOWN") -> str:
    value = fields.get(key, default)
    if value is None or value == []:
        if key in {"dirty_files", "untracked_files", "blocking_failures"}:
            return "(none)"
        return default
    if isinstance(value, list):
        return "(none)" if not value else ", ".join(str(item) for item in value)
    return str(value)


def list_field(fields: dict[str, Any], key: str) -> list[str]:
    value = fields.get(key, [])
    if value == [] or value == "(none)":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def derive_workflow_condition(preflight: dict[str, Any], receipts: dict[str, Any], registry: dict[str, Any]) -> str:
    if preflight_blocker(preflight):
        return "blocked"
    if registry.get("status") == "BLOCKED":
        return "blocked"
    if receipts.get("in_progress_visible") == "yes":
        return "in_progress_receipt_visible"
    if receipts.get("malformed"):
        return "blocked"
    return "idle"


def preflight_blocker(preflight: dict[str, Any]) -> str | None:
    if not preflight.get("ok"):
        return "preflight_insufficient_to_determine_legality"
    fields = preflight.get("fields") or {}
    for key in ("branch", "head", "current_milestone", "milestone_status"):
        if field(fields, key) in {"UNKNOWN", "(none)", ""}:
            return f"preflight_unknown:{key}"
    # These two historical wording notes are informational. Unknown conflicts
    # remain blockers rather than being silently excused by preflight PASS.
    informational = ("record_rollback_describes_no_remote ", "stage_card_review_status_stale ")
    for issue in list_field(fields, "inconsistencies"):
        if not issue.startswith(informational):
            return f"preflight_inconsistency:{issue}"
    if list_field(fields, "blocking_failures"):
        return "preflight_reported_blocking_failures"
    return None


def observed_slice_1b(fields: dict[str, Any]) -> str:
    parked = field(fields, "sim3_state.parked")
    blockers = field(fields, "sim3_state.blockers")
    not_proven = field(fields, "sim3_state.not_proven")
    status = field(fields, "sim3_state.milestone_status")
    blob = f"{parked} {blockers} {not_proven} {status}".lower()
    if "1b" in blob and "not authorised" in blob:
        return "no"
    if "slice 1b" in blob and "not authorised" in blob:
        return "no"
    if "1b" in blob and "reviewed pass" in blob:
        return "yes"
    return "UNKNOWN"


def observed_review(fields: dict[str, Any]) -> str:
    status = field(fields, "sim3_state.milestone_status")
    milestone_status = field(fields, "milestone_status")
    blob = f"{status} {milestone_status}".lower()
    if "independent post-repair review pending" in blob:
        return "pending"
    return "UNKNOWN"


def observed_exit(fields: dict[str, Any]) -> str:
    status = field(fields, "sim3_state.milestone_status")
    milestone_status = field(fields, "milestone_status")
    blob = f"{status} {milestone_status}".lower()
    if "stage 1 exit unclaimed" in blob:
        return "unclaimed"
    return "UNKNOWN"


def inspect(root: Path, ignore_receipts: set[Path] | None = None) -> dict[str, Any]:
    preflight = spawn_preflight(root)
    fields = preflight.get("fields") or {}
    registry = load_registry(root)
    receipts = inspect_receipts(root, ignore_receipts)
    dirty = list_field(fields, "dirty_files")
    untracked = list_field(fields, "untracked_files")
    scientific_next = field(fields, "sim3_state.next_gate")
    return {
        "root": posix(str(root.resolve().as_posix())),
        "preflight": preflight,
        "fields": fields,
        "registry": registry,
        "receipts": receipts,
        "dirty": dirty,
        "untracked": untracked,
        "workflow_condition": derive_workflow_condition(preflight, receipts, registry),
        "scientific_next": scientific_next,
        "scientific_next_executable": "no",
    }


def render_status(data: dict[str, Any]) -> str:
    fields = data["fields"]
    registry = data["registry"]
    receipts = data["receipts"]
    lines = [
        "V3 orchestrator",
        "===============",
        "orchestrator_mode: read-only",
        "orchestrator_phase: 1",
        "this_phase_executes_registered_commands: no",
        "writes: no",
        "invokes_registered_command: no",
        "",
        "WORKFLOW / MECHANICAL STATE",
        "---------------------------",
        f"repository_root: {data['root']}",
        f"branch: {field(fields, 'branch')}",
        f"head: {field(fields, 'head')}",
        f"preflight_result: {field(fields, 'preflight_result')}",
        f"preflight_ok: {'yes' if data['preflight'].get('ok') else 'no'}",
    ]
    if data["preflight"].get("error") and not data["preflight"].get("ok"):
        lines.append(f"preflight_error: {data['preflight']['error']}")
    lines.extend(
        [
            f"dirty_files: {field(fields, 'dirty_files')}",
            f"untracked_files: {field(fields, 'untracked_files')}",
            f"mechanical_workflow_condition: {data['workflow_condition']}",
            "mechanical_workflow_authority: none (derived observation only)",
            f"registry_status: {registry['status']}",
        ]
    )
    if registry.get("reason"):
        lines.append(f"registry_reason: {registry['reason']}")
    lines.extend(
        [
            f"registered_command_count: {registry['count']}",
            f"safe_registered_command_count: {registry['safe_count']}",
            f"unsafe_registered_command_count: {registry['unsafe_count']}",
            "local_receipts_authority: none",
            "local_receipts_non_authoritative: yes",
            f"local_receipts_exist: {receipts['exist']}",
            f"local_receipt_count: {receipts['count']}",
            f"in_progress_receipt_visible: {receipts['in_progress_visible']}",
        ]
    )
    if receipts["rows"]:
        lines.append("local_receipts:")
        for row in receipts["rows"]:
            lines.append(f"  - {row}")
    else:
        lines.append("local_receipts: (none)")
    if receipts["malformed"]:
        lines.append("malformed_local_receipts:")
        for row in receipts["malformed"]:
            lines.append(f"  - {row}")
    lines.extend(
        [
            "",
            "SCIENTIFIC / PROJECT STATE — OBSERVED ONLY",
            "------------------------------------------",
            "scientific_plane: observed_only",
            "snapshot_is_not_governing_authority: yes",
            f"observed_current_milestone: {field(fields, 'sim3_state.current_milestone', field(fields, 'current_milestone'))}",
            f"observed_milestone_status: {field(fields, 'sim3_state.milestone_status', field(fields, 'milestone_status'))}",
            f"observed_stage_1a_exit: {observed_exit(fields)}",
            f"observed_independent_review: {observed_review(fields)}",
            f"observed_slice_1b_authorised: {observed_slice_1b(fields)}",
            f"observed_last_accepted_gate: {field(fields, 'sim3_state.last_accepted_gate')}",
            f"observed_proven: {field(fields, 'sim3_state.proven')}",
            f"observed_scientific_next: {data['scientific_next']}",
            "observed_scientific_next_executable: no",
            "observed_scientific_next_is_registry_id: no",
            "milestone_acceptance_inferred: no",
            f"capability_proven: {UNPROVEN}",
            f"reachability_proven: {UNPROVEN}",
            f"measurement_proven: {UNPROVEN}",
            "note: preflight_result PASS is inspection only; it is not an independent-review verdict, not Stage 1a completion, and not milestone acceptance",
            "note: local automation receipts are not accepted scientific evidence",
        ]
    )
    return "\n".join(lines) + "\n"


def classify_mechanical_actions(data: dict[str, Any]) -> list[dict[str, str]]:
    """Discover legal mechanical actions from the registry only. Never invent ids."""
    registry = data["registry"]
    preflight = data["preflight"]
    dirty = bool(data.get("dirty") or data.get("untracked"))
    in_progress = data["receipts"].get("in_progress_visible") == "yes"
    actions: list[dict[str, str]] = []
    if registry.get("status") != "OK":
        return [
            {
                "id": "UNKNOWN",
                "registered": "no",
                "acceptance_claimed": "UNKNOWN",
                "unsafe": "UNKNOWN",
                "mechanically_eligible": "no",
                "currently_executable": "no",
                "blocked_reason": str(registry.get("reason") or "registry_blocked"),
            }
        ]
    preflight_reason = preflight_blocker(preflight)
    registry_claims_acceptance = any(entry.get("acceptance_claimed") == "true" for entry in registry.get("entries", []))
    registry_malformed = any(entry.get("malformed") for entry in registry.get("entries", []))
    for entry in registry.get("entries") or []:
        action = {
            "id": str(entry.get("id") or "UNKNOWN"),
            "registered": "yes",
            "acceptance_claimed": str(entry.get("acceptance_claimed") or "UNKNOWN"),
            "unsafe": str(entry.get("unsafe") or "UNKNOWN"),
            "mechanically_eligible": "no",
            "currently_executable": "no",
            "blocked_reason": "",
            "recorded_command_identity": str(entry.get("recorded_command") or "UNKNOWN"),
            "future_execution_requires_allow_dirty": "yes" if dirty else "no",
            "future_execution_blocked_by_in_progress_receipt": "yes" if in_progress else "no",
        }
        if preflight_reason:
            action["blocked_reason"] = preflight_reason
        elif entry.get("malformed"):
            action["blocked_reason"] = str(entry.get("future_orchestration_reason") or "malformed_entry")
        elif entry.get("future_orchestration_eligible") != "yes":
            action["blocked_reason"] = str(entry.get("future_orchestration_reason") or "ineligible")
        elif registry_claims_acceptance:
            action["blocked_reason"] = "registry_contains_acceptance_claim"
        elif registry_malformed:
            action["blocked_reason"] = "registry_contains_malformed_entry"
        else:
            action["mechanically_eligible"] = "yes"
            action["blocked_reason"] = "inspection only; execution requires explicit --run and fresh checks"
        actions.append(action)
    return actions


def resolve_dry_run(
    data: dict[str, Any],
    requested_id: str,
    allow_dirty: bool,
) -> dict[str, Any]:
    """Resolve a registry ID to a future run_gate delegation. Never execute it."""
    result = {
        "requested_id": requested_id,
        "registered": "no",
        "mechanically_eligible": "no",
        "currently_executable": "no",
        "allow_dirty_requested": "yes" if allow_dirty else "no",
        "future_execution_blocked": "yes",
        "blocked_reason": "unknown_registry_id",
        "delegation_target": "automation/run_gate.py",
        "delegation_gate_id": "",
        "resolved_argv": [],
        "runtime": None,
        "delegation_executed": "no",
        "receipt_created": "no",
        "scientific_state_changed": "no",
    }
    registry = data["registry"]
    if registry.get("status") != "OK":
        result["blocked_reason"] = str(registry.get("reason") or "registry_blocked")
        return result
    match = None
    for action in classify_mechanical_actions(data):
        if action.get("registered") == "yes" and action.get("id") == requested_id:
            match = action
            break
    if match is None:
        return result
    result["registered"] = "yes"
    result["delegation_gate_id"] = requested_id
    result["mechanically_eligible"] = match["mechanically_eligible"]
    result["blocked_reason"] = match["blocked_reason"]
    if match["mechanically_eligible"] != "yes":
        return result
    # Bind the registered command to the explicit runtime policy. The registry
    # argv is provenance; only a `py -3` prefix resolves, to the controller's
    # native base interpreter. Unsupported launcher forms block here.
    entry = next(item for item in registry["entries"] if item.get("id") == requested_id)
    from automation.controller_io import SafetyError
    from automation.runtime_policy import bind_gate_runtime
    try:
        result["runtime"] = bind_gate_runtime(entry)
    except SafetyError as exc:
        result["blocked_reason"] = f"runtime_policy_refused: {exc}"
        return result
    argv = build_worker_argv(data.get('root', '<inspected repository>'), requested_id,
                             allow_dirty, '<request allocated on explicit run>')
    result["resolved_argv"] = argv
    if data["receipts"].get("in_progress_visible") == "yes":
        result["blocked_reason"] = "in_progress_receipt_requires_review"
        return result
    if data["receipts"].get("malformed"):
        result["blocked_reason"] = "malformed_receipts_require_review"
        return result
    dirty = bool(data.get("dirty") or data.get("untracked"))
    if dirty and not allow_dirty:
        result["future_execution_blocked"] = "yes"
        result["blocked_reason"] = "dirty tree requires explicit --allow-dirty"
        result["resolved_argv"] = argv
        return result
    result["future_execution_blocked"] = "no"
    result["blocked_reason"] = "dry-run only; execution requires fresh checks in the pinned worker"
    result["resolved_argv"] = argv
    return result


def build_worker_argv(root: str | Path, requested_id: str, allow_dirty: bool, request: str | Path,
                      request_hash: str = '<sha256 captured on explicit run>') -> list[str]:
    from automation.controller_io import python_executable
    argv = [python_executable(), '-I', '-B', '-X', 'utf8',
            str(_REPO_ROOT / 'automation/orchestrator_worker.py'), '--root', str(root),
            '--gate', requested_id, '--request', str(request), '--request-sha256', request_hash]
    if allow_dirty:
        argv.append('--allow-dirty')
    return argv


def render_dry_run(data: dict[str, Any], resolved: dict[str, Any]) -> str:
    fields = data["fields"]
    argv = resolved.get("resolved_argv") or []
    argv_text = json.dumps(argv, ensure_ascii=True)
    runtime = (resolved.get("runtime") or {}).get("command") or {}
    lines = [
        "V3 orchestrator dry-run",
        "=======================",
        "orchestrator_mode: read-only",
        "orchestrator_phase: 3",
        "this_phase_executes_registered_commands: no",
        f"requested_registry_id: {resolved['requested_id']}",
        f"registered: {resolved['registered']}",
        f"mechanically_eligible: {resolved['mechanically_eligible']}",
        "currently_executable: no",
        f"repository: {data['root']}",
        f"branch: {field(fields, 'branch')}",
        f"head: {field(fields, 'head')}",
        f"dirty: {'yes' if (data.get('dirty') or data.get('untracked')) else 'no'}",
        f"allow_dirty_requested: {resolved['allow_dirty_requested']}",
        f"future_execution_blocked: {resolved['future_execution_blocked']}",
        f"blocked_reason: {resolved['blocked_reason']}",
        # Registered-command runtime binding (provenance + resolution). These
        # describe the gate command; the delegation argv below names only the
        # pinned worker and registry ID.
        f"registered_command_argv: {json.dumps(runtime.get('registry_argv') or [], ensure_ascii=True)}",
        f"runtime_policy: {runtime.get('policy') or '(none)'}",
        f"runtime_interpreter: {runtime.get('interpreter') or '(none)'}",
        f"runtime_interpreter_sha256: {runtime.get('interpreter_sha256') or '(none)'}",
        f"runtime_resolved_command_argv: {json.dumps(runtime.get('resolved_argv') or [], ensure_ascii=True)}",
        "delegation_target: automation/run_gate.py",
        "delegation_transport: pinned supervised worker; request allocated only on explicit run",
        f"delegation_gate_id: {resolved['delegation_gate_id'] or '(none)'}",
        f"resolved_delegation_argv: {argv_text}",
        "delegation_executed: no",
        "receipt_created: no",
        "scientific_state_changed: no",
        "milestone_acceptance_inferred: no",
        f"capability_proven: {UNPROVEN}",
        f"reachability_proven: {UNPROVEN}",
        f"measurement_proven: {UNPROVEN}",
        "note: dry-run resolves a future run_gate delegation; it does not execute",
    ]
    return "\n".join(lines) + "\n"


def render_next(data: dict[str, Any]) -> str:
    actions = classify_mechanical_actions(data)
    legal = [item for item in actions if item["mechanically_eligible"] == "yes"]
    blocked = [item for item in actions if item["mechanically_eligible"] != "yes"]
    lines = [
        "V3 orchestrator",
        "===============",
        "orchestrator_mode: read-only",
        "orchestrator_phase: 2",
        "this_phase_executes_registered_commands: no",
        "writes: no",
        "invokes_registered_command: no",
        "actions_are_discovered_not_generated: yes",
        "",
        "WORKFLOW / MECHANICAL ACTIONS",
        "-----------------------------",
        f"legal_mechanical_action_count: {len(legal)}",
        f"blocked_registered_action_count: {len(blocked)}",
        "currently_executable: no",
    ]
    if not legal:
        lines.append("legal_mechanical_actions: (none)")
    for item in legal:
        lines.extend(
            [
                "[action]",
                f"id: {item['id']}",
                f"registered: {item['registered']}",
                f"acceptance_claimed: {item['acceptance_claimed']}",
                f"unsafe: {item['unsafe']}",
                "mechanically_eligible: yes",
                "currently_executable: no",
                f"reason: {item['blocked_reason']}",
                f"future_execution_requires_allow_dirty: {item['future_execution_requires_allow_dirty']}",
                f"future_execution_blocked_by_in_progress_receipt: {item['future_execution_blocked_by_in_progress_receipt']}",
                f"recorded_command_identity: {item['recorded_command_identity']}",
                "not_a_scientific_gate: yes",
            ]
        )
    lines.extend(
        [
            "",
            "BLOCKED / INELIGIBLE REGISTERED ACTIONS",
            "---------------------------------------",
        ]
    )
    if not blocked:
        lines.append("blocked_registered_actions: (none)")
    for item in blocked:
        lines.extend(
            [
                "[action]",
                f"id: {item['id']}",
                f"registered: {item['registered']}",
                f"acceptance_claimed: {item['acceptance_claimed']}",
                f"unsafe: {item['unsafe']}",
                "mechanically_eligible: no",
                "currently_executable: no",
                f"reason: {item['blocked_reason']}",
            ]
        )
    lines.extend(
        [
            "",
            "SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY",
            "-----------------------------------------",
            f"observed_scientific_next: {data['scientific_next']}",
            "executable: no",
            "authority: project/scientific process, not orchestrator registry",
            "observed_scientific_next_is_registry_id: no",
            "milestone_acceptance_inferred: no",
            f"capability_proven: {UNPROVEN}",
            f"reachability_proven: {UNPROVEN}",
            f"measurement_proven: {UNPROVEN}",
            f"observed_slice_1b_authorised: {observed_slice_1b(data['fields'])}",
            "note: COMPLETE local receipts are not scientific authority",
            "note: preflight_result PASS is inspection only",
        ]
    )
    return "\n".join(lines) + "\n"


def render_explain(data: dict[str, Any]) -> str:
    lines = [render_status(data).rstrip(), "", "REGISTERED COMMAND SURFACE (MECHANICAL ONLY)", "---------------------------------------------"]
    registry = data["registry"]
    if registry["status"] != "OK":
        lines.append("registered_commands: UNKNOWN")
        lines.append(f"reason: {registry.get('reason')}")
        lines.append("fail_closed: yes")
        lines.append("currently_executable: no")
        return "\n".join(lines) + "\n"
    if not registry["entries"]:
        lines.append("registered_commands: (none)")
        lines.append("currently_executable: no")
        return "\n".join(lines) + "\n"
    for entry in registry["entries"]:
        lines.extend(
            [
                f"registered_command_id: {entry['id']}",
                f"  recorded_command_identity: {entry['recorded_command']}",
                f"  acceptance_claimed: {entry['acceptance_claimed']}",
                f"  unsafe: {entry['unsafe']}",
                f"  future_orchestration_eligible: {entry['future_orchestration_eligible']}",
                f"  future_orchestration_reason: {entry['future_orchestration_reason']}",
                "  currently_executable: no",
                "  not_a_scientific_gate: yes",
            ]
        )
    lines.append("this_phase_executes_registered_commands: no")
    lines.append("observed_scientific_next_executable: no")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulation 3 inspection and controlled execution (Phases 1-4).",
        allow_abbrev=False,
    )
    parser.add_argument("--status", action="store_true", help="Print derived mechanical and observed scientific state.")
    parser.add_argument("--explain", action="store_true", help="Print --status plus the registered command surface.")
    parser.add_argument("--next", action="store_true", help="Print discovered legal mechanical actions; does not execute.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve --run ID to a future run_gate delegation; does not execute.",
    )
    parser.add_argument(
        "--run",
        dest="run_id",
        default=None,
        metavar="REGISTRY_ID",
        help="Exact registry ID. --dry-run resolves only; otherwise use controlled execution.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Explicit dirty-tree permission for --run or --dry-run --run; does not waive other blockers.",
    )
    parser.add_argument("--root", default=None, help="Repository root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.dry_run and not args.run_id:
        sys.stderr.write("error: --dry-run requires --run REGISTRY_ID; dry-run does not execute\n")
        return 2
    if not args.status and not args.explain and not args.next and not args.dry_run and args.run_id is None:
        sys.stderr.write(
            "error: --status, --explain, --next, --dry-run --run, or --run is required\n"
        )
        return 2
    if sum((args.status, args.explain, args.next, args.run_id is not None)) != 1:
        parser.error("choose exactly one of --status, --explain, --next, or [--dry-run] --run ID")
    if args.allow_dirty and args.run_id is None:
        parser.error("--allow-dirty requires --run ID")
    try:
        root = Path(args.root).resolve() if args.root else discover_root(Path.cwd())
        if not root.is_dir():
            raise OrchestratorError(f"error: repository root is not a directory: {posix(str(root))}")
        if args.run_id is not None and not args.dry_run:
            report = execute_run(root, args.run_id, bool(args.allow_dirty))
            sys.stdout.write(render_run(report))
            return {'SUCCESS': 0, 'FAILURE': 1, 'REFUSED': 2, 'INTERRUPTED': 3}[report['overall_result']]
        data = inspect(root)
    except (OrchestratorError, OSError, UnicodeError) as exc:
        sys.stderr.write(str(exc).rstrip() + "\n")
        return 1
    if args.dry_run:
        resolved = resolve_dry_run(data, args.run_id, bool(args.allow_dirty))
        sys.stdout.write(render_dry_run(data, resolved))
        if resolved["registered"] != "yes" or resolved["mechanically_eligible"] != "yes":
            return 2
        return 0
    if args.next:
        sys.stdout.write(render_next(data))
    elif args.explain:
        sys.stdout.write(render_explain(data))
    else:
        sys.stdout.write(render_status(data))
    return 0


def execute_run(root: Path, requested_id: str, allow_dirty: bool) -> dict:
    from automation.orchestrator_execution import execute_run as controlled_run
    return controlled_run(root, requested_id, allow_dirty, inspect=inspect, resolve=resolve_dry_run)


def render_run(report: dict) -> str:
    lines = ['V3 orchestrator run', 'orchestrator_mode: controlled-execution', 'orchestrator_phase: 4']
    for key, value in report.items():
        if key in {'receipt_sha256', 'process'}:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True, ensure_ascii=True)
        lines.append(f'{key}: {value if value is not None else "(none)"}')
    lines.extend(['local_receipts_non_authoritative: yes', 'capability_proven: no',
                  'reachability_proven: no', 'measurement_proven: no',
                  'note: mechanical success is not scientific acceptance or Slice 1b authorisation'])
    return '\n'.join(lines) + '\n'


if __name__ == "__main__":
    # The CLI contract is UTF-8, including redirected Windows output.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
