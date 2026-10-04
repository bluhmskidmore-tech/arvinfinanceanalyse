"""acquire_lock error classification: contention retries, persistent errors fail fast.

Covers:
- contention still times out and the TimeoutError chains the last lock error;
- a persistent open() failure (e.g. path squatted by a directory) raises
  immediately instead of spinning until the timeout;
- a non-contention errno from the lock syscall itself raises immediately.
"""

from __future__ import annotations

import errno
import os
import time
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _load_locks_module():
    return load_module(
        "backend.app.governance.locks",
        "backend/app/governance/locks.py",
    )


@pytest.mark.parametrize("key", ["lock:test:contended", "lock:governance:jsonl:test"])
def test_contention_timeout_chains_last_lock_error(tmp_path, caplog, key):
    locks_module = _load_locks_module()
    definition = locks_module.LockDefinition(key=key, ttl_seconds=5)

    with locks_module.acquire_lock(definition, base_dir=tmp_path, timeout_seconds=1.0):
        with pytest.raises(TimeoutError) as excinfo:
            with locks_module.acquire_lock(
                definition,
                base_dir=tmp_path,
                timeout_seconds=0.05,
            ):
                pass

    cause = excinfo.value.__cause__
    assert isinstance(cause, OSError)
    assert cause.errno in locks_module._LOCK_CONTENTION_ERRNOS
    messages = [record.getMessage() for record in caplog.records]
    if key.startswith("lock:governance:jsonl:"):
        assert any("governance_lock_timeout" in message and key in message for message in messages)
    else:
        assert not messages


def test_slow_governance_holder_is_reported_after_unlock_without_masking_error(
    tmp_path, monkeypatch, caplog,
):
    locks_module = _load_locks_module()
    definition = locks_module.LockDefinition(key="lock:governance:jsonl:slow", ttl_seconds=5)
    now = [100.0]
    monkeypatch.setattr(
        locks_module, "time",
        SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep),
    )
    with pytest.raises(ValueError, match="body failure"):
        with locks_module.acquire_lock(definition, base_dir=tmp_path):
            now[0] += 1.5
            assert not caplog.records
            raise ValueError("body failure")

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "governance_lock_slow" in messages[0]
    assert "hold_ms=1500" in messages[0]
    assert "wait_ms=0" in messages[0]
    assert f"pid={os.getpid()}" in messages[0]
    assert "test_slow_governance_holder_is_reported_after_unlock" in messages[0]
    # Diagnostics must not keep the underlying file lock held on an error path.
    with locks_module.acquire_lock(definition, base_dir=tmp_path, timeout_seconds=0):
        pass
    assert len(caplog.records) == 1


def test_persistent_open_failure_raises_immediately_instead_of_spinning(tmp_path):
    locks_module = _load_locks_module()
    definition = locks_module.LockDefinition(key="lock:test:persistent", ttl_seconds=30)
    lock_dir = tmp_path / ".locks"
    lock_dir.mkdir(parents=True)
    # A directory squatting on the lock path makes open() fail persistently
    # (PermissionError on Windows, IsADirectoryError on POSIX).
    (lock_dir / "lock_test_persistent.lock").mkdir()

    started_at = time.monotonic()
    with pytest.raises(OSError) as excinfo:
        with locks_module.acquire_lock(definition, base_dir=tmp_path, timeout_seconds=5.0):
            pass
    elapsed = time.monotonic() - started_at

    assert not isinstance(excinfo.value, TimeoutError)
    assert elapsed < 2.0, "persistent open() failure must not spin until timeout"


def test_non_contention_locking_error_raises_immediately(tmp_path, monkeypatch):
    locks_module = _load_locks_module()
    definition = locks_module.LockDefinition(key="lock:test:io-error", ttl_seconds=30)

    def raise_io_error(*_args, **_kwargs):
        raise OSError(errno.EIO, "disk I/O error")

    if os.name == "nt":
        monkeypatch.setattr(locks_module.msvcrt, "locking", raise_io_error)
    else:
        monkeypatch.setattr(locks_module.fcntl, "flock", raise_io_error)

    started_at = time.monotonic()
    with pytest.raises(OSError) as excinfo:
        with locks_module.acquire_lock(definition, base_dir=tmp_path, timeout_seconds=5.0):
            pass
    elapsed = time.monotonic() - started_at

    assert excinfo.value.errno == errno.EIO
    assert not isinstance(excinfo.value, TimeoutError)
    assert elapsed < 2.0, "non-contention lock error must not spin until timeout"
