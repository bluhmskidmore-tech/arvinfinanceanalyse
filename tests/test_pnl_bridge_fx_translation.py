from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows


def test_fx_translation_usd_bond_uses_rate_diff():
    """无市值字段时回退面值：fx_translation = face * (current_rate - prior_rate)。"""
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


def test_fx_translation_prefers_dirty_market_value_over_face():
    """有市值时用脏市值原币，不用面值（与 read_models.fx_effect / 脏市值桥一致）。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-DIRTY",
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
                "instrument_code": "USD-BOND-DIRTY",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "face_value_native": "1000",
                "market_value_amount": "1100",
                "accrued_interest_amount": "25",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    # dirty = 1125; 1125 * (7.0827 - 7.04135) = 46.51875
    assert rows[0].fx_translation == Decimal("46.51875000")


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


def test_foreign_bond_missing_fx_rate_flags_diagnostic_with_currency():
    """外币券缺 FX 输入时，必须在 balance_diagnostics 追加含币种的 FX_RATE_MISSING 标记。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-FLAG",
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
                "instrument_code": "USD-BOND-FLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "accounting_basis": "FVTPL",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current=None,
        fx_rates_prior=None,
    )

    row = rows[0]
    assert row.fx_translation == Decimal("0")
    assert any(
        "FX_RATE_MISSING" in message and "USD" in message
        for message in row.balance_diagnostics
    )


def test_foreign_bond_missing_single_currency_rate_flags_diagnostic():
    """FX 字典存在但缺该币种汇率时，同样需要标记。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "EUR-BOND-FLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
                "currency_basis": "EUR",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "EUR-BOND-FLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "EUR",
                "accounting_basis": "FVTPL",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    row = rows[0]
    assert row.fx_translation == Decimal("0")
    assert any(
        "FX_RATE_MISSING" in message and "EUR" in message
        for message in row.balance_diagnostics
    )


def test_domestic_bond_has_no_fx_missing_diagnostic():
    """本币券没有 FX 敞口，不得追加 FX_RATE_MISSING 标记。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "CNY-BOND-NOFLAG",
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
                "instrument_code": "CNY-BOND-NOFLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current=None,
        fx_rates_prior=None,
    )

    row = rows[0]
    assert not any("FX_RATE_MISSING" in message for message in row.balance_diagnostics)


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
    # dirty exposure = 100 + 2 = 102; 102 * (7.0827 - 7.04135) = 4.2177
    assert row.fx_translation == Decimal("4.21770000")
    # 互斥分解：explained = 514(10) + 517(3) + 手工调整(2) + FX 效应(4.2177)，
    # 516(5.00) 是被解释对象、不再计入（审计 PNL-01）。
    assert row.explained_pnl == Decimal("19.21770000")

