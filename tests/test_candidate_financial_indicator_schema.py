from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError


def _schema():
    try:
        from backend.app.schemas.candidate_financial_indicators import (
            CandidateFinancialIndicatorEnvelope,
        )
    except ModuleNotFoundError:
        pytest.fail("candidate financial-indicator schema is not implemented")
    return CandidateFinancialIndicatorEnvelope


def _envelope() -> dict[str, Any]:
    payload = {
        "result_meta": {
            "trace_id": "tr_candidate_financial_indicators_202606",
            "basis": "ledger",
            "result_kind": "ledger_pnl.candidate_financial_indicators",
            "formal_use_allowed": False,
            "amount_currency_basis": "CNX",
            "amount_currency_basis_note": "候选规则固定使用综本 CNX 口径。",
            "source_version": "sv_candidate_abc123",
            "vendor_version": "vv_none",
            "rule_version": "qdb-finance-2026-v1.0.0",
            "cache_version": "cv_candidate_financial_indicators_v1",
            "cache_key": "0" * 64,
            "quality_flag": "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": "202606",
            "resolved_report_date": "2026-06-30",
            "scenario_flag": False,
            "as_of_date": "2026-06-30",
            "date_basis": "report_month_end",
            "fallback_date": None,
            "filters_applied": {
                "report_month": "202606",
                "include_lineage": True,
                "metric_id": "income.interest.net",
            },
            "tables_used": ["综本", "年", "月", "微贷"],
            "evidence_rows": 1961,
            "next_drill": [],
            "source_surface": None,
        },
        "result": {
            "report_month": "202606",
            "report_date": "2026-06-30",
            "currency": "CNX",
            "basis": "ledger",
            "metric_status": "candidate",
            "formal_use_allowed": False,
            "calculation_status": "warning",
            "source_alignment": "mismatch",
            "source_version": "sv_candidate_abc123",
            "rule_version": "qdb-finance-2026-v1.0.0",
            "rule_hash": "7" * 64,
            "idempotency_key": "0" * 64,
            "requested_metric_id": "income.interest.net",
            "include_lineage": True,
            "promotion_readiness": {
                "readiness_contract_version": "promotion-readiness-v1",
                "readiness_evidence_key": "",
                "status": "blocked",
                "blocking_count": 5,
                "check_total": 6,
                "candidate_idempotency_key": "0" * 64,
                "formal_contract_status": "missing_contract",
                "formal_use_allowed": False,
                "owner_approval_required": True,
                "next_action": "核对当前总账与批准样本。",
                "checks": [
                    {
                        "check_id": "rule_asset",
                        "label": "规则资产与候选计算",
                        "status": "passed",
                        "blocking": False,
                        "summary": "批准规则已加载。",
                        "evidence_refs": ["qdb-finance-2026-v1.0.0"],
                        "action": "保持批准规则不变。",
                    },
                    {
                        "check_id": "source_evidence",
                        "label": "来源期间与锁定哈希",
                        "status": "blocked",
                        "blocking": True,
                        "summary": "总账来源哈希不匹配。",
                        "evidence_refs": ["source_hash.ledger"],
                        "action": "核对当前总账与批准样本。",
                    },
                    {
                        "check_id": "validation_controls",
                        "label": "控制校验",
                        "status": "blocked",
                        "blocking": True,
                        "summary": "11 / 12 项控制通过。",
                        "evidence_refs": ["rules.missing_accounts"],
                        "action": "处置未通过控制。",
                    },
                    {
                        "check_id": "manual_inputs",
                        "label": "手工调整输入",
                        "status": "blocked",
                        "blocking": True,
                        "summary": "19 项仍使用默认值。",
                        "evidence_refs": ["input.adjustment.noninterest.r010"],
                        "action": "提交批准输入快照。",
                    },
                    {
                        "check_id": "account_coverage",
                        "label": "规则科目覆盖",
                        "status": "blocked",
                        "blocking": True,
                        "summary": "存在缺失规则科目。",
                        "evidence_refs": ["ledger/l1/599"],
                        "action": "补齐来源或批准零余额证明。",
                    },
                    {
                        "check_id": "formal_contract",
                        "label": "正式契约登记",
                        "status": "blocked",
                        "blocking": True,
                        "summary": "正式契约尚未登记。",
                        "evidence_refs": ["GS-LEDGER-PNL-FIN-IND-202606-MISSING"],
                        "action": "补齐正式冻结样本。",
                    },
                ],
            },
            "sources": [
                {
                    "source_kind": "ledger",
                    "file_name": "总账对账202606.xlsx",
                    "exists": True,
                    "sha256": "2" * 64,
                    "locked_sha256": "0" * 64,
                    "locked_hash_match": False,
                    "sheets": ["综本"],
                    "periods": [
                        {
                            "evidence_id": "ledger",
                            "start": "2026-06-01",
                            "end": "2026-06-30",
                            "source_cell": "综本!A5",
                        }
                    ],
                },
                {
                    "source_kind": "daily",
                    "file_name": "日均202606.xlsx",
                    "exists": True,
                    "sha256": "4" * 64,
                    "locked_sha256": "4" * 64,
                    "locked_hash_match": True,
                    "sheets": ["年", "月", "微贷"],
                    "periods": [
                        {
                            "evidence_id": "daily_ytd",
                            "start": "2026-01-01",
                            "end": "2026-06-30",
                            "source_cell": "年!A2",
                        },
                        {
                            "evidence_id": "daily_month",
                            "start": "2026-06-01",
                            "end": "2026-06-30",
                            "source_cell": "月!A2",
                        },
                        {
                            "evidence_id": "microloan_ytd",
                            "start": "2026-01-01",
                            "end": "2026-06-30",
                            "source_cell": "微贷!A2",
                        },
                        {
                            "evidence_id": "microloan_month",
                            "start": "2026-06-01",
                            "end": "2026-06-30",
                            "source_cell": "微贷!E2",
                        },
                        {
                            "evidence_id": "microloan_ledger",
                            "start": "2026-06-01",
                            "end": "2026-06-30",
                            "source_cell": "微贷!I31",
                        },
                    ],
                },
            ],
            "summary": {
                "metric_total": 186,
                "metric_evaluated": 186,
                "metric_returned": 1,
                "ok_count": 160,
                "warning_count": 7,
                "manual_default_count": 19,
                "error_count": 0,
                "validation_total": 12,
                "validation_evaluated": 12,
                "validation_passed": 11,
                "validation_warning_failed": 1,
                "validation_error_failed": 0,
            },
            "metrics": [
                {
                    "metric_id": "income.interest.net",
                    "name": "利息净收入",
                    "category": "利息净收入",
                    "basis": "cumulative",
                    "unit": "亿元",
                    "value": "57.3617558215",
                    "status": "warning",
                    "reasons": ["dependency_manual_default"],
                    "lineage": [
                        {
                            "lineage_type": "account",
                            "source": "ledger",
                            "basis": None,
                            "level": "l1",
                            "code": "501",
                            "weight": "-1",
                            "observed": True,
                            "raw_yuan": "5736175582.15",
                            "contribution_yi": "-57.3617558215",
                            "evidence_refs": ["综本!G101"],
                        }
                    ],
                }
            ],
            "validations": [
                {
                    "validation_id": "rules.missing_accounts",
                    "severity": "warning",
                    "passed": False,
                    "message": "规则引用的部分零余额科目未在源表出现。",
                    "delta_yi": None,
                    "sample": ["ledger/l1/599"],
                }
            ],
            "gaps": [
                {
                    "gap_id": "source_hash.ledger",
                    "severity": "warning",
                    "kind": "source_hash",
                    "title": "总账来源与锁定样本不一致",
                    "detail": "本次按当前配置来源计算，结果不可冒充锁定黄金样本。",
                    "metric_ids": [],
                }
            ],
        },
    }
    validation_severity = {
        "period.same_end_date": "error",
        "period.ytd_starts_jan1": "error",
        "period.month_is_calendar_month": "error",
        "currency.cnx_only": "error",
        "ledger.balance_identity": "error",
        "ledger.duplicate_full_code": "warning",
        "rules.missing_accounts": "warning",
        "recon.company_deposit": "warning",
        "recon.retail_deposit": "warning",
        "recon.personal_loan": "warning",
        "recon.loan_interest": "warning",
        "recon.noninterest": "warning",
    }
    existing_ids = {
        item["validation_id"] for item in payload["result"]["validations"]
    }
    payload["result"]["validations"].extend(
        {
            "validation_id": validation_id,
            "severity": severity,
            "passed": True,
            "message": "校验通过。",
            "delta_yi": "0" if validation_id.startswith("recon.") else None,
            "sample": [],
        }
        for validation_id, severity in validation_severity.items()
        if validation_id not in existing_ids
    )
    _refresh_readiness_evidence_key(payload)
    return payload


