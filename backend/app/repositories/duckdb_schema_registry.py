"""
Lightweight schema versioning for DuckDB tables.
Each migration is a named Python function registered with a version number.
The registry tracks applied versions in a `_schema_migrations` meta-table
inside the DuckDB file itself.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

Migration = Callable[[duckdb.DuckDBPyConnection], None]


def _connection_has_explicit_transaction(conn: duckdb.DuckDBPyConnection) -> bool:
    """Detect whether consecutive statements share a caller-owned transaction."""
    first_id = conn.execute("select txid_current()").fetchone()[0]
    second_id = conn.execute("select txid_current()").fetchone()[0]
    return first_id == second_id


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
            caller_owns_transaction = _connection_has_explicit_transaction(conn)
            if caller_owns_transaction:
                migration_table_exists = conn.execute(
                    """
                    select count(*)
                    from information_schema.tables
                    where table_schema = 'main' and table_name = '_schema_migrations'
                    """
                ).fetchone() == (1,)
            else:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS _schema_migrations (
                        version INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT current_timestamp
                    )
                    """
                )
                migration_table_exists = True

            applied = (
                {
                    row[0]
                    for row in conn.execute(
                        "SELECT version FROM _schema_migrations"
                    ).fetchall()
                }
                if migration_table_exists
                else set()
            )
            pending_migrations = [
                migration
                for migration in sorted(self._migrations, key=lambda item: item[0])
                if migration[0] not in applied
            ]
            if not pending_migrations:
                return []

            if caller_owns_transaction and not migration_table_exists:
                conn.execute(
                    """
                    CREATE TABLE _schema_migrations (
                        version INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT current_timestamp
                    )
                    """
                )

            for version, description, fn in pending_migrations:
                logger.info("Applying DuckDB migration v%d: %s", version, description)
                if not caller_owns_transaction:
                    conn.execute("BEGIN TRANSACTION")
                try:
                    fn(conn)
                    conn.execute(
                        "INSERT INTO _schema_migrations (version, description) VALUES (?, ?)",
                        [version, description],
                    )
                    if not caller_owns_transaction:
                        conn.execute("COMMIT")
                except Exception:
                    if caller_owns_transaction:
                        # DuckDB has no savepoints. Discard the whole caller
                        # transaction, then leave an empty replacement active
                        # so an outer rollback/commit cannot mask this error.
                        conn.execute("ROLLBACK")
                        conn.execute("BEGIN TRANSACTION")
                    else:
                        conn.execute("ROLLBACK")
                    raise
                applied_descriptions.append(f"v{version}: {description}")
            return applied_descriptions
        finally:
            if close_conn:
                conn.close()
