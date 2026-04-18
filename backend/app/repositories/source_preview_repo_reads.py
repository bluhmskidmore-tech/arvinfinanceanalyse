"""Compatibility re-exports for split source preview read helpers."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

from backend.app.repositories import (
    source_preview_repo_row_reads as _row_reads_mod,
    source_preview_repo_summary_reads as _summary_reads_mod,
    source_preview_repo_versions as _versions_mod,
)
from backend.app.repositories.source_preview_repo_columns import (
    ROW_LABELS_BY_FAMILY,
    TRACE_LABELS,
    _build_preview_columns,
    _build_trace_columns,
    _preview_column_type,
)
from backend.app.schemas.source_preview import (
    PreviewRowPage,
    RuleTracePage,
    SourcePreviewHistoryPage,
    SourcePreviewPayload,
    SourcePreviewSummary,
)


class SourcePreviewReadError(RuntimeError):
    """Raised when preview DuckDB data exists but cannot be read truthfully."""


_preview_read_scope = _row_reads_mod._preview_read_scope
_read_paged_table = _row_reads_mod._read_paged_table
_history_query_parts = _summary_reads_mod._history_query_parts
_join_source_versions = _versions_mod._join_source_versions
_row_table_name = _versions_mod._row_table_name
_trace_table_name = _versions_mod._trace_table_name
source_preview_history_version = _versions_mod.source_preview_history_version
source_preview_payload_version = _versions_mod.source_preview_payload_version


def load_source_preview_payload(duckdb_path: str) -> SourcePreviewPayload:
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return SourcePreviewPayload(sources=[])

    conn = _connect_read_only(
        duckdb_file,
        "Source preview foundation read failed.",
    )
    try:
        if not _has_all_tables(
            conn,
            ("phase1_source_preview_summary", "phase1_source_preview_groups"),
            "Source preview foundation read failed.",
        ):
            return SourcePreviewPayload(sources=[])

        summary_rows = conn.execute(
            """
            with ranked as (
              select ingest_batch_id, batch_created_at, source_family, report_date, report_start_date, report_end_date,
                   report_granularity, source_file, total_rows,
                   manual_review_count, source_version, rule_version, preview_mode,
                   row_number() over (
                     partition by source_family
                     order by batch_created_at desc, ingest_batch_id desc
                   ) as rn
              from phase1_source_preview_summary
            )
            select ingest_batch_id, batch_created_at, source_family, report_date, report_start_date, report_end_date,
                   report_granularity, source_file, total_rows,
                   manual_review_count, source_version, rule_version, preview_mode
            from ranked
            where rn = 1
            order by source_family, report_date, source_file
            """
        ).fetchall()
        group_rows = conn.execute(
            """
            select ingest_batch_id, source_family, group_label, row_count
            from phase1_source_preview_groups
            order by ingest_batch_id, source_family, group_label
            """
        ).fetchall()
    except duckdb.Error as exc:
        raise SourcePreviewReadError("Source preview foundation read failed.") from exc
    finally:
        conn.close()

    grouped_counts: dict[tuple[str, str], dict[str, int]] = {}
    for ingest_batch_id, source_family, group_label, row_count in group_rows:
        grouped_counts.setdefault((str(ingest_batch_id), str(source_family)), {})[
            str(group_label)
        ] = int(row_count)

    return SourcePreviewPayload(
        sources=[
            SourcePreviewSummary(
                ingest_batch_id=str(ingest_batch_id) if ingest_batch_id else None,
                batch_created_at=str(batch_created_at) if batch_created_at else None,
                source_family=str(source_family),
                report_date=str(report_date) if report_date else None,
                report_start_date=str(report_start_date) if report_start_date else None,
                report_end_date=str(report_end_date) if report_end_date else None,
                report_granularity=str(report_granularity) if report_granularity else None,
                source_file=str(source_file),
                total_rows=int(total_rows),
                manual_review_count=int(manual_review_count),
                source_version=str(source_version),
                rule_version=str(rule_version),
                group_counts=grouped_counts.get(
                    (str(ingest_batch_id), str(source_family)),
                    {},
                ),
                preview_mode=str(preview_mode),
            )
            for (
                ingest_batch_id,
                batch_created_at,
                source_family,
                report_date,
                report_start_date,
                report_end_date,
                report_granularity,
                source_file,
                total_rows,
                manual_review_count,
                source_version,
                rule_version,
                preview_mode,
            ) in summary_rows
        ]
    )


def load_source_preview_history_payload(
    duckdb_path: str,
    limit: int,
    offset: int,
    source_family: str | None = None,
) -> SourcePreviewHistoryPage:
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return SourcePreviewHistoryPage(limit=limit, offset=offset, total_rows=0, rows=[])

    conn = _connect_read_only(
        duckdb_file,
        "Source preview history read failed.",
    )
    try:
        if not _has_all_tables(
            conn,
            ("phase1_source_preview_summary",),
            "Source preview history read failed.",
        ):
            return SourcePreviewHistoryPage(limit=limit, offset=offset, total_rows=0, rows=[])

        where_clause, params = _history_query_parts(source_family)
        total_rows = conn.execute(
            f"select count(*) from phase1_source_preview_summary {where_clause}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            select ingest_batch_id, batch_created_at, source_family, report_date, report_start_date, report_end_date,
                   report_granularity, source_file, total_rows, manual_review_count,
                   source_version, rule_version, preview_mode
            from phase1_source_preview_summary
            {where_clause}
            order by batch_created_at desc, ingest_batch_id desc, source_family asc
            limit ? offset ?
            """,
            [*params, limit, offset],
        ).fetchall()
    except duckdb.Error as exc:
        raise SourcePreviewReadError("Source preview history read failed.") from exc
    finally:
        conn.close()

    return SourcePreviewHistoryPage(
        limit=limit,
        offset=offset,
        total_rows=int(total_rows),
        rows=[
            SourcePreviewSummary(
                ingest_batch_id=str(ingest_batch_id) if ingest_batch_id else None,
                batch_created_at=str(batch_created_at) if batch_created_at else None,
                source_family=str(source_family_value),
                report_date=str(report_date) if report_date else None,
                report_start_date=str(report_start_date) if report_start_date else None,
                report_end_date=str(report_end_date) if report_end_date else None,
                report_granularity=str(report_granularity) if report_granularity else None,
                source_file=str(source_file),
                total_rows=int(total_rows_value),
                manual_review_count=int(manual_review_count),
                source_version=str(source_version),
                rule_version=str(rule_version),
                group_counts={},
                preview_mode=str(preview_mode),
            )
            for (
                ingest_batch_id,
                batch_created_at,
                source_family_value,
                report_date,
                report_start_date,
                report_end_date,
                report_granularity,
                source_file,
                total_rows_value,
                manual_review_count,
                source_version,
                rule_version,
                preview_mode,
            ) in rows
        ],
    )


