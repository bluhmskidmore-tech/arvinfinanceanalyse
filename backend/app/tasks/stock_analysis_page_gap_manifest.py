"""Read-only page-gap manifest for /stock-analysis adjustment-factor discrepancies.

Per-row hashes prove only internal self-consistency. They are not signatures,
point-in-time availability evidence, external authenticity, or certification.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypeGuard, cast

import duckdb
from backend.app.tasks.livermore_candidate_history_materialize import (
    EXECUTION_FORMULA_VERSION as LEGACY_EXECUTION_FORMULA_VERSION,
)

SCHEMA_VERSION = 1
MANIFEST_KIND = "stock_analysis_page_gap_manifest_v1"
PAGE_ID = "GAP-STOCK-ANALYSIS-PAGE"
PAGE_ROUTE = "/stock-analysis"
PAGE_PRIMARY_API = "/api/data-health"
PAGE_METRIC_KEY = "data_health.adjustment_factor_gap"
RESULT_KIND = "data_health.overview"
RULE_VERSION = "rv_data_health_v1"
EXECUTION_TABLE = "livermore_candidate_execution_history"
FACTOR_TABLE = "stock_adjustment_factor"

SUCCESS_STATUSES = frozenset({"ready", "gaps_found"})
MANIFEST_STATUSES = SUCCESS_STATUSES | {"blocked"}
FACTOR_PRESENT_STATUS = "present_exact_cell"
FACTOR_MISSING_STATUS = "missing_exact_cell"
FACTOR_INVALID_STATUS = "invalid_exact_cell"
FACTOR_AMBIGUOUS_STATUS = "ambiguous_exact_cell"
FACTOR_STATUSES = frozenset(
    {
        FACTOR_PRESENT_STATUS,
        FACTOR_MISSING_STATUS,
        FACTOR_INVALID_STATUS,
        FACTOR_AMBIGUOUS_STATUS,
    }
)
ROLE_SCOPE_VALUES = frozenset({"entry_only", "exit_only", "both"})
GAP_CLASSIFICATIONS = frozenset(
    {
        "missing_entry_only",
        "missing_exit_only",
        "missing_both",
        "factors_present_history_unmaterialized",
    }
)
_REPAIRABLE_FACTOR_STATUSES = FACTOR_STATUSES
_CANONICAL_STOCK_CODE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")
_METRIC_SEMANTICS = (
    "count each horizon independently when return_*_net is non-null and "
    "return_*_net_adj is null across all physical execution rows and signal kinds"
)
_INTEGRITY_SEMANTICS = "self_consistency_only_no_external_authenticity"
_FULL_MATERIALIZATION_NOTE = (
    "Upper bound only: assumes every exact factor cell can be reconciled to a valid value and "
    "a full-horizon materializer rewrites every affected execution row."
)
_FACTOR_LOOKUP_BATCH_SIZE = 400
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
_HORIZONS: tuple[dict[str, str | int], ...] = (
    {
        "label": "1d",
        "days": 1,
        "raw_col": "return_1d_net",
        "adj_col": "return_1d_net_adj",
        "exit_date_col": "exit_date_1d",
        "exit_price_col": "exit_price_1d",
    },
    {
        "label": "5d",
        "days": 5,
        "raw_col": "return_5d_net",
        "adj_col": "return_5d_net_adj",
        "exit_date_col": "exit_date_5d",
        "exit_price_col": "exit_price_5d",
    },
    {
        "label": "10d",
        "days": 10,
        "raw_col": "return_10d_net",
        "adj_col": "return_10d_net_adj",
        "exit_date_col": "exit_date_10d",
        "exit_price_col": "exit_price_10d",
    },
    {
        "label": "20d",
        "days": 20,
        "raw_col": "return_20d_net",
        "adj_col": "return_20d_net_adj",
        "exit_date_col": "exit_date_20d",
        "exit_price_col": "exit_price_20d",
    },
)


def build_stock_analysis_page_gap_manifest(
    *,
    duckdb_path: str | Path,
    evaluation_as_of_date: str,
    created_at: str,
) -> dict[str, Any]:
    """Build the exact page-gap manifest without mutating DuckDB or the filesystem."""

    target = Path(duckdb_path).resolve()
    if not target.is_file():
        raise ValueError("duckdb_path must point to an existing DuckDB file")
    evaluation = _date_text(evaluation_as_of_date, field_name="evaluation_as_of_date")
    normalized_created_at = _utc_datetime_text(created_at, field_name="created_at")
    database_sha256_before = _file_sha256(target)

    conn: duckdb.DuckDBPyConnection | None = None
    blockers: list[str] = []
    gap_views: list[dict[str, Any]] = []
    missing_factor_cells: list[dict[str, Any]] = []
    physical_page_gap_view_count = 0
    legacy_targets_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    try:
        conn = duckdb.connect(str(target), read_only=True)
        _validate_required_schema(conn)
        legacy_targets_by_key = _legacy_repair_targets_by_key(conn, blockers)
        gap_views, physical_page_gap_view_count = _load_gap_views(
            conn,
            legacy_targets_by_key,
            blockers,
        )
        if gap_views:
            missing_factor_cells = _build_missing_factor_cells(gap_views)
        _append_factor_quality_blockers(gap_views, blockers)
    except (duckdb.Error, ValueError) as exc:
        blockers.append(f"manifest_source_unavailable:{type(exc).__name__}")
    finally:
        if conn is not None:
            conn.close()

    database_sha256_after = _file_sha256(target)
    database_unchanged = database_sha256_before == database_sha256_after
    if not database_unchanged:
        blockers.append("duckdb_changed_during_manifest_build")

    summary = _build_summary(
        gap_views=gap_views,
        missing_factor_cells=missing_factor_cells,
        legacy_targets_by_key=legacy_targets_by_key,
        blockers=blockers,
        physical_page_gap_view_count=physical_page_gap_view_count,
    )
    status = "blocked" if blockers else "gaps_found" if summary["page_gap_view_count_before"] > 0 else "ready"
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "status": status,
        "created_at": normalized_created_at,
        "evaluation_as_of_date": evaluation,
        "page_id": PAGE_ID,
        "page_route": PAGE_ROUTE,
        "primary_api": PAGE_PRIMARY_API,
        "page_metric_key": PAGE_METRIC_KEY,
        "source_contract": {
            "result_kind": RESULT_KIND,
            "rule_version": RULE_VERSION,
            "formal_use_allowed": False,
            "metric_semantics": _METRIC_SEMANTICS,
            "integrity_semantics": _INTEGRITY_SEMANTICS,
        },
        "approval_boundary": {
            "write_allowed": False,
            "materialization_allowed": False,
            "vendor_fetch_executed": False,
            "historical_availability_proven": False,
            "certification_allowed": False,
            "fallback_allowed": False,
        },
        "database": {
            "path": str(target),
            "sha256_before": database_sha256_before,
            "sha256_after": database_sha256_after,
            "unchanged": database_unchanged,
            "read_only": True,
        },
        "summary": summary,
        "legacy_repair_coverage": summary["legacy_repair_coverage"],
        "gap_views": gap_views,
        "missing_factor_cells": missing_factor_cells,
        "blockers": _ordered(blockers),
    }
    manifest["canonical_manifest_sha256"] = _canonical_sha256(manifest)
    return manifest


def validate_stock_analysis_page_gap_manifest(
    manifest: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    """Validate the full page tie-out, projections, references, and self hash."""

    if not isinstance(manifest, Mapping):
        return False, ("manifest must be a mapping",)
    payload = dict(manifest)
    errors: list[str] = []

    for field_name, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("manifest_kind", MANIFEST_KIND),
        ("page_id", PAGE_ID),
        ("page_route", PAGE_ROUTE),
        ("primary_api", PAGE_PRIMARY_API),
        ("page_metric_key", PAGE_METRIC_KEY),
    ):
        if payload.get(field_name) != expected:
            errors.append(f"manifest.{field_name} mismatch")
    status = payload.get("status")
    if status not in MANIFEST_STATUSES:
        errors.append("manifest.status is invalid")
    try:
        evaluation = _date_text(
            payload.get("evaluation_as_of_date"),
            field_name="evaluation_as_of_date",
        )
        if payload.get("evaluation_as_of_date") != evaluation:
            errors.append("manifest.evaluation_as_of_date is not canonical")
        created_at = _utc_datetime_text(payload.get("created_at"), field_name="created_at")
        if payload.get("created_at") != created_at:
            errors.append("manifest.created_at is not canonical UTC")
    except ValueError as exc:
        errors.append(str(exc))

    source_contract = payload.get("source_contract")
    if not isinstance(source_contract, Mapping):
        errors.append("manifest.source_contract must be a mapping")
    else:
        expected_source_contract = {
            "result_kind": RESULT_KIND,
            "rule_version": RULE_VERSION,
            "formal_use_allowed": False,
            "metric_semantics": _METRIC_SEMANTICS,
            "integrity_semantics": _INTEGRITY_SEMANTICS,
        }
        if dict(source_contract) != expected_source_contract:
            errors.append("manifest.source_contract mismatch")

    approval_boundary = payload.get("approval_boundary")
    expected_approval_boundary = {
        "write_allowed": False,
        "materialization_allowed": False,
        "vendor_fetch_executed": False,
        "historical_availability_proven": False,
        "certification_allowed": False,
        "fallback_allowed": False,
    }
    if not isinstance(approval_boundary, Mapping):
        errors.append("manifest.approval_boundary must be a mapping")
    elif dict(approval_boundary) != expected_approval_boundary:
        errors.append("manifest.approval_boundary mismatch")

    database = payload.get("database")
    if not isinstance(database, Mapping):
        errors.append("manifest.database must be a mapping")
    else:
        try:
            _required_text(database.get("path"), field_name="database.path")
            before_sha = _sha256_text(
                database.get("sha256_before"),
                field_name="database.sha256_before",
            )
            after_sha = _sha256_text(
                database.get("sha256_after"),
                field_name="database.sha256_after",
            )
            if before_sha != after_sha:
                errors.append("manifest.database hashes must match")
        except ValueError as exc:
            errors.append(str(exc))
        if database.get("unchanged") is not True:
            errors.append("manifest.database.unchanged must be true")
        if database.get("read_only") is not True:
            errors.append("manifest.database.read_only must be true")

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

    gap_views_raw = payload.get("gap_views")
    if not isinstance(gap_views_raw, list):
        errors.append("manifest.gap_views must be a list")
        gap_views: list[object] = []
    else:
        gap_views = gap_views_raw

    normalized_gap_views: list[dict[str, Any]] = []
    gap_view_ids: set[str] = set()
    natural_groups: defaultdict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    required_factor_statuses: dict[tuple[str, str], str] = {}
    expected_missing_references: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    horizon_counts: Counter[str] = Counter()
    signal_kind_counts: Counter[str] = Counter()
    classification_counts: dict[str, Counter[str]] = {str(horizon["label"]): Counter() for horizon in _HORIZONS}
    targeted_horizon_counts: Counter[str] = Counter()
    targeted_gap_count = 0
    unique_execution_keys: set[tuple[str, str, str]] = set()

    for index, raw_view in enumerate(gap_views):
        if not isinstance(raw_view, Mapping):
            errors.append(f"manifest.gap_views[{index}] must be a mapping")
            continue
        view = dict(raw_view)
        try:
            signal_date = _date_text(
                view.get("signal_date"),
                field_name=f"gap_views[{index}].signal_date",
            )
            stock_code = _stock_code(
                view.get("stock_code"),
                field_name=f"gap_views[{index}].stock_code",
            )
            signal_kind = _trace_text(
                view.get("signal_kind"),
                field_name=f"gap_views[{index}].signal_kind",
            )
            horizon_days = _horizon_days(
                view.get("horizon_days"),
                field_name=f"gap_views[{index}].horizon_days",
            )
            horizon_label = _required_text(
                view.get("horizon_label"),
                field_name=f"gap_views[{index}].horizon_label",
            )
            occurrence_ordinal = _positive_int(
                view.get("occurrence_ordinal"),
                field_name=f"gap_views[{index}].occurrence_ordinal",
            )
            physical_row_count = _positive_int(
                view.get("physical_row_count_for_natural_key"),
                field_name=f"gap_views[{index}].physical_row_count_for_natural_key",
            )
            gap_view_id = _sha256_text(
                view.get("gap_view_id"),
                field_name=f"gap_views[{index}].gap_view_id",
            )
            entry_date = _date_text(
                view.get("entry_date"),
                field_name=f"gap_views[{index}].entry_date",
            )
            exit_date = _date_text(
                view.get("exit_date"),
                field_name=f"gap_views[{index}].exit_date",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        expected_horizon_label = f"{horizon_days}d"
        if horizon_label != expected_horizon_label:
            errors.append(f"manifest.gap_views[{index}].horizon_label mismatch")
        expected_gap_view_id = _gap_view_id(
            signal_date=signal_date,
            stock_code=stock_code,
            signal_kind=signal_kind,
            horizon_days=horizon_days,
            occurrence_ordinal=occurrence_ordinal,
        )
        if gap_view_id != expected_gap_view_id:
            errors.append(f"manifest.gap_views[{index}].gap_view_id mismatch")
        if gap_view_id in gap_view_ids:
            errors.append("manifest.gap_views contains duplicate gap_view_id")
        gap_view_ids.add(gap_view_id)

        for trace_field in (
            "stock_name",
            "market_state",
            "data_status",
            "formula_version",
            "run_id",
        ):
            try:
                _trace_text(
                    view.get(trace_field),
                    field_name=f"gap_views[{index}].{trace_field}",
                )
            except ValueError as exc:
                errors.append(str(exc))
        try:
            _positive_int(
                view.get("candidate_rank"),
                field_name=f"gap_views[{index}].candidate_rank",
            )
        except ValueError as exc:
            errors.append(str(exc))
        if not _is_positive_finite(view.get("signal_close")):
            errors.append(f"manifest.gap_views[{index}].signal_close must be positive finite")
        try:
            source_row_sha256 = _sha256_text(
                view.get("source_row_sha256"),
                field_name=f"gap_views[{index}].source_row_sha256",
            )
            expected_source_row_sha256 = _source_row_sha256(view)
            if source_row_sha256 != expected_source_row_sha256:
                errors.append(f"manifest.gap_views[{index}].source_row_sha256 mismatch")
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))

        natural_key = (signal_date, stock_code, signal_kind, horizon_days)
        natural_groups[natural_key].append(view)
        view["_validated_occurrence_ordinal"] = occurrence_ordinal
        view["_validated_physical_row_count"] = physical_row_count
        if not _is_positive_finite(view.get("entry_price")):
            errors.append(f"manifest.gap_views[{index}].entry_price must be positive finite")
        if not _is_positive_finite(view.get("exit_price")):
            errors.append(f"manifest.gap_views[{index}].exit_price must be positive finite")
        if not _is_number(view.get("raw_return_net")):
            errors.append(f"manifest.gap_views[{index}].raw_return_net must be finite")
        if view.get("adjusted_return_net") is not None:
            errors.append(f"manifest.gap_views[{index}].adjusted_return_net must remain null")

        factor_statuses: dict[str, str] = {}
        for factor_role, factor_key, expected_date in (
            ("entry", "entry_factor", entry_date),
            ("exit", "exit_factor", exit_date),
        ):
            factor = view.get(factor_key)
            if not isinstance(factor, Mapping):
                errors.append(f"manifest.gap_views[{index}].{factor_key} must be a mapping")
                continue
            try:
                factor_stock_code = _stock_code(
                    factor.get("stock_code"),
                    field_name=f"gap_views[{index}].{factor_key}.stock_code",
                )
                factor_trade_date = _date_text(
                    factor.get("trade_date"),
                    field_name=f"gap_views[{index}].{factor_key}.trade_date",
                )
                factor_status = _factor_status(
                    factor.get("status"),
                    field_name=f"gap_views[{index}].{factor_key}.status",
                )
                observed_row_count = _int_value(
                    factor.get("observed_row_count"),
                    field_name=f"gap_views[{index}].{factor_key}.observed_row_count",
                )
                distinct_count = _int_value(
                    factor.get("distinct_observation_count"),
                    field_name=f"gap_views[{index}].{factor_key}.distinct_observation_count",
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if factor_stock_code != stock_code:
                errors.append(f"manifest.gap_views[{index}].{factor_key}.stock_code mismatch")
            if factor_trade_date != expected_date:
                errors.append(f"manifest.gap_views[{index}].{factor_key}.trade_date mismatch")
            cell_key = (factor_stock_code, factor_trade_date)
            prior_status = required_factor_statuses.setdefault(cell_key, factor_status)
            if prior_status != factor_status:
                errors.append(f"manifest factor status inconsistent for {factor_stock_code}:{factor_trade_date}")
            factor_statuses[factor_role] = factor_status
            source_identity = factor.get("source_identity")
            if factor_status == FACTOR_PRESENT_STATUS:
                if observed_row_count != 1 or distinct_count != 1:
                    errors.append(f"manifest.gap_views[{index}].{factor_key} present count mismatch")
                if not _is_positive_finite(factor.get("adj_factor")):
                    errors.append(f"manifest.gap_views[{index}].{factor_key}.adj_factor invalid")
                if not isinstance(source_identity, Mapping):
                    errors.append(f"manifest.gap_views[{index}].{factor_key}.source_identity missing")
                else:
                    try:
                        _required_text(
                            source_identity.get("source_version"),
                            field_name=f"gap_views[{index}].{factor_key}.source_version",
                        )
                        _required_text(
                            source_identity.get("run_id"),
                            field_name=f"gap_views[{index}].{factor_key}.run_id",
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
            else:
                if factor.get("adj_factor") is not None or source_identity is not None:
                    errors.append(f"manifest.gap_views[{index}].{factor_key} unresolved payload mismatch")
                if factor_status == FACTOR_MISSING_STATUS and (observed_row_count != 0 or distinct_count != 0):
                    errors.append(f"manifest.gap_views[{index}].{factor_key} missing count mismatch")
                if factor_status == FACTOR_INVALID_STATUS and observed_row_count < 1:
                    errors.append(f"manifest.gap_views[{index}].{factor_key} invalid count mismatch")
                if factor_status == FACTOR_AMBIGUOUS_STATUS and observed_row_count < 2:
                    errors.append(f"manifest.gap_views[{index}].{factor_key} ambiguous count mismatch")
                expected_missing_references[cell_key].append(
                    {
                        "gap_view_id": gap_view_id,
                        "signal_date": signal_date,
                        "signal_kind": signal_kind,
                        "horizon_label": horizon_label,
                        "horizon_days": horizon_days,
                        "factor_role": factor_role,
                        "status": factor_status,
                    }
                )

        if set(factor_statuses) == {"entry", "exit"}:
            expected_classification = _classification_from_statuses(
                factor_statuses["entry"],
                factor_statuses["exit"],
            )
            if view.get("classification") != expected_classification:
                errors.append(f"manifest.gap_views[{index}].classification mismatch")
            if view.get("missing_reason") != _missing_reason_from_statuses(
                factor_statuses["entry"],
                factor_statuses["exit"],
            ):
                errors.append(f"manifest.gap_views[{index}].missing_reason mismatch")
            classification_counts[horizon_label][expected_classification] += 1

        targeted = view.get("legacy_repair_targeted")
        if targeted not in {True, False}:
            errors.append(f"manifest.gap_views[{index}].legacy_repair_targeted must be boolean")
        reasons = view.get("legacy_repair_reasons")
        remaining_reasons = view.get("legacy_repair_remaining_reasons")
        if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
            errors.append(f"manifest.gap_views[{index}].legacy_repair_reasons invalid")
        if not isinstance(remaining_reasons, list) or remaining_reasons:
            errors.append(f"manifest.gap_views[{index}].legacy_repair_remaining_reasons must be empty")
        if view.get("legacy_repair_repairable") is not False:
            errors.append(f"manifest.gap_views[{index}].legacy_repair_repairable must be false")
        if targeted is True:
            targeted_gap_count += 1
            targeted_horizon_counts[horizon_label] += 1
            if not reasons:
                errors.append(f"manifest.gap_views[{index}] targeted selector needs reasons")
        elif reasons:
            errors.append(f"manifest.gap_views[{index}] untargeted selector cannot have reasons")

        horizon_counts[horizon_label] += 1
        signal_kind_counts[signal_kind] += 1
        unique_execution_keys.add((signal_date, stock_code, signal_kind))
        normalized_gap_views.append(view)

    for natural_key, group in natural_groups.items():
        expected_count = len(group)
        ordinals = sorted(int(view["_validated_occurrence_ordinal"]) for view in group)
        physical_counts = {int(view["_validated_physical_row_count"]) for view in group}
        if ordinals != list(range(1, expected_count + 1)):
            errors.append(f"manifest.gap_views occurrence ordinals mismatch:{natural_key}")
        if physical_counts != {expected_count}:
            errors.append(f"manifest.gap_views physical duplicate count mismatch:{natural_key}")
        if expected_count > 1 and not any(
            blocker.startswith(
                f"duplicate_gap_view_key:{natural_key[0]}:{natural_key[1]}:{natural_key[2]}:{natural_key[3]}:"
            )
            for blocker in blockers
        ):
            errors.append(f"manifest duplicate natural key lacks blocker:{natural_key}")

    sort_keys = [
        (
            str(view.get("signal_date")),
            str(view.get("stock_code")),
            str(view.get("signal_kind")),
            int(view.get("horizon_days") or 0),
            int(view.get("occurrence_ordinal") or 0),
        )
        for view in normalized_gap_views
    ]
    if sort_keys != sorted(sort_keys):
        errors.append("manifest.gap_views must be canonically sorted")

    missing_raw = payload.get("missing_factor_cells")
    if not isinstance(missing_raw, list):
        errors.append("manifest.missing_factor_cells must be a list")
        missing_factor_cells: list[object] = []
    else:
        missing_factor_cells = missing_raw
    seen_missing_keys: set[tuple[str, str]] = set()
    role_scope_counts: Counter[str] = Counter()
    missing_requirement_use_count = 0
    missing_sort_keys: list[tuple[str, str]] = []
    for index, raw_cell in enumerate(missing_factor_cells):
        if not isinstance(raw_cell, Mapping):
            errors.append(f"manifest.missing_factor_cells[{index}] must be a mapping")
            continue
        cell = dict(raw_cell)
        try:
            stock_code = _stock_code(
                cell.get("stock_code"),
                field_name=f"missing_factor_cells[{index}].stock_code",
            )
            trade_date = _date_text(
                cell.get("trade_date"),
                field_name=f"missing_factor_cells[{index}].trade_date",
            )
            cell_id = _sha256_text(
                cell.get("missing_factor_cell_id"),
                field_name=f"missing_factor_cells[{index}].missing_factor_cell_id",
            )
            factor_status = _factor_status(
                cell.get("status"),
                field_name=f"missing_factor_cells[{index}].status",
            )
            role_scope = _role_scope(
                cell.get("role_scope"),
                field_name=f"missing_factor_cells[{index}].role_scope",
            )
            reference_count = _int_value(
                cell.get("gap_view_reference_count"),
                field_name=f"missing_factor_cells[{index}].gap_view_reference_count",
            )
            dependent_gap_count = _int_value(
                cell.get("dependent_gap_count"),
                field_name=f"missing_factor_cells[{index}].dependent_gap_count",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key = (stock_code, trade_date)
        if cell_id != _missing_factor_cell_id(stock_code=stock_code, trade_date=trade_date):
            errors.append(f"manifest.missing_factor_cells[{index}].missing_factor_cell_id mismatch")
        if factor_status == FACTOR_PRESENT_STATUS:
            errors.append(f"manifest.missing_factor_cells[{index}].status must not be present")
        if key in seen_missing_keys:
            errors.append("manifest.missing_factor_cells contains duplicate physical cells")
        seen_missing_keys.add(key)
        missing_sort_keys.append(key)

        expected_references = sorted(
            expected_missing_references.get(key, []),
            key=lambda item: (
                item["signal_date"],
                item["signal_kind"],
                item["horizon_days"],
                item["factor_role"],
            ),
        )
        references = cell.get("gap_view_references")
        if not isinstance(references, list):
            errors.append(f"missing_factor_cells[{index}].gap_view_references must be a list")
            references = []
        if references != expected_references:
            errors.append(f"missing_factor_cells[{index}].gap_view_references mismatch")
        if reference_count != len(expected_references):
            errors.append(f"missing_factor_cells[{index}].gap_view_reference_count mismatch")
        expected_dependent_count = len({str(reference["gap_view_id"]) for reference in expected_references})
        if dependent_gap_count != expected_dependent_count:
            errors.append(f"missing_factor_cells[{index}].dependent_gap_count mismatch")
        entry_count = sum(1 for reference in expected_references if reference["factor_role"] == "entry")
        exit_count = len(expected_references) - entry_count
        expected_role_counts = {"entry": entry_count, "exit": exit_count}
        if cell.get("role_use_counts") != expected_role_counts:
            errors.append(f"missing_factor_cells[{index}].role_use_counts mismatch")
        expected_scope = "both" if entry_count and exit_count else "entry_only" if entry_count else "exit_only"
        if role_scope != expected_scope:
            errors.append(f"missing_factor_cells[{index}].role_scope mismatch")
        expected_status = required_factor_statuses.get(key)
        if expected_status != factor_status:
            errors.append(f"missing_factor_cells[{index}].status mismatch")
        if cell.get("cell_statuses") != [factor_status]:
            errors.append(f"missing_factor_cells[{index}].cell_statuses mismatch")
        role_scope_counts[role_scope] += 1
        missing_requirement_use_count += len(expected_references)

    if missing_sort_keys != sorted(missing_sort_keys):
        errors.append("manifest.missing_factor_cells must be canonically sorted")
    if seen_missing_keys != set(expected_missing_references):
        errors.append("manifest.missing_factor_cells does not tie to gap factor requirements")

    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("manifest.summary must be a mapping")
        summary = {}
    mapped_gap_count = len(normalized_gap_views)
    physical_gap_count = _summary_int(
        summary,
        "page_gap_view_count_before",
        errors,
    )
    if _summary_int(summary, "mapped_gap_view_count", errors) != mapped_gap_count:
        errors.append("manifest.summary.mapped_gap_view_count mismatch")
    if physical_gap_count < mapped_gap_count:
        errors.append("manifest.summary.page_gap_view_count_before cannot be below mapped count")
    if physical_gap_count != mapped_gap_count and not any(
        blocker.startswith("page_gap_physical_mapping_mismatch:") for blocker in blockers
    ):
        errors.append("manifest physical mapping mismatch lacks blocker")

    expected_factor_write_gap = physical_gap_count
    if _summary_int(summary, "factor_write_only_projected_gap_view_count", errors) != expected_factor_write_gap:
        errors.append("manifest.summary.factor_write_only_projected_gap_view_count mismatch")
    if _summary_int(summary, "factor_write_only_reduction", errors) != 0:
        errors.append("manifest.summary.factor_write_only_reduction mismatch")

    structurally_unclearable = sum(1 for view in normalized_gap_views if not _view_conditionally_clearable(view))
    expected_full_gap = physical_gap_count if blockers else structurally_unclearable
    if (
        _summary_int(
            summary,
            "conditional_full_materialization_projected_gap_view_count",
            errors,
        )
        != expected_full_gap
    ):
        errors.append("manifest.summary.conditional_full_materialization_projected_gap_view_count mismatch")
    if (
        _summary_int(summary, "conditional_full_materialization_reduction", errors)
        != physical_gap_count - expected_full_gap
    ):
        errors.append("manifest.summary.conditional_full_materialization_reduction mismatch")
    if summary.get("conditional_full_materialization_note") != _FULL_MATERIALIZATION_NOTE:
        errors.append("manifest.summary.conditional_full_materialization_note mismatch")

    current_recomputable = sum(
        1
        for view in normalized_gap_views
        if str(view["entry_factor"]["status"]) == FACTOR_PRESENT_STATUS
        and str(view["exit_factor"]["status"]) == FACTOR_PRESENT_STATUS
    )
    summary_checks = {
        "current_recomputable_gap_view_count": current_recomputable,
        "unique_execution_key_count": len(unique_execution_keys),
        "unique_required_factor_cell_count": len(required_factor_statuses),
        "required_factor_requirement_count": mapped_gap_count * 2,
        "present_required_factor_cell_count": sum(
            1 for factor_status in required_factor_statuses.values() if factor_status == FACTOR_PRESENT_STATUS
        ),
        "unique_missing_factor_cell_count": len(seen_missing_keys),
        "missing_factor_requirement_use_count": missing_requirement_use_count,
    }
    for field_name, expected in summary_checks.items():
        if _summary_int(summary, field_name, errors) != expected:
            errors.append(f"manifest.summary.{field_name} mismatch")

    if summary.get("horizon_counts") != _distribution_list(horizon_counts):
        errors.append("manifest.summary.horizon_counts mismatch")
    if summary.get("signal_kind_counts") != _distribution_list(signal_kind_counts):
        errors.append("manifest.summary.signal_kind_counts mismatch")
    if summary.get("missing_factor_role_scope_counts") != _distribution_list(role_scope_counts):
        errors.append("manifest.summary.missing_factor_role_scope_counts mismatch")
    expected_classification_counts = {
        str(horizon["label"]): {
            classification: classification_counts[str(horizon["label"])][classification]
            for classification in sorted(GAP_CLASSIFICATIONS)
        }
        for horizon in _HORIZONS
    }
    if summary.get("classification_counts_by_horizon") != expected_classification_counts:
        errors.append("manifest.summary.classification_counts_by_horizon mismatch")
    expected_factor_quality = {
        "missing_required_cell_count": sum(
            1 for factor_status in required_factor_statuses.values() if factor_status == FACTOR_MISSING_STATUS
        ),
        "invalid_required_cell_count": sum(
            1 for factor_status in required_factor_statuses.values() if factor_status == FACTOR_INVALID_STATUS
        ),
        "ambiguous_required_cell_count": sum(
            1 for factor_status in required_factor_statuses.values() if factor_status == FACTOR_AMBIGUOUS_STATUS
        ),
    }
    if summary.get("factor_quality") != expected_factor_quality:
        errors.append("manifest.summary.factor_quality mismatch")

    legacy_coverage = payload.get("legacy_repair_coverage")
    if not isinstance(legacy_coverage, Mapping):
        errors.append("manifest.legacy_repair_coverage must be a mapping")
        legacy_coverage = {}
    expected_legacy_static: dict[str, object] = {
        "coverage_kind": "selector_candidate",
        "selector_signal_kind": "stock_candidate",
        "selector_scope_only": True,
        "effective_repair_preview_executed": False,
    }
    for field_name, expected_static_value in expected_legacy_static.items():
        if legacy_coverage.get(field_name) != expected_static_value:
            errors.append(f"manifest.legacy_repair_coverage.{field_name} mismatch")
    selector_candidate_count = _summary_int(
        legacy_coverage,
        "selector_candidate_logical_key_count",
        errors,
        prefix="manifest.legacy_repair_coverage",
    )
    targeted_unique_keys = {
        (
            str(view.get("signal_date")),
            str(view.get("stock_code")),
            str(view.get("signal_kind")),
        )
        for view in normalized_gap_views
        if view.get("legacy_repair_targeted") is True
    }
    if selector_candidate_count < len(targeted_unique_keys):
        errors.append("manifest.legacy_repair_coverage selector candidate count too small")
    if (
        _summary_int(
            legacy_coverage,
            "covered_gap_view_count",
            errors,
            prefix="manifest.legacy_repair_coverage",
        )
        != targeted_gap_count
    ):
        errors.append("manifest.legacy_repair_coverage.covered_gap_view_count mismatch")
    if legacy_coverage.get("covered_horizon_counts") != _distribution_list(targeted_horizon_counts):
        errors.append("manifest.legacy_repair_coverage.covered_horizon_counts mismatch")
    if summary.get("legacy_repair_coverage") != legacy_coverage:
        errors.append("manifest summary/top-level legacy_repair_coverage mismatch")

    ambiguous_required_count = expected_factor_quality["ambiguous_required_cell_count"]
    invalid_required_count = expected_factor_quality["invalid_required_cell_count"]
    if ambiguous_required_count and (f"ambiguous_required_factor_cells:{ambiguous_required_count}" not in blockers):
        errors.append("manifest ambiguous factor cells lack blocker")
    if invalid_required_count and (f"invalid_required_factor_cells:{invalid_required_count}" not in blockers):
        errors.append("manifest invalid factor cells lack blocker")

    expected_status = "blocked" if blockers else "gaps_found" if physical_gap_count > 0 else "ready"
    if status != expected_status:
        errors.append("manifest.status does not match blockers/page gaps")

    try:
        expected_hash = _canonical_sha256(payload)
    except (TypeError, ValueError) as exc:
        errors.append(f"manifest canonical serialization failed:{exc}")
    else:
        try:
            observed_hash = _sha256_text(
                payload.get("canonical_manifest_sha256"),
                field_name="canonical_manifest_sha256",
            )
        except ValueError as exc:
            errors.append(str(exc))
            observed_hash = ""
        if observed_hash != expected_hash:
            errors.append("manifest.canonical_manifest_sha256 mismatch")
    return not errors, tuple(errors)


def _validate_required_schema(conn: duckdb.DuckDBPyConnection) -> None:
    tables = _table_names(conn)
    if EXECUTION_TABLE not in tables:
        raise ValueError(f"required table missing: {EXECUTION_TABLE}")
    if FACTOR_TABLE not in tables:
        raise ValueError(f"required table missing: {FACTOR_TABLE}")
    execution_columns = _table_columns(conn, EXECUTION_TABLE)
    required_execution = {
        "signal_date",
        "stock_code",
        "signal_kind",
        "entry_date",
        "entry_price",
        "entry_executable",
        "signal_close",
        "formula_version",
        "run_id",
        "data_status",
    }
    for horizon in _HORIZONS:
        required_execution.update(
            {
                str(horizon["raw_col"]),
                str(horizon["adj_col"]),
                str(horizon["exit_date_col"]),
                str(horizon["exit_price_col"]),
            }
        )
    missing_execution = sorted(required_execution.difference(execution_columns))
    if missing_execution:
        raise ValueError("execution schema missing: " + ",".join(missing_execution))
    factor_columns = _table_columns(conn, FACTOR_TABLE)
    required_factor = {"stock_code", "trade_date", "adj_factor", "source_version", "run_id"}
    missing_factor = sorted(required_factor.difference(factor_columns))
    if missing_factor:
        raise ValueError("factor schema missing: " + ",".join(missing_factor))


def _legacy_repair_targets_by_key(
    conn: duckdb.DuckDBPyConnection,
    blockers: list[str],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Reproduce only the legacy selector, never its recompute/write path."""

    try:
        rows = conn.execute(
            f"""
            with scoped as (
              select
                signal_date,
                stock_code,
                signal_kind,
                max(
                  case
                    when entry_executable is true
                     and return_20d_net is not null
                     and return_20d_net_adj is null
                    then 1 else 0
                  end
                ) over logical_key as has_raw_20d_gap,
                max(
                  case when lower(coalesce(data_status, '')) = 'pending' then 1 else 0 end
                ) over logical_key as has_pending,
                max(
                  case when coalesce(formula_version, '') <> ? then 1 else 0 end
                ) over logical_key as has_stale_formula,
                count(*) over logical_key as physical_row_count,
                row_number() over (
                  logical_key
                  order by case when formula_version = ? then 0 else 1 end,
                           run_id desc nulls last
                ) as logical_row_number
              from {EXECUTION_TABLE}
              where signal_kind = 'stock_candidate'
              window logical_key as (partition by signal_date, stock_code, signal_kind)
            )
            select
              signal_date,
              stock_code,
              signal_kind,
              has_raw_20d_gap,
              has_pending,
              has_stale_formula,
              physical_row_count
            from scoped
            where logical_row_number = 1
              and (has_raw_20d_gap = 1 or has_pending = 1 or has_stale_formula = 1)
            order by signal_date, stock_code, signal_kind
            """,
            [LEGACY_EXECUTION_FORMULA_VERSION, LEGACY_EXECUTION_FORMULA_VERSION],
        ).fetchall()
    except duckdb.Error as exc:
        blockers.append(f"legacy_repair_target_audit_failed:{type(exc).__name__}")
        return {}
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        try:
            signal_date = _date_text(row[0], field_name="legacy_target.signal_date")
            stock_code = _stock_code(row[1], field_name="legacy_target.stock_code")
            signal_kind = _required_text(row[2], field_name="legacy_target.signal_kind")
        except ValueError:
            blockers.append("legacy_repair_selector_contains_noncanonical_key")
            continue
        reasons: list[str] = []
        if bool(row[3]):
            reasons.append("raw_20d_without_adjusted_20d")
        if bool(row[4]):
            reasons.append("pending")
        if bool(row[5]):
            reasons.append("formula_version_stale")
        result[(signal_date, stock_code, signal_kind)] = {
            "key": {
                "signal_date": signal_date,
                "stock_code": stock_code,
                "signal_kind": signal_kind,
            },
            "reasons": reasons,
            "remaining_reasons": [],
            "repairable": False,
            "selector_scope_only": True,
            "effective_repair_preview_executed": False,
            "physical_row_count": int(row[6] or 0),
        }
    return result


