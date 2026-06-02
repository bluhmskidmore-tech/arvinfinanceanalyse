"""Curve engine data types — immutable, thread-safe, zero external dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class InterpolationMethod(str, Enum):
    LINEAR = "linear"
    CUBIC_SPLINE = "cubic_spline"


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """Single (years, rate) observation."""
    years: float
    rate: Decimal


@dataclass(frozen=True, slots=True)
class FittedCurve:
    """Immutable fitted curve representation.

    ``points`` must be sorted ascending by ``years``.
    ``spline_coefficients`` is populated only when ``method == CUBIC_SPLINE``.
    Each tuple is ``(a, b, c, d)`` for segment *i*:
        S_i(x) = a + b·(x - x_i) + c·(x - x_i)² + d·(x - x_i)³
    """
    method: InterpolationMethod
    points: tuple[CurvePoint, ...]
    spline_coefficients: tuple[tuple[float, float, float, float], ...] | None = None