def _refresh_readiness_evidence_key(payload: dict[str, Any]) -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
        build_promotion_readiness_evidence_key,
    )

    readiness = payload["result"]["promotion_readiness"]
    readiness["readiness_evidence_key"] = build_promotion_readiness_evidence_key(
        candidate_idempotency_key=readiness["candidate_idempotency_key"],
        formal_contract_status=readiness["formal_contract_status"],
        checks=[
            {
                "check_id": check["check_id"],
                "status": check["status"],
                "evidence_refs": check["evidence_refs"],
            }
            for check in readiness["checks"]
        ],
    )
    if "evidence_pack" not in readiness:
        requirements = [
            {
                "requirement_id": "source_evidence.1",
                "category": "source_evidence",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": ["source_hash.ledger"],
                "required_evidence": ["来源哈希审批记录"],
                "action": "核对当前总账与批准样本。",
            },
            {
                "requirement_id": "manual_input.1",
                "category": "manual_input",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": ["input.adjustment.noninterest.r010"],
                "required_evidence": ["期间匹配的实际值与审批证据"],
                "action": "提交批准输入快照。",
            },
            {
                "requirement_id": "account_coverage.1",
                "category": "account_coverage",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": ["ledger/l1/599"],
                "required_evidence": ["来源记录或批准零余额证明"],
                "action": "补齐来源或批准零余额证明。",
            },
            {
                "requirement_id": "formal_contract.1",
                "category": "formal_contract",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": ["GS-LEDGER-PNL-FIN-IND-202606-MISSING"],
                "required_evidence": ["正式 Excel 冻结样本与契约登记记录"],
                "action": "补齐正式冻结样本。",
            },
            {
                "requirement_id": "business_owner_approval.1",
                "category": "business_owner_approval",
                "status": "awaiting_owner_input",
                "submitted_value": None,
                "evidence_refs": [],
                "required_evidence": ["负责人决定、日期与签名"],
                "action": "提交财务与数据治理负责人复核。",
            },
        ]
        readiness["evidence_pack"] = {
            "contract_version": "candidate-promotion-evidence-v1",
            "evidence_pack_key": "",
            "report_month": payload["result"]["report_month"],
            "report_date": payload["result"]["report_date"],
            "rule_version": payload["result"]["rule_version"],
            "rule_hash": payload["result"]["rule_hash"],
            "source_version": payload["result"]["source_version"],
            "source_alignment": payload["result"]["source_alignment"],
            "candidate_idempotency_key": readiness["candidate_idempotency_key"],
            "readiness_contract_version": readiness["readiness_contract_version"],
            "readiness_evidence_key": readiness["readiness_evidence_key"],
            "metric_status": "candidate",
            "formal_use_allowed": False,
            "owner_approval_required": True,
            "contains_metric_values": False,
            "contains_formal_values": False,
            "certification_effect": "none",
            "blocking_count": readiness["blocking_count"],
            "check_total": readiness["check_total"],
            "formal_contract_status": readiness["formal_contract_status"],
            "formal_sample_id": "GS-LEDGER-PNL-FIN-IND-202606-MISSING",
            "formal_source_version": "sv_formal_financial_indicators_contract_unavailable",
            "formal_release_gate_status": None,
            "formal_metric_count": 0,
            "checks": deepcopy(readiness["checks"]),
            "owner_requirement_count": len(requirements),
            "owner_requirements": requirements,
            "outcome_status": "blocked",
        }
    pack = readiness["evidence_pack"]
    pack["candidate_idempotency_key"] = readiness["candidate_idempotency_key"]
    pack["readiness_evidence_key"] = readiness["readiness_evidence_key"]
    pack["blocking_count"] = readiness["blocking_count"]
    pack["checks"] = deepcopy(readiness["checks"])
    pack["outcome_status"] = (
        "blocked" if readiness["blocking_count"] else "awaiting_owner_approval"
    )
    pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=pack,
    )


