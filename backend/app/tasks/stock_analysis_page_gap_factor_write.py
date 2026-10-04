"""Governed writer for a page-gap exact adjustment-factor approval scope.

The write is deliberately limited to inserting the exact cells in a formally
validated page-gap factor manifest and vendor receipt.  It creates one
byte-identical pre-write backup, writes a pending intent before opening a write
transaction, inserts only the canonical five columns, and verifies every row
after commit.  Downstream execution-history materialization remains a separate
operation and is explicitly false in the final receipt.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance import stock_analysis_page_gap_factor_vendor_receipt as vendor_task
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks import livermore_candidate_history_materialize as _history_task
from backend.app.tasks import stock_analysis_current_rule_factor_write as _write_helpers
from backend.app.tasks import stock_analysis_page_gap_factor_manifest as factor_manifest_task
from backend.app.tasks import stock_analysis_page_gap_manifest as page_manifest_task

SCHEMA_VERSION = 1
WRITE_RECEIPT_KIND = "stock_analysis_page_gap_factor_write_receipt_v1"
COMPLETED_STATUS = "physical_factor_remediation_completed"
PENDING_INTENT_KIND = "stock_analysis_page_gap_factor_write_pending_intent_v1"
PENDING_STATUS = "write_pending"
APPROVAL_SCOPE = vendor_task.APPROVAL_SCOPE
FACTOR_TABLE = _write_helpers.FACTOR_TABLE
TOUCHED_TABLES = [FACTOR_TABLE]
ROLLBACK_INSTRUCTION = (
    "Rollback requires separate explicit authorization and manual restoration "
    "of the verified backup; no automatic rollback is provided."
)
RECOVERY_INSTRUCTION = (
    "A pending intent does not attest completion. Do not retry; first reconcile "
    "the exact target rows, source_version, run_id, database SHA, and backup using "
    "read-only checks."
)

PageGapFactorWriteError = _write_helpers.CurrentRuleFactorWriteError
FileIdentity = tuple[int, int]


def write_stock_analysis_page_gap_factor_cells(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    page_gap_factor_manifest_file: str | Path,
    vendor_receipt_file: str | Path,
    target_backup_file: str | Path,
    write_receipt_file: str | Path,
    executed_at: str,
    approval_reference: str,
    expected_approved_scope_sha256: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Insert the approved exact cells in one transaction."""

    if allow_write is not True:
        raise PageGapFactorWriteError("allow_write must be explicitly true")
    executed_at_text = _write_helpers._utc_datetime_text(executed_at, field_name="executed_at")
    approval_text = _write_helpers._required_text(approval_reference, field_name="approval_reference")
    approved_scope_sha256 = _write_helpers._sha256_text(
        expected_approved_scope_sha256,
        field_name="expected_approved_scope_sha256",
    )

    raw_target = _write_helpers._absolute_without_resolve(duckdb_path)
    _write_helpers._assert_no_symlink_in_raw_path(raw_target, field_name="duckdb_path")
    target = _write_helpers._existing_file(raw_target, field_name="duckdb_path")
    trusted_root = _write_helpers._existing_directory(
        _write_helpers._absolute_without_resolve(trusted_evidence_root),
        field_name="trusted_evidence_root",
    )
    _write_helpers._assert_no_symlink_in_raw_path(trusted_root, field_name="trusted_evidence_root")
    trusted_root_identity = _capture_directory_identity(
        trusted_root,
        field_name="trusted_evidence_root",
    )
    factor_manifest_path = _write_helpers._existing_json_file_within_root(
        trusted_root=trusted_root,
        path=page_gap_factor_manifest_file,
        field_name="page_gap_factor_manifest_file",
    )
    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    vendor_receipt_path = _write_helpers._existing_json_file_within_root(
        trusted_root=trusted_root,
        path=vendor_receipt_file,
        field_name="vendor_receipt_file",
    )
    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    target_receipt_path = _write_helpers._new_json_file_within_root(
        trusted_root=trusted_root,
        path=write_receipt_file,
        field_name="write_receipt_file",
    )
    receipt_parent_identity = _capture_directory_identity(
        target_receipt_path.parent,
        field_name="write_receipt_file.parent",
    )
    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    backup_path = _write_helpers._new_backup_path_for_target(
        target=target,
        backup_path=target_backup_file,
    )
    backup_parent_identity = _capture_directory_identity(
        backup_path.parent,
        field_name="target_backup_file.parent",
    )

    factor_manifest = _write_helpers._load_json_object(factor_manifest_path, field_name="page_gap_factor_manifest_file")
    factor_manifest_file_sha256 = _write_helpers._file_sha256(factor_manifest_path)
    factor_contract = _validated_factor_manifest_contract(
        factor_manifest,
        factor_manifest_path=factor_manifest_path,
        factor_manifest_file_sha256=factor_manifest_file_sha256,
    )
    page_manifest, page_manifest_path, page_manifest_file_sha256 = _load_and_validate_external_page_manifest(
        trusted_root=trusted_root,
        factor_manifest=factor_manifest,
        factor_contract=factor_contract,
    )

    vendor_receipt = _write_helpers._load_json_object(vendor_receipt_path, field_name="vendor_receipt_file")
    vendor_receipt_file_sha256 = _write_helpers._file_sha256(vendor_receipt_path)
    vendor_contract = _validated_vendor_receipt_contract(
        vendor_receipt,
        vendor_receipt_path=vendor_receipt_path,
        vendor_receipt_file_sha256=vendor_receipt_file_sha256,
        factor_manifest=factor_manifest,
        factor_manifest_path=factor_manifest_path,
        factor_manifest_file_sha256=factor_manifest_file_sha256,
        factor_contract=factor_contract,
    )
    if target != factor_contract["database_path"]:
        raise PageGapFactorWriteError("duckdb_path does not match factor manifest")
    if target != vendor_contract["database_path"]:
        raise PageGapFactorWriteError("duckdb_path does not match vendor receipt")

    writer_lock = resolve_duckdb_writer_lock(target)
    with ExitStack() as lock_stack:
        lock_stack.enter_context(acquire_lock(writer_lock, base_dir=target.parent))
        lock_stack.enter_context(
            acquire_lock(
                _history_task.LIVERMORE_CANDIDATE_HISTORY_LOCK,
                base_dir=target.parent,
            )
        )
        _assert_evidence_files_unchanged(
            page_manifest_path=page_manifest_path,
            page_manifest_file_sha256=page_manifest_file_sha256,
            factor_manifest_path=factor_manifest_path,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
        )
        database_sha_before = _write_helpers._file_sha256(target)
        if database_sha_before != factor_contract["database_sha256"]:
            raise PageGapFactorWriteError("factor manifest database SHA does not match current DuckDB")
        if database_sha_before != vendor_contract["database_sha256"]:
            raise PageGapFactorWriteError("vendor receipt database SHA does not match current DuckDB")
        computed_scope = vendor_task.factor_approval_scope_sha256(
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            factor_manifest_canonical_sha256=factor_contract["canonical_manifest_sha256"],
            page_manifest_file_sha256=page_manifest_file_sha256,
            page_manifest_canonical_sha256=str(factor_contract["page_manifest_binding"]["canonical_manifest_sha256"]),
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
            vendor_receipt_canonical_sha256=vendor_contract["canonical_receipt_sha256"],
            database_sha256_before=database_sha_before,
            returned_cells_sha256=vendor_contract["returned_cells_sha256"],
            target_cell_count=len(vendor_contract["returned_cells"]),
            source_version=vendor_contract["source_version"],
            run_id=vendor_contract["run_id"],
        )
        if approved_scope_sha256 != computed_scope:
            raise PageGapFactorWriteError(
                "expected_approved_scope_sha256 does not match actual page/factor/vendor/DB target scope"
            )

        _write_helpers._assert_no_unmerged_duckdb_sidecars(target)
        with duckdb.connect(str(target), read_only=True) as preflight:
            _write_helpers._assert_exact_factor_schema(preflight)
            _write_helpers._assert_global_table_quality(preflight)
            _write_helpers._assert_target_cells_absent(preflight, target_rows=vendor_contract["returned_cells"])
        _write_helpers._assert_no_unmerged_duckdb_sidecars(target)
        backup_sha256, backup_file_identity = _create_prewrite_backup_hardened(
            target=target,
            backup_path=backup_path,
            backup_parent_identity=backup_parent_identity,
        )
        if backup_sha256 != database_sha_before:
            raise PageGapFactorWriteError("backup SHA must equal pre-write database SHA")
        _write_helpers._assert_no_unmerged_duckdb_sidecars(target)
        if _write_helpers._file_sha256(target) != database_sha_before:
            raise PageGapFactorWriteError("DuckDB changed after backup creation")

        pending_intent = _build_pending_intent(
            executed_at=executed_at_text,
            approval_reference=approval_text,
            approval_scope_sha256=approved_scope_sha256,
            page_manifest=page_manifest,
            page_manifest_path=page_manifest_path,
            page_manifest_file_sha256=page_manifest_file_sha256,
            factor_manifest=factor_manifest,
            factor_manifest_path=factor_manifest_path,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            vendor_receipt=vendor_receipt,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
            database_path=target,
            database_sha_before=database_sha_before,
            backup_path=backup_path,
            backup_sha256=backup_sha256,
            target_rows=vendor_contract["returned_cells"],
            source_version=vendor_contract["source_version"],
            run_id=vendor_contract["run_id"],
        )
        pending_file_identity = _write_json_exclusive_hardened(
            path=target_receipt_path,
            payload=pending_intent,
            trusted_root=trusted_root,
            trusted_root_identity=trusted_root_identity,
            parent_identity=receipt_parent_identity,
        )
        persisted_pending = _write_helpers._load_json_object(
            target_receipt_path, field_name="write_receipt_file pending intent"
        )
        if persisted_pending != pending_intent:
            raise PageGapFactorWriteError("persisted pending intent mismatch")
        _assert_leaf_identity(
            target_receipt_path,
            expected_identity=pending_file_identity,
            field_name="write_receipt_file pending intent",
        )

        with duckdb.connect(str(target), read_only=False) as conn:
            row_count_before = _write_helpers._table_row_count(conn)
            try:
                conn.execute("begin transaction")
                _write_helpers._assert_exact_factor_schema(conn)
                _write_helpers._assert_global_table_quality(conn)
                _write_helpers._assert_target_cells_absent(conn, target_rows=vendor_contract["returned_cells"])
                _write_helpers._insert_target_rows(
                    conn,
                    target_rows=vendor_contract["returned_cells"],
                    source_version=vendor_contract["source_version"],
                    run_id=vendor_contract["run_id"],
                )
                _write_helpers._verify_transaction_postconditions(
                    conn,
                    row_count_before=row_count_before,
                    target_rows=vendor_contract["returned_cells"],
                    source_version=vendor_contract["source_version"],
                    run_id=vendor_contract["run_id"],
                )
                conn.execute("commit")
            except Exception:
                _write_helpers._rollback_quietly(conn)
                raise

        with duckdb.connect(str(target), read_only=True) as postflight:
            _write_helpers._assert_exact_factor_schema(postflight)
            _write_helpers._assert_global_table_quality(postflight)
            _write_helpers._verify_target_rows_exact(
                postflight,
                target_rows=vendor_contract["returned_cells"],
                source_version=vendor_contract["source_version"],
                run_id=vendor_contract["run_id"],
            )
        database_sha_after = _write_helpers._file_sha256(target)
        if database_sha_after == database_sha_before:
            raise PageGapFactorWriteError("database SHA must change after committed insert")
        _assert_evidence_files_unchanged(
            page_manifest_path=page_manifest_path,
            page_manifest_file_sha256=page_manifest_file_sha256,
            factor_manifest_path=factor_manifest_path,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
        )
        _assert_directory_identity(
            backup_path.parent,
            expected_identity=backup_parent_identity,
            field_name="target_backup_file.parent",
        )
        _assert_leaf_identity(
            backup_path,
            expected_identity=backup_file_identity,
            field_name="target_backup_file",
        )

        receipt = _build_write_receipt(
            executed_at=executed_at_text,
            approval_reference=approval_text,
            approval_scope_sha256=approved_scope_sha256,
            page_manifest=page_manifest,
            page_manifest_path=page_manifest_path,
            page_manifest_file_sha256=page_manifest_file_sha256,
            factor_manifest=factor_manifest,
            factor_manifest_path=factor_manifest_path,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            vendor_receipt=vendor_receipt,
            vendor_receipt_path=vendor_receipt_path,
            vendor_receipt_file_sha256=vendor_receipt_file_sha256,
            database_path=target,
            database_sha_before=database_sha_before,
            database_sha_after=database_sha_after,
            backup_path=backup_path,
            backup_sha256=backup_sha256,
            target_rows=vendor_contract["returned_cells"],
            source_version=vendor_contract["source_version"],
            run_id=vendor_contract["run_id"],
        )
        valid, errors = validate_stock_analysis_page_gap_factor_write_receipt(
            receipt,
            page_gap_factor_manifest=factor_manifest,
            vendor_receipt=vendor_receipt,
        )
        if not valid:
            raise PageGapFactorWriteError("generated write receipt failed validation: " + "; ".join(errors))
        final_receipt_identity = _replace_json_atomically_hardened(
            path=target_receipt_path,
            payload=receipt,
            expected_existing=pending_intent,
            expected_pending_identity=pending_file_identity,
            trusted_root=trusted_root,
            trusted_root_identity=trusted_root_identity,
            parent_identity=receipt_parent_identity,
        )
        persisted = _write_helpers._load_json_object(target_receipt_path, field_name="write_receipt_file")
        if persisted != receipt:
            raise PageGapFactorWriteError("persisted write receipt mismatch")
        _assert_leaf_identity(
            target_receipt_path,
            expected_identity=final_receipt_identity,
            field_name="write_receipt_file final receipt",
        )
        valid, errors = validate_stock_analysis_page_gap_factor_write_receipt(
            persisted,
            page_gap_factor_manifest=factor_manifest,
            vendor_receipt=vendor_receipt,
        )
        if not valid:
            raise PageGapFactorWriteError("persisted write receipt failed validation: " + "; ".join(errors))
        return persisted


