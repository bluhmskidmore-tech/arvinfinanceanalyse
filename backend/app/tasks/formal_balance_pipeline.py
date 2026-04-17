from __future__ import annotations

"""
Orchestrates `zqtz` / `tyw` formal-balance lane: ingest → snapshot materialize → balance formal facts.

All DuckDB writes happen inside invoked tasks (`ingest_demo_manifest` side effects, `materialize_standard_snapshots`,
`materialize_balance_analysis_facts`). This module does not open DuckDB connections directly.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import ingest_demo_manifest
from backend.app.tasks.snapshot_materialize import materialize_standard_snapshots

def _emit_json_payload(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered, file=sys.stdout)


def _normalize_formal_runtime_payload(
    raw_payload: dict[str, object],
) -> dict[str, object]:
    runtime_payload = raw_payload.get("payload")
    if isinstance(runtime_payload, dict):
        return runtime_payload

    # Backward-compatible fallback while old callsites/stubs are still present.
    return {
        "run": {
            "run_id": raw_payload.get("run_id"),
            "job_name": raw_payload.get("job_name"),
            "report_date": raw_payload.get("report_date"),
            "status": raw_payload.get("status"),
            "lock": raw_payload.get("lock"),
            "queued_at": raw_payload.get("queued_at"),
            "started_at": raw_payload.get("started_at"),
            "finished_at": raw_payload.get("finished_at"),
        },
        "lineage": {
            "cache_key": raw_payload.get("cache_key"),
            "cache_version": raw_payload.get("cache_version"),
            "source_version": raw_payload.get("source_version"),
            "vendor_version": raw_payload.get("vendor_version"),
            "rule_version": raw_payload.get("rule_version"),
            "basis": raw_payload.get("basis"),
            "module_name": raw_payload.get("module_name"),
            "result_kind_family": raw_payload.get("result_kind_family"),
            "run_id": raw_payload.get("run_id"),
            "report_date": raw_payload.get("report_date"),
            "input_sources": raw_payload.get("input_sources"),
            "fact_tables": raw_payload.get("fact_tables"),
        },
        "result": {
            key: value
            for key, value in raw_payload.items()
            if key
            not in {
                "status",
                "cache_key",
                "cache_version",
                "run_id",
                "report_date",
                "source_version",
                "rule_version",
                "vendor_version",
                "lock",
                "payload",
                "queued_at",
                "started_at",
                "finished_at",
                "basis",
                "module_name",
                "result_kind_family",
                "input_sources",
                "fact_tables",
                "job_name",
            }
        },
    }


def _normalize_iso_date(value: str | None, *, field_name: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid calendar date in YYYY-MM-DD format.") from exc


def _resolve_report_dates(
    *,
    governance_dir: str | None,
    ingest_batch_id: str,
    source_families: list[str],
    report_date: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[str]:
    settings = get_settings()
    requested_report_date = _normalize_iso_date(report_date, field_name="report_date")
    requested_start_date = _normalize_iso_date(start_date, field_name="start_date")
    requested_end_date = _normalize_iso_date(end_date, field_name="end_date")

    if requested_report_date is not None and (
        requested_start_date is not None or requested_end_date is not None
    ):
        raise ValueError("report_date cannot be combined with start_date or end_date.")
    if (
        requested_start_date is not None
        and requested_end_date is not None
        and requested_end_date < requested_start_date
    ):
        raise ValueError("end_date must be on or after start_date.")
    if requested_report_date is not None:
        return [requested_report_date.isoformat()]

    manifest_repo = SourceManifestRepository(
        governance_repo=GovernanceRepository(
            base_dir=Path(governance_dir or settings.governance_path)
        ),
    )
    batch_rows = manifest_repo.select_for_snapshot_materialization(
        source_families=source_families,
        ingest_batch_id=ingest_batch_id,
    )

    resolved_dates: list[str] = []
    for raw_date in sorted(
        {
            str(row.get("report_date") or "").strip()
            for row in batch_rows
            if str(row.get("report_date") or "").strip()
        }
    ):
        current_date = _normalize_iso_date(raw_date, field_name="report_date")
        if current_date is None:
            continue
        if requested_start_date is not None and current_date < requested_start_date:
            continue
        if requested_end_date is not None and current_date > requested_end_date:
            continue
        resolved_dates.append(current_date.isoformat())

    if not resolved_dates:
        raise ValueError(
            "Formal balance pipeline could not resolve any eligible report_date values from the ingest batch."
        )
    return resolved_dates


def _run_formal_balance_pipeline(
    *,
    report_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    data_root: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    source_families = ["zqtz", "tyw"]
    ingest_payload = ingest_demo_manifest.fn(
        data_root=data_root,
        governance_dir=governance_dir,
        archive_dir=archive_dir,
        source_family_allowlist=source_families,
    )
    ingest_batch_id = str(ingest_payload.get("ingest_batch_id") or "").strip()
    if not ingest_batch_id:
        raise ValueError("Formal balance pipeline requires a non-empty ingest_batch_id from ingest.")

    report_dates = _resolve_report_dates(
        governance_dir=governance_dir,
        ingest_batch_id=ingest_batch_id,
        source_families=source_families,
        report_date=report_date,
        start_date=start_date,
        end_date=end_date,
    )

    per_report_date: list[dict[str, object]] = []
    for current_report_date in report_dates:
        snapshot_payload = materialize_standard_snapshots.fn(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            source_families=source_families,
            ingest_batch_id=ingest_batch_id,
            report_date=current_report_date,
        )
        balance_payload = materialize_balance_analysis_facts.fn(
            report_date=current_report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            ingest_batch_id=ingest_batch_id,
            data_root=data_root,
            fx_source_path=fx_source_path,
        )
        per_report_date.append(
            {
                "report_date": current_report_date,
                "snapshot": snapshot_payload,
                "balance": balance_payload,
                "balance_runtime": _normalize_formal_runtime_payload(balance_payload),
            }
        )

    payload: dict[str, object] = {
        "status": "completed",
        "report_dates": report_dates,
        "ingest_batch_id": ingest_batch_id,
        "steps": {
            "ingest": ingest_payload,
            "per_report_date": per_report_date,
        },
    }
    if len(per_report_date) == 1:
        payload["report_date"] = report_dates[0]
        payload["steps"]["snapshot"] = per_report_date[0]["snapshot"]
        payload["steps"]["balance"] = per_report_date[0]["balance"]
        payload["steps"]["balance_runtime"] = per_report_date[0]["balance_runtime"]
    return payload


run_formal_balance_pipeline = register_actor_once(
    "run_formal_balance_pipeline",
    _run_formal_balance_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal balance pipeline.")
    parser.add_argument("--report-date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--data-root")
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--archive-dir")
    parser.add_argument("--fx-source-path")
    args = parser.parse_args()

    payload = run_formal_balance_pipeline.fn(
        report_date=args.report_date,
        start_date=args.start_date,
        end_date=args.end_date,
        data_root=args.data_root,
        duckdb_path=args.duckdb_path,
        governance_dir=args.governance_dir,
        archive_dir=args.archive_dir,
        fx_source_path=args.fx_source_path,
    )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
