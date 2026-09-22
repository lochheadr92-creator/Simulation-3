"""Windows process-tree supervision using a private kill-on-close Job Object.

The bootstrap cannot start the worker until assigned to the job. Only handles
created by this invocation are used for termination; no PID liveness signals.
Other platforms refuse execution until an equivalent supervisor is provided.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import time

from automation.controller_io import python_executable


class JobError(OSError):
    pass


class WindowsJob:
    def __init__(self):
        if os.name != 'nt':
            raise JobError('controlled execution requires Windows Job Objects')
        k = self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        k.SetInformationJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.AssignProcessToJobObject.restype = w.BOOL
        k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        k.TerminateJobObject.restype = w.BOOL
        k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
        k.QueryInformationJobObject.restype = w.BOOL
        k.CloseHandle.argtypes = [w.HANDLE]
        k.CloseHandle.restype = w.BOOL

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', w.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_limit', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class Limits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway
        if not k.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process):
        # Popen retains the handle of the process it created. No PID lookup.
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def active(self) -> int:
        class Accounting(ctypes.Structure):
            _fields_ = [('times', ctypes.c_int64 * 4), ('faults', w.DWORD),
                        ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]
        info = Accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.active

    def stop(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_owned(argv: list[str], root: Path, output_dir: Path, timeout: float) -> dict:
    """Preserve output and stop every owned descendant before returning."""
    outcome = {'started': False, 'returncode': None, 'interrupted': False,
               'timed_out': False, 'cleanup_complete': True, 'descendants_left': False,
               'error': None}
    job = None
    process = None
    try:
        job = WindowsJob()  # Failure here is a refusal before any process is created.
        with (output_dir / 'stdout.txt').open('xb') as stdout, (output_dir / 'stderr.txt').open('xb') as stderr:
            bootstrap = Path(__file__).with_name('process_bootstrap.py')
            process = subprocess.Popen(
                [python_executable(), '-I', '-S', '-B', '-X', 'utf8', str(bootstrap)], cwd=root,
                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW, shell=False,
            )
            try:
                job.assign(process)
                process.stdin.write((json.dumps(argv) + '\n').encode('utf-8'))
                process.stdin.flush()
                process.stdin.close()
                outcome['started'] = True
                outcome['returncode'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                outcome['timed_out'] = True
                outcome['interrupted'] = True
            except KeyboardInterrupt:
                outcome['interrupted'] = True
            finally:
                # Assignment failure leaves only the waiting bootstrap. The owned
                # Popen handle may terminate it safely without inspecting any PID.
                if not outcome['started'] and process.poll() is None:
                    process.kill()
                # A signalled process handle can precede the job accounting
                # decrement. Allow only a bounded exit drain, never a live child
                # to outlast ownership. Timeout/interruption skips this grace.
                if process.poll() is not None and not outcome['interrupted']:
                    drain = time.monotonic() + .25
                    while job.active() and time.monotonic() < drain:
                        time.sleep(.01)
                remaining = job.active()
                outcome['descendants_left'] = bool(remaining and process.poll() is not None)
                job.stop()
                deadline = time.monotonic() + 5
                while job.active() and time.monotonic() < deadline:
                    time.sleep(.01)
                outcome['cleanup_complete'] = job.active() == 0
                process.wait(timeout=5)
                stdout.flush()
                stderr.flush()
                os.fsync(stdout.fileno())
                os.fsync(stderr.fileno())
    except (OSError, subprocess.SubprocessError) as exc:
        outcome['error'] = str(exc)
        if process is not None:
            # Any cleanup uncertainty leaves an unresolved controller receipt.
            outcome['cleanup_complete'] = False
    finally:
        if job is not None:
            job.close()
        if process is not None and process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
    return outcome
