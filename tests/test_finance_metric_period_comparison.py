from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.finance_metric_engine import FinanceMetricResult
from backend.app.core_finance.finance_metric_period_comparison import (
    KEY_METRIC_DEFINITIONS,
    build_finance_metric_period_comparisons,
)


def _metric(
    metric_id: str,
    value: str | None,
    *,
    status: str = "ok",
) -> FinanceMetricResult:
    return FinanceMetricResult(
        id=metric_id,
        name=metric_id,
        category="test",
        basis="point" if metric_id.endswith("::point") else "cumulative",
        unit="亿元",
        value=Decimal(value) if value is not None else None,
        status=status,  # type: ignore[arg-type]
        reasons=() if status == "ok" else (f"{metric_id}:{status}",),
        lineage=None,
    )


def _period(values: dict[str, tuple[str | None, str]]) -> tuple[FinanceMetricResult, ...]:
    return tuple(
        _metric(metric_id, value, status=status)
        for metric_id, (value, status) in values.items()
    )


def test_build_period_comparisons_uses_cumulative_month_conversion_and_point_basis() -> None:
    interest_id = "income.interest.net"
    point_id = "balance.deposit.corporate.total::point"
    current = _period({interest_id: ("130", "ok"), point_id: ("120", "ok")})
    prior = _period({interest_id: ("100", "ok"), point_id: ("100", "ok")})
    two_prior = _period({interest_id: ("80", "ok"), point_id: ("90", "ok")})

    rows = build_finance_metric_period_comparisons(
        report_month="202606",
        current_metrics=current,
        previous_metrics=prior,
        two_month_prior_metrics=two_prior,
        comparable_quality_status="degraded_candidate",
    )
    by_id = {row.metric_id: row for row in rows}

    interest = by_id[interest_id]
    assert interest.method == "finance_metric_cumulative_mom"
    assert interest.current_value_yi == Decimal("30")
    assert interest.previous_value_yi == Decimal("20")
    assert interest.delta_yi == Decimal("10")
    assert interest.change_rate == Decimal("0.5")
    assert interest.comparison_status == "comparable"
    assert interest.quality_status == "degraded_candidate"
    assert interest.current_source_value_yi == Decimal("130")
    assert interest.previous_source_value_yi == Decimal("100")
    assert interest.two_month_prior_source_value_yi == Decimal("80")

    point = by_id[point_id]
    assert point.method == "finance_metric_point_to_point"
    assert point.current_value_yi == Decimal("120")
    assert point.previous_value_yi == Decimal("100")
    assert point.delta_yi == Decimal("20")
    assert point.change_rate == Decimal("0.2")


def test_build_period_comparisons_blocks_warning_metrics_and_preserves_zero_denominator_reason() -> None:
    noninterest_id = "income.noninterest.total"
    point_id = "balance.deposit.corporate.total::point"
    current = _period({noninterest_id: ("10", "warning"), point_id: ("5", "ok")})
    prior = _period({noninterest_id: ("8", "warning"), point_id: ("0", "ok")})
    two_prior = _period({noninterest_id: ("7", "warning"), point_id: ("2", "ok")})

    rows = build_finance_metric_period_comparisons(
        report_month="202606",
        current_metrics=current,
        previous_metrics=prior,
        two_month_prior_metrics=two_prior,
        comparable_quality_status="standard_candidate",
    )
    by_id = {row.metric_id: row for row in rows}

    blocked = by_id[noninterest_id]
    assert blocked.comparison_status == "not_comparable"
    assert blocked.current_value_yi is None
    assert blocked.previous_value_yi is None
    assert blocked.delta_yi is None
    assert blocked.change_rate is None
    assert blocked.rate_reason == "metric_status_not_ok"
    assert blocked.quality_status == "not_comparable"
    assert blocked.current_source_value_yi == Decimal("10")

    zero = by_id[point_id]
    assert zero.comparison_status == "comparable"
    assert zero.delta_yi == Decimal("5")
    assert zero.change_rate is None
    assert zero.rate_reason == "zero_denominator"


def test_january_cumulative_comparison_resets_at_year_boundary() -> None:
    metric_id = "income.interest.net"
    rows = build_finance_metric_period_comparisons(
        report_month="202701",
        current_metrics=_period({metric_id: ("12", "ok")}),
        previous_metrics=_period({metric_id: ("120", "ok")}),
        two_month_prior_metrics=_period({metric_id: ("100", "ok")}),
        comparable_quality_status="degraded_candidate",
    )

    row = next(item for item in rows if item.metric_id == metric_id)
    assert row.current_value_yi == Decimal("12")
    assert row.previous_value_yi == Decimal("20")
    assert row.delta_yi == Decimal("-8")
    assert row.change_rate == Decimal("-0.4")


def test_february_cumulative_comparison_uses_january_cumulative_as_january_month() -> None:
    metric_id = "income.interest.net"
    rows = build_finance_metric_period_comparisons(
        report_month="202702",
        current_metrics=_period({metric_id: ("30", "ok")}),
        previous_metrics=_period({metric_id: ("12", "ok")}),
        two_month_prior_metrics=_period({metric_id: ("120", "ok")}),
        comparable_quality_status="degraded_candidate",
    )

    row = next(item for item in rows if item.metric_id == metric_id)
    assert row.current_value_yi == Decimal("18")
    assert row.previous_value_yi == Decimal("12")
    assert row.delta_yi == Decimal("6")
    assert row.change_rate == Decimal("0.5")


def test_key_metric_definitions_are_fixed_and_ordered() -> None:
    assert [item.metric_id for item in KEY_METRIC_DEFINITIONS] == [
        "income.interest.net",
        "income.noninterest.total",
        "income.operating.mother_bank",
        "balance.deposit.corporate.total::point",
        "balance.deposit.retail.total::point",
        "balance.loan.corporate.total::point",
        "balance.loan.retail.total::point",
    ]
    assert all(item.unit == "亿元" for item in KEY_METRIC_DEFINITIONS)
