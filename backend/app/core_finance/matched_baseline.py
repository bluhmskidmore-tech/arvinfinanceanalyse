from __future__ import annotations

import hashlib
import json
import random
import statistics
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from backend.app.core_finance.adjusted_returns import (
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    adjusted_return,
    net_return_after_costs,
    normalize_duckdb_path,
)
from backend.app.core_finance.choice_stock_units import amount_rmb_sql
from backend.app.core_finance.field_normalization import is_tradestatus_halted
from backend.app.core_finance.portfolio_paths import TABLE_LIMIT_PRICE, resolve_limit_prices
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

MATCHED_BASELINE_TABLE = "livermore_matched_baseline_history"
TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_SECTOR = "choice_stock_sector_membership"
TABLE_UNIVERSE = "choice_stock_universe"
# v2: control_return_*_net_adj now uses multiplicative cost netting
# ((1+r)*(1-c)-1) via adjusted_returns.net_return_after_costs.
# v3: halted 判定统一到共享互补口径（is_tradestatus_halted）——"停牌一天"/
# "连续停牌"等非空非可交易值判停牌，控制组入场/卖出在停牌值日顺延到
# 首个可卖 bar（旧完整匹配词表把这些日误判可交易，卖在停牌陈旧价）。
# v4: resolve numeric limit prices from the shared strategy source before exit checks.
FORMULA_VERSION = "fv_livermore_matched_baseline_v4"
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
    candidates_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        signal_date = str(candidate.get("signal_date") or "")[:10]
        if not signal_date:
            continue
        candidates_by_date[signal_date].append(
            {
                **candidate,
                "run_id": candidate.get("run_id") or resolved_run_id,
                "seed": stable_control_seed(
                    run_id=str(candidate.get("run_id") or resolved_run_id),
                    signal_date=signal_date,
                    candidate_stock_code=str(candidate.get("stock_code") or ""),
                ),
            }
        )

    universe_by_date = _load_control_universes_for_dates(conn, list(candidates_by_date))
    rows: list[dict[str, Any]] = []
    for signal_date, date_candidates in candidates_by_date.items():
        universe_rows = universe_by_date.get(signal_date, [])
        planned_controls: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        control_codes: set[str] = set()
        for candidate in date_candidates:
            controls = select_matched_controls(candidate, universe_rows, sample_size=sample_size)
            planned_controls.append((candidate, controls))
            control_codes.update(_stock_code(control) for control in controls)
        returns_by_code = _load_control_execution_returns_for_date(
            conn,
            stock_codes=sorted(control_codes),
            signal_date=signal_date,
        )
        for candidate, controls in planned_controls:
            for control in controls:
                returns = returns_by_code.get(_stock_code(control), {"entry_executable": False})
                rows.append(
                    {
                        "signal_date": signal_date,
                        "candidate_stock_code": _stock_code(candidate),
                        "signal_kind": str(candidate.get("signal_kind") or "stock_candidate").strip()
                        or "stock_candidate",
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


def generate_matched_baseline_pit_proof_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    candidate_rows: list[dict[str, Any]],
    evaluation_as_of_date: str,
    source_availability_receipt: dict[str, Any] | None = None,
    sample_size: int = CONTROL_SAMPLE_SIZE,
) -> list[dict[str, Any]]:
    evaluation = _parse_strict_iso_date(
        evaluation_as_of_date,
        field_name="evaluation_as_of_date",
    ).isoformat()
    source_availability_index = _normalize_source_availability_receipt(source_availability_receipt)
    candidates_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidate_rows:
        signal_date_text = _candidate_signal_date_text(candidate)
        signal_date = _parse_strict_iso_date(
            signal_date_text,
            field_name="candidate.signal_date",
        ).isoformat()
        if signal_date > evaluation:
            raise ValueError("candidate.signal_date must be on or before evaluation_as_of_date.")
        normalized = {
            **candidate,
            "signal_date": signal_date,
            "signal_kind": str(candidate.get("signal_kind") or "stock_candidate").strip()
            or "stock_candidate",
            "seed": candidate.get("seed")
            or stable_control_seed(
                run_id=_text_or_none(candidate.get("run_id")),
                signal_date=signal_date,
                candidate_stock_code=str(candidate.get("stock_code") or ""),
            ),
        }
        candidates_by_date[signal_date].append(normalized)

    universe_by_date = _load_control_universes_for_dates_pit_proof(
        conn,
        list(candidates_by_date),
        evaluation_as_of_date=evaluation,
        source_availability_index=source_availability_index,
    )
    rows: list[dict[str, Any]] = []
    for signal_date, date_candidates in candidates_by_date.items():
        universe_rows = universe_by_date.get(signal_date, [])
        for candidate in date_candidates:
            controls = select_matched_controls(candidate, universe_rows, sample_size=sample_size)
            for control in controls:
                proof = _control_execution_pit_proof(
                    conn,
                    stock_code=_stock_code(control),
                    signal_date=signal_date,
                    evaluation_as_of_date=evaluation,
                    source_availability_index=source_availability_index,
                )
                rows.append(
                    {
                        "signal_date": signal_date,
                        "candidate_stock_code": _stock_code(candidate),
                        "signal_kind": str(candidate.get("signal_kind") or "stock_candidate").strip()
                        or "stock_candidate",
                        "control_stock_code": _stock_code(control),
                        "control_group": control.get("control_group"),
                        "seed": candidate["seed"],
                        "evaluation_as_of_date": evaluation,
                        "control_entry_date": proof["entry"]["trade_date"],
                        "control_entry_price": proof["entry"]["price"],
                        "control_entry_price_kind": proof["entry"]["price_kind"],
                        "control_entry_executable": proof["entry"]["executable"],
                        "control_entry_usable": proof["entry"]["usable"],
                        "control_entry_failure_reason": proof["entry"]["failure_reason"],
                        "control_exit_date_5d": proof["horizons"]["5d"]["trade_date"],
                        "control_exit_price_5d": proof["horizons"]["5d"]["price"],
                        "control_exit_price_kind_5d": proof["horizons"]["5d"]["price_kind"],
                        "control_return_5d_net_adj": proof["horizons"]["5d"]["net_adj_return"],
                        "control_return_5d_usable": proof["horizons"]["5d"]["usable"],
                        "control_failure_reason_5d": proof["horizons"]["5d"]["failure_reason"],
                        "control_exit_date_20d": proof["horizons"]["20d"]["trade_date"],
                        "control_exit_price_20d": proof["horizons"]["20d"]["price"],
                        "control_exit_price_kind_20d": proof["horizons"]["20d"]["price_kind"],
                        "control_return_20d_net_adj": proof["horizons"]["20d"]["net_adj_return"],
                        "control_return_20d_usable": proof["horizons"]["20d"]["usable"],
                        "control_failure_reason_20d": proof["horizons"]["20d"]["failure_reason"],
                        "control_failure_reason": proof["failure_reason"],
                        "price_adjustment_mode": "adj_factor_ratio",
                        "buy_cost_bps": round(POLICY.buy_cost_rate * 10_000, 6),
                        "sell_cost_bps": round(POLICY.sell_cost_rate * 10_000, 6),
                        "slippage_bps": round(POLICY.slippage_rate * 10_000, 6),
                        "metric_basis": "net_next_open_adj",
                        "formula_version": FORMULA_VERSION,
                        "source_evidence": proof["source_evidence"],
                    }
                )
    return rows


def summarize_matched_baseline_pit_proof_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique_candidate_entry_keys = {
        (
            str(row.get("signal_date") or ""),
            str(row.get("candidate_stock_code") or ""),
            str(row.get("signal_kind") or ""),
        )
        for row in rows
        if bool(row.get("control_entry_usable"))
    }
    return {
        "unique_candidate_keys_with_any_usable_control_entry_count": len(unique_candidate_entry_keys),
        "control_row_count": len(rows),
        "usable_control_row_count_5d": sum(bool(row.get("control_return_5d_usable")) for row in rows),
        "usable_control_row_count_20d": sum(bool(row.get("control_return_20d_usable")) for row in rows),
    }


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
        amount_column = (
            amount_rmb_sql(table_alias="o", alias="amount")
            if "vendor_version" in _table_columns(conn, TABLE_OBS)
            else "cast(null as double) as amount"
        )
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
    # The execution/history sources may contain replay duplicates. Preserve one
    # deterministic row per baseline candidate grain before sampling controls;
    # otherwise a duplicated candidate multiplies every selected control row.
    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_row in rows:
        item = dict(zip(keys, raw_row, strict=True))
        key = (
            str(item.get("signal_date") or "")[:10],
            _stock_code(item),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        current = deduplicated.get(key)
        if current is None or _candidate_execution_priority(item) > _candidate_execution_priority(current):
            deduplicated[key] = item
    return list(deduplicated.values())


def _candidate_execution_priority(row: dict[str, Any]) -> tuple[int, int, str]:
    populated_returns = sum(
        row.get(field) is not None
        for field in (
            "return_1d_net_adj",
            "return_5d_net_adj",
            "return_10d_net_adj",
            "return_20d_net_adj",
        )
    )
    try:
        rank_priority = -int(row.get("candidate_rank") or 999_999)
    except (TypeError, ValueError):
        rank_priority = -999_999
    return populated_returns, rank_priority, str(row.get("run_id") or "")


def _load_control_universes_for_dates(
    conn: duckdb.DuckDBPyConnection,
    signal_dates: list[str],
) -> dict[str, list[dict[str, Any]]]:
    resolved_dates = sorted({str(value or "")[:10] for value in signal_dates if str(value or "")[:10]})
    tables = _table_names(conn)
    if not resolved_dates or TABLE_OBS not in tables:
        return {}
    amount_column = (
        amount_rmb_sql(table_alias="raw", alias="amount")
        if "vendor_version" in _table_columns(conn, TABLE_OBS)
        else "cast(null as double) as amount"
    )
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
        with observation_with_entry as (
          select raw.trade_date, raw.stock_code, {amount_column},
                 lead(raw.trade_date) over observation_order as entry_trade_date,
                 lead(raw.open_value) over observation_order as entry_open_value,
                 lead(raw.close_value) over observation_order as entry_close_value,
                 lead(raw.highlimit) over observation_order as entry_highlimit,
                 lead(raw.lowlimit) over observation_order as entry_lowlimit,
                 lead(raw.tradestatus) over observation_order as entry_tradestatus
          from {TABLE_OBS} raw
          window observation_order as (partition by raw.stock_code order by raw.trade_date asc)
        )
        select o.trade_date, o.stock_code, {stock_name_column}, {sector_columns}, o.amount,
               o.entry_trade_date, o.entry_open_value, o.entry_close_value,
               o.entry_highlimit, o.entry_lowlimit, o.entry_tradestatus
        from observation_with_entry o
        {universe_join}
        {sector_join}
        where cast(o.trade_date as date) in (select cast(unnest(?) as date))
        order by o.trade_date asc, o.stock_code asc
        """,
        [resolved_dates],
    ).fetchall()
    entry_bars: dict[int, dict[str, Any]] = {}
    bars_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    entry_keys = ("trade_date", "open_value", "close_value", "highlimit", "lowlimit", "tradestatus")
    for row_number, row in enumerate(rows):
        if row[6] is not None:
            bar = dict(zip(entry_keys, row[6:], strict=True))
            entry_bars[row_number] = bar
            bars_by_code[str(row[1] or "")].append(bar)
    _attach_limit_prices(conn, bars_by_code)
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row_number, row in enumerate(rows):
        signal_date_raw, stock_code, stock_name, sector_code, sector_name, amount = row[:6]
        entry_bar = entry_bars.get(row_number)
        if entry_bar is None:
            entry = {"entry_executable": False, "entry_block_reason": "missing_entry_bar"}
        else:
            entry_price = _entry_price(entry_bar)
            reason = _entry_block_reason(entry_bar, entry_price=entry_price)
            entry = {"entry_executable": not bool(reason), "entry_block_reason": reason}
        signal_date = str(signal_date_raw)[:10]
        out[signal_date].append(
            {
                "signal_date": signal_date,
                "stock_code": str(stock_code or "").upper(),
                "stock_name": stock_name,
                "sector_code": sector_code,
                "sector_name": sector_name,
                "amount": amount,
                "entry_executable": entry["entry_executable"],
                "entry_block_reason": entry["entry_block_reason"],
            }
        )
    return dict(out)


def _load_control_universe_for_date(conn: duckdb.DuckDBPyConnection, signal_date: str) -> list[dict[str, Any]]:
    tables = _table_names(conn)
    if TABLE_OBS not in tables:
        return []
    amount_column = (
        amount_rmb_sql(table_alias="o", alias="amount")
        if "vendor_version" in _table_columns(conn, TABLE_OBS)
        else "cast(null as double) as amount"
    )
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
        select o.trade_date, o.stock_code, {stock_name_column}, {sector_columns}, {amount_column}
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


def _load_control_universes_for_dates_pit_proof(
    conn: duckdb.DuckDBPyConnection,
    signal_dates: list[str],
    *,
    evaluation_as_of_date: str,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
) -> dict[str, list[dict[str, Any]]]:
    resolved_dates = sorted({str(value or "")[:10] for value in signal_dates if str(value or "")[:10]})
    tables = _table_names(conn)
    if not resolved_dates or TABLE_OBS not in tables:
        return {}
    amount_column = (
        amount_rmb_sql(table_alias="o", alias="amount")
        if "vendor_version" in _table_columns(conn, TABLE_OBS)
        else "cast(null as double) as amount"
    )
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
        select o.trade_date, o.stock_code, {stock_name_column}, {sector_columns}, {amount_column}
        from {TABLE_OBS} o
        {universe_join}
        {sector_join}
        where cast(o.trade_date as date) in (select cast(unnest(?) as date))
        order by o.trade_date asc, o.stock_code asc
        """,
        [resolved_dates],
    ).fetchall()
    duplicate_keys = sorted(
        {
            (str(signal_date_raw)[:10], str(stock_code or "").upper())
            for signal_date_raw, stock_code, *_rest in rows
            if sum(
                1
                for inner_signal_date_raw, inner_stock_code, *_ignored in rows
                if str(inner_signal_date_raw)[:10] == str(signal_date_raw)[:10]
                and str(inner_stock_code or "").upper() == str(stock_code or "").upper()
            ) > 1
        }
    )
    if duplicate_keys:
        preview = ", ".join(f"{signal_date}:{stock_code}" for signal_date, stock_code in duplicate_keys[:5])
        raise ValueError(f"PIT control universe contains duplicate logical keys: {preview}")
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal_date_raw, stock_code, stock_name, sector_code, sector_name, amount in rows:
        signal_date = str(signal_date_raw)[:10]
        entry = _control_entry_state_pit_proof(
            conn,
            stock_code=str(stock_code or ""),
            signal_date=signal_date,
            evaluation_as_of_date=evaluation_as_of_date,
            source_availability_index=source_availability_index,
        )
        out[signal_date].append(
            {
                "signal_date": signal_date,
                "stock_code": str(stock_code or "").upper(),
                "stock_name": stock_name,
                "sector_code": sector_code,
                "sector_name": sector_name,
                "amount": amount,
                "entry_executable": entry["entry_executable"],
                "entry_block_reason": entry["entry_block_reason"],
            }
        )
    return dict(out)


def _control_entry_state(conn: duckdb.DuckDBPyConnection, *, stock_code: str, signal_date: str) -> dict[str, Any]:
    bars = _bars_after_signal(conn, stock_code=stock_code, signal_date=signal_date, limit=1)
    if not bars:
        return {"entry_executable": False, "entry_block_reason": "missing_entry_bar"}
    entry_bar = bars[0]
    entry_price = _entry_price(entry_bar)
    reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    return {"entry_executable": not bool(reason), "entry_block_reason": reason}


def _control_entry_state_pit_proof(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    signal_date: str,
    evaluation_as_of_date: str,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
) -> dict[str, Any]:
    bars = _bars_after_signal_until_evaluation(
        conn,
        stock_code=stock_code,
        signal_date=signal_date,
        evaluation_as_of_date=evaluation_as_of_date,
        source_availability_index=source_availability_index,
        prefer_proven_available_source=False,
        limit=1,
    )
    if not bars:
        return {"entry_executable": False, "entry_block_reason": "missing_entry_bar"}
    entry_bar = bars[0]
    entry_price, _ = _next_open_entry_price_with_kind(entry_bar)
    reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    return {"entry_executable": not bool(reason), "entry_block_reason": reason}


def _load_control_execution_returns_for_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_codes: list[str],
    signal_date: str,
) -> dict[str, dict[str, Any]]:
    resolved_codes = sorted({str(value or "").strip().upper() for value in stock_codes if str(value or "").strip()})
    tables = _table_names(conn)
    if not resolved_codes or TABLE_OBS not in tables:
        return {}
    factor_cte = ""
    factor_join = ""
    factor_column = "null as adj_factor"
    if STOCK_ADJUSTMENT_FACTOR_TABLE in tables:
        factor_cte = f""",
        latest_factors as (
          select af.stock_code, af.trade_date, af.adj_factor,
                 row_number() over (
                   partition by af.stock_code, af.trade_date
                   order by af.run_id desc, af.source_version desc
                 ) as factor_number
          from {STOCK_ADJUSTMENT_FACTOR_TABLE} af
          inner join requested_codes c on c.stock_code = af.stock_code
          where af.adj_factor is not null
          qualify factor_number = 1
        )
        """
        factor_join = """
        left join latest_factors f
          on f.stock_code = b.stock_code
         and f.trade_date = b.trade_date
        """
        factor_column = "f.adj_factor"
    rows = conn.execute(
        f"""
        with requested_codes(stock_code) as (select unnest(?)),
        ranked_bars as (
          select o.stock_code, o.trade_date, o.open_value, o.close_value,
                 o.highlimit, o.lowlimit, o.tradestatus,
                 row_number() over (partition by o.stock_code order by o.trade_date asc) as bar_number
          from {TABLE_OBS} o
          inner join requested_codes c on c.stock_code = o.stock_code
          where o.trade_date > ?
          qualify bar_number <= 30
        )
        {factor_cte}
        select b.stock_code, b.trade_date, b.open_value, b.close_value,
               b.highlimit, b.lowlimit, b.tradestatus, {factor_column}
        from ranked_bars b
        {factor_join}
        order by b.stock_code asc, b.trade_date asc
        """,
        [resolved_codes, signal_date],
    ).fetchall()
    bars_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    factors_by_code: dict[str, dict[str, float | None]] = defaultdict(dict)
    for stock_code, trade_date, open_value, close_value, highlimit, lowlimit, tradestatus, adj_factor in rows:
        code = str(stock_code or "").strip().upper()
        date = str(trade_date or "")[:10]
        bars_by_code[code].append(
            {
                "trade_date": trade_date,
                "open_value": open_value,
                "close_value": close_value,
                "highlimit": highlimit,
                "lowlimit": lowlimit,
                "tradestatus": tradestatus,
            }
        )
        factors_by_code[code][date] = _positive_float(adj_factor)
    _attach_limit_prices(conn, bars_by_code)
    return {
        code: _control_execution_returns_from_bars(
            bars_by_code.get(code, []),
            adjustment_factor_for_date=factors_by_code.get(code, {}).get,
        )
        for code in resolved_codes
    }


