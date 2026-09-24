"""A9 宏观口径修复的针对性测试。

覆盖三处口径修复：
- MACRO-P1-02：GDP 现价当季值（未季调水平序列）改用同季上年（四期）差分，
  消除 Q1 季节性对 growth 信号的系统性压低。
- MACRO-P1-04：政策利率 21 日变动只比较"当前日/回看日"两日均有观测的
  工具交集，消除候选工具集合差异带来的伪变动。
- yield_curve_shape.percentile_1y：分位只由当前观测日回看一年内的历史决定，
  并披露实际窗口（cutoff / 起止日期 / 观测数）。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.core_finance import macro_bond_linkage as mbl
from backend.app.core_finance.macro import (
    compute_monetary_policy_stance,
    compute_yield_curve_shape,
)

_REPORT = date(2026, 7, 10)

# ---------------------------------------------------------------------------
# 子项 1（MACRO-P1-02）：GDP 现价当季值同季上年差分
# ---------------------------------------------------------------------------

# 13 个季度、带真实季节形态（Q1 谷、Q4 峰）且同季逐年 +10 的名义 GDP 水平序列。
_GDP_QUARTERLY_POINTS = [
    (date(2023, 3, 31), 280.0), (date(2023, 6, 30), 300.0),
    (date(2023, 9, 30), 310.0), (date(2023, 12, 31), 340.0),
    (date(2024, 3, 31), 290.0), (date(2024, 6, 30), 310.0),
    (date(2024, 9, 30), 320.0), (date(2024, 12, 31), 350.0),
    (date(2025, 3, 31), 300.0), (date(2025, 6, 30), 320.0),
    (date(2025, 9, 30), 330.0), (date(2025, 12, 31), 360.0),
    (date(2026, 3, 31), 310.0),
]
_GDP_SERIES_ID = "EMM00619381"
_INDUSTRIAL_SERIES_ID = "EMM00008445"


def test_gdp_level_series_uses_same_quarter_prior_year_diff() -> None:
    factor = mbl._score_latest_delta(
        _GDP_SERIES_ID, "中国:GDP:现价:当季值", 0.8, _GDP_QUARTERLY_POINTS
    )

    assert factor is not None
    assert factor["diff_lag"] == 4
    # 对比基期必须是同季上年（2025Q1），而不是相邻的 2025Q4。
    assert factor["previous_date"] == "2025-03-31"
    assert factor["report_date"] == "2026-03-31"
    # 310(2026Q1) - 300(2025Q1) = +10；两点均在 winsorize 截尾范围内。
    assert factor["delta"] == pytest.approx(10.0)
    # 同比为正 => growth 信号为正。旧口径（相邻差分 310-360=-50，winsorize 后
    # -38）会把该点打成强负信号（score≈-0.597）。
    assert factor["score"] > 0


def test_gdp_q1_seasonal_trough_no_longer_flips_growth_negative() -> None:
    # 工业增加值配平（delta=0，score=0），growth_score 完全由 GDP 决定。
    history = {
        _GDP_SERIES_ID: _GDP_QUARTERLY_POINTS,
        _INDUSTRIAL_SERIES_ID: [(date(2026, 5, 31), 1.2), (date(2026, 6, 30), 1.2)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mbl.compute_macro_environment_score(latest, history, lookback_days=90)

    # 同季逐年增长的序列，Q1 期末不得再产生负的 growth 信号。
    assert score.growth_score > 0
    gdp_factor = next(
        factor
        for factor in score.contributing_factors
        if factor["series_id"] == _GDP_SERIES_ID
    )
    assert gdp_factor["diff_lag"] == 4
    assert gdp_factor["delta"] == pytest.approx(10.0)


def test_gdp_history_shorter_than_four_quarters_degrades_with_warning() -> None:
    history = {
        _GDP_SERIES_ID: _GDP_QUARTERLY_POINTS[-3:],  # 仅 3 个季度，无法做四期差分
        _INDUSTRIAL_SERIES_ID: [(date(2026, 5, 31), 1.2), (date(2026, 6, 30), 1.5)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mbl.compute_macro_environment_score(latest, history, lookback_days=90)

    assert any("中国:GDP:现价:当季值" in warning for warning in score.warnings)
    assert all(
        factor["series_id"] != _GDP_SERIES_ID
        for factor in score.contributing_factors
        if factor["category"] == "growth"
    )
    # growth 退化为仅由工业增加值（同比上行）驱动。
    assert score.growth_score > 0


def test_non_seasonal_growth_series_keeps_adjacent_diff() -> None:
    factor = mbl._score_latest_delta(
        _INDUSTRIAL_SERIES_ID,
        "工业增加值:当月同比",
        1.0,
        [(date(2026, 5, 31), 1.2), (date(2026, 6, 30), 1.5)],
    )

    assert factor is not None
    assert factor["diff_lag"] == 1
    assert factor["previous_date"] == "2026-05-31"
    assert factor["delta"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# 子项 2（MACRO-P1-04）：政策利率两日工具交集
# ---------------------------------------------------------------------------


def _policy_rows(*, mlf_prior: float) -> list[dict]:
    """22 个交易日均有 DR007；MLF/LPR 两日都有，RRP 仅回看日存在。"""
    rows: list[dict] = [
        {
            "biz_date": _REPORT - timedelta(days=offset),
            "curve_id": "CN_DR",
            "tenor": "7D",
            "rate_value": 1.60,
        }
        for offset in range(22)
    ]
    current_day = _REPORT
    lookback_day = _REPORT - timedelta(days=21)
    rows += [
        {"biz_date": current_day, "curve_id": "CN_MLF", "tenor": "1Y", "rate_value": 2.00},
        {"biz_date": current_day, "curve_id": "CN_LPR", "tenor": "1Y", "rate_value": 3.00},
        {"biz_date": lookback_day, "curve_id": "CN_MLF", "tenor": "1Y", "rate_value": mlf_prior},
        {"biz_date": lookback_day, "curve_id": "CN_LPR", "tenor": "1Y", "rate_value": 3.00},
        # 仅回看日存在的工具：不得进入变动比较。
        {"biz_date": lookback_day, "curve_id": "CN_RRP", "tenor": "7D", "rate_value": 1.80},
    ]
    return rows


def test_policy_rate_change_ignores_instruments_missing_on_either_day() -> None:
    # 交集（MLF/LPR）两日同值：变动必须为 0，不得因回看日多出 RRP 产生
    # 伪上行（旧口径给出 +23.33bp、policy_rate 分量 -93.33）。
    payload = compute_monetary_policy_stance(_policy_rows(mlf_prior=2.00), report_date=_REPORT)

    assert payload["key_metrics"]["policy_change_21d_bp"] == pytest.approx(0.0)
    policy_component = next(
        component for component in payload["components"] if component["key"] == "policy_rate"
    )
    assert policy_component["score"] == pytest.approx(0.0)


def test_policy_rate_change_counts_only_intersection_moves() -> None:
    # MLF 实际下调 10bp：交集 {MLF, LPR} 两工具均值变动 = -5bp；
    # 仅回看日存在的 RRP 不得把方向拉成正值（旧口径给出 +20bp）。
    payload = compute_monetary_policy_stance(_policy_rows(mlf_prior=2.10), report_date=_REPORT)

    assert payload["key_metrics"]["policy_change_21d_bp"] == pytest.approx(-5.0)


# ---------------------------------------------------------------------------
# 子项 3：percentile_1y 真实一年窗口
# ---------------------------------------------------------------------------


def _curve_rows(*, outside_10y: float) -> list[dict]:
    """3 年历史：当前 50bp；一年内 11 个月度点 80bp；一年外 23 个月度点由入参控制。"""
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.50},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.00},
    ]
    for k in range(1, 12):  # 2025-08-10 .. 2026-06-10，全部在一年窗口内
        month, year = (7 - k, 2026) if 7 - k >= 1 else (7 - k + 12, 2025)
        sample_date = date(year, month, 10)
        rows += [
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.50},
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.30},
        ]
    year, month = 2023, 8
    for _ in range(23):  # 2023-08-10 .. 2025-06-10，全部在一年窗口外
        sample_date = date(year, month, 10)
        rows += [
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.50},
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": outside_10y},
        ]
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return rows


def test_percentile_1y_uses_only_last_year_window() -> None:
    # 一年内历史（80bp）全部高于当前（50bp）=> 分位必须为 0；
    # 旧口径把 3 年历史全部纳入，窗外 20bp 低值会把分位推到 67.65。
    payload = compute_yield_curve_shape(_curve_rows(outside_10y=1.70), report_date=_REPORT)

    assert payload["percentile_1y"] == pytest.approx(0.0)
    window = payload["percentile_1y_window"]
    assert window["observation_count"] == 11
    assert window["cutoff_1y"] == "2025-07-10"
    assert window["window_start"] == "2025-08-10"
    assert window["window_end"] == "2026-06-10"


def test_percentile_1y_invariant_to_history_outside_window() -> None:
    low_outside = compute_yield_curve_shape(_curve_rows(outside_10y=1.70), report_date=_REPORT)
    high_outside = compute_yield_curve_shape(_curve_rows(outside_10y=2.40), report_date=_REPORT)

    # 3 年 fixture 中仅窗外数据不同：分位必须完全一致（只由最近一年决定）。
    assert low_outside["percentile_1y"] == high_outside["percentile_1y"]
    assert low_outside["percentile_1y_window"] == high_outside["percentile_1y_window"]


def test_percentile_1y_short_history_discloses_actual_window() -> None:
    rows = [
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.50},
        {"biz_date": _REPORT, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.00},
    ]
    for k in range(1, 4):  # 仅 3 个月历史，不足一年
        sample_date = _REPORT - timedelta(days=30 * k)
        rows += [
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "1Y", "rate_value": 1.50},
            {"biz_date": sample_date, "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 1.80},
        ]

    payload = compute_yield_curve_shape(rows, report_date=_REPORT)

    # 30bp 历史全部低于当前 50bp => 分位 100；窗口披露实际只有 3 个观测。
    assert payload["percentile_1y"] == pytest.approx(100.0)
    window = payload["percentile_1y_window"]
    assert window["observation_count"] == 3
    assert window["window_start"] == (_REPORT - timedelta(days=90)).isoformat()
    assert window["window_end"] == (_REPORT - timedelta(days=30)).isoformat()