def _load_gap_views(
    conn: duckdb.DuckDBPyConnection,
    legacy_targets_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
    blockers: list[str],
) -> tuple[list[dict[str, Any]], int]:
    union_sql = []
    for horizon in _HORIZONS:
        label = str(horizon["label"])
        days = int(horizon["days"])
        raw_col = str(horizon["raw_col"])
        adj_col = str(horizon["adj_col"])
        exit_date_col = str(horizon["exit_date_col"])
        exit_price_col = str(horizon["exit_price_col"])
        union_sql.append(
            f"""
            select
              signal_date,
              stock_code,
              signal_kind,
              stock_name,
              candidate_rank,
              market_state,
              data_status,
              formula_version,
              run_id,
              signal_close,
              entry_date,
              entry_price,
              {exit_date_col} as exit_date,
              {exit_price_col} as exit_price,
              {raw_col} as raw_return_net,
              {adj_col} as adjusted_return_net,
              '{label}' as horizon_label,
              {days} as horizon_days
            from {EXECUTION_TABLE}
            where {raw_col} is not null and {adj_col} is null
            """
        )
    rows = conn.execute(
        "select * from ("
        + "\nunion all\n".join(union_sql)
        + ") page_gap_rows "
        + "order by signal_date, stock_code, signal_kind, horizon_days, "
        + "formula_version, run_id, entry_date, exit_date, entry_price, exit_price, "
        + "raw_return_net, stock_name, candidate_rank, market_state, data_status, signal_close"
    ).fetchall()
    gap_views: list[dict[str, Any]] = []
    gap_key_counts: Counter[tuple[str, str, str, int]] = Counter()
    required_factor_cells: set[tuple[str, str]] = set()
    for row in rows:
        signal_date = _normalize_trade_date_iso(row[0])
        stock_code = _stock_code_or_none(row[1])
        signal_kind = _trace_text_or_none(row[2])
        entry_date = _normalize_trade_date_iso(row[10])
        exit_date = _normalize_trade_date_iso(row[12])
        if signal_date is None or stock_code is None or signal_kind is None:
            continue
        key = (signal_date, stock_code, signal_kind, int(row[17]))
        gap_key_counts[key] += 1
        if entry_date is not None:
            required_factor_cells.add((stock_code, entry_date))
        if exit_date is not None:
            required_factor_cells.add((stock_code, exit_date))
    factor_cache = _load_factor_cache(conn, required_factor_cells)
    occurrence_ordinals: Counter[tuple[str, str, str, int]] = Counter()
    for row in rows:
        signal_date = _normalize_trade_date_iso(row[0])
        stock_code = _stock_code_or_none(row[1])
        signal_kind = _trace_text_or_none(row[2])
        entry_date = _normalize_trade_date_iso(row[10])
        exit_date = _normalize_trade_date_iso(row[12])
        if signal_date is None or stock_code is None or signal_kind is None or entry_date is None or exit_date is None:
            blockers.append("gap_view_contains_noncanonical_key_or_date")
            continue
        gap_key = (signal_date, stock_code, signal_kind, int(row[17]))
        occurrence_ordinals[gap_key] += 1
        occurrence_ordinal = occurrence_ordinals[gap_key]
        if gap_key_counts[gap_key] > 1 and occurrence_ordinal == 1:
            blockers.append(
                "duplicate_gap_view_key:"
                f"{signal_date}:{stock_code}:{signal_kind}:{int(row[17])}:"
                f"physical_rows={gap_key_counts[gap_key]}"
            )
        entry_factor = factor_cache[(stock_code, entry_date)]
        exit_factor = factor_cache[(stock_code, exit_date)]
        legacy_target = legacy_targets_by_key.get((signal_date, stock_code, signal_kind))
        gap_view_id = _gap_view_id(
            signal_date=signal_date,
            stock_code=stock_code,
            signal_kind=signal_kind,
            horizon_days=int(row[17]),
            occurrence_ordinal=occurrence_ordinal,
        )
        entry_price = _finite_float_or_none(row[11])
        exit_price = _finite_float_or_none(row[13])
        raw_return_net = _finite_float_or_none(row[14])
        stock_name = _trace_text_or_none(row[3])
        candidate_rank = _positive_int_or_none(row[4])
        market_state = _trace_text_or_none(row[5])
        data_status = _trace_text_or_none(row[6])
        formula_version = _trace_text_or_none(row[7])
        run_id = _trace_text_or_none(row[8])
        signal_close = _finite_float_or_none(row[9])
        if entry_price is None or entry_price <= 0:
            blockers.append(f"invalid_entry_price:{gap_view_id}")
        if exit_price is None or exit_price <= 0:
            blockers.append(f"invalid_exit_price:{gap_view_id}")
        if raw_return_net is None:
            blockers.append(f"invalid_raw_return_net:{gap_view_id}")
        for trace_field, trace_value in (
            ("stock_name", stock_name),
            ("candidate_rank", candidate_rank),
            ("market_state", market_state),
            ("data_status", data_status),
            ("formula_version", formula_version),
            ("run_id", run_id),
        ):
            if trace_value is None:
                blockers.append(f"invalid_trace_field:{trace_field}:{gap_view_id}")
        if signal_close is None or signal_close <= 0:
            blockers.append(f"invalid_trace_field:signal_close:{gap_view_id}")
        classification = _gap_classification(entry_factor, exit_factor)
        gap_view: dict[str, Any] = {
            "gap_view_id": gap_view_id,
            "signal_date": signal_date,
            "stock_code": stock_code,
            "signal_kind": signal_kind,
            "stock_name": stock_name,
            "candidate_rank": candidate_rank,
            "market_state": market_state,
            "data_status": data_status,
            "formula_version": formula_version,
            "run_id": run_id,
            "signal_close": signal_close,
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "raw_return_net": raw_return_net,
            "adjusted_return_net": None,
            "horizon_label": str(row[16]),
            "horizon_days": int(row[17]),
            "occurrence_ordinal": occurrence_ordinal,
            "physical_row_count_for_natural_key": gap_key_counts[gap_key],
            "entry_factor": dict(entry_factor),
            "exit_factor": dict(exit_factor),
            "classification": classification,
            "missing_reason": _missing_reason(entry_factor, exit_factor),
            "legacy_repair_targeted": legacy_target is not None,
            "legacy_repair_reasons": _string_list(legacy_target.get("reasons")) if legacy_target else [],
            "legacy_repair_remaining_reasons": (
                _string_list(legacy_target.get("remaining_reasons")) if legacy_target else []
            ),
            "legacy_repair_repairable": bool(legacy_target.get("repairable")) if legacy_target else False,
        }
        gap_view["source_row_sha256"] = _source_row_sha256(gap_view)
        gap_views.append(gap_view)
    gap_views.sort(
        key=lambda item: (
            str(item["signal_date"]),
            str(item["stock_code"]),
            str(item["signal_kind"]),
            int(item["horizon_days"]),
            int(item["occurrence_ordinal"]),
        )
    )
    if len(gap_views) != len(rows):
        blockers.append(f"page_gap_physical_mapping_mismatch:physical={len(rows)}:mapped={len(gap_views)}")
    return gap_views, len(rows)


