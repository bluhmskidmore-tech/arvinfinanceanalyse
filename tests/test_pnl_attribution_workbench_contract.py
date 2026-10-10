from __future__ import annotations

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    _risk_exclusion_reason,
    build_advanced_attribution_summary,
    build_carry_roll_down,
    build_krd_attribution,
    build_pnl_composition,
    build_spread_attribution,
    build_tpl_market_correlation,
    build_volume_rate_attribution,
    build_volume_rate_attribution_from_grouped_rows,
)


def test_zero_market_value_matured_history_is_not_a_risk_exclusion() -> None:
    row = {
        "market_value": 0,
        "maturity_date": "2026-06-10",
        "years_to_maturity": 0,
        "modified_duration": 0,
    }

    assert _risk_exclusion_reason(row, report_date="2026-06-30") is None


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


def test_build_volume_rate_attribution_matches_scale_by_cost_center() -> None:
    payload = build_volume_rate_attribution(
        current_pnl=[
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "total_pnl": 10.0,
            },
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C2",
                "total_pnl": 30.0,
            },
        ],
        prior_pnl=[
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "total_pnl": 8.0,
            },
            {
                "invest_type_std": "A",
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C2",
                "total_pnl": 24.0,
            },
        ],
        current_bond=[
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "market_value": 100.0,
            },
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C2",
                "market_value": 300.0,
            },
        ],
        prior_bond=[
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "market_value": 80.0,
            },
            {
                "instrument_code": "B1",
                "portfolio_name": "P1",
                "cost_center": "C2",
                "market_value": 240.0,
            },
        ],
        current_period="2026-04",
        previous_period="2026-03",
        compare_type="mom",
    )

    row = payload["items"][0]
    assert row["current_scale"] == pytest.approx(400.0)
    assert row["previous_scale"] == pytest.approx(320.0)
    assert row["current_yield_pct"] == pytest.approx(10.0)
    assert row["previous_yield_pct"] == pytest.approx(10.0)


def test_build_volume_rate_attribution_from_grouped_rows_uses_aligned_business_scale() -> None:
    payload = build_volume_rate_attribution_from_grouped_rows(
        current_rows=[
            {
                "business_type_primary": "interbank_cd",
                "total_pnl": 120.0,
                "scale_amount": 1_000.0,
            }
        ],
        prior_rows=[
            {
                "business_type_primary": "interbank_cd",
                "total_pnl": 80.0,
                "scale_amount": 800.0,
            }
        ],
        current_period="2026-04",
        previous_period="2026-03",
        compare_type="mom",
    )

    row = payload["items"][0]
    assert row["category"] == "interbank_cd"
    assert row["current_yield_pct"] == pytest.approx(12.0)
    assert row["previous_yield_pct"] == pytest.approx(10.0)
    assert row["volume_effect"] == pytest.approx(20.0)
    assert row["rate_effect"] == pytest.approx(16.0)
    assert row["interaction_effect"] == pytest.approx(4.0)
    assert row["recon_error"] == pytest.approx(0.0)


def test_volume_rate_attribution_closes_exactly_at_float_output_boundary() -> None:
    payload = build_volume_rate_attribution_from_grouped_rows(
        current_rows=[
            {
                "business_type_primary": "rate",
                "total_pnl": 0.1,
                "scale_amount": 0.1,
            }
        ],
        prior_rows=[
            {
                "business_type_primary": "rate",
                "total_pnl": 0.3,
                "scale_amount": 0.1,
            }
        ],
        current_period="2026-04",
        previous_period="2026-03",
        compare_type="mom",
    )

    row = payload["items"][0]
    assert row["volume_effect"] + row["rate_effect"] + row["interaction_effect"] == row["pnl_change"]
    assert row["recon_error"] == 0.0
    assert (
        payload["total_volume_effect"]
        + payload["total_rate_effect"]
        + payload["total_interaction_effect"]
        == payload["total_pnl_change"]
    )
    assert payload["total_recon_error"] == 0.0


