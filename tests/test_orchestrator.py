"""Focused tests for the Phases 1-3 read-only orchestrator control plane.

These tests do not execute registered gates, do not import the kernel, and do
not treat local receipts as scientific acceptance.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automation import orchestrator as orch

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCH_PATH = REPO_ROOT / "automation" / "orchestrator.py"
RUNS = REPO_ROOT / "evidence" / "automation-runs"


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
    env["GIT_AUTHOR_NAME"] = "orch-test"
    env["GIT_AUTHOR_EMAIL"] = "orch-test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "orch-test"
    env["GIT_COMMITTER_EMAIL"] = "orch-test@example.invalid"
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.name", "orch-test")
    _git(root, "config", "user.email", "orch-test@example.invalid")
    (root / "AGENTS.md").write_text("authority\n", encoding="utf-8")
    (root / "DOCTRINE.md").write_text("doctrine\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text(
        "No stage has passed. Stage 1 is open at slice 1a under OD-001.\n",
        encoding="utf-8",
    )
    record = root / "evidence" / "stage-01" / "RECORD.md"
    record.parent.mkdir(parents=True)
    record.write_text(
        "Only slice 1a is open. Stage 1 remains incomplete.\n"
        "the Stage 1 exit gate is not claimed.\n"
        "independent post-repair review is pending.\n"
        "Whole-world executions authorised: 0.\n",
        encoding="utf-8",
    )
    (root / "SIM3_STATE.md").write_text(
        "current_milestone: Stage 1, slice 1a\n"
        "milestone_status: open; no stage has passed; Stage 1 incomplete; "
        "Stage 1 exit unclaimed; independent post-repair review pending\n"
        "last_accepted_gate: none\n"
        "proven: none independently accepted\n"
        "parked: Stages 2-6; slices 1b-1d (not authorised)\n"
        "blockers: no owner direction opens slice 1b or Stage 1 exit\n"
        "next_gate: independent post-repair review of the Stage 1a repaired source\n",
        encoding="utf-8",
    )
    _git(root, "add", "AGENTS.md", "DOCTRINE.md", "ROADMAP.md", "evidence/stage-01/RECORD.md", "SIM3_STATE.md")
    _git(root, "commit", "-m", "init")


def _write_registry(root: Path, payload: dict) -> None:
    path = root / "automation" / "gate_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _cli(root: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(ORCH_PATH), "--root", str(root), *flags],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _source_imports() -> set[str]:
    tree = ast.parse(ORCH_PATH.read_text(encoding="utf-8"), filename=str(ORCH_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def test_o7_source_does_not_import_kernel_or_run_gate():
    imported = _source_imports()
    assert "kernel" not in imported
    text = ORCH_PATH.read_text(encoding="utf-8")
    assert "from automation.run_gate" not in text
    assert "import kernel" not in text
    assert "shell=True" not in text


def test_o1_status_does_not_change_git_or_receipts():
    before_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    before_receipts = []
    if RUNS.is_dir():
        before_receipts = sorted(str(p) for p in RUNS.rglob("STATUS"))
    proc = _cli(REPO_ROOT, "--status")
    assert proc.returncode == 0, proc.stderr
    after_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    after_receipts = []
    if RUNS.is_dir():
        after_receipts = sorted(str(p) for p in RUNS.rglob("STATUS"))
    assert after_git == before_git
    assert after_receipts == before_receipts


def test_o2_complete_receipt_does_not_accept_stage_1a(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "stage-01a-fixture-digests",
                    "acceptance_claimed": False,
                    "recorded_command": "py -3 evidence/stage-01/instrument/fixture_digests.py",
                    "unsafe": [],
                }
            ],
        },
    )
    receipt = tmp_path / "evidence" / "automation-runs" / "stage-01a-fixture-digests" / "deadbeef-001"
    receipt.mkdir(parents=True)
    (receipt / "STATUS").write_text("EVIDENCE_COMPLETE\n", encoding="utf-8")
    (receipt / "run.json").write_text(
        json.dumps({"execution": "SUCCESS", "evidence": "COMPLETE"}) + "\n",
        encoding="utf-8",
    )
    proc = _cli(tmp_path, "--status")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "WORKFLOW / MECHANICAL STATE" in out
    assert "SCIENTIFIC / PROJECT STATE — OBSERVED ONLY" in out
    assert "milestone_acceptance_inferred: no" in out
    assert "observed_last_accepted_gate: none" in out
    assert "observed_proven: none independently accepted" in out
    assert "local_receipts_non_authoritative: yes" in out
    assert "not accepted evidence" in out
    assert "EVIDENCE_COMPLETE" in out
    assert "Stage 1a accepted" not in out
    assert "capability_proven: no" in out


def test_o3_mutation_instrument_is_not_eligible_or_runnable():
    proc = _cli(REPO_ROOT, "--explain")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "registered_command_id: stage-01a-mutation-instrument" in out
    block = out.split("registered_command_id: stage-01a-mutation-instrument", 1)[1]
    next_blocks = block.split("registered_command_id:", 1)[0]
    assert "future_orchestration_eligible: no" in next_blocks
    assert "currently_executable: no" in next_blocks
    assert "unsafe: mutates_working_tree,overwrites_historical_instrument_runs" in next_blocks
    assert "runnable: yes" not in next_blocks.lower()
    assert "future_orchestration_eligible: yes" not in next_blocks


def test_o4_scientific_next_is_not_an_executable_registry_id():
    proc = _cli(REPO_ROOT, "--explain")
    out = proc.stdout
    assert "observed_scientific_next: independent post-repair review of the Stage 1a repaired source" in out
    assert "observed_scientific_next_executable: no" in out
    assert "observed_scientific_next_is_registry_id: no" in out
    assert "registered_command_id: independent post-repair review of the Stage 1a repaired source" not in out


def test_o5_o6_does_not_invoke_run_gate_or_create_receipts(monkeypatch):
    seen: list[list[str]] = []
    real = subprocess.run

    def wrapped(args, **kwargs):
        argv = [str(part) for part in args]
        seen.append(argv)
        return real(args, **kwargs)

    monkeypatch.setattr(orch.subprocess, "run", wrapped)
    before = sorted(p.name for p in RUNS.iterdir()) if RUNS.is_dir() else []
    text = orch.render_status(orch.inspect(REPO_ROOT))
    explain = orch.render_explain(orch.inspect(REPO_ROOT))
    after = sorted(p.name for p in RUNS.iterdir()) if RUNS.is_dir() else []
    assert before == after
    assert "run_gate.py" not in " ".join(" ".join(argv) for argv in seen)
    assert not any("--gate" in argv for argv in seen)
    assert "this_phase_executes_registered_commands: no" in text
    assert "invokes_registered_command: no" in explain


def test_o8_malformed_registry_fails_closed(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(tmp_path, {"format": "not-a-registry", "gates": [{"id": "evil", "unsafe": [], "acceptance_claimed": False}]})
    proc = _cli(tmp_path, "--explain")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "registry_status: BLOCKED" in out
    assert "fail_closed: yes" in out
    assert "registered_command_id: evil" not in out
    assert "future_orchestration_eligible: yes" not in out
    assert "currently_executable: no" in out


def test_o9_o10_o11_o12_planes_and_vocabulary():
    proc = _cli(REPO_ROOT, "--status")
    out = proc.stdout
    mech = out.split("SCIENTIFIC / PROJECT STATE — OBSERVED ONLY", 1)[0]
    sci = out.split("SCIENTIFIC / PROJECT STATE — OBSERVED ONLY", 1)[1]
    assert "WORKFLOW / MECHANICAL STATE" in mech
    assert "preflight_result:" in mech
    assert "milestone_acceptance_inferred: no" in sci
    assert "review_verdict: PASS" not in out
    assert "Stage 1a completion: yes" not in out
    assert "not an independent-review verdict" in sci
    assert "observed_last_accepted_gate: none" in sci
    assert "local_receipts_non_authoritative: yes" in mech
    assert "local_receipts_authority: none" in mech
    assert "note: preflight_result PASS is inspection only" in sci


def test_o11_status_and_explain_keep_acceptance_false():
    for flag in ("--status", "--explain"):
        proc = _cli(REPO_ROOT, flag)
        assert proc.returncode == 0, proc.stderr
        assert "milestone_acceptance_inferred: no" in proc.stdout
        assert "capability_proven: no" in proc.stdout
        assert "reachability_proven: no" in proc.stdout
        assert "measurement_proven: no" in proc.stdout
        assert "this_phase_executes_registered_commands: no" in proc.stdout


def test_missing_status_or_explain_does_not_run_a_gate():
    proc = subprocess.run(
        [sys.executable, "-B", str(ORCH_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 2
    assert "is required" in proc.stderr


def test_malformed_receipt_is_unknown_not_repaired(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {"format": "v3.gate.registry.1", "gates": []},
    )
    receipt = tmp_path / "evidence" / "automation-runs" / "x" / "y"
    receipt.mkdir(parents=True)
    (receipt / "STATUS").write_text("NOT_A_REAL_STATUS\n", encoding="utf-8")
    proc = _cli(tmp_path, "--status")
    assert proc.returncode == 0, proc.stderr
    assert "status=UNKNOWN" in proc.stdout
    assert "malformed local receipt" in proc.stdout
    assert (receipt / "STATUS").read_text(encoding="utf-8") == "NOT_A_REAL_STATUS\n"


def _next_block(out: str, registry_id: str) -> str:
    marker = f"id: {registry_id}"
    assert marker in out
    rest = out.split(marker, 1)[1]
    if "[action]" in rest:
        rest = rest.split("[action]", 1)[0]
    if "SCIENTIFIC / PROJECT NEXT" in rest:
        rest = rest.split("SCIENTIFIC / PROJECT NEXT", 1)[0]
    return rest


def test_n1_n2_n3_next_is_read_only_and_does_not_run_gates(monkeypatch):
    seen: list[list[str]] = []
    real = subprocess.run

    def wrapped(args, **kwargs):
        argv = [str(part) for part in args]
        seen.append(argv)
        return real(args, **kwargs)

    monkeypatch.setattr(orch.subprocess, "run", wrapped)
    before_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    before_receipts = sorted(str(p) for p in RUNS.rglob("STATUS")) if RUNS.is_dir() else []
    proc = _cli(REPO_ROOT, "--next")
    assert proc.returncode == 0, proc.stderr
    after_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    after_receipts = sorted(str(p) for p in RUNS.rglob("STATUS")) if RUNS.is_dir() else []
    assert after_git == before_git
    assert after_receipts == before_receipts
    joined = " ".join(" ".join(argv) for argv in seen)
    assert "run_gate.py" not in joined
    assert not any("--gate" in argv for argv in seen)


def test_n4_n5_n6_safe_eligible_mutation_ineligible():
    proc = _cli(REPO_ROOT, "--next")
    out = proc.stdout
    digest = _next_block(out, "stage-01a-fixture-digests")
    assert "mechanically_eligible: yes" in digest
    assert "currently_executable: no" in digest
    assert "execution capability not implemented" in digest
    mutation = _next_block(out, "stage-01a-mutation-instrument")
    assert "mechanically_eligible: no" in mutation
    assert "currently_executable: no" in mutation
    assert "unsafe:" in mutation
    legal = out.split("BLOCKED / INELIGIBLE REGISTERED ACTIONS", 1)[0]
    assert "id: stage-01a-mutation-instrument" not in legal
    assert "id: stage-01a-fixture-digests" in legal
    assert "id: stage-01a-reference-suite" in legal


def test_n7_n8_scientific_next_is_separate_and_not_a_registry_id():
    proc = _cli(REPO_ROOT, "--next")
    out = proc.stdout
    sci = out.split("SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY", 1)[1]
    mech = out.split("SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY", 1)[0]
    assert "observed_scientific_next: independent post-repair review of the Stage 1a repaired source" in sci
    assert "executable: no" in sci
    assert "authority: project/scientific process, not orchestrator registry" in sci
    assert "id: independent post-repair review of the Stage 1a repaired source" not in mech
    assert "registered_command_id: independent post-repair review" not in out


def test_n9_malformed_registry_fails_closed(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {"format": "nope", "gates": [{"id": "invented-from-failure", "unsafe": [], "acceptance_claimed": False}]},
    )
    proc = _cli(tmp_path, "--next")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "legal_mechanical_action_count: 0" in out
    assert "id: invented-from-failure" not in out
    assert "mechanically_eligible: no" in out
    assert "currently_executable: no" in out


def test_n10_acceptance_claimed_true_is_ineligible(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "claimed-gate",
                    "acceptance_claimed": True,
                    "recorded_command": "py -3 -m pytest",
                    "unsafe": [],
                }
            ],
        },
    )
    proc = _cli(tmp_path, "--next")
    out = proc.stdout
    block = _next_block(out, "claimed-gate")
    assert "mechanically_eligible: no" in block
    assert "currently_executable: no" in block
    assert "acceptance_claimed_true" in block
    legal = out.split("BLOCKED / INELIGIBLE REGISTERED ACTIONS", 1)[0]
    assert "id: claimed-gate" not in legal


def test_n11_unknown_unsafe_metadata_is_not_permissive(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "weird-unsafe",
                    "acceptance_claimed": False,
                    "recorded_command": "py -3 -m pytest",
                    "unsafe": "not-a-list",
                }
            ],
        },
    )
    proc = _cli(tmp_path, "--next")
    out = proc.stdout
    block = _next_block(out, "weird-unsafe")
    assert "mechanically_eligible: no" in block
    assert "currently_executable: no" in block
    legal = out.split("BLOCKED / INELIGIBLE REGISTERED ACTIONS", 1)[0]
    assert "id: weird-unsafe" not in legal


def test_n12_complete_receipt_does_not_clear_scientific_review(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "stage-01a-fixture-digests",
                    "acceptance_claimed": False,
                    "recorded_command": "py -3 evidence/stage-01/instrument/fixture_digests.py",
                    "unsafe": [],
                }
            ],
        },
    )
    receipt = tmp_path / "evidence" / "automation-runs" / "stage-01a-fixture-digests" / "deadbeef-001"
    receipt.mkdir(parents=True)
    (receipt / "STATUS").write_text("EVIDENCE_COMPLETE\n", encoding="utf-8")
    proc = _cli(tmp_path, "--next")
    out = proc.stdout
    sci = out.split("SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY", 1)[1]
    assert "independent post-repair review" in sci
    assert "executable: no" in sci
    assert "COMPLETE local receipts are not scientific authority" in sci
    status = _cli(tmp_path, "--status")
    assert "observed_last_accepted_gate: none" in status.stdout
    assert "milestone_acceptance_inferred: no" in sci


def test_n13_n14_preflight_pass_is_not_acceptance():
    proc = _cli(REPO_ROOT, "--next")
    out = proc.stdout
    assert "milestone_acceptance_inferred: no" in out
    assert "capability_proven: no" in out
    assert "observed_slice_1b_authorised: no" in out
    assert "Stage 1a accepted" not in out
    assert "preflight_result PASS is inspection only" in out


def test_n15_no_arbitrary_command_text_as_action_id():
    proc = _cli(REPO_ROOT, "--next")
    mech = proc.stdout.split("SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY", 1)[0]
    ids = [line.split("id: ", 1)[1].strip() for line in mech.splitlines() if line.startswith("id: ")]
    allowed = {
        "stage-01a-reference-suite",
        "stage-01a-fixture-digests",
        "stage-01a-mutation-instrument",
    }
    assert ids
    assert set(ids) <= allowed


def test_n16_repeated_next_is_deterministic():
    first = _cli(REPO_ROOT, "--next").stdout
    second = _cli(REPO_ROOT, "--next").stdout
    assert first == second


def test_n17_status_and_explain_phase1_behaviour_unchanged():
    status = _cli(REPO_ROOT, "--status").stdout
    explain = _cli(REPO_ROOT, "--explain").stdout
    assert "WORKFLOW / MECHANICAL STATE" in status
    assert "SCIENTIFIC / PROJECT STATE — OBSERVED ONLY" in status
    assert "REGISTERED COMMAND SURFACE (MECHANICAL ONLY)" in explain
    assert "this_phase_executes_registered_commands: no" in status
    assert "currently_executable: no" in explain
    assert "WORKFLOW / MECHANICAL ACTIONS" not in status
    assert "WORKFLOW / MECHANICAL ACTIONS" not in explain.split("SCIENTIFIC / PROJECT STATE — OBSERVED ONLY", 1)[0]


def test_n18_next_source_still_avoids_kernel():
    imported = _source_imports()
    assert "kernel" not in imported
    text = ORCH_PATH.read_text(encoding="utf-8")
    assert "from automation.run_gate" not in text


def test_d1_d2_d3_d4_d24_dry_run_resolves_to_run_gate_without_executing():
    before_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    before_receipts = sorted(str(p) for p in RUNS.rglob("STATUS")) if RUNS.is_dir() else []
    proc = _cli(REPO_ROOT, "--dry-run", "--run", "stage-01a-fixture-digests")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "delegation_target: automation/run_gate.py" in out
    assert "--gate" in out
    assert "stage-01a-fixture-digests" in out
    assert "automation/run_gate.py" in out
    assert "evidence/stage-01/instrument/fixture_digests.py" not in out.split("resolved_delegation_argv:", 1)[1]
    assert "delegation_executed: no" in out
    assert "receipt_created: no" in out
    assert "currently_executable: no" in out
    after_git = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    after_receipts = sorted(str(p) for p in RUNS.rglob("STATUS")) if RUNS.is_dir() else []
    assert after_git == before_git
    assert after_receipts == before_receipts


def test_d5_bare_run_refuses_and_does_not_execute(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Bare --run must refuse before starting a subprocess")

    monkeypatch.setattr(orch.subprocess, "run", forbidden)
    assert orch.main(["--run", "stage-01a-fixture-digests"]) == 2
    assert "execution capability not implemented in Phase 3" in capsys.readouterr().err



def test_d6_unknown_id_refuses():
    proc = _cli(REPO_ROOT, "--dry-run", "--run", "not-a-real-id")
    assert proc.returncode == 2
    assert "registered: no" in proc.stdout
    assert "mechanically_eligible: no" in proc.stdout
    assert "delegation_executed: no" in proc.stdout
    assert "unknown_registry_id" in proc.stdout


def test_d7_d8_unsafe_refuses_even_with_allow_dirty():
    for extra in ([], ["--allow-dirty"]):
        proc = _cli(REPO_ROOT, "--dry-run", "--run", "stage-01a-mutation-instrument", *extra)
        assert proc.returncode == 2, proc.stdout
        assert "mechanically_eligible: no" in proc.stdout
        assert "currently_executable: no" in proc.stdout
        assert "unsafe:" in proc.stdout
        assert "delegation_executed: no" in proc.stdout
        argv_line = [line for line in proc.stdout.splitlines() if line.startswith("resolved_delegation_argv:")][0]
        assert "--gate" not in argv_line or argv_line.endswith("[]")


def test_d9_acceptance_claimed_refuses(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "claimed-gate",
                    "acceptance_claimed": True,
                    "recorded_command": "py -3 -m pytest",
                    "unsafe": [],
                }
            ],
        },
    )
    proc = _cli(tmp_path, "--dry-run", "--run", "claimed-gate")
    assert proc.returncode == 2
    assert "mechanically_eligible: no" in proc.stdout
    assert "acceptance_claimed_true" in proc.stdout


def test_d10_malformed_registry_fails_closed(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(tmp_path, {"format": "nope", "gates": [{"id": "stage-01a-fixture-digests", "unsafe": [], "acceptance_claimed": False}]})
    proc = _cli(tmp_path, "--dry-run", "--run", "stage-01a-fixture-digests")
    assert proc.returncode == 2
    assert "mechanically_eligible: no" in proc.stdout
    assert "delegation_executed: no" in proc.stdout


def test_d11_malformed_unsafe_fails_closed(tmp_path: Path):
    _init_repo(tmp_path)
    _write_registry(
        tmp_path,
        {
            "format": "v3.gate.registry.1",
            "gates": [
                {
                    "id": "weird-unsafe",
                    "acceptance_claimed": False,
                    "recorded_command": "py -3 -m pytest",
                    "unsafe": "not-a-list",
                }
            ],
        },
    )
    proc = _cli(tmp_path, "--dry-run", "--run", "weird-unsafe")
    assert proc.returncode == 2
    assert "mechanically_eligible: no" in proc.stdout


def test_d12_extra_argv_is_rejected():
    proc = subprocess.run(
        [sys.executable, "-B", str(ORCH_PATH), "--dry-run", "--run", "stage-01a-fixture-digests", "extra"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode != 0


def test_d13_d14_d15_no_override_flags():
    text = ORCH_PATH.read_text(encoding="utf-8")
    assert "--registry" not in text
    assert "--command" not in text
    assert "force-unsafe" not in text
    assert "shell=True" not in text
    proc = _cli(REPO_ROOT, "--registry", "evil.json")
    assert proc.returncode != 0


def test_d16_d17_dirty_tree_allow_dirty_resolution(tmp_path):
    _init_repo(tmp_path)
    gate = _valid_gate()
    _write_registry(tmp_path, {"format": orch.REGISTRY_FORMAT, "gates": [gate]})
    without = _cli(tmp_path, "--dry-run", "--run", gate["id"])
    assert without.returncode == 0, without.stderr
    assert "future_execution_blocked: yes" in without.stdout
    assert "dirty tree requires explicit --allow-dirty" in without.stdout
    assert "currently_executable: no" in without.stdout
    assert "delegation_executed: no" in without.stdout
    assert "--gate" in without.stdout
    with_flag = _cli(tmp_path, "--dry-run", "--run", gate["id"], "--allow-dirty")
    assert with_flag.returncode == 0, with_flag.stderr
    assert "future_execution_blocked: no" in with_flag.stdout
    assert "--allow-dirty" in with_flag.stdout
    assert "currently_executable: no" in with_flag.stdout
    assert "delegation_executed: no" in with_flag.stdout
    assert "milestone_acceptance_inferred: no" in with_flag.stdout
    assert "scientific_state_changed: no" in with_flag.stdout


def test_d19_d20_exact_id_and_deterministic():
    first = _cli(REPO_ROOT, "--dry-run", "--run", "stage-01a-fixture-digests")
    second = _cli(REPO_ROOT, "--dry-run", "--run", "stage-01a-fixture-digests")
    assert first.stdout == second.stdout
    assert "delegation_gate_id: stage-01a-fixture-digests" in first.stdout
    assert '"--gate", "stage-01a-fixture-digests"' in first.stdout or "'--gate', 'stage-01a-fixture-digests'" in first.stdout


def test_d21_d22_d23_prior_commands_and_no_kernel():
    for flag in ("--status", "--explain", "--next"):
        proc = _cli(REPO_ROOT, flag)
        assert proc.returncode == 0, proc.stderr
        assert "milestone_acceptance_inferred: no" in proc.stdout
        assert "this_phase_executes_registered_commands: no" in proc.stdout
    imported = _source_imports()
    assert "kernel" not in imported


def test_redteam_path_and_shell_ids_are_unknown():
    for bad in (
        "../kernel/engine.py",
        "py -3 -m pytest",
        "stage-01a-fixture-digests;rm",
        "stage-01a-fixture-digests|cat",
        "independent post-repair review of the Stage 1a repaired source",
    ):
        proc = _cli(REPO_ROOT, "--dry-run", "--run", bad)
        assert proc.returncode == 2, bad
        assert "delegation_executed: no" in proc.stdout
        assert "currently_executable: no" in proc.stdout


def test_safe_entry_is_mechanically_eligible_but_not_executable():
    proc = _cli(REPO_ROOT, "--explain")
    out = proc.stdout
    block = out.split("registered_command_id: stage-01a-fixture-digests", 1)[1]
    block = block.split("registered_command_id:", 1)[0]
    assert "future_orchestration_eligible: yes" in block
    assert "currently_executable: no" in block
    assert "not_a_scientific_gate: yes" in block
    assert "mechanical eligibility only" in block


def _valid_gate():
    return json.loads((REPO_ROOT / "automation/gate_registry.json").read_text(encoding="utf-8"))["gates"][1]


def _inspection_with_gate(root, gate):
    _write_registry(root, {"format": orch.REGISTRY_FORMAT, "gates": [gate]})
    return {
        "registry": orch.load_registry(root),
        "preflight": {"ok": True, "fields": {
            "branch": "test", "head": "a" * 40,
            "current_milestone": "Stage 1, slice 1a",
            "milestone_status": "open",
        }},
        "receipts": orch.inspect_receipts(root),
        "dirty": [], "untracked": [],
    }


@pytest.mark.parametrize("value", [None, False, 0, "", {}])
def test_falsey_unsafe_metadata_cannot_become_safe(tmp_path, value):
    gate = _valid_gate()
    gate["unsafe"] = value
    data = _inspection_with_gate(tmp_path, gate)
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


@pytest.mark.parametrize("value", [None, 0, "false", "", [], {}])
def test_acceptance_requires_explicit_boolean_false(tmp_path, value):
    gate = _valid_gate()
    gate["acceptance_claimed"] = value
    data = _inspection_with_gate(tmp_path, gate)
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


@pytest.mark.parametrize("payload", [[], None, 0, "registry"])
def test_non_object_registry_is_blocked_without_traceback(tmp_path, payload):
    _write_registry(tmp_path, payload)
    assert orch.load_registry(tmp_path)["status"] == "BLOCKED"


def test_invalid_utf8_registry_is_blocked(tmp_path):
    _write_registry(tmp_path, {})
    (tmp_path / orch.REGISTRY_REL).write_bytes(b"\xff")
    assert orch.load_registry(tmp_path)["status"] == "BLOCKED"


def test_duplicate_registry_ids_fail_closed(tmp_path):
    gate = _valid_gate()
    unsafe = dict(gate, unsafe=["mutates_working_tree"])
    _write_registry(tmp_path, {"format": orch.REGISTRY_FORMAT, "gates": [gate, unsafe]})
    assert orch.load_registry(tmp_path)["status"] == "BLOCKED"


@pytest.mark.parametrize("gate_id", [42, ["id"], "../gate", "gate;echo", "gate\naccepted: yes", "--status"])
def test_invalid_registry_identity_fails_closed(tmp_path, gate_id):
    gate = dict(_valid_gate(), id=gate_id)
    data = _inspection_with_gate(tmp_path, gate)
    assert orch.resolve_dry_run(data, str(gate_id), True)["mechanically_eligible"] == "no"


@pytest.mark.parametrize("changes", [
    {"argv": []}, {"argv": "python"}, {"argv": [0]},
    {"timeout_s": -1}, {"timeout_s": True}, {"timeout_s": "forever"},
    {"required_checks": ["python"]}, {"watched_prefixes": "kernel/"},
])
def test_malformed_execution_metadata_is_not_eligible(tmp_path, changes):
    gate = dict(_valid_gate(), **changes)
    data = _inspection_with_gate(tmp_path, gate)
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


@pytest.mark.parametrize("content", [b"", b"\xff", b"EVIDENCE_COMPLETE\nIN_PROGRESS\n"])
def test_corrupt_receipt_blocks_future_resolution_without_crashing(tmp_path, content):
    status = tmp_path / orch.RUNS_REL / "gate" / "run" / "STATUS"
    status.parent.mkdir(parents=True)
    status.write_bytes(content)
    gate = _valid_gate()
    data = _inspection_with_gate(tmp_path, gate)
    assert data["receipts"]["malformed"]
    resolved = orch.resolve_dry_run(data, gate["id"], True)
    assert resolved["future_execution_blocked"] == "yes"
    assert status.read_bytes() == content


def test_in_progress_receipt_blocks_even_with_dirty_override(tmp_path):
    status = tmp_path / orch.RUNS_REL / "gate" / "run" / "STATUS"
    status.parent.mkdir(parents=True)
    status.write_text("IN_PROGRESS\n", encoding="utf-8")
    gate = _valid_gate()
    data = _inspection_with_gate(tmp_path, gate)
    assert orch.resolve_dry_run(data, gate["id"], True)["future_execution_blocked"] == "yes"


def test_inspection_root_cannot_replace_trusted_preflight(tmp_path):
    _init_repo(tmp_path)
    impostor = tmp_path / "automation/preflight.py"
    impostor.parent.mkdir()
    impostor.write_text(
        "from pathlib import Path\nPath('unexpected-execution').write_text('ran')\n"
        "print('preflight_result: PASS')\n", encoding="utf-8")
    result = orch.spawn_preflight(tmp_path)
    assert not (tmp_path / "unexpected-execution").exists()
    assert result["fields"]["current_milestone"] == "Stage 1, slice 1a"


@pytest.mark.parametrize("issue", [
    "sim3_state_milestone_mismatch recorded=Stage 2 actual=Stage 1",
    "sim3_state_claims_accepted_gate fabricated",
    "file_manifest_hash_mismatch kernel/engine.py",
    "unopened_stage_record_present evidence/stage-02/RECORD.md",
])
def test_preflight_pass_does_not_override_authority_or_integrity_conflict(tmp_path, issue):
    gate = _valid_gate()
    data = _inspection_with_gate(tmp_path, gate)
    data["preflight"]["fields"]["inconsistencies"] = [issue]
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


def test_missing_authoritative_milestone_is_not_eligible(tmp_path):
    gate = _valid_gate()
    data = _inspection_with_gate(tmp_path, gate)
    data["preflight"]["fields"]["current_milestone"] = "UNKNOWN"
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


def test_cli_utf8_output_does_not_depend_on_parent_encoding():
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp1252")
    proc = subprocess.run([sys.executable, "-B", str(ORCH_PATH), "--next"],
                          cwd=REPO_ROOT, capture_output=True, env=env)
    assert proc.returncode == 0
    assert "SCIENTIFIC / PROJECT NEXT — OBSERVED ONLY" in proc.stdout.decode("utf-8")


@pytest.mark.parametrize("flags", [
    ["--status"], ["--explain"], ["--next"],
    ["--dry-run", "--run", "stage-01a-fixture-digests"],
    ["--dry-run", "--run", "stage-01a-fixture-digests", "--allow-dirty"],
])
def test_all_inspection_modes_only_spawn_pinned_preflight(monkeypatch, capsys, flags):
    real = subprocess.run
    seen = []

    def guarded(argv, **kwargs):
        seen.append(argv)
        assert Path(argv[argv.index("--root") - 1]).resolve() == (REPO_ROOT / "automation/preflight.py").resolve()
        assert "--gate" not in argv
        return real(argv, **kwargs)

    monkeypatch.setattr(orch.subprocess, "run", guarded)
    assert orch.main(flags) == 0
    assert len(seen) == 1
    assert "milestone_acceptance_inferred: no" in capsys.readouterr().out


@pytest.mark.parametrize("flags", [
    ["--status", "--next"], ["--sta"], ["--status", "--allow-dirty"],
    ["--dry-run"], ["--run", "stage-01a-fixture-digests", "--allow-dirty"],
    ["--status", "--run", "stage-01a-fixture-digests"],
    ["--dry-run", "--run", "stage-01a-fixture-digests", "--command", "anything"],
])
def test_invalid_cli_combinations_refuse_before_inspection(monkeypatch, flags):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid CLI must not inspect or spawn")
    monkeypatch.setattr(orch, "inspect", forbidden)
    try:
        code = orch.main(flags)
    except SystemExit as exc:
        code = exc.code
    assert code == 2


def test_duplicate_json_fields_are_not_silently_overwritten(tmp_path):
    _write_registry(tmp_path, {})
    (tmp_path / orch.REGISTRY_REL).write_text(
        '{"format":"v3.gate.registry.1","gates":[],"gates":[]}', encoding="utf-8")
    assert orch.load_registry(tmp_path)["status"] == "BLOCKED"


def test_preflight_failure_is_blocked_even_without_error_text(tmp_path):
    data = _inspection_with_gate(tmp_path, _valid_gate())
    data["preflight"] = {"ok": False, "fields": {}}
    assert orch.derive_workflow_condition(data["preflight"], data["receipts"], data["registry"]) == "blocked"
    assert orch.resolve_dry_run(data, _valid_gate()["id"], True)["mechanically_eligible"] == "no"


def test_unreadable_receipt_directory_is_blocked(monkeypatch, tmp_path):
    original = Path.iterdir
    base = tmp_path / orch.RUNS_REL
    base.mkdir(parents=True)
    def denied(path):
        if path == base:
            raise PermissionError("receipt directory denied")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", denied)
    data = _inspection_with_gate(tmp_path, _valid_gate())
    assert data["receipts"]["malformed"]
    assert orch.resolve_dry_run(data, _valid_gate()["id"], True)["future_execution_blocked"] == "yes"


def test_other_registry_acceptance_claim_prevents_runner_disagreement(tmp_path):
    gate = _valid_gate()
    data = _inspection_with_gate(tmp_path, gate)
    _write_registry(tmp_path, {"format": orch.REGISTRY_FORMAT, "gates": [
        gate, dict(gate, id="claimed", acceptance_claimed=True),
    ]})
    data["registry"] = orch.load_registry(tmp_path)
    assert orch.resolve_dry_run(data, gate["id"], True)["mechanically_eligible"] == "no"


def test_clean_tree_resolution_is_still_not_execution(tmp_path):
    _init_repo(tmp_path)
    gate = _valid_gate()
    _write_registry(tmp_path, {"format": orch.REGISTRY_FORMAT, "gates": [gate]})
    _git(tmp_path, "add", "automation/gate_registry.json")
    _git(tmp_path, "commit", "-m", "registry")
    proc = _cli(tmp_path, "--dry-run", "--run", gate["id"])
    assert proc.returncode == 0, proc.stderr
    assert "future_execution_blocked: no" in proc.stdout
    assert "currently_executable: no" in proc.stdout
    assert not (tmp_path / orch.RUNS_REL).exists()


def test_live_authority_conflict_is_ineligible(tmp_path):
    _init_repo(tmp_path)
    gate = _valid_gate()
    _write_registry(tmp_path, {"format": orch.REGISTRY_FORMAT, "gates": [gate]})
    state = tmp_path / "SIM3_STATE.md"
    state.write_text(state.read_text(encoding="utf-8").replace("last_accepted_gate: none", "last_accepted_gate: invented"), encoding="utf-8")
    proc = _cli(tmp_path, "--dry-run", "--run", gate["id"], "--allow-dirty")
    assert proc.returncode == 2
    assert "sim3_state_claims_accepted_gate" in proc.stdout
    assert "mechanically_eligible: no" in proc.stdout
