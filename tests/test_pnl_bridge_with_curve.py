from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.bond_analytics.common import build_full_curve, tenor_to_years
from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows


def test_roll_down_nonzero_when_curve_available():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国债",
                "asset_class": "利率债",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国债",
                "asset_class": "利率债",
            }
        ],
        treasury_curve_current={
            "1Y": Decimal("2.00"),
            "2Y": Decimal("3.00"),
            "3Y": Decimal("4.00"),
        },
    )

    assert rows[0].roll_down == Decimal("2.00")


def test_treasury_curve_nonzero_when_both_curves_available():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国债",
                "asset_class": "利率债",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国债",
                "asset_class": "利率债",
            }
        ],
        treasury_curve_current={
            "1Y": Decimal("2.00"),
            "2Y": Decimal("3.00"),
            "3Y": Decimal("4.00"),
        },
        treasury_curve_prior={
            "1Y": Decimal("1.00"),
            "2Y": Decimal("2.00"),
            "3Y": Decimal("3.00"),
        },
    )

    assert rows[0].treasury_curve == Decimal("-2.00")


def test_backward_compatible_without_curve():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].roll_down == Decimal("0")
    assert rows[0].treasury_curve == Decimal("0")


def test_cdb_curve_selected_for_policy_bank_bond():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "CDB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "CDB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国开债",
                "asset_class": "政策性金融债",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "CDB-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "100",
                "accrued_interest_amount": "0",
                    "maturity_date": "2028-12-30",
                "coupon_rate": "0",
                "ytm_value": "0",
                "bond_type": "国开债",
                "asset_class": "政策性金融债",
            }
        ],
        treasury_curve_current={
            "1Y": Decimal("9.00"),
            "2Y": Decimal("9.00"),
            "3Y": Decimal("9.00"),
        },
        treasury_curve_prior={
            "1Y": Decimal("9.00"),
            "2Y": Decimal("9.00"),
            "3Y": Decimal("9.00"),
        },
        cdb_curve_current={
            "1Y": Decimal("2.00"),
            "2Y": Decimal("3.00"),
            "3Y": Decimal("4.00"),
        },
        cdb_curve_prior={
            "1Y": Decimal("1.00"),
            "2Y": Decimal("2.00"),
            "3Y": Decimal("3.00"),
        },
    )

    assert rows[0].treasury_curve == Decimal("-2.00")


def test_build_full_curve_preserves_short_end_nodes():
    curve = build_full_curve(
        {
            "3M": Decimal("1.10"),
            "6M": Decimal("1.20"),
            "9M": Decimal("1.30"),
            "1Y": Decimal("1.40"),
            "3Y": Decimal("1.80"),
            "5Y": Decimal("2.10"),
            "10Y": Decimal("2.50"),
            "30Y": Decimal("3.00"),
        }
    )

    assert curve["3M"] == Decimal("1.10")
    assert curve["6M"] == Decimal("1.20")
    assert curve["9M"] == Decimal("1.30")


def test_tenor_to_years_supports_9m():
    assert tenor_to_years("9M") == 0.75
