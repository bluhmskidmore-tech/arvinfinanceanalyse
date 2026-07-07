"""M10 宏观领先指标（compute_leading_indicator）单测。

覆盖审计问题：
- credit_spread_aaa_3y / term_spread_10y_1y 缺失时不应被 to_decimal_safe 的
  None -> 0 默认值污染评分（credit_score 不应变成满分 100，term_score 不应变成
  中性 50 却仍参与加权），缺失分项应从 LEI 加权中剔除并对剩余分项权重重归一。
- pmi == 0（真实值）不应被 `if pmi_val:` 误判为缺失。
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from backend.app.core_finance.macro.leading_indicator import (
    _M10_WEIGHTS,
    compute_leading_indicator,
)

pytestmark = pytest.mark.unit

REPORT_DATE = date(2026, 4, 10)


def _base_row(**overrides: object) -> dict[str, object]:
    row = {
        "trade_date": REPORT_DATE,
        "pmi": 51.0,
        "m2_yoy": 8.0,
        "social_financing_yoy": 9.0,
        "term_spread_10y_1y": 60.0,
        "credit_spread_aaa_3y": 40.0,
        "brent_oil": 80.0,
    }
    row.update(overrides)
    return row


def _expected_pmi_score(pmi: float) -> Decimal:
    score = (Decimal(str(pmi)) - Decimal("30")) / Decimal("0.4")
    return max(Decimal("0"), min(Decimal("100"), score))


def _renormalized_lei(scores: dict[str, Decimal]) -> Decimal:
    """按 scores 中出现的分项名重归一加权（缺失分项已不在 scores 中）。"""
    weight_sum = sum(_M10_WEIGHTS[name] for name in scores)
    lei = sum(scores[name] * _M10_WEIGHTS[name] for name in scores) / weight_sum
    return lei.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TestCreditSpreadMissing:
    """问题 1：credit_spread_aaa_3y 缺失时，之前会被误算成 credit_score=100（满分）。"""

    def test_credit_missing_excluded_from_weighting_not_scored_as_100(self) -> None:
        row = _base_row(credit_spread_aaa_3y=None)
        result = compute_leading_indicator([row], REPORT_DATE)

        # 缺失分项不再参与加权，且不应再被错误地计为满分 100。
        assert result["credit_spread_score"] is None

        pmi_score = _expected_pmi_score(51.0)
        term_score = Decimal("50") + Decimal("60") / Decimal("2")  # = 80
        m2_score = Decimal("50")  # 单行数据，len(monthly_m2) < 2 -> 中性
        sf_score = Decimal("50")
        commodity_score = Decimal("50")  # 单行数据，len(monthly_oil) < 2 -> 中性

        expected_lei = _renormalized_lei(
            {
                "pmi": pmi_score,
                "m2_yoy": m2_score,
                "social_financing_yoy": sf_score,
                "term_spread": term_score,
                "commodity": commodity_score,
            }
        )
        assert Decimal(str(result["lei_index"])) == expected_lei

        # 修复前的错误行为：credit_score 满分 100 会把 LEI 拉高；确认不再等于该值。
        buggy_lei = (
            pmi_score * _M10_WEIGHTS["pmi"]
            + m2_score * _M10_WEIGHTS["m2_yoy"]
            + sf_score * _M10_WEIGHTS["social_financing_yoy"]
            + term_score * _M10_WEIGHTS["term_spread"]
            + Decimal("100") * _M10_WEIGHTS["credit_spread"]
            + commodity_score * _M10_WEIGHTS["commodity"]
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert Decimal(str(result["lei_index"])) != buggy_lei

        assert "CREDIT_SPREAD_AAA_MISSING" in result["warnings"]
        assert result["data_status"] == "degraded"


class TestTermSpreadMissing:
    """term_spread_10y_1y 缺失时，之前会被误算成 term_score=50（中性）但仍参与加权。"""

    def test_term_missing_excluded_from_weighting(self) -> None:
        row = _base_row(term_spread_10y_1y=None)
        result = compute_leading_indicator([row], REPORT_DATE)

        assert result["term_spread_score"] is None

        pmi_score = _expected_pmi_score(51.0)
        credit_score = Decimal("100") - Decimal("40")  # = 60
        m2_score = Decimal("50")
        sf_score = Decimal("50")
        commodity_score = Decimal("50")

        expected_lei = _renormalized_lei(
            {
                "pmi": pmi_score,
                "m2_yoy": m2_score,
                "social_financing_yoy": sf_score,
                "credit_spread": credit_score,
                "commodity": commodity_score,
            }
        )
        assert Decimal(str(result["lei_index"])) == expected_lei
        assert "TERM_SPREAD_MISSING" in result["warnings"]
        assert result["data_status"] == "degraded"


class TestBothCreditAndTermMissing:
    """term 与 credit 同时缺失：剩余 4 个分项按权重重归一，不应报错或变成 0。"""

    def test_both_missing_renormalizes_over_remaining_components(self) -> None:
        row = _base_row(term_spread_10y_1y=None, credit_spread_aaa_3y=None)
        result = compute_leading_indicator([row], REPORT_DATE)

        assert result["term_spread_score"] is None
        assert result["credit_spread_score"] is None
        assert result["lei_index"] is not None

        pmi_score = _expected_pmi_score(51.0)
        m2_score = Decimal("50")
        sf_score = Decimal("50")
        commodity_score = Decimal("50")
        expected_lei = _renormalized_lei(
            {
                "pmi": pmi_score,
                "m2_yoy": m2_score,
                "social_financing_yoy": sf_score,
                "commodity": commodity_score,
            }
        )
        assert Decimal(str(result["lei_index"])) == expected_lei
        assert {"TERM_SPREAD_MISSING", "CREDIT_SPREAD_AAA_MISSING"}.issubset(set(result["warnings"]))
        assert result["data_status"] == "degraded"


class TestPmiZeroNotTreatedAsMissing:
    """PMI 真实值为 0 不应被 `if pmi_val:` 误判为缺失并强行赋中性 50 分。"""

    def test_pmi_zero_is_scored_not_defaulted_to_neutral(self) -> None:
        row = _base_row(pmi=0.0)
        result = compute_leading_indicator([row], REPORT_DATE)

        # 修复前：pmi_score 会被误置为 50（中性）。真实 PMI=0 应算出被 clamp 到 0 的低分。
        expected_pmi_score = _expected_pmi_score(0.0)
        assert expected_pmi_score == Decimal("0")
        assert Decimal(str(result["pmi_score"])) == expected_pmi_score
        assert Decimal(str(result["pmi_score"])) != Decimal("50")

    def test_pmi_none_still_defaults_to_neutral(self) -> None:
        """对照：PMI 缺失（None）时才应回落中性 50 分，而不是 PMI=0 时。"""
        row = _base_row(pmi=None)
        result = compute_leading_indicator([row], REPORT_DATE)
        assert Decimal(str(result["pmi_score"])) == Decimal("50")
