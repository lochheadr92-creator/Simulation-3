"""Pinned controller worker. A request chooses a registry ID, never executable code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

TRUSTED_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TRUSTED_ROOT))

from automation import orchestrator as orch
from automation import run_gate
from automation.controller_io import RUNS, SafetyError, identity, read_json, safe_path, sha, unique, write_once
from automation.runtime_policy import bind_gate_runtime, check_binding_against_identity


def validate_request(path: Path, expected_hash: str) -> tuple[dict, Path, Path, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_hash:
        raise SafetyError('controller request hash mismatch')
    request = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(request, dict) or request.get('format') != 'v3.controller.request.1':
        raise SafetyError('invalid controller request')
    token = request.get('controller_run_id')
    gate_id = request.get('gate_id')
    if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{32}', token):
        raise SafetyError('invalid controller run identity')
    if not isinstance(gate_id, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*', gate_id):
        raise SafetyError('invalid registry identity')
    if type(request.get('allow_dirty')) is not bool:
        raise SafetyError('invalid dirty permission')
    if not isinstance(request.get('runtime'), dict):
        raise SafetyError('controller request carries no runtime binding')
    root = Path(request['identity']['root']).resolve()
    expected = safe_path(root, root / RUNS / '_orchestrator' / token / 'request.json')
    if path.resolve() != expected:
        raise SafetyError('request is not in its allocated run directory')
    receipt = safe_path(root, root / RUNS / gate_id / token)
    return request, root, receipt, digest


def execute_request(path: Path, validated: tuple[dict, Path, Path, str]) -> dict:
    request, root, receipt, digest = validated
    token = request['controller_run_id']
    # gate_dispatched means the registered command's process was actually
    # created. dispatch_attempted records that the worker reached the launch
    # boundary; the two differ exactly when process creation fails.
    response = {'format': 'v3.controller.response.1', 'controller_run_id': token,
                'gate_id': request['gate_id'], 'request_sha256': digest,
                'dispatch_attempted': False, 'command_started': False, 'launch_error': None,
                'runtime': None, 'gate_dispatched': False, 'result': None, 'error': None}

    def boundary():
        if identity(root) != request['identity']:
            raise SafetyError('repository or trusted code changed before dispatch')
        data = orch.inspect(root, ignore_receipts={path.parent, receipt})
        resolved = orch.resolve_dry_run(data, request['gate_id'], request['allow_dirty'])
        if resolved['future_execution_blocked'] == 'yes':
            raise SafetyError(resolved['blocked_reason'])
        if resolved.get('runtime') != request['runtime']:
            raise SafetyError('runtime resolution differs from the bound request')
        check_binding_against_identity(request['runtime'], request['identity'])

    def before_command():
        boundary()
        response['dispatch_attempted'] = True

    try:
        boundary()
        raw_registry = (root / 'automation/gate_registry.json').read_bytes()
        if hashlib.sha256(raw_registry).hexdigest() != request['identity']['files']['automation/gate_registry.json']:
            raise SafetyError('registry changed while loading the execution snapshot')
        registry_snapshot = json.loads(raw_registry, object_pairs_hook=unique)
        entry = run_gate.get_gate(registry_snapshot, request['gate_id'])
        if bind_gate_runtime(entry) != request['runtime']:
            raise SafetyError('registry snapshot runtime differs from the bound request')
        result = run_gate.run(root, request['gate_id'], allow_dirty=request['allow_dirty'],
                              controller_run_id=token, before_command=before_command,
                              registry_snapshot=registry_snapshot, runtime_binding=request['runtime'])
        response['result'] = result
        # The receipt is authoritative once it exists; the callback flag above
        # only survives when run_gate raised before producing a result.
        response['dispatch_attempted'] = result.get('dispatch_attempted') is True
        response['command_started'] = result.get('command_started') is True
        response['gate_dispatched'] = response['command_started']
        response['launch_error'] = result.get('launch_error')
        response['runtime'] = result.get('runtime')
        response['receipt_sha256'] = {
            file.relative_to(receipt).as_posix(): sha(safe_path(root, file))
            for file in sorted(receipt.rglob('*')) if file.is_file()
        }
    except (SafetyError, run_gate.RunGateError, OSError, ValueError) as exc:
        response['error'] = str(exc)
    return response


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--gate', required=True)
    parser.add_argument('--allow-dirty', action='store_true')
    args = parser.parse_args(argv)
    path = Path(args.request).resolve()
    # Validate before deciding where to write. No arbitrary output-path argument.
    validated = validate_request(path, args.request_sha256)
    request, root, _, _ = validated
    if (Path(args.root).resolve() != root or args.gate != request['gate_id']
            or args.allow_dirty != request['allow_dirty']):
        raise SafetyError('worker arguments differ from the recorded request')
    write_once(path.with_name('response.json'), execute_request(path, validated))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
