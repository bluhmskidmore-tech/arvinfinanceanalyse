"""缺到期日/缺剩余期限时，Campisi 链必须显式披露回退，不得静默污染桶与能力项。

覆盖两个 P2 口径一致性缺陷：

1. ``campisi.py`` 缺 ``maturity_date_start`` 时按 3.0 年取曲线点且无诊断，
   同时按 3Y 落进 ``1-3Y`` 桶 —— 桶级汇总失真且不可见。
   修复后：输出 ``maturity_date_missing_fallback_3y`` 诊断，桶归入 ``UNKNOWN``
   （与 service 侧 ``_formal_maturity_bucket`` 已有的缺失桶名一致）。

2. ``campisi_decision_grade.py`` 缺 ``years_to_maturity`` 时用 3Y 代理但不计入
   ``residual_reasons``，未解释余额仍归 ``selection_proxy``（被下游读作选券能力）。
   修复后：归入 ``residual_noise``，与 ``missing_analytics`` 对称。

期望值均为手算字面量，不调用被测函数回算。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.campisi import (
    MATURITY_DATE_MISSING_DIAGNOSTIC,
    _MATURITY_BUCKET_LABELS,
    campisi_attribution,
    campisi_enhanced,
    maturity_bucket_attribution,
)
from backend.app.core_finance.campisi_decision_grade import compute_decision_grade_row

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 1, 31)
ONE_YEAR_MATURITY = date(2027, 1, 1)

# 期初/期末均为平坦国债曲线（2.0% → 3.0%），任何期限取点的基准变动都是
# (3.0 - 2.0) / 100 = 0.01。平坦曲线让"取点期限被猜成 3Y"不干扰数值手算，
# 从而把断言聚焦在诊断与落桶这两件被修复的事情上。
FLAT_MARKET_START = {
    "treasury_1y": 2.0,
    "treasury_3y": 2.0,
    "treasury_5y": 2.0,
    "treasury_7y": 2.0,
    "treasury_10y": 2.0,
    "treasury_30y": 2.0,
}
FLAT_MARKET_END = {
    "treasury_1y": 3.0,
    "treasury_3y": 3.0,
    "treasury_5y": 3.0,
    "treasury_7y": 3.0,
    "treasury_10y": 3.0,
    "treasury_30y": 3.0,
}

# ---------------------------------------------------------------------------
# 手算期望（零息国债，num_days = (01-31 − 01-01).days = 30）
#
# GOV_OK：mat=2027-01-01，as_of=2026-01-01 → 剩余 365 天 = 1.0 年
#   coupon = 0        → income_return = 0 × 1000 × 30/365 = 0
#   coupon = 0        → Macaulay = 剩余年数 = 1
#   ytm = 0.05, freq = 2（"国债" 非超短融）
#                     → mod_dur = 1 / (1 + 0.05/2) = 1/1.025 = 40/41
#   bench = 0.01      → treasury = −(40/41) × 0.01 × 1000 = −400/41
#   rating = GOV      → spread = 0
#   全价基准：ΔAI = 0，coupon_cash = 0 − 0 = 0
#                     → total_return = (990 − 1000) + 0 = −10
#   selection = −10 − 0 − (−400/41) − 0 = −10/41
#   桶：years = 1.0 ≤ 1 → "0-1Y"
#
# GOV_NOMAT：maturity_date_start = None
#   mat_date = None   → mod_dur = 0（bond_four_effects 既有语义）
#                     → treasury = 0，spread = 0
#   total_return = (1980 − 2000) + 0 = −20
#   selection = −20 − 0 − 0 − 0 = −20
#   桶：修复前按回退值 3.0 落进 "1-3Y"；修复后归 "UNKNOWN"
# ---------------------------------------------------------------------------
GOV_OK_MOD_DURATION = 1 / 1.025
GOV_OK_TREASURY_EFFECT = -400 / 41
GOV_OK_SELECTION_EFFECT = -10 / 41
GOV_OK_TOTAL_RETURN = -10.0
GOV_NOMAT_TOTAL_RETURN = -20.0
GOV_NOMAT_SELECTION_EFFECT = -20.0

ABS_TOL = 1e-9


def _zero_coupon_bond(**overrides: object) -> dict[str, object]:
    return {
        "bond_code": "GOV_OK",
        "market_value_start": 1_000.0,
        "market_value_end": 990.0,
        "face_value_start": 1_000.0,
        "coupon_rate_start": 0.0,
        "yield_to_maturity_start": 0.05,
        "asset_class_start": "国债",
        "maturity_date_start": ONE_YEAR_MATURITY,
        "accrued_interest_start": 0.0,
        "accrued_interest_end": 0.0,
        **overrides,
    }


def _bond_with_maturity() -> dict[str, object]:
    return _zero_coupon_bond()


def _bond_without_maturity() -> dict[str, object]:
    return _zero_coupon_bond(
        bond_code="GOV_NOMAT",
        maturity_date_start=None,
        market_value_start=2_000.0,
        market_value_end=1_980.0,
        face_value_start=2_000.0,
    )


def _attribution(positions: list[dict[str, object]]):
    return campisi_attribution(
        positions_merged=positions,
        market_start=FLAT_MARKET_START,
        market_end=FLAT_MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )


def _row_by_code(result, bond_code: str) -> dict:
    matches = [row for row in result.by_bond if row["bond_code"] == bond_code]
    assert len(matches) == 1, f"expected exactly one {bond_code} row, got {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# 缺陷 1：缺到期日的诊断披露与落桶
# ---------------------------------------------------------------------------


def test_missing_maturity_date_emits_fallback_diagnostic() -> None:
    """缺到期日不得静默按 3Y 取点：必须与 mod_dur_fallback_zero 一样留痕。"""
    result = _attribution([_bond_with_maturity(), _bond_without_maturity()])

    assert f"GOV_NOMAT: {MATURITY_DATE_MISSING_DIAGNOSTIC}" in result.diagnostics
    # 下层归零诊断保持不变：上下层现在同时披露，语义一致。
    assert "GOV_NOMAT: mod_dur_fallback_zero" in result.diagnostics
    # 有到期日的券不得被牵连出任何诊断。
    assert not [d for d in result.diagnostics if d.startswith("GOV_OK:")]


def test_missing_maturity_date_bond_lands_in_unknown_bucket_not_1_3y() -> None:
    """回退值 3.0 只能用于曲线取点，不得把券按 3Y 归进真实的 1-3Y 桶。"""
    result = _attribution([_bond_with_maturity(), _bond_without_maturity()])

    assert _row_by_code(result, "GOV_NOMAT")["maturity_bucket"] == "UNKNOWN"
    assert _row_by_code(result, "GOV_OK")["maturity_bucket"] == "0-1Y"


def test_unknown_bucket_is_aggregated_not_dropped() -> None:
    """UNKNOWN 桶必须真实承接金额，且 1-3Y 桶必须保持全零（缺陷的可见证据）。"""
    buckets = maturity_bucket_attribution(
        positions_merged=[_bond_with_maturity(), _bond_without_maturity()],
        market_start=FLAT_MARKET_START,
        market_end=FLAT_MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    unknown = buckets["UNKNOWN"]
    assert unknown["market_value_start"] == pytest.approx(2_000.0, abs=ABS_TOL)
    assert unknown["income_return"] == pytest.approx(0.0, abs=ABS_TOL)
    assert unknown["treasury_effect"] == pytest.approx(0.0, abs=ABS_TOL)
    assert unknown["spread_effect"] == pytest.approx(0.0, abs=ABS_TOL)
    assert unknown["selection_effect"] == pytest.approx(GOV_NOMAT_SELECTION_EFFECT, abs=ABS_TOL)
    assert unknown["total_return"] == pytest.approx(GOV_NOMAT_TOTAL_RETURN, abs=ABS_TOL)

    # 修复前这里会是 2000 / −20；现在缺到期日的券不再污染真实期限桶。
    assert buckets["1-3Y"] == {
        "market_value_start": 0.0,
        "income_return": 0.0,
        "treasury_effect": 0.0,
        "spread_effect": 0.0,
        "selection_effect": 0.0,
        "total_return": 0.0,
    }

    # 桶聚合不得丢金额：UNKNOWN + 0-1Y 覆盖全部持仓市值。
    assert sum(b["market_value_start"] for b in buckets.values()) == pytest.approx(
        3_000.0, abs=ABS_TOL
    )


def test_enhanced_path_discloses_and_buckets_missing_maturity_identically() -> None:
    """六效应路径与四效应路径共用同一份缺失口径，不得只修一边。"""
    enhanced = campisi_enhanced(
        positions_merged=[_bond_with_maturity(), _bond_without_maturity()],
        market_start=FLAT_MARKET_START,
        market_end=FLAT_MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    assert f"GOV_NOMAT: {MATURITY_DATE_MISSING_DIAGNOSTIC}" in enhanced["diagnostics"]
    buckets = {row["bond_code"]: row["maturity_bucket"] for row in enhanced["by_bond"]}
    assert buckets == {"GOV_OK": "0-1Y", "GOV_NOMAT": "UNKNOWN"}


# ---------------------------------------------------------------------------
# 回归锚：有到期日的正常券行为逐位不变
# ---------------------------------------------------------------------------


def test_normal_bond_only_portfolio_is_bit_for_bit_unchanged() -> None:
    """全部券都有到期日时，诊断、桶集合与四效应数值必须与修复前完全一致。"""
    result = _attribution([_bond_with_maturity()])

    assert result.num_days == 30
    assert result.diagnostics == []

    row = _row_by_code(result, "GOV_OK")
    assert row["maturity_bucket"] == "0-1Y"
    assert row["mod_duration"] == pytest.approx(GOV_OK_MOD_DURATION, abs=ABS_TOL)
    assert row["income_return"] == pytest.approx(0.0, abs=ABS_TOL)
    assert row["treasury_effect"] == pytest.approx(GOV_OK_TREASURY_EFFECT, abs=ABS_TOL)
    assert row["spread_effect"] == pytest.approx(0.0, abs=ABS_TOL)
    assert row["selection_effect"] == pytest.approx(GOV_OK_SELECTION_EFFECT, abs=ABS_TOL)
    assert row["total_return"] == pytest.approx(GOV_OK_TOTAL_RETURN, abs=ABS_TOL)

    assert result.totals["treasury_effect"] == pytest.approx(GOV_OK_TREASURY_EFFECT, abs=ABS_TOL)
    assert result.totals["selection_effect"] == pytest.approx(GOV_OK_SELECTION_EFFECT, abs=ABS_TOL)
    assert result.totals["total_return"] == pytest.approx(GOV_OK_TOTAL_RETURN, abs=ABS_TOL)


def test_no_unknown_bucket_key_appears_when_every_bond_has_maturity() -> None:
    """UNKNOWN 桶按需出现：无缺失券时输出仍是原 6 桶，下游契约形状不变。"""
    buckets = maturity_bucket_attribution(
        positions_merged=[_bond_with_maturity()],
        market_start=FLAT_MARKET_START,
        market_end=FLAT_MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    assert list(buckets) == list(_MATURITY_BUCKET_LABELS)
    assert "UNKNOWN" not in buckets
    assert buckets["0-1Y"]["treasury_effect"] == pytest.approx(
        GOV_OK_TREASURY_EFFECT, abs=ABS_TOL
    )
    assert buckets["0-1Y"]["total_return"] == pytest.approx(GOV_OK_TOTAL_RETURN, abs=ABS_TOL)


# ---------------------------------------------------------------------------
# 缺陷 2：决策评级下缺剩余期限必须归 residual_noise 而非 selection_proxy
# ---------------------------------------------------------------------------

# 1Y 点不变、3Y 点 +2pct：
#   dy_level = ((2.0−2.0) + (4.0−2.0)) / 2 / 100 = 0.01
#   dy_tenor(3Y) = (4.0 − 2.0) / 100 = 0.02
_TREASURY_START = {"1Y": Decimal("2.0"), "3Y": Decimal("2.0")}
_TREASURY_END = {"1Y": Decimal("2.0"), "3Y": Decimal("4.0")}

# 手算固定因子（mod_dur = 1，market_value = 100，非信用、凸性为 0）：
#   rate_level  = −1 × 100 × 0.01          = −1
#   curve_shape = −1 × 100 × (0.02 − 0.01) = −1
#   fixed = carry 40 + (−1) + (−1) + 0 + 0 + realized 5 + manual 2 = 45
#   unexplained = actual_pnl 50 − 45 = 5
_EXPECTED_EXPLAINED = Decimal("45")
_EXPECTED_UNEXPLAINED = Decimal("5")


def _decision_row(years_to_maturity: object) -> dict:
    return {
        "actual_pnl": 50.0,
        "carry": 40.0,
        "realized_trading": 5.0,
        "manual_adjustment": 2.0,
        "market_value": 100.0,
        "modified_duration": 1.0,
        "convexity": 0.0,
        "spread_dv01": 0.0,
        "years_to_maturity": years_to_maturity,
        "is_credit": False,
    }


def _decision_result(years_to_maturity: object) -> dict:
    return compute_decision_grade_row(
        _decision_row(years_to_maturity),
        treasury_start=_TREASURY_START,
        treasury_end=_TREASURY_END,
        credit_start_by_rating={},
        credit_end_by_rating={},
    )


def test_missing_years_to_maturity_routes_unexplained_to_residual_noise() -> None:
    """期限点是猜的，未解释余额就不能算选券能力。"""
    result = _decision_result(None)

    assert "missing_years_to_maturity" in result["residual_reasons"]
    assert result["components"]["selection_proxy"] == Decimal("0")
    assert result["components"]["residual_noise"] == _EXPECTED_UNEXPLAINED
    # 回退仍然要留痕，且不得改变可归因固定因子。
    assert "years_to_maturity_missing_fallback_3y" in result["diagnostics"]
    assert result["explained_pnl"] == _EXPECTED_EXPLAINED


def test_present_years_to_maturity_keeps_unexplained_in_selection_proxy() -> None:
    """配对回归锚：显式给 3Y 时固定因子逐位相同，余额仍归 selection_proxy。

    与上一个用例的唯一差异是 years_to_maturity 缺失与否，因此它单独证明了
    "余额改归 residual_noise" 完全由缺失口径触发，而不是数值口径漂移。
    """
    result = _decision_result(3.0)

    assert result["residual_reasons"] == []
    assert result["diagnostics"] == []
    assert result["components"]["selection_proxy"] == _EXPECTED_UNEXPLAINED
    assert result["components"]["residual_noise"] == Decimal("0")
    assert result["explained_pnl"] == _EXPECTED_EXPLAINED


def test_missing_and_present_years_share_identical_fixed_components() -> None:
    """缺失分支不得顺手改动利率水平/曲线形态等固定因子的数值。"""
    missing = _decision_result(None)["components"]
    present = _decision_result(3.0)["components"]

    for key in (
        "carry",
        "rate_level_effect",
        "curve_shape_effect",
        "credit_spread_effect",
        "convexity_effect",
        "realized_trading",
        "manual_adjustment",
    ):
        assert missing[key] == present[key], key

    assert present["rate_level_effect"] == Decimal("-1.000")
    assert present["curve_shape_effect"] == Decimal("-1.000")
