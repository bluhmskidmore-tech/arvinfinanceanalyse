"""Executive dashboard payload schemas.

Wave 2.1 migrates governed numeric fields from ``str`` to a transitional
``Numeric | str`` union with a coercion validator. Callsites that still
pass raw display strings (service layer, pre-W2.2) are automatically
coerced into display-only Numerics (``raw=None``). Wave 4 will tighten
the union to ``Numeric`` only after service and frontend have migrated.

See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md``
§ 3.3 / § 13.2.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator

from backend.app.schemas.common_numeric import Numeric


def _coerce_display_numeric(value: Any) -> Any:
    """Coerce a bare display ``str`` into a display-only ``Numeric``.

    - ``str`` → ``Numeric(raw=None, unit="yuan", display=value, precision=0, sign_aware=True)``
    - ``dict`` with Numeric shape → passthrough (pydantic will validate)
    - ``Numeric`` → passthrough
    - other → passthrough (pydantic will raise)
    """
    if isinstance(value, str):
        return {
            "raw": None,
            "unit": "yuan",
            "display": value,
            "precision": 0,
            "sign_aware": True,
        }
    return value


class ExecutiveMetric(BaseModel):
    id: str
    label: str
    value: Numeric
    delta: Numeric
    tone: str
    detail: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_str(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "value" in out:
            out["value"] = _coerce_display_numeric(out["value"])
        if "delta" in out:
            out["delta"] = _coerce_display_numeric(out["delta"])
        return out


class OverviewPayload(BaseModel):
    title: str
    metrics: list[ExecutiveMetric]


class SummaryPoint(BaseModel):
    id: str
    label: str
    tone: str
    text: str


class SummaryPayload(BaseModel):
    title: str
    report_date: str | None = None
    narrative: str
    points: list[SummaryPoint]


class AttributionSegment(BaseModel):
    id: str
    label: str
    amount: Numeric
    tone: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_amount_display(cls, data: Any) -> Any:
        """Merge legacy ``{amount: float, display_amount: str}`` into ``amount: Numeric``."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        amount = out.get("amount")
        display_amount = out.pop("display_amount", None)

        if isinstance(amount, (int, float)) and isinstance(display_amount, str):
            # Legacy kwargs: amount is yi-denominated float, display is pre-formatted
            out["amount"] = {
                "raw": float(amount) * 1e8,
                "unit": "yuan",
                "display": display_amount,
                "precision": 2,
                "sign_aware": True,
            }
        elif isinstance(amount, str) and display_amount is None:
            out["amount"] = _coerce_display_numeric(amount)
        # else: amount is already dict / Numeric → let pydantic validate
        return out


class PnlAttributionPayload(BaseModel):
    title: str
    total: Numeric
    segments: list[AttributionSegment]

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_total(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "total" in out:
            out["total"] = _coerce_display_numeric(out["total"])
        return out


class RiskSignal(BaseModel):
    id: str
    label: str
    value: Numeric
    status: str
    detail: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_value(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "value" in out:
            out["value"] = _coerce_display_numeric(out["value"])
        return out


class RiskOverviewPayload(BaseModel):
    title: str
    signals: list[RiskSignal]


class ContributionRow(BaseModel):
    id: str
    name: str
    owner: str
    contribution: Numeric
    completion: int
    status: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_contribution(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "contribution" in out:
            out["contribution"] = _coerce_display_numeric(out["contribution"])
        return out


class ContributionPayload(BaseModel):
    title: str
    rows: list[ContributionRow]


class AlertItem(BaseModel):
    id: str
    severity: str
    title: str
    occurred_at: str
    detail: str


class AlertsPayload(BaseModel):
    title: str
    items: list[AlertItem]


class HomeSnapshotPayload(BaseModel):
    """Authoritative unified home snapshot payload.

    `mode="strict"`: `report_date` is the most recent day where **all four**
    governed business domains (balance / pnl / liability / bond) are
    available. `domains_missing=[]` and all four entries in
    `domains_effective_date` equal `report_date`.

    `mode="partial"`: user-requested or latest historical day; missing
    business domains listed in `domains_missing`; per-domain effective_date
    in `domains_effective_date` may diverge.

    Design reference: docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md § 4.
    """

    report_date: str
    mode: Literal["strict", "partial"]
    source_surface: Literal["executive_analytical"]
    overview: OverviewPayload
    attribution: PnlAttributionPayload
    domains_missing: list[str]
    domains_effective_date: dict[str, str]
