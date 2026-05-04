"""Shared Numeric primitive used across all governed contract schemas.

This module is the canonical definition of how backend exposes a numeric value
to the frontend. All downstream payloads that display a governed number (money,
percent, bp, ratio, count, dv01) should switch from raw strings to ``Numeric``.

Design reference: ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 3.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NumericUnit = Literal["yuan", "pct", "bp", "ratio", "count", "dv01", "yi"]


class Numeric(BaseModel):
    """Canonical typed numeric value exposed across governed contracts.

    Fields:
        raw:          Unconverted raw number in ``unit``; ``None`` means truly missing.
        unit:         The unit of ``raw``; drives how callers format and compare values.
        display:      Pre-formatted display string (sign, unit suffix, precision all
                      baked in); for ``raw is None`` callers should render ``"—"``.
        precision:    Decimal places used to build ``display``; non-negative.
        sign_aware:   When ``True`` callers render negatives and tone-color by sign;
                      when ``False`` callers should treat the value as absolute-valued
                      (e.g. composition pie slices) and must label it accordingly.
    """

    raw: float | None
    unit: NumericUnit
    display: str
    precision: int = Field(ge=0)
    sign_aware: bool


def null_numeric(
    *,
    unit: NumericUnit,
    display: str = "—",
    precision: int = 2,
    sign_aware: bool = True,
) -> Numeric:
    """Build a ``Numeric`` that explicitly represents missing data.

    Callers should prefer this over ad-hoc zero values so the frontend can
    distinguish "no data" from "zero".
    """
    return Numeric(
        raw=None,
        unit=unit,
        display=display,
        precision=precision,
        sign_aware=sign_aware,
    )


def numeric_from_raw(
    *,
    raw: float | None,
    unit: NumericUnit,
    precision: int = 2,
    sign_aware: bool = True,
    signed_format: bool = True,
) -> Numeric:
    """Build a ``Numeric`` from a raw value, generating a default ``display``.

    This is a convenience helper for service-layer construction when callers
    don't need a custom display string. Frontend-facing services that want a
    specific format (e.g. "+12.34 亿") should build the display string via
    their existing formatters and pass it explicitly to ``Numeric(...)``.

    Args:
        raw:           Raw numeric value, or ``None`` for missing.
        unit:          Target unit.
        precision:     Decimal places.
        sign_aware:    Whether callers should render signed.
        signed_format: When ``True`` and ``sign_aware`` and ``raw >= 0``, the
                       default display includes a leading ``+``.
    """
    if raw is None:
        return null_numeric(unit=unit, precision=precision, sign_aware=sign_aware)

    raw_value = float(raw)
    normalized_raw = _normalize_numeric_raw(raw_value, unit)
    display = _format_numeric_display(
        raw=normalized_raw,
        unit=unit,
        precision=precision,
        sign_aware=sign_aware,
        signed_format=signed_format,
    )

    return Numeric(
        raw=normalized_raw,
        unit=unit,
        display=display,
        precision=precision,
        sign_aware=sign_aware,
    )


def _normalize_numeric_raw(raw: float, unit: NumericUnit) -> float:
    if unit == "pct" and abs(raw) >= 1.0:
        return raw / 100.0
    return raw


def _format_numeric_display(
    *,
    raw: float,
    unit: NumericUnit,
    precision: int,
    sign_aware: bool,
    signed_format: bool,
) -> str:
    if unit == "pct":
        value = raw * 100.0
        return _format_signed_number(value, precision, sign_aware, signed_format, suffix="%")
    if unit == "bp":
        return _format_signed_number(raw, precision, sign_aware, signed_format, suffix=" bp")
    if unit == "yi":
        return _format_signed_number(raw, precision, sign_aware, signed_format, suffix=" 亿")
    if unit == "count":
        return f"{raw:,.0f}"
    if unit == "dv01":
        return f"{raw:,.{precision}f}"
    return _format_signed_number(raw, precision, sign_aware, signed_format)


def _format_signed_number(
    value: float,
    precision: int,
    sign_aware: bool,
    signed_format: bool,
    suffix: str = "",
) -> str:
    if sign_aware and signed_format and value >= 0:
        return f"+{value:,.{precision}f}{suffix}"
    return f"{value:,.{precision}f}{suffix}"
