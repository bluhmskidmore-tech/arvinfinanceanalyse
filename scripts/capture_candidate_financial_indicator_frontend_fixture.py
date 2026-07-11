"""Create a synthetic candidate-indicator fixture for the frontend demo client."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.schemas.candidate_financial_indicators import (  # noqa: E402
    build_promotion_evidence_pack_key,
    build_promotion_readiness_evidence_key,
)

DEFAULT_SOURCE_DIR = REPO_ROOT / "data_input" / "pnl_总账对账-日均"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "mocks"
    / "fixtures"
    / "ledgerPnlCandidateFinancialIndicators202606.json"
)

SYNTHETIC_VALIDATION_SEVERITIES = (
    ("period.same_end_date", "error"),
    ("period.ytd_starts_jan1", "error"),
    ("period.month_is_calendar_month", "error"),
    ("currency.cnx_only", "error"),
    ("ledger.balance_identity", "error"),
    ("ledger.duplicate_full_code", "warning"),
    ("rules.missing_accounts", "warning"),
    ("recon.company_deposit", "warning"),
    ("recon.retail_deposit", "warning"),
    ("recon.personal_loan", "warning"),
    ("recon.loan_interest", "warning"),
    ("recon.noninterest", "warning"),
)


def _synthetic_hash(label: str) -> str:
    return hashlib.sha256(f"moss-synthetic-candidate-fixture:{label}".encode()).hexdigest()


def _synthetic_metric_value(index: int, status: str) -> str | None:
    if status == "error":
        return None
    if status == "manual_default":
        return "0"
    return f"{index + 1}.{(index * 37) % 10_000:04d}"


def _synthetic_metric_status(metric_id: str) -> str:
    return (
        "manual_default"
        if metric_id.startswith("input.adjustment.")
        else "ok"
    )


def _synthetic_metric_statuses(
    metrics: list[dict[str, Any]],
    lineage_by_metric: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    statuses = {
        metric["metric_id"]: _synthetic_metric_status(metric["metric_id"])
        for metric in metrics
    }
    changed = True
    while changed:
        changed = False
        for metric in metrics:
            metric_id = metric["metric_id"]
            if statuses[metric_id] == "manual_default":
                continue
            has_non_ok_dependency = any(
                row["lineage_type"] == "metric"
                and statuses.get(row["metric_id"], "warning") != "ok"
                for row in lineage_by_metric[metric_id]
            )
            if has_non_ok_dependency and statuses[metric_id] != "warning":
                statuses[metric_id] = "warning"
                changed = True
    return statuses


def _sanitize_capture(captured: dict[str, Any]) -> dict[str, Any]:
    base_result = captured["result"]
    lineage_by_metric = captured["lineage_by_metric"]
    synthetic_rule_hash = _synthetic_hash("rule")
    base_idempotency_key = _synthetic_hash("base")
    lineage_idempotency_key = _synthetic_hash("lineage")
    source_hashes = {
        "ledger": _synthetic_hash("ledger-source"),
        "daily": _synthetic_hash("daily-source"),
    }
    metric_statuses = _synthetic_metric_statuses(
        base_result["metrics"],
        lineage_by_metric,
    )
    metric_values = {
        metric["metric_id"]: _synthetic_metric_value(
            index,
            metric_statuses[metric["metric_id"]],
        )
        for index, metric in enumerate(base_result["metrics"])
    }

    synthetic_lineage: dict[str, list[dict[str, Any]]] = {}
    account_ordinal = 0
    for metric in base_result["metrics"]:
        metric_id = metric["metric_id"]
        rows: list[dict[str, Any]] = []
        for row_index, row in enumerate(lineage_by_metric[metric_id]):
            if row["lineage_type"] == "account":
                account_ordinal += 1
                raw_yuan = account_ordinal * 100_000_000
                contribution_yi = Decimal(account_ordinal) * Decimal(row["weight"])
                rows.append(
                    {
                        "lineage_type": "account",
                        "source": row["source"],
                        "basis": row["basis"],
                        "level": row["level"],
                        "code": f"99{account_ordinal:06d}",
                        "weight": row["weight"],
                        "observed": True,
                        "raw_yuan": str(raw_yuan),
                        "contribution_yi": format(contribution_yi, "f"),
                        "evidence_refs": [f"DEMO:{metric_id}:{row_index + 1}"],
                    }
                )
            elif row["lineage_type"] == "metric":
                dependency_value = metric_values.get(row["metric_id"])
                contribution_yi = (
                    None
                    if dependency_value is None
                    else format(
                        Decimal(dependency_value) * Decimal(row["weight"]),
                        "f",
                    )
                )
                rows.append(
                    {
                        "lineage_type": "metric",
                        "metric_id": row["metric_id"],
                        "weight": row["weight"],
                        "metric_value_yi": dependency_value,
                        "contribution_yi": contribution_yi,
                        "dependency_status": metric_statuses.get(
                            row["metric_id"],
                            "warning",
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "lineage_type": "manual",
                        "supplied": False,
                        "value_yi": "0",
                    }
                )
        synthetic_lineage[metric_id] = rows

    report_month = base_result["report_month"]
    report_date = base_result["report_date"]
    year = report_month[:4]
    month_start = f"{year}-{report_month[4:]}-01"

    def synthetic_period(evidence_id: str, start: str) -> dict[str, str]:
        return {
            "evidence_id": evidence_id,
            "start": start,
            "end": report_date,
            "source_cell": f"DEMO:{evidence_id}:PERIOD",
        }

    sources = [
        {
            "source_kind": "ledger",
            "file_name": f"synthetic-ledger-{report_month}.xlsx",
            "exists": True,
            "sha256": source_hashes["ledger"],
            "locked_sha256": None,
            "locked_hash_match": None,
            "sheets": ["DEMO-LEDGER"],
            "periods": [synthetic_period("ledger", month_start)],
        },
        {
            "source_kind": "daily",
            "file_name": f"synthetic-daily-{report_month}.xlsx",
            "exists": True,
            "sha256": source_hashes["daily"],
            "locked_sha256": None,
            "locked_hash_match": None,
            "sheets": ["DEMO-DAILY"],
            "periods": [
                synthetic_period("daily_ytd", f"{year}-01-01"),
                synthetic_period("daily_month", month_start),
                synthetic_period("microloan_ytd", f"{year}-01-01"),
                synthetic_period("microloan_month", month_start),
                synthetic_period("microloan_ledger", month_start),
            ],
        },
    ]

    metrics = []
    for metric in base_result["metrics"]:
        status = metric_statuses[metric["metric_id"]]
        metrics.append(
            {
                "metric_id": metric["metric_id"],
                "name": metric["name"],
                "category": metric["category"],
                "basis": metric["basis"],
                "unit": metric["unit"],
                "value": metric_values[metric["metric_id"]],
                "status": status,
                "reasons": (
                    []
                    if status == "ok"
                    else (
                        ["Synthetic demo manual input defaults to zero."]
                        if status == "manual_default"
                        else [
                            "Synthetic demo dependency status propagated from rule topology."
                        ]
                    )
                ),
                "lineage": [],
            }
        )

    validations = [
        {
            "validation_id": validation_id,
            "severity": severity,
            "passed": True,
            "message": "Synthetic demo validation passed",
            "delta_yi": "0",
            "sample": [],
        }
        for validation_id, severity in SYNTHETIC_VALIDATION_SEVERITIES
    ]
    manual_metric_ids = [
        metric["metric_id"]
        for metric in metrics
        if metric["status"] == "manual_default"
    ]
    warning_count = sum(metric["status"] == "warning" for metric in metrics)
    gaps = [
        {
            "gap_id": "synthetic.source_unlocked",
            "severity": "info",
            "kind": "source_hash",
            "title": "Synthetic demo sources are not governed evidence",
            "detail": "Synthetic source hashes only identify demo payloads and are not production evidence.",
            "metric_ids": [],
        },
        {
            "gap_id": "synthetic.manual_defaults",
            "severity": "info",
            "kind": "manual_input",
            "title": "Synthetic manual inputs use demo defaults",
            "detail": "Manual demo metrics are fixed to zero and are not production adjustments.",
            "metric_ids": manual_metric_ids,
        },
    ]
    source_version = "sv_synthetic_candidate_financial_indicators_v1"
    promotion_readiness = {
        "readiness_contract_version": "promotion-readiness-v1",
        "readiness_evidence_key": "",
        "status": "blocked",
        "blocking_count": 3,
        "check_total": 6,
        "candidate_idempotency_key": base_idempotency_key,
        "formal_contract_status": "missing_contract",
        "formal_use_allowed": False,
        "owner_approval_required": True,
        "next_action": "Synthetic demo sources are not approved evidence.",
        "checks": [
            {
                "check_id": "rule_asset",
                "label": "规则资产与候选计算",
                "status": "passed",
                "blocking": False,
                "summary": "Synthetic demo rule topology is loaded.",
                "evidence_refs": ["synthetic-rule"],
                "action": "Keep the synthetic demo rule unchanged.",
            },
            {
                "check_id": "source_evidence",
                "label": "来源期间与锁定哈希",
                "status": "blocked",
                "blocking": True,
                "summary": "Synthetic sources are intentionally not approved evidence.",
                "evidence_refs": ["synthetic-ledger", "synthetic-daily"],
                "action": "Synthetic demo sources cannot be promoted.",
            },
            {
                "check_id": "validation_controls",
                "label": "控制校验",
                "status": "passed",
                "blocking": False,
                "summary": "12 / 12 synthetic controls passed.",
                "evidence_refs": [item["validation_id"] for item in validations],
                "action": "Synthetic controls are complete.",
            },
            {
                "check_id": "manual_inputs",
                "label": "手工调整输入",
                "status": "blocked",
                "blocking": True,
                "summary": f"{len(manual_metric_ids)} synthetic manual inputs use demo defaults.",
                "evidence_refs": manual_metric_ids,
                "action": "Demo defaults are not approved manual inputs.",
            },
            {
                "check_id": "account_coverage",
                "label": "规则科目覆盖",
                "status": "passed",
                "blocking": False,
                "summary": "Synthetic account topology is complete.",
                "evidence_refs": [],
                "action": "Synthetic account topology is complete.",
            },
            {
                "check_id": "formal_contract",
                "label": "正式契约登记",
                "status": "blocked",
                "blocking": True,
                "summary": "Synthetic demo values have no formal contract.",
                "evidence_refs": ["GS-SYNTHETIC-CANDIDATE-MISSING"],
                "action": "Synthetic demo values cannot be registered as formal evidence.",
            },
        ],
    }
    promotion_readiness["readiness_evidence_key"] = build_promotion_readiness_evidence_key(
        candidate_idempotency_key=base_idempotency_key,
        formal_contract_status=promotion_readiness["formal_contract_status"],
        checks=[
            {
                "check_id": item["check_id"],
                "status": item["status"],
                "evidence_refs": item["evidence_refs"],
            }
            for item in promotion_readiness["checks"]
        ],
    )
    owner_requirements = [
        {
            "requirement_id": "source_evidence.1",
            "category": "source_evidence",
            "status": "awaiting_owner_input",
            "submitted_value": None,
            "evidence_refs": ["synthetic-ledger", "synthetic-daily"],
            "required_evidence": ["Approved production source evidence"],
            "action": "Synthetic demo sources cannot be promoted.",
        },
        *[
            {
                "requirement_id": f"manual_input.{index}",
                "category": "manual_input",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": [metric_id],
                "required_evidence": ["Approved period-matched manual input"],
                "action": "Demo defaults are not approved manual inputs.",
            }
            for index, metric_id in enumerate(manual_metric_ids, start=1)
        ],
        {
            "requirement_id": "formal_contract.1",
            "category": "formal_contract",
            "status": "awaiting_owner_input",
            "submitted_value": None,
            "evidence_refs": ["GS-SYNTHETIC-CANDIDATE-MISSING"],
            "required_evidence": ["Frozen formal contract evidence"],
            "action": "Synthetic demo values cannot be registered as formal evidence.",
        },
        {
            "requirement_id": "business_owner_approval.1",
            "category": "business_owner_approval",
            "status": "awaiting_owner_input",
            "submitted_value": None,
            "evidence_refs": [],
            "required_evidence": ["Finance and data-governance owner approval"],
            "action": "Owner approval remains required after technical checks pass.",
        },
    ]
    formal_sample_id = "GS-SYNTHETIC-CANDIDATE-MISSING"
    formal_source_version = "sv_formal_financial_indicators_contract_unavailable"
    evidence_pack = {
        "contract_version": "candidate-promotion-evidence-v1",
        "evidence_pack_key": "",
        "report_month": base_result["report_month"],
        "report_date": base_result["report_date"],
        "rule_version": base_result["rule_version"],
        "rule_hash": synthetic_rule_hash,
        "source_version": source_version,
        "source_alignment": "not_applicable",
        "candidate_idempotency_key": base_idempotency_key,
        "readiness_contract_version": "promotion-readiness-v1",
        "readiness_evidence_key": promotion_readiness["readiness_evidence_key"],
        "metric_status": "candidate",
        "formal_use_allowed": False,
        "owner_approval_required": True,
        "contains_metric_values": False,
        "contains_formal_values": False,
        "certification_effect": "none",
        "blocking_count": 3,
        "check_total": 6,
        "formal_contract_status": "missing_contract",
        "formal_sample_id": formal_sample_id,
        "formal_source_version": formal_source_version,
        "formal_release_gate_status": None,
        "formal_metric_count": 0,
        "checks": promotion_readiness["checks"],
        "owner_requirement_count": len(owner_requirements),
        "owner_requirements": owner_requirements,
        "outcome_status": "blocked",
    }
    evidence_pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=evidence_pack
    )
    promotion_readiness["evidence_pack"] = evidence_pack
    result = {
        "report_month": base_result["report_month"],
        "report_date": base_result["report_date"],
        "currency": base_result["currency"],
        "basis": base_result["basis"],
        "metric_status": base_result["metric_status"],
        "formal_use_allowed": base_result["formal_use_allowed"],
        "calculation_status": "warning",
        "source_alignment": "not_applicable",
        "source_version": source_version,
        "rule_version": base_result["rule_version"],
        "rule_hash": synthetic_rule_hash,
        "idempotency_key": base_idempotency_key,
        "requested_metric_id": None,
        "include_lineage": False,
        "promotion_readiness": promotion_readiness,
        "sources": sources,
        "summary": {
            "metric_total": 186,
            "metric_evaluated": 186,
            "metric_returned": 186,
            "ok_count": 186 - len(manual_metric_ids) - warning_count,
            "warning_count": warning_count,
            "manual_default_count": len(manual_metric_ids),
            "error_count": 0,
            "validation_total": 12,
            "validation_evaluated": 12,
            "validation_passed": 12,
            "validation_warning_failed": 0,
            "validation_error_failed": 0,
        },
        "metrics": metrics,
        "validations": validations,
        "gaps": gaps,
    }
    result_meta = {
        "trace_id": f"mock_candidate_financial_indicators_{report_month}_synthetic",
        "basis": "ledger",
        "result_kind": "ledger_pnl.candidate_financial_indicators",
        "formal_use_allowed": False,
        "amount_currency_basis": "CNX",
        "amount_currency_basis_note": "Synthetic CNX demo values; not financial evidence.",
        "source_version": source_version,
        "vendor_version": "vv_none",
        "rule_version": base_result["rule_version"],
        "cache_version": "cv_synthetic_candidate_financial_indicators_v1",
        "cache_key": base_idempotency_key,
        "quality_flag": "warning",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "requested_report_date": report_month,
        "resolved_report_date": report_date,
        "scenario_flag": False,
        "as_of_date": report_date,
        "date_basis": "report_month_end",
        "fallback_date": None,
        "generated_at": "2000-01-01T00:00:00Z",
        "filters_applied": {
            "report_month": report_month,
            "include_lineage": False,
            "metric_id": None,
        },
        "tables_used": ["synthetic_candidate_ledger", "synthetic_candidate_daily"],
        "evidence_rows": len(metrics),
        "next_drill": [],
        "source_surface": None,
    }
    return {
        "fixture_kind": "synthetic_candidate_financial_indicator_demo",
        "capture_status": "candidate_non_formal",
        "report_month": base_result["report_month"],
        "rule_version": base_result["rule_version"],
        "rule_hash": synthetic_rule_hash,
        "source_hashes": source_hashes,
        "base_idempotency_key": base_idempotency_key,
        "lineage_idempotency_key": lineage_idempotency_key,
        "result_meta": result_meta,
        "result": result,
        "lineage_by_metric": synthetic_lineage,
    }


def capture_fixture(*, source_dir: Path, report_month: str) -> dict[str, Any]:
    from backend.app.services.candidate_financial_indicator_service import (
        candidate_financial_indicator_envelope,
    )

    base = candidate_financial_indicator_envelope(
        source_dir=str(source_dir),
        report_month=report_month,
        include_lineage=False,
        metric_id=None,
    )
    traced = candidate_financial_indicator_envelope(
        source_dir=str(source_dir),
        report_month=report_month,
        include_lineage=True,
        metric_id=None,
    )
    base_result = base["result"]
    traced_result = traced["result"]
    base_ids = [item["metric_id"] for item in base_result["metrics"]]
    traced_ids = [item["metric_id"] for item in traced_result["metrics"]]
    if base_ids != traced_ids or len(base_ids) != 186:
        raise RuntimeError("candidate fixture capture requires the same ordered 186 metrics")
    if base_result["rule_hash"] != traced_result["rule_hash"]:
        raise RuntimeError("candidate fixture capture rule hashes do not match")
    captured = {
        "capture_status": "candidate_non_formal",
        "report_month": report_month,
        "rule_version": base_result["rule_version"],
        "rule_hash": base_result["rule_hash"],
        "source_hashes": {
            item["source_kind"]: item["sha256"]
            for item in base_result["sources"]
        },
        "base_idempotency_key": base_result["idempotency_key"],
        "lineage_idempotency_key": traced_result["idempotency_key"],
        "result_meta": base["result_meta"],
        "result": base_result,
        "lineage_by_metric": {
            item["metric_id"]: item["lineage"]
            for item in traced_result["metrics"]
        },
    }
    return _sanitize_capture(captured)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--report-month", default="202606")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    fixture = capture_fixture(
        source_dir=args.source_dir.resolve(),
        report_month=args.report_month,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "report_month": fixture["report_month"],
                "rule_hash": fixture["rule_hash"],
                "source_hashes": fixture["source_hashes"],
                "metric_count": len(fixture["result"]["metrics"]),
                "lineage_metric_count": len(fixture["lineage_by_metric"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
