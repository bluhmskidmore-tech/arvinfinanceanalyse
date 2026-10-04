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
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro import crisis_score as crisis_score_module
from backend.app.core_finance.macro.crisis_score import (
    CRISIS_SCORE_TREND_WINDOWS,
    build_crisis_score_history_payload,
    classify_crisis_score,
    compute_crisis_score as capability_compute_crisis_score,
    compute_crisis_score_payload,
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


def _build_series_data(periods: int = 180) -> dict[str, list[tuple[object, float]]]:
    dates = pd.date_range("2025-01-01", periods=periods, freq="D")
    idx = np.arange(periods, dtype=float)
    values = {
        "hs300": 4000.0 + idx * 1.5 + 30.0 * np.sin(idx / 4.0),
        "aa_5y": 2.4 + 0.08 * np.sin(idx / 7.0) + idx * 0.0005,
        "gov_5y": 1.9 + 0.03 * np.cos(idx / 8.0) + idx * 0.0002,
        "usdcny": 7.0 + 0.02 * np.sin(idx / 5.0) + idx * 0.0001,
        "nanhua": 1000.0 + idx * 0.8 + 15.0 * np.cos(idx / 6.0),
        "dr007": 1.8 + 0.05 * np.sin(idx / 3.0),
        "reverse_repo_7d": 1.7 + 0.01 * np.cos(idx / 9.0),
    }
    return {
        key: [(point_date.date(), float(value)) for point_date, value in zip(dates, series, strict=True)]
        for key, series in values.items()
    }


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


def test_payload_exposes_backend_owned_20_and_60_point_trends() -> None:
    series_data = _build_series_data()
    report_date = series_data["hs300"][-1][0]

    payload = compute_crisis_score_payload(series_data, report_date=report_date)

    assert payload["data_status"] == "complete"
    assert [item["requested_window_points"] for item in payload["score_trends"]] == list(
        CRISIS_SCORE_TREND_WINDOWS
    )
    assert [item["window_points"] for item in payload["score_trends"]] == [20, 60]
    assert payload["score_trend"] == payload["score_trends"][0]
    expected_fields = {
        "requested_window_points",
        "window_points",
        "start_date",
        "end_date",
        "start_score",
        "end_score",
        "score_change",
        "start_percentile",
        "end_percentile",
        "percentile_change",
        "direction",
    }
    assert all(set(item) == expected_fields for item in payload["score_trends"])
    assert all(item["start_date"] < item["end_date"] for item in payload["score_trends"])


@pytest.mark.parametrize(
    ("raw_score", "published_score", "triggered"),
    [(1.99994, 1.9999, False), (1.99996, 2.0, True)],
)
def test_risk_gate_uses_the_published_four_decimal_score(
    monkeypatch,
    raw_score: float,
    published_score: float,
    triggered: bool,
) -> None:
    report_date = date(2026, 6, 30)
    point_index = pd.DatetimeIndex([pd.Timestamp(report_date)])

    monkeypatch.setattr(
        crisis_score_module,
        "compute_crisis_indicators",
        lambda *_args, **_kwargs: pd.DataFrame({"equity_vol": [1.0]}, index=point_index),
    )
    monkeypatch.setattr(
        crisis_score_module,
        "compute_crisis_score",
        lambda *_args, **_kwargs: pd.DataFrame({"crisis_score": [raw_score]}, index=point_index),
    )
    monkeypatch.setattr(
        crisis_score_module,
        "_component_details",
        lambda *_args, **_kwargs: [{"key": key} for key in WEIGHTS],
    )
    monkeypatch.setattr(crisis_score_module, "_component_warnings", lambda *_args, **_kwargs: [])

    payload = compute_crisis_score_payload({"hs300": [(report_date, 4000.0)]}, report_date=report_date)

    assert payload["crisis_score"] == published_score
    assert payload["risk_gate"]["eligible"] is True
    assert payload["risk_gate"]["triggered"] is triggered
    assert payload["risk_gate"]["reason_code"] == (
        "crisis_score_at_or_above_threshold"
        if triggered
        else "crisis_score_below_threshold"
    )


def test_score_trend_reports_flat_when_displayed_change_rounds_to_zero() -> None:
    scores = pd.Series(
        [1.23456, 1.23457],
        index=pd.date_range("2026-01-01", periods=2, freq="D"),
        dtype="float64",
    )

    trend = crisis_score_module._build_crisis_score_trend(scores, requested_window_points=2)

    assert trend["score_change"] == 0.0
    assert trend["direction"] == "flat"


def test_score_trend_percentiles_use_the_available_prefix_at_each_point() -> None:
    scores = pd.Series(
        [3.0, 1.0, 2.0],
        index=pd.date_range("2026-01-01", periods=3, freq="D"),
        dtype="float64",
    )

    trend = crisis_score_module._build_crisis_score_trend(
        scores,
        requested_window_points=2,
    )

    assert trend["start_percentile"] == 50.0
    assert trend["end_percentile"] == 66.67
    assert trend["percentile_change"] == 16.67


def test_risk_gate_fails_closed_when_all_inputs_lag_the_requested_date() -> None:
    series_data = _build_series_data()
    latest_input_date = series_data["hs300"][-1][0]
    requested_report_date = latest_input_date + timedelta(days=7)

    payload = compute_crisis_score_payload(
        series_data,
        report_date=requested_report_date,
    )

    assert payload["report_date"] == latest_input_date.isoformat()
    assert payload["requested_report_date"] == requested_report_date.isoformat()
    assert payload["data_status"] == "degraded"
    assert "CRISIS_SCORE_REPORT_DATE_LAG" in payload["warnings"]
    assert payload["risk_gate"] == {
        "eligible": False,
        "triggered": False,
        "threshold": 2.0,
        "reason_code": "crisis_score_data_not_complete",
    }


def test_score_history_marks_partial_weight_points_degraded() -> None:
    indicators = _build_indicators()
    degraded = indicators.copy()
    degraded.loc[degraded.index[-3:], "credit_spread"] = np.nan
    score_frame = capability_compute_crisis_score(
        degraded,
        z_window=Z_WINDOW,
        min_z_observations=60,
    )

    history = build_crisis_score_history_payload(score_frame, limit=4)

    assert history[0]["available_component_count"] == 5
    assert history[0]["component_count"] == 5
    assert history[0]["available_weight"] == pytest.approx(1.0)
    assert history[0]["data_status"] == "complete"
    for point in history[-3:]:
        assert point["available_component_count"] == 4
        assert point["component_count"] == 5
        assert point["available_weight"] == pytest.approx(0.75)
        assert point["data_status"] == "degraded"


def test_crisis_history_route_helper_preserves_component_z_scores() -> None:
    from backend.app.services.macro_toolkit_route_support import _crisis_score_history

    series_data = _build_series_data()
    report_date = series_data["hs300"][-1][0]

    score_frame = _crisis_score_history(series_data, report_date)
    history = build_crisis_score_history_payload(score_frame, limit=1)

    assert {f"{key}_z" for key in WEIGHTS}.issubset(score_frame.columns)
    assert history[0]["available_component_count"] == 5
    assert history[0]["available_weight"] == pytest.approx(1.0)
    assert history[0]["data_status"] == "complete"


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
