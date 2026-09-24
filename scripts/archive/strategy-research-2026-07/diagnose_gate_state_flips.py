from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date  # noqa: E402
from backend.app.core_finance.strategy_policy import POLICY  # noqa: E402
from backend.app.core_finance.vol_target_overlay import benchmark_daily_returns  # noqa: E402

DEFAULT_REPORT_PATH = Path("docs/pnl/2026-07-batch2-gate-flip-report.md")
BENCHMARK_SERIES_ID = "CA.CSI300"
TABLE_BENCHMARK_DAILY = "fact_choice_macro_daily"
TABLE_BENCHMARK_SNAPSHOT = "choice_market_snapshot"
TRADING_DAYS_PER_YEAR = 252


def analyze_gate_state_flips(
    points: Sequence[Mapping[str, object]],
    *,
    whipsaw_window: int = 3,
) -> dict[str, Any]:
    rows = _normal_points(points)
    if not rows:
        return {"status": "blocked", "reason": "No gate state rows were available."}

    transition_count = 0
    whipsaw_count = 0
    for index in range(1, len(rows)):
        previous_state = str(rows[index - 1]["state"])
        current_state = str(rows[index]["state"])
        if current_state == previous_state:
            continue
        transition_count += 1
        lookahead = rows[index + 1 : index + 1 + whipsaw_window]
        if any(str(item["state"]) == previous_state for item in lookahead):
            whipsaw_count += 1

    runs = _state_runs(rows)
    dwell_by_state: dict[str, list[int]] = {}
    for run in runs:
        dwell_by_state.setdefault(str(run["state"]), []).append(int(run["days"]))
    years = len(rows) / TRADING_DAYS_PER_YEAR if rows else 0.0
    return {
        "status": "ready",
        "sample_days": len(rows),
        "transition_count": transition_count,
        "annualized_transition_count": _round_optional(transition_count / years if years > 0 else None),
        "whipsaw_window": whipsaw_window,
        "whipsaw_count": whipsaw_count,
        "whipsaw_ratio": _round_optional(whipsaw_count / transition_count if transition_count else None),
        "avg_dwell_days_by_state": {
            state: _round_optional(statistics.fmean(days)) for state, days in sorted(dwell_by_state.items())
        },
        "runs": runs,
    }


def simulate_delayed_downgrade(
    points: Sequence[Mapping[str, object]],
    *,
    confirm_days: int = 2,
) -> list[dict[str, object]]:
    rows = _normal_points(points)
    if confirm_days <= 1:
        return [
            {
                **row,
                "requested_state": row["state"],
                "requested_exposure": row["exposure"],
                "delayed_state": row["state"],
                "delayed_exposure": row["exposure"],
            }
            for row in rows
        ]
    if not rows:
        return []

    current_state = str(rows[0]["state"])
    current_exposure = float(rows[0]["exposure"])
    pending_state: str | None = None
    pending_exposure: float | None = None
    pending_count = 0
    out: list[dict[str, object]] = []
    for row in rows:
        requested_state = str(row["state"])
        requested_exposure = float(row["exposure"])
        if requested_exposure >= current_exposure:
            current_state = requested_state
            current_exposure = requested_exposure
            pending_state = None
            pending_exposure = None
            pending_count = 0
        elif pending_state == requested_state and pending_exposure == requested_exposure:
            pending_count += 1
        else:
            pending_state = requested_state
            pending_exposure = requested_exposure
            pending_count = 1

        if pending_count >= confirm_days and pending_state is not None and pending_exposure is not None:
            current_state = pending_state
            current_exposure = pending_exposure
            pending_state = None
            pending_exposure = None
            pending_count = 0

        out.append(
            {
                **row,
                "requested_state": requested_state,
                "requested_exposure": requested_exposure,
                "delayed_state": current_state,
                "delayed_exposure": round(current_exposure, 6),
            }
        )
    return out


