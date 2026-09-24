"""Wait for job assignment before starting a controller-owned command.

Only the controller calls this pinned script. No project code is imported here.
"""
import json
import subprocess
import sys


def main() -> int:
    line = sys.stdin.buffer.readline()
    if not line:
        return 2
    argv = json.loads(line)
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        return 2
    # On Windows execv can finish the bootstrap while its replacement remains
    # active. Keep an owned parent alive and wait for the actual worker instead.
    return subprocess.run(argv, stdin=subprocess.DEVNULL, shell=False, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
