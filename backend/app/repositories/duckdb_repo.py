from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb


@dataclass
class DuckDBRepository:
    """Shared DuckDB helpers for read-only repository subclasses.

    Set ``guard_path_exists=True`` to silently return empty results when the
    database file does not yet exist (useful for optional/lazy-init stores).
    """

    path: str
    guard_path_exists: bool = field(default=False, repr=False)
    read_only: bool = field(default=True, repr=False)
    transient_open_retries: int = field(default=3, repr=False)
    transient_open_retry_delay_seconds: float = field(default=0.05, repr=False)

    def healthcheck(self) -> dict[str, object]:
        return {
            "ok": True,
            "mode": "read_only",
            "path": self.path,
        }

    def _fetch_rows(self, query: str, params: list[object] | None = None) -> list[tuple]:
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
        if self.guard_path_exists and not Path(self.path).exists():
            return False
        conn = self._connect_read_only()
        if conn is None:
            return False
        try:
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
        finally:
            conn.close()

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
