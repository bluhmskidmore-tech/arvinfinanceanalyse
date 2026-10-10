"""Strict response contract for candidate key-metric period comparison."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecimalString = Annotated[str, Field(pattern=r"^-?\d+(?:\.\d+)?$")]
Sha256String = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ReportMonth = Annotated[str, Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")]

EXPECTED_METRICS = (
    (
        "income.interest.net",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    (
        "income.noninterest.total",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    (
        "income.operating.mother_bank",
        "calendar_month_from_cumulative",
        "finance_metric_cumulative_mom",
    ),
    (
        "balance.deposit.corporate.total::point",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    (
        "balance.deposit.retail.total::point",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    (
        "balance.loan.corporate.total::point",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
    (
        "balance.loan.retail.total::point",
        "month_end_point",
        "finance_metric_point_to_point",
    ),
)

EXPECTED_NET_INTEREST_COMPONENTS = (
    ("income.interest.loan.total", "贷款利息收入", 1),
    ("expense.interest.deposit.total", "存款利息支出", -1),
    ("income.interest.investment", "金融投资利息收入", 1),
    ("income.interest.interbank_net", "同业资产负债利息净收入", 1),
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateFinancialIndicatorComparisonSourcePeriod(_StrictModel):
    month: ReportMonth
    report_date: date
    ledger_file_name: str = Field(min_length=1)
    ledger_sha256: Sha256String
    locked_sha256: Sha256String | None
    lock_status: Literal["locked_match", "locked_mismatch", "unlocked"]

    @model_validator(mode="after")
    def validate_source_period(self) -> CandidateFinancialIndicatorComparisonSourcePeriod:
        year = int(self.month[:4])
        month = int(self.month[4:])
        expected_date = date(year, month, monthrange(year, month)[1])
        if self.report_date != expected_date:
            raise ValueError("source report_date must be the month-end for month")
        if self.ledger_file_name != f"总账对账{self.month}.xlsx":
            raise ValueError("ledger_file_name must match the fixed source naming contract")
        expected_lock_status = (
            "unlocked"
            if self.locked_sha256 is None
            else ("locked_match" if self.ledger_sha256 == self.locked_sha256 else "locked_mismatch")
        )
        if self.lock_status != expected_lock_status:
            raise ValueError("lock_status must match the source hash evidence")
        return self


class CandidateFinancialIndicatorPeriodComparisonMetric(_StrictModel):
    metric_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    basis: Literal["calendar_month_from_cumulative", "month_end_point"]
    method: Literal[
        "finance_metric_cumulative_mom",
        "finance_metric_point_to_point",
    ]
    unit: Literal["亿元"]
    comparison_status: Literal["comparable", "not_comparable"]
    current_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"]
    previous_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"]
    two_month_prior_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"] | None
    current_value_yi: DecimalString | None
    previous_value_yi: DecimalString | None
    current_source_value_yi: DecimalString | None
    previous_source_value_yi: DecimalString | None
    two_month_prior_source_value_yi: DecimalString | None
    delta_yi: DecimalString | None
    change_rate: DecimalString | None
    rate_reason: (
        Literal[
            "zero_denominator",
            "missing_reference",
            "metric_status_not_ok",
        ]
        | None
    )
    reasons: list[str]
    driver_status: Literal["unclear"]
    quality_status: Literal["standard_candidate", "degraded_candidate", "not_comparable"]

    @model_validator(mode="after")
    def validate_metric_coherence(self) -> CandidateFinancialIndicatorPeriodComparisonMetric:
        if self.basis == "calendar_month_from_cumulative":
            if self.method != "finance_metric_cumulative_mom":
                raise ValueError("cumulative metric requires finance_metric_cumulative_mom")
            if self.two_month_prior_metric_status is None:
                raise ValueError("cumulative metric requires two-month-prior status")
        elif self.method != "finance_metric_point_to_point":
            raise ValueError("point metric requires finance_metric_point_to_point")
        elif self.two_month_prior_metric_status is not None:
            raise ValueError("point metric must not claim two-month-prior metric status")
        elif self.two_month_prior_source_value_yi is not None:
            raise ValueError("point metric must not expose two-month-prior source value")

        values = (
            self.current_value_yi,
            self.previous_value_yi,
            self.delta_yi,
        )
        statuses = [self.current_metric_status, self.previous_metric_status]
        if self.two_month_prior_metric_status is not None:
            statuses.append(self.two_month_prior_metric_status)
        if self.comparison_status == "comparable":
            if any(status != "ok" for status in statuses):
                raise ValueError("comparable metric requires all source statuses to be ok")
            if any(value is None for value in values):
                raise ValueError("comparable metric requires current, previous and delta values")
            if self.current_source_value_yi is None or self.previous_source_value_yi is None:
                raise ValueError("comparable metric requires current and previous source values")
            if self.basis == "calendar_month_from_cumulative" and self.two_month_prior_source_value_yi is None:
                raise ValueError("comparable cumulative metric requires two-prior source value")
            if self.rate_reason not in {None, "zero_denominator"}:
                raise ValueError("comparable metric has an invalid rate reason")
            if (self.change_rate is None) != (self.rate_reason == "zero_denominator"):
                raise ValueError("null comparable rate is allowed only for a zero denominator")
            if self.reasons:
                raise ValueError("comparable metric cannot carry blocking reasons")
            if self.quality_status == "not_comparable":
                raise ValueError("comparable metric requires a candidate quality status")
        else:
            if any(value is not None for value in (*values, self.change_rate)):
                raise ValueError("not-comparable metric must not expose comparison values")
            if self.rate_reason not in {"missing_reference", "metric_status_not_ok"}:
                raise ValueError("not-comparable metric requires an explicit blocking reason")
            if not self.reasons:
                raise ValueError("not-comparable metric requires evidence reasons")
            if self.quality_status != "not_comparable":
                raise ValueError("not-comparable metric requires not_comparable quality")
        return self


class CandidateFinancialIndicatorNetInterestComponent(_StrictModel):
    metric_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    formula_weight: Literal[-1, 1]
    current_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"]
    previous_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"]
    two_month_prior_metric_status: Literal["ok", "warning", "manual_default", "error", "missing"]
    current_value_yi: DecimalString | None
    previous_value_yi: DecimalString | None
    current_source_value_yi: DecimalString | None
    previous_source_value_yi: DecimalString | None
    two_month_prior_source_value_yi: DecimalString | None
    component_delta_yi: DecimalString | None
    contribution_to_net_delta_yi: DecimalString | None
    reasons: list[str]

    @model_validator(mode="after")
    def validate_component(
        self,
    ) -> CandidateFinancialIndicatorNetInterestComponent:
        statuses = (
            self.current_metric_status,
            self.previous_metric_status,
            self.two_month_prior_metric_status,
        )
        source_values = (
            self.current_source_value_yi,
            self.previous_source_value_yi,
            self.two_month_prior_source_value_yi,
        )
        computed_values = (
            self.current_value_yi,
            self.previous_value_yi,
            self.component_delta_yi,
            self.contribution_to_net_delta_yi,
        )
        sources_are_evaluable = all(status == "ok" for status in statuses) and all(
            value is not None for value in source_values
        )
        has_all_computed = all(value is not None for value in computed_values)
        has_any_computed = any(value is not None for value in computed_values)
        if has_any_computed != has_all_computed:
            raise ValueError("component computed values must be all present or all null")
        if has_all_computed:
            if not sources_are_evaluable:
                raise ValueError("computed component requires three evaluable sources")
            if self.reasons:
                raise ValueError("computed component cannot carry blocking reasons")
            current_value = Decimal(self.current_value_yi)  # type: ignore[arg-type]
            previous_value = Decimal(self.previous_value_yi)  # type: ignore[arg-type]
            delta = Decimal(self.component_delta_yi)  # type: ignore[arg-type]
            contribution = Decimal(
                self.contribution_to_net_delta_yi  # type: ignore[arg-type]
            )
            if delta != current_value - previous_value:
                raise ValueError("component delta must equal current minus previous")
            if contribution != delta * Decimal(self.formula_weight):
                raise ValueError("component contribution must apply the formula weight")
        elif not self.reasons:
            raise ValueError("non-evaluable component requires blocking reasons")
        return self


class CandidateFinancialIndicatorNetInterestComponentBridge(_StrictModel):
    analysis_kind: Literal["accounting_component_bridge"]
    status: Literal["available", "not_evaluable"]
    metric_id: Literal["income.interest.net"]
    basis: Literal["calendar_month_from_cumulative"]
    method: Literal["finance_metric_component_contribution"]
    unit: Literal["亿元"]
    quality_status: Literal["standard_candidate", "degraded_candidate", "not_evaluable"]
    foot_status: Literal["passed", "failed", "not_evaluable"]
    net_delta_yi: DecimalString | None
    component_contribution_total_yi: DecimalString | None
    reconciliation_delta_yi: DecimalString | None
    reasons: list[str]
    components: list[CandidateFinancialIndicatorNetInterestComponent]

    @model_validator(mode="after")
    def validate_bridge(
        self,
    ) -> CandidateFinancialIndicatorNetInterestComponentBridge:
        aggregate_values = (
            self.net_delta_yi,
            self.component_contribution_total_yi,
            self.reconciliation_delta_yi,
        )
        has_all_aggregates = all(value is not None for value in aggregate_values)
        has_any_aggregate = any(value is not None for value in aggregate_values)
        if has_any_aggregate != has_all_aggregates:
            raise ValueError("bridge aggregate values must be all present or all null")
        all_components_computed = all(item.contribution_to_net_delta_yi is not None for item in self.components)
        any_component_computed = any(item.contribution_to_net_delta_yi is not None for item in self.components)
        if self.status == "available":
            if self.foot_status != "passed":
                raise ValueError("available bridge requires a passed foot")
            if self.quality_status == "not_evaluable":
                raise ValueError("available bridge requires candidate quality")
            if not has_all_aggregates or not all_components_computed:
                raise ValueError("available bridge requires complete Decimal values")
            if self.reasons:
                raise ValueError("available bridge cannot carry blocking reasons")
        else:
            if self.quality_status != "not_evaluable" or not self.reasons:
                raise ValueError("not-evaluable bridge requires evidence and quality")
            if self.foot_status == "passed":
                raise ValueError("a passed foot cannot be marked not evaluable")
            if self.foot_status == "not_evaluable":
                if has_any_aggregate or any_component_computed:
                    raise ValueError("non-evaluable foot must not expose partial results")
                return self
            if not has_all_aggregates or not all_components_computed:
                raise ValueError("failed foot requires complete reconciliation evidence")

        net_delta = Decimal(self.net_delta_yi)  # type: ignore[arg-type]
        contribution_total = Decimal(
            self.component_contribution_total_yi  # type: ignore[arg-type]
        )
        reconciliation_delta = Decimal(
            self.reconciliation_delta_yi  # type: ignore[arg-type]
        )
        component_total = sum(
            (
                Decimal(item.contribution_to_net_delta_yi)
                for item in self.components
                if item.contribution_to_net_delta_yi is not None
            ),
            Decimal(0),
        )
        if contribution_total != component_total:
            raise ValueError("bridge total must equal the four component contributions")
        if reconciliation_delta != net_delta - contribution_total:
            raise ValueError("bridge reconciliation must equal net delta minus total")
        if self.foot_status == "passed" and reconciliation_delta != 0:
            raise ValueError("passed foot requires exact unrounded Decimal equality")
        if self.foot_status == "failed" and reconciliation_delta == 0:
            raise ValueError("failed foot requires a non-zero reconciliation delta")
        return self


class CandidateFinancialIndicatorFullScopeGap(_StrictModel):
    reason_code: Literal[
        "missing_source_file",
        "missing_required_sheet",
        "source_parse_error",
        "full_replay_incomplete",
        "source_evaluation_error",
    ]
    source_kind: Literal["ledger", "daily"]
    month: ReportMonth
    required_sheet: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_gap(self) -> CandidateFinancialIndicatorFullScopeGap:
        if (self.reason_code == "missing_required_sheet") != (self.required_sheet is not None):
            raise ValueError("required_sheet is exclusive to missing_required_sheet")
        return self


class CandidateFinancialIndicatorPeriodComparisonEnvelope(_StrictModel):
    contract_version: Literal["candidate-financial-indicator-period-comparison-v2"]
    report_month: ReportMonth
    report_date: date
    comparison_month: ReportMonth
    two_month_prior: ReportMonth
    comparison_scope: Literal["ledger_only_key_metrics"]
    full_scope_status: Literal["available", "unavailable"]
    full_scope_reason_code: Literal[
        "available",
        "missing_source_file",
        "missing_required_sheet",
        "source_parse_error",
        "full_replay_incomplete",
        "source_evaluation_error",
    ]
    full_scope_detail: str = Field(min_length=1)
    full_scope_gaps: list[CandidateFinancialIndicatorFullScopeGap]
    overall_status: Literal["available", "partial", "unavailable"]
    metric_status: Literal["candidate"]
    formal_use_allowed: Literal[False]
    certification_effect: Literal["none"]
    driver_status: Literal["unclear"]
    rule_version: Literal["qdb-finance-2026-v1.0.1"]
    rule_hash: Sha256String
    idempotency_key: Sha256String
    source_periods: list[CandidateFinancialIndicatorComparisonSourcePeriod]
    net_interest_component_bridge: CandidateFinancialIndicatorNetInterestComponentBridge
    metrics: list[CandidateFinancialIndicatorPeriodComparisonMetric]

    @model_validator(mode="after")
    def validate_envelope(self) -> CandidateFinancialIndicatorPeriodComparisonEnvelope:
        if self.report_date != _month_end(self.report_month):
            raise ValueError("report_date must match report_month month-end")
        if _previous_month(self.report_month) != self.comparison_month:
            raise ValueError("comparison_month must be the exact previous calendar month")
        if _previous_month(self.comparison_month) != self.two_month_prior:
            raise ValueError("two_month_prior must be the exact previous calendar month")
        if [item.month for item in self.source_periods] != [
            self.report_month,
            self.comparison_month,
            self.two_month_prior,
        ]:
            raise ValueError("source_periods must contain the exact three months in order")

        actual_metrics = [(item.metric_id, item.basis, item.method) for item in self.metrics]
        if actual_metrics != list(EXPECTED_METRICS):
            raise ValueError("metrics must match the fixed seven-item comparison contract")
        lock_statuses = [item.lock_status for item in self.source_periods]
        if "locked_mismatch" in lock_statuses:
            raise ValueError("locked source mismatches cannot enter the comparison envelope")
        expected_quality = (
            "standard_candidate" if all(status == "locked_match" for status in lock_statuses) else "degraded_candidate"
        )
        if any(
            item.comparison_status == "comparable" and item.quality_status != expected_quality for item in self.metrics
        ):
            raise ValueError("comparable metric quality must match source lock evidence")
        bridge = self.net_interest_component_bridge
        expected_components = list(EXPECTED_NET_INTEREST_COMPONENTS)
        actual_components = [(item.metric_id, item.metric_name, item.formula_weight) for item in bridge.components]
        if actual_components != expected_components:
            raise ValueError("net-interest bridge must match the fixed four components")
        if bridge.status == "available" and bridge.quality_status != expected_quality:
            raise ValueError("available bridge quality must match source lock evidence")
        if bridge.status == "not_evaluable" and bridge.quality_status != "not_evaluable":
            raise ValueError("not-evaluable bridge cannot claim candidate quality")
        net_metric = next(item for item in self.metrics if item.metric_id == "income.interest.net")
        if bridge.net_delta_yi is not None:
            if net_metric.delta_yi is None or Decimal(bridge.net_delta_yi) != Decimal(net_metric.delta_yi):
                raise ValueError("bridge net delta must equal the outer net-interest delta")
        if bridge.status == "available" and net_metric.comparison_status != "comparable":
            raise ValueError("available bridge requires comparable outer net interest")
        self._validate_bridge_calendar_month_values()
        comparable_count = sum(item.comparison_status == "comparable" for item in self.metrics)
        expected_status = (
            "available"
            if comparable_count == len(EXPECTED_METRICS)
            else "unavailable"
            if comparable_count == 0
            else "partial"
        )
        if self.overall_status != expected_status:
            raise ValueError("overall_status must match comparable metric count")
        if self.full_scope_status == "available":
            if self.full_scope_reason_code != "available" or self.full_scope_gaps:
                raise ValueError("available full scope cannot carry blocking gaps")
        elif (
            self.full_scope_reason_code == "available"
            or not self.full_scope_gaps
            or any(item.month != self.comparison_month for item in self.full_scope_gaps)
            or any(item.reason_code != self.full_scope_reason_code for item in self.full_scope_gaps)
        ):
            raise ValueError("unavailable full scope requires controlled previous-month gaps")
        return self

    def _validate_bridge_calendar_month_values(self) -> None:
        month = int(self.report_month[4:])
        for component in self.net_interest_component_bridge.components:
            if component.current_value_yi is None:
                continue
            assert component.current_source_value_yi is not None
            assert component.previous_source_value_yi is not None
            assert component.two_month_prior_source_value_yi is not None
            current_source = Decimal(component.current_source_value_yi)
            previous_source = Decimal(component.previous_source_value_yi)
            two_month_prior_source = Decimal(component.two_month_prior_source_value_yi)
            if month == 1:
                expected_current = current_source
                expected_previous = previous_source - two_month_prior_source
            elif month == 2:
                expected_current = current_source - previous_source
                expected_previous = previous_source
            else:
                expected_current = current_source - previous_source
                expected_previous = previous_source - two_month_prior_source
            if Decimal(component.current_value_yi) != expected_current:
                raise ValueError("component current month must derive from cumulative sources")
            assert component.previous_value_yi is not None
            if Decimal(component.previous_value_yi) != expected_previous:
                raise ValueError("component previous month must derive from cumulative sources")


def _month_end(report_month: str) -> date:
    year = int(report_month[:4])
    month = int(report_month[4:])
    return date(year, month, monthrange(year, month)[1])


def _previous_month(report_month: str) -> str:
    year = int(report_month[:4])
    month = int(report_month[4:])
    if month == 1:
        return f"{year - 1:04d}12"
    return f"{year:04d}{month - 1:02d}"
