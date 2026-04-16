from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord
from backend.app.tasks.fx_mid_materialize import materialize_fx_mid_for_report_date

logger = logging.getLogger(__name__)

CACHE_KEY = "fx:formal_mid:backfill"
CACHE_VERSION = "cv_fx_formal_mid_backfill_v1"
RULE_VERSION = "rv_fx_formal_mid_backfill_v1"
LOCK_KEY = "lock:duckdb:formal:fx-mid:backfill"


def _normalize_iso_date(value: str, *, field_name: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid calendar date in YYYY-MM-DD format.") from exc


def _iter_report_dates(*, start_date: str, end_date: str) -> list[str]:
    start = _normalize_iso_date(start_date, field_name="start_date")
    end = _normalize_iso_date(end_date, field_name="end_date")
    if end < start:
        raise ValueError("end_date must be on or after start_date.")
    current = start
    resolved: list[str] = []
    while current <= end:
        resolved.append(current.isoformat())
        current += timedelta(days=1)
    return resolved


def _backfill_fx_mid_history(
    *,
    start_date: str,
    end_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    governance_repo = GovernanceRepository(base_dir=governance_path)
    report_dates = _iter_report_dates(start_date=start_date, end_date=end_date)

    run = BuildRunRecord(
        job_name="fx_mid_backfill",
        status="running",
        cache_key=CACHE_KEY,
    )
    active_run_id = run_id or f"fx_mid_backfill:{run.created_at}"
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=active_run_id,
                job_name="fx_mid_backfill",
                status="running",
                cache_key=CACHE_KEY,
                cache_version=CACHE_VERSION,
                lock=LOCK_KEY,
                source_version="sv_fx_backfill_running",
                vendor_version="vv_none",
                rule_version=RULE_VERSION,
            ).model_dump(),
            "start_date": start_date,
            "end_date": end_date,
            "report_dates": report_dates,
            "started_at": run.created_at,
        },
    )

    per_date: list[dict[str, object]] = []
    source_versions: set[str] = set()
    vendor_versions: set[str] = set()
    try:
        for report_date in report_dates:
            payload = materialize_fx_mid_for_report_date.fn(
                report_date=report_date,
                duckdb_path=str(duckdb_file),
                data_input_root=str(settings.data_input_root),
                official_csv_path="",
                explicit_csv_path="",
            )
            per_date.append(payload)
            source_version = str(payload.get("source_version") or "").strip()
            vendor_version = str(payload.get("vendor_version") or "").strip()
            if source_version:
                source_versions.add(source_version)
            if vendor_version:
                vendor_versions.add(vendor_version)
    except Exception as exc:
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **CacheBuildRunRecord(
                    run_id=active_run_id,
                    job_name="fx_mid_backfill",
                    status="failed",
                    cache_key=CACHE_KEY,
                    cache_version=CACHE_VERSION,
                    lock=LOCK_KEY,
                    source_version="__".join(sorted(source_versions)) or "sv_fx_backfill_failed",
                    vendor_version="__".join(sorted(vendor_versions)) or "vv_none",
                    rule_version=RULE_VERSION,
                ).model_dump(),
                "start_date": start_date,
                "end_date": end_date,
                "report_dates": report_dates,
                "completed_dates": [item.get("report_date") for item in per_date],
                "error_message": str(exc),
            },
        )
        raise

    source_version = "__".join(sorted(source_versions)) or "sv_fx_backfill_empty"
    vendor_version = "__".join(sorted(vendor_versions)) or "vv_none"
    governance_repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                {
                    **CacheManifestRecord(
                        cache_key=CACHE_KEY,
                        cache_version=CACHE_VERSION,
                        source_version=source_version,
                        vendor_version=vendor_version,
                        rule_version=RULE_VERSION,
                    ).model_dump(),
                    "start_date": start_date,
                    "end_date": end_date,
                    "report_dates": report_dates,
                    "row_count": sum(int(item.get("row_count") or 0) for item in per_date),
                },
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=active_run_id,
                        job_name="fx_mid_backfill",
                        status="completed",
                        cache_key=CACHE_KEY,
                        cache_version=CACHE_VERSION,
                        lock=LOCK_KEY,
                        source_version=source_version,
                        vendor_version=vendor_version,
                        rule_version=RULE_VERSION,
                    ).model_dump(),
                    "start_date": start_date,
                    "end_date": end_date,
                    "report_dates": report_dates,
                    "completed_dates": report_dates,
                },
            ),
        ]
    )

    return {
        "status": "completed",
        "run_id": active_run_id,
        "cache_key": CACHE_KEY,
        "cache_version": CACHE_VERSION,
        "rule_version": RULE_VERSION,
        "start_date": start_date,
        "end_date": end_date,
        "report_dates": report_dates,
        "row_count": sum(int(item.get("row_count") or 0) for item in per_date),
        "source_version": source_version,
        "vendor_version": vendor_version,
        "per_date": per_date,
        "lock": LOCK_KEY,
    }


backfill_fx_mid_history = register_actor_once(
    "backfill_fx_mid_history",
    _backfill_fx_mid_history,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill governed FX middle-rates over a date range.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    args = parser.parse_args()

    payload = backfill_fx_mid_history.fn(
        start_date=args.start_date,
        end_date=args.end_date,
        duckdb_path=args.duckdb_path,
        governance_dir=args.governance_dir,
    )
    logger.info(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
