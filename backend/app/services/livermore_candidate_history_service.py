from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
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
STRATEGY_SCORE_RESULT_KIND = "market_data.livermore.strategy_score"
STRATEGY_SCORE_RULE_VERSION = "rv_livermore_strategy_score_v1"
STRATEGY_SCORE_CACHE_VERSION = "cv_livermore_strategy_score_v1"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
_DEFAULT_SIGNAL_KINDS = ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"]
_STRATEGY_LABELS = {
    "stock_candidate": "趋势突破",
    "factor_screen": "多因子",
    "theme_breakout": "题材突变",
    "mean_reversion": "超跌反弹",
}
_HORIZON_LABELS = {
    "return_1d": "T+1",
    "return_5d": "T+5",
    "return_20d": "T+20",
}

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

    backtest_window_summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=duckdb_path,
        stock_code=trimmed_code,
        snapshot_from=snapshot_from,
        snapshot_to=snapshot_to,
    )
    result_payload = {
        "items": items,
        "summary": _build_summary(items, backtest_window_summary=backtest_window_summary),
        "backtest_window_summary": backtest_window_summary,
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


def livermore_candidate_history_strategy_score_envelope(
    *,
    duckdb_path: str,
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
) -> dict[str, object]:
    """Read persisted candidate history and score strategies by market state; DuckDB SELECT only."""
    normalized_horizon = primary_horizon if primary_horizon in _HORIZON_LABELS else "return_5d"
    path = Path(duckdb_path)
    if not path.is_file():
        resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        payload = _build_strategy_score_payload(
            items=[],
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
            current_market_state=current_market_state,
            min_sample=min_sample,
            primary_horizon=normalized_horizon,
            backtest_window_summary=_empty_backtest_window_summary(
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
            ),
        )
        return _wrap_strategy_score_envelope(
            payload=payload,
            source_version=EMPTY_SOURCE_VERSION,
            vendor_version=EMPTY_VENDOR_VERSION,
            evidence_rows=0,
            quality_flag="warning",
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            resolved_to = _normalize_date_text(snapshot_to) or date.today().isoformat()
            resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
            payload = _build_strategy_score_payload(
                items=[],
                snapshot_from=resolved_from,
                snapshot_to=resolved_to,
                current_market_state=current_market_state,
                min_sample=min_sample,
                primary_horizon=normalized_horizon,
                backtest_window_summary=_empty_backtest_window_summary(
                    snapshot_from=resolved_from,
                    snapshot_to=resolved_to,
                ),
            )
            return _wrap_strategy_score_envelope(
                payload=payload,
                source_version=EMPTY_SOURCE_VERSION,
                vendor_version=EMPTY_VENDOR_VERSION,
                evidence_rows=0,
                quality_flag="warning",
            )

        resolved_to = _normalize_date_text(snapshot_to) or _latest_history_snapshot_date(conn) or date.today().isoformat()
        resolved_from = _normalize_date_text(snapshot_from) or _default_snapshot_from(resolved_to)
        items = _load_backtest_window_rows(
            conn,
            stock_code=None,
            snapshot_from=resolved_from,
            snapshot_to=resolved_to,
        )
    finally:
        conn.close()

    backtest_window_summary = livermore_candidate_history_backtest_window_summary(
        duckdb_path=duckdb_path,
        stock_code=None,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
    )
    if backtest_window_summary.get("status") in {"valid", "partial"}:
        scoring_items = _horizon_usable_items(items, backtest_window_summary=backtest_window_summary)
    else:
        scoring_items = items
    payload = _build_strategy_score_payload(
        items=scoring_items,
        snapshot_from=resolved_from,
        snapshot_to=resolved_to,
        current_market_state=current_market_state,
        min_sample=min_sample,
        primary_horizon=normalized_horizon,
        backtest_window_summary=backtest_window_summary,
    )
    return _wrap_strategy_score_envelope(
        payload=payload,
        source_version=_first_nonempty_source_version(scoring_items or items),
        vendor_version=_first_nonempty_vendor_version(scoring_items or items) or EMPTY_VENDOR_VERSION,
        evidence_rows=len(scoring_items),
        quality_flag="ok" if scoring_items else "warning",
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


def _build_summary(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
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
        "horizon_stats": _build_horizon_stats(items),
        "by_signal_kind": _count_by_signal_kind(items),
        "by_signal_kind_horizon_stats": _build_signal_kind_horizon_stats(items),
    }
    if backtest_window_summary is not None and backtest_window_summary.get("status") in {"valid", "partial"}:
        horizon_usable_items = _horizon_usable_items(items, backtest_window_summary=backtest_window_summary)
        summary["decision_usable_stats"] = _build_decision_usable_stats(
            items,
            backtest_window_summary=backtest_window_summary,
        )
        summary["horizon_usable_stats"] = _build_horizon_stats(horizon_usable_items)
        summary["by_signal_kind_horizon_usable_stats"] = _build_signal_kind_horizon_stats(horizon_usable_items)
        summary["by_market_state_signal_kind_horizon_stats"] = _build_market_state_signal_kind_horizon_stats(
            horizon_usable_items
        )
    return summary


def _build_decision_usable_stats(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any],
) -> dict[str, Any]:
    included_dates = _decision_usable_dates(backtest_window_summary)
    usable_items = [
        item
        for item in items
        if str(item.get("snapshot_as_of_date") or "")[:10] in included_dates
        and str(item.get("data_status") or "").strip() == "complete"
    ]
    return {
        "row_count": len(usable_items),
        "complete_row_count": _count_status(usable_items, "complete"),
        "pending_row_count": _count_status(usable_items, "pending"),
        "partial_halt_row_count": _count_status(usable_items, "partial_halt"),
        "missing_forward_return_count": sum(
            1
            for item in usable_items
            if item.get("return_1d") is None or item.get("return_5d") is None or item.get("return_20d") is None
        ),
        "avg_return_1d": _avg_present(usable_items, "return_1d"),
        "avg_return_5d": _avg_present(usable_items, "return_5d"),
        "avg_return_20d": _avg_present(usable_items, "return_20d"),
        "win_rate_1d": _win_rate_present(usable_items, "return_1d"),
        "win_rate_5d": _win_rate_present(usable_items, "return_5d"),
        "win_rate_20d": _win_rate_present(usable_items, "return_20d"),
        "by_signal_kind": _count_by_signal_kind(usable_items),
        "by_signal_kind_horizon_stats": _build_signal_kind_horizon_stats(usable_items),
        "included_snapshot_dates": sorted({str(item.get("snapshot_as_of_date") or "")[:10] for item in usable_items}),
        "excluded_snapshot_dates": _decision_excluded_dates(
            items,
            usable_items=usable_items,
            included_dates=included_dates,
        ),
    }


def _decision_usable_dates(backtest_window_summary: dict[str, Any]) -> set[str]:
    return {
        str(item)[:10]
        for item in backtest_window_summary.get("included_completed_stats_dates", [])
        if str(item or "").strip()
    }


def _horizon_usable_items(
    items: list[dict[str, Any]],
    *,
    backtest_window_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    usable_dates = _decision_usable_dates(backtest_window_summary)
    for reason in backtest_window_summary.get("date_reasons", []):
        if not isinstance(reason, dict):
            continue
        if str(reason.get("status") or "").strip() not in {"completed", "pending"}:
            continue
        trade_date = str(reason.get("trade_date") or "").strip()[:10]
        if trade_date:
            usable_dates.add(trade_date)
    return [
        item
        for item in items
        if str(item.get("snapshot_as_of_date") or "").strip()[:10] in usable_dates
    ]


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
        if missing_items == {"limit_up_quality:daily_limit_flags"}:
            return _classification(
                trade_date=trade_date,
                status="unsupported",
                reason_code="missing_daily_limit_flags",
                message=f"daily_limit_flags absent; Livermore strategy replay unsupported for {trade_date}.",
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
            message=f"Full replay coverage produced no Livermore strategy signal rows for {trade_date}.",
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


def _count_by_signal_kind(items: list[dict[str, Any]]) -> dict[str, int]:
    by_signal_kind: dict[str, int] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        by_signal_kind[signal_kind] = by_signal_kind.get(signal_kind, 0) + 1
    return by_signal_kind


def _signal_kinds_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    signal_kinds = sorted({_normalized_signal_kind(row) for row in rows})
    return signal_kinds or list(_DEFAULT_SIGNAL_KINDS)


def _avg_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _win_rate_present(items: list[dict[str, Any]], key: str) -> float | None:
    values = _present_float_values(items, key)
    if not values:
        return None
    return round(sum(1 for value in values if value > 0) / len(values), 6)


def _build_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {key: _horizon_stat(items, key) for key in ("return_1d", "return_5d", "return_20d")}


def _build_signal_kind_horizon_stats(items: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(signal_kind, []).append(item)
    return {signal_kind: _build_horizon_stats(rows) for signal_kind, rows in sorted(grouped.items())}


def _build_market_state_signal_kind_horizon_stats(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in items:
        market_state = _market_state_from_signal_evidence(item)
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(item)
    return {
        market_state: {
            signal_kind: _build_horizon_stats(rows)
            for signal_kind, rows in sorted(signal_groups.items())
        }
        for market_state, signal_groups in sorted(grouped.items())
    }


def _build_strategy_score_payload(
    *,
    items: list[dict[str, Any]],
    snapshot_from: str | None,
    snapshot_to: str | None,
    current_market_state: str | None,
    min_sample: int,
    primary_horizon: str,
    backtest_window_summary: dict[str, Any],
) -> dict[str, Any]:
    effective_min_sample = max(1, int(min_sample))
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in items:
        market_state = _market_state_from_signal_evidence(item)
        signal_kind = _normalized_signal_kind(item)
        grouped.setdefault(market_state, {}).setdefault(signal_kind, []).append(item)

    rows: list[dict[str, Any]] = []
    for market_state, signal_groups in sorted(grouped.items()):
        for signal_kind, signal_items in sorted(signal_groups.items()):
            rows.append(
                _strategy_score_row(
                    market_state=market_state,
                    signal_kind=signal_kind,
                    items=signal_items,
                    min_sample=effective_min_sample,
                    primary_horizon=primary_horizon,
                )
            )

    rows = _rank_strategy_score_rows(rows)
    normalized_current_state = _normalized_text(current_market_state) or None
    current_rows = _sort_strategy_score_rows(
        [row for row in rows if normalized_current_state and row["market_state"] == normalized_current_state]
    )
    if normalized_current_state and not current_rows:
        current_rows = [
            _empty_strategy_score_row(
                market_state=normalized_current_state,
                signal_kind=signal_kind,
                min_sample=effective_min_sample,
                primary_horizon=primary_horizon,
            )
            for signal_kind in _DEFAULT_SIGNAL_KINDS
        ]
    if normalized_current_state and not any(row["sample_status"] == "sufficient" for row in current_rows):
        current_rows = [
            {
                **row,
                "reason": _current_state_insufficient_reason(
                    row["stats"][primary_horizon]["available_count"],
                    min_sample=effective_min_sample,
                    primary_horizon=primary_horizon,
                ),
            }
            for row in current_rows
        ]

    return {
        "as_of_date": snapshot_to,
        "snapshot_from": snapshot_from,
        "snapshot_to": snapshot_to,
        "primary_horizon": primary_horizon,
        "min_sample": effective_min_sample,
        "current_market_state": normalized_current_state,
        "backtest_window_summary": backtest_window_summary,
        "rows": _sort_strategy_score_rows(rows),
        "current_market_state_rows": current_rows,
    }


def _strategy_score_row(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    stats = _build_horizon_stats(items)
    diagnostics = _strategy_score_diagnostics(
        market_state=market_state,
        signal_kind=signal_kind,
        items=items,
        stats=stats,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    primary_stats = stats[primary_horizon]
    available_count = int(primary_stats["available_count"])
    if available_count < min_sample:
        return {
            "market_state": market_state,
            "signal_kind": signal_kind,
            "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
            "sample_status": "insufficient",
            "priority_score": None,
            "priority_rank": None,
            "priority_label": "样本不足",
            "reason": _sample_insufficient_reason(
                available_count,
                min_sample=min_sample,
                primary_horizon=primary_horizon,
            ),
            "stats": stats,
            "diagnostics": diagnostics,
        }

    win_rate = float(primary_stats["win_rate"])
    avg_return = float(primary_stats["avg_return"])
    priority_score = round(win_rate * 100 + avg_return * 100, 2)
    priority_label = "降权观察" if win_rate < 0.5 or avg_return <= 0 else "优先复核"
    return {
        "market_state": market_state,
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        "sample_status": "sufficient",
        "priority_score": priority_score,
        "priority_rank": None,
        "priority_label": priority_label,
        "reason": _score_reason(
            available_count=available_count,
            win_rate=win_rate,
            avg_return=avg_return,
            priority_score=priority_score,
            priority_label=priority_label,
            primary_horizon=primary_horizon,
        ),
        "stats": stats,
        "diagnostics": diagnostics,
    }


def _empty_strategy_score_row(
    *,
    market_state: str,
    signal_kind: str,
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    stats = _empty_horizon_stats_by_key()
    return {
        "market_state": market_state,
        "signal_kind": signal_kind,
        "strategy_label": _STRATEGY_LABELS.get(signal_kind, signal_kind),
        "sample_status": "insufficient",
        "priority_score": None,
        "priority_rank": None,
        "priority_label": "样本不足",
        "reason": _sample_insufficient_reason(0, min_sample=min_sample, primary_horizon=primary_horizon),
        "stats": stats,
        "diagnostics": _empty_strategy_score_diagnostics(),
    }


def _rank_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_state: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_state.setdefault(str(row["market_state"]), []).append(row)
    ranked_rows: list[dict[str, Any]] = []
    for state_rows in rows_by_state.values():
        rank = 1
        for row in _sort_strategy_score_rows(state_rows):
            if row["sample_status"] == "sufficient":
                row = {**row, "priority_rank": rank}
                rank += 1
            ranked_rows.append(row)
    return ranked_rows


def _sort_strategy_score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[str, int, float, int, str]:
        score = row.get("priority_score")
        signal_kind = str(row.get("signal_kind") or "")
        strategy_order = _DEFAULT_SIGNAL_KINDS.index(signal_kind) if signal_kind in _DEFAULT_SIGNAL_KINDS else 999
        return (
            str(row.get("market_state") or ""),
            0 if score is not None else 1,
            -(float(score) if score is not None else -1.0),
            strategy_order,
            signal_kind,
        )

    return sorted(rows, key=sort_key)


def _empty_strategy_score_diagnostics() -> dict[str, Any]:
    return {
        "priority_scope": None,
        "priority_scope_label": None,
        "priority_scope_stats": None,
        "maturity": _empty_maturity_diagnostics(),
        "rank_buckets": [],
        "risk_flags": [],
    }


def _strategy_score_diagnostics(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    stats: dict[str, dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> dict[str, Any]:
    diagnostics = _empty_strategy_score_diagnostics()
    rank_buckets = _rank_bucket_diagnostics(
        market_state=market_state,
        signal_kind=signal_kind,
        items=items,
        min_sample=min_sample,
        primary_horizon=primary_horizon,
    )
    diagnostics["rank_buckets"] = rank_buckets
    if market_state == "OVERHEAT" and signal_kind == "factor_screen" and any(
        int(bucket["rank_from"]) > 10 for bucket in rank_buckets
    ):
        priority_scope_items = [
            item for item in items if (rank := _candidate_rank(item)) is not None and rank <= 10
        ]
        diagnostics["priority_scope"] = "rank<=10"
        diagnostics["priority_scope_label"] = "前10名优先复核"
        diagnostics["priority_scope_stats"] = _build_horizon_stats(priority_scope_items)
        diagnostics["maturity"] = _maturity_diagnostics(priority_scope_items, primary_horizon=primary_horizon)
    else:
        diagnostics["maturity"] = _maturity_diagnostics(items, primary_horizon=primary_horizon)
    diagnostics["risk_flags"] = _strategy_score_risk_flags(
        market_state=market_state,
        signal_kind=signal_kind,
        stats=stats,
        min_sample=min_sample,
    )
    return diagnostics


def _rank_bucket_diagnostics(
    *,
    market_state: str,
    signal_kind: str,
    items: list[dict[str, Any]],
    min_sample: int,
    primary_horizon: str,
) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for rank_from, rank_to, label in _rank_bucket_ranges(signal_kind):
        bucket_items = [
            item
            for item in items
            if (rank := _candidate_rank(item)) is not None and rank >= rank_from and (rank_to is None or rank <= rank_to)
        ]
        if not bucket_items:
            continue
        bucket_stats = _build_horizon_stats(bucket_items)
        primary_stats = bucket_stats[primary_horizon]
        available_count = int(primary_stats["available_count"])
        priority_label, included_in_priority, reason = _rank_bucket_priority(
            market_state=market_state,
            signal_kind=signal_kind,
            rank_from=rank_from,
            available_count=available_count,
            primary_stats=primary_stats,
            min_sample=min_sample,
            primary_horizon=primary_horizon,
        )
        buckets.append(
            {
                "label": label,
                "rank_from": rank_from,
                "rank_to": rank_to,
                "sample_status": "sufficient" if available_count >= min_sample else "insufficient",
                "priority_label": priority_label,
                "included_in_priority": included_in_priority,
                "reason": reason,
                "stats": bucket_stats,
            }
        )
    return buckets


def _rank_bucket_ranges(signal_kind: str) -> list[tuple[int, int | None, str]]:
    if signal_kind == "factor_screen":
        return [(1, 5, "1-5"), (6, 10, "6-10"), (11, 20, "11-20"), (21, None, "21+")]
    if signal_kind == "stock_candidate":
        return [(1, 3, "1-3"), (4, 6, "4-6"), (7, 10, "7-10"), (11, None, "11+")]
    return []


def _rank_bucket_priority(
    *,
    market_state: str,
    signal_kind: str,
    rank_from: int,
    available_count: int,
    primary_stats: dict[str, Any],
    min_sample: int,
    primary_horizon: str,
) -> tuple[str, bool, str]:
    if available_count < min_sample:
        return (
            "样本不足",
            False,
            _sample_insufficient_reason(
                available_count,
                min_sample=min_sample,
                primary_horizon=primary_horizon,
            ),
        )
    if market_state == "OVERHEAT" and signal_kind == "factor_screen" and rank_from > 10:
        return (
            "降权观察",
            False,
            "OVERHEAT 状态下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。",
        )
    win_rate = float(primary_stats["win_rate"])
    avg_return = float(primary_stats["avg_return"])
    if win_rate < 0.5 or avg_return <= 0:
        return (
            "降权观察",
            False,
            f"{_HORIZON_LABELS[primary_horizon]} 胜率低于 50% 或均值不为正，降权观察。",
        )
    return (
        "优先复核",
        True,
        f"{_HORIZON_LABELS[primary_horizon]} 样本满足阈值且均值为正，仅用于优先复核排序。",
    )


def _strategy_score_risk_flags(
    *,
    market_state: str,
    signal_kind: str,
    stats: dict[str, dict[str, Any]],
    min_sample: int,
) -> list[dict[str, Any]]:
    if market_state != "OVERHEAT" or signal_kind != "stock_candidate":
        return []
    t20_stats = stats["return_20d"]
    available_count = int(t20_stats["available_count"])
    if available_count < min_sample:
        return []
    win_rate = t20_stats["win_rate"]
    avg_return = t20_stats["avg_return"]
    if win_rate is None or avg_return is None or (float(win_rate) >= 0.5 and float(avg_return) > 0):
        return []
    return [
        {
            "kind": "long_window_risk",
            "label": "长窗口风险",
            "horizon": "return_20d",
            "reason": (
                f"T+20 样本 {available_count}，胜率 {float(win_rate) * 100:.1f}%，"
                f"均值 {float(avg_return) * 100:+.2f}%，仅按短窗口复核。"
            ),
            "stats": t20_stats,
        }
    ]


def _empty_maturity_diagnostics() -> dict[str, Any]:
    return {
        "status": "narrow",
        "label": "样本偏窄",
        "reason": "T+5 已成熟快照 0/4，等待更多成熟日。",
        "min_mature_snapshot_count": 4,
        "mature_snapshot_count": 0,
        "snapshot_stats": [],
        "tracked_snapshots": [],
        "worst_snapshot": None,
    }


def _maturity_diagnostics(
    items: list[dict[str, Any]],
    *,
    primary_horizon: str,
    min_mature_snapshot_count: int = 4,
) -> dict[str, Any]:
    snapshot_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date or item.get(primary_horizon) is None:
            continue
        snapshot_groups.setdefault(snapshot_date, []).append(item)

    snapshot_stats = [
        _snapshot_maturity_stat(snapshot_date, snapshot_items, primary_horizon=primary_horizon)
        for snapshot_date, snapshot_items in sorted(snapshot_groups.items())
    ]
    mature_count = len(snapshot_stats)
    status = "sufficient" if mature_count >= min_mature_snapshot_count else "narrow"
    label = "成熟快照充足" if status == "sufficient" else "样本偏窄"
    horizon_label = _HORIZON_LABELS[primary_horizon]
    reason = (
        f"{horizon_label} 已成熟快照 {mature_count}/{min_mature_snapshot_count}，"
        + ("可作为强优先复核。" if status == "sufficient" else "等待更多成熟日。")
    )
    return {
        "status": status,
        "label": label,
        "reason": reason,
        "min_mature_snapshot_count": min_mature_snapshot_count,
        "mature_snapshot_count": mature_count,
        "snapshot_stats": snapshot_stats,
        "tracked_snapshots": _tracked_snapshot_stats(items),
        "worst_snapshot": _worst_snapshot_stat(snapshot_stats),
    }


def _tracked_snapshot_stats(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        snapshot_groups.setdefault(snapshot_date, []).append(item)
    return [
        _tracked_snapshot_stat(snapshot_date, snapshot_items)
        for snapshot_date, snapshot_items in sorted(snapshot_groups.items())
    ]


def _tracked_snapshot_stat(snapshot_date: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_count = len(items)
    horizons: dict[str, dict[str, Any]] = {}
    for horizon in _HORIZON_LABELS:
        stat = _horizon_stat(items, horizon)
        available_count = int(stat["available_count"])
        if available_count >= candidate_count and candidate_count > 0:
            status = "complete"
        elif available_count > 0:
            status = "partial"
        else:
            status = "pending"
        horizons[horizon] = {**stat, "status": status}
    return {
        "snapshot_as_of_date": snapshot_date,
        "candidate_count": candidate_count,
        "horizons": horizons,
    }


def _snapshot_maturity_stat(
    snapshot_date: str,
    items: list[dict[str, Any]],
    *,
    primary_horizon: str,
) -> dict[str, Any]:
    stat = _horizon_stat(items, primary_horizon)
    return {
        "snapshot_as_of_date": snapshot_date,
        "available_count": stat["available_count"],
        "positive_count": stat["positive_count"],
        "non_positive_count": stat["non_positive_count"],
        "avg_return": stat["avg_return"],
        "win_rate": stat["win_rate"],
    }


def _worst_snapshot_stat(snapshot_stats: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not snapshot_stats:
        return None
    return min(
        snapshot_stats,
        key=lambda stat: (
            float(stat["win_rate"]) if stat.get("win_rate") is not None else -1.0,
            float(stat["avg_return"]) if stat.get("avg_return") is not None else -1.0,
            str(stat.get("snapshot_as_of_date") or ""),
        ),
    )


def _candidate_rank(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("candidate_rank"))
    except (TypeError, ValueError):
        return None


def _empty_horizon_stats_by_key() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "available_count": 0,
            "missing_count": 0,
            "positive_count": 0,
            "non_positive_count": 0,
            "avg_return": None,
            "win_rate": None,
        }
        for key in _HORIZON_LABELS
    }


def _sample_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，样本不足，仅作观察。"


def _current_state_insufficient_reason(available_count: int, *, min_sample: int, primary_horizon: str) -> str:
    return f"当前状态样本不足：{_HORIZON_LABELS[primary_horizon]} 可用样本 {available_count}/{min_sample}，仅作观察。"


def _score_reason(
    *,
    available_count: int,
    win_rate: float,
    avg_return: float,
    priority_score: float,
    priority_label: str,
    primary_horizon: str,
) -> str:
    horizon_label = _HORIZON_LABELS[primary_horizon]
    base = (
        f"{horizon_label} 样本 {available_count}，胜率 {win_rate * 100:.1f}%，"
        f"均值 {avg_return * 100:+.2f}%，评分 {priority_score:.2f}。"
    )
    if priority_label == "降权观察":
        return base + "胜率低于 50% 或均值不为正，降权观察。"
    return base + "仅用于优先复核排序。"


def _horizon_stat(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = _present_float_values(items, key)
    positive_count = sum(1 for value in values if value > 0)
    return {
        "available_count": len(values),
        "missing_count": len(items) - len(values),
        "positive_count": positive_count,
        "non_positive_count": len(values) - positive_count,
        "avg_return": round(sum(values) / len(values), 6) if values else None,
        "win_rate": round(positive_count / len(values), 6) if values else None,
    }


def _present_float_values(items: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for item in items:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _normalized_signal_kind(item: dict[str, Any]) -> str:
    return str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate"


def _market_state_from_signal_evidence(item: dict[str, Any]) -> str:
    evidence = _parse_signal_evidence_json(item.get("signal_evidence_json"))
    for key in ("market_state", "market_state_kind", "market_gate_state"):
        value = _normalized_text(evidence.get(key))
        if value:
            return value
    market_gate = evidence.get("market_gate")
    if isinstance(market_gate, dict):
        value = _normalized_text(market_gate.get("state"))
        if value:
            return value
    return "unknown"


def _parse_signal_evidence_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _decision_excluded_dates(
    items: list[dict[str, Any]],
    *,
    usable_items: list[dict[str, Any]],
    included_dates: set[str],
) -> list[str]:
    usable_keys = {
        (
            str(item.get("snapshot_as_of_date") or "")[:10],
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        for item in usable_items
    }
    excluded_dates: set[str] = set()
    for item in items:
        snapshot_date = str(item.get("snapshot_as_of_date") or "")[:10]
        if not snapshot_date:
            continue
        row_key = (
            snapshot_date,
            str(item.get("stock_code") or "").strip(),
            str(item.get("signal_kind") or "stock_candidate").strip() or "stock_candidate",
        )
        if snapshot_date not in included_dates or row_key not in usable_keys:
            excluded_dates.add(snapshot_date)
    return sorted(excluded_dates)


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


def _default_snapshot_from(snapshot_to: str) -> str:
    try:
        parsed = date.fromisoformat(snapshot_to[:10])
    except ValueError:
        parsed = date.today()
    return (parsed - timedelta(days=180)).isoformat()


def _latest_history_snapshot_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(f"select max(snapshot_as_of_date) from {TABLE_HIST}").fetchone()
    if not row:
        return None
    return _normalize_date_text(row[0])


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


def _wrap_strategy_score_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_strategy_score_{uuid.uuid4().hex[:12]}",
        result_kind=STRATEGY_SCORE_RESULT_KIND,
        cache_version=STRATEGY_SCORE_CACHE_VERSION,
        source_version=source_version,
        rule_version=STRATEGY_SCORE_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "current_market_state": payload.get("current_market_state"),
            "min_sample": payload.get("min_sample"),
            "primary_horizon": payload.get("primary_horizon"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )
