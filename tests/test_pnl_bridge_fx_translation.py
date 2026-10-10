from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows

# 生产口径：PnL 事实的 currency_basis 只有 CNY/CNX（pnl.CurrencyBasis），真实币种
# 落在余额行的 currency_code 列。桥接余额行来自 CNY 口径投影
# （fetch_pnl_bridge_zqtz_balance_rows），行内 market_value_amount /
# accrued_interest_amount 已按汇率折成 CNY；原币敞口由服务层富集的
# market_value_native / accrued_interest_native（缺失时 face_value_native）承载。
# 所有夹具按该真实形状构造，避免把折 CNY 金额当原币喂入而锁定放大缺陷。


def test_fx_translation_usd_bond_uses_rate_diff():
    """无原币市值字段时回退原币面值：fx_translation = face_native * Δrate。

    行内同时携带折 CNY 的 market_value_amount，验证其不会被误当原币敞口
    （否则 7082.70 * 0.04135 = 292.87 而非 41.35）。
    """
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
                # 折 CNY 字段（1000 USD × 7.0827），不得进入原币敞口。
                "market_value_amount": "7082.70",
                "accrued_interest_amount": "0",
                "face_value_native": "1000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    # 独立手算：1000 * (7.0827 - 7.04135) = 41.35
    assert rows[0].fx_translation == Decimal("41.35")


def test_fx_translation_prefers_dirty_market_value_over_face():
    """有原币市值时用原币脏市值（native 富集字段），不用面值，也不用折 CNY 金额。

    与 read_models._fx_effect 的 market_value_native 口径一致。
    """
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-DIRTY",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
                "face_value_native": "1000",
                # 折 CNY 字段（1100/25 USD × 7.0827），不得进入原币敞口。
                "market_value_amount": "7790.97",
                "accrued_interest_amount": "177.07",
                # 服务层富集的原币字段。
                "market_value_native": "1100",
                "accrued_interest_native": "25",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    # 独立手算：原币脏市值 = 1100 + 25 = 1125; 1125 * (7.0827 - 7.04135) = 46.51875
    assert rows[0].fx_translation == Decimal("46.51875000")


def test_fx_translation_uses_native_dirty_mv_not_cny_converted_market_value():
    """防回归（2026-08 审计）：折 CNY 市值不得再乘 Δ汇率，否则 FX 效应放大约一个汇率倍数。

    原币脏市值 1,000,000 USD（折 CNY 7,100,000），汇率 7.00 → 7.10：
    正确 fx_translation = 1,000,000 * 0.10 = 100,000 CNY；
    缺陷实现会输出 7,100,000 * 0.10 = 710,000 CNY。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2026-01-31",
                "instrument_code": "USD-BOND-REG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
                "interest_income_514": "0",
                "fair_value_change_516": "100000",
                "capital_gain_517": "0",
                "manual_adjustment": "0",
                "total_pnl": "100000",
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2026-01-31",
                "instrument_code": "USD-BOND-REG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
                # 折 CNY 字段（980,000/20,000 USD × 7.10）。
                "market_value_amount": "6958000",
                "accrued_interest_amount": "142000",
                # 服务层富集的原币字段：脏市值合计 1,000,000 USD。
                "market_value_native": "980000",
                "accrued_interest_native": "20000",
                # 面值故意不同于市值，证明富集市值优先于面值回退。
                "face_value_native": "950000",
            }
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.10")},
        fx_rates_prior={"USD": Decimal("7.00")},
    )

    # 独立手算：1,000,000 * (7.10 - 7.00) = 100,000（而不是 700,000/710,000）。
    assert rows[0].fx_translation == Decimal("100000.00000000")


def test_fx_translation_cny_bond_is_zero():
    """本币券（currency_code=CNY）走完 FX 分支后 fx_translation = 0。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "CNY-BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "accounting_basis": "FVTPL",
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
                "currency_code": "CNY",
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-002",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-FLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "EUR-BOND-FLAG",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "EUR",
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
                "accounting_basis": "FVTPL",
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
                "currency_code": "CNY",
                "accounting_basis": "FVTPL",
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
                "currency_basis": "CNY",
            }
        ],
        balance_rows_current=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "USD-BOND-003",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
                "face_value_native": "1000",
                # 折 CNY 字段（100/2 USD × 7.0827）。
                "market_value_amount": "708.27",
                "accrued_interest_amount": "14.17",
                # 服务层富集的原币字段。
                "market_value_native": "100.00",
                "accrued_interest_native": "2.00",
            }
        ],
        balance_rows_prior=[
            {
                "report_date": "2025-10-31",
                "instrument_code": "USD-BOND-003",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "currency_basis": "CNY",
                "currency_code": "USD",
                "face_value_native": "1000",
                # 折 CNY 字段（95/1 USD × 7.04135）。
                "market_value_amount": "668.93",
                "accrued_interest_amount": "7.04",
                # 服务层富集的原币字段。
                "market_value_native": "95.00",
                "accrued_interest_native": "1.00",
            }
        ],
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    row = rows[0]
    # 独立手算：原币脏敞口 = 100 + 2 = 102; 102 * (7.0827 - 7.04135) = 4.2177
    assert row.fx_translation == Decimal("4.21770000")
    # 互斥分解：explained = 514(10) + 517(3) + 手工调整(2) + FX 效应(4.2177)，
    # 516(5.00) 是被解释对象、不再计入（审计 PNL-01）。
    assert row.explained_pnl == Decimal("19.21770000")
