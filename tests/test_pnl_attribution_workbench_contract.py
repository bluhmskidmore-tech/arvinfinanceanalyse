from __future__ import annotations

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    build_advanced_attribution_summary,
    build_tpl_market_correlation,
    build_volume_rate_attribution,
)


def test_build_volume_rate_attribution_exposes_yields_as_percent_values() -> None:
    payload = build_volume_rate_attribution(
        current_pnl=[
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "total_pnl": 20.0,
            }
        ],
        prior_pnl=[
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "total_pnl": 15.0,
            }
        ],
        current_bond=[
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "market_value": 1_000.0,
            }
        ],
        prior_bond=[
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "market_value": 750.0,
            }
        ],
        current_period="2026-03",
        previous_period="2026-02",
        compare_type="mom",
    )

    row = payload["items"][0]
    assert row["current_yield_pct"] == pytest.approx(2.0)
    assert row["previous_yield_pct"] == pytest.approx(2.0)
    assert "current_yield" not in row
    assert "previous_yield" not in row


def test_build_tpl_market_correlation_exposes_total_change_in_bp() -> None:
    payload = build_tpl_market_correlation(
        monthly_points=[
            {
                "period": "2026-02",
                "period_label": "2026年2月",
                "tpl_fair_value_change": 1_000_000.0,
                "tpl_total_pnl": 1_000_000.0,
                "tpl_scale": 10_000_000.0,
                "treasury_10y": 2.35,
                "treasury_10y_change": None,
                "dr007": None,
            },
            {
                "period": "2026-03",
                "period_label": "2026年3月",
                "tpl_fair_value_change": 2_000_000.0,
                "tpl_total_pnl": 2_000_000.0,
                "tpl_scale": 10_500_000.0,
                "treasury_10y": 2.20,
                "treasury_10y_change": -15.0,
                "dr007": None,
            },
        ],
        start_period="2026-02",
        end_period="2026-03",
    )

    assert payload["treasury_10y_total_change_bp"] == pytest.approx(-15.0)
    assert "treasury_10y_total_change" not in payload


def test_build_advanced_attribution_summary_keeps_single_annualization() -> None:
    payload = build_advanced_attribution_summary(
        report_date="2026-03-31",
        carry_payload={
            "portfolio_carry": 1.85,
            "portfolio_rolldown": 0.42,
            "portfolio_static_return": 2.27,
        },
        spread_payload={
            "total_treasury_effect": 22_000_000.0,
            "total_spread_effect": -4_000_000.0,
            "primary_driver": "treasury",
        },
        krd_payload={
            "max_contribution_tenor": "5Y",
            "curve_shift_type": "bull_steepener",
        },
    )

    assert payload["static_return_annualized"] == pytest.approx(2.27)
