from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from backend.app.schemas.advanced_attribution import AdvancedAttributionBundlePayload
from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict

BalanceAnalysisSourceFamily = Literal["zqtz", "tyw", "combined"]
BalancePositionScope = Literal["asset", "liability", "all"]
BalanceCurrencyBasis = Literal["native", "CNY"]
BalanceAnalysisWorkbookSectionKind = Literal[
    "table",
    "decision_items",
    "event_calendar",
    "risk_alerts",
]
BalanceAnalysisSeverity = Literal["low", "medium", "high"]
BalanceAnalysisDecisionStatus = Literal["pending", "confirmed", "dismissed"]
BalanceAnalysisMetricRawUnit = Literal["yuan"]
BalanceAnalysisMetricDisplayUnit = Literal["yi_yuan"]
BalanceAnalysisMetricBasis = Literal["formal"]
BalanceAnalysisMetricSourceSurface = Literal["formal_balance"]
BalanceAnalysisMetricAppliesTo = Literal["overview", "summary", "detail"]


class BalanceAnalysisMetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    source_field: str
    raw_unit: BalanceAnalysisMetricRawUnit
    display_unit: BalanceAnalysisMetricDisplayUnit
    basis: BalanceAnalysisMetricBasis
    source_surface: BalanceAnalysisMetricSourceSurface
    applies_to: list[BalanceAnalysisMetricAppliesTo]
    description: str


class BalanceAnalysisDetailRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: Literal["zqtz", "tyw"]
    report_date: str
    row_key: str
    display_name: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    invest_type_std: str
    accounting_basis: str
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal
    is_issuance_like: bool | None = None


class BalanceAnalysisSummaryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: BalanceAnalysisSourceFamily
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisTableRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    source_family: Literal["zqtz", "tyw"]
    display_name: str
    owner_name: str
    category_name: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    invest_type_std: str
    accounting_basis: str
    detail_row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    details: list[BalanceAnalysisDetailRow]
    summary: list[BalanceAnalysisSummaryRow]


class BalanceAnalysisSummaryTablePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    limit: int
    offset: int
    total_rows: int
    rows: list[BalanceAnalysisTableRow]


class BalanceAnalysisOverviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    detail_row_count: int
    summary_row_count: int
    total_market_value_amount: Decimal
    total_amortized_cost_amount: Decimal
    total_accrued_interest_amount: Decimal
    asset_total_market_value_amount: Decimal
    liability_total_market_value_amount: Decimal
    asset_total_amortized_cost_amount: Decimal
    liability_total_amortized_cost_amount: Decimal
    asset_total_accrued_interest_amount: Decimal
    liability_total_accrued_interest_amount: Decimal
    metric_definitions: list[BalanceAnalysisMetricDefinition]


class BalanceAnalysisBasisBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: Literal["zqtz", "tyw"]
    invest_type_std: str
    accounting_basis: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    detail_row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisBasisBreakdownPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    rows: list[BalanceAnalysisBasisBreakdownRow]


class BalanceAnalysisDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]


class BalanceAnalysisWorkbookCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: Decimal | str | int
    note: str | None = None


class BalanceAnalysisWorkbookColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str


class BalanceAnalysisWorkbookTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    section_kind: Literal["table"]
    columns: list[BalanceAnalysisWorkbookColumn]
    # Workbook sections intentionally have different column sets. Keep row
    # keys dynamic, while constraining every cell to the values the builder
    # actually serializes.
    rows: list[dict[str, Decimal | str | int | None]]


class BalanceAnalysisDecisionItemRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    action_label: str
    severity: BalanceAnalysisSeverity
    reason: str
    source_section: str
    rule_id: str
    rule_version: str


class BalanceAnalysisDecisionStatusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_key: str
    status: BalanceAnalysisDecisionStatus
    updated_at: str | None = None
    updated_by: str | None = None
    comment: str | None = None


class BalanceAnalysisDecisionStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    decision_key: str
    status: BalanceAnalysisDecisionStatus
    comment: str | None = None


class BalanceAnalysisDecisionItemStatusRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_key: str
    title: str
    action_label: str
    severity: BalanceAnalysisSeverity
    reason: str
    source_section: str
    rule_id: str
    rule_version: str
    latest_status: BalanceAnalysisDecisionStatusRecord


class BalanceAnalysisEventCalendarRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_date: str
    event_type: str
    title: str
    source: str
    impact_hint: str
    source_section: str


class BalanceAnalysisRiskAlertRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    severity: BalanceAnalysisSeverity
    reason: str
    source_section: str
    rule_id: str
    rule_version: str


class BalanceAnalysisDecisionItemsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["decision_items"]
    title: str
    section_kind: Literal["decision_items"]
    columns: list[BalanceAnalysisWorkbookColumn]
    rows: list[BalanceAnalysisDecisionItemRow]


class BalanceAnalysisDecisionItemsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    columns: list[BalanceAnalysisWorkbookColumn]
    rows: list[BalanceAnalysisDecisionItemStatusRow]


class BalanceAnalysisEventCalendarSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["event_calendar"]
    title: str
    section_kind: Literal["event_calendar"]
    columns: list[BalanceAnalysisWorkbookColumn]
    rows: list[BalanceAnalysisEventCalendarRow]


class BalanceAnalysisRiskAlertsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["risk_alerts"]
    title: str
    section_kind: Literal["risk_alerts"]
    columns: list[BalanceAnalysisWorkbookColumn]
    rows: list[BalanceAnalysisRiskAlertRow]


class BalanceAnalysisWorkbookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    cards: list[BalanceAnalysisWorkbookCard]
    tables: list[BalanceAnalysisWorkbookTable]
    operational_sections: list[
        BalanceAnalysisDecisionItemsSection
        | BalanceAnalysisEventCalendarSection
        | BalanceAnalysisRiskAlertsSection
    ]


class _StrictBalanceAnalysisResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BalanceAnalysisResultMeta(ResultMeta):
    """Strict balance-analysis view of the shared governed result metadata."""

    model_config = ConfigDict(extra="forbid")

    # `filters_applied` and `next_drill` remain extensible mappings in the
    # shared ResultMeta contract because their keys vary by endpoint. Business
    # result fields are modeled strictly in the payload classes below.


class BalanceAnalysisCalibration(_StrictBalanceAnalysisResponseModel):
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    source_families: list[Literal["zqtz", "tyw"]]
    tyw_amount_semantics: str
    data_basis: Literal["formal_facts"]
    calibration_note: str


class BalanceAnalysisDatesEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisDatesPayload


class BalanceAnalysisDetailEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisPayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisOverviewEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisOverviewPayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisSummaryEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisSummaryTablePayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisBasisBreakdownEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisBasisBreakdownPayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisAdvancedAttributionEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    # Upstream summary keys depend on which analytical components are
    # available, so AdvancedAttributionBundlePayload intentionally keeps those
    # nested maps dynamic while strictly modeling the surrounding contract.
    result: AdvancedAttributionBundlePayload


class BalanceAnalysisWorkbookEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisWorkbookPayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisDecisionItemsEnvelope(_StrictBalanceAnalysisResponseModel):
    result_meta: BalanceAnalysisResultMeta
    result: BalanceAnalysisDecisionItemsPayload
    data_source: Literal["balance_analysis_facts"]
    calibration: BalanceAnalysisCalibration


class BalanceAnalysisCurrentUserPayload(_StrictBalanceAnalysisResponseModel):
    user_id: str
    role: str
    identity_source: Literal["header", "env", "fallback"]
    can_write_decision_status: bool | None


class BalanceAnalysisPublicationStatusPayload(_StrictBalanceAnalysisResponseModel):
    enabled: bool
    available: bool
    generation: str | None
    report_dates: list[str]
    manifest_sha256: str | None
    quality_flag: Literal["ok", "stale"]
    reason: str | None


class _BalanceAnalysisRefreshRunPayload(_StrictBalanceAnalysisResponseModel):
    status: str
    run_id: str
    job_name: str
    trigger_mode: Literal["async", "terminal"]
    cache_key: str
    report_date: str
    cache_version: str | None = None
    lock: str | None = None
    source_version: str | None = None
    vendor_version: str | None = None
    rule_version: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    failure_category: str | None = None
    failure_reason: str | None = None
    created_at: str | None = None
    idempotency_key: str | None = None


class BalanceAnalysisRefreshPayload(_BalanceAnalysisRefreshRunPayload):
    idempotency_replay: bool


class BalanceAnalysisRefreshStatusPayload(_BalanceAnalysisRefreshRunPayload):
    pass


class BalanceRelatedApiEnvelope(BaseModel):
    """Top-level JSON for balance / ADB endpoints that return result_meta + result (+ optional calibration)."""

    model_config = ConfigDict(extra="forbid")

    result_meta: dict[str, Any]
    result: dict[str, Any]
    calibration: dict[str, Any] | None = None
