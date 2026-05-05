from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
    manual_adjustment: Decimal
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

    business_type: str
    interest_income: Decimal
    fair_value_change: Decimal
    capital_gain: Decimal
    total_pnl: Decimal
    proportion: Decimal | None
    assets_count: int


class PnlByBusinessYtdPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    period_type: str = "yearly"
    period_label: str
    total_pnl: Decimal
    source_tables: list[str]
    items: list[PnlByBusinessYtdItem]


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
