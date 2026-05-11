from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.tasks.choice_stock_materialize import load_choice_stock_materialization_coverage

from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

EMPTY_SOURCE_VERSION = "sv_livermore_candidate_history_empty"
EMPTY_VENDOR_VERSION = "vv_none"
RESULT_KIND = "market_data.livermore.candidate_history"
RULE_VERSION = "rv_livermore_candidate_history_v1"
CACHE_VERSION = "cv_livermore_candidate_history_v1"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
_DEFAULT_SIGNAL_KINDS = ["stock_candidate", "theme_breakout"]

_SELECT_COLUMNS = (
    "snapshot_as_of_date",
    "stock_code",
    "stock_name",
    "candidate_rank",
    "sector_code",
    "sector_name",
    "selection_close",
    "forward_trade_date_1d",
    "forward_trade_date_5d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_20d",
    "data_status",
    "formula_version",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
    "signal_kind",
    "theme_key",
    "theme_name",
    "theme_source_kind",
    "theme_rank",
    "stock_rank_in_theme",
    "sector_rank",
    "strength_pctchange",
    "strength_turn",
    "strength_amplitude",
    "close_strength",
    "closed_up_limit",
    "signal_evidence_json",
)


def livermore_candidate_history_envelope(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
    limit: int,
) -> dict[str, object]:
    """Read persisted candidate history slice; DuckDB SELECT only (API read-only)."""
    trimmed_code = stock_code.strip().upper() if stock_code else None
    trimmed_code = trimmed_code if trimmed_code else None

    result_payload_empty: dict[str, object] = {
        "items": [],
        "summary": _build_summary([]),
        "backtest_window_summary": livermore_candidate_history_backtest_window_summary(
            duckdb_path=duckdb_path,
            stock_code=trimmed_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
        ),
        "stock_code": trimmed_code,
        "snapshot_from": snapshot_from.strip() if snapshot_from else None,
        "snapshot_to": snapshot_to.strip() if snapshot_to else None,
        "limit": limit,
    }

    path = Path(duckdb_path)
    if not path.is_file():
        return _wrap_empty_envelope(payload=result_payload_empty)

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {r[0] for r in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            return _wrap_empty_envelope(payload=dict(result_payload_empty))
        available_columns = _available_columns(conn)

        where_clauses: list[str] = []
        bindings: list[object] = []
        if trimmed_code:
            where_clauses.append("stock_code = ?")
            bindings.append(trimmed_code)
        if snapshot_from and snapshot_from.strip():
            where_clauses.append("snapshot_as_of_date >= ?")
            bindings.append(snapshot_from.strip()[:10])
        if snapshot_to and snapshot_to.strip():
            where_clauses.append("snapshot_as_of_date <= ?")
            bindings.append(snapshot_to.strip()[:10])
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        bindings.append(limit)

        rows = conn.execute(
            f"""
            select {_select_list(available_columns)}
            from {TABLE_HIST}
            {sql_where}
            order by snapshot_as_of_date desc, candidate_rank asc
            limit ?
            """,
            bindings,
        ).fetchall()
    finally:
        conn.close()

    items = [_normalize_row(row) for row in rows]

    lineage_src = _first_nonempty_source_version(items)
    lineage_vend = _first_nonempty_vendor_version(items)

    result_payload = {
        "items": items,
        "summary": _build_summary(items),
        "backtest_window_summary": livermore_candidate_history_backtest_window_summary(
            duckdb_path=duckdb_path,
            stock_code=trimmed_code,
            snapshot_from=snapshot_from,
            snapshot_to=snapshot_to,
        ),
        "stock_code": trimmed_code,
        "snapshot_from": snapshot_from.strip() if snapshot_from else None,
        "snapshot_to": snapshot_to.strip() if snapshot_to else None,
        "limit": limit,
    }

    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=lineage_src,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning" if not items else "ok"),
        vendor_version=lineage_vend or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "stock_code": trimmed_code,
            "snapshot_from": result_payload["snapshot_from"],
            "snapshot_to": result_payload["snapshot_to"],
            "limit": limit,
        },
        tables_used=[TABLE_HIST],
        evidence_rows=len(items),
        result_payload=result_payload,
    )


