"""Trusted-runtime resolution, request binding and startup provenance.

Dispatch tests run the real pinned worker in a supervised child and inspect the
receipt files the runner actually wrote; the registered command really is (or
really is not) created by the OS. Parent-side monkeypatches appear only in the
pure policy unit tests and in one standalone-runner interruption test where the
child process is still real. All commands are harmless fixtures in disposable
Git clones. No result here is scientific acceptance.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from automation import controller_io as io
from automation import orchestrator as orch
from automation import orchestrator_execution as control
from automation import orchestrator_worker as worker
from automation import run_gate
from automation import runtime_policy as policy
from tests.test_orchestrator_execution import gate, registry, repo, unit_root  # noqa: F401
from tests.test_run_gate import _init_repo, _write_registry

SOURCE = Path(__file__).resolve().parent.parent
NATIVE = io.python_executable()
NATIVE_SHA = io.sha(Path(NATIVE))


def audit_records(root):
    return [json.loads(line) for line in (root / io.RUNS / 'orchestrator-audit.jsonl').read_text().splitlines()]


def same_file(a, b):
    return Path(a).resolve() == Path(b).resolve()


# --- runtime policy (pure) -------------------------------------------------

def test_py3_prefix_resolves_only_to_the_native_interpreter():
    resolved = policy.resolve_runtime(['py', '-3', 'evidence/x.py', '--flag'])
    assert resolved['policy'] == policy.POLICY_TRUSTED
    assert resolved['registry_argv'] == ['py', '-3', 'evidence/x.py', '--flag']
    assert resolved['matched_prefix'] == ['py', '-3']
    assert resolved['resolved_argv'] == [NATIVE, 'evidence/x.py', '--flag']
    assert resolved['interpreter'] == NATIVE
    assert resolved['interpreter_sha256'] == NATIVE_SHA
    assert Path(NATIVE).is_file()


@pytest.mark.parametrize('argv', [['py'], ['py', '-3'], ['py', '-2', 'x.py'], ['py', '-3.12', 'x.py'],
                                  ['PY.EXE', '-3-64', 'x.py'], ['py', 'x.py'], ['py', '-3', ''], []],
                         ids=['bare', 'no-target', 'py2', 'minor', 'arch', 'no-selector', 'empty-part', 'empty'])
def test_every_other_launcher_form_is_refused(argv):
    with pytest.raises(io.SafetyError, match='runtime policy'):
        policy.resolve_runtime(argv)


def test_non_launcher_argv_runs_verbatim_without_an_interpreter_claim():
    resolved = policy.resolve_runtime([sys.executable, '-c', 'pass'])
    assert resolved['policy'] == policy.POLICY_VERBATIM
    assert resolved['resolved_argv'] == [sys.executable, '-c', 'pass']
    assert resolved['interpreter'] is None and resolved['interpreter_sha256'] is None


def test_recheck_refuses_any_drift_from_the_bound_resolution():
    resolved = policy.resolve_runtime(['py', '-3', 'x.py'])
    policy.recheck_runtime(resolved)
    for key, value in [('interpreter_sha256', '0' * 64), ('resolved_argv', [NATIVE, 'other.py']),
                       ('interpreter', NATIVE + '.other'), ('policy', policy.POLICY_VERBATIM)]:
        with pytest.raises(io.SafetyError, match='runtime policy'):
            policy.recheck_runtime({**resolved, key: value})
    binding = policy.bind_gate_runtime({'argv': ['py', '-3', 'x.py'], 'required_checks': [['py', '-3', 'y.py']]})
    assert [r['resolved_argv'] for r in binding['checks']] == [[NATIVE, 'y.py']]
    policy.check_binding_against_identity(binding, {'python_executable': NATIVE, 'python_sha256': NATIVE_SHA})
    with pytest.raises(io.SafetyError, match='identity snapshot'):
        policy.check_binding_against_identity(binding, {'python_executable': NATIVE, 'python_sha256': '0' * 64})
    with pytest.raises(io.SafetyError, match='identity snapshot'):
        policy.check_binding_against_identity(binding, {'python_executable': NATIVE + '.other', 'python_sha256': NATIVE_SHA})


# --- actual dispatch through the pinned worker ------------------------------

def test_registered_py3_gate_runs_on_the_trusted_interpreter_and_is_bound(repo):
    argv = ['py', '-3', '-c', 'import sys;print("interpreter=" + sys.executable)']
    registry(repo, [gate(argv=argv)])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'SUCCESS', report
    assert (report['dispatch_attempted'], report['command_started'], report['gate_dispatched']) == ('yes', 'yes', 'yes')
    assert report['launch_error'] is None
    assert report['runtime']['command']['policy'] == policy.POLICY_TRUSTED
    receipt = repo / report['receipt']
    stdout = (receipt / 'command/stdout.txt').read_text(encoding='utf-8')
    assert same_file(stdout.strip().split('interpreter=', 1)[1], NATIVE), stdout
    recorded_argv = json.loads((receipt / 'command/argv.json').read_text())
    assert recorded_argv['registry_argv'] == argv
    assert recorded_argv['argv'] == [NATIVE, *argv[2:]]
    assert recorded_argv['runtime']['interpreter_sha256'] == NATIVE_SHA
    launch = json.loads((receipt / 'command/launch.json').read_text())
    assert launch['dispatch_attempted'] is True and launch['command_started'] is True
    assert launch['launch_error'] is None and isinstance(launch['pid'], int) and launch['exit_code'] == 0
    run_json = json.loads((receipt / 'run.json').read_text())
    assert run_json['runtime'] == report['runtime'] and run_json['command_started'] is True
    assert run_json['recorded_command'] == 'harmless fixture only'
    request = io.read_json(repo / io.RUNS / '_orchestrator' / report['controller_run_id'] / 'request.json')
    assert request['runtime'] == report['runtime']
    assert request['runtime']['command']['interpreter'] == request['identity']['python_executable']
    assert request['runtime']['command']['interpreter_sha256'] == request['identity']['python_sha256']
    start, terminal = audit_records(repo)
    assert start['event'] == 'START' and terminal['event'] == 'TERMINAL'
    assert terminal['runtime'] == report['runtime']
    assert (terminal['dispatch_attempted'], terminal['command_started'], terminal['gate_dispatched']) == ('yes', 'yes', 'yes')
    # Registry provenance is untouched: the recorded launcher form is still there.
    assert json.loads((repo / 'automation/gate_registry.json').read_text())['gates'][0]['argv'] == argv


def test_missing_executable_is_recorded_as_not_started(repo, tmp_path):
    missing = str(tmp_path / 'no-such-interpreter.exe')
    registry(repo, [gate(argv=[missing, '-c', 'print(1)'])])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE' and report['mechanical_execution'] == 'FAILURE', report
    assert report['delegation_executed'] == 'yes'
    assert (report['dispatch_attempted'], report['command_started'], report['gate_dispatched']) == ('yes', 'no', 'no')
    assert report['launch_error']['type'] == 'FileNotFoundError'
    assert report['launch_error']['winerror'] == 2 and report['launch_error']['errno'] == 2
    assert report['command_exit_code'] is None
    assert report['evidence'] == 'COMPLETE'  # a complete record of a failed attempt, not a success
    assert report['cleanup_complete'] == 'yes'
    receipt = repo / report['receipt']
    assert (receipt / 'STATUS').read_text().strip() == 'EXECUTION_FAILURE'
    assert json.loads((receipt / 'command/launch.json').read_text()) == {
        'dispatch_attempted': True, 'command_started': False, 'pid': None,
        'launch_error': report['launch_error'], 'exit_code': None, 'timed_out': False}
    assert 'failed to start command' in (receipt / 'command/stderr.txt').read_text()
    assert (receipt / 'command/exit_code.txt').read_text().strip() == ''
    run_json = json.loads((receipt / 'run.json').read_text())
    assert run_json['command_started'] is False and run_json['launch_error'] == report['launch_error']
    response = io.read_json(repo / io.RUNS / '_orchestrator' / report['controller_run_id'] / 'response.json')
    assert (response['dispatch_attempted'], response['command_started'], response['gate_dispatched']) == (True, False, False)
    terminal = audit_records(repo)[1]
    assert (terminal['dispatch_attempted'], terminal['command_started']) == ('yes', 'no')
    assert terminal['launch_error'] == report['launch_error']
    rendered = orch.render_run(report)
    assert 'command_started: no' in rendered and '"winerror": 2' in rendered
    with io.file_lock(repo, repo / io.RUNS / 'orchestrator.guard'):
        pass  # ownership was released after the failed attempt


def test_denied_executable_is_recorded_as_not_started(repo, tmp_path):
    denied = tmp_path / 'directory-not-executable'
    denied.mkdir()
    registry(repo, [gate(argv=[str(denied), '-c', 'print(1)'])])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE', report
    assert (report['dispatch_attempted'], report['command_started'], report['gate_dispatched']) == ('yes', 'no', 'no')
    assert report['launch_error']['type'] == 'PermissionError' and report['launch_error']['winerror'] == 5
    assert report['command_exit_code'] is None and report['cleanup_complete'] == 'yes'
    receipt = repo / report['receipt']
    assert 'Access is denied' in (receipt / 'command/stderr.txt').read_text()
    assert json.loads((receipt / 'command/launch.json').read_text())['command_started'] is False
    assert audit_records(repo)[1]['command_started'] == 'no'


def test_unsupported_launcher_form_refuses_before_any_dispatch(unit_root):
    root, _ = unit_root  # fixture forbids reaching run_owned
    registry(root, [gate(argv=['py', '-2', '-c', 'print(1)'])])
    report = orch.execute_run(root, 'audit-stub', True)
    assert report['overall_result'] == 'REFUSED', report
    assert 'runtime_policy_refused' in report['blocked_reason']
    assert (report['dispatch_attempted'], report['command_started'], report['gate_dispatched']) == ('no', 'no', 'no')
    assert not (root / io.RUNS / '_orchestrator').exists()


def test_dry_run_shows_the_runtime_resolution_without_executing(repo):
    argv = ['py', '-3', 'evidence/stage-01/instrument/fixture_digests.py']
    registry(repo, [gate(argv=argv)])
    proc = subprocess.run([NATIVE, '-I', '-B', '-X', 'utf8', str(SOURCE / 'automation/orchestrator.py'),
                           '--root', str(repo), '--dry-run', '--run', 'audit-stub', '--allow-dirty'],
                          capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert f'registered_command_argv: {json.dumps(argv)}' in out
    assert f'runtime_policy: {policy.POLICY_TRUSTED}' in out
    assert f'runtime_interpreter: {NATIVE}' in out
    assert f'runtime_interpreter_sha256: {NATIVE_SHA}' in out
    assert f'runtime_resolved_command_argv: {json.dumps([NATIVE, argv[2]])}' in out
    assert 'delegation_executed: no' in out and 'receipt_created: no' in out
    assert not (repo / io.RUNS / 'audit-stub').exists()
    assert not (repo / io.RUNS / '_orchestrator').exists()


def test_worker_refuses_a_request_whose_runtime_binding_was_altered(repo):
    """The actual worker function, given a hash-consistent request whose bound
    runtime no longer matches the registry: it must not allocate a receipt."""
    argv = ['py', '-3', '-c', 'print(1)']
    registry(repo, [gate(argv=argv)])
    token = 'c' * 32
    attempt = repo / io.RUNS / '_orchestrator' / token
    attempt.mkdir(parents=True)
    tampered = json.loads(json.dumps(policy.bind_gate_runtime({'argv': argv, 'required_checks': []})))
    tampered['command']['resolved_argv'] = [str(repo / 'not-the-interpreter.exe'), '-c', 'print(1)']
    request = {'format': 'v3.controller.request.1', 'controller_run_id': token, 'gate_id': 'audit-stub',
               'allow_dirty': True, 'identity': io.identity(repo), 'runtime': tampered}
    io.write_once(attempt / 'request.json', request)
    validated = worker.validate_request(attempt / 'request.json', io.sha(attempt / 'request.json'))
    response = worker.execute_request(attempt / 'request.json', validated)
    assert response['error'] and 'runtime' in response['error'], response
    assert response['dispatch_attempted'] is False and response['command_started'] is False
    assert response['result'] is None
    assert not (repo / io.RUNS / 'audit-stub').exists()


def test_run_gate_refuses_a_binding_that_differs_from_its_own_resolution(tmp_path):
    _init_repo(tmp_path)
    reg = _write_registry(tmp_path, ['py', '-3', '-c', 'print(1)'])
    binding = policy.bind_gate_runtime({'argv': ['py', '-3', '-c', 'print(1)'], 'required_checks': []})
    binding['command']['interpreter_sha256'] = '0' * 64
    with pytest.raises(run_gate.RunGateError, match='runtime binding differs'):
        run_gate.run(tmp_path, 'fixture-gate', registry_path=reg, controller_run_id='d' * 32, runtime_binding=binding)
    assert not (tmp_path / run_gate.RUNS_REL / 'fixture-gate').exists()


# --- standalone runner ------------------------------------------------------

def test_standalone_runner_records_a_failed_start_structurally(tmp_path):
    _init_repo(tmp_path)
    reg = _write_registry(tmp_path, [str(tmp_path / 'absent.exe'), '-c', 'print(1)'])
    result = run_gate.run(tmp_path, 'fixture-gate', registry_path=reg)
    assert result['execution'] == 'FAILURE'
    assert result['dispatch_attempted'] is True and result['command_started'] is False
    assert result['launch_error']['type'] == 'FileNotFoundError' and result['command_exit_code'] is None
    run_dir = tmp_path / result['run_dir']
    assert (run_dir / 'STATUS').read_text().strip() == 'EXECUTION_FAILURE'
    assert json.loads((run_dir / 'command/launch.json').read_text())['command_started'] is False
    assert 'failed to start command' in (run_dir / 'command/stderr.txt').read_text()
    assert 'command_started: False' in (run_dir / 'REPORT.txt').read_text()


def test_standalone_runner_resolves_py3_and_keeps_the_registry_argv(tmp_path):
    _init_repo(tmp_path)
    argv = ['py', '-3', '-c', 'import sys;print(sys.executable)']
    reg = _write_registry(tmp_path, argv)
    result = run_gate.run(tmp_path, 'fixture-gate', registry_path=reg)
    assert result['execution'] == 'SUCCESS' and result['command_started'] is True, result
    run_dir = tmp_path / result['run_dir']
    recorded = json.loads((run_dir / 'command/argv.json').read_text())
    assert recorded['registry_argv'] == argv and recorded['argv'] == [NATIVE, *argv[2:]]
    assert same_file((run_dir / 'command/stdout.txt').read_text().strip(), NATIVE)
    assert json.loads(reg.read_text())['gates'][0]['argv'] == argv


def test_standalone_interrupt_kills_the_started_child_and_records_started(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    marker = tmp_path / 'late-marker'
    code = 'import time;from pathlib import Path;time.sleep(2);Path(' + repr(str(marker)) + ').write_text("late")'
    reg = _write_registry(tmp_path, [sys.executable, '-I', '-c', code])
    original = subprocess.Popen.communicate

    def interrupt(self, *args, **kwargs):
        if any('late-marker' in str(part) for part in self.args):
            raise KeyboardInterrupt()  # injected at the runner's wait boundary; the child is real
        return original(self, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, 'communicate', interrupt)
    result = run_gate.run(tmp_path, 'fixture-gate', registry_path=reg)
    assert result['execution'] == 'INTERRUPTED'
    assert result['dispatch_attempted'] is True and result['command_started'] is True
    assert result['launch_error'] is None and result['command_exit_code'] is None
    assert (tmp_path / result['run_dir'] / 'STATUS').read_text().strip() == 'INTERRUPTED'
    time.sleep(2.5)
    assert not marker.exists()


# --- timeout, descendants, lock release on the trusted-runtime path -----------

def test_registered_timeout_after_start_records_started_and_releases_ownership(repo):
    registry(repo, [gate(timeout_s=1, argv=['py', '-3', '-u', '-c',
                                            "import time;print('partial',flush=True);time.sleep(5)"])])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'INTERRUPTED', report
    assert (report['dispatch_attempted'], report['command_started']) == ('yes', 'yes')
    assert report['launch_error'] is None and report['cleanup_complete'] == 'yes'
    receipt = repo / report['receipt']
    launch = json.loads((receipt / 'command/launch.json').read_text())
    assert launch['command_started'] is True and launch['timed_out'] is True and launch['exit_code'] is None
    assert 'partial' in (receipt / 'command/stdout.txt').read_text()
    assert json.loads((receipt / 'command/argv.json').read_text())['argv'][0] == NATIVE
    terminal = audit_records(repo)[1]
    assert terminal['command_started'] == 'yes' and terminal['overall_result'] == 'INTERRUPTED'
    with io.file_lock(repo, repo / io.RUNS / 'orchestrator.guard'):
        pass


def test_trusted_runtime_descendants_are_stopped_on_outer_timeout(repo, monkeypatch, tmp_path):
    late = tmp_path / 'late-marker'
    grandchild = 'import time;from pathlib import Path;time.sleep(5);Path(' + repr(str(late)) + ').write_text("escaped")'
    command = ('import subprocess,sys,time;print("trusted partial",flush=True);'
               'subprocess.Popen([sys.executable,"-I","-c",' + repr(grandchild) + ']);time.sleep(30)')
    registry(repo, [gate(timeout_s=40, argv=['py', '-3', '-u', '-c', command])])
    monkeypatch.setattr(control, 'CHILD_TIMEOUT_S', 6)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'INTERRUPTED', report
    assert report['cleanup_complete'] == 'yes' and report['process']['descendants_left'] is False
    receipt = repo / io.RUNS / 'audit-stub' / report['controller_run_id']
    assert 'trusted partial' in (receipt / 'command/stdout.txt').read_text()
    assert (receipt / 'STATUS').read_text().strip() == 'IN_PROGRESS'
    time.sleep(5.5)
    assert not late.exists()
    with io.file_lock(repo, repo / io.RUNS / 'orchestrator.guard'):
        pass
    assert orch.execute_run(repo, 'audit-stub', True)['overall_result'] == 'REFUSED'
