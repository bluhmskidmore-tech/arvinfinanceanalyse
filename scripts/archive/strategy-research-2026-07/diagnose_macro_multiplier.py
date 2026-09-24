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

DEFAULT_REPORT_PATH = Path("docs/pnl/2026-07-batch2-macro-multiplier-report.md")
BENCHMARK_TABLE = "fact_choice_macro_daily"
BENCHMARK_SERIES_ID = "CA.CSI300"
MACRO_SOURCE_CANDIDATES = (
    "livermore_macro_context_history",
    "macro_composite_history",
    "fact_macro_composite_daily",
    "macro_environment_history",
)
DATE_COLUMNS = ("trade_date", "snapshot_as_of_date", "date")
STATUS_COLUMNS = ("macro_status", "status")
SCORE_COLUMNS = ("composite_score", "macro_composite_score")
TRADING_DAYS_PER_YEAR = 252


def macro_status_from_score(score: object) -> str:
    value = _safe_float(score)
    if value is None:
        return "unknown"
    if value <= -0.3:
        return "supportive"
    if value >= 0.3:
        return "restrictive"
    return "neutral"


def build_macro_multiplier_comparison(
    benchmark_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    macro_rows: Sequence[Mapping[str, object]],
    *,
    macro_multipliers: Mapping[str, float] = POLICY.macro_multipliers,
    initial_capital: float = 100.0,
) -> dict[str, Any]:
    return_rows = benchmark_daily_returns(benchmark_rows)
    if not return_rows:
        return {"status": "benchmark_unavailable", "curves": [], "metrics": {}, "macro_status": {}}

    exposure_by_date = _exposure_by_date(exposure_rows)
    macro_by_date = _macro_status_by_date(macro_rows)
    gate_value = float(initial_capital)
    macro_value = float(initial_capital)
    curves: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    previous_status: str | None = None
    switch_count = 0
    for row in return_rows:
        date_key = str(row["date"])
        daily_return = float(row["daily_return"])
        exposure = exposure_by_date.get(date_key, 0.0)
        status = macro_by_date.get(date_key, "unknown")
        multiplier = float(macro_multipliers.get(status, macro_multipliers.get("unknown", 0.0)))
        if previous_status is not None and status != previous_status:
            switch_count += 1
        previous_status = status
        status_counts[status] = status_counts.get(status, 0) + 1
        gate_value *= 1.0 + daily_return * exposure
        macro_value *= 1.0 + daily_return * exposure * multiplier
        curves.append(
            {
                "date": date_key,
                "daily_return": round(daily_return, 6),
                "exposure": round(exposure, 6),
                "macro_status": status,
                "macro_multiplier": round(multiplier, 6),
                "gate_index": round(gate_value, 6),
                "gate_macro_index": round(macro_value, 6),
            }
        )

    gate_values = [float(row["gate_index"]) for row in curves]
    macro_values = [float(row["gate_macro_index"]) for row in curves]
    gate_metrics = _metrics_from_values(gate_values, initial_capital=initial_capital)
    macro_metrics = _metrics_from_values(macro_values, initial_capital=initial_capital)
    gate_return = _safe_float(gate_metrics.get("cumulative_return"))
    macro_return = _safe_float(macro_metrics.get("cumulative_return"))
    delta = macro_return - gate_return if macro_return is not None and gate_return is not None else None
    cost_band = POLICY.buy_cost_rate + POLICY.sell_cost_rate + 2 * POLICY.slippage_rate
    conclusion = "macro_multiplier_inconclusive"
    if delta is not None and delta < -cost_band:
        conclusion = "macro_multiplier_dragged"
    elif delta is not None and abs(delta) < cost_band:
        conclusion = "difference_within_cost_band_evaluate_simplification"
    elif delta is not None:
        conclusion = "macro_multiplier_added_value"
    total_days = len(curves)
    return {
        "status": "ready",
        "curves": curves,
        "metrics": {
            "gate_index": gate_metrics,
            "gate_macro_index": macro_metrics,
            "cumulative_return_delta": _round_optional(delta),
            "cost_band": _round_optional(cost_band),
            "conclusion": conclusion,
        },
        "macro_status": {
            "day_counts": status_counts,
            "day_ratios": {
                status: _round_optional(count / total_days if total_days else None)
                for status, count in sorted(status_counts.items())
            },
            "switch_count": switch_count,
        },
    }


