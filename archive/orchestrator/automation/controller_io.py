"""Controller ownership, provenance and immutable request/result records."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

RUNS = Path('evidence/automation-runs')
TRUSTED_ROOT = Path(__file__).resolve().parent.parent


class SafetyError(Exception):
    pass


def python_executable() -> str:
    # A Windows venv redirector may spawn Python before its own process can be
    # assigned to a job. Supervise the native interpreter, not that redirector.
    executable = Path(getattr(sys, '_base_executable', sys.executable)).resolve()
    if not executable.is_file():
        raise SafetyError('native Python interpreter unavailable')
    return str(executable)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SafetyError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path: Path):
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise SafetyError('expected JSON object: ' + str(path))
    return value


def safe_path(root: Path, path: Path) -> Path:
    root = root.resolve()
    if not path.resolve().is_relative_to(root):
        raise SafetyError('path escapes repository: ' + str(path))
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise SafetyError('linked path is not an execution boundary: ' + str(part))
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, value) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def set_status(path: Path, status: str) -> None:
    # Only a newly allocated run is updated; historical paths are never reused.
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(status + '\n')
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def file_lock(root: Path, path: Path):
    """Persistent lock inode; the kernel owns the lease, never a recorded PID."""
    safe_path(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if os.fstat(handle.fileno()).st_nlink != 1:
            raise SafetyError('lock has multiple hard links')
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SafetyError('lock_held_or_unavailable') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    # Never unlink a lock: that would permit locking a replacement inode.


def parse_audit(raw: bytes) -> tuple[list[dict], set[str]]:
    if raw and not raw.endswith(b'\n'):
        raise SafetyError('incomplete historical audit line; review required')
    records = []
    pending = set()
    seen = set()
    for line in raw.splitlines():
        record = json.loads(line, object_pairs_hook=unique)
        if not isinstance(record, dict):
            raise SafetyError('malformed historical audit record')
        records.append(record)
        if record.get('format') != 'v3.controller.audit.1':
            continue  # Retain the earlier unversioned audit as reported history.
        token = record.get('controller_run_id')
        event = record.get('event')
        if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{32}', token):
            raise SafetyError('invalid audit run identity')
        if event == 'START':
            if token in seen or not isinstance(record.get('identity'), dict):
                raise SafetyError('duplicate or malformed audit start')
            seen.add(token)
            pending.add(token)
        elif event == 'TERMINAL':
            if token not in pending or record.get('overall_result') not in {'SUCCESS', 'FAILURE', 'REFUSED', 'INTERRUPTED'}:
                raise SafetyError('audit terminal has no matching start or valid result')
            pending.remove(token)
        elif event == 'REFUSED':
            if token in seen or record.get('overall_result') != 'REFUSED' or record.get('delegation_executed') != 'no':
                raise SafetyError('invalid refusal provenance')
            seen.add(token)
        else:
            raise SafetyError('unknown audit event')
    return records, pending


def append_audit(root: Path, value: dict) -> None:
    path = safe_path(root, root / RUNS / 'orchestrator-audit.jsonl')
    with file_lock(root, root / RUNS / 'orchestrator-audit.guard'):
        raw = path.read_bytes() if path.exists() else b''
        line = json.dumps({**value, 'format': 'v3.controller.audit.1', 'timestamp_ns': time.time_ns()},
                          sort_keys=True).encode('utf-8') + b'\n'
        parse_audit(raw + line)
        with path.open('ab', buffering=0) as handle:
            if handle.write(line) != len(line):
                raise SafetyError('short audit append; review required')
            os.fsync(handle.fileno())


def audit_blocker(root: Path) -> str | None:
    path = safe_path(root, root / RUNS / 'orchestrator-audit.jsonl')
    if not path.exists():
        return None
    _, pending = parse_audit(path.read_bytes())
    return 'unresolved_controller_audit' if pending else None


def git_environment() -> dict:
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['NoDefaultCurrentDirectoryInExePath'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def git(root: Path, *args: str) -> bytes:
    # Never search the inspected repository for an executable.
    search = os.pathsep.join(item for item in os.get_exec_path() if Path(item).is_absolute()
                             and Path(item).resolve() != root.resolve())
    previous = os.environ.get('NoDefaultCurrentDirectoryInExePath')
    os.environ['NoDefaultCurrentDirectoryInExePath'] = '1'
    try:
        executable = shutil.which('git', path=search)
    finally:
        if previous is None:
            os.environ.pop('NoDefaultCurrentDirectoryInExePath', None)
        else:
            os.environ['NoDefaultCurrentDirectoryInExePath'] = previous
    if not executable:
        raise SafetyError('trusted Git executable unavailable')
    result = subprocess.run([executable, '--no-optional-locks', '-C', str(root), *args],
                            env=git_environment(), capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise SafetyError('repository identity unavailable: ' + result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def identity(root: Path) -> dict:
    root = root.resolve()
    top = Path(git(root, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve()
    if top != root:
        raise SafetyError('--root must be the exact repository root')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    branch = git(root, 'rev-parse', '--abbrev-ref', 'HEAD').decode().strip()
    if len(head) != 40 or branch in {'HEAD', '', 'UNKNOWN'}:
        raise SafetyError('repository identity is unknown or detached')
    stage = git(root, 'ls-files', '--stage', '-z').decode('utf-8')
    names = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0')
    files = {}
    for name in sorted(set(names) - {''}):
        if name.startswith(RUNS.as_posix() + '/'):
            continue
        path = safe_path(root, root / name)
        files[name] = sha(path) if path.is_file() else 'MISSING'
    # Registry must be identified even if an unusual ignore file hides it.
    path = safe_path(root, root / 'automation/gate_registry.json')
    files['automation/gate_registry.json'] = sha(path)
    trusted = {path.name: sha(path) for path in sorted((TRUSTED_ROOT / 'automation').glob('*.py'))}
    if head != git(root, 'rev-parse', 'HEAD').decode().strip():
        raise SafetyError('HEAD changed during identity capture')
    return {'root': str(root), 'git_dir': git(root, 'rev-parse', '--absolute-git-dir').decode().strip(),
            'head': head, 'branch': branch, 'index': stage, 'files': files,
            'trusted_root': str(TRUSTED_ROOT), 'trusted_python': trusted,
            'python_executable': python_executable(), 'python_sha256': sha(Path(python_executable()))}
