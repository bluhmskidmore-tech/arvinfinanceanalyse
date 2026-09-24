"""模型六 Crisis Score 落盘脚本（crisis_score_cn.py）回归测试。

聚焦审计发现的核心口径：
1. 加权公式 Σ(w_i·z_i)/Σ|w_i| 中，某分项（如 credit_spread 上游断供）z 为 NaN 时，
   其权重必须逐日从分母剔除，分数不能被系统性压小（不掩 0，也不虚增分母）。
2. 落盘脚本与实时 capability 链（backend/app/core_finance/macro/crisis_score.py）
   的归一化口径保持一致。
3. 阈值分档为尽调笔记 1/2/3 边界的向下扩展（<0 宽松档），边界与两条链一致。
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.crisis_score import (
    classify_crisis_score,
    compute_crisis_score as capability_compute_crisis_score,
)
from backend.app.core_finance.macro.toolkit import get_toolkit_script

WEIGHTS = {
    "equity_vol": 0.25,
    "credit_spread": 0.25,
    "fx_vol": 0.15,
    "commodity_vol": 0.15,
    "liquidity_stress": 0.20,
}
Z_WINDOW = 80


@pytest.fixture(scope="module")
def script_module():
    script = get_toolkit_script("crisis_score_cn")
    spec = importlib.util.spec_from_file_location("_crisis_score_cn_under_test", script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_indicators(periods: int = 90) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=periods, freq="D")
    idx = np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "equity_vol": 20.0 + 3.0 * np.sin(idx / 5.0) + idx * 0.05,
            "credit_spread": 0.8 + 0.1 * np.sin(idx / 7.0),
            "fx_vol": 3.0 + 0.5 * np.cos(idx / 6.0),
            "commodity_vol": 12.0 + 2.0 * np.sin(idx / 9.0),
            "liquidity_stress": 0.1 * np.sin(idx / 4.0),
        },
        index=dates,
    )


def _manual_score_row(row: pd.Series) -> float:
    numerator = sum(
        WEIGHTS[key] * row[f"{key}_z"] for key in WEIGHTS if pd.notna(row.get(f"{key}_z"))
    )
    denominator = sum(
        abs(WEIGHTS[key]) for key in WEIGHTS if pd.notna(row.get(f"{key}_z"))
    )
    return numerator / denominator


def test_full_components_score_matches_note_formula(script_module) -> None:
    indicators = _build_indicators()
    result = script_module.compute_crisis_score(indicators, z_window=Z_WINDOW)

    assert not result.empty
    z_columns = [column for column in result.columns if column.endswith("_z")]
    complete_rows = result[result[z_columns].notna().all(axis=1)]
    assert len(complete_rows) >= 10
    for _, row in complete_rows.iterrows():
        # 五项齐全时 Σ|w_i| = 1.0，Score 应等于加权和本身
        assert row["crisis_score"] == pytest.approx(_manual_score_row(row), abs=1e-12)


def test_missing_credit_spread_weight_removed_from_denominator(script_module) -> None:
    complete = _build_indicators()
    degraded = complete.copy()
    degraded.loc[degraded.index[-3:], "credit_spread"] = np.nan

    baseline = script_module.compute_crisis_score(complete, z_window=Z_WINDOW)
    result = script_module.compute_crisis_score(degraded, z_window=Z_WINDOW)

    for missing_date in degraded.index[-3:]:
        row = result.loc[missing_date]
        assert pd.isna(row["credit_spread_z"])
        available_sum = sum(
            WEIGHTS[key] * row[f"{key}_z"] for key in WEIGHTS if pd.notna(row.get(f"{key}_z"))
        )
        # 缺 credit_spread（权重 0.25）当日分母应为 0.75，而不是 1.0
        assert row["crisis_score"] == pytest.approx(available_sum / 0.75, abs=1e-12)
        assert row["crisis_score"] != pytest.approx(available_sum / 1.0, abs=1e-9)

    # 未缺失的日期分数不受影响
    unaffected = degraded.index[degraded.index < degraded.index[-3]]
    changed = (
        baseline.loc[baseline.index.intersection(unaffected), "crisis_score"]
        - result.loc[result.index.intersection(unaffected), "crisis_score"]
    ).abs()
    assert float(changed.max()) == pytest.approx(0.0, abs=1e-12)


def test_script_normalization_matches_realtime_capability(script_module) -> None:
    degraded = _build_indicators()
    degraded.loc[degraded.index[-3:], "credit_spread"] = np.nan
    degraded.loc[degraded.index[-1], "fx_vol"] = np.nan

    script_result = script_module.compute_crisis_score(degraded, z_window=Z_WINDOW)
    capability_result = capability_compute_crisis_score(
        degraded, z_window=Z_WINDOW, min_z_observations=60
    )

    pd.testing.assert_series_equal(
        script_result["crisis_score"],
        capability_result["crisis_score"],
        check_exact=False,
        check_freq=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_regime_thresholds_extend_note_bands(script_module) -> None:
    # 笔记四档边界 1/2/3 保持一致；<0 为实现新增的“宽松”扩展档
    expectations = [
        (-0.1, "宽松"),
        (0.0, "正常"),
        (0.5, "正常"),
        (1.0, "警惕"),
        (1.5, "警惕"),
        (2.0, "高风险"),
        (2.5, "高风险"),
        (3.0, "危机"),
        (3.5, "危机"),
    ]
    for score, expected_regime in expectations:
        regime, recommendation = script_module.classify_regime(score)
        assert regime == expected_regime
        assert recommendation
        # 与实时 capability 链分档保持一致
        assert classify_crisis_score(score)[0] == expected_regime
