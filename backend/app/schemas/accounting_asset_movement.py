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
    # chain_broken：横截面对得上、但本月期初接不上上月期末。跨月勾稽不过的行
    # 不得对外显示成已对平，所以它占用 reconciliation_status 而不是只作为附注。
    reconciliation_status: Literal[
        "matched",
        "mismatch",
        "gl_only",
        "zqtz_only",
        "chain_broken",
    ]
    source_version: str
    rule_version: str
    # 两列都可能为 None：迁移落地前写入的历史行没有记录过控制结论，读取端要把
    # "未记录"和"已判定"分开，不能把 None 当成 no_prior_month / 无头寸源。
    chain_status: Literal["continuous", "broken", "no_prior_month"] | None = None
    position_source_basis: str | None = None


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


class AccountingDrilldownMetaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_tables: list[str]
    source_scope: str
    report_date: str
    prior_report_date: str | None = None
    currency_basis: str
    zqtz_currency_basis: str | None = None
    unit: Literal["yuan"] = "yuan"
    eligible_total: Decimal
    covered_total: Decimal | None = None
    unknown_total: Decimal | None = None
    coverage_pct: Decimal | None = None
    status: Literal[
        "supported",
        "unsupported_missing_columns",
        "unsupported_low_coverage",
        "no_data",
    ]
    caveat: str


class AccountingBasisMovementComponentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_key: str
    component_label: str
    account_code_pattern: str
    previous_balance: Decimal
    current_balance: Decimal
    balance_change: Decimal
    contribution_pct: Decimal | None = None
    source_note: str
    is_supported: bool


class AccountingBasisMovementBucketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis_bucket: Literal["AC", "OCI", "TPL"]
    previous_balance: Decimal
    current_balance: Decimal
    balance_change: Decimal
    rows: list[AccountingBasisMovementComponentPayload]
    residual_amount: Decimal
    closing_check: Decimal


class AccountingBasisMovementDecompositionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: AccountingDrilldownMetaPayload
    buckets: list[AccountingBasisMovementBucketPayload]


class AccountingZqtzMaturityBucketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maturity_bucket: Literal[
        "overdue_or_matured",
        "<=30d",
        "31-90d",
        "91d-1y",
        "1-3y",
        "3-5y",
        ">5y",
        "unknown",
    ]
    bucket_label: str
    current_amount: Decimal
    prior_amount: Decimal
    delta_amount: Decimal
    item_count: int
    share_pct: Decimal | None = None


class AccountingZqtzMaturityStructurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: AccountingDrilldownMetaPayload
    buckets: list[AccountingZqtzMaturityBucketPayload]


class AccountingZqtzConcentrationItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    dimension_value: str
    current_amount: Decimal
    prior_amount: Decimal | None = None
    delta_amount: Decimal | None = None
    share_pct: Decimal | None = None
    item_count: int
    item_kind: Literal["top", "other", "unknown"]


class AccountingZqtzConcentrationDimensionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: Literal["issuer_name", "rating", "industry_name"]
    status: Literal[
        "supported",
        "unsupported_missing_columns",
        "unsupported_low_coverage",
        "no_data",
    ]
    eligible_total: Decimal
    covered_total: Decimal
    unknown_total: Decimal
    coverage_pct: Decimal | None = None
    prior_coverage_pct: Decimal | None = None
    top_n: int
    hhi: Decimal | None = None
    top5_share_pct: Decimal | None = None
    items: list[AccountingZqtzConcentrationItemPayload]
    caveat: str


class AccountingZqtzConcentrationAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: AccountingDrilldownMetaPayload
    dimensions: list[AccountingZqtzConcentrationDimensionPayload]


class AccountingAssetMovementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    currency_basis: str
    available_report_dates: list[str]
    upstream_control_report_dates: list[str]
    freshness_status: Literal[
        "fresh",
        "read_model_lagging",
        "read_model_empty",
        "upstream_empty",
    ]
    rows: list[AccountingAssetMovementRowPayload]
    summary: AccountingAssetMovementSummaryPayload
    trend_months: list[AccountingAssetMovementTrendMonthPayload]
    business_trend_months: list[AccountingBusinessMovementTrendMonthPayload]
    zqtz_calibration_analysis: AccountingZqtzCalibrationAnalysisPayload | None = None
    structure_migration_analysis: AccountingStructureMigrationAnalysisPayload | None = None
    difference_attribution_waterfall: AccountingDifferenceAttributionWaterfallPayload | None = None
    basis_movement_decomposition: AccountingBasisMovementDecompositionPayload | None = None
    zqtz_maturity_structure: AccountingZqtzMaturityStructurePayload | None = None
    zqtz_concentration_analysis: AccountingZqtzConcentrationAnalysisPayload | None = None
    accounting_controls: list[str]
    excluded_controls: list[str]


class AccountingAssetMovementDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]
    upstream_control_report_dates: list[str]
    currency_basis: str
    latest_read_model_report_date: str | None = None
    latest_upstream_control_report_date: str | None = None
    freshness_status: Literal[
        "fresh",
        "read_model_lagging",
        "read_model_empty",
        "upstream_empty",
    ]


class AccountingAssetMovementRefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    cache_key: str
    report_date: str
    currency_basis: str
    run_id: str | None = None
    job_name: str | None = None
    trigger_mode: str | None = None
    row_count: int | None = None
    source_version: str | None = None
    rule_version: str
    product_category_refreshed_dates: list[str] = Field(default_factory=list)
    formal_balance_refreshed_dates: list[str] = Field(default_factory=list)
    movement_refreshed_dates: list[str] = Field(default_factory=list)
