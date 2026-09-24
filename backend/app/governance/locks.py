import errno
import os
import hashlib
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

# Errnos raised by the non-blocking lock calls below when another holder owns
# the lock. POSIX flock raises EWOULDBLOCK/EAGAIN; Windows msvcrt.locking with
# LK_NBLCK raises OSError(EACCES) (surfaced as PermissionError, the same
# type/errno as an open() permission failure — which is why open() errors are
# handled by call site in acquire_lock instead of by exception type).
_LOCK_CONTENTION_ERRNOS = frozenset(
    getattr(errno, name)
    for name in ("EACCES", "EAGAIN", "EWOULDBLOCK", "EDEADLK", "EDEADLOCK")
    if hasattr(errno, name)
)


@dataclass(frozen=True)
class LockDefinition:
    """Named lock used to serialize critical background operations."""

    key: str
    ttl_seconds: int = 300


MATERIALIZE_LOCK = LockDefinition(key="lock:duckdb:materialize", ttl_seconds=900)


def resolve_duckdb_writer_lock(
    duckdb_file: Path | str,
    *,
    ttl_seconds: int = MATERIALIZE_LOCK.ttl_seconds,
) -> LockDefinition:
    canonical_path = os.path.normcase(str(Path(duckdb_file).resolve()))
    digest = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()[:12]
    return LockDefinition(
        key=f"{MATERIALIZE_LOCK.key}:{digest}",
        ttl_seconds=ttl_seconds,
    )


@contextmanager
def acquire_lock(
    definition: LockDefinition,
    base_dir: Path | str = Path("data/governance"),
    timeout_seconds: float | None = None,
    poll_interval_seconds: float = 0.05,
):
    """Acquire the file-based lock described by ``definition``.

    ``timeout_seconds`` defaults to ``definition.ttl_seconds`` (the lock's own
    TTL) rather than a fixed short window, since a caller waiting for a writer
    lock should generally wait as long as that lock is allowed to be held.
    Pass an explicit ``timeout_seconds`` to opt into a shorter/longer wait.
    """
    resolved_timeout_seconds = (
        float(definition.ttl_seconds) if timeout_seconds is None else timeout_seconds
    )
    lock_dir = Path(base_dir) / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{definition.key.replace(':', '_')}.lock"
    deadline = time.monotonic() + resolved_timeout_seconds
    handle = None

    while True:
        # open() failures (permission denied, invalid path, ...) are
        # persistent: retrying cannot succeed, so let them propagate
        # immediately instead of spinning until the timeout masks them.
        handle = open(lock_path, "a+b")
        try:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError as exc:
            handle.close()
            handle = None
            if exc.errno not in _LOCK_CONTENTION_ERRNOS:
                # Not lock contention (e.g. I/O error, bad descriptor):
                # fail fast instead of reporting it as a timeout.
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out acquiring lock {definition.key}"
                ) from exc
            time.sleep(poll_interval_seconds)

    try:
        assert handle is not None
        handle.seek(0)
        handle.truncate()
        handle.write(f"{definition.key}|pid={os.getpid()}".encode())
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
