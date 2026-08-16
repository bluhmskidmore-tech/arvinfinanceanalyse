# 回归（余额 H-1，2026-07-19 审计）：fact_formal_zqtz_balance_daily 的 coupon_rate/ytm_value
# 落库单位裁决为百分数（2.85 = 2.85%）。Campisi 票息/利差收入必须显式 ÷100；
# spread_bp 为百分数差 ×100。单体版与包版双实现输出必须一致。
#
# 测试对象说明（2026-08-12）：生产权威实现是单体 balance_analysis_workbook.py；
# `balance_workbook/` 包的 `_analysis_tables` / `_utils` 是不在生产调用路径上的拆分
# 副本（包级公开入口 builder.py 仅为委托壳）。本文件对包版的直测属于"双实现等价性"
# 断言，目的是防止休眠副本与权威实现漂移，不代表包版是生产入口。
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.balance_analysis import FormalZqtzBalanceFactRow
from backend.app.core_finance.balance_analysis_workbook import (
    _build_campisi_table as _build_campisi_table_monolith,
)
from backend.app.core_finance.balance_analysis_workbook import (
    _spread_bp as _spread_bp_monolith,
)
from backend.app.core_finance.balance_workbook._analysis_tables import (
    _build_campisi_table as _build_campisi_table_package,
)
from backend.app.core_finance.balance_workbook._utils import (
    _spread_bp as _spread_bp_package,
)

RD = date(2026, 3, 31)
MAT = date(2031, 3, 31)
FIXED = "\u56fa\u5b9a"


def _asset_row(
    *,
    code: str,
    bond_type: str,
    face: Decimal,
    coupon: Decimal,
) -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=RD,
        instrument_code=code,
        instrument_name=code,
        portfolio_name="P",
        cost_center="C",
        account_category="",
        asset_class="FVTPL债",
        bond_type=bond_type,
        issuer_name="I",
        industry_name="未分类",
        rating="",
        invest_type_std="T",
        accounting_basis="FVTPL",
        position_scope="asset",
        currency_basis="native",
        currency_code="CNY",
        face_value_amount=face,
        market_value_amount=face,
        amortized_cost_amount=face,
        accrued_interest_amount=Decimal("0"),
        coupon_rate=coupon,
        ytm_value=coupon,
        maturity_date=MAT,
        interest_mode=FIXED,
        is_issuance_like=False,
    )


def _percent_rate_rows() -> list[FormalZqtzBalanceFactRow]:
    # 百分数口径：2.85 = 2.85%（与落库单位一致）
    return [
        _asset_row(code="B1", bond_type="政策性金融债", face=Decimal("100000000"), coupon=Decimal("2.85")),
        _asset_row(code="B2", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
        _asset_row(code="B3", bond_type="中期票据", face=Decimal("150000000"), coupon=Decimal("2.55")),
    ]


def _assert_campisi_percent_semantics(table: dict) -> None:
    out_rows = {r["bond_type"]: r for r in table["rows"]}
    # 加权利率回显百分数
    assert out_rows["政策性金融债"]["weighted_rate_pct"] == Decimal("2.85")
    assert out_rows["企业债"]["weighted_rate_pct"] == Decimal("3.20")
    # 票息收入 = face × coupon% ÷ 100，单位万元
    assert out_rows["政策性金融债"]["coupon_income_amount"] == Decimal("285")  # 100M×2.85% = 2.85M
    assert out_rows["企业债"]["coupon_income_amount"] == Decimal("640")
    assert out_rows["中期票据"]["coupon_income_amount"] == Decimal("382.5")
    # 利差收入 = face × (coupon − benchmark)% ÷ 100，基准为政策性金融债加权票面 2.85%
    assert out_rows["政策性金融债"]["spread_income_amount"] == Decimal("0")
    assert out_rows["企业债"]["spread_income_amount"] == Decimal("70")  # 200M×0.35% = 700k
    assert out_rows["中期票据"]["spread_income_amount"] == Decimal("-45")
    # spread_bp = 百分数差 ×100
    assert out_rows["政策性金融债"]["spread_bp"] == Decimal("0")
    assert out_rows["企业债"]["spread_bp"] == Decimal("35.00")
    assert out_rows["中期票据"]["spread_bp"] == Decimal("-30.00")
    # 占比不受单位换算影响：285 / 1307.5
    assert out_rows["政策性金融债"]["share_of_income"] == Decimal("285") / Decimal("1307.5")


def test_campisi_monolith_consumes_percent_rates() -> None:
    _assert_campisi_percent_semantics(_build_campisi_table_monolith(_percent_rate_rows()))


def test_campisi_package_consumes_percent_rates() -> None:
    _assert_campisi_percent_semantics(_build_campisi_table_package(_percent_rate_rows()))


def test_campisi_monolith_and_package_rows_are_identical() -> None:
    rows = _percent_rate_rows()
    assert _build_campisi_table_monolith(rows)["rows"] == _build_campisi_table_package(rows)["rows"]


def test_campisi_benchmark_missing_monolith_and_package_rows_are_identical() -> None:
    # B10-2 口径：在册无政策性金融债时 spread_bp / spread_income_amount 显式 None，
    # 不允许把基准静默降级为 0。双实现（单体权威 + 休眠副本）必须同口径。
    rows = [
        _asset_row(code="B2", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("3.20")),
        _asset_row(code="B3", bond_type="中期票据", face=Decimal("150000000"), coupon=Decimal("2.55")),
    ]

    monolith_rows = _build_campisi_table_monolith(rows)["rows"]
    package_rows = _build_campisi_table_package(rows)["rows"]

    assert monolith_rows == package_rows
    assert all(row["spread_bp"] is None for row in package_rows)
    assert all(row["spread_income_amount"] is None for row in package_rows)


def test_spread_bp_converts_percent_point_difference_to_bp() -> None:
    # 3.0% − 2.0% = 1 个百分点 = 100bp
    assert _spread_bp_monolith(Decimal("3.0"), Decimal("2.0")) == Decimal("100.0")
    assert _spread_bp_package(Decimal("3.0"), Decimal("2.0")) == Decimal("100.0")
    assert _spread_bp_monolith(None, Decimal("2.0")) is None
