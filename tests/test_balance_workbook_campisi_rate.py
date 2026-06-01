# 回归：balance_analysis_workbook._build_campisi_table 票息/收入用小数 coupon，不重复 /100。
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.balance_analysis import FormalZqtzBalanceFactRow
from backend.app.core_finance.balance_analysis_workbook import _build_campisi_table

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


def test_campisi_table_income_uses_decimal_coupon_without_extra_hundred() -> None:
    rows = [
        _asset_row(code="B1", bond_type="政策性金融债", face=Decimal("100000000"), coupon=Decimal("0.0285")),
        _asset_row(code="B2", bond_type="企业债", face=Decimal("200000000"), coupon=Decimal("0.0320")),
        _asset_row(code="B3", bond_type="中期票据", face=Decimal("150000000"), coupon=Decimal("0.0255")),
    ]
    table = _build_campisi_table(rows)
    out_rows = {r["bond_type"]: r for r in table["rows"]}
    # 万元
    assert out_rows["政策性金融债"]["coupon_income_amount"] == Decimal("285")  # 2.85M / 1e4
    assert out_rows["企业债"]["coupon_income_amount"] == Decimal("640")
    assert out_rows["中期票据"]["coupon_income_amount"] == Decimal("382.5")
    total_wan = Decimal("285") + Decimal("640") + Decimal("382.5")
    assert total_wan == Decimal("1307.5")
    assert out_rows["政策性金融债"]["spread_income_amount"] == Decimal("0")
    # 200M * (0.032 - 0.0285) = 700_000 -> 70 万元
    assert out_rows["企业债"]["spread_income_amount"] == Decimal("70")
    # 150M * (0.0255 - 0.0285) = -450_000 -> -45 万元
    assert out_rows["中期票据"]["spread_income_amount"] == Decimal("-45")
