"""Controlled materialization and promotion for the stock-analysis current-rule cohort.

This module is deliberately not registered with the task broker.  Every public
write entry point requires persisted JSON artifacts, an explicit write switch,
the per-database writer lock, and a byte-identical pre-write backup.  The legacy
``as_produced`` Livermore tables are never read or changed here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import duckdb

from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    TABLE_LIMIT_PRICE,
    TABLE_OBS,
    _control_execution_pit_proof,
    _is_limit_down,
)
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.stock_analysis_calendar_receipt import (
    APPROVED_AUTHORITY_STATUS,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS,
    REQUIRED_VERSION_TUPLE_FIELDS,
    validate_current_rule_zero_signal_certificate,
)
from backend.app.repositories.duckdb_migrations import (
    apply_stock_analysis_current_rule_cohort_schema_on_connection,
)

BUNDLE_KIND = "stock_analysis_current_rule_cohort_bundle"
APPROVAL_KIND = "stock_analysis_current_rule_cohort_approval"
DRY_RUN_RECEIPT_KIND = "stock_analysis_current_rule_cohort_dry_run_receipt"
MATERIALIZE_RECEIPT_KIND = "stock_analysis_current_rule_cohort_materialize_receipt"
PROMOTION_RECEIPT_KIND = "stock_analysis_current_rule_cohort_promotion_receipt"
ROLLBACK_RECEIPT_KIND = "stock_analysis_current_rule_cohort_rollback_receipt"

PAGE_ID = "GAP-STOCK-ANALYSIS-PAGE"
COHORT_MODE = "current_rule_certified"
MATERIALIZED_STATUS = "materialized_unpromoted"
CERTIFIED_STATUS = "certified"
SUPERSEDED_STATUS = "superseded"
ROLLED_BACK_STATUS = "rolled_back"
SIGNAL_CERTIFICATE_STATUS = "completed_with_signals"

CONTROL_COUNT = 20
MIN_COMPLETED_DATES = 20
MIN_MATCHED_ENTRIES = 100
MAX_JSON_INPUT_BYTES = 5 * 1024 * 1024
MAX_BUNDLE_JSON_INPUT_BYTES = 10 * 1024 * 1024

ROW_VERSION_FIELDS = (
    "candidate_rule_version",
    "stock_candidate_selection_formula_version",
    "candidate_outcome_formula_version",
    "execution_formula_version",
    "matched_baseline_formula_version",
    "stock_candidate_selection_policy",
    "decision_metric_basis",
    "coverage_authority_mode",
    "strict_coverage",
    "fallback_covered",
    "candidate_source_version",
    "execution_source_version",
    "matched_baseline_source_version",
)

MANIFEST_TABLE = "stock_analysis_current_rule_cohort_manifest"
FACT_TABLE = "stock_analysis_current_rule_replay_fact"
CERTIFICATE_TABLE = "stock_analysis_current_rule_date_certificate"


class CurrentRuleCohortError(ValueError):
    """Raised when a D6 artifact or state transition fails closed."""


@dataclass(frozen=True)
class _ValidatedBundle:
    path: Path
    payload: dict[str, Any]
    bundle_sha256: str
    calendar_path: Path
    calendar_sha256: str
    source_receipt_sha256s: tuple[str, ...]
    source_availability_index: dict[tuple[str, str, str, str, str], str]
    zero_certificates: dict[str, tuple[Path, str]]
    facts: tuple[dict[str, Any], ...]
    certificates: tuple[dict[str, Any], ...]
    summary: dict[str, int]


def build_stock_analysis_current_rule_cohort_dry_run(
    *,
    duckdb_path: str | Path,
    bundle_path: str | Path,
    receipt_path: str | Path,
    created_at: str,
) -> dict[str, Any]:
    """Validate a persisted bundle while proving the target database is unchanged."""
    target = _existing_file(duckdb_path, field_name="duckdb_path")
    before = _file_sha256(target)
    bundle = _load_and_validate_bundle(Path(bundle_path))
    _assert_bundle_target_identity(target=target, bundle=bundle)
    _validate_bundle_source_rows(target=target, bundle=bundle)

    conn = duckdb.connect(str(target), read_only=True)
    try:
        _assert_no_existing_duplicate_rows(conn, bundle=bundle, allow_exact_existing=True)
    finally:
        conn.close()

    after = _file_sha256(target)
    if before != after:
        raise CurrentRuleCohortError("dry-run changed the target DuckDB file")
    receipt = _seal(
        {
            "schema_version": 1,
            "receipt_kind": DRY_RUN_RECEIPT_KIND,
            "status": "dry_run_completed",
            "cohort_id": _text(bundle.payload.get("cohort_id"), "bundle.cohort_id"),
            "bundle_path": str(bundle.path),
            "bundle_sha256": bundle.bundle_sha256,
            "plan_digest_sha256": _sha256_text(
                bundle.payload.get("plan_digest_sha256"), "bundle.plan_digest_sha256"
            ),
            "target_database_path": str(target),
            "target_database_sha256_before": before,
            "target_database_sha256_after": after,
            "database_unchanged": True,
            "calendar_receipt_sha256": bundle.calendar_sha256,
            "source_availability_receipt_sha256s": list(
                bundle.source_receipt_sha256s
            ),
            "summary": bundle.summary,
            "created_at": _datetime_text(created_at),
        },
        hash_field="canonical_receipt_sha256",
    )
    _write_new_or_identical_json(Path(receipt_path), receipt)
    return receipt


def materialize_stock_analysis_current_rule_cohort(
    *,
    duckdb_path: str | Path,
    bundle_path: str | Path,
    dry_run_receipt_path: str | Path,
    approval_artifact_path: str | Path,
    target_backup_path: str | Path,
    receipt_path: str | Path,
    created_at: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Write one certified bundle as an inactive cohort in a single transaction."""
    _require_write_switch(allow_write)
    target = _existing_file(duckdb_path, field_name="duckdb_path")
    bundle = _load_and_validate_bundle(Path(bundle_path))
    _assert_bundle_target_identity(target=target, bundle=bundle)
    dry_receipt, dry_sha = _load_receipt(
        Path(dry_run_receipt_path), expected_kind=DRY_RUN_RECEIPT_KIND
    )
    _match_dry_receipt(dry_receipt, bundle=bundle, target=target)
    approval, approval_sha = _load_approval(
        Path(approval_artifact_path), operation="materialize", bundle=bundle
    )
    _assert_approval_target(approval, target=target)
    if _sha256_text(
        approval.get("dry_run_receipt_sha256"),
        "approval.dry_run_receipt_sha256",
    ) != dry_sha:
        raise CurrentRuleCohortError("approval dry-run receipt hash mismatch")

    lock = resolve_duckdb_writer_lock(target)
    with acquire_lock(lock, base_dir=target.parent):
        current_hash = _file_sha256(target)
        if current_hash != _sha256_text(
            approval.get("target_database_sha256"),
            "approval.target_database_sha256",
        ):
            existing = _exact_existing_materialization(target, bundle=bundle)
            if existing is not None:
                _validate_bundle_source_rows(target=target, bundle=bundle)
                recorded_backup = _verify_recorded_backup(
                    target=target,
                    backup_path=existing["backup_path"],
                    expected_sha256=existing["backup_sha256"],
                )
                prepared_receipt_path = Path(
                    str(existing["materialize_receipt_path"])
                ).resolve()
                if prepared_receipt_path != Path(receipt_path).resolve():
                    raise CurrentRuleCohortError(
                        "materialize replay must reuse the prepared receipt path"
                    )
                traced_sha = existing.get("materialize_receipt_sha256")
                if traced_sha is not None:
                    traced_receipt, observed_sha = _load_receipt(
                        prepared_receipt_path,
                        expected_kind=MATERIALIZE_RECEIPT_KIND,
                    )
                    expected_stable = {
                        "status": MATERIALIZED_STATUS,
                        "bundle_sha256": bundle.bundle_sha256,
                        "plan_digest_sha256": bundle.payload["plan_digest_sha256"],
                        "dry_run_receipt_sha256": dry_sha,
                        "approval_sha256": approval_sha,
                        "backup_path": str(recorded_backup["path"]),
                        "backup_sha256": recorded_backup["sha256"],
                        "controlled_schema_version": 46,
                        "source_availability_receipt_sha256s": list(
                            bundle.source_receipt_sha256s
                        ),
                        "summary": bundle.summary,
                        "created_at": str(existing["created_at"]),
                    }
                    if observed_sha != traced_sha or any(
                        traced_receipt.get(field) != expected
                        for field, expected in expected_stable.items()
                    ):
                        raise CurrentRuleCohortError(
                            "traced materialize receipt is missing or inconsistent"
                        )
                    return traced_receipt
                recovered_receipt = _materialize_receipt(
                    target=target,
                    bundle=bundle,
                    dry_sha=dry_sha,
                    approval_sha=approval_sha,
                    backup_path=recorded_backup["path"],
                    backup_sha=recorded_backup["sha256"],
                    created_at=str(existing["created_at"]),
                    receipt_path=Path(receipt_path),
                )
                _link_materialize_receipt_trace(
                    target=target,
                    bundle=bundle,
                    receipt_path=Path(receipt_path).resolve(),
                    receipt_sha256=str(recovered_receipt["canonical_receipt_sha256"]),
                )
                return recovered_receipt
            raise CurrentRuleCohortError("target database drifted after approval")

        if current_hash != str(dry_receipt["target_database_sha256_after"]):
            raise CurrentRuleCohortError("target database drifted after dry-run")
        _validate_bundle_source_rows(target=target, bundle=bundle)
        backup = _verify_prewrite_backup(target=target, backup_path=target_backup_path)

        conn = duckdb.connect(str(target))
        try:
            apply_stock_analysis_current_rule_cohort_schema_on_connection(conn)
            _assert_no_existing_duplicate_rows(conn, bundle=bundle, allow_exact_existing=False)
            conn.execute("begin transaction")
            try:
                _insert_materialized_bundle(
                    conn,
                    bundle=bundle,
                    dry_receipt_path=Path(dry_run_receipt_path).resolve(),
                    dry_receipt_sha=dry_sha,
                    approval_path=Path(approval_artifact_path).resolve(),
                    approval_sha=approval_sha,
                    materialize_receipt_path=Path(receipt_path).resolve(),
                    backup_path=backup["path"],
                    backup_sha=backup["sha256"],
                    created_at=_datetime_text(created_at),
                )
                _assert_persisted_cohort(conn, bundle=bundle, expected_status=MATERIALIZED_STATUS)
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
        finally:
            conn.close()
        materialize_receipt = _materialize_receipt(
            target=target,
            bundle=bundle,
            dry_sha=dry_sha,
            approval_sha=approval_sha,
            backup_path=backup["path"],
            backup_sha=backup["sha256"],
            created_at=created_at,
            receipt_path=Path(receipt_path),
        )
        _link_materialize_receipt_trace(
            target=target,
            bundle=bundle,
            receipt_path=Path(receipt_path).resolve(),
            receipt_sha256=str(materialize_receipt["canonical_receipt_sha256"]),
        )
        return materialize_receipt


