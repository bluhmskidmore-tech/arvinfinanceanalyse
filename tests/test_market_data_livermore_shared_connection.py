"""Livermore read-path loaders reuse a shared read-only connection.

Verifies the demonstration wiring: when the orchestrator passes one connection,
each loader queries on it and does NOT close it, so a single request opens the
DuckDB file once for the macro-history + cycle-evidence loaders instead of once
per loader.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.services.market_data_livermore_service import (
    BROAD_INDEX_SERIES_ID,
    _load_broad_index_history,
    _shared_read_only_connection,
)


def _seed_broad_index(conn: duckdb.DuckDBPyConnection, *, start: date, days: int) -> None:
    conn.execute(
        """
        create table fact_choice_macro_daily (
          series_id varchar,
          trade_date varchar,
          value_numeric double,
          source_version varchar,
          vendor_version varchar,
          quality_flag varchar
        )
        """
    )
    rows = [
        (
            BROAD_INDEX_SERIES_ID,
            (start + timedelta(days=offset)).isoformat(),
            3200.0 + offset,
            "sv",
            "vv",
            "ok",
        )
        for offset in range(days)
    ]
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?)",
        rows,
    )


def test_broad_index_loader_reuses_shared_connection(tmp_path):
    db_path = tmp_path / "moss.duckdb"
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_broad_index(writer, start=date(2026, 1, 1), days=5)
    finally:
        writer.close()

    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        rows_a, tables_a = _load_broad_index_history(
            duckdb_path=str(db_path),
            as_of_date=None,
            conn=shared_conn,
        )
        # Loader must not close a borrowed connection: a second query still works.
        rows_b, _ = _load_broad_index_history(
            duckdb_path=str(db_path),
            as_of_date=None,
            conn=shared_conn,
        )
        assert shared_conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 5

    assert len(rows_a) == 5
    assert rows_a == rows_b
    assert "fact_choice_macro_daily" in tables_a


def test_broad_index_loader_still_self_manages_without_shared_connection(tmp_path):
    db_path = tmp_path / "moss.duckdb"
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_broad_index(writer, start=date(2026, 1, 1), days=3)
    finally:
        writer.close()

    rows, tables = _load_broad_index_history(duckdb_path=str(db_path), as_of_date=None)
    assert len(rows) == 3
    assert "fact_choice_macro_daily" in tables


def test_shared_connection_helper_yields_none_for_missing_file(tmp_path):
    missing = tmp_path / "absent.duckdb"
    with _shared_read_only_connection(str(missing)) as conn:
        assert conn is None
