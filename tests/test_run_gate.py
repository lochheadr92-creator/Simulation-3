"""Focused tests for the Phase 3 gate runner.

These tests use a temporary registry. They do not treat execution success as
milestone acceptance and do not run the mutating mutation instrument.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from automation.run_gate import EXIT_REFUSED, main, run

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "automation" / "run_gate.py"
KERNEL = REPO_ROOT / "kernel"


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
    env["GIT_AUTHOR_NAME"] = "run-gate-test"
    env["GIT_AUTHOR_EMAIL"] = "run-gate-test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "run-gate-test"
    env["GIT_COMMITTER_EMAIL"] = "run-gate-test@example.invalid"
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
    _git(root, "config", "user.name", "run-gate-test")
    _git(root, "config", "user.email", "run-gate-test@example.invalid")
    (root / "AGENTS.md").write_text("authority\n", encoding="utf-8")
    (root / "DOCTRINE.md").write_text("doctrine\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text(
        "No stage has passed. Stage 1 is open at slice 1a under OD-001.\n",
        encoding="utf-8",
    )
    record = root / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Whole-world executions authorised: 0.\n"
        "py -3 -m pytest\n"
        "py -3 evidence/stage-01/instrument/fixture_digests.py\n",
        encoding="utf-8",
    )
    _git(root, "add", "AGENTS.md", "DOCTRINE.md", "ROADMAP.md", "evidence/stage-01/RECORD.md")
    _git(root, "commit", "-m", "init")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _write_registry(root: Path, argv: list[str], *, unsafe: list[str] | None = None) -> Path:
    payload = {
        "format": "v3.gate.registry.1",
        "note": "test registry",
        "gates": [
            {
                "id": "fixture-gate",
                "milestone": "Stage 1, slice 1a",
                "gate": "none",
                "acceptance_claimed": False,
                "source": "test",
                "recorded_command": "py -3 -m pytest",
                "argv": argv,
                "timeout_s": 30,
                "unsafe": unsafe or [],
                "required_checks": [],
                "watched_prefixes": ["kernel/"],
            }
        ],
    }
    path = root / "automation" / "gate_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", "automation/gate_registry.json")
    _git(root, "commit", "-m", "registry")
    return path


def test_runner_source_does_not_import_the_kernel():
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "kernel" not in imported


def test_list_does_not_claim_acceptance():
    proc = subprocess.run(
        [sys.executable, "-B", str(RUNNER_PATH), "--list"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "stage-01a-fixture-digests" in proc.stdout
    assert "stage-01a-reference-suite" in proc.stdout
    assert "stage-01a-mutation-instrument" in proc.stdout
    assert "acceptance_claimed: False" in proc.stdout
    assert "milestone_acceptance_inferred: no" in proc.stdout


def test_unknown_gate_is_refused():
    code = main(["--root", str(REPO_ROOT), "--gate", "no-such-gate", "--allow-dirty"])
    assert code == EXIT_REFUSED


def test_mutating_registry_entry_is_refused(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(
        tmp_path,
        [sys.executable, "-c", "print('should not run')"],
        unsafe=["mutates_working_tree"],
    )
    marker = tmp_path / "ran.txt"
    result = run(
        tmp_path,
        "fixture-gate",
        registry_path=registry,
    )
    assert result["execution"] == "REFUSED"
    assert result["evidence"] == "INCOMPLETE"
    assert "unsafe" in result["reason"]
    assert not marker.exists()
    assert (tmp_path / result["run_dir"] / "STATUS").read_text(encoding="utf-8").strip() == "REFUSED"


def test_dirty_tree_is_refused_without_allow_dirty(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(tmp_path, [sys.executable, "-c", "print('should not run')"])
    (tmp_path / "stray.txt").write_text("dirty\n", encoding="utf-8")
    result = run(tmp_path, "fixture-gate", allow_dirty=False, registry_path=registry)
    assert result["execution"] == "REFUSED"
    assert "dirty" in result["reason"]
    stdout = tmp_path / result["run_dir"] / "command" / "stdout.txt"
    assert not stdout.exists()


def test_success_packages_evidence_without_proving_the_milestone(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(tmp_path, [sys.executable, "-c", "print('ok-digest')"])
    result = run(tmp_path, "fixture-gate", registry_path=registry)
    assert result["execution"] == "SUCCESS"
    assert result["evidence"] == "COMPLETE"
    assert result["command_exit_code"] == 0
    assert result["milestone_acceptance_inferred"] == "no"
    assert result["capability_proven"] == "no"
    assert result["reachability_proven"] == "no"
    assert result["measurement_proven"] == "no"
    run_dir = tmp_path / result["run_dir"]
    assert (run_dir / "STATUS").read_text(encoding="utf-8").strip() == "EVIDENCE_COMPLETE"
    assert "ok-digest" in (run_dir / "command" / "stdout.txt").read_text(encoding="utf-8")
    assert (run_dir / "command" / "exit_code.txt").read_text(encoding="utf-8").strip() == "0"
    assert (run_dir / "before" / "head.txt").read_text(encoding="utf-8").strip()
    assert (run_dir / "after" / "kernel-hashes.json").is_file()


def test_failed_command_still_packages_evidence(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(
        tmp_path,
        [sys.executable, "-c", "raise SystemExit(7)"],
    )
    result = run(tmp_path, "fixture-gate", registry_path=registry)
    assert result["execution"] == "FAILURE"
    assert result["command_exit_code"] == 7
    run_dir = tmp_path / result["run_dir"]
    assert (run_dir / "STATUS").read_text(encoding="utf-8").strip() == "EXECUTION_FAILURE"
    assert (run_dir / "command" / "stdout.txt").is_file()
    assert (run_dir / "command" / "stderr.txt").is_file()
    assert (run_dir / "command" / "exit_code.txt").read_text(encoding="utf-8").strip() == "7"


def test_rerun_does_not_overwrite_previous_run(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(tmp_path, [sys.executable, "-c", "print('one')"])
    first = run(tmp_path, "fixture-gate", registry_path=registry)
    second = run(tmp_path, "fixture-gate", registry_path=registry)
    assert first["run_dir"] != second["run_dir"]
    first_out = (tmp_path / first["run_dir"] / "command" / "stdout.txt").read_text(encoding="utf-8")
    assert "one" in first_out
    assert (tmp_path / first["run_dir"] / "STATUS").read_text(encoding="utf-8").strip() == "EVIDENCE_COMPLETE"


def test_allow_dirty_records_dirt_and_does_not_stash(tmp_path: Path):
    _init_repo(tmp_path)
    registry = _write_registry(tmp_path, [sys.executable, "-c", "print('ok')"])
    stray = tmp_path / "stray.txt"
    stray.write_text("keep-me\n", encoding="utf-8")
    result = run(tmp_path, "fixture-gate", allow_dirty=True, registry_path=registry)
    assert result["execution"] == "SUCCESS"
    assert stray.read_text(encoding="utf-8") == "keep-me\n"
    dirty = (tmp_path / result["run_dir"] / "before" / "dirty.txt").read_text(encoding="utf-8")
    assert "stray.txt" in dirty


def test_unexpected_kernel_write_is_not_complete(tmp_path: Path):
    head = _init_repo(tmp_path)
    kernel = tmp_path / "kernel"
    kernel.mkdir()
    version = kernel / "version.py"
    version.write_text('ENGINE_VERSION = "keep"\n', encoding="utf-8")
    _git(tmp_path, "add", "kernel/version.py")
    _git(tmp_path, "commit", "-m", "kernel")
    del head
    registry = _write_registry(
        tmp_path,
        [sys.executable, "-c", "open('kernel/version.py','w',encoding='utf-8').write('mutated\\n')"],
    )
    result = run(tmp_path, "fixture-gate", registry_path=registry)
    assert result["execution"] == "SUCCESS"
    assert result["evidence"] == "INCOMPLETE"
    assert result["unexpected_mutations"]
    assert version.read_text(encoding="utf-8") == "mutated\n"


def test_registry_cannot_claim_acceptance(tmp_path: Path):
    _init_repo(tmp_path)
    path = tmp_path / "automation" / "gate_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "format": "v3.gate.registry.1",
                "gates": [
                    {
                        "id": "bad",
                        "acceptance_claimed": True,
                        "argv": [sys.executable, "-c", "print(1)"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    code = main(["--root", str(tmp_path), "--gate", "bad"])
    assert code == EXIT_REFUSED


def test_production_runner_does_not_mutate_kernel_on_list():
    before = _kernel_hashes()
    code = main(["--root", str(REPO_ROOT), "--list"])
    assert code == 0
    assert _kernel_hashes() == before
