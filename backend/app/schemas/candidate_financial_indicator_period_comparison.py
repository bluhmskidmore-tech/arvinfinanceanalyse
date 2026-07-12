"""Strict response contract for candidate key-metric period comparison."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
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
            else (
                "locked_match"
                if self.ledger_sha256 == self.locked_sha256
                else "locked_mismatch"
            )
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
    two_month_prior_metric_status: (
        Literal["ok", "warning", "manual_default", "error", "missing"] | None
    )
    current_value_yi: DecimalString | None
    previous_value_yi: DecimalString | None
    current_source_value_yi: DecimalString | None
    previous_source_value_yi: DecimalString | None
    two_month_prior_source_value_yi: DecimalString | None
    delta_yi: DecimalString | None
    change_rate: DecimalString | None
    rate_reason: Literal[
        "zero_denominator",
        "missing_reference",
        "metric_status_not_ok",
    ] | None
    reasons: list[str]
    driver_status: Literal["unclear"]
    quality_status: Literal[
        "standard_candidate", "degraded_candidate", "not_comparable"
    ]

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
            if (
                self.current_source_value_yi is None
                or self.previous_source_value_yi is None
            ):
                raise ValueError("comparable metric requires current and previous source values")
            if (
                self.basis == "calendar_month_from_cumulative"
                and self.two_month_prior_source_value_yi is None
            ):
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
        if (self.reason_code == "missing_required_sheet") != (
            self.required_sheet is not None
        ):
            raise ValueError("required_sheet is exclusive to missing_required_sheet")
        return self


class CandidateFinancialIndicatorPeriodComparisonEnvelope(_StrictModel):
    contract_version: Literal[
        "candidate-financial-indicator-period-comparison-v1"
    ]
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

        actual_metrics = [
            (item.metric_id, item.basis, item.method) for item in self.metrics
        ]
        if actual_metrics != list(EXPECTED_METRICS):
            raise ValueError("metrics must match the fixed seven-item comparison contract")
        lock_statuses = [item.lock_status for item in self.source_periods]
        if "locked_mismatch" in lock_statuses:
            raise ValueError("locked source mismatches cannot enter the comparison envelope")
        expected_quality = (
            "standard_candidate"
            if all(status == "locked_match" for status in lock_statuses)
            else "degraded_candidate"
        )
        if any(
            item.comparison_status == "comparable"
            and item.quality_status != expected_quality
            for item in self.metrics
        ):
            raise ValueError("comparable metric quality must match source lock evidence")
        comparable_count = sum(
            item.comparison_status == "comparable" for item in self.metrics
        )
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
            or any(
                item.reason_code != self.full_scope_reason_code
                for item in self.full_scope_gaps
            )
        ):
            raise ValueError("unavailable full scope requires controlled previous-month gaps")
        return self


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
