from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

from backend.app.schemas.source_preview import (
    PreviewColumn,
    PreviewRowPage,
    RuleTracePage,
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


def _history_query_parts(source_family: str | None) -> tuple[str, list[object]]:
    if source_family is None:
        return "", []
    return "where source_family = ?", [source_family]


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


ROW_LABELS_BY_FAMILY: dict[str, dict[str, str]] = {
    "zqtz": {
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "business_type_primary": "业务种类1",
        "business_type_final": "业务种类2归类",
        "asset_group": "资产分组",
        "instrument_code": "债券代码",
        "instrument_name": "债券名称",
        "account_category": "账户类别",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "tyw": {
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "business_type_primary": "业务种类1",
        "product_group": "产品分组",
        "institution_category": "机构类型",
        "special_nature": "特殊性质",
        "counterparty_name": "对手方名称",
        "investment_portfolio": "投资组合",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "instrument_code": "债券代码",
        "invest_type_raw": "投资类型原值",
        "portfolio_name": "投资组合",
        "cost_center": "成本中心",
        "currency": "币种",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_514": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_516": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
    "pnl_517": {
        "source_family": "源类型",
        "ingest_batch_id": "批次ID",
        "row_locator": "行号",
        "report_date": "报告日期",
        "journal_type": "分录类型",
        "product_type": "产品类型",
        "asset_code": "资产代码",
        "account_code": "科目号",
        "dc_flag_raw": "借贷标识",
        "raw_amount": "原始金额",
        "manual_review_needed": "需人工复核",
        "source_version": "数据版本",
        "rule_version": "规则版本",
    },
}

TRACE_LABELS: dict[str, str] = {
    "ingest_batch_id": "批次ID",
    "row_locator": "行号",
    "trace_step": "轨迹步骤",
    "field_name": "字段名",
    "field_value": "字段值",
    "derived_label": "归类标签",
    "manual_review_needed": "需人工复核",
}


def _build_preview_columns(source_family: str, columns: list[str]) -> list[PreviewColumn]:
    labels = ROW_LABELS_BY_FAMILY.get(source_family, {})
    return [
        PreviewColumn(
            key=column,
            label=labels.get(column, column),
            type=_preview_column_type(column),
        )
        for column in columns
    ]


def _build_trace_columns(columns: list[str]) -> list[PreviewColumn]:
    return [
        PreviewColumn(
            key=column,
            label=TRACE_LABELS.get(column, column),
            type=_preview_column_type(column),
        )
        for column in columns
    ]


def _preview_column_type(column: str) -> str:
    if column in {"row_locator", "trace_step"}:
        return "number"
    if column in {"manual_review_needed"}:
        return "boolean"
    return "string"


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
