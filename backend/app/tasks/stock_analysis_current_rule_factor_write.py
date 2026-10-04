"""Governed exact-cell writer for current-rule adjustment-factor remediation.

This module performs one tightly scoped live DuckDB write:

- source rows must come from a formally valid reviewed manifest and vendor
  dry-run receipt bound to the same database path and SHA-256
- only the exact returned cells may be inserted
- the target table must remain the canonical five-column schema
- a byte-identical pre-write backup is created exclusively under
  ``<duckdb parent>/backups``
- a self-hashed write receipt is persisted exclusively under the trusted
  evidence root

The writer is intentionally fail-closed. It does not authorize downstream
materialization, historical-availability claims, or certification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, SupportsFloat, SupportsIndex, TypedDict, TypeGuard, cast

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.stock_analysis_current_rule_factor_vendor_receipt import (
    READY_STATUS as VENDOR_READY_STATUS,
)
from backend.app.governance.stock_analysis_current_rule_factor_vendor_receipt import (
    RECEIPT_KIND as VENDOR_RECEIPT_KIND,
)
from backend.app.governance.stock_analysis_current_rule_factor_vendor_receipt import (
    validate_stock_analysis_current_rule_factor_vendor_receipt,
)
from backend.app.tasks.stock_analysis_current_rule_factor_manifest import (
    FACTOR_TABLE,
    MANIFEST_KIND,
    validate_stock_analysis_current_rule_factor_manifest,
)


class _VendorBinding(TypedDict):
    path: str
    file_sha256: str
    canonical_receipt_sha256: str
    database_path: str
    database_sha256: str
    returned_cells_sha256: str
    proposed_source_version: str
    proposed_run_id: str
    returned_cell_count: int


SCHEMA_VERSION = 1
WRITE_RECEIPT_KIND = "stock_analysis_current_rule_factor_write_receipt_v1"
COMPLETED_STATUS = "physical_remediation_completed"
PENDING_INTENT_KIND = "stock_analysis_current_rule_factor_write_pending_intent_v1"
PENDING_STATUS = "write_pending"

EXPECTED_FACTOR_SCHEMA = (
    ("stock_code", "VARCHAR"),
    ("trade_date", "VARCHAR"),
    ("adj_factor", "DOUBLE"),
    ("source_version", "VARCHAR"),
    ("run_id", "VARCHAR"),
)

APPROVAL_SCOPE = "exact_vendor_receipt_returned_cells_only"
ROLLBACK_INSTRUCTION = (
    "Rollback requires separate explicit authorization and manual restoration "
    "of the verified backup; no automatic rollback is provided."
)
TOUCHED_TABLES = [FACTOR_TABLE]


class CurrentRuleFactorWriteError(ValueError):
    """Raised when the exact-factor remediation write cannot proceed safely."""


def write_stock_analysis_current_rule_factor_cells(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    reviewed_factor_manifest_file: str | Path,
    vendor_receipt_file: str | Path,
    target_backup_file: str | Path,
    write_receipt_file: str | Path,
    executed_at: str,
    approval_reference: str,
    expected_approved_scope_sha256: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Execute the approved exact-cell adjustment-factor remediation.

    ``allow_write`` must be explicitly ``True``. Any other value fails closed.
    """

    if allow_write is not True:
        raise CurrentRuleFactorWriteError("allow_write must be explicitly true")

    executed_at_text = _utc_datetime_text(executed_at, field_name="executed_at")
    approval_text = _required_text(
        approval_reference,
        field_name="approval_reference",
    )
    approved_scope_sha256 = _sha256_text(
        expected_approved_scope_sha256,
        field_name="expected_approved_scope_sha256",
    )

    raw_target = _absolute_without_resolve(duckdb_path)
    _assert_no_symlink_in_raw_path(raw_target, field_name="duckdb_path")
    target = _existing_file(raw_target, field_name="duckdb_path")

    trusted_root = _existing_directory(
        _absolute_without_resolve(trusted_evidence_root),
        field_name="trusted_evidence_root",
    )
    _assert_no_symlink_in_raw_path(trusted_root, field_name="trusted_evidence_root")

    reviewed_manifest_path = _existing_json_file_within_root(
        trusted_root=trusted_root,
        path=reviewed_factor_manifest_file,
        field_name="reviewed_factor_manifest_file",
    )
    vendor_receipt_path = _existing_json_file_within_root(
        trusted_root=trusted_root,
        path=vendor_receipt_file,
        field_name="vendor_receipt_file",
    )
    target_write_receipt_path = _new_json_file_within_root(
        trusted_root=trusted_root,
        path=write_receipt_file,
        field_name="write_receipt_file",
    )
    target_backup_path = _new_backup_path_for_target(
        target=target,
        backup_path=target_backup_file,
    )

    reviewed_manifest = _load_json_object(
        reviewed_manifest_path,
        field_name="reviewed_factor_manifest_file",
    )
    reviewed_manifest_file_sha256 = _file_sha256(reviewed_manifest_path)
    manifest_contract = _validated_manifest_contract(
        reviewed_manifest,
        manifest_path=reviewed_manifest_path,
        manifest_file_sha256=reviewed_manifest_file_sha256,
    )

    vendor_receipt = _load_json_object(
        vendor_receipt_path,
        field_name="vendor_receipt_file",
    )
    vendor_receipt_file_sha256 = _file_sha256(vendor_receipt_path)
    vendor_contract = _validated_vendor_receipt_contract(
        vendor_receipt,
        vendor_receipt_path=vendor_receipt_path,
        vendor_receipt_file_sha256=vendor_receipt_file_sha256,
        reviewed_factor_manifest=reviewed_manifest,
        reviewed_factor_manifest_path=reviewed_manifest_path,
        reviewed_factor_manifest_file_sha256=reviewed_manifest_file_sha256,
    )

    if target != manifest_contract["database_path"]:
        raise CurrentRuleFactorWriteError("duckdb_path does not match reviewed manifest database path")
    if target != vendor_contract["database_path"]:
        raise CurrentRuleFactorWriteError("duckdb_path does not match vendor receipt database path")

    writer_lock = resolve_duckdb_writer_lock(target)
    with acquire_lock(writer_lock, base_dir=target.parent):
        db_sha_before = _file_sha256(target)
        if db_sha_before != manifest_contract["database_sha256"]:
            raise CurrentRuleFactorWriteError("reviewed manifest database SHA does not match current DuckDB")
        if db_sha_before != vendor_contract["database_sha256"]:
            raise CurrentRuleFactorWriteError("vendor receipt database SHA does not match current DuckDB")

        target_rows_sha256 = _canonical_json_sha256(vendor_contract["returned_cells"])
        computed_scope_sha256 = _approval_scope_sha256(
            manifest_canonical_sha256=manifest_contract["canonical_manifest_sha256"],
            vendor_canonical_sha256=vendor_contract["canonical_receipt_sha256"],
            database_sha256_before=db_sha_before,
            target_rows_sha256=target_rows_sha256,
            target_cell_count=vendor_contract["returned_cell_count"],
        )
        if approved_scope_sha256 != computed_scope_sha256:
            raise CurrentRuleFactorWriteError(
                "expected_approved_scope_sha256 does not match the exact reviewed write scope"
            )

        _assert_no_unmerged_duckdb_sidecars(target)

        with duckdb.connect(str(target), read_only=True) as preflight_conn:
            _assert_exact_factor_schema(preflight_conn)
            _assert_global_table_quality(preflight_conn)
            _assert_target_cells_absent(
                preflight_conn,
                target_rows=vendor_contract["returned_cells"],
            )

        _assert_no_unmerged_duckdb_sidecars(target)
        backup_sha256 = _create_prewrite_backup(
            target=target,
            backup_path=target_backup_path,
        )
        _assert_no_unmerged_duckdb_sidecars(target)
        if _file_sha256(target) != db_sha_before:
            raise CurrentRuleFactorWriteError("target DuckDB changed after backup creation")

        pending_intent = _build_pending_write_intent(
            executed_at=executed_at_text,
            approval_reference=approval_text,
            approved_scope_sha256=approved_scope_sha256,
            reviewed_manifest_path=reviewed_manifest_path,
            reviewed_manifest_file_sha256=reviewed_manifest_file_sha256,
            reviewed_manifest=reviewed_manifest,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
            vendor_receipt=vendor_receipt,
            db_path=target,
            db_sha_before=db_sha_before,
            backup_path=target_backup_path,
            backup_sha256=backup_sha256,
            target_rows=vendor_contract["returned_cells"],
            source_version=vendor_contract["proposed_source_version"],
            run_id=vendor_contract["proposed_run_id"],
        )
        _write_json_exclusive(target_write_receipt_path, payload=pending_intent)
        persisted_pending = _load_json_object(
            target_write_receipt_path,
            field_name="write_receipt_file pending intent",
        )
        if persisted_pending != pending_intent:
            raise CurrentRuleFactorWriteError("persisted pending write intent does not match generated intent")

        with duckdb.connect(str(target), read_only=False) as conn:
            row_count_before = _table_row_count(conn)
            try:
                conn.execute("begin transaction")
                _assert_exact_factor_schema(conn)
                _assert_global_table_quality(conn)
                _assert_target_cells_absent(
                    conn,
                    target_rows=vendor_contract["returned_cells"],
                )
                _insert_target_rows(
                    conn,
                    target_rows=vendor_contract["returned_cells"],
                    source_version=vendor_contract["proposed_source_version"],
                    run_id=vendor_contract["proposed_run_id"],
                )
                _verify_transaction_postconditions(
                    conn,
                    row_count_before=row_count_before,
                    target_rows=vendor_contract["returned_cells"],
                    source_version=vendor_contract["proposed_source_version"],
                    run_id=vendor_contract["proposed_run_id"],
                )
                conn.execute("commit")
            except Exception:
                _rollback_quietly(conn)
                raise

        with duckdb.connect(str(target), read_only=True) as post_conn:
            _assert_exact_factor_schema(post_conn)
            _assert_global_table_quality(post_conn)
            _verify_target_rows_exact(
                post_conn,
                target_rows=vendor_contract["returned_cells"],
                source_version=vendor_contract["proposed_source_version"],
                run_id=vendor_contract["proposed_run_id"],
            )

        db_sha_after = _file_sha256(target)
        if db_sha_after == db_sha_before:
            raise CurrentRuleFactorWriteError("database SHA must change after a committed write")

        receipt = _build_write_receipt(
            executed_at=executed_at_text,
            approval_reference=approval_text,
            reviewed_manifest_path=reviewed_manifest_path,
            reviewed_manifest_file_sha256=reviewed_manifest_file_sha256,
            reviewed_manifest=reviewed_manifest,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
            vendor_receipt=vendor_receipt,
            db_path=target,
            db_sha_before=db_sha_before,
            db_sha_after=db_sha_after,
            backup_path=target_backup_path,
            backup_sha256=backup_sha256,
            target_rows=vendor_contract["returned_cells"],
            source_version=vendor_contract["proposed_source_version"],
            run_id=vendor_contract["proposed_run_id"],
            approved_scope_sha256=approved_scope_sha256,
        )
        valid, errors = validate_stock_analysis_current_rule_factor_write_receipt(
            receipt,
            reviewed_factor_manifest=reviewed_manifest,
            vendor_receipt=vendor_receipt,
        )
        if not valid:
            raise CurrentRuleFactorWriteError("generated write receipt failed validation: " + "; ".join(errors))
        _replace_json_atomically_preserving_existing(
            target_write_receipt_path,
            payload=receipt,
            expected_existing=pending_intent,
        )
        persisted = _load_json_object(
            target_write_receipt_path,
            field_name="write_receipt_file",
        )
        if persisted != receipt:
            raise CurrentRuleFactorWriteError("persisted write receipt does not match generated receipt")
        valid, errors = validate_stock_analysis_current_rule_factor_write_receipt(
            persisted,
            reviewed_factor_manifest=reviewed_manifest,
            vendor_receipt=vendor_receipt,
        )
        if not valid:
            raise CurrentRuleFactorWriteError("persisted write receipt failed validation: " + "; ".join(errors))
        return persisted


