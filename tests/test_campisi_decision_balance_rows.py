from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository

pytestmark = pytest.mark.unit


def _create_zqtz_balance_fact_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_formal_zqtz_balance_daily (
            report_date varchar,
            instrument_code varchar,
            instrument_name varchar,
            portfolio_name varchar,
            cost_center varchar,
            asset_class varchar,
            bond_type varchar,
            rating varchar,
            invest_type_std varchar,
            accounting_basis varchar,
            position_scope varchar,
            currency_basis varchar,
            currency_code varchar,
            face_value_amount decimal(24, 8),
            market_value_amount decimal(24, 8),
            amortized_cost_amount decimal(24, 8),
            accrued_interest_amount decimal(24, 8),
            coupon_rate decimal(18, 8),
            ytm_value decimal(18, 8),
            maturity_date varchar,
            is_issuance_like boolean
        )
        """
    )


def _seed_dual_basis_rows(conn: duckdb.DuckDBPyConnection) -> None:
    """同键头寸各物化 native + CNY 两行（复刻 balance_analysis_materialize 的双 basis 写入）。"""
    rows = [
        # CNY 计价债券：native 与 CNY 两行金额相同（漏过滤时市值恰为 2 倍）。
        (
            "2026-01-01", "BOND_CNY", "Bond CNY", "FIOA", "5010", "bond", "treasury", "AAA",
            "H", "AC", "asset", "native", "CNY",
            Decimal("700"), Decimal("700"), Decimal("700"), Decimal("3"),
            Decimal("0.03"), Decimal("0.025"), "2031-01-01", False,
        ),
        (
            "2026-01-01", "BOND_CNY", "Bond CNY", "FIOA", "5010", "bond", "treasury", "AAA",
            "H", "AC", "asset", "CNY", "CNY",
            Decimal("700"), Decimal("700"), Decimal("700"), Decimal("3"),
            Decimal("0.03"), Decimal("0.025"), "2031-01-01", False,
        ),
        # USD 计价债券：native 为原币金额、CNY 为折算金额（漏过滤时为混币加总 100+720）。
        (
            "2026-01-01", "BOND_USD", "Bond USD", "FIOA", "5010", "bond", "treasury", "AAA",
            "T", "FVTPL", "asset", "native", "USD",
            Decimal("100"), Decimal("100"), Decimal("100"), Decimal("1"),
            Decimal("0.04"), Decimal("0.035"), "2030-06-30", False,
        ),
        (
            "2026-01-01", "BOND_USD", "Bond USD", "FIOA", "5010", "bond", "treasury", "AAA",
            "T", "FVTPL", "asset", "CNY", "USD",
            Decimal("720"), Decimal("720"), Decimal("720"), Decimal("7.2"),
            Decimal("0.04"), Decimal("0.035"), "2030-06-30", False,
        ),
    ]
    conn.executemany(
        """
        insert into fact_formal_zqtz_balance_daily values
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def test_campisi_decision_balance_rows_take_cny_basis_only_without_double_count(tmp_path) -> None:
    db_path = tmp_path / "campisi_decision_balance.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_zqtz_balance_fact_table(conn)
        _seed_dual_basis_rows(conn)
    finally:
        conn.close()

    repo = BalanceAnalysisRepository(str(db_path))
    rows = repo.fetch_campisi_decision_balance_rows("2026-01-01")

    assert len(rows) == 2
    by_code = {row["instrument_code"]: row for row in rows}

    cny_bond = by_code["BOND_CNY"]
    # 只取 CNY basis 一行：市值不得双计为 1400。
    assert cny_bond["market_value_amount"] == Decimal("700")
    assert cny_bond["face_value_amount"] == Decimal("700")
    assert cny_bond["accrued_interest_amount"] == Decimal("3")
    # 重复头寸诊断依赖 source_row_count；native+CNY 双行不得计为 2。
    assert cny_bond["source_row_count"] == 1

    usd_bond = by_code["BOND_USD"]
    # USD 头寸只取折算后的 CNY 行，不得原币+人民币混币加总为 820。
    assert usd_bond["market_value_amount"] == Decimal("720")
    assert usd_bond["source_row_count"] == 1

    total_market_value = sum(row["market_value_amount"] for row in rows)
    assert total_market_value == Decimal("1420")
