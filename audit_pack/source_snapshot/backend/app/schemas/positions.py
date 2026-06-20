"""Pydantic models for positions read API (aligned with frontend contracts)."""
from __future__ import annotations

from pydantic import BaseModel


class BondPositionItem(BaseModel):
    bond_code: str
    credit_name: str | None = None
    sub_type: str | None = None
    asset_class: str | None = None
    market_value: str | None = None
    face_value: str | None = None
    valuation_net_price: str | None = None
    yield_rate: str | None = None


class InterbankPositionItem(BaseModel):
    deal_id: str
    counterparty: str | None = None
    product_type: str | None = None
    direction: str | None = None  # "Asset" | "Liability"
    amount: str
    interest_rate: str | None = None
    maturity_date: str | None = None


class BondPositionsPageResponse(BaseModel):
    items: list[BondPositionItem]
    total: int
    page: int
    page_size: int


class InterbankPositionsPageResponse(BaseModel):
    items: list[InterbankPositionItem]
    total: int
    page: int
    page_size: int


class SubTypesResponse(BaseModel):
    sub_types: list[str]


class ProductTypesResponse(BaseModel):
    product_types: list[str]


class CounterpartyStatItem(BaseModel):
    customer_name: str
    total_amount: str
    avg_daily_balance: str
    weighted_rate: str | None = None
    weighted_coupon_rate: str | None = None
    transaction_count: int


class CounterpartyStatsResponse(BaseModel):
    start_date: str
    end_date: str
    num_days: int
    items: list[CounterpartyStatItem]
    total_amount: str
    total_avg_daily: str
    total_weighted_rate: str | None = None
    total_weighted_coupon_rate: str | None = None
    total_customers: int


class RatingStatItem(BaseModel):
    rating: str
    total_amount: str
    avg_daily_balance: str
    weighted_rate: str | None = None
    bond_count: int
    percentage: str


class RatingStatsResponse(BaseModel):
    start_date: str
    end_date: str
    num_days: int
    items: list[RatingStatItem]
    total_amount: str
    total_avg_daily: str


class IndustryStatItem(BaseModel):
    industry: str
    total_amount: str
    avg_daily_balance: str
    weighted_rate: str | None = None
    bond_count: int
    percentage: str


class IndustryStatsResponse(BaseModel):
    start_date: str
    end_date: str
    num_days: int
    items: list[IndustryStatItem]
    total_amount: str
    total_avg_daily: str


class CustomerBondDetailItem(BaseModel):
    bond_code: str
    sub_type: str | None = None
    asset_class: str | None = None
    market_value: str
    yield_rate: str | None = None
    maturity_date: str | None = None
    rating: str = ""
    industry: str = ""


class CustomerBondDetailsResponse(BaseModel):
    customer_name: str
    report_date: str
    total_market_value: str
    bond_count: int
    items: list[CustomerBondDetailItem]


class PositionBalanceTrendItem(BaseModel):
    date: str
    balance: str


class CustomerBalanceTrendResponse(BaseModel):
    customer_name: str
    start_date: str
    end_date: str
    days: int
    items: list[PositionBalanceTrendItem]


class InterbankCounterpartySplitResponse(BaseModel):
    start_date: str
    end_date: str
    num_days: int
    asset_total_amount: str
    asset_total_avg_daily: str
    asset_total_weighted_rate: str | None = None
    asset_customer_count: int
    liability_total_amount: str
    liability_total_avg_daily: str
    liability_total_weighted_rate: str | None = None
    liability_customer_count: int
    asset_items: list[CounterpartyStatItem]
    liability_items: list[CounterpartyStatItem]
