from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import duckdb

from backend.app.core_finance.livermore_strategy import BroadIndexObservation, evaluate_market_gate
from backend.app.services.formal_result_runtime import build_result_envelope

RULE_VERSION = "rv_livermore_strategy_v1"
CACHE_VERSION = "cv_livermore_strategy_v1"
RESULT_KIND = "market_data.livermore"
STRATEGY_NAME = "Livermore A-Share Defended Trend"
EMPTY_SOURCE_VERSION = "sv_livermore_empty"
EMPTY_VENDOR_VERSION = "vv_none"
BROAD_INDEX_SERIES_ID = "CA.CSI300"
HISTORY_LIMIT = 260


def livermore_strategy_envelope(*, duckdb_path: str, as_of_date: str | None = None) -> dict[str, object]:
    requested_date = _parse_optional_date(as_of_date)
    payload, meta = load_livermore_strategy_payload(duckdb_path=duckdb_path, as_of_date=requested_date)
    filters_applied = {
        "requested_as_of_date": None if requested_date is None else requested_date.isoformat(),
        "as_of_date": payload["as_of_date"],
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=meta["source_version"],
        rule_version=RULE_VERSION,
        quality_flag=meta["quality_flag"],
        vendor_version=meta["vendor_version"],
        vendor_status=meta["vendor_status"],
        fallback_mode=meta["fallback_mode"],
        filters_applied=filters_applied,
        tables_used=meta["tables_used"],
        evidence_rows=meta["evidence_rows"],
        result_payload=payload,
    )


def load_livermore_strategy_payload(
    *,
    duckdb_path: str,
    as_of_date: date | None,
) -> tuple[dict[str, object], dict[str, object]]:
    history_rows, tables_used = _load_broad_index_history(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
    )
    market_gate = evaluate_market_gate(history_rows)
    requested_text = None if as_of_date is None else as_of_date.isoformat()
    resolved_as_of_date = history_rows[-1].trade_date.isoformat() if history_rows else None
    diagnostics = _build_diagnostics(
        requested_as_of_date=requested_text,
        resolved_as_of_date=resolved_as_of_date,
        market_gate=market_gate,
        history_count=len(history_rows),
    )
    data_gaps = _build_data_gaps(
        market_gate=market_gate,
        history_count=len(history_rows),
        resolved_as_of_date=resolved_as_of_date,
    )
    rule_readiness = _build_rule_readiness(
        market_gate=market_gate,
        history_count=len(history_rows),
    )
    supported_outputs, unsupported_outputs = _build_supported_outputs(market_gate["state"])
    quality_flag = _quality_flag_for_market_gate(market_gate["state"])
    payload = {
        "as_of_date": resolved_as_of_date,
        "requested_as_of_date": requested_text,
        "strategy_name": STRATEGY_NAME,
        "basis": "analytical",
        "market_gate": market_gate,
        "rule_readiness": rule_readiness,
        "data_gaps": data_gaps,
        "diagnostics": diagnostics,
        "supported_outputs": supported_outputs,
        "unsupported_outputs": unsupported_outputs,
    }
    meta = {
        "quality_flag": quality_flag,
        "vendor_status": _vendor_status_for_state(str(market_gate["state"])),
        "fallback_mode": "latest_snapshot" if quality_flag == "stale" else "none",
        "source_version": _aggregate_lineage(
            [row.source_version for row in history_rows if row.source_version],
            empty_value=EMPTY_SOURCE_VERSION,
        )
        if history_rows
        else EMPTY_SOURCE_VERSION,
        "vendor_version": _aggregate_lineage(
            [row.vendor_version for row in history_rows if row.vendor_version],
            empty_value=EMPTY_VENDOR_VERSION,
        )
        if history_rows
        else EMPTY_VENDOR_VERSION,
        "tables_used": tables_used,
        "evidence_rows": len(history_rows),
    }
    return payload, meta


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))


