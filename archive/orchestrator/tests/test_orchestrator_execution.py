"""Phase 4 regressions. All actual commands are harmless fixture commands.

Controller calls run in the instrumented interpreter. CLI tests use the real
pinned worker and synthetic registries in disposable Git clones, never the
project registry. No parent-only mock is counted as child-process proof.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from automation import orchestrator as orch
from automation import orchestrator_execution as control
from automation import controller_io as io
from automation.owned_process import run_owned

SOURCE = Path(__file__).resolve().parent.parent
BASELINE = SOURCE.parent / 'orchestrator-freeze'


def gate(**updates):
    return dict({'id': 'audit-stub', 'acceptance_claimed': False, 'unsafe': [],
                 'argv': [sys.executable, '-I', '-B', '-c', "print('harmless-stub')"],
                 'recorded_command': 'harmless fixture only', 'timeout_s': 10,
                 'required_checks': [], 'watched_prefixes': []}, **updates)


def registry(root, entries=None):
    path = root / 'automation/gate_registry.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'format': orch.REGISTRY_FORMAT, 'gates': entries or [gate()]}), encoding='utf-8')


@pytest.fixture
def repo(tmp_path):
    result = subprocess.run(['git', '-c', 'safe.directory=' + BASELINE.as_posix(),
        '-c', 'safe.directory=C:/dev/03-Living-World-V3/.git/worktrees/orchestrator-freeze',
        'clone', '--no-hardlinks', '--local', '--branch', 'codex/orchestrator-phases-1-3-freeze',
        str(BASELINE), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with (tmp_path / 'evidence/stage-01/RECORD.md').open('a', encoding='utf-8') as record:
        record.write('\nTest-only disposable fixture: harmless fixture only\n')
    registry(tmp_path)
    return tmp_path


@pytest.fixture
def unit_root(tmp_path, monkeypatch):
    registry(tmp_path)
    fields = {'branch': 'fixture', 'head': 'a' * 40, 'preflight_result': 'PASS',
              'current_milestone': 'Stage 1, slice 1a', 'milestone_status': 'open',
              'dirty_files': [], 'untracked_files': [], 'inconsistencies': [], 'blocking_failures': []}
    monkeypatch.setattr(orch, 'spawn_preflight', lambda root: {'ok': True, 'fields': fields, 'error': None})
    def forbidden(*args, **kwargs):
        raise AssertionError('refused request reached the real controller dispatch boundary')
    monkeypatch.setattr(control, 'run_owned', forbidden)
    return tmp_path, fields


@pytest.mark.parametrize('field,value', [
    ('unsafe', None), ('unsafe', False), ('unsafe', 0), ('unsafe', ''), ('unsafe', {}),
    ('acceptance_claimed', None), ('acceptance_claimed', 0), ('acceptance_claimed', 'false'),
    ('argv', []), ('timeout_s', -1), ('required_checks', ['not-argv'])], ids=[str(n) for n in range(11)])
def test_invalid_metadata_never_dispatches(unit_root, field, value):
    root, _ = unit_root
    registry(root, [gate(**{field: value})])
    assert orch.execute_run(root, 'audit-stub', True)['overall_result'] == 'REFUSED'


@pytest.mark.parametrize('entries,requested', [
    ([gate(), gate(unsafe=['mutates_working_tree'])], 'audit-stub'),
    ([gate(id='../escape')], '../escape'),
    ([gate(), gate(id='claimed', acceptance_claimed=True)], 'audit-stub'),
    ([gate(), gate(id='broken', timeout_s=-1)], 'audit-stub'),
    ([gate()], 'unknown'), ([gate(unsafe=['mutates_working_tree'])], 'audit-stub'),
], ids=['duplicate', 'path', 'claim', 'other-malformed', 'unknown', 'unsafe'])
def test_invalid_registry_never_dispatches(unit_root, entries, requested):
    root, _ = unit_root
    registry(root, entries)
    assert orch.execute_run(root, requested, True)['overall_result'] == 'REFUSED'


@pytest.mark.parametrize('issue', ['sim3_state_claims_accepted_gate invented',
    'file_manifest_hash_mismatch kernel/engine.py', 'sim3_state_milestone_mismatch'], ids=['claim', 'hash', 'stage'])
def test_authority_conflict_refuses(unit_root, issue):
    root, fields = unit_root
    fields['inconsistencies'] = [issue]
    assert orch.execute_run(root, 'audit-stub', True)['overall_result'] == 'REFUSED'


@pytest.mark.parametrize('content', ['IN_PROGRESS\n', 'NOT_A_STATUS\n', '', 'EVIDENCE_COMPLETE\nIN_PROGRESS\n',
                                     'INTERRUPTED\n', 'EVIDENCE_INCOMPLETE\n'], ids=['active', 'bad', 'empty', 'multi', 'interrupt', 'incomplete'])
def test_unresolved_receipts_refuse_and_stay_unchanged(unit_root, content):
    root, _ = unit_root
    status = root / orch.RUNS_REL / 'old' / 'run' / 'STATUS'
    status.parent.mkdir(parents=True)
    status.write_text(content, encoding='utf-8')
    assert orch.execute_run(root, 'audit-stub', True)['overall_result'] == 'REFUSED'
    assert status.read_text(encoding='utf-8') == content


def test_dirty_permission_is_not_implicit(unit_root):
    root, fields = unit_root
    fields['dirty_files'] = ['input.txt']
    assert orch.execute_run(root, 'audit-stub', False)['overall_result'] == 'REFUSED'


@pytest.mark.parametrize('code', [0, 1, 2, 3, 7])
def test_actual_success_failure_and_receipt_protocol(repo, code):
    registry(repo, [gate(argv=[sys.executable, '-I', '-B', '-c', "print('partial-output');raise SystemExit(" + str(code) + ')'])])
    report = orch.execute_run(repo, 'audit-stub', True)
    expected = 'SUCCESS' if code == 0 else 'FAILURE'
    assert report['overall_result'] == expected, report
    assert report['mechanical_execution'] == expected, report
    assert report['evidence'] == 'COMPLETE', report
    assert report['gate_dispatched'] == 'yes'
    assert report['milestone_acceptance_inferred'] == 'no'
    receipt = repo / report['receipt']
    assert 'partial-output' in (receipt / 'command/stdout.txt').read_text(encoding='utf-8')
    assert json.loads((receipt / 'run.json').read_text())['command_exit_code'] == code
    records = [json.loads(line) for line in (repo / io.RUNS / 'orchestrator-audit.jsonl').read_text().splitlines()]
    assert [r['event'] for r in records] == ['START', 'TERMINAL']
    assert records[0]['identity']['files']['automation/gate_registry.json']
    assert records[1]['receipt_sha256']


def test_root_cannot_choose_preflight_or_runner(repo):
    for name in ('preflight.py', 'run_gate.py'):
        (repo / 'automation' / name).write_text("from pathlib import Path\nPath('evil-marker').write_text('executed')\n", encoding='utf-8')
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'SUCCESS', report
    assert not (repo / 'evil-marker').exists()


def test_registry_change_during_acquisition_refuses(repo, monkeypatch):
    real = control.file_lock
    @contextmanager
    def change(root, path):
        with real(root, path):
            if path.name == 'orchestrator.guard':
                registry(root, [gate(unsafe=['mutates_working_tree'])])
            yield
    monkeypatch.setattr(control, 'file_lock', change)
    monkeypatch.setattr(control, 'run_owned', lambda *a, **k: pytest.fail('changed registry dispatched'))
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'REFUSED', report


def test_changed_dirty_bytes_require_review(repo):
    (repo / 'input.txt').write_text('before', encoding='utf-8')
    registry(repo, [gate(argv=[sys.executable, '-I', '-c', "from pathlib import Path;Path('input.txt').write_text('after')"])])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE', report
    assert report['identity_changed'] == 'yes'
    assert report['review_required'] == 'yes'


def test_failed_postflight_is_not_success(repo, monkeypatch):
    real = orch.spawn_preflight
    count = 0
    def failing(root):
        nonlocal count
        count += 1
        result = real(root)
        if count >= 3:
            result['ok'] = False
        return result
    monkeypatch.setattr(orch, 'spawn_preflight', failing)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE'
    assert report['review_required'] == 'yes'


@pytest.mark.parametrize('kind', ['missing', 'corrupt', 'foreign'])
def test_actual_receipt_tampering_prevents_success(repo, monkeypatch, kind):
    real = control.run_owned
    def tamper(argv, root, output_dir, timeout):
        outcome = real(argv, root, output_dir, timeout)
        request = io.read_json(output_dir / 'request.json')
        receipt = root / io.RUNS / 'audit-stub' / request['controller_run_id']
        target = receipt / 'run.json'
        original = target.read_bytes()
        (receipt / 'original-run.saved').write_bytes(original)
        if kind == 'missing':
            target.rename(receipt / 'missing-run.saved')
        elif kind == 'corrupt':
            target.write_text('{broken', encoding='utf-8')
        else:
            response = io.read_json(output_dir / 'response.json')
            response['controller_run_id'] = 'f' * 32
            (output_dir / 'response.json').write_text(json.dumps(response), encoding='utf-8')
        return outcome
    monkeypatch.setattr(control, 'run_owned', tamper)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE', report
    assert report['review_required'] == 'yes'


def test_audit_failure_prevents_dispatch(repo, monkeypatch):
    monkeypatch.setattr(control, 'append_audit', lambda *a, **k: (_ for _ in ()).throw(PermissionError('audit unavailable')))
    monkeypatch.setattr(control, 'run_owned', lambda *a, **k: pytest.fail('unrecorded dispatch'))
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['delegation_executed'] == 'no'
    assert report['overall_result'] != 'SUCCESS'


def test_failed_spawn_does_not_claim_execution(repo, monkeypatch):
    monkeypatch.setattr(control, 'run_owned', lambda *a: {
        'started': False, 'returncode': None, 'interrupted': False, 'timed_out': False,
        'cleanup_complete': True, 'descendants_left': False, 'error': 'failed to start'})
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['delegation_executed'] == 'no'
    assert report['gate_dispatched'] == 'no'
    assert report['overall_result'] == 'FAILURE'


def test_legacy_lock_never_signals_pid_or_deletes_evidence(repo):
    child = subprocess.Popen([io.python_executable(), '-I', '-c', 'import time;time.sleep(30)'], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        lock = repo / io.RUNS / 'orchestrator.lock.json'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({'pid': child.pid, 'controller_run_id': 'old'}), encoding='utf-8')
        original = lock.read_bytes()
        report = orch.execute_run(repo, 'audit-stub', True)
        assert report['overall_result'] == 'REFUSED'
        assert child.poll() is None
        assert lock.read_bytes() == original
    finally:
        child.terminate()
        child.wait(timeout=3)


def test_timeout_stops_grandchild_before_releasing_ownership(tmp_path):
    marker = tmp_path / 'late'
    child_code = 'import time;from pathlib import Path;time.sleep(1);Path(' + repr(str(marker)) + ").write_text('late')"
    parent = 'import subprocess,sys,time;print("partial",flush=True);subprocess.Popen([sys.executable,"-I","-c",' + repr(child_code) + ']);time.sleep(5)'
    outcome = run_owned([sys.executable, '-I', '-u', '-c', parent], tmp_path, tmp_path, .4)
    assert outcome['timed_out'], outcome
    assert outcome['cleanup_complete'], outcome
    assert 'partial' in (tmp_path / 'stdout.txt').read_text()
    time.sleep(1.1)
    assert not marker.exists()


def test_keyboard_interrupt_stops_owned_processes(tmp_path, monkeypatch):
    original = subprocess.Popen.wait
    first = True
    def interrupt(self, *args, **kwargs):
        nonlocal first
        if first:
            first = False
            raise KeyboardInterrupt()
        return original(self, *args, **kwargs)
    monkeypatch.setattr(subprocess.Popen, 'wait', interrupt)
    outcome = run_owned([sys.executable, '-I', '-c', 'import time;time.sleep(10)'], tmp_path, tmp_path, 5)
    assert outcome['interrupted'], outcome
    assert outcome['cleanup_complete'], outcome


def cli(root):
    return [io.python_executable(), '-I', '-B', '-X', 'utf8', str(SOURCE / 'automation/orchestrator.py'),
            '--root', str(root), '--run', 'audit-stub', '--allow-dirty']


def wait_for(path, process):
    deadline = time.monotonic() + 10
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(.02)
    assert path.exists(), process.poll()


def test_actual_concurrent_requests_do_not_overlap(repo):
    ready = repo / io.RUNS / 'ready'
    release = repo / io.RUNS / 'release'
    command = ('from pathlib import Path\nimport time\nPath(' + repr(str(ready)) + ").write_text('ready')\n"
               + 'until=time.monotonic()+8\nwhile not Path(' + repr(str(release)) + ').exists() and time.monotonic()<until:time.sleep(.02)')
    registry(repo, [gate(argv=[sys.executable, '-I', '-c', command])])
    first = subprocess.Popen(cli(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        wait_for(ready, first)
        second = subprocess.run(cli(repo), capture_output=True, text=True, timeout=10)
        release.write_text('release', encoding='utf-8')
        output, error = first.communicate(timeout=10)
        assert first.returncode == 0, (output, error)
        assert second.returncode == 2, second.stdout
        assert 'in_progress_receipt_requires_review' in second.stdout
        assert len(list((repo / io.RUNS / 'audit-stub').iterdir())) == 1
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=5)


def test_kernel_lock_is_exclusive_and_not_unlinked(tmp_path):
    lock = tmp_path / 'lease'
    ready = tmp_path / 'ready'
    code = ('import sys,time\nfrom pathlib import Path\nsys.path.insert(0,' + repr(str(SOURCE)) + ')\n'
            'from automation.controller_io import file_lock\nwith file_lock(Path(' + repr(str(tmp_path)) + '),Path(' + repr(str(lock)) + ')):\n'
            ' Path(' + repr(str(ready)) + ").write_text('ready')\n time.sleep(30)")
    child = subprocess.Popen([io.python_executable(), '-I', '-B', '-c', code], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        wait_for(ready, child)
        for _ in range(2):
            with pytest.raises(io.SafetyError, match='lock_held'):
                with io.file_lock(tmp_path, lock):
                    pytest.fail('overlapping ownership')
        assert lock.stat().st_size == 1
        inode = lock.stat().st_ino
    finally:
        child.terminate()
        child.wait(timeout=3)
    # Kernel releases an abandoned handle. No unlink or PID reclamation occurs.
    with io.file_lock(tmp_path, lock):
        assert lock.stat().st_ino == inode
    assert lock.read_bytes() == b'\0'
    assert lock.exists()


def test_controller_crash_stops_descendants_and_preserves_partial_receipts(repo):
    ready = repo / io.RUNS / 'crash-ready'
    late = repo / io.RUNS / 'crash-late'
    grandchild = 'import time;from pathlib import Path;time.sleep(1.5);Path(' + repr(str(late)) + ").write_text('escaped')"
    command = ('import subprocess,sys,time\nfrom pathlib import Path\nprint("partial before controller crash",flush=True)\nsubprocess.Popen([sys.executable,"-I","-c",' + repr(grandchild)
               + '])\nPath(' + repr(str(ready)) + ").write_text('ready')\ntime.sleep(20)")
    registry(repo, [gate(argv=[sys.executable, '-I', '-c', command], timeout_s=30)])
    parent = subprocess.Popen(cli(repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        wait_for(ready, parent)
        parent.kill()  # Only the process this test created; job handle closes.
        parent.wait(timeout=3)
        time.sleep(1.7)
        assert not late.exists()
        receipts = sorted((repo / io.RUNS / 'audit-stub').iterdir())
        assert len(receipts) == 1
        assert 'partial before controller crash' in (receipts[0] / 'command/stdout.txt').read_text()
        before = {p.relative_to(receipts[0]).as_posix(): p.read_bytes() for p in receipts[0].rglob('*') if p.is_file()}
        refusal = subprocess.run(cli(repo), capture_output=True, text=True, timeout=10)
        assert refusal.returncode == 2
        assert 'in_progress_receipt_requires_review' in refusal.stdout
        assert before == {p.relative_to(receipts[0]).as_posix(): p.read_bytes() for p in receipts[0].rglob('*') if p.is_file()}
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=3)


def test_terminal_audit_failure_cannot_be_success_and_blocks_retry(repo, monkeypatch):
    append = control.append_audit
    def fail_terminal(root, record):
        if record.get('event') == 'TERMINAL':
            raise PermissionError('terminal audit unavailable')
        append(root, record)
    monkeypatch.setattr(control, 'append_audit', fail_terminal)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE'
    assert report['review_required'] == 'yes'
    directory = repo / io.RUNS / '_orchestrator' / report['controller_run_id']
    assert (directory / 'STATUS').read_text().strip() == 'IN_PROGRESS'
    second = orch.execute_run(repo, 'audit-stub', True)
    assert second['overall_result'] == 'REFUSED'
    assert second['delegation_executed'] == 'no'


def test_historical_complete_but_corrupt_receipt_refuses(repo, monkeypatch):
    receipt = repo / io.RUNS / 'old' / 'run'
    receipt.mkdir(parents=True)
    (receipt / 'STATUS').write_text('EVIDENCE_COMPLETE\n', encoding='utf-8')
    (receipt / 'run.json').write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(control, 'run_owned', lambda *a, **k: pytest.fail('corrupt historical evidence dispatched'))
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'REFUSED'
    assert (receipt / 'run.json').read_text() == '{broken'


def test_history_is_append_only_across_successful_runs(repo):
    first = orch.execute_run(repo, 'audit-stub', True)
    assert first['overall_result'] == 'SUCCESS', first
    receipt = repo / first['receipt']
    files = {p.relative_to(receipt).as_posix(): p.read_bytes() for p in receipt.rglob('*') if p.is_file()}
    audit = (repo / io.RUNS / 'orchestrator-audit.jsonl').read_bytes()
    second = orch.execute_run(repo, 'audit-stub', True)
    assert second['overall_result'] == 'SUCCESS', second
    assert first['receipt'] != second['receipt']
    assert (repo / io.RUNS / 'orchestrator-audit.jsonl').read_bytes().startswith(audit)
    assert files == {p.relative_to(receipt).as_posix(): p.read_bytes() for p in receipt.rglob('*') if p.is_file()}
