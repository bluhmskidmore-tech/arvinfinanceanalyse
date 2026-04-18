from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

from backend.app.schemas.source_preview import SourcePreviewHistoryPage, SourcePreviewPayload


def _row_table_name(source_family: str) -> str:
    if source_family == "zqtz":
        return "phase1_zqtz_preview_rows"
    if source_family == "tyw":
        return "phase1_tyw_preview_rows"
    if source_family == "pnl":
        return "phase1_pnl_preview_rows"
    if source_family in {"pnl_514", "pnl_516", "pnl_517"}:
        return "phase1_nonstd_pnl_preview_rows"
    raise ValueError(f"Unsupported source family: {source_family}")


def _trace_table_name(source_family: str) -> str:
    if source_family == "zqtz":
        return "phase1_zqtz_rule_traces"
    if source_family == "tyw":
        return "phase1_tyw_rule_traces"
    if source_family == "pnl":
        return "phase1_pnl_rule_traces"
    if source_family in {"pnl_514", "pnl_516", "pnl_517"}:
        return "phase1_nonstd_pnl_rule_traces"
    raise ValueError(f"Unsupported source family: {source_family}")


def source_preview_payload_version(payload: SourcePreviewPayload) -> str:
    return _join_source_versions(source.source_version for source in payload.sources)


def source_preview_history_version(payload: SourcePreviewHistoryPage) -> str:
    return _join_source_versions(row.source_version for row in payload.rows)


def _join_source_versions(versions) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for version in versions:
        normalized = str(version or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    if not ordered:
        return "sv_preview_empty"
    return "__".join(ordered)


def source_preview_batch_version(
    duckdb_path: str,
    source_family: str,
    ingest_batch_id: str | None,
) -> str:
    return _source_preview_batch_version_cached(
        str(duckdb_path),
        str(source_family),
        None if ingest_batch_id is None else str(ingest_batch_id),
    )


@lru_cache(maxsize=1024)
def _source_preview_batch_version_cached(
    duckdb_path: str,
    source_family: str,
    ingest_batch_id: str | None,
) -> str:
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return "sv_preview_empty"

    filters = ["source_family = ?"]
    params: list[object] = [source_family]
    if ingest_batch_id is not None:
        filters.append("ingest_batch_id = ?")
        params.append(ingest_batch_id)
    where_clause = f"where {' and '.join(filters)}"

    conn = duckdb.connect(str(duckdb_file), read_only=True)
    try:
        row = conn.execute(
            f"""
            select source_version
            from phase1_source_preview_summary
            {where_clause}
            order by batch_created_at desc, ingest_batch_id desc
            limit 1
            """,
            params,
        ).fetchone()
    except duckdb.Error:
        return "sv_preview_empty"
    finally:
        conn.close()

    if row is None:
        return "sv_preview_empty"
    return str(row[0] or "sv_preview_empty")


def _latest_batch_id_for_family(duckdb_path: str, source_family: str) -> str | None:
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        row = conn.execute(
            """
            select ingest_batch_id
            from phase1_source_preview_summary
            where source_family = ?
            order by batch_created_at desc, ingest_batch_id desc
            limit 1
            """,
            [source_family],
        ).fetchone()
    except duckdb.Error:
        return None
    finally:
        conn.close()
    return str(row[0]) if row and row[0] else None
