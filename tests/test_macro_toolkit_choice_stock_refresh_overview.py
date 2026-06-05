from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.services.macro_toolkit_service import choice_stock_refresh_overview


def test_choice_stock_refresh_overview_reports_freshness_and_fallback_dates(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?)",
            [("2026-05-05", "000001.SZ"), ("2026-05-05", "000002.SZ")],
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?)",
            [("2026-04-27", "000001.SZ"), ("2026-04-27", "000002.SZ")],
        )
    finally:
        conn.close()

    payload = choice_stock_refresh_overview(
        duckdb_path,
        tmp_path / "governance",
        reference_date="2026-05-06",
    )

    daily = payload["daily_observation"]
    factor = payload["factor_snapshot"]
    assert daily["freshness_status"] == "current"
    assert daily["reference_date"] == "2026-05-06"
    assert daily["stale_days"] == 1
    assert daily["fallback_mode"] == "none"
    assert daily["fallback_date"] is None
    assert factor["freshness_status"] == "stale"
    assert factor["reference_date"] == "2026-05-06"
    assert factor["stale_days"] == 9
    assert factor["fallback_mode"] == "latest_available"
    assert factor["fallback_date"] == "2026-04-27"
