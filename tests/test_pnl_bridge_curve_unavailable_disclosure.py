"""PnL 桥曲线效应"归零但不是观测值"的显式披露（2026-08 金融审计整改）。

`pnl_bridge` 的 `treasury_curve` / `credit_spread` 在报告日 2026-07-31 合计 0.00
（1715/1715 行全零）。成因不是市场没动，而是：曲线事实停在 2026-06-30，两端回退
到**同一条**曲线，`rate_delta` 于是恒为 0；缺曲线时更是直接归零。两种情况都以
一个普通的 0 发布，并且残差照样闭合，于是 `quality_flag` 还是 "ok"。

本文件锁的是信号，不是数值：
- 行级 `balance_diagnostics` 出现带前缀的原因（唯一可用通道：`PnlBridgeRowSchema`
  是 extra="forbid"，不能加字段）；
- `quality_flag` 不再是 "ok"；
- 所有金额字段与升级前逐字段相同（本次整改不改口径）。

另一半同样重要：**不许误报**。真实平坦但两端不同的曲线、非 FVTPL 行、到期行、
真正的空仓，都不能被标成"曲线不可用"，否则告警会被当成噪音关掉。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_FVTPL
from backend.app.core_finance.pnl_bridge import (
    CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX,
    CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX,
    TREASURY_CURVE_SAME_SOURCE_PREFIX,
    TREASURY_CURVE_UNAVAILABLE_PREFIX,
    build_pnl_bridge_rows,
)

_TENORS = ("3M", "6M", "9M", "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "10Y", "20Y", "30Y")


def _curve(level: str) -> dict[str, Decimal]:
    return {tenor: Decimal(level) for tenor in _TENORS}


def _fact_row(**overrides: object) -> dict:
    row: dict = {
        "report_date": "2026-07-31",
        "instrument_code": "CURVE-GAP-01",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "accounting_basis": ACCOUNTING_BASIS_FVTPL,
        "currency_basis": "CNY",
        "interest_income_514": "100000",
        "fair_value_change_516": "0",
        "capital_gain_517": "0",
        "manual_adjustment": "0",
        "total_pnl": "100000",
    }
    row.update(overrides)
    return row


def _balance_row(report_date: str, **overrides: object) -> dict:
    row: dict = {
        "report_date": report_date,
        "instrument_code": "CURVE-GAP-01",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "currency_basis": "CNY",
        "currency_code": "CNY",
        "accounting_basis": ACCOUNTING_BASIS_FVTPL,
        "years_to_maturity": "5",
        "modified_duration": "4",
        "market_value_amount": "10000000",
        "accrued_interest_amount": "250000",
        "asset_class": "rate",
        "bond_type": "国债",
        "instrument_name": "Bridge Treasury Bond",
    }
    row.update(overrides)
    return row


def _credit_balance_row(report_date: str, **overrides: object) -> dict:
    return _balance_row(
        report_date,
        **{
            "asset_class": "credit",
            "bond_type": "企业债",
            "instrument_name": "Bridge Credit Bond",
            **overrides,
        },
    )


def _run(**kwargs) -> object:
    defaults: dict = {
        "pnl_fi_rows": [_fact_row()],
        "balance_rows_current": [_balance_row("2026-07-31")],
        "balance_rows_prior": [_balance_row("2026-06-30")],
    }
    defaults.update(kwargs)
    return build_pnl_bridge_rows(**defaults)[0]


def _diagnostics_with(row, prefix: str) -> list[str]:
    return [message for message in row.balance_diagnostics if message.startswith(prefix)]


# ---------------------------------------------------------------------------
# 1. 缺曲线：0 是缺输入，不是零变动
# ---------------------------------------------------------------------------


def test_missing_benchmark_curve_is_disclosed_and_blocks_an_ok_flag():
    row = _run()

    disclosures = _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX)
    assert len(disclosures) == 1
    assert "curve_type=treasury" in disclosures[0]
    assert "not an observed zero rate move" in disclosures[0]

    # 数值口径一字未改：效应仍是 0，会计恒等式照旧。
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    assert row.explained_pnl == Decimal("100000")
    assert row.residual == Decimal("0")
    assert row.residual_ratio == Decimal("0")
    # 只有标记变了：残差闭合本来会给出 "ok"，而它闭合恰恰是因为效应被顶成了 0。
    assert row.quality_flag == "warning"


@pytest.mark.parametrize(
    ("current_curve", "prior_curve", "expected_side"),
    [
        (None, _curve("2.50"), "current"),
        (_curve("2.50"), None, "prior"),
        ({}, {}, "current, prior"),
    ],
)
def test_disclosure_names_which_period_end_lost_its_curve(
    current_curve, prior_curve, expected_side
):
    row = _run(treasury_curve_current=current_curve, treasury_curve_prior=prior_curve)

    disclosures = _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX)
    assert len(disclosures) == 1
    assert f"the {expected_side} period end" in disclosures[0]


def test_cdb_row_reports_its_own_curve_type():
    row = _run(
        balance_rows_current=[
            _balance_row("2026-07-31", bond_type="政策性金融债", instrument_name="国开债 24")
        ],
        balance_rows_prior=[
            _balance_row("2026-06-30", bond_type="政策性金融债", instrument_name="国开债 24")
        ],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.40"),
    )

    disclosures = _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX)
    assert len(disclosures) == 1
    # 喂的是国债曲线，但这一行需要的是 CDB 曲线：披露必须指向真正缺的那条。
    assert "curve_type=cdb" in disclosures[0]


# ---------------------------------------------------------------------------
# 2. 两端同源：rate_delta 结构性为 0
# ---------------------------------------------------------------------------


def test_identical_curves_on_both_period_ends_are_disclosed_as_same_source():
    """两个日期都回退到 2026-06-30 那条曲线时，曲线平移在代数上必然为 0。"""
    stale = _curve("2.50")

    row = _run(treasury_curve_current=stale, treasury_curve_prior=dict(stale))

    disclosures = _diagnostics_with(row, TREASURY_CURVE_SAME_SOURCE_PREFIX)
    assert len(disclosures) == 1
    assert "0 by construction" in disclosures[0]
    assert row.treasury_curve == Decimal("0")
    assert row.quality_flag == "warning"


def test_distinct_curves_produce_no_disclosure_and_keep_an_ok_flag():
    """对照组：两端曲线不同 → 效应是被算出来的，标记不受影响。"""
    row = _run(
        pnl_fi_rows=[_fact_row(fair_value_change_516="-100000", total_pnl="0")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.balance_diagnostics == ()
    # −(0.25/100 × 4 × 10,000,000) = −100,000
    assert row.treasury_curve == Decimal("-100000")
    assert row.quality_flag == "ok"


def test_flat_but_distinct_curve_objects_at_the_same_level_are_still_same_source():
    """"同一条曲线"按内容判定：服务层回退可能给出两个不同对象、相同数值。"""
    row = _run(treasury_curve_current=_curve("2.50"), treasury_curve_prior=_curve("2.50"))

    assert _diagnostics_with(row, TREASURY_CURVE_SAME_SOURCE_PREFIX)


# ---------------------------------------------------------------------------
# 3. 信用利差：只对信用簿行报警
# ---------------------------------------------------------------------------


def test_credit_row_missing_aaa_curve_is_disclosed():
    row = _run(
        balance_rows_current=[_credit_balance_row("2026-07-31")],
        balance_rows_prior=[_credit_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    disclosures = _diagnostics_with(row, CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX)
    assert len(disclosures) == 1
    assert "AAA current" in disclosures[0] and "AAA prior" in disclosures[0]
    assert row.credit_spread == Decimal("0")
    assert row.quality_flag != "ok"


def test_rate_row_never_gets_a_credit_spread_disclosure():
    """利率债没有信用利差可动，它的 0 是口径上的结构性零，报警只会制造噪音。"""
    row = _run(treasury_curve_current=_curve("2.50"), treasury_curve_prior=_curve("2.25"))

    assert _diagnostics_with(row, CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX) == []
    assert _diagnostics_with(row, CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX) == []


def test_credit_row_with_stale_aaa_curve_is_disclosed_as_same_source():
    stale_aaa = _curve("3.30")

    row = _run(
        balance_rows_current=[_credit_balance_row("2026-07-31")],
        balance_rows_prior=[_credit_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
        aaa_credit_curve_current=stale_aaa,
        aaa_credit_curve_prior=dict(stale_aaa),
    )

    disclosures = _diagnostics_with(row, CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX)
    assert len(disclosures) == 1
    assert "AAA" in disclosures[0]


def test_fully_governed_credit_row_reports_nothing():
    """四条曲线齐备且两端不同：treasury −100,000、credit −40,000 都是算出来的。

    explained = 514 100,000 − 100,000 − 40,000 = −40,000 = total_pnl ⇒ 残差闭合。
    """
    row = _run(
        pnl_fi_rows=[_fact_row(fair_value_change_516="-140000", total_pnl="-40000")],
        balance_rows_current=[_credit_balance_row("2026-07-31")],
        balance_rows_prior=[_credit_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
        aaa_credit_curve_current=_curve("3.40"),
        aaa_credit_curve_prior=_curve("3.05"),
    )

    assert row.balance_diagnostics == ()
    assert row.treasury_curve == Decimal("-100000")
    assert row.credit_spread == Decimal("-40000")
    assert row.residual == Decimal("0")
    assert row.quality_flag == "ok"


# ---------------------------------------------------------------------------
# 4. 不许误报
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("accounting_basis", ["AC", "FVOCI", "OCI", ""])
def test_non_fvtpl_rows_get_no_curve_disclosure(accounting_basis):
    """非 FVTPL 行整体不计市场效应，其 0 与曲线无关（与 FX 诊断同一门控）。"""
    row = _run(
        pnl_fi_rows=[_fact_row(accounting_basis=accounting_basis)],
        balance_rows_current=[_balance_row("2026-07-31", accounting_basis=accounting_basis)],
        balance_rows_prior=[_balance_row("2026-06-30", accounting_basis=accounting_basis)],
    )

    assert _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX) == []
    assert row.quality_flag == "ok"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"years_to_maturity": "0"}, id="matured"),
        pytest.param({"modified_duration": "0"}, id="zero_duration"),
        pytest.param({"market_value_amount": "0"}, id="flat_position"),
    ],
)
def test_rows_that_cannot_produce_a_curve_effect_are_not_flagged(overrides):
    """这些行即使有曲线也会得到 0，报"曲线不可用"是假警报。"""
    row = _run(
        balance_rows_current=[_balance_row("2026-07-31", **overrides)],
        balance_rows_prior=[_balance_row("2026-06-30", **overrides)],
    )

    assert _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX) == []
    assert row.quality_flag == "ok"


def test_row_with_null_market_value_columns_still_reports_the_curve_gap():
    """市值列全 NULL 时不能断言"这是空仓"。

    `_market_value_base_missing_diagnostic` 只在有曲线时才触发，所以
    "缺市值 + 缺曲线" 的组合原本两边都不报。
    """
    row = _run(
        balance_rows_current=[
            _balance_row("2026-07-31", market_value_amount=None, accrued_interest_amount=None)
        ],
        balance_rows_prior=[_balance_row("2026-06-30")],
    )

    assert len(_diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX)) == 1


def test_missing_current_balance_row_reports_only_the_balance_gap():
    row = _run(balance_rows_current=[])

    assert _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX) == []
    assert any("Missing current balance row" in message for message in row.balance_diagnostics)


# ---------------------------------------------------------------------------
# 5. 标记升级是单向的
# ---------------------------------------------------------------------------


def test_escalation_never_softens_an_existing_error_flag():
    """残差 30% 的行不能因为新增披露被"升级"成 warning。"""
    row = _run(pnl_fi_rows=[_fact_row(interest_income_514="70000", total_pnl="100000")])

    assert _diagnostics_with(row, TREASURY_CURVE_UNAVAILABLE_PREFIX)
    assert row.residual_ratio == Decimal("0.3")
    assert row.quality_flag == "error"


def test_escalation_does_not_touch_amount_fields():
    """逐字段对照：喂同一组输入，只有 quality_flag / diagnostics 与对照组不同。"""
    degraded = _run()
    # 对照组：同样没有曲线，但久期为 0 → 不触发披露，标记保持 ok。
    baseline = _run(
        balance_rows_current=[_balance_row("2026-07-31", modified_duration="0")],
        balance_rows_prior=[_balance_row("2026-06-30", modified_duration="0")],
    )

    amount_fields = (
        "beginning_dirty_mv",
        "ending_dirty_mv",
        "carry",
        "roll_down",
        "treasury_curve",
        "credit_spread",
        "fx_translation",
        "realized_trading",
        "unrealized_fv",
        "manual_adjustment",
        "explained_pnl",
        "actual_pnl",
        "residual",
        "residual_ratio",
    )
    assert [getattr(degraded, field) for field in amount_fields] == [
        getattr(baseline, field) for field in amount_fields
    ]
    assert (degraded.quality_flag, baseline.quality_flag) == ("warning", "ok")
