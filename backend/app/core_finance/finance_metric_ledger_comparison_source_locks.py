from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from pathlib import Path
from typing import Any

from backend.app.core_finance.finance_metric_engine import (
    EXPECTED_SOURCE_HASHES_BY_VERSION,
)

LOCK_ASSET = Path(__file__).with_name(
    "qdb_ledger_comparison_source_locks_2026_v1_0_0.json"
)
PINNED_LOCK_ASSET_SHA256 = (
    "eec5792d94b2c53171c240113fc25f7997a8c2bfc58138af4bec496718521429"
)
COMPATIBLE_RULE_VERSION = "qdb-finance-2026-v1.0.1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REPORT_MONTH_PATTERN = re.compile(r"^\d{4}(?:0[1-9]|1[0-2])$")

EXPECTED_TOP_LEVEL = {
    "contract_version": "ledger-comparison-source-locks-v1",
    "lock_version": "qdb-ledger-comparison-source-locks-2026-v1.0.0",
    "scope": "ledger_only_key_metrics_and_component_detail",
    "compatible_rule_version": COMPATIBLE_RULE_VERSION,
    "sheet": "综本",
    "currency": "CNX",
    "value_basis": "ending_balance",
    "period_basis": "natural_month_end",
    "formal_use_allowed": False,
    "certification_effect": "none",
}
EXPECTED_RECORD_FIELDS = {"report_month", "report_date", "file", "sha256"}


def load_finance_metric_ledger_comparison_source_locks() -> dict[str, Any]:
    """Load the immutable source-identity evidence for ledger-only comparisons."""

    raw = LOCK_ASSET.read_bytes()
    asset_hash = hashlib.sha256(raw).hexdigest()
    if asset_hash != PINNED_LOCK_ASSET_SHA256:
        raise ValueError(
            f"ledger comparison source-lock asset SHA-256 {asset_hash} does not "
            f"match pinned SHA-256 {PINNED_LOCK_ASSET_SHA256}"
        )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("ledger comparison source-lock asset must be an object")
    _validate_finance_metric_ledger_comparison_source_locks(payload)
    return {**payload, "asset_sha256": asset_hash}


def ledger_comparison_source_hashes(contract: dict[str, Any]) -> dict[str, str]:
    """Return the exact governed file-to-hash map without date fallback."""

    return {str(record["file"]): str(record["sha256"]) for record in contract["records"]}


def _validate_finance_metric_ledger_comparison_source_locks(
    payload: dict[str, Any],
) -> None:
    expected_fields = {*EXPECTED_TOP_LEVEL, "records"}
    if set(payload) != expected_fields:
        raise ValueError(
            "ledger comparison source-lock asset fields must match the fixed contract"
        )
    for field, expected in EXPECTED_TOP_LEVEL.items():
        if payload.get(field) != expected:
            raise ValueError(
                f"ledger comparison source-lock {field} must equal {expected!r}"
            )

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("ledger comparison source-lock records must be a non-empty list")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("ledger comparison source-lock records must contain objects")

    months: list[str] = []
    files: list[str] = []
    for record in records:
        if set(record) != EXPECTED_RECORD_FIELDS:
            raise ValueError(
                "ledger comparison source-lock record fields must match the fixed contract"
            )
        report_month = record.get("report_month")
        report_date = record.get("report_date")
        file_name = record.get("file")
        source_hash = record.get("sha256")
        if not isinstance(report_month, str) or not REPORT_MONTH_PATTERN.fullmatch(
            report_month
        ):
            raise ValueError(
                "ledger comparison source-lock file/report month/report date must agree"
            )
        year = int(report_month[:4])
        month = int(report_month[4:])
        expected_date = f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"
        if (
            file_name != f"总账对账{report_month}.xlsx"
            or report_date != expected_date
        ):
            raise ValueError(
                "ledger comparison source-lock file/report month/report date must agree"
            )
        if not isinstance(source_hash, str) or not SHA256_PATTERN.fullmatch(source_hash):
            raise ValueError(
                "ledger comparison source-lock hashes must be lowercase SHA-256 strings"
            )
        months.append(report_month)
        files.append(file_name)

    if len(months) != len(set(months)) or len(files) != len(set(files)):
        raise ValueError(
            "ledger comparison source-lock records require unique report months and files"
        )
    if months != sorted(months):
        raise ValueError(
            "ledger comparison source-lock records must be ordered by report month"
        )

    active_rule_hash = EXPECTED_SOURCE_HASHES_BY_VERSION[
        COMPATIBLE_RULE_VERSION
    ]["总账对账202606.xlsx"]
    manifest_202606 = next(
        (
            str(record["sha256"])
            for record in records
            if record["report_month"] == "202606"
        ),
        None,
    )
    if manifest_202606 != active_rule_hash:
        raise ValueError(
            "ledger comparison 202606 lock must match active rule source evidence"
        )
