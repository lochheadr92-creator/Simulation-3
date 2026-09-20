"""Focused tests for the Phase 1 read-only preflight.

These tests inspect repository tooling. They do not run the kernel, do not
treat a passing suite as milestone completion, and do not write evidence.
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from automation.preflight import collect, main, parse_milestone, render

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT_PATH = REPO_ROOT / "automation" / "preflight.py"
KERNEL = REPO_ROOT / "kernel"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _kernel_hashes() -> dict[str, str]:
    return {
        path.name: _sha256(path)
        for path in sorted(KERNEL.glob("*.py"))
    }


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
    env["GIT_AUTHOR_NAME"] = "preflight-test"
    env["GIT_AUTHOR_EMAIL"] = "preflight-test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "preflight-test"
    env["GIT_COMMITTER_EMAIL"] = "preflight-test@example.invalid"
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )


def _write_minimal_docs(root: Path, *, roadmap_open: bool = True) -> None:
    (root / "AGENTS.md").write_text("authority\n", encoding="utf-8")
    (root / "DOCTRINE.md").write_text("doctrine\n", encoding="utf-8")
    if roadmap_open:
        roadmap = (
            "No stage has passed. Stage 1 is open at slice 1a under\n"
            "owner direction OD-001.\n"
        )
    else:
        roadmap = "This roadmap does not name an active slice.\n"
    (root / "ROADMAP.md").write_text(roadmap, encoding="utf-8")


def _init_repo(root: Path, *, roadmap_open: bool = True) -> None:
    _write_minimal_docs(root, roadmap_open=roadmap_open)
    _git(root, "init")
    _git(root, "config", "user.name", "preflight-test")
    _git(root, "config", "user.email", "preflight-test@example.invalid")
    _git(root, "add", "AGENTS.md", "DOCTRINE.md", "ROADMAP.md")
    _git(root, "commit", "-m", "init")


def test_preflight_source_does_not_import_the_kernel():
    tree = ast.parse(PREFLIGHT_PATH.read_text(encoding="utf-8"), filename=str(PREFLIGHT_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "kernel" not in imported


def test_sim3_state_does_not_claim_a_passed_gate():
    text = (REPO_ROOT / "SIM3_STATE.md").read_text(encoding="utf-8")
    assert "last_accepted_gate: none" in text
    assert "last_accepted_evidence: none" in text
    assert "proven: none independently accepted" in text
    lowered = text.lower()
    assert "stage 1 exit unclaimed" in lowered
    assert "no stage has passed" in lowered
    assert "must not override" in lowered


def test_parse_milestone_stays_unknown_without_authoritative_phrases():
    parsed = parse_milestone("there is code and tests passed", "107 passed, 0 failed")
    assert parsed["current_milestone"] == "UNKNOWN"
    assert parsed["milestone_status"] == "UNKNOWN"
    assert parsed["milestone_completion_inferred"] == "no"


def test_contains_phrase_ignores_case_and_wrapping():
    from automation.preflight import contains_phrase

    wrapped = "in a repository with\nno remote. Nothing else."
    assert contains_phrase(wrapped, "repository with no remote")
    assert contains_phrase(
        "Independent post-repair review is pending.",
        "independent post-repair review is pending",
    )
    assert not contains_phrase("107 passed, 0 failed", "Stage 1 is open at slice 1a")


def test_parse_milestone_reads_roadmap_and_record_phrases():
    roadmap = "No stage has passed. Stage 1 is open at slice 1a under OD-001."
    record = (
        "Only slice 1a is open.\n"
        "Stage 1 remains incomplete.\n"
        "the Stage 1 exit gate is not claimed.\n"
        "independent post-repair review is pending.\n"
        "107 passed, 0 failed.\n"
    )
    parsed = parse_milestone(roadmap, record)
    assert parsed["current_milestone"] == "Stage 1, slice 1a"
    assert "no stage has passed" in parsed["milestone_status"]
    assert "Stage 1 incomplete" in parsed["milestone_status"]
    assert "independent post-repair review pending" in parsed["milestone_status"]
    assert parsed["milestone_completion_inferred"] == "no"
    assert "107 passed" not in parsed["milestone_status"]


def test_collect_on_this_repository_is_deterministic_and_read_only():
    before = _kernel_hashes()
    first = render(collect(REPO_ROOT))
    second = render(collect(REPO_ROOT))
    after = _kernel_hashes()
    assert first == second
    assert before == after
    assert "milestone_completion_inferred: no" in first
    assert "current_milestone: Stage 1, slice 1a" in first
    assert "note: passing tests are not milestone completion" in first
    for section in (
        "repository_root:",
        "branch:",
        "head:",
        "git_status:",
        "dirty_files:",
        "untracked_files:",
        "recent_commits:",
        "authoritative_documents_found:",
        "canonical_file_hashes:",
        "configured_seeds:",
        "configured_horizons:",
        "test_commands:",
        "evidence_directories:",
        "inconsistencies:",
    ):
        assert section in first
    assert "C:\\" not in first.split("repository_root:", 1)[1].splitlines()[0]


def test_preflight_does_not_infer_completion_from_a_green_suite(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    report = render(collect(tmp_path))
    assert "milestone_completion_inferred: no" in report
    assert "preflight_result: PASS" in report
    assert "current_milestone: Stage 1, slice 1a" in report
    assert "107 passed" not in report


def test_missing_git_is_a_blocking_failure(tmp_path: Path):
    _write_minimal_docs(tmp_path)
    data = collect(tmp_path, git_exe=None)
    assert data["preflight_result"] == "FAIL"
    assert data["head"] == "UNKNOWN"
    assert any("git executable not found" in item for item in data["blocking_failures"])
    report = render(data)
    assert "error: git executable not found" in report


def test_missing_authoritative_documents_fail_clearly(tmp_path: Path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "preflight-test")
    _git(tmp_path, "config", "user.email", "preflight-test@example.invalid")
    (tmp_path / "README.md").write_text("empty\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "empty")
    data = collect(tmp_path)
    assert data["preflight_result"] == "FAIL"
    assert data["current_milestone"] == "UNKNOWN"
    assert data["authoritative_documents_missing"] == [
        "AGENTS.md",
        "DOCTRINE.md",
        "ROADMAP.md",
    ]
    report = render(data)
    assert "error: missing authoritative document: AGENTS.md" in report
    assert "missing_authoritative_document AGENTS.md" in report


def test_ancestor_sim3_state_head_is_not_a_mismatch(tmp_path: Path):
    _init_repo(tmp_path)
    first = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()
    (tmp_path / "SIM3_STATE.md").write_text(
        "current_milestone: Stage 1, slice 1a\n"
        f"authoritative_head: {first}\n"
        "last_accepted_gate: none\n",
        encoding="utf-8",
    )
    (tmp_path / "later.txt").write_text("later\n", encoding="utf-8")
    _git(tmp_path, "add", "later.txt")
    _git(tmp_path, "commit", "-m", "later")
    data = collect(tmp_path)
    assert data["head"] != first
    assert not any(item.startswith("sim3_state_head_mismatch") for item in data["inconsistencies"])


def test_stale_sim3_state_head_is_an_inconsistency(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "SIM3_STATE.md").write_text(
        "current_milestone: Stage 1, slice 1a\n"
        "authoritative_head: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
        "last_accepted_gate: none\n",
        encoding="utf-8",
    )
    data = collect(tmp_path)
    assert data["preflight_result"] == "PASS"
    assert any(
        item.startswith("sim3_state_head_mismatch") for item in data["inconsistencies"]
    )


def test_cli_from_repository_root_does_not_mutate_kernel():
    before = _kernel_hashes()
    proc = subprocess.run(
        [sys.executable, "-B", str(PREFLIGHT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    after = _kernel_hashes()
    assert before == after
    assert proc.returncode == 0, proc.stderr
    assert "V3 preflight" in proc.stdout
    assert "milestone_completion_inferred: no" in proc.stdout
    assert proc.stderr == ""


def test_file_manifest_is_not_presented_as_head_or_review():
    data = collect(REPO_ROOT)
    report = render(data)
    assert "file_manifest_base:" not in report
    assert "file_manifest_source_base:" in report
    assert "not a review verdict" in report
    assert "pre-repair revision" in report
    if data["file_manifest_present"] == "yes" and data["head"] not in {"UNKNOWN", ""}:
        assert data["file_manifest_source_base"] != data["head"]


def test_cli_rejects_a_missing_root(tmp_path: Path):
    missing = tmp_path / "no-such-root"
    code = main(["--root", str(missing)])
    assert code == 1
