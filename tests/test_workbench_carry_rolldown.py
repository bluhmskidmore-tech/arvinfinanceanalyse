# 回归：workbench.build_carry_roll_down（carry / rolldown 符号与 static）与
# build_advanced_attribution_summary（static_return_annualized 不 ×12）。
from __future__ import annotations

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    build_advanced_attribution_summary,
    build_carry_roll_down,
)


def test_build_carry_roll_down_golden_sample() -> None:
    bond_rows = [
        {
            "asset_class_std": "利率债",
            "market_value": 500_000_000,
            "coupon_rate": 0.0285,
            "modified_duration": 4.2,
            "ytm": 0.028,
        }
    ]
    out = build_carry_roll_down(
        report_date="2025-12-31",
        bond_rows=bond_rows,
        ftp_rate_pct=2.0,
        curve_slope_bp=15.0,
    )
    item = out["items"][0]
    assert item["carry"] == pytest.approx(0.85, rel=0, abs=1e-6)
    assert item["rolldown"] == pytest.approx(0.63, rel=0, abs=1e-6)
    assert item["static_return"] == pytest.approx(1.48, rel=0, abs=1e-6)
    assert out["portfolio_carry"] == pytest.approx(0.85, rel=0, abs=1e-4)
    assert out["portfolio_rolldown"] == pytest.approx(0.63, rel=0, abs=1e-4)
    assert out["portfolio_static_return"] == pytest.approx(1.48, rel=0, abs=1e-4)


def test_build_advanced_attribution_static_annualized_equals_portfolio_static() -> None:
    carry = build_carry_roll_down(
        report_date="2025-12-31",
        bond_rows=[
            {
                "asset_class_std": "利率债",
                "market_value": 500_000_000,
                "coupon_rate": 0.0285,
                "modified_duration": 4.2,
                "ytm": 0.028,
            }
        ],
        ftp_rate_pct=2.0,
        curve_slope_bp=15.0,
    )
    spread = {
        "total_treasury_effect": -1.0,
        "total_spread_effect": 2.0,
        "primary_driver": "spread",
    }
    krd = {"max_contribution_tenor": "5Y", "curve_shift_type": "parallel"}
    summary = build_advanced_attribution_summary(
        report_date="2025-12-31",
        carry_payload=carry,
        spread_payload=spread,
        krd_payload=krd,
    )
    assert summary["static_return_annualized"] == float(carry["portfolio_static_return"])
    assert summary["static_return_annualized"] == pytest.approx(1.48, rel=0, abs=1e-3)