def _available_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_HIST}')").fetchall()}


def livermore_candidate_history_backtest_window_summary(
    *,
    duckdb_path: str,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, Any]:
    trimmed_code = stock_code.strip().upper() if stock_code else None
    trimmed_code = trimmed_code if trimmed_code else None
    normalized_from = _normalize_date_text(snapshot_from)
    normalized_to = _normalize_date_text(snapshot_to)
    base_summary = _empty_backtest_window_summary(snapshot_from=normalized_from, snapshot_to=normalized_to)

    path = Path(duckdb_path)
    if not path.is_file():
        return base_summary

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables and TABLE_OBS not in tables:
            return base_summary
        history_table_present = TABLE_HIST in tables
        rows = _load_backtest_window_rows(
            conn,
            stock_code=trimmed_code,
            snapshot_from=normalized_from,
            snapshot_to=normalized_to,
        )
        row_dates = sorted({str(row.get("snapshot_as_of_date") or "")[:10] for row in rows if row.get("snapshot_as_of_date")})
        trade_dates = _resolve_replay_trade_dates(
            conn,
            tables=tables,
            snapshot_from=normalized_from,
            snapshot_to=normalized_to,
            row_dates=row_dates,
        )
    finally:
        conn.close()

    if not trade_dates:
        return base_summary

    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        trade_date = str(row.get("snapshot_as_of_date") or "")[:10]
        if not trade_date:
            continue
        rows_by_date.setdefault(trade_date, []).append(row)

    completed_dates = 0
    pending_dates = 0
    unsupported_dates = 0
    proxy_only_dates = 0
    completed_rows = 0
    pending_rows = 0
    unsupported_rows = 0
    proxy_only_rows = 0
    included_dates: list[str] = []
    excluded_dates: list[str] = []
    date_reasons: list[dict[str, Any]] = []

    for trade_date in trade_dates:
        coverage = load_choice_stock_materialization_coverage(duckdb_path=duckdb_path, as_of_date=trade_date)
        classification = _classify_replay_date(
            trade_date=trade_date,
            coverage=coverage,
            rows=rows_by_date.get(trade_date, []),
            history_table_present=history_table_present,
        )
        status = str(classification["status"])
        row_count = len(rows_by_date.get(trade_date, []))
        if status == "completed":
            completed_dates += 1
            completed_rows += row_count
        elif status == "pending":
            pending_dates += 1
            pending_rows += row_count
        elif status == "unsupported":
            unsupported_dates += 1
            unsupported_rows += row_count
        elif status == "proxy_only":
            proxy_only_dates += 1
            proxy_only_rows += row_count

        if bool(classification["affects_completed_stats"]):
            included_dates.append(trade_date)
        else:
            excluded_dates.append(trade_date)

        public_reason = cast(dict[str, Any] | None, classification.get("public_reason"))
        if public_reason is not None:
            date_reasons.append(public_reason)

    if completed_dates and not (pending_dates or unsupported_dates or proxy_only_dates):
        window_status = "valid"
    elif completed_dates:
        window_status = "partial"
    else:
        window_status = "unsupported"

    return {
        "status": window_status,
        "snapshot_from": trade_dates[0],
        "snapshot_to": trade_dates[-1],
        "replay_dates_total": len(trade_dates),
        "replay_dates_completed": completed_dates,
        "replay_dates_pending": pending_dates,
        "replay_dates_unsupported": unsupported_dates,
        "replay_dates_proxy_only": proxy_only_dates,
        "completed_rows": completed_rows,
        "pending_rows": pending_rows,
        "unsupported_rows": unsupported_rows,
        "proxy_only_rows": proxy_only_rows,
        "included_completed_stats_dates": included_dates,
        "excluded_from_completed_stats_dates": excluded_dates,
        "date_reasons": date_reasons,
    }


