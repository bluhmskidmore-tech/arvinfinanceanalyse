from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.portfolio_backtest import (  # noqa: E402
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MAX_POSITIONS,
    PORTFOLIO_ENGINE_VERSION,
    VARIANT_HORIZONS,
    build_benchmark_comparison,
    filter_rows_by_liquidity_floor,
    liquidity_floor_summary,
    run_portfolio_backtests,
    write_equity_curve_csv,
)
from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date  # noqa: E402
from backend.app.core_finance.portfolio_paths import (  # noqa: E402
    PATH_BASIS_RAW_FALLBACK,
    calculate_path_horizon_exit,
    load_position_price_paths,
    path_entry_price,
    path_mark_price,
    position_path_key,
)
from backend.app.core_finance.strategy_policy import POLICY  # noqa: E402
from backend.app.core_finance.vol_target_overlay import build_vol_target_index_comparison  # noqa: E402

TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
TABLE_BENCHMARK_DAILY = "fact_choice_macro_daily"
TABLE_BENCHMARK_SNAPSHOT = "choice_market_snapshot"
BENCHMARK_SERIES_ID = "CA.CSI300"
DEFAULT_REPORT_PATH = Path("docs/pnl/2026-07-portfolio-backtest-report.md")
DEFAULT_HOLD_PROGRESS_MATRIX_PATH = Path("docs/pnl/2026-07-batch2-hold-progress-matrix.md")


