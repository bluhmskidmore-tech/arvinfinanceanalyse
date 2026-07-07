from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import duckdb


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
    read_only: bool = field(default=True, repr=False)
    transient_open_retries: int = field(default=3, repr=False)
    transient_open_retry_delay_seconds: float = field(default=0.05, repr=False)

    def __post_init__(self) -> None:
        # Per-thread holder for an active scoped connection. Never shared across
        # threads, so no locking is required for the connection itself.
        self._scope = threading.local()

    def healthcheck(self) -> dict[str, object]:
        return {
            "ok": True,
            "mode": "read_only",
            "path": self.path,
        }

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
            return self._table_exists_on_conn(scoped, table_name)
        if getattr(self._scope, "active", False):
            return False
        if self.guard_path_exists and not Path(self.path).exists():
            return False
        conn = self._connect_read_only()
        if conn is None:
            return False
        try:
            return self._table_exists_on_conn(conn, table_name)
        finally:
            conn.close()

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
