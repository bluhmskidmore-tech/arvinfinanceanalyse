from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.portfolio_paths import (
    LIMIT_PRICE_SOURCE_MISSING,
    LIMIT_PRICE_SOURCE_OBSERVATION,
    LIMIT_PRICE_SOURCE_TABLE,
    calculate_path_horizon_exit,
    load_position_price_paths,
    position_path_key,
)

_OBS_FLAG_ERA_DDL = """
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
  highlimit varchar,
  lowlimit varchar
)
"""

_LIMIT_PRICE_TABLE_DDL = """
create table stock_limit_price_daily (
  trade_date varchar,
  stock_code varchar,
  up_limit double,
  down_limit double,
  pre_close double,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
"""


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


def test_limit_price_source_three_states_prefer_numeric_table() -> None:
    """三态：新表数值优先 > observation try_cast 回退 > missing 维持 fail-open。"""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_OBS_FLAG_ERA_DDL)
        conn.execute(_LIMIT_PRICE_TABLE_DDL)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10, 10.5, 8.9, ?, 1000, 10000, 'Trading', ?, ?)",
            [
                # choice_native 标志行 + 新表数值行 → stk_limit 优先
                ("2026-01-05", 9.0, "是", "是"),
                # tushare 代际数值字符串行,新表无行 → observation_cast 回退
                ("2026-01-06", 9.45, "11.55", "9.45"),
                # choice_native 标志行,新表无行 → missing(现状 fail-open)
                ("2026-01-07", 9.0, "否", "否"),
            ],
        )
        conn.execute(
            "insert into stock_limit_price_daily values "
            "('2026-01-05', '000001.SZ', 11.0, 9.0, 10.0, 'sv', "
            "'vv_tushare_stk_limit_20260105_0123456789ab', 'rv_stock_limit_price_daily_v1', 'run')"
        )
        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-01-05"}],
            max_horizon_days=5,
        )
    finally:
        conn.close()

    rows = paths[position_path_key("000001.SZ", "2026-01-05")]
    assert [row["limit_price_source"] for row in rows] == [
        LIMIT_PRICE_SOURCE_TABLE,
        LIMIT_PRICE_SOURCE_OBSERVATION,
        LIMIT_PRICE_SOURCE_MISSING,
    ]
    assert rows[0]["lowlimit"] == 9.0
    assert rows[0]["highlimit"] == 11.0
    assert rows[0]["limit_down"] is True  # close 9.0 == down_limit 9.0
    assert rows[1]["lowlimit"] == 9.45
    assert rows[1]["limit_down"] is True  # tushare 代际旧数值仍可用
    assert rows[2]["lowlimit"] is None
    assert rows[2]["limit_down"] is False  # 无数值价,维持 fail-open


def test_limit_price_table_partial_row_falls_back_to_observation() -> None:
    """半缺失防护:新表行 up/down 任一缺失即视为不可用,回退 observation/missing。"""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_OBS_FLAG_ERA_DDL)
        conn.execute(_LIMIT_PRICE_TABLE_DDL)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10, 10.5, 8.9, 9.45, 1000, 10000, 'Trading', ?, ?)",
            [
                # 新表半缺失(只有 up)+ observation 数值 → 回退 observation_cast
                ("2026-01-05", "11.55", "9.45"),
                # 新表半缺失(只有 down)+ observation 标志 → missing
                ("2026-01-06", "否", "否"),
            ],
        )
        conn.executemany(
            "insert into stock_limit_price_daily values (?, '000001.SZ', ?, ?, 10.5, 'sv', "
            "'vv_tushare_stk_limit_20260105_0123456789ab', 'rv_stock_limit_price_daily_v1', 'run')",
            [
                ("2026-01-05", 11.0, None),
                ("2026-01-06", None, 9.0),
            ],
        )
        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-01-05"}],
            max_horizon_days=5,
        )
    finally:
        conn.close()

    rows = paths[position_path_key("000001.SZ", "2026-01-05")]
    assert rows[0]["limit_price_source"] == LIMIT_PRICE_SOURCE_OBSERVATION
    assert rows[0]["lowlimit"] == 9.45
    assert rows[0]["highlimit"] == 11.55
    assert rows[1]["limit_price_source"] == LIMIT_PRICE_SOURCE_MISSING
    assert rows[1]["lowlimit"] is None
    assert rows[1]["limit_down"] is False


def test_limit_down_deferral_recovers_on_native_era_with_numeric_table() -> None:
    """2026 choice_native 段合成跌停日:无新表误判可卖,新表落地后顺延恢复。"""
    observation_rows = [
        # (trade_date, close, highlimit_flag, lowlimit_flag)
        ("2026-01-05", 10.0, "否", "否"),
        ("2026-01-06", 9.0, "否", "是"),  # 跌停日:标志列无数值价
        ("2026-01-07", 9.2, "否", "否"),
    ]

    def _build(conn: duckdb.DuckDBPyConnection, *, with_limit_table: bool) -> list[dict[str, object]]:
        conn.execute(_OBS_FLAG_ERA_DDL)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, ?, ?, ?, 1000, 10000, 'Trading', ?, ?)",
            [
                (trade_date, close, close, close, close, high_flag, low_flag)
                for trade_date, close, high_flag, low_flag in observation_rows
            ],
        )
        if with_limit_table:
            conn.execute(_LIMIT_PRICE_TABLE_DDL)
            conn.executemany(
                "insert into stock_limit_price_daily values (?, '000001.SZ', ?, ?, ?, 'sv', "
                "'vv_tushare_stk_limit_20260106_0123456789ab', 'rv_stock_limit_price_daily_v1', 'run')",
                [
                    ("2026-01-06", 11.0, 9.0, 10.0),  # down_limit == 当日 close → 跌停
                    ("2026-01-07", 9.9, 8.1, 9.0),
                ],
            )
        paths = load_position_price_paths(
            conn,
            [{"stock_code": "000001.SZ", "entry_date": "2026-01-05"}],
            max_horizon_days=5,
        )
        return paths[position_path_key("000001.SZ", "2026-01-05")]

    def _exit_date(rows: list[dict[str, object]]) -> str:
        return calculate_path_horizon_exit(
            rows,
            horizon_days=2,
            entry_price=10.0,
            buy_cost_rate=0.0,
            sell_cost_rate=0.0,
            slippage_rate=0.0,
        )["exit_date"]

    conn = duckdb.connect(":memory:")
    try:
        baseline_rows = _build(conn, with_limit_table=False)
    finally:
        conn.close()
    # 现状 fail-open:跌停日被误判为可卖
    assert baseline_rows[1]["limit_price_source"] == LIMIT_PRICE_SOURCE_MISSING
    assert baseline_rows[1]["limit_down"] is False
    assert _exit_date(baseline_rows) == "2026-01-06"

    conn = duckdb.connect(":memory:")
    try:
        recovered_rows = _build(conn, with_limit_table=True)
    finally:
        conn.close()
    # 新表数值价落地:跌停日顺延到下一可卖日
    assert recovered_rows[1]["limit_price_source"] == LIMIT_PRICE_SOURCE_TABLE
    assert recovered_rows[1]["limit_down"] is True
    assert _exit_date(recovered_rows) == "2026-01-07"
