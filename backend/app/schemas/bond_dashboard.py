from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

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


class BondDashboardHeadlineKpiBlock(BaseModel):
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    unrealized_pnl: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    weighted_ytm: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))
    weighted_duration: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    weighted_coupon: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))
    credit_spread_median: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))
    total_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    bond_count: int = 0

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "unrealized_pnl": ("yuan", True),
        "weighted_ytm": ("pct", True),
        "weighted_duration": ("ratio", False),
        "weighted_coupon": ("pct", True),
        "credit_spread_median": ("pct", True),
        "total_dv01": ("dv01", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardHeadlinePayload(BaseModel):
    report_date: str
    prev_report_date: str | None = None
    kpis: BondDashboardHeadlineKpiBlock
    prev_kpis: BondDashboardHeadlineKpiBlock | None = None


class BondDashboardAssetStructureItem(BaseModel):
    category: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    bond_count: int = 0
    percentage: Numeric | None = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardAssetStructurePayload(BaseModel):
    report_date: str
    group_by: str
    items: list[BondDashboardAssetStructureItem] = Field(default_factory=list)
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardYieldDistributionItem(BaseModel):
    yield_bucket: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    bond_count: int = 0

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardYieldDistributionPayload(BaseModel):
    report_date: str
    items: list[BondDashboardYieldDistributionItem] = Field(default_factory=list)
    weighted_ytm: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "weighted_ytm": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardPortfolioComparisonItem(BaseModel):
    portfolio_name: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    weighted_ytm: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))
    weighted_duration: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    total_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    bond_count: int = 0

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "weighted_ytm": ("pct", True),
        "weighted_duration": ("ratio", False),
        "total_dv01": ("dv01", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardPortfolioComparisonPayload(BaseModel):
    report_date: str
    items: list[BondDashboardPortfolioComparisonItem] = Field(default_factory=list)


class BondDashboardSpreadAnalysisItem(BaseModel):
    bond_type: str
    median_yield: Numeric | None = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=True))
    bond_count: int = 0
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "median_yield": ("pct", True),
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardSpreadAnalysisPayload(BaseModel):
    report_date: str
    items: list[BondDashboardSpreadAnalysisItem] = Field(default_factory=list)


class BondDashboardMaturityStructureItem(BaseModel):
    maturity_bucket: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    bond_count: int = 0
    percentage: Numeric | None = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardMaturityStructurePayload(BaseModel):
    report_date: str
    items: list[BondDashboardMaturityStructureItem] = Field(default_factory=list)
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardIndustryDistributionItem(BaseModel):
    industry_name: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    bond_count: int = 0
    percentage: Numeric | None = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="pct", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondDashboardIndustryDistributionPayload(BaseModel):
    report_date: str
    items: list[BondDashboardIndustryDistributionItem] = Field(default_factory=list)


class BondDashboardRiskIndicatorsPayload(BaseModel):
    report_date: str
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    total_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    weighted_duration: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    credit_ratio: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    weighted_convexity: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    total_spread_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    reinvestment_ratio_1y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "total_dv01": ("dv01", False),
        "weighted_duration": ("ratio", False),
        "credit_ratio": ("ratio", False),
        "weighted_convexity": ("ratio", False),
        "total_spread_dv01": ("dv01", False),
        "reinvestment_ratio_1y": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
