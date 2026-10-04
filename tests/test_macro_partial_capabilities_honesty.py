"""M7/M8/M9/M11/M15：观察标记 + 禁止静默默认填洞。"""

from __future__ import annotations

from backend.app.services import macro_toolkit_analysis_service as macro_toolkit_analysis
from backend.app.services import macro_toolkit_route_support as macro_toolkit_support

from datetime import date, timedelta

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import (
    compute_credit_spread_risk,
    compute_liquidity_stress_test,
    compute_macro_portfolio_impact,
    compute_monetary_policy_stance,
    compute_yield_curve_shape,
)
from backend.app.core_finance.macro.macro_portfolio_impact import build_bond_portfolio_profile
from backend.app.services.macro_toolkit_route_support import _risk_tensor_to_liquidity_inputs

_REPORT = date(2026, 7, 10)


def test_partial_capabilities_are_wired_visible() -> None:
    definitions = {item["key"]: item for item in macro_toolkit_support._CAPABILITY_DEFINITIONS}
    for key in (
        "yield_curve_shape",
        "credit_spread_risk",
        "liquidity_stress",
        "macro_portfolio_impact",
    ):
        assert definitions[key]["route_status"] == "wired", key
        assert definitions[key]["frontend_status"] == "visible", key
        assert key in macro_toolkit_route._DECISION_SUMMARY_OBSERVATION_KEYS


def test_m15_rejects_default_curve_fill() -> None:
    profile = build_bond_portfolio_profile(
        [
            {
                "market_value": 1_000_000,
                "maturity_date": date(2029, 7, 10),
                "coupon_rate": 0.03,
            }
        ],
        _REPORT,
    )
    # 空曲线：不得用 2.5% 填洞后 complete
    empty = compute_macro_portfolio_impact(profile, {}, _REPORT)
    assert empty["data_status"] == "unavailable"
    assert empty["formal_use_allowed"] is False
    assert "NO_GOVERNMENT_CURVE_TENORS" in empty["warnings"]
    assert empty["scenarios"] == []

    # 缺部分期限：degraded，且 new_curve 不含缺失节点
    partial_curve = {"1Y": 1.5, "5Y": 1.8, "10Y": 2.0}
    partial = compute_macro_portfolio_impact(profile, partial_curve, _REPORT)
    assert partial["data_status"] == "degraded"
    assert any(w.startswith("CURVE_TENORS_MISSING") for w in partial["warnings"])
    for scenario in partial["scenarios"]:
        assert "3Y" not in scenario["new_curve"]
        assert "7Y" not in scenario["new_curve"]
        assert scenario["new_curve"]["10Y"] == pytest.approx(2.0 + scenario["curve_shifts_bp"]["10Y"] / 100.0)


def test_m15_10y_plus_bucket_uses_own_duration_not_portfolio_average() -> None:
    """审计回归：10Y+ 桶此前落不进 tenor_to_bucket 映射，只能进 other 桶并被
    赋予组合加权久期（远低于长端自身久期），系统性低估长端情景损失。"""
    positions = [
        {
            "market_value": 5_000_000,
            "maturity_date": _REPORT + timedelta(days=365 * 2),
            "coupon_rate": 0.03,
        },
        {
            "market_value": 5_000_000,
            "maturity_date": _REPORT + timedelta(days=365 * 20),
            "coupon_rate": 0.03,
        },
    ]
    profile = build_bond_portfolio_profile(positions, _REPORT)
    ten_plus = profile["buckets"]["10Y+"]
    assert ten_plus["market_value"] > 0
    # 10Y+ 桶自身久期应明显高于组合加权久期（长端持仓被短端稀释）
    assert ten_plus["avg_duration"] > profile["weighted_duration"] * 1.5

    curve = {"1Y": 1.5, "3Y": 1.7, "5Y": 1.8, "7Y": 1.9, "10Y": 2.0}
    result = compute_macro_portfolio_impact(profile, curve, _REPORT)
    baseline = next(s for s in result["scenarios"] if s["name"] == "baseline")
    impacts = baseline["bucket_impacts"]

    assert "other" not in impacts
    assert "10Y+" in impacts
    ten_plus_impact = impacts["10Y+"]
    assert ten_plus_impact["shift_source_tenor"] == "10Y"

    shift_bp = baseline["curve_shifts_bp"]["10Y"]
    credit_shift = baseline["credit_spread_shift_bp"]
    expected_delta = -ten_plus["market_value"] * ten_plus["avg_duration"] * (shift_bp + credit_shift) / 10000.0
    assert ten_plus_impact["delta_mv"] == pytest.approx(round(expected_delta, 2))

    # 修复前会把组合加权久期错误地赋给该桶；确认与该错误值不同，证明用了自身久期
    wrong_delta = -ten_plus["market_value"] * profile["weighted_duration"] * (shift_bp + credit_shift) / 10000.0
    assert ten_plus_impact["delta_mv"] != pytest.approx(round(wrong_delta, 2))