def test_build_volume_rate_attribution_exposes_total_reconciliation_gap() -> None:
    payload = build_volume_rate_attribution_from_grouped_rows(
        current_rows=[
            {
                "business_type_primary": "existing",
                "total_pnl": 120.0,
                "scale_amount": 1_000.0,
            },
            {
                "business_type_primary": "new",
                "total_pnl": 25.0,
                "scale_amount": 500.0,
            },
        ],
        prior_rows=[
            {
                "business_type_primary": "existing",
                "total_pnl": 80.0,
                "scale_amount": 800.0,
            }
        ],
        current_period="2026-04",
        previous_period="2026-03",
        compare_type="mom",
    )

    assert payload["total_pnl_change"] == pytest.approx(65.0)
    assert (
        payload["total_volume_effect"]
        + payload["total_rate_effect"]
        + payload["total_interaction_effect"]
    ) == pytest.approx(40.0)
    assert payload["total_recon_error"] == pytest.approx(25.0)


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

    assert payload["treasury_10y_total_change_bp"] is None
    assert "treasury_10y_total_change" not in payload


def test_build_tpl_market_correlation_excludes_non_finite_pairs_and_nulls_contaminated_total() -> None:
    payload = build_tpl_market_correlation(
        monthly_points=[
            {
                "period": "2026-01",
                "period_label": "2026年1月",
                "tpl_fair_value_change": 1.0,
                "treasury_10y_change": 1.0,
            },
            {
                "period": "2026-02",
                "period_label": "2026年2月",
                "tpl_fair_value_change": float("nan"),
                "treasury_10y_change": 2.0,
            },
            {
                "period": "2026-03",
                "period_label": "2026年3月",
                "tpl_fair_value_change": 3.0,
                "treasury_10y_change": 3.0,
            },
        ],
        start_period="2026-01",
        end_period="2026-03",
    )

    assert payload["correlation_coefficient"] == pytest.approx(1.0)
    assert payload["total_tpl_fv_change"] is None


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


def test_build_pnl_composition_exposes_unexplained_residual_at_top_and_item_level() -> None:
    payload = build_pnl_composition(
        report_period="2026-03",
        report_date="2026-03-31",
        pnl_rows=[
            {
                "invest_type_std": "利率债",
                "interest_income_514": 100.0,
                "fair_value_change_516": 50.0,
                "capital_gain_517": 20.0,
                "manual_adjustment": 10.0,
                "total_pnl": 200.0,
            },
            {
                "invest_type_std": "信用债",
                "interest_income_514": 30.0,
                "fair_value_change_516": 10.0,
                "capital_gain_517": 5.0,
                "manual_adjustment": 0.0,
                "total_pnl": 60.0,
            },
        ],
        trend_rows=[],
    )

    assert payload["total_pnl"] == pytest.approx(260.0)
    assert payload["total_interest_income"] == pytest.approx(130.0)
    assert payload["total_fair_value_change"] == pytest.approx(60.0)
    assert payload["total_capital_gain"] == pytest.approx(25.0)
    assert payload["total_other_income"] == pytest.approx(10.0)
    assert payload["unexplained_residual"] == pytest.approx(35.0)

    by_cat = {item["category"]: item for item in payload["items"]}
    assert by_cat["利率债"]["unexplained_residual"] == pytest.approx(20.0)
    assert by_cat["信用债"]["unexplained_residual"] == pytest.approx(15.0)


def _krd_bond_row(*, market_value: float, modified_duration: float) -> dict[str, float | str]:
    return {
        "tenor_bucket": "5Y",
        "market_value": market_value,
        "modified_duration": modified_duration,
        "macaulay_duration": modified_duration,
        "convexity": 0.0,
        "years_to_maturity": 5.0,
        "ytm": 0.03,
        "dv01": market_value * modified_duration / 10000.0,
    }


@pytest.mark.parametrize("shift", [None, 0.0])
def test_krd_missing_curve_is_unknown_while_observed_flat_curve_is_zero(shift) -> None:
    row = _krd_bond_row(market_value=1000, modified_duration=5)
    payload = build_krd_attribution(
        report_date="2026-01-31", start_date="2026-01-01", end_date="2026-01-31",
        bond_rows_end=[row], bond_rows_start=[row], treasury_shift_bp=shift,
    )
    expected = None if shift is None else 0
    assert payload["total_duration_effect"] == expected
    assert payload["buckets"][0]["duration_contribution"] == expected
    assert payload["buckets"][0]["contribution_pct"] == expected
    assert payload["max_contribution_tenor"] == ""
    assert payload["max_contribution_value"] == expected
    assert payload["calculation_status"] == ("unavailable" if shift is None else "complete")
    assert payload["curve_shift_type"] == ("unavailable" if shift is None else "parallel")


