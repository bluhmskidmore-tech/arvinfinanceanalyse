from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class LiabilityNameAmountItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    amount: float | int | None = None
    amount_yi: float | int | None = None


class LiabilityBucketAmountItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    bucket: str
    amount: float | int | None = None
    amount_yi: float | int | None = None


class LiabilityYieldKpi(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_yield: float | None = None
    liability_cost: float | None = None
    market_liability_cost: float | None = None
    nim: float | None = None


class LiabilityRiskBucketsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    liabilities_structure: list[LiabilityNameAmountItem]
    liabilities_term_buckets: list[LiabilityBucketAmountItem]
    interbank_liabilities_structure: list[LiabilityNameAmountItem] = []
    interbank_liabilities_term_buckets: list[LiabilityBucketAmountItem] = []
    issued_liabilities_structure: list[LiabilityNameAmountItem] = []
    issued_liabilities_term_buckets: list[LiabilityBucketAmountItem] = []


class LiabilityYieldMetricsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    kpi: LiabilityYieldKpi


class LiabilityCounterpartyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    total_value: float
    top_10: list[dict[str, Any]]
    by_type: list[dict[str, Any]]


class LiabilitiesMonthlyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    year: int
    months: list[dict[str, Any]]
    ytd_avg_total_liabilities: float | int | None = None
    ytd_avg_liability_cost: float | int | None = None
