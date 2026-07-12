"""Pure comparison rules for the governed Ledger PnL candidate key metrics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from backend.app.core_finance.finance_metric_engine import (
    FinanceMetricCumulativeMomResult,
    FinanceMetricResult,
    finance_metric_cumulative_mom,
    finance_metric_ratio,
)

ComparisonBasis = Literal["calendar_month_from_cumulative", "month_end_point"]
ComparisonMethod = Literal[
    "finance_metric_cumulative_mom",
    "finance_metric_point_to_point",
]
ComparisonMetricStatus = Literal["ok", "warning", "manual_default", "error", "missing"]
ComparisonStatus = Literal["comparable", "not_comparable"]
ComparisonQualityStatus = Literal[
    "standard_candidate", "degraded_candidate", "not_comparable"
]
RateReason = Literal["zero_denominator", "missing_reference", "metric_status_not_ok"]


@dataclass(frozen=True, slots=True)
class FinanceMetricPeriodComparisonDefinition:
    metric_id: str
    metric_name: str
    basis: ComparisonBasis
    method: ComparisonMethod
    unit: Literal["亿元"] = "亿元"


KEY_METRIC_DEFINITIONS = (
    FinanceMetricPeriodComparisonDefinition(
        "income.interest.net",
        "利息净收入",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "income.noninterest.total",
        "非息净收入合计",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "income.operating.mother_bank",
        "母公司营业收入",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "balance.deposit.corporate.total::point",
        "公司存款合计",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "balance.deposit.retail.total::point",
        "零售存款合计",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "balance.loan.corporate.total::point",
        "公司贷款合计",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    FinanceMetricPeriodComparisonDefinition(
        "balance.loan.retail.total::point",
        "零售贷款合计",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
)


@dataclass(frozen=True, slots=True)
class FinanceMetricPeriodComparisonRow:
    metric_id: str
    metric_name: str
    basis: ComparisonBasis
    method: ComparisonMethod
    unit: Literal["亿元"]
    comparison_status: ComparisonStatus
    current_metric_status: ComparisonMetricStatus
    previous_metric_status: ComparisonMetricStatus
    two_month_prior_metric_status: ComparisonMetricStatus | None
    current_value_yi: Decimal | None
    previous_value_yi: Decimal | None
    current_source_value_yi: Decimal | None
    previous_source_value_yi: Decimal | None
    two_month_prior_source_value_yi: Decimal | None
    delta_yi: Decimal | None
    change_rate: Decimal | None
    rate_reason: RateReason | None
    reasons: tuple[str, ...]
    quality_status: ComparisonQualityStatus
    driver_status: Literal["unclear"] = "unclear"


def build_finance_metric_period_comparisons(
    *,
    report_month: str,
    current_metrics: tuple[FinanceMetricResult, ...],
    previous_metrics: tuple[FinanceMetricResult, ...],
    two_month_prior_metrics: tuple[FinanceMetricResult, ...],
    comparable_quality_status: Literal["standard_candidate", "degraded_candidate"],
) -> tuple[FinanceMetricPeriodComparisonRow, ...]:
    """Compare the fixed seven metrics without treating missing inputs as zero."""

    current = {item.id: item for item in current_metrics}
    previous = {item.id: item for item in previous_metrics}
    two_month_prior = {item.id: item for item in two_month_prior_metrics}
    return tuple(
        _build_row(
            definition,
            report_month,
            current.get(definition.metric_id),
            previous.get(definition.metric_id),
            two_month_prior.get(definition.metric_id),
            comparable_quality_status,
        )
        for definition in KEY_METRIC_DEFINITIONS
    )


def _build_row(
    definition: FinanceMetricPeriodComparisonDefinition,
    report_month: str,
    current: FinanceMetricResult | None,
    previous: FinanceMetricResult | None,
    two_month_prior: FinanceMetricResult | None,
    comparable_quality_status: Literal["standard_candidate", "degraded_candidate"],
) -> FinanceMetricPeriodComparisonRow:
    required = (
        (current, previous, two_month_prior)
        if definition.basis == "calendar_month_from_cumulative"
        else (current, previous)
    )
    statuses = tuple(_metric_status(item) for item in required)
    if any(item is None or item.value is None or item.status != "ok" for item in required):
        reason = (
            "missing_reference"
            if any(item is None or item.value is None for item in required)
            else "metric_status_not_ok"
        )
        return FinanceMetricPeriodComparisonRow(
            metric_id=definition.metric_id,
            metric_name=definition.metric_name,
            basis=definition.basis,
            method=definition.method,
            unit=definition.unit,
            comparison_status="not_comparable",
            current_metric_status=statuses[0],
            previous_metric_status=statuses[1],
            two_month_prior_metric_status=statuses[2] if len(statuses) == 3 else None,
            current_value_yi=None,
            previous_value_yi=None,
            current_source_value_yi=_metric_value(current),
            previous_source_value_yi=_metric_value(previous),
            two_month_prior_source_value_yi=_metric_value(two_month_prior),
            delta_yi=None,
            change_rate=None,
            rate_reason=reason,
            reasons=_comparison_reasons(required),
            quality_status="not_comparable",
        )

    if definition.basis == "calendar_month_from_cumulative":
        assert current is not None and previous is not None and two_month_prior is not None
        result = _cumulative_mom_for_report_month(
            report_month=report_month,
            current_cumulative=current.value,
            prior_cumulative=previous.value,
            two_month_prior_cumulative=two_month_prior.value,
        )
        return FinanceMetricPeriodComparisonRow(
            metric_id=definition.metric_id,
            metric_name=definition.metric_name,
            basis=definition.basis,
            method=definition.method,
            unit=definition.unit,
            comparison_status="comparable",
            current_metric_status="ok",
            previous_metric_status="ok",
            two_month_prior_metric_status="ok",
            current_value_yi=result.current_month,
            previous_value_yi=result.previous_month,
            current_source_value_yi=current.value,
            previous_source_value_yi=previous.value,
            two_month_prior_source_value_yi=two_month_prior.value,
            delta_yi=result.delta,
            change_rate=result.rate,
            rate_reason=result.reason,  # type: ignore[arg-type]
            reasons=(),
            quality_status=comparable_quality_status,
        )

    assert current is not None and previous is not None
    delta = current.value - previous.value  # type: ignore[operator]
    ratio = finance_metric_ratio(delta, previous.value)
    return FinanceMetricPeriodComparisonRow(
        metric_id=definition.metric_id,
        metric_name=definition.metric_name,
        basis=definition.basis,
        method=definition.method,
        unit=definition.unit,
        comparison_status="comparable",
        current_metric_status="ok",
        previous_metric_status="ok",
        two_month_prior_metric_status=None,
        current_value_yi=current.value,
        previous_value_yi=previous.value,
        current_source_value_yi=current.value,
        previous_source_value_yi=previous.value,
        two_month_prior_source_value_yi=None,
        delta_yi=delta,
        change_rate=ratio.value,
        rate_reason=ratio.reason,  # type: ignore[arg-type]
        reasons=(),
        quality_status=comparable_quality_status,
    )


def _cumulative_mom_for_report_month(
    *,
    report_month: str,
    current_cumulative: Decimal,
    prior_cumulative: Decimal,
    two_month_prior_cumulative: Decimal,
):
    month = int(report_month[4:])
    if month == 1:
        previous_month = prior_cumulative - two_month_prior_cumulative
        delta = current_cumulative - previous_month
        ratio = finance_metric_ratio(delta, previous_month)
        return FinanceMetricCumulativeMomResult(
            current_month=current_cumulative,
            previous_month=previous_month,
            delta=delta,
            rate=ratio.value,
            reason=ratio.reason,
        )
    if month == 2:
        current_month = current_cumulative - prior_cumulative
        delta = current_month - prior_cumulative
        ratio = finance_metric_ratio(delta, prior_cumulative)
        return FinanceMetricCumulativeMomResult(
            current_month=current_month,
            previous_month=prior_cumulative,
            delta=delta,
            rate=ratio.value,
            reason=ratio.reason,
        )
    return finance_metric_cumulative_mom(
        current_cumulative=current_cumulative,
        prior_cumulative=prior_cumulative,
        two_month_prior_cumulative=two_month_prior_cumulative,
    )


def _metric_status(item: FinanceMetricResult | None) -> ComparisonMetricStatus:
    return "missing" if item is None else item.status


def _metric_value(item: FinanceMetricResult | None) -> Decimal | None:
    return None if item is None else item.value


def _comparison_reasons(
    metrics: tuple[FinanceMetricResult | None, ...],
) -> tuple[str, ...]:
    labels = ("current", "previous", "two_month_prior")
    reasons: list[str] = []
    for label, metric in zip(labels[: len(metrics)], metrics, strict=True):
        if metric is None:
            reasons.append(f"{label}:missing_metric")
        elif metric.value is None:
            reasons.append(f"{label}:missing_value")
        elif metric.status != "ok":
            reasons.append(f"{label}:status={metric.status}")
            reasons.extend(f"{label}:{reason}" for reason in metric.reasons)
    return tuple(dict.fromkeys(reasons))
