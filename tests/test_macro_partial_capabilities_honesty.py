"""M8/M9/M11/M15：观察标记 + 禁止静默默认填洞。"""

from __future__ import annotations

from datetime import date

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import (
    compute_credit_spread_risk,
    compute_liquidity_stress_test,
    compute_macro_portfolio_impact,
    compute_yield_curve_shape,
)
from backend.app.core_finance.macro.macro_portfolio_impact import build_bond_portfolio_profile

_REPORT = date(2026, 7, 10)


def test_partial_capabilities_are_wired_visible() -> None:
    definitions = {item["key"]: item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS}
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
