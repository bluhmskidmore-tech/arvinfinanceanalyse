"""Load and apply `duckdb/*.sql` registry slices (MOSS:STMT boundaries)."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any, Callable

import duckdb

REGISTRY_DIR = Path(__file__).resolve().parent / "duckdb"
MANIFEST_PATH = REGISTRY_DIR / "manifest.json"

_STMT_BOUNDARY = re.compile(r"^\s*--\s*MOSS:STMT\s*$", re.MULTILINE)


def parse_registry_sql_text(text: str) -> list[str]:
    parts = _STMT_BOUNDARY.split(text)
    return [part.strip() for part in parts if part.strip()]


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def iter_registry_sql_files() -> list[Path]:
    manifest = load_manifest()
    return [REGISTRY_DIR / entry["path"] for entry in manifest["files"]]


def apply_registry_sql(conn: duckdb.DuckDBPyConnection) -> None:
    for path in iter_registry_sql_files():
        text = path.read_text(encoding="utf-8")
        for statement in parse_registry_sql_text(text):
            conn.execute(statement)


def resolve_ensure(entry: dict[str, Any]) -> Callable[[duckdb.DuckDBPyConnection], None]:
    module = importlib.import_module(entry["ensure_module"])
    target = getattr(module, entry["ensure_symbol"])
    return target


_META_TABLES = frozenset({"_schema_migrations"})


def main_schema_fingerprint(
    conn: duckdb.DuckDBPyConnection,
    *,
    exclude_meta_tables: bool = False,
) -> tuple[tuple[Any, ...], ...]:
    """Stable-ish schema shape: omit table_catalog/data_type to reduce DuckDB metadata drift."""
    tables = conn.execute(
        """
        select table_name, table_type
        from information_schema.tables
        where table_schema = 'main'
        order by table_name, table_type
        """
    ).fetchall()
    columns = conn.execute(
        """
        select table_name, column_name, ordinal_position
        from information_schema.columns
        where table_schema = 'main'
        order by table_name, ordinal_position, column_name
        """
    ).fetchall()
    if exclude_meta_tables:
        tables = tuple(t for t in tables if t[0] not in _META_TABLES)
        columns = tuple(c for c in columns if c[0] not in _META_TABLES)
    return (tuple(tables), tuple(columns))


def normalize_sql(text: str) -> str:
    return " ".join(text.split())


def is_ddl_statement(sql: str) -> bool:
    head = sql.lstrip().lower()
    return head.startswith("create ") or head.startswith("alter ") or head.startswith("create or replace ")


class _SqlCaptureConnection:
    """Wrap DuckDB connection: C-extension connections cannot take arbitrary attributes."""

    __slots__ = ("_conn", "_statements")

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_statements", [])

    @property
    def captured_statements(self) -> list[str]:
        return self._statements

    def execute(self, sql: str, *args: Any, **kwargs: Any):
        self._statements.append(sql.strip())
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def collect_ensure_sql_calls(ensure: Callable[..., None]) -> list[str]:
    raw = duckdb.connect(":memory:")
    try:
        capture = _SqlCaptureConnection(raw)
        ensure(capture)
        return list(capture.captured_statements)
    finally:
        raw.close()


def collect_ensure_ddl_calls(ensure: Callable[[duckdb.DuckDBPyConnection], None]) -> list[str]:
    return [stmt for stmt in collect_ensure_sql_calls(ensure) if is_ddl_statement(stmt)]


def load_manifest_ddl_statements() -> list[str]:
    statements: list[str] = []
    for path in iter_registry_sql_files():
        statements.extend(parse_registry_sql_text(path.read_text(encoding="utf-8")))
    return statements
