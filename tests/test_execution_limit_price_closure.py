"""Execution limit-down deferral closure (slice 40, ``stock_limit_price_daily``).

闭环:choice_native 段的 highlimit/lowlimit 只有"是/否"标志(无数值价),
execution 重建在跌停日 fail-open 误判可卖;stock_limit_price_daily 数值价
落地后,同一重建产生顺延退出(契约 §4.10 覆盖缺口修复)。
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.tasks.livermore_candidate_history_materialize import (
    backfill_livermore_candidate_execution_history,
    materialize_livermore_candidate_history,
)


def _seed_stock_adjustment_factors(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, float | None]],
) -> None:
    conn.execute(
        """
        create table if not exists stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double,
          source_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into stock_adjustment_factor
        (trade_date, stock_code, adj_factor, source_version, run_id)
        values (?, ?, ?, 'sv_test_adj', 'run-test-adj')
        """,
        rows,
    )


def _fake_payload(
    *,
    as_of_date: str,
    items: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "as_of_date": as_of_date,
            "requested_as_of_date": as_of_date,
            "stock_candidates": {"items": items},
            "market_gate": {"state": "HOT", "exposure": 0.5},
        },
        {
            "source_version": "sv_test_candidate_meta",
            "vendor_version": "vv_test_candidate_meta",
            "quality_flag": "ok",
        },
    )


def test_execution_rebuild_defers_limit_down_exit_with_numeric_limit_table(
    monkeypatch, tmp_path
) -> None:
    """闭环:2026 choice_native 段合成跌停日,execution 重建接入
    stock_limit_price_daily 数值价后产生顺延退出(契约 §4.10 覆盖缺口修复)。"""
    db_path = tmp_path / "execution-limit-price-closure.duckdb"
    snap = date(2026, 1, 5)
    stock = "000001.SZ"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        # choice_native 段:highlimit/lowlimit 是"是/否"标志(varchar),无数值价
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit varchar,
              lowlimit varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, 'trading', ?, ?)",
            [
                (snap.isoformat(), stock, 100.0, 100.0, "否", "否"),  # signal 日
                ("2026-01-06", stock, 95.0, 90.0, "否", "是"),  # entry 日=跌停日(标志)
                ("2026-01-07", stock, 91.0, 92.0, "否", "否"),  # 下一可卖日
            ],
        )
        _seed_stock_adjustment_factors(
            conn,
            [
                ((snap + timedelta(days=i)).isoformat(), stock, 1.0)
                for i in range(3)
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "Bank"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path), as_of_date=snap.isoformat())

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        baseline = conn.execute(
            "select exit_date_1d, exit_price_1d from livermore_candidate_execution_history where stock_code = ?",
            [stock],
        ).fetchone()
    finally:
        conn.close()
    # 现状 fail-open:标志列无数值价,跌停日被误判为可卖
    assert baseline == ("2026-01-06", 90.0)

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
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
        )
        conn.executemany(
            "insert into stock_limit_price_daily values (?, ?, ?, ?, ?, 'sv', "
            "'vv_tushare_stk_limit_20260106_0123456789ab', 'rv_stock_limit_price_daily_v1', 'run')",
            [
                ("2026-01-06", stock, 110.0, 90.0, 100.0),  # close 90 == down_limit → 跌停
                ("2026-01-07", stock, 99.0, 81.0, 90.0),
            ],
        )
        conn.execute("delete from livermore_candidate_execution_history")
    finally:
        conn.close()

    out = backfill_livermore_candidate_execution_history(
        str(db_path),
        start_date=snap.isoformat(),
        end_date=snap.isoformat(),
    )
    assert out["execution_row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rebuilt = conn.execute(
            "select exit_date_1d, exit_price_1d from livermore_candidate_execution_history where stock_code = ?",
            [stock],
        ).fetchone()
    finally:
        conn.close()
    # 数值价落地后:跌停日顺延到下一可卖日
    assert rebuilt == ("2026-01-07", 92.0)
