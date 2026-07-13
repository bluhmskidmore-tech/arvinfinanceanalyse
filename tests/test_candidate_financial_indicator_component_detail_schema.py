from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.app.schemas.candidate_financial_indicator_component_detail import (
    CandidateFinancialIndicatorComponentDetailEnvelope,
)


def _source_period(month: str, sha: str, lock_status: str) -> dict[str, object]:
    month_ends = {
        "202606": "2026-06-30",
        "202605": "2026-05-31",
        "202604": "2026-04-30",
    }
    return {
        "month": month,
        "report_date": month_ends[month],
        "ledger_file_name": f"总账对账{month}.xlsx",
        "ledger_sha256": sha,
        "locked_sha256": sha if lock_status == "locked_match" else None,
        "lock_status": lock_status,
    }


def _payload() -> dict[str, object]:
    sources = [
        _source_period("202606", "1" * 64, "locked_match"),
        _source_period("202605", "2" * 64, "unlocked"),
        _source_period("202604", "3" * 64, "unlocked"),
    ]
    endings = ["-100000000", "0", "200000000"]
    locators = [(1041, "A1041", "G1041"), (1040, "A1040", "G1040"), (1039, "A1039", "G1039")]
    evidence = []
    for source, ending, (row, account_cell, ending_cell) in zip(
        sources,
        endings,
        locators,
        strict=True,
    ):
        evidence.append(
            {
                **source,
                "sheet": "综本",
                "row": row,
                "account_code_cell": account_cell,
                "ending_cell": ending_cell,
                "ending_yuan": ending,
            }
        )
    return {
        "contract_version": "candidate-financial-indicator-component-detail-v1",
        "analysis_kind": "accounting_component_account_detail",
        "report_month": "202606",
        "report_date": "2026-06-30",
        "comparison_month": "202605",
        "two_month_prior": "202604",
        "metric_id": "income.interest.investment",
        "metric_name": "金融投资利息收入",
        "formula_weight": 1,
        "currency": "CNX",
        "basis": "calendar_month_from_cumulative",
        "method": "finance_metric_account_contribution",
        "unit": "亿元",
        "status": "available",
        "quality_status": "degraded_candidate",
        "foot_status": "passed",
        "formal_use_allowed": False,
        "certification_effect": "none",
        "driver_status": "unclear",
        "rule_version": "qdb-finance-2026-v1.0.1",
        "rule_hash": "4" * 64,
        "parent_idempotency_key": "5" * 64,
        "idempotency_key": "6" * 64,
        "source_periods": sources,
        "parent_current_value_yi": "1",
        "parent_previous_value_yi": "2",
        "parent_component_delta_yi": "-1",
        "parent_contribution_to_net_delta_yi": "-1",
        "account_current_total_yi": "1",
        "account_previous_total_yi": "2",
        "account_component_delta_total_yi": "-1",
        "account_contribution_total_yi": "-1",
        "current_reconciliation_yi": "0",
        "previous_reconciliation_yi": "0",
        "component_delta_reconciliation_yi": "0",
        "contribution_reconciliation_yi": "0",
        "reasons": [],
        "rows": [
            {
                "row_status": "contributing",
                "account_code": "51402010003",
                "account_name": "其他公允价值变动计入损益的金融资产利息收入",
                "currency": "CNX",
                "effective_component_weight": "-1",
                "effective_net_weight": "-1",
                "matched_terms": [
                    {
                        "source": "ledger",
                        "level": "l1",
                        "code": "514",
                        "weight": "-1",
                    }
                ],
                "current_ending_yuan": endings[0],
                "previous_ending_yuan": endings[1],
                "two_month_prior_ending_yuan": endings[2],
                "current_value_yi": "1",
                "previous_value_yi": "2",
                "component_delta_yi": "-1",
                "contribution_to_net_delta_yi": "-1",
                "source_evidence": evidence,
            }
        ],
    }


def test_component_detail_schema_accepts_exact_available_contract() -> None:
    model = CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(_payload())

    assert model.status == "available"
    assert model.rows[0].source_evidence[0].ending_cell == "G1041"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload.__setitem__("account_component_delta_total_yi", "-2"),
            "account totals",
        ),
        (
            lambda payload: payload["rows"][0].__setitem__("effective_net_weight", "1"),
            "effective net weight",
        ),
        (
            lambda payload: payload["rows"][0]["source_evidence"][0].__setitem__(
                "ledger_sha256", "9" * 64
            ),
            "source evidence",
        ),
        (
            lambda payload: payload["rows"][0].__setitem__("current_value_yi", "9"),
            "calendar-month",
        ),
    ],
)
def test_component_detail_schema_rejects_cross_field_drift(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(payload)


def test_component_detail_schema_rejects_extra_fields() -> None:
    payload = _payload()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(payload)


def test_component_detail_schema_accepts_empty_stale_parent_and_rejects_explanation() -> None:
    stale = _payload()
    stale.update(
        {
            "status": "stale_parent",
            "quality_status": "not_evaluable",
            "foot_status": "not_evaluable",
            "parent_current_value_yi": None,
            "parent_previous_value_yi": None,
            "parent_component_delta_yi": None,
            "parent_contribution_to_net_delta_yi": None,
            "account_current_total_yi": None,
            "account_previous_total_yi": None,
            "account_component_delta_total_yi": None,
            "account_contribution_total_yi": None,
            "current_reconciliation_yi": None,
            "previous_reconciliation_yi": None,
            "component_delta_reconciliation_yi": None,
            "contribution_reconciliation_yi": None,
            "reasons": ["parent_idempotency_key_mismatch"],
            "rows": [],
        }
    )
    CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(stale)

    drift = deepcopy(stale)
    drift["rows"] = _payload()["rows"]
    with pytest.raises(ValidationError, match="stale parent"):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(drift)


def test_component_detail_schema_failed_foot_allows_only_reconciliation_diagnostics() -> None:
    failed = _payload()
    failed.update(
        {
            "status": "not_evaluable",
            "quality_status": "not_evaluable",
            "foot_status": "failed",
            "parent_current_value_yi": "2",
            "parent_previous_value_yi": "2",
            "parent_component_delta_yi": "0",
            "parent_contribution_to_net_delta_yi": "0",
            "account_current_total_yi": None,
            "account_previous_total_yi": None,
            "account_component_delta_total_yi": None,
            "account_contribution_total_yi": None,
            "current_reconciliation_yi": "1",
            "previous_reconciliation_yi": "0",
            "component_delta_reconciliation_yi": "1",
            "contribution_reconciliation_yi": "1",
            "reasons": ["component_account_reconciliation_failed"],
            "rows": [],
        }
    )
    CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(failed)

    leaked_rows = deepcopy(failed)
    leaked_rows["rows"] = _payload()["rows"]
    with pytest.raises(ValidationError, match="failed foot must hide account explanation"):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(leaked_rows)

    leaked_totals = deepcopy(failed)
    leaked_totals["account_current_total_yi"] = "1"
    with pytest.raises(ValidationError, match="failed foot must hide account explanation"):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(leaked_totals)


def test_component_detail_schema_rejects_passed_foot_for_not_evaluable_status() -> None:
    payload = _payload()
    payload["status"] = "not_evaluable"

    with pytest.raises(ValidationError, match="passed foot requires available status"):
        CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(payload)