def test_build_krd_attribution_keeps_parallel_when_only_aggregate_rates_rise_and_long_duration() -> None:
    payload = build_krd_attribution(
        report_date="2026-03-31",
        start_date="2026-02-28",
        end_date="2026-03-31",
        bond_rows_end=[_krd_bond_row(market_value=1_000_000.0, modified_duration=5.0)],
        bond_rows_start=[_krd_bond_row(market_value=1_000_000.0, modified_duration=5.0)],
        treasury_shift_bp=10.0,
    )

    assert payload["portfolio_duration"] == pytest.approx(5.0)
    assert payload["curve_shift_type"] == "parallel"


def test_build_krd_attribution_keeps_parallel_when_only_aggregate_rates_rise_and_short_duration() -> None:
    payload = build_krd_attribution(
        report_date="2026-03-31",
        start_date="2026-02-28",
        end_date="2026-03-31",
        bond_rows_end=[_krd_bond_row(market_value=1_000_000.0, modified_duration=3.0)],
        bond_rows_start=[_krd_bond_row(market_value=1_000_000.0, modified_duration=3.0)],
        treasury_shift_bp=8.0,
    )

    assert payload["curve_shift_type"] == "parallel"


def test_build_krd_attribution_keeps_parallel_for_aggregate_rate_shift_regression() -> None:
    bull = build_krd_attribution(
        report_date="2026-03-31",
        start_date="2026-02-28",
        end_date="2026-03-31",
        bond_rows_end=[_krd_bond_row(market_value=1_000_000.0, modified_duration=5.0)],
        bond_rows_start=[_krd_bond_row(market_value=1_000_000.0, modified_duration=5.0)],
        treasury_shift_bp=-10.0,
    )
    parallel = build_krd_attribution(
        report_date="2026-03-31",
        start_date="2026-02-28",
        end_date="2026-03-31",
        bond_rows_end=[_krd_bond_row(market_value=1_000_000.0, modified_duration=5.0)],
        bond_rows_start=[_krd_bond_row(market_value=1_000_000.0, modified_duration=3.0)],
        treasury_shift_bp=3.0,
    )

    assert bull["curve_shift_type"] == "parallel"
    assert parallel["curve_shift_type"] == "parallel"


def test_spread_weighted_ytm_excludes_missing_values_from_denominator() -> None:
    def row(*, market_value: float, ytm: float | None) -> dict[str, object]:
        return {
            "instrument_code": "MISSING" if ytm is None else "OBSERVED",
            "accounting_class": "FVOCI",
            "currency_code": "CNY",
            "asset_class_std": "rate",
            "tenor_bucket": "5Y",
            "market_value": market_value,
            "modified_duration": 2.0,
            "macaulay_duration": 2.1,
            "convexity": 0.0,
            "years_to_maturity": 5.0,
            "ytm": ytm,
            "dv01": market_value * 2.0 / 10_000.0,
        }

    payload = build_spread_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[
            row(market_value=100.0, ytm=0.030),
            row(market_value=900.0, ytm=None),
        ],
        bond_rows_end=[
            row(market_value=100.0, ytm=0.031),
            row(market_value=900.0, ytm=None),
        ],
        treasury_10y_start_pct=2.0,
        treasury_10y_end_pct=2.0,
        treasury_curve_start={"5Y": 2.0},
        treasury_curve_end={"5Y": 2.0},
    )

    assert payload["items"][0]["yield_change"] == pytest.approx(10.0)
    assert payload["items"][0]["spread_change"] == pytest.approx(10.0)
    assert payload["total_spread_effect"] == pytest.approx(-0.2)


def test_spread_all_missing_ytm_stays_unavailable_instead_of_zero() -> None:
    row = {
        "instrument_code": "MISSING-YTM",
        "accounting_class": "FVOCI",
        "currency_code": "CNY",
        "asset_class_std": "other",
        "tenor_bucket": "5Y",
        "market_value": 1_000.0,
        "modified_duration": 2.0,
        "macaulay_duration": 2.1,
        "convexity": 0.0,
        "years_to_maturity": 5.0,
        "ytm": None,
        "dv01": 0.2,
    }

    payload = build_spread_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[row],
        bond_rows_end=[row],
        treasury_10y_start_pct=2.0,
        treasury_10y_end_pct=2.0,
        treasury_curve_start={"5Y": 2.0},
        treasury_curve_end={"5Y": 2.0},
    )

    assert payload["items"][0]["yield_change"] is None
    assert payload["items"][0]["spread_change"] is None


