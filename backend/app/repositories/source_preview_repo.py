from __future__ import annotations

from backend.app.core_finance.source_preview_parsers import (
    RULE_VERSION,
    TYW_PRODUCT_TYPE,
    TYW_TRACE_FIELDS,
)
from backend.app.repositories.source_preview_repo_constants import (
    MANIFEST_ELIGIBLE_STATUSES,
    PREVIEW_TABLES,
    SUPPORTED_PREVIEW_SOURCE_FAMILIES,
)
from backend.app.repositories.source_preview_repo_materialize import (
    _direct_source_rows,
    _group_label,
    _load_manifest_rows,
    _select_manifest_rows,
    _summarize_rows,
    materialize_source_previews as _materialize_source_previews_impl,
    summarize_source_file,
)
from backend.app.repositories.source_preview_repo_reads import (
    ROW_LABELS_BY_FAMILY,
    TRACE_LABELS,
    _build_preview_columns,
    _build_trace_columns,
    _history_query_parts,
    _join_source_versions,
    _latest_batch_id_for_family,
    _preview_column_type,
    _preview_read_scope,
    _read_paged_table,
    _row_table_name,
    _source_preview_batch_version_cached,
    _trace_table_name,
    load_preview_rows,
    load_rule_traces,
    load_source_preview_history_payload,
    load_source_preview_payload,
    source_preview_batch_version,
    source_preview_history_version,
    source_preview_payload_version,
)
from backend.app.repositories.source_preview_repo_writes import (
    _table_exists,
    cleanup_preview_backups as _cleanup_preview_backups,
    clear_preview_tables as _clear_preview_tables,
    ensure_source_preview_schema_tables as _ensure_source_preview_schema_tables,
    restore_preview_tables as _restore_preview_tables,
    snapshot_preview_tables as _snapshot_preview_tables,
    write_preview_tables as _write_preview_tables_impl,
)


def materialize_source_previews(
    duckdb_path: str,
    governance_dir: str | None = None,
    data_root: str | None = None,
    ingest_batch_id: str | None = None,
    source_families: list[str] | None = None,
) -> list[dict[str, object]]:
    return _materialize_source_previews_impl(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        data_root=data_root,
        ingest_batch_id=ingest_batch_id,
        source_families=source_families,
        write_preview_tables_fn=_write_preview_tables,
    )


def snapshot_preview_tables(duckdb_path: str) -> None:
    _source_preview_batch_version_cached.cache_clear()
    _snapshot_preview_tables(duckdb_path)


def restore_preview_tables(duckdb_path: str) -> None:
    _source_preview_batch_version_cached.cache_clear()
    _restore_preview_tables(duckdb_path)


def cleanup_preview_backups(duckdb_path: str) -> None:
    _source_preview_batch_version_cached.cache_clear()
    _cleanup_preview_backups(duckdb_path)


def clear_preview_tables(duckdb_path: str) -> None:
    _source_preview_batch_version_cached.cache_clear()
    _clear_preview_tables(duckdb_path)


def ensure_source_preview_schema_tables(conn) -> None:
    _ensure_source_preview_schema_tables(conn)


def _write_preview_tables(
    duckdb_path: str,
    summaries: list[dict[str, object]],
    row_records: list[dict[str, object]],
    trace_records: list[dict[str, object]],
) -> None:
    _write_preview_tables_impl(
        duckdb_path,
        summaries,
        row_records,
        trace_records,
        ensure_source_preview_schema_tables_fn=ensure_source_preview_schema_tables,
    )
