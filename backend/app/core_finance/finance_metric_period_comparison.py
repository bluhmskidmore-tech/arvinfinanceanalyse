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
ComparisonQualityStatus = Literal["standard_candidate", "degraded_candidate", "not_comparable"]
RateReason = Literal["zero_denominator", "missing_reference", "metric_status_not_ok"]
NetInterestBridgeStatus = Literal["available", "not_evaluable"]
NetInterestBridgeQualityStatus = Literal["standard_candidate", "degraded_candidate", "not_evaluable"]
NetInterestBridgeFootStatus = Literal["passed", "failed", "not_evaluable"]


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
class NetInterestComponentDefinition:
    metric_id: str
    metric_name: str
    formula_weight: Literal[-1, 1]


NET_INTEREST_COMPONENT_DEFINITIONS = (
    NetInterestComponentDefinition(
        "income.interest.loan.total",
        "贷款利息收入",
        1,
    ),
    NetInterestComponentDefinition(
        "expense.interest.deposit.total",
        "存款利息支出",
        -1,
    ),
    NetInterestComponentDefinition(
        "income.interest.investment",
        "金融投资利息收入",
        1,
    ),
    NetInterestComponentDefinition(
        "income.interest.interbank_net",
        "同业资产负债利息净收入",
        1,
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


@dataclass(frozen=True, slots=True)
class FinanceMetricNetInterestComponentContribution:
    metric_id: str
    metric_name: str
    formula_weight: Literal[-1, 1]
    current_metric_status: ComparisonMetricStatus
    previous_metric_status: ComparisonMetricStatus
    two_month_prior_metric_status: ComparisonMetricStatus
    current_value_yi: Decimal | None
    previous_value_yi: Decimal | None
    current_source_value_yi: Decimal | None
    previous_source_value_yi: Decimal | None
    two_month_prior_source_value_yi: Decimal | None
    component_delta_yi: Decimal | None
    contribution_to_net_delta_yi: Decimal | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinanceMetricNetInterestComponentBridge:
    analysis_kind: Literal["accounting_component_bridge"]
    status: NetInterestBridgeStatus
    metric_id: Literal["income.interest.net"]
    basis: Literal["calendar_month_from_cumulative"]
    method: Literal["finance_metric_component_contribution"]
    unit: Literal["亿元"]
    quality_status: NetInterestBridgeQualityStatus
    foot_status: NetInterestBridgeFootStatus
    net_delta_yi: Decimal | None
    component_contribution_total_yi: Decimal | None
    reconciliation_delta_yi: Decimal | None
    reasons: tuple[str, ...]
    components: tuple[FinanceMetricNetInterestComponentContribution, ...]


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


def build_net_interest_component_bridge(
    *,
    report_month: str,
    current_metrics: tuple[FinanceMetricResult, ...],
    previous_metrics: tuple[FinanceMetricResult, ...],
    two_month_prior_metrics: tuple[FinanceMetricResult, ...],
    net_interest_row: FinanceMetricPeriodComparisonRow,
    comparable_quality_status: Literal["standard_candidate", "degraded_candidate"],
) -> FinanceMetricNetInterestComponentBridge:
    """Build an all-or-nothing arithmetic bridge for net-interest change."""

    periods = (
        {item.id: item for item in current_metrics},
        {item.id: item for item in previous_metrics},
        {item.id: item for item in two_month_prior_metrics},
    )
    source_components = tuple(
        (
            definition,
            periods[0].get(definition.metric_id),
            periods[1].get(definition.metric_id),
            periods[2].get(definition.metric_id),
        )
        for definition in NET_INTEREST_COMPONENT_DEFINITIONS
    )
    blocking_reasons = tuple(
        reason
        for definition, current, previous, two_month_prior in source_components
        for reason in _component_blocking_reasons(
            definition=definition,
            current=current,
            previous=previous,
            two_month_prior=two_month_prior,
        )
    )
    if (
        net_interest_row.metric_id != "income.interest.net"
        or net_interest_row.basis != "calendar_month_from_cumulative"
        or net_interest_row.method != "finance_metric_cumulative_mom"
        or net_interest_row.unit != "亿元"
        or net_interest_row.comparison_status != "comparable"
        or net_interest_row.delta_yi is None
        or not net_interest_row.delta_yi.is_finite()
        or net_interest_row.quality_status != comparable_quality_status
    ):
        blocking_reasons = (
            *blocking_reasons,
            "net_interest_comparison_not_evaluable",
        )
    if blocking_reasons:
        return _not_evaluable_net_interest_bridge(
            source_components=source_components,
            reasons=tuple(dict.fromkeys(blocking_reasons)),
        )

    components = tuple(
        _build_net_interest_component_contribution(
            report_month=report_month,
            definition=definition,
            current=current,
            previous=previous,
            two_month_prior=two_month_prior,
        )
        for definition, current, previous, two_month_prior in source_components
    )
    contribution_total = sum(
        (item.contribution_to_net_delta_yi for item in components if item.contribution_to_net_delta_yi is not None),
        Decimal(0),
    )
    assert net_interest_row.delta_yi is not None
    reconciliation_delta = net_interest_row.delta_yi - contribution_total
    foot_passed = reconciliation_delta == 0
    return FinanceMetricNetInterestComponentBridge(
        analysis_kind="accounting_component_bridge",
        status="available" if foot_passed else "not_evaluable",
        metric_id="income.interest.net",
        basis="calendar_month_from_cumulative",
        method="finance_metric_component_contribution",
        unit="亿元",
        quality_status=(comparable_quality_status if foot_passed else "not_evaluable"),
        foot_status="passed" if foot_passed else "failed",
        net_delta_yi=net_interest_row.delta_yi,
        component_contribution_total_yi=contribution_total,
        reconciliation_delta_yi=reconciliation_delta,
        reasons=(() if foot_passed else ("net_interest_component_reconciliation_failed",)),
        components=components,
    )


def _component_blocking_reasons(
    *,
    definition: NetInterestComponentDefinition,
    current: FinanceMetricResult | None,
    previous: FinanceMetricResult | None,
    two_month_prior: FinanceMetricResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for label, metric in (
        ("current", current),
        ("previous", previous),
        ("two_month_prior", two_month_prior),
    ):
        prefix = f"{definition.metric_id}:{label}"
        if metric is None:
            reasons.append(f"{prefix}:missing_metric")
        elif metric.value is None:
            reasons.append(f"{prefix}:missing_value")
        elif not metric.value.is_finite():
            reasons.append(f"{prefix}:non_finite_value")
        elif metric.status != "ok":
            reasons.append(f"{prefix}:status={metric.status}")
            reasons.extend(f"{prefix}:{reason}" for reason in metric.reasons)
    return tuple(dict.fromkeys(reasons))


def _not_evaluable_net_interest_bridge(
    *,
    source_components: tuple[
        tuple[
            NetInterestComponentDefinition,
            FinanceMetricResult | None,
            FinanceMetricResult | None,
            FinanceMetricResult | None,
        ],
        ...,
    ],
    reasons: tuple[str, ...],
) -> FinanceMetricNetInterestComponentBridge:
    components = tuple(
        FinanceMetricNetInterestComponentContribution(
            metric_id=definition.metric_id,
            metric_name=definition.metric_name,
            formula_weight=definition.formula_weight,
            current_metric_status=_metric_status(current),
            previous_metric_status=_metric_status(previous),
            two_month_prior_metric_status=_metric_status(two_month_prior),
            current_value_yi=None,
            previous_value_yi=None,
            current_source_value_yi=_finite_metric_value(current),
            previous_source_value_yi=_finite_metric_value(previous),
            two_month_prior_source_value_yi=_finite_metric_value(two_month_prior),
            component_delta_yi=None,
            contribution_to_net_delta_yi=None,
            reasons=("bridge_not_evaluable",),
        )
        for definition, current, previous, two_month_prior in source_components
    )
    return FinanceMetricNetInterestComponentBridge(
        analysis_kind="accounting_component_bridge",
        status="not_evaluable",
        metric_id="income.interest.net",
        basis="calendar_month_from_cumulative",
        method="finance_metric_component_contribution",
        unit="亿元",
        quality_status="not_evaluable",
        foot_status="not_evaluable",
        net_delta_yi=None,
        component_contribution_total_yi=None,
        reconciliation_delta_yi=None,
        reasons=reasons,
        components=components,
    )


def _build_net_interest_component_contribution(
    *,
    report_month: str,
    definition: NetInterestComponentDefinition,
    current: FinanceMetricResult | None,
    previous: FinanceMetricResult | None,
    two_month_prior: FinanceMetricResult | None,
) -> FinanceMetricNetInterestComponentContribution:
    assert current is not None and current.value is not None
    assert previous is not None and previous.value is not None
    assert two_month_prior is not None and two_month_prior.value is not None
    comparison = _cumulative_mom_for_report_month(
        report_month=report_month,
        current_cumulative=current.value,
        prior_cumulative=previous.value,
        two_month_prior_cumulative=two_month_prior.value,
    )
    assert comparison.current_month is not None
    assert comparison.previous_month is not None
    assert comparison.delta is not None
    contribution = comparison.delta * Decimal(definition.formula_weight)
    return FinanceMetricNetInterestComponentContribution(
        metric_id=definition.metric_id,
        metric_name=definition.metric_name,
        formula_weight=definition.formula_weight,
        current_metric_status="ok",
        previous_metric_status="ok",
        two_month_prior_metric_status="ok",
        current_value_yi=comparison.current_month,
        previous_value_yi=comparison.previous_month,
        current_source_value_yi=current.value,
        previous_source_value_yi=previous.value,
        two_month_prior_source_value_yi=two_month_prior.value,
        component_delta_yi=comparison.delta,
        contribution_to_net_delta_yi=contribution,
        reasons=(),
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


def _finite_metric_value(item: FinanceMetricResult | None) -> Decimal | None:
    value = _metric_value(item)
    return value if value is not None and value.is_finite() else None


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
