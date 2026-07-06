"""Unit tests for bond analytics shared helpers and read models."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics import common
from backend.app.core_finance.bond_analytics.read_models import (
    summarize_return_decomposition,
)
from tests.helpers import load_module


def _read_models_module():
    return load_module(
        "backend.app.core_finance.bond_analytics.read_models",
        "backend/app/core_finance/bond_analytics/read_models.py",
    )


def test_safe_decimal_coerces_and_handles_bad_input() -> None:
    assert common.safe_decimal(None) == Decimal("0")
    assert common.safe_decimal("") == Decimal("0")
    assert common.safe_decimal("12.5") == Decimal("12.5")
    assert common.safe_decimal(3.25) == Decimal(str(3.25))
    d = Decimal("7.77")
    assert common.safe_decimal(d) is d
    assert common.safe_decimal("not-a-number") == Decimal("0")


def test_rating_aa_and_below_portfolio_weight_excludes_aaa_and_aa_plus() -> None:
    rm = _read_models_module()
    total = Decimal("100")
    credit_rows = [
        {"rating": "AAA", "market_value": Decimal("40")},
        {"rating": "AA+", "market_value": Decimal("30")},
        {"rating": "AA", "market_value": Decimal("20")},
        {"rating": "A", "market_value": Decimal("10")},
    ]
    w = rm.rating_aa_and_below_portfolio_weight(credit_rows, total_portfolio_market_value=total)
    assert w == Decimal("0.3")


def test_rating_aa_and_below_portfolio_weight_ignores_unknown_rating() -> None:
    rm = _read_models_module()
    total = Decimal("100")
    credit_rows = [
        {"rating": "AA", "market_value": Decimal("50")},
        {"rating": "MOODY", "market_value": Decimal("50")},
    ]
    w = rm.rating_aa_and_below_portfolio_weight(credit_rows, total_portfolio_market_value=total)
    assert w == Decimal("0.5")


def test_classify_asset_class_rate_credit_other() -> None:
    assert common.classify_asset_class("国债") == "rate"
    assert common.classify_asset_class("企业债") == "credit"
    assert common.classify_asset_class("xxx") == "other"
    assert common.classify_asset_class("") == "other"


def test_classify_asset_class_recognizes_real_world_credit_bond_labels() -> None:
    assert common.classify_asset_class("信用债券-企业") == "credit"
    assert common.classify_asset_class("信用债券-公用事业") == "credit"
    assert common.classify_asset_class("商业银行债") == "credit"
    assert common.classify_asset_class("资产支持证券") == "credit"


def test_map_accounting_class_patterns() -> None:
    assert common.map_accounting_class("持有至到期") == "AC"
    assert common.map_accounting_class("交易性") == "TPL"
    assert common.map_accounting_class("FVOCI") == "OCI"


def test_estimate_duration_macaulay_vs_fallback() -> None:
    rd = date(2026, 3, 31)
    mat = date(2031, 3, 31)
    coupon = Decimal("0.03")
    ytm = Decimal("0.035")
    d_mac = common.estimate_duration(mat, rd, coupon_rate=coupon, ytm=ytm)
    assert d_mac > Decimal("0")
    # Fallback: no coupon/ytm path uses years to maturity
    d_years = common.estimate_duration(mat, rd)
    years_approx = Decimal("1826") / Decimal("365")  # ~5y
    assert abs(d_years - years_approx) < Decimal("0.02")
    # No dates -> fixed fallback
    assert common.estimate_duration(None, rd) == Decimal("3")


@pytest.mark.parametrize(
    ("period_type", "start_expect", "end_expect"),
    [
        ("MoM", date(2026, 3, 1), date(2026, 3, 31)),
        ("YTD", date(2026, 1, 1), date(2026, 3, 31)),
        ("TTM", date(2025, 3, 31), date(2026, 3, 31)),
    ],
)
def test_resolve_period_mom_ytd_ttm(
    period_type: str,
    start_expect: date,
    end_expect: date,
) -> None:
    rd = date(2026, 3, 31)
    start, end = common.resolve_period(rd, period_type)
    assert start == start_expect
    assert end == end_expect


@pytest.mark.parametrize(
    ("years", "bucket"),
    [
        (0.25, "6M"),
        (1.0, "1Y"),
        (2.0, "2Y"),
        (3.5, "3Y"),
        (5.5, "5Y"),
        (8.0, "7Y"),
        (10.0, "10Y"),
        (15.0, "20Y"),
        (30.0, "30Y"),
    ],
)
def test_get_tenor_bucket(years: float, bucket: str) -> None:
    assert common.get_tenor_bucket(years) == bucket


def test_portfolio_risk_duration_excludes_no_maturity_rows_from_denominator() -> None:
    summary = _read_models_module().summarize_portfolio_risk(
        [
            {
                "market_value": Decimal("100"),
                "maturity_date": date(2030, 1, 1),
                "macaulay_duration": Decimal("4.2"),
                "modified_duration": Decimal("4"),
                "convexity": Decimal("20"),
                "dv01": Decimal("4"),
            },
            {
                "market_value": Decimal("300"),
                "maturity_date": None,
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ]
    )

    assert summary["total_market_value"] == Decimal("400")
    assert summary["portfolio_dv01"] == Decimal("4")
    assert summary["portfolio_duration"] == Decimal("4.2")
    assert summary["portfolio_modified_duration"] == Decimal("4")


def test_convexity_effect_with_curve_data() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        treasury_curve_current={"5Y": Decimal("3.00")},
        treasury_curve_prior={"5Y": Decimal("1.00")},
    )

    expected = Decimal("0.5") * Decimal("2") * Decimal("0.02") * Decimal("0.02") * Decimal("100")

    assert summary["convexity_effect_total"] == expected
    assert summary["bond_details"][0]["convexity_effect"] == expected


def test_roll_down_uses_exclusive_elapsed_days_for_current_anchor() -> None:
    rm = _read_models_module()
    current_curve = {"1Y": Decimal("1.00"), "2Y": Decimal("2.00")}

    summary = rm.summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 2Y",
                "asset_class_raw": "rate",
                "asset_class_std": "rate",
                "bond_type": "treasury",
                "accounting_class": "FVTPL",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("2"),
                "tenor_bucket": "2Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("0"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        treasury_curve_current=current_curve,
    )

    expected = rm._curve_roll_down(
        current_curve=current_curve,
        years_to_maturity=Decimal("2"),
        period_days=30,
        modified_duration=Decimal("4"),
        market_value=Decimal("100"),
    )
    assert summary["roll_down_total"] == expected
    assert summary["bond_details"][0]["roll_down"] == expected


def test_convexity_effect_without_curve_data_is_zero() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )

    assert summary["convexity_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["convexity_effect"] == Decimal("0")


def test_fx_effect_zero_for_cny_bonds() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("0")


def test_fx_effect_positive_when_usd_appreciates() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value_native": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("41.35000000")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("41.35000000")


def test_fx_effect_missing_rate_emits_fx_rate_missing_warning() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value_native": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"EUR": Decimal("7.9")},
        fx_rates_prior={"EUR": Decimal("7.8")},
    )

    # Value still defaults to zero, but the missing FX input must be observable.
    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["fx_rate_missing_currencies"] == ["USD"]
    assert any("FX_RATE_MISSING" in warning for warning in summary["warnings"])


def test_fx_effect_cny_bonds_do_not_emit_fx_rate_missing_warning() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )

    # CNY exposure has no FX effect and must not raise a missing-input warning.
    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["fx_rate_missing_currencies"] == []
    assert all("FX_RATE_MISSING" not in warning for warning in summary["warnings"])


def test_fx_effect_zero_without_native_market_value() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("0")


def test_spread_effect_moves_excess_return_without_selection_residual() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            }
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"5Y": Decimal("2.00")},
        benchmark_curve_prior={"5Y": Decimal("2.00")},
        treasury_curve_current={"5Y": Decimal("2.00")},
        treasury_curve_prior={"5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("6.00")},
        aaa_credit_curve_prior={"5Y": Decimal("5.00")},
    )

    assert summary["excess_return"] == Decimal("-500.00000000")
    assert summary["spread_effect"] == Decimal("-500.00000000")
    assert summary["selection_effect"] == Decimal("0")
    assert summary["allocation_effect"] == Decimal("0")


def test_allocation_effect_uses_non_carry_sector_returns() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("1"),
                "modified_duration": Decimal("1"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        treasury_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("3.00")},
        aaa_credit_curve_prior={"5Y": Decimal("3.00")},
    )

    assert summary["allocation_effect"] == Decimal("-200.0000000")
    assert summary["selection_effect"] == Decimal("200.00000000")
    # recon_error is the unexplained residual: excess minus the independently
    # computed effects (excluding the selection plug). It can be non-zero.
    assert summary["recon_error"] == (
        summary["excess_return"]
        - summary["duration_effect"]
        - summary["curve_effect"]
        - summary["spread_effect"]
        - summary["allocation_effect"]
    )
    assert summary["recon_error"] == summary["selection_effect"]
    assert summary["recon_error"] != Decimal("0")
    assert summary["explained_excess"] == summary["excess_return"]


def test_benchmark_excess_reuses_return_decomposition_for_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    read_models = _read_models_module()
    calls = 0
    original = read_models.summarize_return_decomposition

    def counting_summary(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(read_models, "summarize_return_decomposition", counting_summary)

    summary = read_models.compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "rate",
                "asset_class_std": "rate",
                "bond_type": "treasury",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("1"),
                "modified_duration": Decimal("1"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "credit",
                "asset_class_std": "credit",
                "bond_type": "credit",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        treasury_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("3.00")},
        aaa_credit_curve_prior={"5Y": Decimal("3.00")},
    )

    assert calls == 1
    assert summary["allocation_effect"] == Decimal("-200.0000000")


def test_benchmark_excess_reuses_prepared_curve_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    read_models = _read_models_module()
    calls = 0
    original = read_models.build_full_curve

    def counting_build_full_curve(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(read_models, "build_full_curve", counting_build_full_curve)
    rows = [
        {
            "instrument_code": f"R{i}",
            "instrument_name": f"Treasury {i}Y",
            "asset_class_raw": "rate",
            "asset_class_std": "rate",
            "bond_type": "treasury",
            "accounting_class": "AC",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0"),
            "years_to_maturity": Decimal(str(i)),
            "tenor_bucket": "5Y",
            "macaulay_duration": Decimal(str(i)),
            "modified_duration": Decimal(str(i)),
            "convexity": Decimal("1"),
            "dv01": Decimal("0"),
        }
        for i in range(1, 7)
    ]

    summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "3Y": Decimal("3.20"), "5Y": Decimal("3.40")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "3Y": Decimal("2.20"), "5Y": Decimal("2.40")},
        treasury_curve_current={"1Y": Decimal("3.00"), "3Y": Decimal("3.20"), "5Y": Decimal("3.40")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "3Y": Decimal("2.20"), "5Y": Decimal("2.40")},
    )

    assert summary["benchmark_return"] != Decimal("0")
    assert calls <= 4


def test_portfolio_return_is_invariant_across_benchmark_choice() -> None:
    read_models = _read_models_module()
    rows = [
        {
            "instrument_code": "R1",
            "instrument_name": "Treasury 1Y",
            "asset_class_raw": "rate",
            "asset_class_std": "rate",
            "bond_type": "treasury",
            "accounting_class": "AC",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0.10"),
            "years_to_maturity": Decimal("1"),
            "tenor_bucket": "1Y",
            "macaulay_duration": Decimal("1"),
            "modified_duration": Decimal("1"),
            "convexity": Decimal("0"),
            "dv01": Decimal("0"),
        },
        {
            "instrument_code": "C1",
            "instrument_name": "Credit 5Y",
            "asset_class_raw": "credit",
            "asset_class_std": "credit",
            "bond_type": "credit",
            "accounting_class": "OCI",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0.20"),
            "years_to_maturity": Decimal("5"),
            "tenor_bucket": "5Y",
            "macaulay_duration": Decimal("4"),
            "modified_duration": Decimal("4"),
            "convexity": Decimal("0"),
            "dv01": Decimal("0"),
        },
    ]
    treasury_current = {"1Y": Decimal("2.00"), "5Y": Decimal("2.00")}
    treasury_prior = {"1Y": Decimal("1.00"), "5Y": Decimal("1.00")}
    cdb_current = {"1Y": Decimal("2.50"), "5Y": Decimal("2.50")}
    cdb_prior = {"1Y": Decimal("1.50"), "5Y": Decimal("1.50")}
    aaa_current = {"1Y": Decimal("4.00"), "5Y": Decimal("4.00")}
    aaa_prior = {"1Y": Decimal("2.00"), "5Y": Decimal("2.00")}

    treasury_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current=treasury_current,
        benchmark_curve_prior=treasury_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )
    cdb_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="CDB_INDEX",
        benchmark_curve_current=cdb_current,
        benchmark_curve_prior=cdb_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )
    aaa_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="AAA_CREDIT_INDEX",
        benchmark_curve_current=aaa_current,
        benchmark_curve_prior=aaa_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )

    assert treasury_summary["portfolio_return"] == cdb_summary["portfolio_return"] == aaa_summary["portfolio_return"]


def test_allocation_effect_sums_correctly() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.10"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.20"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
    )

    assert summary["allocation_effect"] == Decimal("500.0000000")
    assert summary["selection_effect"] == Decimal("1000.00000000")
    # recon_error equals the unexplained residual (== the selection plug), non-zero here.
    assert summary["recon_error"] == Decimal("1000.00000000")
    assert summary["explained_excess"] == summary["excess_return"]


def test_summarize_return_decomposition_trading_defaults_to_zero() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )
    assert summary["trading_total"] == Decimal("0")
    assert summary["bond_details"][0]["trading"] == Decimal("0")


def test_rebucket_return_decomposition_aggregates_trading() -> None:
    from backend.app.core_finance.bond_analytics.read_models import rebucket_return_decomposition

    z = Decimal("0")
    d1: dict = {
        "instrument_code": "A1",
        "asset_class_std": "rate",
        "accounting_class": "AC",
        "carry": z,
        "roll_down": z,
        "rate_effect": z,
        "spread_effect": z,
        "convexity_effect": z,
        "fx_effect": z,
        "trading": Decimal("3"),
        "market_value": Decimal("100"),
        "total": Decimal("3"),
    }
    d2: dict = {
        "instrument_code": "A2",
        "asset_class_std": "credit",
        "accounting_class": "AC",
        "carry": z,
        "roll_down": z,
        "rate_effect": z,
        "spread_effect": z,
        "convexity_effect": z,
        "fx_effect": z,
        "trading": Decimal("7"),
        "market_value": Decimal("200"),
        "total": Decimal("7"),
    }
    by_ac, by_acc = rebucket_return_decomposition([d1, d2])
    rate = next(b for b in by_ac if b["key"] == "rate")
    credit = next(b for b in by_ac if b["key"] == "credit")
    assert rate["trading"] == Decimal("3")
    assert credit["trading"] == Decimal("7")
    assert sum((b["trading"] for b in by_acc), Decimal("0")) == Decimal("10")


# --- Standard curve scenarios: full tenor-bucket coverage ---

# Buckets produced by common.get_tenor_bucket (the active bond-analytics path).
_ALL_TENOR_BUCKETS = ("6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y")


def _scenario(name: str) -> dict:
    return next(s for s in common.STANDARD_SCENARIOS if s["name"] == name)


def _risk_row(tenor_bucket: str) -> dict:
    return {
        "tenor_bucket": tenor_bucket,
        "market_value": Decimal("1000000"),
        "modified_duration": Decimal("4"),
        "convexity": Decimal("20"),
        "asset_class_std": "rate",
        "accounting_class": "OCI",
    }


def test_steepening_flattening_scenarios_cover_all_tenor_buckets() -> None:
    for name in ("steepening_50bp", "flattening_50bp"):
        shocks = _scenario(name)["shocks"]
        missing = [t for t in _ALL_TENOR_BUCKETS if not shocks.get(t)]
        assert not missing, f"{name} has zero/missing shocks for buckets: {missing}"


def test_steepening_flattening_anchor_shocks_unchanged() -> None:
    steepening = _scenario("steepening_50bp")["shocks"]
    flattening = _scenario("flattening_50bp")["shocks"]
    assert (steepening["1Y"], steepening["10Y"], steepening["30Y"]) == (-25, 25, 50)
    assert (flattening["1Y"], flattening["10Y"], flattening["30Y"]) == (25, -25, -50)


def test_steepening_shocks_monotonic_and_flattening_is_mirror() -> None:
    steepening = _scenario("steepening_50bp")["shocks"]
    flattening = _scenario("flattening_50bp")["shocks"]
    values = [steepening[t] for t in _ALL_TENOR_BUCKETS]
    assert values == sorted(values), "steepening shocks should be non-decreasing along the curve"
    assert steepening["2Y"] < 0 and steepening["7Y"] > 0
    for tenor in _ALL_TENOR_BUCKETS:
        assert flattening[tenor] == -steepening[tenor]


def test_build_curve_scenarios_shocks_middle_buckets() -> None:
    rm = _read_models_module()
    rows = [_risk_row(t) for t in ("2Y", "5Y", "7Y")]
    scenarios = {s["scenario_name"]: s for s in rm.build_curve_scenarios(rows)}
    for name in ("steepening_50bp", "flattening_50bp"):
        assert scenarios[name]["pnl_economic"] != Decimal("0"), (
            f"{name} must shock middle tenor buckets (2Y/5Y/7Y)"
        )
    # Steepening on this short/mid book (negative shocks) should be a gain; flattening a loss.
    assert scenarios["steepening_50bp"]["pnl_economic"] > Decimal("0")
    assert scenarios["flattening_50bp"]["pnl_economic"] < Decimal("0")


def test_parallel_scenarios_shock_every_bucket_equally() -> None:
    rm = _read_models_module()
    single = {
        s["scenario_name"]: s["pnl_economic"]
        for s in rm.build_curve_scenarios([_risk_row("6M")])
    }
    for tenor in _ALL_TENOR_BUCKETS[1:]:
        other = {
            s["scenario_name"]: s["pnl_economic"]
            for s in rm.build_curve_scenarios([_risk_row(tenor)])
        }
        for name in ("parallel_up_25bp", "parallel_up_100bp", "parallel_down_50bp"):
            assert other[name] == single[name], f"{name} shock differs for bucket {tenor}"
