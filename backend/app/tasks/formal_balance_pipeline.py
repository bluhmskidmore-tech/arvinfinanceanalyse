from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import ingest_demo_manifest
from backend.app.tasks.snapshot_materialize import materialize_standard_snapshots


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
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