def _carry_row(
    *,
    market_value: float,
    coupon_rate: float | None,
    modified_duration: float | None,
) -> dict[str, object]:
    return {
        "asset_class_std": "rate",
        "market_value": market_value,
        "coupon_rate": coupon_rate,
        "modified_duration": modified_duration,
        "ytm": 0.030,
        "years_to_maturity": 5.0,
    }


@pytest.mark.parametrize("missing_field", ["coupon_rate", "modified_duration", "years_to_maturity"])
def test_carry_missing_input_blocks_full_group_rate_and_amount(missing_field) -> None:
    observed = _carry_row(market_value=100_000_000, coupon_rate=0.03, modified_duration=2.0)
    missing = {**observed, "market_value": 900_000_000, missing_field: None}
    payload = build_carry_roll_down(
        report_date="2026-06-30", bond_rows=[observed, missing], ftp_rate_pct=0,
        curve_slope_bp=None, treasury_curve={"1Y": 1, "10Y": 2},
    )
    item = payload["items"][0]
    field = "carry" if missing_field == "coupon_rate" else "rolldown"
    assert item[field] is None
    assert item[f"{field}_pnl"] is None
    assert payload[f"portfolio_{field}"] is None
    assert payload[f"total_{field}_pnl"] is None
    assert payload["portfolio_static_return"] is None
    assert payload["total_static_pnl"] is None
    if missing_field == "coupon_rate":
        assert item["coupon_rate"] is None
        assert item["rolldown"] is not None
    else:
        assert item["carry_pnl"] == 2_500_000
        if missing_field == "modified_duration":
            assert item["duration"] is None
            assert item["curve_slope"] is not None
        else:
            assert item["curve_slope"] is None


@pytest.mark.parametrize("missing_field", ["coupon_rate", "modified_duration", "years_to_maturity"])
def test_carry_incomplete_group_blocks_portfolio_without_hiding_complete_group(missing_field) -> None:
    complete = _carry_row(market_value=100_000_000, coupon_rate=0.03, modified_duration=2.0)
    incomplete = {**complete, "asset_class_std": "credit", missing_field: None}
    payload = build_carry_roll_down(
        report_date="2026-06-30", bond_rows=[complete, incomplete], ftp_rate_pct=0,
        curve_slope_bp=None, treasury_curve={"1Y": 1, "10Y": 2},
    )
    rows = {item["category"]: item for item in payload["items"]}
    assert rows["rate"]["carry_pnl"] == 250_000
    assert rows["rate"]["rolldown_pnl"] is not None
    field = "carry" if missing_field == "coupon_rate" else "rolldown"
    assert payload[f"portfolio_{field}"] is None
    assert payload[f"total_{field}_pnl"] is None
    assert payload["portfolio_static_return"] is None
    assert payload["total_static_pnl"] is None


def test_carry_missing_curve_is_unknown_but_explicit_flat_curve_is_zero() -> None:
    row = _carry_row(market_value=100_000_000, coupon_rate=0.0, modified_duration=0.0)
    unknown = build_carry_roll_down(
        report_date="2026-06-30", bond_rows=[row], ftp_rate_pct=0, curve_slope_bp=None,
    )
    flat = build_carry_roll_down(
        report_date="2026-06-30", bond_rows=[row], ftp_rate_pct=0, curve_slope_bp=0.0,
    )
    assert unknown["portfolio_carry"] == 0
    assert unknown["total_carry_pnl"] == 0
    assert unknown["portfolio_rolldown"] is None
    assert unknown["items"][0]["curve_slope"] is None
    assert flat["portfolio_rolldown"] == 0
    assert flat["total_static_pnl"] == 0


def test_carry_all_missing_inputs_stay_unknown() -> None:
    payload = build_carry_roll_down(
        report_date="2026-06-30",
        bond_rows=[_carry_row(market_value=100_000_000, coupon_rate=None, modified_duration=None)],
        ftp_rate_pct=1, curve_slope_bp=15,
    )
    for field in ("coupon_rate", "duration", "carry", "carry_pnl", "rolldown", "rolldown_pnl", "static_return", "static_pnl"):
        assert payload["items"][0][field] is None
    assert payload["items"][0]["curve_slope"] == 15


def test_carry_rolldown_keeps_explicit_zero_duration_in_denominator() -> None:
    payload = build_carry_roll_down(
        report_date="2026-06-30",
        bond_rows=[
            _carry_row(market_value=100.0, coupon_rate=0.03, modified_duration=2.0),
            _carry_row(market_value=100.0, coupon_rate=0.03, modified_duration=0.0),
        ], ftp_rate_pct=0, curve_slope_bp=15,
    )
    assert payload["items"][0]["rolldown"] == pytest.approx(0.15)


def test_advanced_summary_preserves_unknown_and_real_zero() -> None:
    payload = build_advanced_attribution_summary(
        report_date="2026-06-30", carry_payload={
            "portfolio_carry": None, "portfolio_rolldown": 0.0, "portfolio_static_return": None,
        }, spread_payload={}, krd_payload={},
    )
    assert payload["portfolio_carry"] is None
    assert payload["portfolio_rolldown"] == 0
    assert payload["static_return_annualized"] is None


def test_krd_rebuckets_legacy_start_rows_with_current_tenor_policy() -> None:
    common = {
        "market_value": 1_000_000.0,
        "modified_duration": 12.0,
        "macaulay_duration": 12.2,
        "convexity": 0.0,
        "dv01": 1_200.0,
    }
    payload = build_krd_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[
            {**common, "tenor_bucket": "15Y", "years_to_maturity": 15.0, "ytm": 0.030},
        ],
        bond_rows_end=[
            {**common, "tenor_bucket": "20Y", "years_to_maturity": 14.9, "ytm": 0.031},
        ],
        treasury_shift_bp=2.4,
    )

    assert [bucket["tenor"] for bucket in payload["buckets"]] == ["20Y"]
    assert payload["buckets"][0]["yield_change"] == pytest.approx(10.0)
    assert "10Y" in payload["curve_interpretation"]
    assert "不参与贡献计算" in payload["curve_interpretation"]


def test_krd_serializes_month_bucket_tenor_years() -> None:
    row = {
        "asset_class_std": "rate",
        "tenor_bucket": "6M",
        "market_value": 1_000_000.0,
        "modified_duration": 0.25,
        "macaulay_duration": 0.26,
        "convexity": 0.0,
        "maturity_date": "2026-12-30",
        "years_to_maturity": 0.5,
        "ytm": 0.02,
        "dv01": 25.0,
    }
    payload = build_krd_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[row],
        bond_rows_end=[row],
        treasury_shift_bp=2.4,
    )

    assert payload["buckets"][0]["tenor"] == "6M"
    assert payload["buckets"][0]["tenor_years"] == pytest.approx(0.5)


def _maturity_risk_row(
    *,
    asset_class: str,
    market_value: float,
    modified_duration: float,
    maturity_date: str | None,
    years_to_maturity: float,
    ytm: float | None,
) -> dict[str, object]:
    return {
        "instrument_code": f"{asset_class}-{maturity_date}",
        "accounting_class": "FVOCI",
        "currency_code": "CNY",
        "asset_class_std": asset_class,
        "tenor_bucket": "5Y" if years_to_maturity > 0 else "6M",
        "market_value": market_value,
        "modified_duration": modified_duration,
        "macaulay_duration": modified_duration,
        "convexity": 0.0,
        "maturity_date": maturity_date,
        "years_to_maturity": years_to_maturity,
        "ytm": ytm,
        "dv01": market_value * modified_duration / 10_000.0,
    }


