#!/usr/bin/env python3
"""Governed CLI for the exact current-rule adjustment-factor write."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks import stock_analysis_current_rule_factor_write as write_task  # noqa: E402

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2


def _compact_result(receipt: dict[str, Any]) -> dict[str, Any]:
    database = receipt.get("database")
    backup = receipt.get("backup")
    blockers = receipt.get("blockers")

    return {
        "status": receipt.get("status"),
        "blockers": list(blockers) if isinstance(blockers, list) else [],
        "database_write_executed": receipt.get("database_write_executed"),
        "historical_availability_proven": receipt.get("historical_availability_proven"),
        "formal_historical_replay_use_allowed": receipt.get(
            "formal_historical_replay_use_allowed"
        ),
        "certification_allowed": receipt.get("certification_allowed"),
        "write_receipt": {
            "path": receipt.get("write_receipt_path"),
            "file_sha256": receipt.get("write_receipt_file_sha256"),
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
        "source_version": receipt.get("source_version"),
        "run_id": receipt.get("run_id"),
    }


def run_current_rule_factor_write_cli(
    *,
    duckdb_path: str | Path,
    trusted_evidence_root: str | Path,
    reviewed_factor_manifest_file: str | Path,
    vendor_receipt_file: str | Path,
    target_backup_file: str | Path,
    write_receipt_file: str | Path,
    executed_at: str,
    approval_reference: str,
    expected_approved_scope_sha256: str,
    allow_write: bool = False,
) -> dict[str, Any]:
    try:
        receipt = write_task.write_stock_analysis_current_rule_factor_cells(
            duckdb_path=duckdb_path,
            trusted_evidence_root=trusted_evidence_root,
            reviewed_factor_manifest_file=reviewed_factor_manifest_file,
            vendor_receipt_file=vendor_receipt_file,
            target_backup_file=target_backup_file,
            write_receipt_file=write_receipt_file,
            executed_at=executed_at,
            approval_reference=approval_reference,
            expected_approved_scope_sha256=expected_approved_scope_sha256,
            allow_write=allow_write,
        )
    except Exception as exc:
        pending_intent_present = _has_pending_intent(
            trusted_evidence_root=trusted_evidence_root,
            write_receipt_file=write_receipt_file,
        )
        return {
            "status": "blocked",
            "blockers": [f"factor_write_failed_{type(exc).__name__}"],
            "database_write_executed": None if pending_intent_present else False,
            "historical_availability_proven": False,
            "formal_historical_replay_use_allowed": False,
            "certification_allowed": False,
            "write_receipt": {
                "path": str(write_receipt_file),
                "file_sha256": None,
                "canonical_sha256": None,
            },
            "backup": {"path": str(target_backup_file), "sha256": None},
            "database": {
                "path": str(duckdb_path),
                "sha256_before": None,
                "sha256_after": None,
            },
            "inserted_row_count": None,
            "target_cell_count": None,
            "source_version": None,
            "run_id": None,
        }
    compact = _compact_result(receipt)
    write_receipt = compact.get("write_receipt")
    raw_receipt_path = Path(write_receipt_file)
    receipt_path = (
        raw_receipt_path
        if raw_receipt_path.is_absolute()
        else Path(trusted_evidence_root) / raw_receipt_path
    ).resolve()
    if isinstance(write_receipt, dict) and receipt_path.is_file():
        write_receipt["path"] = str(receipt_path)
        write_receipt["file_sha256"] = _file_sha256(receipt_path)
    return compact


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _has_pending_intent(
    *,
    trusted_evidence_root: str | Path,
    write_receipt_file: str | Path,
) -> bool:
    raw_path = Path(write_receipt_file)
    path = (
        raw_path if raw_path.is_absolute() else Path(trusted_evidence_root) / raw_path
    )
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write the approved exact current-rule adjustment-factor remediation "
            "cells into DuckDB and persist a governed write receipt."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--trusted-evidence-root", required=True)
    parser.add_argument(
        "--factor-manifest-file",
        "--reviewed-factor-manifest-file",
        dest="reviewed_factor_manifest_file",
        required=True,
    )
    parser.add_argument("--vendor-receipt-file", required=True)
    parser.add_argument(
        "--backup-file",
        "--target-backup-file",
        dest="target_backup_file",
        required=True,
    )
    parser.add_argument("--write-receipt-file", required=True)
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--expected-approved-scope-sha256", required=True)
    parser.add_argument(
        "--executed-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    parser.add_argument("--allow-write", action="store_true")
    args = parser.parse_args(argv)

    result = run_current_rule_factor_write_cli(
        duckdb_path=args.duckdb_path,
        trusted_evidence_root=args.trusted_evidence_root,
        reviewed_factor_manifest_file=args.reviewed_factor_manifest_file,
        vendor_receipt_file=args.vendor_receipt_file,
        target_backup_file=args.target_backup_file,
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
        else EXIT_BLOCKED
    )


if __name__ == "__main__":
    raise SystemExit(main())
