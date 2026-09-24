"""Strict contract for lazy net-interest component account detail."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Literal

from backend.app.schemas.candidate_financial_indicator_period_comparison import (
    CandidateFinancialIndicatorComparisonSourcePeriod,
    DecimalString,
    ReportMonth,
    Sha256String,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

COMPONENTS = {
    "income.interest.loan.total": ("贷款利息收入", 1),
    "expense.interest.deposit.total": ("存款利息支出", -1),
    "income.interest.investment": ("金融投资利息收入", 1),
    "income.interest.interbank_net": ("同业资产负债利息净收入", 1),
}
ComponentMetricId = Literal[
    "income.interest.loan.total",
    "expense.interest.deposit.total",
    "income.interest.investment",
    "income.interest.interbank_net",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateFinancialIndicatorComponentMatchedTerm(_StrictModel):
    source: Literal["ledger"]
    level: Literal["l1", "l2", "l3", "full"]
    code: str = Field(pattern=r"^[0-9]+$", min_length=3, max_length=11)
    weight: DecimalString


class CandidateFinancialIndicatorComponentSourceEvidence(_StrictModel):
    month: ReportMonth
    report_date: date
    ledger_file_name: str = Field(min_length=1)
    ledger_sha256: Sha256String
    locked_sha256: Sha256String | None
    lock_status: Literal["locked_match", "unlocked"]
    sheet: Literal["综本"]
    row: int = Field(ge=1)
    account_code_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    ending_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    ending_yuan: DecimalString

    @model_validator(mode="after")
    def validate_locator(self) -> CandidateFinancialIndicatorComponentSourceEvidence:
        month_end = date(
            int(self.month[:4]),
            int(self.month[4:]),
            monthrange(int(self.month[:4]), int(self.month[4:]))[1],
        )
        if self.report_date != month_end:
            raise ValueError("source evidence report date must match its month")
        if self.ledger_file_name != f"总账对账{self.month}.xlsx":
            raise ValueError("source evidence file must match its month")
        expected_lock = (
            "unlocked"
            if self.locked_sha256 is None
            else "locked_match"
            if self.locked_sha256 == self.ledger_sha256
            else "locked_mismatch"
        )
        if self.lock_status != expected_lock:
            raise ValueError("source evidence lock status is inconsistent")
        if not self.account_code_cell.endswith(str(self.row)) or not self.ending_cell.endswith(
            str(self.row)
        ):
            raise ValueError("source row locator cells must match row")
        return self


class CandidateFinancialIndicatorComponentDetailRow(_StrictModel):
    row_status: Literal["contributing", "excluded_offset"]
    account_code: str = Field(pattern=r"^5[0-9]{10}$")
    account_name: str
    currency: Literal["CNX"]
    effective_component_weight: DecimalString
    effective_net_weight: DecimalString
    matched_terms: list[CandidateFinancialIndicatorComponentMatchedTerm] = Field(
        min_length=1
    )
    current_ending_yuan: DecimalString
    previous_ending_yuan: DecimalString
    two_month_prior_ending_yuan: DecimalString
    current_value_yi: DecimalString
    previous_value_yi: DecimalString
    component_delta_yi: DecimalString
    contribution_to_net_delta_yi: DecimalString
    source_evidence: list[CandidateFinancialIndicatorComponentSourceEvidence] = Field(
        min_length=3,
        max_length=3,
    )

    @model_validator(mode="after")
    def validate_row(self) -> CandidateFinancialIndicatorComponentDetailRow:
        effective_weight = sum(
            (Decimal(item.weight) for item in self.matched_terms),
            Decimal(0),
        )
        if Decimal(self.effective_component_weight) != effective_weight:
            raise ValueError("effective component weight must sum matched terms")
        lengths = {"l1": 3, "l2": 5, "l3": 7}
        if any(
            self.account_code != item.code
            if item.level == "full"
            else self.account_code[: lengths[item.level]] != item.code
            for item in self.matched_terms
        ):
            raise ValueError("matched terms must identify the exact account")
        values = (
            Decimal(self.current_value_yi),
            Decimal(self.previous_value_yi),
            Decimal(self.component_delta_yi),
            Decimal(self.contribution_to_net_delta_yi),
        )
        if self.row_status == "contributing" and effective_weight == 0:
            raise ValueError("contributing row requires a non-zero effective weight")
        if self.row_status == "excluded_offset" and (
            effective_weight != 0 or any(value != 0 for value in values)
        ):
            raise ValueError("excluded offset row requires zero effective values")
        endings = (
            self.current_ending_yuan,
            self.previous_ending_yuan,
            self.two_month_prior_ending_yuan,
        )
        if tuple(item.ending_yuan for item in self.source_evidence) != endings:
            raise ValueError("source evidence ending amounts must match the row")
        return self


class CandidateFinancialIndicatorComponentDetailEnvelope(_StrictModel):
    contract_version: Literal["candidate-financial-indicator-component-detail-v1"]
    analysis_kind: Literal["accounting_component_account_detail"]
    report_month: ReportMonth
    report_date: date
    comparison_month: ReportMonth
    two_month_prior: ReportMonth
    metric_id: ComponentMetricId
    metric_name: str = Field(min_length=1)
    formula_weight: Literal[-1, 1]
    currency: Literal["CNX"]
    basis: Literal["calendar_month_from_cumulative"]
    method: Literal["finance_metric_account_contribution"]
    unit: Literal["亿元"]
    status: Literal["available", "not_evaluable", "stale_parent"]
    quality_status: Literal[
        "standard_candidate",
        "degraded_candidate",
        "not_evaluable",
    ]
    foot_status: Literal["passed", "failed", "not_evaluable"]
    formal_use_allowed: Literal[False]
    certification_effect: Literal["none"]
    driver_status: Literal["unclear"]
    rule_version: Literal["qdb-finance-2026-v1.0.1"]
    rule_hash: Sha256String
    parent_idempotency_key: Sha256String
    idempotency_key: Sha256String
    source_periods: list[CandidateFinancialIndicatorComparisonSourcePeriod] = Field(
        min_length=3,
        max_length=3,
    )
    parent_current_value_yi: DecimalString | None
    parent_previous_value_yi: DecimalString | None
    parent_component_delta_yi: DecimalString | None
    parent_contribution_to_net_delta_yi: DecimalString | None
    account_current_total_yi: DecimalString | None
    account_previous_total_yi: DecimalString | None
    account_component_delta_total_yi: DecimalString | None
    account_contribution_total_yi: DecimalString | None
    current_reconciliation_yi: DecimalString | None
    previous_reconciliation_yi: DecimalString | None
    component_delta_reconciliation_yi: DecimalString | None
    contribution_reconciliation_yi: DecimalString | None
    reasons: list[str]
    rows: list[CandidateFinancialIndicatorComponentDetailRow]

    @model_validator(mode="after")
    def validate_envelope(
        self,
    ) -> CandidateFinancialIndicatorComponentDetailEnvelope:
        expected_name, expected_weight = COMPONENTS[self.metric_id]
        if (self.metric_name, self.formula_weight) != (
            expected_name,
            expected_weight,
        ):
            raise ValueError("component identity must match the fixed contract")
        if self.report_date != _month_end(self.report_month):
            raise ValueError("report date must match report month")
        if self.comparison_month != _previous_month(self.report_month) or self.two_month_prior != _previous_month(
            self.comparison_month
        ):
            raise ValueError("component detail requires exact adjacent calendar months")
        expected_months = [
            self.report_month,
            self.comparison_month,
            self.two_month_prior,
        ]
        if [item.month for item in self.source_periods] != expected_months:
            raise ValueError("source periods must contain the exact three months")
        if any(item.lock_status == "locked_mismatch" for item in self.source_periods):
            raise ValueError("locked source mismatch is forbidden")
        all_values = (
            self.parent_current_value_yi,
            self.parent_previous_value_yi,
            self.parent_component_delta_yi,
            self.parent_contribution_to_net_delta_yi,
            self.account_current_total_yi,
            self.account_previous_total_yi,
            self.account_component_delta_total_yi,
            self.account_contribution_total_yi,
            self.current_reconciliation_yi,
            self.previous_reconciliation_yi,
            self.component_delta_reconciliation_yi,
            self.contribution_reconciliation_yi,
        )
        if self.status == "stale_parent":
            if self.quality_status != "not_evaluable" or self.foot_status != "not_evaluable":
                raise ValueError("stale parent cannot claim evaluable quality")
            if self.rows or any(value is not None for value in all_values):
                raise ValueError("stale parent requires an empty explanation")
            if not self.reasons:
                raise ValueError("stale parent requires a reason")
            return self

        parent_values = all_values[:4]
        if all(value is None for value in parent_values):
            if (
                self.status != "not_evaluable"
                or self.quality_status != "not_evaluable"
                or self.foot_status != "not_evaluable"
                or self.rows
                or any(value is not None for value in all_values[4:])
                or not self.reasons
            ):
                raise ValueError("unavailable parent component requires an empty detail")
            return self
        if any(value is None for value in parent_values):
            raise ValueError("parent component values must be all present or all null")
        parent_current, parent_previous, parent_delta, parent_contribution = (
            Decimal(value) for value in parent_values if value is not None
        )
        if parent_delta != parent_current - parent_previous:
            raise ValueError("parent component delta is inconsistent")
        if parent_contribution != parent_delta * Decimal(self.formula_weight):
            raise ValueError("parent component contribution is inconsistent")

        if self.foot_status == "not_evaluable":
            if self.status != "not_evaluable" or self.quality_status != "not_evaluable":
                raise ValueError("non-evaluable foot requires non-evaluable status")
            if self.rows or any(value is not None for value in all_values[4:]):
                raise ValueError("non-evaluable detail must not expose partial account values")
            if not self.reasons:
                raise ValueError("non-evaluable detail requires a reason")
            return self

        if self.foot_status == "failed":
            account_totals = all_values[4:8]
            reconciliation_values = all_values[8:]
            if (
                self.status != "not_evaluable"
                or self.quality_status != "not_evaluable"
                or self.rows
                or any(value is not None for value in account_totals)
                or any(value is None for value in reconciliation_values)
                or not any(
                    Decimal(value) != 0
                    for value in reconciliation_values
                    if value is not None
                )
                or not self.reasons
            ):
                raise ValueError("failed foot must hide account explanation")
            return self

        if self.status != "available":
            raise ValueError("passed foot requires available status")

        if any(value is None for value in all_values):
            raise ValueError("evaluated foot requires complete values")
        self._validate_rows_and_sources()
        account_values = tuple(Decimal(value) for value in all_values[4:8] if value is not None)
        reconciliations = tuple(Decimal(value) for value in all_values[8:] if value is not None)
        contributing = [item for item in self.rows if item.row_status == "contributing"]
        row_totals = (
            sum((Decimal(item.current_value_yi) for item in contributing), Decimal(0)),
            sum((Decimal(item.previous_value_yi) for item in contributing), Decimal(0)),
            sum((Decimal(item.component_delta_yi) for item in contributing), Decimal(0)),
            sum(
                (Decimal(item.contribution_to_net_delta_yi) for item in contributing),
                Decimal(0),
            ),
        )
        if account_values != row_totals:
            raise ValueError("account totals must equal contributing rows")
        expected_reconciliations = tuple(
            parent_value - account_value
            for parent_value, account_value in zip(
                (parent_current, parent_previous, parent_delta, parent_contribution),
                account_values,
                strict=True,
            )
        )
        if reconciliations != expected_reconciliations:
            raise ValueError("account reconciliation values are inconsistent")
        passed = all(value == 0 for value in reconciliations)
        if self.status == "available":
            expected_quality = (
                "standard_candidate"
                if all(item.lock_status == "locked_match" for item in self.source_periods)
                else "degraded_candidate"
            )
            if (
                self.foot_status != "passed"
                or not passed
                or self.quality_status != expected_quality
                or self.reasons
            ):
                raise ValueError("available detail requires an exact passed foot")
        return self

    def _validate_rows_and_sources(self) -> None:
        expected_months = [item.month for item in self.source_periods]
        previous_sort_key: tuple[int, Decimal, str] | None = None
        for row in self.rows:
            if Decimal(row.effective_net_weight) != Decimal(
                row.effective_component_weight
            ) * Decimal(self.formula_weight):
                raise ValueError("effective net weight must apply the bridge weight")
            if [item.month for item in row.source_evidence] != expected_months:
                raise ValueError("row source evidence must follow the three periods")
            for evidence, source in zip(
                row.source_evidence,
                self.source_periods,
                strict=True,
            ):
                if (
                    evidence.report_date != source.report_date
                    or evidence.ledger_file_name != source.ledger_file_name
                    or evidence.ledger_sha256 != source.ledger_sha256
                    or evidence.locked_sha256 != source.locked_sha256
                    or evidence.lock_status != source.lock_status
                ):
                    raise ValueError("source evidence must match source periods")
            current_ending = Decimal(row.current_ending_yuan)
            previous_ending = Decimal(row.previous_ending_yuan)
            two_prior_ending = Decimal(row.two_month_prior_ending_yuan)
            month = int(self.report_month[4:])
            if month == 1:
                current_raw = current_ending
                previous_raw = previous_ending - two_prior_ending
            elif month == 2:
                current_raw = current_ending - previous_ending
                previous_raw = previous_ending
            else:
                current_raw = current_ending - previous_ending
                previous_raw = previous_ending - two_prior_ending
            weight = Decimal(row.effective_component_weight)
            expected_current = current_raw * weight / Decimal("100000000")
            expected_previous = previous_raw * weight / Decimal("100000000")
            if (
                Decimal(row.current_value_yi) != expected_current
                or Decimal(row.previous_value_yi) != expected_previous
            ):
                raise ValueError("calendar-month row values must derive from cumulative endings")
            expected_delta = expected_current - expected_previous
            if Decimal(row.component_delta_yi) != expected_delta:
                raise ValueError("row component delta must equal current minus previous")
            if Decimal(row.contribution_to_net_delta_yi) != expected_delta * Decimal(
                self.formula_weight
            ):
                raise ValueError("row contribution must apply the bridge weight")
            sort_key = (
                0 if row.row_status == "contributing" else 1,
                -abs(Decimal(row.contribution_to_net_delta_yi)),
                row.account_code,
            )
            if previous_sort_key is not None and sort_key < previous_sort_key:
                raise ValueError("rows must be ordered by unrounded contribution")
            previous_sort_key = sort_key


def _month_end(report_month: str) -> date:
    year = int(report_month[:4])
    month = int(report_month[4:])
    return date(year, month, monthrange(year, month)[1])


def _previous_month(report_month: str) -> str:
    year = int(report_month[:4])
    month = int(report_month[4:])
    return f"{year - 1:04d}12" if month == 1 else f"{year:04d}{month - 1:02d}"
