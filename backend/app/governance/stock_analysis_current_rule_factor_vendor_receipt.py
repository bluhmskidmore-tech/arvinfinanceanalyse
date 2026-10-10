"""Governed receipt for an exact-cell adjustment-factor vendor dry run.

The builder consumes a formally valid current-rule factor manifest and the
already-normalized rows returned by the vendor.  It does not call the vendor,
write DuckDB, or authorize a later write.  The resulting receipt is a
remediation proposal that a separate, explicitly approved writer can re-check.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, SupportsFloat, SupportsIndex

from backend.app.tasks.stock_analysis_current_rule_factor_manifest import (
    MANIFEST_KIND,
    validate_stock_analysis_current_rule_factor_manifest,
)

SCHEMA_VERSION = 1
RECEIPT_KIND = "stock_analysis_current_rule_factor_vendor_dry_run_v1"
READY_STATUS = "ready_for_write_approval"

VENDOR_ENDPOINT = "tushare.pro.adj_factor"
VENDOR_VERSION_STATUS = "not_provided"
REQUESTED_CELLS_SOURCE = "reviewed_factor_manifest.missing_unique_cells"
AVAILABILITY_SEMANTICS = "capture_time_only_no_historical_availability_inference"
PROPOSED_SOURCE_VERSION_PREFIX = "stock-adjustment-factor:tushare.pro.adj_factor:v1:"
PROPOSED_RUN_ID_PREFIX = "stock-analysis-current-rule-factor-remediation:v1:"


def build_stock_analysis_current_rule_factor_vendor_receipt(
    *,
    reviewed_factor_manifest: Mapping[str, object],
    reviewed_factor_manifest_path: str | Path,
    reviewed_factor_manifest_file_sha256: str,
    returned_cells: Sequence[Mapping[str, object]],
    captured_at: str,
    database_sha256_before: str,
    database_sha256_after: str,
) -> dict[str, Any]:
    """Build a fail-closed dry-run receipt for the manifest's exact gaps.

    ``returned_cells`` is expected to be normalized by the thin vendor caller.
    Every row must contain ``requested_trade_date``, ``stock_code``,
    ``trade_date`` and ``adj_factor``.  Any missing, extra, duplicate, invalid,
    or wrong-date row prevents receipt construction.
    """

    manifest_contract = _validated_manifest_contract(reviewed_factor_manifest)
    requested_cells = manifest_contract["requested_cells"]
    normalized_returned = _normalize_returned_cells(
        returned_cells,
        field_name="returned_cells",
        require_non_empty=True,
    )
    _require_exact_returned_set(
        requested_cells=requested_cells,
        returned_cells=normalized_returned,
    )

    normalized_captured_at = _utc_datetime_text(
        captured_at,
        field_name="captured_at",
    )
    normalized_manifest_path = _resolved_path_text(
        reviewed_factor_manifest_path,
        field_name="reviewed_factor_manifest_path",
    )
    manifest_file_sha256 = _sha256_text(
        reviewed_factor_manifest_file_sha256,
        field_name="reviewed_factor_manifest_file_sha256",
    )
    database_before = _sha256_text(
        database_sha256_before,
        field_name="database_sha256_before",
    )
    database_after = _sha256_text(
        database_sha256_after,
        field_name="database_sha256_after",
    )
    if database_before != database_after:
        raise ValueError("database SHA changed during vendor dry run")
    if database_before != manifest_contract["database_sha256"]:
        raise ValueError("vendor dry-run database SHA does not match reviewed manifest")

    requested_cells_sha256 = _canonical_json_sha256(requested_cells)
    returned_cells_sha256 = _canonical_json_sha256(normalized_returned)
    proposed_source_version = _proposed_source_version(
        requested_cells_sha256=requested_cells_sha256,
        returned_cells_sha256=returned_cells_sha256,
    )
    proposed_run_id = _proposed_run_id(
        manifest_sha256=manifest_contract["canonical_manifest_sha256"],
        requested_cells_sha256=requested_cells_sha256,
        returned_cells_sha256=returned_cells_sha256,
        captured_at=normalized_captured_at,
        database_sha256=database_before,
    )
    requested_dates = sorted({cell["trade_date"] for cell in requested_cells})

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "status": READY_STATUS,
        "captured_at": normalized_captured_at,
        "manifest_binding": {
            "path": normalized_manifest_path,
            "file_sha256": manifest_file_sha256,
            "canonical_manifest_sha256": manifest_contract["canonical_manifest_sha256"],
            "manifest_kind": MANIFEST_KIND,
            "governed_run_id": manifest_contract["governed_run_id"],
            "missing_unique_cell_count": len(requested_cells),
            "database_path": manifest_contract["database_path"],
            "database_sha256": manifest_contract["database_sha256"],
        },
        "requested_cells_source": REQUESTED_CELLS_SOURCE,
        "vendor_endpoint": VENDOR_ENDPOINT,
        "vendor_version": None,
        "vendor_version_status": VENDOR_VERSION_STATUS,
        "availability_attestation": {
            "semantics": AVAILABILITY_SEMANTICS,
            "captured_at": normalized_captured_at,
            "historical_availability_inferred": False,
        },
        "strict_exact_cells": True,
        "exact_set_match": True,
        "remediation_only": True,
        "database_write_executed": False,
        "write_allowed": False,
        "formal_use_allowed": False,
        "requested_cells": requested_cells,
        "returned_cells": normalized_returned,
        "requested_cell_count": len(requested_cells),
        "returned_cell_count": len(normalized_returned),
        "requested_unique_date_count": len(requested_dates),
        "vendor_call_count": len(requested_dates),
        "missing_cell_count": 0,
        "extra_cell_count": 0,
        "duplicate_cell_count": 0,
        "invalid_cell_count": 0,
        "wrong_date_cell_count": 0,
        "requested_cells_sha256": requested_cells_sha256,
        "returned_cells_sha256": returned_cells_sha256,
        "database": {
            "path": manifest_contract["database_path"],
            "sha256_before": database_before,
            "sha256_after": database_after,
            "unchanged": True,
            "read_only": True,
        },
        "proposed_source_version": proposed_source_version,
        "proposed_run_id": proposed_run_id,
    }
    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)

    valid, errors = validate_stock_analysis_current_rule_factor_vendor_receipt(
        receipt,
        reviewed_factor_manifest=reviewed_factor_manifest,
        reviewed_factor_manifest_path=normalized_manifest_path,
        reviewed_factor_manifest_file_sha256=manifest_file_sha256,
    )
    if not valid:  # pragma: no cover - internal construction invariant
        raise RuntimeError("constructed factor vendor receipt is invalid: " + "; ".join(errors))
    return receipt


def validate_stock_analysis_current_rule_factor_vendor_receipt(
    receipt: Mapping[str, object],
    *,
    reviewed_factor_manifest: Mapping[str, object] | None = None,
    reviewed_factor_manifest_path: str | Path | None = None,
    reviewed_factor_manifest_file_sha256: str | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate receipt internals and, when supplied, its external manifest binding."""

    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    errors: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"receipt.schema_version must equal {SCHEMA_VERSION}")
    if payload.get("receipt_kind") != RECEIPT_KIND:
        errors.append(f"receipt.receipt_kind must equal {RECEIPT_KIND}")
    if payload.get("status") != READY_STATUS:
        errors.append(f"receipt.status must equal {READY_STATUS}")

    captured_at: str | None = None
    try:
        captured_at = _utc_datetime_text(
            payload.get("captured_at"),
            field_name="receipt.captured_at",
        )
        if payload.get("captured_at") != captured_at:
            errors.append("receipt.captured_at must be canonical UTC text")
    except ValueError as exc:
        errors.append(str(exc))

    for field_name, expected in (
        ("strict_exact_cells", True),
        ("exact_set_match", True),
        ("remediation_only", True),
        ("database_write_executed", False),
        ("write_allowed", False),
        ("formal_use_allowed", False),
    ):
        if payload.get(field_name) is not expected:
            errors.append(f"receipt.{field_name} must be {str(expected).lower()}")
    for field_name in (
        "missing_cell_count",
        "extra_cell_count",
        "duplicate_cell_count",
        "invalid_cell_count",
        "wrong_date_cell_count",
    ):
        if payload.get(field_name) != 0:
            errors.append(f"receipt.{field_name} must equal 0")

    if payload.get("requested_cells_source") != REQUESTED_CELLS_SOURCE:
        errors.append("receipt.requested_cells_source mismatch")
    if payload.get("vendor_endpoint") != VENDOR_ENDPOINT:
        errors.append("receipt.vendor_endpoint mismatch")
    if payload.get("vendor_version") is not None:
        errors.append("receipt.vendor_version must be null")
    if payload.get("vendor_version_status") != VENDOR_VERSION_STATUS:
        errors.append("receipt.vendor_version_status must equal not_provided")

    attestation = payload.get("availability_attestation")
    if not isinstance(attestation, Mapping):
        errors.append("receipt.availability_attestation must be a mapping")
    else:
        if attestation.get("semantics") != AVAILABILITY_SEMANTICS:
            errors.append("receipt availability semantics mismatch")
        if attestation.get("historical_availability_inferred") is not False:
            errors.append("receipt.availability_attestation.historical_availability_inferred must be false")
        if captured_at is not None and attestation.get("captured_at") != captured_at:
            errors.append("receipt availability capture time mismatch")

    requested_cells: list[dict[str, str]] = []
    raw_requested = payload.get("requested_cells")
    try:
        requested_cells = _normalize_requested_cells(
            raw_requested,
            field_name="receipt.requested_cells",
            require_non_empty=True,
        )
        if raw_requested != requested_cells:
            errors.append("receipt.requested_cells must be canonical and stably sorted")
    except ValueError as exc:
        errors.append(str(exc))

    returned_cells: list[dict[str, Any]] = []
    raw_returned = payload.get("returned_cells")
    try:
        returned_cells = _normalize_returned_cells(
            raw_returned,
            field_name="receipt.returned_cells",
            require_non_empty=True,
        )
        if raw_returned != returned_cells:
            errors.append("receipt.returned_cells must be canonical and stably sorted")
    except ValueError as exc:
        errors.append(str(exc))

    requested_keys = _cell_keys(requested_cells)
    returned_keys = _cell_keys(returned_cells)
    if requested_cells and returned_cells and requested_keys != returned_keys:
        errors.append("receipt returned cells do not exactly match requested cells")

    expected_requested_count = len(requested_cells)
    expected_returned_count = len(returned_cells)
    expected_unique_date_count = len({cell["trade_date"] for cell in requested_cells})
    if not _exact_int(payload.get("requested_cell_count"), expected_requested_count):
        errors.append("receipt.requested_cell_count mismatch")
    if not _exact_int(payload.get("returned_cell_count"), expected_returned_count):
        errors.append("receipt.returned_cell_count mismatch")
    if not _exact_int(payload.get("requested_unique_date_count"), expected_unique_date_count):
        errors.append("receipt.requested_unique_date_count mismatch")
    if not _exact_int(payload.get("vendor_call_count"), expected_unique_date_count):
        errors.append("receipt.vendor_call_count mismatch")

    expected_requested_sha = _canonical_json_sha256(requested_cells)
    expected_returned_sha = _canonical_json_sha256(returned_cells)
    _validate_hash_equality(
        payload.get("requested_cells_sha256"),
        expected=expected_requested_sha,
        field_name="receipt.requested_cells_sha256",
        errors=errors,
    )
    _validate_hash_equality(
        payload.get("returned_cells_sha256"),
        expected=expected_returned_sha,
        field_name="receipt.returned_cells_sha256",
        errors=errors,
    )

    binding = payload.get("manifest_binding")
    normalized_binding = _validate_manifest_binding(binding, errors=errors)
    database = payload.get("database")
    normalized_database = _validate_database(database, errors=errors)
    if normalized_binding is not None and normalized_database is not None:
        if normalized_binding["database_path"] != normalized_database["path"]:
            errors.append("receipt manifest/database path binding mismatch")
        if normalized_binding["database_sha256"] != normalized_database["sha256_before"]:
            errors.append("receipt manifest/database SHA binding mismatch")
        if normalized_binding["missing_unique_cell_count"] != len(requested_cells):
            errors.append("receipt manifest missing-cell count binding mismatch")

    expected_source_version = _proposed_source_version(
        requested_cells_sha256=expected_requested_sha,
        returned_cells_sha256=expected_returned_sha,
    )
    if payload.get("proposed_source_version") != expected_source_version:
        errors.append("receipt.proposed_source_version mismatch")

    if normalized_binding is not None and normalized_database is not None and captured_at:
        expected_run_id = _proposed_run_id(
            manifest_sha256=normalized_binding["canonical_manifest_sha256"],
            requested_cells_sha256=expected_requested_sha,
            returned_cells_sha256=expected_returned_sha,
            captured_at=captured_at,
            database_sha256=normalized_database["sha256_before"],
        )
        if payload.get("proposed_run_id") != expected_run_id:
            errors.append("receipt.proposed_run_id mismatch")
    elif not _optional_text(payload.get("proposed_run_id")):
        errors.append("receipt.proposed_run_id must be non-empty")

    if reviewed_factor_manifest is not None:
        try:
            external_contract = _validated_manifest_contract(reviewed_factor_manifest)
        except ValueError as exc:
            errors.append(f"reviewed_factor_manifest invalid: {exc}")
        else:
            if requested_cells != external_contract["requested_cells"]:
                errors.append("receipt.requested_cells do not match reviewed manifest missing_unique_cells")
            if normalized_binding is not None:
                for field_name in (
                    "canonical_manifest_sha256",
                    "governed_run_id",
                    "database_path",
                    "database_sha256",
                ):
                    if normalized_binding[field_name] != external_contract[field_name]:
                        errors.append(f"receipt.manifest_binding.{field_name} does not match reviewed manifest")
                if normalized_binding["missing_unique_cell_count"] != len(external_contract["requested_cells"]):
                    errors.append("receipt.manifest_binding.missing_unique_cell_count does not match reviewed manifest")
    if reviewed_factor_manifest_path is not None and normalized_binding is not None:
        try:
            expected_manifest_path = _resolved_path_text(
                reviewed_factor_manifest_path,
                field_name="reviewed_factor_manifest_path",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if normalized_binding["path"] != expected_manifest_path:
                errors.append("receipt.manifest_binding.path does not match reviewed manifest path")
    if reviewed_factor_manifest_file_sha256 is not None and normalized_binding is not None:
        try:
            expected_manifest_file_sha256 = _sha256_text(
                reviewed_factor_manifest_file_sha256,
                field_name="reviewed_factor_manifest_file_sha256",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if normalized_binding["file_sha256"] != expected_manifest_file_sha256:
                errors.append("receipt.manifest_binding.file_sha256 does not match reviewed manifest file")

    observed_hash = payload.get("canonical_receipt_sha256")
    try:
        expected_receipt_sha256 = _receipt_sha256(payload)
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("receipt payload must be canonical JSON without non-finite values")
    else:
        _validate_hash_equality(
            observed_hash,
            expected=expected_receipt_sha256,
            field_name="receipt.canonical_receipt_sha256",
            errors=errors,
        )
    return not errors, tuple(_ordered(errors))


def _validated_manifest_contract(
    manifest: Mapping[str, object],
) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise ValueError("reviewed_factor_manifest must be a mapping")
    valid, validation_errors = validate_stock_analysis_current_rule_factor_manifest(manifest)
    if not valid:
        detail = "; ".join(validation_errors) or "unknown validation error"
        raise ValueError("reviewed_factor_manifest failed formal validation: " + detail)
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        raise ValueError("reviewed_factor_manifest kind mismatch")
    if manifest.get("status") != "gaps_found":
        raise ValueError("reviewed_factor_manifest status must be gaps_found")
    for field_name, expected in (
        ("strict_exact_date_lookup", True),
        ("carry_forward_allowed", False),
        ("fallback_allowed", False),
        ("remediation_only", True),
        ("certification_allowed", False),
    ):
        if manifest.get(field_name) is not expected:
            raise ValueError(f"reviewed_factor_manifest.{field_name} must be {str(expected).lower()}")

    requested_cells = _requested_cells_from_manifest(manifest)
    if not requested_cells:
        raise ValueError("reviewed_factor_manifest.missing_unique_cells must not be empty")
    database = manifest.get("database")
    if not isinstance(database, Mapping):  # also guarded by formal validator
        raise ValueError("reviewed_factor_manifest.database must be a mapping")
    database_before = _sha256_text(
        database.get("sha256_before"),
        field_name="reviewed_factor_manifest.database.sha256_before",
    )
    database_after = _sha256_text(
        database.get("sha256_after"),
        field_name="reviewed_factor_manifest.database.sha256_after",
    )
    if database_before != database_after:
        raise ValueError("reviewed_factor_manifest database hashes differ")
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        raise ValueError("reviewed_factor_manifest database must be unchanged and read-only")
    database_path = _required_text(
        database.get("path"),
        field_name="reviewed_factor_manifest.database.path",
    )
    return {
        "requested_cells": requested_cells,
        "canonical_manifest_sha256": _sha256_text(
            manifest.get("canonical_manifest_sha256"),
            field_name="reviewed_factor_manifest.canonical_manifest_sha256",
        ),
        "governed_run_id": _required_text(
            manifest.get("governed_run_id"),
            field_name="reviewed_factor_manifest.governed_run_id",
        ),
        "database_path": database_path,
        "database_sha256": database_before,
    }


def _requested_cells_from_manifest(
    manifest: Mapping[str, object],
) -> list[dict[str, str]]:
    raw_missing = manifest.get("missing_unique_cells")
    if not isinstance(raw_missing, Sequence) or isinstance(raw_missing, (str, bytes, bytearray)):
        raise ValueError("reviewed_factor_manifest.missing_unique_cells must be a list")
    cells: list[dict[str, object]] = []
    for index, raw_cell in enumerate(raw_missing):
        if not isinstance(raw_cell, Mapping):
            raise ValueError(f"reviewed_factor_manifest.missing_unique_cells[{index}] must be a mapping")
        cells.append(
            {
                "stock_code": raw_cell.get("stock_code"),
                "trade_date": raw_cell.get("trade_date"),
            }
        )
    return _normalize_requested_cells(
        cells,
        field_name="reviewed_factor_manifest.missing_unique_cells",
        require_non_empty=True,
    )


def _normalize_requested_cells(
    value: object,
    *,
    field_name: str,
    require_non_empty: bool,
) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a list")
    if require_non_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(value):
        if not isinstance(raw_cell, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping")
        stock_code = _stock_code(
            raw_cell.get("stock_code"),
            field_name=f"{field_name}[{index}].stock_code",
        )
        trade_date = _iso_date_text(
            raw_cell.get("trade_date"),
            field_name=f"{field_name}[{index}].trade_date",
        )
        key = (stock_code, trade_date)
        if key in seen:
            raise ValueError(f"{field_name} contains duplicate natural keys")
        seen.add(key)
        normalized.append({"stock_code": stock_code, "trade_date": trade_date})
    return sorted(
        normalized,
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )


def _normalize_returned_cells(
    value: object,
    *,
    field_name: str,
    require_non_empty: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a list")
    if require_non_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(value):
        if not isinstance(raw_cell, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping")
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
            raise ValueError(f"{field_name}[{index}] returned trade_date must equal requested_trade_date")
        factor = _positive_finite_float(
            raw_cell.get("adj_factor"),
            field_name=f"{field_name}[{index}].adj_factor",
        )
        key = (stock_code, trade_date)
        if key in seen:
            raise ValueError(f"{field_name} contains duplicate natural keys")
        seen.add(key)
        normalized.append(
            {
                "requested_trade_date": requested_trade_date,
                "stock_code": stock_code,
                "trade_date": trade_date,
                "adj_factor": factor,
            }
        )
    return sorted(
        normalized,
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )


def _require_exact_returned_set(
    *,
    requested_cells: Sequence[Mapping[str, object]],
    returned_cells: Sequence[Mapping[str, object]],
) -> None:
    requested = _cell_keys(requested_cells)
    returned = _cell_keys(returned_cells)
    if requested == returned:
        return
    missing = sorted(requested.difference(returned))
    extra = sorted(returned.difference(requested))
    missing_preview = ",".join(f"{code}@{day}" for code, day in missing[:5])
    extra_preview = ",".join(f"{code}@{day}" for code, day in extra[:5])
    raise ValueError(
        "returned_cells must exactly equal reviewed manifest missing_unique_cells; "
        f"missing={len(missing)}[{missing_preview}]; "
        f"extra={len(extra)}[{extra_preview}]"
    )


def _cell_keys(
    cells: Sequence[Mapping[str, object]],
) -> set[tuple[str, str]]:
    return {(str(cell.get("stock_code")), str(cell.get("trade_date"))) for cell in cells}


def _validate_manifest_binding(
    value: object,
    *,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.manifest_binding must be a mapping")
        return None
    try:
        path = _required_text(
            value.get("path"),
            field_name="receipt.manifest_binding.path",
        )
        file_sha256 = _sha256_text(
            value.get("file_sha256"),
            field_name="receipt.manifest_binding.file_sha256",
        )
        canonical_manifest_sha256 = _sha256_text(
            value.get("canonical_manifest_sha256"),
            field_name="receipt.manifest_binding.canonical_manifest_sha256",
        )
        governed_run_id = _required_text(
            value.get("governed_run_id"),
            field_name="receipt.manifest_binding.governed_run_id",
        )
        database_path = _required_text(
            value.get("database_path"),
            field_name="receipt.manifest_binding.database_path",
        )
        database_sha256 = _sha256_text(
            value.get("database_sha256"),
            field_name="receipt.manifest_binding.database_sha256",
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if value.get("manifest_kind") != MANIFEST_KIND:
        errors.append("receipt.manifest_binding.manifest_kind mismatch")
    missing_count = value.get("missing_unique_cell_count")
    if isinstance(missing_count, bool) or not isinstance(missing_count, int) or missing_count <= 0:
        errors.append("receipt.manifest_binding.missing_unique_cell_count must be a positive int")
        return None
    return {
        "path": path,
        "file_sha256": file_sha256,
        "canonical_manifest_sha256": canonical_manifest_sha256,
        "governed_run_id": governed_run_id,
        "missing_unique_cell_count": missing_count,
        "database_path": database_path,
        "database_sha256": database_sha256,
    }


def _validate_database(
    value: object,
    *,
    errors: list[str],
) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.database must be a mapping")
        return None
    try:
        path = _required_text(value.get("path"), field_name="receipt.database.path")
        before = _sha256_text(
            value.get("sha256_before"),
            field_name="receipt.database.sha256_before",
        )
        after = _sha256_text(
            value.get("sha256_after"),
            field_name="receipt.database.sha256_after",
        )
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if before != after:
        errors.append("receipt database SHA changed during vendor dry run")
    if value.get("unchanged") is not True or value.get("read_only") is not True:
        errors.append("receipt.database must attest unchanged read-only access")
    return {"path": path, "sha256_before": before, "sha256_after": after}


def _proposed_source_version(
    *,
    requested_cells_sha256: str,
    returned_cells_sha256: str,
) -> str:
    digest = _canonical_json_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "vendor_endpoint": VENDOR_ENDPOINT,
            "vendor_version": None,
            "requested_cells_sha256": requested_cells_sha256,
            "returned_cells_sha256": returned_cells_sha256,
        }
    )
    return PROPOSED_SOURCE_VERSION_PREFIX + digest


def _proposed_run_id(
    *,
    manifest_sha256: str,
    requested_cells_sha256: str,
    returned_cells_sha256: str,
    captured_at: str,
    database_sha256: str,
) -> str:
    digest = _canonical_json_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "manifest_sha256": manifest_sha256,
            "requested_cells_sha256": requested_cells_sha256,
            "returned_cells_sha256": returned_cells_sha256,
            "captured_at": captured_at,
            "database_sha256": database_sha256,
        }
    )
    return PROPOSED_RUN_ID_PREFIX + digest


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


def _positive_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive finite number")
    try:
        if not isinstance(value, (str, bytes, bytearray, SupportsFloat, SupportsIndex)):
            raise TypeError
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive finite number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{field_name} must be a positive finite number")
    return parsed


def _exact_int(value: object, expected: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value == expected


def _stock_code(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name).upper()
    if any(character.isspace() for character in normalized):
        raise ValueError(f"{field_name} must not contain whitespace")
    return normalized


def _iso_date_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError(f"{field_name} must be an ISO date")
    try:
        normalized = date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc
    if normalized != value:
        raise ValueError(f"{field_name} must be a canonical ISO date")
    return normalized


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field_name} must use UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _resolved_path_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    return str(Path(normalized).resolve())


def _sha256_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip() or value != value.upper():
        raise ValueError(f"{field_name} must be an uppercase sha256")
    if len(value) != 64 or any(character not in "0123456789ABCDEF" for character in value):
        raise ValueError(f"{field_name} must be an uppercase sha256")
    return value


def _required_text(value: object, *, field_name: str) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _ordered(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


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
    payload.pop("canonical_receipt_sha256", None)
    return _canonical_json_sha256(payload)
