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

TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
DEFAULT_REPORT_PATH = Path("docs/pnl/2026-07-batch2-entry-premium-report.md")
HORIZONS = ("1d", "5d", "20d")
BUCKET_ORDER = ("<0", "[0,1%)", "[1%,2%)", "[2%,3%)", "[3%,5%)", ">=5%")


def entry_premium_bucket(value: float) -> str:
    if value < 0:
        return "<0"
    if value < 0.01:
        return "[0,1%)"
    if value < 0.02:
        return "[1%,2%)"
    if value < 0.03:
        return "[2%,3%)"
    if value < 0.05:
        return "[3%,5%)"
    return ">=5%"


def analyze_entry_premium(rows: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    summary_rows = build_entry_premium_summary(rows)
    premiums = [
        premium
        for row in rows
        if (premium := _entry_premium(row)) is not None
    ]
    high_premium_20d = [
        value
        for row in rows
        if (_entry_premium(row) or -math.inf) >= 0.03
        and (value := _return_for_horizon(row, "20d")) is not None
    ]
    high_avg = statistics.fmean(high_premium_20d) if high_premium_20d else None
    recommendation = "no_threshold_recommendation"
    recommended_threshold: float | None = None
    abandon_ratio: float | None = None
    if high_avg is not None and high_avg < 0:
        recommendation = "max_entry_premium=0.03"
        recommended_threshold = 0.03
        abandon_ratio = (
            sum(1 for premium in premiums if premium > recommended_threshold) / len(premiums)
            if premiums
            else None
        )
    return {
        "status": "ready",
        "row_count": len(rows),
        "judgeable_row_count": len(premiums),
        "summary_rows": summary_rows,
        "conclusion": {
            "high_premium_20d_sample_count": len(high_premium_20d),
            "high_premium_20d_avg_net_return": _round_optional(high_avg),
            "recommendation": recommendation,
            "recommended_threshold": recommended_threshold,
            "estimated_abandon_ratio": _round_optional(abandon_ratio),
        },
    }


def build_entry_premium_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    values: dict[tuple[str, str, str, str], list[float]] = {}
    for row in rows:
        premium = _entry_premium(row)
        if premium is None:
            continue
        bucket = entry_premium_bucket(premium)
        for group_type in ("signal_kind", "market_state"):
            group_value = _text(row.get(group_type)) or "UNKNOWN"
            for horizon in HORIZONS:
                return_value = _return_for_horizon(row, horizon)
                if return_value is None:
                    continue
                values.setdefault((group_type, group_value, horizon, bucket), []).append(return_value)

    bucket_rank = {bucket: index for index, bucket in enumerate(BUCKET_ORDER)}
    summary_rows: list[dict[str, object]] = []
    for key in sorted(values, key=lambda item: (item[0], item[1], item[2], bucket_rank[item[3]])):
        group_type, group_value, horizon, bucket = key
        returns = values[key]
        summary_rows.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "horizon": horizon,
                "entry_premium_bucket": bucket,
                "sample_count": len(returns),
                "avg_net_return": _round_optional(statistics.fmean(returns)),
                "win_rate": _round_optional(sum(1 for value in returns if value > 0) / len(returns)),
                "p10_net_return": _round_optional(_percentile(returns, 0.10)),
            }
        )
    return summary_rows


