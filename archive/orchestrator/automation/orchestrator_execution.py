"""Phase 4 control boundary; scientific authority is never inferred."""
from __future__ import annotations

from pathlib import Path
import uuid

from automation.controller_io import (
    RUNS, SafetyError, append_audit, audit_blocker, file_lock, parse_audit,
    identity, read_json, safe_path, set_status, sha, write_once,
)
from automation.owned_process import run_owned
from automation.runtime_policy import check_binding_against_identity
from automation.verify_evidence import verify

CHILD_TIMEOUT_S = 600


def verify_history(root: Path) -> None:
    """A COMPLETE marker alone cannot clear a malformed historical package."""
    base = root / RUNS
    if not base.exists():
        return
    audit = base / 'orchestrator-audit.jsonl'
    records, _ = parse_audit(audit.read_bytes()) if audit.exists() else ([], set())
    seals = {record['receipt']: record['receipt_sha256'] for record in records
             if record.get('event') == 'TERMINAL' and record.get('receipt') and record.get('receipt_sha256')}
    for command in base.iterdir():
        if not command.is_dir():
            continue
        for receipt in command.iterdir():
            if not receipt.is_dir():
                continue
            safe_path(root, receipt)
            status = safe_path(root, receipt / 'STATUS').read_text(encoding='utf-8').strip()
            seal = seals.get(receipt.relative_to(root).as_posix())
            if seal:
                current_files = {p.relative_to(receipt).as_posix(): sha(safe_path(root, p))
                                 for p in receipt.rglob('*') if p.is_file()}
                if seal != current_files:
                    raise SafetyError('historical receipt differs from its audit seal')
            if status != 'EVIDENCE_COMPLETE':
                continue
            if command.name == '_orchestrator':
                report = read_json(receipt / 'report.json')
                if report.get('overall_result') != 'SUCCESS' or report.get('review_required') != 'no':
                    raise SafetyError('historical controller completion is inconsistent')
            else:
                result = read_json(receipt / 'run.json')
                if (result.get('execution') != 'SUCCESS' or result.get('evidence') != 'COMPLETE'
                        or result.get('verify_ok') is not True or result.get('acceptance_claimed') is not False
                        or result.get('run_dir') != receipt.relative_to(root).as_posix()):
                    raise SafetyError('historical receipt completion is inconsistent')
                contract = read_json(safe_path(root, receipt / 'contract.json'))
                if (contract.get('acceptance_claimed') is not False
                        or contract.get('recorded_revision') != result.get('head')
                        or not isinstance(contract.get('required_files'), list)
                        or not contract['required_files']):
                    raise SafetyError('historical receipt contract is inconsistent')
                for name in contract['required_files']:
                    if not isinstance(name, str) or not safe_path(root, root / name).is_file():
                        raise SafetyError('historical receipt has a missing required artifact')
                # A historical package's recorded HEAD may differ from today's
                # HEAD. Do not rewrite it or apply its old current-head criterion
                # to a new run. New results below receive full current verification.


def verify_startup_provenance(request: dict, response: dict, result: dict) -> None:
    """Attempted dispatch, actual process creation and command outcome are three
    distinct facts. They must agree across the worker response and the receipt."""
    attempted = response['dispatch_attempted']
    started = response['command_started']
    if started and not attempted:
        raise SafetyError('startup provenance: command_started without dispatch_attempted')
    if response['gate_dispatched'] != started:
        raise SafetyError('startup provenance: gate_dispatched must mean process creation')
    if result.get('dispatch_attempted') is not attempted or result.get('command_started') is not started:
        raise SafetyError('startup provenance: receipt disagrees with worker response')
    if response.get('launch_error') != result.get('launch_error'):
        raise SafetyError('startup provenance: launch error differs between response and receipt')
    if attempted:
        if response.get('runtime') != request['runtime'] or result.get('runtime') != request['runtime']:
            raise SafetyError('startup provenance: receipt runtime differs from the bound request')
        if not started:
            error = result.get('launch_error')
            if not isinstance(error, dict) or not error.get('type') or result.get('command_exit_code') is not None:
                raise SafetyError('startup provenance: failed process creation lacks a structured launch error')
            if result.get('execution') == 'SUCCESS':
                raise SafetyError('startup provenance: success claimed without a started process')
        elif result.get('launch_error') is not None:
            raise SafetyError('startup provenance: started process carries a launch error')
    elif started or result.get('execution') not in {'REFUSED', 'INTERRUPTED'}:
        raise SafetyError('startup provenance: outcome recorded without an attempted dispatch')


