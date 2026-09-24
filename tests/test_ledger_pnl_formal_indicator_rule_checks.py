from __future__ import annotations

from typing import Any

from tests.helpers import load_module


def _load_rules_module():
    return load_module(
        "backend.app.core_finance.formal_financial_indicator_rules",
        "backend/app/core_finance/formal_financial_indicator_rules.py",
    )


def _load_service_module():
    return load_module(
        "backend.app.services.ledger_pnl_service",
        "backend/app/services/ledger_pnl_service.py",
    )


def _by_check_key(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["check_key"]): item for item in items}


def _by_rule_key(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["rule_key"]): item for item in items}


def _assert_no_float(value: Any, path: str = "$") -> None:
    assert not isinstance(value, float), f"float leaked at {path}: {value!r}"
    if isinstance(value, dict):
        for key, sub_value in value.items():
            _assert_no_float(sub_value, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, sub_value in enumerate(value):
            _assert_no_float(sub_value, f"{path}[{idx}]")


def test_202603_ratio_recomputation_all_matched():
    module = _load_rules_module()
    result = module.build_formal_financial_indicator_rule_checks(report_month="202603")

    ratios = _by_check_key(result["ratio_recomputation"])
    for check_key in (
        "group.cost_income_ratio",
        "asset_quality.npl_ratio",
        "asset_quality.loan_loss_reserve_ratio",
        "asset_quality.provision_coverage_ratio",
    ):
        assert ratios[check_key]["status"] == "matched", check_key
        assert ratios[check_key]["tolerance"] == "0.0001"

    assert ratios["group.roa"]["status"] == "insufficient_inputs"
    assert ratios["group.roa"]["missing_inputs"]
    assert ratios["group.roe"]["status"] == "insufficient_inputs"
    assert ratios["group.roe"]["missing_inputs"]


def test_202603_additivity_checks_residuals_and_exact_matches():
    module = _load_rules_module()
    result = module.build_formal_financial_indicator_rule_checks(report_month="202603")

    additivity = _by_check_key(result["additivity_checks"])

    residual_present_expected = {
        "group.operating_revenue": "-0.0050816208",
        "group.business_admin_expense": "-0.0029122646",
        "group.impairment_loss": "0.0057448129",
        "group.net_profit": "-0.0003055804",
    }
    for check_key, expected_residual in residual_present_expected.items():
        check = additivity[check_key]
        assert check["status"] == "residual_present", check_key
        assert check["residual"] == expected_residual, check_key
        assert check["note"]

    exact_expected = (
        "asset_quality.writeoff_total",
        "asset_quality.recovery_after_writeoff_total",
        "asset_quality.provision_balance_total",
    )
    for check_key in exact_expected:
        check = additivity[check_key]
        assert check["status"] == "exact", check_key
        from decimal import Decimal

        assert Decimal(check["residual"]) == Decimal("0"), check_key


def test_202603_arrangement_rules_cover_all_five():
    module = _load_rules_module()
    result = module.build_formal_financial_indicator_rule_checks(report_month="202603")

    rules = _by_rule_key(result["arrangement_rules"])
    assert set(rules.keys()) == {
        "rule_expense_growth_le_revenue_growth",
        "rule_npl_ratio_target",
        "rule_provision_ratios_not_below_year_start",
        "rule_tax_exempt_income_assumption",
        "rule_group_equals_parent_plus_subsidiaries",
    }

    assert rules["rule_expense_growth_le_revenue_growth"]["status"] == "insufficient_inputs"
    assert rules["rule_expense_growth_le_revenue_growth"]["missing_inputs"]

    npl_rule = rules["rule_npl_ratio_target"]
    assert npl_rule["status"] == "pass"
    assert npl_rule["actual_value"] == "0.9575326965"
    assert npl_rule["target_value"] == "1.21"
    assert npl_rule["quarter_end_type"] == "一季末"

    assert rules["rule_provision_ratios_not_below_year_start"]["status"] == "insufficient_inputs"
    assert rules["rule_provision_ratios_not_below_year_start"]["missing_inputs"]

    assert rules["rule_tax_exempt_income_assumption"]["status"] == "informational"

    summary_rule = rules["rule_group_equals_parent_plus_subsidiaries"]
    assert summary_rule["status"] == "summary"
    assert summary_rule["exact_count"] == 0
    assert summary_rule["residual_present_count"] == 4


def test_202603_summary_status_counts():
    module = _load_rules_module()
    result = module.build_formal_financial_indicator_rule_checks(report_month="202603")

    summary = result["summary"]
    assert summary["ratio_recomputation"] == {
        "matched": 4,
        "mismatch": 0,
        "insufficient_inputs": 2,
        "total": 6,
    }
    assert summary["additivity_checks"] == {
        "exact": 3,
        "residual_present": 4,
        "total": 7,
    }
    assert summary["arrangement_rules"] == {
        "pass": 1,
        "fail": 0,
        "insufficient_inputs": 2,
        "informational": 1,
        "summary": 1,
        "total": 5,
    }
    assert summary["total_checks"] == 18


def test_202603_result_has_no_float_values():
    module = _load_rules_module()
    result = module.build_formal_financial_indicator_rule_checks(report_month="202603")
    _assert_no_float(result)


def test_unregistered_month_returns_missing_contract_without_raising():
    module = _load_rules_module()

    result = module.build_formal_financial_indicator_rule_checks(report_month="202606")

    assert result["sample_status"] == "missing_contract"
    assert result["report_month"] == "202606"
    assert result["formal_use_allowed"] is False
    assert result["ratio_recomputation"] == []
    assert result["additivity_checks"] == []
    assert result["arrangement_rules"] == []
    assert result["summary"]["total_checks"] == 0
    assert result["remediation"]["required"] is True
    assert result["remediation"]["registration_target"] == (
        "backend/app/core_finance/formal_financial_indicators.py"
    )
    _assert_no_float(result)


def test_ledger_pnl_service_envelope_for_202603():
    service = _load_service_module()

    envelope = service.ledger_pnl_formal_indicator_rule_checks_envelope(report_month="202603")

    assert envelope["result_meta"]["basis"] == "ledger"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["result_kind"] == (
        "ledger_pnl.formal_financial_indicator_rule_checks"
    )
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["evidence_rows"] == 18
    assert envelope["result"]["report_month"] == "202603"
    _assert_no_float(envelope)


def test_ledger_pnl_service_envelope_for_missing_month_is_warning():
    service = _load_service_module()

    envelope = service.ledger_pnl_formal_indicator_rule_checks_envelope(report_month="202606")

    assert envelope["result_meta"]["basis"] == "ledger"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["evidence_rows"] == 0
    assert envelope["result"]["sample_status"] == "missing_contract"
    _assert_no_float(envelope)
