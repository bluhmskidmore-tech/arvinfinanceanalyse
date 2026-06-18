#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.livermore_stock_candidates import (  # noqa: E402
    EXP3B_STOCK_CANDIDATE_POLICY,
    EXP3C_SHADOW_STOCK_CANDIDATE_POLICY,
    diagnose_stock_candidate_filters,
    stock_candidate_policy_active_market_states,
)
from backend.app.core_finance.livermore_sector_rank import compute_sector_rank  # noqa: E402
from backend.app.services.market_data_livermore_service import (  # noqa: E402
    _load_sector_rank_inputs,
    _load_stock_candidate_snapshots,
)
from scripts.run_livermore_daily_pretrade_refresh import (  # noqa: E402
    inspect_livermore_daily_refresh_state,
)

TABLE_HIST = "livermore_candidate_history"
TABLE_DAILY = "choice_stock_daily_observation"
TABLE_POSITION = "livermore_position_snapshot"
TABLE_FACTOR = "choice_stock_factor_snapshot"
TABLE_UNIVERSE = "choice_stock_universe"
HORIZONS = ("return_5d", "return_20d")
STOCK_CANDIDATE_POLICY = EXP3B_STOCK_CANDIDATE_POLICY
SHADOW_STOCK_CANDIDATE_POLICY = EXP3C_SHADOW_STOCK_CANDIDATE_POLICY
FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD = 0.8
FACTOR_SCREEN_PARTIAL_COVERAGE_THRESHOLD = 0.5
FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS = 3


