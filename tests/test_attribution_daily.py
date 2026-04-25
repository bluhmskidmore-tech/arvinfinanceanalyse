"""Unit tests for attribution_daily.py: daily attribution pipeline."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.core_finance.attribution_daily import compute_daily_attribution_row

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PREV_DATE = date(2025, 3, 10)
REPORT_DATE = date(2025, 3, 11)  # 1-day window

MARKET_START = {
    "treasury_1y": 2.40,
    "treasury_3y": 2.60,
    "treasury_5y": 2.80,
    "treasury_7y": 2.95,
    "treasury_10y": 3.10,
    "treasury_30y": 3.50,
    "credit_spread_aaa_3y": 35.0,
    "credit_spread_aa_plus_3y": 60.0,
    "credit_spread_aa_3y": 90.0,
}

MARKET_END = {
    "treasury_1y": 2.38,
    "treasury_3y": 2.58,
    "treasury_5y": 2.78,
    "treasury_7y": 2.93,
    "treasury_10y": 3.08,
    "treasury_30y": 3.48,
    "credit_spread_aaa_3y": 33.0,
    "credit_spread_aa_plus_3y": 58.0,
    "credit_spread_aa_3y": 88.0,
}

POSITION_FVTPL = {
    "bond_code": "240001.IB",
    "asset_class_start": "国债",
    "market_value_start": 10_000_000.0,
    "market_value_end": 10_005_000.0,
    "face_value_start": 10_000_000.0,
    "coupon_rate_start": 0.0255,
    "yield_to_maturity_start": 0.0258,
    "maturity_date_start": date(2029, 3, 11),
    "accrued_interest_start": None,
    "accrued_interest_end": None,
}


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_output_has_all_required_fields():
    """Verify all seven required fields are present in the output."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    required_fields = {
        "carry_return",
        "rolldown_return",
        "spread_return",
        "curve_return",
        "fx_return",
        "total_return",
        "residual_return",
    }
    assert required_fields == set(result.keys())


def test_output_values_are_floats():
    """Verify all output values are Python floats."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    for field, value in result.items():
        assert isinstance(value, float), f"{field} should be float, got {type(value)}"


# ---------------------------------------------------------------------------
# Residual identity: total = carry + rolldown + spread + curve + fx + residual
# ---------------------------------------------------------------------------

def test_residual_closes_to_total():
    """Verify residual = total - carry - rolldown - spread - curve - fx."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    reconstructed = (
        result["carry_return"]
        + result["rolldown_return"]
        + result["spread_return"]
        + result["curve_return"]
        + result["fx_return"]
        + result["residual_return"]
    )
    assert reconstructed == pytest.approx(result["total_return"], abs=1e-6)


def test_residual_closes_to_total_with_fx():
    """Verify residual identity holds when fx_pnl is provided."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5200.0,
        fx_pnl=200.0,
    )

    reconstructed = (
        result["carry_return"]
        + result["rolldown_return"]
        + result["spread_return"]
        + result["curve_return"]
        + result["fx_return"]
        + result["residual_return"]
    )
    assert reconstructed == pytest.approx(result["total_return"], abs=1e-6)
    assert result["fx_return"] == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# Date handling
# ---------------------------------------------------------------------------

def test_report_date_threads_through_num_days():
    """Verify num_days is derived from (report_date - prev_date)."""
    # 1-day window
    result_1d = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        date(2025, 3, 10),
        date(2025, 3, 11),
        total_pnl=5000.0,
    )

    # 5-day window (e.g. over a weekend)
    result_5d = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        date(2025, 3, 7),
        date(2025, 3, 12),
        total_pnl=5000.0,
    )

    # Carry scales with num_days (coupon * face * days / 365)
    assert abs(result_5d["carry_return"]) > abs(result_1d["carry_return"])


def test_same_prev_and_report_date_uses_one_day():
    """Verify same-day window defaults to 1 day (no division by zero)."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        date(2025, 3, 11),
        date(2025, 3, 11),  # same date
        total_pnl=0.0,
    )

    # Should not raise; carry should be positive (1-day coupon accrual)
    assert result["carry_return"] > 0.0


# ---------------------------------------------------------------------------
# total_pnl override
# ---------------------------------------------------------------------------

def test_total_pnl_overrides_model_total():
    """Verify total_return equals total_pnl when provided."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=12345.67,
    )

    assert result["total_return"] == pytest.approx(12345.67)


def test_total_pnl_none_uses_model_total():
    """Verify total_return falls back to model when total_pnl is None."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=None,
    )

    # Model total = mv_end - mv_start + income (no accrued interest)
    expected_total = (
        POSITION_FVTPL["market_value_end"]
        - POSITION_FVTPL["market_value_start"]
        + result["carry_return"]
    )
    assert result["total_return"] == pytest.approx(expected_total, rel=0.01)


# ---------------------------------------------------------------------------
# AC class: rolldown / spread / curve should be zero
# ---------------------------------------------------------------------------

