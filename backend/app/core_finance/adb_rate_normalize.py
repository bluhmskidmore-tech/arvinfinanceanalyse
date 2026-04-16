"""利率归一化（与 V1 `rate_utils.RATE_INPUT_OVERRIDES` 对齐，供 ADB 月度 NIM 计算）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

RATE_INPUT_OVERRIDES: dict[str, str] = {
    "yield_to_maturity": "auto",
    "coupon_rate": "auto",
    "interest_rate": "auto",
    "interbank_interest_rate": "percent",
}


def normalize_rate_series_pd(
    rate_series: pd.Series,
    field_name: str,
    override: str | None = None,
) -> pd.Series:
    if override is None:
        override = RATE_INPUT_OVERRIDES.get(field_name, "auto")

    numeric = pd.to_numeric(rate_series, errors="coerce")

    if override == "percent":
        return (numeric / 100.0).fillna(0.0).astype(float)
    if override == "decimal":
        return numeric.fillna(0.0).astype(float)

    is_interbank = field_name == "interbank_interest_rate"
    if is_interbank:
        return (numeric / 100.0).fillna(0.0).astype(float)
    mask = (numeric >= 1) & (numeric <= 100)
    result = np.where(mask, numeric / 100.0, numeric)
    return pd.Series(result, index=rate_series.index).fillna(0.0).astype(float)
