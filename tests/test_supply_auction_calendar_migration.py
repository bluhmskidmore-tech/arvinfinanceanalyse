from __future__ import annotations

import duckdb

from backend.app.duckdb_schema_bootstrap import upgrade_duckdb_schema_head


def test_duckdb_bootstrap_creates_supply_auction_calendar_read_model(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "supply-auction-bootstrap.duckdb"
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

    assert "std_external_supply_auction_calendar" in names
    assert "vw_external_supply_auction_calendar" in names
