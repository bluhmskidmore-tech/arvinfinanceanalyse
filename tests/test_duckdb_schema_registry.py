"""Verify DuckDB schema registry applies versioned migrations correctly."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry

_BASELINE_VERSION_COUNT = 19


def test_apply_pending_on_fresh_db(tmp_path) -> None:
    """All baseline migrations apply to an empty DuckDB file."""
    db_path = tmp_path / "registry_fresh.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    applied = registry.apply_pending()
    assert len(applied) == _BASELINE_VERSION_COUNT

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "zqtz_bond_daily_snapshot" in names
    assert "fact_formal_bond_analytics_daily" in names
    assert "fx_daily_mid" in names
    assert "_schema_migrations" in names


def test_idempotent_apply(tmp_path) -> None:
    """Running apply_pending twice produces no errors; second run applies nothing."""
    db_path = tmp_path / "registry_idempotent.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    assert len(registry.apply_pending()) == _BASELINE_VERSION_COUNT

    registry2 = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry2)
    assert registry2.apply_pending() == []


def test_migration_tracking(tmp_path) -> None:
    """Applied migrations are recorded in _schema_migrations table."""
    db_path = tmp_path / "registry_tracking.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry.apply_pending()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            "select version, description from _schema_migrations order by version"
        ).fetchall()
        versions = [row[0] for row in rows]
    finally:
        conn.close()

    assert versions == list(range(1, _BASELINE_VERSION_COUNT + 1))
    assert len(rows) == _BASELINE_VERSION_COUNT
    assert any("snapshot" in str(row[1]).lower() for row in rows)
    assert rows[-1] == (19, "bank ledger import traceability tables")


def test_duckdb_migration_registry_keeps_explicit_latest_version_contract() -> None:
    source = Path(__file__).resolve().parents[1] / "backend" / "app" / "repositories" / "duckdb_migrations.py"
    versions = [int(match) for match in re.findall(r"registry\.register\((\d+),", source.read_text(encoding="utf-8"))]

    assert versions == list(range(1, _BASELINE_VERSION_COUNT + 1))