def load_preview_rows(
    duckdb_path: str,
    source_family: str,
    limit: int,
    offset: int,
    ingest_batch_id: str | None = None,
) -> PreviewRowPage:
    empty_page = PreviewRowPage(
        source_family=source_family,
        ingest_batch_id=ingest_batch_id,
        limit=limit,
        offset=offset,
        total_rows=0,
        columns=[],
        rows=[],
    )
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return empty_page

    conn = _connect_read_only(
        duckdb_file,
        f"Source preview row read failed for {source_family}.",
    )
    try:
        table_name = _row_table_name(source_family)
        if not _has_all_tables(
            conn,
            (table_name,),
            f"Source preview row read failed for {source_family}.",
        ):
            return empty_page
        if ingest_batch_id is None and not _has_all_tables(
            conn,
            ("phase1_source_preview_summary",),
            f"Source preview row read failed for {source_family}.",
        ):
            return empty_page

        resolved_batch_id = ingest_batch_id
        filters: list[str] = []
        params: list[object] = []
        if resolved_batch_id is None:
            resolved_batch_id = _latest_batch_id_for_family_from_conn(conn, source_family)
        if resolved_batch_id is not None:
            filters.append("ingest_batch_id = ?")
            params.append(resolved_batch_id)
        if source_family in {"pnl_514", "pnl_516", "pnl_517"}:
            filters.append("source_family = ?")
            params.append(source_family)

        where_clause = f"where {' and '.join(filters)}" if filters else ""
        total_rows = conn.execute(
            f"select count(*) from {table_name} {where_clause}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            select *
            from {table_name}
            {where_clause}
            order by ingest_batch_id, row_locator
            limit ? offset ?
            """,
            [*params, limit, offset],
        ).fetchall()
        columns = [item[0] for item in conn.description]
    except duckdb.Error as exc:
        raise SourcePreviewReadError(
            f"Source preview row read failed for {source_family}.",
        ) from exc
    finally:
        conn.close()

    return PreviewRowPage(
        source_family=source_family,
        ingest_batch_id=resolved_batch_id,
        limit=limit,
        offset=offset,
        total_rows=int(total_rows),
        columns=_build_preview_columns(source_family, columns),
        rows=[dict(zip(columns, row, strict=False)) for row in rows],
    )


def load_rule_traces(
    duckdb_path: str,
    source_family: str,
    limit: int,
    offset: int,
    ingest_batch_id: str | None = None,
) -> RuleTracePage:
    empty_page = RuleTracePage(
        source_family=source_family,
        ingest_batch_id=ingest_batch_id,
        limit=limit,
        offset=offset,
        total_rows=0,
        columns=[],
        rows=[],
    )
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return empty_page

    conn = _connect_read_only(
        duckdb_file,
        f"Source preview trace read failed for {source_family}.",
    )
    try:
        table_name = _trace_table_name(source_family)
        if not _has_all_tables(
            conn,
            (table_name,),
            f"Source preview trace read failed for {source_family}.",
        ):
            return empty_page
        if ingest_batch_id is None and not _has_all_tables(
            conn,
            ("phase1_source_preview_summary",),
            f"Source preview trace read failed for {source_family}.",
        ):
            return empty_page

        resolved_batch_id = ingest_batch_id
        filters: list[str] = []
        params: list[object] = []
        if resolved_batch_id is None:
            resolved_batch_id = _latest_batch_id_for_family_from_conn(conn, source_family)
        if resolved_batch_id is not None:
            filters.append("ingest_batch_id = ?")
            params.append(resolved_batch_id)
        if source_family in {"pnl_514", "pnl_516", "pnl_517"}:
            filters.append("source_family = ?")
            params.append(source_family)

        where_clause = f"where {' and '.join(filters)}" if filters else ""
        total_rows = conn.execute(
            f"select count(*) from {table_name} {where_clause}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            select ingest_batch_id, row_locator, trace_step, field_name,
                   field_value, derived_label, manual_review_needed
            from {table_name}
            {where_clause}
            order by ingest_batch_id, row_locator, trace_step
            limit ? offset ?
            """,
            [*params, limit, offset],
        ).fetchall()
        columns = [item[0] for item in conn.description]
    except duckdb.Error as exc:
        raise SourcePreviewReadError(
            f"Source preview trace read failed for {source_family}.",
        ) from exc
    finally:
        conn.close()

    return RuleTracePage(
        source_family=source_family,
        ingest_batch_id=resolved_batch_id,
        limit=limit,
        offset=offset,
        total_rows=int(total_rows),
        columns=_build_trace_columns(columns),
        rows=[
            {
                "ingest_batch_id": str(batch_id),
                "row_locator": int(row_locator),
                "trace_step": int(trace_step),
                "field_name": str(field_name),
                "field_value": str(field_value),
                "derived_label": str(derived_label),
                "manual_review_needed": bool(manual_review_needed),
            }
            for (
                batch_id,
                row_locator,
                trace_step,
                field_name,
                field_value,
                derived_label,
                manual_review_needed,
            ) in rows
        ],
    )


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

    conn = _connect_read_only(
        duckdb_file,
        f"Source preview batch version read failed for {source_family}.",
    )
    try:
        if not _has_all_tables(
            conn,
            ("phase1_source_preview_summary",),
            f"Source preview batch version read failed for {source_family}.",
        ):
            return "sv_preview_empty"
        filters = ["source_family = ?"]
        params: list[object] = [source_family]
        if ingest_batch_id is not None:
            filters.append("ingest_batch_id = ?")
            params.append(ingest_batch_id)
        where_clause = f"where {' and '.join(filters)}"
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
    except duckdb.Error as exc:
        raise SourcePreviewReadError(
            f"Source preview batch version read failed for {source_family}.",
        ) from exc
    finally:
        conn.close()

    if row is None:
        return "sv_preview_empty"
    return str(row[0] or "sv_preview_empty")