def _load_broad_index_history(
    *,
    duckdb_path: str,
    as_of_date: date | None,
) -> tuple[list[_LoadedObservation], list[str]]:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return [], []

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return [], []

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        queries: list[str] = []
        params: list[object] = []
        tables_used: list[str] = []
        date_filter = "and cast(trade_date as date) <= ?" if as_of_date is not None else ""
        if "fact_choice_macro_daily" in tables:
            tables_used.append("fact_choice_macro_daily")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  coalesce(quality_flag, 'ok') as quality_flag,
                  0 as source_rank
                from fact_choice_macro_daily
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if "choice_market_snapshot" in tables:
            tables_used.append("choice_market_snapshot")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  'ok' as quality_flag,
                  1 as source_rank
                from choice_market_snapshot
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if not queries:
            return [], []
        rows = conn.execute(
            f"""
            with unioned as (
              {" union all ".join(queries)}
            ),
            deduped as (
              select
                trade_date,
                close_value,
                source_version,
                vendor_version,
                quality_flag,
                row_number() over (
                  partition by trade_date
                  order by source_rank asc, source_version desc
                ) as rn
              from unioned
            )
            select
              trade_date,
              close_value,
              source_version,
              vendor_version,
              quality_flag
            from deduped
            where rn = 1
            order by trade_date desc
            limit {HISTORY_LIMIT}
            """,
            params,
        ).fetchall()
    except duckdb.Error:
        return [], tables_used if "tables_used" in locals() else []
    finally:
        conn.close()

    ordered = [
        _LoadedObservation(
            trade_date=row[0],
            close=float(row[1]),
            source_version=str(row[2] or ""),
            vendor_version=str(row[3] or ""),
            quality_flag=str(row[4] or "ok"),
        )
        for row in reversed(rows)
        if row[0] is not None and row[1] is not None
    ]
    return ordered, tables_used


class _LoadedObservation(BroadIndexObservation):
    pass


def _build_supported_outputs(state: str) -> tuple[list[str], list[dict[str, str]]]:
    unsupported = [
        {
            "key": "sector_rank",
            "reason": "Sector membership and sector-strength inputs are not landed yet.",
        },
        {
            "key": "stock_candidates",
            "reason": "Stock-level OHLCV, status, and candidate filters are not landed yet.",
        },
        {
            "key": "risk_exit",
            "reason": "Position and entry-cost inputs are not landed yet.",
        },
    ]
    if state == "NO_DATA":
        return [], [
            {
                "key": "market_gate",
                "reason": "Broad-index history is unavailable for CA.CSI300.",
            },
            *unsupported,
        ]
    return ["market_gate"], unsupported


def _build_rule_readiness(*, market_gate: dict[str, object], history_count: int) -> list[dict[str, object]]:
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gate_status = "missing"
        gate_summary = "Broad-index history is unavailable, so the market gate cannot be evaluated."
        gate_missing_inputs = ["broad_index_history", "breadth", "limit_up_quality"]
    elif gate_state == "STALE":
        gate_status = "stale"
        gate_summary = "Broad-index history resolved, but the latest landed point is stale."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    else:
        gate_status = "partial"
        if gate_state == "PENDING_DATA":
            gate_summary = f"Broad-index history is present but only {history_count} observations are landed."
        else:
            gate_summary = "Trend-only market gate is available; breadth and limit-up quality remain missing."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    return [
        {
            "key": "market_gate",
            "title": "Market gate",
            "status": gate_status,
            "summary": gate_summary,
            "required_inputs": [
                "broad_index_history",
                "breadth",
                "limit_up_quality",
            ],
            "missing_inputs": gate_missing_inputs,
        },
        {
            "key": "sector_rank",
            "title": "Sector ranking",
            "status": "missing",
            "summary": "Sector membership and sector-strength inputs are not landed yet.",
            "required_inputs": ["sector_membership", "sector_strength"],
            "missing_inputs": ["sector_membership", "sector_strength"],
        },
        {
            "key": "stock_pivot",
            "title": "Stock pivot filters",
            "status": "blocked",
            "summary": "Stock pivot output is blocked until sector rank and stock-universe inputs land.",
            "required_inputs": ["stock_ohlcv", "stock_status", "sector_rank"],
            "missing_inputs": ["stock_ohlcv", "stock_status", "sector_rank"],
        },
        {
            "key": "risk_exit",
            "title": "Risk and exit rules",
            "status": "blocked",
            "summary": "Risk and exit output is blocked until position and entry-cost inputs land.",
            "required_inputs": ["positions", "entry_cost", "bars_since_entry"],
            "missing_inputs": ["positions", "entry_cost", "bars_since_entry"],
        },
    ]


