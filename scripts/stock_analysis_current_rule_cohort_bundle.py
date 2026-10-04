#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import stock_analysis_current_rule_cohort_bundle_producer as producer_task  # noqa: E402
from backend.app.tasks import stock_analysis_current_rule_cohort_evidence as evidence_task  # noqa: E402
from scripts.stock_analysis_current_rule_replay_dry_run import (  # noqa: E402
    build_current_rule_replay_dry_run,
)

EXIT_READY = 0
EXIT_BLOCKED = 2


def run_current_rule_cohort_bundle_cli(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    approved_calendar_receipt: str | Path,
    source_availability_receipts: list[str | Path],
    version_tuple_file: str | Path,
    output_root: str | Path,
    batch_name: str,
    cohort_id: str,
    run_id: str,
    evaluation_as_of_date: str,
    choice_stock_catalog_file: str | Path,
    max_workers: int,
    created_at: str,
) -> dict[str, Any]:
    target_db = Path(duckdb_path).resolve()
    db_sha_before: str | None = None
    governed_run_id: str | None = None
    temp_batch_dir: Path | None = None
    final_batch_dir: Path | None = None
    final_batch_created_by_this_run = False

    try:
        target_db = _require_existing_duckdb_path(duckdb_path)
        db_sha_before = _file_sha256(target_db)
        inputs = _load_governed_inputs(
            trusted_evidence_root=trusted_evidence_root,
            approved_calendar_receipt=approved_calendar_receipt,
            source_availability_receipts=source_availability_receipts,
            version_tuple_file=version_tuple_file,
            evaluation_as_of_date=evaluation_as_of_date,
        )
        governed_run_id = str(inputs["governed_run_id"])
        output_dir = producer_task._existing_directory(  # type: ignore[attr-defined]
            output_root,
            field_name="output_root",
        )
        normalized_batch_name = _validate_final_batch_name(batch_name)
        final_batch_dir = _resolve_final_batch_dir(
            output_root=output_dir,
            batch_name=normalized_batch_name,
        )

        replay_report = build_current_rule_replay_dry_run(
            duckdb_path=target_db,
            start_date=str(inputs["start_date"]),
            end_date=str(inputs["end_date"]),
            choice_stock_catalog_file=choice_stock_catalog_file,
            max_workers=max_workers,
        )
        db_sha_after_replay = _file_sha256(target_db)
        replay_hash_unchanged = db_sha_after_replay == db_sha_before
        if not replay_hash_unchanged:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_replay"],
                governed_run_id=governed_run_id,
                duckdb_path=target_db,
                db_sha_before=db_sha_before,
                db_sha_after=db_sha_after_replay,
                replay_report=replay_report,
                evidence_report={},
                calendar_receipt=inputs["calendar_receipt"],
                source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            )

        evidence_report = evidence_task.collect_stock_analysis_current_rule_cohort_evidence(
            duckdb_path=target_db,
            evaluation_as_of_date=str(inputs["evaluation_as_of_date"]),
            governed_run_id=governed_run_id,
            runner_results=list(_date_results_from_replay(replay_report)),
            source_availability_receipts=list(inputs["source_receipts"]),
            frozen_version_tuple=dict(inputs["version_tuple"]),
            choice_stock_catalog_file=choice_stock_catalog_file,
        )
        db_sha_after_evidence = _file_sha256(target_db)
        evidence_hash_unchanged = db_sha_after_evidence == db_sha_before
        evidence_hash_blockers = (
            []
            if evidence_hash_unchanged
            else ["duckdb_hash_changed_during_evidence_collection"]
        )
        blockers = _ordered_strings(
            [*evidence_hash_blockers, *_string_list(evidence_report.get("blockers"))]
        )
        if blockers or evidence_report.get("status") != "ready":
            return _result_payload(
                status="blocked",
                blockers=blockers,
                governed_run_id=governed_run_id,
                duckdb_path=target_db,
                db_sha_before=db_sha_before,
                db_sha_after=db_sha_after_evidence,
                replay_report=replay_report,
                evidence_report=evidence_report,
                calendar_receipt=inputs["calendar_receipt"],
                source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            )

        temp_batch_name = f".pending-{normalized_batch_name}-{uuid.uuid4().hex}"
        temp_batch_dir = output_dir / temp_batch_name
        produced = producer_task.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target_db,
            approved_calendar_receipt_path=inputs["approved_calendar_receipt_path"],
            source_availability_receipt_paths=list(inputs["source_receipt_paths"]),
            trusted_evidence_root=trusted_evidence_root,
            output_root=output_dir,
            batch_name=temp_batch_name,
            cohort_id=cohort_id,
            run_id=run_id,
            governed_run_id=governed_run_id,
            evaluation_as_of_date=str(inputs["evaluation_as_of_date"]),
            frozen_version_tuple=dict(inputs["version_tuple"]),
            date_evidence=list(evidence_report.get("date_evidence") or []),
            created_at=created_at,
        )
        db_sha_after = _file_sha256(target_db)
        if db_sha_after != db_sha_before:
            _safe_remove_temp_batch(temp_batch_dir, output_root=output_dir)
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_after_bundle_production"],
                governed_run_id=governed_run_id,
                duckdb_path=target_db,
                db_sha_before=db_sha_before,
                db_sha_after=db_sha_after,
                replay_report=replay_report,
                evidence_report=evidence_report,
                calendar_receipt=inputs["calendar_receipt"],
                source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            )

        if final_batch_dir.exists():
            _safe_remove_temp_batch(temp_batch_dir, output_root=output_dir)
            return _result_payload(
                status="error",
                blockers=["output_batch_already_exists"],
                governed_run_id=governed_run_id,
                duckdb_path=target_db,
                db_sha_before=db_sha_before,
                db_sha_after=db_sha_after,
                replay_report=replay_report,
                evidence_report=evidence_report,
                calendar_receipt=inputs["calendar_receipt"],
                source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            )
        _remove_file_if_present(
            Path(str(produced["dry_run_receipt_path"])),
            governed_root=temp_batch_dir,
            field_name="dry_run_receipt_path",
        )
        _safe_promote_temp_batch(
            temp_batch_dir=temp_batch_dir,
            final_batch_dir=final_batch_dir,
            output_root=output_dir,
        )
        final_batch_created_by_this_run = True
        finalized = _finalize_batch_artifacts(
            produced=produced,
            temp_batch_dir=temp_batch_dir,
            final_batch_dir=final_batch_dir,
            duckdb_path=target_db,
            created_at=created_at,
        )
        db_sha_after_finalize = _file_sha256(target_db)
        if db_sha_after_finalize != db_sha_before:
            if final_batch_created_by_this_run:
                _safe_remove_final_batch(final_batch_dir, output_root=output_dir)
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_after_final_dry_run"],
                governed_run_id=governed_run_id,
                duckdb_path=target_db,
                db_sha_before=db_sha_before,
                db_sha_after=db_sha_after_finalize,
                replay_report=replay_report,
                evidence_report=evidence_report,
                calendar_receipt=inputs["calendar_receipt"],
                source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            )
        return _result_payload(
            status="ready",
            blockers=[],
            governed_run_id=governed_run_id,
            duckdb_path=target_db,
            db_sha_before=db_sha_before,
            db_sha_after=db_sha_after_finalize,
            replay_report=replay_report,
            evidence_report=evidence_report,
            calendar_receipt=inputs["calendar_receipt"],
            source_receipt_sha256s=list(inputs["source_receipt_sha256s"]),
            produced=finalized,
        )
    except Exception as exc:
        if temp_batch_dir is not None and final_batch_dir is not None and temp_batch_dir.exists():
            _safe_remove_temp_batch(
                temp_batch_dir,
                output_root=final_batch_dir.parent,
            )
        if (
            final_batch_created_by_this_run
            and final_batch_dir is not None
            and final_batch_dir.exists()
        ):
            _safe_remove_final_batch(
                final_batch_dir,
                output_root=final_batch_dir.parent,
            )
        db_sha_after_error = _file_sha256(target_db) if target_db.is_file() else None
        return _result_payload(
            status="error",
            blockers=[f"{type(exc).__name__}:{exc}"],
            governed_run_id=governed_run_id,
            duckdb_path=target_db,
            db_sha_before=db_sha_before,
            db_sha_after=db_sha_after_error,
            replay_report={},
            evidence_report={},
            calendar_receipt={},
            source_receipt_sha256s=[],
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Produce a read-only current-rule cohort bundle from approved evidence inputs."
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--approved-calendar-receipt", required=True)
    parser.add_argument(
        "--source-availability-receipt",
        action="append",
        dest="source_availability_receipts",
        required=True,
    )
    parser.add_argument("--version-tuple-file", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--cohort-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evaluation-as-of-date", required=True)
    parser.add_argument("--choice-stock-catalog-file", required=True)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--created-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)

    result = run_current_rule_cohort_bundle_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        approved_calendar_receipt=args.approved_calendar_receipt,
        source_availability_receipts=list(args.source_availability_receipts),
        version_tuple_file=args.version_tuple_file,
        output_root=args.output_root,
        batch_name=args.batch_name,
        cohort_id=args.cohort_id,
        run_id=args.run_id,
        evaluation_as_of_date=args.evaluation_as_of_date,
        choice_stock_catalog_file=args.choice_stock_catalog_file,
        max_workers=max(1, int(args.max_workers)),
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_READY if result.get("status") == "ready" else EXIT_BLOCKED


def _load_governed_inputs(
    *,
    trusted_evidence_root: str | Path,
    approved_calendar_receipt: str | Path,
    source_availability_receipts: list[str | Path],
    version_tuple_file: str | Path,
    evaluation_as_of_date: str,
) -> dict[str, Any]:
    trusted_root = producer_task._existing_directory(  # type: ignore[attr-defined]
        trusted_evidence_root,
        field_name="trusted_evidence_root",
    )
    calendar_path = producer_task._trusted_existing_file(  # type: ignore[attr-defined]
        trusted_root=trusted_root,
        raw_path=approved_calendar_receipt,
        field_name="approved_calendar_receipt",
    )
    calendar_payload = producer_task._load_json_object(  # type: ignore[attr-defined]
        calendar_path,
        field_name="approved_calendar_receipt",
    )
    ok, errors = producer_task.validate_stock_analysis_calendar_receipt(calendar_payload)
    if not ok:
        raise producer_task.CurrentRuleCohortError(
            "approved calendar receipt is invalid: " + "; ".join(errors)
        )
    if calendar_payload.get("authority_status") != producer_task.APPROVED_AUTHORITY_STATUS:
        raise producer_task.CurrentRuleCohortError(
            "approved calendar receipt must be approved"
        )
    open_dates = producer_task._open_calendar_dates(calendar_payload)  # type: ignore[attr-defined]
    if not open_dates:
        raise producer_task.CurrentRuleCohortError(
            "approved calendar receipt must contain at least one open trade date"
        )
    version_tuple_path = producer_task._trusted_existing_file(  # type: ignore[attr-defined]
        trusted_root=trusted_root,
        raw_path=version_tuple_file,
        field_name="version_tuple_file",
    )
    version_tuple = producer_task._load_json_object(  # type: ignore[attr-defined]
        version_tuple_path,
        field_name="version_tuple_file",
    )
    normalized_version_tuple = producer_task._freeze_version_tuple(version_tuple)  # type: ignore[attr-defined]
    source_payloads: list[dict[str, Any]] = []
    source_paths: list[str] = []
    source_sha256s: list[str] = []
    for index, raw_path in enumerate(source_availability_receipts):
        source_path = producer_task._trusted_existing_file(  # type: ignore[attr-defined]
            trusted_root=trusted_root,
            raw_path=raw_path,
            field_name=f"source_availability_receipts[{index}]",
        )
        source_payload = producer_task._load_json_object(  # type: ignore[attr-defined]
            source_path,
            field_name=f"source_availability_receipts[{index}]",
        )
        source_payloads.append(source_payload)
        source_paths.append(str(source_path))
        source_sha256s.append(producer_task._canonical_sha256(source_payload))  # type: ignore[attr-defined]
    if not source_payloads:
        raise producer_task.CurrentRuleCohortError(
            "at least one source availability receipt is required"
        )
    calendar_sha = producer_task._sha256_text(  # type: ignore[attr-defined]
        calendar_payload.get("canonical_receipt_sha256"),
        "approved_calendar_receipt.canonical_receipt_sha256",
    )
    governed_run_id = producer_task.derive_expected_stock_analysis_current_rule_governed_run_id(
        calendar_receipt_sha256=calendar_sha,
        source_availability_receipt_sha256s=source_sha256s,
        frozen_version_tuple=normalized_version_tuple,
        evaluation_as_of_date=evaluation_as_of_date,
        open_dates=open_dates,
    )
    return {
        "trusted_root": trusted_root,
        "approved_calendar_receipt_path": str(calendar_path),
        "calendar_receipt": calendar_payload,
        "evaluation_as_of_date": evaluation_as_of_date,
        "source_receipts": source_payloads,
        "source_receipt_paths": source_paths,
        "source_receipt_sha256s": sorted(source_sha256s),
        "version_tuple": normalized_version_tuple,
        "governed_run_id": governed_run_id,
        "start_date": open_dates[0],
        "end_date": open_dates[-1],
        "open_dates": open_dates,
    }


def _date_results_from_replay(report: dict[str, Any]) -> list[dict[str, Any]]:
    date_results = report.get("date_results")
    if isinstance(date_results, list):
        return [dict(item) for item in date_results if isinstance(item, dict)]
    return []


def _result_payload(
    *,
    status: str,
    blockers: list[str],
    governed_run_id: str | None,
    duckdb_path: Path,
    db_sha_before: str | None,
    db_sha_after: str | None,
    replay_report: dict[str, Any],
    evidence_report: dict[str, Any],
    calendar_receipt: dict[str, Any],
    source_receipt_sha256s: list[str],
    produced: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = replay_report.get("summary") if isinstance(replay_report, dict) else {}
    replay_counts = summary if isinstance(summary, dict) else {}
    evidence_counts = evidence_report.get("counts") if isinstance(evidence_report, dict) else {}
    request = (
        calendar_receipt.get("request")
        if isinstance(calendar_receipt, dict)
        else None
    )
    request = request if isinstance(request, dict) else {}
    payload = {
        "status": status,
        "blockers": _ordered_strings(blockers),
        "governed_run_id": governed_run_id,
        "duckdb_path": str(duckdb_path),
        "duckdb_sha256_before": db_sha_before,
        "duckdb_sha256_after": db_sha_after,
        "database_unchanged": bool(db_sha_before and db_sha_after and db_sha_before == db_sha_after),
        "calendar": {
            "request_start_date": request.get("start_date"),
            "request_end_date": request.get("end_date"),
            "open_date_count": len(producer_task._open_calendar_dates(calendar_receipt))  # type: ignore[attr-defined]
            if isinstance(calendar_receipt, dict)
            else 0,
        },
        "source_availability_receipt_sha256s": list(source_receipt_sha256s),
        "replay": {
            "requested_range": replay_report.get("requested_range") if isinstance(replay_report, dict) else {},
            "status_counts": replay_counts.get("status_counts") if isinstance(replay_counts, dict) else {},
            "attempted_dates": replay_counts.get("attempted_dates"),
            "candidate_signal_date_count": replay_counts.get("candidate_signal_date_count"),
            "candidate_rows_total": replay_counts.get("candidate_rows_total"),
            "future_business_date_violation_count": replay_counts.get("future_business_date_violation_count"),
            "future_availability_violation_count": replay_counts.get("future_availability_violation_count"),
            "report_blockers": _string_list(replay_report.get("blockers"))
            if isinstance(replay_report, dict)
            else [],
            "diagnostic_limitations": _string_list(
                replay_report.get("diagnostic_limitations")
            )
            if isinstance(replay_report, dict)
            else [],
        },
        "evidence": {
            "status": evidence_report.get("status") if isinstance(evidence_report, dict) else None,
            "counts": evidence_counts if isinstance(evidence_counts, dict) else {},
            "blockers": evidence_report.get("blockers") if isinstance(evidence_report, dict) else [],
            "date_evidence_count": len(evidence_report.get("date_evidence") or [])
            if isinstance(evidence_report, dict)
            else 0,
        },
    }
    if produced is not None:
        payload["bundle"] = {
            "bundle_path": produced.get("bundle_path"),
            "bundle_sha256": produced.get("bundle_sha256"),
            "dry_run_receipt_path": produced.get("dry_run_receipt_path"),
            "dry_run_receipt_sha256": produced.get("dry_run_receipt_sha256"),
            "zero_signal_certificate_paths": produced.get("zero_signal_certificate_paths"),
            "summary": produced.get("summary"),
        }
    return payload


def _finalize_batch_artifacts(
    *,
    produced: dict[str, Any],
    temp_batch_dir: Path,
    final_batch_dir: Path,
    duckdb_path: Path,
    created_at: str,
) -> dict[str, Any]:
    final_bundle_path = _relocate_batch_path(
        raw_path=produced.get("bundle_path"),
        temp_batch_dir=temp_batch_dir,
        final_batch_dir=final_batch_dir,
        field_name="bundle_path",
    )
    final_receipt_path = _relocate_batch_path(
        raw_path=produced.get("dry_run_receipt_path"),
        temp_batch_dir=temp_batch_dir,
        final_batch_dir=final_batch_dir,
        field_name="dry_run_receipt_path",
    )
    rebuilt_receipt = producer_task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=duckdb_path,
        bundle_path=final_bundle_path,
        receipt_path=final_receipt_path,
        created_at=created_at,
    )
    finalized = dict(produced)
    finalized["bundle_path"] = str(final_bundle_path)
    finalized["dry_run_receipt_path"] = str(final_receipt_path)
    finalized["dry_run_receipt_sha256"] = str(
        rebuilt_receipt["canonical_receipt_sha256"]
    )
    finalized["zero_signal_certificate_paths"] = [
        str(
            _relocate_batch_path(
                raw_path=path,
                temp_batch_dir=temp_batch_dir,
                final_batch_dir=final_batch_dir,
                field_name="zero_signal_certificate_paths[]",
            )
        )
        for path in _string_list(produced.get("zero_signal_certificate_paths"))
    ]
    return finalized


def _relocate_batch_path(
    *,
    raw_path: Any,
    temp_batch_dir: Path,
    final_batch_dir: Path,
    field_name: str,
) -> Path:
    text = _text(raw_path)
    if text is None:
        raise producer_task.CurrentRuleCohortError(f"{field_name} is required")
    raw_path_obj = Path(text)
    try:
        relative = raw_path_obj.resolve().relative_to(temp_batch_dir.resolve())
    except ValueError as exc:
        raise producer_task.CurrentRuleCohortError(
            f"{field_name} must stay within producer temp batch directory"
        ) from exc
    path = (final_batch_dir / relative).resolve()
    try:
        path.relative_to(final_batch_dir.resolve())
    except ValueError as exc:
        raise producer_task.CurrentRuleCohortError(
            f"{field_name} must stay within final batch directory"
        ) from exc
    return path


def _validate_final_batch_name(batch_name: Any) -> str:
    text = _text(batch_name)
    if text is None:
        raise producer_task.CurrentRuleCohortError("batch_name is required")
    if text in {".", ".."}:
        raise producer_task.CurrentRuleCohortError(
            "batch_name must be a single safe path segment"
        )
    if text.startswith(".pending-"):
        raise producer_task.CurrentRuleCohortError(
            "batch_name must not use the reserved .pending- prefix"
        )
    if any(separator in text for separator in ("/", "\\", ":")):
        raise producer_task.CurrentRuleCohortError(
            "batch_name must be a single safe path segment"
        )
    parts = Path(text).parts
    if len(parts) != 1 or Path(text).is_absolute():
        raise producer_task.CurrentRuleCohortError(
            "batch_name must be a single safe path segment"
        )
    return text


def _resolve_final_batch_dir(*, output_root: Path, batch_name: str) -> Path:
    candidate = (output_root / batch_name).resolve()
    try:
        candidate.relative_to(output_root.resolve())
    except ValueError as exc:
        raise producer_task.CurrentRuleCohortError(
            "batch_name must remain within output_root"
        ) from exc
    return candidate


def _safe_remove_temp_batch(path: Path, *, output_root: Path) -> None:
    candidate = _assert_raw_path_within_root(
        path=path,
        governed_root=output_root,
        field_name="temporary batch directory",
        escaped_message="temporary batch directory escaped output root",
    )
    if not candidate.name.startswith(".pending-"):
        raise producer_task.CurrentRuleCohortError(
            "temporary batch directory name is unsafe"
        )
    if candidate.exists():
        candidate = _assert_raw_path_within_root(
            path=candidate,
            governed_root=output_root,
            field_name="temporary batch directory",
            escaped_message="temporary batch directory escaped output root",
        )
        shutil.rmtree(candidate)


def _safe_remove_final_batch(path: Path, *, output_root: Path) -> None:
    candidate = _assert_raw_path_within_root(
        path=path,
        governed_root=output_root,
        field_name="final batch directory",
        escaped_message="final batch directory escaped output root",
    )
    if candidate.name.startswith(".pending-"):
        raise producer_task.CurrentRuleCohortError(
            "final batch directory name is unsafe"
        )
    if candidate.exists():
        candidate = _assert_raw_path_within_root(
            path=candidate,
            governed_root=output_root,
            field_name="final batch directory",
            escaped_message="final batch directory escaped output root",
        )
        shutil.rmtree(candidate)


def _safe_promote_temp_batch(
    *,
    temp_batch_dir: Path,
    final_batch_dir: Path,
    output_root: Path,
) -> None:
    source = _assert_raw_path_within_root(
        path=temp_batch_dir,
        governed_root=output_root,
        field_name="temporary batch directory",
        escaped_message="temporary batch directory escaped output root",
    )
    if not source.name.startswith(".pending-"):
        raise producer_task.CurrentRuleCohortError(
            "temporary batch directory name is unsafe"
        )
    destination = _assert_raw_path_within_root(
        path=final_batch_dir,
        governed_root=output_root,
        field_name="final batch directory",
        escaped_message="final batch directory escaped output root",
    )
    if destination.name.startswith(".pending-"):
        raise producer_task.CurrentRuleCohortError(
            "final batch directory name is unsafe"
        )
    source.rename(destination)


def _remove_file_if_present(
    path: Path,
    *,
    governed_root: Path,
    field_name: str,
) -> None:
    candidate = _assert_raw_path_within_root(
        path=path,
        governed_root=governed_root,
        field_name=field_name,
        escaped_message=f"{field_name} escaped governed cleanup root",
    )
    if candidate.exists():
        candidate = _assert_raw_path_within_root(
            path=candidate,
            governed_root=governed_root,
            field_name=field_name,
            escaped_message=f"{field_name} escaped governed cleanup root",
        )
        candidate.unlink()


def _require_existing_duckdb_path(path: str | Path) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_file():
        raise producer_task.CurrentRuleCohortError(
            "duckdb_path must be an existing file"
        )
    return candidate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _ordered_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _text(value)
        if text is None or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _assert_raw_path_within_root(
    *,
    path: str | Path,
    governed_root: Path,
    field_name: str,
    escaped_message: str,
) -> Path:
    candidate = _absolute_without_resolve(path)
    root = _absolute_without_resolve(governed_root)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise producer_task.CurrentRuleCohortError(escaped_message) from exc
    producer_task._assert_no_symlink_in_raw_path(  # type: ignore[attr-defined]
        candidate,
        field_name=field_name,
    )
    return candidate


def _absolute_without_resolve(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


if __name__ == "__main__":
    raise SystemExit(main())