def build_stock_strategy_health_report(
    *,
    duckdb_path: str | Path,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    path = _resolve_duckdb_path(duckdb_path)
    if not path.exists():
        return {
            "status": "blocked",
            "duckdb_path": str(path),
            "as_of_date": _normalize_optional_date(as_of_date),
            "data_freshness": {},
            "factor_screen_coverage": {
                "status": "blocked",
                "reason": f"DuckDB file not found: {path}",
            },
            "performance_by_signal": {},
            "performance_by_market_state_signal": {},
            "risk_exit": {
                "status": "blocked",
                "reason": f"DuckDB file not found: {path}",
            },
            "findings": [
                {
                    "code": "duckdb_missing",
                    "severity": "block",
                    "message": f"DuckDB file not found: {path}",
                }
            ],
            "recommended_next_actions": ["Restore or configure the local MOSS DuckDB path."],
            "pretrade_readiness": {"ready": False, "missing": ["duckdb_missing"], "checks": {}},
            "candidate_filter_diagnostic": {
                "status": "unavailable",
                "reason": f"DuckDB file not found: {path}",
            },
            "shadow_candidate_filter_diagnostic": {
                "status": "unavailable",
                "reason": f"DuckDB file not found: {path}",
            },
        }

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = _table_names(conn)
        freshness = _data_freshness(conn, tables=tables)
        report_as_of = _report_as_of_date(freshness, as_of_date)
        findings: list[dict[str, Any]] = []
        if TABLE_HIST not in tables:
            findings.append(
                {
                    "code": "candidate_history_missing",
                    "severity": "block",
                    "message": f"{TABLE_HIST} is not materialized.",
                }
            )
            performance_by_signal: dict[str, Any] = {}
            performance_by_market_state_signal: dict[str, Any] = {}
        else:
            performance_by_signal = _performance_by_signal(conn)
            performance_by_market_state_signal = _performance_by_market_state_signal(conn)
            findings.extend(
                _strategy_findings(
                    freshness=freshness,
                    performance_by_market_state_signal=performance_by_market_state_signal,
                    as_of_date=_normalize_optional_date(as_of_date),
                )
            )
        pretrade_readiness = _pretrade_readiness(path, as_of_date=report_as_of)
        findings.extend(_pretrade_findings(pretrade_readiness))
        factor_screen_coverage = _factor_screen_coverage(conn, tables=tables, as_of_date=report_as_of)
        findings.extend(_factor_screen_coverage_findings(factor_screen_coverage))
        risk_exit = _risk_exit_status(conn, tables=tables, as_of_date=report_as_of)
        if risk_exit["status"] != "ready":
            findings.append(
                {
                    "code": "risk_exit_blocked",
                    "severity": "warning",
                    "message": risk_exit["reason"],
                }
            )
        market_state = _market_state_for_date(conn, tables=tables, as_of_date=report_as_of)
    finally:
        conn.close()

    candidate_filter_diagnostic = _candidate_filter_diagnostic(
        path,
        as_of_date=report_as_of,
        market_state=market_state,
        policy_name=STOCK_CANDIDATE_POLICY,
    )
    shadow_candidate_filter_diagnostic = _candidate_filter_diagnostic(
        path,
        as_of_date=report_as_of,
        market_state=market_state,
        policy_name=SHADOW_STOCK_CANDIDATE_POLICY,
    )
    findings.extend(_candidate_filter_findings(candidate_filter_diagnostic))
    findings.extend(_shadow_candidate_filter_findings(candidate_filter_diagnostic, shadow_candidate_filter_diagnostic))
    status = "blocked" if any(item["severity"] == "block" for item in findings) else ("warning" if findings else "ok")
    return {
        "status": status,
        "duckdb_path": str(path),
        "as_of_date": report_as_of,
        "data_freshness": freshness,
        "factor_screen_coverage": factor_screen_coverage,
        "pretrade_readiness": pretrade_readiness,
        "candidate_filter_diagnostic": candidate_filter_diagnostic,
        "shadow_candidate_filter_diagnostic": shadow_candidate_filter_diagnostic,
        "performance_by_signal": performance_by_signal,
        "performance_by_market_state_signal": performance_by_market_state_signal,
        "risk_exit": risk_exit,
        "findings": findings,
        "recommended_next_actions": _recommended_next_actions(findings, as_of_date=report_as_of),
    }


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        return ROOT / path
    return path


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _data_freshness(conn: duckdb.DuckDBPyConnection, *, tables: set[str]) -> dict[str, Any]:
    freshness: dict[str, Any] = {}
    if TABLE_DAILY in tables:
        max_date, row_count = conn.execute(
            f"select max(trade_date), count(*) from {TABLE_DAILY}"
        ).fetchone()
        freshness[TABLE_DAILY] = {
            "status": "available",
            "max_date": _date_text(max_date),
            "row_count": int(row_count or 0),
        }
    else:
        freshness[TABLE_DAILY] = {"status": "missing", "max_date": None, "row_count": 0}

    if TABLE_HIST in tables:
        max_date, row_count = conn.execute(
            f"select max(snapshot_as_of_date), count(*) from {TABLE_HIST}"
        ).fetchone()
        stock_candidate_latest = conn.execute(
            f"""
            select max(snapshot_as_of_date)
            from {TABLE_HIST}
            where signal_kind = 'stock_candidate'
            """
        ).fetchone()[0]
        freshness[TABLE_HIST] = {
            "status": "available",
            "max_date": _date_text(max_date),
            "row_count": int(row_count or 0),
        }
        freshness["stock_candidate_latest_date"] = _date_text(stock_candidate_latest)
        freshness["stock_candidate_policy"] = _stock_candidate_policy_context(conn)
    else:
        freshness[TABLE_HIST] = {"status": "missing", "max_date": None, "row_count": 0}
        freshness["stock_candidate_latest_date"] = None
        freshness["stock_candidate_policy"] = _stock_candidate_policy_context(None)
    return freshness


def _stock_candidate_policy_context(conn: duckdb.DuckDBPyConnection | None) -> dict[str, Any]:
    active_states = sorted(stock_candidate_policy_active_market_states(STOCK_CANDIDATE_POLICY))
    context: dict[str, Any] = {
        "name": STOCK_CANDIDATE_POLICY,
        "active_market_states": active_states,
        "latest_history_market_state": None,
        "latest_policy_active_history_date": None,
        "latest_policy_active_history_row_count": 0,
    }
    if conn is None:
        return context

    latest_state_row = conn.execute(
        f"""
        select coalesce(market_state, 'unknown') as market_state, count(*) as item_count
        from {TABLE_HIST}
        where snapshot_as_of_date = (select max(snapshot_as_of_date) from {TABLE_HIST})
        group by 1
        order by item_count desc, market_state asc
        limit 1
        """
    ).fetchone()
    if latest_state_row:
        context["latest_history_market_state"] = str(latest_state_row[0])

    if active_states:
        placeholders = ", ".join("?" for _ in active_states)
        latest_active = conn.execute(
            f"""
            select max(snapshot_as_of_date)
            from {TABLE_HIST}
            where coalesce(market_state, 'unknown') in ({placeholders})
            """,
            active_states,
        ).fetchone()[0]
        latest_active_text = _date_text(latest_active)
        context["latest_policy_active_history_date"] = latest_active_text
        if latest_active_text:
            active_count = conn.execute(
                f"""
                select count(*)::integer
                from {TABLE_HIST}
                where snapshot_as_of_date = ?
                  and coalesce(market_state, 'unknown') in ({placeholders})
                """,
                [latest_active_text, *active_states],
            ).fetchone()[0]
            context["latest_policy_active_history_row_count"] = int(active_count or 0)
    return context


def _performance_by_signal(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = conn.execute(
        f"""
        select signal_kind, count(*) as row_count
        from {TABLE_HIST}
        group by signal_kind
        order by signal_kind
        """
    ).fetchall()
    return {
        str(signal_kind or "unknown"): {
            "row_count": int(row_count or 0),
            **_horizon_stats(conn, where_sql="signal_kind = ?", params=[signal_kind]),
        }
        for signal_kind, row_count in rows
    }


def _performance_by_market_state_signal(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = conn.execute(
        f"""
        select coalesce(market_state, 'unknown') as market_state, signal_kind, count(*) as row_count
        from {TABLE_HIST}
        group by market_state, signal_kind
        order by market_state, signal_kind
        """
    ).fetchall()
    grouped: dict[str, Any] = {}
    for market_state, signal_kind, row_count in rows:
        state_key = str(market_state or "unknown")
        signal_key = str(signal_kind or "unknown")
        grouped.setdefault(state_key, {})[signal_key] = {
            "row_count": int(row_count or 0),
            **_horizon_stats(
                conn,
                where_sql="coalesce(market_state, 'unknown') = ? and signal_kind = ?",
                params=[state_key, signal_kind],
            ),
        }
    return grouped


def _horizon_stats(
    conn: duckdb.DuckDBPyConnection,
    *,
    where_sql: str,
    params: list[Any],
) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for horizon in HORIZONS:
        n, avg_return, wins = conn.execute(
            f"""
            select
              count({horizon})::integer,
              avg({horizon}),
              sum(case when {horizon} > 0 then 1 else 0 end)::integer
            from {TABLE_HIST}
            where {where_sql}
            """,
            params,
        ).fetchone()
        count = int(n or 0)
        win_count = int(wins or 0)
        stats[horizon] = {
            "count": count,
            "avg_return": None if avg_return is None else float(avg_return),
            "win_rate": None if count == 0 else win_count / count,
        }
    return stats


def _risk_exit_status(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str | None,
) -> dict[str, Any]:
    if TABLE_POSITION not in tables:
        return {
            "status": "blocked",
            "reason": "livermore_position_snapshot table is not materialized.",
            "latest_active_as_of_date": None,
            "active_rows": 0,
        }
    try:
        latest_active = conn.execute(
            f"""
            select max(as_of_date)
            from {TABLE_POSITION}
            where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            """
        ).fetchone()[0]
        if as_of_date:
            active_rows = conn.execute(
                f"""
                select count(*)::integer
                from {TABLE_POSITION}
                where as_of_date = ?
                  and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
                """,
                [as_of_date],
            ).fetchone()[0]
        else:
            active_rows = 0
    except duckdb.Error as exc:
        return {
            "status": "blocked",
            "reason": f"livermore_position_snapshot cannot be checked: {exc}",
            "latest_active_as_of_date": None,
            "active_rows": 0,
        }
    if int(active_rows or 0) <= 0:
        return {
            "status": "blocked",
            "reason": f"livermore_position_snapshot has no ACTIVE rows for as_of_date {as_of_date}.",
            "latest_active_as_of_date": _date_text(latest_active),
            "active_rows": int(active_rows or 0),
        }
    return {
        "status": "ready",
        "reason": "",
        "latest_active_as_of_date": _date_text(latest_active),
        "active_rows": int(active_rows or 0),
    }


def _factor_screen_coverage(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str | None,
) -> dict[str, Any]:
    if TABLE_FACTOR not in tables:
        return {
            "status": "blocked",
            "reason": f"{TABLE_FACTOR} is not materialized.",
            "snapshot_as_of_date": None,
            "coverage_count": 0,
            "coverage_denominator": 0,
            "coverage_ratio": None,
            "coverage_threshold": FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD,
        }
    if TABLE_UNIVERSE not in tables:
        return {
            "status": "blocked",
            "reason": f"{TABLE_UNIVERSE} is not materialized.",
            "snapshot_as_of_date": None,
            "coverage_count": 0,
            "coverage_denominator": 0,
            "coverage_ratio": None,
            "coverage_threshold": FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD,
        }
    snapshot_as_of_date = _latest_table_date_on_or_before(
        conn,
        table=TABLE_FACTOR,
        date_column="as_of_date",
        as_of_date=as_of_date,
    )
    if not snapshot_as_of_date:
        return {
            "status": "blocked",
            "reason": f"{TABLE_FACTOR} has no rows on or before {as_of_date}.",
            "snapshot_as_of_date": None,
            "coverage_count": 0,
            "coverage_denominator": 0,
            "coverage_ratio": None,
            "coverage_threshold": FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD,
        }
    universe_as_of_date = _latest_table_date_on_or_before(
        conn,
        table=TABLE_UNIVERSE,
        date_column="as_of_date",
        as_of_date=snapshot_as_of_date,
    )
    if not universe_as_of_date:
        return {
            "status": "blocked",
            "reason": f"{TABLE_UNIVERSE} has no rows on or before {snapshot_as_of_date}.",
            "snapshot_as_of_date": snapshot_as_of_date,
            "coverage_count": 0,
            "coverage_denominator": 0,
            "coverage_ratio": None,
            "coverage_threshold": FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD,
        }
    coverage_count = _count_distinct_stock_codes(
        conn,
        table=TABLE_FACTOR,
        date_column="as_of_date",
        date_value=snapshot_as_of_date,
    )
    coverage_denominator = _count_distinct_stock_codes(
        conn,
        table=TABLE_UNIVERSE,
        date_column="as_of_date",
        date_value=universe_as_of_date,
    )
    coverage_ratio = None if coverage_denominator <= 0 else round(coverage_count / coverage_denominator, 6)
    lag_days = _factor_screen_lag_days(
        conn,
        tables=tables,
        source_date=snapshot_as_of_date,
        as_of_date=as_of_date,
    )
    reason = ""
    if lag_days is not None and lag_days > FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS:
        status = "blocked"
        reason = (
            f"{TABLE_FACTOR} snapshot {snapshot_as_of_date} lags requested as_of_date {as_of_date} "
            f"by {lag_days} days; threshold is {FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS} days."
        )
    elif coverage_ratio is None or coverage_ratio < FACTOR_SCREEN_PARTIAL_COVERAGE_THRESHOLD:
        status = "blocked"
    elif coverage_ratio < FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD:
        status = "partial"
    else:
        status = "ready"
    return {
        "status": status,
        "reason": reason,
        "snapshot_as_of_date": snapshot_as_of_date,
        "universe_as_of_date": universe_as_of_date,
        "lag_days": lag_days,
        "freshness_threshold_days": FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS,
        "coverage_count": coverage_count,
        "coverage_denominator": coverage_denominator,
        "coverage_ratio": coverage_ratio,
        "coverage_threshold": FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD,
    }


def _factor_screen_coverage_findings(factor_screen_coverage: dict[str, Any]) -> list[dict[str, Any]]:
    status = str(factor_screen_coverage.get("status") or "")
    if status == "ready":
        return []
    lag_days = factor_screen_coverage.get("lag_days")
    if isinstance(lag_days, int) and lag_days > FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS:
        return [
            {
                "code": "factor_screen_stale_vs_requested",
                "severity": "block",
                "message": str(factor_screen_coverage.get("reason") or "factor_screen snapshot is stale."),
            }
        ]
    ratio = factor_screen_coverage.get("coverage_ratio")
    ratio_text = "unknown" if ratio is None else f"{float(ratio) * 100:.1f}%"
    return [
        {
            "code": "factor_screen_coverage_below_primary_threshold",
            "severity": "block" if status == "blocked" else "warning",
            "message": (
                "factor_screen coverage is below the primary threshold: "
                f"{factor_screen_coverage.get('coverage_count', 0)}/"
                f"{factor_screen_coverage.get('coverage_denominator', 0)} ({ratio_text}), "
                f"threshold {FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD * 100:.0f}%."
            ),
        }
    ]


def _latest_table_date_on_or_before(
    conn: duckdb.DuckDBPyConnection,
    *,
    table: str,
    date_column: str,
    as_of_date: str | None,
) -> str | None:
    if not as_of_date:
        return None
    row = conn.execute(
        f"""
        select max({date_column})
        from {table}
        where cast({date_column} as date) <= cast(? as date)
        """,
        [as_of_date],
    ).fetchone()
    return _date_text(row[0]) if row else None


def _count_distinct_stock_codes(
    conn: duckdb.DuckDBPyConnection,
    *,
    table: str,
    date_column: str,
    date_value: str,
) -> int:
    row = conn.execute(
        f"""
        select count(distinct stock_code)::integer
        from {table}
        where cast({date_column} as date) = cast(? as date)
        """,
        [date_value],
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _factor_screen_lag_days(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    source_date: str | None,
    as_of_date: str | None,
) -> int | None:
    trading_lag = _trading_lag_days(conn, tables=tables, source_date=source_date, as_of_date=as_of_date)
    if trading_lag is not None:
        return trading_lag
    return _calendar_lag_days(source_date, as_of_date)


def _trading_lag_days(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    source_date: str | None,
    as_of_date: str | None,
) -> int | None:
    if TABLE_DAILY not in tables or not source_date or not as_of_date:
        return None
    try:
        row = conn.execute(
            f"""
            select count(distinct trade_date)::integer
            from {TABLE_DAILY}
            where cast(trade_date as date) > cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
            """,
            [source_date, as_of_date],
        ).fetchone()
    except duckdb.Error:
        return None
    if not row or row[0] is None:
        return None
    count = int(row[0] or 0)
    return count if count > 0 else None


def _calendar_lag_days(source_date: str | None, as_of_date: str | None) -> int | None:
    if not source_date or not as_of_date:
        return None
    try:
        source = date.fromisoformat(source_date)
        target = date.fromisoformat(as_of_date)
    except ValueError:
        return None
    return max(0, (target - source).days)


def _pretrade_readiness(path: Path, *, as_of_date: str | None) -> dict[str, Any]:
    if not as_of_date:
        return {"ready": False, "missing": ["as_of_date"], "checks": {}}
    try:
        state = inspect_livermore_daily_refresh_state(
            duckdb_path=path,
            target_date=as_of_date,
        )
    except Exception as exc:
        return {
            "ready": False,
            "missing": ["pretrade_readiness_error"],
            "checks": {},
            "reason": str(exc).splitlines()[0] if str(exc).strip() else exc.__class__.__name__,
        }
    return {
        "ready": bool(state.get("ready")),
        "missing": list(state.get("missing") or []),
        "checks": state.get("checks") or {},
    }


def _pretrade_findings(pretrade_readiness: dict[str, Any]) -> list[dict[str, Any]]:
    missing = {str(item) for item in pretrade_readiness.get("missing", [])}
    findings: list[dict[str, Any]] = []
    if "pretrade_readiness_error" in missing:
        reason = str(pretrade_readiness.get("reason") or "unknown readiness error")
        findings.append(
            {
                "code": "pretrade_readiness_error",
                "severity": "block",
                "message": f"Pretrade readiness check failed: {reason}",
            }
        )
    if "choice_stock_inputs" in missing:
        findings.append(
            {
                "code": "pretrade_choice_stock_inputs_missing",
                "severity": "warning",
                "message": "Pretrade chain is missing choice stock inputs for the requested as_of_date.",
            }
        )
    if "choice_stock_inputs" in missing and "position_snapshot" in missing:
        findings.append(
            {
                "code": "position_rollforward_waits_for_choice_stock_inputs",
                "severity": "warning",
                "message": "Do not roll forward Livermore positions alone while choice stock inputs are missing.",
            }
        )
    return findings


def _market_state_for_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str | None,
) -> str | None:
    if TABLE_HIST not in tables or not as_of_date:
        return None
    row = conn.execute(
        f"""
        select coalesce(market_state, 'unknown') as market_state, count(*) as item_count
        from {TABLE_HIST}
        where snapshot_as_of_date = ?
        group by 1
        order by item_count desc, market_state asc
        limit 1
        """,
        [as_of_date],
    ).fetchone()
    return None if not row else str(row[0])


def _candidate_filter_diagnostic(
    path: Path,
    *,
    as_of_date: str | None,
    market_state: str | None,
    policy_name: str,
) -> dict[str, Any]:
    if not as_of_date:
        return {"status": "unavailable", "reason": "as_of_date is unavailable."}
    if not market_state:
        return {
            "status": "unavailable",
            "reason": f"market_state is unavailable for {as_of_date}.",
        }
    try:
        sector_rows, _sector_tables, _sector_sources, _sector_vendors = _load_sector_rank_inputs(
            duckdb_path=str(path),
            as_of_date=as_of_date,
        )
        sector_result = compute_sector_rank(as_of_date=as_of_date, rows=sector_rows)
        if not sector_result.ready:
            return {
                "status": "unavailable",
                "reason": f"sector_rank is unavailable for {as_of_date}.",
            }
        snapshots, stock_tables, _stock_sources, _stock_vendors = _load_stock_candidate_snapshots(
            duckdb_path=str(path),
            as_of_date=as_of_date,
            sector_rank_payload=sector_result.payload,
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc).splitlines()[0] if str(exc).strip() else exc.__class__.__name__,
        }
    if not snapshots:
        return {
            "status": "unavailable",
            "reason": f"stock candidate snapshots are unavailable for {as_of_date}.",
            "tables_used": stock_tables,
        }
    return diagnose_stock_candidate_filters(
        as_of_date=as_of_date,
        market_state=market_state,
        snapshots=snapshots,
        policy_name=policy_name,
    )


def _candidate_filter_findings(candidate_filter_diagnostic: dict[str, Any]) -> list[dict[str, Any]]:
    if candidate_filter_diagnostic.get("status") != "ready":
        return []
    if int(candidate_filter_diagnostic.get("final_candidate_count") or 0) > 0:
        return []
    primary_blocker = _primary_zero_output_blocker(candidate_filter_diagnostic)
    near_miss = _format_near_miss(candidate_filter_diagnostic)
    message = (
        f"{STOCK_CANDIDATE_POLICY} filter funnel ended at zero"
        f"{'; primary blocker ' + primary_blocker if primary_blocker else ''}"
        f"{'; near miss ' + near_miss if near_miss else ''}."
    )
    return [
        {
            "code": "stock_candidate_filter_zero_output",
            "severity": "warning",
            "message": message,
            "primary_blocker": primary_blocker,
        }
    ]


def _shadow_candidate_filter_findings(
    official_diagnostic: dict[str, Any],
    shadow_diagnostic: dict[str, Any],
) -> list[dict[str, Any]]:
    if official_diagnostic.get("status") != "ready" or shadow_diagnostic.get("status") != "ready":
        return []
    official_count = int(official_diagnostic.get("final_candidate_count") or 0)
    shadow_count = int(shadow_diagnostic.get("final_candidate_count") or 0)
    if shadow_count <= official_count:
        return []
    shadow_label = str(shadow_diagnostic.get("selection_policy") or SHADOW_STOCK_CANDIDATE_POLICY)
    shadow_candidate = _format_first_candidate(shadow_diagnostic)
    message = (
        f"{shadow_label} emits {shadow_count} candidates vs official {official_count}"
        f"{'; first shadow candidate ' + shadow_candidate if shadow_candidate else ''}."
    )
    return [
        {
            "code": "stock_candidate_shadow_policy_delta",
            "severity": "info",
            "message": message,
            "official_candidate_count": official_count,
            "shadow_candidate_count": shadow_count,
            "shadow_policy": shadow_label,
        }
    ]


def _primary_zero_output_blocker(candidate_filter_diagnostic: dict[str, Any]) -> str:
    for row in candidate_filter_diagnostic.get("funnel") or []:
        if int(row.get("before") or 0) > 0 and int(row.get("pass") or 0) == 0:
            return str(row.get("step") or "")
    return ""


def _format_near_miss(candidate_filter_diagnostic: dict[str, Any]) -> str:
    near_misses = candidate_filter_diagnostic.get("near_misses") or []
    if not near_misses:
        return ""
    first = near_misses[0]
    code = str(first.get("stock_code") or "")
    name = str(first.get("stock_name") or "")
    reasons = ", ".join(str(item) for item in first.get("fail_reasons") or [])
    label = " ".join(part for part in [code, name] if part)
    return f"{label} ({reasons})" if reasons else label


def _format_first_candidate(candidate_filter_diagnostic: dict[str, Any]) -> str:
    candidate_items = candidate_filter_diagnostic.get("candidate_items") or []
    if not candidate_items:
        return _format_near_miss(candidate_filter_diagnostic)
    first = candidate_items[0]
    code = str(first.get("stock_code") or "")
    name = str(first.get("stock_name") or "")
    return " ".join(part for part in [code, name] if part)


def _strategy_findings(
    *,
    freshness: dict[str, Any],
    performance_by_market_state_signal: dict[str, Any],
    as_of_date: str | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    daily_date = freshness.get(TABLE_DAILY, {}).get("max_date")
    stock_candidate_date = freshness.get("stock_candidate_latest_date")
    policy = freshness.get("stock_candidate_policy", {})
    policy_active_date = policy.get("latest_policy_active_history_date") if isinstance(policy, dict) else None
    policy_active_row_count = (
        int(policy.get("latest_policy_active_history_row_count") or 0) if isinstance(policy, dict) else 0
    )
    if as_of_date and daily_date and daily_date < as_of_date:
        findings.append(
            {
                "code": "daily_observation_stale_vs_requested",
                "severity": "warning",
                "message": f"daily observation max date {daily_date} is before requested as_of_date {as_of_date}.",
            }
        )
    if policy_active_date and policy_active_row_count > 0 and stock_candidate_date != policy_active_date:
        findings.append(
            {
                "code": "stock_candidate_absent_on_policy_active_date",
                "severity": "warning",
                "message": (
                    f"{STOCK_CANDIDATE_POLICY} policy-active history exists on {policy_active_date}, "
                    "but no stock_candidate rows were emitted for that date."
                ),
            }
        )
    elif policy_active_date and not stock_candidate_date:
        findings.append(
            {
                "code": "stock_candidate_missing_for_policy_active_date",
                "severity": "warning",
                "message": f"stock_candidate has no rows, but policy {STOCK_CANDIDATE_POLICY} has active-market history through {policy_active_date}.",
            }
        )
    elif policy_active_date and stock_candidate_date and stock_candidate_date < policy_active_date:
        findings.append(
            {
                "code": "stock_candidate_stale_vs_policy_active_date",
                "severity": "warning",
                "message": (
                    f"stock_candidate latest date {stock_candidate_date} is before latest "
                    f"{STOCK_CANDIDATE_POLICY} policy-active history date {policy_active_date}."
                ),
            }
        )
    overheat_stock = performance_by_market_state_signal.get("OVERHEAT", {}).get("stock_candidate")
    if overheat_stock:
        stat_5d = overheat_stock.get("return_5d", {})
        avg_return = stat_5d.get("avg_return")
        win_rate = stat_5d.get("win_rate")
        if (avg_return is not None and avg_return <= 0.0) or (win_rate is not None and win_rate < 0.4):
            findings.append(
                {
                    "code": "overheat_stock_candidate_underperforms",
                    "severity": "warning",
                    "message": "OVERHEAT stock_candidate return_5d is weak; keep OVERHEAT entry blocked or review-only.",
                    "avg_return_5d": avg_return,
                    "win_rate_5d": win_rate,
                }
            )
    return findings


def _recommended_next_actions(findings: list[dict[str, Any]], *, as_of_date: str | None) -> list[str]:
    actions: list[str] = []
    codes = {str(item["code"]) for item in findings}
    date_label = as_of_date or "the requested as_of_date"
    if "pretrade_readiness_error" in codes:
        actions.append("Fix the pretrade readiness check before using this diagnostic for execution decisions.")
    if "daily_observation_stale_vs_requested" in codes:
        actions.append("Refresh choice stock daily observations through the requested as_of_date, then rerun strategy history.")
    if "pretrade_choice_stock_inputs_missing" in codes:
        actions.append(f"Provide a local source DuckDB or enabled Choice/Tushare refresh before materializing {date_label} stock inputs.")
    if "factor_screen_coverage_below_primary_threshold" in codes:
        actions.append("Refresh or backfill factor snapshots against the active A-share universe before treating factor_screen as primary evidence.")
    if "position_rollforward_waits_for_choice_stock_inputs" in codes:
        actions.append("Do not roll forward the Livermore position snapshot until choice stock inputs are ready for the same as_of_date.")
    if "stock_candidate_stale_vs_policy_active_date" in codes or "stock_candidate_missing_for_policy_active_date" in codes:
        actions.append("Rerun Livermore stock_candidate materialization for the latest WARM/HOT policy-active date.")
    if "stock_candidate_absent_on_policy_active_date" in codes:
        actions.append("Review exp3b filters and candidate evidence for the latest WARM/HOT date; the run completed but emitted zero stock candidates.")
    filter_zero = next(
        (item for item in findings if item.get("code") == "stock_candidate_filter_zero_output"),
        None,
    )
    if filter_zero is not None:
        blocker = str(filter_zero.get("primary_blocker") or "the primary zero-output blocker")
        actions.append(
            f"Use the {date_label} filter waterfall to test {blocker} before relaxing unrelated exp3b gates."
        )
    shadow_delta = next(
        (item for item in findings if item.get("code") == "stock_candidate_shadow_policy_delta"),
        None,
    )
    if shadow_delta is not None:
        shadow_policy = str(shadow_delta.get("shadow_policy") or SHADOW_STOCK_CANDIDATE_POLICY)
        actions.append(
            f"Track {shadow_policy} as shadow-only evidence for {date_label}; do not promote until at least 30 mature T+5 samples pass review."
        )
    if "overheat_stock_candidate_underperforms" in codes:
        actions.append("Keep OVERHEAT new-entry policy disabled unless a separate validated OVERHEAT rule is introduced.")
    if "risk_exit_blocked" in codes and "position_rollforward_waits_for_choice_stock_inputs" not in codes:
        actions.append("Land active Livermore position snapshots with entry cost, bars since entry, close history, and volume history.")
    if not actions:
        actions.append("Use the report as a baseline before testing parameter changes.")
    return actions


def _report_as_of_date(freshness: dict[str, Any], as_of_date: str | None) -> str | None:
    normalized = _normalize_optional_date(as_of_date)
    if normalized:
        return normalized
    daily_date = freshness.get(TABLE_DAILY, {}).get("max_date")
    hist_date = freshness.get(TABLE_HIST, {}).get("max_date")
    return str(daily_date or hist_date or "") or None


def _normalize_optional_date(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    return text or None


def _date_text(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    return text or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a local MOSS stock strategy health diagnostic report.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--as-of-date")
    args = parser.parse_args(argv)

    report = build_stock_strategy_health_report(
        duckdb_path=args.duckdb_path,
        as_of_date=args.as_of_date,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