def verify_response(root: Path, request: dict, attempt: Path, request_hash: str) -> dict:
    if sha(attempt / 'request.json') != request_hash:
        raise SafetyError('controller request changed after dispatch resolution')
    response = read_json(attempt / 'response.json')
    if not isinstance(response, dict) or any((
        response.get('format') != 'v3.controller.response.1',
        response.get('controller_run_id') != request['controller_run_id'],
        response.get('gate_id') != request['gate_id'],
        response.get('request_sha256') != request_hash,
        type(response.get('gate_dispatched')) is not bool,
        type(response.get('dispatch_attempted')) is not bool,
        type(response.get('command_started')) is not bool,
    )):
        raise SafetyError('worker result provenance mismatch')
    if response.get('error'):
        raise SafetyError('worker refused or failed: ' + str(response['error']))
    result = response.get('result')
    if not isinstance(result, dict):
        raise SafetyError('worker did not provide a receipt result')
    verify_startup_provenance(request, response, result)
    receipt = safe_path(root, root / RUNS / request['gate_id'] / request['controller_run_id'])
    rel = receipt.relative_to(root).as_posix()
    if result.get('run_dir') != rel or result.get('gate_id') != request['gate_id']:
        raise SafetyError('receipt is not tied to this request')
    if result.get('head') != request['identity']['head'] or result.get('branch') != request['identity']['branch']:
        raise SafetyError('receipt source identity mismatch')
    recorded = read_json(receipt / 'run.json')
    if recorded != result:
        raise SafetyError('worker result differs from actual receipt')
    for name in ('milestone_acceptance_inferred', 'capability_proven', 'reachability_proven', 'measurement_proven'):
        if result.get(name) != 'no':
            raise SafetyError('receipt claims scientific authority')
    actual_hashes = {p.relative_to(receipt).as_posix(): sha(safe_path(root, p))
                     for p in sorted(receipt.rglob('*')) if p.is_file()}
    if not actual_hashes or response.get('receipt_sha256') != actual_hashes:
        raise SafetyError('receipt files changed or are missing')
    execution = result.get('execution')
    evidence = result.get('evidence')
    status = (receipt / 'STATUS').read_text(encoding='utf-8').strip()
    expected = {'SUCCESS': 'EVIDENCE_COMPLETE' if evidence == 'COMPLETE' else 'EVIDENCE_INCOMPLETE',
                'FAILURE': 'EXECUTION_FAILURE', 'REFUSED': 'REFUSED', 'INTERRUPTED': 'INTERRUPTED'}
    if execution not in expected or status != expected[execution]:
        raise SafetyError('receipt status/result mismatch')
    if evidence == 'COMPLETE':
        if result.get('verify_ok') is not True or result.get('acceptance_claimed') is not False:
            raise SafetyError('invalid evidence-complete claim')
        contract = safe_path(root, receipt / 'contract.json')
        if read_json(contract).get('acceptance_claimed') is not False:
            raise SafetyError('invalid receipt contract authority')
        verified = verify(root, contract)
        if verified.get('evidence_verification') != 'OK':
            raise SafetyError('actual receipt verification failed')
    elif evidence != 'INCOMPLETE':
        raise SafetyError('unknown evidence state')
    return {**result, 'gate_dispatched': response['gate_dispatched'],
            'dispatch_attempted': response['dispatch_attempted'], 'command_started': response['command_started'],
            'launch_error': response.get('launch_error'), 'runtime': response.get('runtime'),
            'receipt_sha256': actual_hashes}


