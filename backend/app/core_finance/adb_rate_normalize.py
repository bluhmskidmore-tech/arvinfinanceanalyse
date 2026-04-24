"""利率归一化（与 V1 `rate_utils.RATE_INPUT_OVERRIDES` 对齐，供 ADB 月度 NIM 计算）。"""

from __future__ import annotations

import math

import pandas as pd

RATE_INPUT_OVERRIDES: dict[str, str] = {
    "yield_to_maturity": "auto",
    "coupon_rate": "auto",
    "interest_rate": "auto",
    "interbank_interest_rate": "percent",
}


def normalize_rate_values(
    values: list[object],
    field_name: str,
    override: str | None = None,
) -> list[float]:
    if override is None:
        override = RATE_INPUT_OVERRIDES.get(field_name, "auto")

    if override == "percent":
        return [_normalize_percent_value(value) for value in values]
    if override == "decimal":
        return [_normalize_decimal_value(value) for value in values]

    if field_name == "interbank_interest_rate":
        return [_normalize_percent_value(value) for value in values]
    return [_normalize_auto_value(value) for value in values]


def normalize_rate_series_pd(
    rate_series: pd.Series,
    field_name: str,
    override: str | None = None,
) -> pd.Series:
    normalized = normalize_rate_values(
        rate_series.tolist(),
        field_name=field_name,
        override=override,
    )
    return pd.Series(normalized, index=rate_series.index, dtype=float)


def _coerce_rate_number(value: object) -> float | None:
    if value is None:
        return None

    candidate = value
    if hasattr(candidate, "item"):
        try:
            candidate = candidate.item()
        except Exception:
            pass

    if isinstance(candidate, str):
        candidate = candidate.strip()
        if not candidate or candidate.lower() in {"nan", "none", "null", "<na>", "inf", "-inf"}:
            return None

    try:
        number = float(candidate) if isinstance(candidate, (int, float, str)) else float(str(candidate))
    except (TypeError, ValueError):
        return None

    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _normalize_percent_value(value: object) -> float:
    number = _coerce_rate_number(value)
    if number is None:
        return 0.0
    return number / 100.0


def _normalize_decimal_value(value: object) -> float:
    number = _coerce_rate_number(value)
    if number is None:
        return 0.0
    return number


def _normalize_auto_value(value: object) -> float:
    number = _coerce_rate_number(value)
    if number is None:
        return 0.0
    if 1 <= number <= 100:
        return number / 100.0
    return number
