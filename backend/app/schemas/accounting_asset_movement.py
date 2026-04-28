from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountingAssetMovementRowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    report_month: str
    currency_basis: str
    sort_order: int
    basis_bucket: Literal["AC", "OCI", "TPL"]
    previous_balance: Decimal
    current_balance: Decimal
    previous_balance_pct: Decimal | None = None
    current_balance_pct: Decimal | None = None
    balance_change: Decimal
    change_pct: Decimal | None
    contribution_pct: Decimal | None
    zqtz_amount: Decimal
    gl_amount: Decimal
    reconciliation_diff: Decimal
    reconciliation_status: Literal["matched", "mismatch", "gl_only", "zqtz_only"]
    source_version: str
    rule_version: str


class AccountingAssetMovementSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_balance_total: Decimal
    current_balance_total: Decimal
    balance_change_total: Decimal
    zqtz_amount_total: Decimal
    reconciliation_diff_total: Decimal
    matched_bucket_count: int
    bucket_count: int


class AccountingAssetMovementTrendMonthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    report_month: str
    current_balance_total: Decimal
    balance_change_total: Decimal
    rows: list[AccountingAssetMovementRowPayload]


class AccountingBusinessMovementRowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    report_month: str
    currency_basis: str
    side: Literal["asset", "liability"]
    sort_order: int
    row_key: str
    row_label: str
    current_balance: Decimal
    source_kind: Literal["ledger", "zqtz"]
    source_note: str
    source_version: str
    rule_version: str


class AccountingBusinessMovementTrendMonthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    report_month: str
    asset_balance_total: Decimal
    liability_balance_total: Decimal
    net_balance_total: Decimal
    rows: list[AccountingBusinessMovementRowPayload]


class AccountingZqtzCalibrationItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    row_label: str
    system_amount: Decimal
    reference_amount: Decimal
    diff_amount: Decimal
    status: Literal["matched", "watch"]
    note: str


class AccountingZqtzCalibrationAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    conclusion: str
    root_cause: str
    remediation: str
    items: list[AccountingZqtzCalibrationItemPayload]
    residual_risks: list[str]


class AccountingStructureMigrationBucketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis_bucket: Literal["AC", "OCI", "TPL"]
    previous_balance: Decimal
    current_balance: Decimal
    balance_delta: Decimal
    previous_share_pct: Decimal | None = None
    current_share_pct: Decimal | None = None
    share_delta_pp: Decimal | None = None


class AccountingStructureMigrationPairPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_report_date: str
    current_report_date: str
    previous_report_month: str
    current_report_month: str
    total_balance_delta: Decimal
    dominant_share_increase_bucket: Literal["AC", "OCI", "TPL"] | None = None
    fvtpl_volatility_signal: str
    oci_valuation_signal: str
    buckets: list[AccountingStructureMigrationBucketPayload]


class AccountingStructureMigrationAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    caveat: str
    pairs: list[AccountingStructureMigrationPairPayload]


class AccountingDifferenceAttributionComponentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_key: str
    component_label: str
    amount: Decimal
    source_kind: Literal["ledger", "zqtz", "derived", "residual"]
    evidence_note: str
    is_residual: bool = False
    is_supported: bool = True


class AccountingDifferenceAttributionWaterfallPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_label: str
    reference_total: Decimal
    target_label: str
    target_total: Decimal
    net_difference: Decimal
    components: list[AccountingDifferenceAttributionComponentPayload]
    closing_check: Decimal
    caveat: str


class AccountingAssetMovementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    currency_basis: str
    rows: list[AccountingAssetMovementRowPayload]
    summary: AccountingAssetMovementSummaryPayload
    trend_months: list[AccountingAssetMovementTrendMonthPayload]
    business_trend_months: list[AccountingBusinessMovementTrendMonthPayload]
    zqtz_calibration_analysis: AccountingZqtzCalibrationAnalysisPayload | None = None
    structure_migration_analysis: AccountingStructureMigrationAnalysisPayload | None = None
    difference_attribution_waterfall: AccountingDifferenceAttributionWaterfallPayload | None = None
    accounting_controls: list[str]
    excluded_controls: list[str]


class AccountingAssetMovementDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]
    currency_basis: str


class AccountingAssetMovementRefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    cache_key: str
    report_date: str
    currency_basis: str
    row_count: int
    source_version: str
    rule_version: str
    product_category_refreshed_dates: list[str] = Field(default_factory=list)
    formal_balance_refreshed_dates: list[str] = Field(default_factory=list)
    movement_refreshed_dates: list[str] = Field(default_factory=list)
