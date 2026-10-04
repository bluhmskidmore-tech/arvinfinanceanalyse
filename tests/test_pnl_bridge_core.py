from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows


def test_bridge_carry_equals_514():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "12.34",
                "fair_value_change_516": "-1.00",
                "capital_gain_517": "2.00",
                "manual_adjustment": "0.50",
                "total_pnl": "13.84",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "2.00",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-11-30",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "market_value_amount": "90.00",
                "accrued_interest_amount": "1.00",
            }
        ],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.report_date == date(2025, 12, 31)
    assert row.carry == Decimal("12.34")
    assert row.realized_trading == Decimal("2.00")
    assert row.unrealized_fv == Decimal("-1.00")
    assert row.beginning_dirty_mv == Decimal("91.00")
    assert row.ending_dirty_mv == Decimal("102.00")
    # 互斥分解：explained = 514 + 517 + 手工调整（无曲线输入时市场效应为 0，
    # 516 不再自我解释）；残差 = 未被解释的公允价值变动 −1.00。
    assert row.explained_pnl == Decimal("14.84")
    assert row.actual_pnl == Decimal("13.84")
    assert row.residual == Decimal("-1.00")
    assert row.quality_flag == "warning"
    assert row.current_balance_found is True
    assert row.prior_balance_found is True
    assert len(row.balance_diagnostics) == 1
    assert row.balance_diagnostics[0].startswith("SENSITIVITY_INPUT_UNAVAILABLE:")
    assert row.treasury_curve_availability == "unavailable"
    assert row.treasury_curve_availability_reason == "sensitivity_input_unavailable"


def test_bridge_dirty_market_value_adds_clean_market_value_and_accrued_once():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "CLEAN-DIRTY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVOCI",
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
                "instrument_code": "CLEAN-DIRTY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVOCI",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "4.50",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-11-30",
                "instrument_code": "CLEAN-DIRTY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVOCI",
                "market_value_amount": "90.00",
                "accrued_interest_amount": "1.25",
            }
        ],
    )

    row = rows[0]
    assert row.beginning_dirty_mv == Decimal("91.25")
    assert row.ending_dirty_mv == Decimal("104.50")
    assert row.ending_dirty_mv != Decimal("109.00")


def test_bridge_residual_calculation():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "5.00",
                "fair_value_change_516": "1.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "1.00",
                "total_pnl": "10.00",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    # AC 行：516 既不进 explained（互斥分解）也不产生市场效应（FVTPL 门控）。
    assert row.explained_pnl == Decimal("7.00")
    assert row.actual_pnl == Decimal("10.00")
    assert row.residual == Decimal("3.00")
    assert row.residual_ratio == Decimal("0.30")
    assert row.quality_flag == "error"
    assert row.current_balance_found is False
    assert row.prior_balance_found is False
    assert row.balance_diagnostics == (
        "Missing current balance row; ending_dirty_mv defaults to 0.",
        "Missing prior balance row; beginning_dirty_mv defaults to 0.",
    )


def test_bridge_quality_flag_thresholds():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "OK-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "95.10",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "WARN-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "91.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "ERR-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "90.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            },
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert [row.quality_flag for row in rows] == ["ok", "warning", "error"]
    assert [row.residual_ratio for row in rows] == [
        Decimal("0.049"),
        Decimal("0.09"),
        Decimal("0.10"),
    ]


def test_bridge_missing_prior_balance_graceful():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240003.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVOCI",
                "interest_income_514": "5.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "5.00",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240003.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "market_value_amount": "80.00",
                "accrued_interest_amount": "2.00",
            }
        ],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.beginning_dirty_mv == Decimal("0")
    assert row.ending_dirty_mv == Decimal("82.00")
    assert row.explained_pnl == Decimal("5.00")
    assert row.residual == Decimal("0.00")
    assert row.current_balance_found is True
    assert row.prior_balance_found is False
    assert row.balance_diagnostics == (
        "Missing prior balance row; beginning_dirty_mv defaults to 0.",
    )


def test_bridge_realized_equals_517():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "BOND-517",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "7.77",
                "manual_adjustment": "0",
                "total_pnl": "7.77",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].realized_trading == Decimal("7.77")


def test_bridge_balance_match_respects_accounting_basis():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "BASIS-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "1.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "1.00",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "BASIS-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "10.00",
                "accrued_interest_amount": "1.00",
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "BASIS-ROW",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVTPL",
                "market_value_amount": "20.00",
                "accrued_interest_amount": "2.00",
            },
        ],
        balance_rows_prior=[],
    )

    assert rows[0].ending_dirty_mv == Decimal("22.00")
    assert rows[0].current_balance_found is True


