from __future__ import annotations

from collections import Counter
from pathlib import Path

from backend.app.core_finance.source_preview_parsers import (
    RULE_VERSION,
    build_source_version,
    parse_source_file,
)
from backend.app.repositories.governance_repo import (
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.source_preview_repo_constants import (
    MANIFEST_ELIGIBLE_STATUSES,
    SUPPORTED_PREVIEW_SOURCE_FAMILIES,
)
from backend.app.repositories.source_preview_repo_reads import (
    _source_preview_batch_version_cached,
)
from backend.app.services.source_rules import describe_source_file


def summarize_source_file(path: Path) -> dict[str, object]:
    metadata = describe_source_file(path.name)
    source_version = build_source_version(path)
    family, report_date, parsed_rows, _ = parse_source_file(
        path=path,
        ingest_batch_id="preview",
        source_version=source_version,
        source_file_name=path.name,
    )
    return _summarize_rows(
        ingest_batch_id="preview",
        batch_created_at="preview",
        family=family,
        report_date=report_date,
        report_start_date=metadata.report_start_date,
        report_end_date=metadata.report_end_date,
        report_granularity=metadata.report_granularity,
        source_file=str(path),
        source_version=source_version,
        rows=parsed_rows,
    )


def materialize_source_previews(
    duckdb_path: str,
    governance_dir: str | None = None,
    data_root: str | None = None,
    ingest_batch_id: str | None = None,
    source_families: list[str] | None = None,
    *,
    write_preview_tables_fn,
) -> list[dict[str, object]]:
    manifest_rows = _load_manifest_rows(governance_dir) if governance_dir is not None else []
    selected = _select_manifest_rows(
        manifest_rows,
        ingest_batch_id=ingest_batch_id,
        source_families=source_families,
    )
    summaries: list[dict[str, object]] = []
    row_records: list[dict[str, object]] = []
    trace_records: list[dict[str, object]] = []
    _source_preview_batch_version_cached.cache_clear()

    for manifest_row in selected:
        path = Path(str(manifest_row["archived_path"]))
        metadata = describe_source_file(str(manifest_row.get("source_file") or path.name))
        family, report_date, parsed_rows, parsed_traces = parse_source_file(
            path=path,
            ingest_batch_id=str(manifest_row["ingest_batch_id"]),
            source_version=str(manifest_row["source_version"]),
            source_file_name=str(manifest_row.get("source_file") or path.name),
        )
        summaries.append(
            _summarize_rows(
                ingest_batch_id=str(manifest_row["ingest_batch_id"]),
                batch_created_at=str(manifest_row.get("created_at", "")),
                family=family,
                report_date=report_date,
                report_start_date=str(manifest_row.get("report_start_date") or metadata.report_start_date or ""),
                report_end_date=str(manifest_row.get("report_end_date") or metadata.report_end_date or ""),
                report_granularity=str(manifest_row.get("report_granularity") or metadata.report_granularity or ""),
                source_file=str(manifest_row["source_file"]),
                source_version=str(manifest_row["source_version"]),
                rows=parsed_rows,
            )
        )
        row_records.extend(parsed_rows)
        trace_records.extend(parsed_traces)

    write_preview_tables_fn(duckdb_path, summaries, row_records, trace_records)
    return summaries


def _load_manifest_rows(governance_dir: str) -> list[dict[str, object]]:
    return GovernanceRepository(base_dir=governance_dir).read_all(SOURCE_MANIFEST_STREAM)


def _select_manifest_rows(
    manifest_rows: list[dict[str, object]],
    ingest_batch_id: str | None = None,
    source_families: list[str] | None = None,
) -> list[dict[str, object]]:
    eligible_rows = [
        row
        for row in manifest_rows
        if str(row.get("status", "")) in MANIFEST_ELIGIBLE_STATUSES
        and row.get("archived_path")
        and Path(str(row["archived_path"])).exists()
    ]
    if source_families is not None:
        allowed = {str(family) for family in source_families}
        eligible_rows = [
            row
            for row in eligible_rows
            if str(row.get("source_family", "")) in allowed
        ]
    if ingest_batch_id is not None:
        return [
            row
            for row in eligible_rows
            if str(row.get("ingest_batch_id", "")) == ingest_batch_id
        ]

    latest_rows: list[dict[str, object]] = []
    families = sorted({str(row.get("source_family", "")) for row in eligible_rows if row.get("source_family")})
    for family in families:
        family_rows = [row for row in eligible_rows if str(row.get("source_family", "")) == family]
        latest_report_date = max(str(row.get("report_date", "")) for row in family_rows)
        bounded_rows = [row for row in family_rows if str(row.get("report_date", "")) == latest_report_date]
        latest_batch_id = max(
            bounded_rows,
            key=lambda item: (
                str(item.get("created_at", "")),
                str(item.get("ingest_batch_id", "")),
            ),
        )["ingest_batch_id"]
        latest_rows.extend(
            sorted(
                [row for row in bounded_rows if str(row.get("ingest_batch_id", "")) == str(latest_batch_id)],
                key=lambda item: str(item.get("archived_path", "")),
            )
        )
    return latest_rows


def _summarize_rows(
    ingest_batch_id: str,
    batch_created_at: str,
    family: str,
    report_date: str | None,
    report_start_date: str | None,
    report_end_date: str | None,
    report_granularity: str | None,
    source_file: str,
    source_version: str,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    group_counts = Counter(_group_label(family, row) for row in rows)
    return {
        "ingest_batch_id": ingest_batch_id,
        "batch_created_at": batch_created_at,
        "source_family": family,
        "report_date": report_date,
        "report_start_date": report_start_date,
        "report_end_date": report_end_date,
        "report_granularity": report_granularity,
        "source_file": source_file,
        "total_rows": len(rows),
        "manual_review_count": sum(int(bool(row["manual_review_needed"])) for row in rows),
        "source_version": source_version,
        "rule_version": RULE_VERSION,
        "group_counts": dict(group_counts),
        "preview_mode": "tabular",
    }


def _group_label(source_family: str, row: dict[str, object]) -> str:
    if source_family == "zqtz":
        return str(row["asset_group"])
    if source_family == "tyw":
        return str(row["product_group"])
    if source_family == "pnl":
        return str(row["invest_type_raw"] or "鏈爣娉?")
    return str(row["product_type"] or row["journal_type"] or "鏈爣娉?")


def _direct_source_rows(data_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in data_root.rglob("*") if item.is_file()):
        metadata = describe_source_file(path.name)
        if metadata.source_family not in SUPPORTED_PREVIEW_SOURCE_FAMILIES:
            continue
        rows.append(
            {
                "source_family": metadata.source_family,
                "report_date": metadata.report_date,
                "report_start_date": metadata.report_start_date,
                "report_end_date": metadata.report_end_date,
                "report_granularity": metadata.report_granularity,
                "source_file": path.name,
                "archived_path": str(path),
                "ingest_batch_id": "preview-direct",
                "source_version": build_source_version(path),
                "status": "completed",
                "created_at": path.stat().st_mtime_ns,
            }
        )
    return rows
