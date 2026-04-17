from __future__ import annotations

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

    def _fetch_rows(self, query: str, params: list[object] | None = None) -> list[tuple]:
        if self.guard_path_exists and not Path(self.path).exists():
            return []
        conn = duckdb.connect(self.path, read_only=True)
        try:
            return conn.execute(query, params or []).fetchall()
        finally:
            conn.close()

    def _table_exists(self, table_name: str) -> bool:
        if self.guard_path_exists and not Path(self.path).exists():
            return False
        conn = duckdb.connect(self.path, read_only=True)
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
