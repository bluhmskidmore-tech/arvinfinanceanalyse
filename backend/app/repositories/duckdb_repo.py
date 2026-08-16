from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

# Catalog probes (information_schema lookups) cost tens of milliseconds on large
# DuckDB files, so presence results are cached per (path, kind, name) and
# invalidated whenever the database file mtime changes (i.e. after a writer
# checkpoint). Entries are never returned for a missing/unstattable file.
_CATALOG_PRESENCE_CACHE: dict[tuple[str, str, str], tuple[int, bool]] = {}
_CATALOG_PRESENCE_CACHE_LOCK = threading.Lock()
_CATALOG_PRESENCE_CACHE_MAX_ENTRIES = 4096


def catalog_presence_cached(
    path: str,
    kind: str,
    name: str,
    probe: Callable[[], bool],
) -> bool:
    """Return a cached catalog presence result, re-probing when the file changes."""
    try:
        mtime_ns = Path(path).stat().st_mtime_ns
    except OSError:
        return probe()
    try:
        # Un-checkpointed writes live in the WAL; fold its mtime into the cache
        # stamp so fresh tables/columns are observed before the next checkpoint.
        mtime_ns = max(mtime_ns, Path(f"{path}.wal").stat().st_mtime_ns)
    except OSError:
        pass

    key = (str(path), kind, name)
    with _CATALOG_PRESENCE_CACHE_LOCK:
        entry = _CATALOG_PRESENCE_CACHE.get(key)
        if entry is not None and entry[0] == mtime_ns:
            return entry[1]

    result = bool(probe())
    with _CATALOG_PRESENCE_CACHE_LOCK:
        if len(_CATALOG_PRESENCE_CACHE) >= _CATALOG_PRESENCE_CACHE_MAX_ENTRIES:
            _CATALOG_PRESENCE_CACHE.clear()
        _CATALOG_PRESENCE_CACHE[key] = (mtime_ns, result)
    return result


def reset_catalog_presence_cache() -> None:
    with _CATALOG_PRESENCE_CACHE_LOCK:
        _CATALOG_PRESENCE_CACHE.clear()


