from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.services import macro_toolkit_service
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


def test_choice_stock_refresh_overview_reuses_one_duckdb_connection(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
        conn.execute("insert into choice_stock_daily_observation values ('2026-05-05', '000001.SZ')")
        conn.execute("insert into choice_stock_factor_snapshot values ('2026-05-05', '000001.SZ')")
    finally:
        conn.close()

    original_connect = duckdb.connect
    connect_paths: list[str] = []

    def counting_connect(*args, **kwargs):
        connect_paths.append(str(args[0]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", counting_connect)

    payload = choice_stock_refresh_overview(
        duckdb_path,
        tmp_path / "governance",
        reference_date="2026-05-06",
    )

    assert connect_paths == [str(duckdb_path)]
    assert payload["daily_observation"]["status"] == "ok"
    assert payload["factor_snapshot"]["status"] == "ok"


def test_choice_stock_refresh_overview_reuses_table_status_for_different_reference_dates(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
        conn.execute("insert into choice_stock_daily_observation values ('2026-05-05', '000001.SZ')")
        conn.execute("insert into choice_stock_factor_snapshot values ('2026-04-27', '000001.SZ')")
    finally:
        conn.close()

    original_connect = duckdb.connect
    connect_paths: list[str] = []

    def counting_connect(*args, **kwargs):
        connect_paths.append(str(args[0]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", counting_connect)

    first = choice_stock_refresh_overview(
        duckdb_path,
        tmp_path / "governance",
        reference_date="2026-05-06",
    )
    second = choice_stock_refresh_overview(
        duckdb_path,
        tmp_path / "governance",
        reference_date="2026-05-08",
    )

    assert connect_paths == [str(duckdb_path)]
    assert first["daily_observation"]["stale_days"] == 1
    assert second["daily_observation"]["stale_days"] == 3
    assert first["factor_snapshot"]["stale_days"] == 9
    assert second["factor_snapshot"]["stale_days"] == 11