def test_ac_class_effects_are_zero():
    """Verify AC-class bonds have zero rolldown, spread, and curve effects."""
    position_ac = {
        **POSITION_FVTPL,
        "bond_code": "AC-BOND-001",
        "asset_class_start": "AC持有至到期",  # triggers AC accounting class
    }

    result = compute_daily_attribution_row(
        position_ac,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=None,
    )

    assert result["rolldown_return"] == pytest.approx(0.0)
    assert result["spread_return"] == pytest.approx(0.0)
    assert result["curve_return"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Edge cases: missing market data
# ---------------------------------------------------------------------------

def test_missing_market_start_does_not_crash():
    """Verify graceful degradation when market_start is None."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        None,  # no start market data
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    assert isinstance(result, dict)
    assert result["total_return"] == pytest.approx(5000.0)
    # Residual identity still holds
    reconstructed = (
        result["carry_return"]
        + result["rolldown_return"]
        + result["spread_return"]
        + result["curve_return"]
        + result["fx_return"]
        + result["residual_return"]
    )
    assert reconstructed == pytest.approx(result["total_return"], abs=1e-6)


def test_missing_market_end_does_not_crash():
    """Verify graceful degradation when market_end is None."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        None,  # no end market data
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    assert isinstance(result, dict)
    assert result["total_return"] == pytest.approx(5000.0)
    # rolldown requires market_end; should be 0 when missing
    assert result["rolldown_return"] == pytest.approx(0.0)


def test_both_market_dicts_none_does_not_crash():
    """Verify graceful degradation when both market dicts are None."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        None,
        None,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=0.0,
    )

    assert isinstance(result, dict)
    assert set(result.keys()) == {
        "carry_return", "rolldown_return", "spread_return",
        "curve_return", "fx_return", "total_return", "residual_return",
    }


def test_missing_maturity_date_does_not_crash():
    """Verify graceful degradation when maturity_date_start is None."""
    position_no_mat = {**POSITION_FVTPL, "maturity_date_start": None}

    result = compute_daily_attribution_row(
        position_no_mat,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    assert isinstance(result, dict)
    assert result["total_return"] == pytest.approx(5000.0)


def test_zero_market_value_does_not_crash():
    """Verify zero market value position does not raise."""
    position_zero = {
        **POSITION_FVTPL,
        "market_value_start": 0.0,
        "market_value_end": 0.0,
        "face_value_start": 0.0,
    }

    result = compute_daily_attribution_row(
        position_zero,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=0.0,
    )

    assert isinstance(result, dict)
    assert result["carry_return"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Multiple positions: aggregation
# ---------------------------------------------------------------------------

def test_multiple_positions_aggregation():
    """Verify summing two positions gives correct aggregate attribution."""
    position_a = {
        "bond_code": "BOND-A",
        "asset_class_start": "国债",
        "market_value_start": 5_000_000.0,
        "market_value_end": 5_002_000.0,
        "face_value_start": 5_000_000.0,
        "coupon_rate_start": 0.0250,
        "yield_to_maturity_start": 0.0252,
        "maturity_date_start": date(2028, 6, 15),
        "accrued_interest_start": None,
        "accrued_interest_end": None,
    }
    position_b = {
        "bond_code": "BOND-B",
        "asset_class_start": "政策性金融债",
        "market_value_start": 8_000_000.0,
        "market_value_end": 8_003_000.0,
        "face_value_start": 8_000_000.0,
        "coupon_rate_start": 0.0270,
        "yield_to_maturity_start": 0.0275,
        "maturity_date_start": date(2030, 9, 20),
        "accrued_interest_start": None,
        "accrued_interest_end": None,
    }

    result_a = compute_daily_attribution_row(
        position_a, MARKET_START, MARKET_END, PREV_DATE, REPORT_DATE, total_pnl=2000.0
    )
    result_b = compute_daily_attribution_row(
        position_b, MARKET_START, MARKET_END, PREV_DATE, REPORT_DATE, total_pnl=3000.0
    )

    # Aggregate by summing each effect
    aggregate = {
        k: result_a[k] + result_b[k]
        for k in result_a
    }

    # Residual identity must hold for the aggregate too
    reconstructed = (
        aggregate["carry_return"]
        + aggregate["rolldown_return"]
        + aggregate["spread_return"]
        + aggregate["curve_return"]
        + aggregate["fx_return"]
        + aggregate["residual_return"]
    )
    assert reconstructed == pytest.approx(aggregate["total_return"], abs=1e-6)
    assert aggregate["total_return"] == pytest.approx(5000.0)


def test_multiple_positions_carry_scales_with_face_value():
    """Verify carry is proportional to face value across positions."""
    position_small = {
        **POSITION_FVTPL,
        "bond_code": "SMALL",
        "market_value_start": 1_000_000.0,
        "market_value_end": 1_000_500.0,
        "face_value_start": 1_000_000.0,
    }
    position_large = {
        **POSITION_FVTPL,
        "bond_code": "LARGE",
        "market_value_start": 10_000_000.0,
        "market_value_end": 10_005_000.0,
        "face_value_start": 10_000_000.0,
    }

    result_small = compute_daily_attribution_row(
        position_small, MARKET_START, MARKET_END, PREV_DATE, REPORT_DATE, total_pnl=500.0
    )
    result_large = compute_daily_attribution_row(
        position_large, MARKET_START, MARKET_END, PREV_DATE, REPORT_DATE, total_pnl=5000.0
    )

    # Carry should be 10x larger for the 10x larger position
    assert result_large["carry_return"] == pytest.approx(
        result_small["carry_return"] * 10.0, rel=1e-6
    )


# ---------------------------------------------------------------------------
# fx_return passthrough
# ---------------------------------------------------------------------------

def test_fx_return_is_zero_when_not_provided():
    """Verify fx_return defaults to 0 when fx_pnl is not passed."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
    )

    assert result["fx_return"] == pytest.approx(0.0)


def test_fx_return_passthrough():
    """Verify fx_return equals fx_pnl when provided."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5500.0,
        fx_pnl=500.0,
    )

    assert result["fx_return"] == pytest.approx(500.0)


def test_fx_return_zero_explicit():
    """Verify fx_return is 0 when fx_pnl=0 is explicitly passed."""
    result = compute_daily_attribution_row(
        POSITION_FVTPL,
        MARKET_START,
        MARKET_END,
        PREV_DATE,
        REPORT_DATE,
        total_pnl=5000.0,
        fx_pnl=0.0,
    )

    assert result["fx_return"] == pytest.approx(0.0)
