"""Read-only exact-cell contract derived from the validated stock-analysis page gap.

This manifest is remediation scope only.  It does not prove point-in-time source
availability, authorize a database write, or certify a materialized page result.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.app.tasks import stock_analysis_page_gap_manifest as page_manifest_task

SCHEMA_VERSION = 1
MANIFEST_KIND = "stock_analysis_page_gap_factor_manifest_v1"
GAPS_FOUND_STATUS = "gaps_found"
BLOCKED_STATUS = "blocked"
MANIFEST_STATUSES = frozenset({GAPS_FOUND_STATUS, BLOCKED_STATUS})

EXPECTED_PAGE_MANIFEST_KIND = page_manifest_task.MANIFEST_KIND
EXPECTED_PAGE_ID = page_manifest_task.PAGE_ID
EXPECTED_PAGE_ROUTE = page_manifest_task.PAGE_ROUTE
EXPECTED_PAGE_METRIC_KEY = page_manifest_task.PAGE_METRIC_KEY
EXPECTED_PAGE_STATUS = "gaps_found"
EXPECTED_FACTOR_CELL_STATUS = page_manifest_task.FACTOR_MISSING_STATUS

_CANONICAL_STOCK_CODE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")
_PAGE_BINDING_FIELDS = frozenset(
    {
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
    }
)
_DATABASE_FIELDS = frozenset({"path", "sha256_before", "sha256_after", "unchanged", "read_only"})


def build_stock_analysis_page_gap_factor_manifest(
    *,
    page_manifest_path: str | Path,
    duckdb_path: str | Path,
    created_at: str,
) -> dict[str, Any]:
    """Build a read-only exact-cell target contract from one page-gap manifest.

    This is an internal trusted-path API. Untrusted path input must use the
    hardened CLI, which enforces trusted-root containment and link rejection.
    """

    source_path = _existing_file(page_manifest_path, field_name="page_manifest_path")
    database_path = _existing_file(duckdb_path, field_name="duckdb_path")
    normalized_created_at = _utc_datetime_text(created_at, field_name="created_at")

    page_file_sha256_before = _file_sha256(source_path)
    database_sha256_before = _file_sha256(database_path)
    blockers: list[str] = []
    page_payload: dict[str, Any] = {}
    page_loaded = False
    target_cells: list[dict[str, str]] = []

    try:
        page_payload = _load_json_object(source_path)
        page_loaded = True
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        blockers.append(f"page_manifest_unavailable:{type(exc).__name__}")

    page_file_sha256_after = _file_sha256(source_path)
    if page_file_sha256_after != page_file_sha256_before:
        blockers.append("page_manifest_changed_during_build")

    if page_loaded:
        try:
            valid, validation_errors = page_manifest_task.validate_stock_analysis_page_gap_manifest(page_payload)
        except Exception as exc:  # noqa: BLE001 - Any formal-page validator failure adds an authority blocker before candidate target cells can be accepted.
            blockers.append(f"page_manifest_validator_failed:{type(exc).__name__}")
        else:
            if not valid:
                blockers.append("page_manifest_formal_validation_failed")
                blockers.append(f"page_manifest_validation_error_count:{len(validation_errors)}")
        _append_page_contract_blockers(
            page_payload=page_payload,
            database_path=database_path,
            database_sha256=database_sha256_before,
            blockers=blockers,
        )
        candidate_targets = _target_cells_from_page_manifest(page_payload, blockers)
        if not blockers:
            target_cells = candidate_targets

    page_file_sha256_final = _file_sha256(source_path)
    if page_file_sha256_final != page_file_sha256_before:
        blockers.append("page_manifest_changed_during_build")

    database_sha256_after = _file_sha256(database_path)
    database_unchanged = database_sha256_before == database_sha256_after
    if not database_unchanged:
        blockers.append("duckdb_changed_during_factor_manifest_build")

    if blockers:
        target_cells = []

    normalized_blockers = _ordered(blockers)
    target_cell_count = len(target_cells)
    requested_unique_date_count = len({cell["trade_date"] for cell in target_cells})
    page_binding = _page_manifest_binding(
        source_path=source_path,
        page_file_sha256=page_file_sha256_before,
        page_payload=page_payload,
    )
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "status": BLOCKED_STATUS if normalized_blockers else GAPS_FOUND_STATUS,
        "created_at": normalized_created_at,
        "remediation_only": True,
        "strict_exact_date_lookup": True,
        "carry_forward_allowed": False,
        "fallback_allowed": False,
        "write_allowed": False,
        "historical_availability_proven": False,
        "certification_allowed": False,
        "downstream_materialization_allowed": False,
        "page_manifest_binding": page_binding,
        "target_cells": target_cells,
        "target_cell_count": target_cell_count,
        "target_cells_sha256": _canonical_value_sha256(target_cells),
        "requested_unique_date_count": requested_unique_date_count,
        "database": {
            "path": str(database_path),
            "sha256_before": database_sha256_before,
            "sha256_after": database_sha256_after,
            "unchanged": database_unchanged,
            "read_only": True,
        },
        "blockers": normalized_blockers,
    }
    manifest["canonical_manifest_sha256"] = _canonical_manifest_sha256(manifest)
    return manifest


def validate_stock_analysis_page_gap_factor_manifest(
    manifest: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    """Validate exact targets, source binding, immutable boundaries, and self hash."""

    if not isinstance(manifest, Mapping):
        return False, ("manifest must be a mapping",)
    payload = dict(manifest)
    errors: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest.schema_version must equal {SCHEMA_VERSION}")
    if payload.get("manifest_kind") != MANIFEST_KIND:
        errors.append(f"manifest.manifest_kind must equal {MANIFEST_KIND}")
    status = payload.get("status")
    if status not in MANIFEST_STATUSES:
        errors.append("manifest.status is invalid")

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
        if payload.get(field_name) is not expected:
            errors.append(f"manifest.{field_name} must be {str(expected).lower()}")

    try:
        created_at = _utc_datetime_text(payload.get("created_at"), field_name="created_at")
        if payload.get("created_at") != created_at:
            errors.append("manifest.created_at is not canonical UTC")
    except ValueError as exc:
        errors.append(str(exc))

    binding_raw = payload.get("page_manifest_binding")
    binding: dict[str, Any] = {}
    if not isinstance(binding_raw, Mapping):
        errors.append("manifest.page_manifest_binding must be a mapping")
    else:
        binding = dict(binding_raw)
        if set(binding) != _PAGE_BINDING_FIELDS:
            errors.append("manifest.page_manifest_binding fields mismatch")
        _validate_page_binding(binding, status=status, errors=errors)

    targets_raw = payload.get("target_cells")
    if not isinstance(targets_raw, list):
        errors.append("manifest.target_cells must be a list")
        targets: list[object] = []
    else:
        targets = targets_raw
    normalized_targets: list[dict[str, str]] = []
    seen_targets: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(targets):
        if not isinstance(raw_cell, Mapping):
            errors.append(f"manifest.target_cells[{index}] must be a mapping")
            continue
        cell = dict(raw_cell)
        if set(cell) != {"stock_code", "trade_date"}:
            errors.append(f"manifest.target_cells[{index}] fields mismatch")
        try:
            stock_code = _stock_code(
                cell.get("stock_code"),
                field_name=f"target_cells[{index}].stock_code",
            )
            trade_date = _date_text(
                cell.get("trade_date"),
                field_name=f"target_cells[{index}].trade_date",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key = (stock_code, trade_date)
        if key in seen_targets:
            errors.append("manifest.target_cells contains duplicate exact cells")
        seen_targets.add(key)
        normalized_targets.append({"stock_code": stock_code, "trade_date": trade_date})

    expected_targets = sorted(
        normalized_targets,
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )
    if normalized_targets != expected_targets:
        errors.append("manifest.target_cells must be canonically sorted")

    target_count = _nonnegative_int(
        payload.get("target_cell_count"),
        field_name="target_cell_count",
        errors=errors,
    )
    if target_count != len(normalized_targets):
        errors.append("manifest.target_cell_count mismatch")
    requested_date_count = _nonnegative_int(
        payload.get("requested_unique_date_count"),
        field_name="requested_unique_date_count",
        errors=errors,
    )
    if requested_date_count != len({cell["trade_date"] for cell in normalized_targets}):
        errors.append("manifest.requested_unique_date_count mismatch")
    try:
        observed_target_sha = _sha256_text(payload.get("target_cells_sha256"), field_name="target_cells_sha256")
        if observed_target_sha != _canonical_value_sha256(normalized_targets):
            errors.append("manifest.target_cells_sha256 mismatch")
    except ValueError as exc:
        errors.append(str(exc))

    database_raw = payload.get("database")
    database: dict[str, Any] = {}
    if not isinstance(database_raw, Mapping):
        errors.append("manifest.database must be a mapping")
    else:
        database = dict(database_raw)
        if set(database) != _DATABASE_FIELDS:
            errors.append("manifest.database fields mismatch")
        _validate_database(
            database,
            binding=binding,
            status=status,
            errors=errors,
        )

    blockers_raw = payload.get("blockers")
    if not isinstance(blockers_raw, list) or any(
        not isinstance(item, str) or not item.strip() for item in blockers_raw
    ):
        errors.append("manifest.blockers must be a list of non-empty strings")
        blockers: list[str] = []
    else:
        blockers = [str(item) for item in blockers_raw]
        if blockers != _ordered(blockers):
            errors.append("manifest.blockers must be unique and ordered")

    if status == GAPS_FOUND_STATUS:
        if blockers:
            errors.append("gaps_found manifest cannot contain blockers")
        if target_count < 1:
            errors.append("gaps_found manifest requires exact-cell targets")
        if binding and target_count != binding.get("missing_factor_cell_count"):
            errors.append("manifest.target_cell_count does not match page binding")
    elif status == BLOCKED_STATUS:
        if not blockers:
            errors.append("blocked manifest requires blockers")
        if normalized_targets or target_count != 0 or requested_date_count != 0:
            errors.append("blocked manifest must not expose remediation targets")

    try:
        observed_manifest_sha = _sha256_text(
            payload.get("canonical_manifest_sha256"),
            field_name="canonical_manifest_sha256",
        )
        if observed_manifest_sha != _canonical_manifest_sha256(payload):
            errors.append("manifest.canonical_manifest_sha256 mismatch")
    except ValueError as exc:
        errors.append(str(exc))
    return not errors, tuple(errors)


def _append_page_contract_blockers(
    *,
    page_payload: Mapping[str, Any],
    database_path: Path,
    database_sha256: str,
    blockers: list[str],
) -> None:
    expected_fields = (
        ("manifest_kind", EXPECTED_PAGE_MANIFEST_KIND),
        ("page_id", EXPECTED_PAGE_ID),
        ("page_route", EXPECTED_PAGE_ROUTE),
        ("page_metric_key", EXPECTED_PAGE_METRIC_KEY),
        ("status", EXPECTED_PAGE_STATUS),
    )
    for field_name, expected in expected_fields:
        if page_payload.get(field_name) != expected:
            blockers.append(f"page_manifest_{field_name}_mismatch")

    page_blockers = page_payload.get("blockers")
    if page_blockers != []:
        blockers.append("page_manifest_has_blockers")

    summary = page_payload.get("summary")
    if not isinstance(summary, Mapping):
        blockers.append("page_manifest_summary_invalid")
    else:
        page_gap_count = summary.get("page_gap_view_count_before")
        mapped_gap_count = summary.get("mapped_gap_view_count")
        missing_cell_count = summary.get("unique_missing_factor_cell_count")
        if not _is_positive_int(page_gap_count):
            blockers.append("page_manifest_page_gap_view_count_invalid")
        if mapped_gap_count != page_gap_count:
            blockers.append("page_manifest_mapped_gap_view_count_mismatch")
        if not _is_positive_int(missing_cell_count):
            blockers.append("page_manifest_missing_factor_cell_count_invalid")
        factor_quality = summary.get("factor_quality")
        if not isinstance(factor_quality, Mapping) or dict(factor_quality) != {
            "missing_required_cell_count": missing_cell_count,
            "invalid_required_cell_count": 0,
            "ambiguous_required_cell_count": 0,
        }:
            blockers.append("page_manifest_factor_quality_mismatch")

    database = page_payload.get("database")
    if not isinstance(database, Mapping):
        blockers.append("page_manifest_database_binding_invalid")
    else:
        try:
            bound_path = _existing_file(database.get("path"), field_name="page_manifest.database.path")
        except (TypeError, ValueError):
            blockers.append("page_manifest_database_path_invalid")
        else:
            if bound_path != database_path:
                blockers.append("page_manifest_database_path_mismatch")
        if database.get("sha256_before") != database_sha256 or database.get("sha256_after") != database_sha256:
            blockers.append("page_manifest_database_sha256_drift")


def _target_cells_from_page_manifest(page_payload: Mapping[str, Any], blockers: list[str]) -> list[dict[str, str]]:
    raw_cells = page_payload.get("missing_factor_cells")
    if not isinstance(raw_cells, list):
        blockers.append("page_manifest_missing_factor_cells_invalid")
        return []
    summary = page_payload.get("summary")
    expected_count = summary.get("unique_missing_factor_cell_count") if isinstance(summary, Mapping) else None
    if len(raw_cells) != expected_count:
        blockers.append("page_manifest_missing_factor_cells_length_mismatch")
        return []

    target_cells: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, Mapping):
            blockers.append("page_manifest_missing_factor_cell_invalid")
            return []
        if raw_cell.get("status") != EXPECTED_FACTOR_CELL_STATUS or raw_cell.get("cell_statuses") != [
            EXPECTED_FACTOR_CELL_STATUS
        ]:
            blockers.append("page_manifest_missing_factor_cell_status_mismatch")
            return []
        try:
            stock_code = _stock_code(raw_cell.get("stock_code"), field_name="missing_factor_cell.stock_code")
            trade_date = _date_text(raw_cell.get("trade_date"), field_name="missing_factor_cell.trade_date")
        except ValueError:
            blockers.append("page_manifest_missing_factor_cell_key_invalid")
            return []
        key = (stock_code, trade_date)
        if key in seen:
            blockers.append("page_manifest_missing_factor_cell_duplicate")
            return []
        seen.add(key)
        target_cells.append({"stock_code": stock_code, "trade_date": trade_date})

    return sorted(
        target_cells,
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )


def _page_manifest_binding(
    *,
    source_path: Path,
    page_file_sha256: str,
    page_payload: Mapping[str, Any],
) -> dict[str, Any]:
    summary = page_payload.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    database = page_payload.get("database")
    database = database if isinstance(database, Mapping) else {}
    return {
        "path": str(source_path),
        "file_sha256": page_file_sha256,
        "canonical_manifest_sha256": page_payload.get("canonical_manifest_sha256"),
        "manifest_kind": page_payload.get("manifest_kind"),
        "page_id": page_payload.get("page_id"),
        "page_route": page_payload.get("page_route"),
        "page_metric_key": page_payload.get("page_metric_key"),
        "database_path": database.get("path"),
        "database_sha256": database.get("sha256_after"),
        "page_gap_view_count": summary.get("page_gap_view_count_before"),
        "missing_factor_cell_count": summary.get("unique_missing_factor_cell_count"),
    }


def _validate_page_binding(binding: Mapping[str, Any], *, status: object, errors: list[str]) -> None:
    try:
        _required_text(binding.get("path"), field_name="page_manifest_binding.path")
        _sha256_text(
            binding.get("file_sha256"),
            field_name="page_manifest_binding.file_sha256",
        )
    except ValueError as exc:
        errors.append(str(exc))

    if status != GAPS_FOUND_STATUS:
        return
    for field_name, expected in (
        ("manifest_kind", EXPECTED_PAGE_MANIFEST_KIND),
        ("page_id", EXPECTED_PAGE_ID),
        ("page_route", EXPECTED_PAGE_ROUTE),
        ("page_metric_key", EXPECTED_PAGE_METRIC_KEY),
    ):
        if binding.get(field_name) != expected:
            errors.append(f"manifest.page_manifest_binding.{field_name} mismatch")
    if not _is_positive_int(binding.get("page_gap_view_count")):
        errors.append("manifest.page_manifest_binding.page_gap_view_count must be positive")
    if not _is_positive_int(binding.get("missing_factor_cell_count")):
        errors.append("manifest.page_manifest_binding.missing_factor_cell_count must be positive")
    try:
        _sha256_text(
            binding.get("canonical_manifest_sha256"),
            field_name="page_manifest_binding.canonical_manifest_sha256",
        )
        _required_text(
            binding.get("database_path"),
            field_name="page_manifest_binding.database_path",
        )
        _sha256_text(
            binding.get("database_sha256"),
            field_name="page_manifest_binding.database_sha256",
        )
    except ValueError as exc:
        errors.append(str(exc))


def _validate_database(
    database: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    status: object,
    errors: list[str],
) -> None:
    try:
        path = _required_text(database.get("path"), field_name="database.path")
        before = _sha256_text(database.get("sha256_before"), field_name="database.sha256_before")
        after = _sha256_text(database.get("sha256_after"), field_name="database.sha256_after")
        hashes_match = before == after
        if database.get("unchanged") is not hashes_match:
            errors.append("manifest.database.unchanged does not match hashes")
        if status == GAPS_FOUND_STATUS and not hashes_match:
            errors.append("manifest.database hashes must match")
        if status == GAPS_FOUND_STATUS and binding:
            if path != binding.get("database_path"):
                errors.append("manifest database path does not match page binding")
            if after != binding.get("database_sha256"):
                errors.append("manifest database sha256 does not match page binding")
    except ValueError as exc:
        errors.append(str(exc))
    if status == GAPS_FOUND_STATUS and database.get("unchanged") is not True:
        errors.append("manifest.database.unchanged must be true")
    if database.get("read_only") is not True:
        errors.append("manifest.database.read_only must be true")


def _existing_file(path_value: object, *, field_name: str) -> Path:
    if not isinstance(path_value, (str, Path)):
        raise ValueError(f"{field_name} must identify an existing file")
    path = Path(path_value).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{field_name} must identify an existing file")
    return path


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("page manifest must be a JSON object")
    return dict(payload)


def _stock_code(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name).upper()
    if not _CANONICAL_STOCK_CODE_RE.fullmatch(text) or value != text:
        raise ValueError(f"{field_name} must be a canonical stock code")
    return text


def _date_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be a canonical ISO date")
    return text


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field_name} must use UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty canonical string")
    return value


def _sha256_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    if len(text) != 64 or any(character not in "0123456789ABCDEF" for character in text):
        raise ValueError(f"{field_name} must be an uppercase sha256")
    return text


def _nonnegative_int(value: object, *, field_name: str, errors: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"manifest.{field_name} must be a non-negative integer")
        return 0
    return value


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _ordered(values: Sequence[str]) -> list[str]:
    return sorted(set(values))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_value_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _canonical_manifest_sha256(payload: Mapping[str, object]) -> str:
    content = dict(payload)
    content.pop("canonical_manifest_sha256", None)
    return _canonical_value_sha256(content)
