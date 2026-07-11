from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field, model_validator

LedgerPnlCurrencyBasis = Literal["CNX", "CNY"]
LedgerPnlAvailability = Literal["ready", "no_data"]
LedgerPnlMetricKey = Literal[
    "assets",
    "liabilities",
    "net_assets",
    "core_pnl",
    "all_pnl",
    "other_5_pnl",
]


class _StrictLedgerPnlAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LedgerPnlAnalysisMoney(_StrictLedgerPnlAnalysisModel):
    yuan: str = Field(pattern=r"^-?\d+(?:\.\d+)?$")
    yi: str = Field(pattern=r"^-?\d+(?:\.\d+)?$")

    @model_validator(mode="after")
    def validate_yuan_yi_consistency(self) -> LedgerPnlAnalysisMoney:
        expected_yi = (Decimal(self.yuan) / Decimal("100000000")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if Decimal(self.yi) != expected_yi:
            raise ValueError("yi must equal yuan converted to hundred-millions")
        return self


class LedgerPnlAnalysisBasisAvailability(_StrictLedgerPnlAnalysisModel):
    CNX: LedgerPnlAvailability
    CNY: LedgerPnlAvailability


class LedgerPnlAnalysisBasisEvidenceRows(_StrictLedgerPnlAnalysisModel):
    CNX: int = Field(ge=0)
    CNY: int = Field(ge=0)


class LedgerPnlAnalysisBridgeComponent(_StrictLedgerPnlAnalysisModel):
    metric_key: Literal["core_pnl", "other_5_pnl"]
    metric_name: str
    amount: LedgerPnlAnalysisMoney | None


class LedgerPnlAnalysisBridge(_StrictLedgerPnlAnalysisModel):
    components: list[LedgerPnlAnalysisBridgeComponent]
    total: LedgerPnlAnalysisMoney | None
    residual: LedgerPnlAnalysisMoney | None


class LedgerPnlAnalysisBasisComparisonRow(_StrictLedgerPnlAnalysisModel):
    metric_key: LedgerPnlMetricKey
    metric_name: str
    cnx: LedgerPnlAnalysisMoney | None
    cny: LedgerPnlAnalysisMoney | None
    cnx_minus_cny: LedgerPnlAnalysisMoney | None
    availability: LedgerPnlAnalysisBasisAvailability
    evidence_rows: LedgerPnlAnalysisBasisEvidenceRows

    @model_validator(mode="after")
    def validate_availability(self) -> LedgerPnlAnalysisBasisComparisonRow:
        for basis, amount in (("CNX", self.cnx), ("CNY", self.cny)):
            availability = getattr(self.availability, basis)
            evidence_rows = getattr(self.evidence_rows, basis)
            if availability == "ready" and (amount is None or evidence_rows == 0):
                raise ValueError(f"{basis} ready requires an amount and evidence rows")
            if availability == "no_data" and amount is not None:
                raise ValueError(f"{basis} no_data requires a null amount")

        both_ready = self.availability.CNX == "ready" and self.availability.CNY == "ready"
        if both_ready != (self.cnx_minus_cny is not None):
            raise ValueError("CNX - CNY is available only when both accounting bases are ready")
        return self


class LedgerPnlAnalysisConclusion(_StrictLedgerPnlAnalysisModel):
    direction: Literal["positive", "negative", "flat", "unavailable"]
    other_effect: Literal["support", "drag", "neutral", "unavailable"]
    core_pnl: LedgerPnlAnalysisMoney | None
    other_5_pnl: LedgerPnlAnalysisMoney | None
    all_pnl: LedgerPnlAnalysisMoney | None


class LedgerPnlAnalysisContributor(_StrictLedgerPnlAnalysisModel):
    rank: int = Field(ge=1)
    account_code: str = Field(pattern=r"^5[0-9]+$", max_length=32)
    account_name: str
    amount: LedgerPnlAnalysisMoney
    count: int = Field(ge=0)


class LedgerPnlAnalysisContributors(_StrictLedgerPnlAnalysisModel):
    positive_total: LedgerPnlAnalysisMoney | None
    negative_total: LedgerPnlAnalysisMoney | None
    net_total: LedgerPnlAnalysisMoney | None
    top_positive: list[LedgerPnlAnalysisContributor]
    top_negative: list[LedgerPnlAnalysisContributor]


class LedgerPnlAnalysisPeriodRow(_StrictLedgerPnlAnalysisModel):
    metric_key: Literal["core_pnl", "other_5_pnl", "all_pnl"]
    metric_name: str
    current: LedgerPnlAnalysisMoney
    previous: LedgerPnlAnalysisMoney
    change: LedgerPnlAnalysisMoney


class LedgerPnlAnalysisPeriodComparison(_StrictLedgerPnlAnalysisModel):
    status: Literal[
        "available",
        "no_previous_period",
        "current_basis_no_data",
        "previous_basis_no_data",
    ]
    previous_report_date: str | None
    previous_source_version: str | None
    rows: list[LedgerPnlAnalysisPeriodRow]

    @model_validator(mode="after")
    def validate_rows_for_status(self) -> LedgerPnlAnalysisPeriodComparison:
        if self.status == "available":
            if self.previous_report_date is None or self.previous_source_version is None:
                raise ValueError("available period comparison requires previous source metadata")
        elif self.rows:
            raise ValueError("unavailable period comparison must not contain metric rows")
        return self


class LedgerPnlAnalysisCalculationBasis(_StrictLedgerPnlAnalysisModel):
    core_pnl_prefixes: list[str]
    all_pnl_prefixes: list[str]
    other_5_pnl_formula: str
    other_5_pnl_boundary: str
    basis_difference_formula: str
    basis_boundary: str
    basis_availability_boundary: str
    previous_period_rule: str
    metric_boundary: str


class LedgerPnlAnalysisPayload(_StrictLedgerPnlAnalysisModel):
    report_date: str
    source_version: str
    currency_basis: LedgerPnlCurrencyBasis
    analysis_status: Literal["ready", "no_data"]
    metric_status: Literal["candidate"]
    basis_availability: LedgerPnlAnalysisBasisAvailability
    conclusion: LedgerPnlAnalysisConclusion
    pnl_bridge: LedgerPnlAnalysisBridge
    basis_comparison: list[LedgerPnlAnalysisBasisComparisonRow]
    contributors: LedgerPnlAnalysisContributors
    period_comparison: LedgerPnlAnalysisPeriodComparison
    calculation_basis: LedgerPnlAnalysisCalculationBasis

    @model_validator(mode="after")
    def validate_selected_basis_state(self) -> LedgerPnlAnalysisPayload:
        selected_availability = getattr(self.basis_availability, self.currency_basis)
        expected_status = "ready" if selected_availability == "ready" else "no_data"
        if self.analysis_status != expected_status:
            raise ValueError("analysis_status must match selected-basis PnL availability")

        conclusion_amounts = (
            self.conclusion.core_pnl,
            self.conclusion.other_5_pnl,
            self.conclusion.all_pnl,
        )
        bridge_amounts = (
            *(component.amount for component in self.pnl_bridge.components),
            self.pnl_bridge.total,
            self.pnl_bridge.residual,
        )
        contributor_totals = (
            self.contributors.positive_total,
            self.contributors.negative_total,
            self.contributors.net_total,
        )
        analytical_amounts = conclusion_amounts + bridge_amounts + contributor_totals
        if self.analysis_status == "ready":
            if any(amount is None for amount in analytical_amounts):
                raise ValueError("ready analysis requires all selected-basis amounts")
        else:
            if any(amount is not None for amount in analytical_amounts):
                raise ValueError("no_data analysis requires null selected-basis amounts")
            if self.contributors.top_positive or self.contributors.top_negative:
                raise ValueError("no_data analysis must not rank contributors")
        return self


class LedgerPnlAnalysisFilters(_StrictLedgerPnlAnalysisModel):
    report_date: str
    currency: LedgerPnlCurrencyBasis
    currency_basis: LedgerPnlCurrencyBasis
    currency_basis_note: str

    @model_validator(mode="after")
    def validate_basis_aliases(self) -> LedgerPnlAnalysisFilters:
        if self.currency != self.currency_basis:
            raise ValueError("currency and currency_basis must identify the same accounting basis")
        return self


class LedgerPnlAnalysisNextDrill(_StrictLedgerPnlAnalysisModel):
    label: str
    detail: str


class LedgerPnlAnalysisResultMeta(ResultMeta):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["ledger"] = "ledger"
    result_kind: Literal["ledger_pnl.analysis"] = "ledger_pnl.analysis"
    formal_use_allowed: Literal[False] = False
    date_basis: Literal["ledger_report_date"] = "ledger_report_date"
    filters_applied: LedgerPnlAnalysisFilters
    evidence_rows: int | None = Field(default=None, ge=0)
    next_drill: list[LedgerPnlAnalysisNextDrill] = Field(default_factory=list)


class LedgerPnlAnalysisEnvelope(_StrictLedgerPnlAnalysisModel):
    result_meta: LedgerPnlAnalysisResultMeta
    result: LedgerPnlAnalysisPayload


class LedgerPnlAccountDetailAccount(_StrictLedgerPnlAnalysisModel):
    account_code: str = Field(pattern=r"^5[0-9]+$", max_length=32)
    account_name: str | None


class LedgerPnlAccountDetailPeriodComparison(_StrictLedgerPnlAnalysisModel):
    status: Literal[
        "available",
        "current_account_no_data",
        "no_previous_period",
        "previous_account_no_data",
    ]
    previous_report_date: str | None
    previous_source_version: str | None
    current_monthly_pnl: LedgerPnlAnalysisMoney | None
    previous_monthly_pnl: LedgerPnlAnalysisMoney | None
    change: LedgerPnlAnalysisMoney | None
    current_evidence_rows: int = Field(ge=0)
    previous_evidence_rows: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_status_and_amounts(self) -> LedgerPnlAccountDetailPeriodComparison:
        current_ready = self.current_evidence_rows > 0
        previous_ready = self.previous_evidence_rows > 0
        if current_ready != (self.current_monthly_pnl is not None):
            raise ValueError("current amount availability must match current evidence rows")
        if previous_ready != (self.previous_monthly_pnl is not None):
            raise ValueError("previous amount availability must match previous evidence rows")

        has_previous_metadata = self.previous_report_date is not None
        if has_previous_metadata != (self.previous_source_version is not None):
            raise ValueError("previous report date and source version must be provided together")
        if previous_ready and not has_previous_metadata:
            raise ValueError("previous evidence requires previous source metadata")

        if not current_ready:
            expected_status = "current_account_no_data"
        elif not has_previous_metadata:
            expected_status = "no_previous_period"
        elif not previous_ready:
            expected_status = "previous_account_no_data"
        else:
            expected_status = "available"
        if self.status != expected_status:
            raise ValueError("period comparison status does not match evidence availability")

        if self.status == "available":
            if self.change is None:
                raise ValueError("available comparison requires a change amount")
            expected_change = (
                Decimal(self.current_monthly_pnl.yuan)
                - Decimal(self.previous_monthly_pnl.yuan)
            )
            if Decimal(self.change.yuan) != expected_change:
                raise ValueError("change must equal current monthly PnL minus previous monthly PnL")
        elif self.change is not None:
            raise ValueError("unavailable comparison requires a null change")
        return self


class LedgerPnlAccountDetailBasisSnapshot(_StrictLedgerPnlAnalysisModel):
    report_date: str
    source_version: str
    cnx: LedgerPnlAnalysisMoney | None
    cny: LedgerPnlAnalysisMoney | None
    cnx_minus_cny: LedgerPnlAnalysisMoney | None
    availability: LedgerPnlAnalysisBasisAvailability
    evidence_rows: LedgerPnlAnalysisBasisEvidenceRows

    @model_validator(mode="after")
    def validate_basis_availability(self) -> LedgerPnlAccountDetailBasisSnapshot:
        for basis, amount in (("CNX", self.cnx), ("CNY", self.cny)):
            ready = getattr(self.availability, basis) == "ready"
            evidence_rows = getattr(self.evidence_rows, basis)
            if ready != (amount is not None and evidence_rows > 0):
                raise ValueError(f"{basis} availability must match amount and evidence rows")
            if not ready and evidence_rows != 0:
                raise ValueError(f"{basis} no_data requires zero evidence rows")

        both_ready = self.cnx is not None and self.cny is not None
        if both_ready != (self.cnx_minus_cny is not None):
            raise ValueError("CNX - CNY is available only when both bases are ready")
        if both_ready:
            expected_difference = Decimal(self.cnx.yuan) - Decimal(self.cny.yuan)
            if Decimal(self.cnx_minus_cny.yuan) != expected_difference:
                raise ValueError("CNX - CNY amount is inconsistent")
        return self


class LedgerPnlAccountDetailBasisComparison(_StrictLedgerPnlAnalysisModel):
    current: LedgerPnlAccountDetailBasisSnapshot
    previous: LedgerPnlAccountDetailBasisSnapshot | None


class LedgerPnlAccountDetailEvidenceRow(_StrictLedgerPnlAnalysisModel):
    period: Literal["current", "previous"]
    report_date: str
    source_version: str
    account_code: str = Field(pattern=r"^5[0-9]+$", max_length=32)
    account_name: str
    currency: LedgerPnlCurrencyBasis
    beginning_balance: LedgerPnlAnalysisMoney
    ending_balance: LedgerPnlAnalysisMoney
    monthly_pnl: LedgerPnlAnalysisMoney
    days_in_period: int = Field(ge=1, le=31)


class LedgerPnlAccountDetailCalculationBasis(_StrictLedgerPnlAnalysisModel):
    account_match: Literal["exact"]
    amount_field: Literal["monthly_pnl"]
    change_formula: Literal["current_monthly_pnl - previous_monthly_pnl"]
    basis_difference_formula: Literal["CNX - CNY"]
    basis_boundary: str
    previous_period_rule: str
    evidence_boundary: str
    metric_boundary: str


class LedgerPnlAccountDetailPayload(_StrictLedgerPnlAnalysisModel):
    report_date: str
    source_version: str
    currency_basis: LedgerPnlCurrencyBasis
    analysis_status: Literal["ready", "no_data"]
    metric_status: Literal["candidate"]
    account: LedgerPnlAccountDetailAccount
    period_comparison: LedgerPnlAccountDetailPeriodComparison
    basis_comparison: LedgerPnlAccountDetailBasisComparison
    canonical_evidence_rows: list[LedgerPnlAccountDetailEvidenceRow]
    calculation_basis: LedgerPnlAccountDetailCalculationBasis

    @model_validator(mode="after")
    def validate_cross_section_consistency(self) -> LedgerPnlAccountDetailPayload:
        current = self.basis_comparison.current
        if current.report_date != self.report_date or current.source_version != self.source_version:
            raise ValueError("current basis snapshot must match the payload source")

        selected_amount = self.cnx_or_cny(current)
        selected_evidence_rows = getattr(current.evidence_rows, self.currency_basis)
        expected_analysis_status = "ready" if selected_amount is not None else "no_data"
        if self.analysis_status != expected_analysis_status:
            raise ValueError("analysis status must match selected-basis availability")
        if self.period_comparison.current_monthly_pnl != selected_amount:
            raise ValueError("period current amount must match selected current basis")
        if self.period_comparison.current_evidence_rows != selected_evidence_rows:
            raise ValueError("period current evidence must match selected current basis")

        previous = self.basis_comparison.previous
        if previous is None:
            if (
                self.period_comparison.previous_report_date is not None
                or self.period_comparison.previous_source_version is not None
            ):
                raise ValueError("missing previous snapshot requires null previous metadata")
        else:
            if (
                previous.report_date != self.period_comparison.previous_report_date
                or previous.source_version != self.period_comparison.previous_source_version
            ):
                raise ValueError("previous basis snapshot must match period metadata")
            previous_amount = self.cnx_or_cny(previous)
            previous_evidence_rows = getattr(previous.evidence_rows, self.currency_basis)
            if self.period_comparison.previous_monthly_pnl != previous_amount:
                raise ValueError("period previous amount must match selected previous basis")
            if self.period_comparison.previous_evidence_rows != previous_evidence_rows:
                raise ValueError("period previous evidence must match selected previous basis")

        evidence_counts = {
            (period, basis): 0
            for period in ("current", "previous")
            for basis in ("CNX", "CNY")
        }
        evidence_amounts = {
            (period, basis): Decimal("0")
            for period in ("current", "previous")
            for basis in ("CNX", "CNY")
        }
        for row in self.canonical_evidence_rows:
            if row.account_code != self.account.account_code:
                raise ValueError("canonical evidence must use the requested exact account code")
            if row.period == "current":
                if row.report_date != self.report_date or row.source_version != self.source_version:
                    raise ValueError("current evidence must match the current payload source")
            elif previous is None or (
                row.report_date != previous.report_date
                or row.source_version != previous.source_version
            ):
                raise ValueError("previous evidence must match the previous basis snapshot")
            evidence_counts[(row.period, row.currency)] += 1
            evidence_amounts[(row.period, row.currency)] += Decimal(
                row.monthly_pnl.yuan
            )

        for basis in ("CNX", "CNY"):
            if evidence_counts[("current", basis)] != getattr(current.evidence_rows, basis):
                raise ValueError("current canonical evidence count is inconsistent")
            current_amount = current.cnx if basis == "CNX" else current.cny
            if current_amount is not None and Decimal(current_amount.yuan) != evidence_amounts[
                ("current", basis)
            ]:
                raise ValueError("current snapshot must equal the canonical evidence amount")
            expected_previous_rows = (
                getattr(previous.evidence_rows, basis) if previous is not None else 0
            )
            if evidence_counts[("previous", basis)] != expected_previous_rows:
                raise ValueError("previous canonical evidence count is inconsistent")
            previous_amount = (
                previous.cnx if previous is not None and basis == "CNX"
                else previous.cny if previous is not None
                else None
            )
            if previous_amount is not None and Decimal(
                previous_amount.yuan
            ) != evidence_amounts[("previous", basis)]:
                raise ValueError("previous snapshot must equal the canonical evidence amount")
        return self

    def cnx_or_cny(
        self,
        snapshot: LedgerPnlAccountDetailBasisSnapshot,
    ) -> LedgerPnlAnalysisMoney | None:
        return snapshot.cnx if self.currency_basis == "CNX" else snapshot.cny


class LedgerPnlAccountDetailFilters(_StrictLedgerPnlAnalysisModel):
    report_date: str
    account_code: str = Field(pattern=r"^5[0-9]+$", max_length=32)
    currency: LedgerPnlCurrencyBasis
    currency_basis: LedgerPnlCurrencyBasis
    currency_basis_note: str

    @model_validator(mode="after")
    def validate_basis_aliases(self) -> LedgerPnlAccountDetailFilters:
        if self.currency != self.currency_basis:
            raise ValueError("currency and currency_basis must identify the same accounting basis")
        return self


class LedgerPnlAccountDetailResultMeta(ResultMeta):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["ledger"] = "ledger"
    result_kind: Literal["ledger_pnl.account_detail"] = "ledger_pnl.account_detail"
    formal_use_allowed: Literal[False] = False
    date_basis: Literal["ledger_report_date"] = "ledger_report_date"
    filters_applied: LedgerPnlAccountDetailFilters
    evidence_rows: int = Field(ge=0)
    next_drill: list[LedgerPnlAnalysisNextDrill] = Field(default_factory=list)


class LedgerPnlAccountDetailEnvelope(_StrictLedgerPnlAnalysisModel):
    result_meta: LedgerPnlAccountDetailResultMeta
    result: LedgerPnlAccountDetailPayload

    @model_validator(mode="after")
    def validate_meta_matches_result(self) -> LedgerPnlAccountDetailEnvelope:
        meta = self.result_meta
        result = self.result
        filters = meta.filters_applied
        if (
            meta.source_version != result.source_version
            or meta.resolved_report_date != result.report_date
            or meta.as_of_date != result.report_date
        ):
            raise ValueError("result metadata must match the current result source")
        if (
            filters.report_date != result.report_date
            or filters.account_code != result.account.account_code
            or filters.currency_basis != result.currency_basis
        ):
            raise ValueError("applied filters must match the account detail result")
        if meta.evidence_rows != result.period_comparison.current_evidence_rows:
            raise ValueError("meta evidence rows must count the selected current basis")
        return self
