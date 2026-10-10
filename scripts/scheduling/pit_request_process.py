"""Bound only the Python child family started by the PIT maintenance host."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes


class ContainmentUnverified(RuntimeError):
    """The host must retain maintenance until an operator confirms termination."""


def run_bounded(arguments: list[str], timeout_seconds: float) -> int:
    if os.name != "nt":
        raise RuntimeError("PIT maintenance requires Windows process containment")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("reserved", wintypes.LPWSTR),
            ("desktop", wintypes.LPWSTR),
            ("title", wintypes.LPWSTR),
            ("x", wintypes.DWORD),
            ("y", wintypes.DWORD),
            ("x_size", wintypes.DWORD),
            ("y_size", wintypes.DWORD),
            ("x_chars", wintypes.DWORD),
            ("y_chars", wintypes.DWORD),
            ("fill", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("show", wintypes.WORD),
            ("reserved_size", wintypes.WORD),
            ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)),
            ("stdin", wintypes.HANDLE),
            ("stdout", wintypes.HANDLE),
            ("stderr", wintypes.HANDLE),
        ]

    class ProcessInfo(ctypes.Structure):
        _fields_ = [
            ("process", wintypes.HANDLE),
            ("thread", wintypes.HANDLE),
            ("pid", wintypes.DWORD),
            ("tid", wintypes.DWORD),
        ]

    class JobAccounting(ctypes.Structure):
        _fields_ = [
            ("user", ctypes.c_longlong),
            ("kernel", ctypes.c_longlong),
            ("period_user", ctypes.c_longlong),
            ("period_kernel", ctypes.c_longlong),
            ("faults", wintypes.DWORD),
            ("total", wintypes.DWORD),
            ("active", wintypes.DWORD),
            ("terminated", wintypes.DWORD),
        ]

    class JobLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("minimum_set", ctypes.c_size_t),
            ("maximum_set", ctypes.c_size_t),
            ("process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", JobLimits),
            ("io", ctypes.c_ulonglong * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    signatures = {
        "GetStdHandle": ([wintypes.DWORD], wintypes.HANDLE),
        "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        "CreateProcessW": (
            [
                wintypes.LPCWSTR,
                wintypes.LPWSTR,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.BOOL,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.LPCWSTR,
                ctypes.POINTER(StartupInfo),
                ctypes.POINTER(ProcessInfo),
            ],
            wintypes.BOOL,
        ),
        "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "GetExitCodeProcess": (
            [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
            wintypes.BOOL,
        ),
        "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "SetInformationJobObject": (
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
            wintypes.BOOL,
        ),
        "TerminateProcess": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "QueryInformationJobObject": (
            [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.c_void_p,
            ],
            wintypes.BOOL,
        ),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes = argtypes
        function.restype = restype

    def check(value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    job = check(kernel.CreateJobObjectW(None, None))
    process = ProcessInfo()
    assigned = False
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        check(
            kernel.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
        )
        startup = StartupInfo(
            cb=ctypes.sizeof(StartupInfo),
            flags=0x100,
            stdin=kernel.GetStdHandle(-10 & 0xFFFFFFFF),
            stdout=kernel.GetStdHandle(-11 & 0xFFFFFFFF),
            stderr=kernel.GetStdHandle(-12 & 0xFFFFFFFF),
        )
        command = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([sys.executable, *arguments])
        )
        # Suspended creation closes the spawn-to-containment race. Descendants
        # inherit this unnamed job; no PID/name scan ever selects other workers.
        check(
            kernel.CreateProcessW(
                sys.executable,
                command,
                None,
                None,
                True,
                0x00000004 | 0x08000000,
                None,
                None,
                ctypes.byref(startup),
                ctypes.byref(process),
            )
        )
        check(kernel.AssignProcessToJobObject(job, process.process))
        assigned = True
        if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        wait = kernel.WaitForSingleObject(process.process, int(timeout_seconds * 1000))
        if wait == 0x00000102:
            return 124
        if wait != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        check(kernel.GetExitCodeProcess(process.process, ctypes.byref(code)))
        return code.value
    finally:
        try:
            if assigned:
                check(kernel.TerminateJobObject(job, 124))
                # Do not permit API restoration while any owned descendant remains.
                accounting = JobAccounting()
                deadline = time.monotonic() + 10
                while True:
                    check(
                        kernel.QueryInformationJobObject(
                            job,
                            1,
                            ctypes.byref(accounting),
                            ctypes.sizeof(accounting),
                            None,
                        )
                    )
                    if accounting.active == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise ContainmentUnverified(
                            "Owned process termination is unverified"
                        )
                    time.sleep(0.01)
            elif process.process:
                check(kernel.TerminateProcess(process.process, 125))
                if kernel.WaitForSingleObject(process.process, 5000) != 0:
                    raise ContainmentUnverified(
                        "Suspended child termination is unverified"
                    )
        except Exception as error:
            raise ContainmentUnverified(
                "Owned process termination is unverified"
            ) from error
        finally:
            for handle in (process.thread, process.process, job):
                if handle:
                    kernel.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    arguments = options.arguments
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    if not 0 < options.timeout_seconds <= 1800 or not arguments:
        parser.error("A finite deadline and Python child arguments are required")
    try:
        return run_bounded(arguments, options.timeout_seconds)
    except ContainmentUnverified:
        return 126
    except Exception:
        # Provider stderr and inherited credentials must not enter host output.
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
