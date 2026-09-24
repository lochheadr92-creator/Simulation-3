"""Explicit runtime policy for registered Python commands.

A registry entry records ``py -3 ...`` as provenance. Nothing here searches PATH
for a launcher, creates a shim, or accepts a command or executable-path input.
The only supported resolution maps exactly that prefix to the controller's own
native base interpreter, whose path and SHA-256 the identity snapshot already
records. Every other ``py`` launcher form is refused before dispatch. Any other
argv (test fixtures name an absolute interpreter) is executed verbatim.
"""
from __future__ import annotations

from pathlib import Path

from automation.controller_io import SafetyError, python_executable, sha

BINDING_FORMAT = 'v3.runtime.binding.1'
POLICY_TRUSTED = 'trusted-native-python'
POLICY_VERBATIM = 'registry-argv-verbatim'
LAUNCHER_NAMES = {'py', 'py.exe'}
TRUSTED_SELECTOR = '-3'


def _valid_argv(argv) -> list[str]:
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise SafetyError('runtime policy: invalid argv')
    return list(argv)


def resolve_runtime(argv) -> dict:
    """Resolve one registered argv. Raises SafetyError for unsupported launcher forms."""
    argv = _valid_argv(argv)
    if argv[0].lower() not in LAUNCHER_NAMES:
        return {'policy': POLICY_VERBATIM, 'registry_argv': argv, 'matched_prefix': [],
                'interpreter': None, 'interpreter_sha256': None, 'resolved_argv': argv}
    if len(argv) < 3 or argv[1] != TRUSTED_SELECTOR:
        raise SafetyError('runtime policy: only the registered "py -3 <target...>" form is supported; '
                          'launcher argv ' + repr(argv[:2]) + ' is refused')
    interpreter = python_executable()
    return {'policy': POLICY_TRUSTED, 'registry_argv': argv, 'matched_prefix': [argv[0], argv[1]],
            'interpreter': interpreter, 'interpreter_sha256': sha(Path(interpreter)),
            'resolved_argv': [interpreter, *argv[2:]]}


def bind_gate_runtime(gate: dict) -> dict:
    """Bind the runtime for a validated registry entry: main command plus required checks."""
    checks = gate.get('required_checks') or []
    if not isinstance(checks, list):
        raise SafetyError('runtime policy: invalid required_checks')
    return {'format': BINDING_FORMAT, 'command': resolve_runtime(gate.get('argv')),
            'checks': [resolve_runtime(check) for check in checks]}


def recheck_runtime(resolution: dict) -> None:
    """Recompute a resolution immediately before dispatch; any drift refuses."""
    if not isinstance(resolution, dict) or resolution.get('policy') not in {POLICY_TRUSTED, POLICY_VERBATIM}:
        raise SafetyError('runtime policy: malformed runtime binding')
    if resolve_runtime(resolution.get('registry_argv')) != resolution:
        raise SafetyError('runtime policy: runtime binding changed before dispatch')
    if resolution['policy'] == POLICY_TRUSTED and not Path(resolution['interpreter']).is_file():
        raise SafetyError('runtime policy: trusted interpreter unavailable')


def check_binding_against_identity(binding: dict, identity: dict) -> None:
    """A trusted resolution must name the interpreter the identity snapshot recorded."""
    if not isinstance(binding, dict) or binding.get('format') != BINDING_FORMAT:
        raise SafetyError('runtime policy: malformed runtime binding')
    for resolution in [binding.get('command'), *(binding.get('checks') or [])]:
        recheck_runtime(resolution)
        if resolution['policy'] == POLICY_TRUSTED and (
                resolution['interpreter'] != identity.get('python_executable')
                or resolution['interpreter_sha256'] != identity.get('python_sha256')):
            raise SafetyError('runtime policy: bound interpreter differs from the identity snapshot')