def validate_stock_analysis_page_gap_factor_write_receipt(
    receipt: Mapping[str, object],
    *,
    page_gap_factor_manifest: Mapping[str, object] | None = None,
    vendor_receipt: Mapping[str, object] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate the final self-hash, boundaries, bindings, and exact digests."""

    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    errors: list[str] = []
    if (page_gap_factor_manifest is None) ^ (vendor_receipt is None):
        errors.append("factor manifest and vendor receipt must be supplied together")
    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("receipt_kind", WRITE_RECEIPT_KIND),
        ("status", COMPLETED_STATUS),
        ("approval_scope", APPROVAL_SCOPE),
        ("database_write_executed", True),
        ("additional_write_allowed", False),
        ("physical_factor_remediation_completed", True),
        ("completion_attested", True),
        ("historical_availability_proven", False),
        ("formal_historical_replay_use_allowed", False),
        ("certification_allowed", False),
        ("downstream_materialization_executed", False),
        ("page_gap_closed", False),
        ("no_overwrite_or_delete_performed", True),
    ):
        observed = payload.get(field_name)
        if isinstance(expected, bool):
            if observed is not expected:
                errors.append(f"receipt.{field_name} mismatch")
        elif observed != expected:
            errors.append(f"receipt.{field_name} mismatch")
    try:
        executed_at = _write_helpers._utc_datetime_text(payload.get("executed_at"), field_name="receipt.executed_at")
        if payload.get("executed_at") != executed_at:
            errors.append("receipt.executed_at must be canonical UTC")
        _write_helpers._required_text(payload.get("approval_reference"), field_name="receipt.approval_reference")
    except ValueError as exc:
        errors.append(str(exc))
    if payload.get("touched_tables") != TOUCHED_TABLES:
        errors.append("receipt.touched_tables mismatch")
    if payload.get("rollback_instruction") != ROLLBACK_INSTRUCTION:
        errors.append("receipt.rollback_instruction mismatch")

    page_binding = _validate_page_binding(payload.get("page_manifest_binding"), errors)
    factor_binding = _validate_factor_binding(payload.get("factor_manifest_binding"), errors)
    vendor_binding = _validate_vendor_binding(payload.get("vendor_receipt_binding"), errors)
    database = _validate_written_database(payload.get("database"), errors)
    backup = _validate_backup(payload.get("backup"), errors)

    target_cells: list[dict[str, str]] = []
    try:
        raw_target_cells = payload.get("target_cells", [])
        if not isinstance(raw_target_cells, list):
            raise ValueError("receipt.target_cells must be a list")
        target_cells = _write_helpers._normalize_returned_cells(
            [
                {
                    "requested_trade_date": cell.get("trade_date") if isinstance(cell, Mapping) else None,
                    "stock_code": cell.get("stock_code") if isinstance(cell, Mapping) else None,
                    "trade_date": cell.get("trade_date") if isinstance(cell, Mapping) else None,
                    "adj_factor": 1.0,
                }
                for cell in raw_target_cells
            ],
            field_name="receipt.target_cells",
            require_non_empty=True,
        )
        normalized_keys = [{"stock_code": row["stock_code"], "trade_date": row["trade_date"]} for row in target_cells]
        if payload.get("target_cells") != normalized_keys:
            errors.append("receipt.target_cells must be canonical and sorted")
        target_cells = normalized_keys
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        target_cells = []
    target_cells_sha256 = _write_helpers._canonical_json_sha256(target_cells)
    _validate_sha(
        payload.get("target_cells_sha256"),
        target_cells_sha256,
        "receipt.target_cells_sha256",
        errors,
    )
    if payload.get("target_cell_count") != len(target_cells):
        errors.append("receipt.target_cell_count mismatch")
    if payload.get("existing_target_row_count") != 0:
        errors.append("receipt.existing_target_row_count must equal 0")
    if payload.get("inserted_row_count") != len(target_cells):
        errors.append("receipt.inserted_row_count mismatch")
    try:
        target_rows_sha256 = _write_helpers._sha256_text(
            payload.get("target_rows_sha256"), field_name="receipt.target_rows_sha256"
        )
        approval_scope_sha256 = _write_helpers._sha256_text(
            payload.get("approval_scope_sha256"),
            field_name="receipt.approval_scope_sha256",
        )
        source_version = _write_helpers._required_text(
            payload.get("source_version"), field_name="receipt.source_version"
        )
        run_id = _write_helpers._required_text(payload.get("run_id"), field_name="receipt.run_id")
    except ValueError as exc:
        errors.append(str(exc))
        target_rows_sha256 = approval_scope_sha256 = source_version = run_id = ""

    if page_binding and factor_binding and vendor_binding and database and backup:
        if len(target_cells) != factor_binding["target_cell_count"]:
            errors.append("receipt target/factor count mismatch")
        if target_cells_sha256 != factor_binding["target_cells_sha256"]:
            errors.append("receipt target/factor SHA mismatch")
        if len(target_cells) != vendor_binding["returned_cell_count"]:
            errors.append("receipt target/vendor count mismatch")
        if target_rows_sha256 != vendor_binding["returned_cells_sha256"]:
            errors.append("receipt target rows/vendor SHA mismatch")
        if source_version != vendor_binding["proposed_source_version"]:
            errors.append("receipt source_version/vendor mismatch")
        if run_id != vendor_binding["proposed_run_id"]:
            errors.append("receipt run_id/vendor mismatch")
        if approval_scope_sha256 != vendor_binding["factor_approval_scope_sha256"]:
            errors.append("receipt approval/vendor binding mismatch")
        expected_scope = vendor_task.factor_approval_scope_sha256(
            factor_manifest_file_sha256=factor_binding["file_sha256"],
            factor_manifest_canonical_sha256=factor_binding["canonical_manifest_sha256"],
            page_manifest_file_sha256=page_binding["file_sha256"],
            page_manifest_canonical_sha256=page_binding["canonical_manifest_sha256"],
            vendor_receipt_file_sha256=vendor_binding["file_sha256"],
            vendor_receipt_canonical_sha256=vendor_binding["canonical_receipt_sha256"],
            database_sha256_before=database["sha256_before"],
            returned_cells_sha256=target_rows_sha256,
            target_cell_count=len(target_cells),
            source_version=source_version,
            run_id=run_id,
        )
        if approval_scope_sha256 != expected_scope:
            errors.append("receipt.approval_scope_sha256 does not match bound evidence")
        if database["sha256_before"] != backup["sha256"]:
            errors.append("receipt backup must match database before SHA")
        for binding_name, binding in (
            ("page", page_binding),
            ("factor", factor_binding),
            ("vendor", vendor_binding),
        ):
            if binding["database_path"] != database["path"]:
                errors.append(f"receipt {binding_name}/database path mismatch")
            if binding["database_sha256"] != database["sha256_before"]:
                errors.append(f"receipt {binding_name}/database before SHA mismatch")

    if page_gap_factor_manifest is not None and vendor_receipt is not None:
        valid_manifest, manifest_errors = factor_manifest_task.validate_stock_analysis_page_gap_factor_manifest(
            page_gap_factor_manifest
        )
        if not valid_manifest:
            errors.append("external factor manifest invalid:" + ";".join(manifest_errors))
        valid_vendor, vendor_errors = vendor_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
            vendor_receipt,
            reviewed_factor_manifest=page_gap_factor_manifest,
        )
        if not valid_vendor:
            errors.append("external vendor receipt invalid:" + ";".join(vendor_errors))
        if factor_binding and factor_binding["canonical_manifest_sha256"] != page_gap_factor_manifest.get(
            "canonical_manifest_sha256"
        ):
            errors.append("receipt factor binding does not match external manifest")
        if vendor_binding and vendor_binding["canonical_receipt_sha256"] != vendor_receipt.get(
            "canonical_receipt_sha256"
        ):
            errors.append("receipt vendor binding does not match external receipt")
        if page_binding and page_binding != page_gap_factor_manifest.get("page_manifest_binding"):
            errors.append("receipt page binding does not match external factor manifest")

    try:
        expected_hash = _write_receipt_sha256(payload)
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("receipt payload must be canonical JSON")
    else:
        _validate_sha(
            payload.get("canonical_write_receipt_sha256"),
            expected_hash,
            "receipt.canonical_write_receipt_sha256",
            errors,
        )
    return not errors, tuple(_ordered(errors))


def _validated_factor_manifest_contract(
    manifest: Mapping[str, object],
    *,
    factor_manifest_path: Path,
    factor_manifest_file_sha256: str,
) -> dict[str, Any]:
    valid, errors = factor_manifest_task.validate_stock_analysis_page_gap_factor_manifest(manifest)
    if not valid:
        raise PageGapFactorWriteError("factor manifest failed formal validation: " + "; ".join(errors))
    if manifest.get("status") != "gaps_found" or manifest.get("blockers") != []:
        raise PageGapFactorWriteError("factor manifest must be unblocked gaps_found")
    for field_name, expected in (
        ("remediation_only", True),
        ("strict_exact_date_lookup", True),
        ("carry_forward_allowed", False),
        ("fallback_allowed", False),
        ("write_allowed", False),
        ("historical_availability_proven", False),
        ("certification_allowed", False),
        ("downstream_materialization_allowed", False),
    ):
        if manifest.get(field_name) is not expected:
            raise PageGapFactorWriteError(f"factor manifest {field_name} boundary mismatch")
    target_cells = _normalize_target_cells(manifest.get("target_cells"))
    target_sha = _write_helpers._canonical_json_sha256(target_cells)
    if manifest.get("target_cell_count") != len(target_cells):
        raise PageGapFactorWriteError("factor manifest target count mismatch")
    if manifest.get("target_cells_sha256") != target_sha:
        raise PageGapFactorWriteError("factor manifest target SHA mismatch")
    database = _write_helpers._mapping(manifest.get("database"), field_name="factor_manifest.database")
    database_path = _write_helpers._existing_file(
        _write_helpers._absolute_without_resolve(
            _write_helpers._required_text(database.get("path"), field_name="factor_manifest.database.path")
        ),
        field_name="factor_manifest.database.path",
    )
    before = _write_helpers._sha256_text(
        database.get("sha256_before"), field_name="factor_manifest.database.sha256_before"
    )
    after = _write_helpers._sha256_text(
        database.get("sha256_after"), field_name="factor_manifest.database.sha256_after"
    )
    if before != after or database.get("unchanged") is not True or database.get("read_only") is not True:
        raise PageGapFactorWriteError("factor manifest database must be unchanged/read-only")
    page_binding = _write_helpers._mapping(
        manifest.get("page_manifest_binding"), field_name="factor_manifest.page_manifest_binding"
    )
    return {
        "path": factor_manifest_path,
        "file_sha256": _write_helpers._sha256_text(
            factor_manifest_file_sha256, field_name="factor_manifest_file_sha256"
        ),
        "canonical_manifest_sha256": _write_helpers._sha256_text(
            manifest.get("canonical_manifest_sha256"),
            field_name="factor_manifest.canonical_manifest_sha256",
        ),
        "database_path": database_path,
        "database_sha256": before,
        "target_cells": target_cells,
        "target_cells_sha256": target_sha,
        "page_manifest_binding": page_binding,
    }


def _load_and_validate_external_page_manifest(
    *,
    trusted_root: Path,
    factor_manifest: Mapping[str, object],
    factor_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], Path, str]:
    binding = _write_helpers._mapping(factor_contract.get("page_manifest_binding"), field_name="page_manifest_binding")
    page_path = _write_helpers._existing_json_file_within_root(
        trusted_root=trusted_root,
        path=_write_helpers._required_text(binding.get("path"), field_name="page_manifest_binding.path"),
        field_name="page_manifest_binding.path",
    )
    page_file_sha = _write_helpers._file_sha256(page_path)
    if page_file_sha != binding.get("file_sha256"):
        raise PageGapFactorWriteError("external page manifest file SHA mismatch")
    page_manifest = _write_helpers._load_json_object(page_path, field_name="page_manifest_binding.path")
    valid, errors = page_manifest_task.validate_stock_analysis_page_gap_manifest(page_manifest)
    if not valid:
        raise PageGapFactorWriteError("external page manifest failed formal validation: " + "; ".join(errors))
    if page_manifest.get("status") != "gaps_found" or page_manifest.get("blockers") != []:
        raise PageGapFactorWriteError("external page manifest is not remediation eligible")
    summary = _write_helpers._mapping(page_manifest.get("summary"), field_name="page_manifest.summary")
    database = _write_helpers._mapping(page_manifest.get("database"), field_name="page_manifest.database")
    expected_binding = {
        "path": str(page_path),
        "file_sha256": page_file_sha,
        "canonical_manifest_sha256": page_manifest.get("canonical_manifest_sha256"),
        "manifest_kind": page_manifest.get("manifest_kind"),
        "page_id": page_manifest.get("page_id"),
        "page_route": page_manifest.get("page_route"),
        "page_metric_key": page_manifest.get("page_metric_key"),
        "database_path": database.get("path"),
        "database_sha256": database.get("sha256_before"),
        "page_gap_view_count": summary.get("page_gap_view_count_before"),
        "missing_factor_cell_count": summary.get("unique_missing_factor_cell_count"),
    }
    if binding != expected_binding:
        raise PageGapFactorWriteError("factor manifest page binding does not match external page manifest")
    raw_missing = page_manifest.get("missing_factor_cells")
    if not isinstance(raw_missing, list):
        raise PageGapFactorWriteError("external page manifest missing_factor_cells must be a list")
    page_cells = _normalize_target_cells(
        [
            {"stock_code": cell.get("stock_code"), "trade_date": cell.get("trade_date")}
            for cell in raw_missing
            if isinstance(cell, Mapping)
        ]
    )
    if page_cells != factor_contract["target_cells"]:
        raise PageGapFactorWriteError("factor target cells do not match external page manifest")
    if (
        database.get("sha256_before") != factor_contract["database_sha256"]
        or database.get("sha256_after") != factor_contract["database_sha256"]
    ):
        raise PageGapFactorWriteError("external page manifest database SHA mismatch")
    _ = factor_manifest
    return page_manifest, page_path, page_file_sha


def _validated_vendor_receipt_contract(
    receipt: Mapping[str, object],
    *,
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
    factor_manifest: Mapping[str, object],
    factor_manifest_path: Path,
    factor_manifest_file_sha256: str,
    factor_contract: Mapping[str, Any],
) -> dict[str, Any]:
    valid, errors = vendor_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
        receipt,
        reviewed_factor_manifest=factor_manifest,
        reviewed_factor_manifest_path=factor_manifest_path,
        reviewed_factor_manifest_file_sha256=factor_manifest_file_sha256,
    )
    if not valid:
        raise PageGapFactorWriteError("vendor receipt failed formal validation: " + "; ".join(errors))
    if receipt.get("status") != vendor_task.READY_STATUS:
        raise PageGapFactorWriteError("vendor receipt is not ready for approval")
    returned = _write_helpers._normalize_returned_cells(
        receipt.get("returned_cells"),
        field_name="vendor_receipt.returned_cells",
        require_non_empty=True,
    )
    returned_keys = [{"stock_code": row["stock_code"], "trade_date": row["trade_date"]} for row in returned]
    if returned_keys != factor_contract["target_cells"]:
        raise PageGapFactorWriteError("vendor returned cells do not match factor targets")
    database = _write_helpers._mapping(receipt.get("database"), field_name="vendor_receipt.database")
    if (
        database.get("sha256_before") != factor_contract["database_sha256"]
        or database.get("sha256_after") != factor_contract["database_sha256"]
    ):
        raise PageGapFactorWriteError("vendor receipt database SHA mismatch")
    return {
        "path": vendor_receipt_path,
        "file_sha256": _write_helpers._sha256_text(vendor_receipt_file_sha256, field_name="vendor_receipt_file_sha256"),
        "canonical_receipt_sha256": _write_helpers._sha256_text(
            receipt.get("canonical_receipt_sha256"),
            field_name="vendor_receipt.canonical_receipt_sha256",
        ),
        "database_path": factor_contract["database_path"],
        "database_sha256": factor_contract["database_sha256"],
        "returned_cells": returned,
        "returned_cells_sha256": _write_helpers._sha256_text(
            receipt.get("returned_cells_sha256"),
            field_name="vendor_receipt.returned_cells_sha256",
        ),
        "source_version": _write_helpers._required_text(
            receipt.get("proposed_source_version"), field_name="vendor_receipt.proposed_source_version"
        ),
        "run_id": _write_helpers._required_text(
            receipt.get("proposed_run_id"), field_name="vendor_receipt.proposed_run_id"
        ),
    }


def _build_pending_intent(
    **kwargs: Any,
) -> dict[str, Any]:
    target_rows = _write_helpers._normalize_returned_cells(
        kwargs["target_rows"], field_name="target_rows", require_non_empty=True
    )
    pending = _common_receipt_payload(
        receipt_kind=PENDING_INTENT_KIND,
        status=PENDING_STATUS,
        database_sha_after=None,
        database_write_executed=None,
        physical_factor_remediation_completed=None,
        completion_attested=False,
        target_rows=target_rows,
        **{key: value for key, value in kwargs.items() if key != "target_rows"},
    )
    pending["recovery_instruction"] = RECOVERY_INSTRUCTION
    pending["canonical_pending_intent_sha256"] = _pending_intent_sha256(pending)
    return pending


def _build_write_receipt(
    **kwargs: Any,
) -> dict[str, Any]:
    target_rows = _write_helpers._normalize_returned_cells(
        kwargs["target_rows"], field_name="target_rows", require_non_empty=True
    )
    receipt = _common_receipt_payload(
        receipt_kind=WRITE_RECEIPT_KIND,
        status=COMPLETED_STATUS,
        database_write_executed=True,
        physical_factor_remediation_completed=True,
        completion_attested=True,
        target_rows=target_rows,
        **{key: value for key, value in kwargs.items() if key != "target_rows"},
    )
    receipt.pop("target_rows", None)
    receipt["existing_target_row_count"] = 0
    receipt["inserted_row_count"] = len(target_rows)
    receipt["page_gap_closed"] = False
    receipt["rollback_instruction"] = ROLLBACK_INSTRUCTION
    receipt["canonical_write_receipt_sha256"] = _write_receipt_sha256(receipt)
    return receipt


def _common_receipt_payload(
    *,
    receipt_kind: str,
    status: str,
    executed_at: str,
    approval_reference: str,
    approval_scope_sha256: str,
    page_manifest: Mapping[str, object],
    page_manifest_path: Path,
    page_manifest_file_sha256: str,
    factor_manifest: Mapping[str, object],
    factor_manifest_path: Path,
    factor_manifest_file_sha256: str,
    vendor_receipt: Mapping[str, object],
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
    database_path: Path,
    database_sha_before: str,
    backup_path: Path,
    backup_sha256: str,
    target_rows: Sequence[Mapping[str, Any]],
    source_version: str,
    run_id: str,
    database_sha_after: str | None = None,
    database_write_executed: bool | None,
    physical_factor_remediation_completed: bool | None,
    completion_attested: bool,
) -> dict[str, Any]:
    normalized_rows = _write_helpers._normalize_returned_cells(
        target_rows, field_name="target_rows", require_non_empty=True
    )
    target_cells = [{"stock_code": row["stock_code"], "trade_date": row["trade_date"]} for row in normalized_rows]
    page_binding = dict(
        _write_helpers._mapping(factor_manifest.get("page_manifest_binding"), field_name="page_manifest_binding")
    )
    factor_database = _write_helpers._mapping(factor_manifest.get("database"), field_name="factor_manifest.database")
    vendor_database = _write_helpers._mapping(vendor_receipt.get("database"), field_name="vendor_receipt.database")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": receipt_kind,
        "status": status,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": approval_scope_sha256,
        "database_write_executed": database_write_executed,
        "physical_factor_remediation_completed": physical_factor_remediation_completed,
        "completion_attested": completion_attested,
        "additional_write_allowed": False,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "downstream_materialization_executed": False,
        "no_overwrite_or_delete_performed": True,
        "touched_tables": list(TOUCHED_TABLES),
        "page_manifest_binding": page_binding,
        "factor_manifest_binding": {
            "path": str(factor_manifest_path),
            "file_sha256": factor_manifest_file_sha256,
            "canonical_manifest_sha256": factor_manifest.get("canonical_manifest_sha256"),
            "manifest_kind": factor_manifest.get("manifest_kind"),
            "status": factor_manifest.get("status"),
            "target_cell_count": len(target_cells),
            "target_cells_sha256": _write_helpers._canonical_json_sha256(target_cells),
            "database_path": factor_database.get("path"),
            "database_sha256": factor_database.get("sha256_before"),
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
            "factor_approval_scope_sha256": approval_scope_sha256,
        },
        "database": {
            "path": str(database_path),
            "sha256_before": database_sha_before,
            "sha256_after": database_sha_after,
            "changed": (None if database_sha_after is None else database_sha_after != database_sha_before),
        },
        "backup": {
            "path": str(backup_path),
            "sha256": backup_sha256,
            "created_exclusive": True,
            "byte_identical_prewrite_target": True,
        },
        "target_cells": target_cells,
        "target_cell_count": len(target_cells),
        "target_cells_sha256": _write_helpers._canonical_json_sha256(target_cells),
        "target_rows": normalized_rows,
        "target_rows_sha256": _write_helpers._canonical_json_sha256(normalized_rows),
        "source_version": source_version,
        "run_id": run_id,
    }
    _ = page_manifest, page_manifest_path, page_manifest_file_sha256
    return payload


def _normalize_target_cells(value: object) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PageGapFactorWriteError("target_cells must be a list")
    rows = _write_helpers._normalize_returned_cells(
        [
            {
                "requested_trade_date": cell.get("trade_date") if isinstance(cell, Mapping) else None,
                "stock_code": cell.get("stock_code") if isinstance(cell, Mapping) else None,
                "trade_date": cell.get("trade_date") if isinstance(cell, Mapping) else None,
                "adj_factor": 1.0,
            }
            for cell in value
        ],
        field_name="target_cells",
        require_non_empty=True,
    )
    return [{"stock_code": row["stock_code"], "trade_date": row["trade_date"]} for row in rows]


def _assert_evidence_files_unchanged(
    *,
    page_manifest_path: Path,
    page_manifest_file_sha256: str,
    factor_manifest_path: Path,
    factor_manifest_file_sha256: str,
    vendor_receipt_path: Path,
    vendor_receipt_file_sha256: str,
) -> None:
    for field_name, path, expected_sha in (
        ("page manifest", page_manifest_path, page_manifest_file_sha256),
        ("factor manifest", factor_manifest_path, factor_manifest_file_sha256),
        ("vendor receipt", vendor_receipt_path, vendor_receipt_file_sha256),
    ):
        _write_helpers._assert_no_symlink_in_raw_path(path, field_name=field_name)
        if not path.is_file() or _write_helpers._file_sha256(path) != expected_sha:
            raise PageGapFactorWriteError(f"{field_name} changed during governed write")


def _capture_directory_identity(path: Path, *, field_name: str) -> FileIdentity:
    """Freeze a real directory identity without following a leaf link."""

    _write_helpers._assert_no_symlink_in_raw_path(path, field_name=field_name)
    if _write_helpers._is_forbidden_link_component(path):
        raise PageGapFactorWriteError(f"{field_name} must not be a symlink or junction")
    try:
        observed = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise PageGapFactorWriteError(f"{field_name} identity is unavailable") from exc
    if not stat.S_ISDIR(observed.st_mode):
        raise PageGapFactorWriteError(f"{field_name} must remain a directory")
    return (observed.st_dev, observed.st_ino)


def _assert_directory_identity(
    path: Path,
    *,
    expected_identity: FileIdentity,
    field_name: str,
) -> None:
    observed = _capture_directory_identity(path, field_name=field_name)
    if observed != expected_identity:
        raise PageGapFactorWriteError(f"{field_name} identity changed during governed write")


def _assert_leaf_identity(
    path: Path,
    *,
    expected_identity: FileIdentity,
    field_name: str,
) -> None:
    if _write_helpers._is_forbidden_link_component(path):
        raise PageGapFactorWriteError(f"{field_name} became a symlink or junction")
    try:
        observed = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise PageGapFactorWriteError(f"{field_name} identity is unavailable") from exc
    if not stat.S_ISREG(observed.st_mode):
        raise PageGapFactorWriteError(f"{field_name} must remain a regular file")
    if (observed.st_dev, observed.st_ino) != expected_identity:
        raise PageGapFactorWriteError(f"{field_name} identity changed during governed write")


def _safe_unlink_created_leaf(
    *,
    path: Path,
    expected_leaf_identity: FileIdentity | None,
    parent_identity: FileIdentity,
) -> bool:
    """Remove only the exact leaf created by this invocation."""

    if expected_leaf_identity is None:
        return False
    try:
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name=f"{path.name}.parent",
        )
        _assert_leaf_identity(
            path,
            expected_identity=expected_leaf_identity,
            field_name=path.name,
        )
        path.unlink()
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name=f"{path.name}.parent",
        )
    except (OSError, ValueError):
        return False
    return True


def _create_prewrite_backup_hardened(
    *,
    target: Path,
    backup_path: Path,
    backup_parent_identity: FileIdentity,
) -> tuple[str, FileIdentity]:
    """Create a byte-identical backup bound to its validated parent and leaf."""

    _assert_directory_identity(
        backup_path.parent,
        expected_identity=backup_parent_identity,
        field_name="target_backup_file.parent",
    )
    if os.path.lexists(backup_path):
        raise PageGapFactorWriteError("target_backup_file must be new")
    _assert_directory_identity(
        backup_path.parent,
        expected_identity=backup_parent_identity,
        field_name="target_backup_file.parent",
    )
    created_identity: FileIdentity | None = None
    try:
        with target.open("rb") as source, backup_path.open("xb") as destination:
            source_identity = _identity_from_fstat(source.fileno())
            _assert_leaf_identity(
                target,
                expected_identity=source_identity,
                field_name="duckdb_path backup source",
            )
            created_identity = _identity_from_fstat(destination.fileno())
            _assert_directory_identity(
                backup_path.parent,
                expected_identity=backup_parent_identity,
                field_name="target_backup_file.parent",
            )
            _assert_leaf_identity(
                backup_path,
                expected_identity=created_identity,
                field_name="target_backup_file",
            )
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        _assert_directory_identity(
            backup_path.parent,
            expected_identity=backup_parent_identity,
            field_name="target_backup_file.parent",
        )
        _assert_leaf_identity(
            backup_path,
            expected_identity=created_identity,
            field_name="target_backup_file",
        )
        backup_sha256 = _write_helpers._file_sha256(backup_path)
        target_sha256 = _write_helpers._file_sha256(target)
        _assert_leaf_identity(
            backup_path,
            expected_identity=created_identity,
            field_name="target_backup_file",
        )
        if backup_sha256 != target_sha256:
            raise PageGapFactorWriteError("backup must be byte-identical to the pre-write target database")
        return backup_sha256, created_identity
    except Exception:
        _safe_unlink_created_leaf(
            path=backup_path,
            expected_leaf_identity=created_identity,
            parent_identity=backup_parent_identity,
        )
        raise


def _write_json_exclusive_hardened(
    *,
    path: Path,
    payload: Mapping[str, Any],
    trusted_root: Path,
    trusted_root_identity: FileIdentity,
    parent_identity: FileIdentity,
) -> FileIdentity:
    """Create a JSON leaf exclusively and bind its opened file identity."""

    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    _assert_directory_identity(
        path.parent,
        expected_identity=parent_identity,
        field_name="write_receipt_file.parent",
    )
    if os.path.lexists(path):
        raise PageGapFactorWriteError("write_receipt_file must be new")
    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    _assert_directory_identity(
        path.parent,
        expected_identity=parent_identity,
        field_name="write_receipt_file.parent",
    )
    created_identity: FileIdentity | None = None
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            created_identity = _identity_from_fstat(handle.fileno())
            _assert_directory_identity(
                trusted_root,
                expected_identity=trusted_root_identity,
                field_name="trusted_evidence_root",
            )
            _assert_directory_identity(
                path.parent,
                expected_identity=parent_identity,
                field_name="write_receipt_file.parent",
            )
            _assert_leaf_identity(
                path,
                expected_identity=created_identity,
                field_name="write_receipt_file pending intent",
            )
            handle.write(_write_helpers._encoded_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        _assert_directory_identity(
            trusted_root,
            expected_identity=trusted_root_identity,
            field_name="trusted_evidence_root",
        )
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name="write_receipt_file.parent",
        )
        _assert_leaf_identity(
            path,
            expected_identity=created_identity,
            field_name="write_receipt_file pending intent",
        )
        return created_identity
    except Exception:
        _safe_unlink_created_leaf(
            path=path,
            expected_leaf_identity=created_identity,
            parent_identity=parent_identity,
        )
        raise


def _replace_json_atomically_hardened(
    *,
    path: Path,
    payload: Mapping[str, Any],
    expected_existing: Mapping[str, Any],
    expected_pending_identity: FileIdentity,
    trusted_root: Path,
    trusted_root_identity: FileIdentity,
    parent_identity: FileIdentity,
) -> FileIdentity:
    """Replace only the exact pending leaf inside the frozen receipt parent."""

    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    _assert_directory_identity(
        path.parent,
        expected_identity=parent_identity,
        field_name="write_receipt_file.parent",
    )
    _assert_leaf_identity(
        path,
        expected_identity=expected_pending_identity,
        field_name="write_receipt_file pending intent",
    )
    persisted_pending = _write_helpers._load_json_object(
        path,
        field_name="write_receipt_file pending intent",
    )
    _assert_leaf_identity(
        path,
        expected_identity=expected_pending_identity,
        field_name="write_receipt_file pending intent",
    )
    if persisted_pending != dict(expected_existing):
        raise PageGapFactorWriteError("write_receipt_file pending intent changed before finalization")

    _assert_directory_identity(
        trusted_root,
        expected_identity=trusted_root_identity,
        field_name="trusted_evidence_root",
    )
    _assert_directory_identity(
        path.parent,
        expected_identity=parent_identity,
        field_name="write_receipt_file.parent",
    )
    _assert_leaf_identity(
        path,
        expected_identity=expected_pending_identity,
        field_name="write_receipt_file pending intent",
    )
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".completed.tmp",
        dir=path.parent,
        text=True,
    )
    temp_path = Path(raw_temp_path)
    temp_identity: FileIdentity | None = None
    descriptor_open = True
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor_open = False
            temp_identity = _identity_from_fstat(handle.fileno())
            _assert_directory_identity(
                trusted_root,
                expected_identity=trusted_root_identity,
                field_name="trusted_evidence_root",
            )
            _assert_directory_identity(
                path.parent,
                expected_identity=parent_identity,
                field_name="write_receipt_file.parent",
            )
            _assert_leaf_identity(
                temp_path,
                expected_identity=temp_identity,
                field_name="completed write receipt temporary file",
            )
            handle.write(_write_helpers._encoded_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        _assert_directory_identity(
            trusted_root,
            expected_identity=trusted_root_identity,
            field_name="trusted_evidence_root",
        )
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name="write_receipt_file.parent",
        )
        _assert_leaf_identity(
            path,
            expected_identity=expected_pending_identity,
            field_name="write_receipt_file pending intent",
        )
        _assert_leaf_identity(
            temp_path,
            expected_identity=temp_identity,
            field_name="completed write receipt temporary file",
        )
        persisted_temp = _write_helpers._load_json_object(
            temp_path,
            field_name="completed write receipt temporary file",
        )
        _assert_leaf_identity(
            temp_path,
            expected_identity=temp_identity,
            field_name="completed write receipt temporary file",
        )
        if persisted_temp != dict(payload):
            raise PageGapFactorWriteError("completed write receipt temporary file does not match generated receipt")
        _assert_leaf_identity(
            path,
            expected_identity=expected_pending_identity,
            field_name="write_receipt_file pending intent",
        )
        _assert_directory_identity(
            trusted_root,
            expected_identity=trusted_root_identity,
            field_name="trusted_evidence_root",
        )
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name="write_receipt_file.parent",
        )
        _assert_leaf_identity(
            temp_path,
            expected_identity=temp_identity,
            field_name="completed write receipt temporary file",
        )
        os.replace(temp_path, path)
        replaced = True
        _assert_directory_identity(
            trusted_root,
            expected_identity=trusted_root_identity,
            field_name="trusted_evidence_root",
        )
        _assert_directory_identity(
            path.parent,
            expected_identity=parent_identity,
            field_name="write_receipt_file.parent",
        )
        _assert_leaf_identity(
            path,
            expected_identity=temp_identity,
            field_name="write_receipt_file final receipt",
        )
        return temp_identity
    finally:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not replaced:
            _safe_unlink_created_leaf(
                path=temp_path,
                expected_leaf_identity=temp_identity,
                parent_identity=parent_identity,
            )


def _identity_from_fstat(file_descriptor: int) -> FileIdentity:
    observed = os.fstat(file_descriptor)
    return (observed.st_dev, observed.st_ino)


def _validate_page_binding(value: object, errors: list[str]) -> dict[str, Any] | None:
    return _validate_exact_binding(
        value,
        fields=(
            "path",
            "file_sha256",
            "canonical_manifest_sha256",
            "manifest_kind",
            "page_id",
            "page_route",
            "page_metric_key",
            "database_path",
            "database_sha256",
            "page_gap_view_count",
            "missing_factor_cell_count",
        ),
        hash_fields=("file_sha256", "canonical_manifest_sha256", "database_sha256"),
        path_fields=("path", "database_path"),
        field_name="receipt.page_manifest_binding",
        errors=errors,
    )


def _validate_factor_binding(value: object, errors: list[str]) -> dict[str, Any] | None:
    return _validate_exact_binding(
        value,
        fields=(
            "path",
            "file_sha256",
            "canonical_manifest_sha256",
            "manifest_kind",
            "status",
            "target_cell_count",
            "target_cells_sha256",
            "database_path",
            "database_sha256",
        ),
        hash_fields=(
            "file_sha256",
            "canonical_manifest_sha256",
            "target_cells_sha256",
            "database_sha256",
        ),
        path_fields=("path", "database_path"),
        field_name="receipt.factor_manifest_binding",
        errors=errors,
    )


def _validate_vendor_binding(value: object, errors: list[str]) -> dict[str, Any] | None:
    return _validate_exact_binding(
        value,
        fields=(
            "path",
            "file_sha256",
            "canonical_receipt_sha256",
            "receipt_kind",
            "status",
            "database_path",
            "database_sha256",
            "returned_cells_sha256",
            "proposed_source_version",
            "proposed_run_id",
            "returned_cell_count",
            "factor_approval_scope_sha256",
        ),
        hash_fields=(
            "file_sha256",
            "canonical_receipt_sha256",
            "database_sha256",
            "returned_cells_sha256",
            "factor_approval_scope_sha256",
        ),
        path_fields=("path", "database_path"),
        field_name="receipt.vendor_receipt_binding",
        errors=errors,
    )


def _validate_exact_binding(
    value: object,
    *,
    fields: Sequence[str],
    hash_fields: Sequence[str],
    path_fields: Sequence[str],
    field_name: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field_name} must be a mapping")
        return None
    binding = dict(value)
    if set(binding) != set(fields):
        errors.append(f"{field_name} fields mismatch")
    for name in hash_fields:
        try:
            _write_helpers._sha256_text(binding.get(name), field_name=f"{field_name}.{name}")
        except ValueError as exc:
            errors.append(str(exc))
    for name in path_fields:
        try:
            binding[name] = str(
                _write_helpers._absolute_without_resolve(
                    _write_helpers._required_text(binding.get(name), field_name=f"{field_name}.{name}")
                )
            )
        except ValueError as exc:
            errors.append(str(exc))
    return binding


def _validate_written_database(value: object, errors: list[str]) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.database must be a mapping")
        return None
    try:
        path = str(
            _write_helpers._absolute_without_resolve(
                _write_helpers._required_text(value.get("path"), field_name="receipt.database.path")
            )
        )
        before = _write_helpers._sha256_text(value.get("sha256_before"), field_name="receipt.database.sha256_before")
        after = _write_helpers._sha256_text(value.get("sha256_after"), field_name="receipt.database.sha256_after")
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if before == after or value.get("changed") is not True:
        errors.append("receipt.database must attest a changed SHA")
    if set(value) != {"path", "sha256_before", "sha256_after", "changed"}:
        errors.append("receipt.database fields mismatch")
    return {"path": path, "sha256_before": before, "sha256_after": after}


def _validate_backup(value: object, errors: list[str]) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.backup must be a mapping")
        return None
    try:
        path = str(
            _write_helpers._absolute_without_resolve(
                _write_helpers._required_text(value.get("path"), field_name="receipt.backup.path")
            )
        )
        sha = _write_helpers._sha256_text(value.get("sha256"), field_name="receipt.backup.sha256")
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("created_exclusive") is not True or value.get("byte_identical_prewrite_target") is not True:
        errors.append("receipt.backup attestations mismatch")
    if set(value) != {"path", "sha256", "created_exclusive", "byte_identical_prewrite_target"}:
        errors.append("receipt.backup fields mismatch")
    return {"path": path, "sha256": sha}


def _validate_sha(value: object, expected: str, field_name: str, errors: list[str]) -> None:
    try:
        observed = _write_helpers._sha256_text(value, field_name=field_name)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if observed != expected:
        errors.append(f"{field_name} mismatch")


def _write_receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_write_receipt_sha256", None)
    return _write_helpers._canonical_json_sha256(payload)


def _pending_intent_sha256(intent: Mapping[str, object]) -> str:
    payload = dict(intent)
    payload.pop("canonical_pending_intent_sha256", None)
    return _write_helpers._canonical_json_sha256(payload)


def _ordered(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