def validate_stock_analysis_current_rule_factor_write_receipt(
    receipt: Mapping[str, object],
    *,
    reviewed_factor_manifest: Mapping[str, object] | None = None,
    vendor_receipt: Mapping[str, object] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate the governed exact-factor write receipt."""

    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    errors: list[str] = []

    if (reviewed_factor_manifest is None) ^ (vendor_receipt is None):
        errors.append("reviewed_factor_manifest and vendor_receipt must be supplied together")

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"receipt.schema_version must equal {SCHEMA_VERSION}")
    if payload.get("receipt_kind") != WRITE_RECEIPT_KIND:
        errors.append(f"receipt.receipt_kind must equal {WRITE_RECEIPT_KIND}")
    if payload.get("status") != COMPLETED_STATUS:
        errors.append(f"receipt.status must equal {COMPLETED_STATUS}")

    try:
        normalized_executed_at = _utc_datetime_text(
            payload.get("executed_at"),
            field_name="receipt.executed_at",
        )
        if payload.get("executed_at") != normalized_executed_at:
            errors.append("receipt.executed_at must be canonical UTC text")
    except ValueError as exc:
        errors.append(str(exc))
        normalized_executed_at = None

    try:
        _required_text(
            payload.get("approval_reference"),
            field_name="receipt.approval_reference",
        )
    except ValueError as exc:
        errors.append(str(exc))

    if payload.get("approval_scope") != APPROVAL_SCOPE:
        errors.append("receipt.approval_scope mismatch")

    for field_name, expected in (
        ("database_write_executed", True),
        ("additional_write_allowed", False),
        ("physical_gap_remediation_completed", True),
        ("historical_availability_proven", False),
        ("formal_historical_replay_use_allowed", False),
        ("certification_allowed", False),
        ("downstream_materialization_executed", False),
        ("no_overwrite_or_delete_performed", True),
    ):
        if payload.get(field_name) is not expected:
            errors.append(f"receipt.{field_name} must be {str(expected).lower()}")

    if payload.get("rollback_instruction") != ROLLBACK_INSTRUCTION:
        errors.append("receipt.rollback_instruction mismatch")

    touched_tables = payload.get("touched_tables")
    if touched_tables != TOUCHED_TABLES:
        errors.append("receipt.touched_tables must only contain stock_adjustment_factor")

    manifest_binding = payload.get("reviewed_manifest_binding")
    normalized_manifest_binding = _validate_manifest_binding(
        manifest_binding,
        field_name="receipt.reviewed_manifest_binding",
        errors=errors,
        expected_kind=MANIFEST_KIND,
    )
    vendor_binding = payload.get("vendor_receipt_binding")
    normalized_vendor_binding = _validate_vendor_binding(
        vendor_binding,
        errors=errors,
    )
    normalized_database = _validate_database_binding(
        payload.get("database"),
        errors=errors,
    )
    normalized_backup = _validate_backup_binding(
        payload.get("backup"),
        errors=errors,
    )

    target_rows: list[dict[str, Any]] = []
    raw_target_rows = payload.get("target_rows")
    try:
        target_rows = _normalize_returned_cells(
            raw_target_rows,
            field_name="receipt.target_rows",
            require_non_empty=True,
        )
        if raw_target_rows != target_rows:
            errors.append("receipt.target_rows must be canonical and stably sorted")
    except ValueError as exc:
        errors.append(str(exc))

    expected_target_count = len(target_rows)
    if not _exact_int(payload.get("inserted_row_count"), expected_target_count):
        errors.append("receipt.inserted_row_count mismatch")
    if not _exact_int(payload.get("target_cell_count"), expected_target_count):
        errors.append("receipt.target_cell_count mismatch")

    expected_target_sha = _canonical_json_sha256(target_rows)
    _validate_hash_equality(
        payload.get("target_rows_sha256"),
        expected=expected_target_sha,
        field_name="receipt.target_rows_sha256",
        errors=errors,
    )

    try:
        source_version = _required_text(
            payload.get("source_version"),
            field_name="receipt.source_version",
        )
        run_id = _required_text(payload.get("run_id"), field_name="receipt.run_id")
    except ValueError as exc:
        errors.append(str(exc))
        source_version = None
        run_id = None

    if normalized_vendor_binding is not None:
        if source_version is not None and source_version != normalized_vendor_binding["proposed_source_version"]:
            errors.append("receipt.source_version must match vendor receipt proposed_source_version")
        if run_id is not None and run_id != normalized_vendor_binding["proposed_run_id"]:
            errors.append("receipt.run_id must match vendor receipt proposed_run_id")
        if expected_target_count and normalized_vendor_binding["returned_cell_count"] != expected_target_count:
            errors.append("receipt.target rows do not match vendor receipt row count")
        if target_rows and normalized_vendor_binding["returned_cells_sha256"] != expected_target_sha:
            errors.append("receipt.target rows do not match vendor receipt returned_cells")

    if normalized_manifest_binding is not None and normalized_database is not None:
        if normalized_manifest_binding["database_path"] != normalized_database["path"]:
            errors.append("receipt manifest/database path binding mismatch")
        if normalized_manifest_binding["database_sha256"] != normalized_database["sha256_before"]:
            errors.append("receipt manifest/database SHA binding mismatch")

    if normalized_backup is not None and normalized_database is not None:
        if normalized_backup["sha256"] != normalized_database["sha256_before"]:
            errors.append("receipt backup SHA must equal pre-write database SHA")

    if reviewed_factor_manifest is not None and vendor_receipt is not None:
        try:
            manifest_contract = _validated_manifest_contract(
                reviewed_factor_manifest,
                manifest_path=Path(
                    _required_text(
                        normalized_manifest_binding["path"] if normalized_manifest_binding else None,
                        field_name="receipt.reviewed_manifest_binding.path",
                    )
                )
                if normalized_manifest_binding is not None
                else Path("."),
                manifest_file_sha256=(
                    normalized_manifest_binding["file_sha256"] if normalized_manifest_binding is not None else "0" * 64
                ),
            )
        except ValueError as exc:
            errors.append(f"reviewed_factor_manifest invalid: {exc}")
        else:
            if target_rows and _target_row_keys(target_rows) != manifest_contract["missing_keys"]:
                errors.append("receipt.target_rows do not match reviewed manifest missing_unique_cells")
            if normalized_manifest_binding is not None:
                if normalized_manifest_binding["canonical_sha256"] != manifest_contract["canonical_manifest_sha256"]:
                    errors.append(
                        "receipt.reviewed_manifest_binding.canonical_manifest_sha256 does not match reviewed manifest"
                    )

    if reviewed_factor_manifest is not None and vendor_receipt is not None:
        try:
            vendor_contract = _validated_vendor_receipt_contract(
                vendor_receipt,
                vendor_receipt_path=Path(
                    _required_text(
                        normalized_vendor_binding["path"] if normalized_vendor_binding else None,
                        field_name="receipt.vendor_receipt_binding.path",
                    )
                )
                if normalized_vendor_binding is not None
                else Path("."),
                vendor_receipt_file_sha256=(
                    normalized_vendor_binding["file_sha256"] if normalized_vendor_binding is not None else "0" * 64
                ),
                reviewed_factor_manifest=reviewed_factor_manifest or {},
                reviewed_factor_manifest_path=Path(normalized_manifest_binding["path"])
                if normalized_manifest_binding is not None
                else Path("."),
                reviewed_factor_manifest_file_sha256=(
                    normalized_manifest_binding["file_sha256"] if normalized_manifest_binding is not None else "0" * 64
                ),
            )
        except ValueError as exc:
            errors.append(f"vendor_receipt invalid: {exc}")
        else:
            if target_rows and target_rows != vendor_contract["returned_cells"]:
                errors.append("receipt.target_rows do not match vendor receipt returned_cells")

    if (
        normalized_manifest_binding is not None
        and normalized_vendor_binding is not None
        and normalized_database is not None
    ):
        expected_approval_scope_sha = _approval_scope_sha256(
            manifest_canonical_sha256=normalized_manifest_binding["canonical_sha256"],
            vendor_canonical_sha256=normalized_vendor_binding["canonical_receipt_sha256"],
            database_sha256_before=normalized_database["sha256_before"],
            target_rows_sha256=expected_target_sha,
            target_cell_count=expected_target_count,
        )
        _validate_hash_equality(
            payload.get("approval_scope_sha256"),
            expected=expected_approval_scope_sha,
            field_name="receipt.approval_scope_sha256",
            errors=errors,
        )

    try:
        expected_receipt_sha = _receipt_sha256(payload)
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("receipt payload must be canonical JSON without non-finite values")
    else:
        _validate_hash_equality(
            payload.get("canonical_write_receipt_sha256"),
            expected=expected_receipt_sha,
            field_name="receipt.canonical_write_receipt_sha256",
            errors=errors,
        )
    return not errors, tuple(_ordered(errors))


def _validated_manifest_contract(
    manifest: Mapping[str, object],
    *,
    manifest_path: Path,
    manifest_file_sha256: str,
) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest must be a mapping")
    valid, errors = validate_stock_analysis_current_rule_factor_manifest(manifest)
    if not valid:
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest failed formal validation: " + "; ".join(errors))
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest kind mismatch")
    if manifest.get("status") != "gaps_found":
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest status must be gaps_found")
    if manifest.get("remediation_only") is not True or manifest.get("certification_allowed") is not False:
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest must remain remediation-only and uncertified")

    database = manifest.get("database")
    if not isinstance(database, Mapping):
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest.database must be a mapping")
    database_path = _existing_file(
        _absolute_without_resolve(
            _required_text(database.get("path"), field_name="reviewed_factor_manifest.database.path")
        ),
        field_name="reviewed_factor_manifest.database.path",
    )
    database_sha_before = _sha256_text(
        database.get("sha256_before"),
        field_name="reviewed_factor_manifest.database.sha256_before",
    )
    database_sha_after = _sha256_text(
        database.get("sha256_after"),
        field_name="reviewed_factor_manifest.database.sha256_after",
    )
    if database_sha_before != database_sha_after:
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest database hashes must be unchanged")
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest database must attest unchanged read-only access")

    missing_rows = _missing_rows_from_manifest(manifest)
    return {
        "path": manifest_path,
        "file_sha256": _sha256_text(
            manifest_file_sha256,
            field_name="reviewed_factor_manifest_file_sha256",
        ),
        "canonical_manifest_sha256": _sha256_text(
            manifest.get("canonical_manifest_sha256"),
            field_name="reviewed_factor_manifest.canonical_manifest_sha256",
        ),
        "database_path": database_path,
        "database_sha256": database_sha_before,
        "governed_run_id": _required_text(
            manifest.get("governed_run_id"),
            field_name="reviewed_factor_manifest.governed_run_id",
        ),
        "missing_rows": missing_rows,
        "missing_keys": {(row["stock_code"], row["trade_date"]) for row in missing_rows},
    }


def _validated_vendor_receipt_contract(
    vendor_receipt: Mapping[str, object],
    *,
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
    reviewed_factor_manifest: Mapping[str, object],
    reviewed_factor_manifest_path: Path,
    reviewed_factor_manifest_file_sha256: str,
) -> dict[str, Any]:
    if not isinstance(vendor_receipt, Mapping):
        raise CurrentRuleFactorWriteError("vendor_receipt must be a mapping")
    valid, errors = validate_stock_analysis_current_rule_factor_vendor_receipt(
        vendor_receipt,
        reviewed_factor_manifest=reviewed_factor_manifest,
        reviewed_factor_manifest_path=reviewed_factor_manifest_path,
        reviewed_factor_manifest_file_sha256=reviewed_factor_manifest_file_sha256,
    )
    if not valid:
        raise CurrentRuleFactorWriteError("vendor_receipt failed formal validation: " + "; ".join(errors))
    if vendor_receipt.get("receipt_kind") != VENDOR_RECEIPT_KIND:
        raise CurrentRuleFactorWriteError("vendor_receipt kind mismatch")
    if vendor_receipt.get("status") != VENDOR_READY_STATUS:
        raise CurrentRuleFactorWriteError("vendor_receipt status must be ready_for_write_approval")
    if vendor_receipt.get("database_write_executed") is not False:
        raise CurrentRuleFactorWriteError("vendor_receipt must attest that no database write was executed")
    if vendor_receipt.get("write_allowed") is not False:
        raise CurrentRuleFactorWriteError("vendor_receipt must not self-authorize a write")

    returned_cells = _normalize_returned_cells(
        vendor_receipt.get("returned_cells"),
        field_name="vendor_receipt.returned_cells",
        require_non_empty=True,
    )
    binding = vendor_receipt.get("manifest_binding")
    if not isinstance(binding, Mapping):
        raise CurrentRuleFactorWriteError("vendor_receipt.manifest_binding must be a mapping")
    if _required_text(binding.get("path"), field_name="vendor_receipt.manifest_binding.path") != str(
        reviewed_factor_manifest_path
    ):
        raise CurrentRuleFactorWriteError("vendor_receipt manifest path does not match reviewed manifest path")
    if _sha256_text(
        binding.get("file_sha256"),
        field_name="vendor_receipt.manifest_binding.file_sha256",
    ) != _sha256_text(
        reviewed_factor_manifest_file_sha256,
        field_name="reviewed_factor_manifest_file_sha256",
    ):
        raise CurrentRuleFactorWriteError("vendor_receipt manifest file SHA does not match reviewed manifest file")

    database = vendor_receipt.get("database")
    if not isinstance(database, Mapping):
        raise CurrentRuleFactorWriteError("vendor_receipt.database must be a mapping")
    database_path = _existing_file(
        _absolute_without_resolve(_required_text(database.get("path"), field_name="vendor_receipt.database.path")),
        field_name="vendor_receipt.database.path",
    )
    database_sha_before = _sha256_text(
        database.get("sha256_before"),
        field_name="vendor_receipt.database.sha256_before",
    )
    database_sha_after = _sha256_text(
        database.get("sha256_after"),
        field_name="vendor_receipt.database.sha256_after",
    )
    if database_sha_before != database_sha_after:
        raise CurrentRuleFactorWriteError("vendor_receipt database hashes must remain unchanged")
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        raise CurrentRuleFactorWriteError("vendor_receipt database must attest unchanged read-only access")

    return {
        "path": vendor_receipt_path,
        "file_sha256": _sha256_text(
            vendor_receipt_file_sha256,
            field_name="vendor_receipt_file_sha256",
        ),
        "canonical_receipt_sha256": _sha256_text(
            vendor_receipt.get("canonical_receipt_sha256"),
            field_name="vendor_receipt.canonical_receipt_sha256",
        ),
        "database_path": database_path,
        "database_sha256": database_sha_before,
        "returned_cells": returned_cells,
        "returned_cells_sha256": _sha256_text(
            vendor_receipt.get("returned_cells_sha256"),
            field_name="vendor_receipt.returned_cells_sha256",
        ),
        "proposed_source_version": _required_text(
            vendor_receipt.get("proposed_source_version"),
            field_name="vendor_receipt.proposed_source_version",
        ),
        "proposed_run_id": _required_text(
            vendor_receipt.get("proposed_run_id"),
            field_name="vendor_receipt.proposed_run_id",
        ),
        "returned_cell_count": len(returned_cells),
    }


def _assert_exact_factor_schema(conn: duckdb.DuckDBPyConnection) -> None:
    rows = conn.execute(f"pragma table_info('{FACTOR_TABLE}')").fetchall()
    if not rows:
        raise CurrentRuleFactorWriteError("stock_adjustment_factor table is missing")
    observed = tuple((str(row[1]).lower(), str(row[2]).upper()) for row in rows)
    expected = tuple((name, dtype) for name, dtype in EXPECTED_FACTOR_SCHEMA)
    if observed != expected:
        raise CurrentRuleFactorWriteError(
            "stock_adjustment_factor schema must stay the exact five-column governed shape"
        )


def _assert_global_table_quality(conn: duckdb.DuckDBPyConnection) -> None:
    duplicate = conn.execute(
        f"""
        with normalized as (
            select
                upper(trim(cast(stock_code as varchar))) as normalized_stock_code,
                try_cast(trim(cast(trade_date as varchar)) as date) as normalized_trade_date
            from {FACTOR_TABLE}
        )
        select normalized_stock_code, cast(normalized_trade_date as varchar), count(*) as row_count
        from normalized
        where normalized_stock_code <> ''
          and normalized_trade_date is not null
        group by normalized_stock_code, normalized_trade_date
        having count(*) > 1
        limit 1
        """
    ).fetchone()
    if duplicate is not None:
        raise CurrentRuleFactorWriteError("stock_adjustment_factor contains duplicate natural keys")

    required_blank = conn.execute(
        f"""
        select 1
        from {FACTOR_TABLE}
        where trim(coalesce(cast(stock_code as varchar), '')) = ''
           or trim(coalesce(cast(trade_date as varchar), '')) = ''
           or trim(coalesce(cast(source_version as varchar), '')) = ''
           or trim(coalesce(cast(run_id as varchar), '')) = ''
        limit 1
        """
    ).fetchone()
    if required_blank is not None:
        raise CurrentRuleFactorWriteError("stock_adjustment_factor contains blank required fields")

    noncanonical_key = conn.execute(
        f"""
        select 1
        from {FACTOR_TABLE}
        where cast(stock_code as varchar) <> upper(trim(cast(stock_code as varchar)))
           or try_cast(trim(cast(trade_date as varchar)) as date) is null
           or cast(try_cast(trim(cast(trade_date as varchar)) as date) as varchar) <> trim(cast(trade_date as varchar))
        limit 1
        """
    ).fetchone()
    if noncanonical_key is not None:
        raise CurrentRuleFactorWriteError("stock_adjustment_factor contains noncanonical stock_code or trade_date keys")

    invalid_factor = conn.execute(
        f"""
        select 1
        from {FACTOR_TABLE}
        where adj_factor is null
           or not isfinite(adj_factor)
           or adj_factor <= 0
        limit 1
        """
    ).fetchone()
    if invalid_factor is not None:
        raise CurrentRuleFactorWriteError("stock_adjustment_factor contains nonpositive or nonfinite factors")


def _assert_target_cells_absent(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_rows: Sequence[Mapping[str, Any]],
) -> None:
    rows = _existing_target_rows(conn, target_rows=target_rows)
    if rows:
        raise CurrentRuleFactorWriteError("target factor cells already exist in stock_adjustment_factor")


def _table_row_count(conn: duckdb.DuckDBPyConnection) -> int:
    return int(cast(tuple[int], conn.execute(f"select count(*) from {FACTOR_TABLE}").fetchone())[0])


def _insert_target_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
) -> None:
    conn.executemany(
        f"""
        insert into {FACTOR_TABLE}
        (stock_code, trade_date, adj_factor, source_version, run_id)
        values (?, ?, ?, ?, ?)
        """,
        [
            (
                str(row["stock_code"]),
                str(row["trade_date"]),
                float(row["adj_factor"]),
                source_version,
                run_id,
            )
            for row in target_rows
        ],
    )


def _verify_transaction_postconditions(
    conn: duckdb.DuckDBPyConnection,
    *,
    row_count_before: int,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
) -> None:
    expected_delta = len(target_rows)
    if _table_row_count(conn) != row_count_before + expected_delta:
        raise CurrentRuleFactorWriteError("transaction row count delta mismatch")
    _assert_global_table_quality(conn)
    _verify_target_rows_exact(
        conn,
        target_rows=target_rows,
        source_version=source_version,
        run_id=run_id,
    )


def _verify_target_rows_exact(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
) -> None:
    observed_rows = _load_target_rows(
        conn,
        target_rows=target_rows,
    )
    expected_rows = [
        {
            "requested_trade_date": str(row["trade_date"]),
            "stock_code": str(row["stock_code"]),
            "trade_date": str(row["trade_date"]),
            "adj_factor": float(row["adj_factor"]),
            "source_version": source_version,
            "run_id": run_id,
        }
        for row in _normalize_returned_cells(
            target_rows,
            field_name="target_rows",
            require_non_empty=True,
        )
    ]
    if observed_rows != expected_rows:
        raise CurrentRuleFactorWriteError("target factor rows do not match the approved exact source/run payload")


def _existing_target_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_rows: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str]]:
    rows = _load_target_rows(conn, target_rows=target_rows)
    return [(str(row["stock_code"]), str(row["trade_date"])) for row in rows]


def _load_target_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized = _normalize_returned_cells(
        target_rows,
        field_name="target_rows",
        require_non_empty=True,
    )
    values_sql = ",".join("(?, ?)" for _ in normalized)
    params: list[object] = []
    for target_row in normalized:
        params.extend((target_row["stock_code"], target_row["trade_date"]))
    rows = conn.execute(
        f"""
        with target_cells(stock_code, trade_date) as (
            values {values_sql}
        )
        select
            cast(f.stock_code as varchar),
            cast(f.trade_date as varchar),
            f.adj_factor,
            cast(f.source_version as varchar),
            cast(f.run_id as varchar)
        from {FACTOR_TABLE} as f
        inner join target_cells as t
          on upper(trim(cast(f.stock_code as varchar))) = t.stock_code
         and try_cast(trim(cast(f.trade_date as varchar)) as date) = cast(t.trade_date as date)
        order by cast(f.trade_date as varchar), cast(f.stock_code as varchar)
        """,
        params,
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "requested_trade_date": str(row[1]),
                "stock_code": str(row[0]),
                "trade_date": str(row[1]),
                "adj_factor": _positive_finite_float(
                    row[2],
                    field_name="loaded_target_row.adj_factor",
                ),
                "source_version": str(row[3]),
                "run_id": str(row[4]),
            }
        )
    return result


def _create_prewrite_backup(*, target: Path, backup_path: Path) -> str:
    if os.path.lexists(backup_path):
        raise CurrentRuleFactorWriteError("target_backup_file must be new")
    created = False
    try:
        with target.open("rb") as source, backup_path.open("xb") as destination:
            created = True
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
    except Exception:
        if created:
            backup_path.unlink(missing_ok=True)
        raise
    backup_sha = _file_sha256(backup_path)
    target_sha = _file_sha256(target)
    if backup_sha != target_sha:
        backup_path.unlink(missing_ok=True)
        raise CurrentRuleFactorWriteError("backup must be byte-identical to the pre-write target database")
    return backup_sha


def _assert_no_unmerged_duckdb_sidecars(target: Path) -> None:
    """Reject a byte-copy backup while DuckDB WAL state may be unmerged."""

    wal_path = target.with_name(f"{target.name}.wal")
    related_wal_paths = sorted(
        target.parent.glob(f"{target.name}.wal.*"),
        key=lambda path: path.name,
    )
    sidecars = [wal_path, *related_wal_paths]
    existing = [path for path in sidecars if os.path.lexists(path)]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise CurrentRuleFactorWriteError(f"unmerged DuckDB WAL/sidecar prevents a complete pre-write backup: {names}")


def _build_pending_write_intent(
    *,
    executed_at: str,
    approval_reference: str,
    approved_scope_sha256: str,
    reviewed_manifest_path: Path,
    reviewed_manifest_file_sha256: str,
    reviewed_manifest: Mapping[str, object],
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
    vendor_receipt: Mapping[str, object],
    db_path: Path,
    db_sha_before: str,
    backup_path: Path,
    backup_sha256: str,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
) -> dict[str, Any]:
    """Build a non-completion intent that survives receipt-finalization failure."""

    manifest_database = _mapping(
        reviewed_manifest.get("database"),
        field_name="reviewed_factor_manifest.database",
    )
    vendor_database = _mapping(
        vendor_receipt.get("database"),
        field_name="vendor_receipt.database",
    )
    normalized_target_rows = _normalize_returned_cells(
        target_rows,
        field_name="target_rows",
        require_non_empty=True,
    )
    pending: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": PENDING_INTENT_KIND,
        "status": PENDING_STATUS,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": approved_scope_sha256,
        # A pending artifact deliberately does not assert whether a later
        # transaction committed. Its continued presence requires read-only
        # reconciliation and must never be interpreted as completion.
        "database_write_executed": None,
        "physical_gap_remediation_completed": None,
        "completion_attested": False,
        "additional_write_allowed": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "downstream_materialization_executed": False,
        "touched_tables": list(TOUCHED_TABLES),
        "reviewed_manifest_binding": {
            "path": str(reviewed_manifest_path),
            "file_sha256": reviewed_manifest_file_sha256,
            "canonical_manifest_sha256": reviewed_manifest.get("canonical_manifest_sha256"),
            "manifest_kind": reviewed_manifest.get("manifest_kind"),
            "governed_run_id": reviewed_manifest.get("governed_run_id"),
            "database_path": manifest_database.get("path"),
            "database_sha256": manifest_database.get("sha256_before"),
        },
        "vendor_receipt_binding": {
            "path": str(vendor_receipt_path),
            "file_sha256": vendor_receipt_file_sha256,
            "canonical_receipt_sha256": vendor_receipt.get("canonical_receipt_sha256"),
            "receipt_kind": vendor_receipt.get("receipt_kind"),
            "status": vendor_receipt.get("status"),
            "database_path": vendor_database.get("path"),
            "database_sha256": vendor_database.get("sha256_before"),
            "returned_cells_sha256": vendor_receipt.get("returned_cells_sha256"),
            "proposed_source_version": vendor_receipt.get("proposed_source_version"),
            "proposed_run_id": vendor_receipt.get("proposed_run_id"),
            "returned_cell_count": vendor_receipt.get("returned_cell_count"),
        },
        "database": {
            "path": str(db_path),
            "sha256_before": db_sha_before,
            "sha256_after": None,
            "changed": None,
        },
        "backup": {
            "path": str(backup_path),
            "sha256": backup_sha256,
            "created_exclusive": True,
            "byte_identical_prewrite_target": True,
        },
        "target_cell_count": len(normalized_target_rows),
        "target_rows": normalized_target_rows,
        "target_rows_sha256": _canonical_json_sha256(normalized_target_rows),
        "source_version": source_version,
        "run_id": run_id,
        "recovery_instruction": (
            "This pending intent does not attest completion. Do not retry the write; "
            "first reconcile the exact target rows, source_version, run_id, database "
            "SHA, and verified backup using read-only checks."
        ),
    }
    pending["canonical_pending_intent_sha256"] = _pending_intent_sha256(pending)
    return pending


def _build_write_receipt(
    *,
    executed_at: str,
    approval_reference: str,
    reviewed_manifest_path: Path,
    reviewed_manifest_file_sha256: str,
    reviewed_manifest: Mapping[str, object],
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
    vendor_receipt: Mapping[str, object],
    db_path: Path,
    db_sha_before: str,
    db_sha_after: str,
    backup_path: Path,
    backup_sha256: str,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
    approved_scope_sha256: str,
) -> dict[str, Any]:
    manifest_binding = dict(_mapping(reviewed_manifest.get("database"), field_name="reviewed_factor_manifest.database"))
    vendor_binding = dict(_mapping(vendor_receipt.get("database"), field_name="vendor_receipt.database"))
    normalized_target_rows = _normalize_returned_cells(
        target_rows,
        field_name="target_rows",
        require_non_empty=True,
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": WRITE_RECEIPT_KIND,
        "status": COMPLETED_STATUS,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "approval_scope": APPROVAL_SCOPE,
        "database_write_executed": True,
        "additional_write_allowed": False,
        "physical_gap_remediation_completed": True,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "downstream_materialization_executed": False,
        "no_overwrite_or_delete_performed": True,
        "touched_tables": list(TOUCHED_TABLES),
        "rollback_instruction": ROLLBACK_INSTRUCTION,
        "reviewed_manifest_binding": {
            "path": str(reviewed_manifest_path),
            "file_sha256": reviewed_manifest_file_sha256,
            "canonical_manifest_sha256": reviewed_manifest.get("canonical_manifest_sha256"),
            "manifest_kind": reviewed_manifest.get("manifest_kind"),
            "governed_run_id": reviewed_manifest.get("governed_run_id"),
            "database_path": manifest_binding.get("path"),
            "database_sha256": manifest_binding.get("sha256_before"),
        },
        "vendor_receipt_binding": {
            "path": str(vendor_receipt_path),
            "file_sha256": vendor_receipt_file_sha256,
            "canonical_receipt_sha256": vendor_receipt.get("canonical_receipt_sha256"),
            "receipt_kind": vendor_receipt.get("receipt_kind"),
            "status": vendor_receipt.get("status"),
            "database_path": vendor_binding.get("path"),
            "database_sha256": vendor_binding.get("sha256_before"),
            "returned_cells_sha256": vendor_receipt.get("returned_cells_sha256"),
            "proposed_source_version": vendor_receipt.get("proposed_source_version"),
            "proposed_run_id": vendor_receipt.get("proposed_run_id"),
            "returned_cell_count": vendor_receipt.get("returned_cell_count"),
        },
        "database": {
            "path": str(db_path),
            "sha256_before": db_sha_before,
            "sha256_after": db_sha_after,
            "changed": db_sha_before != db_sha_after,
        },
        "backup": {
            "path": str(backup_path),
            "sha256": backup_sha256,
            "created_exclusive": True,
            "byte_identical_prewrite_target": True,
        },
        "inserted_row_count": len(normalized_target_rows),
        "target_cell_count": len(normalized_target_rows),
        "target_rows": normalized_target_rows,
        "target_rows_sha256": _canonical_json_sha256(normalized_target_rows),
        "source_version": source_version,
        "run_id": run_id,
        "approval_scope_sha256": approved_scope_sha256,
    }
    receipt["canonical_write_receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def _validate_manifest_binding(
    value: object,
    *,
    field_name: str,
    errors: list[str],
    expected_kind: str,
) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field_name} must be a mapping")
        return None
    try:
        path = _required_text(value.get("path"), field_name=f"{field_name}.path")
        file_sha256 = _sha256_text(
            value.get("file_sha256"),
            field_name=f"{field_name}.file_sha256",
        )
        canonical_sha256 = _sha256_text(
            value.get("canonical_manifest_sha256"),
            field_name=f"{field_name}.canonical_manifest_sha256",
        )
        governed_run_id = _required_text(
            value.get("governed_run_id"),
            field_name=f"{field_name}.governed_run_id",
        )
        database_path = _required_text(
            value.get("database_path"),
            field_name=f"{field_name}.database_path",
        )
        database_sha256 = _sha256_text(
            value.get("database_sha256"),
            field_name=f"{field_name}.database_sha256",
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("manifest_kind") != expected_kind:
        errors.append(f"{field_name}.manifest_kind mismatch")
    return {
        "path": path,
        "file_sha256": file_sha256,
        "canonical_sha256": canonical_sha256,
        "governed_run_id": governed_run_id,
        "database_path": database_path,
        "database_sha256": database_sha256,
    }


def _validate_vendor_binding(
    value: object,
    *,
    errors: list[str],
) -> _VendorBinding | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.vendor_receipt_binding must be a mapping")
        return None
    try:
        path = _required_text(value.get("path"), field_name="receipt.vendor_receipt_binding.path")
        file_sha256 = _sha256_text(
            value.get("file_sha256"),
            field_name="receipt.vendor_receipt_binding.file_sha256",
        )
        canonical_receipt_sha256 = _sha256_text(
            value.get("canonical_receipt_sha256"),
            field_name="receipt.vendor_receipt_binding.canonical_receipt_sha256",
        )
        database_path = _required_text(
            value.get("database_path"),
            field_name="receipt.vendor_receipt_binding.database_path",
        )
        database_sha256 = _sha256_text(
            value.get("database_sha256"),
            field_name="receipt.vendor_receipt_binding.database_sha256",
        )
        returned_cells_sha256 = _sha256_text(
            value.get("returned_cells_sha256"),
            field_name="receipt.vendor_receipt_binding.returned_cells_sha256",
        )
        proposed_source_version = _required_text(
            value.get("proposed_source_version"),
            field_name="receipt.vendor_receipt_binding.proposed_source_version",
        )
        proposed_run_id = _required_text(
            value.get("proposed_run_id"),
            field_name="receipt.vendor_receipt_binding.proposed_run_id",
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("receipt_kind") != VENDOR_RECEIPT_KIND:
        errors.append("receipt.vendor_receipt_binding.receipt_kind mismatch")
    if value.get("status") != VENDOR_READY_STATUS:
        errors.append("receipt.vendor_receipt_binding.status mismatch")
    returned_cell_count = value.get("returned_cell_count")
    if not _exact_positive_int(returned_cell_count):
        errors.append("receipt.vendor_receipt_binding.returned_cell_count must be a positive int")
        return None
    return {
        "path": path,
        "file_sha256": file_sha256,
        "canonical_receipt_sha256": canonical_receipt_sha256,
        "database_path": database_path,
        "database_sha256": database_sha256,
        "returned_cells_sha256": returned_cells_sha256,
        "proposed_source_version": proposed_source_version,
        "proposed_run_id": proposed_run_id,
        "returned_cell_count": int(returned_cell_count),
    }


def _validate_database_binding(
    value: object,
    *,
    errors: list[str],
) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.database must be a mapping")
        return None
    try:
        path = _required_text(value.get("path"), field_name="receipt.database.path")
        sha256_before = _sha256_text(
            value.get("sha256_before"),
            field_name="receipt.database.sha256_before",
        )
        sha256_after = _sha256_text(
            value.get("sha256_after"),
            field_name="receipt.database.sha256_after",
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("changed") is not True:
        errors.append("receipt.database.changed must be true")
    if sha256_before == sha256_after:
        errors.append("receipt.database SHA must change across the committed write")
    return {"path": path, "sha256_before": sha256_before, "sha256_after": sha256_after}


def _validate_backup_binding(
    value: object,
    *,
    errors: list[str],
) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.backup must be a mapping")
        return None
    try:
        path = _required_text(value.get("path"), field_name="receipt.backup.path")
        sha256 = _sha256_text(value.get("sha256"), field_name="receipt.backup.sha256")
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("created_exclusive") is not True:
        errors.append("receipt.backup.created_exclusive must be true")
    if value.get("byte_identical_prewrite_target") is not True:
        errors.append("receipt.backup.byte_identical_prewrite_target must be true")
    return {"path": path, "sha256": sha256}


def _missing_rows_from_manifest(manifest: Mapping[str, object]) -> list[dict[str, Any]]:
    raw_missing = manifest.get("missing_unique_cells")
    if not isinstance(raw_missing, Sequence) or isinstance(raw_missing, (str, bytes, bytearray)):
        raise CurrentRuleFactorWriteError("reviewed_factor_manifest.missing_unique_cells must be a list")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(raw_missing):
        if not isinstance(raw_cell, Mapping):
            raise CurrentRuleFactorWriteError(
                f"reviewed_factor_manifest.missing_unique_cells[{index}] must be a mapping"
            )
        stock_code = _stock_code(
            raw_cell.get("stock_code"),
            field_name=f"reviewed_factor_manifest.missing_unique_cells[{index}].stock_code",
        )
        trade_date = _iso_date_text(
            raw_cell.get("trade_date"),
            field_name=f"reviewed_factor_manifest.missing_unique_cells[{index}].trade_date",
        )
        key = (stock_code, trade_date)
        if key in seen:
            raise CurrentRuleFactorWriteError(
                "reviewed_factor_manifest.missing_unique_cells contains duplicate physical keys"
            )
        seen.add(key)
        rows.append(
            {
                "stock_code": stock_code,
                "trade_date": trade_date,
                "adj_factor": None,
            }
        )
    return sorted(rows, key=lambda row: (row["trade_date"], row["stock_code"]))


def _normalize_returned_cells(
    value: object,
    *,
    field_name: str,
    require_non_empty: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CurrentRuleFactorWriteError(f"{field_name} must be a list")
    if require_non_empty and not value:
        raise CurrentRuleFactorWriteError(f"{field_name} must not be empty")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(value):
        if not isinstance(raw_cell, Mapping):
            raise CurrentRuleFactorWriteError(f"{field_name}[{index}] must be a mapping")
        stock_code = _stock_code(
            raw_cell.get("stock_code"),
            field_name=f"{field_name}[{index}].stock_code",
        )
        requested_trade_date = _iso_date_text(
            raw_cell.get("requested_trade_date"),
            field_name=f"{field_name}[{index}].requested_trade_date",
        )
        trade_date = _iso_date_text(
            raw_cell.get("trade_date"),
            field_name=f"{field_name}[{index}].trade_date",
        )
        if requested_trade_date != trade_date:
            raise CurrentRuleFactorWriteError(
                f"{field_name}[{index}] returned trade_date must equal requested_trade_date"
            )
        adj_factor = _positive_finite_float(
            raw_cell.get("adj_factor"),
            field_name=f"{field_name}[{index}].adj_factor",
        )
        key = (stock_code, trade_date)
        if key in seen:
            raise CurrentRuleFactorWriteError(f"{field_name} contains duplicate natural keys")
        seen.add(key)
        normalized.append(
            {
                "requested_trade_date": requested_trade_date,
                "stock_code": stock_code,
                "trade_date": trade_date,
                "adj_factor": adj_factor,
            }
        )
    return sorted(normalized, key=lambda row: (row["trade_date"], row["stock_code"]))


def _target_row_keys(rows: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    return {(str(row["stock_code"]), str(row["trade_date"])) for row in rows}


def _write_json_exclusive(path: Path, *, payload: Mapping[str, Any]) -> None:
    encoded = _encoded_json(payload)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def _replace_json_atomically_preserving_existing(
    path: Path,
    *,
    payload: Mapping[str, Any],
    expected_existing: Mapping[str, Any],
) -> None:
    """Atomically replace the exact pending intent with a verified final receipt."""

    if _is_forbidden_link_component(path):
        raise CurrentRuleFactorWriteError("write_receipt_file pending intent became a forbidden symlink/junction")
    persisted_pending = _load_json_object(
        path,
        field_name="write_receipt_file pending intent",
    )
    if persisted_pending != dict(expected_existing):
        raise CurrentRuleFactorWriteError("write_receipt_file pending intent changed before finalization")

    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".completed.tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(raw_temp_path)
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_encoded_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        persisted_temp = _load_json_object(
            temp_path,
            field_name="completed write receipt temporary file",
        )
        if persisted_temp != dict(payload):
            raise CurrentRuleFactorWriteError("completed write receipt temporary file does not match generated receipt")
        os.replace(temp_path, path)
        replaced = True
    finally:
        if not replaced:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temp_path.unlink(missing_ok=True)


def _encoded_json(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def _existing_json_file_within_root(
    *,
    trusted_root: Path,
    path: str | Path,
    field_name: str,
) -> Path:
    candidate = _path_within_root(
        trusted_root=trusted_root,
        path=path,
        field_name=field_name,
    )
    if candidate.suffix.lower() != ".json":
        raise CurrentRuleFactorWriteError(f"{field_name} must be a JSON file")
    return _existing_file(candidate, field_name=field_name)


def _new_json_file_within_root(
    *,
    trusted_root: Path,
    path: str | Path,
    field_name: str,
) -> Path:
    candidate = _path_within_root(
        trusted_root=trusted_root,
        path=path,
        field_name=field_name,
    )
    if candidate.suffix.lower() != ".json":
        raise CurrentRuleFactorWriteError(f"{field_name} must use a .json extension")
    if os.path.lexists(candidate):
        raise CurrentRuleFactorWriteError(f"{field_name} must be new; existing evidence is never overwritten")
    if not candidate.parent.is_dir():
        raise CurrentRuleFactorWriteError(f"{field_name} parent must be an existing directory")
    return candidate


def _new_backup_path_for_target(*, target: Path, backup_path: str | Path) -> Path:
    candidate = _absolute_without_resolve(backup_path)
    _assert_no_symlink_in_raw_path(candidate, field_name="target_backup_file")
    backups_root = _existing_directory(target.parent / "backups", field_name="target backups directory")
    try:
        candidate.relative_to(backups_root)
    except ValueError as exc:
        raise CurrentRuleFactorWriteError("target_backup_file must stay within <duckdb parent>/backups") from exc
    if candidate.parent != backups_root and not candidate.parent.is_dir():
        raise CurrentRuleFactorWriteError("target_backup_file parent must be an existing directory inside backups")
    if candidate == target or os.path.samefile(candidate.parent, target.parent) and candidate.name == target.name:
        raise CurrentRuleFactorWriteError("target_backup_file must not alias the live database path")
    if os.path.lexists(candidate):
        raise CurrentRuleFactorWriteError("target_backup_file must be new")
    return candidate


def _path_within_root(
    *,
    trusted_root: Path,
    path: str | Path,
    field_name: str,
) -> Path:
    root = _absolute_without_resolve(trusted_root)
    raw = Path(path)
    candidate = _absolute_without_resolve(raw if raw.is_absolute() else root / raw)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CurrentRuleFactorWriteError(f"{field_name} must stay within trusted_evidence_root") from exc
    _assert_no_symlink_in_raw_path(candidate, field_name=field_name)
    return candidate


def _load_json_object(path: Path, *, field_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentRuleFactorWriteError(f"{field_name} must be readable UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise CurrentRuleFactorWriteError(f"{field_name} must contain a JSON object")
    return dict(payload)


def _existing_directory(path: Path, *, field_name: str) -> Path:
    if not path.is_dir():
        raise CurrentRuleFactorWriteError(f"{field_name} must be an existing directory")
    return path


def _existing_file(path: Path, *, field_name: str) -> Path:
    if not path.is_file():
        raise CurrentRuleFactorWriteError(f"{field_name} must be an existing file")
    return path


def _assert_no_symlink_in_raw_path(path: Path, *, field_name: str) -> None:
    current: Path | None = None
    for part in path.parts:
        current = Path(part) if current is None else current / part
        if current.exists() and _is_forbidden_link_component(current):
            raise CurrentRuleFactorWriteError(f"{field_name} contains forbidden symlink/junction component: {current}")


def _is_forbidden_link_component(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            return bool(is_junction())
        except OSError:
            return False
    return False


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except Exception as exc:
        _ = exc


def _absolute_without_resolve(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CurrentRuleFactorWriteError(f"{field_name} must be a mapping")
    return dict(value)


def _stock_code(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name).upper()
    if any(character.isspace() for character in normalized):
        raise CurrentRuleFactorWriteError(f"{field_name} must not contain whitespace")
    return normalized


def _iso_date_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise CurrentRuleFactorWriteError(f"{field_name} must be an ISO date")
    try:
        normalized = date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CurrentRuleFactorWriteError(f"{field_name} must be an ISO date") from exc
    if normalized != value:
        raise CurrentRuleFactorWriteError(f"{field_name} must be a canonical ISO date")
    return normalized


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentRuleFactorWriteError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise CurrentRuleFactorWriteError(f"{field_name} must use UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _positive_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise CurrentRuleFactorWriteError(f"{field_name} must be a positive finite number")
    try:
        parsed = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError) as exc:
        raise CurrentRuleFactorWriteError(f"{field_name} must be a positive finite number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise CurrentRuleFactorWriteError(f"{field_name} must be a positive finite number")
    return parsed


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise CurrentRuleFactorWriteError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _sha256_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip() or value != value.upper():
        raise CurrentRuleFactorWriteError(f"{field_name} must be an uppercase sha256")
    if len(value) != 64 or any(character not in "0123456789ABCDEF" for character in value):
        raise CurrentRuleFactorWriteError(f"{field_name} must be an uppercase sha256")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_write_receipt_sha256", None)
    return _canonical_json_sha256(payload)


def _pending_intent_sha256(intent: Mapping[str, object]) -> str:
    payload = dict(intent)
    payload.pop("canonical_pending_intent_sha256", None)
    return _canonical_json_sha256(payload)


def _approval_scope_sha256(
    *,
    manifest_canonical_sha256: str,
    vendor_canonical_sha256: str,
    database_sha256_before: str,
    target_rows_sha256: str,
    target_cell_count: int,
) -> str:
    return _canonical_json_sha256(
        {
            "approval_scope": APPROVAL_SCOPE,
            "manifest_canonical_sha256": manifest_canonical_sha256,
            "vendor_canonical_sha256": vendor_canonical_sha256,
            "database_sha256_before": database_sha256_before,
            "target_rows_sha256": target_rows_sha256,
            "target_cell_count": target_cell_count,
        }
    )


def _validate_hash_equality(
    value: object,
    *,
    expected: str,
    field_name: str,
    errors: list[str],
) -> None:
    try:
        normalized = _sha256_text(value, field_name=field_name)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if normalized != expected:
        errors.append(f"{field_name} mismatch")


def _exact_int(value: object, expected: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value == expected


def _exact_positive_int(value: object) -> TypeGuard[int]:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _ordered(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
