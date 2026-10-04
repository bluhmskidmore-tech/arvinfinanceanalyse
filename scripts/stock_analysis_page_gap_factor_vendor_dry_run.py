#!/usr/bin/env python3
"""Read-only Tushare dry run for page-gap exact adjustment-factor cells."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance import (  # noqa: E402
    stock_analysis_page_gap_factor_vendor_receipt as receipt_task,
)
from backend.app.tasks import stock_analysis_page_gap_factor_manifest as manifest_task  # noqa: E402
from backend.app.tasks import stock_analysis_page_gap_manifest as page_manifest_task  # noqa: E402
from scripts import stock_analysis_current_rule_factor_vendor_dry_run as _vendor_helpers  # noqa: E402
from scripts import stock_analysis_page_gap_manifest as _evidence_helpers  # noqa: E402

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_RUNTIME_ERROR = 3


def run_page_gap_factor_vendor_dry_run(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    factor_manifest_file: str | Path,
    output_file: str | Path,
    captured_at: str,
    max_vendor_calls: int,
    retry_attempts: int = 3,
    retry_sleep_seconds: float = 1.0,
    client: object | None = None,
) -> dict[str, Any]:
    """Fetch exactly the manifest cells and persist only an exact-match receipt.

    DuckDB is never opened.  Its bytes are hashed before and after every material
    boundary; any drift blocks persistence or removes only the exact file created
    by this invocation.
    """

    target_db: Path | None = None
    trusted_root: Path | None = None
    target_output: Path | None = None
    created_identity: tuple[int, int] | None = None
    database_sha_before: str | None = None
    database_sha_after: str | None = None
    factor_manifest_file_sha256: str | None = None
    canonical_manifest_sha256: str | None = None
    vendor_call_count = 0

    try:
        target_db = _evidence_helpers._normalize_existing_file(
            duckdb_path,
            field_name="duckdb_path",
        )
        trusted_root = _evidence_helpers._normalize_existing_directory(
            trusted_evidence_root,
            field_name="trusted_evidence_root",
        )
        manifest_path = _existing_json_within_root(
            trusted_root=trusted_root,
            path=factor_manifest_file,
            field_name="factor_manifest_file",
        )
        target_output = _evidence_helpers._new_output_path(
            trusted_root=trusted_root,
            output_file=output_file,
        )
        call_budget = _positive_int(max_vendor_calls, field_name="max_vendor_calls")
        attempt_limit = _positive_int(retry_attempts, field_name="retry_attempts")
        retry_delay = _nonnegative_finite_float(
            retry_sleep_seconds,
            field_name="retry_sleep_seconds",
        )
        database_sha_before = _evidence_helpers._file_sha256(target_db)
        manifest = _evidence_helpers._load_json_object(manifest_path)
        manifest_valid, _manifest_errors = (
            manifest_task.validate_stock_analysis_page_gap_factor_manifest(manifest)
        )
        if not manifest_valid:
            return _result(
                status="blocked",
                blockers=["factor_manifest_validation_failed"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_before,
                vendor_call_count=0,
            )
        if manifest.get("status") != "gaps_found" or manifest.get("blockers") != []:
            return _result(
                status="blocked",
                blockers=["factor_manifest_not_vendor_dry_run_eligible"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_before,
                vendor_call_count=0,
            )
        for field_name, expected in (
            ("remediation_only", True),
            ("write_allowed", False),
            ("historical_availability_proven", False),
            ("certification_allowed", False),
            ("downstream_materialization_allowed", False),
        ):
            if manifest.get(field_name) is not expected:
                return _result(
                    status="blocked",
                    blockers=["factor_manifest_boundary_invalid"],
                    output_file=None,
                    database_sha_before=database_sha_before,
                    database_sha_after=database_sha_before,
                    vendor_call_count=0,
                )

        factor_manifest_file_sha256 = _evidence_helpers._file_sha256(manifest_path)
        canonical_manifest_sha256 = _required_text(
            manifest.get("canonical_manifest_sha256"),
            field_name="factor_manifest.canonical_manifest_sha256",
        )
        binding_error = _database_binding_error(
            target_db=target_db,
            current_sha256=database_sha_before,
            manifest=manifest,
        )
        if binding_error:
            return _result(
                status="blocked",
                blockers=[binding_error],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_before,
                vendor_call_count=0,
            )

        try:
            _validate_external_page_manifest_binding(
                factor_manifest=manifest,
                trusted_root=trusted_root,
                target_db=target_db,
                current_database_sha256=database_sha_before,
            )
        except ValueError:
            return _result(
                status="blocked",
                blockers=["page_manifest_external_binding_failed"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_before,
                vendor_call_count=0,
            )

        requested_cells = _manifest_target_cells(manifest)
        cells_by_date: defaultdict[str, set[str]] = defaultdict(set)
        for stock_code, trade_date in requested_cells:
            cells_by_date[trade_date].add(stock_code)
        requested_dates = sorted(cells_by_date)
        if len(requested_dates) > call_budget:
            return _result(
                status="blocked",
                blockers=["vendor_call_budget_exceeded"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_before,
                vendor_call_count=0,
                summary={
                    "requested_cell_count": len(requested_cells),
                    "requested_unique_date_count": len(requested_dates),
                    "max_vendor_calls": call_budget,
                },
            )

        vendor_client = (
            client if client is not None else _vendor_helpers._DefaultTushareClient()
        )
        returned_cells: list[dict[str, Any]] = []
        for requested_trade_date in requested_dates:
            payload = _fetch_adj_factor_with_retry(
                vendor_client=vendor_client,
                trade_date=requested_trade_date.replace("-", ""),
                retry_attempts=attempt_limit,
                retry_sleep_seconds=retry_delay,
            )
            vendor_call_count += 1
            returned_cells.extend(
                _vendor_helpers._target_rows_from_vendor_payload(
                    payload,
                    requested_trade_date=requested_trade_date,
                    requested_codes=cells_by_date[requested_trade_date],
                )
            )
        returned_cells.sort(key=_vendor_helpers._returned_cell_sort_key)

        database_sha_after_fetch = _evidence_helpers._file_sha256(target_db)
        if database_sha_after_fetch != database_sha_before:
            return _result(
                status="blocked",
                blockers=["duckdb_hash_changed_during_vendor_fetch"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_after_fetch,
                vendor_call_count=vendor_call_count,
            )
        exact_match, summary = _vendor_helpers._strict_exact_match(
            requested_cells=requested_cells,
            returned_cells=returned_cells,
        )
        summary["vendor_call_count"] = vendor_call_count
        summary["requested_unique_date_count"] = len(requested_dates)
        if not exact_match:
            return _result(
                status="blocked",
                blockers=["factor_vendor_exact_match_failed"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_after_fetch,
                vendor_call_count=vendor_call_count,
                summary=summary,
            )

        receipt = receipt_task.build_stock_analysis_page_gap_factor_vendor_receipt(
            reviewed_factor_manifest=manifest,
            reviewed_factor_manifest_path=manifest_path,
            reviewed_factor_manifest_file_sha256=factor_manifest_file_sha256,
            returned_cells=returned_cells,
            captured_at=captured_at,
            database_sha256_before=database_sha_before,
            database_sha256_after=database_sha_after_fetch,
        )
        receipt_valid, _receipt_errors = (
            receipt_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
                receipt,
                reviewed_factor_manifest=manifest,
                reviewed_factor_manifest_path=manifest_path,
                reviewed_factor_manifest_file_sha256=factor_manifest_file_sha256,
            )
        )
        if not receipt_valid:
            return _result(
                status="blocked",
                blockers=["factor_vendor_receipt_validation_failed"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=_evidence_helpers._file_sha256(target_db),
                vendor_call_count=vendor_call_count,
            )
        database_sha_after_receipt = _evidence_helpers._file_sha256(target_db)
        if database_sha_after_receipt != database_sha_before:
            return _result(
                status="blocked",
                blockers=["duckdb_hash_changed_during_receipt_build"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_after_receipt,
                vendor_call_count=vendor_call_count,
            )

        created_identity = _evidence_helpers._write_json_exclusive(
            trusted_root=trusted_root,
            output_file=target_output,
            payload=receipt,
        )
        persisted = _evidence_helpers._load_json_object(target_output)
        if persisted != receipt:
            raise RuntimeError(
                "persisted vendor receipt differs from generated receipt"
            )
        persisted_valid, _persisted_errors = (
            receipt_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
                persisted,
                reviewed_factor_manifest=manifest,
                reviewed_factor_manifest_path=manifest_path,
                reviewed_factor_manifest_file_sha256=factor_manifest_file_sha256,
            )
        )
        if not persisted_valid:
            raise RuntimeError("persisted vendor receipt failed formal validation")
        database_sha_after = _evidence_helpers._file_sha256(target_db)
        if database_sha_after != database_sha_before:
            _evidence_helpers._remove_output_file_if_same(
                trusted_root=trusted_root,
                output_file=target_output,
                created_identity=created_identity,
            )
            created_identity = None
            return _result(
                status="blocked",
                blockers=["duckdb_hash_changed_during_receipt_persistence"],
                output_file=None,
                database_sha_before=database_sha_before,
                database_sha_after=database_sha_after,
                vendor_call_count=vendor_call_count,
            )
        output_file_sha256 = _evidence_helpers._file_sha256(target_output)
        factor_binding = receipt["factor_manifest_binding"]
        page_binding = receipt["page_manifest_binding"]
        approval_scope_sha256 = receipt_task.factor_approval_scope_sha256(
            factor_manifest_file_sha256=str(factor_binding["file_sha256"]),
            factor_manifest_canonical_sha256=str(
                factor_binding["canonical_manifest_sha256"]
            ),
            page_manifest_file_sha256=str(page_binding["file_sha256"]),
            page_manifest_canonical_sha256=str(
                page_binding["canonical_manifest_sha256"]
            ),
            vendor_receipt_file_sha256=output_file_sha256,
            vendor_receipt_canonical_sha256=str(receipt["canonical_receipt_sha256"]),
            database_sha256_before=database_sha_before,
            returned_cells_sha256=str(receipt["returned_cells_sha256"]),
            target_cell_count=int(receipt["returned_cell_count"]),
            source_version=str(receipt["proposed_source_version"]),
            run_id=str(receipt["proposed_run_id"]),
        )
        return _result(
            status="ready",
            blockers=[],
            output_file=target_output,
            database_sha_before=database_sha_before,
            database_sha_after=database_sha_after,
            vendor_call_count=vendor_call_count,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            canonical_manifest_sha256=canonical_manifest_sha256,
            receipt=receipt,
            factor_approval_scope_sha256=approval_scope_sha256,
            summary=_receipt_summary(receipt),
        )
    except Exception as exc:
        if created_identity and trusted_root and target_output:
            try:
                _evidence_helpers._remove_output_file_if_same(
                    trusted_root=trusted_root,
                    output_file=target_output,
                    created_identity=created_identity,
                )
            except Exception as cleanup_error:
                logging.getLogger(__name__).warning(
                    "Artifact cleanup failed (%s); preserving the original failure",
                    type(cleanup_error).__name__,
                )
        if target_db and target_db.is_file() and database_sha_before:
            try:
                database_sha_after = _evidence_helpers._file_sha256(target_db)
            except OSError:
                database_sha_after = None
        drifted = bool(
            database_sha_before
            and database_sha_after
            and database_sha_before != database_sha_after
        )
        return _result(
            status="blocked" if drifted else "error",
            blockers=(
                ["duckdb_hash_changed_during_factor_vendor_dry_run"]
                if drifted
                else [f"factor_vendor_dry_run_failed_{type(exc).__name__}"]
            ),
            output_file=None,
            database_sha_before=database_sha_before,
            database_sha_after=database_sha_after,
            vendor_call_count=vendor_call_count,
            factor_manifest_file_sha256=factor_manifest_file_sha256,
            canonical_manifest_sha256=canonical_manifest_sha256,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--factor-manifest-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--max-vendor-calls", required=True, type=int)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--retry-sleep-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    result = run_page_gap_factor_vendor_dry_run(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        factor_manifest_file=args.factor_manifest_file,
        output_file=args.output_file,
        captured_at=args.captured_at,
        max_vendor_calls=args.max_vendor_calls,
        retry_attempts=args.retry_attempts,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return (
        EXIT_SUCCESS
        if result["status"] == "ready"
        else EXIT_BLOCKED
        if result["status"] == "blocked"
        else EXIT_RUNTIME_ERROR
    )


def _existing_json_within_root(
    *, trusted_root: Path, path: str | Path, field_name: str
) -> Path:
    raw = Path(path)
    candidate = _evidence_helpers._absolute_without_resolve(
        raw if raw.is_absolute() else trusted_root / raw
    )
    _evidence_helpers._assert_within_trusted_root(
        trusted_root=trusted_root,
        output_file=candidate,
    )
    if candidate.suffix.lower() != ".json" or not candidate.is_file():
        raise ValueError(
            f"{field_name} must be an existing JSON file within trusted root"
        )
    resolved = candidate.resolve(strict=True)
    _evidence_helpers._assert_within_trusted_root(
        trusted_root=trusted_root.resolve(strict=True),
        output_file=resolved,
    )
    return resolved


def _validate_external_page_manifest_binding(
    *,
    factor_manifest: Mapping[str, Any],
    trusted_root: Path,
    target_db: Path,
    current_database_sha256: str,
) -> dict[str, Any]:
    binding = factor_manifest.get("page_manifest_binding")
    if not isinstance(binding, Mapping):
        raise ValueError("factor manifest page binding must be a mapping")
    page_path = _existing_json_within_root(
        trusted_root=trusted_root,
        path=_required_text(
            binding.get("path"), field_name="page_manifest_binding.path"
        ),
        field_name="page_manifest_binding.path",
    )
    page_file_sha256 = _evidence_helpers._file_sha256(page_path)
    if page_file_sha256 != str(binding.get("file_sha256") or "").strip().upper():
        raise ValueError("page manifest file SHA binding mismatch")
    page_manifest = _evidence_helpers._load_json_object(page_path)
    valid, _errors = page_manifest_task.validate_stock_analysis_page_gap_manifest(
        page_manifest
    )
    if not valid:
        raise ValueError("page manifest failed formal validation")
    if (
        page_manifest.get("status") != "gaps_found"
        or page_manifest.get("blockers") != []
    ):
        raise ValueError("page manifest is not remediation eligible")
    summary = page_manifest.get("summary")
    database = page_manifest.get("database")
    if not isinstance(summary, Mapping) or not isinstance(database, Mapping):
        raise ValueError("page manifest summary/database binding missing")
    expected_binding = {
        "path": str(page_path),
        "file_sha256": page_file_sha256,
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
    if dict(binding) != expected_binding:
        raise ValueError(
            "factor manifest page binding does not match external page manifest"
        )
    if (
        _evidence_helpers._absolute_without_resolve(str(database.get("path") or ""))
        != target_db
    ):
        raise ValueError("external page manifest database path mismatch")
    if (
        database.get("sha256_before") != current_database_sha256
        or database.get("sha256_after") != current_database_sha256
    ):
        raise ValueError("external page manifest database SHA mismatch")
    raw_missing = page_manifest.get("missing_factor_cells")
    if not isinstance(raw_missing, list):
        raise ValueError("external page manifest missing_factor_cells must be a list")
    page_cells = sorted(
        (
            {
                "stock_code": _vendor_helpers._stock_code(
                    cell.get("stock_code"),
                    field_name="page_manifest.missing_factor_cells.stock_code",
                ),
                "trade_date": _vendor_helpers._date_text(
                    cell.get("trade_date"),
                    field_name="page_manifest.missing_factor_cells.trade_date",
                ),
            }
            for cell in raw_missing
            if isinstance(cell, Mapping)
        ),
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )
    factor_cells = sorted(
        (
            {"stock_code": stock_code, "trade_date": trade_date}
            for stock_code, trade_date in _manifest_target_cells(factor_manifest)
        ),
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )
    if page_cells != factor_cells:
        raise ValueError("factor target cells do not match external page manifest")
    return page_manifest


def _database_binding_error(
    *, target_db: Path, current_sha256: str, manifest: Mapping[str, Any]
) -> str | None:
    database = manifest.get("database")
    if not isinstance(database, Mapping):
        return "factor_manifest_database_binding_missing"
    expected_path = str(database.get("path") or "").strip()
    if not expected_path:
        return "factor_manifest_database_path_missing"
    if _evidence_helpers._absolute_without_resolve(expected_path) != target_db:
        return "factor_manifest_database_path_mismatch"
    before = str(database.get("sha256_before") or "").strip().upper()
    after = str(database.get("sha256_after") or "").strip().upper()
    if current_sha256 != before or current_sha256 != after:
        return "factor_manifest_database_sha256_mismatch"
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        return "factor_manifest_database_attestation_invalid"
    return None


def _manifest_target_cells(manifest: Mapping[str, Any]) -> set[tuple[str, str]]:
    raw_cells = manifest.get("target_cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValueError("factor_manifest.target_cells must be a non-empty list")
    cells: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(raw_cells):
        if not isinstance(raw_cell, Mapping):
            raise ValueError(f"factor_manifest.target_cells[{index}] must be an object")
        stock_code = _vendor_helpers._stock_code(
            raw_cell.get("stock_code"),
            field_name=f"target_cells[{index}].stock_code",
        )
        trade_date = _vendor_helpers._date_text(
            raw_cell.get("trade_date"),
            field_name=f"target_cells[{index}].trade_date",
        )
        key = (stock_code, trade_date)
        if key in cells:
            raise ValueError("factor_manifest.target_cells contains duplicate keys")
        cells.add(key)
    if manifest.get("target_cell_count") != len(cells):
        raise ValueError("factor_manifest.target_cell_count mismatch")
    if manifest.get("requested_unique_date_count") != len({date for _, date in cells}):
        raise ValueError("factor_manifest.requested_unique_date_count mismatch")
    return cells


def _receipt_summary(receipt: Mapping[str, Any]) -> dict[str, int]:
    return {
        field_name: int(receipt[field_name])
        for field_name in (
            "requested_cell_count",
            "returned_cell_count",
            "requested_unique_date_count",
            "vendor_call_count",
            "missing_cell_count",
            "extra_cell_count",
            "duplicate_cell_count",
            "invalid_cell_count",
            "wrong_date_cell_count",
        )
        if isinstance(receipt.get(field_name), int)
        and not isinstance(receipt.get(field_name), bool)
    }


def _result(
    *,
    status: str,
    blockers: Sequence[str],
    output_file: Path | None,
    database_sha_before: str | None,
    database_sha_after: str | None,
    vendor_call_count: int,
    factor_manifest_file_sha256: str | None = None,
    canonical_manifest_sha256: str | None = None,
    receipt: Mapping[str, Any] | None = None,
    factor_approval_scope_sha256: str | None = None,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt_payload = dict(receipt or {})
    return {
        "status": status,
        "blockers": list(dict.fromkeys(str(item) for item in blockers)),
        "output_file": str(output_file) if output_file else None,
        "output_file_sha256": (
            _evidence_helpers._file_sha256(output_file)
            if output_file and output_file.is_file()
            else None
        ),
        "factor_manifest_file_sha256": factor_manifest_file_sha256,
        "canonical_manifest_sha256": canonical_manifest_sha256,
        "canonical_receipt_sha256": receipt_payload.get("canonical_receipt_sha256"),
        "factor_approval_scope_sha256": factor_approval_scope_sha256,
        "database_sha256_before": database_sha_before,
        "database_sha256_after": database_sha_after,
        "database_unchanged": bool(
            database_sha_before
            and database_sha_after
            and database_sha_before == database_sha_after
        ),
        "vendor_call_count": vendor_call_count,
        "summary": dict(summary or {}),
    }


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _nonnegative_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a non-negative finite number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative finite number")
    return parsed


def _fetch_adj_factor_with_retry(
    *,
    vendor_client: object,
    trade_date: str,
    retry_attempts: int,
    retry_sleep_seconds: float,
) -> object:
    for attempt_number in range(1, retry_attempts + 1):
        try:
            return vendor_client.adj_factor(  # type: ignore[attr-defined]
                trade_date=trade_date,
                fields="ts_code,trade_date,adj_factor",
            )
        except Exception as exc:
            if not _is_retryable_vendor_exception(exc):
                raise
            if attempt_number >= retry_attempts:
                raise
            if retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds)
    raise AssertionError("unreachable vendor retry state")


def _is_retryable_vendor_exception(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (
            ConnectionError,
            TimeoutError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
