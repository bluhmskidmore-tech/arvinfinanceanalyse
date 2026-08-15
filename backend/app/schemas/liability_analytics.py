from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from backend.app.schemas.common_numeric import Numeric, NumericRawScale, NumericUnit, numeric_from_raw
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class LiabilityNimStress(BaseModel):
    model_config = ConfigDict(extra="allow")

    nim_stressed: Numeric | None = None
    delta_bp: Numeric | None = None

    # nim_stressed: liability_analytics_service._build_nim_stress -> nim(decimal ratio) - 0.005.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "nim_stressed": ("pct", True, "ratio"),
        "delta_bp": ("bp", True),
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
    nim_stress: LiabilityNimStress | None = None

    # All four: core_finance.liability_analytics_compat.compute_liability_yield_metrics
    # -> weighted_rate over normalize_*_rate_decimal outputs (decimal ratios, 0.0255 == 2.55%).
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "asset_yield": ("pct", True, "ratio"),
        "liability_cost": ("pct", True, "ratio"),
        "market_liability_cost": ("pct", True, "ratio"),
        "nim": ("pct", True, "ratio"),
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

    # weighted_cost: compute_liability_counterparty -> weighted_num/weighted_den over
    # normalize_interbank_rate_decimal outputs (decimal ratio).
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "value": ("yuan", False),
        "weighted_cost": ("pct", True, "ratio"),
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

    # proportion/pct: compute_liabilities_monthly & monthly_breakdown_items/monthly_v1_term_items
    # -> avg_value / total shares (decimal ratios). weighted_cost: weighted_num/weighted_den
    # over normalized decimal rates (decimal ratio).
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "avg_balance": ("yuan", False),
        "avg_value": ("yuan", False),
        "proportion": ("pct", False, "ratio"),
        "amount": ("yuan", False),
        "pct": ("pct", False, "ratio"),
        "weighted_cost": ("pct", True, "ratio"),
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
    top10_share: Numeric | None = None
    hhi: Numeric | None = None
    population_count: int = Field(default=0, ge=0)
    is_truncated: bool = False
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

    # avg_liability_cost: liability_analytics_compat.compute_liabilities_monthly L722
    # weighted_num/weighted_den over normalize_*_rate_decimal outputs (decimal ratio).
    # mom_change_pct: producer emits None only (compat L727-728, cached-route parity);
    # no confirmed numeric-scale evidence, so it stays on the legacy "auto" heuristic.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "avg_total_liabilities": ("yuan", False),
        "avg_interbank_liabilities": ("yuan", False),
        "avg_issued_liabilities": ("yuan", False),
        "avg_liability_cost": ("pct", True, "ratio"),
        "mom_change": ("yuan", True),
        "mom_change_pct": ("pct", True),
        "top10_share": ("pct", False, "ratio"),
        "hhi": ("count", False),
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
    missing_maturity_count: int = Field(default=0, ge=0)


class LiabilityYieldHistoryPoint(BaseModel):
    """Time series point for yield_metrics charts (plain floats, not Numeric envelopes)."""

    model_config = ConfigDict(extra="forbid")

    date: str
    asset_yield: float | None = None
    liability_cost: float | None = None
    market_liability_cost: float | None = None
    nim: float | None = None


class LiabilityYieldScatterPoint(BaseModel):
    """Scatter point: years-to-maturity (x), YTM as decimal (y), |market value| (z)."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float
    name: str


class LiabilityYieldMetricsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    kpi: LiabilityYieldKpi
    history: list[LiabilityYieldHistoryPoint] = Field(default_factory=list)
    scatter: list[LiabilityYieldScatterPoint] = Field(default_factory=list)


class LiabilityCounterpartyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    report_date: str
    total_value: Numeric
    top10_share: Numeric | None = None
    hhi: Numeric | None = None
    population_count: int = Field(default=0, ge=0)
    is_truncated: bool = False
    top_10: list[LiabilityCounterpartyTopItem]
    by_type: list[LiabilityCounterpartyByTypeItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "total_value": ("yuan", False),
        "top10_share": ("pct", False, "ratio"),
        "hhi": ("count", False),
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

    # ytd_avg_liability_cost: liability_analytics_compat.compute_liabilities_monthly
    # L831-833 ytd_weighted_num/ytd_weighted_den over the same normalized decimal rates.
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "ytd_avg_total_liabilities": ("yuan", False),
        "ytd_avg_liability_cost": ("pct", True, "ratio"),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
