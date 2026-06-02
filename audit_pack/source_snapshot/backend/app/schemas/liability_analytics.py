from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


def _coerce_value_to_numeric(value: Any, unit: NumericUnit, sign_aware: bool) -> Any:
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
    if isinstance(value, Decimal):
        return numeric_from_raw(raw=float(value), unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return value
        try:
            raw = float(Decimal(normalized))
        except InvalidOperation:
            return value
        return numeric_from_raw(raw=raw, unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return numeric_from_raw(raw=float(value), unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    return value


def _apply_numeric_coercion(
    field_map: dict[str, tuple[NumericUnit, bool]],
    data: Any,
) -> Any:
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for field_name, (unit, sign_aware) in field_map.items():
        if field_name in out:
            out[field_name] = _coerce_value_to_numeric(out[field_name], unit, sign_aware)
    return out


class LiabilityNameAmountItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    amount: Numeric | None = None
    amount_yi: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "amount": ("yuan", False),
        "amount_yi": ("yi", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityBucketAmountItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    bucket: str
    amount: Numeric | None = None
    amount_yi: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "amount": ("yuan", False),
        "amount_yi": ("yi", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityYieldKpi(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_yield: Numeric | None = None
    liability_cost: Numeric | None = None
    market_liability_cost: Numeric | None = None
    nim: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "asset_yield": ("pct", True),
        "liability_cost": ("pct", True),
        "market_liability_cost": ("pct", True),
        "nim": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityCounterpartyTopItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Numeric | None = None
    type: str
    weighted_cost: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "value": ("yuan", False),
        "weighted_cost": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityCounterpartyByTypeItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityMonthlyBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str | None = None
    bucket: str | None = None
    type: str | None = None
    name: str | None = None
    avg_balance: Numeric | None = None
    avg_value: Numeric | None = None
    proportion: Numeric | None = None
    amount: Numeric | None = None
    pct: Numeric | None = None
    weighted_cost: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "avg_balance": ("yuan", False),
        "avg_value": ("yuan", False),
        "proportion": ("pct", False),
        "amount": ("yuan", False),
        "pct": ("pct", False),
        "weighted_cost": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityMonthlyItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    month: str
    month_label: str
    avg_total_liabilities: Numeric | None = None
    avg_interbank_liabilities: Numeric | None = None
    avg_issued_liabilities: Numeric | None = None
    avg_liability_cost: Numeric | None = None
    mom_change: Numeric | None = None
    mom_change_pct: Numeric | None = None
    counterparty_top10: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    by_institution_type: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    structure_overview: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    term_buckets: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    interbank_by_type: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    interbank_term_buckets: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    issued_by_type: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    issued_term_buckets: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    counterparty_details: list[LiabilityMonthlyBreakdownRow] = Field(default_factory=list)
    num_days: int

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "avg_total_liabilities": ("yuan", False),
        "avg_interbank_liabilities": ("yuan", False),
        "avg_issued_liabilities": ("yuan", False),
        "avg_liability_cost": ("pct", True),
        "mom_change": ("yuan", True),
        "mom_change_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilityRiskBucketsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    liabilities_structure: list[LiabilityNameAmountItem]
    liabilities_term_buckets: list[LiabilityBucketAmountItem]
    interbank_liabilities_structure: list[LiabilityNameAmountItem] = Field(default_factory=list)
    interbank_liabilities_term_buckets: list[LiabilityBucketAmountItem] = Field(default_factory=list)
    issued_liabilities_structure: list[LiabilityNameAmountItem] = Field(default_factory=list)
    issued_liabilities_term_buckets: list[LiabilityBucketAmountItem] = Field(default_factory=list)


class LiabilityYieldMetricsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    kpi: LiabilityYieldKpi


class LiabilityCounterpartyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    total_value: Numeric
    top_10: list[LiabilityCounterpartyTopItem]
    by_type: list[LiabilityCounterpartyByTypeItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class LiabilitiesMonthlyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    year: int
    months: list[LiabilityMonthlyItem]
    ytd_avg_total_liabilities: Numeric | None = None
    ytd_avg_liability_cost: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "ytd_avg_total_liabilities": ("yuan", False),
        "ytd_avg_liability_cost": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
