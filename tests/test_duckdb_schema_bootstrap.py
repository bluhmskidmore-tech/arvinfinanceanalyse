from __future__ import annotations

import duckdb

from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head


def test_duckdb_bootstrap_creates_expected_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "boot.duckdb"
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "0")
    monkeypatch.setenv("MOSS_SKIP_POSTGRES_MIGRATIONS", "0")
    monkeypatch.delenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", raising=False)
    monkeypatch.delenv("MOSS_SKIP_POSTGRES_MIGRATIONS", raising=False)

    upgrade_duckdb_schema_head(duckdb_path=str(db_path))

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
    assert "phase1_source_preview_summary" in names
    assert "fact_formal_pnl_fi" in names
    assert "phase1_materialize_runs" in names
    assert "fx_daily_mid" in names
    assert "market_data_series_category" in names
    assert "choice_news_event" in names


def test_duckdb_bootstrap_skipped_when_flag_set(tmp_path, monkeypatch):
    db_path = tmp_path / "skip.duckdb"
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    upgrade_duckdb_schema_head(duckdb_path=str(db_path))
    assert not db_path.exists()
