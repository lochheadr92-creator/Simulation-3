"""Focused tests for the Phase 2 evidence verifier.

Mechanical packet checks only. These tests do not run the kernel and do not
treat receipt integrity as capability, reachability, measurement, or acceptance.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from automation.verify_evidence import FORMAT, main, render, verify

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = REPO_ROOT / "automation" / "verify_evidence.py"
KERNEL = REPO_ROOT / "kernel"
REPAIR_CONTRACT = Path("automation") / "evidence_contracts" / "stage-01-repair-1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _kernel_hashes() -> dict[str, str]:
    return {path.name: _sha256(path) for path in sorted(KERNEL.glob("*.py"))}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
    ):
        env.pop(key, None)
    env["GIT_AUTHOR_NAME"] = "verify-test"
    env["GIT_AUTHOR_EMAIL"] = "verify-test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "verify-test"
    env["GIT_COMMITTER_EMAIL"] = "verify-test@example.invalid"
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )


def _init_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.name", "verify-test")
    _git(root, "config", "user.email", "verify-test@example.invalid")
    (root / "AGENTS.md").write_text("authority\n", encoding="utf-8")
    _git(root, "add", "AGENTS.md")
    _git(root, "commit", "-m", "init")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _write_contract(root: Path, name: str, payload: dict) -> Path:
    directory = root / "automation" / "evidence_contracts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _base_contract(head: str, **overrides: object) -> dict:
    data: dict = {
        "format": FORMAT,
        "packet_id": "fixture-packet",
        "milestone": "Stage 1, slice 1a",
        "gate": "none",
        "acceptance_claimed": False,
        "role": "historical",
        "recorded_revision": head,
        "must_match_current_head": False,
        "stage_record": "evidence/stage-01/RECORD.md",
        "required_files": ["evidence/stage-01/RECORD.md"],
        "receipts": {"test_suite": [], "determinism": [], "mutation": [], "replay": []},
        "replay_required": False,
        "command_phrases": ["py -3 -m pytest"],
        "recorded_seeds": [],
        "recorded_horizons": [
            {
                "id": "whole_world_executions_authorised",
                "phrase": "Whole-world executions authorised: 0",
                "in": "evidence/stage-01/RECORD.md",
            }
        ],
    }
    data.update(overrides)
    return data


def test_verifier_source_does_not_import_the_kernel():
    tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"), filename=str(VERIFIER_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "kernel" not in imported


def test_representative_packets_are_mechanically_ok_and_not_acceptance():
    first = verify(REPO_ROOT)
    second = verify(REPO_ROOT)
    assert render(first) == render(second)
    assert first["evidence_verification"] == "OK"
    assert first["milestone_acceptance_inferred"] == "no"
    assert first["capability_proven"] == "no"
    assert first["reachability_proven"] == "no"
    assert first["measurement_proven"] == "no"
    ids = [packet["packet_id"] for packet in first["packets"]]
    assert ids == ["stage-01-attempt-1", "stage-01-repair-1"]
    assert all(packet["result"] == "OK" for packet in first["packets"])
    report = render(first)
    assert "148 passed" not in report
    assert "not milestone acceptance" in report
    repair = next(p for p in first["packets"] if p["packet_id"] == "stage-01-repair-1")
    assert repair["must_match_current_head"] is False
    assert repair["recorded_revision"] != first["head"]


def test_verifier_does_not_mutate_kernel():
    before = _kernel_hashes()
    verify(REPO_ROOT)
    assert _kernel_hashes() == before


def test_repair_contract_skips_amended_docs_and_still_checks_kernel():
    data = verify(REPO_ROOT, REPO_ROOT / REPAIR_CONTRACT)
    codes = [(status, code) for status, code, _detail in data["packets"][0]["checks"]]
    assert ("OK", "manifest_hash_skipped") in codes
    assert ("OK", "manifest_hash_match") in codes
    assert ("ERROR", "manifest_hash_mismatch") not in codes
    skipped = [
        detail
        for status, code, detail in data["packets"][0]["checks"]
        if code == "manifest_hash_skipped"
    ]
    assert any("AGENTS.md" in item for item in skipped)
    assert any("RECORD.md" in item for item in skipped)


def test_missing_required_file_fails(tmp_path: Path):
    head = _init_repo(tmp_path)
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(head, required_files=["evidence/stage-01/RECORD.md", "missing.txt"]),
    )
    data = verify(tmp_path)
    assert data["evidence_verification"] == "ERROR"
    assert data["capability_proven"] == "no"
    assert any(code == "missing_file" for _status, code, _detail in data["packets"][0]["checks"])


def test_malformed_json_receipt_fails(tmp_path: Path):
    head = _init_repo(tmp_path)
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    receipt = tmp_path / "evidence" / "stage-01" / "broken.json"
    receipt.write_text("{not json", encoding="utf-8")
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            head,
            json_receipts=[{"path": "evidence/stage-01/broken.json", "required_keys": ["head"]}],
        ),
    )
    data = verify(tmp_path)
    assert data["evidence_verification"] == "ERROR"
    assert any(code == "malformed_json_receipt" for _status, code, _detail in data["packets"][0]["checks"])


def test_hash_mismatch_fails(tmp_path: Path):
    head = _init_repo(tmp_path)
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    target = tmp_path / "kernel" / "version.py"
    target.parent.mkdir()
    target.write_text('ENGINE_VERSION = "x"\n', encoding="utf-8")
    manifest = tmp_path / "evidence" / "stage-01" / "FILE_MANIFEST.json"
    manifest.write_text(
        json.dumps({"base": head, "sha256": {"kernel/version.py": "0" * 64}}) + "\n",
        encoding="utf-8",
    )
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            head,
            file_manifest="evidence/stage-01/FILE_MANIFEST.json",
            required_files=["evidence/stage-01/RECORD.md", "evidence/stage-01/FILE_MANIFEST.json"],
        ),
    )
    data = verify(tmp_path)
    assert data["evidence_verification"] == "ERROR"
    assert any(code == "manifest_hash_mismatch" for _status, code, _detail in data["packets"][0]["checks"])


def test_current_head_mismatch_is_stale_when_required(tmp_path: Path):
    head = _init_repo(tmp_path)
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            head,
            role="current",
            must_match_current_head=True,
            recorded_revision="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        ),
    )
    data = verify(tmp_path)
    assert data["evidence_verification"] == "ERROR"
    codes = [code for _status, code, _detail in data["packets"][0]["checks"]]
    assert "stale_or_unrelated_head" in codes or "recorded_revision_missing" in codes


def test_historical_packet_may_differ_from_head(tmp_path: Path):
    head = _init_repo(tmp_path)
    (tmp_path / "extra.txt").write_text("later\n", encoding="utf-8")
    _git(tmp_path, "add", "extra.txt")
    _git(tmp_path, "commit", "-m", "later")
    later = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert later != head
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    _write_contract(tmp_path, "packet.json", _base_contract(head, must_match_current_head=False))
    data = verify(tmp_path)
    assert data["evidence_verification"] == "OK"
    assert data["head"] == later
    assert any(
        code == "historical_revision_not_required_to_be_head"
        for _status, code, _detail in data["packets"][0]["checks"]
    )


def test_contract_cannot_claim_acceptance(tmp_path: Path):
    head = _init_repo(tmp_path)
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(head, acceptance_claimed=True),
    )
    code = main(["--root", str(tmp_path)])
    assert code == 1


def test_green_receipt_does_not_prove_capability(tmp_path: Path):
    head = _init_repo(tmp_path)
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    receipt = tmp_path / "evidence" / "stage-01" / "suite.txt"
    receipt.write_text("148 passed in 0.76s\n", encoding="utf-8")
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            head,
            receipts={
                "test_suite": ["evidence/stage-01/suite.txt"],
                "determinism": [],
                "mutation": [],
                "replay": [],
            },
        ),
    )
    data = verify(tmp_path)
    assert data["evidence_verification"] == "OK"
    assert data["capability_proven"] == "no"
    assert data["reachability_proven"] == "no"
    assert data["measurement_proven"] == "no"
    assert data["milestone_acceptance_inferred"] == "no"


def test_cli_from_repository_root():
    before = _kernel_hashes()
    proc = subprocess.run(
        [sys.executable, "-B", str(VERIFIER_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert before == _kernel_hashes()
    assert proc.returncode == 0, proc.stderr
    assert "evidence_verification: OK" in proc.stdout
    assert "capability_proven: no" in proc.stdout
    assert proc.stderr == ""


def _record_and_tracked_kernel(tmp_path: Path) -> tuple[str, Path]:
    record = tmp_path / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\npy -3 -m pytest\n",
        encoding="utf-8",
    )
    target = tmp_path / "kernel" / "version.py"
    target.parent.mkdir()
    target.write_text('ENGINE_VERSION = "recorded"\n', encoding="utf-8")
    _git(tmp_path, "add", "kernel/version.py")
    _git(tmp_path, "commit", "-m", "kernel")
    rev = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    manifest = tmp_path / "evidence" / "stage-01" / "FILE_MANIFEST.json"
    manifest.write_text(
        json.dumps({"base": rev, "sha256": {"kernel/version.py": _sha256(target)}}) + "\n",
        encoding="utf-8",
    )
    return rev, target


def test_historical_manifest_survives_a_later_change_to_a_tracked_file(tmp_path: Path):
    _init_repo(tmp_path)
    rev, target = _record_and_tracked_kernel(tmp_path)
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            rev,
            file_manifest="evidence/stage-01/FILE_MANIFEST.json",
            required_files=["evidence/stage-01/RECORD.md", "evidence/stage-01/FILE_MANIFEST.json"],
        ),
    )
    target.write_text('ENGINE_VERSION = "next-slice"\n', encoding="utf-8")  # a later declared change
    data = verify(tmp_path)
    codes = [(status, code) for status, code, _detail in data["packets"][0]["checks"]]
    assert data["evidence_verification"] == "OK"
    assert ("OK", "manifest_hash_match") in codes
    assert ("OK", "manifest_superseded_in_working_tree") in codes
    assert ("ERROR", "manifest_hash_mismatch") not in codes


def test_historical_manifest_that_disagrees_with_its_revision_still_fails(tmp_path: Path):
    _init_repo(tmp_path)
    rev, _target = _record_and_tracked_kernel(tmp_path)
    manifest = tmp_path / "evidence" / "stage-01" / "FILE_MANIFEST.json"
    manifest.write_text(json.dumps({"base": rev, "sha256": {"kernel/version.py": "0" * 64}}) + "\n", encoding="utf-8")
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            rev,
            file_manifest="evidence/stage-01/FILE_MANIFEST.json",
            required_files=["evidence/stage-01/RECORD.md", "evidence/stage-01/FILE_MANIFEST.json"],
        ),
    )
    data = verify(tmp_path)
    checks = data["packets"][0]["checks"]
    assert data["evidence_verification"] == "ERROR"
    assert any(code == "manifest_hash_mismatch" and "at_revision=" in detail for _s, code, detail in checks)


def test_current_manifest_is_still_checked_against_the_working_tree(tmp_path: Path):
    _init_repo(tmp_path)
    rev, target = _record_and_tracked_kernel(tmp_path)
    _write_contract(
        tmp_path,
        "packet.json",
        _base_contract(
            rev,
            role="current",
            must_match_current_head=True,
            file_manifest="evidence/stage-01/FILE_MANIFEST.json",
            required_files=["evidence/stage-01/RECORD.md", "evidence/stage-01/FILE_MANIFEST.json"],
        ),
    )
    target.write_text('ENGINE_VERSION = "drifted"\n', encoding="utf-8")
    data = verify(tmp_path)
    assert data["evidence_verification"] == "ERROR"
    assert any(code == "manifest_hash_mismatch" for _s, code, _d in data["packets"][0]["checks"])
