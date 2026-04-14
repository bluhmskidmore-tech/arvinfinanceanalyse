from __future__ import annotations

from backend.app.repositories.source_preview_repo import (
    RULE_VERSION,
    load_preview_rows,
    load_rule_traces,
    load_source_preview_history_payload,
    load_source_preview_payload,
    source_preview_batch_version,
    source_preview_history_version,
    source_preview_payload_version,
)
from backend.app.schemas.result_meta import ResultMeta
from backend.app.schemas.source_preview import SourcePreviewPayload

CACHE_VERSION = "cv_phase1_source_preview_v1"
SOURCE_FOUNDATION_FAMILIES = frozenset({"zqtz", "tyw"})


def _preview_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    source_version: str,
) -> dict[str, object]:
    return ResultMeta(
        trace_id=trace_id,
        basis="analytical",
        result_kind=result_kind,
        formal_use_allowed=False,
        source_version=source_version,
        vendor_version="vv_none",
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="ok",
        scenario_flag=False,
    ).model_dump(mode="json")


def source_preview_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_source_preview_payload(duckdb_path)
    payload = SourcePreviewPayload(
        sources=[
            source
            for source in payload.sources
            if str(source.source_family) in SOURCE_FOUNDATION_FAMILIES
        ]
    )
    return {
        "result_meta": _preview_result_meta(
            trace_id="tr_preview_source_foundation",
            result_kind="preview.source-foundation",
            source_version=source_preview_payload_version(payload),
        ),
        "result": payload.model_dump(mode="json"),
    }


def source_preview_history_envelope(
    duckdb_path: str,
    limit: int,
    offset: int,
    source_family: str | None = None,
) -> dict[str, object]:
    payload = load_source_preview_history_payload(
        duckdb_path,
        limit,
        offset,
        source_family=source_family,
    )
    return {
        "result_meta": _preview_result_meta(
            trace_id="tr_preview_source_foundation_history",
            result_kind="preview.source-foundation.history",
            source_version=source_preview_history_version(payload),
        ),
        "result": payload.model_dump(mode="json"),
    }


def preview_rows_envelope(
    duckdb_path: str,
    source_family: str,
    limit: int,
    offset: int,
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    payload = load_preview_rows(duckdb_path, source_family, limit, offset, ingest_batch_id)
    row_versions = [
        str(row.get("source_version") or "").strip()
        for row in payload.rows
        if str(row.get("source_version") or "").strip()
    ]
    source_version = (
        "__".join(dict.fromkeys(row_versions))
        if row_versions
        else source_preview_batch_version(
            duckdb_path=duckdb_path,
            source_family=source_family,
            ingest_batch_id=payload.ingest_batch_id,
        )
    )
    return {
        "result_meta": _preview_result_meta(
            trace_id=f"tr_preview_{source_family}_rows",
            result_kind=f"preview.{source_family}.rows",
            source_version=source_version,
        ),
        "result": payload.model_dump(mode="json"),
    }


def preview_traces_envelope(
    duckdb_path: str,
    source_family: str,
    limit: int,
    offset: int,
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    payload = load_rule_traces(duckdb_path, source_family, limit, offset, ingest_batch_id)
    return {
        "result_meta": _preview_result_meta(
            trace_id=f"tr_preview_{source_family}_traces",
            result_kind=f"preview.{source_family}.traces",
            source_version=source_preview_batch_version(
                duckdb_path=duckdb_path,
                source_family=source_family,
                ingest_batch_id=payload.ingest_batch_id,
            ),
        ),
        "result": payload.model_dump(mode="json"),
    }