def _build_data_gaps(
    *,
    market_gate: dict[str, object],
    history_count: int,
    resolved_as_of_date: str | None,
) -> list[dict[str, str]]:
    gaps = [
        {
            "input_family": "breadth",
            "status": "missing",
            "evidence": "5-day breadth input family is not landed in DuckDB for this slice.",
        },
        {
            "input_family": "limit_up_quality",
            "status": "missing",
            "evidence": "Limit-up seal/break quality input family is not landed in DuckDB for this slice.",
        },
        {
            "input_family": "sector_strength",
            "status": "missing",
            "evidence": "Sector membership and ranking inputs are not landed in DuckDB for this slice.",
        },
        {
            "input_family": "stock_universe",
            "status": "missing",
            "evidence": "Stock OHLCV, status, and candidate-filter inputs are not landed in DuckDB for this slice.",
        },
        {
            "input_family": "position_risk",
            "status": "missing",
            "evidence": "Position and entry-cost inputs are not landed in DuckDB for this slice.",
        },
    ]
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "missing",
                "evidence": "CA.CSI300 history is unavailable in fact_choice_macro_daily/choice_market_snapshot.",
            },
        )
    elif gate_state == "PENDING_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "partial",
                "evidence": f"CA.CSI300 history has {history_count} observations; 60 are required.",
            },
        )
    elif gate_state == "STALE":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "stale",
                "evidence": f"Latest CA.CSI300 input on {resolved_as_of_date} is marked stale.",
            },
        )
    return gaps


def _build_diagnostics(
    *,
    requested_as_of_date: str | None,
    resolved_as_of_date: str | None,
    market_gate: dict[str, object],
    history_count: int,
) -> list[dict[str, str | None]]:
    diagnostics: list[dict[str, str | None]] = []
    state = str(market_gate["state"])
    if requested_as_of_date is not None and resolved_as_of_date != requested_as_of_date:
        diagnostics.append(
            {
                "severity": "info",
                "code": "LIVERMORE_REQUESTED_DATE_RESOLVED_TO_AVAILABLE",
                "message": (
                    f"Requested {requested_as_of_date}; resolved to latest available broad-index input "
                    f"{resolved_as_of_date}."
                ),
                "input_family": "broad_index_history",
            }
        )
    if state == "NO_DATA":
        diagnostics.append(
            {
                "severity": "error",
                "code": "LIVERMORE_BROAD_INDEX_NO_DATA",
                "message": "CA.CSI300 history is unavailable in landed market-data tables.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "PENDING_DATA":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_INSUFFICIENT_HISTORY",
                "message": f"Need at least 60 broad-index observations; found {history_count}.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "STALE":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_STALE",
                "message": "Latest CA.CSI300 input is marked stale and cannot be treated as current.",
                "input_family": "broad_index_history",
            }
        )
    diagnostics.extend(
        [
            {
                "severity": "warning",
                "code": "LIVERMORE_BREADTH_MISSING",
                "message": "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
                "input_family": "breadth",
            },
            {
                "severity": "warning",
                "code": "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
                "message": "Limit-up quality inputs are unavailable; the market gate is capped at the trend-only slice.",
                "input_family": "limit_up_quality",
            },
            {
                "severity": "warning",
                "code": "LIVERMORE_SECTOR_INPUTS_MISSING",
                "message": "Sector membership and sector-strength inputs are unavailable.",
                "input_family": "sector_strength",
            },
            {
                "severity": "warning",
                "code": "LIVERMORE_STOCK_INPUTS_MISSING",
                "message": "Stock-universe inputs are unavailable, so no candidates are produced.",
                "input_family": "stock_universe",
            },
            {
                "severity": "warning",
                "code": "LIVERMORE_RISK_INPUTS_MISSING",
                "message": "Position and entry-cost inputs are unavailable, so risk/exit output is blocked.",
                "input_family": "position_risk",
            },
        ]
    )
    return diagnostics


def _quality_flag_for_market_gate(state: str) -> str:
    if state == "STALE":
        return "stale"
    if state in {"NO_DATA", "PENDING_DATA"}:
        return "warning"
    return "ok"


def _vendor_status_for_state(state: str) -> str:
    if state == "STALE":
        return "vendor_stale"
    if state == "NO_DATA":
        return "vendor_unavailable"
    return "ok"


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)
