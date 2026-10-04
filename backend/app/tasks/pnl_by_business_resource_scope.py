from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import duckdb
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository

logger = logging.getLogger(__name__)

PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV = "MOSS_PNL_BY_BUSINESS_RESOURCE_PROFILE"
PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE = "bounded_v1"
PNL_BY_BUSINESS_MAX_DUCKDB_THREADS = 8
PNL_BY_BUSINESS_DUCKDB_MEMORY_FRACTION = Decimal("0.30")
PNL_BY_BUSINESS_PROCESS_MEMORY_FRACTION = Decimal("0.40")
PNL_BY_BUSINESS_PROCESS_ROOT_PID_ENV = "MOSS_PNL_BY_BUSINESS_PROCESS_ROOT_PID"
PNL_BY_BUSINESS_MEMORY_SAMPLE_INTERVAL_SECONDS = 0.25

class PnlByBusinessResourceBudgetExceeded(RuntimeError):
    def __init__(self, message: str, *, receipt: dict[str, object]) -> None:
        super().__init__(message)
        self.receipt = receipt


class DuckdbResourceObservation(TypedDict):
    label: str
    database_path: str
    access_mode: str
    threads: int
    memory_limit: str
    memory_limit_bytes: int


class ProcessMemorySample(TypedDict):
    sampled_at_monotonic: float
    rss_bytes: int
    process_count: int
    process_ids: list[int]


@dataclass
class _DatabaseAnchor:
    path: Path
    read_only: bool
    connection: duckdb.DuckDBPyConnection


def physical_memory_bytes() -> int:
    if sys.platform == "win32":
        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
        return int(status.ullTotalPhys)

    sysconf = getattr(os, "sysconf", None)
    if sysconf is None:
        raise RuntimeError(f"Physical-memory discovery is unsupported on {sys.platform!r}.")
    page_size = int(sysconf("SC_PAGE_SIZE"))
    page_count = int(sysconf("SC_PHYS_PAGES"))
    return page_size * page_count


def duckdb_memory_setting_bytes(value: object) -> int:
    import re

    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?i?b)\s*",
        str(value),
        flags=re.IGNORECASE,
    )
    if match is None:
        raise RuntimeError(f"DuckDB returned an unrecognized memory_limit setting: {value!r}")
    unit = match.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "PB": 1000**5,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
        "PIB": 1024**5,
    }
    return int(Decimal(match.group(1)) * multipliers[unit])


def _configured_process_root_pid() -> int:
    raw = str(os.getenv(PNL_BY_BUSINESS_PROCESS_ROOT_PID_ENV) or "").strip()
    if not raw:
        return os.getpid()
    try:
        pid = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{PNL_BY_BUSINESS_PROCESS_ROOT_PID_ENV} must be a positive process id."
        ) from exc
    if pid <= 0:
        raise RuntimeError(
            f"{PNL_BY_BUSINESS_PROCESS_ROOT_PID_ENV} must be a positive process id."
        )
    return pid


def _process_tree_rss_bytes(root_pid: int) -> tuple[int, tuple[int, ...]]:
    if sys.platform == "win32":
        return _windows_process_tree_rss_bytes(root_pid)
    if sys.platform.startswith("linux"):
        return _linux_process_tree_rss_bytes(root_pid)
    raise RuntimeError(f"Process-tree RSS sampling is unsupported on {sys.platform!r}.")


def _linux_process_tree_rss_bytes(root_pid: int) -> tuple[int, tuple[int, ...]]:
    proc_root = Path("/proc")
    parent_by_pid: dict[int, int] = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").split()
            parent_by_pid[int(entry.name)] = int(fields[3])
        except (FileNotFoundError, IndexError, OSError, ValueError):
            continue
    process_ids = _descendant_process_ids(root_pid, parent_by_pid)
    sysconf = getattr(os, "sysconf", None)
    if sysconf is None:
        raise RuntimeError("Linux process sampling requires os.sysconf.")
    page_size = int(sysconf("SC_PAGE_SIZE"))
    rss_bytes = 0
    observed: list[int] = []
    for pid in process_ids:
        try:
            fields = (proc_root / str(pid) / "statm").read_text(encoding="utf-8").split()
            rss_bytes += int(fields[1]) * page_size
            observed.append(pid)
        except FileNotFoundError:
            continue
        except (IndexError, OSError, ValueError) as exc:
            raise RuntimeError(f"Could not sample RSS for worker process pid={pid}.") from exc
    if root_pid not in observed:
        raise RuntimeError(f"Worker process root pid={root_pid} is unavailable for RSS sampling.")
    return rss_bytes, tuple(observed)