def _load_factor_cache(
    conn: duckdb.DuckDBPyConnection,
    required_cells: set[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load all required exact cells in bounded read-only VALUES-join batches."""

    cells = sorted(required_cells)
    observations: defaultdict[tuple[str, str], list[tuple[Any, ...]]] = defaultdict(list)
    for start in range(0, len(cells), _FACTOR_LOOKUP_BATCH_SIZE):
        batch = cells[start : start + _FACTOR_LOOKUP_BATCH_SIZE]
        values_sql = ", ".join("(?, ?)" for _ in batch)
        parameters = [value for cell in batch for value in cell]
        rows = conn.execute(
            f"""
            with requested_cells(stock_code, trade_date) as (
              values {values_sql}
            )
            select
              requested_cells.stock_code,
              requested_cells.trade_date,
              cast(factor.stock_code as varchar),
              factor.trade_date,
              factor.adj_factor,
              factor.source_version,
              factor.run_id
            from requested_cells
            join {FACTOR_TABLE} as factor
              on upper(trim(cast(factor.stock_code as varchar))) = requested_cells.stock_code
             and try_cast(factor.trade_date as date) = cast(requested_cells.trade_date as date)
            order by requested_cells.stock_code, requested_cells.trade_date
            """,
            parameters,
        ).fetchall()
        for row in rows:
            requested_code = _stock_code(
                row[0],
                field_name="requested_factor_cell.stock_code",
            )
            requested_date = _date_text(
                row[1],
                field_name="requested_factor_cell.trade_date",
            )
            observations[(requested_code, requested_date)].append(tuple(row[2:]))

    return {
        cell: _factor_cell_payload(
            stock_code=cell[0],
            trade_date=cell[1],
            rows=observations.get(cell, []),
        )
        for cell in cells
    }


def _factor_cell_payload(
    *,
    stock_code: str,
    trade_date: str,
    rows: Sequence[Sequence[Any]],
) -> dict[str, Any]:
    distinct_values = sorted(
        {_factor_token(row[2]) for row in rows},
        key=lambda item: str(item),
    )
    if not rows:
        return {
            "stock_code": stock_code,
            "trade_date": trade_date,
            "status": FACTOR_MISSING_STATUS,
            "adj_factor": None,
            "observed_row_count": 0,
            "distinct_observation_count": 0,
            "source_identity": None,
        }
    if len(rows) != 1:
        return {
            "stock_code": stock_code,
            "trade_date": trade_date,
            "status": FACTOR_AMBIGUOUS_STATUS,
            "adj_factor": None,
            "observed_row_count": len(rows),
            "distinct_observation_count": len(distinct_values),
            "source_identity": None,
        }

    factor_value = distinct_values[0]
    observed_stock_code = _stock_code_or_none(rows[0][0])
    observed_trade_date = _normalize_trade_date_iso(rows[0][1])
    source_version = _optional_text(rows[0][3])
    run_id = _optional_text(rows[0][4])
    if (
        observed_stock_code != stock_code
        or observed_trade_date != trade_date
        or not _is_positive_finite(factor_value)
        or source_version is None
        or run_id is None
    ):
        return {
            "stock_code": stock_code,
            "trade_date": trade_date,
            "status": FACTOR_INVALID_STATUS,
            "adj_factor": None,
            "observed_row_count": len(rows),
            "distinct_observation_count": 1,
            "source_identity": None,
        }
    return {
        "stock_code": stock_code,
        "trade_date": trade_date,
        "status": FACTOR_PRESENT_STATUS,
        "adj_factor": float(factor_value),
        "observed_row_count": len(rows),
        "distinct_observation_count": 1,
        "source_identity": {
            "source_version": source_version,
            "run_id": run_id,
        },
    }


def _append_factor_quality_blockers(
    gap_views: Sequence[Mapping[str, Any]],
    blockers: list[str],
) -> None:
    statuses_by_cell: dict[tuple[str, str], str] = {}
    for view in gap_views:
        for factor_key in ("entry_factor", "exit_factor"):
            factor = view.get(factor_key)
            if not isinstance(factor, Mapping):
                continue
            key = (
                str(factor.get("stock_code") or ""),
                str(factor.get("trade_date") or ""),
            )
            status = str(factor.get("status") or "")
            previous = statuses_by_cell.setdefault(key, status)
            if previous != status:
                statuses_by_cell[key] = FACTOR_AMBIGUOUS_STATUS
    ambiguous_count = sum(1 for status in statuses_by_cell.values() if status == FACTOR_AMBIGUOUS_STATUS)
    invalid_count = sum(1 for status in statuses_by_cell.values() if status == FACTOR_INVALID_STATUS)
    if ambiguous_count:
        blockers.append(f"ambiguous_required_factor_cells:{ambiguous_count}")
    if invalid_count:
        blockers.append(f"invalid_required_factor_cells:{invalid_count}")


def _build_missing_factor_cells(gap_views: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for view in gap_views:
        for factor_role, factor_key in (("entry", "entry_factor"), ("exit", "exit_factor")):
            factor = view.get(factor_key)
            if not isinstance(factor, Mapping):
                continue
            status = str(factor.get("status") or "")
            if status == FACTOR_PRESENT_STATUS:
                continue
            stock_code = str(factor.get("stock_code") or "")
            trade_date = str(factor.get("trade_date") or "")
            grouped[(stock_code, trade_date)].append(
                {
                    "gap_view_id": str(view.get("gap_view_id") or ""),
                    "signal_date": str(view.get("signal_date") or ""),
                    "signal_kind": str(view.get("signal_kind") or ""),
                    "horizon_label": str(view.get("horizon_label") or ""),
                    "horizon_days": int(view.get("horizon_days") or 0),
                    "factor_role": factor_role,
                    "status": status,
                }
            )
    result: list[dict[str, Any]] = []
    for (stock_code, trade_date), references in sorted(grouped.items()):
        entry_refs = sum(1 for reference in references if reference["factor_role"] == "entry")
        exit_refs = len(references) - entry_refs
        role_scope = "both" if entry_refs and exit_refs else "entry_only" if entry_refs else "exit_only"
        statuses = sorted({reference["status"] for reference in references})
        chosen_status = statuses[0] if len(statuses) == 1 else FACTOR_AMBIGUOUS_STATUS
        result.append(
            {
                "missing_factor_cell_id": _missing_factor_cell_id(
                    stock_code=stock_code,
                    trade_date=trade_date,
                ),
                "stock_code": stock_code,
                "trade_date": trade_date,
                "status": chosen_status,
                "cell_statuses": statuses,
                "role_scope": role_scope,
                "gap_view_reference_count": len(references),
                "dependent_gap_count": len({str(reference["gap_view_id"]) for reference in references}),
                "role_use_counts": {
                    "entry": entry_refs,
                    "exit": exit_refs,
                },
                "gap_view_references": sorted(
                    references,
                    key=lambda item: (
                        item["signal_date"],
                        item["signal_kind"],
                        item["horizon_days"],
                        item["factor_role"],
                    ),
                ),
            }
        )
    return result


def _build_summary(
    *,
    gap_views: Sequence[Mapping[str, Any]],
    missing_factor_cells: Sequence[Mapping[str, Any]],
    legacy_targets_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
    blockers: Sequence[str],
    physical_page_gap_view_count: int,
) -> dict[str, Any]:
    horizon_counts = _distribution_list(Counter(str(view["horizon_label"]) for view in gap_views))
    signal_kind_counts = _distribution_list(Counter(str(view["signal_kind"]) for view in gap_views))
    role_scope_counts = _distribution_list(Counter(str(cell["role_scope"]) for cell in missing_factor_cells))
    classification_counts_by_horizon = {
        str(horizon["label"]): {
            classification: sum(
                1
                for view in gap_views
                if str(view["horizon_label"]) == str(horizon["label"]) and str(view["classification"]) == classification
            )
            for classification in sorted(GAP_CLASSIFICATIONS)
        }
        for horizon in _HORIZONS
    }
    required_factor_cells = {
        (str(factor.get("stock_code") or ""), str(factor.get("trade_date") or ""))
        for view in gap_views
        for factor in (view["entry_factor"], view["exit_factor"])
        if isinstance(factor, Mapping)
    }
    missing_requirement_use_count = sum(int(cell["gap_view_reference_count"]) for cell in missing_factor_cells)
    current_recomputable_gap_view_count = sum(
        1
        for view in gap_views
        if str(view["entry_factor"]["status"]) == FACTOR_PRESENT_STATUS
        and str(view["exit_factor"]["status"]) == FACTOR_PRESENT_STATUS
    )
    structurally_unclearable_count = sum(1 for view in gap_views if not _view_conditionally_clearable(view))
    legacy_target_keys = set(legacy_targets_by_key)
    legacy_targeted_views = [
        view
        for view in gap_views
        if (
            str(view["signal_date"]),
            str(view["stock_code"]),
            str(view["signal_kind"]),
        )
        in legacy_target_keys
    ]
    factor_status_by_cell: dict[tuple[str, str], str] = {}
    for view in gap_views:
        for factor in (view["entry_factor"], view["exit_factor"]):
            if not isinstance(factor, Mapping):
                continue
            factor_status_by_cell[
                (
                    str(factor.get("stock_code") or ""),
                    str(factor.get("trade_date") or ""),
                )
            ] = str(factor.get("status") or "")
    projected_after_full_materialization = physical_page_gap_view_count if blockers else structurally_unclearable_count
    return {
        "page_gap_view_count_before": physical_page_gap_view_count,
        "mapped_gap_view_count": len(gap_views),
        "factor_write_only_projected_gap_view_count": physical_page_gap_view_count,
        "factor_write_only_reduction": 0,
        "conditional_full_materialization_projected_gap_view_count": (projected_after_full_materialization),
        "conditional_full_materialization_reduction": (
            physical_page_gap_view_count - projected_after_full_materialization
        ),
        "conditional_full_materialization_note": (_FULL_MATERIALIZATION_NOTE),
        "current_recomputable_gap_view_count": current_recomputable_gap_view_count,
        "unique_execution_key_count": len(
            {
                (
                    str(view["signal_date"]),
                    str(view["stock_code"]),
                    str(view["signal_kind"]),
                )
                for view in gap_views
            }
        ),
        "unique_required_factor_cell_count": len(required_factor_cells),
        "required_factor_requirement_count": len(gap_views) * 2,
        "present_required_factor_cell_count": sum(
            1 for status in factor_status_by_cell.values() if status == FACTOR_PRESENT_STATUS
        ),
        "unique_missing_factor_cell_count": len(missing_factor_cells),
        "missing_factor_requirement_use_count": missing_requirement_use_count,
        "factor_quality": {
            "missing_required_cell_count": sum(
                1 for status in factor_status_by_cell.values() if status == FACTOR_MISSING_STATUS
            ),
            "invalid_required_cell_count": sum(
                1 for status in factor_status_by_cell.values() if status == FACTOR_INVALID_STATUS
            ),
            "ambiguous_required_cell_count": sum(
                1 for status in factor_status_by_cell.values() if status == FACTOR_AMBIGUOUS_STATUS
            ),
        },
        "horizon_counts": horizon_counts,
        "classification_counts_by_horizon": classification_counts_by_horizon,
        "signal_kind_counts": signal_kind_counts,
        "missing_factor_role_scope_counts": role_scope_counts,
        "legacy_repair_coverage": {
            "coverage_kind": "selector_candidate",
            "selector_signal_kind": "stock_candidate",
            "selector_scope_only": True,
            "effective_repair_preview_executed": False,
            "selector_candidate_logical_key_count": len(legacy_target_keys),
            "covered_gap_view_count": len(legacy_targeted_views),
            "covered_horizon_counts": _distribution_list(
                Counter(str(view["horizon_label"]) for view in legacy_targeted_views)
            ),
        },
    }


def _view_conditionally_clearable(view: Mapping[str, Any]) -> bool:
    for factor_key in ("entry_factor", "exit_factor"):
        factor = view.get(factor_key)
        if not isinstance(factor, Mapping):
            return False
        if str(factor.get("status") or "") not in _REPAIRABLE_FACTOR_STATUSES:
            return False
    return True


def _missing_reason(entry_factor: Mapping[str, Any], exit_factor: Mapping[str, Any]) -> str:
    entry_missing = str(entry_factor.get("status") or "") != FACTOR_PRESENT_STATUS
    exit_missing = str(exit_factor.get("status") or "") != FACTOR_PRESENT_STATUS
    if entry_missing and exit_missing:
        return "entry_and_exit_factor_unresolved"
    if entry_missing:
        return "entry_factor_unresolved"
    if exit_missing:
        return "exit_factor_unresolved"
    return "factors_present_but_history_not_rewritten"


def _gap_classification(
    entry_factor: Mapping[str, Any],
    exit_factor: Mapping[str, Any],
) -> str:
    entry_missing = str(entry_factor.get("status") or "") != FACTOR_PRESENT_STATUS
    exit_missing = str(exit_factor.get("status") or "") != FACTOR_PRESENT_STATUS
    if entry_missing and exit_missing:
        return "missing_both"
    if entry_missing:
        return "missing_entry_only"
    if exit_missing:
        return "missing_exit_only"
    return "factors_present_history_unmaterialized"


def _classification_from_statuses(entry_status: str, exit_status: str) -> str:
    return _gap_classification(
        {"status": entry_status},
        {"status": exit_status},
    )


def _missing_reason_from_statuses(entry_status: str, exit_status: str) -> str:
    return _missing_reason(
        {"status": entry_status},
        {"status": exit_status},
    )


def _gap_view_id(
    *,
    signal_date: str,
    stock_code: str,
    signal_kind: str,
    horizon_days: int,
    occurrence_ordinal: int,
) -> str:
    return _stable_id(
        "gap_view",
        signal_date,
        stock_code,
        signal_kind,
        str(horizon_days),
        str(occurrence_ordinal),
    )


def _missing_factor_cell_id(*, stock_code: str, trade_date: str) -> str:
    return _stable_id("missing_factor_cell", stock_code, trade_date)


def _stable_id(prefix: str, *values: str) -> str:
    encoded = "|".join((prefix, *values)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _source_row_sha256(view: Mapping[str, Any]) -> str:
    payload = {field_name: view.get(field_name) for field_name in _SOURCE_ROW_HASH_FIELDS}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _factor_token(value: object) -> float | str | None:
    if value is None:
        return None
    try:
        number = float(cast(str | float, value))
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "NaN" if math.isnan(number) else ("Infinity" if number > 0 else "-Infinity")
    return number


def _is_positive_finite(value: object) -> TypeGuard[int | float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    parsed = float(value)
    return math.isfinite(parsed) and parsed > 0


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    parsed = float(value)
    return math.isfinite(parsed)


def _distribution_list(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _ordered(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered_values: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            ordered_values.append(normalized)
            seen.add(normalized)
    return ordered_values


def _stock_code(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a canonical A-share stock code")
    original = value
    normalized = original.upper()
    if original != normalized or not _CANONICAL_STOCK_CODE_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a canonical A-share stock code")
    return normalized


def _stock_code_or_none(value: object) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    normalized = value.upper()
    if value != normalized or not _CANONICAL_STOCK_CODE_RE.fullmatch(normalized):
        return None
    return normalized


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _trace_text_or_none(value: object) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    return value


def _trace_text(value: object, *, field_name: str) -> str:
    text = _trace_text_or_none(value)
    if text is None:
        raise ValueError(f"{field_name} must be a non-empty canonical string")
    return text


def _date_text(value: object, *, field_name: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be an ISO date")
    text = value
    try:
        normalized = date.fromisoformat(text).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc
    if text != normalized:
        raise ValueError(f"{field_name} must be an ISO date")
    return normalized


def _normalize_trade_date_iso(value: object) -> str | None:
    try:
        return _date_text(value, field_name="trade_date")
    except ValueError:
        return None


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
    original = _required_text(value, field_name=field_name)
    normalized = original.upper()
    if len(normalized) != 64 or any(character not in "0123456789ABCDEF" for character in normalized):
        raise ValueError(f"{field_name} must be an uppercase sha256")
    if original != normalized:
        raise ValueError(f"{field_name} must be an uppercase sha256")
    return normalized


def _horizon_days(value: object, *, field_name: str) -> int:
    parsed = _int_value(value, field_name=field_name)
    if parsed not in {1, 5, 10, 20}:
        raise ValueError(f"{field_name} must be one of 1, 5, 10, 20")
    return parsed


def _factor_status(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    if text not in FACTOR_STATUSES:
        raise ValueError(f"{field_name} is invalid")
    return text


def _role_scope(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    if text not in ROLE_SCOPE_VALUES:
        raise ValueError(f"{field_name} is invalid")
    return text


def _int_value(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _positive_int(value: object, *, field_name: str) -> int:
    parsed = _int_value(value, field_name=field_name)
    if parsed < 1:
        raise ValueError(f"{field_name} must be positive")
    return parsed


def _summary_int(
    mapping: Mapping[str, object],
    field_name: str,
    errors: list[str],
    *,
    prefix: str = "manifest.summary",
) -> int:
    try:
        return _int_value(mapping.get(field_name), field_name=f"{prefix}.{field_name}")
    except ValueError as exc:
        errors.append(str(exc))
        return 0


def _positive_int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _safe_float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(cast(str | float, value))
    except (TypeError, ValueError):
        return None


def _finite_float_or_none(value: object) -> float | None:
    parsed = _safe_float_or_none(value)
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def _string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is not None:
            result.append(text)
    return result


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
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