def _latest_batch_id_for_family(duckdb_path: str, source_family: str) -> str | None:
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return None

    conn = _connect_read_only(
        duckdb_file,
        f"Source preview batch lookup failed for {source_family}.",
    )
    try:
        if not _has_all_tables(
            conn,
            ("phase1_source_preview_summary",),
            f"Source preview batch lookup failed for {source_family}.",
        ):
            return None
        return _latest_batch_id_for_family_from_conn(conn, source_family)
    finally:
        conn.close()


def _connect_read_only(duckdb_file: Path, error_message: str):
    try:
        return duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error as exc:
        raise SourcePreviewReadError(error_message) from exc


def _has_all_tables(conn, table_names: tuple[str, ...], error_message: str) -> bool:
    try:
        existing = {
            str(row[0])
            for row in conn.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = current_schema()
                """
            ).fetchall()
        }
    except duckdb.Error as exc:
        raise SourcePreviewReadError(error_message) from exc
    return all(table_name in existing for table_name in table_names)


def _latest_batch_id_for_family_from_conn(conn, source_family: str) -> str | None:
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
    return str(row[0]) if row and row[0] else None

__all__ = [
    "ROW_LABELS_BY_FAMILY",
    "TRACE_LABELS",
    "SourcePreviewReadError",
    "load_source_preview_payload",
    "load_source_preview_history_payload",
    "load_preview_rows",
    "load_rule_traces",
    "_history_query_parts",
    "_preview_read_scope",
    "_read_paged_table",
    "_build_preview_columns",
    "_build_trace_columns",
    "_preview_column_type",
    "_row_table_name",
    "_trace_table_name",
    "source_preview_payload_version",
    "source_preview_history_version",
    "_join_source_versions",
    "source_preview_batch_version",
    "_source_preview_batch_version_cached",
    "_latest_batch_id_for_family",
]