def execute_run(root: Path, requested_id: str, allow_dirty: bool, *, inspect, resolve) -> dict:
    root = root.resolve()
    token = uuid.uuid4().hex
    report = {'controller_run_id': token, 'requested_id': requested_id,
              'overall_result': 'REFUSED', 'mechanical_execution': 'NOT_STARTED',
              'evidence': 'INCOMPLETE', 'delegation_executed': 'no',
              # dispatch_attempted: the worker reached the launch boundary.
              # command_started / gate_dispatched: the registered command's
              # process was actually created. launch_error: structured reason
              # when it was not. runtime: the bound interpreter resolution.
              'dispatch_attempted': 'no', 'command_started': 'no', 'gate_dispatched': 'no',
              'launch_error': None, 'runtime': None,
              'identity_changed': 'no', 'review_required': 'no', 'blocked_reason': '',
              'milestone_acceptance_inferred': 'no', 'scientific_state_changed': 'no',
              'controller_audit_authority': 'none', 'receipt': None, 'child_exit_code': None}
    attempt = None
    started_audit = False
    request = None
    runtime = None

    def require(data):
        nonlocal runtime
        resolution = resolve(data, requested_id, allow_dirty)
        report['registered'] = resolution['registered']
        report['mechanically_eligible'] = resolution['mechanically_eligible']
        if resolution['future_execution_blocked'] == 'yes':
            raise SafetyError(resolution['blocked_reason'])
        if not isinstance(resolution.get('runtime'), dict):
            raise SafetyError('runtime_policy_unresolved')
        if runtime is not None and resolution['runtime'] != runtime:
            raise SafetyError('runtime resolution changed between resolution and lock acquisition')
        runtime = resolution['runtime']

    try:
        data = inspect(root)
        require(data)
        initial = identity(root)
        legacy = safe_path(root, root / RUNS / 'orchestrator.lock.json')
        if legacy.exists():
            raise SafetyError('legacy_lock_requires_review; no automatic PID check or reclamation')
        with file_lock(root, root / RUNS / 'orchestrator.guard'):
            try:
                # Resolution performed before ownership is never sufficient.
                require(inspect(root))
                if legacy.exists():
                    raise SafetyError('legacy_lock_requires_review')
                verify_history(root)
                current = identity(root)
                if initial != current:
                    raise SafetyError('repository changed between resolution and lock acquisition')
                blocker = audit_blocker(root)
                if blocker:
                    raise SafetyError(blocker)
                # The bound runtime must name the interpreter this identity
                # snapshot recorded, checked before any attempt is allocated.
                check_binding_against_identity(runtime, current)
                report['runtime'] = runtime
                allocation = safe_path(root, root / RUNS / '_orchestrator' / token)
                allocation.mkdir(parents=True, exist_ok=False)
                attempt = allocation
                set_status(attempt / 'STATUS', 'IN_PROGRESS')
                request = {'format': 'v3.controller.request.1', 'controller_run_id': token,
                           'gate_id': requested_id, 'allow_dirty': allow_dirty, 'identity': current,
                           'runtime': runtime}
                write_once(attempt / 'request.json', request)
                request_hash = sha(attempt / 'request.json')
                from automation.orchestrator import build_worker_argv
                argv = build_worker_argv(root, requested_id, allow_dirty, attempt / 'request.json', request_hash)
                append_audit(root, {'event': 'START', 'controller_run_id': token,
                                   'requested_registry_id': requested_id, 'identity': current,
                                   'allow_dirty': allow_dirty, 'delegated_argv': argv,
                                   'request_sha256': request_hash, 'delegation_started': False})
                started_audit = True
                if identity(root) != current:
                    raise SafetyError('repository changed immediately before dispatch')
                report['delegation_executed'] = 'UNKNOWN'
                report['dispatch_attempted'] = 'UNKNOWN'
                report['command_started'] = 'UNKNOWN'
                report['gate_dispatched'] = 'UNKNOWN'
                report['mechanical_execution'] = 'UNKNOWN'
                outcome = run_owned(argv, root, attempt, CHILD_TIMEOUT_S)
                report['delegation_executed'] = 'yes' if outcome['started'] else 'no'
                if not outcome['started']:
                    # The worker itself never ran: no dispatch was attempted.
                    report['dispatch_attempted'] = 'no'
                    report['command_started'] = 'no'
                    report['gate_dispatched'] = 'no'
                    report['mechanical_execution'] = 'NOT_STARTED'
                report['child_exit_code'] = outcome['returncode']
                report['process'] = outcome
                report['cleanup_complete'] = 'yes' if outcome['cleanup_complete'] else 'no'
                report['overall_result'] = 'FAILURE'
                if outcome['interrupted']:
                    report['mechanical_execution'] = 'INTERRUPTED'
                    report['overall_result'] = 'INTERRUPTED'
                    report['review_required'] = 'yes'
                elif outcome['error'] or not outcome['cleanup_complete'] or outcome['descendants_left']:
                    raise SafetyError(outcome['error'] or 'owned process cleanup requires review')
                elif outcome['returncode'] != 0:
                    raise SafetyError('worker failed without a verified result')
                else:
                    result = verify_response(root, request, attempt, request_hash)
                    report['mechanical_execution'] = result['execution']
                    report['command_exit_code'] = result.get('command_exit_code')
                    report['evidence'] = result['evidence']
                    report['dispatch_attempted'] = 'yes' if result['dispatch_attempted'] else 'no'
                    report['command_started'] = 'yes' if result['command_started'] else 'no'
                    report['gate_dispatched'] = 'yes' if result['gate_dispatched'] else 'no'
                    report['launch_error'] = result.get('launch_error')
                    report['receipt'] = result['run_dir']
                    report['receipt_sha256'] = result['receipt_sha256']
                    report['overall_result'] = result['execution']
                    if result.get('timed_out'):
                        report.update(overall_result='INTERRUPTED', mechanical_execution='INTERRUPTED', review_required='yes')
                    if result['evidence'] != 'COMPLETE':
                        report['review_required'] = 'yes'
                        if report['overall_result'] == 'SUCCESS':
                            report['overall_result'] = 'FAILURE'
                # Ignore only this controller's own unfinished record. The gate's
                # receipt and all historical receipts still participate in review.
                after = inspect(root, ignore_receipts={attempt})
                if identity(root) != current:
                    report['identity_changed'] = 'yes'
                    raise SafetyError('repository or trusted code changed during execution')
                from automation.orchestrator import preflight_blocker
                if preflight_blocker(after['preflight']):
                    raise SafetyError('postflight is unavailable or inconsistent')
                if (report['overall_result'] != 'INTERRUPTED'
                        and (after['receipts']['malformed'] or after['receipts']['in_progress_visible'] != 'no')):
                    raise SafetyError('unresolved receipt after execution')
            except (SafetyError, OSError, ValueError, KeyError, TypeError) as exc:
                report['blocked_reason'] = str(exc)
                if attempt is not None:
                    report['overall_result'] = 'FAILURE'
                    report['review_required'] = 'yes'
            except KeyboardInterrupt:
                report.update(overall_result='INTERRUPTED', mechanical_execution='INTERRUPTED', review_required='yes')
            finally:
                if attempt is not None:
                    # A failed append or finalisation leaves STATUS IN_PROGRESS;
                    # future requests refuse even though the OS lease is released.
                    write_once(attempt / 'report.json', report)
                    if started_audit:
                        append_audit(root, {'event': 'TERMINAL', **report,
                                           'request_sha256': request_hash})
                        status = {'SUCCESS': 'EVIDENCE_COMPLETE', 'FAILURE': 'EXECUTION_FAILURE',
                                  'REFUSED': 'REFUSED', 'INTERRUPTED': 'INTERRUPTED'}[report['overall_result']]
                        if report['review_required'] == 'yes' and status not in {'REFUSED', 'INTERRUPTED'}:
                            status = 'EVIDENCE_INCOMPLETE'
                        set_status(attempt / 'STATUS', status)
    except (SafetyError, OSError, ValueError, KeyError, TypeError) as exc:
        report['blocked_reason'] = str(exc)
        report['review_required'] = 'yes' if attempt is not None else 'no'
        report['overall_result'] = 'FAILURE' if attempt is not None else 'REFUSED'
    if attempt is None:
        try:
            append_audit(root, {'event': 'REFUSED', **report, 'allow_dirty': allow_dirty})
        except (SafetyError, OSError, ValueError) as exc:
            report['audit_error'] = str(exc)
            report['review_required'] = 'yes'
    return report