def _windows_process_tree_rss_bytes(root_pid: int) -> tuple[int, tuple[int, ...]]:
    th32cs_snapprocess = 0x00000002
    process_query_information = 0x0400
    process_vm_read = 0x0010
    invalid_handle_value = ctypes.c_void_p(-1).value

    class _ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class _ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessEntry32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessEntry32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    if snapshot == invalid_handle_value:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    parent_by_pid: dict[int, int] = {}
    try:
        entry = _ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(entry)
        has_entry = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while has_entry:
            parent_by_pid[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            has_entry = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)

    process_ids = _descendant_process_ids(root_pid, parent_by_pid)
    rss_bytes = 0
    observed: list[int] = []
    for pid in process_ids:
        handle = kernel32.OpenProcess(
            process_query_information | process_vm_read,
            False,
            pid,
        )
        if not handle:
            if pid == root_pid:
                raise OSError(ctypes.get_last_error(), f"OpenProcess failed for root pid={pid}")
            continue
        try:
            counters = _ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                ctypes.sizeof(counters),
            ):
                raise OSError(ctypes.get_last_error(), f"GetProcessMemoryInfo failed for pid={pid}")
            rss_bytes += int(counters.WorkingSetSize)
            observed.append(pid)
        finally:
            kernel32.CloseHandle(handle)
    if root_pid not in observed:
        raise RuntimeError(f"Worker process root pid={root_pid} is unavailable for RSS sampling.")
    return rss_bytes, tuple(observed)


def _descendant_process_ids(root_pid: int, parent_by_pid: dict[int, int]) -> tuple[int, ...]:
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent_pid in parent_by_pid.items():
            if pid not in descendants and parent_pid in descendants:
                descendants.add(pid)
                changed = True
    return tuple(sorted(descendants))


def pnl_by_business_resource_failure_for_run(
    governance_dir: str | Path,
    *,
    run_id: str,
    job_name: str,
) -> dict[str, object] | None:
    """Return the durable terminal resource failure for one exact task run."""
    records = GovernanceRepository(base_dir=Path(governance_dir)).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    for record in reversed(records):
        if (
            str(record.get("run_id") or "") == run_id
            and str(record.get("job_name") or "") == job_name
        ):
            if (
                str(record.get("status") or "") == "failed"
                and str(record.get("failure_category") or "")
                == "resource_over_budget"
            ):
                return dict(record)
    return None


def pnl_by_business_dependency_resource_failure(
    governance_dir: str | Path,
    *,
    year: int,
    dependency_revision: int,
    as_of_date: str,
) -> dict[str, object] | None:
    """Return an uncleared resource failure for one dependency identity."""
    blocking_failure: dict[str, object] | None = None
    records = GovernanceRepository(base_dir=Path(governance_dir)).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    for record in records:
        if (
            str(record.get("job_name") or "") != "pnl_by_business_precompute"
            or str(record.get("target_year")) != str(int(year))
            or str(record.get("dependency_revision")) != str(int(dependency_revision))
        ):
            continue
        target_dates = record.get("target_as_of_dates")
        if isinstance(target_dates, list):
            covers_date = as_of_date in {str(value) for value in target_dates}
        else:
            covers_date = str(record.get("report_date") or "") == as_of_date
        if not covers_date:
            continue
        if str(record.get("status") or "") == "completed":
            blocking_failure = None
        elif (
            str(record.get("status") or "") == "failed"
            and str(record.get("failure_category") or "")
            == "resource_over_budget"
        ):
            blocking_failure = dict(record)
    return blocking_failure


