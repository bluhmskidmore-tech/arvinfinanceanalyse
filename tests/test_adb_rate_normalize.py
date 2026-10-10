from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from tests.helpers import load_module


def test_normalize_rate_values_auto_converts_percent_like_inputs() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize_contract",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    normalized = module.normalize_rate_values(
        [Decimal("2.4"), Decimal("0.035"), None, "bad"],
        field_name="yield_to_maturity",
    )

    # yield_to_maturity is percent: 2.4 -> 0.024; 0.035 -> 0.035% -> 0.00035.
    # Missing/bad inputs stay nullable so weighted-rate callers can exclude them.
    assert normalized[:2] == pytest.approx([0.024, 0.00035], abs=1e-10)
    assert normalized[2:] == [None, None]


def test_normalize_rate_series_pd_preserves_index_and_interbank_percent_rule() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize_contract_pd",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    series = pd.Series([Decimal("1.5"), Decimal("2.0")], index=["a", "b"])
    normalized = module.normalize_rate_series_pd(series, field_name="interbank_interest_rate")

    assert list(normalized.index) == ["a", "b"]
    assert normalized.tolist() == [0.015, 0.02]


def test_normalize_rate_values_handles_nan_like_inputs_without_vector_dependency() -> None:
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize_contract_nan",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    normalized = module.normalize_rate_values(
        [float("nan"), "nan", "<NA>", "2.5", "0.035"],
        field_name="coupon_rate",
    )

    # coupon_rate is percent: 2.5 -> 0.025; 0.035 -> 0.035% -> 0.00035.
    # Liability ADB enrich keeps missing coupons nullable; explicit 0 remains 0% for zero-coupon semantics.
    assert normalized[:3] == [None, None, None]
    assert normalized[3:] == pytest.approx([0.025, 0.00035], abs=1e-10)


def test_normalize_percent_rejects_negative_and_dirty_extremes_like_rate_units() -> None:
    """percent 口径须与 rate_units.normalize_percent_rate_to_decimal 防护一致：负数/>20 → None。"""
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize_contract_dirty",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    normalized = module.normalize_rate_values(
        [
            Decimal("-0.5"),        # 负利率：拒收
            Decimal("20720.93"),    # 取证极值 ytm（2026-07-19 审计）：拒收
            Decimal("20.01"),       # 略超上界：拒收
            Decimal("20"),          # 上界本身：放行 -> 0.20
            Decimal("0"),           # 零票息：放行 -> 0.0
            Decimal("3.5"),         # 正常百分数：放行 -> 0.035
        ],
        field_name="yield_to_maturity",
    )

    assert normalized[:3] == [None, None, None]
    assert normalized[3:] == pytest.approx([0.20, 0.0, 0.035], abs=1e-10)


def test_normalize_rate_series_pd_keeps_dirty_rows_nan_for_weighted_exclusion() -> None:
    """pd 路径下脏值应为 NaN（dtype=float 的 None 表示），供 build_rate_map 分子分母同时跳过。"""
    module = load_module(
        "backend.app.core_finance.adb_rate_normalize_contract_pd_dirty",
        "backend/app/core_finance/adb_rate_normalize.py",
    )

    series = pd.Series([Decimal("-1"), Decimal("999"), Decimal("2.4")], index=["a", "b", "c"])
    normalized = module.normalize_rate_series_pd(series, field_name="coupon_rate")

    assert list(normalized.index) == ["a", "b", "c"]
    assert pd.isna(normalized.loc["a"])
    assert pd.isna(normalized.loc["b"])
    assert normalized.loc["c"] == pytest.approx(0.024, abs=1e-10)
