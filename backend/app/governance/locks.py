import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


@dataclass(frozen=True)
class LockDefinition:
    """Named lock used to serialize critical background operations."""

    key: str
    ttl_seconds: int = 300


MATERIALIZE_LOCK = LockDefinition(key="lock:duckdb:materialize", ttl_seconds=900)


@contextmanager
def acquire_lock(
    definition: LockDefinition,
    base_dir: Path | str = Path("data/governance"),
    timeout_seconds: float = 1.0,
    poll_interval_seconds: float = 0.05,
):
    lock_dir = Path(base_dir) / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{definition.key.replace(':', '_')}.lock"
    deadline = time.monotonic() + timeout_seconds
    handle = None

    while True:
        try:
            handle = open(lock_path, "a+b")
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if handle is not None:
                handle.close()
                handle = None
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out acquiring lock {definition.key}")
            time.sleep(poll_interval_seconds)

    try:
        assert handle is not None
        handle.seek(0)
        handle.truncate()
        handle.write(f"{definition.key}|pid={os.getpid()}".encode("utf-8"))
        handle.flush()
        yield lock_path
    finally:
        if handle is not None:
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