def run_portfolio_backtest_from_duckdb(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    output_dir: str | Path = "docs/pnl",
    signal_kind: str = "stock_candidate",
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    exposure_basis: str = "per-date",
    mode: str = "horizon",
    hold_progress_report_path: str | Path = DEFAULT_HOLD_PROGRESS_MATRIX_PATH,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    db_file = Path(db_path)
    if not db_file.exists():
        payload = _blocked_payload(f"DuckDB file not found: {db_file}")
        _write_blocked_report(report, payload)
        if mode == "path":
            _write_hold_progress_matrix_report(Path(hold_progress_report_path), payload)
        return payload

    conn = duckdb.connect(str(db_file), read_only=True)
    try:
        tables = _table_names(conn)
        if TABLE_EXECUTION_HIST not in tables:
            payload = _blocked_payload(
                f"Required table {TABLE_EXECUTION_HIST} is missing; run execution-history materialization first."
            )
            _write_blocked_report(report, payload)
            if mode == "path":
                _write_hold_progress_matrix_report(Path(hold_progress_report_path), payload)
            return payload

        execution_rows, load_issues = _load_execution_rows(
            conn,
            tables=tables,
            signal_kind=signal_kind,
            start_date=start_date,
            end_date=end_date,
        )
        if not execution_rows:
            payload = {
                "status": "empty",
                "reason": "No execution rows matched the requested filters.",
                "issues": load_issues,
                "report_path": str(report),
            }
            _write_empty_report(report, payload)
            if mode == "path":
                _write_hold_progress_matrix_report(Path(hold_progress_report_path), payload)
            return payload

        market_state_rows = _market_state_rows_from_execution(execution_rows)
        exposure_start = min(str(row["entry_date"])[:10] for row in execution_rows if row.get("entry_date"))
        exposure_end = max(
            str(row.get("exit_date_20d") or row.get("exit_date_5d") or row.get("entry_date"))[:10]
            for row in execution_rows
        )
        if exposure_basis == "state-max":
            exposure_rows = []
            exposure_issues = ["Using state_max exposure basis by explicit request."]
        else:
            exposure_rows, exposure_issues = _load_daily_exposure_rows(
                conn,
                tables=tables,
                start_date=exposure_start,
                end_date=exposure_end,
            )
        load_issues.extend(exposure_issues)
        benchmark_rows, benchmark_tables = _load_benchmark_rows(
            conn,
            tables=tables,
            start_date=exposure_start,
            end_date=exposure_end,
        )
        price_paths = (
            load_position_price_paths(conn, execution_rows, max_horizon_days=25)
            if mode == "path"
            else {}
        )
    finally:
        conn.close()

    vol_target = _build_vol_target_payload(
        benchmark_rows,
        exposure_rows,
        market_state_rows,
        initial_capital=initial_capital,
    )
    vol_target_exposure_by_target = {
        float(target_vol): {
            str(date_key): float(exposure)
            for date_key, exposure in comparison.get("vol_target_exposure_by_date", {}).items()
        }
        for target_vol, comparison in vol_target.get("comparisons", {}).items()
        if comparison.get("status") == "ready"
    }

    results = _run_portfolio_result_set(
        execution_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        initial_capital=initial_capital,
        max_positions=max_positions,
        mode=mode,
        price_paths=price_paths,
        vol_target_exposure_by_target=vol_target_exposure_by_target,
    )
    csv_paths: dict[str, str] = {}
    comparisons: dict[str, dict[str, object]] = {}
    for variant, result in results.items():
        csv_path = output_path / f"portfolio_equity_{variant}.csv"
        write_equity_curve_csv(csv_path, result.equity_curve)
        csv_paths[variant] = str(csv_path)
        comparisons[variant] = build_benchmark_comparison(
            result.equity_curve,
            benchmark_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            initial_capital=initial_capital,
        )

    liquidity_summary = liquidity_floor_summary(execution_rows)
    liquidity_rows = filter_rows_by_liquidity_floor(execution_rows)
    liquidity_results = _run_portfolio_result_set(
        liquidity_rows,
        market_state_rows,
        exposure_rows=exposure_rows,
        initial_capital=initial_capital,
        max_positions=max_positions,
        mode=mode,
        price_paths=price_paths,
        vol_target_exposure_by_target=vol_target_exposure_by_target,
    )
    actual_exposure_basis = next(
        (str(result.metrics.get("exposure_basis")) for result in results.values() if result.metrics.get("exposure_basis")),
        "state_max_fallback",
    )
    payload = {
        "status": "ready",
        "db_path": str(db_file),
        "report_path": str(report),
        "csv_paths": csv_paths,
        "execution_row_count": len(execution_rows),
        "signal_kind": signal_kind,
        "portfolio_engine_version": PORTFOLIO_ENGINE_VERSION,
        "mode": mode,
        "metric_basis": "T+1 open execution history, net adjusted horizon returns, daily market_gate exposure when available; otherwise policy state fallback; risk_budget variants size by risk_per_trade / stop_distance_pct with policy caps; max_entry_premium variants skip rows with entry_price/signal_close - 1 above the threshold; probe_pyramid variants use half-size probes, close>signal-high confirmation, and next-open add/failed-exit path accounting",
        "exposure_basis": actual_exposure_basis,
        "daily_exposure_rows": len(exposure_rows),
        "price_path_count": len(price_paths),
        "price_path_adj_factor_missing_rows": _price_path_missing_adj_factor_rows(price_paths),
        "price_path_adj_factor_forward_filled_rows": (
            _price_path_forward_filled_adj_factor_rows(price_paths)
        ),
        "price_path_raw_fallback_paths": _price_path_raw_fallback_paths(price_paths),
        "results": {
            variant: {
                "metrics": result.metrics,
                "skip_counts": result.skip_counts,
                "trade_count": len(result.trades),
            }
            for variant, result in results.items()
        },
        "comparisons": comparisons,
        "benchmark_tables": benchmark_tables,
        "liquidity_floor": {
            "summary": liquidity_summary,
            "filtered_row_count": len(liquidity_rows),
            "metrics_after_floor": {
                variant: result.metrics for variant, result in liquidity_results.items()
            },
        },
        "risk_exit_variant": {
            "status": "not_run",
            "reason": "Task5 report did not provide per-position risk-exit dates in the local dataset.",
        },
        "vol_target": vol_target,
        "issues": load_issues,
    }
    if mode == "path":
        matrix_payload = _build_hold_progress_matrix(execution_rows, price_paths)
        payload["hold_progress_matrix"] = {
            "status": matrix_payload["status"],
            "row_count": len(matrix_payload.get("rows") or []),
            "report_path": str(hold_progress_report_path),
        }
        _write_hold_progress_matrix_report(Path(hold_progress_report_path), matrix_payload)
    _write_ready_report(report, payload)
    return payload


def _load_execution_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    signal_kind: str,
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[dict[str, object]], list[str]]:
    columns = _columns(conn, TABLE_EXECUTION_HIST)
    required = {
        "signal_date",
        "stock_code",
        "signal_kind",
        "candidate_rank",
        "market_state",
        "entry_date",
        "entry_executable",
        "exit_date_5d",
        "exit_date_20d",
    }
    missing = sorted(required - columns)
    return_5d_expr = _first_available_column_sql(
        columns,
        ("return_5d_net_adj", "return_5d_adj", "return_5d_net", "return_5d"),
        alias="return_5d_net_adj",
    )
    return_20d_expr = _first_available_column_sql(
        columns,
        ("return_20d_net_adj", "return_20d_adj", "return_20d_net", "return_20d"),
        alias="return_20d_net_adj",
    )
    if return_5d_expr is None:
        missing.append("one of return_5d_net_adj, return_5d_adj, return_5d_net, return_5d")
    if return_20d_expr is None:
        missing.append("one of return_20d_net_adj, return_20d_adj, return_20d_net, return_20d")
    if missing:
        return [], [f"{TABLE_EXECUTION_HIST} missing columns: {', '.join(missing)}"]

    obs_columns = _columns(conn, TABLE_OBS) if TABLE_OBS in tables else set()
    has_daily_amount = "amount" in obs_columns
    has_signal_high = "high_value" in obs_columns
    has_execution_signal_close = "signal_close" in columns
    has_observation_signal_close = "close_value" in obs_columns
    needs_signal_adj = has_signal_high or (not has_execution_signal_close and has_observation_signal_close)
    has_signal_adj = needs_signal_adj and TABLE_ADJ_FACTOR in tables and {
        "stock_code",
        "trade_date",
        "adj_factor",
    }.issubset(_columns(conn, TABLE_ADJ_FACTOR))
    has_daily_join = has_daily_amount or has_signal_high or (not has_execution_signal_close and has_observation_signal_close)
    daily_select = "d.amount as daily_amount" if has_daily_amount else "cast(null as double) as daily_amount"
    signal_factor_expr = "af_signal.adj_factor" if has_signal_adj else "1.0"
    signal_adj_missing_select = (
        "d.stock_code is not null and af_signal.adj_factor is null as signal_adj_factor_missing"
        if has_signal_adj
        else "false as signal_adj_factor_missing"
    )
    signal_high_select = (
        f"d.high_value * {signal_factor_expr} as signal_high"
        if has_signal_high
        else "cast(null as double) as signal_high"
    )
    if has_execution_signal_close:
        signal_close_select = "e.signal_close as signal_close"
    elif has_observation_signal_close:
        signal_close_select = f"d.close_value * {signal_factor_expr} as signal_close"
    else:
        signal_close_select = "cast(null as double) as signal_close"
    daily_join = (
        f"""
        left join {TABLE_OBS} d
          on d.stock_code = e.stock_code
         and cast(d.trade_date as date) = cast(e.signal_date as date)
        """
        if has_daily_join
        else ""
    )
    signal_adj_join = (
        f"""
        left join {TABLE_ADJ_FACTOR} af_signal
          on af_signal.stock_code = d.stock_code
         and cast(af_signal.trade_date as date) = cast(d.trade_date as date)
        """
        if has_signal_adj
        else ""
    )
    history_columns = _columns(conn, "livermore_candidate_history") if "livermore_candidate_history" in tables else set()
    has_history_ema10 = {
        "snapshot_as_of_date",
        "stock_code",
        "ema10",
    }.issubset(history_columns)
    history_select = "h.ema10 as ema10_signal" if has_history_ema10 else "cast(null as double) as ema10_signal"
    if has_history_ema10 and "signal_kind" in history_columns:
        history_join = """
        left join livermore_candidate_history h
          on h.stock_code = e.stock_code
         and cast(h.snapshot_as_of_date as date) = cast(e.signal_date as date)
         and coalesce(h.signal_kind, e.signal_kind) = e.signal_kind
        """
    elif has_history_ema10:
        history_join = """
        left join livermore_candidate_history h
          on h.stock_code = e.stock_code
         and cast(h.snapshot_as_of_date as date) = cast(e.signal_date as date)
        """
    else:
        history_join = ""
    where = ["e.entry_date is not null"]
    params: list[object] = []
    if signal_kind:
        where.append("e.signal_kind = ?")
        params.append(signal_kind)
    if start_date:
        where.append("cast(e.signal_date as date) >= cast(? as date)")
        params.append(start_date)
    if end_date:
        where.append("cast(e.signal_date as date) <= cast(? as date)")
        params.append(end_date)
    rows = conn.execute(
        f"""
        select
          e.signal_date,
          e.stock_code,
          e.stock_name,
          e.signal_kind,
          e.candidate_rank,
          e.market_state,
          e.entry_date,
          e.entry_price,
          {signal_close_select},
          e.entry_executable,
          e.entry_block_reason,
          e.exit_date_5d,
          {return_5d_expr},
          e.exit_date_20d,
          {return_20d_expr},
          {daily_select},
          {signal_high_select},
          {history_select},
          {signal_adj_missing_select}
        from {TABLE_EXECUTION_HIST} e
        {daily_join}
        {signal_adj_join}
        {history_join}
        where {" and ".join(where)}
        order by cast(e.entry_date as date), e.candidate_rank, e.stock_code
        """,
        params,
    ).fetchall()
    out = [
        {
            "signal_date": str(row[0])[:10],
            "stock_code": str(row[1]),
            "stock_name": row[2],
            "signal_kind": row[3],
            "candidate_rank": row[4],
            "market_state": row[5],
            "entry_date": str(row[6])[:10] if row[6] is not None else None,
            "entry_price": row[7],
            "signal_close": row[8],
            "entry_executable": row[9],
            "entry_block_reason": row[10],
            "exit_date_5d": str(row[11])[:10] if row[11] is not None else None,
            "return_5d_net_adj": row[12],
            "exit_date_20d": str(row[13])[:10] if row[13] is not None else None,
            "return_20d_net_adj": row[14],
            "daily_amount": row[15],
            "signal_high": row[16],
            "ema10": row[17],
        }
        for row in rows
    ]
    issues = []
    if not has_daily_amount:
        issues.append(f"{TABLE_OBS}.amount unavailable; liquidity sensitivity keeps rows as unknown.")
    if not has_signal_high:
        issues.append(f"{TABLE_OBS}.high_value unavailable; probe_pyramid variants skip rows.")
    if not has_execution_signal_close and not has_observation_signal_close:
        issues.append("signal_close unavailable; max_entry_premium variants cannot block rows.")
    signal_adj_missing_count = sum(1 for row in rows if bool(row[18])) if has_signal_adj else 0
    if signal_adj_missing_count:
        issues.append(
            f"{signal_adj_missing_count} rows lacked signal-day adjustment factors; "
            "signal_high/observation signal_close are set to null for adjusted-basis variants."
        )
    return out, issues