class PnlByBusinessTaskResourceScope:
    def __init__(
        self,
        duckdb_path: str | Path,
        *,
        scope_name: str,
        physical_memory: int | None = None,
        process_root_pid: int | None = None,
        sample_interval_seconds: float = PNL_BY_BUSINESS_MEMORY_SAMPLE_INTERVAL_SECONDS,
        max_database_instances: int = 1,
        on_budget_exceeded: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.duckdb_path = Path(duckdb_path).resolve()
        self.scope_name = scope_name
        self.physical_memory_bytes = physical_memory or physical_memory_bytes()
        self.thread_budget = min(
            PNL_BY_BUSINESS_MAX_DUCKDB_THREADS,
            max(1, (os.cpu_count() or 1) // 2),
        )
        self.duckdb_memory_budget_bytes = int(
            Decimal(self.physical_memory_bytes) * PNL_BY_BUSINESS_DUCKDB_MEMORY_FRACTION
        )
        if max_database_instances < 1:
            raise ValueError("max_database_instances must be at least one.")
        self.max_database_instances = max_database_instances
        self.per_database_memory_budget_bytes = (
            self.duckdb_memory_budget_bytes // self.max_database_instances
        )
        self.process_memory_budget_bytes = int(
            Decimal(self.physical_memory_bytes) * PNL_BY_BUSINESS_PROCESS_MEMORY_FRACTION
        )
        self.process_root_pid = process_root_pid or _configured_process_root_pid()
        self.sample_interval_seconds = sample_interval_seconds
        self.on_budget_exceeded = on_budget_exceeded
        self.observations: list[DuckdbResourceObservation] = []
        self._anchors: dict[str, _DatabaseAnchor] = {}
        self._sample_lock = threading.Lock()
        self._stop_sampling = threading.Event()
        self._sampler: threading.Thread | None = None
        self._sample_count = 0
        self._latest_sample: ProcessMemorySample | None = None
        self._peak_sample: ProcessMemorySample | None = None
        self._exceeded_sample: ProcessMemorySample | None = None
        self._sampling_error: str | None = None
        self._budget_exceeded_notified = False
        self._finalized = False
        self.started_at_monotonic: float | None = None
        self.completed_at_monotonic: float | None = None

    def __enter__(self) -> PnlByBusinessTaskResourceScope:
        try:
            self.started_at_monotonic = time.monotonic()
            self._record_process_memory_sample()
            self._sampler = threading.Thread(
                target=self._sample_process_memory_until_stopped,
                name="pnl-by-business-memory-sampler",
                daemon=True,
            )
            self._sampler.start()
        except BaseException:
            self._release()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is None and not self._finalized:
                self.complete("scope_exit")
            else:
                self.stop_sampling()
        finally:
            self._release()

    def complete(self, stage: str) -> None:
        self.stop_sampling()
        try:
            self.assert_within_budget(stage)
        finally:
            self.completed_at_monotonic = time.monotonic()
            self._finalized = True

    def freeze_for_pointer_commit(self) -> None:
        """Take the final synchronous sample immediately before the pointer CAS."""
        self.complete("before_pointer_commit")

    def bind_database(
        self,
        database_path: str | Path,
        *,
        read_only: bool,
        label: str,
    ) -> None:
        path = Path(database_path).resolve()
        key = os.path.normcase(str(path))
        previous = self._anchors.get(key)
        if previous is not None and previous.read_only == read_only:
            return
        if previous is not None:
            previous.connection.close()
            del self._anchors[key]
        anchor = duckdb.connect(str(path), read_only=read_only)
        try:
            self.configure_connection(
                anchor,
                database_path=path,
                read_only=read_only,
                label=label,
            )
            verifier = duckdb.connect(str(path), read_only=read_only)
            try:
                self._observe_connection(
                    verifier,
                    database_path=path,
                    read_only=read_only,
                    label=f"{label}:inherited",
                )
            finally:
                verifier.close()
        except BaseException:
            anchor.close()
            raise
        self._anchors[key] = _DatabaseAnchor(path=path, read_only=read_only, connection=anchor)

    def configure_connection(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        database_path: str | Path,
        read_only: bool,
        label: str,
    ) -> None:
        connection.execute("set threads = ?", [self.thread_budget])
        connection.execute(
            "set memory_limit = ?", [f"{self.per_database_memory_budget_bytes}B"]
        )
        self._observe_connection(
            connection,
            database_path=Path(database_path).resolve(),
            read_only=read_only,
            label=label,
        )

    def database_connection(
        self, database_path: str | Path
    ) -> duckdb.DuckDBPyConnection:
        key = os.path.normcase(str(Path(database_path).resolve()))
        anchor = self._anchors.get(key)
        if anchor is None:
            raise RuntimeError(f"No bounded DuckDB anchor exists for {database_path!s}.")
        return anchor.connection

    def assert_within_budget(self, stage: str) -> None:
        self._record_process_memory_sample()
        with self._sample_lock:
            sampling_error = self._sampling_error
            exceeded_sample = self._exceeded_sample
        if sampling_error is not None:
            raise PnlByBusinessResourceBudgetExceeded(
                f"PnL-by-business process-tree memory sampling failed at {stage}: {sampling_error}",
                receipt=self.receipt(stage=stage),
            )
        if exceeded_sample is not None:
            raise PnlByBusinessResourceBudgetExceeded(
                "PnL-by-business worker process tree exceeded its memory budget at "
                f"{stage}: observed={exceeded_sample['rss_bytes']} "
                f"budget={self.process_memory_budget_bytes}.",
                receipt=self.receipt(stage=stage),
            )

    def stop_sampling(self) -> None:
        sampler = self._sampler
        if sampler is None:
            return
        self._stop_sampling.set()
        sampler.join(timeout=max(1.0, self.sample_interval_seconds * 4))
        if sampler.is_alive():
            with self._sample_lock:
                self._sampling_error = "process-tree memory sampler did not stop"
        self._sampler = None

    def receipt(self, *, stage: str | None = None) -> dict[str, object]:
        with self._sample_lock:
            latest = dict(self._latest_sample) if self._latest_sample is not None else None
            peak = dict(self._peak_sample) if self._peak_sample is not None else None
            exceeded = dict(self._exceeded_sample) if self._exceeded_sample is not None else None
            sample_count = self._sample_count
            sampling_error = self._sampling_error
        return {
            "profile": PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
            "scope": self.scope_name,
            "stage": stage,
            "heavy_lock": "duckdb_writer_lock_owned_by_task_caller",
            "started_at_monotonic": self.started_at_monotonic,
            "completed_at_monotonic": self.completed_at_monotonic,
            "logical_processors": os.cpu_count() or 1,
            "physical_memory_bytes": self.physical_memory_bytes,
            "thread_budget": self.thread_budget,
            "duckdb_memory_budget_bytes": self.duckdb_memory_budget_bytes,
            "max_database_instances": self.max_database_instances,
            "per_database_memory_budget_bytes": self.per_database_memory_budget_bytes,
            "process_memory_budget_bytes": self.process_memory_budget_bytes,
            "process_root_pid": self.process_root_pid,
            "process_memory_sample_count": sample_count,
            "latest_process_memory_sample": latest,
            "peak_process_memory_sample": peak,
            "exceeded_process_memory_sample": exceeded,
            "sampling_error": sampling_error,
            "observations": [dict(item) for item in self.observations],
        }

    def _observe_connection(
        self,
        connection: duckdb.DuckDBPyConnection,
        *,
        database_path: Path,
        read_only: bool,
        label: str,
    ) -> None:
        row = connection.execute(
            "select current_setting('threads'), current_setting('memory_limit')"
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckDB resource settings could not be observed.")
        observed_threads = int(row[0])
        observed_memory_text = str(row[1])
        observed_memory_bytes = duckdb_memory_setting_bytes(observed_memory_text)
        if observed_threads != self.thread_budget:
            raise RuntimeError(
                "DuckDB thread limit did not apply to a task connection: "
                f"expected {self.thread_budget}, observed {observed_threads}."
            )
        if not 0 < observed_memory_bytes <= self.per_database_memory_budget_bytes:
            raise RuntimeError(
                "DuckDB memory limit did not apply within the bounded task budget: "
                f"per-database budget {self.per_database_memory_budget_bytes}, "
                f"observed {observed_memory_bytes}."
            )
        self.observations.append(
            {
                "label": label,
                "database_path": str(database_path),
                "access_mode": "read_only" if read_only else "read_write",
                "threads": observed_threads,
                "memory_limit": observed_memory_text,
                "memory_limit_bytes": observed_memory_bytes,
            }
        )

    def _sample_process_memory_until_stopped(self) -> None:
        while not self._stop_sampling.wait(self.sample_interval_seconds):
            try:
                self._record_process_memory_sample()
            # The sampler is a daemon thread: every ordinary failure must be
            # latched so pointer publication fails closed instead of losing it.
            except Exception as exc:
                logger.exception("PnL-by-business process-tree memory sampling failed")
                with self._sample_lock:
                    self._sampling_error = f"{type(exc).__name__}: {exc}"
                return

    def _record_process_memory_sample(self) -> None:
        rss_bytes, process_ids = _process_tree_rss_bytes(self.process_root_pid)
        sample: ProcessMemorySample = {
            "sampled_at_monotonic": time.monotonic(),
            "rss_bytes": rss_bytes,
            "process_count": len(process_ids),
            "process_ids": list(process_ids),
        }
        notify_budget_exceeded = False
        with self._sample_lock:
            self._sample_count += 1
            self._latest_sample = sample
            if self._peak_sample is None or rss_bytes > self._peak_sample["rss_bytes"]:
                self._peak_sample = sample
            if rss_bytes > self.process_memory_budget_bytes and self._exceeded_sample is None:
                self._exceeded_sample = sample
            if self._exceeded_sample is not None and not self._budget_exceeded_notified:
                self._budget_exceeded_notified = True
                notify_budget_exceeded = True
        if notify_budget_exceeded and self.on_budget_exceeded is not None:
            try:
                self.on_budget_exceeded(self.receipt(stage="memory_sample"))
            # The callback is the durability boundary.  Any ordinary write
            # failure must become a sampling error and block publication.
            except Exception as exc:
                logger.exception("PnL-by-business resource latch persistence failed")
                with self._sample_lock:
                    self._sampling_error = (
                        "resource budget latch persistence failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

    def _release(self) -> None:
        self.stop_sampling()
        for anchor in reversed(tuple(self._anchors.values())):
            anchor.connection.close()
        self._anchors.clear()