def _select_list(available_columns: set[str]) -> str:
    parts: list[str] = []
    for column in _SELECT_COLUMNS:
        if column.lower() in available_columns:
            parts.append(column)
        elif column == "signal_kind":
            parts.append("'stock_candidate' as signal_kind")
        else:
            parts.append(f"null as {column}")
    return ", ".join(parts)


def _load_backtest_window_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str | None,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> list[dict[str, Any]]:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if TABLE_HIST not in tables:
        return []
    available_columns = _available_columns(conn)
    where_clauses: list[str] = []
    bindings: list[object] = []
    if stock_code:
        where_clauses.append("stock_code = ?")
        bindings.append(stock_code)
    if snapshot_from:
        where_clauses.append("snapshot_as_of_date >= ?")
        bindings.append(snapshot_from)
    if snapshot_to:
        where_clauses.append("snapshot_as_of_date <= ?")
        bindings.append(snapshot_to)
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = conn.execute(
        f"""
        select {_select_list(available_columns)}
        from {TABLE_HIST}
        {sql_where}
        order by snapshot_as_of_date asc, candidate_rank asc
        """,
        bindings,
    ).fetchall()
    return [_normalize_row(row) for row in rows]


def _normalize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = {_SELECT_COLUMNS[i]: row[i] for i in range(len(_SELECT_COLUMNS))}
    if not str(item.get("signal_kind") or "").strip():
        item["signal_kind"] = "stock_candidate"
    return item


def _resolve_replay_trade_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    snapshot_from: str | None,
    snapshot_to: str | None,
    row_dates: list[str],
) -> list[str]:
    if TABLE_OBS not in tables:
        return row_dates
    if not snapshot_from and not snapshot_to:
        return row_dates

    where_clauses: list[str] = []
    bindings: list[object] = []
    if snapshot_from:
        where_clauses.append("trade_date >= ?")
        bindings.append(snapshot_from)
    if snapshot_to:
        where_clauses.append("trade_date <= ?")
        bindings.append(snapshot_to)
    sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
    observed = [
        str(row[0])[:10]
        for row in conn.execute(
            f"""
            select distinct trade_date
            from {TABLE_OBS}
            {sql_where}
            order by trade_date asc
            """,
            bindings,
        ).fetchall()
        if str(row[0] or "").strip()
    ]
    return observed or row_dates


def _build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_signal_kind: dict[str, int] = {}
    for item in items:
        signal_kind = str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1

    return {
        "row_count": len(items),
        "complete_count": _count_status(items, "complete"),
        "pending_count": _count_status(items, "pending"),
        "partial_halt_count": _count_status(items, "partial_halt"),
        "missing_forward_return_count": sum(
            1
            for item in items
            if item.get("return_1d") is None or item.get("return_5d") is None or item.get("return_20d") is None
        ),
        "avg_return_1d": _avg_present(items, "return_1d"),
        "avg_return_5d": _avg_present(items, "return_5d"),
        "avg_return_20d": _avg_present(items, "return_20d"),
        "by_signal_kind": by_signal_kind,
    }


