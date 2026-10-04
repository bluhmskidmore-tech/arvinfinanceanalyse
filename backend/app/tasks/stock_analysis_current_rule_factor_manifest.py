"""Read-only adjustment-factor gap manifest for stock-analysis current-rule replay.

The manifest is deliberately remediation-only.  It inventories exact physical
``stock_adjustment_factor`` cells required by fresh replay runner candidates;
it neither certifies a cohort nor writes data, files, or vendor state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, SupportsFloat, SupportsIndex, SupportsInt, cast

import duckdb
from backend.app.governance.stock_analysis_current_rule_version_tuple import (
    validate_stock_analysis_current_rule_version_tuple,
)
from backend.app.governance.stock_analysis_source_availability_receipt import (
    validate_stock_analysis_source_availability_receipt,
)
from backend.app.tasks import livermore_candidate_history_materialize as execution_task

SCHEMA_VERSION = 1
MANIFEST_KIND = "stock_analysis_current_rule_factor_manifest_v1"
SOURCE_AVAILABILITY_SEMANTICS = "capture_time_only_no_historical_ingestion_inference"
FACTOR_TABLE = "stock_adjustment_factor"

SIGNAL_STATUS = "selection_completed_with_signals"
ZERO_STATUS = "selection_completed_no_signals"
POLICY_INACTIVE_STATUS = "selection_policy_inactive"
UNSUPPORTED_STATUS = "selection_unsupported"
LOADER_ERROR_STATUS = "loader_error"
RUNNER_STATUSES = frozenset(
    {
        SIGNAL_STATUS,
        ZERO_STATUS,
        POLICY_INACTIVE_STATUS,
        UNSUPPORTED_STATUS,
        LOADER_ERROR_STATUS,
    }
)

CELL_ROLES = ("signal", "entry", "exit_1d", "exit_5d", "exit_10d", "exit_20d")
CELL_STATUSES = frozenset(
    {
        "present_pit_usable",
        "missing",
        "invalid",
        "ambiguous",
        "present_source_unproven",
        "present_after_evaluation",
        "date_unresolved",
    }
)
PHYSICAL_GAP_CELL_STATUSES = CELL_STATUSES.difference(
    {"present_pit_usable", "date_unresolved"}
)
MANIFEST_STATUSES = frozenset({"ready", "gaps_found", "blocked"})


def build_stock_analysis_current_rule_factor_manifest(
    *,
    duckdb_path: str | Path,
    evaluation_as_of_date: str,
    governed_run_id: str,
    runner_results: Sequence[Mapping[str, Any]],
    source_availability_receipts: Sequence[Mapping[str, Any]],
    frozen_version_tuple: Mapping[str, Any],
    calendar_receipt_sha256: str,
    replay_plan_digest_version: str,
    replay_plan_digest: str,
    created_at: str,
) -> dict[str, Any]:
    """Build an exact-date factor manifest without mutating DuckDB or the filesystem."""

    target = Path(duckdb_path).resolve()
    if not target.is_file():
        raise ValueError("duckdb_path must be an existing file")
    evaluation = _date_text(evaluation_as_of_date, field_name="evaluation_as_of_date")
    normalized_created_at = _utc_datetime_text(created_at, field_name="created_at")
    run_id = _required_text(governed_run_id, field_name="governed_run_id")
    calendar_sha = _sha256_text(calendar_receipt_sha256, field_name="calendar_receipt_sha256")
    digest_version = _required_text(
        replay_plan_digest_version,
        field_name="replay_plan_digest_version",
    )
    plan_digest = _sha256_text(replay_plan_digest, field_name="replay_plan_digest")

    database_sha256_before = _file_sha256(target)
    blockers: list[str] = []
    candidate_cells: list[dict[str, Any]] = []
    normalized_runners: list[dict[str, Any]] = []
    source_receipt_hashes: tuple[str, ...] = ()
    source_index: dict[tuple[str, str, str, str, str], tuple[str, str]] = {}
    version_tuple = dict(frozen_version_tuple) if isinstance(frozen_version_tuple, Mapping) else {}

    valid_version, version_errors = validate_stock_analysis_current_rule_version_tuple(version_tuple)
    if not valid_version:
        blockers.extend(f"frozen_version_tuple_invalid:{error}" for error in version_errors)

    try:
        source_index, source_receipt_hashes = _prepare_source_receipts(
            source_availability_receipts
        )
    except ValueError as exc:
        blockers.append(f"source_receipts_invalid:{exc}")

    try:
        normalized_runners, runner_blockers = _normalize_runner_results(
            runner_results,
            evaluation=evaluation,
            version_tuple=version_tuple,
        )
        blockers.extend(runner_blockers)
    except ValueError as exc:
        blockers.append(f"runner_results_invalid:{exc}")

    conn: duckdb.DuckDBPyConnection | None = None
    try:
        if not blockers:
            conn = duckdb.connect(str(target), read_only=True)
            factor_columns = _factor_table_columns(conn)
            for runner in normalized_runners:
                if runner["status"] != SIGNAL_STATUS:
                    continue
                signal_date = str(runner["trade_date"])
                for stock_code in runner["accepted_candidate_codes"]:
                    try:
                        execution = execution_task._execution_returns_for_candidate(
                            conn,
                            stock_code=stock_code,
                            snapshot_as_of_date=signal_date,
                        )
                    except Exception as exc:  # pragma: no cover - defensive vendor-shape boundary
                        blockers.append(
                            "execution_probe_failed:"
                            f"{signal_date}:{stock_code}:{type(exc).__name__}"
                        )
                        continue
                    role_dates = _execution_role_dates(
                        signal_date=signal_date,
                        stock_code=stock_code,
                        execution=execution,
                        evaluation=evaluation,
                    )
                    for role in CELL_ROLES:
                        candidate_cells.append(
                            _build_candidate_cell(
                                conn=conn,
                                factor_columns=factor_columns,
                                signal_date=signal_date,
                                stock_code=stock_code,
                                role=role,
                                factor_date=role_dates[role],
                                execution_data_status=(
                                    str(execution.get("data_status") or "unknown")
                                    if isinstance(execution, Mapping)
                                    else "missing_signal_observation"
                                ),
                                source_index=source_index,
                                evaluation=evaluation,
                            )
                        )
    except ValueError as exc:
        blockers.append(str(exc))
    finally:
        if conn is not None:
            conn.close()

    candidate_cells.sort(
        key=lambda cell: (
            cell["signal_date"],
            cell["stock_code"],
            CELL_ROLES.index(cell["role"]),
        )
    )
    missing_unique_cells = _missing_unique_cells(candidate_cells)
    database_sha256_after = _file_sha256(target)
    database_unchanged = database_sha256_before == database_sha256_after
    if not database_unchanged:
        blockers.append("duckdb_changed_during_manifest_build")

    runner_status_counts = Counter(str(item["status"]) for item in normalized_runners)
    cell_status_counts = Counter(str(item["status"]) for item in candidate_cells)
    accepted_candidate_count = sum(
        len(item["accepted_candidate_codes"])
        for item in normalized_runners
        if item["status"] == SIGNAL_STATUS
    )
    gap_cell_count = sum(
        cell_status_counts.get(status, 0) for status in PHYSICAL_GAP_CELL_STATUSES
    )
    unresolved_cell_count = cell_status_counts.get("date_unresolved", 0)
    normalized_blockers = _ordered(blockers)
    status = (
        "blocked"
        if normalized_blockers
        else "gaps_found"
        if gap_cell_count
        else "ready"
    )
    summary = {
        "runner_date_count": len(normalized_runners),
        "runner_status_counts": {
            key: runner_status_counts.get(key, 0) for key in sorted(RUNNER_STATUSES)
        },
        "signal_date_count": runner_status_counts.get(SIGNAL_STATUS, 0),
        "zero_signal_date_count": runner_status_counts.get(ZERO_STATUS, 0),
        "policy_inactive_date_count": runner_status_counts.get(POLICY_INACTIVE_STATUS, 0),
        "accepted_candidate_count": accepted_candidate_count,
        "candidate_cell_count": len(candidate_cells),
        "expected_candidate_cell_count": accepted_candidate_count * len(CELL_ROLES),
        "cell_status_counts": {
            key: cell_status_counts.get(key, 0) for key in sorted(CELL_STATUSES)
        },
        "pit_usable_cell_count": cell_status_counts.get("present_pit_usable", 0),
        "gap_cell_count": gap_cell_count,
        "unresolved_cell_count": unresolved_cell_count,
        "missing_unique_cell_count": len(missing_unique_cells),
        "blocker_count": len(normalized_blockers),
    }
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "status": status,
        "created_at": normalized_created_at,
        "evaluation_as_of_date": evaluation,
        "governed_run_id": run_id,
        "calendar_receipt_sha256": calendar_sha,
        "replay_plan_digest_version": digest_version,
        "replay_plan_digest": plan_digest,
        "frozen_version_tuple": version_tuple,
        "source_availability_receipt_sha256s": list(source_receipt_hashes),
        "source_availability_semantics": SOURCE_AVAILABILITY_SEMANTICS,
        "strict_exact_date_lookup": True,
        "carry_forward_allowed": False,
        "fallback_allowed": False,
        "remediation_only": True,
        "certification_allowed": False,
        "candidate_scope_authority": "fresh_runner_accepted_candidate_codes_only",
        "non_signal_status_semantics": {
            ZERO_STATUS: "disclosure_only_zero_cells_no_certificate_semantics",
            POLICY_INACTIVE_STATUS: "disclosure_only_zero_cells_no_certificate_semantics",
        },
        "candidate_cells": candidate_cells,
        "missing_unique_cells": missing_unique_cells,
        "summary": summary,
        "blockers": normalized_blockers,
        "database": {
            "path": str(target),
            "sha256_before": database_sha256_before,
            "sha256_after": database_sha256_after,
            "unchanged": database_unchanged,
            "read_only": True,
        },
    }
    manifest["canonical_manifest_sha256"] = _canonical_sha256(manifest)
    return manifest


def validate_stock_analysis_current_rule_factor_manifest(
    manifest: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    """Validate the manifest's shape, internal counts, dedupe, and self hash."""

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
        ("strict_exact_date_lookup", True),
        ("carry_forward_allowed", False),
        ("fallback_allowed", False),
        ("remediation_only", True),
        ("certification_allowed", False),
    ):
        if payload.get(field_name) is not expected:
            errors.append(f"manifest.{field_name} must be {str(expected).lower()}")
    if payload.get("source_availability_semantics") != SOURCE_AVAILABILITY_SEMANTICS:
        errors.append("manifest.source_availability_semantics mismatch")
    evaluation: str | None = None
    try:
        evaluation = _date_text(
            payload.get("evaluation_as_of_date"), field_name="evaluation_as_of_date"
        )
        _utc_datetime_text(payload.get("created_at"), field_name="created_at")
        _required_text(payload.get("governed_run_id"), field_name="governed_run_id")
        _sha256_text(payload.get("calendar_receipt_sha256"), field_name="calendar_receipt_sha256")
        _required_text(
            payload.get("replay_plan_digest_version"),
            field_name="replay_plan_digest_version",
        )
        _sha256_text(payload.get("replay_plan_digest"), field_name="replay_plan_digest")
    except ValueError as exc:
        errors.append(str(exc))

    normalized_source_hashes: list[str] = []
    source_receipt_hashes = payload.get("source_availability_receipt_sha256s")
    if not isinstance(source_receipt_hashes, list) or not source_receipt_hashes:
        errors.append("manifest.source_availability_receipt_sha256s must be a non-empty list")
    else:
        for index, source_hash in enumerate(source_receipt_hashes):
            try:
                normalized_source_hashes.append(
                    _sha256_text(
                        source_hash,
                        field_name=f"source_availability_receipt_sha256s[{index}]",
                    )
                )
            except ValueError as exc:
                errors.append(str(exc))
        if normalized_source_hashes != sorted(set(normalized_source_hashes)):
            errors.append(
                "manifest.source_availability_receipt_sha256s must be sorted and unique"
            )

    database = payload.get("database")
    if not isinstance(database, Mapping):
        errors.append("manifest.database must be a mapping")
    else:
        before = database.get("sha256_before")
        after = database.get("sha256_after")
        try:
            before_sha = _sha256_text(before, field_name="database.sha256_before")
            after_sha = _sha256_text(after, field_name="database.sha256_after")
            if before_sha != after_sha:
                errors.append("manifest database hashes must be unchanged")
        except ValueError as exc:
            errors.append(str(exc))
        if database.get("unchanged") is not True or database.get("read_only") is not True:
            errors.append("manifest.database must attest unchanged read-only access")

    cells = payload.get("candidate_cells")
    if not isinstance(cells, list):
        errors.append("manifest.candidate_cells must be a list")
        cells = []
    normalized_cells: list[dict[str, Any]] = []
    seen_candidate_roles: set[tuple[str, str, str]] = set()
    roles_by_candidate: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for index, raw_cell in enumerate(cells):
        if not isinstance(raw_cell, Mapping):
            errors.append(f"manifest.candidate_cells[{index}] must be a mapping")
            continue
        cell = dict(raw_cell)
        role = cell.get("role")
        cell_status = cell.get("status")
        if role not in CELL_ROLES:
            errors.append(f"manifest.candidate_cells[{index}].role is invalid")
            continue
        if cell_status not in CELL_STATUSES:
            errors.append(f"manifest.candidate_cells[{index}].status is invalid")
        try:
            signal_date = _date_text(
                cell.get("signal_date"), field_name=f"candidate_cells[{index}].signal_date"
            )
            stock_code = _stock_code(
                cell.get("stock_code"), field_name=f"candidate_cells[{index}].stock_code"
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        candidate_role = (signal_date, stock_code, str(role))
        if candidate_role in seen_candidate_roles:
            errors.append("manifest.candidate_cells contains duplicate candidate roles")
        seen_candidate_roles.add(candidate_role)
        roles_by_candidate[(signal_date, stock_code)].add(str(role))
        factor_date = cell.get("factor_date")
        if cell_status == "date_unresolved":
            if factor_date is not None:
                errors.append(f"manifest.candidate_cells[{index}] unresolved date must be null")
        else:
            try:
                _date_text(factor_date, field_name=f"candidate_cells[{index}].factor_date")
            except ValueError as exc:
                errors.append(str(exc))
        if cell_status in {"present_pit_usable", "present_after_evaluation"}:
            factor = cell.get("adj_factor")
            if not _is_positive_finite(factor) or cell.get("source_receipt_match") is not True:
                errors.append(f"manifest.candidate_cells[{index}] matched cell is not proven")
            try:
                cell_receipt_sha = _sha256_text(
                    cell.get("source_receipt_sha256"),
                    field_name=f"candidate_cells[{index}].source_receipt_sha256",
                )
                if cell_receipt_sha not in set(normalized_source_hashes):
                    errors.append(
                        f"manifest.candidate_cells[{index}] source receipt hash is not bound at manifest level"
                    )
            except ValueError as exc:
                errors.append(str(exc))
            try:
                available_at = _date_text(
                    cell.get("available_at"),
                    field_name=f"candidate_cells[{index}].available_at",
                )
                if evaluation is not None:
                    if cell_status == "present_pit_usable" and available_at > evaluation:
                        errors.append(
                            f"manifest.candidate_cells[{index}] usable availability is after evaluation"
                        )
                    if (
                        cell_status == "present_after_evaluation"
                        and available_at <= evaluation
                    ):
                        errors.append(
                            f"manifest.candidate_cells[{index}] after-evaluation status is inconsistent"
                        )
            except ValueError as exc:
                errors.append(str(exc))
        normalized_cells.append(cell)
    for candidate, roles in roles_by_candidate.items():
        if roles != set(CELL_ROLES):
            errors.append(f"manifest candidate {candidate[0]}:{candidate[1]} lacks exactly six roles")

    expected_missing = _missing_unique_cells(normalized_cells)
    observed_missing = payload.get("missing_unique_cells")
    if observed_missing != expected_missing:
        errors.append("manifest.missing_unique_cells does not match candidate cell gaps")

    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or any(not str(item).strip() for item in blockers):
        errors.append("manifest.blockers must be a list of non-empty strings")
        blockers = []
    gap_count = sum(
        cell.get("status") in PHYSICAL_GAP_CELL_STATUSES for cell in normalized_cells
    )
    unresolved_count = sum(
        cell.get("status") == "date_unresolved" for cell in normalized_cells
    )
    if status == "ready" and (blockers or gap_count):
        errors.append("ready manifest cannot contain blockers or factor gaps")
    if status == "gaps_found" and (blockers or gap_count == 0):
        errors.append("gaps_found manifest requires gaps and no blockers")
    if status == "blocked" and not blockers:
        errors.append("blocked manifest requires blockers")

    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("manifest.summary must be a mapping")
    else:
        if summary.get("candidate_cell_count") != len(normalized_cells):
            errors.append("manifest.summary.candidate_cell_count mismatch")
        if summary.get("gap_cell_count") != gap_count:
            errors.append("manifest.summary.gap_cell_count mismatch")
        if summary.get("unresolved_cell_count") != unresolved_count:
            errors.append("manifest.summary.unresolved_cell_count mismatch")
        if summary.get("missing_unique_cell_count") != len(expected_missing):
            errors.append("manifest.summary.missing_unique_cell_count mismatch")
        if summary.get("blocker_count") != len(blockers):
            errors.append("manifest.summary.blocker_count mismatch")
        expected_cell_status_counts = Counter(str(cell.get("status")) for cell in normalized_cells)
        if summary.get("cell_status_counts") != {
            key: expected_cell_status_counts.get(key, 0) for key in sorted(CELL_STATUSES)
        }:
            errors.append("manifest.summary.cell_status_counts mismatch")

    version_tuple = payload.get("frozen_version_tuple")
    valid_version, version_errors = validate_stock_analysis_current_rule_version_tuple(
        version_tuple if isinstance(version_tuple, Mapping) else {}
    )
    if not valid_version:
        errors.extend(f"manifest.frozen_version_tuple invalid: {error}" for error in version_errors)

    observed_hash = payload.get("canonical_manifest_sha256")
    try:
        normalized_hash = _sha256_text(
            observed_hash,
            field_name="canonical_manifest_sha256",
        )
        if normalized_hash != _canonical_sha256(payload):
            errors.append("manifest.canonical_manifest_sha256 mismatch")
    except ValueError as exc:
        errors.append(str(exc))
    return not errors, tuple(errors)


def _prepare_source_receipts(
    receipts: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[str, str, str, str, str], tuple[str, str]],
    tuple[str, ...],
]:
    if isinstance(receipts, (str, bytes, bytearray)) or not isinstance(receipts, Sequence):
        raise ValueError("source_availability_receipts must be a sequence")
    if not receipts:
        raise ValueError("source_availability_receipts must not be empty")
    source_index: dict[tuple[str, str, str, str, str], tuple[str, str]] = {}
    receipt_hashes: list[str] = []
    for receipt_index, raw_receipt in enumerate(receipts):
        if not isinstance(raw_receipt, Mapping):
            raise ValueError(f"source_availability_receipts[{receipt_index}] must be a mapping")
        receipt = dict(raw_receipt)
        valid, validation_errors = validate_stock_analysis_source_availability_receipt(
            receipt
        )
        if not valid:
            detail = "; ".join(validation_errors) or "unknown validation error"
            raise ValueError(
                f"source_availability_receipts[{receipt_index}] failed formal validation: {detail}"
            )
        canonical_receipt_sha256 = _sha256_text(
            receipt.get("canonical_receipt_sha256"),
            field_name=(
                f"source_availability_receipts[{receipt_index}].canonical_receipt_sha256"
            ),
        )
        raw_sources = receipt.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources:  # formally validated above
            raise AssertionError("validated source receipt must contain sources")
        for source_index_value, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, Mapping):
                raise ValueError(
                    f"source_availability_receipts[{receipt_index}].sources[{source_index_value}] must be a mapping"
                )
            key = (
                _required_text(raw_source.get("table"), field_name="source.table"),
                _required_text(
                    raw_source.get("source_version"), field_name="source.source_version"
                ),
                _optional_text(raw_source.get("vendor_version")) or "",
                _optional_text(raw_source.get("rule_version")) or "",
                _required_text(raw_source.get("run_id"), field_name="source.run_id"),
            )
            available_at = _date_text(
                raw_source.get("available_at"), field_name="source.available_at"
            )
            if key in source_index:
                raise ValueError("duplicate source availability key across receipts")
            source_index[key] = (available_at, canonical_receipt_sha256)
        receipt_hashes.append(canonical_receipt_sha256)
    if len(receipt_hashes) != len(set(receipt_hashes)):
        raise ValueError("duplicate source availability receipt")
    return source_index, tuple(sorted(receipt_hashes))


