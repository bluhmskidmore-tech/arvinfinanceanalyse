from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.app.schemas.candidate_financial_indicator_period_comparison import (
    CandidateFinancialIndicatorPeriodComparisonEnvelope,
)


def _payload() -> dict[str, object]:
    ids = [
        "income.interest.net",
        "income.noninterest.total",
        "income.operating.mother_bank",
        "balance.deposit.corporate.total::point",
        "balance.deposit.retail.total::point",
        "balance.loan.corporate.total::point",
        "balance.loan.retail.total::point",
    ]
    metrics = []
    for index, metric_id in enumerate(ids):
        cumulative = index < 3
        comparable = metric_id not in {
            "income.noninterest.total",
            "income.operating.mother_bank",
        }
        metrics.append(
            {
                "metric_id": metric_id,
                "metric_name": metric_id,
                "basis": "calendar_month_from_cumulative" if cumulative else "month_end_point",
                "method": "finance_metric_cumulative_mom" if cumulative else "finance_metric_point_to_point",
                "unit": "亿元",
                "comparison_status": "comparable" if comparable else "not_comparable",
                "current_metric_status": "ok" if comparable else "warning",
                "previous_metric_status": "ok" if comparable else "warning",
                "two_month_prior_metric_status": (
                    "ok" if comparable else "warning"
                )
                if cumulative
                else None,
                "current_value_yi": "3" if comparable else None,
                "previous_value_yi": "2" if comparable else None,
                "current_source_value_yi": "10",
                "previous_source_value_yi": "7",
                "two_month_prior_source_value_yi": "5" if cumulative else None,
                "delta_yi": "1" if comparable else None,
                "change_rate": "0.5" if comparable else None,
                "rate_reason": None if comparable else "metric_status_not_ok",
                "reasons": [] if comparable else ["warning source metric"],
                "driver_status": "unclear",
                "quality_status": "degraded_candidate" if comparable else "not_comparable",
            }
        )
    return {
        "contract_version": "candidate-financial-indicator-period-comparison-v1",
        "report_month": "202606",
        "report_date": "2026-06-30",
        "comparison_month": "202605",
        "two_month_prior": "202604",
        "comparison_scope": "ledger_only_key_metrics",
        "full_scope_status": "unavailable",
        "full_scope_reason_code": "missing_required_sheet",
        "full_scope_detail": "上期完整六期间重放缺少必需工作表，未用于全量跨期比较。",
        "full_scope_gaps": [
            {
                "reason_code": "missing_required_sheet",
                "source_kind": "daily",
                "month": "202605",
                "required_sheet": "微贷",
            }
        ],
        "overall_status": "partial",
        "metric_status": "candidate",
        "formal_use_allowed": False,
        "certification_effect": "none",
        "driver_status": "unclear",
        "rule_version": "qdb-finance-2026-v1.0.1",
        "rule_hash": "a" * 64,
        "idempotency_key": "b" * 64,
        "source_periods": [
            {
                "month": month,
                "report_date": report_date,
                "ledger_file_name": f"总账对账{month}.xlsx",
                "ledger_sha256": str(index) * 64,
                "locked_sha256": None,
                "lock_status": "unlocked",
            }
            for index, (month, report_date) in enumerate(
                (
                    ("202606", "2026-06-30"),
                    ("202605", "2026-05-31"),
                    ("202604", "2026-04-30"),
                ),
                start=1,
            )
        ],
        "metrics": metrics,
    }


def test_period_comparison_schema_serializes_decimal_fields_as_strings() -> None:
    envelope = CandidateFinancialIndicatorPeriodComparisonEnvelope.model_validate(_payload())

    dumped = envelope.model_dump(mode="json")

    assert dumped["metrics"][0]["current_value_yi"] == "3"
    assert dumped["metrics"][0]["change_rate"] == "0.5"


@pytest.mark.parametrize("mutation", ["extra", "order", "basis", "null_incoherent"])
def test_period_comparison_schema_rejects_contract_drift(mutation: str) -> None:
    payload = deepcopy(_payload())
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    if mutation == "extra":
        payload["anomaly"] = True
    elif mutation == "order":
        metrics[0], metrics[1] = metrics[1], metrics[0]
    elif mutation == "basis":
        metrics[0]["basis"] = "month_end_point"
    else:
        metrics[1]["delta_yi"] = "1"

    with pytest.raises(ValidationError):
        CandidateFinancialIndicatorPeriodComparisonEnvelope.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    ["all_locked_but_degraded", "unlocked_but_standard", "locked_mismatch"],
)
def test_period_comparison_schema_binds_source_locks_to_metric_quality(
    mutation: str,
) -> None:
    payload = deepcopy(_payload())
    source_periods = payload["source_periods"]
    metrics = payload["metrics"]
    assert isinstance(source_periods, list)
    assert isinstance(metrics, list)
    if mutation == "all_locked_but_degraded":
        for source in source_periods:
            source["locked_sha256"] = source["ledger_sha256"]
            source["lock_status"] = "locked_match"
    elif mutation == "unlocked_but_standard":
        for metric in metrics:
            if metric["comparison_status"] == "comparable":
                metric["quality_status"] = "standard_candidate"
    else:
        source_periods[0]["locked_sha256"] = "f" * 64
        source_periods[0]["lock_status"] = "locked_mismatch"

    with pytest.raises(ValidationError):
        CandidateFinancialIndicatorPeriodComparisonEnvelope.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "current_source_missing",
        "previous_source_missing",
        "cumulative_two_prior_source_missing",
        "point_two_prior_source_present",
    ],
)
def test_period_comparison_schema_rejects_incoherent_source_values(
    mutation: str,
) -> None:
    payload = deepcopy(_payload())
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    if mutation == "current_source_missing":
        metrics[0]["current_source_value_yi"] = None
    elif mutation == "previous_source_missing":
        metrics[0]["previous_source_value_yi"] = None
    elif mutation == "cumulative_two_prior_source_missing":
        metrics[0]["two_month_prior_source_value_yi"] = None
    else:
        metrics[3]["two_month_prior_source_value_yi"] = "1"

    with pytest.raises(ValidationError):
        CandidateFinancialIndicatorPeriodComparisonEnvelope.model_validate(payload)