def run_macro_multiplier_diagnostic(
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
        macro_rows, macro_issues = _load_macro_rows(conn, tables)
        if macro_issues:
            payload = _blocked_payload("; ".join(macro_issues))
            _write_report(report, payload)
            return payload
        benchmark_rows, benchmark_issues = _load_benchmark_rows(conn, tables)
        if benchmark_issues:
            payload = _blocked_payload("; ".join(benchmark_issues))
            _write_report(report, payload)
            return payload
        if not benchmark_rows:
            payload = _blocked_payload(f"No benchmark rows found for {BENCHMARK_SERIES_ID}.")
            _write_report(report, payload)
            return payload
        start_date = min(row["date"] for row in benchmark_rows)
        end_date = max(row["date"] for row in benchmark_rows)
        exposure_rows = [
            {"date": date_key, "exposure": point.exposure, "market_state": point.state}
            for date_key, point in load_gate_exposure_by_date(conn, start_date, end_date).items()
            if point.source != "missing"
        ]
    finally:
        conn.close()

    payload = build_macro_multiplier_comparison(
        benchmark_rows,
        exposure_rows,
        macro_rows,
        macro_multipliers=POLICY.macro_multipliers,
    )
    payload.update(
        {
            "db_path": str(db_file),
            "report_path": str(report),
            "macro_source": macro_rows[0].get("source_table") if macro_rows else None,
        }
    )
    _write_report(report, payload)
    return payload


def _load_macro_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> tuple[list[dict[str, object]], list[str]]:
    for table in MACRO_SOURCE_CANDIDATES:
        if table not in tables:
            continue
        columns = _columns(conn, table)
        date_column = next((column for column in DATE_COLUMNS if column in columns), None)
        status_column = next((column for column in STATUS_COLUMNS if column in columns), None)
        score_column = next((column for column in SCORE_COLUMNS if column in columns), None)
        if date_column is None or (status_column is None and score_column is None):
            continue
        status_select = status_column if status_column is not None else "cast(null as varchar)"
        score_select = score_column if score_column is not None else "cast(null as double)"
        rows = conn.execute(
            f"""
            select {date_column} as date_key, {status_select} as macro_status, {score_select} as composite_score
            from {table}
            where {date_column} is not null
            order by cast({date_column} as date)
            """
        ).fetchall()
        out = []
        for date_key, macro_status, composite_score in rows:
            status = _normal_macro_status(macro_status) or macro_status_from_score(composite_score)
            out.append(
                {
                    "date": str(date_key)[:10],
                    "macro_status": status,
                    "composite_score": composite_score,
                    "source_table": table,
                }
            )
        if not out:
            return [], [f"{table} contained no macro history rows."]
        return out, []
    return [], [
        "Missing macro composite history source. Expected one of: "
        + ", ".join(MACRO_SOURCE_CANDIDATES)
        + " with a date column and macro_status/status or composite_score."
    ]


def _load_benchmark_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> tuple[list[dict[str, object]], list[str]]:
    if BENCHMARK_TABLE not in tables:
        return [], [f"Required benchmark table {BENCHMARK_TABLE} is missing."]
    columns = _columns(conn, BENCHMARK_TABLE)
    required = {"series_id", "trade_date", "value_numeric"}
    missing = sorted(required - columns)
    if missing:
        return [], [f"{BENCHMARK_TABLE} missing columns: {', '.join(missing)}"]
    rows = conn.execute(
        f"""
        select trade_date, value_numeric
        from {BENCHMARK_TABLE}
        where series_id = ?
          and value_numeric is not null
        order by cast(trade_date as date)
        """,
        [BENCHMARK_SERIES_ID],
    ).fetchall()
    return [{"date": str(date_key)[:10], "value": value} for date_key, value in rows], []


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "ready":
        path.write_text(
            "\n".join(
                [
                    "# 2026-07 Batch 2 Macro Multiplier Diagnostic",
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
    macro_status = payload["macro_status"]
    conclusion = metrics["conclusion"]
    lines = [
        "# 2026-07 Batch 2 Macro Multiplier Diagnostic",
        "",
        "- status: ready",
        f"- db_path: {payload.get('db_path')}",
        f"- macro_source: {payload.get('macro_source')}",
        f"- conclusion: {conclusion}",
        f"- cumulative_return_delta: {_fmt(metrics.get('cumulative_return_delta'))}",
        f"- cost_band: {_fmt(metrics.get('cost_band'))}",
        f"- status_switch_count: {macro_status['switch_count']}",
        "",
        "## Line Metrics",
        "",
        "| line | terminal_value | cumulative_return | cagr | max_drawdown | daily_sharpe |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for line_name in ("gate_index", "gate_macro_index"):
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
    lines.extend(
        [
            "",
            "## Macro Status Mix",
            "",
            "| status | day_count | day_ratio |",
            "|---|---:|---:|",
        ]
    )
    for status, count in sorted(macro_status["day_counts"].items()):
        lines.append(f"| {status} | {count} | {_fmt(macro_status['day_ratios'].get(status))} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _macro_status_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        date_key = _date_text(row.get("date") or row.get("trade_date") or row.get("snapshot_as_of_date"))
        status = _normal_macro_status(row.get("macro_status") or row.get("status"))
        if not status:
            status = macro_status_from_score(row.get("composite_score"))
        if date_key:
            out[date_key] = status
    return out


def _normal_macro_status(value: object) -> str:
    text = _text(value).lower()
    return text if text in {"supportive", "neutral", "restrictive", "unknown"} else ""


def _exposure_by_date(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows:
        date_key = _date_text(row.get("trade_date") or row.get("date") or row.get("snapshot_as_of_date"))
        exposure = _first_float(row.get("exposure"), row.get("market_gate_exposure"), row.get("value"))
        if date_key and exposure is not None:
            out[date_key] = min(max(exposure, 0.0), 1.0)
    return out


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


def _first_float(*values: object) -> float | None:
    for value in values:
        coerced = _safe_float(value)
        if coerced is not None:
            return coerced
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round_optional(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _date_text(value: object) -> str:
    return "" if value is None else str(value).strip()[:10]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose gate exposure with and without macro multipliers.")
    parser.add_argument("--db-path", default="data/moss.duckdb", help="DuckDB database path.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    args = parser.parse_args()
    payload = run_macro_multiplier_diagnostic(db_path=args.db_path, report_path=args.report_path)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
