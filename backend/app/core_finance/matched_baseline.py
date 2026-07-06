from __future__ import annotations

import hashlib
import json
import random
import statistics
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb

from backend.app.core_finance.adjusted_returns import (
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    adjusted_return,
    net_return_after_costs,
    normalize_duckdb_path,
)
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

MATCHED_BASELINE_TABLE = "livermore_matched_baseline_history"
TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_SECTOR = "choice_stock_sector_membership"
TABLE_UNIVERSE = "choice_stock_universe"
FORMULA_VERSION = "fv_livermore_matched_baseline_v1"
CONTROL_SAMPLE_SIZE = 20
SAME_SECTOR_CONTROL_GROUP = "same_sector"
LIQUIDITY_FALLBACK_CONTROL_GROUP = "liquidity_quintile_fallback"
HORIZONS = ("1d", "5d", "10d", "20d")


def ensure_livermore_matched_baseline_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "31_livermore_matched_baseline.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def stable_control_seed(*, run_id: str | None, signal_date: str, candidate_stock_code: str) -> str:
    payload = "|".join([str(run_id or ""), str(signal_date or "")[:10], str(candidate_stock_code or "").upper()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def select_matched_controls(
    candidate: dict[str, Any],
    universe_rows: list[dict[str, Any]],
    *,
    sample_size: int = CONTROL_SAMPLE_SIZE,
    min_same_sector: int = CONTROL_SAMPLE_SIZE,
) -> list[dict[str, Any]]:
    candidate_code = _stock_code(candidate)
    seed = str(candidate.get("seed") or stable_control_seed(
        run_id=_text_or_none(candidate.get("run_id")),
        signal_date=str(candidate.get("signal_date") or ""),
        candidate_stock_code=candidate_code,
    ))
    eligible = [
        row
        for row in universe_rows
        if _stock_code(row) != candidate_code
        and _bool_value(row.get("entry_executable")) is True
        and not _is_st_stock(row)
    ]
    candidate_sector = _sector_key(candidate)
    same_sector = [row for row in eligible if candidate_sector and _sector_key(row) == candidate_sector]
    if len(same_sector) >= min_same_sector:
        return _sample_rows(same_sector, sample_size=sample_size, seed=f"{seed}:same_sector", group=SAME_SECTOR_CONTROL_GROUP)

    buckets = _liquidity_buckets(universe_rows)
    candidate_bucket = buckets.get(candidate_code)
    fallback_pool = [
        row
        for row in eligible
        if candidate_bucket is not None and buckets.get(_stock_code(row)) == candidate_bucket
    ]
    if not fallback_pool:
        fallback_pool = eligible
    return _sample_rows(
        fallback_pool,
        sample_size=sample_size,
        seed=f"{seed}:liquidity",
        group=LIQUIDITY_FALLBACK_CONTROL_GROUP,
    )


def generate_matched_baseline_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str | None,
    end_date: str | None,
    sample_size: int = CONTROL_SAMPLE_SIZE,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    resolved_run_id = run_id or f"run_matched_baseline_{uuid.uuid4().hex[:12]}"
    candidates = _load_candidate_execution_rows(conn, start_date=start_date, end_date=end_date)
    rows: list[dict[str, Any]] = []
    universe_by_date: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        signal_date = str(candidate.get("signal_date") or "")[:10]
        if not signal_date:
            continue
        candidate = {
            **candidate,
            "run_id": candidate.get("run_id") or resolved_run_id,
            "seed": stable_control_seed(
                run_id=str(candidate.get("run_id") or resolved_run_id),
                signal_date=signal_date,
                candidate_stock_code=str(candidate.get("stock_code") or ""),
            ),
        }
        universe_rows = universe_by_date.setdefault(signal_date, _load_control_universe_for_date(conn, signal_date))
        controls = select_matched_controls(candidate, universe_rows, sample_size=sample_size)
        for control in controls:
            returns = _control_execution_returns(
                conn,
                stock_code=_stock_code(control),
                signal_date=signal_date,
            )
            rows.append(
                {
                    "signal_date": signal_date,
                    "candidate_stock_code": _stock_code(candidate),
                    "signal_kind": str(candidate.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
                    "control_stock_code": _stock_code(control),
                    "control_group": control.get("control_group"),
                    "control_return_1d_net_adj": returns.get("return_1d_net_adj"),
                    "control_return_5d_net_adj": returns.get("return_5d_net_adj"),
                    "control_return_10d_net_adj": returns.get("return_10d_net_adj"),
                    "control_return_20d_net_adj": returns.get("return_20d_net_adj"),
                    "control_entry_executable": returns.get("entry_executable"),
                    "seed": candidate["seed"],
                    "formula_version": FORMULA_VERSION,
                    "run_id": resolved_run_id,
                }
            )
    return rows


def write_matched_baseline_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    start_date: str | None,
    end_date: str | None,
) -> int:
    ensure_livermore_matched_baseline_schema(conn)
    where_clauses: list[str] = []
    bindings: list[object] = []
    if start_date:
        where_clauses.append("cast(signal_date as date) >= cast(? as date)")
        bindings.append(start_date)
    if end_date:
        where_clauses.append("cast(signal_date as date) <= cast(? as date)")
        bindings.append(end_date)
    if where_clauses:
        conn.execute(
            f"delete from {MATCHED_BASELINE_TABLE} where {' and '.join(where_clauses)}",
            bindings,
        )
    if not rows:
        return 0
    conn.executemany(
        f"""
        insert into {MATCHED_BASELINE_TABLE}
        (signal_date, candidate_stock_code, signal_kind, control_stock_code, control_group,
         control_return_1d_net_adj, control_return_5d_net_adj, control_return_10d_net_adj,
         control_return_20d_net_adj, control_entry_executable, seed, formula_version, run_id)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["signal_date"],
                row["candidate_stock_code"],
                row["signal_kind"],
                row["control_stock_code"],
                row["control_group"],
                row["control_return_1d_net_adj"],
                row["control_return_5d_net_adj"],
                row["control_return_10d_net_adj"],
                row["control_return_20d_net_adj"],
                row["control_entry_executable"],
                row["seed"],
                row["formula_version"],
                row["run_id"],
            )
            for row in rows
        ],
    )
    return len(rows)


def backfill_matched_baseline(
    *,
    duckdb_path: str | Path,
    start_date: str | None,
    end_date: str | None,
    sample_size: int = CONTROL_SAMPLE_SIZE,
    dry_run: bool = False,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    path = normalize_duckdb_path(duckdb_path)
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    resolved_report = Path(report_path) if report_path else Path.cwd() / "docs/pnl/2026-07-matched-baseline-report.md"
    if not resolved_report.is_absolute():
        resolved_report = Path.cwd() / resolved_report
    run_id = f"run_matched_baseline_{uuid.uuid4().hex[:12]}"
    conn = duckdb.connect(str(path), read_only=dry_run)
    try:
        if not dry_run:
            ensure_livermore_matched_baseline_schema(conn)
        rows = generate_matched_baseline_rows(
            conn,
            start_date=start_date,
            end_date=end_date,
            sample_size=sample_size,
            run_id=run_id,
        )
        inserted = 0 if dry_run else write_matched_baseline_rows(conn, rows, start_date=start_date, end_date=end_date)
        candidate_rows = _load_candidate_execution_rows(conn, start_date=start_date, end_date=end_date)
        stats = matched_baseline_stats_from_rows(candidate_rows, rows, dimensions=("signal_kind",))
        by_market_state = matched_baseline_stats_from_rows(candidate_rows, rows, dimensions=("market_state", "signal_kind"))
    finally:
        conn.close()
    report_text = _build_report_text(stats=stats, by_market_state=by_market_state, row_count=len(rows), dry_run=dry_run)
    if not dry_run:
        resolved_report.parent.mkdir(parents=True, exist_ok=True)
        resolved_report.write_text(report_text, encoding="utf-8")
    return {
        "status": "dry_run" if dry_run else ("completed" if inserted else "noop"),
        "duckdb_path": str(path),
        "start_date": start_date,
        "end_date": end_date,
        "sample_size": sample_size,
        "generated_rows": len(rows),
        "inserted_rows": inserted,
        "run_id": run_id,
        "formula_version": FORMULA_VERSION,
        "report_path": str(resolved_report),
        "matched_baseline_stats": stats,
        "matched_baseline_by_market_state": by_market_state,
    }


def matched_baseline_stats_from_rows(
    candidate_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    *,
    dimensions: tuple[str, ...] = ("signal_kind",),
    bootstrap_iterations: int = 1000,
    seed: str = "matched_baseline_stats",
) -> dict[str, Any]:
    candidates_by_key = {
        (
            str(row.get("signal_date") or "")[:10],
            _stock_code({"stock_code": row.get("stock_code") or row.get("candidate_stock_code")}),
            str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        ): row
        for row in candidate_rows
    }
    controls_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in control_rows:
        key = (
            str(row.get("signal_date") or "")[:10],
            _stock_code({"stock_code": row.get("candidate_stock_code")}),
            str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        controls_by_key[key].append(row)

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for key, candidate in candidates_by_key.items():
        controls = controls_by_key.get(key, [])
        if not controls:
            continue
        for horizon in HORIZONS:
            candidate_return = _float_or_none(candidate.get(f"return_{horizon}_net_adj"))
            control_values = [
                value
                for control in controls
                if (value := _float_or_none(control.get(f"control_return_{horizon}_net_adj"))) is not None
            ]
            if candidate_return is None or not control_values:
                continue
            row = {
                "signal_date": key[0],
                "horizon": f"return_{horizon}",
                "paired_alpha": candidate_return - (sum(control_values) / len(control_values)),
                "control_count": len(control_values),
            }
            for dimension in dimensions:
                row[dimension] = _dimension_value(candidate, dimension)
            grouped[tuple(row[dimension] for dimension in dimensions)].append(row)

    return _nest_stats(grouped, dimensions=dimensions, bootstrap_iterations=bootstrap_iterations, seed=seed)


def _nest_stats(
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]],
    *,
    dimensions: tuple[str, ...],
    bootstrap_iterations: int,
    seed: str,
) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for dim_values, rows in sorted(grouped.items()):
        cursor = root
        for value in dim_values:
            cursor = cursor.setdefault(str(value or "unknown"), {})
        for horizon in sorted({str(row["horizon"]) for row in rows}):
            horizon_rows = [row for row in rows if row["horizon"] == horizon]
            values = [float(row["paired_alpha"]) for row in horizon_rows]
            cursor[horizon] = {
                "n": len(values),
                "paired_alpha_avg": round(sum(values) / len(values), 6) if values else None,
                "paired_alpha_median": _median(values),
                "bootstrap_ci_95": _cluster_bootstrap_ci(
                    horizon_rows,
                    iterations=bootstrap_iterations,
                    seed=f"{seed}:{':'.join(map(str, dim_values))}:{horizon}",
                ),
                "avg_control_count": round(sum(float(row["control_count"]) for row in horizon_rows) / len(horizon_rows), 6)
                if horizon_rows
                else None,
            }
    return root


def _cluster_bootstrap_ci(rows: list[dict[str, Any]], *, iterations: int, seed: str) -> dict[str, Any]:
    if not rows:
        return {"low": None, "high": None, "confidence": 0.95, "iterations": iterations}
    by_date: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_date[str(row["signal_date"])].append(float(row["paired_alpha"]))
    dates = sorted(by_date)
    rng = random.Random(_seed_int(seed))
    estimates: list[float] = []
    for _ in range(max(1, iterations)):
        sampled_values: list[float] = []
        for _index in range(len(dates)):
            sampled_values.extend(by_date[rng.choice(dates)])
        estimates.append(sum(sampled_values) / len(sampled_values))
    return {
        "low": _percentile(estimates, 0.025),
        "high": _percentile(estimates, 0.975),
        "confidence": 0.95,
        "iterations": max(1, iterations),
    }


def _load_candidate_execution_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    tables = _table_names(conn)
    if TABLE_EXECUTION_HIST not in tables:
        return []
    hist_join = ""
    hist_columns = "null as sector_code, null as sector_name"
    if TABLE_HIST in tables:
        hist_join = f"""
        left join {TABLE_HIST} h
          on h.snapshot_as_of_date = e.signal_date
         and h.stock_code = e.stock_code
         and coalesce(h.signal_kind, 'stock_candidate') = coalesce(e.signal_kind, 'stock_candidate')
        """
        hist_columns = "h.sector_code, h.sector_name"
    universe_join = ""
    universe_column = "null as stock_name"
    if TABLE_UNIVERSE in tables:
        universe_join = f"""
        left join {TABLE_UNIVERSE} u
          on u.as_of_date = e.signal_date
         and u.stock_code = e.stock_code
        """
        universe_column = "u.stock_name"
    obs_join = ""
    amount_column = "null as amount"
    if TABLE_OBS in tables:
        obs_join = f"""
        left join {TABLE_OBS} o
          on o.trade_date = e.signal_date
         and o.stock_code = e.stock_code
        """
        amount_column = "o.amount"
    where = ["e.entry_executable = true"]
    bindings: list[object] = []
    if start_date:
        where.append("cast(e.signal_date as date) >= cast(? as date)")
        bindings.append(start_date)
    if end_date:
        where.append("cast(e.signal_date as date) <= cast(? as date)")
        bindings.append(end_date)
    rows = conn.execute(
        f"""
        select e.signal_date, e.stock_code, e.signal_kind, e.market_state, e.candidate_rank,
               e.return_1d_net_adj, e.return_5d_net_adj, e.return_10d_net_adj, e.return_20d_net_adj,
               e.run_id, {hist_columns}, {universe_column}, {amount_column}
        from {TABLE_EXECUTION_HIST} e
        {hist_join}
        {universe_join}
        {obs_join}
        where {' and '.join(where)}
        order by e.signal_date asc, e.candidate_rank asc, e.stock_code asc
        """,
        bindings,
    ).fetchall()
    keys = (
        "signal_date",
        "stock_code",
        "signal_kind",
        "market_state",
        "candidate_rank",
        "return_1d_net_adj",
        "return_5d_net_adj",
        "return_10d_net_adj",
        "return_20d_net_adj",
        "run_id",
        "sector_code",
        "sector_name",
        "stock_name",
        "amount",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _load_control_universe_for_date(conn: duckdb.DuckDBPyConnection, signal_date: str) -> list[dict[str, Any]]:
    tables = _table_names(conn)
    if TABLE_OBS not in tables:
        return []
    universe_join = ""
    stock_name_column = "'' as stock_name"
    if TABLE_UNIVERSE in tables:
        universe_join = f"""
        left join {TABLE_UNIVERSE} u
          on u.as_of_date = o.trade_date
         and u.stock_code = o.stock_code
        """
        stock_name_column = "coalesce(u.stock_name, '') as stock_name"
    sector_join = ""
    sector_columns = "'' as sector_code, '' as sector_name"
    if TABLE_SECTOR in tables:
        sector_join = f"""
        left join {TABLE_SECTOR} s
          on s.as_of_date = o.trade_date
         and s.stock_code = o.stock_code
        """
        sector_columns = "coalesce(s.sw2021code, '') as sector_code, coalesce(s.sw2021, '') as sector_name"
    rows = conn.execute(
        f"""
        select o.trade_date, o.stock_code, {stock_name_column}, {sector_columns}, o.amount
        from {TABLE_OBS} o
        {universe_join}
        {sector_join}
        where o.trade_date = ?
        order by o.stock_code asc
        """,
        [signal_date],
    ).fetchall()
    out: list[dict[str, Any]] = []
    for signal_date_raw, stock_code, stock_name, sector_code, sector_name, amount in rows:
        entry = _control_entry_state(conn, stock_code=str(stock_code or ""), signal_date=str(signal_date_raw)[:10])
        out.append(
            {
                "signal_date": str(signal_date_raw)[:10],
                "stock_code": str(stock_code or "").upper(),
                "stock_name": stock_name,
                "sector_code": sector_code,
                "sector_name": sector_name,
                "amount": amount,
                "entry_executable": entry["entry_executable"],
                "entry_block_reason": entry["entry_block_reason"],
            }
        )
    return out


def _control_entry_state(conn: duckdb.DuckDBPyConnection, *, stock_code: str, signal_date: str) -> dict[str, Any]:
    bars = _bars_after_signal(conn, stock_code=stock_code, signal_date=signal_date, limit=1)
    if not bars:
        return {"entry_executable": False, "entry_block_reason": "missing_entry_bar"}
    entry_bar = bars[0]
    entry_price = _entry_price(entry_bar)
    reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    return {"entry_executable": not bool(reason), "entry_block_reason": reason}


def _control_execution_returns(conn: duckdb.DuckDBPyConnection, *, stock_code: str, signal_date: str) -> dict[str, Any]:
    bars = _bars_after_signal(conn, stock_code=stock_code, signal_date=signal_date, limit=30)
    if not bars:
        return {"entry_executable": False}
    entry_bar = bars[0]
    entry_price = _entry_price(entry_bar)
    reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    if reason:
        return {"entry_executable": False}
    entry_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=str(entry_bar["trade_date"])[:10])
    out: dict[str, Any] = {"entry_executable": True}
    for horizon, index in (("1d", 0), ("5d", 4), ("10d", 9), ("20d", 19)):
        exit_bar = _first_sellable_bar_at_or_after(bars, index)
        exit_price = _positive_float(exit_bar.get("close_value") if exit_bar else None)
        exit_factor = _adjustment_factor(
            conn,
            stock_code=stock_code,
            trade_date=str(exit_bar.get("trade_date") if exit_bar else "")[:10],
        )
        gross_adj = adjusted_return(
            start_price=entry_price,
            start_adj_factor=entry_factor,
            end_price=exit_price,
            end_adj_factor=exit_factor,
        )
        out[f"return_{horizon}_net_adj"] = net_return_after_costs(
            gross_adj,
            buy_cost_rate=POLICY.buy_cost_rate,
            sell_cost_rate=POLICY.sell_cost_rate,
            slippage_rate=POLICY.slippage_rate,
        )
    return out


def _bars_after_signal(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    signal_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        select trade_date, open_value, close_value, highlimit, lowlimit, tradestatus
        from {TABLE_OBS}
        where stock_code = ?
          and trade_date > ?
        order by trade_date asc
        limit ?
        """,
        [stock_code, signal_date, limit],
    ).fetchall()
    keys = ("trade_date", "open_value", "close_value", "highlimit", "lowlimit", "tradestatus")
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _adjustment_factor(conn: duckdb.DuckDBPyConnection, *, stock_code: str, trade_date: str) -> float | None:
    if STOCK_ADJUSTMENT_FACTOR_TABLE not in _table_names(conn) or not stock_code or not trade_date:
        return None
    row = conn.execute(
        f"""
        select adj_factor
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where stock_code = ? and trade_date = ? and adj_factor is not null
        order by run_id desc, source_version desc
        limit 1
        """,
        [stock_code, trade_date],
    ).fetchone()
    return _positive_float(row[0]) if row else None


def _entry_price(bar: dict[str, Any]) -> float | None:
    return _positive_float(bar.get("open_value")) or _positive_float(bar.get("close_value"))


def _entry_block_reason(bar: dict[str, Any], *, entry_price: float | None) -> str:
    if entry_price is None:
        return "missing_entry_price"
    if _is_halted(bar):
        return "entry_halted"
    highlimit = _positive_float(bar.get("highlimit"))
    if highlimit is not None and entry_price >= highlimit * 0.999:
        return "entry_limit_up_or_one_line"
    return ""


def _first_sellable_bar_at_or_after(bars: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    for bar in bars[start_index:]:
        if _is_halted(bar) or _is_limit_down(bar):
            continue
        if _positive_float(bar.get("close_value")) is None:
            continue
        return bar
    return None


def _is_halted(bar: dict[str, Any]) -> bool:
    return str(bar.get("tradestatus") or "").strip().lower() in {
        "0",
        "false",
        "halt",
        "halted",
        "suspend",
        "suspended",
        "\u505c\u724c",
    }


def _is_limit_down(bar: dict[str, Any]) -> bool:
    lowlimit = _positive_float(bar.get("lowlimit"))
    close_value = _positive_float(bar.get("close_value"))
    return lowlimit is not None and close_value is not None and close_value <= lowlimit * 1.001


def _sample_rows(rows: list[dict[str, Any]], *, sample_size: int, seed: str, group: str) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: _stock_code(row))
    if len(ordered) > sample_size:
        rng = random.Random(_seed_int(seed))
        ordered = rng.sample(ordered, sample_size)
    return [{**row, "control_group": group} for row in ordered]


def _liquidity_buckets(rows: list[dict[str, Any]], *, bucket_count: int = 5) -> dict[str, int]:
    ordered = sorted(
        [row for row in rows if _float_or_none(row.get("amount")) is not None],
        key=lambda row: (_float_or_none(row.get("amount")) or 0.0, _stock_code(row)),
    )
    total = len(ordered)
    if total == 0:
        return {}
    return {
        _stock_code(row): min(bucket_count - 1, int(index * bucket_count / total))
        for index, row in enumerate(ordered)
    }


def _build_report_text(*, stats: dict[str, Any], by_market_state: dict[str, Any], row_count: int, dry_run: bool) -> str:
    return "\n".join(
        [
            "# 2026-07 Matched Baseline Report",
            "",
            f"- status: {'dry_run' if dry_run else 'completed'}",
            f"- matched_control_rows: {row_count}",
            f"- formula_version: {FORMULA_VERSION}",
            "",
            "## By Signal Kind",
            "```json",
            json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## By Market State And Signal Kind",
            "```json",
            json.dumps(by_market_state, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "Conclusion: signal kinds whose bootstrap interval excludes zero have measurable stock-selection alpha under the matched same-day execution basis.",
        ]
    )


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _stock_code(row: dict[str, Any]) -> str:
    return str(row.get("stock_code") or row.get("candidate_stock_code") or "").strip().upper()


def _sector_key(row: dict[str, Any]) -> str:
    return str(row.get("sector_code") or row.get("industry") or row.get("sector_name") or "").strip()


def _dimension_value(row: dict[str, Any], dimension: str) -> str:
    if dimension == "signal_kind":
        return str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"
    if dimension == "market_state":
        return str(row.get("market_state") or "unknown").strip() or "unknown"
    return str(row.get(dimension) or "unknown").strip() or "unknown"


def _is_st_stock(row: dict[str, Any]) -> bool:
    if _bool_value(row.get("is_st")) is True:
        return True
    raw_name = str(row.get("stock_name") or "").strip().upper()
    compact = raw_name.replace(" ", "")
    return (
        compact.startswith("*ST")
        or raw_name.startswith("ST ")
        or raw_name.startswith("ST*")
        or "\u9000" in compact
    )


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


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value: Any) -> float | None:
    number = _float_or_none(value)
    return number if number is not None and number > 0 else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 6)


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


def _seed_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def _text_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
