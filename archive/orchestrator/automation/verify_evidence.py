"""Read-only mechanical evidence verifier for V3 (Phase 2).

Checks that declared evidence packets still exist, resolve, and match recorded
file identities. It does not run the simulation, does not accept a milestone,
and does not answer capability, reachability, or measurement.

Run from the repository root:

    py -3 automation/verify_evidence.py
    py -3 automation/verify_evidence.py --contract automation/evidence_contracts/stage-01-repair-1.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from automation.preflight import (  # noqa: E402
    discover_root,
    display_root,
    git_blob_bytes,
    run_git,
    sha256_bytes,
    sha256_file,
)

FORMAT = "v3.evidence.contract.1"
CONTRACT_DIR_REL = Path("automation") / "evidence_contracts"
REQUIRED_FIELDS = (
    "format",
    "packet_id",
    "milestone",
    "gate",
    "acceptance_claimed",
    "role",
    "recorded_revision",
    "must_match_current_head",
    "stage_record",
    "required_files",
)

# These three remain "no" unless an authoritative gate later supplies a
# deterministic machine-verifiable criterion. No such criterion exists now.
UNPROVEN = "no"


class VerifyError(Exception):
    """A blocking verifier failure with a stable message."""


def posix_join(rel: str) -> Path:
    return Path(*rel.split("/"))


def lookup(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(".".join(path))
        current = current[key]
    return current


def git_full_revision(root: Path, git_exe: str | None, rev: str) -> str | None:
    if git_exe is None or not rev:
        return None
    proc = run_git(root, ["rev-parse", "--verify", f"{rev}^{{commit}}"], git_exe)
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def git_head(root: Path, git_exe: str | None) -> str:
    if git_exe is None:
        return "UNKNOWN"
    proc = run_git(root, ["rev-parse", "HEAD"], git_exe)
    if proc.returncode != 0:
        return "UNKNOWN"
    return (proc.stdout or "").strip() or "UNKNOWN"


def add_check(
    checks: list[tuple[str, str, str]],
    status: str,
    code: str,
    detail: str,
) -> None:
    checks.append((status, code, detail))


def validate_contract(data: Any, rel: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{rel}: contract is not a JSON object"]
    if data.get("format") != FORMAT:
        errors.append(f"{rel}: format must be {FORMAT}")
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"{rel}: missing field {field}")
    if data.get("acceptance_claimed") is True:
        errors.append(
            f"{rel}: acceptance_claimed is true; a contract cannot claim "
            "milestone acceptance"
        )
    if data.get("role") not in {"historical", "current"}:
        errors.append(f"{rel}: role must be historical or current")
    if data.get("role") == "current" and data.get("must_match_current_head") is not True:
        errors.append(f"{rel}: role current requires must_match_current_head true")
    if not isinstance(data.get("required_files", []), list):
        errors.append(f"{rel}: required_files must be a list")
    return errors


def load_contracts(root: Path, selected: Path | None) -> list[tuple[str, dict[str, Any]]]:
    if selected is not None:
        path = selected if selected.is_absolute() else root / selected
        if not path.is_file():
            raise VerifyError(f"error: contract not found: {path.as_posix()}")
        rel = path.resolve().relative_to(root.resolve()).as_posix() if path.resolve().is_relative_to(root.resolve()) else path.as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VerifyError(f"error: malformed contract {rel}: {exc}") from exc
        problems = validate_contract(data, rel)
        if problems:
            raise VerifyError("error: " + "; ".join(problems))
        return [(rel, data)]
    directory = root / CONTRACT_DIR_REL
    if not directory.is_dir():
        raise VerifyError(f"error: contract directory missing: {CONTRACT_DIR_REL.as_posix()}")
    found: list[tuple[str, dict[str, Any]]] = []
    schema_errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        rel = (CONTRACT_DIR_REL / path.name).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            schema_errors.append(f"{rel}: malformed JSON: {exc}")
            continue
        problems = validate_contract(data, rel)
        if problems:
            schema_errors.extend(problems)
            continue
        found.append((rel, data))
    if schema_errors:
        raise VerifyError("error: " + "; ".join(schema_errors))
    if not found:
        raise VerifyError("error: no evidence contracts found")
    return found


def verify_required_files(root: Path, packet_id: str, files: list[Any], checks: list[tuple[str, str, str]]) -> None:
    for item in files:
        if not isinstance(item, str) or not item:
            add_check(checks, "ERROR", "required_file_invalid", f"packet={packet_id} {item!r}")
            continue
        path = root / posix_join(item)
        if path.is_file():
            add_check(checks, "OK", "required_file", f"packet={packet_id} {item}")
        else:
            add_check(checks, "ERROR", "missing_file", f"packet={packet_id} {item}")


def verify_manifest(
    root: Path,
    packet_id: str,
    manifest_rel: str | None,
    exclude: list[str],
    checks: list[tuple[str, str, str]],
    *,
    role: str | None = None,
    recorded_revision: str | None = None,
    git_exe: str | None = None,
) -> None:
    """Check a packet's file manifest.

    A historical packet asserts what its files were at its recorded revision,
    so with git available those blobs are what the manifest is checked against;
    a later declared change in the working tree is reported as superseded, not
    as a mismatch. A current packet, an entry not tracked at that revision, or
    a run without git falls back to the working tree.
    """
    if not manifest_rel:
        add_check(checks, "OK", "file_manifest", f"packet={packet_id} none declared")
        return
    path = root / posix_join(manifest_rel)
    if not path.is_file():
        add_check(checks, "ERROR", "missing_file_manifest", f"packet={packet_id} {manifest_rel}")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add_check(checks, "ERROR", "malformed_file_manifest", f"packet={packet_id} {manifest_rel} {exc}")
        return
    hashes = payload.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        add_check(checks, "ERROR", "malformed_file_manifest", f"packet={packet_id} sha256 map missing")
        return
    add_check(checks, "OK", "file_manifest_readable", f"packet={packet_id} {manifest_rel}")
    excluded = set(exclude)
    historical = role == "historical" and bool(recorded_revision) and git_exe is not None
    for rel, expected in sorted(hashes.items()):
        target = root / posix_join(rel)
        if rel not in excluded and historical:
            blob = git_blob_bytes(root, git_exe, str(recorded_revision), rel)
            if blob is not None:
                at_revision = sha256_bytes(blob)
                if at_revision != expected:
                    add_check(
                        checks,
                        "ERROR",
                        "manifest_hash_mismatch",
                        f"packet={packet_id} {rel} recorded={expected} at_revision={at_revision}",
                    )
                    continue
                add_check(
                    checks,
                    "OK",
                    "manifest_hash_match",
                    f"packet={packet_id} {rel} at recorded revision {str(recorded_revision)[:12]}",
                )
                if not target.is_file() or sha256_file(target) != expected:
                    add_check(
                        checks,
                        "OK",
                        "manifest_superseded_in_working_tree",
                        f"packet={packet_id} {rel} differs from the recorded revision in the working tree",
                    )
                continue
        if not target.is_file():
            add_check(checks, "ERROR", "manifest_path_missing", f"packet={packet_id} {rel}")
            continue
        add_check(checks, "OK", "manifest_path_exists", f"packet={packet_id} {rel}")
        if rel in excluded:
            add_check(
                checks,
                "OK",
                "manifest_hash_skipped",
                f"packet={packet_id} {rel} excluded (amended after the snapshot)",
            )
            continue
        actual = sha256_file(target)
        if actual == expected:
            add_check(checks, "OK", "manifest_hash_match", f"packet={packet_id} {rel}")
        else:
            add_check(
                checks,
                "ERROR",
                "manifest_hash_mismatch",
                f"packet={packet_id} {rel} recorded={expected} actual={actual}",
            )


def verify_receipts(root: Path, packet_id: str, receipts: Any, replay_required: bool, checks: list[tuple[str, str, str]]) -> None:
    if receipts is None:
        receipts = {}
    if not isinstance(receipts, dict):
        add_check(checks, "ERROR", "malformed_receipts", f"packet={packet_id}")
        return
    for kind in ("test_suite", "determinism", "mutation", "replay"):
        items = receipts.get(kind, [])
        if not isinstance(items, list):
            add_check(checks, "ERROR", "malformed_receipts", f"packet={packet_id} {kind}")
            continue
        if not items:
            if kind == "replay" and not replay_required:
                add_check(
                    checks,
                    "OK",
                    "replay_not_required",
                    f"packet={packet_id} no sealed replay in this slice",
                )
            else:
                add_check(checks, "OK", "receipts_none", f"packet={packet_id} {kind}")
            continue
        for item in items:
            path = root / posix_join(str(item))
            if path.is_file():
                add_check(checks, "OK", "receipt_exists", f"packet={packet_id} {kind} {item}")
            else:
                add_check(checks, "ERROR", "missing_receipt", f"packet={packet_id} {kind} {item}")
    if replay_required and not receipts.get("replay"):
        add_check(checks, "ERROR", "missing_replay_receipts", f"packet={packet_id}")


def verify_json_receipt(
    root: Path,
    packet_id: str,
    spec: dict[str, Any],
    source_base: str | None,
    recorded_revision: str | None,
    current_head: str,
    checks: list[tuple[str, str, str]],
) -> None:
    rel = spec.get("path")
    if not isinstance(rel, str):
        add_check(checks, "ERROR", "malformed_json_receipt", f"packet={packet_id} path missing")
        return
    path = root / posix_join(rel)
    if not path.is_file():
        add_check(checks, "ERROR", "missing_json_receipt", f"packet={packet_id} {rel}")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add_check(checks, "ERROR", "malformed_json_receipt", f"packet={packet_id} {rel} {exc}")
        return
    if not isinstance(payload, dict):
        add_check(checks, "ERROR", "malformed_json_receipt", f"packet={packet_id} {rel} not an object")
        return
    add_check(checks, "OK", "json_receipt_readable", f"packet={packet_id} {rel}")
    for key in spec.get("required_keys") or []:
        if key in payload:
            add_check(checks, "OK", "json_receipt_key", f"packet={packet_id} {rel} {key}")
        else:
            add_check(checks, "ERROR", "json_receipt_missing_key", f"packet={packet_id} {rel} {key}")
    expected = spec.get("expected_values") or {}
    if isinstance(expected, dict):
        for key, value in sorted(expected.items()):
            if payload.get(key) == value:
                add_check(checks, "OK", "json_receipt_value", f"packet={packet_id} {rel} {key}={value!r}")
            else:
                add_check(
                    checks,
                    "ERROR",
                    "json_receipt_value_mismatch",
                    f"packet={packet_id} {rel} {key} recorded={payload.get(key)!r} expected={value!r}",
                )
    head_field = spec.get("head_field")
    head_equals = spec.get("head_equals")
    if head_field:
        recorded_head = payload.get(head_field)
        mapping = {
            "source_base": source_base,
            "recorded_revision": recorded_revision,
            "current_head": current_head,
        }
        expected_head = mapping.get(str(head_equals))
        if expected_head and recorded_head == expected_head:
            add_check(
                checks,
                "OK",
                "json_receipt_head",
                f"packet={packet_id} {rel} {head_field}={recorded_head} equals {head_equals}",
            )
        else:
            add_check(
                checks,
                "ERROR",
                "json_receipt_head_mismatch",
                (
                    f"packet={packet_id} {rel} {head_field}={recorded_head!r} "
                    f"expected {head_equals}={expected_head!r}"
                ),
            )
        if head_equals != "current_head" and recorded_head == current_head and source_base != current_head:
            add_check(
                checks,
                "ERROR",
                "stale_head_confused_with_current",
                f"packet={packet_id} {rel} receipt head unexpectedly equals current HEAD",
            )
    artifact = spec.get("artifact")
    if artifact:
        try:
            art_rel = lookup(payload, list(artifact["path_from"]))
            art_hash = lookup(payload, list(artifact["sha256_from"]))
        except (KeyError, TypeError):
            add_check(checks, "ERROR", "artifact_pointer_missing", f"packet={packet_id} {rel}")
            return
        art_path = path.parent / str(art_rel)
        if not art_path.is_file():
            add_check(checks, "ERROR", "artifact_missing", f"packet={packet_id} {art_path.as_posix()}")
            return
        actual = sha256_file(art_path)
        if actual == art_hash:
            add_check(checks, "OK", "artifact_hash_match", f"packet={packet_id} {art_rel}")
        else:
            add_check(
                checks,
                "ERROR",
                "artifact_hash_mismatch",
                f"packet={packet_id} {art_rel} recorded={art_hash} actual={actual}",
            )


def verify_phrases(root: Path, packet_id: str, record_rel: str, phrases: list[Any], checks: list[tuple[str, str, str]]) -> None:
    record_path = root / posix_join(record_rel)
    if not record_path.is_file():
        add_check(checks, "ERROR", "missing_stage_record", f"packet={packet_id} {record_rel}")
        return
    text = record_path.read_text(encoding="utf-8")
    for phrase in phrases:
        if not isinstance(phrase, str):
            continue
        if phrase in text:
            add_check(checks, "OK", "command_phrase", f"packet={packet_id} {phrase}")
        else:
            add_check(checks, "ERROR", "missing_command_phrase", f"packet={packet_id} {phrase}")


def verify_seeds_horizons(root: Path, packet_id: str, contract: dict[str, Any], checks: list[tuple[str, str, str]]) -> None:
    seeds = contract.get("recorded_seeds") or []
    if not seeds:
        add_check(checks, "OK", "seeds_none_declared", f"packet={packet_id}")
    for spec in seeds:
        if not isinstance(spec, dict):
            add_check(checks, "ERROR", "malformed_seed", f"packet={packet_id}")
            continue
        seed_id = spec.get("id", "UNKNOWN")
        files = spec.get("evidence_files") or []
        if not files:
            add_check(checks, "ERROR", "seed_without_evidence", f"packet={packet_id} {seed_id}")
            continue
        for item in files:
            path = root / posix_join(str(item))
            if path.is_file():
                add_check(checks, "OK", "seed_evidence", f"packet={packet_id} {seed_id} {item}")
            else:
                add_check(checks, "ERROR", "missing_seed_evidence", f"packet={packet_id} {seed_id} {item}")
    horizons = contract.get("recorded_horizons") or []
    if not horizons:
        add_check(checks, "OK", "horizons_none_declared", f"packet={packet_id}")
    for spec in horizons:
        if not isinstance(spec, dict):
            add_check(checks, "ERROR", "malformed_horizon", f"packet={packet_id}")
            continue
        rel = spec.get("in")
        phrase = spec.get("phrase")
        horizon_id = spec.get("id", "UNKNOWN")
        path = root / posix_join(str(rel))
        if not path.is_file():
            add_check(checks, "ERROR", "missing_horizon_source", f"packet={packet_id} {horizon_id} {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if isinstance(phrase, str) and phrase in text:
            add_check(checks, "OK", "horizon_recorded", f"packet={packet_id} {horizon_id}")
        else:
            add_check(checks, "ERROR", "missing_horizon_phrase", f"packet={packet_id} {horizon_id}")


def verify_revisions(
    root: Path,
    packet_id: str,
    contract: dict[str, Any],
    git_exe: str | None,
    current_head: str,
    checks: list[tuple[str, str, str]],
) -> tuple[str | None, str | None]:
    recorded = str(contract.get("recorded_revision") or "")
    source_base = str(contract.get("source_base") or "") or None
    if git_exe is None:
        add_check(checks, "ERROR", "git_missing", f"packet={packet_id}")
        return None, source_base
    recorded_full = git_full_revision(root, git_exe, recorded)
    if recorded_full:
        add_check(
            checks,
            "OK",
            "recorded_revision_present",
            f"packet={packet_id} {recorded_full}",
        )
    else:
        add_check(
            checks,
            "ERROR",
            "recorded_revision_missing",
            f"packet={packet_id} {recorded}",
        )
    if source_base:
        source_full = git_full_revision(root, git_exe, source_base)
        if source_full:
            add_check(checks, "OK", "source_base_present", f"packet={packet_id} {source_full}")
            source_base = source_full
        else:
            add_check(checks, "ERROR", "source_base_missing", f"packet={packet_id} {source_base}")
    if contract.get("must_match_current_head"):
        if recorded_full and recorded_full == current_head:
            add_check(checks, "OK", "head_matches_recorded", f"packet={packet_id} {current_head}")
        else:
            add_check(
                checks,
                "ERROR",
                "stale_or_unrelated_head",
                f"packet={packet_id} recorded={recorded_full!r} current={current_head!r}",
            )
    else:
        if recorded_full and recorded_full == current_head:
            add_check(
                checks,
                "OK",
                "historical_revision_is_also_head",
                f"packet={packet_id} {current_head}",
            )
        else:
            add_check(
                checks,
                "OK",
                "historical_revision_not_required_to_be_head",
                f"packet={packet_id} recorded={recorded_full} current={current_head}",
            )
    return recorded_full, source_base


def verify_packet(
    root: Path,
    rel: str,
    contract: dict[str, Any],
    git_exe: str | None,
    current_head: str,
) -> dict[str, Any]:
    packet_id = str(contract.get("packet_id") or rel)
    checks: list[tuple[str, str, str]] = []
    add_check(checks, "OK", "contract_loaded", f"packet={packet_id} {rel}")
    add_check(checks, "OK", "milestone", f"packet={packet_id} {contract.get('milestone')}")
    add_check(checks, "OK", "gate", f"packet={packet_id} {contract.get('gate')}")
    add_check(
        checks,
        "OK",
        "acceptance_claimed",
        f"packet={packet_id} {contract.get('acceptance_claimed')}",
    )
    recorded_full, source_base = verify_revisions(
        root, packet_id, contract, git_exe, current_head, checks
    )
    stage_record = str(contract.get("stage_record") or "")
    verify_required_files(root, packet_id, list(contract.get("required_files") or []), checks)
    verify_manifest(
        root,
        packet_id,
        contract.get("file_manifest"),
        list(contract.get("hash_compare_exclude") or []),
        checks,
        role=contract.get("role"),
        recorded_revision=recorded_full,
        git_exe=git_exe,
    )
    verify_receipts(
        root,
        packet_id,
        contract.get("receipts"),
        bool(contract.get("replay_required")),
        checks,
    )
    for spec in contract.get("json_receipts") or []:
        if isinstance(spec, dict):
            verify_json_receipt(
                root, packet_id, spec, source_base, recorded_full, current_head, checks
            )
        else:
            add_check(checks, "ERROR", "malformed_json_receipt", f"packet={packet_id}")
    verify_phrases(root, packet_id, stage_record, list(contract.get("command_phrases") or []), checks)
    if stage_record:
        record_path = root / posix_join(stage_record)
        milestone = str(contract.get("milestone") or "")
        if record_path.is_file() and milestone:
            text = record_path.read_text(encoding="utf-8")
            # Association is mechanical: the stage record must mention the slice.
            token = "slice 1a" if "1a" in milestone else milestone
            if token.lower() in text.lower():
                add_check(checks, "OK", "milestone_associated", f"packet={packet_id} {stage_record}")
            else:
                add_check(
                    checks,
                    "ERROR",
                    "milestone_not_associated",
                    f"packet={packet_id} {stage_record} does not mention {token!r}",
                )
    verify_seeds_horizons(root, packet_id, contract, checks)
    errors = [item for item in checks if item[0] == "ERROR"]
    return {
        "packet_id": packet_id,
        "contract_path": rel,
        "milestone": contract.get("milestone"),
        "gate": contract.get("gate"),
        "role": contract.get("role"),
        "recorded_revision": recorded_full or contract.get("recorded_revision"),
        "must_match_current_head": bool(contract.get("must_match_current_head")),
        "checks": checks,
        "result": "ERROR" if errors else "OK",
        "error_count": len(errors),
        "check_count": len(checks),
    }


def verify(
    root: Path,
    contract_path: Path | None = None,
    git_exe: str | None | object = Ellipsis,
) -> dict[str, Any]:
    root = root.resolve()
    if git_exe is Ellipsis:
        git_exe = shutil.which("git")
    current_head = git_head(root, git_exe if isinstance(git_exe, str) else None)
    contracts = load_contracts(root, contract_path)
    packets = [
        verify_packet(root, rel, data, git_exe if isinstance(git_exe, str) else None, current_head)
        for rel, data in contracts
    ]
    errors = sum(packet["error_count"] for packet in packets)
    return {
        "repository_root": display_root(root),
        "head": current_head,
        "evidence_verification": "ERROR" if errors else "OK",
        "milestone_acceptance_inferred": UNPROVEN,
        "capability_proven": UNPROVEN,
        "reachability_proven": UNPROVEN,
        "measurement_proven": UNPROVEN,
        "packets": packets,
        "packet_count": len(packets),
        "error_count": errors,
    }


def render(data: dict[str, Any]) -> str:
    lines = [
        "V3 evidence verification",
        "========================",
        f"evidence_verification: {data['evidence_verification']}",
        f"milestone_acceptance_inferred: {data['milestone_acceptance_inferred']}",
        f"capability_proven: {data['capability_proven']}",
        f"reachability_proven: {data['reachability_proven']}",
        f"measurement_proven: {data['measurement_proven']}",
        f"repository_root: {data['repository_root']}",
        f"head: {data['head']}",
        f"packet_count: {data['packet_count']}",
        f"error_count: {data['error_count']}",
        "note: OK means declared receipts exist and recorded identities match; "
        "it is not milestone acceptance and does not prove capability, "
        "reachability, or measurement",
    ]
    for packet in data["packets"]:
        lines.append(f"packet {packet['packet_id']}: {packet['result']}")
        lines.append(f"  contract: {packet['contract_path']}")
        lines.append(f"  milestone: {packet['milestone']}")
        lines.append(f"  gate: {packet['gate']}")
        lines.append(f"  role: {packet['role']}")
        lines.append(f"  recorded_revision: {packet['recorded_revision']}")
        lines.append(f"  must_match_current_head: {packet['must_match_current_head']}")
        lines.append(f"  checks: {packet['check_count']} errors: {packet['error_count']}")
        for status, code, detail in packet["checks"]:
            lines.append(f"  - {status} {code} {detail}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only V3 evidence packet verifier (Phase 2)."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root. Default: discover from the current directory.",
    )
    parser.add_argument(
        "--contract",
        default=None,
        help="Verify a single contract file instead of automation/evidence_contracts/*.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else discover_root(Path.cwd())
        if not root.is_dir():
            raise VerifyError(f"error: repository root is not a directory: {display_root(root)}")
        selected = Path(args.contract) if args.contract else None
        data = verify(root, selected)
    except VerifyError as exc:
        sys.stderr.write(str(exc).rstrip() + "\n")
        return 1
    sys.stdout.write(render(data))
    return 0 if data["evidence_verification"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
