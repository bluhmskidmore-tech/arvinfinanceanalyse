from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from backend.app.core_finance.decimal_utils import to_decimal_strict
from backend.app.core_finance.formal_financial_indicators import (
    build_formal_financial_indicator_contract,
)

RULE_VERSION = "rv_formal_financial_indicator_rule_checks_v1"
BASIS = "formal_financial_indicator_rule_checks"
RATIO_TOLERANCE = Decimal("0.0001")
ADDITIVITY_TOLERANCE = Decimal("0.0001")
_QUANT_10DP = Decimal("0.0000000001")
_RESIDUAL_NOTE = "Frozen sample residual requires later governed-source explanation."
_ADDITIVITY_MISSING_NOTE = (
    "Frozen additivity components are unavailable for this report month."
)

# The rule-check sample depends on decomposed rows that are intentionally not
# exposed by the formal-indicator source contract itself.
_RULE_CHECK_COMPONENT_FIXTURES: dict[str, dict[str, str]] = {
    "202603": {
        "subsidiary.jinzu.operating_revenue": "1.7633073047",
        "subsidiary.licai.operating_revenue": "1.1233358159",
        "subsidiary.village_bank.operating_revenue": "0.0321492748",
        "parent.business_admin_expense": "9.2856413190",
        "subsidiary.jinzu.business_admin_expense": "0.1529288536",
        "subsidiary.licai.business_admin_expense": "0.2508577245",
        "subsidiary.village_bank.business_admin_expense": "0.0470170997",
        "parent.impairment_loss": "13.8357855232",
        "subsidiary.impairment_loss": "0.0378967223",
        "subsidiary.jinzu.net_profit": "1.1775187483",
        "subsidiary.licai.net_profit": "0.6390026754",
        "subsidiary.village_bank.net_profit": "-0.0149530904",
        "asset_quality.writeoff_total": "3.0847286675",
        "asset_quality.loan_writeoff": "3.0497046763",
        "asset_quality.other_asset_writeoff": "0.0350239912",
        "asset_quality.recovery_after_writeoff_total": "0.5154111414",
        "asset_quality.loan_recovery_after_writeoff": "0.5143695576",
        "asset_quality.other_asset_recovery_after_writeoff": "0.0010415838",
        "asset_quality.provision_balance_total": "192.4598240500",
        "asset_quality.other_asset_provision_balance": "69.7302242330",
    }
}


