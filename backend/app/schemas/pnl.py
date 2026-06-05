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


class PnlByBusinessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_count: int
    total_pnl: Decimal
    total_scale_amount: Decimal
    traced_pnl_row_count: int
    untraced_pnl_row_count: int


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
    current_balance: Decimal
    balance_yield_pct: Decimal | None
    source_kind: str | None = None
    source_note: str | None = None
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
    source_tables: list[str]
    items: list[PnlByBusinessYtdItem]


class PnlByBusinessManualAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    row_key: str = Field(min_length=1)
    business_type: str = ""
    operator: Literal["ADD", "DELTA", "OVERRIDE"] = "DELTA"
    approval_status: Literal["approved", "pending", "rejected"] = "approved"
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
    summary: PnlByBusinessMonthlySummary
    items: list[PnlByBusinessMonthlyItem]


class PnlByBusinessMonthlyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    as_of_date: str
    source_tables: list[str]
    months: list[PnlByBusinessMonthlyBucket]


PnlByBusinessAnalysisDimension = Literal[
    "monthly",
    "portfolio",
    "accounting",
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