def _control_execution_returns(conn: duckdb.DuckDBPyConnection, *, stock_code: str, signal_date: str) -> dict[str, Any]:
    bars = _bars_after_signal(conn, stock_code=stock_code, signal_date=signal_date, limit=30)
    return _control_execution_returns_from_bars(
        bars,
        adjustment_factor_for_date=lambda trade_date: _adjustment_factor(
            conn,
            stock_code=stock_code,
            trade_date=trade_date,
        ),
    )


def _control_execution_pit_proof(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    signal_date: str,
    evaluation_as_of_date: str,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
) -> dict[str, Any]:
    bars = _bars_after_signal_until_evaluation(
        conn,
        stock_code=stock_code,
        signal_date=signal_date,
        evaluation_as_of_date=evaluation_as_of_date,
        source_availability_index=source_availability_index,
        prefer_proven_available_source=True,
        limit=30,
    )
    evaluation = str(evaluation_as_of_date or "")[:10]
    if not bars:
        return {
            "entry": {
                "trade_date": None,
                "price": None,
                "price_kind": None,
                "executable": False,
                "usable": False,
                "failure_reason": "missing_entry_bar",
            },
            "horizons": {
                horizon: {
                    "trade_date": None,
                    "price": None,
                    "price_kind": None,
                    "net_adj_return": None,
                    "usable": False,
                    "failure_reason": "missing_entry_bar",
                }
                for horizon in ("5d", "20d")
            },
            "failure_reason": "missing_entry_bar",
            "source_evidence": {
                "observation": {"table": TABLE_OBS, "vendor": None, "rule": None, "run": None},
                "adjustment_factor": {
                    "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
                    "vendor": None,
                    "rule": None,
                    "run": None,
                },
            },
        }
    entry_bar = bars[0]
    entry_price, entry_price_kind = _next_open_entry_price_with_kind(entry_bar)
    entry_block_reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    entry_factor = _adjustment_factor_with_source(
        conn,
        stock_code=stock_code,
        trade_date=str(entry_bar["trade_date"])[:10],
        evaluation_as_of_date=evaluation_as_of_date,
        source_availability_index=source_availability_index,
    )
    entry_observation_source = _source_with_availability(
        table=TABLE_OBS,
        source=_bar_source_evidence(entry_bar, prefix="obs_"),
        source_availability_index=source_availability_index,
        evaluation_as_of_date=evaluation_as_of_date,
    )
    entry_factor_source = entry_factor["source"]
    source_evidence = {
        "limit_price": {
            "table": TABLE_LIMIT_PRICE,
            "entry": entry_bar.get("limit_price_evidence"),
            "entry_source": entry_bar.get("limit_price_source"),
        },
        "observation": {
            "table": TABLE_OBS,
            "vendor": _source_field(entry_bar, "obs_vendor_version"),
            "rule": _source_field(entry_bar, "obs_rule_version"),
            "run": _source_field(entry_bar, "obs_run_id"),
            "entry": entry_observation_source,
        },
        "adjustment_factor": {
            "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
            "vendor": _source_field(entry_factor, "vendor_version"),
            "rule": _source_field(entry_factor, "rule_version"),
            "run": _source_field(entry_factor, "run_id"),
            "entry": entry_factor_source,
        },
    }
    horizons: dict[str, dict[str, Any]] = {}
    entry_failure_reason = (
        entry_block_reason
        or ("missing_entry_adjustment_factor" if entry_factor["adj_factor"] is None else "")
        or _source_failure_reason(
            entry_observation_source,
            missing_reason="missing_entry_observation_source_metadata",
            unproven_reason="entry_observation_source_availability_unproven",
            future_reason="entry_observation_source_available_after_evaluation",
        )
        or _source_failure_reason(
            entry_factor_source,
            missing_reason="missing_entry_adjustment_factor_source_metadata",
            unproven_reason="entry_adjustment_factor_source_availability_unproven",
            future_reason="entry_adjustment_factor_source_available_after_evaluation",
        )
        or None
    )
    entry_usable = entry_failure_reason is None
    for horizon, index in (("5d", 4), ("20d", 19)):
        exit_bar = _first_sellable_bar_at_or_after(bars, index)
        if not entry_usable:
            horizons[horizon] = {
                "trade_date": None,
                "price": None,
                "price_kind": None,
                "net_adj_return": None,
                "usable": False,
                "failure_reason": entry_failure_reason,
            }
            continue
        exit_decisions: list[dict[str, Any]] = []
        decision_failure_reason = None
        for decision_bar in bars[index:]:
            if _is_halted(decision_bar):
                decision = "halted"
            elif _is_limit_down(decision_bar):
                decision = "limit_down"
            elif _positive_float(decision_bar.get("close_value")) is None:
                decision = "missing_close"
            else:
                decision = "sellable"
            decision_observation_source = _source_with_availability(
                table=TABLE_OBS,
                source=_bar_source_evidence(decision_bar, prefix="obs_"),
                source_availability_index=source_availability_index,
                evaluation_as_of_date=evaluation_as_of_date,
            )
            if decision_bar is not exit_bar:
                decision_failure_reason = decision_failure_reason or _source_failure_reason(
                    decision_observation_source,
                    missing_reason="missing_exit_decision_observation_source_metadata",
                    unproven_reason="exit_decision_observation_source_availability_unproven",
                    future_reason="exit_decision_observation_source_available_after_evaluation",
                )
            exit_decisions.append(
                {
                    "trade_date": str(decision_bar["trade_date"])[:10],
                    "decision": decision,
                    "close_value": decision_bar.get("close_value"),
                    "up_limit": decision_bar.get("highlimit"),
                    "down_limit": decision_bar.get("lowlimit"),
                    "limit_down_flag": bool(decision_bar.get("limit_down_flag")),
                    "limit_price_source": decision_bar.get("limit_price_source"),
                    "source": decision_bar.get("limit_price_evidence"),
                    "observation": decision_observation_source,
                }
            )
            if decision_bar is exit_bar:
                break
        source_evidence["limit_price"][f"exit_{horizon}_decisions"] = exit_decisions
        if exit_bar is None:
            horizons[horizon] = {
                "trade_date": None,
                "price": None,
                "price_kind": None,
                "net_adj_return": None,
                "usable": False,
                "failure_reason": decision_failure_reason or "exit_horizon_unreached_by_evaluation",
            }
            continue
        exit_date = str(exit_bar["trade_date"])[:10]
        source_evidence["limit_price"][f"exit_{horizon}"] = exit_bar.get("limit_price_evidence")
        source_evidence["limit_price"][f"exit_{horizon}_source"] = exit_bar.get("limit_price_source")
        if exit_date > evaluation:
            horizons[horizon] = {
                "trade_date": exit_date,
                "price": None,
                "price_kind": None,
                "net_adj_return": None,
                "usable": False,
                "failure_reason": "exit_after_evaluation_date",
            }
            continue
        exit_observation_source = _source_with_availability(
            table=TABLE_OBS,
            source=_bar_source_evidence(exit_bar, prefix="obs_"),
            source_availability_index=source_availability_index,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        exit_factor = _adjustment_factor_with_source(
            conn,
            stock_code=stock_code,
            trade_date=exit_date,
            evaluation_as_of_date=evaluation_as_of_date,
            source_availability_index=source_availability_index,
        )
        source_evidence["observation"][f"exit_{horizon}"] = exit_observation_source
        source_evidence["adjustment_factor"][f"exit_{horizon}"] = exit_factor["source"]
        exit_price = _positive_float(exit_bar.get("close_value"))
        failure_reason = decision_failure_reason
        if exit_price is None:
            failure_reason = "missing_exit_price"
        elif exit_factor["adj_factor"] is None:
            failure_reason = "missing_exit_adjustment_factor"
        elif failure_reason is None:
            failure_reason = _source_failure_reason(
                exit_observation_source,
                missing_reason="missing_exit_observation_source_metadata",
                unproven_reason="exit_observation_source_availability_unproven",
                future_reason="exit_observation_source_available_after_evaluation",
            ) or _source_failure_reason(
                exit_factor["source"],
                missing_reason="missing_exit_adjustment_factor_source_metadata",
                unproven_reason="exit_adjustment_factor_source_availability_unproven",
                future_reason="exit_adjustment_factor_source_available_after_evaluation",
            )
        net_adj_return = None
        if failure_reason is None:
            gross_adj = adjusted_return(
                start_price=entry_price,
                start_adj_factor=entry_factor["adj_factor"],
                end_price=exit_price,
                end_adj_factor=exit_factor["adj_factor"],
            )
            net_adj_return = net_return_after_costs(
                gross_adj,
                buy_cost_rate=POLICY.buy_cost_rate,
                sell_cost_rate=POLICY.sell_cost_rate,
                slippage_rate=POLICY.slippage_rate,
            )
        horizons[horizon] = {
            "trade_date": exit_date,
            "price": exit_price,
            "price_kind": "close_sellable" if exit_price is not None else None,
            "net_adj_return": net_adj_return,
            "usable": failure_reason is None,
            "failure_reason": failure_reason,
        }
    failure_reason = (
        entry_failure_reason
        or horizons["20d"]["failure_reason"]
        or horizons["5d"]["failure_reason"]
    )
    return {
        "entry": {
            "trade_date": str(entry_bar["trade_date"])[:10],
            "price": entry_price,
            "price_kind": entry_price_kind,
            "executable": not bool(entry_block_reason),
            "usable": entry_usable,
            "failure_reason": entry_failure_reason,
        },
        "horizons": horizons,
        "failure_reason": failure_reason,
        "source_evidence": source_evidence,
    }


def _control_execution_returns_from_bars(
    bars: list[dict[str, Any]],
    *,
    adjustment_factor_for_date: Callable[[str], float | None],
) -> dict[str, Any]:
    if not bars:
        return {"entry_executable": False}
    entry_bar = bars[0]
    entry_price = _entry_price(entry_bar)
    reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    if reason:
        return {"entry_executable": False}
    entry_factor = adjustment_factor_for_date(str(entry_bar["trade_date"])[:10])
    out: dict[str, Any] = {"entry_executable": True}
    for horizon, index in (("1d", 0), ("5d", 4), ("10d", 9), ("20d", 19)):
        exit_bar = _first_sellable_bar_at_or_after(bars, index)
        exit_price = _positive_float(exit_bar.get("close_value") if exit_bar else None)
        exit_factor = adjustment_factor_for_date(str(exit_bar.get("trade_date") if exit_bar else "")[:10])
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
    bars = [dict(zip(keys, row, strict=True)) for row in rows]
    _attach_limit_prices(conn, {stock_code: bars})
    return bars


def _bars_after_signal_until_evaluation(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    signal_date: str,
    evaluation_as_of_date: str,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
    prefer_proven_available_source: bool,
    limit: int,
) -> list[dict[str, Any]]:
    observation_columns = _table_columns(conn, TABLE_OBS)
    source_version_expr = (
        "source_version as obs_source_version"
        if "source_version" in observation_columns
        else "cast(null as varchar) as obs_source_version"
    )
    vendor_version_expr = (
        "vendor_version as obs_vendor_version"
        if "vendor_version" in observation_columns
        else "cast(null as varchar) as obs_vendor_version"
    )
    rule_version_expr = (
        "rule_version as obs_rule_version"
        if "rule_version" in observation_columns
        else "cast(null as varchar) as obs_rule_version"
    )
    run_id_expr = (
        "run_id as obs_run_id"
        if "run_id" in observation_columns
        else "cast(null as varchar) as obs_run_id"
    )
    rows = conn.execute(
        f"""
        select trade_date, open_value, close_value, highlimit, lowlimit, tradestatus,
               {source_version_expr}, {vendor_version_expr}, {rule_version_expr}, {run_id_expr}
        from {TABLE_OBS}
        where stock_code = ?
          and trade_date > ?
          and trade_date <= ?
        order by trade_date asc, obs_run_id desc, obs_source_version desc
        """,
        [stock_code, signal_date, evaluation_as_of_date],
    ).fetchall()
    keys = (
        "trade_date",
        "open_value",
        "close_value",
        "highlimit",
        "lowlimit",
        "tradestatus",
        "obs_source_version",
        "obs_vendor_version",
        "obs_rule_version",
        "obs_run_id",
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        item = dict(zip(keys, row, strict=True))
        grouped[str(item["trade_date"])[:10]].append(
            _row_with_source_availability(
                item,
                source_availability_index=source_availability_index,
                evaluation_as_of_date=evaluation_as_of_date,
            )
        )
    selected: list[dict[str, Any]] = []
    for trade_date in sorted(grouped):
        candidates = grouped[trade_date]
        selected.append(
            _select_pit_observation_row(
                candidates,
                prefer_proven_available_source=prefer_proven_available_source,
            )
        )
        if len(selected) >= limit:
            break
    _attach_limit_prices(
        conn, {stock_code: selected}, source_availability_index=source_availability_index,
        evaluation_as_of_date=evaluation_as_of_date,
    )
    return selected


def _attach_limit_prices(
    conn: duckdb.DuckDBPyConnection,
    bars_by_code: dict[str, list[dict[str, Any]]],
    *,
    source_availability_index: dict | None = None,
    evaluation_as_of_date: str | None = None,
) -> None:
    """Use the strategy path's numeric-price source, never interpret native flags as yuan."""
    prices: dict[tuple[str, str], dict[str, Any]] = {}
    if TABLE_LIMIT_PRICE in _table_names(conn) and bars_by_code:
        columns = _table_columns(conn, TABLE_LIMIT_PRICE)
        metadata = [f"{name}" if name in columns else f"cast(null as varchar) as {name}"
                    for name in ("source_version", "vendor_version", "rule_version", "run_id")]
        dates = sorted({str(bar["trade_date"])[:10] for bars in bars_by_code.values() for bar in bars})
        rows = conn.execute(
            f"""select stock_code, trade_date, up_limit, down_limit, {', '.join(metadata)}
                from {TABLE_LIMIT_PRICE}
                where stock_code = any(?) and cast(trade_date as varchar) = any(?)
                order by run_id desc, source_version desc""", [list(bars_by_code), dates],
        ).fetchall()
        for code, trade_date, high, low, source_version, vendor, rule, run in rows:
            key = (str(code), str(trade_date)[:10])
            source = _factor_source_evidence(source_version, vendor, rule, run)
            if source_availability_index is not None:
                source = _source_with_availability(
                    table=TABLE_LIMIT_PRICE, source=source,
                    source_availability_index=source_availability_index,
                    evaluation_as_of_date=evaluation_as_of_date or "",
                )
                if source.get("availability_status") != "available":
                    continue
            if key not in prices:
                prices[key] = {"up_limit": high, "down_limit": low, "source": source}
    for code, bars in bars_by_code.items():
        for bar in bars:
            table = prices.get((code, str(bar["trade_date"])[:10]), {})
            flags = _has_binary_limit_flags(bar)
            high, low, limit_source = resolve_limit_prices(
                observation_highlimit=None if flags else bar.get("highlimit"),
                observation_lowlimit=None if flags else bar.get("lowlimit"),
                table_up_limit=table.get("up_limit"), table_down_limit=table.get("down_limit"),
            )
            bar["limit_up_flag"] = flags and _float_or_none(bar.get("highlimit")) == 1 and limit_source != "stk_limit"
            bar["limit_down_flag"] = flags and _float_or_none(bar.get("lowlimit")) == 1 and limit_source != "stk_limit"
            bar["highlimit"], bar["lowlimit"] = high, low
            bar["limit_price_source"] = limit_source
            if limit_source == "stk_limit":
                bar["limit_price_evidence"] = table.get("source")


def _has_binary_limit_flags(bar: dict[str, Any]) -> bool:
    return all(_float_or_none(bar.get(key)) in (0.0, 1.0) for key in ("highlimit", "lowlimit"))


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


def _adjustment_factor_with_source(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    trade_date: str,
    evaluation_as_of_date: str,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
) -> dict[str, Any]:
    if STOCK_ADJUSTMENT_FACTOR_TABLE not in _table_names(conn) or not stock_code or not trade_date:
        empty_source = _source_with_availability(
            table=STOCK_ADJUSTMENT_FACTOR_TABLE,
            source=_factor_source_evidence(None, None, None, None),
            source_availability_index=source_availability_index,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        return {"adj_factor": None, "source": empty_source}
    factor_columns = _table_columns(conn, STOCK_ADJUSTMENT_FACTOR_TABLE)
    source_version_expr = (
        "source_version as source_version"
        if "source_version" in factor_columns
        else "cast(null as varchar) as source_version"
    )
    vendor_version_expr = (
        "vendor_version as vendor_version"
        if "vendor_version" in factor_columns
        else "cast(null as varchar) as vendor_version"
    )
    rule_version_expr = (
        "rule_version as rule_version"
        if "rule_version" in factor_columns
        else "cast(null as varchar) as rule_version"
    )
    run_id_expr = (
        "run_id as run_id"
        if "run_id" in factor_columns
        else "cast(null as varchar) as run_id"
    )
    rows = conn.execute(
        f"""
        select adj_factor, {source_version_expr}, {vendor_version_expr}, {rule_version_expr}, {run_id_expr}
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where stock_code = ? and trade_date = ? and adj_factor is not null
        order by run_id desc, source_version desc
        """,
        [stock_code, trade_date],
    ).fetchall()
    if not rows:
        empty_source = _source_with_availability(
            table=STOCK_ADJUSTMENT_FACTOR_TABLE,
            source=_factor_source_evidence(None, None, None, None),
            source_availability_index=source_availability_index,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        return {
            "adj_factor": None,
            "source": empty_source,
            "source_version": None,
            "vendor_version": None,
            "rule_version": None,
            "run_id": None,
        }
    selected: tuple[Any, ...] | None = None
    selected_source: dict[str, Any] | None = None
    fallback_row = rows[0]
    fallback_source = _source_with_availability(
        table=STOCK_ADJUSTMENT_FACTOR_TABLE,
        source=_factor_source_evidence(
            fallback_row[1],
            fallback_row[2],
            fallback_row[3],
            fallback_row[4],
        ),
        source_availability_index=source_availability_index,
        evaluation_as_of_date=evaluation_as_of_date,
    )
    for row in rows:
        candidate_source = _source_with_availability(
            table=STOCK_ADJUSTMENT_FACTOR_TABLE,
            source=_factor_source_evidence(row[1], row[2], row[3], row[4]),
            source_availability_index=source_availability_index,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        if str(candidate_source.get("availability_status") or "") == "available":
            selected = row
            selected_source = candidate_source
            break
    row = selected or fallback_row
    source = selected_source or fallback_source
    return {
        "adj_factor": _positive_float(row[0]),
        "source": source,
        "source_version": _text_or_none(row[1]),
        "vendor_version": _text_or_none(row[2]),
        "rule_version": _text_or_none(row[3]),
        "run_id": _text_or_none(row[4]),
    }


def _entry_price(bar: dict[str, Any]) -> float | None:
    return _positive_float(bar.get("open_value")) or _positive_float(bar.get("close_value"))


def _next_open_entry_price_with_kind(bar: dict[str, Any]) -> tuple[float | None, str | None]:
    open_price = _positive_float(bar.get("open_value"))
    if open_price is not None:
        return open_price, "open"
    return None, None


def _entry_block_reason(bar: dict[str, Any], *, entry_price: float | None) -> str:
    if entry_price is None:
        return "missing_entry_price"
    if _is_halted(bar):
        return "entry_halted"
    if bar.get("limit_up_flag") or (_has_binary_limit_flags(bar) and _float_or_none(bar.get("highlimit")) == 1):
        return "entry_limit_up_or_one_line"
    if _has_binary_limit_flags(bar):
        return ""
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
    return is_tradestatus_halted(bar.get("tradestatus"))


def _is_limit_down(bar: dict[str, Any]) -> bool:
    if bar.get("limit_down_flag") or (_has_binary_limit_flags(bar) and _float_or_none(bar.get("lowlimit")) == 1):
        return True
    if _has_binary_limit_flags(bar):
        return False
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


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _bar_source_evidence(bar: dict[str, Any], *, prefix: str) -> dict[str, Any]:
    return {
        "trade_date": str(bar.get("trade_date") or "")[:10] or None,
        "source_version": _source_field(bar, f"{prefix}source_version"),
        "vendor_version": _source_field(bar, f"{prefix}vendor_version"),
        "rule_version": _source_field(bar, f"{prefix}rule_version"),
        "run_id": _source_field(bar, f"{prefix}run_id"),
    }


def _factor_source_evidence(
    source_version: Any,
    vendor_version: Any,
    rule_version: Any,
    run_id: Any,
) -> dict[str, Any]:
    return {
        "source_version": _text_or_none(source_version),
        "vendor_version": _text_or_none(vendor_version),
        "rule_version": _text_or_none(rule_version),
        "run_id": _text_or_none(run_id),
    }


def _source_field(payload: dict[str, Any], key: str) -> str | None:
    return _text_or_none(payload.get(key))


def _source_metadata_complete(source: dict[str, Any]) -> bool:
    return bool(_text_or_none(source.get("source_version"))) and bool(_text_or_none(source.get("run_id")))


def _source_failure_reason(
    source: dict[str, Any],
    *,
    missing_reason: str,
    unproven_reason: str,
    future_reason: str,
) -> str | None:
    if not _source_metadata_complete(source):
        return missing_reason
    status = str(source.get("availability_status") or "")
    if status == "available":
        return None
    if status == "available_after_evaluation":
        return future_reason
    return unproven_reason


def _normalize_source_availability_receipt(
    receipt: dict[str, Any] | None,
) -> dict[tuple[str, str | None, str | None, str | None, str | None], str]:
    if receipt is None:
        return {}
    sources = receipt.get("sources") if isinstance(receipt, dict) else None
    if not isinstance(sources, list):
        raise ValueError("source_availability_receipt.sources must be a list.")
    normalized: dict[tuple[str, str | None, str | None, str | None, str | None], str] = {}
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            raise ValueError(f"source_availability_receipt.sources[{index}] must be an object.")
        table = _text_or_none(item.get("table"))
        if not table:
            raise ValueError(f"source_availability_receipt.sources[{index}].table is required.")
        available_at = _parse_strict_iso_date(
            item.get("available_at"),
            field_name=f"source_availability_receipt.sources[{index}].available_at",
        ).isoformat()
        key = _source_availability_key(
            table=table,
            source_version=item.get("source_version"),
            vendor_version=item.get("vendor_version"),
            rule_version=item.get("rule_version"),
            run_id=item.get("run_id"),
        )
        if key in normalized:
            raise ValueError(
                f"source_availability_receipt contains duplicate source availability key for table={table}."
            )
        normalized[key] = available_at
    return normalized


def _source_availability_key(
    *,
    table: str,
    source_version: Any,
    vendor_version: Any,
    rule_version: Any,
    run_id: Any,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    return (
        str(table or "").strip(),
        _text_or_none(source_version),
        _text_or_none(vendor_version),
        _text_or_none(rule_version),
        _text_or_none(run_id),
    )


def _source_with_availability(
    *,
    table: str,
    source: dict[str, Any],
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    normalized = dict(source)
    key = _source_availability_key(
        table=table,
        source_version=normalized.get("source_version"),
        vendor_version=normalized.get("vendor_version"),
        rule_version=normalized.get("rule_version"),
        run_id=normalized.get("run_id"),
    )
    available_at = source_availability_index.get(key)
    if not _source_metadata_complete(normalized):
        status = "metadata_missing"
    elif available_at is None:
        status = "availability_unproven"
    elif available_at > str(evaluation_as_of_date or "")[:10]:
        status = "available_after_evaluation"
    else:
        status = "available"
    normalized["available_at"] = available_at
    normalized["availability_status"] = status
    return normalized


def _row_with_source_availability(
    row: dict[str, Any],
    *,
    source_availability_index: dict[tuple[str, str | None, str | None, str | None, str | None], str],
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    source = _source_with_availability(
        table=TABLE_OBS,
        source=_bar_source_evidence(row, prefix="obs_"),
        source_availability_index=source_availability_index,
        evaluation_as_of_date=evaluation_as_of_date,
    )
    return {**row, **{f"obs_{key}": value for key, value in source.items()}}


def _select_pit_observation_row(
    rows: list[dict[str, Any]],
    *,
    prefer_proven_available_source: bool,
) -> dict[str, Any]:
    if prefer_proven_available_source:
        for row in rows:
            if str(row.get("obs_availability_status") or "") == "available":
                return row
    return rows[0]


def _candidate_signal_date_text(candidate: dict[str, Any]) -> str:
    signal_date = _text_or_none(candidate.get("signal_date")) or _text_or_none(
        candidate.get("snapshot_as_of_date")
    )
    if not signal_date:
        raise ValueError("candidate.signal_date is required.")
    return signal_date


def _parse_strict_iso_date(value: Any, *, field_name: str) -> date:
    text = _text_or_none(value)
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be strict ISO date YYYY-MM-DD.") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be strict ISO date YYYY-MM-DD.")
    return parsed