def test_candidate_financial_indicator_schema_preserves_decimal_strings_and_boundary() -> None:
    schema = _schema()

    envelope = schema.model_validate(_envelope()).model_dump(mode="json")

    assert envelope["result_meta"]["basis"] == "ledger"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result"]["metric_status"] == "candidate"
    assert envelope["result"]["currency"] == "CNX"
    assert envelope["result"]["metrics"][0]["value"] == "57.3617558215"
    assert envelope["result"]["metrics"][0]["lineage"][0]["raw_yuan"] == "5736175582.15"


def test_candidate_financial_indicator_schema_rejects_promotion_count_drift() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["blocking_count"] = 4

    with pytest.raises(ValidationError, match="blocking_count"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_binds_promotion_to_candidate_run() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["candidate_idempotency_key"] = "9" * 64
    _refresh_readiness_evidence_key(payload)

    with pytest.raises(ValidationError, match="candidate idempotency"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_readiness_evidence_key_drift() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["readiness_evidence_key"] = "9" * 64

    with pytest.raises(ValidationError, match="readiness_evidence_key"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_evidence_pack_key_drift() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["evidence_pack"][
        "evidence_pack_key"
    ] = "9" * 64

    with pytest.raises(ValidationError, match="evidence_pack_key"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_hashes_owner_actions() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["evidence_pack"][
        "owner_requirements"
    ][0]["action"] = "tampered governance instruction"

    with pytest.raises(ValidationError, match="evidence_pack_key"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_cross_period_evidence_pack() -> None:
    payload = _envelope()
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
    )

    pack = payload["result"]["promotion_readiness"]["evidence_pack"]
    pack["report_month"] = "202605"
    pack["report_date"] = "2026-05-31"
    pack["evidence_pack_key"] = build_promotion_evidence_pack_key(evidence_pack=pack)

    with pytest.raises(ValidationError, match="bind payload report_month"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_owner_value_in_evidence_pack() -> None:
    payload = _envelope()
    payload["result"]["promotion_readiness"]["evidence_pack"][
        "owner_requirements"
    ][0]["submitted_value"] = "approved"

    with pytest.raises(ValidationError, match="submitted_value"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_binds_evidence_pack_to_readiness() -> None:
    payload = _envelope()
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
    )

    pack = payload["result"]["promotion_readiness"]["evidence_pack"]
    pack["readiness_evidence_key"] = "9" * 64
    pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=pack,
    )

    with pytest.raises(ValidationError, match="bind the readiness evidence key"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_promotion_that_contradicts_evidence() -> None:
    payload = _envelope()
    readiness = payload["result"]["promotion_readiness"]
    readiness["status"] = "review_required"
    readiness["blocking_count"] = 0
    for check in readiness["checks"]:
        check["status"] = "passed"
        check["blocking"] = False
    _refresh_readiness_evidence_key(payload)

    with pytest.raises(ValidationError, match="promotion readiness contradicts"):
        _schema().model_validate(payload)


@pytest.mark.parametrize(
    "path",
    [
        ("result", "unexpected"),
        ("result", "metrics", 0, "unexpected"),
        ("result", "sources", 0, "unexpected"),
        ("result_meta", "unexpected"),
    ],
)
def test_candidate_financial_indicator_schema_forbids_extra_fields(path: tuple[Any, ...]) -> None:
    payload = _envelope()
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_summary_count_drift() -> None:
    payload = _envelope()
    payload["result"]["summary"]["warning_count"] = 6

    with pytest.raises(ValidationError, match="metric status counts"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_validation_count_drift() -> None:
    payload = _envelope()
    payload["result"]["summary"]["validation_passed"] = 10
    payload["result"]["summary"]["validation_warning_failed"] = 2

    with pytest.raises(ValidationError, match="validation summary counts"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_duplicate_period_evidence() -> None:
    payload = _envelope()
    payload["result"]["sources"][1]["periods"].append(
        deepcopy(payload["result"]["sources"][1]["periods"][0])
    )

    with pytest.raises(ValidationError, match="six unique source period"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_duplicate_source_kind() -> None:
    payload = _envelope()
    payload["result"]["sources"].append(
        deepcopy(payload["result"]["sources"][0])
    )

    with pytest.raises(ValidationError, match="one ledger and one daily"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_report_date_month_mismatch() -> None:
    payload = _envelope()
    payload["result"]["report_date"] = "2026-05-31"

    with pytest.raises(ValidationError, match="month end"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_lineage_when_not_requested() -> None:
    payload = _envelope()
    payload["result"]["include_lineage"] = False
    payload["result_meta"]["filters_applied"]["include_lineage"] = False

    with pytest.raises(ValidationError, match="lineage"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_incoherent_source_hash_match() -> None:
    payload = _envelope()
    payload["result"]["sources"][0]["locked_hash_match"] = True

    with pytest.raises(ValidationError, match="locked_hash_match"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_wrong_filtered_metric() -> None:
    payload = _envelope()
    payload["result"]["requested_metric_id"] = "income.noninterest.total"

    with pytest.raises(ValidationError, match="requested_metric_id"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_ready_with_visible_gaps() -> None:
    payload = deepcopy(_envelope())
    payload["result"]["calculation_status"] = "ready"
    payload["result"]["source_alignment"] = "matched"
    payload["result"]["promotion_readiness"]["evidence_pack"][
        "source_alignment"
    ] = "matched"
    _refresh_readiness_evidence_key(payload)
    payload["result"]["sources"][0]["sha256"] = "0" * 64
    payload["result"]["sources"][0]["locked_hash_match"] = True

    with pytest.raises(ValidationError, match="ready"):
        _schema().model_validate(payload)


def test_candidate_financial_indicator_schema_rejects_ready_with_unlocked_sources() -> None:
    payload = deepcopy(_envelope())
    result = payload["result"]
    result["calculation_status"] = "ready"
    result["source_alignment"] = "not_applicable"
    result["promotion_readiness"]["evidence_pack"][
        "source_alignment"
    ] = "not_applicable"
    _refresh_readiness_evidence_key(payload)
    result["gaps"] = []
    for source in result["sources"]:
        source["locked_sha256"] = None
        source["locked_hash_match"] = None
    result["summary"].update(
        ok_count=186,
        warning_count=0,
        manual_default_count=0,
        error_count=0,
        validation_passed=12,
        validation_warning_failed=0,
        validation_error_failed=0,
    )
    result["metrics"][0]["status"] = "ok"
    result["metrics"][0]["reasons"] = []
    for validation in result["validations"]:
        validation["passed"] = True

    with pytest.raises(ValidationError, match="locked source hashes"):
        _schema().model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_currency_basis_note", None),
        ("vendor_version", "vv_other"),
        ("quality_flag", "stale"),
        ("vendor_status", "vendor_unavailable"),
        ("fallback_mode", "latest_snapshot"),
        ("requested_report_date", None),
        ("resolved_report_date", None),
        ("scenario_flag", True),
        ("as_of_date", None),
        ("fallback_date", "2026-05-31"),
        ("evidence_rows", None),
        ("source_surface", "formal_pnl"),
    ],
)
def test_candidate_financial_indicator_schema_rejects_impossible_result_meta_states(
    field: str,
    value: object,
) -> None:
    payload = _envelope()
    payload["result_meta"][field] = value

    with pytest.raises(ValidationError):
        _schema().model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requested_report_date", "202605"),
        ("resolved_report_date", "2026-06-29"),
        ("as_of_date", "2026-06-29"),
    ],
)
def test_candidate_financial_indicator_schema_rejects_result_meta_date_drift(
    field: str,
    value: str,
) -> None:
    payload = _envelope()
    payload["result_meta"][field] = value

    with pytest.raises(ValidationError, match="result_meta dates"):
        _schema().model_validate(payload)


def test_revalidation_request_accepts_only_strict_evidenced_decimal_overrides() -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        CandidateFinancialIndicatorRevalidationRequest,
    )

    request = CandidateFinancialIndicatorRevalidationRequest.model_validate(
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {
                "input.adjustment.noninterest.r010": {
                    "value_yi": "0.125",
                    "submitted_evidence_refs": ["voucher:202606:10"],
                }
            },
        }
    )

    assert request.manual_overrides["input.adjustment.noninterest.r010"].value_yi == "0.125"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {},
            "approved": True,
        },
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {
                "input.adjustment.noninterest.r010": {
                    "value_yi": "NaN",
                    "submitted_evidence_refs": ["voucher:1"],
                }
            },
        },
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {
                "input.adjustment.noninterest.r010": {
                    "value_yi": True,
                    "submitted_evidence_refs": ["voucher:1"],
                }
            },
        },
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {
                "input.adjustment.noninterest.r010": {
                    "value_yi": "0",
                    "submitted_evidence_refs": [],
                }
            },
        },
        {
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {
                "input.adjustment.noninterest.r010": {
                    "value_yi": "0",
                    "submitted_evidence_refs": ["   "],
                }
            },
        },
    ],
)
def test_revalidation_request_rejects_extra_non_decimal_and_zero_proof(
    payload: dict[str, Any],
) -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        CandidateFinancialIndicatorRevalidationRequest,
    )

    with pytest.raises(ValidationError):
        CandidateFinancialIndicatorRevalidationRequest.model_validate(payload)