def test_m8_secondary_spreads_not_zero_filled() -> None:
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.5},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.0},
    ]
    payload = compute_yield_curve_shape(rows, report_date=_REPORT)
    assert payload["formal_use_allowed"] is False
    assert payload["data_status"] == "degraded"
    assert payload["spreads"]["10Y-1Y"] == pytest.approx(50.0)
    assert payload["spreads"]["10Y-5Y"] is None
    assert payload["spreads"]["30Y-10Y"] is None
    assert "SPREAD_10Y_5Y_UNAVAILABLE" in payload["warnings"]
    assert "SPREAD_30Y_10Y_UNAVAILABLE" in payload["warnings"]


def test_m7_uses_latest_common_government_curve_date() -> None:
    common_date = _REPORT - timedelta(days=1)
    rows = [
        # Newer funding-only point must not become M7's valuation date.
        {"biz_date": _REPORT, "curve_id": "CN_DR", "tenor": "7D", "rate_value": 1.7},
        {"biz_date": _REPORT, "curve_id": "CN_RRP", "tenor": "7D", "rate_value": 1.4},
        {"biz_date": common_date, "curve_id": "CN_DR", "tenor": "7D", "rate_value": 1.65},
        {"biz_date": common_date, "curve_id": "CN_RRP", "tenor": "7D", "rate_value": 1.4},
        {"biz_date": common_date, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.5},
        {"biz_date": common_date, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.0},
        {"biz_date": common_date, "curve_id": "CN_GOVT", "tenor": "3Y", "rate_value": 1.8},
        {"biz_date": common_date, "curve_id": "CN_CREDIT_AAA", "tenor": "3Y", "rate_value": 2.3},
        {"biz_date": common_date, "curve_id": "CN_CREDIT_AA", "tenor": "3Y", "rate_value": 2.6},
    ]

    payload = compute_monetary_policy_stance(rows, report_date=_REPORT)

    assert payload["as_of_date"] == common_date.isoformat()
    assert payload["key_metrics"]["gov_slope_10y_1y_bp"] == pytest.approx(50.0)
    assert payload["key_metrics"]["aaa_spread_bp"] == pytest.approx(50.0)
    assert payload["key_metrics"]["aa_minus_aaa_bp"] == pytest.approx(30.0)
    assert "GOVERNMENT_SLOPE_MISSING" not in payload["warnings"]
    assert "AAA_SPREAD_MISSING" not in payload["warnings"]
    assert f"as_of={common_date.isoformat()}" in macro_toolkit_analysis._capability_result_evidence(
        "monetary_policy_stance",
        payload,
    )


def test_m7_does_not_mix_aa_and_aaa_tenors() -> None:
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_DR", "tenor": "7D", "rate_value": 1.65},
        {"biz_date": _REPORT, "curve_id": "CN_RRP", "tenor": "7D", "rate_value": 1.4},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.5},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.0},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "3Y", "rate_value": 1.8},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AAA", "tenor": "3Y", "rate_value": 2.3},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AAA", "tenor": "5Y", "rate_value": 2.5},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AA", "tenor": "5Y", "rate_value": 3.1},
    ]

    payload = compute_monetary_policy_stance(rows, report_date=_REPORT)

    assert payload["key_metrics"]["aaa_spread_bp"] == pytest.approx(50.0)
    assert payload["key_metrics"]["aa_minus_aaa_bp"] is None


def test_m9_marks_missing_aa_and_change_windows() -> None:
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "3Y", "rate_value": 1.8},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AAA", "tenor": "3Y", "rate_value": 2.3},
    ]
    payload = compute_credit_spread_risk(rows, report_date=_REPORT)
    assert payload["formal_use_allowed"] is False
    assert payload["data_status"] == "degraded"
    assert payload["aaa_spread_bp"] == pytest.approx(50.0)
    assert "AA_MINUS_AAA_UNAVAILABLE" in payload["warnings"]
    assert "WEEKLY_CHANGE_UNAVAILABLE" in payload["warnings"]


