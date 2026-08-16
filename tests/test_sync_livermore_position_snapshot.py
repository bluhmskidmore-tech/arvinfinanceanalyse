from __future__ import annotations

import duckdb

from backend.app.tasks.livermore_position_snapshot_materialize import (
    _materialize_livermore_position_snapshot_rows as materialize_rows,
)
from backend.app.tasks.livermore_position_snapshot_materialize import (
    ensure_livermore_position_snapshot_schema,
)
from scripts.sync_livermore_position_snapshot import sync_livermore_position_snapshot

PROXY_SOURCE_SYSTEM = "obsidian_proxy_position"


def _seed_csi300_trade_dates(duckdb_path, dates: list[str]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_choice_macro_daily (series_id, trade_date) values (?, ?)",
            [("CA.CSI300", trade_date) for trade_date in dates],
        )
    finally:
        conn.close()


def _seed_active_row(
    duckdb_path,
    *,
    as_of_date: str,
    stock_code: str = "002837.SZ",
    bars_since_entry: int = 5,
    source_system: str = PROXY_SOURCE_SYSTEM,
) -> None:
    materialize_rows(
        as_of_date=as_of_date,
        rows=[
            {
                "stock_code": stock_code,
                "stock_name": "Test Stock",
                "entry_cost": 10.0,
                "bars_since_entry": bars_since_entry,
                "position_status": "ACTIVE",
                "source_system": source_system,
            }
        ],
        duckdb_path=str(duckdb_path),
        run_id="seed-run",
    )


def _insert_raw_row(
    duckdb_path,
    *,
    as_of_date: str,
    stock_code: str,
    position_status: str,
    bars_since_entry: int = 5,
    source_system: str = PROXY_SOURCE_SYSTEM,
) -> None:
    """Insert a row directly via SQL, bypassing the ACTIVE-only materialize filter.

    Used to simulate a non-ACTIVE row landing in the table (e.g. a future write
    path change) so the sync script's own ACTIVE filter can be exercised.
    """
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_livermore_position_snapshot_schema(conn)
        conn.execute(
            """
            insert into livermore_position_snapshot (
              as_of_date, stock_code, stock_name, entry_cost, bars_since_entry,
              position_status, source_system, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [as_of_date, stock_code, "Raw Row", 10.0, bars_since_entry, position_status, source_system, "raw-seed"],
        )
    finally:
        conn.close()


def test_sync_rolls_bars_since_entry_forward_by_intervening_trading_days(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_active_row(duckdb_path, as_of_date="2026-08-05", bars_since_entry=5)
    # 08-05 (source, exclusive), 08-06, 08-07 trading days, 08-08/09 weekend (absent), 08-10, 08-11.
    _seed_csi300_trade_dates(
        duckdb_path,
        ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11"],
    )

    result = sync_livermore_position_snapshot(duckdb_path=duckdb_path, target_as_of="2026-08-11")

    assert result["status"] == "completed"
    assert result["source_as_of_date"] == "2026-08-05"
    assert result["target_as_of_date"] == "2026-08-11"
    assert result["trading_day_delta"] == 4  # 08-06, 08-07, 08-10, 08-11
    # risk_exit_input_status/_block_reason also depend on close-history landing
    # (choice_stock_daily_observation), which is out of scope for this roll-
    # forward-only fixture; covered separately by the daily-refresh integration.
    assert result["risk_exit_input_status"] in {"ready", "blocked"}

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select as_of_date, stock_code, bars_since_entry, position_status, source_system
            from livermore_position_snapshot
            order by as_of_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("2026-08-05", "002837.SZ", 5, "ACTIVE", PROXY_SOURCE_SYSTEM),
        ("2026-08-11", "002837.SZ", 9, "ACTIVE", PROXY_SOURCE_SYSTEM),
    ]


def test_sync_is_idempotent_once_source_reaches_target_date(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_active_row(duckdb_path, as_of_date="2026-08-05", bars_since_entry=5)
    _seed_csi300_trade_dates(
        duckdb_path,
        ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11"],
    )

    first = sync_livermore_position_snapshot(duckdb_path=duckdb_path, target_as_of="2026-08-11")
    assert first["status"] == "completed"

    second = sync_livermore_position_snapshot(duckdb_path=duckdb_path, target_as_of="2026-08-11")
    assert second["status"] == "noop"
    assert second["source_as_of_date"] == "2026-08-11"
    assert second["target_as_of_date"] == "2026-08-11"
    assert second["risk_exit_input_status"] in {"ready", "blocked"}

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            "select as_of_date, bars_since_entry from livermore_position_snapshot order by as_of_date"
        ).fetchall()
    finally:
        conn.close()

    # Still exactly the source row plus the single rolled-forward row: no duplicate write.
    assert rows == [("2026-08-05", 5), ("2026-08-11", 9)]


def test_sync_does_not_copy_non_active_rows(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _insert_raw_row(
        duckdb_path,
        as_of_date="2026-08-05",
        stock_code="002837.SZ",
        position_status="ACTIVE",
        bars_since_entry=5,
    )
    _insert_raw_row(
        duckdb_path,
        as_of_date="2026-08-05",
        stock_code="600000.SH",
        position_status="CLOSED",
        bars_since_entry=3,
    )
    _seed_csi300_trade_dates(duckdb_path, ["2026-08-05", "2026-08-06"])

    result = sync_livermore_position_snapshot(duckdb_path=duckdb_path, target_as_of="2026-08-06")

    assert result["status"] == "completed"
    assert result["materialize_result"]["row_count"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rolled_codes = {
            row[0]
            for row in conn.execute(
                "select stock_code from livermore_position_snapshot where as_of_date = ?",
                ["2026-08-06"],
            ).fetchall()
        }
    finally:
        conn.close()

    assert rolled_codes == {"002837.SZ"}


def test_sync_blocked_when_no_active_rows_exist(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _insert_raw_row(
        duckdb_path,
        as_of_date="2026-08-05",
        stock_code="600000.SH",
        position_status="CLOSED",
    )
    _seed_csi300_trade_dates(duckdb_path, ["2026-08-05", "2026-08-06"])

    result = sync_livermore_position_snapshot(duckdb_path=duckdb_path, target_as_of="2026-08-06")

    assert result["status"] == "blocked"
    assert "No ACTIVE" in result["reason"]
