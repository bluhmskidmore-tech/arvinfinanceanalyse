#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.core_finance.adjusted_returns import normalize_duckdb_path
from backend.app.core_finance.strategy_policy import POLICY

TABLE_UNIVERSE_HISTORY = "livermore_stock_candidate_universe_history"
REPORT_PATH = ROOT / "docs/pnl/2026-07-walk-forward-report.md"
DEFAULT_CLOSE_STRENGTH_VALUES = (0.85, 0.88, 0.90, 0.92, 0.95, 0.97)
DEFAULT_ATU_MIN_VALUES = (1.0, 1.1, 1.2, 1.3)
DEFAULT_ATU_MAX_VALUES = (1.8, 2.0, 2.5, None)
DEFAULT_GAP_NORM_MIN_VALUES = (-0.10, -0.05, 0.0, 0.05)


@dataclass(frozen=True)
class ThresholdConfig:
    close_strength_min: float
    atu_min: float
    atu_max: float | None
    gap_norm_min: float


V7_FIXED_CONFIG = ThresholdConfig(
    close_strength_min=POLICY.entry_filters.close_strength_min,
    atu_min=POLICY.entry_filters.abnormal_turnover_range[0],
    atu_max=POLICY.entry_filters.abnormal_turnover_range[1],
    gap_norm_min=POLICY.entry_filters.gap_norm_min,
)


def build_threshold_grid(
    *,
    close_strength_values: Iterable[float] = DEFAULT_CLOSE_STRENGTH_VALUES,
    atu_min_values: Iterable[float] = DEFAULT_ATU_MIN_VALUES,
    atu_max_values: Iterable[float | None] = DEFAULT_ATU_MAX_VALUES,
    gap_norm_min_values: Iterable[float] = DEFAULT_GAP_NORM_MIN_VALUES,
) -> list[ThresholdConfig]:
    grid: list[ThresholdConfig] = []
    for close_strength_min in close_strength_values:
        for atu_min in atu_min_values:
            for atu_max in atu_max_values:
                if atu_max is not None and atu_min > atu_max:
                    continue
                for gap_norm_min in gap_norm_min_values:
                    grid.append(
                        ThresholdConfig(
                            close_strength_min=float(close_strength_min),
                            atu_min=float(atu_min),
                            atu_max=None if atu_max is None else float(atu_max),
                            gap_norm_min=float(gap_norm_min),
                        )
                    )
    return grid


def run_walk_forward_scan(
    rows: list[dict[str, Any]],
    *,
    start: str,
    train_months: int,
    test_months: int,
    step_months: int,
    min_sample: int,
    grid: list[ThresholdConfig] | None = None,
    fixed_config: ThresholdConfig = V7_FIXED_CONFIG,
) -> dict[str, Any]:
    normalized = [_normalize_row(row) for row in rows]
    usable_rows = [
        row
        for row in normalized
        if row["signal_date"] is not None
        and row["market_state"] in POLICY.entry_observation_states
        and row["eligible_before_truncation"] is True
        and row["return_5d_adj"] is not None
    ]
    missing_return_count = sum(
        1
        for row in normalized
        if row["signal_date"] is not None
        and row["market_state"] in POLICY.entry_observation_states
        and row["eligible_before_truncation"] is True
        and row["return_5d_adj"] is None
    )
    scan_grid = grid or build_threshold_grid()
    windows = _walk_windows(
        start=start,
        max_date=max((row["signal_date"] for row in usable_rows), default=None),
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
    )
    results: list[dict[str, Any]] = []
    for window in windows:
        train_rows = _rows_between(usable_rows, window["train_start"], window["train_end"])
        test_rows = _rows_between(usable_rows, window["test_start"], window["test_end"])
        best_config, train_stats = select_best_config(train_rows, scan_grid, min_sample=min_sample)
        test_stats = evaluate_config(test_rows, best_config) if best_config is not None else _empty_stats()
        fixed_train_stats = evaluate_config(train_rows, fixed_config)
        fixed_test_stats = evaluate_config(test_rows, fixed_config)
        results.append(
            {
                **window,
                "best_config": _config_dict(best_config),
                "train": train_stats,
                "test": test_stats,
                "fixed_v7_config": _config_dict(fixed_config),
                "fixed_v7_train": fixed_train_stats,
                "fixed_v7_test": fixed_test_stats,
                "oos_decay": _decay(train_stats, test_stats),
            }
        )
    return {
        "status": "completed" if results else "empty",
        "sample_filter": {
            "market_states": sorted(POLICY.entry_observation_states),
            "eligible_before_truncation": True,
            "return_column": "return_5d_adj",
        },
        "missing_return_count": missing_return_count,
        "window_count": len(results),
        "windows": results,
        "summary": _summary(results),
    }


def select_best_config(
    rows: list[dict[str, Any]],
    grid: list[ThresholdConfig],
    *,
    min_sample: int,
) -> tuple[ThresholdConfig | None, dict[str, Any]]:
    best_config: ThresholdConfig | None = None
    best_stats = _empty_stats()
    for config in grid:
        stats = evaluate_config(rows, config)
        if int(stats["n"]) < min_sample:
            continue
        if best_config is None or _score_tuple(stats, config) > _score_tuple(best_stats, best_config):
            best_config = config
            best_stats = stats
    return best_config, best_stats


def evaluate_config(rows: list[dict[str, Any]], config: ThresholdConfig | None) -> dict[str, Any]:
    if config is None:
        return _empty_stats()
    values = [
        float(row["return_5d_adj"])
        for row in rows
        if _passes_config(row, config) and row.get("return_5d_adj") is not None
    ]
    if not values:
        return _empty_stats()
    return {
        "n": len(values),
        "avg": round(sum(values) / len(values), 6),
        "win": round(sum(1 for value in values if value > 0) / len(values), 6),
        "p10": _percentile(values, 0.1),
        "p90": _percentile(values, 0.9),
    }


def load_universe_history_rows(duckdb_path: str | Path) -> list[dict[str, Any]]:
    path = normalize_duckdb_path(duckdb_path)
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_UNIVERSE_HISTORY not in tables:
            return []
        columns = {str(row[1]) for row in conn.execute(f"pragma table_info('{TABLE_UNIVERSE_HISTORY}')").fetchall()}
        if "return_5d_adj" not in columns:
            return []
        rows = conn.execute(
            f"""
            select snapshot_as_of_date, stock_code, close_strength, abnormal_turnover,
                   gap_norm, market_state, eligible_before_truncation, return_5d_adj
            from {TABLE_UNIVERSE_HISTORY}
            order by snapshot_as_of_date asc, stock_code asc
            """
        ).fetchall()
    finally:
        conn.close()
    keys = (
        "signal_date",
        "stock_code",
        "close_strength",
        "abnormal_turnover",
        "gap_norm",
        "market_state",
        "eligible_before_truncation",
        "return_5d_adj",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def run_walk_forward_from_duckdb(
    *,
    duckdb_path: str | Path,
    start: str,
    train_months: int,
    test_months: int,
    step_months: int,
    min_sample: int,
    report_path: str | Path = REPORT_PATH,
) -> dict[str, Any]:
    rows = load_universe_history_rows(duckdb_path)
    result = run_walk_forward_scan(
        rows,
        start=start,
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
        min_sample=min_sample,
    )
    resolved_report = Path(report_path)
    if not resolved_report.is_absolute():
        resolved_report = ROOT / resolved_report
    resolved_report.parent.mkdir(parents=True, exist_ok=True)
    resolved_report.write_text(_report_text(result), encoding="utf-8")
    return {**result, "report_path": str(resolved_report)}


def _walk_windows(
    *,
    start: str,
    max_date: date | None,
    train_months: int,
    test_months: int,
    step_months: int,
) -> list[dict[str, Any]]:
    if max_date is None:
        return []
    current = _month_start(start)
    windows: list[dict[str, Any]] = []
    while True:
        train_start = current
        train_end = _add_months(train_start, train_months)
        test_start = train_end
        test_end = _add_months(test_start, test_months)
        if test_start > max_date:
            break
        windows.append(
            {
                "train_start": train_start.isoformat(),
                "train_end": train_end.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
            }
        )
        current = _add_months(current, step_months)
    return windows


def _rows_between(rows: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return [row for row in rows if start_date <= row["signal_date"] < end_date]


def _passes_config(row: dict[str, Any], config: ThresholdConfig) -> bool:
    atu = row.get("abnormal_turnover")
    return (
        row.get("close_strength") is not None
        and row.get("gap_norm") is not None
        and atu is not None
        and float(row["close_strength"]) >= config.close_strength_min
        and float(atu) >= config.atu_min
        and (config.atu_max is None or float(atu) <= config.atu_max)
        and float(row["gap_norm"]) >= config.gap_norm_min
    )


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_date": _date_or_none(row.get("signal_date") or row.get("snapshot_as_of_date")),
        "stock_code": str(row.get("stock_code") or ""),
        "close_strength": _float_or_none(row.get("close_strength")),
        "abnormal_turnover": _float_or_none(row.get("abnormal_turnover")),
        "gap_norm": _float_or_none(row.get("gap_norm")),
        "market_state": str(row.get("market_state") or "unknown").strip() or "unknown",
        "eligible_before_truncation": _bool_value(row.get("eligible_before_truncation")),
        "return_5d_adj": _float_or_none(row.get("return_5d_adj")),
    }


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    best_test_avgs = [row["test"]["avg"] for row in results if row["test"]["avg"] is not None]
    fixed_test_avgs = [row["fixed_v7_test"]["avg"] for row in results if row["fixed_v7_test"]["avg"] is not None]
    decays = [row["oos_decay"] for row in results if row["oos_decay"] is not None]
    return {
        "avg_best_oos": _avg(best_test_avgs),
        "avg_fixed_v7_oos": _avg(fixed_test_avgs),
        "avg_oos_decay": _avg(decays),
        "fixed_v7_positive_windows": sum(1 for value in fixed_test_avgs if value > 0),
        "fixed_v7_window_count": len(fixed_test_avgs),
        "answer": _conclusion(best_test_avgs, fixed_test_avgs, decays),
    }


def _conclusion(best_test_avgs: list[float], fixed_test_avgs: list[float], decays: list[float]) -> str:
    if not fixed_test_avgs:
        return "No out-of-sample windows had enough fixed-v7 observations."
    fixed_positive = sum(1 for value in fixed_test_avgs if value > 0)
    fixed_ok = fixed_positive == len(fixed_test_avgs)
    high_decay = bool(decays and (_avg(decays) or 0.0) > 0.03)
    if fixed_ok and not high_decay:
        return "v7 fixed thresholds remain positive out-of-sample in all evaluated windows."
    return "Threshold stability is weak; review v6-compatible candidates before promoting looser entry settings."


def _report_text(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 2026-07 Walk-Forward Threshold Report",
            "",
            f"- status: {result['status']}",
            f"- window_count: {result['window_count']}",
            f"- missing_return_count: {result['missing_return_count']}",
            f"- conclusion: {result['summary']['answer']}",
            "",
            "```json",
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            "```",
            "",
        ]
    )


def _config_dict(config: ThresholdConfig | None) -> dict[str, Any] | None:
    if config is None:
        return None
    return asdict(config)


def _score_tuple(stats: dict[str, Any], config: ThresholdConfig) -> tuple[float, int, float, float, float]:
    avg = float(stats["avg"]) if stats.get("avg") is not None else -math.inf
    return (avg, int(stats.get("n") or 0), config.close_strength_min, config.atu_min, config.gap_norm_min)


def _decay(train_stats: dict[str, Any], test_stats: dict[str, Any]) -> float | None:
    if train_stats.get("avg") is None or test_stats.get("avg") is None:
        return None
    return round(float(train_stats["avg"]) - float(test_stats["avg"]), 6)


def _empty_stats() -> dict[str, Any]:
    return {"n": 0, "avg": None, "win": None, "p10": None, "p90": None}


def _month_start(value: str) -> date:
    text = str(value).strip()
    if len(text) == 7:
        text = f"{text}-01"
    parsed = date.fromisoformat(text[:10])
    return date(parsed.year, parsed.month, 1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _date_or_none(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    return date.fromisoformat(text)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in {"true", "t", "1", "yes", "y"}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    position = max(0.0, min(1.0, percentile)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 6)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Livermore stock-candidate walk-forward threshold scan.")
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--train-months", type=int, default=6)
    parser.add_argument("--test-months", type=int, default=2)
    parser.add_argument("--step-months", type=int, default=2)
    parser.add_argument("--start", default="2024-07")
    parser.add_argument("--min-sample", type=int, default=60)
    parser.add_argument("--report-path", default=str(REPORT_PATH))
    args = parser.parse_args(argv)
    result = run_walk_forward_from_duckdb(
        duckdb_path=args.duckdb_path,
        start=args.start,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
        min_sample=args.min_sample,
        report_path=args.report_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