def test_m9_uses_latest_common_credit_and_government_curve_date() -> None:
    common_date = _REPORT - timedelta(days=1)
    rows = [
        # A newer unrelated funding point must not become M9's valuation date.
        {"biz_date": _REPORT, "curve_id": "CN_DR", "tenor": "7D", "rate_value": 1.7},
        {"biz_date": common_date, "curve_id": "CN_GOVT", "tenor": "3Y", "rate_value": 1.8},
        {"biz_date": common_date, "curve_id": "CN_CREDIT_AAA", "tenor": "3Y", "rate_value": 2.3},
        {"biz_date": common_date, "curve_id": "CN_CREDIT_AA", "tenor": "3Y", "rate_value": 2.6},
    ]

    payload = compute_credit_spread_risk(rows, report_date=_REPORT)

    assert payload["data_status"] == "degraded"
    assert payload["as_of_date"] == common_date.isoformat()
    assert payload["aaa_spread_bp"] == pytest.approx(50.0)
    assert payload["aa_minus_aaa_bp"] == pytest.approx(30.0)
    assert "AAA_SPREAD_MISSING" not in payload["warnings"]
    assert f"as_of={common_date.isoformat()}" in macro_toolkit_analysis._capability_result_evidence(
        "credit_spread_risk",
        payload,
    )


def test_m9_does_not_mix_aa_and_aaa_tenors() -> None:
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "3Y", "rate_value": 1.8},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AAA", "tenor": "3Y", "rate_value": 2.3},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AAA", "tenor": "5Y", "rate_value": 2.5},
        {"biz_date": _REPORT, "curve_id": "CN_CREDIT_AA", "tenor": "5Y", "rate_value": 3.1},
    ]

    payload = compute_credit_spread_risk(rows, report_date=_REPORT)

    assert payload["credit_spread_tenor"] == "3Y"
    assert payload["aa_minus_aaa_bp"] is None
    assert "AA_MINUS_AAA_UNAVAILABLE" in payload["warnings"]


def test_m11_skips_buckets_without_net_gap() -> None:
    payload = compute_liquidity_stress_test(
        [{"book_id": "B1", "dv01_sum": 10, "share_of_abs_dv01": 0.2, "row_count": 1}],
        [{"bucket_name": "<=1M", "asset_amount": 1, "liability_amount": 2}],  # no net_gap
        report_date=_REPORT,
        total_assets=100,
    )
    assert payload["formal_use_allowed"] is False
    assert payload["data_status"] == "degraded"
    assert payload["buckets"] == []
    assert any(w.startswith("BUCKET_NET_GAP_MISSING") for w in payload["warnings"])


def test_m11_issuer_top5_weight_not_scored_as_book_dv01_concentration() -> None:
    """审计 P0-2 回归：issuer_top5_weight 是发行人市值 Top5 集中度（利率债组合常态
    0.6-1.0），不是单账簿 DV01 份额；不得填入 share_of_abs_dv01 触发 >=0.60 的
    CRITICAL 告警并虚增 40 分压力分。"""
    proxy_rows, bucket_rows, total_assets = _risk_tensor_to_liquidity_inputs(
        {
            "issuer_top5_weight": 0.9,
            "portfolio_dv01": 1234.5,
            "bond_count": 42,
            "total_market_value": 1_000_000.0,
        }
    )

    # dv01_sum / row_count 等真实字段保留展示用途；集中度腿 fail-closed 置 None。
    assert len(proxy_rows) == 1
    assert proxy_rows[0]["share_of_abs_dv01"] is None
    assert proxy_rows[0]["dv01_sum"] == 1234.5
    assert proxy_rows[0]["row_count"] == 42
    assert total_assets == 1_000_000.0

    payload = compute_liquidity_stress_test(
        proxy_rows,
        bucket_rows,
        report_date=_REPORT,
        total_assets=total_assets,
    )
    assert payload["top_book_share_of_abs_dv01"] is None
    # 集中度腿缺失 → 不加分；无期限缺口输入时压力分必须为 0（不含 40 分集中度腿）。
    assert payload["stress_score"] == 0
    assert payload["alerts"] == []
    assert all("DV01 集中度" not in str(alert.get("message", "")) for alert in payload["alerts"])
    assert payload["top_books"][0]["dv01_sum"] == 1234.5
