#!/usr/bin/env python3
"""CLI for the explicitly approved page-gap exact-factor write."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import stock_analysis_page_gap_factor_write as write_task  # noqa: E402

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2


def run_page_gap_factor_write_cli(
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
    """Run the writer and return a compact, non-sensitive status object."""

    try:
        receipt = write_task.write_stock_analysis_page_gap_factor_cells(
            duckdb_path=duckdb_path,
            trusted_evidence_root=trusted_evidence_root,
            page_gap_factor_manifest_file=page_gap_factor_manifest_file,
            vendor_receipt_file=vendor_receipt_file,
            target_backup_file=target_backup_file,
            write_receipt_file=write_receipt_file,
            executed_at=executed_at,
            approval_reference=approval_reference,
            expected_approved_scope_sha256=expected_approved_scope_sha256,
            allow_write=allow_write,
        )
    except Exception as exc:
        pending_path = _safe_receipt_path(
            trusted_evidence_root=trusted_evidence_root,
            write_receipt_file=write_receipt_file,
        )
        pending = _has_pending_intent(
            trusted_evidence_root=trusted_evidence_root,
            write_receipt_file=write_receipt_file,
        )
        return {
            "status": "blocked",
            "blockers": [f"page_gap_factor_write_failed_{type(exc).__name__}"],
            "database_write_executed": None if pending else False,
            "completion_attested": False,
            "pending_intent_detected": pending,
            "historical_availability_proven": False,
            "formal_historical_replay_use_allowed": False,
            "certification_allowed": False,
            "downstream_materialization_executed": False,
            "page_gap_closed": False,
            "write_receipt": {
                "path": str(pending_path) if pending and pending_path else None,
                "file_sha256": (
                    write_task._write_helpers._file_sha256(pending_path)
                    if pending and pending_path and pending_path.is_file()
                    else None
                ),
                "canonical_sha256": (
                    _pending_canonical_sha256(pending_path)
                    if pending and pending_path
                    else None
                ),
            },
            "backup": {"path": str(target_backup_file), "sha256": None},
            "database": {
                "path": str(duckdb_path),
                "sha256_before": None,
                "sha256_after": None,
            },
            "inserted_row_count": None,
            "target_cell_count": None,
            "target_cells_sha256": None,
            "target_rows_sha256": None,
            "approval_scope_sha256": None,
            "source_version": None,
            "run_id": None,
        }
    compact = _compact_result(receipt)
    receipt_path = _safe_receipt_path(
        trusted_evidence_root=trusted_evidence_root,
        write_receipt_file=write_receipt_file,
    )
    if receipt_path and receipt_path.is_file():
        compact["write_receipt"]["path"] = str(receipt_path)
        compact["write_receipt"]["file_sha256"] = (
            write_task._write_helpers._file_sha256(receipt_path)
        )
    return compact


def _compact_result(receipt: dict[str, Any]) -> dict[str, Any]:
    database = receipt.get("database")
    backup = receipt.get("backup")
    return {
        "status": receipt.get("status"),
        "blockers": [],
        "database_write_executed": receipt.get("database_write_executed"),
        "completion_attested": receipt.get("completion_attested"),
        "pending_intent_detected": False,
        "historical_availability_proven": receipt.get("historical_availability_proven"),
        "formal_historical_replay_use_allowed": receipt.get(
            "formal_historical_replay_use_allowed"
        ),
        "certification_allowed": receipt.get("certification_allowed"),
        "downstream_materialization_executed": receipt.get(
            "downstream_materialization_executed"
        ),
        "page_gap_closed": receipt.get("page_gap_closed"),
        "write_receipt": {
            "path": None,
            "file_sha256": None,
            "canonical_sha256": receipt.get("canonical_write_receipt_sha256"),
        },
        "backup": {
            "path": backup.get("path") if isinstance(backup, dict) else None,
            "sha256": backup.get("sha256") if isinstance(backup, dict) else None,
        },
        "database": {
            "path": database.get("path") if isinstance(database, dict) else None,
            "sha256_before": (
                database.get("sha256_before") if isinstance(database, dict) else None
            ),
            "sha256_after": (
                database.get("sha256_after") if isinstance(database, dict) else None
            ),
        },
        "inserted_row_count": receipt.get("inserted_row_count"),
        "target_cell_count": receipt.get("target_cell_count"),
        "target_cells_sha256": receipt.get("target_cells_sha256"),
        "target_rows_sha256": receipt.get("target_rows_sha256"),
        "approval_scope_sha256": receipt.get("approval_scope_sha256"),
        "source_version": receipt.get("source_version"),
        "run_id": receipt.get("run_id"),
    }


def _safe_receipt_path(
    *, trusted_evidence_root: str | Path, write_receipt_file: str | Path
) -> Path | None:
    try:
        root = write_task._write_helpers._absolute_without_resolve(
            trusted_evidence_root
        )
        candidate = write_task._write_helpers._path_within_root(
            trusted_root=root,
            path=write_receipt_file,
            field_name="write_receipt_file",
        )
    except Exception:
        return None
    return candidate


def _has_pending_intent(
    *, trusted_evidence_root: str | Path, write_receipt_file: str | Path
) -> bool:
    path = _safe_receipt_path(
        trusted_evidence_root=trusted_evidence_root,
        write_receipt_file=write_receipt_file,
    )
    if path is None:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("receipt_kind") == write_task.PENDING_INTENT_KIND
        and payload.get("status") == write_task.PENDING_STATUS
        and payload.get("completion_attested") is False
    )


def _pending_canonical_sha256(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    value = (
        payload.get("canonical_pending_intent_sha256")
        if isinstance(payload, dict)
        else None
    )
    return value if isinstance(value, str) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument("--factor-manifest-file", required=True)
    parser.add_argument("--vendor-receipt-file", required=True)
    parser.add_argument("--backup-file", required=True)
    parser.add_argument("--write-receipt-file", required=True)
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--expected-approved-scope-sha256", required=True)
    parser.add_argument(
        "--executed-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    parser.add_argument("--allow-write", action="store_true")
    args = parser.parse_args(argv)
    result = run_page_gap_factor_write_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        page_gap_factor_manifest_file=args.factor_manifest_file,
        vendor_receipt_file=args.vendor_receipt_file,
        target_backup_file=args.backup_file,
        write_receipt_file=args.write_receipt_file,
        executed_at=args.executed_at,
        approval_reference=args.approval_reference,
        expected_approved_scope_sha256=args.expected_approved_scope_sha256,
        allow_write=args.allow_write,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return (
        EXIT_SUCCESS
        if result.get("status") == write_task.COMPLETED_STATUS
        and result.get("database_write_executed") is True
        and result.get("completion_attested") is True
        else EXIT_BLOCKED
    )


if __name__ == "__main__":
    raise SystemExit(main())
