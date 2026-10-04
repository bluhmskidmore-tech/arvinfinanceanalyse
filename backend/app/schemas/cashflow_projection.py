from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from backend.app.schemas.common_numeric import Numeric, NumericRawScale, NumericUnit, numeric_from_raw
from backend.app.schemas.result_meta import ResultMeta
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

class CashflowMonthlyBucketPayload(BaseModel):
    year_month: str
    asset_inflow: Numeric
    liability_outflow: Numeric
    net_cashflow: Numeric
    cumulative_net: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "asset_inflow": ("yuan", False),
        "liability_outflow": ("yuan", False),
        "net_cashflow": ("yuan", True),
        "cumulative_net": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CashflowMaturingAssetPayload(BaseModel):
    instrument_code: str
    instrument_name: str
    maturity_date: str
    face_value: Numeric
    market_value: Numeric
    currency_code: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "face_value": ("yuan", False),
        "market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CashflowProjectionInputLineagePayload(BaseModel):
    """One fact table read by the cashflow-projection service.

    Empty version, batch, or trace lists mean that no non-empty value was present
    in the rows returned by that fact read; they must not be interpreted as a
    synthetic or inherited lineage value. ``row_count`` is the number of rows
    directly read from ``table_name`` before any duration attachment.
    """

    table_name: str
    row_count: int = Field(ge=0)
    source_versions: list[str] = Field(default_factory=list)
    rule_versions: list[str] = Field(default_factory=list)
    ingest_batch_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


class CashflowProjectionResponse(BaseModel):
    report_date: date
    duration_gap: Numeric
    asset_duration: Numeric
    liability_duration: Numeric
    equity_duration: Numeric
    rate_sensitivity_1bp: Numeric
    reinvestment_risk_12m: Numeric
    # Covered/excluded balances are CNY yuan amounts. The current service always
    # emits a Numeric (including raw=0 when the relevant balance is zero); a
    # field-level null means a legacy response that predates this disclosure.
    asset_duration_covered_balance: Numeric | None = Field(
        default=None,
        description="CNY asset market value included in the duration numerator and denominator.",
    )
    liability_duration_covered_balance: Numeric | None = Field(
        default=None,
        description="CNY liability value included in the duration numerator and denominator.",
    )
    asset_excluded_balance: Numeric | None = Field(
        default=None,
        description="CNY asset market value excluded because a usable duration was unavailable.",
    )
    liability_excluded_balance: Numeric | None = Field(
        default=None,
        description="CNY liability value excluded because a usable duration was unavailable.",
    )
    # Raw values are decimal ratios (not percent points). On a current response,
    # ``raw=null`` means the corresponding total balance is zero; a field-level
    # null means the response predates this coverage disclosure.
    asset_duration_coverage_ratio: Numeric | None = Field(
        default=None,
        description="Covered asset balance divided by total asset market value; raw is a decimal ratio.",
    )
    liability_duration_coverage_ratio: Numeric | None = Field(
        default=None,
        description="Covered liability balance divided by total liability value; raw is a decimal ratio.",
    )
    input_lineage: list[CashflowProjectionInputLineagePayload] | None = None
    monthly_buckets: list[CashflowMonthlyBucketPayload]
    top_maturing_assets_12m: list[CashflowMaturingAssetPayload]
    floating_rate_proxy_count: int = 0
    floating_rate_proxy_market_value: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False)
    )
    payment_frequency_fallback_count: int = 0
    payment_frequency_fallback_market_value: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False)
    )
    bullet_value_date_fallback_count: int = 0
    bullet_value_date_fallback_market_value: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False)
    )
    warnings: list[str] = Field(default_factory=list)
    computed_at: str

    # reinvestment_risk_12m: core_finance.cashflow_projection L445 maturing face value /
    # total asset market value — a decimal ratio that can legitimately reach or exceed 1
    # (cashflow_projection_service._ratio_pct_numeric_json already serializes it as ratio).
    _NUMERIC_FIELDS: ClassVar[dict[str, _NumericFieldSpec]] = {
        "duration_gap": ("years", True),
        "asset_duration": ("years", False),
        "liability_duration": ("years", False),
        "equity_duration": ("years", True),
        "rate_sensitivity_1bp": ("yuan", True),
        "reinvestment_risk_12m": ("pct", False, "ratio"),
        "asset_duration_covered_balance": ("yuan", False),
        "liability_duration_covered_balance": ("yuan", False),
        "asset_excluded_balance": ("yuan", False),
        "liability_excluded_balance": ("yuan", False),
        "asset_duration_coverage_ratio": ("pct", False, "ratio"),
        "liability_duration_coverage_ratio": ("pct", False, "ratio"),
        "floating_rate_proxy_market_value": ("yuan", False),
        "payment_frequency_fallback_market_value": ("yuan", False),
        "bullet_value_date_fallback_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CashflowProjectionEnvelope(BaseModel):
    """`GET /api/cashflow-projection` wire shape.

    `extra="forbid"` keeps an undeclared response key loud instead of letting
    FastAPI drop it on the way out.
    """

    model_config = ConfigDict(extra="forbid")

    result_meta: ResultMeta
    result: CashflowProjectionResponse