def _classify_replay_date(
    *,
    trade_date: str,
    coverage: Any,
    rows: list[dict[str, Any]],
    history_table_present: bool,
) -> dict[str, Any]:
    if not history_table_present:
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"{TABLE_HIST} table absent; cannot distinguish no-signal dates from missing candidate-history materialization for {trade_date}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    missing_items = {str(item) for item in getattr(coverage, "missing_request_items", [])}
    if not bool(getattr(coverage, "full_coverage", False)):
        if "limit_up_quality:daily_limit_flags" in missing_items:
            return _classification(
                trade_date=trade_date,
                status="unsupported",
                reason_code="missing_daily_limit_flags",
                message=f"daily_limit_flags absent; stock_candidate and theme_breakout replay unsupported for {trade_date}.",
                affects_completed_stats=False,
                signal_kinds=_DEFAULT_SIGNAL_KINDS,
            )
        missing_detail = ", ".join(sorted(missing_items)) or str(getattr(coverage, "status", "not_materialized"))
        return _classification(
            trade_date=trade_date,
            status="unsupported",
            reason_code="missing_required_source_table",
            message=f"Required source coverage is incomplete for {trade_date}: {missing_detail}.",
            affects_completed_stats=False,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )
    if not rows:
        return _classification(
            trade_date=trade_date,
            status="completed",
            reason_code="no_strategy_signals",
            message=f"Full replay coverage produced no Livermore stock_candidate or theme_breakout rows for {trade_date}.",
            affects_completed_stats=True,
            signal_kinds=_DEFAULT_SIGNAL_KINDS,
        )

    signal_kinds = _signal_kinds_for_rows(rows)
    if any(str(row.get("data_status") or "").strip() == "pending" for row in rows):
        return _classification(
            trade_date=trade_date,
            status="pending",
            reason_code="forward_returns_pending",
            message=f"Forward return bars are not available yet; exclude {trade_date} from completed forward-return statistics.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
        )
    if any(
        str(row.get("signal_kind") or "").strip() == "theme_breakout"
        and str(row.get("theme_source_kind") or "").strip() == "proxy"
        for row in rows
    ):
        return _classification(
            trade_date=trade_date,
            status="proxy_only",
            reason_code="proxy_theme_only",
            message=f"Theme breakout replay for {trade_date} relies on proxy-only theme evidence.",
            affects_completed_stats=False,
            signal_kinds=signal_kinds,
        )
    return {
        "status": "completed",
        "affects_completed_stats": True,
        "public_reason": None,
    }


def _classification(
    *,
    trade_date: str,
    status: str,
    reason_code: str,
    message: str,
    affects_completed_stats: bool,
    signal_kinds: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "affects_completed_stats": affects_completed_stats,
        "public_reason": {
            "trade_date": trade_date,
            "status": status,
            "reason_code": reason_code,
            "message": message,
            "affects_completed_stats": affects_completed_stats,
            "signal_kinds": signal_kinds,
        },
    }


def _count_status(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if str(item.get("data_status") or "").strip() == status)


def _signal_kinds_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    signal_kinds = sorted(
        {
            str(row.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"
            for row in rows
        }
    )
    return signal_kinds or list(_DEFAULT_SIGNAL_KINDS)


def _avg_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = []
    for item in items:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _empty_backtest_window_summary(
    *,
    snapshot_from: str | None,
    snapshot_to: str | None,
) -> dict[str, Any]:
    return {
        "status": "unsupported",
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "replay_dates_total": 0,
        "replay_dates_completed": 0,
        "replay_dates_pending": 0,
        "replay_dates_unsupported": 0,
        "replay_dates_proxy_only": 0,
        "completed_rows": 0,
        "pending_rows": 0,
        "unsupported_rows": 0,
        "proxy_only_rows": 0,
        "included_completed_stats_dates": [],
        "excluded_from_completed_stats_dates": [],
        "date_reasons": [],
    }


def _first_nonempty_source_version(items: list[dict[str, Any]]) -> str:
    for row in items:
        text = str(row.get("source_version") or "").strip()
        if text:
            return text
    return EMPTY_SOURCE_VERSION


def _normalize_date_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]


def _first_nonempty_vendor_version(items: list[dict[str, Any]]) -> str | None:
    for row in items:
        text = str(row.get("vendor_version") or "").strip()
        if text:
            return text
    return None


def _wrap_empty_envelope(*, payload: dict[str, object]) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "stock_code": payload.get("stock_code"),
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "limit": payload.get("limit"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=0,
        result_payload=payload,
    )