def promote_stock_analysis_current_rule_cohort(
    *,
    duckdb_path: str | Path,
    bundle_path: str | Path,
    materialize_receipt_path: str | Path,
    approval_artifact_path: str | Path,
    receipt_path: str | Path,
    created_at: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Atomically supersede the prior active cohort and activate this cohort."""
    _require_write_switch(allow_write)
    target = _existing_file(duckdb_path, field_name="duckdb_path")
    bundle = _load_and_validate_bundle(Path(bundle_path))
    _assert_bundle_target_identity(target=target, bundle=bundle)
    materialize_receipt, materialize_sha = _load_receipt(
        Path(materialize_receipt_path), expected_kind=MATERIALIZE_RECEIPT_KIND
    )
    if materialize_receipt.get("bundle_sha256") != bundle.bundle_sha256:
        raise CurrentRuleCohortError("materialize receipt bundle hash mismatch")
    approval, approval_sha = _load_approval(
        Path(approval_artifact_path), operation="promote", bundle=bundle
    )
    _assert_approval_target(approval, target=target)
    if _sha256_text(
        approval.get("materialize_receipt_sha256"),
        "approval.materialize_receipt_sha256",
    ) != materialize_sha:
        raise CurrentRuleCohortError("approval materialize receipt hash mismatch")

    lock = resolve_duckdb_writer_lock(target)
    with acquire_lock(lock, base_dir=target.parent):
        current_hash = _file_sha256(target)
        if current_hash != _sha256_text(
            approval.get("target_database_sha256"),
            "approval.target_database_sha256",
        ):
            already_applied, prior_id = _promotion_already_applied(
                target,
                bundle=bundle,
                materialize_receipt_path=Path(materialize_receipt_path).resolve(),
                materialize_receipt_sha256=materialize_sha,
            )
            if not already_applied:
                raise CurrentRuleCohortError("target database drifted after promotion approval")
            _validate_bundle_source_rows(target=target, bundle=bundle)
            return _promotion_receipt(
                target=target,
                bundle=bundle,
                approval_sha=approval_sha,
                materialize_sha=materialize_sha,
                promoted_from=prior_id,
                created_at=created_at,
                idempotent=True,
                receipt_path=Path(receipt_path),
            )

        _validate_bundle_source_rows(target=target, bundle=bundle)
        conn = duckdb.connect(str(target))
        try:
            _assert_persisted_cohort(conn, bundle=bundle, expected_status=MATERIALIZED_STATUS)
            _assert_materialize_receipt_trace(
                conn,
                bundle=bundle,
                materialize_receipt_path=Path(materialize_receipt_path).resolve(),
                materialize_receipt_sha256=materialize_sha,
            )
            active_rows = _active_rows(conn)
            if len(active_rows) > 1:
                raise CurrentRuleCohortError("multiple active current-rule cohorts detected")
            promoted_from = str(active_rows[0][0]) if active_rows else None
            if promoted_from == bundle.payload["cohort_id"]:
                raise CurrentRuleCohortError("materialized cohort is already active with invalid status")
            now = _datetime_text(created_at)
            conn.execute("begin transaction")
            try:
                if promoted_from is not None:
                    superseded = conn.execute(
                        f"""
                        update {MANIFEST_TABLE}
                        set cohort_status = ?, is_active = false, superseded_at = ?
                        where cohort_id = ? and is_active = true
                        returning cohort_id
                        """,
                        [SUPERSEDED_STATUS, now, promoted_from],
                    ).fetchall()
                    if superseded != [(promoted_from,)]:
                        raise CurrentRuleCohortError(
                            "prior active cohort changed concurrently"
                        )
                updated = conn.execute(
                    f"""
                    update {MANIFEST_TABLE}
                    set cohort_status = ?, is_active = true, certified_at = ?, promoted_at = ?,
                        promoted_from_cohort_id = ?, promoted_by_run_id = ?
                    where cohort_id = ? and cohort_status = ? and is_active = false
                    returning cohort_id
                    """,
                    [
                        CERTIFIED_STATUS,
                        now,
                        now,
                        promoted_from,
                        _text(approval.get("run_id"), "approval.run_id"),
                        bundle.payload["cohort_id"],
                        MATERIALIZED_STATUS,
                    ],
                ).fetchall()
                if len(updated) != 1 or str(updated[0][0]) != bundle.payload["cohort_id"]:
                    raise CurrentRuleCohortError("promotion candidate state changed concurrently")
                if len(_active_rows(conn)) != 1:
                    raise CurrentRuleCohortError("promotion did not produce exactly one active cohort")
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
        finally:
            conn.close()

    return _promotion_receipt(
        target=target,
        bundle=bundle,
        approval_sha=approval_sha,
        materialize_sha=materialize_sha,
        promoted_from=promoted_from,
        created_at=created_at,
        idempotent=False,
        receipt_path=Path(receipt_path),
    )


def rollback_stock_analysis_current_rule_cohort_promotion(
    *,
    duckdb_path: str | Path,
    promotion_receipt_path: str | Path,
    approval_artifact_path: str | Path,
    receipt_path: str | Path,
    created_at: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Rollback only the active pointer; facts and date certificates are retained."""
    _require_write_switch(allow_write)
    target = _existing_file(duckdb_path, field_name="duckdb_path")
    promotion, promotion_sha = _load_receipt(
        Path(promotion_receipt_path), expected_kind=PROMOTION_RECEIPT_KIND
    )
    cohort_id = _text(promotion.get("cohort_id"), "promotion.cohort_id")
    raw_previous_id = promotion.get("promoted_from_cohort_id")
    previous_id = (
        _text(raw_previous_id, "promotion.promoted_from_cohort_id")
        if raw_previous_id is not None
        else None
    )
    approval, approval_sha = _load_operation_approval(
        Path(approval_artifact_path), operation="rollback_promotion"
    )
    _assert_approval_target(approval, target=target)
    if approval.get("cohort_id") != cohort_id:
        raise CurrentRuleCohortError("rollback approval cohort mismatch")
    if _sha256_text(
        approval.get("promotion_receipt_sha256"),
        "approval.promotion_receipt_sha256",
    ) != promotion_sha:
        raise CurrentRuleCohortError("rollback approval promotion receipt hash mismatch")

    lock = resolve_duckdb_writer_lock(target)
    with acquire_lock(lock, base_dir=target.parent):
        current_hash = _file_sha256(target)
        if current_hash != _sha256_text(
            approval.get("target_database_sha256"),
            "approval.target_database_sha256",
        ):
            already = _rollback_already_applied(target, cohort_id=cohort_id, previous_id=previous_id)
            if not already:
                raise CurrentRuleCohortError("target database drifted after rollback approval")
            return _rollback_receipt(
                target=target,
                cohort_id=cohort_id,
                previous_id=previous_id,
                promotion_sha=promotion_sha,
                approval_sha=approval_sha,
                created_at=created_at,
                idempotent=True,
                receipt_path=Path(receipt_path),
            )

        conn = duckdb.connect(str(target))
        try:
            active = _active_rows(conn)
            if len(active) != 1 or str(active[0][0]) != cohort_id:
                raise CurrentRuleCohortError("rollback target is not the unique active cohort")
            if previous_id is not None:
                prior = conn.execute(
                    f"select cohort_status from {MANIFEST_TABLE} where cohort_id = ?",
                    [previous_id],
                ).fetchall()
                if len(prior) != 1 or str(prior[0][0]) != SUPERSEDED_STATUS:
                    raise CurrentRuleCohortError(
                        "rollback predecessor is not uniquely superseded"
                    )
            now = _datetime_text(created_at)
            conn.execute("begin transaction")
            try:
                rolled = conn.execute(
                    f"""
                    update {MANIFEST_TABLE}
                    set cohort_status = ?, is_active = false, superseded_at = ?
                    where cohort_id = ? and is_active = true
                    returning cohort_id
                    """,
                    [ROLLED_BACK_STATUS, now, cohort_id],
                ).fetchall()
                restored: list[tuple[Any, ...]] = []
                if previous_id is not None:
                    restored = conn.execute(
                        f"""
                        update {MANIFEST_TABLE}
                        set cohort_status = ?, is_active = true, superseded_at = null
                        where cohort_id = ? and cohort_status = ? and is_active = false
                        returning cohort_id
                        """,
                        [CERTIFIED_STATUS, previous_id, SUPERSEDED_STATUS],
                    ).fetchall()
                if rolled != [(cohort_id,)] or (
                    previous_id is not None and restored != [(previous_id,)]
                ):
                    raise CurrentRuleCohortError("rollback cohort states changed concurrently")
                active_after = _active_rows(conn)
                if previous_id is None:
                    if active_after:
                        raise CurrentRuleCohortError(
                            "first-promotion rollback must leave no active cohort"
                        )
                elif len(active_after) != 1 or str(active_after[0][0]) != previous_id:
                    raise CurrentRuleCohortError(
                        "rollback did not restore exactly one predecessor"
                    )
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
        finally:
            conn.close()

    return _rollback_receipt(
        target=target,
        cohort_id=cohort_id,
        previous_id=previous_id,
        promotion_sha=promotion_sha,
        approval_sha=approval_sha,
        created_at=created_at,
        idempotent=False,
        receipt_path=Path(receipt_path),
    )


def _load_and_validate_bundle(path: Path) -> _ValidatedBundle:
    resolved, payload = _load_json(
        path, field_name="bundle_path", max_bytes=MAX_BUNDLE_JSON_INPUT_BYTES
    )
    if payload.get("bundle_kind") != BUNDLE_KIND or payload.get("schema_version") != 1:
        raise CurrentRuleCohortError("unsupported current-rule bundle contract")
    bundle_sha = _validate_self_hash(payload, "canonical_bundle_sha256")
    if payload.get("page_id") != PAGE_ID or payload.get("cohort_mode") != COHORT_MODE:
        raise CurrentRuleCohortError("bundle must target /stock-analysis current_rule_certified")
    _text(payload.get("cohort_id"), "bundle.cohort_id")
    _text(payload.get("run_id"), "bundle.run_id")
    _text(payload.get("idempotency_key"), "bundle.idempotency_key")
    plan_digest = _sha256_text(payload.get("plan_digest_sha256"), "bundle.plan_digest_sha256")
    plan = _mapping(payload.get("plan"), "bundle.plan")
    if _canonical_sha256(plan) != plan_digest:
        raise CurrentRuleCohortError("bundle plan_digest_sha256 does not match canonical plan")
    expected_plan_fields = {
        "plan_kind": "stock_analysis_current_rule_cohort_plan",
        "control_count": CONTROL_COUNT,
        "minimum_completed_dates": MIN_COMPLETED_DATES,
        "minimum_matched_entries": MIN_MATCHED_ENTRIES,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
    }
    for field, expected in expected_plan_fields.items():
        if plan.get(field) != expected:
            raise CurrentRuleCohortError(f"bundle plan field mismatch: {field}")
    _text(plan.get("governed_run_id"), "bundle.plan.governed_run_id")

    version = _mapping(payload.get("version_tuple"), "bundle.version_tuple")
    missing_versions = [field for field in REQUIRED_VERSION_TUPLE_FIELDS if field not in version]
    if missing_versions:
        raise CurrentRuleCohortError(
            "bundle version_tuple missing: " + ", ".join(missing_versions)
        )
    if version["stock_candidate_selection_policy"] != EXP3B_STOCK_CANDIDATE_POLICY:
        raise CurrentRuleCohortError("bundle selection policy must be exp3b")
    if version["stock_candidate_selection_formula_version"] != STOCK_CANDIDATE_FORMULA_VERSION:
        raise CurrentRuleCohortError("bundle candidate selection formula is not current v7")
    if version["matched_baseline_formula_version"] != MATCHED_BASELINE_FORMULA_VERSION:
        raise CurrentRuleCohortError(
            f"bundle matched-baseline formula is not current {MATCHED_BASELINE_FORMULA_VERSION}"
        )
    if version["decision_metric_basis"] != ALLOWED_DECISION_METRIC_BASIS:
        raise CurrentRuleCohortError("bundle decision basis must be net_next_open_adj")
    if version["coverage_authority_mode"] != CURRENT_RULE_COVERAGE_AUTHORITY_MODE:
        raise CurrentRuleCohortError("bundle calendar authority mode mismatch")
    if version["strict_coverage"] is not True or version["fallback_covered"] is not False:
        raise CurrentRuleCohortError("bundle must be strict coverage without fallback")
    for field in REQUIRED_VERSION_TUPLE_FIELDS:
        if field not in {"strict_coverage", "fallback_covered"}:
            _text(version[field], f"bundle.version_tuple.{field}")

    artifacts = _mapping(payload.get("artifacts"), "bundle.artifacts")
    calendar_ref = _mapping(artifacts.get("calendar_receipt"), "bundle.artifacts.calendar_receipt")
    calendar_path, calendar = _load_bundle_artifact(
        resolved, calendar_ref.get("path"), field_name="calendar_receipt"
    )
    ok, errors = validate_stock_analysis_calendar_receipt(calendar)
    if not ok:
        raise CurrentRuleCohortError("calendar receipt invalid: " + "; ".join(errors))
    calendar_sha = _sha256_text(
        calendar.get("canonical_receipt_sha256"), "calendar.canonical_receipt_sha256"
    )
    if calendar_sha != _sha256_text(calendar_ref.get("sha256"), "calendar_receipt.sha256"):
        raise CurrentRuleCohortError("calendar receipt reference hash mismatch")
    if calendar.get("authority_status") != APPROVED_AUTHORITY_STATUS:
        raise CurrentRuleCohortError("calendar receipt must be approved")
    if calendar.get("certification_allowed") is not True or not calendar.get("owner_approval_id"):
        raise CurrentRuleCohortError("calendar receipt lacks owner certification approval")

    evaluation = _date_text(payload.get("evaluation_as_of_date"), "bundle.evaluation_as_of_date")
    source_hashes: list[str] = []
    source_index: dict[tuple[str, str, str, str, str], str] = {}
    for index, raw_ref in enumerate(_list(artifacts.get("source_availability_receipts"), "source receipts")):
        ref = _mapping(raw_ref, f"source_receipts[{index}]")
        _, source_receipt = _load_bundle_artifact(
            resolved, ref.get("path"), field_name=f"source_receipts[{index}]"
        )
        source_sha = _canonical_sha256(source_receipt)
        if source_sha != _sha256_text(ref.get("sha256"), f"source_receipts[{index}].sha256"):
            raise CurrentRuleCohortError("source availability receipt reference hash mismatch")
        receipt_index = _validate_source_availability_receipt(
            source_receipt, evaluation=evaluation
        )
        duplicate_source_keys = set(source_index).intersection(receipt_index)
        if duplicate_source_keys:
            raise CurrentRuleCohortError("duplicate source availability key across receipts")
        source_index.update(receipt_index)
        if source_sha in source_hashes:
            raise CurrentRuleCohortError("duplicate source availability receipt hash")
        source_hashes.append(source_sha)
    if not source_hashes:
        raise CurrentRuleCohortError("at least one persisted source availability receipt is required")

    zero_by_date: dict[str, tuple[Path, str]] = {}
    for index, raw_ref in enumerate(_list(artifacts.get("zero_signal_certificates", []), "zero certificates")):
        ref = _mapping(raw_ref, f"zero_certificates[{index}]")
        zero_path, zero = _load_bundle_artifact(
            resolved, ref.get("path"), field_name=f"zero_certificates[{index}]"
        )
        validate_current_rule_zero_signal_certificate(zero)
        zero_sha = _sha256_text(zero.get("payload_sha256"), "zero.payload_sha256")
        if zero_sha != _sha256_text(ref.get("sha256"), f"zero_certificates[{index}].sha256"):
            raise CurrentRuleCohortError("zero-signal certificate reference hash mismatch")
        zero_date = _date_text(zero.get("trade_date"), "zero.trade_date")
        if zero_date in zero_by_date:
            raise CurrentRuleCohortError("duplicate zero-signal certificate date")
        if zero.get("cohort_id") != payload.get("cohort_id"):
            raise CurrentRuleCohortError("zero-signal certificate cohort mismatch")
        if zero.get("plan_digest_sha256") != payload.get("plan_digest_sha256"):
            raise CurrentRuleCohortError("zero-signal certificate plan mismatch")
        if zero.get("calendar_receipt_sha256") != calendar_sha:
            raise CurrentRuleCohortError("zero-signal certificate calendar mismatch")
        if zero.get("version_tuple") != version:
            raise CurrentRuleCohortError("zero-signal certificate version tuple mismatch")
        zero_by_date[zero_date] = (zero_path, zero_sha)

    facts = tuple(_mapping(row, f"facts[{index}]") for index, row in enumerate(_list(payload.get("facts"), "bundle.facts")))
    certificates = tuple(
        _mapping(row, f"date_certificates[{index}]")
        for index, row in enumerate(_list(payload.get("date_certificates"), "bundle.date_certificates"))
    )
    summary = _validate_business_rows(
        payload=payload,
        facts=facts,
        certificates=certificates,
        zero_by_date=zero_by_date,
        calendar=calendar,
        source_hashes=tuple(sorted(source_hashes)),
        source_index=source_index,
    )
    return _ValidatedBundle(
        path=resolved,
        payload=payload,
        bundle_sha256=bundle_sha,
        calendar_path=calendar_path,
        calendar_sha256=calendar_sha,
        source_receipt_sha256s=tuple(sorted(source_hashes)),
        source_availability_index=source_index,
        zero_certificates=zero_by_date,
        facts=facts,
        certificates=certificates,
        summary=summary,
    )


def _validate_business_rows(
    *,
    payload: dict[str, Any],
    facts: tuple[dict[str, Any], ...],
    certificates: tuple[dict[str, Any], ...],
    zero_by_date: dict[str, tuple[Path, str]],
    calendar: dict[str, Any],
    source_hashes: tuple[str, ...],
    source_index: dict[tuple[str, str, str, str, str], str],
) -> dict[str, int]:
    evaluation = _date_text(payload.get("evaluation_as_of_date"), "bundle.evaluation_as_of_date")
    fact_keys: set[tuple[str, str, str]] = set()
    facts_by_date: dict[str, int] = {}
    version = _mapping(payload.get("version_tuple"), "bundle.version_tuple")
    for index, fact in enumerate(facts):
        signal_date = _date_text(fact.get("signal_date"), f"facts[{index}].signal_date")
        stock_code = _text(fact.get("stock_code"), f"facts[{index}].stock_code")
        signal_kind = _text(fact.get("signal_kind"), f"facts[{index}].signal_kind")
        key = (signal_date, stock_code, signal_kind)
        if key in fact_keys:
            raise CurrentRuleCohortError(f"duplicate fact key: {key}")
        fact_keys.add(key)
        facts_by_date[signal_date] = facts_by_date.get(signal_date, 0) + 1
        if signal_kind != "stock_candidate":
            raise CurrentRuleCohortError("signal_kind must equal stock_candidate")
        if fact.get("entry_executable") is not True or fact.get("entry_price_kind") != "next_open":
            raise CurrentRuleCohortError("every candidate requires an executable next-open entry")
        _positive_number(fact.get("entry_price"), f"facts[{index}].entry_price")
        _positive_number(fact.get("exit_price_5d"), f"facts[{index}].exit_price_5d")
        _positive_number(fact.get("exit_price_20d"), f"facts[{index}].exit_price_20d")
        for metric in (
            "return_5d_net_adj",
            "return_20d_net_adj",
            "matched_alpha_5d",
            "matched_alpha_20d",
        ):
            _finite_number(fact.get(metric), f"facts[{index}].{metric}")
        if fact.get("price_adjustment_mode") != "adj_factor_ratio":
            raise CurrentRuleCohortError("every candidate requires adj_factor_ratio pricing")
        if fact.get("candidate_data_status") != "usable" or fact.get("execution_data_status") != "usable":
            raise CurrentRuleCohortError("candidate and execution rows must be usable")
        if fact.get("matched_baseline_status") != "usable":
            raise CurrentRuleCohortError("matched baseline must be usable")
        if fact.get("matched_baseline_control_count") != CONTROL_COUNT:
            raise CurrentRuleCohortError("every candidate must have exactly 20 controls")
        if fact.get("control_eval_basis") != ALLOWED_DECISION_METRIC_BASIS:
            raise CurrentRuleCohortError("control evaluation basis mismatch")
        entry = _date_text(fact.get("entry_date"), f"facts[{index}].entry_date")
        exit5 = _date_text(fact.get("exit_date_5d"), f"facts[{index}].exit_date_5d")
        exit20 = _date_text(fact.get("exit_date_20d"), f"facts[{index}].exit_date_20d")
        if not (signal_date < entry <= exit5 <= exit20 <= evaluation):
            raise CurrentRuleCohortError("candidate entry/T5/T20 dates violate PIT order")
        evidence = _mapping(fact.get("evidence"), f"facts[{index}].evidence")
        _validate_exact_candidate_source_evidence(
            evidence.get("candidate_source_evidence"),
            source_index=source_index,
            evaluation=evaluation,
            entry_date=entry,
            exit_date_5d=exit5,
            exit_date_20d=exit20,
        )
        proof = _mapping(fact.get("control_pit_proof"), f"facts[{index}].control_pit_proof")
        proof_hashes = sorted(
            _sha256_text(value, "control proof source receipt hash")
            for value in _list(
                proof.get("source_availability_receipt_sha256s"),
                "control proof source receipt hashes",
            )
        )
        if proof_hashes != list(source_hashes):
            raise CurrentRuleCohortError("control proof source receipts do not match bundle")
        controls = _list(proof.get("controls"), "control proof controls")
        if len(controls) != CONTROL_COUNT:
            raise CurrentRuleCohortError("control proof must contain exactly 20 rows")
        control_codes: set[str] = set()
        control_return_5d_total = 0.0
        control_return_20d_total = 0.0
        for control_index, raw_control in enumerate(controls):
            control = _mapping(raw_control, f"controls[{control_index}]")
            code = _text(control.get("control_stock_code"), "control_stock_code")
            if code == stock_code or code in control_codes:
                raise CurrentRuleCohortError("control codes must be unique and exclude candidate")
            control_codes.add(code)
            required_true = (
                control.get("control_entry_usable"),
                control.get("control_return_5d_usable"),
                control.get("control_return_20d_usable"),
            )
            if required_true != (True, True, True):
                raise CurrentRuleCohortError("entry, T5 and T20 control proof must all be usable")
            if any(
                control.get(field)
                for field in (
                    "control_entry_failure_reason",
                    "control_failure_reason_5d",
                    "control_failure_reason_20d",
                    "control_failure_reason",
                )
            ):
                raise CurrentRuleCohortError("usable control proof cannot carry a failure reason")
            if control.get("formula_version") != MATCHED_BASELINE_FORMULA_VERSION:
                raise CurrentRuleCohortError("control proof formula version mismatch")
            if control.get("metric_basis") != ALLOWED_DECISION_METRIC_BASIS:
                raise CurrentRuleCohortError("control proof metric basis mismatch")
            if control.get("price_adjustment_mode") != "adj_factor_ratio":
                raise CurrentRuleCohortError("control proof adjustment mode mismatch")
            if control.get("control_entry_price_kind") != "open":
                raise CurrentRuleCohortError("control proof entry must use next open")
            if control.get("evaluation_as_of_date") != evaluation:
                raise CurrentRuleCohortError("control proof evaluation date mismatch")
            if control.get("candidate_stock_code") != stock_code:
                raise CurrentRuleCohortError("control proof candidate stock mismatch")
            if control.get("signal_date") != signal_date or control.get("signal_kind") != signal_kind:
                raise CurrentRuleCohortError("control proof candidate key mismatch")
            control_entry = _date_text(control.get("control_entry_date"), "control_entry_date")
            control_exit5 = _date_text(control.get("control_exit_date_5d"), "control_exit_date_5d")
            control_exit20 = _date_text(control.get("control_exit_date_20d"), "control_exit_date_20d")
            if not (signal_date < control_entry <= control_exit5 <= control_exit20 <= evaluation):
                raise CurrentRuleCohortError("control entry/T5/T20 dates violate PIT order")
            if control.get("control_entry_executable") is not True:
                raise CurrentRuleCohortError("control entry must be executable")
            _positive_number(control.get("control_entry_price"), "control_entry_price")
            _positive_number(control.get("control_exit_price_5d"), "control_exit_price_5d")
            _positive_number(control.get("control_exit_price_20d"), "control_exit_price_20d")
            control_return_5d_total += _finite_number(
                control.get("control_return_5d_net_adj"),
                "control_return_5d_net_adj",
            )
            control_return_20d_total += _finite_number(
                control.get("control_return_20d_net_adj"),
                "control_return_20d_net_adj",
            )
            _validate_exact_control_source_evidence(
                control.get("source_evidence"),
                source_index=source_index,
                evaluation=evaluation,
                entry_date=control_entry,
                exit_date_5d=control_exit5,
                exit_date_20d=control_exit20,
            )
        expected_alpha_5d = _finite_number(
            fact.get("return_5d_net_adj"),
            f"facts[{index}].return_5d_net_adj",
        ) - (control_return_5d_total / CONTROL_COUNT)
        expected_alpha_20d = _finite_number(
            fact.get("return_20d_net_adj"),
            f"facts[{index}].return_20d_net_adj",
        ) - (control_return_20d_total / CONTROL_COUNT)
        if abs(expected_alpha_5d - float(fact["matched_alpha_5d"])) > 1e-12:
            raise CurrentRuleCohortError("matched_alpha_5d must equal candidate minus 20-control mean")
        if abs(expected_alpha_20d - float(fact["matched_alpha_20d"])) > 1e-12:
            raise CurrentRuleCohortError("matched_alpha_20d must equal candidate minus 20-control mean")

        for field in ROW_VERSION_FIELDS:
            if field not in fact or fact[field] != version[field]:
                raise CurrentRuleCohortError(f"fact version mismatch: {field}")

    cert_dates: set[str] = set()
    completed_with_signals = 0
    completed_no_signals = 0
    fact_keys_by_date: dict[str, list[tuple[str, str, str]]] = {}
    for signal_date, stock_code, signal_kind in fact_keys:
        fact_keys_by_date.setdefault(signal_date, []).append(
            (signal_date, stock_code, signal_kind)
        )
    for date_key in fact_keys_by_date:
        fact_keys_by_date[date_key].sort()
    calendar_rows = {
        str(row["cal_date"]): row
        for row in _list(calendar.get("calendar_rows"), "calendar rows")
        if isinstance(row, dict)
    }
    for index, cert in enumerate(certificates):
        trade_date = _date_text(cert.get("trade_date"), f"date_certificates[{index}].trade_date")
        if trade_date in cert_dates:
            raise CurrentRuleCohortError(f"duplicate date certificate: {trade_date}")
        cert_dates.add(trade_date)
        if calendar_rows.get(trade_date, {}).get("is_open") != 1:
            raise CurrentRuleCohortError("certified date is not open in approved calendar")
        if cert.get("affects_completed_stats") is not True:
            raise CurrentRuleCohortError("every bundled certificate must affect completed stats")
        for field in ROW_VERSION_FIELDS:
            if field not in cert or cert[field] != version[field]:
                raise CurrentRuleCohortError(
                    f"date certificate version mismatch: {field}"
                )
        row_count = facts_by_date.get(trade_date, 0)
        status = cert.get("certificate_status")
        if row_count:
            completed_with_signals += 1
            if status != SIGNAL_CERTIFICATE_STATUS:
                raise CurrentRuleCohortError("signal date certificate status mismatch")
            if trade_date in zero_by_date:
                raise CurrentRuleCohortError("signal date cannot have zero-signal certificate")
            _validate_runner_candidate_key_proof(
                cert=cert,
                trade_date=trade_date,
                expected_fact_keys=fact_keys_by_date.get(trade_date, []),
            )
        else:
            completed_no_signals += 1
            if status != CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS:
                raise CurrentRuleCohortError("zero-signal date certificate status mismatch")
            if trade_date not in zero_by_date:
                raise CurrentRuleCohortError("zero-signal date lacks persisted certificate")
        expected = {
            "candidate_count": row_count,
            "executable_candidate_count": row_count,
            "t5_usable_count": row_count,
            "t20_usable_count": row_count,
            "matched_entry_count": row_count,
            "control_entry_proven_count": row_count * CONTROL_COUNT,
            "control_exit_proven_5d_count": row_count * CONTROL_COUNT,
            "control_exit_proven_20d_count": row_count * CONTROL_COUNT,
            "stale_execution_row_count": 0,
            "stale_matched_baseline_row_count": 0,
            "unsupported_source_count": 0,
            "proxy_only_evidence_count": 0,
            "blocking_gap_count": 0,
        }
        for field, value in expected.items():
            if cert.get(field) != value:
                raise CurrentRuleCohortError(f"date certificate count mismatch: {field}")
        control_eval_proof = _mapping(
            cert.get("control_eval_proof"),
            f"date_certificates[{index}].control_eval_proof",
        )
        cert_source_hashes = sorted(
            _sha256_text(value, "date certificate source receipt hash")
            for value in _list(
                control_eval_proof.get("source_availability_receipt_sha256s"),
                "date certificate source receipt hashes",
            )
        )
        if cert_source_hashes != list(source_hashes):
            raise CurrentRuleCohortError(
                "date certificate source receipts do not match bundle"
            )
        source_coverage = _mapping(
            cert.get("source_coverage"),
            f"date_certificates[{index}].source_coverage",
        )
        if source_coverage.get("strict") is not True or source_coverage.get("fallback") is not False:
            raise CurrentRuleCohortError("date certificate must be strict without fallback")

    if set(facts_by_date) - cert_dates:
        raise CurrentRuleCohortError("facts exist without date certificates")
    if set(zero_by_date) != {date_key for date_key in cert_dates if date_key not in facts_by_date}:
        raise CurrentRuleCohortError("zero-signal artifact set does not match certified zero dates")
    bounds = _mapping(payload.get("date_bounds"), "bundle.date_bounds")
    requested_start = _date_text(bounds.get("requested_start_date"), "requested_start_date")
    requested_end = _date_text(bounds.get("requested_end_date"), "requested_end_date")
    observed_start = _date_text(bounds.get("observed_start_date"), "observed_start_date")
    observed_end = _date_text(bounds.get("observed_end_date"), "observed_end_date")
    certified_start = _date_text(bounds.get("certified_start_date"), "certified_start_date")
    certified_end = _date_text(bounds.get("certified_end_date"), "certified_end_date")
    governed_start = _date_text(bounds.get("governed_era_start"), "governed_era_start")
    governed_end = _date_text(bounds.get("governed_era_end"), "governed_era_end")
    if not (
        requested_start == observed_start == certified_start
        and requested_end == observed_end == certified_end
    ):
        raise CurrentRuleCohortError("requested, observed and certified bounds must align")
    if not (governed_start <= certified_start <= certified_end <= governed_end <= evaluation):
        raise CurrentRuleCohortError("governed era and evaluation bounds are inconsistent")
    request = _mapping(calendar.get("request"), "calendar.request")
    if request.get("start_date") != requested_start or request.get("end_date") != requested_end:
        raise CurrentRuleCohortError("calendar request bounds do not match cohort bounds")
    required_open_dates = {
        cal_date
        for cal_date, row in calendar_rows.items()
        if certified_start <= cal_date <= certified_end and row.get("is_open") == 1
    }
    if cert_dates != required_open_dates:
        raise CurrentRuleCohortError("strict coverage requires every approved open date")
    if cert_dates and (min(cert_dates) != certified_start or max(cert_dates) != certified_end):
        raise CurrentRuleCohortError("certified bounds do not match certificate range")
    summary = {
        "completed_dates": len(cert_dates),
        "completed_with_signals_dates": completed_with_signals,
        "completed_no_signal_dates": completed_no_signals,
        "pending_tail_dates": 0,
        "blocking_pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "matched_entry_count": len(fact_keys),
        "t5_usable_count": len(fact_keys),
        "t20_usable_count": len(fact_keys),
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }
    declared = _mapping(payload.get("summary"), "bundle.summary")
    if any(declared.get(key) != value for key, value in summary.items()):
        raise CurrentRuleCohortError("bundle summary does not match certified rows")
    if summary["completed_dates"] < MIN_COMPLETED_DATES:
        raise CurrentRuleCohortError("completed_dates must be at least 20")
    if summary["matched_entry_count"] < MIN_MATCHED_ENTRIES:
        raise CurrentRuleCohortError("matched_entry_count must be at least 100")
    return summary


def _validate_runner_candidate_key_proof(
    *,
    cert: Mapping[str, Any],
    trade_date: str,
    expected_fact_keys: list[tuple[str, str, str]],
) -> None:
    blocker_detail = _mapping(cert.get("blocker_detail"), "date_certificate.blocker_detail")
    proof = _mapping(
        blocker_detail.get("runner_candidate_key_proof"),
        "date_certificate.blocker_detail.runner_candidate_key_proof",
    )
    candidate_keys = [
        (
            _date_text(row.get("signal_date"), "runner_candidate_key_proof.signal_date"),
            _text(row.get("stock_code"), "runner_candidate_key_proof.stock_code"),
            _text(row.get("signal_kind"), "runner_candidate_key_proof.signal_kind"),
        )
        for row in _list(proof.get("candidate_keys"), "runner_candidate_key_proof.candidate_keys")
        for row in [_mapping(row, "runner_candidate_key_proof.candidate_key")]
    ]
    if any(date_key != trade_date for date_key, _, _ in candidate_keys):
        raise CurrentRuleCohortError("runner candidate proof trade_date mismatch")
    if sorted(candidate_keys) != expected_fact_keys:
        raise CurrentRuleCohortError("runner candidate proof does not match fact key set")
    candidate_key_sha = _sha256_text(
        proof.get("candidate_key_sha256"),
        "runner_candidate_key_proof.candidate_key_sha256",
    )
    payload = [
        {
            "signal_date": signal_date,
            "signal_kind": signal_kind,
            "stock_code": stock_code,
        }
        for signal_date, stock_code, signal_kind in candidate_keys
    ]
    if _canonical_sha256(payload) != candidate_key_sha:
        raise CurrentRuleCohortError("runner candidate proof sha mismatch")
    if proof.get("runner_candidate_count") != len(expected_fact_keys):
        raise CurrentRuleCohortError("runner candidate proof count mismatch")


def _insert_materialized_bundle(
    conn: duckdb.DuckDBPyConnection,
    *,
    bundle: _ValidatedBundle,
    dry_receipt_path: Path,
    dry_receipt_sha: str,
    approval_path: Path,
    approval_sha: str,
    materialize_receipt_path: Path,
    backup_path: Path,
    backup_sha: str,
    created_at: str,
) -> None:
    payload = bundle.payload
    version = _mapping(payload["version_tuple"], "bundle.version_tuple")
    bounds = _mapping(payload.get("date_bounds"), "bundle.date_bounds")
    for key in (
        "requested_start_date",
        "requested_end_date",
        "observed_start_date",
        "observed_end_date",
        "certified_start_date",
        "certified_end_date",
        "governed_era_start",
        "governed_era_end",
    ):
        _date_text(bounds.get(key), f"bundle.date_bounds.{key}")
    notes = {
        "bundle_path": str(bundle.path),
        "bundle_sha256": bundle.bundle_sha256,
        "approval_path": str(approval_path),
        "approval_sha256": approval_sha,
        "manifest_receipt_role": "dry_run_receipt",
        "date_certificate_receipt_role": "certified_bundle",
        "materialize_receipt_path": str(materialize_receipt_path),
        "materialize_receipt_role": "post_commit_external_receipt_expected",
        "controlled_schema_version": 46,
        "source_availability_receipt_sha256s": list(bundle.source_receipt_sha256s),
        "zero_signal_certificate_sha256s": sorted(
            value[1] for value in bundle.zero_certificates.values()
        ),
    }
    manifest = {
        "cohort_id": payload["cohort_id"],
        "page_id": PAGE_ID,
        "cohort_mode": COHORT_MODE,
        "cohort_status": MATERIALIZED_STATUS,
        "is_active": False,
        **bounds,
        "evaluation_as_of_date": payload["evaluation_as_of_date"],
        **{field: version[field] for field in REQUIRED_VERSION_TUPLE_FIELDS},
        "calendar_source_id": "tushare.trade_cal:SSE",
        "calendar_source_version": bundle.calendar_sha256,
        "source_lineage_json": _json_text(payload.get("source_lineage", {})),
        "plan_digest_sha256": payload["plan_digest_sha256"],
        "receipt_path": str(dry_receipt_path),
        "receipt_sha256": dry_receipt_sha,
        "calendar_receipt_path": str(bundle.calendar_path),
        "calendar_receipt_sha256": bundle.calendar_sha256,
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha,
        "run_id": payload["run_id"],
        "idempotency_key": payload["idempotency_key"],
        **bundle.summary,
        "audit_counts_json": _json_text(bundle.summary),
        "blocker_summary_json": _json_text({}),
        "notes_json": _json_text(notes),
        "created_at": created_at,
    }
    _insert_rows(conn, MANIFEST_TABLE, [manifest])

    fact_rows: list[dict[str, Any]] = []
    for raw in bundle.facts:
        row = dict(raw)
        row["control_pit_proof_json"] = _json_text(row.pop("control_pit_proof"))
        row["evidence_json"] = _json_text(row.pop("evidence", {}))
        row.update(
            {
                "cohort_id": payload["cohort_id"],
                "run_id": payload["run_id"],
                "created_at": created_at,
                **{
                    field: version[field]
                    for field in (
                        "candidate_rule_version",
                        "stock_candidate_selection_formula_version",
                        "candidate_outcome_formula_version",
                        "execution_formula_version",
                        "matched_baseline_formula_version",
                        "stock_candidate_selection_policy",
                        "decision_metric_basis",
                        "coverage_authority_mode",
                        "strict_coverage",
                        "fallback_covered",
                        "candidate_source_version",
                        "execution_source_version",
                        "matched_baseline_source_version",
                    )
                },
            }
        )
        fact_rows.append(row)
    _insert_rows(conn, FACT_TABLE, fact_rows)

    certificate_rows: list[dict[str, Any]] = []
    for raw in bundle.certificates:
        row = dict(raw)
        trade_date = str(row["trade_date"])
        row["control_eval_proof_json"] = _json_text(row.pop("control_eval_proof", {}))
        row["source_coverage_json"] = _json_text(row.pop("source_coverage", {}))
        row["blocker_detail_json"] = _json_text(row.pop("blocker_detail", {}))
        zero = bundle.zero_certificates.get(trade_date)
        row.update(
            {
                "cohort_id": payload["cohort_id"],
                "run_id": payload["run_id"],
                "created_at": created_at,
                **{
                    field: version[field]
                    for field in (
                        "candidate_rule_version",
                        "stock_candidate_selection_formula_version",
                        "candidate_outcome_formula_version",
                        "execution_formula_version",
                        "matched_baseline_formula_version",
                        "stock_candidate_selection_policy",
                        "decision_metric_basis",
                        "coverage_authority_mode",
                        "strict_coverage",
                        "fallback_covered",
                        "candidate_source_version",
                        "execution_source_version",
                        "matched_baseline_source_version",
                    )
                },
                "calendar_source_id": "tushare.trade_cal:SSE",
                "calendar_source_version": bundle.calendar_sha256,
                "calendar_receipt_path": str(bundle.calendar_path),
                "calendar_receipt_sha256": bundle.calendar_sha256,
                "zero_signal_certificate_path": str(zero[0]) if zero else None,
                "zero_signal_certificate_sha256": zero[1] if zero else None,
                "receipt_path": str(bundle.path),
                "receipt_sha256": bundle.bundle_sha256,
            }
        )
        certificate_rows.append(row)
    _insert_rows(conn, CERTIFICATE_TABLE, certificate_rows)


def _insert_rows(conn: duckdb.DuckDBPyConnection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = [str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()]
    known = set(columns)
    for row in rows:
        unknown = set(row) - known
        if unknown:
            raise CurrentRuleCohortError(f"{table} row has unknown fields: {sorted(unknown)}")
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    conn.executemany(
        f"insert into {table} ({column_sql}) values ({placeholders})",
        [[row.get(column) for column in columns] for row in rows],
    )


def _assert_persisted_cohort(
    conn: duckdb.DuckDBPyConnection,
    *,
    bundle: _ValidatedBundle,
    expected_status: str,
) -> None:
    cohort_id = str(bundle.payload["cohort_id"])
    manifests = conn.execute(
        f"select cohort_status, notes_json from {MANIFEST_TABLE} where cohort_id = ?",
        [cohort_id],
    ).fetchall()
    if len(manifests) != 1 or str(manifests[0][0]) != expected_status:
        raise CurrentRuleCohortError("persisted manifest state mismatch")
    notes = json.loads(str(manifests[0][1]))
    if notes.get("bundle_sha256") != bundle.bundle_sha256:
        raise CurrentRuleCohortError("persisted manifest bundle hash mismatch")
    fact_count_row = conn.execute(f"select count(*) from {FACT_TABLE} where cohort_id = ?", [cohort_id]).fetchone()
    cert_count_row = conn.execute(f"select count(*) from {CERTIFICATE_TABLE} where cohort_id = ?", [cohort_id]).fetchone()
    fact_count = cast(tuple[int], fact_count_row)[0]
    cert_count = cast(tuple[int], cert_count_row)[0]
    if fact_count != len(bundle.facts) or cert_count != len(bundle.certificates):
        raise CurrentRuleCohortError("persisted cohort row counts mismatch")
    fact_duplicates_row = conn.execute(
        f"""
        select count(*) from (
          select signal_date, stock_code, signal_kind
          from {FACT_TABLE} where cohort_id = ?
          group by 1, 2, 3 having count(*) <> 1
        )
        """,
        [cohort_id],
    ).fetchone()
    cert_duplicates_row = conn.execute(
        f"""
        select count(*) from (
          select trade_date from {CERTIFICATE_TABLE} where cohort_id = ?
          group by 1 having count(*) <> 1
        )
        """,
        [cohort_id],
    ).fetchone()
    fact_duplicates = cast(tuple[int], fact_duplicates_row)[0]
    cert_duplicates = cast(tuple[int], cert_duplicates_row)[0]
    if fact_duplicates or cert_duplicates:
        raise CurrentRuleCohortError("persisted cohort contains duplicate natural keys")
    stored_facts = conn.execute(
        f"""
        select signal_date, stock_code, signal_kind,
               entry_date, entry_price, entry_price_kind, entry_executable,
               exit_date_5d, return_5d_net_adj, exit_date_20d, return_20d_net_adj,
               matched_baseline_status, matched_baseline_control_count,
               matched_alpha_5d, matched_alpha_20d, control_eval_basis,
               control_pit_proof_json, strict_coverage, fallback_covered
        from {FACT_TABLE}
        where cohort_id = ?
        order by signal_date, stock_code, signal_kind
        """,
        [cohort_id],
    ).fetchall()
    expected_facts = sorted(
        (
            row["signal_date"],
            row["stock_code"],
            row["signal_kind"],
            row["entry_date"],
            float(row["entry_price"]),
            row["entry_price_kind"],
            row["entry_executable"],
            row["exit_date_5d"],
            float(row["return_5d_net_adj"]),
            row["exit_date_20d"],
            float(row["return_20d_net_adj"]),
            row["matched_baseline_status"],
            row["matched_baseline_control_count"],
            float(row["matched_alpha_5d"]),
            float(row["matched_alpha_20d"]),
            row["control_eval_basis"],
            _json_text(row["control_pit_proof"]),
            True,
            False,
        )
        for row in bundle.facts
    )
    if stored_facts != expected_facts:
        raise CurrentRuleCohortError("persisted fact payload does not match bundle")

    stored_certificates = conn.execute(
        f"""
        select trade_date, certificate_status, affects_completed_stats,
               candidate_count, executable_candidate_count, t5_usable_count,
               t20_usable_count, matched_entry_count,
               stale_execution_row_count, stale_matched_baseline_row_count,
               unsupported_source_count, proxy_only_evidence_count, blocking_gap_count,
               control_entry_proven_count, control_exit_proven_5d_count,
               control_exit_proven_20d_count, control_eval_proof_json,
               zero_signal_certificate_sha256, calendar_receipt_sha256,
               strict_coverage, fallback_covered
        from {CERTIFICATE_TABLE}
        where cohort_id = ?
        order by trade_date
        """,
        [cohort_id],
    ).fetchall()
    expected_certificates = []
    for row in sorted(bundle.certificates, key=lambda item: str(item["trade_date"])):
        zero = bundle.zero_certificates.get(str(row["trade_date"]))
        expected_certificates.append(
            (
                row["trade_date"],
                row["certificate_status"],
                row["affects_completed_stats"],
                row["candidate_count"],
                row["executable_candidate_count"],
                row["t5_usable_count"],
                row["t20_usable_count"],
                row["matched_entry_count"],
                row["stale_execution_row_count"],
                row["stale_matched_baseline_row_count"],
                row["unsupported_source_count"],
                row["proxy_only_evidence_count"],
                row["blocking_gap_count"],
                row["control_entry_proven_count"],
                row["control_exit_proven_5d_count"],
                row["control_exit_proven_20d_count"],
                _json_text(row["control_eval_proof"]),
                zero[1] if zero else None,
                bundle.calendar_sha256,
                True,
                False,
            )
        )
    if stored_certificates != expected_certificates:
        raise CurrentRuleCohortError("persisted date certificate payload does not match bundle")


def _assert_materialize_receipt_trace(
    conn: duckdb.DuckDBPyConnection,
    *,
    bundle: _ValidatedBundle,
    materialize_receipt_path: Path,
    materialize_receipt_sha256: str,
) -> None:
    row = conn.execute(
        f"select notes_json from {MANIFEST_TABLE} where cohort_id = ?",
        [bundle.payload["cohort_id"]],
    ).fetchone()
    if row is None:
        raise CurrentRuleCohortError("materialize receipt trace lacks manifest")
    notes = json.loads(str(row[0]))
    if notes.get("manifest_receipt_role") != "dry_run_receipt":
        raise CurrentRuleCohortError("manifest receipt role is not dry-run")
    if notes.get("date_certificate_receipt_role") != "certified_bundle":
        raise CurrentRuleCohortError("date certificate receipt role is not bundle")
    if Path(str(notes.get("materialize_receipt_path"))).resolve() != materialize_receipt_path:
        raise CurrentRuleCohortError("materialize receipt path is not traceable from manifest")
    if notes.get("materialize_receipt_sha256") != materialize_receipt_sha256:
        raise CurrentRuleCohortError("materialize receipt hash is not traceable from manifest")
    if notes.get("materialize_receipt_role") != "post_commit_external_receipt_linked":
        raise CurrentRuleCohortError("materialize receipt trace is not linked")
    if notes.get("controlled_schema_version") != 46:
        raise CurrentRuleCohortError("materialize receipt trace schema version mismatch")


def _link_materialize_receipt_trace(
    *,
    target: Path,
    bundle: _ValidatedBundle,
    receipt_path: Path,
    receipt_sha256: str,
) -> None:
    receipt, observed_sha = _load_receipt(
        receipt_path,
        expected_kind=MATERIALIZE_RECEIPT_KIND,
    )
    expected_sha = _sha256_text(receipt_sha256, "materialize receipt sha256")
    if observed_sha != expected_sha or receipt.get("bundle_sha256") != bundle.bundle_sha256:
        raise CurrentRuleCohortError("materialize receipt cannot be linked to bundle")
    conn = duckdb.connect(str(target))
    try:
        conn.execute("begin transaction")
        try:
            row = conn.execute(
                f"""
                select cohort_status, is_active, notes_json
                from {MANIFEST_TABLE}
                where cohort_id = ?
                """,
                [bundle.payload["cohort_id"]],
            ).fetchone()
            if row is None or str(row[0]) != MATERIALIZED_STATUS or bool(row[1]):
                raise CurrentRuleCohortError(
                    "materialize receipt may only link to materialized_unpromoted cohort"
                )
            notes = json.loads(str(row[2]))
            if notes.get("controlled_schema_version") != 46:
                raise CurrentRuleCohortError("controlled schema version trace mismatch")
            if Path(str(notes.get("materialize_receipt_path"))).resolve() != receipt_path:
                raise CurrentRuleCohortError("materialize receipt path differs from prepared trace")
            existing_sha = notes.get("materialize_receipt_sha256")
            if existing_sha is not None and existing_sha != expected_sha:
                raise CurrentRuleCohortError("materialize receipt trace hash conflict")
            if existing_sha is None:
                notes["materialize_receipt_sha256"] = expected_sha
                notes["materialize_receipt_role"] = (
                    "post_commit_external_receipt_linked"
                )
                updated = conn.execute(
                    f"""
                    update {MANIFEST_TABLE}
                    set notes_json = ?
                    where cohort_id = ? and cohort_status = ? and is_active = false
                    returning cohort_id
                    """,
                    [
                        _json_text(notes),
                        bundle.payload["cohort_id"],
                        MATERIALIZED_STATUS,
                    ],
                ).fetchall()
                if updated != [(bundle.payload["cohort_id"],)]:
                    raise CurrentRuleCohortError(
                        "materialize receipt trace state changed concurrently"
                    )
            elif notes.get("materialize_receipt_role") != "post_commit_external_receipt_linked":
                raise CurrentRuleCohortError("materialize receipt trace role conflict")
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
    finally:
        conn.close()


def _assert_no_existing_duplicate_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    bundle: _ValidatedBundle,
    allow_exact_existing: bool,
) -> None:
    if not _table_exists(conn, MANIFEST_TABLE):
        return
    rows = conn.execute(
        f"""
        select cohort_id, idempotency_key, plan_digest_sha256, notes_json
        from {MANIFEST_TABLE}
        where cohort_id = ? or idempotency_key = ?
        """,
        [bundle.payload["cohort_id"], bundle.payload["idempotency_key"]],
    ).fetchall()
    if not rows:
        return
    if allow_exact_existing and len(rows) == 1:
        notes = json.loads(str(rows[0][3]))
        if (
            str(rows[0][0]) == bundle.payload["cohort_id"]
            and str(rows[0][1]) == bundle.payload["idempotency_key"]
            and str(rows[0][2]) == bundle.payload["plan_digest_sha256"]
            and notes.get("bundle_sha256") == bundle.bundle_sha256
        ):
            return
    raise CurrentRuleCohortError("cohort_id or idempotency_key already exists")


def _exact_existing_materialization(
    target: Path,
    *,
    bundle: _ValidatedBundle,
) -> dict[str, Any] | None:
    conn = duckdb.connect(str(target), read_only=True)
    try:
        if not _table_exists(conn, MANIFEST_TABLE):
            return None
        rows = conn.execute(
            f"""
            select cohort_status, plan_digest_sha256, notes_json, backup_path, backup_sha256,
                   created_at
            from {MANIFEST_TABLE}
            where cohort_id = ? and idempotency_key = ?
            """,
            [bundle.payload["cohort_id"], bundle.payload["idempotency_key"]],
        ).fetchall()
        if len(rows) != 1:
            return None
        notes = json.loads(str(rows[0][2]))
        if (
            str(rows[0][1]) != bundle.payload["plan_digest_sha256"]
            or notes.get("bundle_sha256") != bundle.bundle_sha256
        ):
            return None
        status = str(rows[0][0])
        if status != MATERIALIZED_STATUS:
            raise CurrentRuleCohortError(
                "materialize replay is forbidden after cohort lifecycle advancement"
            )
        _assert_persisted_cohort(
            conn,
            bundle=bundle,
            expected_status=MATERIALIZED_STATUS,
        )
        if notes.get("materialize_receipt_sha256") is not None and notes.get(
            "materialize_receipt_role"
        ) != "post_commit_external_receipt_linked":
            raise CurrentRuleCohortError("materialize receipt trace role is inconsistent")
        if notes.get("controlled_schema_version") != 46:
            raise CurrentRuleCohortError("controlled schema version trace is inconsistent")
        return {
            "backup_path": rows[0][3],
            "backup_sha256": rows[0][4],
            "materialize_receipt_path": notes.get("materialize_receipt_path"),
            "materialize_receipt_sha256": notes.get("materialize_receipt_sha256"),
            "controlled_schema_version": notes.get("controlled_schema_version"),
            "created_at": rows[0][5],
        }
    finally:
        conn.close()


def _promotion_already_applied(
    target: Path,
    *,
    bundle: _ValidatedBundle,
    materialize_receipt_path: Path,
    materialize_receipt_sha256: str,
) -> tuple[bool, str | None]:
    conn = duckdb.connect(str(target), read_only=True)
    try:
        active = _active_rows(conn)
        if len(active) != 1 or str(active[0][0]) != bundle.payload["cohort_id"]:
            return False, None
        row = conn.execute(
            f"select cohort_status, promoted_from_cohort_id from {MANIFEST_TABLE} where cohort_id = ?",
            [bundle.payload["cohort_id"]],
        ).fetchone()
        if row is None or str(row[0]) != CERTIFIED_STATUS:
            return False, None
        _assert_persisted_cohort(
            conn,
            bundle=bundle,
            expected_status=CERTIFIED_STATUS,
        )
        _assert_materialize_receipt_trace(
            conn,
            bundle=bundle,
            materialize_receipt_path=materialize_receipt_path,
            materialize_receipt_sha256=_sha256_text(
                materialize_receipt_sha256,
                "materialize receipt sha256",
            ),
        )
        return True, str(row[1]) if row[1] is not None else None
    finally:
        conn.close()


def _rollback_already_applied(
    target: Path,
    *,
    cohort_id: str,
    previous_id: str | None,
) -> bool:
    conn = duckdb.connect(str(target), read_only=True)
    try:
        active = _active_rows(conn)
        row = conn.execute(
            f"select cohort_status from {MANIFEST_TABLE} where cohort_id = ?", [cohort_id]
        ).fetchone()
        target_rolled_back = row is not None and str(row[0]) == ROLLED_BACK_STATUS
        if previous_id is None:
            return not active and target_rolled_back
        return (
            len(active) == 1
            and str(active[0][0]) == previous_id
            and target_rolled_back
        )
    finally:
        conn.close()


def _active_rows(conn: duckdb.DuckDBPyConnection) -> list[tuple[Any, ...]]:
    rows = conn.execute(
        f"""
        select cohort_id, cohort_status from {MANIFEST_TABLE}
        where page_id = ? and cohort_mode = ? and is_active = true
        order by cohort_id
        """,
        [PAGE_ID, COHORT_MODE],
    ).fetchall()
    if any(str(row[1]) != CERTIFIED_STATUS for row in rows):
        raise CurrentRuleCohortError("active cohort must have certified status")
    return rows


def _materialize_receipt(
    *,
    target: Path,
    bundle: _ValidatedBundle,
    dry_sha: str,
    approval_sha: str,
    backup_path: Path,
    backup_sha: str,
    created_at: str | None,
    receipt_path: Path,
) -> dict[str, Any]:
    content = {
        "schema_version": 1,
        "receipt_kind": MATERIALIZE_RECEIPT_KIND,
        "status": MATERIALIZED_STATUS,
        "cohort_id": bundle.payload["cohort_id"],
        "bundle_sha256": bundle.bundle_sha256,
        "plan_digest_sha256": bundle.payload["plan_digest_sha256"],
        "dry_run_receipt_sha256": dry_sha,
        "approval_sha256": approval_sha,
        "target_database_sha256_after_materialization_before_receipt_trace": _file_sha256(
            target
        ),
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha,
        "controlled_schema_version": 46,
        "source_availability_receipt_sha256s": list(bundle.source_receipt_sha256s),
        "summary": bundle.summary,
        "created_at": _datetime_text(created_at),
    }
    existing = _existing_bound_receipt(
        receipt_path,
        expected_kind=MATERIALIZE_RECEIPT_KIND,
        cohort_id=str(bundle.payload["cohort_id"]),
        bundle_sha256=bundle.bundle_sha256,
        expected_fields=content,
    )
    if existing is not None:
        return existing
    receipt = _seal(content, hash_field="canonical_receipt_sha256")
    _write_new_or_identical_json(receipt_path, receipt)
    return receipt


def _promotion_receipt(
    *,
    target: Path,
    bundle: _ValidatedBundle,
    approval_sha: str,
    materialize_sha: str,
    promoted_from: str | None,
    created_at: str | None,
    idempotent: bool,
    receipt_path: Path,
) -> dict[str, Any]:
    content = {
        "schema_version": 1,
        "receipt_kind": PROMOTION_RECEIPT_KIND,
        "status": CERTIFIED_STATUS,
        "cohort_id": bundle.payload["cohort_id"],
        "promoted_from_cohort_id": promoted_from,
        "bundle_sha256": bundle.bundle_sha256,
        "plan_digest_sha256": bundle.payload["plan_digest_sha256"],
        "materialize_receipt_sha256": materialize_sha,
        "approval_sha256": approval_sha,
        "target_database_sha256_after": _file_sha256(target),
        "source_availability_receipt_sha256s": list(bundle.source_receipt_sha256s),
        "idempotent_replay": idempotent,
        "created_at": _datetime_text(created_at),
    }
    existing = _existing_bound_receipt(
        receipt_path,
        expected_kind=PROMOTION_RECEIPT_KIND,
        cohort_id=str(bundle.payload["cohort_id"]),
        bundle_sha256=bundle.bundle_sha256,
        expected_fields={
            key: value for key, value in content.items() if key != "idempotent_replay"
        },
    )
    if existing is not None:
        return existing
    receipt = _seal(content, hash_field="canonical_receipt_sha256")
    _write_new_or_identical_json(receipt_path, receipt)
    return receipt


def _rollback_receipt(
    *,
    target: Path,
    cohort_id: str,
    previous_id: str | None,
    promotion_sha: str,
    approval_sha: str,
    created_at: str | None,
    idempotent: bool,
    receipt_path: Path,
) -> dict[str, Any]:
    content = {
        "schema_version": 1,
        "receipt_kind": ROLLBACK_RECEIPT_KIND,
        "status": ROLLED_BACK_STATUS,
        "cohort_id": cohort_id,
        "restored_cohort_id": previous_id,
        "promotion_receipt_sha256": promotion_sha,
        "approval_sha256": approval_sha,
        "target_database_sha256_after": _file_sha256(target),
        "idempotent_replay": idempotent,
        "created_at": _datetime_text(created_at),
    }
    existing = _existing_bound_receipt(
        receipt_path,
        expected_kind=ROLLBACK_RECEIPT_KIND,
        cohort_id=cohort_id,
        expected_fields={
            key: value for key, value in content.items() if key != "idempotent_replay"
        },
    )
    if existing is not None:
        return existing
    receipt = _seal(content, hash_field="canonical_receipt_sha256")
    _write_new_or_identical_json(receipt_path, receipt)
    return receipt


def _load_approval(
    path: Path,
    *,
    operation: str,
    bundle: _ValidatedBundle,
) -> tuple[dict[str, Any], str]:
    payload, approval_sha = _load_operation_approval(path, operation=operation)
    if payload.get("cohort_id") != bundle.payload["cohort_id"]:
        raise CurrentRuleCohortError("approval cohort mismatch")
    if payload.get("bundle_sha256") != bundle.bundle_sha256:
        raise CurrentRuleCohortError("approval bundle hash mismatch")
    if payload.get("plan_digest_sha256") != bundle.payload["plan_digest_sha256"]:
        raise CurrentRuleCohortError("approval plan hash mismatch")
    attested = sorted(
        _sha256_text(value, "approval source receipt hash")
        for value in _list(
            payload.get("attested_source_availability_receipt_sha256s"),
            "approval source receipt hashes",
        )
    )
    if attested != list(bundle.source_receipt_sha256s):
        raise CurrentRuleCohortError("approval source availability attestations mismatch")
    if payload.get("historical_source_availability_attested") is not True:
        raise CurrentRuleCohortError("historical source availability must be explicitly attested")
    calendar_owner = _load_json(bundle.calendar_path, field_name="calendar receipt")[1].get(
        "owner_approval_id"
    )
    if payload.get("owner_approval_id") != calendar_owner:
        raise CurrentRuleCohortError("approval owner does not match calendar authority owner")
    return payload, approval_sha


def _load_operation_approval(path: Path, *, operation: str) -> tuple[dict[str, Any], str]:
    _, payload = _load_json(path, field_name="approval_artifact_path")
    if payload.get("approval_kind") != APPROVAL_KIND or payload.get("schema_version") != 1:
        raise CurrentRuleCohortError("unsupported D6b approval contract")
    approval_sha = _validate_self_hash(payload, "canonical_approval_sha256")
    if payload.get("approval_status") != "approved" or payload.get("operation") != operation:
        raise CurrentRuleCohortError(f"approval does not authorize {operation}")
    _text(payload.get("owner_approval_id"), "approval.owner_approval_id")
    _text(payload.get("run_id"), "approval.run_id")
    _datetime_text(payload.get("approved_at"))
    return payload, approval_sha


def _load_receipt(path: Path, *, expected_kind: str) -> tuple[dict[str, Any], str]:
    _, payload = _load_json(path, field_name="receipt_path")
    if payload.get("receipt_kind") != expected_kind or payload.get("schema_version") != 1:
        raise CurrentRuleCohortError("unexpected receipt contract")
    return payload, _validate_self_hash(payload, "canonical_receipt_sha256")


def _existing_bound_receipt(
    path: Path,
    *,
    expected_kind: str,
    cohort_id: str,
    bundle_sha256: str | None = None,
    expected_fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not path.resolve().is_file():
        return None
    payload, _ = _load_receipt(path, expected_kind=expected_kind)
    if payload.get("cohort_id") != cohort_id:
        raise CurrentRuleCohortError("existing receipt cohort binding mismatch")
    if bundle_sha256 is not None and payload.get("bundle_sha256") != bundle_sha256:
        raise CurrentRuleCohortError("existing receipt bundle binding mismatch")
    for field, expected in (expected_fields or {}).items():
        if payload.get(field) != expected:
            raise CurrentRuleCohortError(
                f"existing receipt binding mismatch: {field}"
            )
    return payload


def _match_dry_receipt(
    receipt: dict[str, Any],
    *,
    bundle: _ValidatedBundle,
    target: Path,
) -> None:
    if receipt.get("status") != "dry_run_completed" or receipt.get("database_unchanged") is not True:
        raise CurrentRuleCohortError("dry-run receipt is not completed and unchanged")
    if receipt.get("cohort_id") != bundle.payload["cohort_id"]:
        raise CurrentRuleCohortError("dry-run receipt cohort mismatch")
    if receipt.get("bundle_sha256") != bundle.bundle_sha256:
        raise CurrentRuleCohortError("dry-run receipt bundle hash mismatch")
    if Path(str(receipt.get("target_database_path"))).resolve() != target:
        raise CurrentRuleCohortError("dry-run receipt target database mismatch")
    if receipt.get("target_database_sha256_before") != receipt.get("target_database_sha256_after"):
        raise CurrentRuleCohortError("dry-run receipt hashes are not unchanged")


def _validate_source_availability_receipt(
    payload: dict[str, Any],
    *,
    evaluation: str,
) -> dict[tuple[str, str, str, str, str], str]:
    if payload.get("receipt_kind") != "pit_source_availability_v1":
        raise CurrentRuleCohortError("source availability receipt kind mismatch")
    _datetime_text(payload.get("captured_at"))
    seen: set[tuple[Any, ...]] = set()
    index_by_source: dict[tuple[str, str, str, str, str], str] = {}
    sources = _list(payload.get("sources"), "source availability receipt sources")
    if not sources:
        raise CurrentRuleCohortError("source availability receipt must contain sources")
    for index, raw in enumerate(sources):
        source = _mapping(raw, f"sources[{index}]")
        key = (
            _text(source.get("table"), "source.table"),
            _text(source.get("source_version"), "source.source_version"),
            str(source.get("vendor_version") or ""),
            str(source.get("rule_version") or ""),
            _text(source.get("run_id"), "source.run_id"),
        )
        if key in seen:
            raise CurrentRuleCohortError("duplicate source availability key")
        seen.add(key)
        available = _date_text(source.get("available_at"), "source.available_at")
        if available > evaluation:
            raise CurrentRuleCohortError("source availability occurs after evaluation date")
        index_by_source[key] = available
    return index_by_source


def _validate_exact_candidate_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    _validate_exact_pit_source_evidence(
        value,
        source_index=source_index,
        evaluation=evaluation,
        field_label="candidate source evidence",
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
    )


def _validate_control_source_evidence(
    value: Any,
    *,
    source_index: Mapping[tuple[str, str, str, str, str], str],
    evaluation: str,
    field_label: str,
    inherited_table: str | None = None,
) -> int:
    proven = 0
    if isinstance(value, dict):
        table = str(value.get("table") or inherited_table or "").strip() or None
        if "availability_status" in value:
            if value.get("availability_status") != "available":
                raise CurrentRuleCohortError(f"{field_label} availability is not available")
            if table is None:
                raise CurrentRuleCohortError(f"{field_label} table is missing")
            key = (
                table,
                _text(value.get("source_version"), f"{field_label} source_version"),
                str(value.get("vendor_version") or ""),
                str(value.get("rule_version") or ""),
                _text(value.get("run_id"), f"{field_label} run_id"),
            )
            available_at = _date_text(value.get("available_at"), f"{field_label} available_at")
            if available_at > evaluation or source_index.get(key) != available_at:
                raise CurrentRuleCohortError(
                    f"{field_label} is not attested by persisted availability receipt"
                )
            proven += 1
        for nested in value.values():
            proven += _validate_control_source_evidence(
                nested,
                source_index=source_index,
                evaluation=evaluation,
                field_label=field_label,
                inherited_table=table,
            )
    elif isinstance(value, list):
        for nested in value:
            proven += _validate_control_source_evidence(
                nested,
                source_index=source_index,
                evaluation=evaluation,
                field_label=field_label,
                inherited_table=inherited_table,
            )
    return proven


def _validate_v4_limit_price_evidence(
    value: Any,
    *,
    observation: Mapping[str, Any],
    source_index: Mapping[tuple[str, str, str, str, str], str],
    evaluation: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
    field_label: str,
) -> None:
    limit_price = _mapping(value, f"{field_label}.limit_price")
    required = {
        "table", "entry", "entry_source",
        "exit_5d", "exit_5d_source", "exit_5d_decisions",
        "exit_20d", "exit_20d_source", "exit_20d_decisions",
    }
    if set(limit_price) != required or limit_price["table"] != TABLE_LIMIT_PRICE:
        raise CurrentRuleCohortError(f"{field_label} limit_price contract mismatch")
    if observation.get("table") != TABLE_OBS:
        raise CurrentRuleCohortError(f"{field_label} observation table mismatch")

    def validate_limit_source(source_kind: Any, source: Any, *, label: str) -> None:
        if not isinstance(source_kind, str) or source_kind not in {"stk_limit", "observation_cast", "missing"}:
            raise CurrentRuleCohortError(f"{label} limit_price source is invalid")
        if source_kind == "stk_limit":
            leaf = _mapping(source, f"{label} limit_price source")
            if set(leaf) != {
                "source_version", "vendor_version", "rule_version", "run_id",
                "available_at", "availability_status",
            } or _validate_control_source_evidence(
                leaf,
                source_index=source_index,
                evaluation=evaluation,
                field_label=f"{label} limit_price source",
                inherited_table=TABLE_LIMIT_PRICE,
            ) != 1:
                raise CurrentRuleCohortError(f"{label} limit_price source receipt mismatch")
        elif source is not None:
            raise CurrentRuleCohortError(f"{label} unexpected limit_price source receipt")

    validate_limit_source(limit_price["entry_source"], limit_price["entry"], label=f"{field_label}.entry")
    expected_dates = {"entry": entry_date, "exit_5d": exit_date_5d, "exit_20d": exit_date_20d}
    for point, expected_date in expected_dates.items():
        leaf = _mapping(observation.get(point), f"{field_label}.observation.{point}")
        if _date_text(leaf.get("trade_date"), f"{field_label}.observation.{point}.trade_date") != expected_date:
            raise CurrentRuleCohortError(f"{field_label} observation date mismatch: {point}")

    for horizon, exit_date in (("5d", exit_date_5d), ("20d", exit_date_20d)):
        exit_source_kind = limit_price[f"exit_{horizon}_source"]
        exit_source = limit_price[f"exit_{horizon}"]
        validate_limit_source(exit_source_kind, exit_source, label=f"{field_label}.exit_{horizon}")
        decisions = _list(limit_price[f"exit_{horizon}_decisions"], f"{field_label}.exit_{horizon}_decisions")
        if not decisions:
            raise CurrentRuleCohortError(f"{field_label} limit_price decisions are missing")
        previous_date = entry_date
        for index, raw_decision in enumerate(decisions):
            decision = _mapping(raw_decision, f"{field_label}.exit_{horizon}_decisions[{index}]")
            if set(decision) != {
                "trade_date", "decision", "close_value", "up_limit", "down_limit",
                "limit_down_flag", "limit_price_source", "source", "observation",
            }:
                raise CurrentRuleCohortError(f"{field_label} limit_price decision contract mismatch")
            decision_date = _date_text(decision.get("trade_date"), f"{field_label} decision trade_date")
            if decision_date < entry_date or (index > 0 and decision_date <= previous_date) or decision_date > evaluation:
                raise CurrentRuleCohortError(f"{field_label} limit_price decision date mismatch")
            previous_date = decision_date
            decision_kind = decision.get("decision")
            if not isinstance(decision_kind, str) or decision_kind not in {"halted", "limit_down", "missing_close", "sellable"}:
                raise CurrentRuleCohortError(f"{field_label} limit_price decision is invalid")
            price_is_limit_down = _is_limit_down({
                "close_value": decision.get("close_value"),
                "highlimit": decision.get("up_limit"),
                "lowlimit": decision.get("down_limit"),
                "limit_down_flag": decision.get("limit_down_flag"),
            })
            if (decision_kind == "limit_down" and not price_is_limit_down) or (
                decision_kind == "sellable" and price_is_limit_down
            ):
                raise CurrentRuleCohortError(f"{field_label} limit_price decision contradicts price")
            if index < len(decisions) - 1 and decision_kind == "sellable":
                raise CurrentRuleCohortError(f"{field_label} limit_price decision order mismatch")
            decision_observation = _mapping(decision.get("observation"), f"{field_label} decision observation")
            if set(decision_observation) != {
                "trade_date", "source_version", "vendor_version", "rule_version",
                "run_id", "available_at", "availability_status",
            }:
                raise CurrentRuleCohortError(f"{field_label} decision observation contract mismatch")
            if _date_text(decision_observation.get("trade_date"), f"{field_label} decision observation date") != decision_date:
                raise CurrentRuleCohortError(f"{field_label} limit_price decision observation date mismatch")
            if _validate_control_source_evidence(
                decision_observation,
                source_index=source_index,
                evaluation=evaluation,
                field_label=f"{field_label} decision observation",
                inherited_table=TABLE_OBS,
            ) != 1:
                raise CurrentRuleCohortError(f"{field_label} decision observation receipt mismatch")
            validate_limit_source(
                decision.get("limit_price_source"), decision.get("source"),
                label=f"{field_label}.exit_{horizon}_decisions[{index}]",
            )
        terminal = _mapping(decisions[-1], f"{field_label} terminal decision")
        if (
            previous_date != exit_date
            or terminal.get("decision") != "sellable"
            or terminal.get("limit_price_source") != exit_source_kind
            or terminal.get("source") != exit_source
            or terminal.get("observation") != observation[f"exit_{horizon}"]
        ):
            raise CurrentRuleCohortError(f"{field_label} limit_price terminal decision mismatch")


def _validate_exact_control_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    _validate_exact_pit_source_evidence(
        value,
        source_index=source_index,
        evaluation=evaluation,
        field_label="control source evidence",
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
    )


def _validate_exact_pit_source_evidence(
    value: Any,
    *,
    source_index: dict[tuple[str, str, str, str, str], str],
    evaluation: str,
    field_label: str,
    entry_date: str,
    exit_date_5d: str,
    exit_date_20d: str,
) -> None:
    evidence = _mapping(value, field_label)
    if set(evidence) != {"observation", "adjustment_factor", "limit_price"}:
        raise CurrentRuleCohortError(
            f"{field_label} must contain observation, adjustment_factor and limit_price"
        )
    for group_name in ("observation", "adjustment_factor"):
        group = _mapping(evidence.get(group_name), f"{field_label}.{group_name}")
        _text(group.get("table"), f"{field_label}.{group_name}.table")
        for point in ("entry", "exit_5d", "exit_20d"):
            leaf = _mapping(
                group.get(point),
                f"{field_label}.{group_name}.{point}",
            )
            proven = _validate_control_source_evidence(
                leaf,
                source_index=source_index,
                evaluation=evaluation,
                field_label=field_label,
                inherited_table=str(group["table"]),
            )
            if proven != 1:
                raise CurrentRuleCohortError(
                    f"each {field_label} leaf must contain exactly one availability record"
                )
        group_proven = _validate_control_source_evidence(
            group,
            source_index=source_index,
            evaluation=evaluation,
            field_label=field_label,
        )
        if group_proven != 3:
            raise CurrentRuleCohortError(
                f"{field_label} must contain exactly entry/T5/T20 availability"
            )
    _validate_v4_limit_price_evidence(
        evidence["limit_price"],
        observation=_mapping(evidence["observation"], f"{field_label}.observation"),
        source_index=source_index,
        evaluation=evaluation,
        entry_date=entry_date,
        exit_date_5d=exit_date_5d,
        exit_date_20d=exit_date_20d,
        field_label=field_label,
    )


def _validate_bundle_source_rows(*, target: Path, bundle: _ValidatedBundle) -> None:
    """Verify v4 decisions against rows in the identity-bound source database."""
    evaluation = _date_text(bundle.payload.get("evaluation_as_of_date"), "bundle.evaluation_as_of_date")
    core_source_index: dict[
        tuple[str, str | None, str | None, str | None, str | None], str
    ] = {
        (table, source, vendor or None, rule or None, run): available
        for (table, source, vendor, rule, run), available in bundle.source_availability_index.items()
    }
    try:
        conn = duckdb.connect(str(target), read_only=True)
        try:
            for fact in bundle.facts:
                signal_date = _date_text(fact.get("signal_date"), "fact.signal_date")
                stock_code = _text(fact.get("stock_code"), "fact.stock_code")
                candidate = _control_execution_pit_proof(
                    conn,
                    stock_code=stock_code,
                    signal_date=signal_date,
                    evaluation_as_of_date=evaluation,
                    source_availability_index=core_source_index,
                )
                submitted = _mapping(
                    _mapping(fact.get("evidence"), "fact.evidence").get("candidate_source_evidence"),
                    "candidate source evidence",
                )
                if candidate.get("source_evidence", {}).get("limit_price") != submitted.get("limit_price"):
                    raise CurrentRuleCohortError(f"candidate decision source rows mismatch: {stock_code}")
                proof = _mapping(fact.get("control_pit_proof"), "fact.control_pit_proof")
                for raw_control in _list(proof.get("controls"), "control_pit_proof.controls"):
                    control = _mapping(raw_control, "control")
                    control_code = _text(control.get("control_stock_code"), "control_stock_code")
                    expected = _control_execution_pit_proof(
                        conn,
                        stock_code=control_code,
                        signal_date=signal_date,
                        evaluation_as_of_date=evaluation,
                        source_availability_index=core_source_index,
                    )
                    if expected.get("source_evidence", {}).get("limit_price") != _mapping(
                        control.get("source_evidence"), "control source evidence"
                    ).get("limit_price"):
                        raise CurrentRuleCohortError(f"control decision source rows mismatch: {control_code}")
        finally:
            conn.close()
    except duckdb.Error as exc:
        raise CurrentRuleCohortError("unable to verify decision rows in source DuckDB") from exc


def _assert_bundle_target_identity(*, target: Path, bundle: _ValidatedBundle) -> None:
    expected = _canonical_sha256(
        {
            "target_database_path": str(target),
            "plan_digest_sha256": bundle.payload["plan_digest_sha256"],
            "version_tuple": bundle.payload["version_tuple"],
            "calendar_receipt_sha256": bundle.calendar_sha256,
            "source_availability_receipt_sha256s": list(
                bundle.source_receipt_sha256s
            ),
            "control_count": CONTROL_COUNT,
        }
    )
    if bundle.payload.get("idempotency_key") != expected:
        raise CurrentRuleCohortError(
            "bundle idempotency_key does not bind target, plan, tuple and receipts"
        )


def _assert_approval_target(payload: dict[str, Any], *, target: Path) -> None:
    raw_path = _text(payload.get("target_database_path"), "approval.target_database_path")
    if Path(raw_path).resolve() != target:
        raise CurrentRuleCohortError("approval target database path mismatch")


def _verify_prewrite_backup(*, target: Path, backup_path: str | Path) -> dict[str, Any]:
    backup = _existing_file(backup_path, field_name="target_backup_path")
    if backup == target or os.path.samefile(backup, target):
        raise CurrentRuleCohortError("target backup must be a different path")
    target_sha = _file_sha256(target)
    backup_sha = _file_sha256(backup)
    if target_sha != backup_sha:
        raise CurrentRuleCohortError("target backup hash does not match target database")
    return {"path": backup, "sha256": backup_sha}


def _verify_recorded_backup(
    *,
    target: Path,
    backup_path: Any,
    expected_sha256: Any,
) -> dict[str, Any]:
    backup = _existing_file(str(backup_path), field_name="recorded target backup")
    if os.path.samefile(backup, target):
        raise CurrentRuleCohortError("recorded target backup aliases the live database")
    expected = _sha256_text(expected_sha256, "manifest.backup_sha256")
    actual = _file_sha256(backup)
    if actual != expected:
        raise CurrentRuleCohortError("recorded target backup hash mismatch")
    return {"path": backup, "sha256": actual}


def _load_bundle_artifact(
    bundle_path: Path,
    raw_path: Any,
    *,
    field_name: str,
) -> tuple[Path, dict[str, Any]]:
    text = _text(raw_path, f"{field_name}.path")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = bundle_path.parent / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(bundle_path.parent.resolve())
    except ValueError as exc:
        raise CurrentRuleCohortError(
            f"{field_name} must be persisted inside the bundle directory"
        ) from exc
    return _load_json(resolved, field_name=field_name)


def _load_json(
    path: Path, *, field_name: str, max_bytes: int = MAX_JSON_INPUT_BYTES
) -> tuple[Path, dict[str, Any]]:
    resolved = _existing_file(path, field_name=field_name)
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise CurrentRuleCohortError(f"{field_name} could not be inspected") from exc
    if size > max_bytes:
        raise CurrentRuleCohortError(
            f"{field_name} exceeds max JSON input size of {max_bytes} bytes"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentRuleCohortError(f"{field_name} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise CurrentRuleCohortError(f"{field_name} must contain a JSON object")
    return resolved, payload


def _seal(payload: dict[str, Any], *, hash_field: str) -> dict[str, Any]:
    sealed = dict(payload)
    sealed[hash_field] = _canonical_sha256(sealed)
    return sealed


def _validate_self_hash(payload: dict[str, Any], hash_field: str) -> str:
    actual = _sha256_text(payload.get(hash_field), hash_field)
    content = {key: value for key, value in payload.items() if key != hash_field}
    if actual != _canonical_sha256(content):
        raise CurrentRuleCohortError(f"{hash_field} mismatch")
    return actual


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest().upper()


def _write_new_or_identical_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if resolved.exists():
        if resolved.read_text(encoding="utf-8") != content:
            raise CurrentRuleCohortError(f"receipt path already exists with different content: {resolved}")
        return
    temporary = resolved.with_name(f".{resolved.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, resolved)
        except FileExistsError:
            if resolved.read_text(encoding="utf-8") != content:
                raise CurrentRuleCohortError(
                    f"receipt path already exists with different content: {resolved}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = conn.execute(
        "select count(*) from information_schema.tables where table_schema = 'main' and table_name = ?",
        [table],
    ).fetchone()
    return cast(tuple[int], row)[0] == 1


def _existing_file(path: str | Path, *, field_name: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise CurrentRuleCohortError(f"{field_name} must be an existing file")
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _require_write_switch(value: bool) -> None:
    if value is not True:
        raise CurrentRuleCohortError("production write is disabled; allow_write=True is required")


def _text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CurrentRuleCohortError(f"{field_name} is required")
    return text


def _sha256_text(value: Any, field_name: str) -> str:
    text = _text(value, field_name).upper()
    if len(text) != 64 or any(char not in "0123456789ABCDEF" for char in text):
        raise CurrentRuleCohortError(f"{field_name} must be an uppercase SHA256")
    return text


def _date_text(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise CurrentRuleCohortError(f"{field_name} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise CurrentRuleCohortError(f"{field_name} must be strict YYYY-MM-DD")
    return text


def _datetime_text(value: Any | None) -> str:
    if value is None:
        raise CurrentRuleCohortError("datetime artifact field is required")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentRuleCohortError("datetime artifact field must be ISO-8601") from exc
    if parsed.utcoffset() is None:
        raise CurrentRuleCohortError("datetime artifact field must include a timezone")
    return text


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CurrentRuleCohortError(f"{field_name} must be an object")
    return dict(value)


def _list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise CurrentRuleCohortError(f"{field_name} must be a list")
    return value


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _finite_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CurrentRuleCohortError(f"{field_name} must be finite") from exc
    if not math.isfinite(number):
        raise CurrentRuleCohortError(f"{field_name} must be finite")
    return number


def _positive_number(value: Any, field_name: str) -> float:
    number = _finite_number(value, field_name)
    if number <= 0:
        raise CurrentRuleCohortError(f"{field_name} must be positive")
    return number
