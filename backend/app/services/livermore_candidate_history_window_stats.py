"""Livermore 候选历史：重放窗口分类与收益/执行统计辅助。

从 livermore_candidate_history_service 门面按行为等价逐字拆出：重放日
分类、决策可用行辅助、横截面/执行口径收益统计、信号种类与文本规范化、
周期代理回测的样本代际与执行收益富化辅助。本模块不得导入门面模块。
"""

from __future__ import annotations

from typing import Any
from backend.app.services.livermore_candidate_history_read_support import (
    TABLE_HIST,
    _missing_bar_count,
    _safe_optional_date,
)


_DEFAULT_SIGNAL_KINDS = ["hybrid_fusion", "stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"]

_HORIZON_LABELS = {
    "return_1d": "T+1",
    "return_5d": "T+5",
    "return_10d": "T+10",
    "return_20d": "T+20",
}

_ADJUSTED_FORWARD_RETURN_KEYS = {
    "return_1d": "return_1d_adj",
    "return_5d": "return_5d_adj",
    "return_10d": "return_10d_adj",
    "return_20d": "return_20d_adj",
}

_EXECUTION_RETURN_KEYS = {
    "return_1d": "return_1d_net_adj",
    "return_5d": "return_5d_net_adj",
    "return_10d": "return_10d_net_adj",
    "return_20d": "return_20d_net_adj",
}

_EXECUTION_METRIC_BASIS = "net_next_open_adj"

_CYCLE_PROXY_SIGNAL_KIND = "stock_candidate"

# Vendor-era boundary for the caliber_disclosure sample_generation split;
# mirrors CHOICE_NATIVE_ERA_START in scripts/run_portfolio_backtest.py.
CHOICE_NATIVE_ERA_START = "2026-01-05"

def _snapshot_row_dates(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            normalized
            for row in rows
            if (normalized := _safe_optional_date(str(row.get("snapshot_as_of_date") or "")))
        }
    )

def _decision_usable_adjusted_item(item: dict[str, Any]) -> dict[str, Any] | None:
    adjusted_item = dict(item)
    has_adjusted_return = False
    for raw_key, adjusted_key in _ADJUSTED_FORWARD_RETURN_KEYS.items():
        adjusted_value = item.get(adjusted_key)
        adjusted_item[raw_key] = adjusted_value
        if adjusted_value is not None:
            has_adjusted_return = True
    if not has_adjusted_return:
        return None
    return adjusted_item

def _decision_usable_dates(backtest_window_summary: dict[str, Any]) -> set[str]:
    return {
        str(item)[:10]
        for item in backtest_window_summary.get("included_completed_stats_dates", [])
        if str(item or "").strip()
    }

def _horizon_usable_items(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    usable_dates = _decision_usable_dates(backtest_window_summary)
    for reason in backtest_window_summary.get("date_reasons", []):
        if not isinstance(reason, dict):
            continue
        if str(reason.get("status") or "").strip() not in {"completed", "pending"}:
            continue
        trade_date = str(reason.get("trade_date") or "").strip()[:10]
        if trade_date:
            usable_dates.add(trade_date)
    return [
        item
        for item in items
        if str(item.get("snapshot_as_of_date") or "").strip()[:10] in usable_dates
    ]

def _classify_replay_date(
    *,
    trade_date: str,
    coverage: Any,
    rows: list[dict[str, Any]],
    history_table_present: bool,
) -> dict[str, Any]:
    if not history_table_present:
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"{TABLE_HIST} table absent; cannot distinguish no-signal dates from missing candidate-history materialization for {trade_date}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    missing_items = {str(item) for item in getattr(coverage, "missing_request_items", [])}
    if not bool(getattr(coverage, "full_coverage", False)):
        if missing_items == {"limit_up_quality:daily_limit_flags"}:
            return _classification(
                trade_date=trade_date,
                status="unsupported",
                reason_code="missing_daily_limit_flags",
                message=f"daily_limit_flags absent; Livermore strategy replay unsupported for {trade_date}.",
                affects_completed_stats=False,
                signal_kinds=_DEFAULT_SIGNAL_KINDS,
            )
        missing_detail = ", ".join(sorted(missing_items)) or str(getattr(coverage, "status", "not_materialized"))
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"Required source coverage is incomplete for {trade_date}: {missing_detail}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )
    if not rows:
        return _classification(
            trade_date=trade_date,
            status="completed",
            reason_code="no_strategy_signals",
            message=f"Full replay coverage produced no Livermore strategy signal rows for {trade_date}.",
            affects_completed_stats=True,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    signal_kinds = _signal_kinds_for_rows(rows)
    if any(str(row.get("data_status") or "").strip() == "pending" for row in rows):
        return _classification(
            trade_date=trade_date,
            status="pending",
            reason_code="forward_returns_pending",
            message=f"Forward return bars are not available yet; exclude {trade_date} from completed forward-return statistics.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
            missing_bar_row_count=_missing_bar_count(rows),
        )
    if any(
        str(row.get("signal_kind") or "").strip() == "theme_breakout"
        and str(row.get("theme_source_kind") or "").strip() == "proxy"
        for row in rows
    ):
        return _classification(
            trade_date=trade_date,
            status="proxy_only",
            reason_code="proxy_theme_only",
            message=f"Theme breakout replay for {trade_date} relies on proxy-only theme evidence.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
        )
    return {
        "status": "completed",
        "affects_completed_stats": True,
        "public_reason": None,
    }

def _classification(
    *,
    trade_date: str,
    status: str,
    reason_code: str,
    message: str,
    affects_completed_stats: bool,
    signal_kinds: list[str],
    missing_bar_row_count: int | None = None,
) -> dict[str, Any]:
    public_reason: dict[str, Any] = {
        "trade_date": trade_date,
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "affects_completed_stats": affects_completed_stats,
        "signal_kinds": signal_kinds,
    }
    if missing_bar_row_count is not None:
        public_reason["missing_bar_row_count"] = missing_bar_row_count
    return {
        "status": status,
        "affects_completed_stats": affects_completed_stats,
        "public_reason": public_reason,
    }

def _count_status(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if str(item.get("data_status") or "").strip() == status)

def _count_by_signal_kind(items: list[dict[str, Any]]) -> dict[str, int]:
    by_signal_kind: dict[str, int] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1
    return by_signal_kind

def _signal_kinds_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    signal_kinds = sorted({_normalized_signal_kind(row) for row in rows})
    return signal_kinds or list(_DEFAULT_SIGNAL_KINDS)

def _avg_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(values) / len(values), 6)

def _win_rate_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(1 for value in values if value > 0) / len(values), 6)

