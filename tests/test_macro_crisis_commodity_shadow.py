from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.app.core_finance.macro.crisis_commodity_shadow import (
    evaluate_crisis_commodity_shadow,
)


_HISTORY_SHORT_NEXT_STEP = (
    "先补齐商品期货历史数据，再做历史回测、相关性检验和权重审批。"
)
_REVIEW_READY_NEXT_STEP = (
    "进入公式前仍需历史回测、相关性检验、权重审批和版本记录。"
)


def _price_frame(values: list[float]) -> pd.DataFrame:
    start = date(2026, 1, 1)
    return pd.DataFrame(
        [
            {"date": start + timedelta(days=offset), "value": value}
            for offset, value in enumerate(values)
        ]
    )


def _crisis_history(values: list[float]) -> pd.DataFrame:
    start = date(2026, 1, 1)
    return pd.DataFrame(
        {"crisis_score": values},
        index=pd.to_datetime(
            [start + timedelta(days=offset) for offset in range(1, len(values) + 1)]
        ),
    )


def test_crisis_commodity_shadow_reports_missing_history_without_calculating() -> None:
    result = evaluate_crisis_commodity_shadow(
        pd.DataFrame(columns=["date", "value"]),
        pd.DataFrame(columns=["crisis_score"]),
    )

    assert result == {
        "status": "history_short",
        "label": "影子评估样本不足",
        "sample_count": 0,
        "minimum_sample_count": 20,
        "sample_gap": 20,
        "target": "crisis_score",
        "candidate_metric": "daily_return",
        "summary": "商品候选缺少足够历史样本，暂不能评估相关性。",
        "next_step": _HISTORY_SHORT_NEXT_STEP,
    }


def test_crisis_commodity_shadow_preserves_short_overlap_semantics() -> None:
    result = evaluate_crisis_commodity_shadow(
        _price_frame([100.0, 101.0, 102.0, 103.0, 104.0]),
        _crisis_history([1.0, 2.0, 3.0, 4.0]),
    )

    assert result == {
        "status": "history_short",
        "label": "影子评估样本不足",
        "sample_count": 4,
        "minimum_sample_count": 20,
        "sample_gap": 16,
        "target": "crisis_score",
        "candidate_metric": "daily_return",
        "summary": "商品候选与 Crisis Score 仅 4 个重叠样本，暂不能评估相关性。",
        "next_step": _HISTORY_SHORT_NEXT_STEP,
    }


def test_crisis_commodity_shadow_preserves_review_ready_metrics() -> None:
    result = evaluate_crisis_commodity_shadow(
        _price_frame([float(100 + offset * offset) for offset in range(21)]),
        _crisis_history([float(value) for value in range(1, 21)]),
    )

    assert result == {
        "status": "review_ready",
        "label": "影子评估可读",
        "sample_count": 20,
        "window_start": "2026-01-02",
        "window_end": "2026-01-21",
        "target": "crisis_score",
        "candidate_metric": "daily_return",
        "same_day_correlation": 0.63,
        "lead_1d_correlation": 0.67,
        "lag_1d_correlation": 0.54,
        "latest_return_z": 0.0183,
        "crisis_hit_rate": 1.0,
        "crisis_sample_count": 5,
        "summary": "影子评估：样本 20，同日相关 0.63，危机期命中率 1.00。",
        "next_step": _REVIEW_READY_NEXT_STEP,
    }


def test_crisis_commodity_shadow_keeps_degenerate_metrics_nullable() -> None:
    result = evaluate_crisis_commodity_shadow(
        _price_frame([100.0] * 21),
        _crisis_history([float(value) for value in range(20)]),
    )

    assert result["status"] == "review_ready"
    assert result["same_day_correlation"] is None
    assert result["lead_1d_correlation"] is None
    assert result["lag_1d_correlation"] is None
    assert result["latest_return_z"] is None
    assert result["crisis_hit_rate"] == 0.0
    assert result["summary"] == "影子评估：样本 20，同日相关 缺失，危机期命中率 0.00。"
