#!/usr/bin/env python3
"""Governed, read-only vendor dry-run for exact adjustment-factor gap cells."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance import (  # noqa: E402
    stock_analysis_current_rule_factor_vendor_receipt as receipt_task,
)
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.tasks import (  # noqa: E402
    stock_analysis_current_rule_factor_manifest as manifest_task,
)
from scripts import stock_analysis_current_rule_factor_manifest as manifest_cli  # noqa: E402
from scripts import stock_analysis_current_rule_cohort_bundle as cohort_bundle_cli  # noqa: E402

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2

_SAFE_BLOCKER_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")


def run_current_rule_factor_vendor_dry_run(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    factor_manifest_file: str | Path,
    output_file: str | Path,
    created_at: str,
    max_vendor_calls: int,
    client: object | None = None,
) -> dict[str, Any]:
    """Fetch only manifest gap cells and exclusively persist a governed receipt.

    This function never opens DuckDB.  The database is used only as a file whose
    current path and SHA-256 must remain bound to the reviewed manifest.
    """

    target_db = Path(duckdb_path)
    database_sha256_before: str | None = None
    database_sha256_after: str | None = None
    manifest_file_sha256: str | None = None
    canonical_manifest_sha256: str | None = None
    trusted_root: Path | None = None
    target_output: Path | None = None
    output_created_by_this_run = False
    vendor_call_count = 0

    try:
        raw_db_path = manifest_cli._absolute_without_resolve(duckdb_path)
        cohort_bundle_cli.producer_task._assert_no_symlink_in_raw_path(  # type: ignore[attr-defined]
            raw_db_path,
            field_name="duckdb_path",
        )
        target_db = cohort_bundle_cli._require_existing_duckdb_path(duckdb_path)
        database_sha256_before = manifest_cli._file_sha256(target_db)
        trusted_root = _trusted_evidence_root(trusted_evidence_root)
        target_manifest = _existing_evidence_json_path(
            trusted_root=trusted_root,
            evidence_file=factor_manifest_file,
            field_name="factor_manifest_file",
        )
        target_output = manifest_cli._new_manifest_output_path(
            trusted_root=trusted_root,
            output_file=output_file,
        )

        reviewed_manifest = manifest_cli._load_json_object(target_manifest)
        manifest_valid, _manifest_errors = (
            manifest_task.validate_stock_analysis_current_rule_factor_manifest(
                reviewed_manifest
            )
        )
        if not manifest_valid:
            return _result_payload(
                status="blocked",
                blockers=["factor_manifest_validation_failed"],
                output_file=None,
                manifest_file_sha256=None,
                canonical_manifest_sha256=None,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_before,
                vendor_call_count=0,
            )

        manifest_file_sha256 = manifest_cli._file_sha256(target_manifest)
        canonical_manifest_sha256 = _required_text(
            reviewed_manifest.get("canonical_manifest_sha256"),
            field_name="factor_manifest.canonical_manifest_sha256",
        )
        manifest_blockers = reviewed_manifest.get("blockers")
        if (
            reviewed_manifest.get("status") != "gaps_found"
            or reviewed_manifest.get("remediation_only") is not True
            or reviewed_manifest.get("certification_allowed") is not False
            or not isinstance(manifest_blockers, list)
            or manifest_blockers
        ):
            return _result_payload(
                status="blocked",
                blockers=["factor_manifest_not_vendor_dry_run_eligible"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_before,
                vendor_call_count=0,
            )

        database_binding_error = _database_binding_error(
            target_db=target_db,
            current_sha256=database_sha256_before,
            manifest=reviewed_manifest,
        )
        if database_binding_error is not None:
            return _result_payload(
                status="blocked",
                blockers=[database_binding_error],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_before,
                vendor_call_count=0,
            )

        requested_cells = _manifest_missing_cells(reviewed_manifest)
        cells_by_date: defaultdict[str, set[str]] = defaultdict(set)
        for stock_code, trade_date in requested_cells:
            cells_by_date[trade_date].add(stock_code)
        requested_dates = sorted(cells_by_date)
        call_budget = _positive_int(max_vendor_calls, field_name="max_vendor_calls")
        if len(requested_dates) > call_budget:
            return _result_payload(
                status="blocked",
                blockers=["vendor_call_budget_exceeded"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_before,
                vendor_call_count=0,
            )

        vendor_client = client if client is not None else _DefaultTushareClient()
        returned_cells: list[dict[str, Any]] = []
        for requested_trade_date in requested_dates:
            payload = vendor_client.adj_factor(  # type: ignore[attr-defined]
                trade_date=requested_trade_date.replace("-", ""),
                fields="ts_code,trade_date,adj_factor",
            )
            vendor_call_count += 1
            returned_cells.extend(
                _target_rows_from_vendor_payload(
                    payload,
                    requested_trade_date=requested_trade_date,
                    requested_codes=cells_by_date[requested_trade_date],
                )
            )
        returned_cells.sort(key=_returned_cell_sort_key)

        database_sha256_after_fetch = manifest_cli._file_sha256(target_db)
        if database_sha256_after_fetch != database_sha256_before:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_vendor_fetch"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_fetch,
                vendor_call_count=vendor_call_count,
            )

        exact_match, local_summary = _strict_exact_match(
            requested_cells=requested_cells,
            returned_cells=returned_cells,
        )
        local_summary["vendor_call_count"] = vendor_call_count
        if not exact_match:
            return _result_payload(
                status="blocked",
                blockers=["factor_vendor_exact_match_failed"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=None,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_fetch,
                vendor_call_count=vendor_call_count,
                summary=local_summary,
            )
        receipt = receipt_task.build_stock_analysis_current_rule_factor_vendor_receipt(
            reviewed_factor_manifest=reviewed_manifest,
            reviewed_factor_manifest_path=target_manifest,
            reviewed_factor_manifest_file_sha256=manifest_file_sha256,
            returned_cells=returned_cells,
            captured_at=created_at,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after_fetch,
        )
        receipt_payload = _mapping(receipt, field_name="factor_vendor_receipt")
        receipt_valid, _receipt_errors = (
            receipt_task.validate_stock_analysis_current_rule_factor_vendor_receipt(
                receipt_payload,
                reviewed_factor_manifest=reviewed_manifest,
                reviewed_factor_manifest_path=target_manifest,
                reviewed_factor_manifest_file_sha256=manifest_file_sha256,
            )
        )
        database_sha256_after_receipt = manifest_cli._file_sha256(target_db)
        if database_sha256_after_receipt != database_sha256_before:
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_receipt_build"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=receipt_payload,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_receipt,
                vendor_call_count=vendor_call_count,
            )
        if not receipt_valid:
            return _result_payload(
                status="blocked",
                blockers=["factor_vendor_receipt_validation_failed"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=receipt_payload,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_receipt,
                vendor_call_count=vendor_call_count,
            )

        ready = (
            exact_match
            and receipt_payload.get("status") == receipt_task.READY_STATUS
            and _receipt_indicates_exact_match(
                receipt_payload,
                expected_cell_count=len(requested_cells),
                expected_vendor_call_count=len(requested_dates),
            )
        )
        if not ready:
            return _result_payload(
                status="blocked",
                blockers=["factor_vendor_receipt_not_ready"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=receipt_payload,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after_receipt,
                vendor_call_count=vendor_call_count,
                summary=_receipt_summary(receipt_payload),
            )

        manifest_cli._write_json_exclusive(
            trusted_root=trusted_root,
            output_file=target_output,
            payload=receipt_payload,
        )
        output_created_by_this_run = True
        persisted = manifest_cli._load_json_object(target_output)
        if persisted != receipt_payload:
            raise FactorVendorDryRunError(
                "persisted factor vendor receipt does not match generated receipt"
            )

        database_sha256_after = manifest_cli._file_sha256(target_db)
        if database_sha256_after != database_sha256_before:
            manifest_cli._remove_new_manifest_file(
                trusted_root=trusted_root,
                output_file=target_output,
            )
            output_created_by_this_run = False
            return _result_payload(
                status="blocked",
                blockers=["duckdb_hash_changed_during_receipt_persistence"],
                output_file=None,
                manifest_file_sha256=manifest_file_sha256,
                canonical_manifest_sha256=canonical_manifest_sha256,
                receipt=receipt_payload,
                database_sha256_before=database_sha256_before,
                database_sha256_after=database_sha256_after,
                vendor_call_count=vendor_call_count,
            )

        return _result_payload(
            status="ready",
            blockers=[],
            output_file=target_output,
            manifest_file_sha256=manifest_file_sha256,
            canonical_manifest_sha256=canonical_manifest_sha256,
            receipt=receipt_payload,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            vendor_call_count=vendor_call_count,
            summary=_receipt_summary(receipt_payload),
        )
    except Exception as exc:
        if (
            output_created_by_this_run
            and trusted_root is not None
            and target_output is not None
        ):
            try:
                manifest_cli._remove_new_manifest_file(
                    trusted_root=trusted_root,
                    output_file=target_output,
                )
            except Exception as cleanup_error:
                logging.getLogger(__name__).warning(
                    "Artifact cleanup failed (%s); preserving the original failure",
                    type(cleanup_error).__name__,
                )
        if database_sha256_before is not None and target_db.is_file():
            try:
                database_sha256_after = manifest_cli._file_sha256(target_db)
            except OSError:
                database_sha256_after = None
        database_drifted = bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before != database_sha256_after
        )
        return _result_payload(
            status="blocked" if database_drifted else "error",
            blockers=(
                ["duckdb_hash_changed_during_factor_vendor_dry_run"]
                if database_drifted
                else [f"factor_vendor_dry_run_failed_{type(exc).__name__}"]
            ),
            output_file=None,
            manifest_file_sha256=manifest_file_sha256,
            canonical_manifest_sha256=canonical_manifest_sha256,
            receipt=None,
            database_sha256_before=database_sha256_before,
            database_sha256_after=database_sha256_after,
            vendor_call_count=vendor_call_count,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch only the exact adjustment-factor cells in a reviewed current-rule "
            "manifest and write a governed dry-run receipt. DuckDB is never opened or written."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--factor-manifest-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--max-vendor-calls", type=int, default=32)
    parser.add_argument(
        "--created-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)
    result = run_current_rule_factor_vendor_dry_run(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        factor_manifest_file=args.factor_manifest_file,
        output_file=args.output_file,
        created_at=args.created_at,
        max_vendor_calls=args.max_vendor_calls,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return EXIT_SUCCESS if result.get("status") == "ready" else EXIT_BLOCKED


class FactorVendorDryRunError(ValueError):
    """Raised when governed vendor dry-run inputs or outputs are unsafe."""


class _DefaultTushareClient:
    def __init__(self) -> None:
        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            raise FactorVendorDryRunError("Tushare credentials are unavailable")
        self._api = import_tushare_pro().pro_api(token)

    def adj_factor(self, **kwargs: object) -> object:
        return self._api.adj_factor(**kwargs)


def _trusted_evidence_root(path: str | Path) -> Path:
    root = manifest_cli._absolute_without_resolve(path)
    manifest_cli._assert_output_path_within_trusted_root(
        trusted_root=root,
        output_file=root,
    )
    if not root.is_dir():
        raise FactorVendorDryRunError(
            "trusted_evidence_root must be an existing directory"
        )
    return root


def _existing_evidence_json_path(
    *,
    trusted_root: Path,
    evidence_file: str | Path,
    field_name: str,
) -> Path:
    raw = Path(evidence_file)
    candidate = manifest_cli._absolute_without_resolve(
        raw if raw.is_absolute() else trusted_root / raw
    )
    manifest_cli._assert_output_path_within_trusted_root(
        trusted_root=trusted_root,
        output_file=candidate,
    )
    if candidate.suffix.lower() != ".json" or not candidate.is_file():
        raise FactorVendorDryRunError(
            f"{field_name} must be an existing JSON file within trusted_evidence_root"
        )
    return candidate


def _database_binding_error(
    *,
    target_db: Path,
    current_sha256: str,
    manifest: Mapping[str, Any],
) -> str | None:
    database = manifest.get("database")
    if not isinstance(database, Mapping):
        return "factor_manifest_database_binding_missing"
    manifest_path = str(database.get("path") or "").strip()
    if not manifest_path:
        return "factor_manifest_database_path_missing"
    expected_path = manifest_cli._absolute_without_resolve(manifest_path)
    actual_path = manifest_cli._absolute_without_resolve(target_db)
    if expected_path != actual_path:
        return "factor_manifest_database_path_mismatch"
    before = str(database.get("sha256_before") or "").strip().upper()
    after = str(database.get("sha256_after") or "").strip().upper()
    if current_sha256.upper() != before or current_sha256.upper() != after:
        return "factor_manifest_database_sha256_mismatch"
    if database.get("unchanged") is not True or database.get("read_only") is not True:
        return "factor_manifest_database_attestation_invalid"
    return None


def _manifest_missing_cells(manifest: Mapping[str, Any]) -> set[tuple[str, str]]:
    raw_cells = manifest.get("missing_unique_cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise FactorVendorDryRunError(
            "factor_manifest.missing_unique_cells must be a non-empty list"
        )
    cells: set[tuple[str, str]] = set()
    for index, raw_cell in enumerate(raw_cells):
        if not isinstance(raw_cell, Mapping):
            raise FactorVendorDryRunError(
                f"factor_manifest.missing_unique_cells[{index}] must be an object"
            )
        stock_code = _stock_code(
            raw_cell.get("stock_code"),
            field_name=f"missing_unique_cells[{index}].stock_code",
        )
        trade_date = _date_text(
            raw_cell.get("trade_date"),
            field_name=f"missing_unique_cells[{index}].trade_date",
        )
        physical_key = raw_cell.get("physical_cell_key")
        if not isinstance(physical_key, Mapping) or (
            str(physical_key.get("stock_code") or "").strip().upper(),
            str(physical_key.get("trade_date") or "").strip(),
        ) != (stock_code, trade_date):
            raise FactorVendorDryRunError(
                f"factor_manifest.missing_unique_cells[{index}] physical key mismatch"
            )
        key = (stock_code, trade_date)
        if key in cells:
            raise FactorVendorDryRunError(
                "factor_manifest.missing_unique_cells contains duplicate physical keys"
            )
        cells.add(key)
    summary = manifest.get("summary")
    if not isinstance(summary, Mapping) or summary.get(
        "missing_unique_cell_count"
    ) != len(cells):
        raise FactorVendorDryRunError(
            "factor_manifest missing unique cell count mismatch"
        )
    return cells


def _target_rows_from_vendor_payload(
    payload: object,
    *,
    requested_trade_date: str,
    requested_codes: set[str],
) -> list[dict[str, Any]]:
    returned: list[dict[str, Any]] = []
    for record in _records_from_tabular_payload(payload):
        stock_code = (
            str(record.get("ts_code") or record.get("stock_code") or "").strip().upper()
        )
        if stock_code not in requested_codes:
            continue
        returned.append(
            {
                "requested_trade_date": requested_trade_date,
                "stock_code": stock_code,
                "trade_date": _vendor_date_value(record.get("trade_date")),
                "adj_factor": _vendor_factor_value(record.get("adj_factor")),
            }
        )
    return returned


def _records_from_tabular_payload(payload: object) -> list[dict[str, Any]]:
    if payload is None:
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        records = to_dict(orient="records")
    elif isinstance(payload, list):
        records = payload
    elif isinstance(payload, Mapping):
        records = payload.get("data")
    else:
        records = []
    if not isinstance(records, Sequence) or isinstance(
        records, (str, bytes, bytearray)
    ):
        return []
    return [dict(record) for record in records if isinstance(record, Mapping)]


def _vendor_date_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        candidate = f"{text[:4]}-{text[4:6]}-{text[6:]}"
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return text
    try:
        if len(text) == 10:
            return date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    return text or None


def _vendor_factor_value(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return numeric if math.isfinite(numeric) else str(value)


def _strict_exact_match(
    *,
    requested_cells: set[tuple[str, str]],
    returned_cells: Sequence[Mapping[str, Any]],
) -> tuple[bool, dict[str, int]]:
    occurrences: Counter[tuple[str, str]] = Counter()
    valid_values: defaultdict[tuple[str, str], set[float]] = defaultdict(set)
    wrong_date_count = 0
    invalid_factor_count = 0
    unexpected_target_cell_count = 0
    for cell in returned_cells:
        stock_code = str(cell.get("stock_code") or "").strip().upper()
        requested_trade_date = str(cell.get("requested_trade_date") or "").strip()
        trade_date = str(cell.get("trade_date") or "").strip()
        requested_key = (stock_code, requested_trade_date)
        occurrences[requested_key] += 1
        if requested_key not in requested_cells:
            unexpected_target_cell_count += 1
            continue
        if trade_date != requested_trade_date:
            wrong_date_count += 1
            continue
        factor = cell.get("adj_factor")
        if not _is_positive_finite(factor):
            invalid_factor_count += 1
            continue
        valid_values[requested_key].add(float(factor))
    duplicate_cell_count = sum(count > 1 for count in occurrences.values())
    conflict_cell_count = sum(len(values) > 1 for values in valid_values.values())
    accepted = {
        key
        for key, values in valid_values.items()
        if occurrences[key] == 1 and len(values) == 1
    }
    missing = requested_cells.difference(accepted)
    exact = (
        not any(
            (
                wrong_date_count,
                invalid_factor_count,
                unexpected_target_cell_count,
                duplicate_cell_count,
                conflict_cell_count,
                len(missing),
            )
        )
        and accepted == requested_cells
    )
    return exact, {
        "requested_cell_count": len(requested_cells),
        "returned_target_row_count": len(returned_cells),
        "accepted_cell_count": len(accepted),
        "missing_cell_count": len(missing),
        "wrong_date_row_count": wrong_date_count,
        "invalid_factor_row_count": invalid_factor_count,
        "duplicate_cell_count": duplicate_cell_count,
        "conflict_cell_count": conflict_cell_count,
        "unexpected_target_cell_count": unexpected_target_cell_count,
    }


def _receipt_indicates_exact_match(
    receipt: Mapping[str, Any],
    *,
    expected_cell_count: int,
    expected_vendor_call_count: int,
) -> bool:
    return (
        receipt.get("strict_exact_cells") is True
        and receipt.get("exact_set_match") is True
        and receipt.get("requested_cell_count") == expected_cell_count
        and receipt.get("returned_cell_count") == expected_cell_count
        and receipt.get("vendor_call_count") == expected_vendor_call_count
        and receipt.get("requested_unique_date_count") == expected_vendor_call_count
        and all(
            receipt.get(field_name) == 0
            for field_name in (
                "missing_cell_count",
                "extra_cell_count",
                "duplicate_cell_count",
                "wrong_date_cell_count",
                "invalid_cell_count",
            )
        )
    )


def _receipt_summary(receipt: Mapping[str, Any]) -> dict[str, int]:
    fields = (
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
    return {
        field_name: int(receipt[field_name])
        for field_name in fields
        if isinstance(receipt.get(field_name), int)
        and not isinstance(receipt.get(field_name), bool)
    }


def _result_payload(
    *,
    status: str,
    blockers: Sequence[str],
    output_file: Path | None,
    manifest_file_sha256: str | None,
    canonical_manifest_sha256: str | None,
    receipt: Mapping[str, Any] | None,
    database_sha256_before: str | None,
    database_sha256_after: str | None,
    vendor_call_count: int,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt_payload = dict(receipt or {})
    compact_summary = (
        {
            str(key): value
            for key, value in summary.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        if isinstance(summary, Mapping)
        else {}
    )
    return {
        "status": status,
        "blockers": _safe_blocker_codes(blockers),
        "output_file": str(output_file) if output_file is not None else None,
        "receipt_file_sha256": (
            manifest_cli._file_sha256(output_file)
            if output_file is not None and output_file.is_file()
            else None
        ),
        "canonical_receipt_sha256": receipt_payload.get("canonical_receipt_sha256"),
        "factor_manifest_file_sha256": manifest_file_sha256,
        "canonical_factor_manifest_sha256": canonical_manifest_sha256,
        "duckdb_sha256_before": database_sha256_before,
        "duckdb_sha256_after": database_sha256_after,
        "database_unchanged": bool(
            database_sha256_before
            and database_sha256_after
            and database_sha256_before == database_sha256_after
        ),
        "vendor_call_count": vendor_call_count,
        "summary": compact_summary,
    }


def _safe_blocker_codes(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        safe = (
            text if _SAFE_BLOCKER_PATTERN.fullmatch(text) else "blocker_detail_redacted"
        )
        if safe and safe not in result:
            result.append(safe)
    return result


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FactorVendorDryRunError(f"{field_name} must be an object")
    return dict(value)


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FactorVendorDryRunError(f"{field_name} is required")
    return text


def _date_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise FactorVendorDryRunError(f"{field_name} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise FactorVendorDryRunError(f"{field_name} must be strict YYYY-MM-DD")
    return text


def _stock_code(value: object, *, field_name: str) -> str:
    code = _required_text(value, field_name=field_name).upper()
    if not re.fullmatch(r"\d{6}\.(?:SH|SZ|BJ)", code):
        raise FactorVendorDryRunError(f"{field_name} must be a canonical stock code")
    return code


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise FactorVendorDryRunError(f"{field_name} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise FactorVendorDryRunError(
            f"{field_name} must be a positive integer"
        ) from exc
    if normalized <= 0 or normalized != value:
        raise FactorVendorDryRunError(f"{field_name} must be a positive integer")
    return normalized


def _is_positive_finite(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and numeric > 0


def _returned_cell_sort_key(cell: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(cell.get("requested_trade_date") or ""),
        str(cell.get("stock_code") or ""),
        str(cell.get("trade_date") or ""),
        str(cell.get("adj_factor")),
    )


if __name__ == "__main__":
    raise SystemExit(main())