def _assert_partial_maturity_risk_coverage(payload: dict[str, object]) -> None:
    coverage = payload["risk_coverage"]
    assert isinstance(coverage, dict)
    assert coverage["total_row_count"] == 3
    assert coverage["covered_row_count"] == 1
    assert coverage["excluded_row_count"] == 2
    assert coverage["total_market_value"] == pytest.approx(1_000.0)
    assert coverage["covered_market_value"] == pytest.approx(600.0)
    assert coverage["excluded_market_value"] == pytest.approx(400.0)
    assert coverage["covered_market_value"] + coverage["excluded_market_value"] == pytest.approx(
        coverage["total_market_value"]
    )
    assert coverage["coverage_pct"] == pytest.approx(60.0)
    assert coverage["excluded_pct"] == pytest.approx(40.0)

    exclusions = {item["reason"]: item for item in coverage["exclusions"]}
    assert exclusions["no_maturity"]["row_count"] == 1
    assert exclusions["no_maturity"]["market_value"] == pytest.approx(300.0)
    assert exclusions["matured_or_expired"]["row_count"] == 1
    assert exclusions["matured_or_expired"]["market_value"] == pytest.approx(100.0)


def test_krd_excludes_missing_and_matured_rows_and_reports_risk_coverage() -> None:
    valid_start = _maturity_risk_row(
        asset_class="rate",
        market_value=600.0,
        modified_duration=2.0,
        maturity_date="2031-06-30",
        years_to_maturity=5.0,
        ytm=0.030,
    )
    valid_end = {**valid_start, "ytm": 0.031}
    missing = _maturity_risk_row(
        asset_class="other",
        market_value=300.0,
        modified_duration=4.0,
        maturity_date=None,
        years_to_maturity=5.0,
        ytm=0.040,
    )
    matured = _maturity_risk_row(
        asset_class="other",
        market_value=100.0,
        modified_duration=0.0,
        maturity_date="2026-05-15",
        years_to_maturity=0.0,
        ytm=None,
    )

    covered_only = build_krd_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start],
        bond_rows_end=[valid_end],
        treasury_shift_bp=10.0,
    )
    mixed = build_krd_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start, missing, matured],
        bond_rows_end=[valid_end, missing, matured],
        treasury_shift_bp=10.0,
    )

    assert mixed["total_market_value"] == pytest.approx(1_000.0)
    assert [bucket["tenor"] for bucket in mixed["buckets"]] == ["5Y"]
    assert mixed["buckets"][0]["market_value"] == pytest.approx(600.0)
    assert mixed["buckets"][0]["weight"] == pytest.approx(60.0)
    assert mixed["buckets"][0]["bond_count"] == 1
    assert mixed["portfolio_duration"] == pytest.approx(covered_only["portfolio_duration"])
    assert mixed["portfolio_dv01"] == pytest.approx(covered_only["portfolio_dv01"])
    assert mixed["total_duration_effect"] == pytest.approx(
        covered_only["total_duration_effect"]
    )
    assert mixed["total_duration_effect"] == pytest.approx(-1.2)
    _assert_partial_maturity_risk_coverage(mixed)


def test_spread_excludes_missing_and_matured_rows_and_reports_risk_coverage() -> None:
    valid_start = _maturity_risk_row(
        asset_class="rate",
        market_value=600.0,
        modified_duration=2.0,
        maturity_date="2031-06-30",
        years_to_maturity=5.0,
        ytm=0.030,
    )
    valid_end = {**valid_start, "ytm": 0.031}
    missing = _maturity_risk_row(
        asset_class="other",
        market_value=300.0,
        modified_duration=4.0,
        maturity_date=None,
        years_to_maturity=5.0,
        ytm=0.040,
    )
    matured = _maturity_risk_row(
        asset_class="other",
        market_value=100.0,
        modified_duration=0.0,
        maturity_date="2026-05-15",
        years_to_maturity=0.0,
        ytm=None,
    )

    covered_only = build_spread_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start],
        bond_rows_end=[valid_end],
        treasury_10y_start_pct=2.00,
        treasury_10y_end_pct=2.05,
        treasury_curve_start={"5Y": 2.00},
        treasury_curve_end={"5Y": 2.05},
    )
    mixed = build_spread_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start, missing, matured],
        bond_rows_end=[valid_end, missing, matured],
        treasury_10y_start_pct=2.00,
        treasury_10y_end_pct=2.05,
        treasury_curve_start={"5Y": 2.00},
        treasury_curve_end={"5Y": 2.05},
    )

    assert mixed["total_market_value"] == pytest.approx(1_000.0)
    assert [item["category"] for item in mixed["items"]] == ["rate"]
    assert mixed["items"][0]["market_value"] == pytest.approx(600.0)
    assert mixed["items"][0]["weight"] == pytest.approx(60.0)
    assert mixed["portfolio_duration"] == pytest.approx(covered_only["portfolio_duration"])
    assert mixed["total_treasury_effect"] == pytest.approx(
        covered_only["total_treasury_effect"]
    )
    assert mixed["total_spread_effect"] == pytest.approx(covered_only["total_spread_effect"])
    assert mixed["total_price_change"] == pytest.approx(covered_only["total_price_change"])
    assert mixed["total_treasury_effect"] == pytest.approx(-0.6)
    assert mixed["total_spread_effect"] == pytest.approx(-0.6)
    _assert_partial_maturity_risk_coverage(mixed)

