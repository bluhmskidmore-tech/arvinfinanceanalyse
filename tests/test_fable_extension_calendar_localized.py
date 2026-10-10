from __future__ import annotations

import duckdb

from scripts.run_fable_extension_study import load_trading_calendar


def test_trading_calendar_accepts_canonical_localized_trading_statuses() -> None:
    conn = duckdb.connect()
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10.0, ?)",
            [
                ("2026-06-01", "\u4ea4\u6613"),
                ("2026-06-02", "\u6b63\u5e38\u4ea4\u6613"),
                ("2026-06-03", "\u505c\u724c"),
            ],
        )

        dates = load_trading_calendar(conn)
    finally:
        conn.close()

    assert dates == ["2026-06-01", "2026-06-02"]
