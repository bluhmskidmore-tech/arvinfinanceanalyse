from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal

import pytest


def _module():
    return importlib.import_module("backend.app.core_finance.finance_metric_engine")


def test_ratio_uses_absolute_denominator_and_reports_zero_or_missing_reference() -> None:
    module = _module()
    assert hasattr(module, "finance_metric_ratio"), "typed finance metric ratio is not implemented"

    assert module.finance_metric_ratio(Decimal("5"), Decimal("-10")).value == Decimal("0.5")
    zero = module.finance_metric_ratio(Decimal("5"), Decimal("0"))
    assert zero.value is None
    assert zero.reason == "zero_denominator"
    missing = module.finance_metric_ratio(None, Decimal("10"))
    assert missing.value is None
    assert missing.reason == "missing_reference"


def test_cumulative_mom_compares_derived_single_month_values() -> None:
    module = _module()
    result = module.finance_metric_cumulative_mom(
        current_cumulative=Decimal("60"),
        prior_cumulative=Decimal("50"),
        two_month_prior_cumulative=Decimal("45"),
    )

    assert result.current_month == Decimal("10")
    assert result.previous_month == Decimal("5")
    assert result.delta == Decimal("5")
    assert result.rate == Decimal("1")
    assert result.reason is None

    missing = module.finance_metric_cumulative_mom(
        current_cumulative=Decimal("60"),
        prior_cumulative=None,
        two_month_prior_cumulative=Decimal("45"),
    )
    assert missing.current_month is None
    assert missing.delta is None
    assert missing.rate is None
    assert missing.reason == "missing_reference"


def test_budget_time_progress_and_mix_preserve_decimal_rate_semantics() -> None:
    module = _module()

    assert module.finance_metric_budget_progress(Decimal("50"), Decimal("-100")).value == Decimal(
        "0.5"
    )
    assert module.finance_metric_budget_progress(Decimal("50"), Decimal("0")).reason == "zero_denominator"
    assert module.finance_metric_budget_progress(None, Decimal("100")).reason == "missing_reference"
    assert module.finance_metric_time_progress(days=181, year_days=365).value == Decimal(181) / Decimal(365)
    assert module.finance_metric_mix(Decimal("2"), Decimal("-8")).value == Decimal("0.25")


def test_annualization_uses_inclusive_days_and_leap_year_length() -> None:
    module = _module()

    assert module.finance_metric_year_days(date(2024, 6, 30)) == 366
    assert module.finance_metric_year_days(date(2026, 6, 30)) == 365
    assert module.finance_metric_elapsed_days(date(2024, 1, 1), date(2024, 6, 30)) == 182
    assert module.finance_metric_elapsed_days(date(2026, 1, 1), date(2026, 6, 30)) == 181
    assert module.finance_metric_annualize(Decimal("10"), days=182, year_days=366) == (
        Decimal("10") / Decimal(182) * Decimal(366)
    )


def test_ytd_and_month_rates_use_decimal_rates_and_missing_reference_semantics() -> None:
    module = _module()

    ytd = module.finance_metric_annualized_rate(
        amount_yi=Decimal("10"),
        average_balance_yi=Decimal("100"),
        days=182,
        year_days=366,
    )
    month = module.finance_metric_annualized_rate(
        amount_yi=Decimal("1"),
        average_balance_yi=Decimal("100"),
        days=30,
        year_days=366,
    )
    assert ytd.value == Decimal("0.1") * Decimal(366) / Decimal(182)
    assert month.value == Decimal("0.01") * Decimal(366) / Decimal(30)
    assert module.finance_metric_annualized_rate(
        amount_yi=Decimal("1"), average_balance_yi=None, days=30, year_days=366
    ).reason == "missing_reference"


def test_analysis_day_counts_must_be_positive() -> None:
    module = _module()

    with pytest.raises(ValueError, match="days must be positive"):
        module.finance_metric_time_progress(days=0, year_days=365)
    with pytest.raises(ValueError, match="year_days must be positive"):
        module.finance_metric_annualize(Decimal("1"), days=1, year_days=0)
    with pytest.raises(ValueError, match="days must be positive"):
        module.finance_metric_annualized_rate(
            amount_yi=Decimal("1"), average_balance_yi=Decimal("1"), days=-1, year_days=365
        )
    with pytest.raises(ValueError, match="start must not be after end"):
        module.finance_metric_elapsed_days(date(2026, 7, 1), date(2026, 6, 30))


def test_three_factor_attribution_reconciles_volume_rate_cross_to_total_change() -> None:
    module = _module()
    assert hasattr(
        module, "FinanceMetricThreeFactorAttribution"
    ), "typed three-factor attribution is not implemented"

    result = module.finance_metric_three_factor_attribution(
        prior_balance_yi=Decimal("100"),
        current_balance_yi=Decimal("120"),
        prior_rate=Decimal("0.04"),
        current_rate=Decimal("0.05"),
        days=30,
        year_days=365,
    )
    factor = Decimal(30) / Decimal(365)

    assert result.volume == Decimal("20") * Decimal("0.04") * factor
    assert result.rate == Decimal("100") * Decimal("0.01") * factor
    assert result.cross == Decimal("20") * Decimal("0.01") * factor
    assert result.volume + result.rate + result.cross == result.total_change
    assert result.reconciliation_delta == Decimal("0")
