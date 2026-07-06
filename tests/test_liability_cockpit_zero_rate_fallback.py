# 回归：liability_cockpit 中 ytm=0 时必须视为"未采集"，回退到 coupon/interest_rate 下一候选，
# 与 liability_analytics_compat.compute_liability_yield_metrics 的显式回退链语义保持一致。
from __future__ import annotations

from backend.app.core_finance.liability_cockpit import (
    compute_cockpit_warnings,
    compute_contribution_split,
)


def _asset_row(*, ytm_value, coupon_rate) -> dict:
    return {
        "is_issuance_like": False,
        "asset_type": "H",
        "asset_class": "AC债券投资",
        "market_value_native": "100000000",
        "ytm_value": ytm_value,
        "coupon_rate": coupon_rate,
    }


def _liability_row(*, coupon_rate) -> dict:
    return {
        "is_issuance_like": True,
        "amortized_cost_native": "100000000",
        "coupon_rate": coupon_rate,
    }


def test_cockpit_warnings_ytm_zero_falls_back_to_coupon_not_zero_rate() -> None:
    asset_row = _asset_row(ytm_value="0", coupon_rate="0.05")
    liability_row = _liability_row(coupon_rate="0.02")

    result = compute_cockpit_warnings("2026-06-30", [asset_row, liability_row], [])

    alert_ids = {item["id"] for item in result["alert_events"]}
    watch_ids = {item["id"] for item in result["watch_items"]}
    # asset_yield 应取 coupon=0.05（ytm=0 视为未采集），NIM = 0.05-0.02 = 0.03，
    # 高于关注/告警阈值；若 ytm=0 被误当作真实零利率，asset_yield 会变成 0，
    # NIM 会跌到 -0.02 并触发"净息差为负"告警。
    assert "alert_nim_negative" not in alert_ids
    assert "watch_nim_thin" not in watch_ids


def test_contribution_split_ytm_zero_falls_back_to_coupon_not_zero_rate() -> None:
    asset_row = _asset_row(ytm_value="0", coupon_rate="0.05")

    result = compute_contribution_split("2026-06-30", [asset_row], [])

    entry = next(row for row in result["contributions"] if row["side"] == "asset")
    assert entry["yield_or_cost"] == 0.05