def build_formal_financial_indicator_rule_checks(*, report_month: str) -> dict[str, Any]:
    contract = build_formal_financial_indicator_contract(report_month=report_month)

    if contract.get("sample_status") == "missing_contract":
        return _missing_contract_result(contract)

    metrics = _build_rule_metric_lookup(contract)

    ratio_recomputation = [
        _ratio_check(
            check_key="group.cost_income_ratio",
            metric_name="Cost-income ratio",
            numerator_key="group.business_admin_expense",
            denominator_key="group.operating_revenue",
            contract_metric_key="group.cost_income_ratio",
            metrics=metrics,
        ),
        _ratio_check(
            check_key="asset_quality.npl_ratio",
            metric_name="NPL ratio",
            numerator_key="asset_quality.npl_balance",
            denominator_key="asset_quality.loan_balance",
            contract_metric_key="asset_quality.npl_ratio",
            metrics=metrics,
        ),
        _ratio_check(
            check_key="asset_quality.loan_loss_reserve_ratio",
            metric_name="Loan loss reserve ratio",
            numerator_key="asset_quality.loan_loss_provision_balance",
            denominator_key="asset_quality.loan_balance",
            contract_metric_key="asset_quality.loan_loss_reserve_ratio",
            metrics=metrics,
        ),
        _ratio_check(
            check_key="asset_quality.provision_coverage_ratio",
            metric_name="Provision coverage ratio",
            numerator_key="asset_quality.loan_loss_provision_balance",
            denominator_key="asset_quality.npl_balance",
            contract_metric_key="asset_quality.provision_coverage_ratio",
            metrics=metrics,
        ),
        _insufficient_ratio_check(
            check_key="group.roa",
            metric_name="Group ROA",
            contract_metric_key="group.roa",
            metrics=metrics,
            missing_inputs=["period-start total assets"],
            note="ROA needs an average-balance denominator that is not frozen in the contract.",
        ),
        _insufficient_ratio_check(
            check_key="group.roe",
            metric_name="Group ROE",
            contract_metric_key="group.roe",
            metrics=metrics,
            missing_inputs=["period-start attributable equity", "preferred dividend"],
            note="ROE needs upstream inputs that are not frozen in the contract.",
        ),
    ]

    additivity_checks = [
        _additivity_check(
            check_key="group.operating_revenue",
            metric_name="Group operating revenue",
            total_key="group.operating_revenue",
            component_keys=(
                "parent.operating_revenue.consolidated_basis",
                "subsidiary.jinzu.operating_revenue",
                "subsidiary.licai.operating_revenue",
                "subsidiary.village_bank.operating_revenue",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="group.business_admin_expense",
            metric_name="Group business/admin expense",
            total_key="group.business_admin_expense",
            component_keys=(
                "parent.business_admin_expense",
                "subsidiary.jinzu.business_admin_expense",
                "subsidiary.licai.business_admin_expense",
                "subsidiary.village_bank.business_admin_expense",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="group.impairment_loss",
            metric_name="Group impairment loss",
            total_key="group.impairment_loss",
            component_keys=(
                "parent.impairment_loss",
                "subsidiary.impairment_loss",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="group.net_profit",
            metric_name="Group net profit",
            total_key="group.net_profit",
            component_keys=(
                "parent.net_profit",
                "subsidiary.jinzu.net_profit",
                "subsidiary.licai.net_profit",
                "subsidiary.village_bank.net_profit",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="asset_quality.writeoff_total",
            metric_name="Writeoff total",
            total_key="asset_quality.writeoff_total",
            component_keys=(
                "asset_quality.loan_writeoff",
                "asset_quality.other_asset_writeoff",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="asset_quality.recovery_after_writeoff_total",
            metric_name="Recovery after writeoff total",
            total_key="asset_quality.recovery_after_writeoff_total",
            component_keys=(
                "asset_quality.loan_recovery_after_writeoff",
                "asset_quality.other_asset_recovery_after_writeoff",
            ),
            metrics=metrics,
        ),
        _additivity_check(
            check_key="asset_quality.provision_balance_total",
            metric_name="Provision balance total",
            total_key="asset_quality.provision_balance_total",
            component_keys=(
                "asset_quality.loan_loss_provision_balance",
                "asset_quality.other_asset_provision_balance",
            ),
            metrics=metrics,
        ),
    ]

    group_equals_parent_plus_subsidiaries_keys = (
        "group.operating_revenue",
        "group.business_admin_expense",
        "group.impairment_loss",
        "group.net_profit",
    )
    additivity_by_key = {item["check_key"]: item for item in additivity_checks}
    arrangement_rules = [
        {
            "rule_key": "rule_expense_growth_le_revenue_growth",
            "rule_name": "Expense growth <= revenue growth",
            "source_ref": "B57",
            "status": "insufficient_inputs",
            "missing_inputs": ["2025 comparable revenue", "2025 comparable expense"],
            "note": "Prior-period frozen values are not registered in this contract.",
        },
        _rule_npl_ratio_target(report_month=str(contract["report_month"]), metrics=metrics),
        {
            "rule_key": "rule_provision_ratios_not_below_year_start",
            "rule_name": "Provision ratios not below year-start",
            "source_ref": "B59",
            "status": "insufficient_inputs",
            "missing_inputs": [
                "2025 year-end loan loss reserve ratio",
                "2025 year-end provision coverage ratio",
                "prior quarter loan loss reserve ratio",
                "prior quarter provision coverage ratio",
            ],
            "note": "Year-start and prior-quarter comparison points are not registered.",
        },
        {
            "rule_key": "rule_tax_exempt_income_assumption",
            "rule_name": "Tax-exempt income assumption",
            "source_ref": "B60",
            "status": "informational",
            "assumption_value": "28",
            "assumption_unit": "亿元",
            "note": "Management assumption only; not a recomputable rule check.",
        },
        {
            "rule_key": "rule_group_equals_parent_plus_subsidiaries",
            "rule_name": "Group equals parent plus subsidiaries",
            "source_ref": "B61-B62",
            "status": "summary",
            "referenced_additivity_check_keys": list(group_equals_parent_plus_subsidiaries_keys),
            "exact_count": sum(
                1
                for key in group_equals_parent_plus_subsidiaries_keys
                if additivity_by_key[key]["status"] == "exact"
            ),
            "residual_present_count": sum(
                1
                for key in group_equals_parent_plus_subsidiaries_keys
                if additivity_by_key[key]["status"] == "residual_present"
            ),
            "note": "Residuals reflect frozen-sample consolidation adjustments, not auto-failures.",
        },
    ]

    summary = {
        "ratio_recomputation": _status_counts(
            ratio_recomputation, ("matched", "mismatch", "insufficient_inputs")
        ),
        "additivity_checks": _status_counts(
            additivity_checks, ("exact", "residual_present")
        ),
        "arrangement_rules": _status_counts(
            arrangement_rules,
            ("pass", "fail", "insufficient_inputs", "informational", "summary"),
        ),
        "total_checks": len(ratio_recomputation) + len(additivity_checks) + len(arrangement_rules),
    }

    return {
        "report_month": contract["report_month"],
        "report_date": contract["report_date"],
        "basis": BASIS,
        "formal_use_allowed": False,
        "sample_status": contract["sample_status"],
        "source_version": contract["source_version"],
        "rule_version": RULE_VERSION,
        "contract_note": (
            "This result validates the frozen formal-indicator sample only. "
            "It does not create new formal values."
        ),
        "ratio_recomputation": ratio_recomputation,
        "additivity_checks": additivity_checks,
        "arrangement_rules": arrangement_rules,
        "summary": summary,
    }


def _missing_contract_result(contract: dict[str, Any]) -> dict[str, Any]:
    empty_summary = {
        "ratio_recomputation": {"matched": 0, "mismatch": 0, "insufficient_inputs": 0, "total": 0},
        "additivity_checks": {"exact": 0, "residual_present": 0, "total": 0},
        "arrangement_rules": {
            "pass": 0,
            "fail": 0,
            "insufficient_inputs": 0,
            "informational": 0,
            "summary": 0,
            "total": 0,
        },
        "total_checks": 0,
    }
    return {
        "report_month": contract["report_month"],
        "report_date": contract["report_date"],
        "basis": BASIS,
        "formal_use_allowed": False,
        "sample_status": "missing_contract",
        "source_version": contract["source_version"],
        "rule_version": RULE_VERSION,
        "contract_note": (
            "No frozen formal-indicator contract is registered for this report month, "
            "so rule-check evaluation cannot run."
        ),
        "ratio_recomputation": [],
        "additivity_checks": [],
        "arrangement_rules": [],
        "summary": empty_summary,
        "remediation": contract["remediation"],
    }


def _build_rule_metric_lookup(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = {str(metric["metric_key"]): metric for metric in contract["metrics"]}
    for metric_key, excel_value in _RULE_CHECK_COMPONENT_FIXTURES.get(
        str(contract["report_month"]),
        {},
    ).items():
        metrics.setdefault(metric_key, {"metric_key": metric_key, "excel_value": excel_value})
    return metrics


def _ratio_check(
    *,
    check_key: str,
    metric_name: str,
    numerator_key: str,
    denominator_key: str,
    contract_metric_key: str,
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    numerator = to_decimal_strict(metrics[numerator_key]["excel_value"])
    denominator = to_decimal_strict(metrics[denominator_key]["excel_value"])
    contract_value = to_decimal_strict(metrics[contract_metric_key]["excel_value"])
    recomputed = (numerator / denominator * Decimal("100")).quantize(
        _QUANT_10DP, rounding=ROUND_HALF_UP
    )
    diff = recomputed - contract_value
    status = "matched" if abs(diff) <= RATIO_TOLERANCE else "mismatch"
    return {
        "check_key": check_key,
        "metric_name": metric_name,
        "formula": f"{numerator_key} / {denominator_key} 脳 100",
        "numerator_metric_key": numerator_key,
        "numerator_value": str(numerator),
        "denominator_metric_key": denominator_key,
        "denominator_value": str(denominator),
        "recomputed_value": str(recomputed),
        "contract_metric_key": contract_metric_key,
        "contract_value": str(contract_value),
        "diff": str(diff),
        "tolerance": str(RATIO_TOLERANCE),
        "unit": "%",
        "status": status,
    }


def _insufficient_ratio_check(
    *,
    check_key: str,
    metric_name: str,
    contract_metric_key: str,
    metrics: dict[str, dict[str, Any]],
    missing_inputs: list[str],
    note: str,
) -> dict[str, Any]:
    contract_value = to_decimal_strict(metrics[contract_metric_key]["excel_value"])
    return {
        "check_key": check_key,
        "metric_name": metric_name,
        "contract_metric_key": contract_metric_key,
        "contract_value": str(contract_value),
        "unit": "%",
        "status": "insufficient_inputs",
        "missing_inputs": list(missing_inputs),
        "note": note,
    }


def _additivity_check(
    *,
    check_key: str,
    metric_name: str,
    total_key: str,
    component_keys: tuple[str, ...],
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing_inputs = [
        metric_key
        for metric_key in (total_key, *component_keys)
        if metric_key not in metrics
    ]
    if missing_inputs:
        return {
            "check_key": check_key,
            "metric_name": metric_name,
            "total_metric_key": total_key,
            "unit": "亿元",
            "status": "insufficient_inputs",
            "missing_inputs": missing_inputs,
            "note": _ADDITIVITY_MISSING_NOTE,
        }

    total = to_decimal_strict(metrics[total_key]["excel_value"])
    component_values = [to_decimal_strict(metrics[key]["excel_value"]) for key in component_keys]
    components_sum = sum(component_values, Decimal("0"))
    residual = total - components_sum
    status = "exact" if abs(residual) <= ADDITIVITY_TOLERANCE else "residual_present"
    result: dict[str, Any] = {
        "check_key": check_key,
        "metric_name": metric_name,
        "total_metric_key": total_key,
        "total_value": str(total),
        "components": [
            {"metric_key": key, "value": str(value)}
            for key, value in zip(component_keys, component_values)
        ],
        "components_sum": str(components_sum),
        "residual": str(residual),
        "unit": "亿元",
        "status": status,
    }
    if status == "residual_present":
        result["note"] = _RESIDUAL_NOTE
    return result


def _rule_npl_ratio_target(*, report_month: str, metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    is_q1_end = len(report_month) == 6 and report_month[4:6] == "03"
    target_value = Decimal("1.21") if is_q1_end else Decimal("1.20")
    actual_value = to_decimal_strict(metrics["asset_quality.npl_ratio"]["excel_value"])
    status = "pass" if actual_value <= target_value else "fail"
    return {
        "rule_key": "rule_npl_ratio_target",
        "rule_name": "NPL ratio threshold",
        "source_ref": "B58",
        "quarter_end_type": "一季末" if is_q1_end else "非一季末",
        "actual_value": str(actual_value),
        "target_value": str(target_value),
        "comparator": "actual_value <= target_value",
        "unit": "%",
        "status": status,
    }


def _status_counts(items: list[dict[str, Any]], statuses: tuple[str, ...]) -> dict[str, int]:
    counts = {status: 0 for status in statuses}
    for item in items:
        item_status = str(item["status"])
        counts[item_status] = counts.get(item_status, 0) + 1
    counts["total"] = len(items)
    return counts
