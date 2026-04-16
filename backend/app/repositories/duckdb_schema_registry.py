"""
Lightweight schema versioning for DuckDB tables.
Each migration is a named Python function registered with a version number.
The registry tracks applied versions in a `_schema_migrations` meta-table
inside the DuckDB file itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import duckdb

logger = logging.getLogger(__name__)

Migration = Callable[[duckdb.DuckDBPyConnection], None]


def main_database_file_path(conn: duckdb.DuckDBPyConnection) -> str | None:
    """Return resolved on-disk path for `main`, or None for in-memory databases."""
    rows = conn.execute("PRAGMA database_list").fetchall()
    for _db_id, name, file_path in rows:
        if name == "main" and file_path and file_path != ":memory:":
            return str(Path(file_path).resolve())
    return None


@dataclass
class DuckDBSchemaRegistry:
    db_path: str
    _migrations: list[tuple[int, str, Migration]] = field(init=False, default_factory=list, repr=False)

    def register(self, version: int, description: str, fn: Migration) -> None:
        self._migrations.append((version, description, fn))

    def apply_pending(self, conn: duckdb.DuckDBPyConnection | None = None) -> list[str]:
        """Apply pending migrations. Pass `conn` to run on an existing open connection (avoids file lock issues)."""
        close_conn = False
        if conn is None:
            path = Path(self.db_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = duckdb.connect(str(path), read_only=False)
            close_conn = True
        applied_descriptions: list[str] = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT current_timestamp
                )
                """
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM _schema_migrations").fetchall()}
            for version, description, fn in sorted(self._migrations, key=lambda item: item[0]):
                if version in applied:
                    continue
                logger.info("Applying DuckDB migration v%d: %s", version, description)
                if close_conn:
                    conn.execute("BEGIN TRANSACTION")
                try:
                    fn(conn)
                    conn.execute(
                        "INSERT INTO _schema_migrations (version, description) VALUES (?, ?)",
                        [version, description],
                    )
                    if close_conn:
                        conn.execute("COMMIT")
                except Exception:
                    if close_conn:
                        conn.execute("ROLLBACK")
                    raise
                applied_descriptions.append(f"v{version}: {description}")
            return applied_descriptions
        finally:
            if close_conn:
                conn.close()
