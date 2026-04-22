"""DuckDB DDL ensure helpers for M2b external std + legacy read views."""

from __future__ import annotations

import duckdb
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text


def ensure_std_external_macro_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply ``15_external_std_macro.sql`` on the connection."""
    text = (REGISTRY_DIR / "15_external_std_macro.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def ensure_external_vw_legacy_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply ``16_external_vw_legacy.sql`` on the connection."""
    text = (REGISTRY_DIR / "16_external_vw_legacy.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)