def _median_float(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return round(ordered[midpoint], 6)
    return round((ordered[midpoint - 1] + ordered[midpoint]) / 2, 6)

def _horizon_stat_from_values(values: list[float], *, item_count: int) -> dict[str, Any]:
    positive_count = sum(1 for value in values if value > 0)
    return {
        "available_count": len(values),
        "missing_count": item_count - len(values),
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": round(sum(values) / len(values), 6) if values else None,
        "median_return": _median_float(values),
        "win_rate": round(positive_count / len(values), 6) if values else None,
    }

def _execution_rows_for_dates(rows: list[dict[str, Any]], included_dates: set[str]) -> list[dict[str, Any]]:
    if not included_dates:
        return []
    return [row for row in rows if str(row.get("signal_date") or "").strip()[:10] in included_dates]

def _execution_executable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _bool_value(row.get("entry_executable")) is True]

def _build_execution_usable_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    executable_rows = _execution_executable_rows(rows)
    signal_kind_stats = _build_execution_signal_kind_horizon_stats(executable_rows)
    return {
        "metric_basis": _EXECUTION_METRIC_BASIS,
        "basis_label": "T+1\u5f00\u76d8\u6210\u4ea4\u00b7\u542b\u8d39\u00b7\u590d\u6743",
        "row_count": len(executable_rows),
        "execution_row_count": len(rows),
        "entry_executable_count": len(executable_rows),
        "horizon_usable_stats": _build_execution_horizon_stats(executable_rows),
        "by_signal_kind": _count_by_execution_signal_kind(executable_rows),
        "by_signal_kind_horizon_stats": signal_kind_stats,
        "by_signal_kind_horizon_usable_stats": signal_kind_stats,
        "included_signal_dates": sorted(
            {date_text for row in executable_rows if (date_text := str(row.get("signal_date") or "").strip()[:10])}
        ),
    }

def _build_execution_horizon_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        horizon: _execution_horizon_stat(rows, column)
        for horizon, column in _EXECUTION_RETURN_KEYS.items()
    }

def _execution_horizon_stat(rows: list[dict[str, Any]], column: str) -> dict[str, Any]:
    values = _present_float_values(rows, column)
    positive_count = sum(1 for value in values if value > 0)
    avg_return = round(sum(values) / len(values), 6) if values else None
    median_return = _median_float(values)
    win_rate = round(positive_count / len(values), 6) if values else None
    missing_count = len(rows) - len(values)
    return {
        "available_count": len(values),
        "missing_count": missing_count,
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": avg_return,
        "median_return": median_return,
        "win_rate": win_rate,
        "n": len(values),
        "adj_missing_n": missing_count,
        "win": win_rate,
        "avg": avg_return,
        "median": median_return,
        "p10": _percentile_float(values, 0.1),
        "p90": _percentile_float(values, 0.9),
    }