def _normalize_runner_results(
    runner_results: Sequence[Mapping[str, Any]],
    *,
    evaluation: str,
    version_tuple: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if isinstance(runner_results, (str, bytes, bytearray)) or not isinstance(
        runner_results, Sequence
    ):
        raise ValueError("runner_results must be a sequence")
    if not runner_results:
        raise ValueError("runner_results must not be empty")
    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    seen_dates: set[str] = set()
    expected_policy = version_tuple.get("stock_candidate_selection_policy")
    expected_formula = version_tuple.get("stock_candidate_selection_formula_version")
    for index, raw_runner in enumerate(runner_results):
        if not isinstance(raw_runner, Mapping):
            raise ValueError(f"runner_results[{index}] must be a mapping")
        runner = dict(raw_runner)
        trade_date = _date_text(
            runner.get("trade_date") or runner.get("requested_as_of_date"),
            field_name=f"runner_results[{index}].trade_date",
        )
        status = _optional_text(runner.get("status"))
        if status not in RUNNER_STATUSES:
            raise ValueError(f"runner_results[{index}].status is unsupported")
        if trade_date in seen_dates:
            raise ValueError(f"duplicate runner trade_date: {trade_date}")
        seen_dates.add(trade_date)
        if trade_date > evaluation:
            blockers.append(f"runner_trade_date_after_evaluation:{trade_date}")
        if runner.get("requested_as_of_date") != trade_date:
            blockers.append(f"runner_requested_date_mismatch:{trade_date}")
        if runner.get("resolved_as_of_date") != trade_date:
            blockers.append(f"runner_resolved_date_mismatch:{trade_date}")
        if runner.get("requested_matches_resolved") is not True:
            blockers.append(f"runner_not_fresh_exact_date:{trade_date}")
        if status in {SIGNAL_STATUS, ZERO_STATUS}:
            if runner.get("rule_tuple_matches") is not True:
                blockers.append(f"runner_rule_tuple_mismatch:{trade_date}")
            if runner.get("selection_policy") != expected_policy:
                blockers.append(f"runner_selection_policy_mismatch:{trade_date}")
            if runner.get("stock_candidate_formula_version") != expected_formula:
                blockers.append(f"runner_formula_version_mismatch:{trade_date}")
        if (
            status == POLICY_INACTIVE_STATUS
            and _optional_text(runner.get("status_reason")) != POLICY_INACTIVE_STATUS
        ):
            blockers.append(f"runner_policy_inactive_reason_missing:{trade_date}")
        if _sequence_length(runner.get("future_business_date_violations")):
            blockers.append(f"runner_future_business_date_violation:{trade_date}")
        if _sequence_length(runner.get("future_availability_violations")):
            blockers.append(f"runner_future_availability_violation:{trade_date}")
        if _sequence_length(runner.get("blockers")):
            blockers.append(f"runner_blockers_present:{trade_date}")
        if status in {UNSUPPORTED_STATUS, LOADER_ERROR_STATUS}:
            blockers.append(f"runner_status_blocked:{trade_date}:{status}")

        accepted_codes = _accepted_codes(runner.get("accepted_candidate_codes"))
        if len(accepted_codes) != _int_value(
            runner.get("accepted_candidate_count"), default=-1
        ):
            blockers.append(f"runner_accepted_candidate_count_mismatch:{trade_date}")
        if status == SIGNAL_STATUS and not accepted_codes:
            blockers.append(f"runner_signal_candidates_empty:{trade_date}")
        if status != SIGNAL_STATUS and accepted_codes:
            blockers.append(f"runner_non_signal_candidates_present:{trade_date}")
            accepted_codes = []
        normalized.append(
            {
                "trade_date": trade_date,
                "status": status,
                "status_reason": _optional_text(runner.get("status_reason")),
                "accepted_candidate_codes": sorted(accepted_codes),
            }
        )
    normalized.sort(key=lambda item: item["trade_date"])
    return normalized, _ordered(blockers)


def _factor_table_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    tables = {
        str(row[0])
        for row in conn.execute(
            "select table_name from information_schema.tables where table_schema = 'main'"
        ).fetchall()
    }
    if FACTOR_TABLE not in tables:
        raise ValueError("stock_adjustment_factor_table_missing")
    columns = {str(row[1]) for row in conn.execute(f"pragma table_info('{FACTOR_TABLE}')").fetchall()}
    required = {"stock_code", "trade_date", "adj_factor", "source_version", "run_id"}
    missing = sorted(required.difference(columns))
    if missing:
        raise ValueError("stock_adjustment_factor_schema_missing:" + ",".join(missing))
    return columns


def _execution_role_dates(
    *,
    signal_date: str,
    stock_code: str,
    execution: Mapping[str, Any] | None,
    evaluation: str,
) -> dict[str, str | None]:
    raw_dates: dict[str, object] = {
        "signal": signal_date,
        "entry": execution.get("entry_date") if isinstance(execution, Mapping) else None,
        "exit_1d": execution.get("exit_date_1d") if isinstance(execution, Mapping) else None,
        "exit_5d": execution.get("exit_date_5d") if isinstance(execution, Mapping) else None,
        "exit_10d": execution.get("exit_date_10d") if isinstance(execution, Mapping) else None,
        "exit_20d": execution.get("exit_date_20d") if isinstance(execution, Mapping) else None,
    }
    resolved: dict[str, str | None] = {}
    for role, raw_date in raw_dates.items():
        if raw_date is None or not str(raw_date).strip():
            resolved[role] = None
            continue
        try:
            parsed = _date_text(raw_date, field_name=f"execution.{role}_date")
        except ValueError as exc:
            raise ValueError(
                f"execution_role_date_invalid:{signal_date}:{stock_code}:{role}"
            ) from exc
        resolved[role] = parsed if parsed <= evaluation else None
    return resolved


def _build_candidate_cell(
    *,
    conn: duckdb.DuckDBPyConnection,
    factor_columns: set[str],
    signal_date: str,
    stock_code: str,
    role: str,
    factor_date: str | None,
    execution_data_status: str,
    source_index: Mapping[tuple[str, str, str, str, str], tuple[str, str]],
    evaluation: str,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "signal_date": signal_date,
        "stock_code": stock_code,
        "role": role,
        "factor_date": factor_date,
        "physical_cell_key": (
            {"stock_code": stock_code, "trade_date": factor_date}
            if factor_date is not None
            else None
        ),
        "execution_data_status": execution_data_status,
        "strict_exact_date_lookup": True,
    }
    if factor_date is None:
        return {
            **base,
            "status": "date_unresolved",
            "adj_factor": None,
            "source_identity": None,
            "available_at": None,
            "source_receipt_match": False,
            "source_receipt_sha256": None,
            "observed_row_count": 0,
            "distinct_observation_count": 0,
        }
    vendor_expr = (
        "coalesce(trim(cast(vendor_version as varchar)), '')"
        if "vendor_version" in factor_columns
        else "''"
    )
    rule_expr = (
        "coalesce(trim(cast(rule_version as varchar)), '')"
        if "rule_version" in factor_columns
        else "''"
    )
    rows = conn.execute(
        f"""
        select adj_factor,
               coalesce(trim(cast(source_version as varchar)), ''),
               {vendor_expr},
               {rule_expr},
               coalesce(trim(cast(run_id as varchar)), '')
        from {FACTOR_TABLE}
        where upper(trim(cast(stock_code as varchar))) = ?
          and try_cast(trade_date as date) = cast(? as date)
        """,
        [stock_code, factor_date],
    ).fetchall()
    if not rows:
        return {
            **base,
            "status": "missing",
            "adj_factor": None,
            "source_identity": None,
            "available_at": None,
            "source_receipt_match": False,
            "source_receipt_sha256": None,
            "observed_row_count": 0,
            "distinct_observation_count": 0,
        }
    normalized_rows = sorted(
        {
            (
                _factor_value_token(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
            )
            for row in rows
        },
        key=lambda item: tuple(str(value) for value in item),
    )
    if len(normalized_rows) != 1:
        return {
            **base,
            "status": "ambiguous",
            "adj_factor": None,
            "source_identity": None,
            "available_at": None,
            "source_receipt_match": False,
            "source_receipt_sha256": None,
            "observed_row_count": len(rows),
            "distinct_observation_count": len(normalized_rows),
            "observed_candidates": [
                {
                    "adj_factor": item[0],
                    "source_version": item[1],
                    "vendor_version": item[2],
                    "rule_version": item[3],
                    "run_id": item[4],
                }
                for item in normalized_rows
            ],
        }
    factor_token, source_version, vendor_version, rule_version, run_id = normalized_rows[0]
    factor = factor_token if isinstance(factor_token, float) else None
    source_identity = {
        "table": FACTOR_TABLE,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": rule_version,
        "run_id": run_id,
    }
    if factor is None or not _is_positive_finite(factor):
        cell_status = "invalid"
        available_at = None
        source_receipt_sha256 = None
        receipt_match = False
    else:
        source_key = (
            FACTOR_TABLE,
            source_version,
            vendor_version,
            rule_version,
            run_id,
        )
        source_binding = source_index.get(source_key)
        receipt_match = source_binding is not None
        if not receipt_match:
            available_at = None
            source_receipt_sha256 = None
            cell_status = "present_source_unproven"
        else:
            assert source_binding is not None
            available_at, source_receipt_sha256 = source_binding
            if available_at > evaluation:
                cell_status = "present_after_evaluation"
            else:
                cell_status = "present_pit_usable"
    return {
        **base,
        "status": cell_status,
        "adj_factor": factor,
        "source_identity": source_identity,
        "available_at": available_at,
        "source_receipt_match": receipt_match,
        "source_receipt_sha256": source_receipt_sha256,
        "observed_row_count": len(rows),
        "distinct_observation_count": 1,
    }


def _missing_unique_cells(candidate_cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for cell in candidate_cells:
        factor_date = cell.get("factor_date")
        if cell.get("status") == "present_pit_usable" or factor_date is None:
            continue
        grouped[(str(cell.get("stock_code")), str(factor_date))].append(cell)
    result: list[dict[str, Any]] = []
    for (stock_code, factor_date), cells in sorted(grouped.items()):
        statuses = sorted({str(cell.get("status")) for cell in cells})
        references = sorted(
            (
                {
                    "signal_date": str(cell.get("signal_date")),
                    "role": str(cell.get("role")),
                }
                for cell in cells
            ),
            key=lambda item: (item["signal_date"], CELL_ROLES.index(item["role"])),
        )
        result.append(
            {
                "stock_code": stock_code,
                "trade_date": factor_date,
                "physical_cell_key": {"stock_code": stock_code, "trade_date": factor_date},
                "status": statuses[0] if len(statuses) == 1 else "ambiguous",
                "cell_statuses": statuses,
                "occurrence_count": len(cells),
                "candidate_references": references,
                "remediation_action": "supply_or_reconcile_exact_date_factor_with_attested_source",
            }
        )
    return result


def _accepted_codes(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    normalized = [_stock_code(item, field_name="accepted_candidate_codes") for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError("accepted_candidate_codes must be unique")
    return normalized


def _factor_value_token(value: object) -> float | str | None:
    if value is None:
        return None
    try:
        parsed = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(parsed):
        return "NaN" if math.isnan(parsed) else ("Infinity" if parsed > 0 else "-Infinity")
    return parsed


def _is_positive_finite(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        parsed = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError):
        return False
    return math.isfinite(parsed) and parsed > 0


def _sequence_length(value: object) -> int:
    return len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else 0


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(cast(str | bytes | bytearray | SupportsInt | SupportsIndex, value))
    except (TypeError, ValueError):
        return default


def _ordered(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _stock_code(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name).upper()
    if any(character.isspace() for character in normalized):
        raise ValueError(f"{field_name} must not contain whitespace")
    return normalized


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


def _date_text(value: object, *, field_name: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _aware_datetime_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.isoformat()


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field_name} must use UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name).upper()
    if len(normalized) != 64 or any(character not in "0123456789ABCDEF" for character in normalized):
        raise ValueError(f"{field_name} must be an uppercase sha256")
    return normalized


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_sha256(payload: Mapping[str, object]) -> str:
    content = dict(payload)
    content.pop("canonical_manifest_sha256", None)
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()
