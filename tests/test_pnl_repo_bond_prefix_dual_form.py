"""BOND- 前缀双形态券码（X 与 BOND-X 并存）不得让一条 PnL 行双计。

旧实现用 `(b.code = p.code or b.code = replace(p.code,'BOND-','') or 'BOND-'||b.code = p.code)`
的 OR 匹配：当同键下 X 与 BOND-X 两种拼写并存时，一条 PnL 行同时命中两条
balance 行，按业务聚合与 untraced 诊断分解都会把该 PnL 双计。修复后按
「剥掉 BOND- 前缀的规范化券码」等值匹配。
"""
from __future__ import annotations

import duckdb

from backend.app.repositories.pnl_repo import PnlRepository

REPORT_DATE = "2026-05-31"


def _create_pnl_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_formal_pnl_fi (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          currency_basis varchar,
          invest_type_std varchar,
          interest_income_514 decimal(24, 8),
          fair_value_change_516 decimal(24, 8),
          capital_gain_517 decimal(24, 8),
          manual_adjustment decimal(24, 8),
          total_pnl decimal(24, 8)
        )
        """
    )
    conn.execute(
        """
        create table fact_nonstd_pnl_bridge (
          report_date varchar,
          bond_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          interest_income_514 decimal(24, 8),
          fair_value_change_516 decimal(24, 8),
          capital_gain_517 decimal(24, 8),
          manual_adjustment decimal(24, 8),
          total_pnl decimal(24, 8)
        )
        """
    )
    conn.execute(
        """
        create table fact_formal_zqtz_balance_daily (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          currency_basis varchar,
          position_scope varchar,
          business_type_primary varchar,
          sub_type varchar,
          asset_class varchar,
          market_value_amount decimal(24, 8),
          maturity_date varchar
        )
        """
    )


def test_by_business_rows_do_not_double_count_pnl_when_both_code_forms_exist(tmp_path):
    db_path = tmp_path / "pnl-dual-form.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_pnl_tables(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            (?, 'BOND-X1', 'P1', 'CC1', 'CNY', 'FI', 10, 0, 0, 0, 10)
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, 'X1', 'P1', 'CC1', 'CNY', 'asset', 'BT1', 'BT1', 'BT1', 100, null),
            (?, 'BOND-X1', 'P1', 'CC1', 'CNY', 'asset', 'BT1', 'BT1', 'BT1', 50, null)
            """,
            [REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()

    rows = PnlRepository(str(db_path)).fetch_by_business_rows(REPORT_DATE)

    assert len(rows) == 1
    row = rows[0]
    assert row["business_type_primary"] == "BT1"
    # 一条 PnL 行只计一次；双拼写的两个 balance 头寸规模各消费一次。
    assert row["pnl_row_count"] == 1
    assert float(row["total_pnl"]) == 10.0
    assert float(row["interest_income_514"]) == 10.0
    assert float(row["scale_amount"]) == 150.0


def test_untraced_breakdown_does_not_double_count_pnl_when_both_code_forms_exist(tmp_path):
    db_path = tmp_path / "pnl-dual-form-untraced.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_pnl_tables(conn)
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            (?, 'BOND-X2', 'P2', 'CC2', 'CNY', 'FI', 10, 0, 0, 0, 10)
            """,
            [REPORT_DATE],
        )
        # 同日两种拼写的 balance 行都没有 business_type_primary：PnL 行属 untraced，
        # 诊断分类连接（historical_balance）不得因双拼写把它数成两行。
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, 'X2', 'P2', 'CC2', 'CNY', 'asset', null, null, null, 100, null),
            (?, 'BOND-X2', 'P2', 'CC2', 'CNY', 'asset', null, null, null, 50, null)
            """,
            [REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()

    repo = PnlRepository(str(db_path))
    breakdown = repo.fetch_untraced_formal_fi_breakdown(REPORT_DATE)

    assert len(breakdown) == 1
    entry = breakdown[0]
    assert entry["reason_code"] == "same_day_balance_without_primary_type"
    assert entry["pnl_row_count"] == 1
    assert float(entry["total_pnl"]) == 10.0

    # untraced 计数（布尔语义 SQL）与分解行数必须一致：分解侧修复前会数成 2。
    assert repo.count_untraced_formal_fi_rows(REPORT_DATE) == 1
    assert sum(int(item["pnl_row_count"]) for item in breakdown) == 1
