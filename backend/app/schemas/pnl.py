from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PnlMaterializePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    cache_key: str
    run_id: str
    report_date: str
    formal_fi_rows: int
    nonstd_bridge_rows: int
    source_version: str
    rule_version: str
    vendor_version: str
    lock: str
    pnl_by_business_precompute_records: int = 0


class PnlFormalFiRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    instrument_code: str
    portfolio_name: str
    cost_center: str
    invest_type_std: str
    accounting_basis: str
    currency_basis: str
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    source_version: str
    rule_version: str
    ingest_batch_id: str
    trace_id: str


class PnlNonStdBridgeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    bond_code: str
    portfolio_name: str
    cost_center: str
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal = Decimal("0")
    total_pnl: Decimal
    source_version: str
    rule_version: str
    ingest_batch_id: str
    trace_id: str


class PnlDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]
    formal_fi_report_dates: list[str]
    nonstd_bridge_report_dates: list[str]


class PnlDataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    formal_fi_rows: list[PnlFormalFiRow]
    nonstd_bridge_rows: list[PnlNonStdBridgeRow]


class PnlOverviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    formal_fi_row_count: int
    nonstd_bridge_row_count: int
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal


class PnlV1DetailRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    source: str
    asset_code: str
    bond_name: str
    portfolio: str
    asset_type: str
    asset_class: str
    market_value: Decimal
    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    total_pnl: Decimal
    source_version: str
    trace_id: str


class PnlV1DataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    source_tables: list[str]
    rows: list[PnlV1DetailRow]


class PnlByBusinessRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    business_type_primary: str
    business_type: str
    currency_basis: str
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    scale_amount: Decimal
    yield_pct: Decimal | None
    pnl_row_count: int
    balance_row_count: int


PnlByBusinessUntracedReason = Literal[
    "position_absent_before_maturity",
    "matured_before_or_on_report_date",
    "never_seen_in_zqtz_asset_balance",
    "same_day_balance_without_primary_type",
    "same_day_balance_multiple_primary_types",
    "unexpected_untraced",
]


class PnlByBusinessUntracedBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: PnlByBusinessUntracedReason
    invest_type_std: str
    pnl_row_count: int
    total_pnl: Decimal
    abs_pnl: Decimal
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal


class PnlByBusinessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_count: int
    total_pnl: Decimal
    total_scale_amount: Decimal
    traced_pnl_row_count: int
    untraced_pnl_row_count: int
    untraced_breakdown: list[PnlByBusinessUntracedBreakdownRow] = Field(default_factory=list)


class PnlByBusinessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    source_tables: list[str]
    summary: PnlByBusinessSummary
    rows: list[PnlByBusinessRow]


class PnlByBusinessYtdItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    sort_order: int
    business_type: str
    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    avg_balance: Decimal
    current_balance: Decimal
    balance_yield_pct: Decimal | None
    annualized_yield_pct: Decimal | None
    ftp_rate_pct: Decimal
    ftp_cost: Decimal | None
    ftp_net_pnl: Decimal | None
    ftp_net_annualized_yield_pct: Decimal | None
    source_kind: str | None = None
    source_note: str | None = None
    proportion: Decimal | None
    assets_count: int


PnlByBusinessYtdUnallocatedReason = Literal[
    "no_business_rule_match",
    "detail_only_business_rule_match",
]


class PnlByBusinessYtdUnallocatedBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: PnlByBusinessYtdUnallocatedReason
    source_kind: str
    invest_type_std: str
    accounting_basis: str
    portfolio_name: str
    cost_center: str
    pnl_row_count: int
    total_pnl: Decimal
    abs_pnl: Decimal
    sample_instrument_codes: list[str] = Field(default_factory=list)


class PnlByBusinessYtdUnallocatedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    reason_code: PnlByBusinessYtdUnallocatedReason
    source_kind: str
    instrument_code: str
    portfolio_name: str
    cost_center: str
    invest_type_std: str
    accounting_basis: str
    currency_basis: str
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    abs_pnl: Decimal


class PnlByBusinessYtdSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    avg_balance: Decimal
    current_balance: Decimal
    annualized_yield_pct: Decimal | None
    ftp_rate_pct: Decimal
    ftp_cost: Decimal | None
    ftp_net_pnl: Decimal | None
    ftp_net_annualized_yield_pct: Decimal | None
    proportion: Decimal | None
    assets_count: int


class PnlByBusinessYtdPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    period_type: str = "yearly"
    period_label: str
    period_start_date: str
    period_end_date: str
    total_pnl: Decimal
    coverage_days: int = 0
    expected_days: int = 0
    sample_filled: bool = False
    sample_fill_method: str | None = None
    classified_parent_total_pnl: Decimal = Decimal("0")
    summary: PnlByBusinessYtdSummary
    unallocated_pnl: Decimal = Decimal("0")
    unallocated_abs_pnl: Decimal = Decimal("0")
    unallocated_row_count: int = 0
    reconciliation_delta: Decimal = Decimal("0")
    unallocated_breakdown: list[PnlByBusinessYtdUnallocatedBreakdownRow] = Field(default_factory=list)
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem] = Field(default_factory=list)
    source_tables: list[str]
    items: list[PnlByBusinessYtdItem]


class PnlByBusinessManualAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    row_key: str = Field(min_length=1)
    business_type: str = ""
    operator: Literal["ADD", "DELTA", "OVERRIDE"] = "DELTA"
    approval_status: Literal["approved", "pending", "rejected"] = "pending"
    manual_adjustment: Decimal
    reason: str = ""

    @field_validator("report_date")
    @classmethod
    def validate_report_date(cls, value: str) -> str:
        parts = value.split("-")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError("report_date must be YYYY-MM-DD")
        year, month, day = parts
        if len(year) != 4 or len(month) != 2 or len(day) != 2:
            raise ValueError("report_date must be YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def validate_manual_adjustment_nonzero(self) -> "PnlByBusinessManualAdjustmentRequest":
        if self.manual_adjustment == Decimal("0"):
            raise ValueError("manual_adjustment must be non-zero.")
        return self


class PnlByBusinessManualAdjustmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustment_id: str
    event_type: str
    created_at: str
    stream: str
    report_date: str
    row_key: str
    business_type: str
    operator: str
    approval_status: str
    manual_adjustment: Decimal
    reason: str = ""
    created_by: str = ""
    approved_by: str = ""


class PnlByBusinessManualAdjustmentListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    adjustment_count: int
    event_total: int
    adjustments: list[PnlByBusinessManualAdjustmentPayload]
    events: list[PnlByBusinessManualAdjustmentPayload]


class PnlByBusinessMonthlyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    sort_order: int
    business_type: str
    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    avg_balance: Decimal
    current_balance: Decimal
    annualized_yield_pct: Decimal | None
    ftp_rate_pct: Decimal
    ftp_cost: Decimal | None
    ftp_net_pnl: Decimal | None
    ftp_net_annualized_yield_pct: Decimal | None
    proportion: Decimal | None
    asset_count: int
    source_note: str | None = None


class PnlByBusinessMonthlySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    avg_balance: Decimal
    current_balance: Decimal
    annualized_yield_pct: Decimal | None
    ftp_rate_pct: Decimal
    ftp_cost: Decimal | None
    ftp_net_pnl: Decimal | None
    ftp_net_annualized_yield_pct: Decimal | None
    asset_count: int


class PnlByBusinessMonthlyBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month_key: str
    period_start_date: str
    period_end_date: str
    calendar_days: int
    coverage_days: int = 0
    expected_days: int = 0
    sample_filled: bool = False
    sample_fill_method: str | None = None
    source_total_pnl: Decimal = Decimal("0")
    classified_parent_total_pnl: Decimal = Decimal("0")
    unallocated_pnl: Decimal = Decimal("0")
    unallocated_abs_pnl: Decimal = Decimal("0")
    unallocated_row_count: int = 0
    reconciliation_delta: Decimal = Decimal("0")
    unallocated_breakdown: list[PnlByBusinessYtdUnallocatedBreakdownRow] = Field(default_factory=list)
    unallocated_items: list[PnlByBusinessYtdUnallocatedItem] = Field(default_factory=list)
    unallocated_evidence_complete: bool = False
    summary: PnlByBusinessMonthlySummary
    items: list[PnlByBusinessMonthlyItem]


PnlByBusinessMonthlyComparisonStatus = Literal[
    "available",
    "data_quality_warning",
    "current_month_missing",
    "previous_month_missing",
    "previous_month_outside_request_scope",
    "period_incomplete",
]
PnlByBusinessMonthlyRowComparisonReason = Literal[
    "available",
    "current_row_missing",
    "previous_row_missing",
]


class PnlByBusinessMonthlyChangeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interest_income_delta: Decimal | None = None
    fair_value_change_delta: Decimal | None = None
    capital_gain_delta: Decimal | None = None
    manual_adjustment_delta: Decimal | None = None
    total_pnl_delta: Decimal | None = None
    avg_balance_delta: Decimal | None = None
    current_balance_delta: Decimal | None = None
    annualized_yield_delta_bp: Decimal | None = None
    ftp_cost_delta: Decimal | None = None
    ftp_net_pnl_delta: Decimal | None = None
    ftp_net_annualized_yield_delta_bp: Decimal | None = None


class PnlByBusinessMonthlyChangeRow(PnlByBusinessMonthlyChangeMetrics):
    row_key: str
    sort_order: int
    business_type: str
    comparison_available: bool
    comparison_reason: PnlByBusinessMonthlyRowComparisonReason


class PnlByBusinessMonthlyManagementChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_basis: Literal["latest_month_vs_previous_calendar_month"]
    comparison_scope: Literal["requested_year"]
    comparison_status: PnlByBusinessMonthlyComparisonStatus
    comparison_available: bool
    current_month_key: str
    previous_month_key: str
    coverage_warning_months: list[str]
    reconciliation_warning_months: list[str]
    incomplete_months: list[str]
    summary: PnlByBusinessMonthlyChangeMetrics | None
    rows: list[PnlByBusinessMonthlyChangeRow]


class PnlByBusinessMonthlyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str
    source_tables: list[str]
    months: list[PnlByBusinessMonthlyBucket]
    management_change: PnlByBusinessMonthlyManagementChange | None = None


PnlByBusinessAnalysisDimension = Literal[
    "monthly",
    "portfolio",
    "accounting",
    "currency",
    "cost_center",
    "instrument",
    "bond_bucket",
    "bond_bucket_monthly",
]


class PnlByBusinessAnalysisRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_key: str
    dimension_label: str
    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    manual_adjustment: Decimal
    total_pnl: Decimal
    avg_balance: Decimal
    current_balance: Decimal
    annualized_yield_pct: Decimal | None
    ftp_rate_pct: Decimal
    ftp_cost: Decimal | None
    ftp_net_pnl: Decimal | None
    ftp_net_annualized_yield_pct: Decimal | None
    asset_count: int


class PnlByBusinessAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str
    business_key: str | None
    dimension: PnlByBusinessAnalysisDimension
    period_start_date: str
    period_end_date: str
    coverage_days: int = 0
    expected_days: int = 0
    sample_filled: bool = False
    sample_fill_method: str | None = None
    source_tables: list[str]
    rows: list[PnlByBusinessAnalysisRow]


class PnlYearlyBusinessSummaryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    report_month: str
    report_date: str
    business_type_primary: str
    business_type: str
    currency_basis: str
    total_pnl: Decimal
    scale_amount: Decimal
    yield_pct: Decimal | None
    pnl_row_count: int


class PnlYearlyBusinessSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    source_tables: list[str]
    rows: list[PnlYearlyBusinessSummaryRow]


# ── Candidate (non-formal) business-type insights ───────────────────────────
# `status=candidate` in docs/metric_dictionary.md (MTR-PNLBIZ-001~005). These
# schemas only shape a re-aggregation of already-computed
# `pnl_by_business_ytd_envelope` / `pnl_by_business_monthly_envelope` parent
# rows; they are analytical-only and must not be treated as formal PnL truth.
#
# `PnlByBusinessUntracedTrendRow`/`Summary` (MTR-PNLBIZ-006, further below) are
# a DIFFERENT kind of candidate metric: a formal reconciliation/data-quality
# diagnostic, not a business-analysis re-aggregation. Do not mix their
# `untraced_`-prefixed fields into the business-type rows/summaries above.


class PnlByBusinessConcentrationRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    business_type: str
    avg_balance: Decimal
    share_pct: Decimal


class PnlByBusinessConcentrationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str | None
    total_avg_balance: Decimal | None
    hhi_pct: Decimal | None
    top_n: int
    top_n_share_pct: Decimal | None
    rows: list[PnlByBusinessConcentrationRow]


class PnlByBusinessNegativeFtpPersistenceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    business_type: str
    months_observed: int
    negative_ftp_month_share_pct: Decimal | None
    negative_ftp_longest_streak_months: int


class PnlByBusinessNegativeFtpPersistenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: str
    lookback_months: int
    window_start_month: str | None
    window_end_month: str | None
    months_observed: int
    negative_ftp_month_share_pct: Decimal | None
    negative_ftp_longest_streak_months: int
    rows: list[PnlByBusinessNegativeFtpPersistenceRow]


class PnlByBusinessShareDriftRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    business_type: str
    current_share_pct: Decimal
    baseline_share_pct: Decimal | None
    drift_pp: Decimal | None


class PnlByBusinessShareDriftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str
    baseline_year: int
    baseline_as_of_date: str | None
    baseline_available: bool
    rows: list[PnlByBusinessShareDriftRow]


class PnlByBusinessUntracedTrendRow(BaseModel):
    """一个 formal 报表日的对账健康度诊断行（非业务分析行，字段用 ``untraced_`` 前缀区分）。"""

    model_config = ConfigDict(extra="forbid")

    report_date: str
    untraced_row_count: int
    total_row_count: int
    untraced_share_pct: Decimal | None


class PnlByBusinessUntracedTrendSummary(BaseModel):
    """`MTR-PNLBIZ-006`：formal 对账健康度诊断趋势，非业务贡献/拖累结论。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: str
    lookback_months: int
    rows: list[PnlByBusinessUntracedTrendRow]


class PnlByBusinessCandidateInsightsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str
    concentration: PnlByBusinessConcentrationSummary
    negative_ftp_persistence: PnlByBusinessNegativeFtpPersistenceSummary
    share_drift: PnlByBusinessShareDriftSummary
    reconciliation_diagnostics: PnlByBusinessUntracedTrendSummary
