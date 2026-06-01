"""Verify DuckDB schema registry applies versioned migrations correctly."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry

_BASELINE_VERSION_COUNT = 29


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
    assert "fact_commodity_futures_daily" in names
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
    assert rows[-1] == (29, "Commodity futures main-contract daily ingest")


def test_legacy_missing_zqtz_tables_can_still_recover_current_schema(tmp_path) -> None:
    """A macro-only legacy DB may record ZQTZ patch migrations before ZQTZ tables exist."""
    db_path = tmp_path / "legacy_macro_only.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table _schema_migrations (
              version integer primary key,
              description text not null,
              applied_at timestamp default current_timestamp
            )
            """
        )
        for version in range(1, 17):
            conn.execute(
                "insert into _schema_migrations (version, description) values (?, ?)",
                [version, "applied"],
            )
    finally:
        conn.close()

    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry.apply_pending()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        zqtz_columns = {
            row[0]
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = 'zqtz_bond_daily_snapshot'
                """
            ).fetchall()
        }
        formal_columns = {
            row[0]
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = 'fact_formal_zqtz_balance_daily'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"business_type_primary", "sub_type"} <= zqtz_columns
    assert {"business_type_primary", "sub_type"} <= formal_columns


def test_duckdb_migration_registry_keeps_explicit_latest_version_contract() -> None:
    source = Path(__file__).resolve().parents[1] / "backend" / "app" / "repositories" / "duckdb_migrations.py"
    versions = [int(match) for match in re.findall(r"registry\.register\((\d+),", source.read_text(encoding="utf-8"))]

    assert versions == list(range(1, _BASELINE_VERSION_COUNT + 1))