def test_duration_risk_excludes_nonpositive_duration_end_to_end() -> None:
    valid_start = _maturity_risk_row(
        asset_class="rate",
        market_value=600.0,
        modified_duration=2.0,
        maturity_date="2031-06-30",
        years_to_maturity=5.0,
        ytm=0.030,
    )
    valid_end = {**valid_start, "ytm": 0.031}
    nonpositive = _maturity_risk_row(
        asset_class="other",
        market_value=400.0,
        modified_duration=0.0,
        maturity_date="2028-06-30",
        years_to_maturity=2.0,
        ytm=0.025,
    )

    krd = build_krd_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start, nonpositive],
        bond_rows_end=[valid_end, nonpositive],
        treasury_shift_bp=10.0,
    )
    spread = build_spread_attribution(
        report_date="2026-06-30",
        start_date="2026-05-31",
        end_date="2026-06-30",
        bond_rows_start=[valid_start, nonpositive],
        bond_rows_end=[valid_end, nonpositive],
        treasury_10y_start_pct=2.00,
        treasury_10y_end_pct=2.05,
        treasury_curve_start={"5Y": 2.00},
        treasury_curve_end={"5Y": 2.05},
    )

    assert [bucket["tenor"] for bucket in krd["buckets"]] == ["5Y"]
    assert [item["category"] for item in spread["items"]] == ["rate"]
    for payload in (krd, spread):
        coverage = payload["risk_coverage"]
        assert coverage["total_row_count"] == 2
        assert coverage["covered_row_count"] == 1
        assert coverage["excluded_row_count"] == 1
        assert coverage["total_market_value"] == pytest.approx(1_000.0)
        assert coverage["covered_market_value"] == pytest.approx(600.0)
        assert coverage["excluded_market_value"] == pytest.approx(400.0)
        assert coverage["coverage_pct"] == pytest.approx(60.0)
        assert coverage["excluded_pct"] == pytest.approx(40.0)
        assert coverage["exclusions"] == [
            {
                "reason": "nonpositive_duration",
                "row_count": 1,
                "market_value": 400.0,
            }
        ]


@pytest.mark.parametrize("zero_category", ["rate", "inactive"])
def test_carry_zero_exposure_missing_row_does_not_block_portfolio(zero_category) -> None:
    active = _carry_row(market_value=100_000_000, coupon_rate=0.03, modified_duration=2.0)
    zero = {**_carry_row(market_value=0, coupon_rate=None, modified_duration=None), "asset_class_std": zero_category}
    common = dict(report_date="2026-06-30", ftp_rate_pct=0, curve_slope_bp=15)
    expected = build_carry_roll_down(bond_rows=[active], **common)
    actual = build_carry_roll_down(bond_rows=[active, zero], **common)
    for field in ("portfolio_carry", "portfolio_rolldown", "portfolio_static_return", "total_carry_pnl", "total_rolldown_pnl", "total_static_pnl"):
        assert actual[field] == expected[field]


def test_carry_offsetting_exposure_is_not_treated_as_zero_exposure() -> None:
    active = _carry_row(market_value=100_000_000, coupon_rate=0.03, modified_duration=2.0)
    long_row = {**active, "asset_class_std": "offsetting"}
    short_row = {**long_row, "market_value": -100_000_000, "coupon_rate": None}
    payload = build_carry_roll_down(
        report_date="2026-06-30", bond_rows=[active, long_row, short_row],
        ftp_rate_pct=0, curve_slope_bp=15,
    )
    assert payload["portfolio_carry"] is None
    assert payload["total_carry_pnl"] is None