def test_bridge_does_not_cross_match_different_accounting_basis():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "NO-CROSS",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVOCI",
                "interest_income_514": "1.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "1.00",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "NO-CROSS",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "AC",
                "market_value_amount": "10.00",
                "accrued_interest_amount": "1.00",
            }
        ],
        balance_rows_prior=[],
    )

    assert rows[0].current_balance_found is False
    assert rows[0].ending_dirty_mv == Decimal("0")


def test_bridge_balance_fallback_does_not_cross_currency_basis():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "NO-CROSS-CCY",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "1.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "1.00",
                "currency_basis": "USD",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "NO-CROSS-CCY",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVTPL",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "5.00",
            }
        ],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.current_balance_found is True
    assert row.ending_dirty_mv == Decimal("105.00")
    assert any("currency_basis mismatch" in message for message in row.balance_diagnostics)


def test_bridge_unrealized_equals_516():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "BOND-516",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "-3.21",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "-3.21",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].unrealized_fv == Decimal("-3.21")


def test_bridge_explained_is_sum_of_components():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "SUM-CHECK",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "10.00",
                "fair_value_change_516": "2.00",
                "capital_gain_517": "3.00",
                "manual_adjustment": "1.50",
                "total_pnl": "16.50",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    # 互斥分解恒等式：unrealized_fv（516）不计入 explained，它是市场效应
    # 要解释的对象；两者同时相加会使残差退化（审计 PNL-01）。
    expected = (
        row.carry + row.roll_down + row.treasury_curve + row.credit_spread
        + row.fx_translation + row.realized_trading
        + row.manual_adjustment
    )
    assert row.explained_pnl == expected
    assert row.explained_pnl == Decimal("14.50")


def test_bridge_quality_flag_ok():
    """ratio < 0.05 -> ok"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "FLAG-OK",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "96.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].quality_flag == "ok"
    assert abs(rows[0].residual_ratio) < Decimal("0.05")


def test_bridge_quality_flag_warning():
    """0.05 <= ratio < 0.10 -> warning"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "FLAG-WARN",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "93.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].quality_flag == "warning"
    assert Decimal("0.05") <= abs(rows[0].residual_ratio) < Decimal("0.10")


def test_bridge_quality_flag_error():
    """ratio >= 0.10 -> error"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "FLAG-ERR",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "80.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100.00",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    assert rows[0].quality_flag == "error"
    assert abs(rows[0].residual_ratio) >= Decimal("0.10")


def test_bridge_zero_actual_pnl_and_zero_explained_pnl_is_ok():
    """When both actual and explained PnL are 0, residual_ratio should be 0."""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "ZERO-PNL",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.actual_pnl == Decimal("0")
    assert row.residual_ratio == Decimal("0")
    assert row.quality_flag == "ok"


def test_bridge_zero_actual_pnl_with_nonzero_explained_pnl_is_warning():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "ZERO-PNL-NONZERO-EXPLAINED",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "10.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "0",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.actual_pnl == Decimal("0")
    assert row.explained_pnl == Decimal("10.00")
    assert row.residual == Decimal("-10.00")
    assert row.residual_ratio is None
    assert row.quality_flag == "warning"


def test_bridge_missing_actual_pnl_is_warning_with_null_residual_ratio():
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "MISSING-ACTUAL",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "0",
                "fair_value_change_516": "0",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": None,
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.actual_pnl == Decimal("0")
    assert row.residual_ratio is None
    assert row.quality_flag == "warning"
    assert any("actual_pnl missing" in message for message in row.balance_diagnostics)


def test_bridge_market_effects_do_not_double_count_516():
    """FVTPL 行互斥分解：explained 不含 516；残差 = 516 − 市场效应（审计 PNL-01）。

    市场效应（骑乘/曲线/利差/汇兑）是对公允价值变动 516 的解释项。会计分项
    与市场效应同时计入 explained 会使残差恒等于市场效应之和的相反数，
    质量标记随之失真。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-P0",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "10.00",
                "fair_value_change_516": "-2.50",
                "capital_gain_517": "3.00",
                "manual_adjustment": "0.50",
                "total_pnl": "11.00",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-P0",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVTPL",
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
                "instrument_code": "TB-P0",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVTPL",
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

    row = rows[0]
    # 市场效应真实非零（骑乘 +2.00、曲线 −2.00），确保本测试覆盖到效应路径。
    assert row.roll_down == Decimal("2.00")
    assert row.treasury_curve == Decimal("-2.00")
    market_effects = row.roll_down + row.treasury_curve + row.credit_spread + row.fx_translation
    # 互斥分解恒等式：explained 不含 unrealized_fv。
    assert row.explained_pnl == (
        row.carry + market_effects + row.realized_trading + row.manual_adjustment
    )
    assert row.explained_pnl == Decimal("13.50")
    # 残差 = 未实现公允变动中模型未解释的部分。
    assert row.residual == row.unrealized_fv - market_effects
    assert row.residual == Decimal("-2.50")


