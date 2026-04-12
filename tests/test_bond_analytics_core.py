"""Unit tests for bond analytics shared helpers and read models."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics import common
from backend.app.core_finance.bond_analytics.read_models import (
    compute_benchmark_excess,
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


def test_classify_asset_class_rate_credit_other() -> None:
    assert common.classify_asset_class("国债") == "rate"
    assert common.classify_asset_class("企业债") == "credit"
    assert common.classify_asset_class("xxx") == "other"
    assert common.classify_asset_class("") == "other"


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
                "market_value": Decimal("1000"),
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

    assert summary["allocation_effect"] == Decimal("0")
