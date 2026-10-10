from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

SOURCE_IMPACT_ASSET = Path(__file__).with_name(
    "qdb_finance_2026_v1_0_1_source_impact.json"
)
APPROVED_SOURCE_IMPACT_SHA256 = (
    "b4bf1dda371c9866d196e05cc63b1a65ef3711c59333346f50651e4651586622"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def load_finance_metric_source_impact() -> dict[str, Any]:
    raw = SOURCE_IMPACT_ASSET.read_bytes()
    asset_hash = hashlib.sha256(raw).hexdigest()
    if asset_hash != APPROVED_SOURCE_IMPACT_SHA256:
        raise ValueError(
            f"finance metric source impact asset SHA-256 {asset_hash} does not match "
            f"approved SHA-256 {APPROVED_SOURCE_IMPACT_SHA256}"
        )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finance metric source impact asset must be an object")
    _validate_source_impact(payload)
    return {**payload, "impact_asset_sha256": asset_hash}


def build_finance_metric_source_impact(
    *,
    report_month: str,
    rule_version: str,
    ledger_sha256: str,
    daily_sha256: str,
    metric_values: Mapping[str, Decimal | None],
) -> dict[str, Any] | None:
    contract = load_finance_metric_source_impact()
    if (
        report_month != contract["report_month"]
        or rule_version != contract["current_rule_version"]
        or ledger_sha256 != contract["current_ledger_sha256"]
        or daily_sha256 != contract["daily_sha256"]
    ):
        return None

    current_values = {
        metric_id: _canonical_decimal_text(value)
        for metric_id, value in sorted(metric_values.items())
    }
    current_digest = hashlib.sha256(
        json.dumps(
            current_values,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    compared_metric_count = len(current_values)
    metric_total = contract["reference_metric_count"]
    comparable = compared_metric_count == metric_total
    numerically_unchanged = (
        comparable and current_digest == contract["reference_numeric_digest"]
    )
    serialization_ids = (
        contract["serialization_only_metric_ids"] if numerically_unchanged else []
    )
    return {
        "contract_version": contract["contract_version"],
        "impact_asset_sha256": contract["impact_asset_sha256"],
        "status": (
            "numerically_unchanged"
            if numerically_unchanged
            else "numeric_digest_mismatch"
            if comparable
            else "comparison_incomplete"
        ),
        "comparison_basis": contract["comparison_basis"],
        "report_month": report_month,
        "reference_rule_version": contract["reference_rule_version"],
        "current_rule_version": rule_version,
        "reference_result_sha256": contract["reference_result_sha256"],
        "reference_ledger_sha256": contract["reference_ledger_sha256"],
        "current_ledger_sha256": ledger_sha256,
        "daily_sha256": daily_sha256,
        "metric_total": metric_total,
        "compared_metric_count": compared_metric_count,
        "reference_numeric_digest": contract["reference_numeric_digest"],
        "current_numeric_digest": current_digest,
        "numeric_changed_count": 0 if numerically_unchanged else None,
        "serialization_only_count": len(serialization_ids),
        "serialization_only_metric_ids": serialization_ids,
        "formal_use_allowed": False,
        "certification_effect": "none",
    }


def _canonical_decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _validate_source_impact(payload: dict[str, Any]) -> None:
    expected = {
        "contract_version": "candidate-source-version-impact-v1",
        "report_month": "202606",
        "reference_rule_version": "qdb-finance-2026-v1.0.0",
        "current_rule_version": "qdb-finance-2026-v1.0.1",
        "comparison_basis": "canonical_decimal_value",
        "reference_metric_count": 186,
        "formal_use_allowed": False,
        "certification_effect": "none",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"source impact {field} must equal {value!r}")
    for field in (
        "reference_result_sha256",
        "reference_ledger_sha256",
        "current_ledger_sha256",
        "daily_sha256",
        "reference_numeric_digest",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
            raise ValueError(f"source impact {field} must be a SHA-256 string")
    metric_ids = payload.get("serialization_only_metric_ids")
    if (
        not isinstance(metric_ids, list)
        or len(metric_ids) != 8
        or len(metric_ids) != len(set(metric_ids))
        or not all(isinstance(metric_id, str) and metric_id for metric_id in metric_ids)
    ):
        raise ValueError("source impact serialization_only_metric_ids must contain 8 unique IDs")
