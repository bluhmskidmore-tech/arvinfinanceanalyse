"""choice_stock_daily_observation 单位归一化 SQL 表达式的行为锁定。

单位契约见 docs/data_contracts.md §4.10:tushare 代际 amount=千元/volume=手,
choice_native 代际 amount=元/volume=股,NULL/空白 vendor 无法定标输出 NULL。
"""

from __future__ import annotations

import duckdb

from backend.app.repositories.choice_stock_units import (
    amount_rmb_sql,
    scale_unknown_sql,
    volume_shares_sql,
)


def _seeded_connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        create table choice_stock_daily_observation (
          stock_code varchar,
          amount double,
          volume double,
          vendor_version varchar
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?)",
        [
            ("TUSHARE.SZ", 300_000.0, 1_000.0, "vv_choice_tushare_stock_20251231_001"),
            ("NATIVE.SZ", 500_000_000.0, 2_000_000.0, "vv_choice_stock_20260811_001"),
            ("NULLV.SZ", 400_000_000.0, 3_000_000.0, None),
            ("UPPER.SZ", 700_000.0, 4_000.0, "VV_CHOICE_TUSHARE_STOCK_20251231_002"),
            ("EMPTYV.SZ", 800_000_000.0, 5_000_000.0, ""),
            ("BLANKV.SZ", 900_000_000.0, 6_000_000.0, "   "),
        ],
    )
    return conn


def test_amount_rmb_sql_normalizes_by_vendor_generation() -> None:
    conn = _seeded_connection()
    try:
        rows = dict(
            conn.execute(
                f"select stock_code, {amount_rmb_sql()} from choice_stock_daily_observation"
            ).fetchall()
        )
    finally:
        conn.close()

    assert rows["TUSHARE.SZ"] == 300_000_000.0  # 千元 -> 元
    assert rows["NATIVE.SZ"] == 500_000_000.0  # 元口径透传
    assert rows["NULLV.SZ"] is None  # 无法定标 fail-closed
    assert rows["UPPER.SZ"] == 700_000_000.0  # vendor 大小写不敏感
    assert rows["EMPTYV.SZ"] is None  # 空字符串 vendor 同样无法定标 fail-closed
    assert rows["BLANKV.SZ"] is None  # 纯空格 vendor 同样无法定标 fail-closed


def test_volume_shares_sql_normalizes_by_vendor_generation() -> None:
    conn = _seeded_connection()
    try:
        rows = dict(
            conn.execute(
                f"select stock_code, {volume_shares_sql()} from choice_stock_daily_observation"
            ).fetchall()
        )
    finally:
        conn.close()

    assert rows["TUSHARE.SZ"] == 100_000.0  # 手 -> 股
    assert rows["NATIVE.SZ"] == 2_000_000.0
    assert rows["NULLV.SZ"] is None
    assert rows["EMPTYV.SZ"] is None  # 空字符串 vendor 无法定标 fail-closed
    assert rows["BLANKV.SZ"] is None  # 纯空格 vendor 无法定标 fail-closed
    assert rows["UPPER.SZ"] == 400_000.0  # vendor 大小写不敏感(volume 侧独立锁定)


def test_table_alias_and_bare_expression_forms() -> None:
    conn = _seeded_connection()
    try:
        rows = dict(
            conn.execute(
                "select d.stock_code, "
                + amount_rmb_sql(table_alias="d", alias="amount_rmb")
                + " from choice_stock_daily_observation d"
            ).fetchall()
        )
        bare = conn.execute(
            "select sum("
            + amount_rmb_sql(alias=None)
            + ") from choice_stock_daily_observation"
        ).fetchone()
    finally:
        conn.close()

    assert rows["TUSHARE.SZ"] == 300_000_000.0
    assert bare is not None
    # NULL vendor 行不计入 sum:3e8 + 5e8 + 7e8
    assert bare[0] == 1_500_000_000.0


def test_scale_unknown_sql_flags_null_vendor_rows_only() -> None:
    conn = _seeded_connection()
    try:
        rows = dict(
            conn.execute(
                "select stock_code, "
                + scale_unknown_sql("amount", alias="scale_unknown")
                + " from choice_stock_daily_observation"
            ).fetchall()
        )
        # 括号包裹保证 where not (...) 语义正确(共享 API 防误用)。
        negated = conn.execute(
            "select count(*) from choice_stock_daily_observation where not "
            + scale_unknown_sql("amount")
        ).fetchone()
    finally:
        conn.close()

    assert rows["NULLV.SZ"] is True
    assert rows["TUSHARE.SZ"] is False
    assert rows["NATIVE.SZ"] is False
    assert rows["EMPTYV.SZ"] is True  # 空字符串 vendor 归一后视为无法定标
    assert rows["BLANKV.SZ"] is True  # 纯空格 vendor 归一后视为无法定标
    assert negated is not None
    assert negated[0] == 3  # 6 行中 NULLV.SZ / EMPTYV.SZ / BLANKV.SZ 被排除


def test_unknown_non_null_vendor_passes_through_as_native() -> None:
    """锁定现状语义:非空且不含 tushare 的未知 vendor 按 choice_native(元/股)透传。

    第三代 vendor 引入时本测试应爆红,提示同步回改本模块与契约 §4.10。
    """

    conn = _seeded_connection()
    try:
        conn.execute(
            "insert into choice_stock_daily_observation values "
            "('THIRDGEN.SZ', 200.0, 300.0, 'vv_wind_stock_20270101_abc')"
        )
        row = conn.execute(
            f"select {amount_rmb_sql()}, {volume_shares_sql()} "
            "from choice_stock_daily_observation where stock_code = 'THIRDGEN.SZ'"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == 200.0  # 未知代际透传(fail-open),依赖摄入侧命名纪律
    assert row[1] == 300.0