def test_bridge_market_effects_zero_for_non_fvtpl_rows():
    """AC 行市场效应归零：正式事实已剔除非 FVTPL 的 516（审计 PNL-02）。

    与 bond_four_effects 的 AC 归零、campisi_attribution_service 的 FVTPL
    门控同一口径；否则 AC 账户的桥接残差会被幻影市场效应主导。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-AC",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "AC",
                "interest_income_514": "10.00",
                "fair_value_change_516": "0",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0",
                "total_pnl": "11.00",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-12-31",
                "instrument_code": "TB-AC",
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
                "instrument_code": "TB-AC",
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

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    assert row.fx_translation == Decimal("0")
    assert row.explained_pnl == Decimal("11.00")
    assert row.residual == Decimal("0")
    assert row.quality_flag == "ok"


def test_bridge_phase3_stubs_are_zero():
    """Without curves or FX inputs, curve effects and fx_translation remain 0."""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "STUB-CHECK",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "10.00",
                "fair_value_change_516": "5.00",
                "capital_gain_517": "3.00",
                "manual_adjustment": "2.00",
                "total_pnl": "20.00",
            }
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    assert row.fx_translation == Decimal("0")


def test_bridge_duplicate_balance_key_rejects_formal_result():
    """重复自然键不能以任意首行生成正式损益桥。"""
    with pytest.raises(RuntimeError, match="DUPLICATE_BALANCE_KEY") as error:
        build_pnl_bridge_rows(
            pnl_fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "DUP-KEY-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "accounting_basis": "FVOCI",
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
                    "instrument_code": "DUP-KEY-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "100.00",
                    "accrued_interest_amount": "2.00",
                },
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "DUP-KEY-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "999.00",
                    "accrued_interest_amount": "999.00",
                },
            ],
            balance_rows_prior=[],
        )
    assert "DUP-KEY-001" in str(error.value)
    assert "2 " in str(error.value)


def test_bridge_no_duplicate_balance_key_diagnostic_when_keys_unique():
    """反向对照：balance_rows 无重复键时不应产生该诊断，避免误报。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "NO-DUP-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVOCI",
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
                "instrument_code": "NO-DUP-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVOCI",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "2.00",
            }
        ],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.ending_dirty_mv == Decimal("102.00")
    assert not any("DUPLICATE_BALANCE_KEY" in message for message in row.balance_diagnostics)


