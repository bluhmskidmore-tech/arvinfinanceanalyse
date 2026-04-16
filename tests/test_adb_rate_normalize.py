from __future__ import annotations

from decimal import Decimal

import pandas as pd

from tests.helpers import load_module


def test_normalize_rate_values_auto_converts_percent_like_inputs() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    normalized = module.normalize_rate_values(
        [Decimal("2.4"), Decimal("0.035"), None, "bad"],
        field_name="yield_to_maturity",
    )

    assert normalized == [0.024, 0.035, 0.0, 0.0]


def test_normalize_rate_series_pd_preserves_index_and_interbank_percent_rule() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    series = pd.Series([Decimal("1.5"), Decimal("2.0")], index=["a", "b"])
    normalized = module.normalize_rate_series_pd(series, field_name="interbank_interest_rate")

    assert list(normalized.index) == ["a", "b"]
    assert normalized.tolist() == [0.015, 0.02]


def test_normalize_rate_values_handles_nan_like_inputs_without_pandas_vector_ops() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    normalized = module.normalize_rate_values(
        [float("nan"), "nan", "<NA>", "2.5", "0.035"],
        field_name="coupon_rate",
    )

    assert normalized == [0.0, 0.0, 0.0, 0.025, 0.035]
