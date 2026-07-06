from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.core_finance.adjusted_returns import (  # noqa: E402
    PRICE_ADJUSTMENT_MODE,
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    adjusted_return,
    factors_changed,
    net_return_after_costs,
    normalize_duckdb_path,
)
from backend.app.tasks import livermore_candidate_history_materialize as history_task  # noqa: E402


HORIZONS = ("1d", "5d", "10d", "20d")


def backfill_adjusted_returns(
    *,
    duckdb_path: str | Path,
    start_date: str,
    end_date: str,
    report_path: str | Path | None = None,
) -> dict[str, object]:
    resolved_path = normalize_duckdb_path(duckdb_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")
    resolved_report_path = Path(report_path) if report_path is not None else ROOT / "docs/pnl/2026-07-adjusted-vs-unadjusted-report.md"
    if not resolved_report_path.is_absolute():
        resolved_report_path = ROOT / resolved_report_path

    conn = duckdb.connect(str(resolved_path), read_only=False)
    try:
        history_task.ensure_livermore_candidate_history_schema(conn)
        candidate_updated = _backfill_forward_table(
            conn,
            table_name=history_task.TABLE_HIST,
            date_column="snapshot_as_of_date",
            evidence_column="signal_evidence_json",
            start_date=start_date,
            end_date=end_date,
        )
        universe_updated = _backfill_forward_table(
            conn,
            table_name=history_task.TABLE_STOCK_UNIVERSE,
            date_column="snapshot_as_of_date",
            evidence_column="evidence_json",
            start_date=start_date,
            end_date=end_date,
        )
        execution_updated = _backfill_execution_table(conn, start_date=start_date, end_date=end_date)
        report_text = _build_report(
            conn,
            start_date=start_date,
            end_date=end_date,
            candidate_updated=candidate_updated,
            universe_updated=universe_updated,
            execution_updated=execution_updated,
        )
    finally:
        conn.close()

    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_path.write_text(report_text, encoding="utf-8")
    status = "completed" if candidate_updated or universe_updated or execution_updated else "noop"
    return {
        "status": status,
        "duckdb_path": str(resolved_path),
        "start_date": start_date,
        "end_date": end_date,
        "candidate_updated_count": candidate_updated,
        "universe_updated_count": universe_updated,
        "execution_updated_count": execution_updated,
        "report_path": str(resolved_report_path),
    }


def _backfill_forward_table(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    date_column: str,
    evidence_column: str,
    start_date: str,
    end_date: str,
) -> int:
    if table_name not in _table_names(conn):
        return 0
    columns = _table_columns(conn, table_name)
    required = {date_column, "stock_code", "selection_close", evidence_column}
    if not required.issubset(columns):
        return 0

    rows = conn.execute(
        f"""
        select {date_column}, stock_code, selection_close,
               forward_trade_date_1d, forward_trade_date_5d,
               forward_trade_date_10d, forward_trade_date_20d,
               return_1d, return_5d, return_10d, return_20d,
               {evidence_column}
        from {table_name}
        where cast({date_column} as date) >= cast(? as date)
          and cast({date_column} as date) <= cast(? as date)
        """,
        [start_date, end_date],
    ).fetchall()

    updated = 0
    for row in rows:
        (
            signal_date,
            stock_code,
            selection_close,
            fwd_1d,
            fwd_5d,
            fwd_10d,
            fwd_20d,
            raw_1d,
            raw_5d,
            raw_10d,
            raw_20d,
            evidence_json,
        ) = row
        signal_date_text = str(signal_date)[:10]
        stock_code_text = str(stock_code or "").strip().upper()
        selection_price = _positive_float(selection_close)
        signal_factor = _adjustment_factor(conn, stock_code=stock_code_text, trade_date=signal_date_text)
        forward_dates = {"1d": fwd_1d, "5d": fwd_5d, "10d": fwd_10d, "20d": fwd_20d}
        raw_returns = {"1d": raw_1d, "5d": raw_5d, "10d": raw_10d, "20d": raw_20d}
        adj_returns: dict[str, float | None] = {}
        forward_factors: dict[str, float | None] = {}
        factor_values = [signal_factor]
        missing_horizons: list[str] = []
        for horizon in HORIZONS:
            target_date = _date_text(forward_dates[horizon])
            if not target_date:
                adj_returns[horizon] = None
                forward_factors[horizon] = None
                continue
            target_factor = _adjustment_factor(conn, stock_code=stock_code_text, trade_date=target_date)
            forward_factors[horizon] = target_factor
            factor_values.append(target_factor)
            exit_price = _close_value(conn, stock_code=stock_code_text, trade_date=target_date)
            if exit_price is None and selection_price is not None and raw_returns[horizon] is not None:
                exit_price = selection_price * (1.0 + float(raw_returns[horizon]))
            adj_returns[horizon] = adjusted_return(
                start_price=selection_price,
                start_adj_factor=signal_factor,
                end_price=exit_price,
                end_adj_factor=target_factor,
            )
            if adj_returns[horizon] is None:
                missing_horizons.append(horizon)

        ex_div = factors_changed(factor_values)
        evidence = _merge_adjustment_evidence(
            evidence_json,
            {
                "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
                "signal_adj_factor": signal_factor,
                "forward_adj_factors": forward_factors,
                "adj_factor_missing": bool(missing_horizons),
                "adj_factor_missing_horizons": missing_horizons,
                "adjusted_returns_status": "partial_missing_adj_factor"
                if missing_horizons
                else "complete",
                "ex_div_in_window": ex_div,
            },
        )
        conn.execute(
            f"""
            update {table_name}
            set return_1d_adj = ?,
                return_5d_adj = ?,
                return_10d_adj = ?,
                return_20d_adj = ?,
                ex_div_in_window = ?,
                {evidence_column} = ?
            where {date_column} = ?
              and stock_code = ?
            """,
            [
                adj_returns["1d"],
                adj_returns["5d"],
                adj_returns["10d"],
                adj_returns["20d"],
                ex_div,
                json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                signal_date,
                stock_code,
            ],
        )
        updated += 1
    return updated


def _backfill_execution_table(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
) -> int:
    table_name = history_task.TABLE_EXECUTION_HIST
    if table_name not in _table_names(conn):
        return 0
    columns = _table_columns(conn, table_name)
    required = {"signal_date", "stock_code", "entry_date", "entry_price", "evidence_json"}
    if not required.issubset(columns):
        return 0

    rows = conn.execute(
        f"""
        select signal_date, stock_code, entry_date, entry_price,
               exit_date_1d, exit_price_1d,
               exit_date_5d, exit_price_5d,
               exit_date_10d, exit_price_10d,
               exit_date_20d, exit_price_20d,
               evidence_json
        from {table_name}
        where cast(signal_date as date) >= cast(? as date)
          and cast(signal_date as date) <= cast(? as date)
        """,
        [start_date, end_date],
    ).fetchall()

    updated = 0
    for row in rows:
        (
            signal_date,
            stock_code,
            entry_date,
            entry_price,
            exit_1d,
            exit_price_1d,
            exit_5d,
            exit_price_5d,
            exit_10d,
            exit_price_10d,
            exit_20d,
            exit_price_20d,
            evidence_json,
        ) = row
        stock_code_text = str(stock_code or "").strip().upper()
        signal_factor = _adjustment_factor(conn, stock_code=stock_code_text, trade_date=str(signal_date)[:10])
        entry_date_text = _date_text(entry_date)
        entry_factor = _adjustment_factor(conn, stock_code=stock_code_text, trade_date=entry_date_text)
        entry_price_value = _positive_float(entry_price)
        entry_ex_div = factors_changed([signal_factor, entry_factor])
        horizon_inputs = {
            "1d": (exit_1d, exit_price_1d),
            "5d": (exit_5d, exit_price_5d),
            "10d": (exit_10d, exit_price_10d),
            "20d": (exit_20d, exit_price_20d),
        }
        adj: dict[str, tuple[float | None, float | None]] = {}
        missing_horizons: list[str] = []
        for horizon, (exit_date, exit_price) in horizon_inputs.items():
            exit_date_text = _date_text(exit_date)
            exit_factor = _adjustment_factor(conn, stock_code=stock_code_text, trade_date=exit_date_text)
            gross_adj = adjusted_return(
                start_price=entry_price_value,
                start_adj_factor=entry_factor,
                end_price=_positive_float(exit_price),
                end_adj_factor=exit_factor,
            )
            net_adj = net_return_after_costs(
                gross_adj,
                buy_cost_rate=history_task.BUY_COST_RATE,
                sell_cost_rate=history_task.SELL_COST_RATE,
                slippage_rate=history_task.SLIPPAGE_RATE,
            )
            adj[horizon] = (gross_adj, net_adj)
            if exit_date_text and gross_adj is None:
                missing_horizons.append(horizon)

        evidence = _merge_adjustment_evidence(
            evidence_json,
            {
                "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
                "adj_factor_missing": bool(missing_horizons or (entry_date_text and entry_factor is None)),
                "adj_factor_missing_horizons": missing_horizons,
                "entry_ex_div": entry_ex_div,
                "entry_adj_factor_signal": signal_factor,
                "entry_adj_factor": entry_factor,
            },
        )
        conn.execute(
            f"""
            update {table_name}
            set entry_ex_div = ?,
                return_1d_gross_adj = ?,
                return_1d_net_adj = ?,
                return_5d_gross_adj = ?,
                return_5d_net_adj = ?,
                return_10d_gross_adj = ?,
                return_10d_net_adj = ?,
                return_20d_gross_adj = ?,
                return_20d_net_adj = ?,
                price_adjustment_mode = ?,
                evidence_json = ?
            where signal_date = ?
              and stock_code = ?
            """,
            [
                entry_ex_div,
                adj["1d"][0],
                adj["1d"][1],
                adj["5d"][0],
                adj["5d"][1],
                adj["10d"][0],
                adj["10d"][1],
                adj["20d"][0],
                adj["20d"][1],
                PRICE_ADJUSTMENT_MODE,
                json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                signal_date,
                stock_code,
            ],
        )
        updated += 1
    return updated


def _build_report(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
    candidate_updated: int,
    universe_updated: int,
    execution_updated: int,
) -> str:
    affected_rows = _safe_scalar(
        conn,
        """
        select count(*) from livermore_candidate_history
        where ex_div_in_window = true
          and cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        """,
        [start_date, end_date],
    )
    total_rows = _safe_scalar(
        conn,
        """
        select count(*) from livermore_candidate_history
        where cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        """,
        [start_date, end_date],
    )
    bucket_rows = _safe_rows(
        conn,
        """
        select
          coalesce(market_state, 'UNKNOWN') as market_state,
          coalesce(signal_kind, 'UNKNOWN') as signal_kind,
          count(return_5d) as n_raw,
          avg(return_5d) as avg_5d_raw,
          avg(case when return_5d > 0 then 1.0 else 0.0 end) as win_5d_raw,
          count(return_5d_adj) as n_adj,
          avg(return_5d_adj) as avg_5d_adj,
          avg(case when return_5d_adj > 0 then 1.0 else 0.0 end) as win_5d_adj
        from livermore_candidate_history
        where cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        group by 1, 2
        order by 1, 2
        """,
        [start_date, end_date],
    )
    lines = [
        "# 2026-07 Adjusted vs Unadjusted Return Report",
        "",
        f"- Window: {start_date} to {end_date}",
        f"- Candidate rows updated: {candidate_updated}",
        f"- Universe rows updated: {universe_updated}",
        f"- Execution rows updated: {execution_updated}",
        f"- Ex-div affected candidate rows: {affected_rows} / {total_rows}",
        "",
        "## Market State x Signal Kind",
        "",
        "| market_state | signal_kind | n_raw | avg_5d_raw | win_5d_raw | n_adj | avg_5d_adj | win_5d_adj | conclusion_flipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in bucket_rows:
        market_state, signal_kind, n_raw, avg_raw, win_raw, n_adj, avg_adj, win_adj = row
        flipped = _sign_flipped(avg_raw, avg_adj)
        lines.append(
            f"| {market_state} | {signal_kind} | {int(n_raw or 0)} | {_fmt_pct(avg_raw)} | {_fmt_pct(win_raw)} | "
            f"{int(n_adj or 0)} | {_fmt_pct(avg_adj)} | {_fmt_pct(win_adj)} | {'yes' if flipped else 'no'} |"
        )
    if not bucket_rows:
        lines.append("| no_data | no_data | 0 | n/a | n/a | 0 | n/a | n/a | no |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Adjusted returns use close/open prices multiplied by same-date adj_factor ratio.",
            "- Rows with missing adj_factor keep adjusted return columns null and carry adjustment_evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _adjustment_factor(conn: duckdb.DuckDBPyConnection, *, stock_code: str, trade_date: str) -> float | None:
    if not stock_code or not trade_date or STOCK_ADJUSTMENT_FACTOR_TABLE not in _table_names(conn):
        return None
    row = conn.execute(
        f"""
        select adj_factor
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where stock_code = ? and trade_date = ? and adj_factor is not null
        order by run_id desc, source_version desc
        limit 1
        """,
        [stock_code, trade_date[:10]],
    ).fetchone()
    return _positive_float(row[0]) if row is not None else None


def _close_value(conn: duckdb.DuckDBPyConnection, *, stock_code: str, trade_date: str) -> float | None:
    if history_task.TABLE_OBS not in _table_names(conn):
        return None
    row = conn.execute(
        f"""
        select close_value
        from {history_task.TABLE_OBS}
        where stock_code = ? and trade_date = ? and close_value is not null
        limit 1
        """,
        [stock_code, trade_date[:10]],
    ).fetchone()
    return _positive_float(row[0]) if row is not None else None


def _merge_adjustment_evidence(existing_json: object, adjustment: dict[str, object]) -> dict[str, object]:
    existing: dict[str, object]
    try:
        parsed = json.loads(str(existing_json or "{}"))
        existing = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        existing = {}
    existing["adjustment_evidence"] = adjustment
    return existing


def _safe_scalar(conn: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        return 0
    return int(row[0] or 0) if row else 0


def _safe_rows(conn: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> list[tuple[Any, ...]]:
    try:
        return list(conn.execute(sql, params).fetchall())
    except Exception:
        return []


def _sign_flipped(a: object, b: object) -> bool:
    left = _positive_or_zero(a)
    right = _positive_or_zero(b)
    if left is None or right is None:
        return False
    return (left < 0 < right) or (right < 0 < left)


def _fmt_pct(value: object) -> str:
    number = _positive_or_zero(value)
    if number is None:
        return "n/a"
    return f"{number:.4%}"


def _positive_or_zero(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value: object) -> float | None:
    number = _positive_or_zero(value)
    if number is None or number <= 0:
        return None
    return number


def _date_text(value: object) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else ""


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill adjusted Livermore strategy return columns.")
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--start", "--start-date", dest="start_date", required=True)
    parser.add_argument("--end", "--end-date", dest="end_date", required=True)
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args()

    try:
        result = backfill_adjusted_returns(
            duckdb_path=args.duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
            report_path=args.report_path,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