def test_bridge_multi_currency_fallback_key_no_disclosure_when_exact_hits():
    """防误报核心用例：同券多币种行天然共享 fallback 键（键不含 currency_basis），
    这是合法数据形态。只要请求经 exact 精确命中，粗粒度共键不得产生任何披露。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "MULTI-CCY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVOCI",
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
                "instrument_code": "MULTI-CCY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "accounting_basis": "FVOCI",
                "market_value_amount": "100.00",
                "accrued_interest_amount": "2.00",
            },
            {
                "report_date": "2025-12-31",
                "instrument_code": "MULTI-CCY-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "USD",
                "accounting_basis": "FVOCI",
                "market_value_amount": "200.00",
                "accrued_interest_amount": "3.00",
            },
        ],
        balance_rows_prior=[],
    )

    row = rows[0]
    # exact 命中 USD 行（200+3），而不是 fallback 键下的首行 CNY（100+2）。
    assert row.ending_dirty_mv == Decimal("203.00")
    assert row.current_balance_found is True
    assert not any("AMBIGUOUS_BALANCE" in message for message in row.balance_diagnostics)
    assert not any("DUPLICATE_BALANCE_KEY" in message for message in row.balance_diagnostics)


def test_bridge_fallback_ambiguous_key_rejects_formal_result():
    """请求实际命中多候选 fallback 时拒绝生成正式结果。"""
    with pytest.raises(RuntimeError, match="AMBIGUOUS_BALANCE_FALLBACK_KEY") as error:
        build_pnl_bridge_rows(
            pnl_fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-FB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "accounting_basis": "FVOCI",
                    "interest_income_514": "0",
                    "fair_value_change_516": "0",
                    "capital_gain_517": "0",
                    "manual_adjustment": "0",
                    "total_pnl": "0",
                    "currency_basis": "",
                }
            ],
            balance_rows_current=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-FB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "100.00",
                    "accrued_interest_amount": "2.00",
                },
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-FB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "USD",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "999.00",
                    "accrued_interest_amount": "999.00",
                },
            ],
            balance_rows_prior=[],
        )
    assert "AMBIG-FB-001" in str(error.value)
    assert "2 " in str(error.value)


def test_bridge_fallback_ambiguity_rejects_before_currency_mismatch():
    """多候选 fallback 应先拒绝，不能挑一行再披露币种错配。"""
    with pytest.raises(RuntimeError, match="AMBIGUOUS_BALANCE_FALLBACK_KEY") as error:
        build_pnl_bridge_rows(
            pnl_fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-FB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "accounting_basis": "FVOCI",
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
                    "instrument_code": "AMBIG-FB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "100.00",
                    "accrued_interest_amount": "2.00",
                },
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-FB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "EUR",
                    "accounting_basis": "FVOCI",
                    "market_value_amount": "999.00",
                    "accrued_interest_amount": "999.00",
                },
            ],
            balance_rows_prior=[],
        )
    assert "AMBIG-FB-002" in str(error.value)
    assert "2 " in str(error.value)


def test_bridge_without_basis_ambiguous_key_rejects_formal_result():
    """空 accounting_basis 的多候选余额行不能取首行。"""
    with pytest.raises(RuntimeError, match="AMBIGUOUS_BALANCE_WITHOUT_BASIS_KEY") as error:
        build_pnl_bridge_rows(
            pnl_fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-WB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "accounting_basis": "FVOCI",
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
                    "instrument_code": "AMBIG-WB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "market_value_amount": "100.00",
                    "accrued_interest_amount": "2.00",
                },
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-WB-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "market_value_amount": "999.00",
                    "accrued_interest_amount": "999.00",
                },
            ],
            balance_rows_prior=[],
        )
    assert "AMBIG-WB-001" in str(error.value)
    assert "2 " in str(error.value)


def test_bridge_without_basis_duplicate_rows_resolved_via_exact_rejected():
    """空 basis 请求精确命中重复自然键时拒绝生成正式结果。"""
    with pytest.raises(RuntimeError, match="DUPLICATE_BALANCE_KEY") as error:
        build_pnl_bridge_rows(
            pnl_fi_rows=[
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-WB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "accounting_basis": "",
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
                    "instrument_code": "AMBIG-WB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "market_value_amount": "100.00",
                    "accrued_interest_amount": "2.00",
                },
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "AMBIG-WB-002",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "currency_basis": "CNY",
                    "market_value_amount": "999.00",
                    "accrued_interest_amount": "999.00",
                },
            ],
            balance_rows_prior=[],
        )
    assert "AMBIG-WB-002" in str(error.value)
    assert "2 " in str(error.value)


def test_modified_duration_fallback_applies_par_assumption_when_ytm_missing():
    """W-fi-2026-08 P1 残余修复：有票息缺 ytm 的余额行重算修正久期时，
    Macaulay 与修正折算必须共用同一 par 生效 ytm（=coupon），而非用原始
    ytm=0 跳过折算返回未折算的 Macaulay（约 +3% 高估）。

    独立手算（年付、c=y=3%、整 10 年）：
    par Macaulay = (1.03/0.03) x (1 - 1.03**-10) = 8.786108921879104
    修正久期 = 8.786108921879104 / 1.03 = 8.530202836775829
    """
    from backend.app.core_finance.pnl_bridge import _modified_duration

    report_date = date(2026, 7, 31)
    row = {
        # Ten actual annual coupon periods; 3650 days misses leap days and is
        # off the coupon-date grid, so it cannot use the whole-period benchmark.
        "maturity_date": date(2036, 7, 31).isoformat(),
        "coupon_rate": "3",  # fact 表 percent 口径（3 = 3%）
        "ytm_value": None,
        "instrument_code": "PARFALL.IB",
    }
    result = _modified_duration(report_date=report_date, row=row)
    assert abs(result - Decimal("8.530202836775829")) < Decimal("1e-9")
    # 回归锚：修复前返回未折算的 par Macaulay（8.7861...），不允许回潮。
    assert abs(result - Decimal("8.786108921879104")) > Decimal("0.2")
