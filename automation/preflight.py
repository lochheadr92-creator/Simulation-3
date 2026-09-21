"""Read-only repository preflight for V3 development automation (Phase 1).

Reports git identity, authoritative documents, the recorded active milestone,
canonical file hashes, discoverable test configuration, and obvious
repository-state inconsistencies. It does not run the simulation, does not
infer milestone completion from tests, and does not write project files.

Run from the repository root:

    py -3 automation/preflight.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

AUTHORITATIVE_DOCS = ("AGENTS.md", "DOCTRINE.md", "ROADMAP.md")
STAGE_RECORD_REL = Path("evidence") / "stage-01" / "RECORD.md"
SIM3_STATE_REL = Path("SIM3_STATE.md")
VERSION_REL = Path("kernel") / "version.py"
PYPROJECT_REL = Path("pyproject.toml")
FILE_MANIFEST_REL = Path("evidence") / "stage-01" / "repair-1" / "FILE_MANIFEST.json"
MANIFEST_CONTRACT_REL = Path("automation") / "evidence_contracts" / "stage-01-repair-1.json"
MANIFEST_COMPARE_PREFIXES = ("kernel/", "tests/")
MANIFEST_COMPARE_EXACT = (
    "evidence/stage-01/instrument/mutation_check.py",
)
UNOPENED_STAGE_RECORDS = tuple(
    Path("evidence") / f"stage-{n:02d}" / "RECORD.md" for n in range(2, 7)
)
GIT_OVERRIDE_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)
RECENT_COMMIT_COUNT = 10
HASH_CHUNK = 65536
GIT_TIMEOUT_S = 30

# Explicit phrases from authoritative documents. Absence yields UNKNOWN.
ROADMAP_MILESTONE_PHRASE = "Stage 1 is open at slice 1a"
ROADMAP_NO_STAGE_PASSED = "No stage has passed"
RECORD_SLICE_OPEN = "Only slice 1a is open"
RECORD_STAGE_INCOMPLETE = "Stage 1 remains incomplete"
RECORD_EXIT_UNCLAIMED_PHRASES = (
    "the Stage 1 exit gate is not claimed",
    "Stage 1 exit remains unclaimed",
)
RECORD_REVIEW_PENDING = "independent post-repair review is pending"
RECORD_WORLD_BUDGET = "Whole-world executions authorised: 0"


class PreflightError(Exception):
    """A blocking preflight failure with a stable message."""


def posix_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def display_root(path: Path) -> str:
    return path.resolve().as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_OVERRIDE_VARS:
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def run_git(root: Path, args: list[str], git_exe: str) -> subprocess.CompletedProcess[str]:
    command = [
        git_exe,
        "-C",
        str(root),
        "--no-optional-locks",
        "-c",
        "color.ui=never",
        "-c",
        "core.quotepath=false",
        *args,
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=git_env(),
        timeout=GIT_TIMEOUT_S,
        check=False,
    )


def git_blob_bytes(root: Path, git_exe: str | None, rev: str, rel: str) -> bytes | None:
    """The bytes of `rel` at `rev`, or None if git, the revision or the path is unavailable."""
    if git_exe is None or not rev or not rel:
        return None
    try:
        proc = subprocess.run(
            [git_exe, "-C", str(root), "--no-optional-locks", "show", f"{rev}:{rel}"],
            capture_output=True,
            env=git_env(),
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def discover_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / ".git").exists():
            return candidate
    raise PreflightError(
        f"error: cannot locate repository root from {display_root(start)}; "
        "expected AGENTS.md and a .git directory or file"
    )


def parse_porcelain(text: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    dirty: list[str] = []
    untracked: list[str] = []
    lines = tuple(line for line in text.splitlines() if line)
    for line in lines:
        xy = line[:2]
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if xy == "??":
            untracked.append(path)
        else:
            dirty.append(path)
    return lines, tuple(sorted(dirty)), tuple(sorted(untracked))


def contains_phrase(text: str, phrase: str) -> bool:
    haystack = " ".join(text.split()).lower()
    needle = " ".join(phrase.split()).lower()
    return needle in haystack


def parse_assignment(text: str, name: str) -> str:
    match = re.search(
        rf'^{re.escape(name)}\s*=\s*"([^"]*)"\s*$',
        text,
        re.MULTILINE,
    )
    if match is None:
        return "UNKNOWN"
    return match.group(1)


def parse_sim3_state(text: str) -> dict[str, str]:
    wanted = (
        "current_milestone",
        "milestone_status",
        "authoritative_head",
        "last_accepted_gate",
        "last_accepted_evidence",
        "current_hypothesis",
        "proven",
        "not_proven",
        "parked",
        "blockers",
        "next_gate",
        "authoritative_documents",
        "last_updated",
    )
    fields = {name: "UNKNOWN" for name in wanted}
    for raw in text.splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in fields:
            fields[key] = value.strip() or "UNKNOWN"
    return fields


def parse_milestone(roadmap_text: str, record_text: str | None) -> dict[str, str]:
    milestone = "UNKNOWN"
    status_parts: list[str] = []
    if contains_phrase(roadmap_text, ROADMAP_MILESTONE_PHRASE):
        milestone = "Stage 1, slice 1a"
    if contains_phrase(roadmap_text, ROADMAP_NO_STAGE_PASSED):
        status_parts.append("no stage has passed")
    if record_text is not None:
        if contains_phrase(record_text, RECORD_SLICE_OPEN) and milestone == "UNKNOWN":
            milestone = "Stage 1, slice 1a"
        if contains_phrase(record_text, RECORD_STAGE_INCOMPLETE):
            status_parts.append("Stage 1 incomplete")
        if any(contains_phrase(record_text, phrase) for phrase in RECORD_EXIT_UNCLAIMED_PHRASES):
            status_parts.append("Stage 1 exit unclaimed")
        if contains_phrase(record_text, RECORD_REVIEW_PENDING):
            status_parts.append("independent post-repair review pending")
    if milestone != "UNKNOWN" and "no stage has passed" in status_parts:
        status_parts.insert(0, "open")
    status = "; ".join(status_parts) if status_parts else "UNKNOWN"
    return {
        "current_milestone": milestone,
        "milestone_status": status,
        "milestone_completion_inferred": "no",
    }


def parse_world_budget(record_text: str | None) -> str:
    if record_text is None:
        return "UNKNOWN"
    if contains_phrase(record_text, RECORD_WORLD_BUDGET):
        return "0"
    return "UNKNOWN"


def collect_git(root: Path, git_exe: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "branch": "UNKNOWN",
        "head": "UNKNOWN",
        "git_status": ("UNKNOWN",),
        "dirty_files": (),
        "untracked_files": (),
        "recent_commits": ("UNKNOWN",),
        "failures": [],
        "git_exe": git_exe,
    }
    if git_exe is None:
        result["failures"].append("error: git executable not found; preflight cannot read repository identity")
        return result
    probes = {
        "head": ["rev-parse", "HEAD"],
        "branch": ["rev-parse", "--abbrev-ref", "HEAD"],
        "status": ["status", "--porcelain=v1", "--untracked-files=all"],
        "log": ["log", f"-n{RECENT_COMMIT_COUNT}", "--format=%H %s"],
    }
    outputs: dict[str, str] = {}
    for name, args in probes.items():
        try:
            proc = run_git(root, args, git_exe)
        except subprocess.TimeoutExpired:
            result["failures"].append(f"error: git {' '.join(args)} timed out")
            return result
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            result["failures"].append(f"error: git {' '.join(args)} failed: {detail}")
            return result
        outputs[name] = proc.stdout
    result["head"] = outputs["head"].strip() or "UNKNOWN"
    result["branch"] = outputs["branch"].strip() or "UNKNOWN"
    porcelain, dirty, untracked = parse_porcelain(outputs["status"])
    result["git_status"] = porcelain if porcelain else ("clean",)
    result["dirty_files"] = dirty
    result["untracked_files"] = untracked
    commits = tuple(line for line in outputs["log"].splitlines() if line.strip())
    result["recent_commits"] = commits if commits else ("UNKNOWN",)
    return result


def collect_canonical_hashes(root: Path) -> list[str]:
    paths = [root / name for name in AUTHORITATIVE_DOCS]
    kernel = root / "kernel"
    if kernel.is_dir():
        paths.extend(sorted(p for p in kernel.glob("*.py") if p.name != "__init__.py"))
        init_py = kernel / "__init__.py"
        if init_py.is_file():
            paths.append(init_py)
    state_path = root / SIM3_STATE_REL
    if state_path.is_file():
        paths.append(state_path)
    lines: list[str] = []
    seen: set[str] = set()
    for path in paths:
        rel = posix_rel(path, root)
        if rel in seen:
            continue
        seen.add(rel)
        if not path.is_file():
            lines.append(f"{rel}  MISSING")
            continue
        lines.append(f"{rel}  sha256:{sha256_file(path)}")
    return sorted(lines)


def manifest_recorded_revision(root: Path) -> str:
    """The revision at which the Repair 1 manifest's hashes were recorded.

    Read from the packet's evidence contract, which owns that fact; the manifest
    itself only names the pre-repair source base.
    """
    try:
        payload = json.loads((root / MANIFEST_CONTRACT_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = payload.get("recorded_revision") if isinstance(payload, dict) else None
    return str(value) if isinstance(value, str) else ""


def compare_file_manifest(root: Path, git_exe: str | None = None) -> dict[str, Any]:
    """Check the historical manifest against the bytes it recorded.

    A historical packet asserts what its files were at its recorded revision.
    With git available those blobs are compared, so a later, declared kernel
    change (a new slice) is reported as `superseded`, not as an inconsistency.
    A mismatch against the recorded revision means the evidence and history
    disagree, which is an inconsistency. Without git, or for entries not
    tracked at that revision, the working tree is compared as before.
    """
    path = root / FILE_MANIFEST_REL
    info: dict[str, Any] = {
        "path": FILE_MANIFEST_REL.as_posix(),
        "present": path.is_file(),
        "source_base": "UNKNOWN",
        "recorded_revision": "UNKNOWN",
        "compared_against": "working tree",
        "compared": 0,
        "matched": 0,
        "superseded": [],
        "mismatches": [],
        "unreadable": None,
        "compared_subset": (
            "kernel/*, tests/*, evidence/stage-01/instrument/mutation_check.py "
            "from the Repair 1 sha256 map (repaired file bytes), compared against "
            "the packet's recorded revision when git can read it, else the working "
            "tree. source_base is the pre-repair revision the repair was applied to, "
            "not HEAD and not a review verdict. Entries that differ in the working "
            "tree after matching at the recorded revision are listed as superseded, "
            "which is information, not an inconsistency. Other manifest entries, "
            "including AGENTS.md and RECORD.md, are not compared."
        ),
    }
    if not path.is_file():
        return info
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        info["unreadable"] = str(exc)
        return info
    info["source_base"] = str(payload.get("base") or "UNKNOWN")
    hashes = payload.get("sha256")
    if not isinstance(hashes, dict):
        info["unreadable"] = "sha256 map missing"
        return info
    revision = manifest_recorded_revision(root) if git_exe else ""
    if revision:
        info["recorded_revision"] = revision
    for rel, expected in sorted(hashes.items()):
        if not (
            rel.startswith(MANIFEST_COMPARE_PREFIXES)
            or rel in MANIFEST_COMPARE_EXACT
        ):
            continue
        current = root / Path(*rel.split("/"))
        blob = git_blob_bytes(root, git_exe, revision, rel) if revision else None
        if blob is not None:
            info["compared_against"] = f"recorded revision {revision}"
            info["compared"] += 1
            at_revision = sha256_bytes(blob)
            if at_revision == expected:
                info["matched"] += 1
                if not current.is_file() or sha256_file(current) != expected:
                    info["superseded"].append(rel)
            else:
                info["mismatches"].append(
                    f"{rel}  recorded={expected} at_revision={at_revision}"
                )
            continue
        if not current.is_file():
            info["compared"] += 1
            info["mismatches"].append(f"{rel}  recorded={expected} actual=MISSING")
            continue
        actual = sha256_file(current)
        info["compared"] += 1
        if actual == expected:
            info["matched"] += 1
        else:
            info["mismatches"].append(
                f"{rel}  recorded={expected} actual={actual}"
            )
    return info


def collect_pytest_config(root: Path) -> dict[str, str]:
    path = root / PYPROJECT_REL
    if not path.is_file():
        return {
            "present": "no",
            "testpaths": "UNKNOWN",
            "pythonpath": "UNKNOWN",
        }
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {
            "present": "unreadable",
            "testpaths": "UNKNOWN",
            "pythonpath": "UNKNOWN",
        }
    options = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    testpaths = options.get("testpaths", "UNKNOWN")
    pythonpath = options.get("pythonpath", "UNKNOWN")
    if isinstance(testpaths, list):
        testpaths = ", ".join(str(item) for item in testpaths)
    if isinstance(pythonpath, list):
        pythonpath = ", ".join(str(item) for item in pythonpath)
    return {
        "present": "yes",
        "testpaths": str(testpaths),
        "pythonpath": str(pythonpath),
    }


def collect_test_commands(root: Path) -> list[str]:
    commands = ["py -3 -m pytest"]
    fixture = root / "evidence" / "stage-01" / "instrument" / "fixture_digests.py"
    mutation = root / "evidence" / "stage-01" / "instrument" / "mutation_check.py"
    if fixture.is_file():
        commands.append("py -3 evidence/stage-01/instrument/fixture_digests.py")
    if mutation.is_file():
        commands.append(
            "py -3 evidence/stage-01/instrument/mutation_check.py  "
            "# mutates working tree; not part of preflight"
        )
    return commands


def collect_evidence_directories(root: Path) -> list[str]:
    evidence = root / "evidence"
    if not evidence.is_dir():
        return []
    found = [posix_rel(evidence, root) + "/"]
    for dirpath, dirnames, _filenames in os.walk(evidence):
        dirnames[:] = sorted(name for name in dirnames if name != "__pycache__")
        for name in dirnames:
            found.append(posix_rel(Path(dirpath) / name, root) + "/")
    return sorted(set(found))


def collect_inconsistencies(
    root: Path,
    git_info: dict[str, Any],
    milestone: dict[str, str],
    sim3_fields: dict[str, str] | None,
    sim3_present: bool,
    missing_docs: list[str],
    record_text: str | None,
    manifest: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    for name in missing_docs:
        notes.append(f"missing_authoritative_document {name}")
    record_path = root / STAGE_RECORD_REL
    if milestone["current_milestone"] == "Stage 1, slice 1a" and not record_path.is_file():
        notes.append("missing_stage_record evidence/stage-01/RECORD.md")
    for extra in UNOPENED_STAGE_RECORDS:
        if (root / extra).is_file():
            notes.append(f"unopened_stage_record_present {extra.as_posix()}")
    if sim3_present and sim3_fields is not None:
        recorded_head = sim3_fields.get("authoritative_head", "UNKNOWN")
        actual_head = git_info.get("head", "UNKNOWN")
        if recorded_head != "UNKNOWN" and actual_head != "UNKNOWN" and recorded_head != actual_head:
            ancestor = False
            git_exe = git_info.get("git_exe")
            if isinstance(git_exe, str) and recorded_head and actual_head:
                proc = run_git(
                    root,
                    ["merge-base", "--is-ancestor", recorded_head, actual_head],
                    git_exe,
                )
                ancestor = proc.returncode == 0
            if not ancestor:
                notes.append(
                    f"sim3_state_head_mismatch recorded={recorded_head} actual={actual_head}"
                )
        recorded_milestone = sim3_fields.get("current_milestone", "UNKNOWN")
        actual_milestone = milestone["current_milestone"]
        if (
            recorded_milestone != "UNKNOWN"
            and actual_milestone != "UNKNOWN"
            and recorded_milestone != actual_milestone
        ):
            notes.append(
                "sim3_state_milestone_mismatch "
                f"recorded={recorded_milestone} actual={actual_milestone}"
            )
        if sim3_fields.get("last_accepted_gate", "").lower() not in {"none", "UNKNOWN".lower()}:
            # A claimed accepted gate is not independently verified here.
            notes.append(
                "sim3_state_claims_accepted_gate "
                f"{sim3_fields.get('last_accepted_gate', 'UNKNOWN')}"
            )
    if record_text is not None and contains_phrase(record_text, "repository with no remote"):
        notes.append(
            "record_rollback_describes_no_remote "
            "evidence/stage-01/RECORD.md rollback text still describes a repository with no remote"
        )
    review_packet = (
        root / "evidence" / "stage-01" / "repair-1" / "review-before-repair" / "REVIEW.md"
    )
    if record_text is not None and review_packet.is_file():
        card_line = None
        for line in record_text.splitlines():
            if line.startswith("| State |") and "Review status:" in line:
                card_line = line
                break
        if card_line and contains_phrase(card_line, "no independent review requested or held"):
            notes.append(
                "stage_card_review_status_stale "
                "card still says no independent review was held; "
                "evidence/stage-01/repair-1/review-before-repair/REVIEW.md exists"
            )
    if manifest.get("unreadable"):
        notes.append(f"file_manifest_unreadable {manifest['unreadable']}")
    for mismatch in manifest.get("mismatches") or []:
        notes.append(f"file_manifest_hash_mismatch {mismatch}")
    return sorted(notes)


def collect(root: Path, git_exe: str | None | object = Ellipsis) -> dict[str, Any]:
    root = root.resolve()
    failures: list[str] = []
    if git_exe is Ellipsis:
        git_exe = shutil.which("git")
    git_info = collect_git(root, git_exe if isinstance(git_exe, str) or git_exe is None else None)
    failures.extend(git_info["failures"])

    found_docs = [name for name in AUTHORITATIVE_DOCS if (root / name).is_file()]
    missing_docs = [name for name in AUTHORITATIVE_DOCS if name not in found_docs]
    for name in missing_docs:
        failures.append(f"error: missing authoritative document: {name}")
    record_path = root / STAGE_RECORD_REL
    if record_path.is_file():
        found_docs.append(STAGE_RECORD_REL.as_posix())
    found_docs = sorted(dict.fromkeys(found_docs))

    roadmap_text = (root / "ROADMAP.md").read_text(encoding="utf-8") if (root / "ROADMAP.md").is_file() else ""
    record_text = record_path.read_text(encoding="utf-8") if record_path.is_file() else None
    milestone = parse_milestone(roadmap_text, record_text)

    version_path = root / VERSION_REL
    if version_path.is_file():
        version_text = version_path.read_text(encoding="utf-8")
        engine_version = parse_assignment(version_text, "ENGINE_VERSION")
        schema_version = parse_assignment(version_text, "SCHEMA_VERSION")
    else:
        engine_version = "UNKNOWN"
        schema_version = "UNKNOWN"

    sim3_path = root / SIM3_STATE_REL
    sim3_present = sim3_path.is_file()
    sim3_fields = parse_sim3_state(sim3_path.read_text(encoding="utf-8")) if sim3_present else None

    manifest = compare_file_manifest(root, git_info.get("git_exe"))
    pytest_config = collect_pytest_config(root)
    inconsistencies = collect_inconsistencies(
        root,
        git_info,
        milestone,
        sim3_fields,
        sim3_present,
        missing_docs,
        record_text,
        manifest,
    )

    experiments_dir = root / "experiments"
    seeds = "none discovered"
    horizons = "none discovered"
    world_budget = parse_world_budget(record_text)

    return {
        "repository_root": display_root(root),
        "branch": git_info["branch"],
        "head": git_info["head"],
        "git_status": list(git_info["git_status"]),
        "dirty_files": list(git_info["dirty_files"]),
        "untracked_files": list(git_info["untracked_files"]),
        "recent_commits": list(git_info["recent_commits"]),
        "authoritative_documents_found": found_docs,
        "authoritative_documents_missing": missing_docs,
        "current_milestone": milestone["current_milestone"],
        "milestone_status": milestone["milestone_status"],
        "milestone_completion_inferred": "no",
        "engine_version": engine_version,
        "schema_version": schema_version,
        "canonical_file_hashes": collect_canonical_hashes(root),
        "file_manifest_path": manifest["path"],
        "file_manifest_present": "yes" if manifest["present"] else "no",
        "file_manifest_source_base": manifest["source_base"],
        "file_manifest_compared_subset": manifest["compared_subset"],
        "file_manifest_compared": str(manifest["compared"]),
        "file_manifest_matched": str(manifest["matched"]),
        "file_manifest_recorded_revision": manifest["recorded_revision"],
        "file_manifest_compared_against": manifest["compared_against"],
        "file_manifest_superseded_in_working_tree": list(manifest["superseded"]),
        "configured_seeds": seeds,
        "configured_horizons": horizons,
        "active_slice_whole_world_executions_authorised": world_budget,
        "experiments_directory": "present" if experiments_dir.is_dir() else "none",
        "test_commands": collect_test_commands(root),
        "pytest_present": pytest_config["present"],
        "pytest_testpaths": pytest_config["testpaths"],
        "pytest_pythonpath": pytest_config["pythonpath"],
        "evidence_directories": collect_evidence_directories(root),
        "sim3_state_present": "yes" if sim3_present else "no",
        "sim3_state": sim3_fields or {},
        "inconsistencies": inconsistencies,
        "blocking_failures": failures,
        "preflight_result": "FAIL" if failures else "PASS",
    }


def _emit_list(name: str, items: list[str] | tuple[str, ...]) -> list[str]:
    if not items:
        return [f"{name}: (none)"]
    lines = [f"{name}:"]
    for item in items:
        lines.append(f"  - {item}")
    return lines


def render(data: dict[str, Any]) -> str:
    lines = [
        "V3 preflight",
        "============",
        f"preflight_result: {data['preflight_result']}",
        f"milestone_completion_inferred: {data['milestone_completion_inferred']}",
        *_emit_list("blocking_failures", data["blocking_failures"]),
        f"repository_root: {data['repository_root']}",
        f"branch: {data['branch']}",
        f"head: {data['head']}",
        *_emit_list("git_status", data["git_status"]),
        *_emit_list("dirty_files", data["dirty_files"]),
        *_emit_list("untracked_files", data["untracked_files"]),
        *_emit_list("recent_commits", data["recent_commits"]),
        *_emit_list("authoritative_documents_found", data["authoritative_documents_found"]),
        *_emit_list("authoritative_documents_missing", data["authoritative_documents_missing"]),
        f"current_milestone: {data['current_milestone']}",
        f"milestone_status: {data['milestone_status']}",
        f"engine_version: {data['engine_version']}",
        f"schema_version: {data['schema_version']}",
        *_emit_list("canonical_file_hashes", data["canonical_file_hashes"]),
        f"file_manifest_path: {data['file_manifest_path']}",
        f"file_manifest_present: {data['file_manifest_present']}",
        f"file_manifest_source_base: {data['file_manifest_source_base']}",
        f"file_manifest_compared_subset: {data['file_manifest_compared_subset']}",
        f"file_manifest_compared: {data['file_manifest_compared']}",
        f"file_manifest_matched: {data['file_manifest_matched']}",
        f"file_manifest_recorded_revision: {data['file_manifest_recorded_revision']}",
        f"file_manifest_compared_against: {data['file_manifest_compared_against']}",
        *_emit_list("file_manifest_superseded_in_working_tree", data["file_manifest_superseded_in_working_tree"]),
        f"configured_seeds: {data['configured_seeds']}",
        f"configured_horizons: {data['configured_horizons']}",
        (
            "active_slice_whole_world_executions_authorised: "
            f"{data['active_slice_whole_world_executions_authorised']}"
        ),
        f"experiments_directory: {data['experiments_directory']}",
        *_emit_list("test_commands", data["test_commands"]),
        f"pytest_present: {data['pytest_present']}",
        f"pytest_testpaths: {data['pytest_testpaths']}",
        f"pytest_pythonpath: {data['pytest_pythonpath']}",
        *_emit_list("evidence_directories", data["evidence_directories"]),
        f"sim3_state_present: {data['sim3_state_present']}",
    ]
    if data["sim3_state"]:
        for key in sorted(data["sim3_state"]):
            lines.append(f"sim3_state.{key}: {data['sim3_state'][key]}")
    lines.extend(_emit_list("inconsistencies", data["inconsistencies"]))
    lines.append(
        "note: passing tests are not milestone completion; "
        "this report does not run the simulation"
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only V3 repository preflight (Phase 1)."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root. Default: discover from the current directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else discover_root(Path.cwd())
        if not root.is_dir():
            raise PreflightError(f"error: repository root is not a directory: {display_root(root)}")
        data = collect(root)
    except PreflightError as exc:
        sys.stderr.write(str(exc).rstrip() + "\n")
        return 1
    sys.stdout.write(render(data))
    if data["blocking_failures"]:
        for item in data["blocking_failures"]:
            sys.stderr.write(item.rstrip() + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
