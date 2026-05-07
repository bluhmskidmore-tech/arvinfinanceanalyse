from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.services.market_data_livermore_service import (
    _load_risk_exit_snapshots,
    _risk_exit_input_block_reason,
)
from backend.app.tasks.livermore_position_snapshot_materialize import (
    ensure_livermore_position_snapshot_schema,
)


def test_market_data_risk_exit_reads_only_active_stock_position_facts(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    as_of_date = "2026-04-29"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_livermore_position_snapshot_schema(conn)
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              close_value double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        position_rows = [
            (
                as_of_date,
                "000001.SZ",
                "Alpha",
                10.5,
                6,
                "2026-04-21",
                10000.0,
                "ACTIVE",
                "stock_position_book",
                "sha256:test",
                2,
                "sv_position_active",
                "vv_position_active",
                "rv_livermore_position_snapshot_v1",
                "run-test",
            ),
            (
                as_of_date,
                "000002.SZ",
                "Beta",
                8.2,
                3,
                "2026-04-25",
                0.0,
                "CLOSED",
                "stock_position_book",
                "sha256:test",
                3,
                "sv_position_closed",
                "vv_position_closed",
                "rv_livermore_position_snapshot_v1",
                "run-test",
            ),
        ]
        conn.executemany(
            """
            insert into livermore_position_snapshot (
              as_of_date, stock_code, stock_name, entry_cost, bars_since_entry,
              entry_date, position_quantity, position_status, source_system,
              source_file_hash, source_row_no, source_version, vendor_version,
              rule_version, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            position_rows,
        )
        start_date = date.fromisoformat(as_of_date) - timedelta(days=11)
        daily_rows = [
            (
                stock_code,
                (start_date + timedelta(days=offset)).isoformat(),
                10.0 + offset,
                "sv_daily",
                "vv_daily",
            )
            for stock_code in ("000001.SZ", "000002.SZ")
            for offset in range(12)
        ]
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?)",
            daily_rows,
        )
    finally:
        conn.close()

    snapshots, tables_used, source_versions, vendor_versions = _load_risk_exit_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date=as_of_date,
    )

    assert [snapshot.stock_code for snapshot in snapshots] == ["000001.SZ"]
    assert tables_used == ["livermore_position_snapshot", "choice_stock_daily_observation"]
    assert "sv_position_active" in source_versions
    assert "sv_position_closed" not in source_versions
    assert "vv_position_active" in vendor_versions
    assert "vv_position_closed" not in vendor_versions


def test_risk_exit_input_block_reason_reports_missing_position_table(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              close_value double
            )
            """
        )
    finally:
        conn.close()

    reason = _risk_exit_input_block_reason(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-29",
    )

    assert "livermore_position_snapshot table is not materialized" in reason


def test_risk_exit_input_block_reason_reports_no_active_stock_positions(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    as_of_date = "2026-04-29"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_livermore_position_snapshot_schema(conn)
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              close_value double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_position_snapshot (
              as_of_date, stock_code, stock_name, entry_cost, bars_since_entry,
              entry_date, position_quantity, position_status, source_system,
              source_file_hash, source_row_no, source_version, vendor_version,
              rule_version, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                as_of_date,
                "000001.SZ",
                "Alpha",
                10.5,
                6,
                "2026-04-21",
                0.0,
                "CLOSED",
                "stock_position_book",
                "sha256:test",
                2,
                "sv_position_closed",
                "vv_position_closed",
                "rv_livermore_position_snapshot_v1",
                "run-test",
            ],
        )
    finally:
        conn.close()

    reason = _risk_exit_input_block_reason(
        duckdb_path=str(duckdb_path),
        as_of_date=as_of_date,
    )

    assert "no ACTIVE A-share rows for as_of_date 2026-04-29" in reason
