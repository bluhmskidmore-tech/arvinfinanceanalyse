from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Literal

from backend.app.schemas.common_numeric import Numeric, NumericRawScale, NumericUnit, numeric_from_raw
from pydantic import BaseModel, Field, model_validator

# (unit, sign_aware) keeps the legacy "auto" pct heuristic;
# (unit, sign_aware, raw_scale) declares the producing raw scale explicitly.
_NumericFieldSpec = tuple[NumericUnit, bool] | tuple[NumericUnit, bool, NumericRawScale]


def _coerce_value_to_numeric(
    value: Any,
    unit: NumericUnit,
    sign_aware: bool,
    raw_scale: NumericRawScale = "auto",
) -> Any:
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
    if isinstance(value, Decimal):
        return numeric_from_raw(
            raw=float(value), unit=unit, sign_aware=sign_aware, raw_scale=raw_scale
        ).model_dump(mode="json")
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return value
        try:
            raw = float(Decimal(normalized))
        except InvalidOperation:
            return value
        return numeric_from_raw(
            raw=raw, unit=unit, sign_aware=sign_aware, raw_scale=raw_scale
        ).model_dump(mode="json")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return numeric_from_raw(
            raw=float(value), unit=unit, sign_aware=sign_aware, raw_scale=raw_scale
        ).model_dump(mode="json")
    return value


def _apply_numeric_coercion(
    field_map: dict[str, _NumericFieldSpec],
    data: Any,
) -> Any:
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for field_name, spec in field_map.items():
        if field_name in out:
            unit, sign_aware = spec[0], spec[1]
            raw_scale: NumericRawScale = spec[2] if len(spec) == 3 else "auto"
            out[field_name] = _coerce_value_to_numeric(out[field_name], unit, sign_aware, raw_scale)
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

    # Rates are normalized to decimal ratios in bond_analytics.engine L304-321,
    # then passed through unchanged by bond_dashboard_service L419-430.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_market_value": ("yuan", False),
        "unrealized_pnl": ("yuan", True),
        "weighted_ytm": ("pct", True, "ratio"),
        "weighted_duration": ("ratio", False),
        "weighted_coupon": ("pct", True, "ratio"),
        "credit_spread_median": ("pct", True, "ratio"),
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

    # bond_dashboard_service L413-416 calculates percentage as part / whole.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False, "ratio"),
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

    # weighted_ytm is the normalized fact value passed through at
    # bond_dashboard_service L700-718.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "weighted_ytm": ("pct", True, "ratio"),
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

    # bond_analytics_repo L815-821 computes weighted_ytm from fact ytm ratios.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_market_value": ("yuan", False),
        "weighted_ytm": ("pct", True, "ratio"),
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

    # bond_analytics_repo L861-864 takes median(ytm), whose snapshot source is
    # normalized to a decimal ratio in bond_analytics.engine L304-321.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "median_yield": ("pct", True, "ratio"),
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

    # bond_dashboard_service L793-809 calculates percentage as part / whole.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False, "ratio"),
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

    # bond_dashboard_service L825-841 calculates percentage as part / whole.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_market_value": ("yuan", False),
        "percentage": ("pct", False, "ratio"),
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


class BondDashboardBusinessTypeMetricItem(BaseModel):
    name: str
    market_value: str
    weighted_avg_ytm_pct: str
    weighted_avg_duration: str
    duration_source: str = ""


class BondDashboardBusinessTypeMetricsPayload(BaseModel):
    report_date: str
    items: list[BondDashboardBusinessTypeMetricItem] = Field(default_factory=list)


class BondDashboardHomeSummaryPayload(BaseModel):
    report_date: str
    headline: BondDashboardHeadlinePayload
    risk: BondDashboardRiskIndicatorsPayload
    asset_type: BondDashboardAssetStructurePayload
    asset_rating: BondDashboardAssetStructurePayload
    maturity: BondDashboardMaturityStructurePayload
    industry: BondDashboardIndustryDistributionPayload
    yield_distribution: BondDashboardYieldDistributionPayload
    portfolio_comparison: BondDashboardPortfolioComparisonPayload
    spread: BondDashboardSpreadAnalysisPayload
    business_type: BondDashboardBusinessTypeMetricsPayload


class BondDashboardBundleSectionStatus(BaseModel):
    status: Literal["ok", "error"]
    message: str | None = None
    duration_ms: float = 0.0


class BondDashboardBundlePayload(BaseModel):
    report_date: str | None = None
    requested_sections: list[str] = Field(default_factory=list)
    sections: dict[str, dict[str, object]] = Field(default_factory=dict)
    section_statuses: dict[str, BondDashboardBundleSectionStatus] = Field(default_factory=dict)
    failed_sections: list[str] = Field(default_factory=list)
