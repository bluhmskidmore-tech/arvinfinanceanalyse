from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.repositories.source_preview_repo_columns import (
    _build_preview_columns,
    _build_trace_columns,
)
from backend.app.repositories.source_preview_repo_versions import (
    _latest_batch_id_for_family,
    _row_table_name,
    _trace_table_name,
)
from backend.app.schemas.source_preview import PreviewRowPage, RuleTracePage


def load_preview_rows(
    duckdb_path: str,
    source_family: str,
    limit: int,
    offset: int,
    ingest_batch_id: str | None = None,
) -> PreviewRowPage:
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return PreviewRowPage(
            source_family=source_family,
            ingest_batch_id=ingest_batch_id,
            limit=limit,
            offset=offset,
            total_rows=0,
            columns=[],
            rows=[],
        )

    table_name = _row_table_name(source_family)
    resolved_batch_id, where_clause, params = _preview_read_scope(
        duckdb_path=str(duckdb_file),
        source_family=source_family,
        ingest_batch_id=ingest_batch_id,
    )

    result = _read_paged_table(
        duckdb_file=duckdb_file,
        table_name=table_name,
        where_clause=where_clause,
        params=params,
        select_clause="select *",
        order_clause="order by ingest_batch_id, row_locator",
        limit=limit,
        offset=offset,
    )
    if result is None:
        return PreviewRowPage(
            source_family=source_family,
            ingest_batch_id=ingest_batch_id,
            limit=limit,
            offset=offset,
            total_rows=0,
            columns=[],
            rows=[],
        )

    total_rows, rows, columns = result

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
    duckdb_file = Path(str(duckdb_path))
    if not duckdb_file.exists():
        return RuleTracePage(
            source_family=source_family,
            ingest_batch_id=ingest_batch_id,
            limit=limit,
            offset=offset,
            total_rows=0,
            columns=[],
            rows=[],
        )

    table_name = _trace_table_name(source_family)
    resolved_batch_id, where_clause, params = _preview_read_scope(
        duckdb_path=str(duckdb_file),
        source_family=source_family,
        ingest_batch_id=ingest_batch_id,
    )

    result = _read_paged_table(
        duckdb_file=duckdb_file,
        table_name=table_name,
        where_clause=where_clause,
        params=params,
        select_clause=(
            "select ingest_batch_id, row_locator, trace_step, field_name, "
            "field_value, derived_label, manual_review_needed"
        ),
        order_clause="order by ingest_batch_id, row_locator, trace_step",
        limit=limit,
        offset=offset,
    )
    if result is None:
        return RuleTracePage(
            source_family=source_family,
            ingest_batch_id=ingest_batch_id,
            limit=limit,
            offset=offset,
            total_rows=0,
            columns=[],
            rows=[],
        )

    total_rows, rows, columns = result

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
            for batch_id, row_locator, trace_step, field_name, field_value, derived_label, manual_review_needed in rows
        ],
    )


def _preview_read_scope(
    duckdb_path: str,
    source_family: str,
    ingest_batch_id: str | None,
) -> tuple[str | None, str, list[object]]:
    resolved_batch_id = ingest_batch_id
    filters: list[str] = []
    params: list[object] = []

    if resolved_batch_id is None:
        resolved_batch_id = _latest_batch_id_for_family(duckdb_path, source_family)
    if resolved_batch_id is not None:
        filters.append("ingest_batch_id = ?")
        params.append(resolved_batch_id)
    if source_family in {"pnl_514", "pnl_516", "pnl_517"}:
        filters.append("source_family = ?")
        params.append(source_family)

    where_clause = f"where {' and '.join(filters)}" if filters else ""
    return resolved_batch_id, where_clause, params


def _read_paged_table(
    duckdb_file: Path,
    table_name: str,
    where_clause: str,
    params: list[object],
    select_clause: str,
    order_clause: str,
    limit: int,
    offset: int,
) -> tuple[int, list[tuple[object, ...]], list[str]] | None:
    conn = duckdb.connect(str(duckdb_file), read_only=True)
    try:
        total_rows = conn.execute(
            f"select count(*) from {table_name} {where_clause}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            {select_clause}
            from {table_name}
            {where_clause}
            {order_clause}
            limit ? offset ?
            """,
            [*params, limit, offset],
        ).fetchall()
        columns = [item[0] for item in conn.description]
    except duckdb.Error:
        return None
    finally:
        conn.close()

    return int(total_rows), rows, columns