def _build_execution_signal_kind_horizon_stats(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        signal_kind = _execution_signal_kind(row)
        grouped.setdefault(signal_kind, []).append(row)
    return {signal_kind: _build_execution_horizon_stats(group_rows) for signal_kind, group_rows in sorted(grouped.items())}

def _build_market_state_signal_kind_execution_stats(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in _execution_executable_rows(rows):
        market_state = _execution_market_state(row)
        signal_kind = _execution_signal_kind(row)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(row)
    return {
        market_state: {
            signal_kind: _build_execution_horizon_stats(group_rows)
            for signal_kind, group_rows in sorted(signal_groups.items())
        }
        for market_state, signal_groups in sorted(grouped.items())
    }

def _build_entry_blocked_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_rows = [row for row in rows if _bool_value(row.get("entry_executable")) is False]
    by_reason: dict[str, dict[str, Any]] = {}
    for row in blocked_rows:
        reason = str(row.get("entry_block_reason") or "unknown").strip() or "unknown"
        current = by_reason.setdefault(reason, {"count": 0, "share": None})
        current["count"] += 1
    for reason in sorted(by_reason):
        by_reason[reason]["share"] = round(by_reason[reason]["count"] / len(rows), 6) if rows else None
    executable_count = len(_execution_executable_rows(rows))
    return {
        "metric_basis": _EXECUTION_METRIC_BASIS,
        "total_row_count": len(rows),
        "entry_executable_count": executable_count,
        "blocked_row_count": len(blocked_rows),
        "blocked_ratio": round(len(blocked_rows) / len(rows), 6) if rows else None,
        "by_reason": dict(sorted(by_reason.items())),
    }

def _count_by_execution_signal_kind(rows: list[dict[str, Any]]) -> dict[str, int]:
    by_signal_kind: dict[str, int] = {}
    for row in rows:
        signal_kind = _execution_signal_kind(row)
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1
    return by_signal_kind

def _era_sample_generation(items: list[dict[str, Any]]) -> dict[str, int]:
    """Split replay rows at the Choice-native era boundary by signal date.

    Mirrors ``_execution_vendor_era_counts`` in ``scripts/run_portfolio_backtest.py``;
    candidate-history replay rows carry their signal date as ``snapshot_as_of_date``.
    """
    tushare_rows = 0
    native_rows = 0
    for row in items:
        signal_date = str(row.get("snapshot_as_of_date") or "")[:10]
        if signal_date and signal_date < CHOICE_NATIVE_ERA_START:
            tushare_rows += 1
        elif signal_date:
            native_rows += 1
    return {"tushare_era_rows": tushare_rows, "native_era_rows": native_rows}

def _enrich_cycle_proxy_execution_returns(
    items: list[dict[str, Any]],
    *,
    execution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach point-in-time next-open returns by signal date and stock code."""
    execution_by_key = {
        (
            str(row.get("signal_date") or "")[:10],
            str(row.get("stock_code") or "").strip(),
        ): row
        for row in execution_rows
        if str(row.get("signal_date") or "").strip()
        and str(row.get("stock_code") or "").strip()
        and _normalized_signal_kind(row) == _CYCLE_PROXY_SIGNAL_KIND
    }
    enriched: list[dict[str, Any]] = []
    for item in items:
        key = (
            str(item.get("snapshot_as_of_date") or "")[:10],
            str(item.get("stock_code") or "").strip(),
        )
        if _normalized_signal_kind(item) != _CYCLE_PROXY_SIGNAL_KIND:
            enriched.append(item)
            continue
        execution = execution_by_key.get(key)
        if execution is None:
            enriched.append(item)
            continue
        enriched_item = dict(item)
        if execution.get("entry_executable") is False:
            enriched_item["execution_entry_blocked"] = True
            enriched.append(enriched_item)
            continue
        if execution.get("entry_executable") is True:
            enriched_item["execution_entry_date"] = execution.get("entry_date")
            enriched_item["execution_exit_date_5d"] = execution.get("exit_date_5d")
            enriched_item["return_5d_gross_adj"] = execution.get("return_5d_gross_adj")
            enriched_item["return_5d_net_adj"] = execution.get("return_5d_net_adj")
        enriched.append(enriched_item)
    return enriched

def _append_optional_table(tables: list[str], table: str | list[str] | None) -> list[str]:
    if table is None:
        return tables
    optional_tables = table if isinstance(table, list) else [table]
    out = [*tables]
    for item in optional_tables:
        if item not in out:
            out.append(item)
    return out

def _present_float_values(items: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for item in items:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values

def _percentile_float(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    bounded = min(max(float(percentile), 0.0), 1.0)
    position = bounded * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return round(ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight, 6)

def _normalized_signal_kind(item: dict[str, Any]) -> str:
    return str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"

def _execution_signal_kind(row: dict[str, Any]) -> str:
    return str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"

def _execution_market_state(row: dict[str, Any]) -> str:
    return _normalized_text(row.get("market_state")) or "unknown"

def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    if text in {"false", "f", "0", "no", "n"}:
        return False
    return None

def _normalized_text(value: Any) -> str:
    return str(value or "").strip()

def _decision_excluded_dates(
    items: list[dict[str, Any]],
    *,
    usable_items: list[dict[str, Any]],
    included_dates: set[str],
) -> list[str]:
    usable_keys = {
        (
            str(item.get("snapshot_as_of_date") or "")[:10],
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        for item in usable_items
    }
    excluded_dates: set[str] = set()
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        row_key = (
            snapshot_date,
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        if snapshot_date not in included_dates or row_key not in usable_keys:
            excluded_dates.add(snapshot_date)
    return sorted(excluded_dates)