def build_gate_state_flip_comparison(
    points: Sequence[Mapping[str, object]],
    benchmark_rows: Sequence[Mapping[str, object]],
    *,
    confirm_days: int = 2,
    initial_capital: float = 100.0,
) -> dict[str, Any]:
    return_rows = benchmark_daily_returns(benchmark_rows)
    if not return_rows:
        return {"status": "benchmark_unavailable", "curves": [], "metrics": {}, "flip_stats": {}}
    rows = _normal_points(points)
    if not rows:
        return {"status": "gate_unavailable", "curves": [], "metrics": {}, "flip_stats": {}}

    immediate_by_date = {str(row["date"]): row for row in rows}
    delayed_by_date = {str(row["date"]): row for row in simulate_delayed_downgrade(rows, confirm_days=confirm_days)}
    immediate_value = float(initial_capital)
    delayed_value = float(initial_capital)
    curves: list[dict[str, object]] = []
    for row in return_rows:
        date_key = str(row["date"])
        daily_return = float(row["daily_return"])
        immediate_exposure = float(immediate_by_date.get(date_key, {}).get("exposure", 0.0))
        delayed_exposure = float(delayed_by_date.get(date_key, {}).get("delayed_exposure", immediate_exposure))
        immediate_value *= 1.0 + daily_return * immediate_exposure
        delayed_value *= 1.0 + daily_return * delayed_exposure
        curves.append(
            {
                "date": date_key,
                "daily_return": round(daily_return, 6),
                "immediate_exposure": round(immediate_exposure, 6),
                "delayed_exposure": round(delayed_exposure, 6),
                "immediate_index": round(immediate_value, 6),
                "delayed_downgrade_index": round(delayed_value, 6),
            }
        )

    immediate_metrics = _metrics_from_values(
        [float(row["immediate_index"]) for row in curves],
        initial_capital=initial_capital,
    )
    delayed_metrics = _metrics_from_values(
        [float(row["delayed_downgrade_index"]) for row in curves],
        initial_capital=initial_capital,
    )
    immediate_return = _safe_float(immediate_metrics.get("cumulative_return"))
    delayed_return = _safe_float(delayed_metrics.get("cumulative_return"))
    delta = delayed_return - immediate_return if delayed_return is not None and immediate_return is not None else None
    cost_band = POLICY.buy_cost_rate + POLICY.sell_cost_rate + 2 * POLICY.slippage_rate
    flip_stats = analyze_gate_state_flips(rows)
    return {
        "status": "ready",
        "confirm_days": confirm_days,
        "curves": curves,
        "flip_stats": flip_stats,
        "metrics": {
            "immediate_index": immediate_metrics,
            "delayed_downgrade_index": delayed_metrics,
            "cumulative_return_delta": _round_optional(delta),
            "cost_band": _round_optional(cost_band),
            "whipsaw_cost_proxy": _round_optional((flip_stats.get("whipsaw_count") or 0) * cost_band),
            "conclusion": _comparison_conclusion(delta, cost_band, flip_stats),
        },
    }


def run_gate_state_flip_diagnostic(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    db_file = Path(db_path)
    if not db_file.exists():
        payload = _blocked_payload(f"DuckDB file not found: {db_file}")
        _write_report(report, payload)
        return payload

    conn = duckdb.connect(str(db_file), read_only=True)
    try:
        tables = _table_names(conn)
        benchmark_rows, benchmark_tables = _load_benchmark_rows(conn, tables=tables)
        if not benchmark_rows:
            payload = _blocked_payload(f"No {BENCHMARK_SERIES_ID} benchmark rows were available.")
            _write_report(report, payload)
            return payload
        start_date = min(str(row["date"]) for row in benchmark_rows)
        end_date = max(str(row["date"]) for row in benchmark_rows)
        exposure_by_date = load_gate_exposure_by_date(conn, start_date, end_date)
    finally:
        conn.close()

    points = [
        {
            "date": row["date"],
            "state": exposure_by_date[str(row["date"])].state,
            "exposure": exposure_by_date[str(row["date"])].exposure,
            "source": exposure_by_date[str(row["date"])].source,
        }
        for row in benchmark_rows
        if str(row["date"]) in exposure_by_date
    ]
    non_missing_days = sum(1 for row in points if row["source"] != "missing")
    if non_missing_days <= 0:
        payload = _blocked_payload("Gate exposure sequence was unavailable for benchmark dates.")
        _write_report(report, payload)
        return payload

    payload = build_gate_state_flip_comparison(points, benchmark_rows)
    payload.update(
        {
            "db_path": str(db_file),
            "report_path": str(report),
            "benchmark_tables": benchmark_tables,
            "non_missing_gate_days": non_missing_days,
            "missing_gate_days": len(points) - non_missing_days,
        }
    )
    _write_report(report, payload)
    return payload


def _load_benchmark_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
) -> tuple[list[dict[str, object]], list[str]]:
    by_date: dict[str, dict[str, object]] = {}
    tables_used: list[str] = []
    for table in (TABLE_BENCHMARK_SNAPSHOT, TABLE_BENCHMARK_DAILY):
        if table not in tables:
            continue
        columns = _columns(conn, table)
        if not {"series_id", "trade_date", "value_numeric"}.issubset(columns):
            continue
        rows = conn.execute(
            f"""
            select trade_date, value_numeric
            from {table}
            where series_id = ?
              and value_numeric is not null
            order by cast(trade_date as date)
            """,
            [BENCHMARK_SERIES_ID],
        ).fetchall()
        if rows:
            tables_used.append(table)
        for trade_date, value in rows:
            by_date[str(trade_date)[:10]] = {"date": str(trade_date)[:10], "value": value}
    return [by_date[key] for key in sorted(by_date)], tables_used


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "ready":
        path.write_text(
            "\n".join(
                [
                    "# 2026-07 Batch 2 Gate State Flip Diagnostic",
                    "",
                    f"- status: {payload.get('status', 'blocked')}",
                    f"- reason: {payload.get('reason', 'No diagnostic was generated.')}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return

    metrics = payload["metrics"]
    flip_stats = payload["flip_stats"]
    lines = [
        "# 2026-07 Batch 2 Gate State Flip Diagnostic",
        "",
        "- status: ready",
        f"- db_path: {payload.get('db_path')}",
        f"- benchmark_tables: {', '.join(payload.get('benchmark_tables') or [])}",
        f"- conclusion: {metrics.get('conclusion')}",
        f"- transition_count: {flip_stats.get('transition_count')}",
        f"- annualized_transition_count: {_fmt(flip_stats.get('annualized_transition_count'))}",
        f"- whipsaw_count: {flip_stats.get('whipsaw_count')}",
        f"- whipsaw_ratio: {_fmt(flip_stats.get('whipsaw_ratio'))}",
        f"- cumulative_return_delta: {_fmt(metrics.get('cumulative_return_delta'))}",
        f"- missing_gate_days: {payload.get('missing_gate_days')}",
        "",
        "## Line Metrics",
        "",
        "| line | terminal_value | cumulative_return | cagr | max_drawdown | daily_sharpe |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for line_name in ("immediate_index", "delayed_downgrade_index"):
        line_metrics = metrics[line_name]
        lines.append(
            "| {line} | {terminal} | {cum} | {cagr} | {mdd} | {sharpe} |".format(
                line=line_name,
                terminal=_fmt(line_metrics.get("terminal_value")),
                cum=_fmt(line_metrics.get("cumulative_return")),
                cagr=_fmt(line_metrics.get("cagr")),
                mdd=_fmt(line_metrics.get("max_drawdown")),
                sharpe=_fmt(line_metrics.get("daily_sharpe")),
            )
        )
    lines.extend(["", "## Dwell", "", "| state | avg_dwell_days |", "|---|---:|"])
    for state, dwell in (flip_stats.get("avg_dwell_days_by_state") or {}).items():
        lines.append(f"| {state} | {_fmt(dwell)} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normal_points(points: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in sorted(points, key=lambda item: _date_text(item.get("trade_date") or item.get("date"))):
        date_key = _date_text(row.get("trade_date") or row.get("date"))
        state = _text(row.get("state") or row.get("market_state"))
        exposure = _first_float(row.get("exposure"), row.get("market_gate_exposure"))
        if not date_key or not state or exposure is None:
            continue
        out.append({"date": date_key, "state": state, "exposure": min(max(exposure, 0.0), 1.0)})
    return out


def _state_runs(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    runs: list[dict[str, object]] = []
    current_state = str(rows[0]["state"])
    start_date = str(rows[0]["date"])
    previous_date = start_date
    days = 0
    for row in rows:
        state = str(row["state"])
        if state != current_state:
            runs.append({"state": current_state, "start_date": start_date, "end_date": previous_date, "days": days})
            current_state = state
            start_date = str(row["date"])
            days = 0
        days += 1
        previous_date = str(row["date"])
    runs.append({"state": current_state, "start_date": start_date, "end_date": previous_date, "days": days})
    return runs


def _metrics_from_values(values: Sequence[float], *, initial_capital: float) -> dict[str, object]:
    if not values:
        return {
            "sample_days": 0,
            "terminal_value": None,
            "cumulative_return": None,
            "cagr": None,
            "max_drawdown": None,
            "daily_sharpe": None,
        }
    sample_days = max(len(values) - 1, 0)
    terminal_value = values[-1]
    returns = [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
        if values[index - 1] > 0
    ]
    cagr = (
        (terminal_value / initial_capital) ** (TRADING_DAYS_PER_YEAR / sample_days) - 1.0
        if sample_days > 0 and terminal_value > 0 and initial_capital > 0
        else None
    )
    return {
        "sample_days": sample_days,
        "terminal_value": _round_optional(terminal_value),
        "cumulative_return": _round_optional(terminal_value / initial_capital - 1.0 if initial_capital > 0 else None),
        "cagr": _round_optional(cagr),
        "max_drawdown": _round_optional(_max_drawdown(values)),
        "daily_sharpe": _round_optional(_sharpe(returns)),
    }


def _comparison_conclusion(delta: float | None, cost_band: float, flip_stats: Mapping[str, object]) -> str:
    if int(flip_stats.get("transition_count") or 0) <= 0:
        return "gate_lag_not_actionable_no_flips"
    if delta is not None and delta > cost_band:
        return "delayed_downgrade_added_value"
    if delta is not None and delta < -cost_band:
        return "delayed_downgrade_hurt_timing"
    return "difference_within_cost_band_evaluate_lag_simplification"


def _max_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, 1.0 - value / peak)
    return max_drawdown


def _sharpe(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return statistics.fmean(returns) / stdev * math.sqrt(TRADING_DAYS_PER_YEAR)


def _blocked_payload(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_float(*values: object) -> float | None:
    for value in values:
        number = _safe_float(value)
        if number is not None:
            return number
    return None


def _round_optional(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _date_text(value: object) -> str:
    return "" if value is None else str(value).strip()[:10]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose gate state flips and a delayed-downgrade simulation.")
    parser.add_argument("--db-path", default="data/moss.duckdb", help="DuckDB database path.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    args = parser.parse_args()
    payload = run_gate_state_flip_diagnostic(db_path=args.db_path, report_path=args.report_path)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
