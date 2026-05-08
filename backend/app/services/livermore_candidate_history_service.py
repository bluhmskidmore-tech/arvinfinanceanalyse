from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

import duckdb

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
            select {_select_list()}
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


def _select_list() -> str:
    return ", ".join(_SELECT_COLUMNS)


def _normalize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {_SELECT_COLUMNS[i]: row[i] for i in range(len(_SELECT_COLUMNS))}


def _first_nonempty_source_version(items: list[dict[str, Any]]) -> str:
    for row in items:
        text = str(row.get("source_version") or "").strip()
        if text:
            return text
    return EMPTY_SOURCE_VERSION


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
