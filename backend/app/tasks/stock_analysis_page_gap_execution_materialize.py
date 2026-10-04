"""Governed page-exact adjusted-return materializer for ``/stock-analysis``.

The task consumes the observational page-gap manifest and the completed
page-gap factor-write receipt.  It never rebuilds or deletes execution rows.
Only missing adjusted gross/net fields for the manifest's exact logical keys
and their audit evidence are eligible for change.

The factor receipt proves capture-time physical remediation only.  This task
therefore closes legacy physical nulls without claiming point-in-time
availability, formal historical replay eligibility, or strategy certification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat as stat_module
import tempfile
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from backend.app.core_finance.adjusted_returns import (
    PRICE_ADJUSTMENT_MODE,
    adjusted_return,
    net_return_after_costs,
)
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks.livermore_candidate_history_materialize import (
    LIVERMORE_CANDIDATE_HISTORY_LOCK,
)
from backend.app.tasks.stock_analysis_page_gap_manifest import (
    MANIFEST_KIND as PAGE_MANIFEST_KIND,
)
from backend.app.tasks.stock_analysis_page_gap_manifest import (
    PAGE_ID,
    PAGE_METRIC_KEY,
    PAGE_ROUTE,
    validate_stock_analysis_page_gap_manifest,
)

SCHEMA_VERSION = 1
PLAN_KIND = "stock_analysis_page_gap_execution_materialization_plan_v1"
RECEIPT_KIND = "stock_analysis_page_gap_execution_materialization_receipt_v1"
PENDING_INTENT_KIND = "stock_analysis_page_gap_execution_materialization_pending_intent_v1"
FACTOR_WRITE_RECEIPT_KIND = "stock_analysis_page_gap_factor_write_receipt_v1"
FACTOR_WRITE_COMPLETED_STATUS = "physical_factor_remediation_completed"
READY_STATUS = "ready"
ALREADY_COMPLETE_STATUS = "already_complete"
COMPLETED_STATUS = "materialization_completed"
PENDING_STATUS = "materialization_pending"
MATERIALIZER_RULE_VERSION = "rv_stock_analysis_page_gap_execution_materialize_v1"
EXECUTION_TABLE = "livermore_candidate_execution_history"
FACTOR_TABLE = "stock_adjustment_factor"
APPROVAL_SCOPE = "page_manifest_exact_execution_keys_and_horizons_only"
EVIDENCE_TRACE_KEY = "page_gap_adjusted_return_materialization"
FACTOR_BATCH_SIZE = 400
_SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
_STOCK_CODE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")
_FLOAT_TOLERANCE = 1e-12

_HORIZONS: tuple[dict[str, str | int], ...] = (
    {
        "label": "1d",
        "days": 1,
        "exit_date_col": "exit_date_1d",
        "exit_price_col": "exit_price_1d",
        "raw_net_col": "return_1d_net",
        "gross_adj_col": "return_1d_gross_adj",
        "net_adj_col": "return_1d_net_adj",
    },
    {
        "label": "5d",
        "days": 5,
        "exit_date_col": "exit_date_5d",
        "exit_price_col": "exit_price_5d",
        "raw_net_col": "return_5d_net",
        "gross_adj_col": "return_5d_gross_adj",
        "net_adj_col": "return_5d_net_adj",
    },
    {
        "label": "10d",
        "days": 10,
        "exit_date_col": "exit_date_10d",
        "exit_price_col": "exit_price_10d",
        "raw_net_col": "return_10d_net",
        "gross_adj_col": "return_10d_gross_adj",
        "net_adj_col": "return_10d_net_adj",
    },
    {
        "label": "20d",
        "days": 20,
        "exit_date_col": "exit_date_20d",
        "exit_price_col": "exit_price_20d",
        "raw_net_col": "return_20d_net",
        "gross_adj_col": "return_20d_gross_adj",
        "net_adj_col": "return_20d_net_adj",
    },
)
_HORIZON_BY_DAYS = {int(item["days"]): item for item in _HORIZONS}
_HORIZON_LABELS = tuple(str(item["label"]) for item in _HORIZONS)
_SOURCE_ROW_HASH_FIELDS = (
    "signal_date",
    "stock_code",
    "signal_kind",
    "stock_name",
    "candidate_rank",
    "market_state",
    "data_status",
    "formula_version",
    "run_id",
    "signal_close",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "raw_return_net",
    "adjusted_return_net",
    "horizon_label",
    "horizon_days",
)
_REQUIRED_EXECUTION_COLUMNS = {
    "signal_date",
    "stock_code",
    "stock_name",
    "signal_kind",
    "candidate_rank",
    "market_state",
    "signal_close",
    "entry_date",
    "entry_price",
    "buy_cost_bps",
    "sell_cost_bps",
    "slippage_bps",
    "price_adjustment_mode",
    "data_status",
    "formula_version",
    "run_id",
    "evidence_json",
}
for _horizon in _HORIZONS:
    _REQUIRED_EXECUTION_COLUMNS.update(
        {
            str(_horizon["exit_date_col"]),
            str(_horizon["exit_price_col"]),
            str(_horizon["raw_net_col"]),
            str(_horizon["gross_adj_col"]),
            str(_horizon["net_adj_col"]),
        }
    )


class PageGapExecutionMaterializeError(ValueError):
    """Raised when page-exact materialization cannot proceed safely."""


def build_stock_analysis_page_gap_execution_materialization_plan_from_files(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    page_manifest_file: str | Path,
    factor_write_receipt_file: str | Path,
    created_at: str,
) -> dict[str, Any]:
    """Load governed inputs and build a read-only, full-scope dry-run plan."""

    target, trusted_root, page_path, factor_receipt_path = _validated_input_paths(
        duckdb_path=duckdb_path,
        trusted_evidence_root=trusted_evidence_root,
        page_manifest_file=page_manifest_file,
        factor_write_receipt_file=factor_write_receipt_file,
    )
    return build_stock_analysis_page_gap_execution_materialization_plan(
        duckdb_path=target,
        page_manifest=_load_json_object(page_path, field_name="page_manifest_file"),
        page_manifest_path=page_path,
        page_manifest_file_sha256=_file_sha256(page_path),
        factor_write_receipt=_load_json_object(
            factor_receipt_path,
            field_name="factor_write_receipt_file",
        ),
        factor_write_receipt_path=factor_receipt_path,
        factor_write_receipt_file_sha256=_file_sha256(factor_receipt_path),
        created_at=created_at,
        trusted_evidence_root=trusted_root,
    )


def build_stock_analysis_page_gap_execution_materialization_plan(
    *,
    duckdb_path: str | Path,
    page_manifest: Mapping[str, object],
    page_manifest_path: str | Path,
    page_manifest_file_sha256: str,
    factor_write_receipt: Mapping[str, object],
    factor_write_receipt_path: str | Path,
    factor_write_receipt_file_sha256: str,
    created_at: str,
    trusted_evidence_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build the exact plan without mutating DuckDB or the filesystem."""

    target = _existing_file_no_links(duckdb_path, field_name="duckdb_path")
    created_at_text = _utc_datetime_text(created_at, field_name="created_at")
    page_path = _existing_file_no_links(page_manifest_path, field_name="page_manifest_path")
    factor_receipt_path = _existing_file_no_links(
        factor_write_receipt_path,
        field_name="factor_write_receipt_path",
    )
    if trusted_evidence_root is not None:
        root = _existing_directory_no_links(
            trusted_evidence_root,
            field_name="trusted_evidence_root",
        )
        _assert_path_within(root, page_path, field_name="page_manifest_path")
        _assert_path_within(root, factor_receipt_path, field_name="factor_write_receipt_path")

    page_file_sha = _sha256_text(
        page_manifest_file_sha256,
        field_name="page_manifest_file_sha256",
    )
    factor_file_sha = _sha256_text(
        factor_write_receipt_file_sha256,
        field_name="factor_write_receipt_file_sha256",
    )
    if _file_sha256(page_path) != page_file_sha:
        raise PageGapExecutionMaterializeError("page manifest file SHA does not match supplied binding")
    if _file_sha256(factor_receipt_path) != factor_file_sha:
        raise PageGapExecutionMaterializeError("factor write receipt file SHA does not match supplied binding")

    page = _validated_page_manifest(page_manifest)
    factor_receipt = _validated_factor_write_receipt(factor_write_receipt)
    bindings = _validated_cross_bindings(
        target=target,
        page=page,
        page_path=page_path,
        page_file_sha=page_file_sha,
        factor_receipt=factor_receipt,
        factor_receipt_path=factor_receipt_path,
        factor_file_sha=factor_file_sha,
    )
    targets = _targets_from_page_manifest(page)
    current_sha = _file_sha256(target)

    with duckdb.connect(str(target), read_only=True) as conn:
        analysis = _analyze_database_state(
            conn,
            page=page,
            targets=targets,
            factor_receipt=factor_receipt,
            bindings=bindings,
        )
    current_sha_after_analysis = _file_sha256(target)
    if current_sha_after_analysis != current_sha:
        raise PageGapExecutionMaterializeError("DuckDB changed during read-only materialization analysis")

    state = str(analysis["state"])
    factor_sha_after = str(bindings["factor_database_sha256_after"])
    if state == READY_STATUS and current_sha != factor_sha_after:
        raise PageGapExecutionMaterializeError("current DuckDB SHA does not match factor write receipt after SHA")
    if state not in {READY_STATUS, ALREADY_COMPLETE_STATUS}:
        raise PageGapExecutionMaterializeError("execution targets are partially materialized or inconsistent")

    target_keys = [item["key"] for item in analysis["targets"]]
    target_horizon_scope = [
        {
            "signal_date": item["key"]["signal_date"],
            "stock_code": item["key"]["stock_code"],
            "signal_kind": item["key"]["signal_kind"],
            "horizon_days": horizon["horizon_days"],
            "gap_view_id": horizon["gap_view_id"],
            "source_row_sha256": horizon["source_row_sha256"],
        }
        for item in analysis["targets"]
        for horizon in item["horizons"]
    ]
    calculation_outputs = [
        {
            "signal_date": item["key"]["signal_date"],
            "stock_code": item["key"]["stock_code"],
            "signal_kind": item["key"]["signal_kind"],
            "horizon_days": horizon["horizon_days"],
            "entry_factor": horizon["entry_factor"],
            "exit_factor": horizon["exit_factor"],
            "buy_cost_bps": horizon["buy_cost_bps"],
            "sell_cost_bps": horizon["sell_cost_bps"],
            "slippage_bps": horizon["slippage_bps"],
            "computed_adjusted_gross": horizon["computed_adjusted_gross"],
            "computed_adjusted_net": horizon["computed_adjusted_net"],
        }
        for item in analysis["targets"]
        for horizon in item["horizons"]
    ]
    target_execution_keys_sha256 = _canonical_json_sha256(target_keys)
    target_horizons_sha256 = _canonical_json_sha256(target_horizon_scope)
    calculation_outputs_sha256 = _canonical_json_sha256(calculation_outputs)
    approval_scope_sha256 = _materialization_approval_scope_sha256(
        page_manifest_canonical_sha256=str(bindings["page_manifest_canonical_sha256"]),
        page_manifest_file_sha256=page_file_sha,
        factor_write_receipt_canonical_sha256=str(bindings["factor_receipt_canonical_sha256"]),
        factor_write_receipt_file_sha256=factor_file_sha,
        factor_database_sha256_after=factor_sha_after,
        target_execution_keys_sha256=target_execution_keys_sha256,
        target_horizons_sha256=target_horizons_sha256,
        calculation_outputs_sha256=calculation_outputs_sha256,
        target_execution_key_count=len(target_keys),
        target_gap_horizon_count=len(target_horizon_scope),
    )
    if state == ALREADY_COMPLETE_STATUS:
        _assert_completed_evidence_bindings(
            analysis=analysis,
            page_manifest_canonical_sha256=str(bindings["page_manifest_canonical_sha256"]),
            factor_receipt_canonical_sha256=str(bindings["factor_receipt_canonical_sha256"]),
            factor_receipt_file_sha256=factor_file_sha,
            approval_scope_sha256=approval_scope_sha256,
            target_execution_keys_sha256=target_execution_keys_sha256,
            target_horizons_sha256=target_horizons_sha256,
            calculation_outputs_sha256=calculation_outputs_sha256,
        )

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "plan_kind": PLAN_KIND,
        "status": state,
        "created_at": created_at_text,
        "page_id": PAGE_ID,
        "page_route": PAGE_ROUTE,
        "page_metric_key": PAGE_METRIC_KEY,
        "materializer_rule_version": MATERIALIZER_RULE_VERSION,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": approval_scope_sha256,
        "database_write_executed": False,
        "read_only": True,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "page_manifest_binding": {
            "path": str(page_path),
            "file_sha256": page_file_sha,
            "canonical_manifest_sha256": bindings["page_manifest_canonical_sha256"],
            "manifest_kind": PAGE_MANIFEST_KIND,
            "database_sha256": bindings["page_database_sha256"],
        },
        "factor_write_receipt_binding": {
            "path": str(factor_receipt_path),
            "file_sha256": factor_file_sha,
            "canonical_write_receipt_sha256": bindings["factor_receipt_canonical_sha256"],
            "receipt_kind": FACTOR_WRITE_RECEIPT_KIND,
            "database_sha256_before": bindings["factor_database_sha256_before"],
            "database_sha256_after": factor_sha_after,
            "target_cell_count": bindings["factor_target_cell_count"],
            "target_cells_sha256": bindings["factor_target_cells_sha256"],
            "target_rows_sha256": bindings["factor_target_rows_sha256"],
        },
        "database": {
            "path": str(target),
            "factor_write_after_sha256": factor_sha_after,
            "current_sha256": current_sha,
            "at_factor_write_boundary": current_sha == factor_sha_after,
            "read_only": True,
        },
        "rollback_anchor": dict(bindings["backup"]),
        "summary": {
            "target_execution_key_count": len(target_keys),
            "clearable_execution_key_count": len(target_keys),
            "target_gap_horizon_count": len(target_horizon_scope),
            "clearable_gap_horizon_count": len(target_horizon_scope),
            "pending_update_field_count": int(analysis["pending_update_field_count"]),
            "page_gap_view_count_before_manifest": len(target_horizon_scope),
            "current_page_gap_view_count": int(analysis["global_gap_counts"]["total"]),
            "projected_page_gap_view_count_after": 0,
            "row_count_before": int(analysis["row_count"]),
            "logical_duplicate_key_count": 0,
            "horizon_counts_before_manifest": _horizon_count_rows(target_horizon_scope),
            "current_horizon_gap_counts": _horizon_count_rows_from_mapping(analysis["global_gap_counts"]),
            "projected_horizon_gap_counts_after": [{"value": label, "count": 0} for label in _HORIZON_LABELS],
            "signal_kind_counts": _signal_kind_count_rows(target_keys),
        },
        "target_scope": {
            "target_execution_keys_sha256": target_execution_keys_sha256,
            "target_horizons_sha256": target_horizons_sha256,
            "calculation_outputs_sha256": calculation_outputs_sha256,
            "target_invariant_rows_sha256_before": analysis["target_invariant_rows_sha256"],
            "non_target_rows_sha256_before": analysis["non_target_rows_sha256"],
        },
        "targets": analysis["targets"],
        "blockers": [],
    }
    plan["canonical_plan_sha256"] = _plan_sha256(plan)
    valid, errors = validate_stock_analysis_page_gap_execution_materialization_plan(plan)
    if not valid:
        raise PageGapExecutionMaterializeError("generated materialization plan failed validation: " + "; ".join(errors))
    return plan


