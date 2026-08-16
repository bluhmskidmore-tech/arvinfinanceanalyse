"""曲线效应可用性的结构化契约（2026-08 金融审计整改，前端可消费的那一半）。

前一轮整改把"这个 0 不是观测值"写进了 `balance_diagnostics` 字符串。字符串对人有效，
对页面无效：只要前端不做前缀匹配，使用者看到的仍然是"利率效应 0"，并把它读成
"利率没动"。本文件锁的是把同一判断搬到结构化字段之后的契约：

- 行级 `treasury_curve_availability` / `credit_spread_availability` 三态可分；
- 汇总级把行级折叠成 ok / partial / unavailable / not_applicable；
- **金额一分不变**：`treasury_curve` 等仍是 0，`explained_pnl` / `residual` /
  `residual_ratio` 及其序列化形态逐字段与整改前相同。第 3 节把整条已发布的行
  payload 冻结成字面量，就是为了让任何"顺手把 0 改成 null"的尝试立刻失败。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_FVTPL
from backend.app.core_finance.pnl_bridge import (
    CURVE_EFFECT_NOT_APPLICABLE,
    CURVE_EFFECT_OK,
    CURVE_EFFECT_PARTIAL,
    CURVE_EFFECT_REASON_BALANCE_ROW_MISSING,
    CURVE_EFFECT_REASON_CURVE_UNAVAILABLE,
    CURVE_EFFECT_REASON_MARKET_VALUE_BASE_MISSING,
    CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY,
    CURVE_EFFECT_REASON_NON_FVTPL_BASIS,
    CURVE_EFFECT_REASON_NOT_CREDIT_BOOK,
    CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING,
    CURVE_EFFECT_REASON_SAME_SOURCE_CURVE,
    CURVE_EFFECT_REASON_TENOR_OUTSIDE_CURVE,
    CURVE_EFFECT_UNAVAILABLE,
    build_pnl_bridge_rows,
    summarize_curve_effect_availability,
)
from backend.app.schemas.pnl_bridge import PnlBridgeRowSchema, PnlBridgeSummarySchema
from backend.app.services.explicit_numeric import promote_flat_payload
from backend.app.services.pnl_bridge_service import _build_summary

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


def _short_end_balance_row(report_date: str, **overrides: object) -> dict:
    """3M 以内的货币市场品种（SCP / 同业存单），落在曲线最短期限之外。"""
    return _balance_row(
        report_date,
        **{"years_to_maturity": "0.1", "modified_duration": "0.1", **overrides},
    )


def _run(**kwargs):
    defaults: dict = {
        "pnl_fi_rows": [_fact_row()],
        "balance_rows_current": [_balance_row("2026-07-31")],
        "balance_rows_prior": [_balance_row("2026-06-30")],
    }
    defaults.update(kwargs)
    return build_pnl_bridge_rows(**defaults)


def _first(**kwargs):
    return _run(**kwargs)[0]


# ---------------------------------------------------------------------------
# 1. 行级：三种 0 必须可分
# ---------------------------------------------------------------------------


def test_missing_curve_marks_the_zero_as_unavailable_not_observed():
    row = _first()

    assert row.treasury_curve == Decimal("0")
    assert row.treasury_curve_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.treasury_curve_availability_reason == CURVE_EFFECT_REASON_CURVE_UNAVAILABLE


def test_same_source_curve_reports_its_own_reason():
    """缺曲线和两端同源都给出 0，但处置不同：一个要补数，一个要修回退口径。"""
    stale = _curve("2.50")

    row = _first(treasury_curve_current=stale, treasury_curve_prior=dict(stale))

    assert row.treasury_curve_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.treasury_curve_availability_reason == CURVE_EFFECT_REASON_SAME_SOURCE_CURVE


def test_flat_but_comparable_curves_stay_observed():
    """曲线齐备且两端不同，只是恰好算出 0：这是观测值，页面照常显示 0。"""
    row = _first(
        pnl_fi_rows=[_fact_row(fair_value_change_516="-100000", total_pnl="0")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.treasury_curve == Decimal("-100000")
    assert row.treasury_curve_availability == CURVE_EFFECT_OK
    assert row.treasury_curve_availability_reason is None


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"years_to_maturity": "0"}, id="matured"),
        pytest.param({"modified_duration": "0"}, id="zero_duration"),
        pytest.param({"market_value_amount": "0"}, id="flat_position"),
    ],
)
def test_rows_that_cannot_move_are_exempt_rather_than_observed(overrides):
    """到期 / 零久期 / 真实空仓有曲线也是 0。

    标成"不可用"是假警报；但标成"观测为零"同样错——它们根本没有观测曲线，算进
    分母会把"缺曲线的行占比"稀释掉（真实数据上正是这样把 152/152 冲淡成 152/236）。
    """
    row = _first(
        balance_rows_current=[_balance_row("2026-07-31", **overrides)],
        balance_rows_prior=[_balance_row("2026-06-30", **overrides)],
    )

    assert row.treasury_curve_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.treasury_curve_availability_reason == CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY


def test_row_without_a_current_balance_row_names_that_gap_instead_of_claiming_zero():
    row = _first(balance_rows_current=[])

    assert row.treasury_curve_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.treasury_curve_availability_reason == CURVE_EFFECT_REASON_BALANCE_ROW_MISSING


def test_insensitive_rows_do_not_dilute_the_curve_gap_ratio():
    """一行缺曲线 + 一行到期：占比必须是 1/1 而不是 1/2。"""
    rows = _run(
        pnl_fi_rows=[_fact_row(), _fact_row(instrument_code="MATURED-01")],
        balance_rows_current=[
            _balance_row("2026-07-31"),
            _balance_row("2026-07-31", instrument_code="MATURED-01", years_to_maturity="0"),
        ],
        balance_rows_prior=[
            _balance_row("2026-06-30"),
            _balance_row("2026-06-30", instrument_code="MATURED-01", years_to_maturity="0"),
        ],
    )
    summary = _build_summary(rows)

    assert summary.treasury_curve_availability.status == CURVE_EFFECT_UNAVAILABLE
    assert summary.treasury_curve_availability.unavailable_rows == 1
    assert summary.treasury_curve_availability.applicable_rows == 1


@pytest.mark.parametrize("accounting_basis", ["AC", "FVOCI", "OCI", ""])
def test_non_fvtpl_rows_are_not_applicable_rather_than_observed(accounting_basis):
    """非 FVTPL 行按口径整体不计市场效应，它的 0 既不是观测也不是缺失。"""
    row = _first(
        pnl_fi_rows=[_fact_row(accounting_basis=accounting_basis)],
        balance_rows_current=[_balance_row("2026-07-31", accounting_basis=accounting_basis)],
        balance_rows_prior=[_balance_row("2026-06-30", accounting_basis=accounting_basis)],
    )

    assert row.treasury_curve_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.treasury_curve_availability_reason == CURVE_EFFECT_REASON_NON_FVTPL_BASIS
    assert row.credit_spread_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.credit_spread_availability_reason == CURVE_EFFECT_REASON_NON_FVTPL_BASIS


def test_rate_book_credit_spread_is_not_applicable():
    row = _first(treasury_curve_current=_curve("2.50"), treasury_curve_prior=_curve("2.25"))

    assert row.credit_spread_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.credit_spread_availability_reason == CURVE_EFFECT_REASON_NOT_CREDIT_BOOK


def test_credit_row_missing_aaa_curve_is_unavailable():
    row = _first(
        balance_rows_current=[_credit_balance_row("2026-07-31")],
        balance_rows_prior=[_credit_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.credit_spread == Decimal("0")
    assert row.credit_spread_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.credit_spread_availability_reason == CURVE_EFFECT_REASON_CURVE_UNAVAILABLE


_ZEROING_DIAGNOSTIC_PREFIXES = (
    "TREASURY_CURVE_",
    "CREDIT_SPREAD_CURVE_",
    "MARKET_VALUE_BASE_MISSING",
    "ROLL_DOWN_WINDOW_MISSING",
    "ROLL_DOWN_TENOR_OUTSIDE_CURVE",
)

# 每一种"把某个效应顶成 0 却不是观测值"的场景，连同它的诊断前缀。
_ZEROED_SCENARIOS = {
    "no_curve": {},
    "same_source_curve": {
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.5"),
    },
    "healthy_curve": {
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.25"),
    },
    "credit_row_without_aaa": {
        "balance_rows_current": [_credit_balance_row("2026-07-31")],
        "balance_rows_prior": [_credit_balance_row("2026-06-30")],
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.25"),
    },
    "no_market_value_base": {
        "balance_rows_current": [_balance_row("2026-07-31", market_value_amount=None)],
        "balance_rows_prior": [_balance_row("2026-06-30", market_value_amount=None)],
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.25"),
    },
    "no_roll_window": {
        "balance_rows_prior": [],
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.25"),
    },
    "tenor_below_curve_short_end": {
        "balance_rows_current": [_short_end_balance_row("2026-07-31")],
        "balance_rows_prior": [_short_end_balance_row("2026-06-30")],
        "treasury_curve_current": _curve("2.5"),
        "treasury_curve_prior": _curve("2.25"),
    },
}


def test_structured_field_never_contradicts_the_diagnostic_string():
    """两条通道并行下发，判断只有一处：任一行都不能出现"字符串报警、枚举正常"。

    覆盖每一个会把效应顶成 0 的诊断前缀，而不只是曲线那两个——``roll_down`` 的口子
    正是这样漏掉的：诊断字符串早就点了它的名，结构化字段却没有它。
    """
    for name, overrides in _ZEROED_SCENARIOS.items():
        row = _first(**overrides)
        flagged = any(
            message.startswith(_ZEROING_DIAGNOSTIC_PREFIXES)
            for message in row.balance_diagnostics
        )
        structured = CURVE_EFFECT_UNAVAILABLE in (
            row.roll_down_availability,
            row.treasury_curve_availability,
            row.credit_spread_availability,
        )
        assert flagged == structured, name


# ---------------------------------------------------------------------------
# 1b. roll_down：与 treasury_curve 同模式，但门控不同，不能借用它的结论
# ---------------------------------------------------------------------------


def test_missing_curve_marks_roll_down_unavailable_too():
    """缺曲线时 roll_down 也被顶成 0，诊断字符串早已点名，此前却没有结构化字段。"""
    row = _first()

    assert row.roll_down == Decimal("0")
    assert row.roll_down_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_CURVE_UNAVAILABLE


def test_same_source_curve_leaves_roll_down_observed():
    """两端同源只让"两端相减"恒为 0；roll_down 沿单条曲线滚动，仍是观测值。

    2026-07-31 的真实形态正是这一种：曲线停在 06-30，两端解析到同一份快照，
    treasury_curve 被判不可用，而 roll_down 仍从那条（陈旧的）曲线上算出了真实数字。
    把它一并标成不可用是假警报，会把一个能用的数字从页面上抹掉。
    """
    stale = _curve("2.50")

    row = _first(treasury_curve_current=stale, treasury_curve_prior=dict(stale))

    assert row.treasury_curve_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability == CURVE_EFFECT_OK
    assert row.roll_down_availability_reason is None


def test_missing_prior_curve_alone_leaves_roll_down_observed():
    """roll_down 不需要上期曲线：只缺上期时它照算，不能跟着 treasury_curve 一起改判。"""
    row = _first(treasury_curve_current=_curve("2.50"), treasury_curve_prior=None)

    assert row.treasury_curve_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability == CURVE_EFFECT_OK


def test_missing_roll_window_is_roll_down_only():
    """缺上期余额行只打掉 roll_down；treasury_curve 仍由当期余额行算出，照常是观测值。"""
    row = _first(
        balance_rows_prior=[],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.roll_down == Decimal("0")
    assert row.roll_down_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING
    assert row.treasury_curve_availability == CURVE_EFFECT_OK


def test_same_day_prior_row_is_also_a_missing_roll_window():
    row = _first(
        balance_rows_prior=[_balance_row("2026-07-31")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.roll_down_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING


def test_roll_down_stays_observed_when_the_curve_is_usable():
    row = _first(treasury_curve_current=_curve("2.50"), treasury_curve_prior=_curve("2.25"))

    assert row.roll_down_availability == CURVE_EFFECT_OK
    assert row.roll_down_availability_reason is None


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"years_to_maturity": "0"}, id="matured"),
        pytest.param({"modified_duration": "0"}, id="zero_duration"),
        pytest.param({"market_value_amount": "0"}, id="flat_position"),
    ],
)
def test_roll_down_shares_the_structural_exemptions(overrides):
    row = _first(
        balance_rows_current=[_balance_row("2026-07-31", **overrides)],
        balance_rows_prior=[_balance_row("2026-06-30", **overrides)],
    )

    assert row.roll_down_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY


def test_tenor_below_the_curve_short_end_is_a_roll_down_gap_not_an_observation():
    """曲线最短 3M，而 SCP / 同业存单的剩余期限普遍在 3M 以内。

    插值器对支撑区间外的取点一律钳到最近节点，两次取值落在同一个节点上，
    roll_down 因此恒为 0——这是曲线没有覆盖到，不是这只券真的没有骑乘收益。
    只有 roll_down 受影响：它是唯一一个在同一条曲线上读两个期限的效应，
    treasury_curve / credit_spread 比的是同一期限的两天，钳位后仍是真实变动。
    """
    row = _first(
        balance_rows_current=[_short_end_balance_row("2026-07-31")],
        balance_rows_prior=[_short_end_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )

    assert row.roll_down == Decimal("0")
    assert row.roll_down_availability == CURVE_EFFECT_UNAVAILABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_TENOR_OUTSIDE_CURVE
    assert row.treasury_curve_availability == CURVE_EFFECT_OK


def test_a_flat_curve_inside_its_support_is_still_an_observed_zero_roll():
    """曲线本身是平的（各期限同一水平）时 roll_down 也是 0，但那是观测到的平坦。

    把它一并报成"曲线覆盖不到"就是假警报——这条测试守的正是新判据的边界。
    """
    flat = _curve("2.50")

    row = _first(treasury_curve_current=flat, treasury_curve_prior=_curve("2.25"))

    assert row.roll_down == Decimal("0")
    assert row.roll_down_availability == CURVE_EFFECT_OK


def test_missing_market_value_base_is_unavailable_on_all_three_effects():
    """市值基数全 NULL 会把三项效应一起顶成 0，且明确不属于结构性豁免。

    此前这一条只有诊断字符串，枚举报 ``ok``——正是"字符串报警、枚举正常"的那种漂移。
    """
    row = _first(
        balance_rows_current=[_credit_balance_row("2026-07-31", market_value_amount=None)],
        balance_rows_prior=[_credit_balance_row("2026-06-30", market_value_amount=None)],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
        aaa_credit_curve_current=_curve("3.50"),
        aaa_credit_curve_prior=_curve("3.20"),
    )

    assert (row.roll_down, row.treasury_curve, row.credit_spread) == (
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    )
    for availability, reason in (
        (row.roll_down_availability, row.roll_down_availability_reason),
        (row.treasury_curve_availability, row.treasury_curve_availability_reason),
        (row.credit_spread_availability, row.credit_spread_availability_reason),
    ):
        assert availability == CURVE_EFFECT_UNAVAILABLE
        assert reason == CURVE_EFFECT_REASON_MARKET_VALUE_BASE_MISSING


def test_non_fvtpl_rows_report_roll_down_as_not_applicable():
    row = _first(
        pnl_fi_rows=[_fact_row(accounting_basis="AC")],
        balance_rows_current=[_balance_row("2026-07-31", accounting_basis="AC")],
        balance_rows_prior=[_balance_row("2026-06-30", accounting_basis="AC")],
    )

    assert row.roll_down_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_NON_FVTPL_BASIS


def test_row_without_a_current_balance_row_reports_roll_down_gap_too():
    row = _first(balance_rows_current=[])

    assert row.roll_down_availability == CURVE_EFFECT_NOT_APPLICABLE
    assert row.roll_down_availability_reason == CURVE_EFFECT_REASON_BALANCE_ROW_MISSING


# ---------------------------------------------------------------------------
# 2. 汇总级折叠
# ---------------------------------------------------------------------------


def test_summary_reports_unavailable_when_every_applicable_row_lost_its_curve():
    summary = _build_summary(_run())

    assert summary.total_treasury_curve.raw == 0.0
    assert summary.treasury_curve_availability.status == CURVE_EFFECT_UNAVAILABLE
    assert summary.treasury_curve_availability.unavailable_rows == 1
    assert summary.treasury_curve_availability.applicable_rows == 1
    assert summary.treasury_curve_availability.reasons == [CURVE_EFFECT_REASON_CURVE_UNAVAILABLE]


def test_summary_stays_ok_when_the_curve_was_comparable():
    summary = _build_summary(
        _run(treasury_curve_current=_curve("2.50"), treasury_curve_prior=_curve("2.25"))
    )

    assert summary.treasury_curve_availability.status == CURVE_EFFECT_OK
    assert summary.treasury_curve_availability.reasons == []


def test_non_fvtpl_only_book_folds_to_not_applicable_not_ok():
    """全是 AC 行时合计 0 也不是"曲线没动"，但它同样不需要补数据。"""
    summary = _build_summary(
        _run(
            pnl_fi_rows=[_fact_row(accounting_basis="AC")],
            balance_rows_current=[_balance_row("2026-07-31", accounting_basis="AC")],
            balance_rows_prior=[_balance_row("2026-06-30", accounting_basis="AC")],
        )
    )

    assert summary.treasury_curve_availability.status == CURVE_EFFECT_NOT_APPLICABLE
    assert summary.treasury_curve_availability.applicable_rows == 0
    assert summary.treasury_curve_availability.reasons == [CURVE_EFFECT_REASON_NON_FVTPL_BASIS]


def test_structurally_exempt_rows_do_not_dilute_the_unavailable_ratio():
    """分母只数可用行，否则一本 AC 大账会把"全部 FVTPL 行不可用"稀释成 partial。"""
    folded = summarize_curve_effect_availability(
        [
            (CURVE_EFFECT_UNAVAILABLE, CURVE_EFFECT_REASON_CURVE_UNAVAILABLE),
            (CURVE_EFFECT_NOT_APPLICABLE, CURVE_EFFECT_REASON_NON_FVTPL_BASIS),
            (CURVE_EFFECT_NOT_APPLICABLE, CURVE_EFFECT_REASON_NON_FVTPL_BASIS),
        ]
    )

    assert folded.status == CURVE_EFFECT_UNAVAILABLE
    assert (folded.unavailable_rows, folded.applicable_rows) == (1, 1)


def test_summary_reports_roll_down_availability_independently_of_the_curve_shift():
    """同一页上"利率效应不可用"而"骑乘 0"是自相矛盾的；两者必须各自表态。

    这里刻意用 2026-07-31 的真实形态（曲线两端同源）：treasury_curve 不可用，
    而 roll_down 仍是观测量——汇总必须如实分开报，而不是共用一个结论。
    """
    stale = _curve("2.50")
    summary = _build_summary(_run(treasury_curve_current=stale, treasury_curve_prior=dict(stale)))

    assert summary.treasury_curve_availability.status == CURVE_EFFECT_UNAVAILABLE
    assert summary.roll_down_availability.status == CURVE_EFFECT_OK
    assert summary.roll_down_availability.reasons == []


def test_summary_folds_roll_down_window_gaps():
    summary = _build_summary(
        _run(
            balance_rows_prior=[],
            treasury_curve_current=_curve("2.50"),
            treasury_curve_prior=_curve("2.25"),
        )
    )

    assert summary.roll_down_availability.status == CURVE_EFFECT_UNAVAILABLE
    assert summary.roll_down_availability.reasons == [CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING]
    assert summary.treasury_curve_availability.status == CURVE_EFFECT_OK


def test_summary_roll_down_folds_to_partial_on_a_mixed_book():
    rows = _run(
        pnl_fi_rows=[_fact_row(), _fact_row(instrument_code="NO-WINDOW-01")],
        balance_rows_current=[
            _balance_row("2026-07-31"),
            _balance_row("2026-07-31", instrument_code="NO-WINDOW-01"),
        ],
        # 第二只券没有上期余额行，滚动窗口缺失；第一只券完好。
        balance_rows_prior=[_balance_row("2026-06-30")],
        treasury_curve_current=_curve("2.50"),
        treasury_curve_prior=_curve("2.25"),
    )
    summary = _build_summary(rows)

    assert summary.roll_down_availability.status == CURVE_EFFECT_PARTIAL
    assert (
        summary.roll_down_availability.unavailable_rows,
        summary.roll_down_availability.applicable_rows,
    ) == (1, 2)


def test_mixed_book_folds_to_partial():
    folded = summarize_curve_effect_availability(
        [
            (CURVE_EFFECT_UNAVAILABLE, CURVE_EFFECT_REASON_CURVE_UNAVAILABLE),
            (CURVE_EFFECT_OK, None),
        ]
    )

    assert folded.status == CURVE_EFFECT_PARTIAL
    assert (folded.unavailable_rows, folded.applicable_rows) == (1, 1 + 1)


# ---------------------------------------------------------------------------
# 3. 数值不变：整条已发布 payload 冻结
# ---------------------------------------------------------------------------

_NEW_ROW_KEYS = frozenset(
    {
        "roll_down_availability",
        "roll_down_availability_reason",
        "treasury_curve_availability",
        "treasury_curve_availability_reason",
        "credit_spread_availability",
        "credit_spread_availability_reason",
    }
)
_NEW_SUMMARY_KEYS = frozenset(
    {"roll_down_availability", "treasury_curve_availability", "credit_spread_availability"}
)

# 整改前 `PnlBridgeRowSchema` 对 2026-07-31 缺曲线场景发布的完整行，逐字段照抄。
# 曲线效应仍是 0，`explained_pnl` = 514 的 100,000，残差闭合、比率为 0。
_FROZEN_ROW_BEFORE_AVAILABILITY: dict = {
    "report_date": "2026-07-31",
    "instrument_code": "CURVE-GAP-01",
    "portfolio_name": "FI Desk",
    "cost_center": "CC100",
    "accounting_basis": "FVTPL",
    "beginning_dirty_mv": {
        "raw": 10250000.0,
        "unit": "yuan",
        "display": "10,250,000.00",
        "precision": 2,
        "sign_aware": False,
    },
    "ending_dirty_mv": {
        "raw": 10250000.0,
        "unit": "yuan",
        "display": "10,250,000.00",
        "precision": 2,
        "sign_aware": False,
    },
    "carry": {
        "raw": 100000.0,
        "unit": "yuan",
        "display": "+100,000.00",
        "precision": 2,
        "sign_aware": True,
    },
    "roll_down": {"raw": 0.0, "unit": "yuan", "display": "+0.00", "precision": 2, "sign_aware": True},
    "treasury_curve": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "credit_spread": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "fx_translation": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "realized_trading": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "unrealized_fv": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "manual_adjustment": {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "explained_pnl": {
        "raw": 100000.0,
        "unit": "yuan",
        "display": "+100,000.00",
        "precision": 2,
        "sign_aware": True,
    },
    "actual_pnl": {
        "raw": 100000.0,
        "unit": "yuan",
        "display": "+100,000.00",
        "precision": 2,
        "sign_aware": True,
    },
    "residual": {"raw": 0.0, "unit": "yuan", "display": "+0.00", "precision": 2, "sign_aware": True},
    "residual_ratio": {
        "raw": 0.0,
        "unit": "ratio",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    },
    "quality_flag": "warning",
    "current_balance_found": True,
    "prior_balance_found": True,
    "balance_diagnostics": [
        "TREASURY_CURVE_UNAVAILABLE: curve_type=treasury; no benchmark curve for the current, "
        "prior period end; roll_down / treasury_curve defaulted to 0. This is a missing input, "
        "not an observed zero rate move."
    ],
}


def test_published_row_payload_is_unchanged_apart_from_the_new_availability_keys():
    """缺曲线行的每一个既有字段逐字段冻结。

    这条测试是"我没有动数字"的证据：`treasury_curve` 依然是 `+0.00` 而不是 null 或
    "unavailable"，`explained_pnl` / `residual` / `residual_ratio` 及其 display 串
    与整改前完全一致。要把 0 换成缺失值，必须先来这里改冻结值——那正是应该被看见
    的一次口径变更，而不是顺手做掉的事。
    """
    row = _first()
    dumped = PnlBridgeRowSchema.model_validate(
        promote_flat_payload(row, PnlBridgeRowSchema)
    ).model_dump(mode="json")

    assert set(dumped) - _NEW_ROW_KEYS == set(_FROZEN_ROW_BEFORE_AVAILABILITY)
    for key, expected in _FROZEN_ROW_BEFORE_AVAILABILITY.items():
        assert dumped[key] == expected, key

    # 新增字段确实是"这个 0 的性质"，而不是又一个数字。
    assert dumped["treasury_curve_availability"] == CURVE_EFFECT_UNAVAILABLE
    assert dumped["roll_down_availability"] == CURVE_EFFECT_UNAVAILABLE
    # `roll_down` 的金额通道原样不动：仍是那个 `+0.00`，不是 null、不是字符串。
    assert dumped["roll_down"] == _FROZEN_ROW_BEFORE_AVAILABILITY["roll_down"]


def test_summary_amount_fields_are_unchanged_apart_from_the_new_availability_keys():
    dumped = _build_summary(_run()).model_dump(mode="json")
    amounts = {key: value for key, value in dumped.items() if key not in _NEW_SUMMARY_KEYS}

    assert set(dumped) - _NEW_SUMMARY_KEYS == set(amounts)
    assert amounts["total_treasury_curve"] == {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    }
    assert amounts["total_roll_down"] == {
        "raw": 0.0,
        "unit": "yuan",
        "display": "+0.00",
        "precision": 2,
        "sign_aware": True,
    }
    assert amounts["total_credit_spread"]["raw"] == 0.0
    assert amounts["total_explained_pnl"]["raw"] == 100000.0
    assert amounts["total_actual_pnl"]["raw"] == 100000.0
    assert amounts["total_residual"]["raw"] == 0.0


def test_availability_fields_are_the_only_schema_additions():
    """字段级契约锁：既有键一个都没被改名或删除。"""
    legacy_row_keys = frozenset(_FROZEN_ROW_BEFORE_AVAILABILITY)
    assert frozenset(PnlBridgeRowSchema.model_fields) == legacy_row_keys | _NEW_ROW_KEYS

    legacy_summary_keys = frozenset(PnlBridgeSummarySchema.model_fields) - _NEW_SUMMARY_KEYS
    assert "total_treasury_curve" in legacy_summary_keys
    assert frozenset(PnlBridgeSummarySchema.model_fields) == legacy_summary_keys | _NEW_SUMMARY_KEYS
