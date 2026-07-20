from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.portfolio_paths import (
    calculate_path_horizon_exit,
    load_position_price_paths,
    position_path_key,
)


def test_load_position_price_paths_forward_fills_missing_adjustment_factor() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-06-01", 10.0, 10.5, 9.8, 10.2, 1000.0, 10_000.0, "Trading", 11.0, 9.0),
                ("2026-06-02", 10.2, 10.7, 10.0, 10.5, 1100.0, 11_000.0, "Trading", 11.5, 9.5),
                ("2026-06-03", 10.5, 10.8, 10.1, 10.4, 1200.0, 12_000.0, "Trading", 11.6, 9.6),
            ],
        )
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, ?, 'sv', 'run')",
            [
                ("2026-06-01", 1.0),
                ("2026-06-02", 1.1),
            ],
        )

        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-06-01"}],
            max_horizon_days=3,
        )
    finally:
        conn.close()

    rows = paths[position_path_key("000001.SZ", "2026-06-01")]
    assert [row["trade_date"] for row in rows] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert {row["path_price_basis"] for row in rows} == {"adjusted"}
    assert rows[0]["adj_open"] == 10.0
    assert rows[1]["adj_close"] == 11.55
    assert rows[2]["adj_factor_missing"] is True
    assert rows[2]["adj_factor_forward_filled"] is True
    assert rows[2]["adj_factor"] == 1.1
    assert rows[2]["adj_close"] == pytest.approx(11.44)
    assert calculate_path_horizon_exit(
        rows,
        horizon_days=2,
        entry_price=10.0,
        buy_cost_rate=0.0,
        sell_cost_rate=0.0,
        slippage_rate=0.0,
    )["return_net"] == pytest.approx(0.155)


def test_load_position_price_paths_uses_raw_only_when_factor_cannot_be_filled() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10, 10.5, 9.8, ?, 1000, 10000, 'Trading', 11, 9)",
            [
                ("2026-06-01", 10.2),
                ("2026-06-02", 10.5),
            ],
        )

        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-06-01"}],
            max_horizon_days=2,
        )
    finally:
        conn.close()

    rows = paths[position_path_key("000001.SZ", "2026-06-01")]
    assert {row["path_price_basis"] for row in rows} == {"raw_fallback_missing_adj_factor"}
    assert all(row["adj_factor_missing"] is True for row in rows)
    assert all(row["adj_factor_forward_filled"] is False for row in rows)


def test_load_position_price_paths_keeps_delay_buffer_for_blocked_exits() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        start = date(2026, 6, 1)
        trade_dates = [(start + timedelta(days=index)).isoformat() for index in range(37)]
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10, 10, ?, ?, 1000, 10000, 'Trading', 20, ?)",
            [(trade_date, 10.0, 10.0, 1.0) for trade_date in trade_dates[:19]]
            + [(trade_date, 9.0, 9.0, 9.0) for trade_date in trade_dates[19:36]]
            + [(trade_dates[36], 8.5, 8.8, 7.8)],
        )

        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-06-01"}],
            max_horizon_days=25,
        )
    finally:
        conn.close()

    rows = paths[position_path_key("000001.SZ", "2026-06-01")]
    assert rows[-1]["trade_date"] == "2026-07-07"
    assert calculate_path_horizon_exit(
        rows,
        horizon_days=20,
        entry_price=10.0,
        buy_cost_rate=0.0,
        sell_cost_rate=0.0,
        slippage_rate=0.0,
    )["exit_date"] == "2026-07-07"