def _load_daily_exposure_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, object]], list[str]]:
    points = load_gate_exposure_by_date(conn, start_date, end_date)
    rows = [
        {
            "trade_date": trade_date,
            "exposure": point.exposure,
            "market_state": point.state,
            "source": point.source,
        }
        for trade_date, point in points.items()
        if point.source != "missing"
    ]
    source_counts: dict[str, int] = {}
    for point in points.values():
        source_counts[point.source] = source_counts.get(point.source, 0) + 1
    issues = [
        "Daily exposure source counts: "
        + ", ".join(f"{source}={count}" for source, count in sorted(source_counts.items()))
    ]
    if source_counts.get("missing"):
        issues.append(
            f"{source_counts['missing']} dates lacked persisted or replayed gate exposure; portfolio uses state fallback for those dates."
        )
    if not rows:
        issues.append("Portfolio uses policy state exposure fallback.")
    return rows, issues


def _load_benchmark_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start_date: str,
    end_date: str,
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
              and cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
            order by cast(trade_date as date)
            """,
            [BENCHMARK_SERIES_ID, start_date, end_date],
        ).fetchall()
        if rows:
            tables_used.append(table)
        for trade_date, value in rows:
            by_date[str(trade_date)[:10]] = {
                "trade_date": str(trade_date)[:10],
                "value": value,
            }
    return [by_date[key] for key in sorted(by_date)], tables_used


def _market_state_rows_from_execution(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_date: dict[str, str] = {}
    for row in rows:
        state = str(row.get("market_state") or "").strip()
        if not state:
            continue
        date_value = row.get("entry_date")
        if date_value:
            by_date.setdefault(str(date_value)[:10], state)
    return [{"trade_date": key, "market_state": by_date[key]} for key in sorted(by_date)]


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _first_available_column_sql(columns: set[str], candidates: Sequence[str], *, alias: str) -> str | None:
    available = [f"e.{column}" for column in candidates if column in columns]
    if not available:
        return None
    if len(available) == 1:
        return f"{available[0]} as {alias}"
    return f"coalesce({', '.join(available)}) as {alias}"


def _price_path_missing_adj_factor_rows(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> int:
    return sum(
        1
        for rows in price_paths.values()
        for row in rows
        if bool(row.get("adj_factor_missing"))
    )


def _price_path_forward_filled_adj_factor_rows(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> int:
    return sum(
        1
        for rows in price_paths.values()
        for row in rows
        if bool(row.get("adj_factor_forward_filled"))
    )


def _price_path_raw_fallback_paths(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> int:
    return sum(
        1
        for rows in price_paths.values()
        if any(
            str(row.get("path_price_basis") or "") == PATH_BASIS_RAW_FALLBACK
            for row in rows
        )
    )


def _run_portfolio_result_set(
    execution_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    initial_capital: float,
    max_positions: int,
    mode: str,
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    vol_target_exposure_by_target: Mapping[float, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    results: dict[str, Any] = dict(
        run_portfolio_backtests(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variants=tuple(VARIANT_HORIZONS),
            initial_capital=initial_capital,
            max_positions=max_positions,
            mode=mode,
            price_paths=price_paths,
        )
    )
    for risk_per_trade in POLICY.backtest_variants.risk_budget_risk_per_trade_grid:
        risk_results = run_portfolio_backtests(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variants=("fixed_20d",),
            initial_capital=initial_capital,
            max_positions=max_positions,
            mode=mode,
            price_paths=price_paths,
            sizing="risk_budget",
            risk_per_trade=risk_per_trade,
            single_name_cap=POLICY.backtest_variants.risk_budget_single_name_cap,
            fallback_stop_distance_pct=POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct,
        )
        for variant, result in risk_results.items():
            results[f"{variant}_risk_budget_rpt_{_risk_per_trade_label(risk_per_trade)}"] = result
    for max_entry_premium in POLICY.backtest_variants.max_entry_premium_grid:
        premium_results = run_portfolio_backtests(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variants=("fixed_20d",),
            initial_capital=initial_capital,
            max_positions=max_positions,
            mode=mode,
            price_paths=price_paths,
            max_entry_premium=max_entry_premium,
        )
        for variant, result in premium_results.items():
            results[f"{variant}_max_entry_premium_{_max_entry_premium_label(max_entry_premium)}"] = result
    for target_vol, exposure_by_date in (vol_target_exposure_by_target or {}).items():
        vol_results = run_portfolio_backtests(
            execution_rows,
            market_state_rows,
            exposure_rows=exposure_rows,
            variants=("fixed_20d",),
            initial_capital=initial_capital,
            max_positions=max_positions,
            mode=mode,
            price_paths=price_paths,
            exposure_by_date=exposure_by_date,
            vol_target=target_vol,
        )
        for variant, result in vol_results.items():
            results[f"{variant}_vol_target_{_target_vol_label(target_vol)}"] = result
    if mode == "path":
        for confirm_days in POLICY.backtest_variants.probe_confirm_days_grid:
            probe_results = run_portfolio_backtests(
                execution_rows,
                market_state_rows,
                exposure_rows=exposure_rows,
                variants=("fixed_20d",),
                initial_capital=initial_capital,
                max_positions=max_positions,
                mode=mode,
                price_paths=price_paths,
                entry_style="probe_pyramid",
                probe_fraction=POLICY.backtest_variants.probe_fraction,
                confirm_days=confirm_days,
            )
            for variant, result in probe_results.items():
                results[f"{variant}_probe_pyramid_cd_{confirm_days}"] = result
    return results


def _risk_per_trade_label(value: float) -> str:
    return f"{value:.3f}".replace(".", "p")


def _max_entry_premium_label(value: float | None) -> str:
    return "none" if value is None else f"{value:.2f}".replace(".", "p")


def _target_vol_label(value: float) -> str:
    return f"{value:.2f}".replace(".", "p")


def _build_vol_target_payload(
    benchmark_rows: Sequence[Mapping[str, object]],
    exposure_rows: Sequence[Mapping[str, object]],
    market_state_rows: Sequence[Mapping[str, object]],
    *,
    initial_capital: float,
) -> dict[str, Any]:
    comparisons: dict[float, dict[str, object]] = {}
    for target_vol in POLICY.backtest_variants.vol_target_grid:
        comparisons[float(target_vol)] = build_vol_target_index_comparison(
            benchmark_rows,
            exposure_rows=exposure_rows,
            market_state_rows=market_state_rows,
            exposure_by_market_state=POLICY.exposure_by_market_state,
            target_vol=target_vol,
            window=POLICY.backtest_variants.vol_target_window,
            initial_capital=initial_capital,
        )
    status = "ready" if any(row.get("status") == "ready" for row in comparisons.values()) else "benchmark_unavailable"
    return {
        "status": status,
        "window": POLICY.backtest_variants.vol_target_window,
        "comparisons": comparisons,
    }


def _build_hold_progress_matrix(
    execution_rows: list[dict[str, object]],
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, Any]:
    if not execution_rows:
        return _blocked_payload("No execution rows available for hold-progress matrix.")
    if not price_paths:
        return _blocked_payload("No position price paths available for hold-progress matrix.")

    observations: dict[tuple[int, str], list[float]] = {}
    counts: dict[tuple[int, str], int] = {}
    for row in execution_rows:
        stock_code = str(row.get("stock_code") or "").strip()
        entry_date = str(row.get("entry_date") or "")[:10]
        final_return = _first_float(row.get("return_20d_net_adj"), row.get("return_20d_net"))
        if not stock_code or not entry_date:
            continue
        path = price_paths.get(position_path_key(stock_code, entry_date))
        if not path:
            continue
        entry_price = path_entry_price(path[0], fallback=_first_float(row.get("entry_price")))
        if entry_price is None or entry_price <= 0:
            continue
        if final_return is None:
            final_exit = calculate_path_horizon_exit(
                path,
                horizon_days=20,
                entry_price=entry_price,
                buy_cost_rate=POLICY.buy_cost_rate,
                sell_cost_rate=POLICY.sell_cost_rate,
                slippage_rate=POLICY.slippage_rate,
            )
            final_return = _first_float(final_exit.get("return_net")) if final_exit is not None else None
        if final_return is None:
            continue
        for day_index in (1, 2, 3, 5, 8):
            if len(path) < day_index:
                continue
            mark = path_mark_price(path[day_index - 1])
            if mark is None:
                continue
            progress_return = mark / entry_price - 1.0
            bucket = _hold_progress_bucket(progress_return)
            key = (day_index, bucket)
            observations.setdefault(key, []).append(final_return)
            counts[key] = counts.get(key, 0) + 1

    rows: list[dict[str, object]] = []
    for key in sorted(observations):
        final_returns = observations[key]
        day_index, bucket = key
        rows.append(
            {
                "day": day_index,
                "progress_bucket": bucket,
                "sample_count": counts[key],
                "avg_t20_net_return": sum(final_returns) / len(final_returns),
                "win_rate": sum(1 for value in final_returns if value > 0) / len(final_returns),
            }
        )
    if not rows:
        return _blocked_payload("No matched path and T+20 return samples for hold-progress matrix.")
    return {"status": "ready", "rows": rows}


def _hold_progress_bucket(value: float) -> str:
    if value < -0.03:
        return "lt_-3pct"
    if value < 0.0:
        return "-3pct_to_0"
    if value < 0.02:
        return "0_to_+2pct"
    if value < 0.05:
        return "+2pct_to_+5pct"
    return "gt_+5pct"


def _blocked_payload(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason}


def _write_blocked_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        "\n".join(
            [
                "# 2026-07 Portfolio Backtest Report",
                "",
                f"- status: {payload['status']}",
                f"- reason: {payload['reason']}",
                "",
                "No portfolio net-value curve was generated.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_empty_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        "\n".join(
            [
                "# 2026-07 Portfolio Backtest Report",
                "",
                "- status: empty",
                f"- reason: {payload['reason']}",
                f"- issues: {payload.get('issues') or []}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_hold_progress_matrix_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload.get("status") != "ready":
        path.write_text(
            "\n".join(
                [
                    "# 2026-07 Batch 2 Hold Progress Matrix",
                    "",
                    f"- status: {payload.get('status', 'blocked')}",
                    f"- reason: {payload.get('reason', 'No matrix was generated.')}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return
    lines = [
        "# 2026-07 Batch 2 Hold Progress Matrix",
        "",
        "- status: ready",
        "",
        "| entry_day | floating_pnl_bucket | sample_count | avg_t20_net_return | win_rate |",
        "|---:|---|---:|---:|---:|",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            "| {day} | {bucket} | {count} | {avg} | {win} |".format(
                day=row["day"],
                bucket=row["progress_bucket"],
                count=row["sample_count"],
                avg=_fmt(row["avg_t20_net_return"]),
                win=_fmt(row["win_rate"]),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ready_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# 2026-07 Portfolio Backtest Report",
        "",
        f"- status: {payload['status']}",
        f"- db_path: {payload['db_path']}",
        f"- signal_kind: {payload['signal_kind']}",
        f"- portfolio_engine_version: {payload['portfolio_engine_version']}",
        f"- mode: {payload['mode']}",
        f"- execution_row_count: {payload['execution_row_count']}",
        f"- metric_basis: {payload['metric_basis']}",
        f"- exposure_basis: {payload['exposure_basis']}",
        f"- daily_exposure_rows: {payload['daily_exposure_rows']}",
        f"- price_path_count: {payload['price_path_count']}",
        f"- price_path_adj_factor_missing_rows: {payload['price_path_adj_factor_missing_rows']}",
        f"- price_path_adj_factor_forward_filled_rows: {payload['price_path_adj_factor_forward_filled_rows']}",
        f"- price_path_raw_fallback_paths: {payload['price_path_raw_fallback_paths']}",
        f"- benchmark_tables: {payload['benchmark_tables'] or 'unavailable'}",
        f"- issues: {payload['issues'] or []}",
        "",
        "## Strategy Metrics",
        "",
        "| variant | sizing | entry_style | risk_per_trade | max_entry_premium | vol_target | entry_premium_blocked | probe_confirm_rate | probe_failed_exit | probe_failed_avg_loss | probe_confirmed_avg_return | probe_confirmed_median_return | probe_confirmed_win_rate | terminal_value | cumulative_return | cagr | max_drawdown | daily_sharpe | annual_turnover | avg_slot_utilization | empty_day_ratio | max_single_name_weight | risk_budget_hit_rate | stop_ref_fallback | exposure_cap_clipped | exposure_fallback_days | exposure_fallback_day_ratio | skips |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, result in payload["results"].items():
        metrics = result["metrics"]
        skips = sum(int(value) for value in result["skip_counts"].values())
        lines.append(
            "| {variant} | {sizing} | {entry_style} | {risk_per_trade} | {max_entry_premium} | {vol_target} | {entry_premium_blocked} | {probe_confirm_rate} | {probe_failed_exit} | {probe_failed_loss} | {probe_confirmed_avg} | {probe_confirmed_median} | {probe_confirmed_win} | {terminal} | {cum} | {cagr} | {mdd} | {sharpe} | {turnover} | {slot} | {empty} | {single} | {risk_hit} | {stop_fallback} | {cap_clipped} | {fallback_days} | {fallback_ratio} | {skips} |".format(
                variant=variant,
                sizing=metrics.get("sizing") or "equal_weight",
                entry_style=metrics.get("entry_style") or "full",
                risk_per_trade=_fmt(metrics.get("risk_per_trade")),
                max_entry_premium=_fmt(metrics.get("max_entry_premium")),
                vol_target=_fmt(metrics.get("vol_target")),
                entry_premium_blocked=_fmt(metrics.get("entry_premium_blocked")),
                probe_confirm_rate=_fmt(metrics.get("probe_confirm_rate")),
                probe_failed_exit=_fmt(metrics.get("probe_failed_exit")),
                probe_failed_loss=_fmt(metrics.get("probe_failed_avg_loss")),
                probe_confirmed_avg=_fmt(metrics.get("probe_confirmed_avg_return")),
                probe_confirmed_median=_fmt(metrics.get("probe_confirmed_median_return")),
                probe_confirmed_win=_fmt(metrics.get("probe_confirmed_win_rate")),
                terminal=_fmt(metrics.get("terminal_value")),
                cum=_fmt(metrics.get("cumulative_return")),
                cagr=_fmt(metrics.get("cagr")),
                mdd=_fmt(metrics.get("max_drawdown")),
                sharpe=_fmt(metrics.get("daily_sharpe")),
                turnover=_fmt(metrics.get("annual_turnover")),
                slot=_fmt(metrics.get("avg_slot_utilization")),
                empty=_fmt(metrics.get("empty_day_ratio")),
                single=_fmt(metrics.get("max_single_name_weight")),
                risk_hit=_fmt(metrics.get("risk_budget_hit_rate")),
                stop_fallback=_fmt(metrics.get("stop_ref_fallback")),
                cap_clipped=_fmt(metrics.get("exposure_cap_clipped")),
                fallback_days=_fmt(metrics.get("exposure_fallback_days")),
                fallback_ratio=_fmt(metrics.get("exposure_fallback_day_ratio")),
                skips=skips,
            )
        )
    lines.extend(
        [
            "",
            "## Benchmark Comparison",
            "",
            "| variant | benchmark_status | strategy_return | csi300_buy_hold_return | gate_timing_return | stock_selection_increment |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for variant, comparison in payload["comparisons"].items():
        metrics = comparison.get("metrics") if isinstance(comparison, dict) else {}
        strategy = metrics.get("strategy", {}) if isinstance(metrics, dict) else {}
        buy_hold = metrics.get("csi300_buy_hold", {}) if isinstance(metrics, dict) else {}
        gate = metrics.get("gate_timing_csi300", {}) if isinstance(metrics, dict) else {}
        increment = metrics.get("stock_selection_increment", {}) if isinstance(metrics, dict) else {}
        lines.append(
            "| {variant} | {status} | {strategy} | {buy_hold} | {gate} | {increment} |".format(
                variant=variant,
                status=comparison.get("status") if isinstance(comparison, dict) else "unknown",
                strategy=_fmt(strategy.get("cumulative_return")),
                buy_hold=_fmt(buy_hold.get("cumulative_return")),
                gate=_fmt(gate.get("cumulative_return")),
                increment=_fmt(increment.get("cumulative_return")),
            )
        )

    vol_target = payload.get("vol_target", {})
    lines.extend(
        [
            "",
            "## Vol Target",
            "",
            f"- status: {vol_target.get('status', 'not_run') if isinstance(vol_target, dict) else 'not_run'}",
            f"- window: {vol_target.get('window', 'NA') if isinstance(vol_target, dict) else 'NA'}",
            "",
            "| target_vol | line | cumulative_return | cagr | max_drawdown | daily_sharpe | avg_exposure | avg_multiplier | insufficient_history_days |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    comparisons_by_target = vol_target.get("comparisons", {}) if isinstance(vol_target, dict) else {}
    for target_vol, comparison in comparisons_by_target.items():
        metrics = comparison.get("metrics", {}) if isinstance(comparison, dict) else {}
        for line_name in ("gate_index", "gate_voltarget_index"):
            line_metrics = metrics.get(line_name, {}) if isinstance(metrics, dict) else {}
            lines.append(
                "| {target_vol} | {line} | {cum} | {cagr} | {mdd} | {sharpe} | {avg_exp} | {avg_mult} | {insufficient} |".format(
                    target_vol=_fmt(float(target_vol)),
                    line=line_name,
                    cum=_fmt(line_metrics.get("cumulative_return")),
                    cagr=_fmt(line_metrics.get("cagr")),
                    mdd=_fmt(line_metrics.get("max_drawdown")),
                    sharpe=_fmt(line_metrics.get("daily_sharpe")),
                    avg_exp=_fmt(line_metrics.get("avg_exposure")),
                    avg_mult=_fmt(line_metrics.get("avg_multiplier")),
                    insufficient=_fmt(line_metrics.get("insufficient_history_days")),
                )
            )

    liquidity = payload["liquidity_floor"]
    summary = liquidity["summary"]
    lines.extend(
        [
            "",
            "## Liquidity Floor Observation",
            "",
            f"- min_daily_amount: {summary['min_daily_amount']}",
            f"- known_pass_rows: {summary['known_pass_rows']}",
            f"- known_fail_rows: {summary['known_fail_rows']}",
            f"- missing_amount_rows: {summary['missing_amount_rows']}",
            f"- filtered_row_count: {liquidity['filtered_row_count']}",
            "",
            "| variant | before_cumulative_return | after_floor_cumulative_return | before_max_drawdown | after_floor_max_drawdown |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for variant, result in payload["results"].items():
        before = result["metrics"]
        after = liquidity["metrics_after_floor"].get(variant, {})
        lines.append(
            "| {variant} | {before_return} | {after_return} | {before_mdd} | {after_mdd} |".format(
                variant=variant,
                before_return=_fmt(before.get("cumulative_return")),
                after_return=_fmt(after.get("cumulative_return")),
                before_mdd=_fmt(before.get("max_drawdown")),
                after_mdd=_fmt(after.get("max_drawdown")),
            )
        )

    lines.extend(
        [
            "",
            "## Variant Notes",
            "",
            f"- risk_exit_variant: {payload['risk_exit_variant']['status']} - {payload['risk_exit_variant']['reason']}",
            "- live candidate behavior: unchanged; daily_amount/liquidity_floor_pass are observation fields only.",
            f"- hold_progress_matrix: {payload.get('hold_progress_matrix', {}).get('status', 'not_run')} ({payload.get('hold_progress_matrix', {}).get('report_path', 'not_generated')})",
            "",
            "## Output Files",
            "",
        ]
    )
    for variant, csv_path in payload["csv_paths"].items():
        lines.append(f"- {variant}: {csv_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _first_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and number not in {float("inf"), float("-inf")}:
            return number
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Livermore stock-candidate portfolio backtest.")
    parser.add_argument("--db-path", required=True, help="DuckDB database path.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    parser.add_argument("--output-dir", default="docs/pnl", help="Directory for portfolio equity CSV files.")
    parser.add_argument("--signal-kind", default="stock_candidate", help="Signal kind to include.")
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD signal-date lower bound.")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD signal-date upper bound.")
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL)
    parser.add_argument("--max-positions", type=int, default=DEFAULT_MAX_POSITIONS)
    parser.add_argument("--mode", choices=("horizon", "path"), default="horizon")
    parser.add_argument(
        "--hold-progress-report-path",
        default=str(DEFAULT_HOLD_PROGRESS_MATRIX_PATH),
        help="Markdown report path for path-mode hold progress matrix.",
    )
    parser.add_argument(
        "--exposure-basis",
        choices=("per-date", "state-max"),
        default="per-date",
        help="Use per-date gate exposure by default, or state-max fallback for old-basis comparisons.",
    )
    args = parser.parse_args()

    payload = run_portfolio_backtest_from_duckdb(
        db_path=args.db_path,
        report_path=args.report_path,
        output_dir=args.output_dir,
        signal_kind=args.signal_kind,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        exposure_basis=args.exposure_basis,
        mode=args.mode,
        hold_progress_report_path=args.hold_progress_report_path,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