def run_entry_premium_diagnostic(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    signal_kind: str | None = None,
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
        if TABLE_EXECUTION_HIST not in tables:
            payload = _blocked_payload(f"Required table {TABLE_EXECUTION_HIST} is missing.")
            _write_report(report, payload)
            return payload
        rows, issues = _load_execution_rows(conn, signal_kind=signal_kind)
    finally:
        conn.close()

    if issues:
        payload = _blocked_payload("; ".join(issues))
        _write_report(report, payload)
        return payload
    payload = analyze_entry_premium(rows)
    payload.update(
        {
            "db_path": str(db_file),
            "report_path": str(report),
            "signal_kind": signal_kind or "ALL",
        }
    )
    _write_report(report, payload)
    return payload


def _load_execution_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_kind: str | None,
) -> tuple[list[dict[str, object]], list[str]]:
    columns = _columns(conn, TABLE_EXECUTION_HIST)
    required = {
        "signal_date",
        "stock_code",
        "signal_kind",
        "market_state",
        "signal_close",
        "entry_price",
    }
    missing = sorted(required - columns)
    return_exprs = {
        horizon: _first_available_column_sql(
            columns,
            (f"return_{horizon}_net_adj", f"return_{horizon}_net", f"return_{horizon}_adj", f"return_{horizon}"),
            alias=f"return_{horizon}_net_adj",
        )
        for horizon in HORIZONS
    }
    for horizon, expr in return_exprs.items():
        if expr is None:
            missing.append(f"one of return_{horizon}_net_adj, return_{horizon}_net, return_{horizon}_adj, return_{horizon}")
    if missing:
        return [], [f"{TABLE_EXECUTION_HIST} missing columns: {', '.join(missing)}"]

    where = ["entry_price is not null", "signal_close is not null"]
    params: list[object] = []
    if signal_kind:
        where.append("signal_kind = ?")
        params.append(signal_kind)
    rows = conn.execute(
        f"""
        select
          signal_date,
          stock_code,
          signal_kind,
          market_state,
          signal_close,
          entry_price,
          {return_exprs["1d"]},
          {return_exprs["5d"]},
          {return_exprs["20d"]}
        from {TABLE_EXECUTION_HIST}
        where {" and ".join(where)}
        order by cast(signal_date as date), stock_code
        """,
        params,
    ).fetchall()
    return [
        {
            "signal_date": str(row[0])[:10],
            "stock_code": row[1],
            "signal_kind": row[2],
            "market_state": row[3],
            "signal_close": row[4],
            "entry_price": row[5],
            "return_1d_net_adj": row[6],
            "return_5d_net_adj": row[7],
            "return_20d_net_adj": row[8],
        }
        for row in rows
    ], []


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "ready":
        path.write_text(
            "\n".join(
                [
                    "# 2026-07 Batch 2 Entry Premium Diagnostic",
                    "",
                    f"- status: {payload.get('status', 'blocked')}",
                    f"- reason: {payload.get('reason', 'No diagnostic was generated.')}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return

    conclusion = payload["conclusion"]
    lines = [
        "# 2026-07 Batch 2 Entry Premium Diagnostic",
        "",
        "- status: ready",
        f"- db_path: {payload.get('db_path')}",
        f"- signal_kind: {payload.get('signal_kind')}",
        f"- row_count: {payload['row_count']}",
        f"- judgeable_row_count: {payload['judgeable_row_count']}",
        f"- high_premium_20d_sample_count: {conclusion['high_premium_20d_sample_count']}",
        f"- high_premium_20d_avg_net_return: {_fmt(conclusion['high_premium_20d_avg_net_return'])}",
        f"- recommendation: {conclusion['recommendation']}",
        f"- recommended_threshold: {_fmt(conclusion['recommended_threshold'])}",
        f"- estimated_abandon_ratio: {_fmt(conclusion['estimated_abandon_ratio'])}",
        "",
        "## Bucket Summary",
        "",
        "| group_type | group_value | horizon | entry_premium_bucket | sample_count | avg_net_return | win_rate | p10_net_return |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["summary_rows"]:
        lines.append(
            "| {group_type} | {group_value} | {horizon} | {bucket} | {count} | {avg} | {win} | {p10} |".format(
                group_type=row["group_type"],
                group_value=row["group_value"],
                horizon=row["horizon"],
                bucket=row["entry_premium_bucket"],
                count=row["sample_count"],
                avg=_fmt(row["avg_net_return"]),
                win=_fmt(row["win_rate"]),
                p10=_fmt(row["p10_net_return"]),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _entry_premium(row: Mapping[str, object]) -> float | None:
    entry_price = _safe_float(row.get("entry_price"))
    signal_close = _safe_float(row.get("signal_close"))
    if entry_price is None or signal_close is None or signal_close <= 0:
        return None
    return entry_price / signal_close - 1.0


def _return_for_horizon(row: Mapping[str, object], horizon: str) -> float | None:
    return _first_float(
        row.get(f"return_{horizon}_net_adj"),
        row.get(f"return_{horizon}_net"),
        row.get(f"return_{horizon}_adj"),
        row.get(f"return_{horizon}"),
    )


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _blocked_payload(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _first_available_column_sql(columns: set[str], candidates: Sequence[str], *, alias: str) -> str | None:
    available = [column for column in candidates if column in columns]
    if not available:
        return None
    if len(available) == 1:
        return f"{available[0]} as {alias}"
    return f"coalesce({', '.join(available)}) as {alias}"


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


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose T+1 entry premium by forward net return bucket.")
    parser.add_argument("--db-path", default="data/moss.duckdb", help="DuckDB database path.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    parser.add_argument("--signal-kind", default=None, help="Optional signal kind filter.")
    args = parser.parse_args()
    payload = run_entry_premium_diagnostic(
        db_path=args.db_path,
        report_path=args.report_path,
        signal_kind=args.signal_kind,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
