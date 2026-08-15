"""写回 snapshot 的 CNY 市值必须按自然键连接，否则同一只券的两条腿会被互换。

`sync_zqtz_snapshot_market_value_cny_from_formal` 用 14 个描述列做 ``update ... from``
连接，唯独漏了 ``maturity_date``。同一只券在展期/重分类期间会以两个到期日各出一行
（面值一正一负），其余连接列完全相同，于是形成 2×2 笛卡尔积，DuckDB 任取其一。

这不是理论风险：只读副本 `moss.duckdb.bak-20260812-1920-presnapshot` 的
939,755 行快照里，``currency_code='CNY'`` 却 ``market_value_cny <> market_value_native``
的正好 5 行，全部是 031800572.IB，全部落在 2025-10-31 / 2025-12-31 / 2026-01-31 /
2026-02-28 这四个重复日上，且两条腿的值被交叉赋值。本文件用同一形态复现，并锁定
加上 ``maturity_date`` 之后每条腿各自拿回自己的 CNY 市值。
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.balance_analysis_repo import (
    ensure_balance_analysis_tables,
    sync_zqtz_snapshot_market_value_cny_from_formal,
)

REPORT_DATE = "2025-12-31"
INSTRUMENT = "031800572.IB"
LONG_LEG_MATURITY = "2024-02-21"
SHORT_LEG_MATURITY = "2026-09-21"
AMOUNT = Decimal("14273208.63")

_SHARED = {
    "instrument_code": INSTRUMENT,
    "instrument_name": "18GUOHOUJINRONGPPN002",
    "portfolio_name": "FIOA",
    "cost_center": "",
    "account_category": "银行账户",
    "asset_class": "可供出售类资产",
    "bond_type": "中期票据",
    "sub_type": "中期票据",
    "business_type_primary": "中期票据",
    "issuer_name": "国厚金融",
    "industry_name": "金融",
    "rating": "AA",
    "currency_code": "CNY",
}


def _insert_snapshot_leg(conn: duckdb.DuckDBPyConnection, *, maturity_date: str, native: Decimal) -> None:
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, sub_type, business_type_primary,
          issuer_name, industry_name, rating, currency_code, maturity_date,
          face_value_native, market_value_native, is_issuance_like
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            REPORT_DATE,
            *[
                _SHARED[column]
                for column in (
                    "instrument_code",
                    "instrument_name",
                    "portfolio_name",
                    "cost_center",
                    "account_category",
                    "asset_class",
                    "bond_type",
                    "sub_type",
                    "business_type_primary",
                    "issuer_name",
                    "industry_name",
                    "rating",
                    "currency_code",
                )
            ],
            maturity_date,
            native,
            native,
            False,
        ],
    )


def _insert_fact_leg(conn: duckdb.DuckDBPyConnection, *, maturity_date: str, cny: Decimal) -> None:
    conn.execute(
        """
        insert into fact_formal_zqtz_balance_daily (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, sub_type, business_type_primary,
          issuer_name, industry_name, rating, currency_code, maturity_date,
          accounting_basis, position_scope, currency_basis,
          face_value_amount, market_value_amount, is_issuance_like
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            REPORT_DATE,
            *[
                _SHARED[column]
                for column in (
                    "instrument_code",
                    "instrument_name",
                    "portfolio_name",
                    "cost_center",
                    "account_category",
                    "asset_class",
                    "bond_type",
                    "sub_type",
                    "business_type_primary",
                    "issuer_name",
                    "industry_name",
                    "rating",
                    "currency_code",
                )
            ],
            maturity_date,
            "FVOCI",
            "asset",
            "CNY",
            cny,
            cny,
            False,
        ],
    )


@pytest.fixture
def seeded_conn(tmp_path):
    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False)
    try:
        ensure_balance_analysis_tables(conn)
        _insert_snapshot_leg(conn, maturity_date=LONG_LEG_MATURITY, native=AMOUNT)
        _insert_snapshot_leg(conn, maturity_date=SHORT_LEG_MATURITY, native=-AMOUNT)
        _insert_fact_leg(conn, maturity_date=LONG_LEG_MATURITY, cny=AMOUNT)
        _insert_fact_leg(conn, maturity_date=SHORT_LEG_MATURITY, cny=-AMOUNT)
        yield conn
    finally:
        conn.close()


def test_each_maturity_leg_gets_its_own_cny_market_value(seeded_conn):
    sync_zqtz_snapshot_market_value_cny_from_formal(seeded_conn, REPORT_DATE)

    written = dict(
        seeded_conn.execute(
            """
            select cast(maturity_date as varchar), market_value_cny
            from zqtz_bond_daily_snapshot
            where instrument_code = ?
            """,
            [INSTRUMENT],
        ).fetchall()
    )

    assert written[LONG_LEG_MATURITY] == AMOUNT
    assert written[SHORT_LEG_MATURITY] == -AMOUNT


def test_a_cny_row_never_ends_up_with_a_cny_value_that_contradicts_its_native_value(seeded_conn):
    """库里已固化的损害指纹：本币行的 CNY 值等于原币值的相反数。

    折算率对 CNY 恒为 1，所以这两列相等是恒等式；不相等就意味着连接发生了 fanout。
    """
    sync_zqtz_snapshot_market_value_cny_from_formal(seeded_conn, REPORT_DATE)

    contradictions = seeded_conn.execute(
        """
        select count(*)
        from zqtz_bond_daily_snapshot
        where upper(coalesce(currency_code, '')) = 'CNY'
          and market_value_cny is not null
          and market_value_native is not null
          and market_value_cny <> market_value_native
        """
    ).fetchone()

    assert contradictions[0] == 0
