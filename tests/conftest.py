"""Pytest hooks: skip storage migrations on app/worker startup during unit tests."""

from __future__ import annotations

import os
import shutil
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
os.environ.setdefault("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")


import pytest


def _pid_is_running(pid: int) -> bool:
    """Return whether *pid* is live, preserving directories when uncertain."""

    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        if pid > 0xFFFFFFFF:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = open_process(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87
        try:
            exit_code = wintypes.DWORD()
            if not get_exit_code(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259
        finally:
            close_handle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return True
    return True


@contextmanager
def _locked_pytest_basetemp_root(root: Path) -> Iterator[None]:
    """Serialize cleanup and creation across concurrent pytest processes."""

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".pytest-basetemp.lock").open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            lock_file.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _prune_dead_pytest_basetemps(root: Path, current_pid: int) -> None:
    """Remove exact per-PID roots only after their owning process has exited."""

    prefix = "pytest-basetemp-"
    for candidate in root.iterdir():
        suffix = candidate.name.removeprefix(prefix)
        if (
            suffix == candidate.name
            or not suffix.isascii()
            or not suffix.isdecimal()
            or not candidate.is_dir()
            or candidate.is_symlink()
        ):
            continue
        pid = int(suffix)
        if pid != current_pid and not _pid_is_running(pid):
            shutil.rmtree(candidate, ignore_errors=True)


def _prepare_process_pytest_basetemp(root: Path, current_pid: int) -> Path:
    """Prune abandoned roots and create a clean root for this process."""

    basetemp = root / f"pytest-basetemp-{current_pid}"
    with _locked_pytest_basetemp_root(root):
        _prune_dead_pytest_basetemps(root, current_pid)
        if basetemp.exists():
            shutil.rmtree(basetemp, ignore_errors=True)
        if basetemp.exists():
            raise OSError(f"Could not reset reused pytest basetemp: {basetemp}")
        if os.name == "nt":
            basetemp.mkdir(parents=True)
        else:
            basetemp.mkdir(mode=0o700, parents=True)
    return basetemp.resolve()


def _install_windows_readable_pytest_basetemp() -> None:
    """Keep pytest temp roots process-scoped and readable in this Windows sandbox.

    Pytest creates tmp_path basetemp with mode=0o700. Here that can translate to
    a directory the same process cannot enumerate, so use default mkdir ACLs on
    Windows. All platforms keep the default basetemp inside the repo and isolate
    it by process so concurrent pytest commands cannot share tmp_path state.
    """

    from _pytest.tmpdir import TempPathFactory

    original_getbasetemp = TempPathFactory.getbasetemp
    prepared_default_basetemps: dict[Path, Path] = {}
    preparation_lock = threading.Lock()

    def _getbasetemp_windows_readable(self: TempPathFactory) -> Path:
        if self._basetemp is not None:
            return self._basetemp
        if self._given_basetemp is not None:
            if os.name != "nt":
                return original_getbasetemp(self)
            basetemp = Path(self._given_basetemp)
            if basetemp.exists():
                shutil.rmtree(basetemp, ignore_errors=True)
                if basetemp.exists():
                    basetemp = basetemp.with_name(f"{basetemp.name}-readable")
            basetemp.mkdir(parents=True, exist_ok=True)
        else:
            root = Path.cwd() / ".codex-tmp"
            with preparation_lock:
                basetemp = prepared_default_basetemps.get(root)
                if basetemp is None or not basetemp.is_dir():
                    basetemp = _prepare_process_pytest_basetemp(root, os.getpid())
                    prepared_default_basetemps[root] = basetemp
        self._basetemp = basetemp.resolve()
        return self._basetemp

    def _mktemp_windows_readable(
        self: TempPathFactory,
        basename: str,
        numbered: bool = True,
    ) -> Path:
        basename = self._ensure_relative_to_basetemp(basename)
        base = self.getbasetemp()
        if not numbered:
            path = base / basename
            path.mkdir(exist_ok=False)
            return path
        index = 0
        while True:
            path = base / f"{basename}{index}"
            try:
                path.mkdir()
                return path
            except FileExistsError:
                index += 1

    TempPathFactory.getbasetemp = _getbasetemp_windows_readable
    if os.name == "nt":
        TempPathFactory.mktemp = _mktemp_windows_readable


_install_windows_readable_pytest_basetemp()


@pytest.fixture()
def seed_wildcard_scope(tmp_path, monkeypatch):
    """Grant wildcard permissions so existing functional tests pass with auth enforcement."""
    from backend.app.governance.settings import get_settings

    sqlite_path = tmp_path / "auth-scope-wildcard.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    repo.grant_scope(user_id="*", role=None, resource="*", action="*")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="read")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="refresh")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl.adjustment", action="write")
    repo.grant_scope(user_id="*", role=None, resource="pnl_by_business.adjustment", action="write")
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_auth_scope_decision_cache():
    """Keep permission decisions isolated between tests despite the TTL cache."""
    from backend.app.security.auth_context import reset_scope_decision_cache

    reset_scope_decision_cache()
    yield
    reset_scope_decision_cache()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Clear the env-derived Settings cache around each test.

    Tests that monkeypatch MOSS_* env vars and prime get_settings() would
    otherwise leak a stale Settings instance (e.g. tmp_path duckdb/governance
    paths) into later tests when a mid-test assertion fails before the tail
    cache_clear() call runs.
    """
    from backend.app.governance.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_choice_runtime_cache():
    yield

    runtime_module = sys.modules.get("backend.app.config.choice_runtime")
    if runtime_module is not None and hasattr(runtime_module, "_EM_C"):
        runtime_module._EM_C = None

    for module_name in list(sys.modules):
        if module_name == "EmQuantAPI" or module_name.startswith("EmQuantAPI."):
            sys.modules.pop(module_name, None)
