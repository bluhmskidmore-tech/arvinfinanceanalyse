"""Formal yield-curve term-structure (canonical tenor ladder) response models."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from backend.app.schemas.common_numeric import Numeric


class YieldCurveTermPoint(BaseModel):
    tenor: str
    yield_pct: Numeric | None = None
    delta_bp_prev: Numeric | None = None


class YieldCurveTermStructureCurve(BaseModel):
    curve_type: str
    trade_date_requested: str
    trade_date_resolved: str | None = None
    points: list[YieldCurveTermPoint] = Field(default_factory=list)
    source_version: str = ""
    rule_version: str = ""
    vendor_name: str = ""
    vendor_version: str = ""


class YieldCurveTermStructureResponse(BaseModel):
    report_date: date
    curves: list[YieldCurveTermStructureCurve] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    computed_at: str
