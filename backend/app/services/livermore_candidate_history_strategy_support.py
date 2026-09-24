"""Livermore 候选历史：策略族元数据/就绪度与评审门辅助。

从 livermore_candidate_history_service 门面按行为等价逐字拆出：策略族
元数据与契约索引、就绪度评估、策略评审门与阈值、优化切片排序键、评分
行诊断与桶辅助。本模块不得导入门面模块。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from backend.app.services.livermore_candidate_history_window_stats import (
    _DEFAULT_SIGNAL_KINDS,
    _HORIZON_LABELS,
    _median_float,
    _normalized_text,
    _present_float_values,
)


STRATEGY_FAMILY_READINESS_CONTRACT_VERSION = "rv_livermore_strategy_family_readiness_v1"

_STRATEGY_FAMILY_FIELDS = (
    "family_key",
    "family_label",
    "family_contract_version",
    "primary_sample_size",
)

_STRATEGY_REVIEW_HORIZON = "return_5d"

_STRATEGY_REVIEW_LONG_HORIZON = "return_20d"

_STRATEGY_REVIEW_MIN_T5_SAMPLE = 30

_STRATEGY_REVIEW_MIN_T5_WIN_RATE = 0.5

_STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR = 0.012

_STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_TARGET = 0.024

def _empty_strategy_family_metadata() -> dict[str, Any]:
    return {field: None for field in _STRATEGY_FAMILY_FIELDS}

def _strategy_family_metadata_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in _STRATEGY_FAMILY_FIELDS}

def _strategy_family_metadata_index(
    *,
    rows: list[dict[str, Any]],
    key_field: str,
    target_type: str,
) -> dict[tuple[str, str], dict[str, Any] | None]:
    index: dict[tuple[str, str], dict[str, Any] | None] = {}
    duplicate_keys: set[str] = set()
    for row in rows:
        target_key = str(row.get(key_field) or "")
        if not target_key:
            continue
        index_key = (target_type, target_key)
        if index_key in index:
            duplicate_keys.add(target_key)
            continue
        index[index_key] = _strategy_family_metadata_from_row(row)
    for target_key in duplicate_keys:
        index[(target_type, target_key)] = None
    return index

def _load_strategy_macro_context(
    loader: Callable[[str], dict[str, Any] | None] | None,
    snapshot_to: str | None,
) -> dict[str, Any] | None:
    if loader is None or not snapshot_to:
        return None
    context = loader(snapshot_to)
    return _strategy_macro_context(context)

def _strategy_macro_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(context, dict) or not context:
        return None
    return dict(context)

def _strategy_family_sample_maturity(
    *,
    primary_sample_size: Any,
    min_sample: int,
) -> str:
    if primary_sample_size is None:
        return "unknown"
    try:
        sample_size = int(primary_sample_size)
    except (TypeError, ValueError):
        return "unknown"
    return "sufficient" if sample_size >= min_sample else "insufficient"

def _strategy_family_data_readiness(macro_context: dict[str, Any] | None) -> str:
    if not macro_context:
        return "missing"
    data_state = _normalized_text(macro_context.get("data_state")) or "missing"
    if data_state == "ready":
        return "ready"
    if data_state in {"degraded", "stale"}:
        return "degraded"
    return "missing"

def _strategy_family_macro_compatibility(data_readiness: str) -> str:
    if data_readiness == "ready":
        return "compatible"
    if data_readiness == "degraded":
        return "degraded"
    return "unknown"

def _strategy_family_readiness_reasons(
    *,
    macro_context: dict[str, Any] | None,
    sample_maturity: str,
) -> list[str]:
    reasons = ["OBSERVATION_ONLY_BOUNDARY"]
    if not macro_context:
        reasons.append("MACRO_CONTEXT_MISSING")
    else:
        raw_reasons = macro_context.get("readiness_reasons")
        if isinstance(raw_reasons, list):
            reasons.extend(str(reason) for reason in raw_reasons if str(reason or "").strip())
    if sample_maturity != "sufficient":
        reasons.append("SAMPLE_MATURITY_INSUFFICIENT")
    return _dedupe_preserve_order(reasons)

def _strategy_family_readiness(
    *,
    family_metadata: dict[str, Any],
    macro_context: dict[str, Any] | None,
    min_sample: int,
) -> dict[str, Any] | None:
    if not family_metadata.get("family_key"):
        return None
    sample_maturity = _strategy_family_sample_maturity(
        primary_sample_size=family_metadata.get("primary_sample_size"),
        min_sample=min_sample,
    )
    data_readiness = _strategy_family_data_readiness(macro_context)
    readiness_state = (
        "observation_ready"
        if data_readiness == "ready" and sample_maturity == "sufficient"
        else "degraded_observation"
    )
    return {
        "readiness_contract_version": STRATEGY_FAMILY_READINESS_CONTRACT_VERSION,
        "readiness_state": readiness_state,
        "macro_context_id": (macro_context or {}).get("macro_context_id"),
        "market_gate_context_id": None,
        "macro_compatibility": _strategy_family_macro_compatibility(data_readiness),
        "market_gate_compatibility": "unknown",
        "data_readiness": data_readiness,
        "sample_maturity": sample_maturity,
        "readiness_reasons": _strategy_family_readiness_reasons(
            macro_context=macro_context,
            sample_maturity=sample_maturity,
        ),
        "observational_only": True,
        "formal_use_allowed": False,
    }

def _strategy_family_contract_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_strategy_family_metadata_from_row(row),
        "family_readiness": row.get("family_readiness"),
    }

def _strategy_family_contract_index(
    *,
    rows: list[dict[str, Any]],
    key_field: str,
    target_type: str,
) -> dict[tuple[str, str], dict[str, Any] | None]:
    index: dict[tuple[str, str], dict[str, Any] | None] = {}
    duplicate_keys: set[str] = set()
    for row in rows:
        target_key = str(row.get(key_field) or "")
        if not target_key:
            continue
        index_key = (target_type, target_key)
        if index_key in index:
            duplicate_keys.add(target_key)
            continue
        index[index_key] = _strategy_family_contract_from_row(row)
    for target_key in duplicate_keys:
        index[(target_type, target_key)] = None
    return index

def _strategy_family_contract_for_recommendation_target(
    *,
    target_type: str,
    target_key: str,
    family_by_target: dict[tuple[str, str], dict[str, Any] | None],
) -> dict[str, Any]:
    source = family_by_target.get((target_type, target_key))
    if source is None:
        return {**_empty_strategy_family_metadata(), "family_readiness": None}
    return {
        **{field: source.get(field) for field in _STRATEGY_FAMILY_FIELDS},
        "family_readiness": source.get("family_readiness"),
    }

def _optimization_recommendation(
    *,
    stats: dict[str, dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    review = _strategy_review_gate(stats=stats, min_sample=min_sample)
    return {
        "action": review["action"],
        "priority_label": review["priority_label"],
        "reason": review["reason"],
        "primary_horizon": primary_horizon,
        "review_horizon": _STRATEGY_REVIEW_HORIZON,
        "available_count": review["available_count"],
        "min_sample": review["min_sample"],
        "avg_return": review["avg_return"],
        "median_return": review["median_return"],
        "t20_median_return": review["t20_median_return"],
        "win_rate": review["win_rate"],
        "score": review["score"],
    }

def _optimization_score(*, avg_return: Any, win_rate: Any) -> float | None:
    if avg_return is None or win_rate is None:
        return None
    try:
        return round(float(win_rate) * 100 + float(avg_return) * 100, 4)
    except (TypeError, ValueError):
        return None

def _strategy_review_thresholds(min_sample: int) -> dict[str, Any]:
    return {
        "review_horizon": _STRATEGY_REVIEW_HORIZON,
        "mature_min_sample": max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample)),
        "min_t5_win_rate": _STRATEGY_REVIEW_MIN_T5_WIN_RATE,
        "official_t5_avg_return_band": {
            "lower": _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR,
            "upper": _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_TARGET,
        },
        "long_horizon": _STRATEGY_REVIEW_LONG_HORIZON,
        "long_horizon_median_rule": "not_below_t5_median",
    }

def _strategy_review_gate(*, stats: dict[str, dict[str, Any]], min_sample: int) -> dict[str, Any]:
    required_sample = max(_STRATEGY_REVIEW_MIN_T5_SAMPLE, int(min_sample))
    t5_stats = stats.get(_STRATEGY_REVIEW_HORIZON) or {}
    t20_stats = stats.get(_STRATEGY_REVIEW_LONG_HORIZON) or {}
    available_count = int(t5_stats.get("available_count") or 0)
    avg_return = _float_value(t5_stats.get("avg_return"))
    win_rate = _float_value(t5_stats.get("win_rate"))
    median_return = _float_value(t5_stats.get("median_return"))
    t20_median_return = _float_value(t20_stats.get("median_return"))
    score = _optimization_score(avg_return=avg_return, win_rate=win_rate)

    if available_count < required_sample or avg_return is None or win_rate is None:
        return {
            "action": "pending_more_history",
            "priority_label": "样本不足",
            "sample_status": "insufficient",
            "reason": _sample_insufficient_reason(
                available_count,
                min_sample=required_sample,
                primary_horizon=_STRATEGY_REVIEW_HORIZON,
            ),
            "available_count": available_count,
            "min_sample": required_sample,
            "avg_return": avg_return,
            "median_return": median_return,
            "t20_median_return": t20_median_return,
            "win_rate": win_rate,
            "score": score,
            "passed": False,
        }

    issues: list[str] = []
    metric_failed = False
    if win_rate < _STRATEGY_REVIEW_MIN_T5_WIN_RATE:
        metric_failed = True
        issues.append(f"T+5 胜率低于 {_STRATEGY_REVIEW_MIN_T5_WIN_RATE * 100:.0f}%")
    if avg_return < _STRATEGY_REVIEW_OFFICIAL_T5_AVG_RETURN_FLOOR:
        metric_failed = True
        issues.append("T+5 均值低于 official 1.20%-2.40% 区间下沿")

    long_window_pending = t20_median_return is None
    long_window_worse = median_return is not None and t20_median_return is not None and t20_median_return < median_return
    if long_window_pending:
        issues.append("T+20 中位数待成熟")
    elif long_window_worse:
        issues.append("T+20 中位数低于 T+5 中位数")

    if metric_failed or long_window_worse:
        action = "downgrade"
        priority_label = "降权观察"
    elif long_window_pending:
        action = "observe"
        priority_label = "继续观察"
    else:
        action = "promote"
        priority_label = "优先复核"

    base_reason = (
        f"T+5 成熟样本 {available_count}/{required_sample}，胜率 {win_rate * 100:.1f}% ，"
        f"均值 {avg_return * 100:+.2f}%（official 1.20%-2.40%），"
        f"中位数 {_format_optional_percent(median_return)}，"
        f"T+20 中位数 {_format_optional_percent(t20_median_return)}，评分 {score:.2f}。"
    )
    if action == "promote":
        reason = base_reason + "通过 T+5 成熟样本、胜率、official 下沿和 T+20 中位数不恶化门槛，仅用于优先复核排序。"
    elif action == "observe":
        reason = base_reason + "；".join(issues) + "，继续观察。"
    else:
        reason = base_reason + "；".join(issues) + "，降权观察。"

    return {
        "action": action,
        "priority_label": priority_label,
        "sample_status": "sufficient",
        "reason": reason,
        "available_count": available_count,
        "min_sample": required_sample,
        "avg_return": avg_return,
        "median_return": median_return,
        "t20_median_return": t20_median_return,
        "win_rate": win_rate,
        "score": score,
        "passed": action == "promote",
    }

def _format_optional_percent(value: Any) -> str:
    numeric = _float_value(value)
    if numeric is None:
        return "待成熟"
    return f"{numeric * 100:+.2f}%"

def _date_weighted_horizon_stat(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    by_date: dict[str, list[float]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "").strip()[:10]
        if not snapshot_date:
            continue
        value = _float_value(item.get(key))
        if value is None:
            continue
        by_date.setdefault(snapshot_date, []).append(value)
    return _date_weighted_horizon_stat_from_daily(by_date)

def _date_weighted_horizon_stat_from_daily(by_date: dict[str, list[float]]) -> dict[str, Any]:
    daily_returns = [sum(values) / len(values) for values in by_date.values() if values]
    return {
        "available_day_count": len(daily_returns),
        "candidate_row_count": sum(len(values) for values in by_date.values()),
        "avg_return": round(sum(daily_returns) / len(daily_returns), 6) if daily_returns else None,
        "positive_day_rate": round(sum(1 for value in daily_returns if value > 0) / len(daily_returns), 6)
        if daily_returns
        else None,
        "worst_day_return": round(min(daily_returns), 6) if daily_returns else None,
        "best_day_return": round(max(daily_returns), 6) if daily_returns else None,
    }

def _strategy_optimization_pending_summary(items: list[dict[str, Any]], *, primary_horizon: str) -> dict[str, Any]:
    pending_items = [item for item in items if item.get(primary_horizon) is None]
    pending_dates = sorted(
        {
            str(item.get("snapshot_as_of_date") or "").strip()[:10]
            for item in pending_items
            if str(item.get("snapshot_as_of_date") or "").strip()
        }
    )
    latest_pending_date = pending_dates[-1] if pending_dates else None
    horizon_label = _HORIZON_LABELS[primary_horizon]
    if pending_items:
        message = (
            f"{horizon_label} 仍有 {len(pending_items)} 条收益待成熟"
            + (f"，最新 pending 日期 {latest_pending_date}" if latest_pending_date else "")
            + "。"
        )
    else:
        message = f"{horizon_label} 已成熟样本内暂无 pending 收益。"
    return {
        "primary_horizon": primary_horizon,
        "pending_rows": len(pending_items),
        "pending_dates": pending_dates,
        "latest_pending_date": latest_pending_date,
        "message": message,
    }

def _strategy_optimization_sample_maturity(
    *,
    strategy_summaries: list[dict[str, Any]],
    slices: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    all_items = [*strategy_summaries, *slices]
    sufficient_count = sum(1 for item in all_items if item.get("sample_status") == "sufficient")
    insufficient_count = sum(1 for item in all_items if item.get("sample_status") != "sufficient")
    return {
        "status": "sufficient" if sufficient_count else "insufficient",
        "primary_horizon": primary_horizon,
        "min_sample": min_sample,
        "sufficient_count": sufficient_count,
        "insufficient_count": insufficient_count,
    }

def _sort_strategy_optimization_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_strategy_optimization_row_sort_key)

def _sort_strategy_optimization_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_strategy_optimization_row_sort_key)

def _strategy_optimization_row_sort_key(row: dict[str, Any]) -> tuple[int, float, int, str]:
    recommendation = cast(dict[str, Any], row.get("recommendation") or {})
    score = recommendation.get("score")
    signal_kind = str(row.get("signal_kind") or "")
    return (
        0 if score is not None else 1,
        -(float(score) if score is not None else -1.0),
        _strategy_order_index(signal_kind),
        str(row.get("slice_key") or row.get("summary_key") or ""),
    )

def _strategy_optimization_recommendation_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    action_order = {
        "promote": 0,
        "downgrade": 1,
        "observe": 2,
        "pending_more_history": 3,
    }
    score = row.get("score")
    return (
        action_order.get(str(row.get("action") or ""), 9),
        -(float(score) if score is not None else -1.0),
        str(row.get("target_key") or ""),
    )

def _strategy_order_index(signal_kind: str) -> int:
    return _DEFAULT_SIGNAL_KINDS.index(signal_kind) if signal_kind in _DEFAULT_SIGNAL_KINDS else 999

def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _abnormal_turnover_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < 1:
        return "<1"
    if value < 2:
        return "1-2"
    if value <= 3.5:
        return "2-3.5"
    return ">3.5"

def _gap_norm_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "<=0"
    if value <= 0.2:
        return "0-0.2"
    if value <= 0.45:
        return "0.2-0.45"
    return ">0.45"

def _breakout_extension_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0.1:
        return "<=0.1"
    if value <= 0.25:
        return "0.1-0.25"
    if value <= 0.35:
        return "0.25-0.35"
    return ">0.35"

def _movement_event_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0"
    if value <= 5:
        return "1-5"
    if value <= 10:
        return "6-10"
    return ">10"

def _stock_movement_event_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    return "2+"

def _slug_text(value: str) -> str:
    return (
        str(value or "unknown")
        .strip()
        .replace(" ", "_")
        .replace("<=", "lte")
        .replace(">=", "gte")
        .replace("<", "lt")
        .replace(">", "gt")
        .replace("+", "plus")
    )

def _rank_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_state: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_state.setdefault(str(row["market_state"]), []).append(row)
    ranked_rows: list[dict[str, Any]] = []
    for state_rows in rows_by_state.values():
        rank = 1
        for row in _sort_strategy_score_rows(state_rows):
            if row["sample_status"] == "sufficient" and row.get("priority_label") == "优先复核":
                row = {**row, "priority_rank": rank}
                rank += 1
            ranked_rows.append(row)
    return ranked_rows

def _sort_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[str, int, float, int, str]:
        score = row.get("priority_score")
        signal_kind = str(row.get("signal_kind") or "")
        strategy_order = _DEFAULT_SIGNAL_KINDS.index(signal_kind) if signal_kind in _DEFAULT_SIGNAL_KINDS else 999
        return (
            str(row.get("market_state") or ""),
            0 if score is not None else 1,
            -(float(score) if score is not None else -1.0),
            strategy_order,
            signal_kind,
        )

    return sorted(rows, key=sort_key)

def _empty_strategy_score_diagnostics() -> dict[str, Any]:
    return {
        "priority_scope": None,
        "priority_scope_label": None,
        "priority_scope_stats": None,
        "maturity": _empty_maturity_diagnostics(),
        "rank_buckets": [],
        "risk_flags": [],
    }

def _rank_bucket_ranges(signal_kind: str) -> list[tuple[int, int | None, str]]:
    if signal_kind == "factor_screen":
        return [(1, 5, "1-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, None, "21+")]
    if signal_kind == "stock_candidate":
        return [(1, 3, "1-3"), (4, 6, "4-6"), (7, 10, "7-10"), (11, None, "11+")]
    return []

def _rank_bucket_priority(
    *,
    market_state: str,
    signal_kind: str,
    rank_from: int,
    review: dict[str, Any],
) -> tuple[str, bool, str]:
    if review["sample_status"] == "insufficient":
        return (str(review["priority_label"]), False, str(review["reason"]))
    if market_state == "OVERHEAT" and signal_kind == "factor_screen" and rank_from > 10:
        return (
            "降权观察",
            False,
            "OVERHEAT 状态下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。",
        )
    if review["action"] != "promote":
        return (str(review["priority_label"]), False, str(review["reason"]))
    return (
        "优先复核",
        True,
        str(review["reason"]),
    )

def _strategy_score_risk_flags(
    *,
    market_state: str,
    signal_kind: str,
    stats: dict[str, dict[str, Any]],
    min_sample: int,
) -> list[dict[str, Any]]:
    if market_state != "OVERHEAT" or signal_kind != "stock_candidate":
        return []
    t5_stats = stats[_STRATEGY_REVIEW_HORIZON]
    t20_stats = stats[_STRATEGY_REVIEW_LONG_HORIZON]
    available_count = int(t20_stats["available_count"])
    if available_count < min_sample:
        return []
    t5_median = _float_value(t5_stats.get("median_return"))
    t20_median = _float_value(t20_stats.get("median_return"))
    if t5_median is None or t20_median is None or t20_median >= t5_median:
        return []
    return [
        {
            "kind": "long_window_median_worse",
            "label": "长窗口中位数恶化",
            "horizon": _STRATEGY_REVIEW_LONG_HORIZON,
            "reason": (
                f"T+20 样本 {available_count}，中位数 {t20_median * 100:+.2f}% "
                f"低于 T+5 中位数 {t5_median * 100:+.2f}%，仅按短窗口复核。"
            ),
            "stats": t20_stats,
        }
    ]

def _empty_maturity_diagnostics() -> dict[str, Any]:
    return {
        "status": "narrow",
        "label": "样本偏窄",
        "reason": "T+5 已成熟快照 0/4，等待更多成熟日。",
        "min_mature_snapshot_count": 4,
        "mature_snapshot_count": 0,
        "snapshot_stats": [],
        "tracked_snapshots": [],
        "worst_snapshot": None,
    }

def _snapshot_maturity_stat(
    snapshot_date: str,
    items: list[dict[str, Any]],
    *,
    primary_horizon: str,
) -> dict[str, Any]:
    stat = _horizon_stat(items, primary_horizon)
    return {
        "snapshot_as_of_date": snapshot_date,
        "available_count": stat["available_count"],
        "positive_count": stat["positive_count"],
        "non_positive_count": stat["non_positive_count"],
        "avg_return": stat["avg_return"],
        "median_return": stat["median_return"],
        "win_rate": stat["win_rate"],
    }

def _worst_snapshot_stat(snapshot_stats: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not snapshot_stats:
        return None
    return min(
        snapshot_stats,
        key=lambda stat: (
            float(stat["win_rate"]) if stat.get("win_rate") is not None else -1.0,
            float(stat["avg_return"]) if stat.get("avg_return") is not None else -1.0,
            str(stat.get("snapshot_as_of_date") or ""),
        ),
    )

def _candidate_rank(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("candidate_rank"))
    except (TypeError, ValueError):
        return None

def _empty_horizon_stats_by_key() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "available_count": 0,
            "missing_count": 0,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        }
        for key in _HORIZON_LABELS
    }

def _sample_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，样本不足，仅作观察。"

def _current_state_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"当前状态样本不足：{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，仅作观察。"

def _score_reason(
    *,
    available_count: int,
    win_rate: float,
    avg_return: float,
    priority_score: float,
    priority_label: str,
    primary_horizon: str,
) -> str:
    horizon_label = _HORIZON_LABELS[primary_horizon]
    base = (
        f"{horizon_label} 样本 {available_count}，胜率 {win_rate * 100:.1f}%，"
        f"均值 {avg_return * 100:+.2f}%，评分 {priority_score:.2f}。"
    )
    if priority_label == "降权观察":
        return base + "胜率低于 50% 或均值不为正，降权观察。"
    return base + "仅用于优先复核排序。"

def _horizon_stat(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = _present_float_values(items, key)
    positive_count = sum(1 for value in values if value > 0)
    return {
        "available_count": len(values),
        "missing_count": len(items) - len(values),
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": round(sum(values) / len(values), 6) if values else None,
        "median_return": _median_float(values),
        "win_rate": round(positive_count / len(values), 6) if values else None,
    }

def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped
