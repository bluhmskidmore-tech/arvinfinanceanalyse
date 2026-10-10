"""Pure crisis-score commodity shadow evaluation.

This calculation is observation-only.  It evaluates a candidate commodity
series against Crisis Score history without changing the official score.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

CRISIS_COMMODITY_SHADOW_MIN_SAMPLES = 20

_HISTORY_SHORT_NEXT_STEP = (
    "先补齐商品期货历史数据，再做历史回测、相关性检验和权重审批。"
)
_REVIEW_READY_NEXT_STEP = (
    "进入公式前仍需历史回测、相关性检验、权重审批和版本记录。"
)


def evaluate_crisis_commodity_shadow(
    frame: pd.DataFrame,
    crisis_history: pd.DataFrame,
) -> dict[str, object]:
    if frame.empty or crisis_history.empty or "crisis_score" not in crisis_history.columns:
        sample_count = 0
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count,
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": "商品候选缺少足够历史样本，暂不能评估相关性。",
            "next_step": _HISTORY_SHORT_NEXT_STEP,
        }

    points = _frame_to_points(frame)
    if len(points) < 3:
        sample_count = len(points)
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": max(
                0,
                CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count,
            ),
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": f"商品候选仅 {sample_count} 个历史点，暂不能评估相关性。",
            "next_step": _HISTORY_SHORT_NEXT_STEP,
        }

    price_series = pd.Series(
        {
            pd.Timestamp(point_date): value
            for point_date, value in points
        },
        dtype="float64",
    ).sort_index()
    candidate_returns = (
        price_series.pct_change()
        .replace([float("inf"), float("-inf")], pd.NA)
        .dropna()
    )
    aligned = pd.concat(
        {
            "candidate_return": candidate_returns,
            "crisis_score": crisis_history["crisis_score"],
        },
        axis=1,
    ).dropna()
    if len(aligned) < CRISIS_COMMODITY_SHADOW_MIN_SAMPLES:
        sample_count = int(len(aligned))
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count,
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": (
                f"商品候选与 Crisis Score 仅 {sample_count} 个重叠样本，"
                "暂不能评估相关性。"
            ),
            "next_step": _HISTORY_SHORT_NEXT_STEP,
        }

    same_day = _series_corr(
        aligned["candidate_return"],
        aligned["crisis_score"],
    )
    lead_1d = _series_corr(
        aligned["candidate_return"].shift(1),
        aligned["crisis_score"],
    )
    lag_1d = _series_corr(
        aligned["candidate_return"].shift(-1),
        aligned["crisis_score"],
    )
    candidate_return_z = _latest_standard_score(aligned["candidate_return"])
    crisis_threshold = aligned["crisis_score"].quantile(0.75)
    crisis_rows = aligned[aligned["crisis_score"] >= crisis_threshold]
    hit_rate = None
    if not crisis_rows.empty:
        expected_sign = 1 if (same_day or 0) >= 0 else -1
        hit_rate = float(
            (crisis_rows["candidate_return"] * expected_sign > 0).mean()
        )

    return {
        "status": "review_ready",
        "label": "影子评估可读",
        "sample_count": int(len(aligned)),
        "window_start": aligned.index.min().date().isoformat(),
        "window_end": aligned.index.max().date().isoformat(),
        "target": "crisis_score",
        "candidate_metric": "daily_return",
        "same_day_correlation": same_day,
        "lead_1d_correlation": lead_1d,
        "lag_1d_correlation": lag_1d,
        "latest_return_z": candidate_return_z,
        "crisis_hit_rate": round(hit_rate, 2) if hit_rate is not None else None,
        "crisis_sample_count": int(len(crisis_rows)),
        "summary": (
            f"影子评估：样本 {len(aligned)}，同日相关 {_format_metric(same_day)}，"
            f"危机期命中率 {_format_metric(hit_rate)}。"
        ),
        "next_step": _REVIEW_READY_NEXT_STEP,
    }


def _frame_to_points(frame: pd.DataFrame) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    for _, row in frame.sort_values("date").iterrows():
        sample_date = _coerce_date(row.get("date"))
        value = _float_or_none(row.get("value"))
        if sample_date is None or value is None:
            continue
        points.append((sample_date, value))
    return points


def _series_corr(left: pd.Series, right: pd.Series) -> float | None:
    aligned = pd.concat({"left": left, "right": right}, axis=1).dropna()
    if (
        len(aligned) < 3
        or aligned["left"].nunique() < 2
        or aligned["right"].nunique() < 2
    ):
        return None
    value = aligned["left"].corr(aligned["right"])
    return round(float(value), 2) if pd.notna(value) else None


def _latest_standard_score(series: pd.Series) -> float | None:
    clean = series.dropna()
    if (
        len(clean) < CRISIS_COMMODITY_SHADOW_MIN_SAMPLES
        or clean.nunique() < 2
    ):
        return None
    std = clean.std()
    if pd.isna(std) or float(std) == 0.0:
        return None
    value = (clean.iloc[-1] - clean.mean()) / std
    return round(float(value), 4) if pd.notna(value) else None


def _format_metric(value: float | None) -> str:
    return "缺失" if value is None else f"{value:.2f}"


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except (AttributeError, TypeError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
