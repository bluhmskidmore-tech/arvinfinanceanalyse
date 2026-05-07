from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class YieldCurvePoint:
    tenor: str
    rate_pct: Decimal


@dataclass(slots=True, frozen=True)
class YieldCurveSnapshot:
    curve_type: str
    trade_date: str
    points: list[YieldCurvePoint]
    vendor_name: str
    vendor_version: str
    source_version: str
