"""Governed vendor receipt for the /stock-analysis page-gap factor scope.

This contract is intentionally remediation-only.  It proves that a capture-time
Tushare response exactly covered the reviewed page-gap factor manifest; it does
not prove historical availability, authorize a database write, run downstream
materialization, or certify a current-rule cohort.

The normalization and canonical-hash primitives are deliberately shared with
the already reviewed current-rule exact-cell receipt.  Their dependency is
locked by focused tests so this page-specific contract cannot silently drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.app.governance import (
    stock_analysis_current_rule_factor_vendor_receipt as _exact_cell_receipt,
)
from backend.app.tasks import stock_analysis_page_gap_factor_manifest as factor_manifest_task

SCHEMA_VERSION = 1
RECEIPT_KIND = "stock_analysis_page_gap_factor_vendor_receipt_v1"
READY_STATUS = "ready_for_write_approval"
VENDOR_ENDPOINT = "tushare.pro.adj_factor"
VENDOR_VERSION_STATUS = "not_provided"
REQUESTED_CELLS_SOURCE = "reviewed_page_gap_factor_manifest.target_cells"
AVAILABILITY_SEMANTICS = "capture_time_only_no_historical_availability_inference"
APPROVAL_SCOPE = "page_gap_exact_vendor_returned_cells_only"
PROPOSED_SOURCE_VERSION_PREFIX = "stock-adjustment-factor:tushare.pro.adj_factor:page-gap:v1:"
PROPOSED_RUN_ID_PREFIX = "stock-analysis-page-gap-factor-remediation:v1:"


def build_stock_analysis_page_gap_factor_vendor_receipt(
    *,
    reviewed_factor_manifest: Mapping[str, object],
    reviewed_factor_manifest_path: str | Path,
    reviewed_factor_manifest_file_sha256: str,
    returned_cells: Sequence[Mapping[str, object]],
    captured_at: str,
    database_sha256_before: str,
    database_sha256_after: str,
) -> dict[str, Any]:
    """Build a self-hashed receipt only for a complete exact-cell match."""

    contract = _validated_factor_manifest_contract(reviewed_factor_manifest)
    requested_cells = contract["target_cells"]
    normalized_returned = _exact_cell_receipt._normalize_returned_cells(
        returned_cells,
        field_name="returned_cells",
        require_non_empty=True,
    )
    _exact_cell_receipt._require_exact_returned_set(
        requested_cells=requested_cells,
        returned_cells=normalized_returned,
    )

    captured_at_text = _exact_cell_receipt._utc_datetime_text(
        captured_at,
        field_name="captured_at",
    )
    manifest_path_text = _exact_cell_receipt._resolved_path_text(
        reviewed_factor_manifest_path,
        field_name="reviewed_factor_manifest_path",
    )
    manifest_file_sha256 = _exact_cell_receipt._sha256_text(
        reviewed_factor_manifest_file_sha256,
        field_name="reviewed_factor_manifest_file_sha256",
    )
    database_before = _exact_cell_receipt._sha256_text(
        database_sha256_before,
        field_name="database_sha256_before",
    )
    database_after = _exact_cell_receipt._sha256_text(
        database_sha256_after,
        field_name="database_sha256_after",
    )
    if database_before != database_after:
        raise ValueError("database SHA changed during vendor dry run")
    if database_before != contract["database_sha256"]:
        raise ValueError("vendor dry-run database SHA does not match factor manifest")

    requested_sha256 = _exact_cell_receipt._canonical_json_sha256(requested_cells)
    returned_sha256 = _exact_cell_receipt._canonical_json_sha256(normalized_returned)
    source_version = _proposed_source_version(
        requested_cells_sha256=requested_sha256,
        returned_cells_sha256=returned_sha256,
    )
    run_id = _proposed_run_id(
        factor_manifest_sha256=contract["canonical_manifest_sha256"],
        requested_cells_sha256=requested_sha256,
        returned_cells_sha256=returned_sha256,
        captured_at=captured_at_text,
        database_sha256=database_before,
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "status": READY_STATUS,
        "captured_at": captured_at_text,
        "approval_scope": APPROVAL_SCOPE,
        "factor_manifest_binding": {
            "path": manifest_path_text,
            "file_sha256": manifest_file_sha256,
            "canonical_manifest_sha256": contract["canonical_manifest_sha256"],
            "manifest_kind": factor_manifest_task.MANIFEST_KIND,
            "status": reviewed_factor_manifest.get("status"),
            "target_cell_count": len(requested_cells),
            "target_cells_sha256": requested_sha256,
            "database_path": contract["database_path"],
            "database_sha256": contract["database_sha256"],
        },
        "page_manifest_binding": dict(contract["page_manifest_binding"]),
        "requested_cells_source": REQUESTED_CELLS_SOURCE,
        "vendor_endpoint": VENDOR_ENDPOINT,
        "vendor_version": None,
        "vendor_version_status": VENDOR_VERSION_STATUS,
        "availability_attestation": {
            "semantics": AVAILABILITY_SEMANTICS,
            "captured_at": captured_at_text,
            "historical_availability_inferred": False,
        },
        "strict_exact_cells": True,
        "exact_set_match": True,
        "remediation_only": True,
        "database_write_executed": False,
        "write_allowed": False,
        "historical_availability_proven": False,
        "formal_use_allowed": False,
        "certification_allowed": False,
        "downstream_materialization_executed": False,
        "requested_cells": requested_cells,
        "returned_cells": normalized_returned,
        "requested_cell_count": len(requested_cells),
        "returned_cell_count": len(normalized_returned),
        "requested_unique_date_count": len({cell["trade_date"] for cell in requested_cells}),
        "vendor_call_count": len({cell["trade_date"] for cell in requested_cells}),
        "missing_cell_count": 0,
        "extra_cell_count": 0,
        "duplicate_cell_count": 0,
        "invalid_cell_count": 0,
        "wrong_date_cell_count": 0,
        "requested_cells_sha256": requested_sha256,
        "returned_cells_sha256": returned_sha256,
        "database": {
            "path": contract["database_path"],
            "sha256_before": database_before,
            "sha256_after": database_after,
            "unchanged": True,
            "read_only": True,
        },
        "proposed_source_version": source_version,
        "proposed_run_id": run_id,
    }
    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
    valid, errors = validate_stock_analysis_page_gap_factor_vendor_receipt(
        receipt,
        reviewed_factor_manifest=reviewed_factor_manifest,
        reviewed_factor_manifest_path=manifest_path_text,
        reviewed_factor_manifest_file_sha256=manifest_file_sha256,
    )
    if not valid:  # pragma: no cover - construction invariant
        raise RuntimeError("constructed page-gap factor vendor receipt is invalid: " + "; ".join(errors))
    return receipt


def validate_stock_analysis_page_gap_factor_vendor_receipt(
    receipt: Mapping[str, object],
    *,
    reviewed_factor_manifest: Mapping[str, object] | None = None,
    reviewed_factor_manifest_path: str | Path | None = None,
    reviewed_factor_manifest_file_sha256: str | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate receipt self-consistency and optional external bindings."""

    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    errors: list[str] = []

    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("receipt_kind", RECEIPT_KIND),
        ("status", READY_STATUS),
        ("approval_scope", APPROVAL_SCOPE),
        ("requested_cells_source", REQUESTED_CELLS_SOURCE),
        ("vendor_endpoint", VENDOR_ENDPOINT),
        ("vendor_version_status", VENDOR_VERSION_STATUS),
    ):
        if payload.get(field_name) != expected:
            errors.append(f"receipt.{field_name} mismatch")
    if payload.get("vendor_version") is not None:
        errors.append("receipt.vendor_version must be null")
    for field_name, expected in (
        ("strict_exact_cells", True),
        ("exact_set_match", True),
        ("remediation_only", True),
        ("database_write_executed", False),
        ("write_allowed", False),
        ("historical_availability_proven", False),
        ("formal_use_allowed", False),
        ("certification_allowed", False),
        ("downstream_materialization_executed", False),
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

    captured_at: str | None = None
    try:
        captured_at = _exact_cell_receipt._utc_datetime_text(
            payload.get("captured_at"),
            field_name="receipt.captured_at",
        )
        if payload.get("captured_at") != captured_at:
            errors.append("receipt.captured_at must be canonical UTC text")
    except ValueError as exc:
        errors.append(str(exc))

    attestation = payload.get("availability_attestation")
    if not isinstance(attestation, Mapping):
        errors.append("receipt.availability_attestation must be a mapping")
    else:
        if attestation.get("semantics") != AVAILABILITY_SEMANTICS:
            errors.append("receipt availability semantics mismatch")
        if attestation.get("historical_availability_inferred") is not False:
            errors.append("receipt historical availability inference must remain false")
        if captured_at is not None and attestation.get("captured_at") != captured_at:
            errors.append("receipt availability capture time mismatch")

    requested_cells: list[dict[str, str]] = []
    returned_cells: list[dict[str, Any]] = []
    try:
        requested_cells = _exact_cell_receipt._normalize_requested_cells(
            payload.get("requested_cells"),
            field_name="receipt.requested_cells",
            require_non_empty=True,
        )
        if payload.get("requested_cells") != requested_cells:
            errors.append("receipt.requested_cells must be canonical and sorted")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        returned_cells = _exact_cell_receipt._normalize_returned_cells(
            payload.get("returned_cells"),
            field_name="receipt.returned_cells",
            require_non_empty=True,
        )
        if payload.get("returned_cells") != returned_cells:
            errors.append("receipt.returned_cells must be canonical and sorted")
    except ValueError as exc:
        errors.append(str(exc))

    requested_keys = _exact_cell_receipt._cell_keys(requested_cells)
    returned_keys = _exact_cell_receipt._cell_keys(returned_cells)
    if requested_cells and returned_cells and requested_keys != returned_keys:
        errors.append("receipt returned cells do not exactly match requested cells")
    unique_date_count = len({cell["trade_date"] for cell in requested_cells})
    for field_name, expected in (
        ("requested_cell_count", len(requested_cells)),
        ("returned_cell_count", len(returned_cells)),
        ("requested_unique_date_count", unique_date_count),
        ("vendor_call_count", unique_date_count),
    ):
        if not _exact_int(payload.get(field_name), expected):
            errors.append(f"receipt.{field_name} mismatch")

    requested_sha256 = _exact_cell_receipt._canonical_json_sha256(requested_cells)
    returned_sha256 = _exact_cell_receipt._canonical_json_sha256(returned_cells)
    _validate_sha(
        payload.get("requested_cells_sha256"),
        requested_sha256,
        "receipt.requested_cells_sha256",
        errors,
    )
    _validate_sha(
        payload.get("returned_cells_sha256"),
        returned_sha256,
        "receipt.returned_cells_sha256",
        errors,
    )

    factor_binding = _validate_factor_manifest_binding(
        payload.get("factor_manifest_binding"),
        errors=errors,
    )
    page_binding = _validate_page_manifest_binding(
        payload.get("page_manifest_binding"),
        errors=errors,
    )
    database = _validate_database(payload.get("database"), errors=errors)
    if factor_binding and page_binding and database:
        if factor_binding["database_path"] != database["path"]:
            errors.append("receipt factor manifest/database path binding mismatch")
        if factor_binding["database_sha256"] != database["sha256_before"]:
            errors.append("receipt factor manifest/database SHA binding mismatch")
        if page_binding["database_path"] != database["path"]:
            errors.append("receipt page manifest/database path binding mismatch")
        if page_binding["database_sha256"] != database["sha256_before"]:
            errors.append("receipt page manifest/database SHA binding mismatch")
        if factor_binding["target_cell_count"] != len(requested_cells):
            errors.append("receipt factor manifest target count binding mismatch")
        if factor_binding["target_cells_sha256"] != requested_sha256:
            errors.append("receipt factor manifest target SHA binding mismatch")

    expected_source_version = _proposed_source_version(
        requested_cells_sha256=requested_sha256,
        returned_cells_sha256=returned_sha256,
    )
    if payload.get("proposed_source_version") != expected_source_version:
        errors.append("receipt.proposed_source_version mismatch")
    expected_run_id: str | None = None
    if factor_binding and database and captured_at:
        expected_run_id = _proposed_run_id(
            factor_manifest_sha256=factor_binding["canonical_manifest_sha256"],
            requested_cells_sha256=requested_sha256,
            returned_cells_sha256=returned_sha256,
            captured_at=captured_at,
            database_sha256=database["sha256_before"],
        )
        if payload.get("proposed_run_id") != expected_run_id:
            errors.append("receipt.proposed_run_id mismatch")

    if reviewed_factor_manifest is not None:
        try:
            external = _validated_factor_manifest_contract(reviewed_factor_manifest)
        except ValueError as exc:
            errors.append(f"reviewed_factor_manifest invalid: {exc}")
        else:
            if requested_cells != external["target_cells"]:
                errors.append("receipt.requested_cells do not match factor manifest target_cells")
            if factor_binding:
                for field_name in (
                    "canonical_manifest_sha256",
                    "database_path",
                    "database_sha256",
                    "target_cell_count",
                    "target_cells_sha256",
                ):
                    expected = (
                        external["canonical_manifest_sha256"]
                        if field_name == "canonical_manifest_sha256"
                        else external["database_path"]
                        if field_name == "database_path"
                        else external["database_sha256"]
                        if field_name == "database_sha256"
                        else len(external["target_cells"])
                        if field_name == "target_cell_count"
                        else requested_sha256
                    )
                    if factor_binding[field_name] != expected:
                        errors.append(f"receipt.factor_manifest_binding.{field_name} mismatch")
            if page_binding and page_binding != external["page_manifest_binding"]:
                errors.append("receipt.page_manifest_binding does not match factor manifest")
    if reviewed_factor_manifest_path is not None and factor_binding:
        try:
            expected_path = _exact_cell_receipt._resolved_path_text(
                reviewed_factor_manifest_path,
                field_name="reviewed_factor_manifest_path",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if factor_binding["path"] != expected_path:
                errors.append("receipt.factor_manifest_binding.path mismatch")
    if reviewed_factor_manifest_file_sha256 is not None and factor_binding:
        try:
            expected_file_sha = _exact_cell_receipt._sha256_text(
                reviewed_factor_manifest_file_sha256,
                field_name="reviewed_factor_manifest_file_sha256",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if factor_binding["file_sha256"] != expected_file_sha:
                errors.append("receipt.factor_manifest_binding.file_sha256 mismatch")

    try:
        expected_receipt_sha = _receipt_sha256(payload)
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("receipt payload must be canonical JSON without non-finite values")
    else:
        _validate_sha(
            payload.get("canonical_receipt_sha256"),
            expected_receipt_sha,
            "receipt.canonical_receipt_sha256",
            errors,
        )
    return not errors, tuple(_ordered(errors))


def factor_approval_scope_sha256(
    *,
    factor_manifest_file_sha256: str,
    factor_manifest_canonical_sha256: str,
    page_manifest_file_sha256: str,
    page_manifest_canonical_sha256: str,
    vendor_receipt_file_sha256: str,
    vendor_receipt_canonical_sha256: str,
    database_sha256_before: str,
    returned_cells_sha256: str,
    target_cell_count: int,
    source_version: str,
    run_id: str,
) -> str:
    """Return the exact approval digest printed by the vendor dry-run CLI."""

    return _exact_cell_receipt._canonical_json_sha256(
        {
            "approval_scope": APPROVAL_SCOPE,
            "factor_manifest_file_sha256": factor_manifest_file_sha256,
            "factor_manifest_canonical_sha256": factor_manifest_canonical_sha256,
            "page_manifest_file_sha256": page_manifest_file_sha256,
            "page_manifest_canonical_sha256": page_manifest_canonical_sha256,
            "vendor_receipt_file_sha256": vendor_receipt_file_sha256,
            "vendor_receipt_canonical_sha256": vendor_receipt_canonical_sha256,
            "database_sha256_before": database_sha256_before,
            "returned_cells_sha256": returned_cells_sha256,
            "target_cell_count": target_cell_count,
            "source_version": source_version,
            "run_id": run_id,
        }
    )


def _validated_factor_manifest_contract(manifest: Mapping[str, object]) -> dict[str, Any]:
    valid, errors = factor_manifest_task.validate_stock_analysis_page_gap_factor_manifest(manifest)
    if not valid:
        raise ValueError("factor manifest failed formal validation: " + "; ".join(errors))
    if manifest.get("status") != "gaps_found":
        raise ValueError("factor manifest status must be gaps_found")
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
            raise ValueError(f"factor manifest {field_name} boundary mismatch")
    blockers = manifest.get("blockers")
    if blockers != []:
        raise ValueError("factor manifest blockers must be empty")
    target_cells = _exact_cell_receipt._normalize_requested_cells(
        manifest.get("target_cells"),
        field_name="factor_manifest.target_cells",
        require_non_empty=True,
    )
    unique_date_count = len({cell["trade_date"] for cell in target_cells})
    target_sha = _exact_cell_receipt._canonical_json_sha256(target_cells)
    if manifest.get("target_cells_sha256") != target_sha:
        raise ValueError("factor manifest target_cells_sha256 mismatch")
    if manifest.get("target_cell_count") != len(target_cells):
        raise ValueError("factor manifest target_cell_count mismatch")
    if manifest.get("requested_unique_date_count") != unique_date_count:
        raise ValueError("factor manifest requested_unique_date_count mismatch")

    database = manifest.get("database")
    if not isinstance(database, Mapping):
        raise ValueError("factor manifest database must be a mapping")
    database_path = _exact_cell_receipt._resolved_path_text(
        database.get("path"),
        field_name="factor_manifest.database.path",
    )
    database_before = _exact_cell_receipt._sha256_text(
        database.get("sha256_before"),
        field_name="factor_manifest.database.sha256_before",
    )
    database_after = _exact_cell_receipt._sha256_text(
        database.get("sha256_after"),
        field_name="factor_manifest.database.sha256_after",
    )
    if database_before != database_after:
        raise ValueError("factor manifest database hashes must match")
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        raise ValueError("factor manifest database must be unchanged and read-only")

    page_binding = _validate_page_manifest_binding(
        manifest.get("page_manifest_binding"),
        errors=[],
    )
    if page_binding is None:
        raise ValueError("factor manifest page_manifest_binding is invalid")
    if page_binding["database_path"] != database_path:
        raise ValueError("factor/page manifest database path mismatch")
    if page_binding["database_sha256"] != database_before:
        raise ValueError("factor/page manifest database SHA mismatch")
    if page_binding["missing_factor_cell_count"] != len(target_cells):
        raise ValueError("factor/page manifest missing cell count mismatch")
    return {
        "canonical_manifest_sha256": _exact_cell_receipt._sha256_text(
            manifest.get("canonical_manifest_sha256"),
            field_name="factor_manifest.canonical_manifest_sha256",
        ),
        "database_path": database_path,
        "database_sha256": database_before,
        "target_cells": target_cells,
        "page_manifest_binding": page_binding,
    }


def _validate_factor_manifest_binding(
    value: object,
    *,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.factor_manifest_binding must be a mapping")
        return None
    binding = dict(value)
    try:
        normalized = {
            "path": _exact_cell_receipt._resolved_path_text(
                binding.get("path"), field_name="receipt.factor_manifest_binding.path"
            ),
            "file_sha256": _exact_cell_receipt._sha256_text(
                binding.get("file_sha256"),
                field_name="receipt.factor_manifest_binding.file_sha256",
            ),
            "canonical_manifest_sha256": _exact_cell_receipt._sha256_text(
                binding.get("canonical_manifest_sha256"),
                field_name="receipt.factor_manifest_binding.canonical_manifest_sha256",
            ),
            "manifest_kind": str(binding.get("manifest_kind") or ""),
            "status": str(binding.get("status") or ""),
            "target_cell_count": binding.get("target_cell_count"),
            "target_cells_sha256": _exact_cell_receipt._sha256_text(
                binding.get("target_cells_sha256"),
                field_name="receipt.factor_manifest_binding.target_cells_sha256",
            ),
            "database_path": _exact_cell_receipt._resolved_path_text(
                binding.get("database_path"),
                field_name="receipt.factor_manifest_binding.database_path",
            ),
            "database_sha256": _exact_cell_receipt._sha256_text(
                binding.get("database_sha256"),
                field_name="receipt.factor_manifest_binding.database_sha256",
            ),
        }
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if binding != normalized:
        errors.append("receipt.factor_manifest_binding must contain the exact canonical fields")
    if normalized["manifest_kind"] != factor_manifest_task.MANIFEST_KIND:
        errors.append("receipt.factor_manifest_binding.manifest_kind mismatch")
    if normalized["status"] != "gaps_found":
        errors.append("receipt.factor_manifest_binding.status mismatch")
    if not _positive_int(normalized["target_cell_count"]):
        errors.append("receipt.factor_manifest_binding.target_cell_count must be positive")
    return normalized


def _validate_page_manifest_binding(
    value: object,
    *,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append("page_manifest_binding must be a mapping")
        return None
    binding = dict(value)
    required_text_fields = (
        "path",
        "manifest_kind",
        "page_id",
        "page_route",
        "page_metric_key",
        "database_path",
    )
    try:
        normalized: dict[str, Any] = {field: str(binding.get(field) or "").strip() for field in required_text_fields}
        if any(not normalized[field] for field in required_text_fields):
            raise ValueError("page_manifest_binding text fields must be non-empty")
        normalized["path"] = _exact_cell_receipt._resolved_path_text(
            normalized["path"], field_name="page_manifest_binding.path"
        )
        normalized["database_path"] = _exact_cell_receipt._resolved_path_text(
            normalized["database_path"], field_name="page_manifest_binding.database_path"
        )
        normalized["file_sha256"] = _exact_cell_receipt._sha256_text(
            binding.get("file_sha256"), field_name="page_manifest_binding.file_sha256"
        )
        normalized["canonical_manifest_sha256"] = _exact_cell_receipt._sha256_text(
            binding.get("canonical_manifest_sha256"),
            field_name="page_manifest_binding.canonical_manifest_sha256",
        )
        normalized["database_sha256"] = _exact_cell_receipt._sha256_text(
            binding.get("database_sha256"), field_name="page_manifest_binding.database_sha256"
        )
        normalized["page_gap_view_count"] = binding.get("page_gap_view_count")
        normalized["missing_factor_cell_count"] = binding.get("missing_factor_cell_count")
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if binding != normalized:
        errors.append("page_manifest_binding must contain the exact canonical fields")
    if not _positive_int(normalized["missing_factor_cell_count"]):
        errors.append("page_manifest_binding missing factor cell count must be positive")
    if not _positive_int(normalized["page_gap_view_count"]):
        errors.append("page_manifest_binding page gap view count must be positive")
    return normalized


def _validate_database(value: object, *, errors: list[str]) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        errors.append("receipt.database must be a mapping")
        return None
    try:
        path = _exact_cell_receipt._resolved_path_text(value.get("path"), field_name="receipt.database.path")
        before = _exact_cell_receipt._sha256_text(
            value.get("sha256_before"), field_name="receipt.database.sha256_before"
        )
        after = _exact_cell_receipt._sha256_text(value.get("sha256_after"), field_name="receipt.database.sha256_after")
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if before != after:
        errors.append("receipt.database hashes must match")
    if value.get("unchanged") is not True or value.get("read_only") is not True:
        errors.append("receipt.database must be unchanged and read-only")
    expected = {
        "path": path,
        "sha256_before": before,
        "sha256_after": after,
        "unchanged": True,
        "read_only": True,
    }
    if dict(value) != expected:
        errors.append("receipt.database must contain the exact canonical fields")
    return {"path": path, "sha256_before": before}


def _proposed_source_version(*, requested_cells_sha256: str, returned_cells_sha256: str) -> str:
    digest = _exact_cell_receipt._canonical_json_sha256(
        {
            "requested_cells_sha256": requested_cells_sha256,
            "returned_cells_sha256": returned_cells_sha256,
            "vendor_endpoint": VENDOR_ENDPOINT,
        }
    )
    return f"{PROPOSED_SOURCE_VERSION_PREFIX}{digest[:24]}"


def _proposed_run_id(
    *,
    factor_manifest_sha256: str,
    requested_cells_sha256: str,
    returned_cells_sha256: str,
    captured_at: str,
    database_sha256: str,
) -> str:
    digest = _exact_cell_receipt._canonical_json_sha256(
        {
            "factor_manifest_sha256": factor_manifest_sha256,
            "requested_cells_sha256": requested_cells_sha256,
            "returned_cells_sha256": returned_cells_sha256,
            "captured_at": captured_at,
            "database_sha256": database_sha256,
        }
    )
    return f"{PROPOSED_RUN_ID_PREFIX}{digest[:24]}"


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_receipt_sha256", None)
    return _exact_cell_receipt._canonical_json_sha256(payload)


def _validate_sha(value: object, expected: str, field_name: str, errors: list[str]) -> None:
    try:
        normalized = _exact_cell_receipt._sha256_text(value, field_name=field_name)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if normalized != expected:
        errors.append(f"{field_name} mismatch")


def _exact_int(value: object, expected: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value == expected


def _positive_int(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _ordered(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
