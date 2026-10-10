"""Response models for the ledger-basis PnL read surfaces.

Scope is deliberately the four `/api/ledger-pnl/*` reads whose full runtime
shape is observable end to end: `dates`, `data`, `summary` and
`monthly-analysis/dates`. Each model was derived from the payload the service
actually returns in both the populated and the empty-source branch, not from
reading the builder.

`extra="forbid"` is the point of the exercise: FastAPI drops any key the model
does not declare, silently, with a 200. On a PnL surface a silently missing
number is worse than an outage, so an undeclared key must fail loudly instead.

The money shape is `LedgerPnlAnalysisMoney`, the same strict `{yuan, yi}`
contract already enforced on `/api/ledger-pnl/analysis` and `/account-detail`.
"""
from __future__ import annotations

from typing import Literal

from backend.app.schemas.ledger_pnl_analysis import LedgerPnlAnalysisMoney
from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictLedgerPnlReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LedgerPnlDatesPayload(_StrictLedgerPnlReadModel):
    dates: list[str]


class LedgerPnlDatesEnvelope(_StrictLedgerPnlReadModel):
    result_meta: ResultMeta
    result: LedgerPnlDatesPayload


class LedgerPnlDataRow(_StrictLedgerPnlReadModel):
    account_code: str
    account_name: str
    currency: str
    beginning_balance: LedgerPnlAnalysisMoney
    ending_balance: LedgerPnlAnalysisMoney
    # Source formula is period credit - period debit. It is signed PnL only for
    # 5* accounts; for other ledger accounts it is the month's net activity.
    monthly_pnl: LedgerPnlAnalysisMoney
    daily_avg_balance: LedgerPnlAnalysisMoney
    days_in_period: int
    # "ledger" = 总账工作簿真实观测行；"average_only" = 仅日均工作簿存在、
    # 总账侧填 0 的合成行（PRD 2026-08-26 R1 冻结契约）。
    source_presence: Literal["ledger", "average_only"]


class LedgerPnlDataSummary(_StrictLedgerPnlReadModel):
    total_pnl_cnx: LedgerPnlAnalysisMoney
    total_pnl_cny: LedgerPnlAnalysisMoney
    total_pnl: LedgerPnlAnalysisMoney
    # `count` covers every detail row (union caliber, unchanged semantics);
    # `pnl_account_count` is the 5* population used by the three total_pnl
    # fields above.
    count: int
    pnl_account_count: int
    # R1 冻结契约：总账真实观测行数 / 日均侧合成行数，恒等于 count。
    ledger_evidence_rows: int = Field(ge=0)
    average_only_row_count: int = Field(ge=0)
    # 说明字段：声明 count/evidence_rows 的并集口径，避免行数被误读为总账行数。
    evidence_rows_basis: str

    @model_validator(mode="after")
    def validate_source_presence_identity(self) -> LedgerPnlDataSummary:
        if self.ledger_evidence_rows + self.average_only_row_count != self.count:
            raise ValueError(
                "ledger_evidence_rows + average_only_row_count must equal count"
            )
        return self


class LedgerPnlDataPayload(_StrictLedgerPnlReadModel):
    data_status: str
    report_date: str
    source_version: str
    items: list[LedgerPnlDataRow]
    summary: LedgerPnlDataSummary


class LedgerPnlDataEnvelope(_StrictLedgerPnlReadModel):
    result_meta: ResultMeta
    result: LedgerPnlDataPayload


class LedgerPnlSummaryByCurrency(_StrictLedgerPnlReadModel):
    currency: str
    total_pnl: LedgerPnlAnalysisMoney


class LedgerPnlSummaryByAccount(_StrictLedgerPnlReadModel):
    account_code: str
    account_name: str
    total_pnl: LedgerPnlAnalysisMoney
    count: int


class LedgerPnlSummaryPayload(_StrictLedgerPnlReadModel):
    # `GS-LEDGER-PNL-SUMMARY-A` was captured before `data_status` existed, so the
    # field is optional here and the route serializes with `exclude_unset` to
    # keep "absent" distinct from "null".
    data_status: str | None = None
    report_date: str
    source_version: str
    ledger_total_assets: LedgerPnlAnalysisMoney
    ledger_total_liabilities: LedgerPnlAnalysisMoney
    ledger_net_assets: LedgerPnlAnalysisMoney
    ledger_monthly_pnl_core: LedgerPnlAnalysisMoney
    ledger_monthly_pnl_all: LedgerPnlAnalysisMoney
    by_currency: list[LedgerPnlSummaryByCurrency]
    by_account: list[LedgerPnlSummaryByAccount]


class LedgerPnlSummaryEnvelope(_StrictLedgerPnlReadModel):
    result_meta: ResultMeta
    result: LedgerPnlSummaryPayload


class LedgerFinancialIndicatorPeriod(_StrictLedgerPnlReadModel):
    period_id: str
    flow_label: str
    flow_compare_label: str
    point_label: str
    point_compare_label: str
    current_month: str
    flow_compare_month: str
    point_compare_month: str
    current_available: bool
    flow_compare_available: bool
    point_compare_available: bool


class LedgerFinancialIndicatorCell(_StrictLedgerPnlReadModel):
    # Amounts are decimal strings; `None` means "no system source", which is a
    # governed state and must never be rendered as zero.
    period_id: str
    current: str | None = None
    compare: str | None = None
    delta: str | None = None
    delta_pct: str | None = None


class LedgerFinancialIndicatorRow(_StrictLedgerPnlReadModel):
    row_id: str
    name: str
    indent: int
    basis: str
    value_kind: str
    availability: str
    caliber_note: str | None = None
    unavailable_reason: str | None = None
    account_evidence: str | None = None
    values: list[LedgerFinancialIndicatorCell]


class LedgerFinancialIndicatorSection(_StrictLedgerPnlReadModel):
    section_id: str
    title: str
    basis_note: str
    rows: list[LedgerFinancialIndicatorRow]


class LedgerFinancialIndicatorCoverage(_StrictLedgerPnlReadModel):
    row_total: int
    row_computed: int
    row_unavailable: int


class LedgerFinancialIndicatorQualityCheck(_StrictLedgerPnlReadModel):
    check_id: str
    month: str
    passed: bool
    gap_yuan: str
    message: str


class LedgerFinancialIndicatorSourceFile(_StrictLedgerPnlReadModel):
    month: str
    file_name: str
    source_version: str


class LedgerFinancialIndicatorSummaryPayload(_StrictLedgerPnlReadModel):
    contract_version: str
    title: str
    report_month: str
    report_year: int
    currency_basis: str
    unit: str
    data_status: str
    periods: list[LedgerFinancialIndicatorPeriod]
    sections: list[LedgerFinancialIndicatorSection]
    coverage: LedgerFinancialIndicatorCoverage
    notes: list[str]
    quality_checks: list[LedgerFinancialIndicatorQualityCheck]
    source_files: list[LedgerFinancialIndicatorSourceFile]


class LedgerFinancialIndicatorSummaryEnvelope(_StrictLedgerPnlReadModel):
    result_meta: ResultMeta
    result: LedgerFinancialIndicatorSummaryPayload


class QdbGlMonthlyAnalysisDatesPayload(_StrictLedgerPnlReadModel):
    report_months: list[str]


class QdbGlMonthlyAnalysisDatesEnvelope(_StrictLedgerPnlReadModel):
    result_meta: ResultMeta
    result: QdbGlMonthlyAnalysisDatesPayload
