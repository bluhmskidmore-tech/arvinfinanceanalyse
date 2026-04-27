from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class AccountingAssetMovementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    currency_basis: str
    rows: list[AccountingAssetMovementRowPayload]
    summary: AccountingAssetMovementSummaryPayload
    trend_months: list[AccountingAssetMovementTrendMonthPayload]
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
