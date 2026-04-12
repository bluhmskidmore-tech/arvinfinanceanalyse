from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows


def test_fx_translation_usd_bond_uses_rate_diff():
    """USD 债券的 fx_translation = face_value * (current_rate - prior_rate)"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "41.35",
                "currency_basis": "USD",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert rows[0].fx_translation == Decimal("41.35")


def test_fx_translation_cny_bond_is_zero():
    """CNY 债券的 fx_translation = 0"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "CNY-BOND-001",
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
                "report_date": "2025-12-31",
                "instrument_code": "CNY-BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert rows[0].fx_translation == Decimal("0")


def test_fx_translation_missing_rates_returns_zero():
    """缺少 FX 数据时 fx_translation = 0，不报错"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-002",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "USD",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-002",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "face_value_native": "500",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current=None,
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert rows[0].fx_translation == Decimal("0")


def test_fx_translation_integration_with_pnl_bridge():
    """端到端：build_pnl_bridge_rows 传入 fx_rates 后 fx_translation 非零"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-003",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "3.00",
                "manual_adjustment": "2.00",
                "total_pnl": "30.00",
                "currency_basis": "USD",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-003",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "face_value_native": "1000",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "2.00",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-10-31",
                "instrument_code": "USD-BOND-003",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "face_value_native": "1000",
                "market_value_amount": "95.00",
                "accrued_interest_amount": "1.00",
            }
        ],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    row = rows[0]
    assert row.fx_translation == Decimal("41.35")
    assert row.explained_pnl == Decimal("61.35")

