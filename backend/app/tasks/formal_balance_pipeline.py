"""
Orchestrates `zqtz` / `tyw` formal-balance lane: ingest → snapshot materialize → balance formal facts.

Range/backfill runs additionally materialize the downstream daily analytics lane
(`materialize_bond_analytics_facts` → `materialize_risk_tensor_facts`) for the same dates, because no
scheduler drives that lane and range mode is the only operational entry point that backfills it.
The lane is deliberately limited to those two steps: month-end oriented steps (formal PnL, product
category) must not be looped over a date range, and a whole-chain range loop would hold the global
refresh lock for the length of the range.

All DuckDB writes happen inside invoked tasks (`ingest_demo_manifest` side effects, `materialize_standard_snapshots`,
`materialize_balance_analysis_facts`, `materialize_bond_analytics_facts`, `materialize_risk_tensor_facts`).
This module does not open DuckDB connections directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import ingest_demo_manifest
from backend.app.tasks.risk_tensor_materialize import materialize_risk_tensor_facts
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


def _resolve_materialization_ingest_batch_id(
    *,
    governance_dir: str | None,
    source_families: list[str],
    report_date: str,
    requested_ingest_batch_id: str | None,
) -> str | None:
    if not requested_ingest_batch_id:
        return None

    settings = get_settings()
    manifest_repo = SourceManifestRepository(
        governance_repo=GovernanceRepository(
            base_dir=Path(governance_dir or settings.governance_path),
        ),
    )
    requested_rows = manifest_repo.select_for_snapshot_materialization(
        source_families=source_families,
        report_date=report_date,
        ingest_batch_id=requested_ingest_batch_id,
    )
    if requested_rows:
        return requested_ingest_batch_id

    report_date_rows = manifest_repo.select_for_snapshot_materialization(
        source_families=source_families,
        report_date=report_date,
    )
    if report_date_rows:
        return None
    return requested_ingest_batch_id


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
    ingest_batch_id: str | None,
    source_families: list[str],
    report_date: str | None,
    start_date: str | None,
    end_date: str | None,
    backfill: bool,
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
    if backfill:
        candidate_dates = sorted(
            {
                str(row.get("report_date") or "").strip()
                for row in manifest_repo.load_all()
                if str(row.get("source_family") or "").strip() in source_families
                and str(row.get("report_date") or "").strip()
            }
        )
        batch_rows = [
            row
            for candidate_date in candidate_dates
            for row in manifest_repo.select_for_snapshot_materialization(
                source_families=source_families,
                report_date=candidate_date,
            )
        ]
    else:
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
            "Formal balance pipeline could not resolve any eligible report_date values "
            "from the manifest (ingest_batch_id="
            f"{ingest_batch_id!r}). Place zqtz/tyw sources under data_input (or raw_files) "
            "and run ingest, or pass --report-date."
        )
    return resolved_dates


def _resolve_analytics_lane_enabled(
    *,
    include_analytics: bool | None,
    backfill: bool,
    start_date: str | None,
    end_date: str | None,
) -> bool:
    """Range/backfill runs own the daily analytics lane; single-date runs do not.

    `scripts/run_global_data_refresh.py` already sequences bond_analytics/risk_tensor after the
    single-date balance lane, so defaulting the lane on there would duplicate two materializations
    per run. Range mode has no such orchestrator, which is exactly how 2026-06/07 lost 59 dates.
    """
    if include_analytics is not None:
        return include_analytics
    return bool(
        backfill
        or str(start_date or "").strip()
        or str(end_date or "").strip()
    )


def _run_formal_balance_pipeline(
    *,
    report_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    backfill: bool = False,
    include_analytics: bool | None = None,
    data_root: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    source_families = ["zqtz", "tyw"]
    analytics_lane_enabled = _resolve_analytics_lane_enabled(
        include_analytics=include_analytics,
        backfill=backfill,
        start_date=start_date,
        end_date=end_date,
    )
    ingest_payload = ingest_demo_manifest.fn(
        data_root=data_root,
        governance_dir=governance_dir,
        archive_dir=archive_dir,
        source_family_allowlist=source_families,
    )
    # New incremental ingest may be empty (already archived); fall back to latest manifest rows.
    ingest_batch_id = str(ingest_payload.get("ingest_batch_id") or "").strip() or None

    report_dates = _resolve_report_dates(
        governance_dir=governance_dir,
        ingest_batch_id=ingest_batch_id,
        source_families=source_families,
        report_date=report_date,
        start_date=start_date,
        end_date=end_date,
        backfill=backfill,
    )

    per_report_date: list[dict[str, object]] = []
    for current_report_date in report_dates:
        materialization_ingest_batch_id = _resolve_materialization_ingest_batch_id(
            governance_dir=governance_dir,
            source_families=source_families,
            report_date=current_report_date,
            requested_ingest_batch_id=ingest_batch_id,
        )
        snapshot_payload = materialize_standard_snapshots.fn(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            source_families=source_families,
            ingest_batch_id=materialization_ingest_batch_id,
            report_date=current_report_date,
        )
        balance_payload = materialize_balance_analysis_facts.fn(
            report_date=current_report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            ingest_batch_id=materialization_ingest_batch_id,
            data_root=data_root,
            fx_source_path=fx_source_path,
        )
        current_entry: dict[str, object] = {
            "report_date": current_report_date,
            "materialization_ingest_batch_id": materialization_ingest_batch_id,
            "snapshot": snapshot_payload,
            "balance": balance_payload,
            "balance_runtime": _normalize_formal_runtime_payload(balance_payload),
        }
        if analytics_lane_enabled:
            # use_existing_curves_only=True keeps the range loop read-only against
            # fact_formal_yield_curve_daily; the alternative path calls
            # ensure_yield_curve_inputs_on_or_before, which writes new curve snapshots.
            current_entry["bond_analytics"] = materialize_bond_analytics_facts.fn(
                report_date=current_report_date,
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                use_existing_curves_only=True,
            )
            current_entry["risk_tensor"] = materialize_risk_tensor_facts.fn(
                report_date=current_report_date,
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
            )
        per_report_date.append(current_entry)

    steps: dict[str, object] = {
        "ingest": ingest_payload,
        "per_report_date": per_report_date,
    }
    payload: dict[str, object] = {
        "status": "completed",
        "report_dates": report_dates,
        "ingest_batch_id": ingest_batch_id,
        "analytics_lane_enabled": analytics_lane_enabled,
        "steps": steps,
    }
    if len(per_report_date) == 1:
        payload["report_date"] = report_dates[0]
        steps["snapshot"] = per_report_date[0]["snapshot"]
        steps["balance"] = per_report_date[0]["balance"]
        steps["balance_runtime"] = per_report_date[0]["balance_runtime"]
        if analytics_lane_enabled:
            steps["bond_analytics"] = per_report_date[0]["bond_analytics"]
            steps["risk_tensor"] = per_report_date[0]["risk_tensor"]
    return payload


run_formal_balance_pipeline = register_actor_once(
    "run_formal_balance_pipeline",
    _run_formal_balance_pipeline,
)


def run_formal_balance_pipeline_sync(
    *,
    report_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    backfill: bool = False,
    include_analytics: bool | None = None,
    data_root: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    # Delegation transparency (tests/test_task_sync_wrapper_contracts.py): forward
    # only caller-provided kwargs and never inject defaults on the caller's behalf,
    # so the private implementation stays the single owner of default semantics.
    return _run_formal_balance_pipeline(
        **({} if report_date is None else {"report_date": report_date}),
        **({} if start_date is None else {"start_date": start_date}),
        **({} if end_date is None else {"end_date": end_date}),
        **({} if not backfill else {"backfill": backfill}),
        **({} if include_analytics is None else {"include_analytics": include_analytics}),
        **({} if data_root is None else {"data_root": data_root}),
        **({} if duckdb_path is None else {"duckdb_path": duckdb_path}),
        **({} if governance_dir is None else {"governance_dir": governance_dir}),
        **({} if archive_dir is None else {"archive_dir": archive_dir}),
        **({} if fx_source_path is None else {"fx_source_path": fx_source_path}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal balance pipeline.")
    parser.add_argument("--report-date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument(
        "--include-analytics",
        dest="include_analytics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Force the bond_analytics + risk_tensor lane on/off. "
            "Default: on for --backfill/--start-date/--end-date runs, off for a single --report-date."
        ),
    )
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
        backfill=args.backfill,
        include_analytics=args.include_analytics,
        data_root=args.data_root,
        duckdb_path=args.duckdb_path,
        governance_dir=args.governance_dir,
        archive_dir=args.archive_dir,
        fx_source_path=args.fx_source_path,
    )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
