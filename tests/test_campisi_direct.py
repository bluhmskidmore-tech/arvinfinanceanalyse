from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance import campisi


def _single_position():
    return [
        {
            "bond_code": "240001.IB",
            "market_value_start": 100.0,
            "market_value_end": 101.0,
            "face_value_start": 100.0,
            "coupon_rate_start": 0.05,
            "yield_to_maturity_start": 0.04,
            "asset_class_start": "AAA企业债",
            "maturity_date_start": date(2027, 7, 1),
        }
    ]


def _market_snapshot(treasury_1y: float, treasury_3y: float, aaa_spread_bp: float):
    return {
        "treasury_1y": treasury_1y,
        "treasury_3y": treasury_3y,
        "treasury_5y": treasury_3y + 0.4,
        "treasury_7y": treasury_3y + 0.6,
        "treasury_10y": treasury_3y + 0.8,
        "treasury_30y": treasury_3y + 1.2,
        "credit_spread_aaa_3y": aaa_spread_bp,
    }


def test_interpolate_treasury_yield_pct_scales_decimal_curves_before_interpolation() -> None:
    yield_pct = campisi.interpolate_treasury_yield_pct(
        {"treasury_1y": 0.02, "treasury_3y": 0.03, "treasury_5y": 0.04},
        maturity_years=2.0,
    )

    assert yield_pct == 2.5


def test_credit_spread_change_decimal_converts_bp_and_ignores_government_bonds() -> None:
    start = {"credit_spread_aaa_3y": 50}
    end = {"credit_spread_aaa_3y": 70}

    assert campisi.credit_spread_change_decimal(start, end, "AAA") == Decimal("0.002")
    assert campisi.credit_spread_change_decimal(start, end, "GOV") == Decimal("0")


def test_campisi_attribution_aggregates_by_asset_class_and_bucket() -> None:
    result = campisi.campisi_attribution(
        positions_merged=_single_position(),
        market_start=_market_snapshot(2.0, 2.4, 50),
        market_end=_market_snapshot(2.2, 2.6, 60),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
    )

    assert result.num_days == 31
    assert result.totals["market_value_start"] == 100.0
    assert result.by_bond[0]["maturity_bucket"] == "1-3Y"
    assert result.by_asset_class[0]["asset_class"] == "AAA企业债"
    assert result.by_asset_class[0]["weight_pct"] == 100.0
    assert result.totals["total_return"] == result.by_bond[0]["total_return"]


def test_campisi_enhanced_and_maturity_bucket_rollup_keep_second_order_components() -> None:
    enhanced = campisi.campisi_enhanced(
        positions_merged=_single_position(),
        market_start=_market_snapshot(2.0, 2.4, 50),
        market_end=_market_snapshot(2.2, 2.6, 60),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
    )
    buckets = campisi.maturity_bucket_attribution(
        positions_merged=_single_position(),
        market_start=_market_snapshot(2.0, 2.4, 50),
        market_end=_market_snapshot(2.2, 2.6, 60),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
    )

    assert enhanced["totals"]["convexity_effect"] > 0
    assert enhanced["totals"]["cross_effect"] > 0
    assert enhanced["by_asset_class"][0]["convexity_effect_pct"] != 0
    assert buckets["1-3Y"]["total_return"] == enhanced["totals"]["total_return"]
