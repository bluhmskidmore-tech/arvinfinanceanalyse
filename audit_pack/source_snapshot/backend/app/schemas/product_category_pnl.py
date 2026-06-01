from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductCategoryPnlRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str
    category_name: str
    side: str
    level: int
    view: str
    report_date: str
    baseline_ftp_rate_pct: Decimal
    cnx_scale: Decimal
    cny_scale: Decimal
    foreign_scale: Decimal
    cnx_cash: Decimal
    cny_cash: Decimal
    foreign_cash: Decimal
    cny_ftp: Decimal
    foreign_ftp: Decimal
    cny_net: Decimal
    foreign_net: Decimal
    business_net_income: Decimal
    weighted_yield: Decimal | None = None
    is_total: bool = False
    children: list[str] = []
    scenario_rate_pct: Decimal | None = None


class ProductCategoryPnlPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    view: str
    available_views: list[str]
    scenario_rate_pct: float | None = None
    rows: list[ProductCategoryPnlRow]
    asset_total: ProductCategoryPnlRow
    liability_total: ProductCategoryPnlRow
    grand_total: ProductCategoryPnlRow


class ProductCategoryAttributionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    days: int
    scale: Decimal
    yield_pct: Decimal | None = None
    cash: Decimal
    ftp: Decimal
    business_net_income: Decimal


class ProductCategoryAttributionEffects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_effect: Decimal
    scale_effect: Decimal
    rate_effect: Decimal
    ftp_effect: Decimal
    direct_effect: Decimal
    unexplained_effect: Decimal
    explained_effect: Decimal
    delta_business_net_income: Decimal
    closure_error: Decimal


class ProductCategoryAttributionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str
    category_name: str
    side: str
    level: int
    state: Literal["complete", "partial"]
    current: ProductCategoryAttributionPoint | None = None
    prior: ProductCategoryAttributionPoint | None = None
    effects: ProductCategoryAttributionEffects


class ProductCategoryAttributionTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_total: ProductCategoryAttributionRow
    liability_total: ProductCategoryAttributionRow
    grand_total: ProductCategoryAttributionRow


class ProductCategoryAttributionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    compare: Literal["mom", "yoy"]
    current_report_date: str
    prior_report_date: str
    state: Literal["complete", "incomplete"]
    reason: str | None = None
    rows: list[ProductCategoryAttributionRow]
    totals: ProductCategoryAttributionTotals | None = None


class ProductCategoryDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]


class ProductCategoryManualAdjustmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    operator: Literal["ADD", "DELTA", "OVERRIDE"] = "DELTA"
    approval_status: Literal["approved", "pending", "rejected"] = "approved"
    account_code: str = Field(min_length=1)
    currency: Literal["CNX", "CNY"]
    account_name: str = ""
    beginning_balance: Decimal | None = None
    ending_balance: Decimal | None = None
    monthly_pnl: Decimal | None = None
    daily_avg_balance: Decimal | None = None
    annual_avg_balance: Decimal | None = None

    @field_validator("report_date")
    @classmethod
    def validate_report_date(cls, value: str) -> str:
        return _validate_report_date(value)

    @model_validator(mode="after")
    def validate_amount_presence(self) -> "ProductCategoryManualAdjustmentCreateRequest":
        if all(
            value is None
            for value in (
                self.beginning_balance,
                self.ending_balance,
                self.monthly_pnl,
                self.daily_avg_balance,
                self.annual_avg_balance,
            )
        ):
            raise ValueError("At least one adjustment value is required.")
        return self


class ProductCategoryManualAdjustmentUpdateRequest(
    ProductCategoryManualAdjustmentCreateRequest
):
    pass


class ProductCategoryManualAdjustmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustment_id: str
    event_type: str
    created_at: str
    stream: str
    report_date: str
    operator: str
    approval_status: str
    account_code: str
    currency: str
    account_name: str = ""
    beginning_balance: Decimal | None = None
    ending_balance: Decimal | None = None
    monthly_pnl: Decimal | None = None
    daily_avg_balance: Decimal | None = None
    annual_avg_balance: Decimal | None = None


ProductCategoryCurrentSortField = Literal[
    "created_at",
    "adjustment_id",
    "approval_status",
    "account_code",
]
ProductCategoryEventSortField = Literal[
    "created_at",
    "adjustment_id",
    "event_type",
    "approval_status",
    "account_code",
]
ProductCategorySortDirection = Literal["asc", "desc"]


class ProductCategoryManualAdjustmentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    adjustment_id: str | None = None
    adjustment_id_exact: bool = False
    account_code: str | None = None
    approval_status: str | None = None
    event_type: str | None = None
    current_sort_field: ProductCategoryCurrentSortField = "created_at"
    current_sort_dir: ProductCategorySortDirection = "desc"
    event_sort_field: ProductCategoryEventSortField = "created_at"
    event_sort_dir: ProductCategorySortDirection = "desc"
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    adjustment_limit: int = Field(20, ge=1, le=200)
    adjustment_offset: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=200)
    offset: int = Field(0, ge=0)

    @field_validator("created_at_from", "created_at_to")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("created_at filters must be ISO 8601 UTC timestamps")
        return value.astimezone(timezone.utc)


class ProductCategoryManualAdjustmentListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    adjustment_count: int
    adjustment_limit: int
    adjustment_offset: int
    event_total: int
    event_limit: int
    event_offset: int
    adjustments: list[ProductCategoryManualAdjustmentPayload]
    events: list[ProductCategoryManualAdjustmentPayload]


def _validate_report_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    normalized = parsed.strftime("%Y-%m-%d")
    if normalized != value:
        raise ValueError("report_date must be a single YYYY-MM-DD value")
    return value
