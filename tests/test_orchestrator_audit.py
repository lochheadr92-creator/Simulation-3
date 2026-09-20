"""Focused structured-record and timeout boundaries with synthetic commands."""
import json
from pathlib import Path
import sys
import subprocess

import pytest

from automation import orchestrator as orch
from automation import orchestrator_execution as control
from automation import controller_io as io
from tests.test_orchestrator_execution import repo, gate, registry


@pytest.mark.parametrize('record', [[], {'format': 'v3.controller.audit.1', 'event': 'UNKNOWN', 'controller_run_id': 'a' * 32},
    {'format': 'v3.controller.audit.1', 'event': 'TERMINAL', 'controller_run_id': 'a' * 32, 'overall_result': 'SUCCESS'}], ids=['array', 'event', 'orphan'])
def test_malformed_audit_prevents_dispatch_and_stays_unchanged(repo, monkeypatch, record):
    path = repo / io.RUNS / 'orchestrator-audit.jsonl'
    path.write_text(json.dumps(record) + '\n', encoding='utf-8')
    original = path.read_bytes()
    monkeypatch.setattr(control, 'run_owned', lambda *a, **k: pytest.fail('malformed audit dispatched'))
    result = orch.execute_run(repo, 'audit-stub', True)
    assert result['overall_result'] == 'REFUSED'
    assert path.read_bytes() == original


@pytest.mark.parametrize('required_check', [False, True], ids=['main', 'check'])
def test_registered_timeout_requires_review(repo, required_check):
    slow = [sys.executable, '-I', '-u', '-c', "import time;print('partial',flush=True);time.sleep(3)"]
    entry = gate(timeout_s=1)
    if required_check:
        entry['required_checks'] = [slow]
    else:
        entry['argv'] = slow
    registry(repo, [entry])
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'INTERRUPTED', report
    assert report['review_required'] == 'yes'
    assert report['mechanical_execution'] == 'INTERRUPTED'
    retry = orch.execute_run(repo, 'audit-stub', True)
    assert retry['overall_result'] == 'REFUSED'


def test_changed_historical_receipt_is_not_silently_trusted(repo, monkeypatch):
    first = orch.execute_run(repo, 'audit-stub', True)
    assert first['overall_result'] == 'SUCCESS', first
    receipt = repo / first['receipt'] / 'command/stdout.txt'
    receipt.with_suffix('.saved').write_bytes(receipt.read_bytes())
    receipt.write_text('changed', encoding='utf-8')
    monkeypatch.setattr(control, 'run_owned', lambda *a, **k: pytest.fail('changed history dispatched'))
    second = orch.execute_run(repo, 'audit-stub', True)
    assert second['overall_result'] == 'REFUSED'
    assert 'audit seal' in second['blocked_reason']


def test_supervised_interpreter_pid_is_the_actual_python_process():
    child = subprocess.Popen([io.python_executable(), '-I', '-S', '-c', 'import os;print(os.getpid())'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    output, error = child.communicate(timeout=3)
    assert child.returncode == 0, error
    assert int(output) == child.pid


def test_outer_timeout_preserves_actual_gate_output_and_blocks_retry(repo, monkeypatch):
    registry(repo, [gate(timeout_s=20, argv=[sys.executable, '-I', '-u', '-c',
        "import time;print('native gate partial output',flush=True);time.sleep(15)"])])
    monkeypatch.setattr(control, 'CHILD_TIMEOUT_S', 4)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'INTERRUPTED', report
    assert report['cleanup_complete'] == 'yes'
    receipt = repo / io.RUNS / 'audit-stub' / report['controller_run_id']
    assert 'native gate partial output' in (receipt / 'command/stdout.txt').read_text()
    assert (receipt / 'STATUS').read_text().strip() == 'IN_PROGRESS'
    assert orch.execute_run(repo, 'audit-stub', True)['overall_result'] == 'REFUSED'


def test_request_rewrite_cannot_authorise_a_changed_registry(repo, monkeypatch):
    original = control.run_owned
    marker = repo / io.RUNS / 'rewritten-request-executed'
    def rewrite(argv, root, attempt, timeout):
        registry(root, [gate(argv=[sys.executable, '-I', '-c',
            'from pathlib import Path;Path(' + repr(str(marker)) + ").write_text('must not execute')"])])
        request = io.read_json(attempt / 'request.json')
        request['identity'] = io.identity(root)
        (attempt / 'request.json').write_text(json.dumps(request), encoding='utf-8')
        return original(argv, root, attempt, timeout)
    monkeypatch.setattr(control, 'run_owned', rewrite)
    report = orch.execute_run(repo, 'audit-stub', True)
    assert report['overall_result'] == 'FAILURE'
    assert not marker.exists()
    assert not (repo / io.RUNS / 'audit-stub').exists()
