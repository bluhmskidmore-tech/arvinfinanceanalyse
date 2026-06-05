from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_four_effects import (
    compute_bond_four_effects,
    compute_bond_six_effects,
)
from backend.app.core_finance.campisi import (
    campisi_attribution,
    credit_spread_change_decimal,
    maturity_bucket_attribution,
)


START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 1, 31)
ONE_YEAR_MATURITY = date(2027, 1, 1)


def _zero_coupon_bond(**overrides: object) -> dict[str, object]:
    return {
        "bond_code": "GOV_GOLDEN",
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


def test_government_four_effect_golden_sample_closes_on_full_price_basis() -> None:
    bond = _zero_coupon_bond()
    benchmark_delta = Decimal("0.01")
    modified_duration = Decimal("1") / (Decimal("1") + Decimal("0.05") / Decimal("2"))

    result = compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=benchmark_delta,
        spread_change=Decimal("0"),
        report_date=START_DATE,
    )

    assert result["income_return"] == pytest.approx(Decimal("0"))
    assert result["treasury_effect"] == pytest.approx(
        -modified_duration * benchmark_delta * Decimal("1000")
    )
    assert result["spread_effect"] == pytest.approx(Decimal("0"))
    assert result["total_return"] == pytest.approx(Decimal("-10"))
    assert result["selection_effect"] == pytest.approx(
        result["total_return"]
        - result["income_return"]
        - result["treasury_effect"]
        - result["spread_effect"]
    )
    assert result["has_accrued_interest"] is True
    assert result["diagnostics"] == []


def test_credit_spread_effect_uses_basis_points_as_decimal_delta() -> None:
    bond = _zero_coupon_bond(
        bond_code="CREDIT_GOLDEN",
        asset_class_start="AAA 信用债",
        market_value_end=995.0,
    )
    spread_delta = credit_spread_change_decimal(
        {"credit_spread_aaa_3y": 50.0},
        {"credit_spread_aaa_3y": 100.0},
        "AAA",
    )
    modified_duration = Decimal("1") / (Decimal("1") + Decimal("0.05") / Decimal("2"))

    result = compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0"),
        spread_change=spread_delta,
        report_date=START_DATE,
    )

    assert spread_delta == Decimal("0.005")
    assert result["spread_effect"] == pytest.approx(
        -modified_duration * Decimal("0.005") * Decimal("1000")
    )
    assert result["total_return"] == pytest.approx(Decimal("-5"))
    assert result["selection_effect"] == pytest.approx(
        result["total_return"]
        - result["income_return"]
        - result["treasury_effect"]
        - result["spread_effect"]
    )


def test_ac_bond_only_contributes_income_even_when_market_moves() -> None:
    bond = _zero_coupon_bond(
        asset_class_start="AC",
        coupon_rate_start=0.05,
        market_value_end=1_200.0,
        accrued_interest_end=50.0,
    )

    result = compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0.02"),
        spread_change=Decimal("0.005"),
        report_date=START_DATE,
    )

    expected_income = Decimal("0.05") * Decimal("1000") * Decimal("30") / Decimal("365")
    assert result["income_return"] == pytest.approx(expected_income)
    assert result["treasury_effect"] == pytest.approx(Decimal("0"))
    assert result["spread_effect"] == pytest.approx(Decimal("0"))
    assert result["selection_effect"] == pytest.approx(Decimal("0"))
    assert result["total_return"] == pytest.approx(expected_income)


def test_missing_accrued_interest_falls_back_to_clean_price_plus_income() -> None:
    bond = _zero_coupon_bond(
        bond_code="MISSING_AI_GOLDEN",
        coupon_rate_start=0.05,
        market_value_end=1_005.0,
        accrued_interest_start=None,
        accrued_interest_end=None,
    )

    result = compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0"),
        spread_change=Decimal("0"),
        report_date=START_DATE,
    )

    expected_income = Decimal("0.05") * Decimal("1000") * Decimal("30") / Decimal("365")
    assert result["total_price_change"] == pytest.approx(Decimal("5"))
    assert result["total_return"] == pytest.approx(Decimal("5") + expected_income)
    assert result["has_accrued_interest"] is False
    assert "accrued_interest_missing" in result["diagnostics"]


def test_six_effect_and_maturity_bucket_totals_close_to_four_effect_totals() -> None:
    positions = [
        _zero_coupon_bond(bond_code="GOV_GOLDEN", market_value_end=990.0),
        _zero_coupon_bond(
            bond_code="CREDIT_GOLDEN",
            asset_class_start="AAA 信用债",
            market_value_end=995.0,
        ),
    ]
    market_start = {
        "treasury_1y": 2.0,
        "treasury_3y": 2.0,
        "treasury_5y": 2.0,
        "treasury_7y": 2.0,
        "treasury_10y": 2.0,
        "treasury_30y": 2.0,
        "credit_spread_aaa_3y": 50.0,
    }
    market_end = {
        "treasury_1y": 3.0,
        "treasury_3y": 3.0,
        "treasury_5y": 3.0,
        "treasury_7y": 3.0,
        "treasury_10y": 3.0,
        "treasury_30y": 3.0,
        "credit_spread_aaa_3y": 100.0,
    }

    four = campisi_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    enhanced_rows = [
        compute_bond_six_effects(
            position,
            num_days=30,
            benchmark_yield_change=Decimal("0.01"),
            spread_change=Decimal("0")
            if position["asset_class_start"] == "国债"
            else Decimal("0.005"),
            report_date=START_DATE,
        )
        for position in positions
    ]
    buckets = maturity_bucket_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    four_components = (
        four.totals["income_return"]
        + four.totals["treasury_effect"]
        + four.totals["spread_effect"]
        + four.totals["selection_effect"]
    )
    enhanced_total = sum(float(row["total_return"]) for row in enhanced_rows)
    enhanced_components = sum(
        float(row["income_return"])
        + float(row["treasury_effect"])
        + float(row["spread_effect"])
        + float(row["convexity_effect"])
        + float(row["cross_effect"])
        + float(row["reinvestment_effect"])
        + float(row["selection_effect"])
        for row in enhanced_rows
    )

    assert four_components == pytest.approx(four.totals["total_return"])
    assert enhanced_components == pytest.approx(enhanced_total)
    assert sum(bucket["total_return"] for bucket in buckets.values()) == pytest.approx(
        four.totals["total_return"]
    )
    assert sum(bucket["income_return"] for bucket in buckets.values()) == pytest.approx(
        four.totals["income_return"]
    )
    assert sum(bucket["treasury_effect"] for bucket in buckets.values()) == pytest.approx(
        four.totals["treasury_effect"]
    )
    assert sum(bucket["spread_effect"] for bucket in buckets.values()) == pytest.approx(
        four.totals["spread_effect"]
    )
    assert sum(bucket["selection_effect"] for bucket in buckets.values()) == pytest.approx(
        four.totals["selection_effect"]
    )