@contextmanager
def read_only_connection(
    path: str,
    *,
    retries: int = 3,
    retry_delay_seconds: float = 0.05,
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a read-only DuckDB connection, yield it, and always close it.

    Retries transient open failures (e.g. a writer briefly holding the file lock
    on Windows). Raises the last error if every attempt fails, so callers that
    want to degrade gracefully should wrap the ``with`` block in ``try/except``.

    The connection is closed on exit so writer processes are not blocked for
    longer than the scope of the ``with`` block.
    """
    conn: duckdb.DuckDBPyConnection | None = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            conn = duckdb.connect(path, read_only=True)
            break
        except (OSError, duckdb.Error):
            if attempt < attempts - 1:
                time.sleep(retry_delay_seconds)
                continue
            raise
    assert conn is not None  # nosec: loop either sets conn or raises
    try:
        yield conn
    finally:
        conn.close()


@dataclass
class DuckDBRepository:
    """Shared DuckDB helpers for read-only repository subclasses.

    Set ``guard_path_exists=True`` to silently return empty results when the
    database file does not yet exist (useful for optional/lazy-init stores).

    Connection reuse
    ----------------
    By default each ``_fetch_rows`` / ``_table_exists`` call opens and closes a
    fresh read-only connection. Methods that issue several queries (for example a
    ``_table_exists`` guard followed by a data query) can collapse those opens
    onto a single connection by wrapping the block in ``with self.scoped_connection():``.

    The active scoped connection is stored per-thread, so concurrent requests on
    the uvicorn thread pool never share a DuckDB connection (DuckDB connections
    are not thread-safe). The connection is closed when the outermost scope
    exits, which keeps the file-lock window short enough for a separate writer
    process to acquire read-write access between requests.
    """

    path: str
    guard_path_exists: bool = field(default=False, repr=False)
    # Backward-compat constructor flag only: every connection opened by this
    # class (see ``_connect_read_only``) is always ``read_only=True``,
    # regardless of the value passed here. Kept (rather than removed) because
    # existing callers/tests construct instances with ``read_only=False`` and
    # rely on connections still being forced read-only.
    read_only: bool = field(default=True, repr=False)
    transient_open_retries: int = field(default=3, repr=False)
    transient_open_retry_delay_seconds: float = field(default=0.05, repr=False)

    def __post_init__(self) -> None:
        # Per-thread holder for an active scoped connection. Never shared across
        # threads, so no locking is required for the connection itself.
        self._scope = threading.local()

    def healthcheck(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": False,
            "mode": "read_only",
            "path": self.path,
            "can_connect": False,
            "sql_roundtrip": False,
        }
        conn: duckdb.DuckDBPyConnection | None = None
        try:
            conn = self._connect_read_only()
            if conn is None:
                return result
            result["can_connect"] = True
            result["sql_roundtrip"] = conn.execute("select 1").fetchone() == (1,)
            result["ok"] = result["sql_roundtrip"]
        except (OSError, duckdb.Error):
            return result
        finally:
            if conn is not None:
                conn.close()
        return result

    @contextmanager
    def scoped_connection(self) -> Iterator[duckdb.DuckDBPyConnection | None]:
        """Reuse one read-only connection for every query issued in this block.

        Nested scopes reuse the outermost connection. On exit of the outermost
        scope the connection is closed. Returns ``None`` when the guarded path is
        missing or the connection could not be opened; queries issued inside such
        a scope return empty results, matching the non-scoped behaviour.
        """
        if getattr(self._scope, "active", False):
            # Already inside a scope on this thread: reuse it (possibly None).
            yield getattr(self._scope, "conn", None)
            return

        if self.guard_path_exists and not Path(self.path).exists():
            self._scope.active = True
            self._scope.conn = None
            try:
                yield None
            finally:
                self._scope.active = False
                self._scope.conn = None
            return

        conn = self._connect_read_only()
        self._scope.active = True
        self._scope.conn = conn
        try:
            yield conn
        finally:
            self._scope.active = False
            self._scope.conn = None
            if conn is not None:
                conn.close()

    def _fetch_rows(self, query: str, params: list[object] | None = None) -> list[tuple]:
        scoped = getattr(self._scope, "conn", None)
        if scoped is not None:
            return scoped.execute(query, params or []).fetchall()
        if getattr(self._scope, "active", False):
            # Inside a scope whose connection is unavailable (guarded/missing).
            return []
        if self.guard_path_exists and not Path(self.path).exists():
            return []
        conn = self._connect_read_only()
        if conn is None:
            return []
        try:
            return conn.execute(query, params or []).fetchall()
        finally:
            conn.close()

    def _table_exists(self, table_name: str) -> bool:
        scoped = getattr(self._scope, "conn", None)
        if scoped is not None:
            return catalog_presence_cached(
                self.path,
                "table",
                table_name,
                lambda: self._table_exists_on_conn(scoped, table_name),
            )
        if getattr(self._scope, "active", False):
            return False
        if self.guard_path_exists and not Path(self.path).exists():
            return False

        def _probe() -> bool:
            conn = self._connect_read_only()
            if conn is None:
                return False
            try:
                return self._table_exists_on_conn(conn, table_name)
            finally:
                conn.close()

        return catalog_presence_cached(self.path, "table", table_name, _probe)

    @staticmethod
    def _table_exists_on_conn(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = ?
            limit 1
            """,
            [table_name],
        ).fetchone()
        return row is not None

    def _connect_read_only(self) -> duckdb.DuckDBPyConnection | None:
        attempts = max(1, self.transient_open_retries)
        for attempt in range(attempts):
            try:
                return duckdb.connect(self.path, read_only=True)
            except (OSError, duckdb.Error):
                if attempt < attempts - 1:
                    time.sleep(self.transient_open_retry_delay_seconds)
                    continue
                if self.guard_path_exists:
                    return None
                raise
        return None
