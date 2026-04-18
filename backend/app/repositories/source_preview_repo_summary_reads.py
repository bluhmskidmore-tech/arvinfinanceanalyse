from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.schemas.source_preview import (
    SourcePreviewHistoryPage,
    SourcePreviewPayload,
    SourcePreviewSummary,
)


def load_source_preview_payload(duckdb_path: str) -> SourcePreviewPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return SourcePreviewPayload(sources=[])

    conn = duckdb.connect(str(duckdb_file), read_only=True)
    try:
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
    except duckdb.Error:
        return SourcePreviewPayload(sources=[])
    finally:
        conn.close()

    grouped_counts: dict[tuple[str, str], dict[str, int]] = {}
    for ingest_batch_id, source_family, group_label, row_count in group_rows:
        grouped_counts.setdefault((str(ingest_batch_id), str(source_family)), {})[str(group_label)] = int(row_count)

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
                group_counts=grouped_counts.get((str(ingest_batch_id), str(source_family)), {}),
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
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return SourcePreviewHistoryPage(limit=limit, offset=offset, total_rows=0, rows=[])

    where_clause, params = _history_query_parts(source_family)
    conn = duckdb.connect(str(duckdb_file), read_only=True)
    try:
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
    except duckdb.Error:
        return SourcePreviewHistoryPage(limit=limit, offset=offset, total_rows=0, rows=[])
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
                source_family=str(source_family),
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
                source_family,
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


def _history_query_parts(source_family: str | None) -> tuple[str, list[object]]:
    if source_family is None:
        return "", []
    return "where source_family = ?", [source_family]