def validate_stock_analysis_page_gap_execution_materialization_plan(
    plan: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    """Validate a complete dry-run plan and its approval-scope binding."""

    if not isinstance(plan, Mapping):
        return False, ("plan must be a mapping",)
    payload = dict(plan)
    errors: list[str] = []
    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("plan_kind", PLAN_KIND),
        ("page_id", PAGE_ID),
        ("page_route", PAGE_ROUTE),
        ("page_metric_key", PAGE_METRIC_KEY),
        ("materializer_rule_version", MATERIALIZER_RULE_VERSION),
        ("approval_scope", APPROVAL_SCOPE),
        ("database_write_executed", False),
        ("read_only", True),
        ("historical_availability_proven", False),
        ("formal_historical_replay_use_allowed", False),
        ("certification_allowed", False),
    ):
        if payload.get(field_name) != expected:
            errors.append(f"plan.{field_name} mismatch")
    if payload.get("status") not in {READY_STATUS, ALREADY_COMPLETE_STATUS}:
        errors.append("plan.status is invalid")
    try:
        if payload.get("created_at") != _utc_datetime_text(payload.get("created_at"), field_name="plan.created_at"):
            errors.append("plan.created_at is not canonical UTC")
    except ValueError as exc:
        errors.append(str(exc))

    targets_raw = payload.get("targets")
    if not isinstance(targets_raw, list):
        errors.append("plan.targets must be a list")
        targets: list[Mapping[str, Any]] = []
    else:
        targets = [item for item in targets_raw if isinstance(item, Mapping)]
        if len(targets) != len(targets_raw):
            errors.append("plan.targets must contain only mappings")

    key_payloads: list[dict[str, str]] = []
    horizon_payloads: list[dict[str, Any]] = []
    calculation_payloads: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    seen_horizons: set[tuple[str, str, str, int]] = set()
    pending_update_field_count = 0
    for index, target in enumerate(targets):
        key = target.get("key")
        horizons = target.get("horizons")
        if not isinstance(key, Mapping) or not isinstance(horizons, list):
            errors.append(f"plan.targets[{index}] has invalid key or horizons")
            continue
        try:
            normalized_key = {
                "signal_date": _iso_date_text(key.get("signal_date"), field_name=f"targets[{index}].signal_date"),
                "stock_code": _stock_code(key.get("stock_code"), field_name=f"targets[{index}].stock_code"),
                "signal_kind": _required_text(key.get("signal_kind"), field_name=f"targets[{index}].signal_kind"),
            }
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key_tuple = (
            normalized_key["signal_date"],
            normalized_key["stock_code"],
            normalized_key["signal_kind"],
        )
        if key_tuple in seen_keys:
            errors.append("plan.targets contains duplicate execution key")
        seen_keys.add(key_tuple)
        key_payloads.append(normalized_key)
        for horizon_index, raw_horizon in enumerate(horizons):
            if not isinstance(raw_horizon, Mapping):
                errors.append(f"plan.targets[{index}].horizons[{horizon_index}] must be a mapping")
                continue
            horizon = dict(raw_horizon)
            days = horizon.get("horizon_days")
            if days not in _HORIZON_BY_DAYS:
                errors.append("plan target horizon_days is invalid")
                continue
            natural_horizon = (*key_tuple, int(days))
            if natural_horizon in seen_horizons:
                errors.append("plan.targets contains duplicate target horizon")
            seen_horizons.add(natural_horizon)
            try:
                gap_view_id = _sha256_text(horizon.get("gap_view_id"), field_name="target.gap_view_id")
                source_row_sha = _sha256_text(
                    horizon.get("source_row_sha256"),
                    field_name="target.source_row_sha256",
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            update_fields = horizon.get("update_fields")
            if not isinstance(update_fields, list) or any(not isinstance(item, str) for item in update_fields):
                errors.append("target.update_fields must be a string list")
                update_fields = []
            pending_update_field_count += len(update_fields)
            horizon_payloads.append(
                {
                    **normalized_key,
                    "horizon_days": int(days),
                    "gap_view_id": gap_view_id,
                    "source_row_sha256": source_row_sha,
                }
            )
            calculation_payloads.append(
                {
                    **normalized_key,
                    "horizon_days": int(days),
                    "entry_factor": horizon.get("entry_factor"),
                    "exit_factor": horizon.get("exit_factor"),
                    "buy_cost_bps": horizon.get("buy_cost_bps"),
                    "sell_cost_bps": horizon.get("sell_cost_bps"),
                    "slippage_bps": horizon.get("slippage_bps"),
                    "computed_adjusted_gross": horizon.get("computed_adjusted_gross"),
                    "computed_adjusted_net": horizon.get("computed_adjusted_net"),
                }
            )

    summary = payload.get("summary")
    target_scope = payload.get("target_scope")
    factor_binding = payload.get("factor_write_receipt_binding")
    page_binding = payload.get("page_manifest_binding")
    if not isinstance(summary, Mapping):
        errors.append("plan.summary must be a mapping")
    else:
        expected_counts = {
            "target_execution_key_count": len(key_payloads),
            "clearable_execution_key_count": len(key_payloads),
            "target_gap_horizon_count": len(horizon_payloads),
            "clearable_gap_horizon_count": len(horizon_payloads),
            "pending_update_field_count": pending_update_field_count,
            "page_gap_view_count_before_manifest": len(horizon_payloads),
            "projected_page_gap_view_count_after": 0,
            "logical_duplicate_key_count": 0,
        }
        for name, expected in expected_counts.items():
            if summary.get(name) != expected:
                errors.append(f"plan.summary.{name} mismatch")
        if payload.get("status") == READY_STATUS:
            if summary.get("current_page_gap_view_count") != len(horizon_payloads):
                errors.append("ready plan current page gap count must equal target horizon count")
            if pending_update_field_count < len(horizon_payloads):
                errors.append("ready plan must update every missing adjusted net")
        elif payload.get("status") == ALREADY_COMPLETE_STATUS:
            if summary.get("current_page_gap_view_count") != 0:
                errors.append("already-complete plan current page gap count must be zero")
            if pending_update_field_count != 0:
                errors.append("already-complete plan cannot contain updates")

    if not isinstance(target_scope, Mapping):
        errors.append("plan.target_scope must be a mapping")
    else:
        expected_hashes = {
            "target_execution_keys_sha256": _canonical_json_sha256(key_payloads),
            "target_horizons_sha256": _canonical_json_sha256(horizon_payloads),
            "calculation_outputs_sha256": _canonical_json_sha256(calculation_payloads),
        }
        for name, expected in expected_hashes.items():
            if target_scope.get(name) != expected:
                errors.append(f"plan.target_scope.{name} mismatch")

    if not isinstance(page_binding, Mapping) or not isinstance(factor_binding, Mapping):
        errors.append("plan input bindings must be mappings")
    elif isinstance(target_scope, Mapping):
        try:
            expected_scope = _materialization_approval_scope_sha256(
                page_manifest_canonical_sha256=_sha256_text(
                    page_binding.get("canonical_manifest_sha256"),
                    field_name="page binding canonical SHA",
                ),
                page_manifest_file_sha256=_sha256_text(
                    page_binding.get("file_sha256"), field_name="page binding file SHA"
                ),
                factor_write_receipt_canonical_sha256=_sha256_text(
                    factor_binding.get("canonical_write_receipt_sha256"),
                    field_name="factor receipt canonical SHA",
                ),
                factor_write_receipt_file_sha256=_sha256_text(
                    factor_binding.get("file_sha256"),
                    field_name="factor receipt file SHA",
                ),
                factor_database_sha256_after=_sha256_text(
                    factor_binding.get("database_sha256_after"),
                    field_name="factor receipt database after SHA",
                ),
                target_execution_keys_sha256=_sha256_text(
                    target_scope.get("target_execution_keys_sha256"),
                    field_name="target execution keys SHA",
                ),
                target_horizons_sha256=_sha256_text(
                    target_scope.get("target_horizons_sha256"),
                    field_name="target horizons SHA",
                ),
                calculation_outputs_sha256=_sha256_text(
                    target_scope.get("calculation_outputs_sha256"),
                    field_name="calculation outputs SHA",
                ),
                target_execution_key_count=len(key_payloads),
                target_gap_horizon_count=len(horizon_payloads),
            )
            if payload.get("approval_scope_sha256") != expected_scope:
                errors.append("plan.approval_scope_sha256 mismatch")
        except ValueError as exc:
            errors.append(str(exc))

    try:
        observed_plan_sha = _sha256_text(
            payload.get("canonical_plan_sha256"),
            field_name="plan.canonical_plan_sha256",
        )
        if observed_plan_sha != _plan_sha256(payload):
            errors.append("plan.canonical_plan_sha256 mismatch")
    except ValueError as exc:
        errors.append(str(exc))
    return not errors, tuple(errors)


def materialize_stock_analysis_page_gap_execution_history(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    page_manifest_file: str | Path,
    factor_write_receipt_file: str | Path,
    write_receipt_file: str | Path,
    executed_at: str,
    approval_reference: str,
    expected_materialization_approval_scope_sha256: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Materialize the exact approved page gaps in one DuckDB transaction."""

    if allow_write is not True:
        raise PageGapExecutionMaterializeError("allow_write must be explicitly true")
    executed_at_text = _utc_datetime_text(executed_at, field_name="executed_at")
    approval_text = _required_text(approval_reference, field_name="approval_reference")
    expected_scope = _sha256_text(
        expected_materialization_approval_scope_sha256,
        field_name="expected_materialization_approval_scope_sha256",
    )
    target, trusted_root, page_path, factor_receipt_path = _validated_input_paths(
        duckdb_path=duckdb_path,
        trusted_evidence_root=trusted_evidence_root,
        page_manifest_file=page_manifest_file,
        factor_write_receipt_file=factor_write_receipt_file,
    )
    output_path = _new_json_path_within_root(
        trusted_root=trusted_root,
        path=write_receipt_file,
        field_name="write_receipt_file",
    )

    writer_lock = resolve_duckdb_writer_lock(target)
    # Fixed global order: path-scoped writer lock, then Livermore history lock.
    with ExitStack() as lock_stack:
        lock_stack.enter_context(acquire_lock(writer_lock, base_dir=target.parent))
        lock_stack.enter_context(acquire_lock(LIVERMORE_CANDIDATE_HISTORY_LOCK, base_dir=target.parent))
        plan = build_stock_analysis_page_gap_execution_materialization_plan_from_files(
            duckdb_path=target,
            trusted_evidence_root=trusted_root,
            page_manifest_file=page_path,
            factor_write_receipt_file=factor_receipt_path,
            created_at=executed_at_text,
        )
        if plan["approval_scope_sha256"] != expected_scope:
            raise PageGapExecutionMaterializeError(
                "expected materialization approval scope SHA does not match exact plan"
            )

        if plan["status"] == ALREADY_COMPLETE_STATUS:
            no_op_receipt = _build_already_complete_receipt(
                plan=plan,
                executed_at=executed_at_text,
                approval_reference=approval_text,
            )
            valid, errors = validate_stock_analysis_page_gap_execution_materialization_receipt(
                no_op_receipt,
                plan=plan,
            )
            if not valid:
                raise PageGapExecutionMaterializeError(
                    "generated already-complete receipt failed validation: " + "; ".join(errors)
                )
            _write_json_exclusive(output_path, payload=no_op_receipt)
            persisted_no_op = _load_json_object(
                output_path,
                field_name="write_receipt_file",
            )
            if persisted_no_op != no_op_receipt:
                raise PageGapExecutionMaterializeError(
                    "persisted already-complete receipt does not match generated receipt"
                )
            return persisted_no_op

        database_binding = _mapping(plan["database"], field_name="plan.database")
        h1 = _sha256_text(
            database_binding.get("factor_write_after_sha256"),
            field_name="plan.database.factor_write_after_sha256",
        )
        if _file_sha256(target) != h1:
            raise PageGapExecutionMaterializeError("DuckDB changed after live preflight and before pending intent")
        _assert_no_unmerged_duckdb_sidecars(target)
        _verify_rollback_anchor(plan=plan, target=target)

        materialization_run_id = f"stock_analysis_page_gap_materialize:{uuid.uuid4()}"
        pending_intent = _build_pending_intent(
            plan=plan,
            executed_at=executed_at_text,
            approval_reference=approval_text,
            materialization_run_id=materialization_run_id,
        )
        _write_json_exclusive(output_path, payload=pending_intent)
        if _load_json_object(output_path, field_name="pending write intent") != pending_intent:
            raise PageGapExecutionMaterializeError("persisted pending intent does not match generated intent")

        page = _load_json_object(page_path, field_name="page_manifest_file")
        factor_receipt = _load_json_object(
            factor_receipt_path,
            field_name="factor_write_receipt_file",
        )
        targets = _targets_from_page_manifest(page)
        page_file_sha = _file_sha256(page_path)
        factor_file_sha = _file_sha256(factor_receipt_path)
        bindings = _validated_cross_bindings(
            target=target,
            page=_validated_page_manifest(page),
            page_path=page_path,
            page_file_sha=page_file_sha,
            factor_receipt=_validated_factor_write_receipt(factor_receipt),
            factor_receipt_path=factor_receipt_path,
            factor_file_sha=factor_file_sha,
        )

        _assert_no_unmerged_duckdb_sidecars(target)
        if _file_sha256(target) != h1:
            raise PageGapExecutionMaterializeError("DuckDB changed after pending intent and before transaction")
        transaction_started = False
        pre_analysis: dict[str, Any] | None = None
        post_analysis: dict[str, Any] | None = None
        with duckdb.connect(str(target), read_only=False) as conn:
            try:
                conn.execute("begin transaction")
                transaction_started = True
                pre_analysis = _analyze_database_state(
                    conn,
                    page=page,
                    targets=targets,
                    factor_receipt=factor_receipt,
                    bindings=bindings,
                )
                if pre_analysis["state"] != READY_STATUS:
                    raise PageGapExecutionMaterializeError(
                        "transaction preflight no longer matches ready dry-run state"
                    )
                _assert_analysis_matches_plan(pre_analysis, plan=plan)
                expected_rows = _apply_exact_target_updates(
                    conn,
                    plan=plan,
                    before=pre_analysis,
                    materialization_run_id=materialization_run_id,
                    executed_at=executed_at_text,
                )
                post_analysis = _analyze_database_state(
                    conn,
                    page=page,
                    targets=targets,
                    factor_receipt=factor_receipt,
                    bindings=bindings,
                    expected_completion_evidence={
                        "materialization_run_id": materialization_run_id,
                        "approval_scope_sha256": expected_scope,
                        "executed_at": executed_at_text,
                        "target_execution_keys_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                            "target_execution_keys_sha256"
                        ],
                        "target_horizons_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                            "target_horizons_sha256"
                        ],
                        "calculation_outputs_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                            "calculation_outputs_sha256"
                        ],
                    },
                )
                _verify_transaction_postconditions(
                    conn,
                    plan=plan,
                    before=pre_analysis,
                    after=post_analysis,
                    expected_rows=expected_rows,
                )
                _assert_evidence_files_unchanged(
                    page_manifest_path=page_path,
                    page_manifest_file_sha256=page_file_sha,
                    factor_receipt_path=factor_receipt_path,
                    factor_receipt_file_sha256=factor_file_sha,
                )
                conn.execute("commit")
                transaction_started = False
            except Exception:
                if transaction_started:
                    _rollback_quietly(conn)
                raise

        h2 = _file_sha256(target)
        if h2 == h1:
            raise PageGapExecutionMaterializeError("database SHA must change after committed materialization")
        with duckdb.connect(str(target), read_only=True) as post_conn:
            verified_post = _analyze_database_state(
                post_conn,
                page=page,
                targets=targets,
                factor_receipt=factor_receipt,
                bindings=bindings,
                expected_completion_evidence={
                    "materialization_run_id": materialization_run_id,
                    "approval_scope_sha256": expected_scope,
                    "executed_at": executed_at_text,
                    "target_execution_keys_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                        "target_execution_keys_sha256"
                    ],
                    "target_horizons_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                        "target_horizons_sha256"
                    ],
                    "calculation_outputs_sha256": _mapping(plan["target_scope"], field_name="plan target scope")[
                        "calculation_outputs_sha256"
                    ],
                },
            )
            if pre_analysis is None or post_analysis is None:
                raise PageGapExecutionMaterializeError("materialization transaction evidence is unavailable")
            _verify_transaction_postconditions(
                post_conn,
                plan=plan,
                before=pre_analysis,
                after=verified_post,
                expected_rows=None,
            )
        _assert_evidence_files_unchanged(
            page_manifest_path=page_path,
            page_manifest_file_sha256=page_file_sha,
            factor_receipt_path=factor_receipt_path,
            factor_receipt_file_sha256=factor_file_sha,
        )

        receipt = _build_completed_receipt(
            plan=plan,
            executed_at=executed_at_text,
            approval_reference=approval_text,
            materialization_run_id=materialization_run_id,
            database_sha256_before=h1,
            database_sha256_after=h2,
            before=pre_analysis,
            after=verified_post,
        )
        valid, errors = validate_stock_analysis_page_gap_execution_materialization_receipt(
            receipt,
            plan=plan,
        )
        if not valid:
            raise PageGapExecutionMaterializeError(
                "generated materialization receipt failed validation: " + "; ".join(errors)
            )
        _replace_json_atomically_preserving_existing(
            output_path,
            payload=receipt,
            expected_existing=pending_intent,
        )
        persisted = _load_json_object(output_path, field_name="write_receipt_file")
        if persisted != receipt:
            raise PageGapExecutionMaterializeError("persisted materialization receipt does not match generated receipt")
        valid, errors = validate_stock_analysis_page_gap_execution_materialization_receipt(
            persisted,
            plan=plan,
        )
        if not valid:
            raise PageGapExecutionMaterializeError(
                "persisted materialization receipt failed validation: " + "; ".join(errors)
            )
        return persisted


def validate_stock_analysis_page_gap_execution_materialization_receipt(
    receipt: Mapping[str, object],
    *,
    plan: Mapping[str, object] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate a completed or evidence-bound already-complete receipt."""

    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    errors: list[str] = []
    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("receipt_kind", RECEIPT_KIND),
        ("page_id", PAGE_ID),
        ("page_route", PAGE_ROUTE),
        ("page_metric_key", PAGE_METRIC_KEY),
        ("materializer_rule_version", MATERIALIZER_RULE_VERSION),
        ("approval_scope", APPROVAL_SCOPE),
        ("historical_availability_proven", False),
        ("formal_historical_replay_use_allowed", False),
        ("certification_allowed", False),
        ("target_rows_deleted", 0),
        ("non_target_rows_changed", 0),
    ):
        if payload.get(field_name) != expected:
            errors.append(f"receipt.{field_name} mismatch")
    status = payload.get("status")
    if status not in {COMPLETED_STATUS, ALREADY_COMPLETE_STATUS}:
        errors.append("receipt.status is invalid")
    try:
        _required_text(payload.get("approval_reference"), field_name="receipt.approval_reference")
        if payload.get("executed_at") != _utc_datetime_text(
            payload.get("executed_at"), field_name="receipt.executed_at"
        ):
            errors.append("receipt.executed_at is not canonical UTC")
        _sha256_text(payload.get("approval_scope_sha256"), field_name="receipt approval scope SHA")
    except ValueError as exc:
        errors.append(str(exc))

    database = payload.get("database")
    verification = payload.get("verification")
    target_scope = payload.get("target_scope")
    page_binding = payload.get("page_manifest_binding")
    factor_binding = payload.get("factor_write_receipt_binding")
    rollback_anchor = payload.get("rollback_anchor")
    if not isinstance(database, Mapping):
        errors.append("receipt.database must be a mapping")
    else:
        try:
            before_sha = _sha256_text(database.get("sha256_before"), field_name="receipt.database.sha256_before")
            after_sha = _sha256_text(database.get("sha256_after"), field_name="receipt.database.sha256_after")
            if status == COMPLETED_STATUS:
                if before_sha == after_sha or database.get("changed") is not True:
                    errors.append("completed receipt database hashes must differ")
                if payload.get("database_write_executed") is not True:
                    errors.append("completed receipt must record database_write_executed=true")
            elif status == ALREADY_COMPLETE_STATUS:
                if before_sha != after_sha or database.get("changed") is not False:
                    errors.append("already-complete receipt database hashes must match")
                if payload.get("database_write_executed") is not False:
                    errors.append("already-complete receipt must record database_write_executed=false")
        except ValueError as exc:
            errors.append(str(exc))
    if not isinstance(verification, Mapping):
        errors.append("receipt.verification must be a mapping")
    else:
        if verification.get("page_gap_view_count_after") != 0:
            errors.append("receipt verification page gap count after must be zero")
        after_horizons = verification.get("horizon_gap_counts_after")
        if after_horizons != {label: 0 for label in _HORIZON_LABELS}:
            errors.append("receipt verification horizon gaps after must all be zero")
        if verification.get("logical_duplicate_key_count_after") != 0:
            errors.append("receipt verification duplicate key count after must be zero")
        if verification.get("row_count_before") != verification.get("row_count_after"):
            errors.append("receipt verification row count must remain unchanged")
        if verification.get("non_target_rows_sha256_before") != verification.get("non_target_rows_sha256_after"):
            errors.append("receipt verification non-target digest changed")
        if verification.get("target_invariant_rows_sha256_before") != verification.get(
            "target_invariant_rows_sha256_after"
        ):
            errors.append("receipt verification target invariant digest changed")
    if not isinstance(target_scope, Mapping):
        errors.append("receipt.target_scope must be a mapping")
    if not isinstance(page_binding, Mapping) or not isinstance(factor_binding, Mapping):
        errors.append("receipt input bindings must be mappings")
    elif isinstance(target_scope, Mapping):
        try:
            target_key_count = _positive_int(
                payload.get("target_execution_key_count"),
                field_name="receipt.target_execution_key_count",
            )
            target_horizon_count = _positive_int(
                payload.get("target_gap_horizon_count"),
                field_name="receipt.target_gap_horizon_count",
            )
            expected_scope = _materialization_approval_scope_sha256(
                page_manifest_canonical_sha256=_sha256_text(
                    page_binding.get("canonical_manifest_sha256"),
                    field_name="receipt page canonical SHA",
                ),
                page_manifest_file_sha256=_sha256_text(
                    page_binding.get("file_sha256"),
                    field_name="receipt page file SHA",
                ),
                factor_write_receipt_canonical_sha256=_sha256_text(
                    factor_binding.get("canonical_write_receipt_sha256"),
                    field_name="receipt factor canonical SHA",
                ),
                factor_write_receipt_file_sha256=_sha256_text(
                    factor_binding.get("file_sha256"),
                    field_name="receipt factor file SHA",
                ),
                factor_database_sha256_after=_sha256_text(
                    factor_binding.get("database_sha256_after"),
                    field_name="receipt factor database after SHA",
                ),
                target_execution_keys_sha256=_sha256_text(
                    target_scope.get("target_execution_keys_sha256"),
                    field_name="receipt target execution keys SHA",
                ),
                target_horizons_sha256=_sha256_text(
                    target_scope.get("target_horizons_sha256"),
                    field_name="receipt target horizons SHA",
                ),
                calculation_outputs_sha256=_sha256_text(
                    target_scope.get("calculation_outputs_sha256"),
                    field_name="receipt calculation outputs SHA",
                ),
                target_execution_key_count=target_key_count,
                target_gap_horizon_count=target_horizon_count,
            )
            if payload.get("approval_scope_sha256") != expected_scope:
                errors.append("receipt.approval_scope_sha256 semantic mismatch")
            page_database_sha = _sha256_text(
                page_binding.get("database_sha256"),
                field_name="receipt page database SHA",
            )
            factor_before_sha = _sha256_text(
                factor_binding.get("database_sha256_before"),
                field_name="receipt factor database before SHA",
            )
            factor_after_sha = _sha256_text(
                factor_binding.get("database_sha256_after"),
                field_name="receipt factor database after SHA",
            )
            if page_database_sha != factor_before_sha:
                errors.append("receipt page/factor-before SHA mismatch")
            if status == COMPLETED_STATUS and isinstance(database, Mapping):
                if database.get("sha256_before") != factor_after_sha:
                    errors.append("receipt materialization before SHA must equal factor after SHA")
        except ValueError as exc:
            errors.append(str(exc))
    if not isinstance(rollback_anchor, Mapping):
        errors.append("receipt.rollback_anchor must be a mapping")
    elif isinstance(page_binding, Mapping):
        try:
            anchor_sha = _sha256_text(
                rollback_anchor.get("sha256"),
                field_name="receipt rollback anchor SHA",
            )
            page_database_sha = _sha256_text(
                page_binding.get("database_sha256"),
                field_name="receipt page database SHA",
            )
            if anchor_sha != page_database_sha:
                errors.append("receipt rollback anchor must equal pre-factor DB SHA")
            if rollback_anchor.get("reused_factor_prewrite_backup") is not True:
                errors.append("receipt must reuse factor pre-write backup")
            if rollback_anchor.get("second_backup_created") is not False:
                errors.append("receipt must not attest a second backup")
        except ValueError as exc:
            errors.append(str(exc))

    if plan is not None:
        plan_valid, plan_errors = validate_stock_analysis_page_gap_execution_materialization_plan(plan)
        if not plan_valid:
            errors.append("bound plan is invalid: " + "; ".join(plan_errors))
        else:
            for name in (
                "approval_scope_sha256",
                "page_manifest_binding",
                "factor_write_receipt_binding",
                "rollback_anchor",
                "target_scope",
            ):
                plan_value = plan.get(name)
                receipt_value = payload.get(name)
                if name == "target_scope" and isinstance(plan_value, Mapping):
                    plan_value = {
                        key: plan_value.get(key)
                        for key in (
                            "target_execution_keys_sha256",
                            "target_horizons_sha256",
                            "calculation_outputs_sha256",
                        )
                    }
                    if isinstance(receipt_value, Mapping):
                        receipt_value = {
                            key: receipt_value.get(key)
                            for key in (
                                "target_execution_keys_sha256",
                                "target_horizons_sha256",
                                "calculation_outputs_sha256",
                            )
                        }
                if receipt_value != plan_value:
                    errors.append(f"receipt.{name} does not match bound plan")
    try:
        observed = _sha256_text(
            payload.get("canonical_materialization_receipt_sha256"),
            field_name="receipt canonical SHA",
        )
        if observed != _receipt_sha256(payload):
            errors.append("receipt canonical SHA mismatch")
    except ValueError as exc:
        errors.append(str(exc))
    return not errors, tuple(errors)


def _validated_input_paths(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    page_manifest_file: str | Path,
    factor_write_receipt_file: str | Path,
) -> tuple[Path, Path, Path, Path]:
    target = _existing_file_no_links(duckdb_path, field_name="duckdb_path")
    root = _existing_directory_no_links(
        trusted_evidence_root,
        field_name="trusted_evidence_root",
    )
    page_path = _existing_json_path_within_root(
        trusted_root=root,
        path=page_manifest_file,
        field_name="page_manifest_file",
    )
    factor_path = _existing_json_path_within_root(
        trusted_root=root,
        path=factor_write_receipt_file,
        field_name="factor_write_receipt_file",
    )
    return target, root, page_path, factor_path


def _validated_page_manifest(manifest: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise PageGapExecutionMaterializeError("page manifest must be a mapping")
    page = dict(manifest)
    valid, errors = validate_stock_analysis_page_gap_manifest(page)
    if not valid:
        raise PageGapExecutionMaterializeError("page manifest failed validation: " + "; ".join(errors))
    if page.get("manifest_kind") != PAGE_MANIFEST_KIND:
        raise PageGapExecutionMaterializeError("page manifest kind mismatch")
    if page.get("status") != "gaps_found":
        raise PageGapExecutionMaterializeError("page manifest must have gaps_found status")
    blockers = page.get("blockers")
    if blockers != []:
        raise PageGapExecutionMaterializeError("page manifest contains blockers")
    return page


def _validated_factor_write_receipt(receipt: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise PageGapExecutionMaterializeError("factor write receipt must be a mapping")
    payload = dict(receipt)
    try:
        from backend.app.tasks.stock_analysis_page_gap_factor_write import (
            validate_stock_analysis_page_gap_factor_write_receipt,
        )
    except ImportError as exc:
        raise PageGapExecutionMaterializeError("page-gap factor write receipt validator is unavailable") from exc
    valid, errors = validate_stock_analysis_page_gap_factor_write_receipt(payload)
    if not valid:
        raise PageGapExecutionMaterializeError("factor write receipt failed validation: " + "; ".join(errors))
    if payload.get("receipt_kind") != FACTOR_WRITE_RECEIPT_KIND:
        raise PageGapExecutionMaterializeError("factor write receipt kind mismatch")
    if payload.get("status") != FACTOR_WRITE_COMPLETED_STATUS:
        raise PageGapExecutionMaterializeError("factor write receipt status mismatch")
    for field_name, expected in (
        ("database_write_executed", True),
        ("additional_write_allowed", False),
        ("historical_availability_proven", False),
        ("formal_historical_replay_use_allowed", False),
        ("certification_allowed", False),
        ("downstream_materialization_executed", False),
        ("no_overwrite_or_delete_performed", True),
    ):
        if payload.get(field_name) is not expected:
            raise PageGapExecutionMaterializeError(f"factor write receipt {field_name} boundary mismatch")
    return payload


def _validated_cross_bindings(
    *,
    target: Path,
    page: Mapping[str, Any],
    page_path: Path,
    page_file_sha: str,
    factor_receipt: Mapping[str, Any],
    factor_receipt_path: Path,
    factor_file_sha: str,
) -> dict[str, Any]:
    page_database = _mapping(page.get("database"), field_name="page manifest database")
    page_database_path = _existing_file_no_links(
        _required_text(page_database.get("path"), field_name="page database path"),
        field_name="page database path",
    )
    if page_database_path != target:
        raise PageGapExecutionMaterializeError("page manifest database path mismatch")
    page_database_sha = _sha256_text(
        page_database.get("sha256_before"),
        field_name="page manifest database SHA",
    )
    if page_database.get("sha256_after") != page_database_sha:
        raise PageGapExecutionMaterializeError("page manifest database hashes must match")
    page_canonical_sha = _sha256_text(
        page.get("canonical_manifest_sha256"),
        field_name="page manifest canonical SHA",
    )

    page_binding = _mapping(
        factor_receipt.get("page_manifest_binding"),
        field_name="factor receipt page_manifest_binding",
    )
    expected_page_binding_values = {
        "file_sha256": page_file_sha,
        "canonical_manifest_sha256": page_canonical_sha,
        "manifest_kind": PAGE_MANIFEST_KIND,
        "page_id": PAGE_ID,
        "page_route": PAGE_ROUTE,
        "page_metric_key": PAGE_METRIC_KEY,
        "database_path": str(target),
        "database_sha256": page_database_sha,
    }
    for field_name, expected in expected_page_binding_values.items():
        observed = page_binding.get(field_name)
        if field_name == "database_path":
            try:
                observed = str(_existing_file_no_links(observed, field_name="factor page binding database path"))
            except (OSError, ValueError, TypeError) as exc:
                raise PageGapExecutionMaterializeError("factor receipt page database path is invalid") from exc
        if observed != expected:
            raise PageGapExecutionMaterializeError(f"factor receipt page binding {field_name} mismatch")
    binding_page_path = _existing_file_no_links(
        _required_text(page_binding.get("path"), field_name="factor page binding path"),
        field_name="factor page binding path",
    )
    if binding_page_path != page_path:
        raise PageGapExecutionMaterializeError("factor receipt page manifest path mismatch")

    summary = _mapping(page.get("summary"), field_name="page manifest summary")
    gap_views = _sequence_of_mappings(page.get("gap_views"), field_name="page gap_views")
    missing_cells = _sequence_of_mappings(
        page.get("missing_factor_cells"),
        field_name="page missing_factor_cells",
    )
    expected_gap_count = len(gap_views)
    expected_missing_count = len(missing_cells)
    if summary.get("page_gap_view_count_before") != expected_gap_count:
        raise PageGapExecutionMaterializeError("page manifest gap count mismatch")
    if summary.get("unique_missing_factor_cell_count") != expected_missing_count:
        raise PageGapExecutionMaterializeError("page manifest missing factor count mismatch")
    if page_binding.get("page_gap_view_count") != expected_gap_count:
        raise PageGapExecutionMaterializeError("factor receipt bound page gap count mismatch")
    if page_binding.get("missing_factor_cell_count") != expected_missing_count:
        raise PageGapExecutionMaterializeError("factor receipt bound missing factor cell count mismatch")

    database = _mapping(factor_receipt.get("database"), field_name="factor receipt database")
    database_path = _existing_file_no_links(
        _required_text(database.get("path"), field_name="factor receipt database path"),
        field_name="factor receipt database path",
    )
    if database_path != target:
        raise PageGapExecutionMaterializeError("factor receipt database path mismatch")
    factor_before_sha = _sha256_text(database.get("sha256_before"), field_name="factor receipt database before SHA")
    factor_after_sha = _sha256_text(database.get("sha256_after"), field_name="factor receipt database after SHA")
    if factor_before_sha != page_database_sha:
        raise PageGapExecutionMaterializeError("original page manifest DB SHA must equal factor write before SHA")
    if factor_before_sha == factor_after_sha or database.get("changed") is not True:
        raise PageGapExecutionMaterializeError("factor write receipt must bind a changed database")

    target_cells = _normalize_target_cells(factor_receipt.get("target_cells"))
    missing_keys = {
        (
            _stock_code(item.get("stock_code"), field_name="missing factor stock_code"),
            _iso_date_text(item.get("trade_date"), field_name="missing factor trade_date"),
        )
        for item in missing_cells
    }
    target_keys = {(item["stock_code"], item["trade_date"]) for item in target_cells}
    if target_keys != missing_keys:
        raise PageGapExecutionMaterializeError(
            "factor receipt target cells do not exactly equal page missing factor cells"
        )
    target_cell_count = len(target_cells)
    if factor_receipt.get("target_cell_count") != target_cell_count:
        raise PageGapExecutionMaterializeError("factor receipt target cell count mismatch")
    if factor_receipt.get("inserted_row_count") != target_cell_count:
        raise PageGapExecutionMaterializeError("all target factor cells must be inserted")
    if factor_receipt.get("existing_target_row_count") != 0:
        raise PageGapExecutionMaterializeError("factor write receipt existing target count must be zero")
    target_cells_sha = _canonical_json_sha256(
        sorted(target_cells, key=lambda item: (item["trade_date"], item["stock_code"]))
    )
    if factor_receipt.get("target_cells_sha256") != target_cells_sha:
        raise PageGapExecutionMaterializeError("factor receipt target cells SHA mismatch")

    factor_canonical_sha = _sha256_text(
        factor_receipt.get("canonical_write_receipt_sha256"),
        field_name="factor receipt canonical SHA",
    )
    backup = _mapping(factor_receipt.get("backup"), field_name="factor receipt backup")
    backup_path = _existing_file_no_links(
        _required_text(backup.get("path"), field_name="factor receipt backup path"),
        field_name="factor receipt backup path",
    )
    if backup_path == target:
        raise PageGapExecutionMaterializeError("rollback anchor must differ from live DuckDB")
    backups_root = _existing_directory_no_links(
        target.parent / "backups",
        field_name="target backups directory",
    )
    _assert_path_within(backups_root, backup_path, field_name="factor receipt backup path")
    backup_sha = _sha256_text(backup.get("sha256"), field_name="factor receipt backup SHA")
    if backup_sha != factor_before_sha or _file_sha256(backup_path) != backup_sha:
        raise PageGapExecutionMaterializeError("factor pre-write backup SHA must equal factor write before SHA")
    if backup.get("created_exclusive") is not True or backup.get("byte_identical_prewrite_target") is not True:
        raise PageGapExecutionMaterializeError("factor receipt backup guarantees are incomplete")

    return {
        "page_manifest_canonical_sha256": page_canonical_sha,
        "page_database_sha256": page_database_sha,
        "factor_receipt_canonical_sha256": factor_canonical_sha,
        "factor_receipt_file_sha256": factor_file_sha,
        "factor_database_sha256_before": factor_before_sha,
        "factor_database_sha256_after": factor_after_sha,
        "factor_target_cell_count": target_cell_count,
        "factor_target_cells_sha256": target_cells_sha,
        "factor_target_rows_sha256": _sha256_text(
            factor_receipt.get("target_rows_sha256"),
            field_name="factor receipt target rows SHA",
        ),
        "factor_source_version": _required_text(
            factor_receipt.get("source_version"),
            field_name="factor receipt source_version",
        ),
        "factor_run_id": _required_text(
            factor_receipt.get("run_id"),
            field_name="factor receipt run_id",
        ),
        "factor_target_cells": target_cells,
        "backup": {
            "path": str(backup_path),
            "sha256": backup_sha,
            "reused_factor_prewrite_backup": True,
            "byte_identical_factor_prewrite_target": True,
            "second_backup_created": False,
        },
    }


def _targets_from_page_manifest(
    page: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gap_views = _sequence_of_mappings(page.get("gap_views"), field_name="page gap_views")
    grouped: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_horizons: set[tuple[str, str, str, int]] = set()
    for index, raw_view in enumerate(gap_views):
        view = dict(raw_view)
        key = (
            _iso_date_text(view.get("signal_date"), field_name=f"gap_views[{index}].signal_date"),
            _stock_code(view.get("stock_code"), field_name=f"gap_views[{index}].stock_code"),
            _required_text(view.get("signal_kind"), field_name=f"gap_views[{index}].signal_kind"),
        )
        days = view.get("horizon_days")
        if days not in _HORIZON_BY_DAYS:
            raise PageGapExecutionMaterializeError("page manifest contains invalid horizon")
        horizon_key = (*key, int(days))
        if horizon_key in seen_horizons:
            raise PageGapExecutionMaterializeError("page manifest contains duplicate logical key/horizon")
        seen_horizons.add(horizon_key)
        if view.get("occurrence_ordinal") != 1 or view.get("physical_row_count_for_natural_key") != 1:
            raise PageGapExecutionMaterializeError("page manifest contains duplicate physical execution rows")
        grouped[key].append(view)
    targets: list[dict[str, Any]] = []
    for key, grouped_views in sorted(grouped.items()):
        targets.append(
            {
                "key": {
                    "signal_date": key[0],
                    "stock_code": key[1],
                    "signal_kind": key[2],
                },
                "views": sorted(grouped_views, key=lambda item: int(item["horizon_days"])),
            }
        )
    summary = _mapping(page.get("summary"), field_name="page manifest summary")
    if summary.get("unique_execution_key_count") != len(targets):
        raise PageGapExecutionMaterializeError("page manifest execution key count mismatch")
    if summary.get("page_gap_view_count_before") != len(gap_views):
        raise PageGapExecutionMaterializeError("page manifest target horizon count mismatch")
    return targets


def _analyze_database_state(
    conn: duckdb.DuckDBPyConnection,
    *,
    page: Mapping[str, Any],
    targets: Sequence[Mapping[str, Any]],
    factor_receipt: Mapping[str, Any],
    bindings: Mapping[str, Any],
    expected_completion_evidence: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    columns = _validate_execution_schema(conn)
    _validate_factor_schema_and_quality(conn)
    required_cells = {
        (
            _stock_code(
                factor.get("stock_code"),
                field_name="page required factor stock_code",
            ),
            _iso_date_text(
                factor.get("trade_date"),
                field_name="page required factor trade_date",
            ),
        )
        for target in targets
        for view in _sequence_of_mappings(target.get("views"), field_name="target views")
        for factor in (
            _mapping(view.get("entry_factor"), field_name="view entry_factor"),
            _mapping(view.get("exit_factor"), field_name="view exit_factor"),
        )
    }
    factor_rows = _load_required_factor_rows(conn, required_cells)
    _verify_original_present_factors(page=page, factor_rows=factor_rows)
    _verify_factor_write_targets(
        factor_rows=factor_rows,
        factor_receipt=factor_receipt,
        bindings=bindings,
    )

    all_rows = _load_execution_rows(conn, columns=columns)
    rows_by_key: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row_index, row in enumerate(all_rows):
        key = _execution_key(row, field_name=f"execution row {row_index}")
        rows_by_key[key].append(row)
    duplicate_keys = {key: values for key, values in rows_by_key.items() if len(values) != 1}
    if duplicate_keys:
        raise PageGapExecutionMaterializeError("execution history contains duplicate logical keys")

    target_key_set = {
        (
            str(_mapping(target.get("key"), field_name="target key")["signal_date"]),
            str(_mapping(target.get("key"), field_name="target key")["stock_code"]),
            str(_mapping(target.get("key"), field_name="target key")["signal_kind"]),
        )
        for target in targets
    }
    missing_keys = sorted(target_key_set.difference(rows_by_key))
    if missing_keys:
        raise PageGapExecutionMaterializeError("page manifest execution logical key is missing from current DuckDB")

    global_gap_counts = _global_page_gap_counts(conn)
    analyzed_targets: list[dict[str, Any]] = []
    target_invariant_payload: list[dict[str, Any]] = []
    pending_update_field_count = 0
    target_states: set[str] = set()
    for target in targets:
        key_mapping = _mapping(target.get("key"), field_name="target key")
        key = (
            str(key_mapping["signal_date"]),
            str(key_mapping["stock_code"]),
            str(key_mapping["signal_kind"]),
        )
        row = rows_by_key[key][0]
        horizons: list[dict[str, Any]] = []
        allowed_columns = {"evidence_json"}
        row_states: set[str] = set()
        for view in _sequence_of_mappings(target.get("views"), field_name="target views"):
            days = int(view["horizon_days"])
            horizon = _HORIZON_BY_DAYS[days]
            _assert_source_view_matches_execution_row(view=view, row=row, horizon=horizon)
            entry_date = _iso_date_text(row.get("entry_date"), field_name="execution entry_date")
            exit_date = _iso_date_text(
                row.get(str(horizon["exit_date_col"])),
                field_name=f"execution {horizon['exit_date_col']}",
            )
            stock_code = key[1]
            entry_factor = float(factor_rows[(stock_code, entry_date)]["adj_factor"])
            exit_factor = float(factor_rows[(stock_code, exit_date)]["adj_factor"])
            entry_price = _positive_finite_float(row.get("entry_price"), field_name="execution entry_price")
            exit_price = _positive_finite_float(
                row.get(str(horizon["exit_price_col"])),
                field_name=f"execution {horizon['exit_price_col']}",
            )
            buy_cost_bps = _nonnegative_finite_float(row.get("buy_cost_bps"), field_name="execution buy_cost_bps")
            sell_cost_bps = _nonnegative_finite_float(row.get("sell_cost_bps"), field_name="execution sell_cost_bps")
            slippage_bps = _nonnegative_finite_float(row.get("slippage_bps"), field_name="execution slippage_bps")
            if row.get("price_adjustment_mode") != PRICE_ADJUSTMENT_MODE:
                raise PageGapExecutionMaterializeError(
                    "execution price_adjustment_mode is not the formal adj-factor ratio mode"
                )
            computed_gross = adjusted_return(
                start_price=entry_price,
                start_adj_factor=entry_factor,
                end_price=exit_price,
                end_adj_factor=exit_factor,
            )
            computed_net = net_return_after_costs(
                computed_gross,
                buy_cost_rate=buy_cost_bps / 10000.0,
                sell_cost_rate=sell_cost_bps / 10000.0,
                slippage_rate=slippage_bps / 10000.0,
            )
            if computed_gross is None or computed_net is None:
                raise PageGapExecutionMaterializeError("formal adjusted-return calculation returned null")
            gross_col = str(horizon["gross_adj_col"])
            net_col = str(horizon["net_adj_col"])
            current_gross = _optional_finite_float(row.get(gross_col), field_name=gross_col)
            current_net = _optional_finite_float(row.get(net_col), field_name=net_col)
            if current_gross is not None and not _float_equal(current_gross, computed_gross):
                raise PageGapExecutionMaterializeError(
                    "existing adjusted gross return conflicts with formal calculation"
                )
            if current_net is not None and not _float_equal(current_net, computed_net):
                raise PageGapExecutionMaterializeError("existing adjusted net return conflicts with formal calculation")
            if current_net is None:
                row_state = READY_STATUS
                update_fields = [net_col]
                if current_gross is None:
                    update_fields.insert(0, gross_col)
            elif current_gross is not None:
                row_state = ALREADY_COMPLETE_STATUS
                update_fields = []
            else:
                raise PageGapExecutionMaterializeError("adjusted return target is partially materialized")
            row_states.add(row_state)
            allowed_columns.update({gross_col, net_col})
            pending_update_field_count += len(update_fields)
            horizons.append(
                {
                    "gap_view_id": view["gap_view_id"],
                    "source_row_sha256": view["source_row_sha256"],
                    "horizon_label": horizon["label"],
                    "horizon_days": days,
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": exit_date,
                    "exit_price": exit_price,
                    "entry_factor": entry_factor,
                    "exit_factor": exit_factor,
                    "buy_cost_bps": buy_cost_bps,
                    "sell_cost_bps": sell_cost_bps,
                    "slippage_bps": slippage_bps,
                    "current_adjusted_gross": current_gross,
                    "current_adjusted_net": current_net,
                    "computed_adjusted_gross": computed_gross,
                    "computed_adjusted_net": computed_net,
                    "update_fields": update_fields,
                }
            )
        if len(row_states) != 1:
            raise PageGapExecutionMaterializeError("an execution key is partially materialized across target horizons")
        row_state = next(iter(row_states))
        target_states.add(row_state)
        evidence = _parse_evidence_json(row.get("evidence_json"))
        analyzed_targets.append(
            {
                "key": {
                    "signal_date": key[0],
                    "stock_code": key[1],
                    "signal_kind": key[2],
                },
                "state": row_state,
                "source_evidence_sha256": _canonical_json_sha256(evidence),
                "horizons": horizons,
            }
        )
        target_invariant_payload.append(
            {
                "key": {
                    "signal_date": key[0],
                    "stock_code": key[1],
                    "signal_kind": key[2],
                },
                "row": {
                    column: _canonical_value(row.get(column)) for column in columns if column not in allowed_columns
                },
            }
        )

    if len(target_states) != 1:
        raise PageGapExecutionMaterializeError("execution targets are partially materialized across logical keys")
    state = next(iter(target_states))
    target_gap_count = sum(
        len(_sequence_of_mappings(target.get("views"), field_name="target views")) for target in targets
    )
    if state == READY_STATUS and int(global_gap_counts["total"]) != target_gap_count:
        raise PageGapExecutionMaterializeError("current page gaps do not exactly equal the manifest target horizons")
    if state == ALREADY_COMPLETE_STATUS and int(global_gap_counts["total"]) != 0:
        raise PageGapExecutionMaterializeError("already-complete targets coexist with unclosed global page gaps")
    if state == ALREADY_COMPLETE_STATUS:
        for target_payload in analyzed_targets:
            row_key = _key_tuple(target_payload["key"])
            _assert_materialization_evidence(
                evidence=_parse_evidence_json(rows_by_key[row_key][0].get("evidence_json")),
                key=target_payload["key"],
                horizons=target_payload["horizons"],
                page_manifest_canonical_sha256=str(bindings["page_manifest_canonical_sha256"]),
                factor_receipt_canonical_sha256=str(bindings["factor_receipt_canonical_sha256"]),
                factor_receipt_file_sha256=str(bindings["factor_receipt_file_sha256"]),
                expected_completion_evidence=expected_completion_evidence,
            )

    non_target_rows = [row for key, values in rows_by_key.items() if key not in target_key_set for row in values]
    analyzed_targets.sort(
        key=lambda item: (
            item["key"]["signal_date"],
            item["key"]["stock_code"],
            item["key"]["signal_kind"],
        )
    )
    target_invariant_payload.sort(
        key=lambda item: (
            item["key"]["signal_date"],
            item["key"]["stock_code"],
            item["key"]["signal_kind"],
        )
    )
    return {
        "state": state,
        "row_count": len(all_rows),
        "global_gap_counts": global_gap_counts,
        "pending_update_field_count": pending_update_field_count,
        "target_invariant_rows_sha256": _canonical_json_sha256(target_invariant_payload),
        "non_target_rows_sha256": _rows_sha256(non_target_rows, columns=columns),
        "targets": analyzed_targets,
        "_columns": columns,
        "_rows_by_key": dict(rows_by_key),
        "_target_key_set": target_key_set,
        "_target_invariant_payload": target_invariant_payload,
        "_completion_traces": {
            key: _parse_evidence_json(rows_by_key[key][0].get("evidence_json")).get(EVIDENCE_TRACE_KEY)
            for key in target_key_set
        },
    }


def _validate_execution_schema(conn: duckdb.DuckDBPyConnection) -> list[str]:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if EXECUTION_TABLE not in tables:
        raise PageGapExecutionMaterializeError("execution history table is missing")
    columns = [str(row[1]) for row in conn.execute(f"pragma table_info('{EXECUTION_TABLE}')").fetchall()]
    missing = sorted(_REQUIRED_EXECUTION_COLUMNS.difference(columns))
    if missing:
        raise PageGapExecutionMaterializeError(
            "execution history schema is missing required columns: " + ",".join(missing)
        )
    return columns


def _validate_factor_schema_and_quality(conn: duckdb.DuckDBPyConnection) -> None:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if FACTOR_TABLE not in tables:
        raise PageGapExecutionMaterializeError("adjustment factor table is missing")
    columns = {str(row[1]) for row in conn.execute(f"pragma table_info('{FACTOR_TABLE}')").fetchall()}
    required = {"stock_code", "trade_date", "adj_factor", "source_version", "run_id"}
    if not required.issubset(columns):
        raise PageGapExecutionMaterializeError("adjustment factor schema is incomplete")
    quality = conn.execute(
        f"""
        select
          count(*) filter (
            where stock_code is null
               or not regexp_matches(trim(cast(stock_code as varchar)), '^[0-9]{{6}}\\.(SH|SZ|BJ)$')
               or trade_date is null
               or try_cast(trade_date as date) is null
               or trim(cast(trade_date as varchar)) <> strftime(try_cast(trade_date as date), '%Y-%m-%d')
               or adj_factor is null
               or not isfinite(adj_factor)
               or adj_factor <= 0
               or source_version is null or trim(cast(source_version as varchar)) = ''
               or run_id is null or trim(cast(run_id as varchar)) = ''
          ) as invalid_count,
          (
            select count(*) from (
              select stock_code, trade_date
              from {FACTOR_TABLE}
              group by stock_code, trade_date
              having count(*) <> 1
            ) duplicate_cells
          ) as duplicate_count
        from {FACTOR_TABLE}
        """
    ).fetchone()
    if quality is None or int(quality[0] or 0) or int(quality[1] or 0):
        raise PageGapExecutionMaterializeError("adjustment factor table contains invalid or duplicate rows")


def _load_required_factor_rows(
    conn: duckdb.DuckDBPyConnection,
    required_cells: set[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    observations: defaultdict[tuple[str, str], list[tuple[Any, ...]]] = defaultdict(list)
    cells = sorted(required_cells)
    for start in range(0, len(cells), FACTOR_BATCH_SIZE):
        batch = cells[start : start + FACTOR_BATCH_SIZE]
        values_sql = ", ".join("(?, ?)" for _ in batch)
        params = [value for cell in batch for value in cell]
        rows = conn.execute(
            f"""
            with requested(stock_code, trade_date) as (values {values_sql})
            select requested.stock_code,
                   requested.trade_date,
                   factor.stock_code,
                   factor.trade_date,
                   factor.adj_factor,
                   factor.source_version,
                   factor.run_id
            from requested
            left join {FACTOR_TABLE} factor
              on factor.stock_code = requested.stock_code
             and factor.trade_date = requested.trade_date
            order by requested.trade_date, requested.stock_code
            """,
            params,
        ).fetchall()
        for row in rows:
            key = (
                _stock_code(row[0], field_name="requested factor stock_code"),
                _iso_date_text(row[1], field_name="requested factor trade_date"),
            )
            observations[key].append(tuple(row[2:]))
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for cell in cells:
        rows = observations.get(cell, [])
        if len(rows) != 1 or rows[0][0] is None:
            raise PageGapExecutionMaterializeError(
                "every required exact adjustment-factor cell must exist exactly once"
            )
        observed = rows[0]
        stock_code = _stock_code(observed[0], field_name="factor stock_code")
        trade_date = _iso_date_text(observed[1], field_name="factor trade_date")
        if (stock_code, trade_date) != cell:
            raise PageGapExecutionMaterializeError("factor exact-cell key mismatch")
        result[cell] = {
            "stock_code": stock_code,
            "trade_date": trade_date,
            "adj_factor": _positive_finite_float(observed[2], field_name="factor adj_factor"),
            "source_version": _required_text(observed[3], field_name="factor source_version"),
            "run_id": _required_text(observed[4], field_name="factor run_id"),
        }
    return result


def _verify_original_present_factors(
    *,
    page: Mapping[str, Any],
    factor_rows: Mapping[tuple[str, str], Mapping[str, Any]],
) -> None:
    for view in _sequence_of_mappings(page.get("gap_views"), field_name="page gap_views"):
        for factor_name in ("entry_factor", "exit_factor"):
            factor = _mapping(view.get(factor_name), field_name=factor_name)
            if factor.get("status") != "present_exact_cell":
                continue
            key = (
                _stock_code(factor.get("stock_code"), field_name="present factor stock_code"),
                _iso_date_text(factor.get("trade_date"), field_name="present factor trade_date"),
            )
            observed = factor_rows[key]
            expected_value = _positive_finite_float(factor.get("adj_factor"), field_name="manifest present adj_factor")
            if not _float_equal(float(observed["adj_factor"]), expected_value):
                raise PageGapExecutionMaterializeError(
                    "an originally present factor changed after page manifest creation"
                )
            source = _mapping(factor.get("source_identity"), field_name="factor source_identity")
            if observed["source_version"] != source.get("source_version") or observed["run_id"] != source.get("run_id"):
                raise PageGapExecutionMaterializeError("an originally present factor source identity changed")


def _verify_factor_write_targets(
    *,
    factor_rows: Mapping[tuple[str, str], Mapping[str, Any]],
    factor_receipt: Mapping[str, Any],
    bindings: Mapping[str, Any],
) -> None:
    target_cells = _sequence_of_mappings(
        bindings.get("factor_target_cells"),
        field_name="factor target cells",
    )
    source_version = str(bindings["factor_source_version"])
    run_id = str(bindings["factor_run_id"])
    normalized_rows: list[dict[str, Any]] = []
    for cell in target_cells:
        key = (str(cell["stock_code"]), str(cell["trade_date"]))
        observed = factor_rows.get(key)
        if observed is None:
            raise PageGapExecutionMaterializeError("factor write target is absent from current DB")
        if observed["source_version"] != source_version or observed["run_id"] != run_id:
            raise PageGapExecutionMaterializeError("factor write target source_version/run_id mismatch")
        normalized_rows.append(
            {
                "requested_trade_date": key[1],
                "stock_code": key[0],
                "trade_date": key[1],
                "adj_factor": float(observed["adj_factor"]),
            }
        )
    normalized_rows.sort(key=lambda item: (item["trade_date"], item["stock_code"]))
    if _canonical_json_sha256(normalized_rows) != bindings["factor_target_rows_sha256"]:
        raise PageGapExecutionMaterializeError(
            "current exact factor rows do not match factor write receipt target rows SHA"
        )


def _load_execution_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    columns: Sequence[str],
) -> list[dict[str, Any]]:
    rows = conn.execute(f"select * from {EXECUTION_TABLE}").fetchall()
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _execution_key(row: Mapping[str, Any], *, field_name: str) -> tuple[str, str, str]:
    return (
        _iso_date_text(row.get("signal_date"), field_name=f"{field_name}.signal_date"),
        _stock_code(row.get("stock_code"), field_name=f"{field_name}.stock_code"),
        _required_text(row.get("signal_kind"), field_name=f"{field_name}.signal_kind"),
    )


def _assert_source_view_matches_execution_row(
    *,
    view: Mapping[str, Any],
    row: Mapping[str, Any],
    horizon: Mapping[str, str | int],
) -> None:
    payload = {
        "signal_date": _iso_date_text(row.get("signal_date"), field_name="row signal_date"),
        "stock_code": _stock_code(row.get("stock_code"), field_name="row stock_code"),
        "signal_kind": _required_text(row.get("signal_kind"), field_name="row signal_kind"),
        "stock_name": _required_text(row.get("stock_name"), field_name="row stock_name"),
        "candidate_rank": _positive_int(row.get("candidate_rank"), field_name="row candidate_rank"),
        "market_state": _required_text(row.get("market_state"), field_name="row market_state"),
        "data_status": _required_text(row.get("data_status"), field_name="row data_status"),
        "formula_version": _required_text(row.get("formula_version"), field_name="row formula_version"),
        "run_id": _required_text(row.get("run_id"), field_name="row run_id"),
        "signal_close": _positive_finite_float(row.get("signal_close"), field_name="row signal_close"),
        "entry_date": _iso_date_text(row.get("entry_date"), field_name="row entry_date"),
        "entry_price": _positive_finite_float(row.get("entry_price"), field_name="row entry_price"),
        "exit_date": _iso_date_text(row.get(str(horizon["exit_date_col"])), field_name="row exit_date"),
        "exit_price": _positive_finite_float(row.get(str(horizon["exit_price_col"])), field_name="row exit_price"),
        "raw_return_net": _finite_float(row.get(str(horizon["raw_net_col"])), field_name="row raw_return_net"),
        # The manifest source hash intentionally captured this field as null.
        "adjusted_return_net": None,
        "horizon_label": str(horizon["label"]),
        "horizon_days": int(horizon["days"]),
    }
    expected_hash = _sha256_text(view.get("source_row_sha256"), field_name="view source_row_sha256")
    if _source_row_sha256(payload) != expected_hash:
        raise PageGapExecutionMaterializeError(
            "current execution dates, prices, raw returns, or trace fields drifted from page manifest"
        )


def _global_page_gap_counts(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    select_items = [
        f"sum(case when {item['raw_net_col']} is not null and {item['net_adj_col']} is null then 1 else 0 end)"
        for item in _HORIZONS
    ]
    row = conn.execute(f"select {', '.join(select_items)} from {EXECUTION_TABLE}").fetchone()
    if row is None:
        raise PageGapExecutionMaterializeError("cannot read global page gap counts")
    result = {str(item["label"]): int(row[index] or 0) for index, item in enumerate(_HORIZONS)}
    result["total"] = sum(result.values())
    return result


def _apply_exact_target_updates(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: Mapping[str, Any],
    before: Mapping[str, Any],
    materialization_run_id: str,
    executed_at: str,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    page_binding = _mapping(plan.get("page_manifest_binding"), field_name="plan page binding")
    factor_binding = _mapping(
        plan.get("factor_write_receipt_binding"),
        field_name="plan factor receipt binding",
    )
    target_scope = _mapping(plan.get("target_scope"), field_name="plan target scope")
    approval_scope_sha = _sha256_text(plan.get("approval_scope_sha256"), field_name="plan approval scope SHA")
    expected_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    allowed_adjusted_columns = {
        str(horizon[field]) for horizon in _HORIZONS for field in ("gross_adj_col", "net_adj_col")
    }
    rows_by_key = _mapping(before.get("_rows_by_key"), field_name="preflight rows by key")
    for target in _sequence_of_mappings(plan.get("targets"), field_name="plan targets"):
        key_mapping = _mapping(target.get("key"), field_name="plan target key")
        key = _key_tuple(key_mapping)
        current_rows = rows_by_key.get(key)
        if not isinstance(current_rows, list) or len(current_rows) != 1:
            raise PageGapExecutionMaterializeError("target execution key ceased to be physically unique")
        evidence = _parse_evidence_json(current_rows[0].get("evidence_json"))
        if EVIDENCE_TRACE_KEY in evidence:
            raise PageGapExecutionMaterializeError("target evidence already contains a page-gap materialization trace")
        horizons = _sequence_of_mappings(target.get("horizons"), field_name="target horizons")
        trace = {
            "schema_version": SCHEMA_VERSION,
            "materializer_rule_version": MATERIALIZER_RULE_VERSION,
            "materialization_run_id": materialization_run_id,
            "executed_at": executed_at,
            "approval_scope_sha256": approval_scope_sha,
            "page_manifest_canonical_sha256": page_binding["canonical_manifest_sha256"],
            "factor_write_receipt_canonical_sha256": factor_binding["canonical_write_receipt_sha256"],
            "factor_write_receipt_file_sha256": factor_binding["file_sha256"],
            "target_execution_key": {
                "signal_date": key[0],
                "stock_code": key[1],
                "signal_kind": key[2],
            },
            "target_horizon_days": sorted(int(item["horizon_days"]) for item in horizons),
            "target_execution_keys_sha256": target_scope["target_execution_keys_sha256"],
            "target_horizons_sha256": target_scope["target_horizons_sha256"],
            "calculation_outputs_sha256": target_scope["calculation_outputs_sha256"],
            "historical_availability_proven": False,
            "formal_historical_replay_use_allowed": False,
            "certification_allowed": False,
        }
        evidence[EVIDENCE_TRACE_KEY] = trace
        evidence_text = _json_text(evidence)
        assignments: list[str] = []
        parameters: list[Any] = []
        null_guards: list[str] = []
        expected_updates: dict[str, float] = {}
        for horizon in horizons:
            update_fields = horizon.get("update_fields")
            if not isinstance(update_fields, list):
                raise PageGapExecutionMaterializeError("target update_fields is invalid")
            horizon_meta = _HORIZON_BY_DAYS[int(horizon["horizon_days"])]
            value_by_column = {
                str(horizon_meta["gross_adj_col"]): float(horizon["computed_adjusted_gross"]),
                str(horizon_meta["net_adj_col"]): float(horizon["computed_adjusted_net"]),
            }
            for column in update_fields:
                if column not in allowed_adjusted_columns or column not in value_by_column:
                    raise PageGapExecutionMaterializeError("plan attempts to update a non-approved execution column")
                if column in expected_updates:
                    raise PageGapExecutionMaterializeError("plan repeats an adjusted-return update column")
                assignments.append(f"{column} = ?")
                parameters.append(value_by_column[column])
                null_guards.append(f"{column} is null")
                expected_updates[column] = value_by_column[column]
        if not assignments:
            raise PageGapExecutionMaterializeError("ready target has no adjusted-return updates")
        assignments.append("evidence_json = ?")
        parameters.append(evidence_text)
        parameters.extend(key)
        conn.execute(
            f"""
            update {EXECUTION_TABLE}
            set {", ".join(assignments)}
            where signal_date = ? and stock_code = ? and signal_kind = ?
              and {" and ".join(null_guards)}
            """,
            parameters,
        )
        expected_rows[key] = {
            "updates": expected_updates,
            "evidence_json": evidence_text,
        }
    return expected_rows


def _assert_analysis_matches_plan(
    analysis: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
) -> None:
    summary = _mapping(plan.get("summary"), field_name="plan summary")
    scope = _mapping(plan.get("target_scope"), field_name="plan target scope")
    if analysis.get("state") != READY_STATUS:
        raise PageGapExecutionMaterializeError("live analysis is not ready")
    if analysis.get("row_count") != summary.get("row_count_before"):
        raise PageGapExecutionMaterializeError("execution row count drifted after approval")
    if analysis.get("global_gap_counts", {}).get("total") != summary.get("current_page_gap_view_count"):
        raise PageGapExecutionMaterializeError("global page gap count drifted after approval")
    if analysis.get("target_invariant_rows_sha256") != scope.get("target_invariant_rows_sha256_before"):
        raise PageGapExecutionMaterializeError("target invariant rows drifted after approval")
    if analysis.get("non_target_rows_sha256") != scope.get("non_target_rows_sha256_before"):
        raise PageGapExecutionMaterializeError("non-target rows drifted after approval")
    if _canonical_json_sha256(analysis.get("targets")) != _canonical_json_sha256(plan.get("targets")):
        raise PageGapExecutionMaterializeError("calculation outputs drifted after approval")


def _verify_transaction_postconditions(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    expected_rows: Mapping[tuple[str, str, str], Mapping[str, Any]] | None,
) -> None:
    del conn  # The analyzed snapshots are the transaction-consistent evidence.
    if after.get("state") != ALREADY_COMPLETE_STATUS:
        raise PageGapExecutionMaterializeError("all target horizons must be complete before commit")
    gap_counts = _mapping(after.get("global_gap_counts"), field_name="post gap counts")
    if gap_counts != {**{label: 0 for label in _HORIZON_LABELS}, "total": 0}:
        raise PageGapExecutionMaterializeError("all four global page gap counts must be zero")
    if before.get("row_count") != after.get("row_count"):
        raise PageGapExecutionMaterializeError("execution row count changed during materialization")
    if before.get("non_target_rows_sha256") != after.get("non_target_rows_sha256"):
        raise PageGapExecutionMaterializeError("a non-target execution row changed")
    if before.get("target_invariant_rows_sha256") != after.get("target_invariant_rows_sha256"):
        raise PageGapExecutionMaterializeError(
            "target raw returns, dates, prices, keys, or non-approved columns changed"
        )
    if int(after.get("pending_update_field_count") or 0) != 0:
        raise PageGapExecutionMaterializeError("post-transaction targets still require updates")
    if len(_mapping(after.get("_rows_by_key"), field_name="post rows by key")) != int(after.get("row_count") or 0):
        raise PageGapExecutionMaterializeError("logical execution keys are not globally unique")
    if expected_rows is not None:
        rows_by_key = _mapping(after.get("_rows_by_key"), field_name="post rows by key")
        for key, expected in expected_rows.items():
            rows = rows_by_key.get(key)
            if not isinstance(rows, list) or len(rows) != 1:
                raise PageGapExecutionMaterializeError("updated target row is unavailable")
            row = rows[0]
            for column, expected_value in _mapping(
                expected.get("updates"), field_name="expected target updates"
            ).items():
                actual = _optional_finite_float(row.get(column), field_name=column)
                if actual is None or not _float_equal(actual, float(expected_value)):
                    raise PageGapExecutionMaterializeError("updated target value changed before commit")
            if row.get("evidence_json") != expected.get("evidence_json"):
                raise PageGapExecutionMaterializeError("updated target evidence changed before commit")
    summary = _mapping(plan.get("summary"), field_name="plan summary")
    if int(before.get("row_count") or 0) != int(summary["row_count_before"]):
        raise PageGapExecutionMaterializeError("row count no longer matches approved plan")


def _build_pending_intent(
    *,
    plan: Mapping[str, Any],
    executed_at: str,
    approval_reference: str,
    materialization_run_id: str,
) -> dict[str, Any]:
    summary = _mapping(plan.get("summary"), field_name="plan summary")
    intent: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "intent_kind": PENDING_INTENT_KIND,
        "status": PENDING_STATUS,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": plan["approval_scope_sha256"],
        "materializer_rule_version": MATERIALIZER_RULE_VERSION,
        "materialization_run_id": materialization_run_id,
        "page_manifest_binding": plan["page_manifest_binding"],
        "factor_write_receipt_binding": plan["factor_write_receipt_binding"],
        "database": {
            "path": _mapping(plan["database"], field_name="plan database")["path"],
            "sha256_before": _mapping(plan["database"], field_name="plan database")["factor_write_after_sha256"],
            "sha256_after": None,
        },
        "rollback_anchor": plan["rollback_anchor"],
        "target_scope": plan["target_scope"],
        "target_execution_key_count": summary["target_execution_key_count"],
        "target_gap_horizon_count": summary["target_gap_horizon_count"],
        "planned_update_field_count": summary["pending_update_field_count"],
        "database_write_executed": False,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
    }
    intent["canonical_pending_intent_sha256"] = _pending_intent_sha256(intent)
    return intent


def _build_completed_receipt(
    *,
    plan: Mapping[str, Any],
    executed_at: str,
    approval_reference: str,
    materialization_run_id: str,
    database_sha256_before: str,
    database_sha256_after: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _mapping(plan.get("summary"), field_name="plan summary")
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "status": COMPLETED_STATUS,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "page_id": PAGE_ID,
        "page_route": PAGE_ROUTE,
        "page_metric_key": PAGE_METRIC_KEY,
        "materializer_rule_version": MATERIALIZER_RULE_VERSION,
        "materialization_run_id": materialization_run_id,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": plan["approval_scope_sha256"],
        "page_manifest_binding": plan["page_manifest_binding"],
        "factor_write_receipt_binding": plan["factor_write_receipt_binding"],
        "rollback_anchor": plan["rollback_anchor"],
        "target_scope": plan["target_scope"],
        "database": {
            "path": _mapping(plan["database"], field_name="plan database")["path"],
            "sha256_before": database_sha256_before,
            "sha256_after": database_sha256_after,
            "changed": True,
        },
        "target_execution_key_count": summary["target_execution_key_count"],
        "target_gap_horizon_count": summary["target_gap_horizon_count"],
        "updated_execution_key_count": summary["target_execution_key_count"],
        "updated_adjusted_field_count": summary["pending_update_field_count"],
        "target_rows_deleted": 0,
        "non_target_rows_changed": 0,
        "database_write_executed": True,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "verification": _verification_payload(before=before, after=after),
    }
    receipt["canonical_materialization_receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def _build_already_complete_receipt(
    *,
    plan: Mapping[str, Any],
    executed_at: str,
    approval_reference: str,
) -> dict[str, Any]:
    summary = _mapping(plan.get("summary"), field_name="plan summary")
    database = _mapping(plan.get("database"), field_name="plan database")
    current_sha = _sha256_text(database.get("current_sha256"), field_name="current DB SHA")
    scope = _mapping(plan.get("target_scope"), field_name="plan target scope")
    zero_gaps = {label: 0 for label in _HORIZON_LABELS}
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "status": ALREADY_COMPLETE_STATUS,
        "executed_at": executed_at,
        "approval_reference": approval_reference,
        "page_id": PAGE_ID,
        "page_route": PAGE_ROUTE,
        "page_metric_key": PAGE_METRIC_KEY,
        "materializer_rule_version": MATERIALIZER_RULE_VERSION,
        "materialization_run_id": None,
        "approval_scope": APPROVAL_SCOPE,
        "approval_scope_sha256": plan["approval_scope_sha256"],
        "page_manifest_binding": plan["page_manifest_binding"],
        "factor_write_receipt_binding": plan["factor_write_receipt_binding"],
        "rollback_anchor": plan["rollback_anchor"],
        "target_scope": plan["target_scope"],
        "database": {
            "path": database["path"],
            "sha256_before": current_sha,
            "sha256_after": current_sha,
            "changed": False,
        },
        "target_execution_key_count": summary["target_execution_key_count"],
        "target_gap_horizon_count": summary["target_gap_horizon_count"],
        "updated_execution_key_count": 0,
        "updated_adjusted_field_count": 0,
        "target_rows_deleted": 0,
        "non_target_rows_changed": 0,
        "database_write_executed": False,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "verification": {
            "row_count_before": summary["row_count_before"],
            "row_count_after": summary["row_count_before"],
            "page_gap_view_count_before": 0,
            "page_gap_view_count_after": 0,
            "horizon_gap_counts_before": zero_gaps,
            "horizon_gap_counts_after": zero_gaps,
            "logical_duplicate_key_count_after": 0,
            "non_target_rows_sha256_before": scope["non_target_rows_sha256_before"],
            "non_target_rows_sha256_after": scope["non_target_rows_sha256_before"],
            "target_invariant_rows_sha256_before": scope["target_invariant_rows_sha256_before"],
            "target_invariant_rows_sha256_after": scope["target_invariant_rows_sha256_before"],
        },
    }
    receipt["canonical_materialization_receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def _verification_payload(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_gaps = _mapping(before.get("global_gap_counts"), field_name="before gap counts")
    after_gaps = _mapping(after.get("global_gap_counts"), field_name="after gap counts")
    return {
        "row_count_before": before["row_count"],
        "row_count_after": after["row_count"],
        "page_gap_view_count_before": before_gaps["total"],
        "page_gap_view_count_after": after_gaps["total"],
        "horizon_gap_counts_before": {label: before_gaps[label] for label in _HORIZON_LABELS},
        "horizon_gap_counts_after": {label: after_gaps[label] for label in _HORIZON_LABELS},
        "logical_duplicate_key_count_after": 0,
        "non_target_rows_sha256_before": before["non_target_rows_sha256"],
        "non_target_rows_sha256_after": after["non_target_rows_sha256"],
        "target_invariant_rows_sha256_before": before["target_invariant_rows_sha256"],
        "target_invariant_rows_sha256_after": after["target_invariant_rows_sha256"],
    }


def _assert_materialization_evidence(
    *,
    evidence: Mapping[str, Any],
    key: Mapping[str, Any],
    horizons: Sequence[Mapping[str, Any]],
    page_manifest_canonical_sha256: str,
    factor_receipt_canonical_sha256: str,
    factor_receipt_file_sha256: str,
    expected_completion_evidence: Mapping[str, str] | None,
) -> None:
    trace = evidence.get(EVIDENCE_TRACE_KEY)
    if not isinstance(trace, Mapping):
        raise PageGapExecutionMaterializeError("completed target lacks governed page-gap materialization evidence")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "materializer_rule_version": MATERIALIZER_RULE_VERSION,
        "page_manifest_canonical_sha256": page_manifest_canonical_sha256,
        "factor_write_receipt_canonical_sha256": factor_receipt_canonical_sha256,
        "factor_write_receipt_file_sha256": factor_receipt_file_sha256,
        "target_execution_key": dict(key),
        "target_horizon_days": sorted(int(item["horizon_days"]) for item in horizons),
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
    }
    for field_name, expected_value in expected.items():
        if trace.get(field_name) != expected_value:
            raise PageGapExecutionMaterializeError(f"completed target evidence {field_name} binding mismatch")
    for field_name in (
        "approval_scope_sha256",
        "target_execution_keys_sha256",
        "target_horizons_sha256",
        "calculation_outputs_sha256",
    ):
        _sha256_text(trace.get(field_name), field_name=f"completed evidence {field_name}")
    _required_text(
        trace.get("materialization_run_id"),
        field_name="completed evidence materialization_run_id",
    )
    _utc_datetime_text(trace.get("executed_at"), field_name="completed evidence executed_at")
    if expected_completion_evidence is not None:
        for field_name, expected_value in expected_completion_evidence.items():
            if trace.get(field_name) != expected_value:
                raise PageGapExecutionMaterializeError(
                    f"completed target evidence {field_name} changed before verification"
                )


def _assert_completed_evidence_bindings(
    *,
    analysis: Mapping[str, Any],
    page_manifest_canonical_sha256: str,
    factor_receipt_canonical_sha256: str,
    factor_receipt_file_sha256: str,
    approval_scope_sha256: str,
    target_execution_keys_sha256: str,
    target_horizons_sha256: str,
    calculation_outputs_sha256: str,
) -> None:
    del page_manifest_canonical_sha256, factor_receipt_canonical_sha256, factor_receipt_file_sha256
    traces = _mapping(analysis.get("_completion_traces"), field_name="completion traces")
    if len(traces) != len(_sequence_of_mappings(analysis.get("targets"), field_name="targets")):
        raise PageGapExecutionMaterializeError("completed evidence trace count mismatch")
    run_ids: set[str] = set()
    executed_at_values: set[str] = set()
    for trace in traces.values():
        if not isinstance(trace, Mapping):
            raise PageGapExecutionMaterializeError("completed evidence trace is not a mapping")
        for field_name, expected in (
            ("approval_scope_sha256", approval_scope_sha256),
            ("target_execution_keys_sha256", target_execution_keys_sha256),
            ("target_horizons_sha256", target_horizons_sha256),
            ("calculation_outputs_sha256", calculation_outputs_sha256),
        ):
            if trace.get(field_name) != expected:
                raise PageGapExecutionMaterializeError(f"completed evidence does not bind current {field_name}")
        run_ids.add(str(trace.get("materialization_run_id")))
        executed_at_values.add(str(trace.get("executed_at")))
    if len(run_ids) != 1 or len(executed_at_values) != 1:
        raise PageGapExecutionMaterializeError("completed evidence must share one materialization run and timestamp")


def _verify_rollback_anchor(*, plan: Mapping[str, Any], target: Path) -> None:
    anchor = _mapping(plan.get("rollback_anchor"), field_name="plan rollback anchor")
    backup_path = _existing_file_no_links(
        _required_text(anchor.get("path"), field_name="rollback anchor path"),
        field_name="rollback anchor path",
    )
    if backup_path == target:
        raise PageGapExecutionMaterializeError("rollback anchor aliases live DuckDB")
    expected_sha = _sha256_text(anchor.get("sha256"), field_name="rollback anchor SHA")
    page_binding = _mapping(plan.get("page_manifest_binding"), field_name="page binding")
    if expected_sha != page_binding.get("database_sha256"):
        raise PageGapExecutionMaterializeError("rollback anchor must equal the pre-factor page manifest DB SHA")
    if _file_sha256(backup_path) != expected_sha:
        raise PageGapExecutionMaterializeError("rollback anchor content SHA changed")
    if anchor.get("reused_factor_prewrite_backup") is not True or anchor.get("second_backup_created") is not False:
        raise PageGapExecutionMaterializeError("rollback anchor reuse boundary mismatch")


def _assert_evidence_files_unchanged(
    *,
    page_manifest_path: Path,
    page_manifest_file_sha256: str,
    factor_receipt_path: Path,
    factor_receipt_file_sha256: str,
) -> None:
    for field_name, path, expected_sha in (
        ("page manifest", page_manifest_path, page_manifest_file_sha256),
        ("factor write receipt", factor_receipt_path, factor_receipt_file_sha256),
    ):
        _assert_no_symlink_or_junction(path, field_name=field_name)
        if not path.is_file() or _file_sha256(path) != expected_sha:
            raise PageGapExecutionMaterializeError(f"{field_name} changed during governed materialization")


def _assert_no_unmerged_duckdb_sidecars(target: Path) -> None:
    sidecars = (
        target.with_name(target.name + ".wal"),
        target.with_name(target.name + ".tmp"),
    )
    existing = [path.name for path in sidecars if os.path.lexists(path)]
    if existing:
        raise PageGapExecutionMaterializeError("unmerged DuckDB sidecar prevents governed materialization")


def _materialization_approval_scope_sha256(
    *,
    page_manifest_canonical_sha256: str,
    page_manifest_file_sha256: str,
    factor_write_receipt_canonical_sha256: str,
    factor_write_receipt_file_sha256: str,
    factor_database_sha256_after: str,
    target_execution_keys_sha256: str,
    target_horizons_sha256: str,
    calculation_outputs_sha256: str,
    target_execution_key_count: int,
    target_gap_horizon_count: int,
) -> str:
    return _canonical_json_sha256(
        {
            "operation": "stock_analysis_page_gap_execution_materialize",
            "approval_scope": APPROVAL_SCOPE,
            "materializer_rule_version": MATERIALIZER_RULE_VERSION,
            "page_manifest_canonical_sha256": page_manifest_canonical_sha256,
            "page_manifest_file_sha256": page_manifest_file_sha256,
            "factor_write_receipt_canonical_sha256": factor_write_receipt_canonical_sha256,
            "factor_write_receipt_file_sha256": factor_write_receipt_file_sha256,
            "factor_database_sha256_after": factor_database_sha256_after,
            "target_execution_keys_sha256": target_execution_keys_sha256,
            "target_horizons_sha256": target_horizons_sha256,
            "calculation_outputs_sha256": calculation_outputs_sha256,
            "target_execution_key_count": target_execution_key_count,
            "target_gap_horizon_count": target_gap_horizon_count,
        }
    )


def _normalize_target_cells(value: object) -> list[dict[str, str]]:
    cells = _sequence_of_mappings(value, field_name="factor receipt target_cells")
    normalized = [
        {
            "stock_code": _stock_code(cell.get("stock_code"), field_name="target cell stock_code"),
            "trade_date": _iso_date_text(cell.get("trade_date"), field_name="target cell trade_date"),
        }
        for cell in cells
    ]
    expected = sorted(normalized, key=lambda item: (item["trade_date"], item["stock_code"]))
    if normalized != expected:
        raise PageGapExecutionMaterializeError(
            "factor receipt target_cells must use canonical trade_date/stock_code order"
        )
    if len({(item["stock_code"], item["trade_date"]) for item in normalized}) != len(normalized):
        raise PageGapExecutionMaterializeError("factor receipt target_cells contains duplicates")
    return normalized


def _source_row_sha256(payload: Mapping[str, Any]) -> str:
    return _canonical_json_sha256({field_name: payload.get(field_name) for field_name in _SOURCE_ROW_HASH_FIELDS})


def _rows_sha256(rows: Sequence[Mapping[str, Any]], *, columns: Sequence[str]) -> str:
    normalized = [{column: _canonical_value(row.get(column)) for column in columns} for row in rows]
    normalized.sort(key=lambda row: _canonical_json_text(row))
    return _canonical_json_sha256(normalized)


def _horizon_count_rows(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(f"{int(item['horizon_days'])}d" for item in items)
    return [{"value": label, "count": counts[label]} for label in _HORIZON_LABELS]


def _horizon_count_rows_from_mapping(value: object) -> list[dict[str, Any]]:
    mapping = _mapping(value, field_name="horizon gap counts")
    return [{"value": label, "count": int(mapping.get(label) or 0)} for label in _HORIZON_LABELS]


def _signal_kind_count_rows(keys: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(item["signal_kind"]) for item in keys)
    return [{"value": value, "count": counts[value]} for value in sorted(counts)]


def _parse_evidence_json(value: object) -> dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {}
    if not isinstance(value, str):
        raise PageGapExecutionMaterializeError("execution evidence_json must be JSON text")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PageGapExecutionMaterializeError("execution evidence_json is invalid") from exc
    if not isinstance(payload, Mapping):
        raise PageGapExecutionMaterializeError("execution evidence_json must decode to an object")
    return dict(payload)


def _key_tuple(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _iso_date_text(value.get("signal_date"), field_name="key signal_date"),
        _stock_code(value.get("stock_code"), field_name="key stock_code"),
        _required_text(value.get("signal_kind"), field_name="key signal_kind"),
    )


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PageGapExecutionMaterializeError("execution row contains non-finite float")
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex().upper()
    return str(value)


def _mapping(value: object, *, field_name: str) -> dict[Any, Any]:
    if not isinstance(value, Mapping):
        raise PageGapExecutionMaterializeError(f"{field_name} must be a mapping")
    return dict(value)


def _sequence_of_mappings(value: object, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PageGapExecutionMaterializeError(f"{field_name} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise PageGapExecutionMaterializeError(f"{field_name} must contain only mappings")
        result.append(dict(item))
    return result


def _stock_code(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value != value.strip().upper() or not _STOCK_CODE_RE.fullmatch(value):
        raise PageGapExecutionMaterializeError(f"{field_name} must be a canonical A-share stock code")
    return value


def _iso_date_text(value: object, *, field_name: str) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise PageGapExecutionMaterializeError(f"{field_name} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PageGapExecutionMaterializeError(f"{field_name} must be an ISO date") from exc
    if value != parsed.isoformat():
        raise PageGapExecutionMaterializeError(f"{field_name} must be a canonical ISO date")
    return value


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise PageGapExecutionMaterializeError(f"{field_name} must be UTC datetime text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PageGapExecutionMaterializeError(f"{field_name} must be UTC datetime text") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise PageGapExecutionMaterializeError(f"{field_name} must be UTC datetime text")
    normalized = parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    if value != normalized:
        raise PageGapExecutionMaterializeError(f"{field_name} must be canonical UTC datetime text")
    return normalized


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PageGapExecutionMaterializeError(f"{field_name} must be non-empty canonical text")
    return value


def _sha256_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise PageGapExecutionMaterializeError(f"{field_name} must be an uppercase SHA-256")
    return value


def _positive_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise PageGapExecutionMaterializeError(f"{field_name} must be a positive integer")
    return value


def _finite_float(value: object, *, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PageGapExecutionMaterializeError(f"{field_name} must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise PageGapExecutionMaterializeError(f"{field_name} must be finite")
    return number


def _positive_finite_float(value: object, *, field_name: str) -> float:
    number = _finite_float(value, field_name=field_name)
    if number <= 0:
        raise PageGapExecutionMaterializeError(f"{field_name} must be positive")
    return number


def _nonnegative_finite_float(value: object, *, field_name: str) -> float:
    number = _finite_float(value, field_name=field_name)
    if number < 0:
        raise PageGapExecutionMaterializeError(f"{field_name} must be nonnegative")
    return number


def _optional_finite_float(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, field_name=field_name)


def _float_equal(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=_FLOAT_TOLERANCE, abs_tol=_FLOAT_TOLERANCE)


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_json_text(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_json_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json_text(payload).encode("utf-8")).hexdigest().upper()


def _plan_sha256(plan: Mapping[str, object]) -> str:
    payload = dict(plan)
    payload.pop("canonical_plan_sha256", None)
    return _canonical_json_sha256(payload)


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_materialization_receipt_sha256", None)
    return _canonical_json_sha256(payload)


def _pending_intent_sha256(intent: Mapping[str, object]) -> str:
    payload = dict(intent)
    payload.pop("canonical_pending_intent_sha256", None)
    return _canonical_json_sha256(payload)


def _file_sha256(path: Path) -> str:
    _assert_no_symlink_or_junction(path, field_name="hashed file")
    parent_identity = _path_identity(path.parent, field_name="hashed file parent")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        opened_identity = _stat_identity(os.fstat(handle.fileno()))
        if not stat_module.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise PageGapExecutionMaterializeError("hashed path must be a regular file")
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    _assert_opened_leaf_and_parent_unchanged(
        path,
        opened_identity=opened_identity,
        parent_identity=parent_identity,
        field_name="hashed file",
    )
    return digest.hexdigest().upper()


def _load_json_object(path: Path, *, field_name: str) -> dict[str, Any]:
    try:
        _assert_no_symlink_or_junction(path, field_name=field_name)
        parent_identity = _path_identity(path.parent, field_name=f"{field_name} parent")
        with path.open("r", encoding="utf-8") as handle:
            opened_stat = os.fstat(handle.fileno())
            if not stat_module.S_ISREG(opened_stat.st_mode):
                raise PageGapExecutionMaterializeError(f"{field_name} must be a regular file")
            opened_identity = _stat_identity(opened_stat)
            text = handle.read()
        _assert_opened_leaf_and_parent_unchanged(
            path,
            opened_identity=opened_identity,
            parent_identity=parent_identity,
            field_name=field_name,
        )
        payload = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PageGapExecutionMaterializeError(f"{field_name} must be readable UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise PageGapExecutionMaterializeError(f"{field_name} must contain a JSON object")
    return dict(payload)


def _write_json_exclusive(path: Path, *, payload: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    identity: tuple[int, int] | None = None
    parent_identity = _path_identity(path.parent, field_name="JSON output parent")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            stat = os.fstat(handle.fileno())
            identity = (stat.st_dev, stat.st_ino)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_opened_leaf_and_parent_unchanged(
            path,
            opened_identity=identity,
            parent_identity=parent_identity,
            field_name="JSON output",
        )
    except Exception:
        _remove_path_if_identity(
            path,
            identity=identity,
            parent_identity=parent_identity,
        )
        raise


def _remove_path_if_identity(
    path: Path,
    *,
    identity: tuple[int, int] | None,
    parent_identity: tuple[int, int] | None,
) -> bool:
    """Remove only this call's partial leaf under its original parent."""

    if identity is None or parent_identity is None:
        return False
    try:
        parent_stat = path.parent.stat(follow_symlinks=False)
        stat = path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return False
    if (
        path.parent.is_symlink()
        or getattr(path.parent, "is_junction", lambda: False)()
        or _stat_identity(parent_stat) != parent_identity
        or path.is_symlink()
        or getattr(path, "is_junction", lambda: False)()
        or _stat_identity(stat) != identity
    ):
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _replace_json_atomically_preserving_existing(
    path: Path,
    *,
    payload: Mapping[str, Any],
    expected_existing: Mapping[str, Any],
) -> None:
    _assert_no_symlink_or_junction(path, field_name="write_receipt_file")
    parent_identity = _path_identity(path.parent, field_name="write receipt parent")
    pending_identity = _path_identity(path, field_name="pending intent")
    if _load_json_object(path, field_name="pending intent") != dict(expected_existing):
        raise PageGapExecutionMaterializeError("pending intent changed before final receipt replacement")
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".completed.tmp",
        dir=path.parent,
        text=True,
    )
    temp_identity = _stat_identity(os.fstat(descriptor))
    temp_path = Path(raw_temp_path)
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        if _load_json_object(temp_path, field_name="temporary final receipt") != dict(payload):
            raise PageGapExecutionMaterializeError("temporary final receipt readback mismatch")
        if _path_identity(path, field_name="pending intent") != pending_identity:
            raise PageGapExecutionMaterializeError("pending intent file identity changed before finalization")
        if _path_identity(path.parent, field_name="write receipt parent") != parent_identity:
            raise PageGapExecutionMaterializeError("write receipt parent identity changed before finalization")
        os.replace(temp_path, path)
        replaced = True
        _assert_no_symlink_or_junction(path, field_name="final write receipt")
        if _path_identity(path, field_name="final write receipt") != temp_identity:
            raise PageGapExecutionMaterializeError(
                "final write receipt identity does not match generated temporary receipt"
            )
        if _path_identity(path.parent, field_name="write receipt parent") != parent_identity:
            raise PageGapExecutionMaterializeError("write receipt parent identity changed during finalization")
    finally:
        if not replaced:
            try:
                os.close(descriptor)
            except OSError:
                pass
            _remove_path_if_identity(
                temp_path,
                identity=temp_identity,
                parent_identity=parent_identity,
            )


def _existing_json_path_within_root(
    *,
    trusted_root: Path,
    path: str | Path,
    field_name: str,
) -> Path:
    candidate = _path_relative_to_root(trusted_root, path)
    result = _existing_file_no_links(candidate, field_name=field_name)
    _assert_path_within(trusted_root, result, field_name=field_name)
    if result.suffix.lower() != ".json":
        raise PageGapExecutionMaterializeError(f"{field_name} must use .json")
    return result


def _new_json_path_within_root(
    *,
    trusted_root: Path,
    path: str | Path,
    field_name: str,
) -> Path:
    candidate = _path_relative_to_root(trusted_root, path)
    _assert_no_symlink_or_junction(candidate, field_name=field_name)
    _assert_path_within(trusted_root, candidate, field_name=field_name)
    if candidate.suffix.lower() != ".json":
        raise PageGapExecutionMaterializeError(f"{field_name} must use .json")
    if os.path.lexists(candidate):
        raise PageGapExecutionMaterializeError(f"{field_name} must be new")
    if not candidate.parent.is_dir():
        raise PageGapExecutionMaterializeError(f"{field_name} parent must exist")
    return candidate


def _existing_file_no_links(path: str | Path | object, *, field_name: str) -> Path:
    candidate = _absolute_without_resolve(path)
    _assert_no_symlink_or_junction(candidate, field_name=field_name)
    if not candidate.is_file():
        raise PageGapExecutionMaterializeError(f"{field_name} must be an existing file")
    parent_identity = _path_identity(candidate.parent, field_name=f"{field_name} parent")
    leaf_identity = _path_identity(candidate, field_name=field_name)
    resolved = candidate.resolve(strict=True)
    if _path_identity(candidate.parent, field_name=f"{field_name} parent") != parent_identity:
        raise PageGapExecutionMaterializeError(f"{field_name} parent identity changed")
    if _path_identity(candidate, field_name=field_name) != leaf_identity:
        raise PageGapExecutionMaterializeError(f"{field_name} identity changed")
    return resolved


def _existing_directory_no_links(path: str | Path, *, field_name: str) -> Path:
    candidate = _absolute_without_resolve(path)
    _assert_no_symlink_or_junction(candidate, field_name=field_name)
    if not candidate.is_dir():
        raise PageGapExecutionMaterializeError(f"{field_name} must be an existing directory")
    return candidate.resolve(strict=True)


def _path_relative_to_root(root: Path, value: str | Path) -> Path:
    raw = Path(value)
    return _absolute_without_resolve(raw if raw.is_absolute() else root / raw)


def _assert_path_within(root: Path, path: Path, *, field_name: str) -> None:
    root_resolved = root.resolve(strict=True)
    candidate = _absolute_without_resolve(path)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PageGapExecutionMaterializeError(f"{field_name} must stay within trusted root") from exc
    _assert_no_symlink_or_junction(candidate, field_name=field_name)
    if candidate.parent.is_dir():
        try:
            candidate.parent.resolve(strict=True).relative_to(root_resolved)
        except ValueError as exc:
            raise PageGapExecutionMaterializeError(f"{field_name} resolved parent escapes trusted root") from exc


def _assert_no_symlink_or_junction(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise PageGapExecutionMaterializeError(f"{field_name} contains a symlink or junction component")


def _absolute_without_resolve(path: str | Path | object) -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise PageGapExecutionMaterializeError("path value is invalid")
    try:
        raw = os.fspath(path)
    except TypeError as exc:
        raise PageGapExecutionMaterializeError("path value is invalid") from exc
    return Path(os.path.normpath(os.path.abspath(raw)))


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        pass


def _path_identity(path: Path, *, field_name: str) -> tuple[int, int]:
    try:
        stat = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise PageGapExecutionMaterializeError(f"{field_name} identity is unavailable") from exc
    return _stat_identity(stat)


def _stat_identity(stat: os.stat_result) -> tuple[int, int]:
    return stat.st_dev, stat.st_ino


def _assert_opened_leaf_and_parent_unchanged(
    path: Path,
    *,
    opened_identity: tuple[int, int],
    parent_identity: tuple[int, int],
    field_name: str,
) -> None:
    _assert_no_symlink_or_junction(path, field_name=field_name)
    if _path_identity(path, field_name=field_name) != opened_identity:
        raise PageGapExecutionMaterializeError(f"{field_name} identity changed while open")
    if _path_identity(path.parent, field_name=f"{field_name} parent") != parent_identity:
        raise PageGapExecutionMaterializeError(f"{field_name} parent identity changed while open")
