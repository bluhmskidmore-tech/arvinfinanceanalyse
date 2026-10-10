from __future__ import annotations

from dataclasses import fields

import pytest
from pydantic import ValidationError

from tests.helpers import load_module


def test_balance_analysis_schema_defines_governed_payload_models():
    module = load_module(
        "backend.app.schemas.balance_analysis",
        "backend/app/schemas/balance_analysis.py",
    )

    detail_row = getattr(module, "BalanceAnalysisDetailRow")
    summary_row = getattr(module, "BalanceAnalysisSummaryRow")
    payload = getattr(module, "BalanceAnalysisPayload")
    dates_payload = getattr(module, "BalanceAnalysisDatesPayload")
    workbook_card = getattr(module, "BalanceAnalysisWorkbookCard")
    workbook_table = getattr(module, "BalanceAnalysisWorkbookTable")
    workbook_payload = getattr(module, "BalanceAnalysisWorkbookPayload")
    basis_row = getattr(module, "BalanceAnalysisBasisBreakdownRow")
    basis_payload = getattr(module, "BalanceAnalysisBasisBreakdownPayload")
    metric_definition = getattr(module, "BalanceAnalysisMetricDefinition")
    overview_payload = getattr(module, "BalanceAnalysisOverviewPayload")

    assert {
        "source_family",
        "report_date",
        "row_key",
        "display_name",
        "position_scope",
        "currency_basis",
        "invest_type_std",
        "accounting_basis",
        "market_value_amount",
        "amortized_cost_amount",
        "accrued_interest_amount",
    } <= set(detail_row.model_fields)
    assert {
        "source_family",
        "position_scope",
        "currency_basis",
        "row_count",
        "market_value_amount",
        "amortized_cost_amount",
        "accrued_interest_amount",
    } <= set(summary_row.model_fields)
    assert {
        "report_date",
        "position_scope",
        "currency_basis",
        "details",
        "summary",
    } <= set(payload.model_fields)
    assert set(dates_payload.model_fields) == {"report_dates"}
    assert {"key", "label", "value", "note"} <= set(workbook_card.model_fields)
    assert {"key", "title", "columns", "rows"} <= set(workbook_table.model_fields)
    assert {"report_date", "position_scope", "currency_basis", "cards", "tables"} <= set(
        workbook_payload.model_fields
    )
    assert {
        "source_family",
        "invest_type_std",
        "accounting_basis",
        "position_scope",
        "currency_basis",
        "detail_row_count",
        "market_value_amount",
        "amortized_cost_amount",
        "accrued_interest_amount",
    } <= set(basis_row.model_fields)
    assert {"report_date", "position_scope", "currency_basis", "rows"} <= set(basis_payload.model_fields)
    assert {
        "key",
        "label",
        "source_field",
        "raw_unit",
        "display_unit",
        "basis",
        "source_surface",
        "applies_to",
        "description",
    } <= set(metric_definition.model_fields)
    assert "metric_definitions" in overview_payload.model_fields


def test_balance_analysis_api_openapi_uses_concrete_response_models():
    app = load_module("backend.app.main", "backend/app/main.py").app
    spec = app.openapi()

    expected_json_responses = {
        ("get", "/ui/balance-analysis/dates"): "BalanceAnalysisDatesEnvelope",
        ("get", "/ui/balance-analysis"): "BalanceAnalysisDetailEnvelope",
        ("get", "/ui/balance-analysis/overview"): "BalanceAnalysisOverviewEnvelope",
        ("get", "/ui/balance-analysis/summary"): "BalanceAnalysisSummaryEnvelope",
        (
            "get",
            "/ui/balance-analysis/summary-by-basis",
        ): "BalanceAnalysisBasisBreakdownEnvelope",
        (
            "get",
            "/ui/balance-analysis/advanced-attribution",
        ): "BalanceAnalysisAdvancedAttributionEnvelope",
        ("get", "/ui/balance-analysis/workbook"): "BalanceAnalysisWorkbookEnvelope",
        ("get", "/ui/balance-analysis/current-user"): "BalanceAnalysisCurrentUserPayload",
        (
            "get",
            "/ui/balance-analysis/decision-items",
        ): "BalanceAnalysisDecisionItemsEnvelope",
        (
            "post",
            "/ui/balance-analysis/decision-items/status",
        ): "BalanceAnalysisDecisionStatusRecord",
        ("post", "/ui/balance-analysis/refresh"): "BalanceAnalysisRefreshPayload",
        (
            "get",
            "/ui/balance-analysis/refresh-status",
        ): "BalanceAnalysisRefreshStatusPayload",
    }
    for (method, path), component_name in expected_json_responses.items():
        schema = spec["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert schema == {"$ref": f"#/components/schemas/{component_name}"}
        assert spec["components"]["schemas"][component_name]["additionalProperties"] is False

    summary_export = spec["paths"]["/ui/balance-analysis/summary/export"]["get"]["responses"]["200"]
    assert summary_export["content"]["text/csv"]["schema"] == {"type": "string"}
    workbook_export = spec["paths"]["/ui/balance-analysis/workbook/export"]["get"]["responses"]["200"]
    workbook_media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert workbook_export["content"][workbook_media_type]["schema"] == {
        "type": "string",
        "format": "binary",
    }


def test_balance_analysis_api_envelope_rejects_undeclared_service_fields():
    module = load_module(
        "backend.app.schemas.balance_analysis",
        "backend/app/schemas/balance_analysis.py",
    )
    payload = {
        "result_meta": {
            "trace_id": "tr-balance-contract",
            "result_kind": "balance-analysis.dates",
            "source_version": "sv-balance-contract",
            "rule_version": "rv-balance-contract",
            "cache_version": "cv-balance-contract",
            "source_surface": "formal_balance",
        },
        "result": {"report_dates": ["2025-12-31"]},
        "undeclared_service_field": "must fail",
    }

    with pytest.raises(ValidationError, match="undeclared_service_field"):
        module.BalanceAnalysisDatesEnvelope.model_validate(payload)

    payload.pop("undeclared_service_field")
    payload["result"]["undeclared_result_field"] = "must also fail"
    with pytest.raises(ValidationError, match="undeclared_result_field"):
        module.BalanceAnalysisDatesEnvelope.model_validate(payload)


def test_balance_analysis_core_exports_future_formal_fact_types():
    module = load_module(
        "backend.app.core_finance.balance_analysis",
        "backend/app/core_finance/balance_analysis.py",
    )

    assert [field.name for field in fields(module.FormalZqtzBalanceFactRow)] == [
        "report_date",
        "instrument_code",
        "instrument_name",
        "portfolio_name",
        "cost_center",
        "account_category",
        "asset_class",
        "bond_type",
        "issuer_name",
        "industry_name",
        "rating",
        "invest_type_std",
        "accounting_basis",
        "position_scope",
        "currency_basis",
        "currency_code",
        "face_value_amount",
        "market_value_amount",
        "amortized_cost_amount",
        "accrued_interest_amount",
        "coupon_rate",
        "ytm_value",
        "maturity_date",
        "interest_mode",
        "is_issuance_like",
        "overdue_principal_days",
        "overdue_interest_days",
        "value_date",
        "customer_attribute",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
        "business_type_primary",
        "sub_type",
    ]
    assert [field.name for field in fields(module.FormalTywBalanceFactRow)] == [
        "report_date",
        "position_id",
        "product_type",
        "position_side",
        "counterparty_name",
        "account_type",
        "special_account_type",
        "core_customer_type",
        "invest_type_std",
        "accounting_basis",
        "position_scope",
        "currency_basis",
        "currency_code",
        "principal_amount",
        "accrued_interest_amount",
        "funding_cost_rate",
        "maturity_date",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ]


def test_core_finance_root_package_lazily_exports_balance_analysis_symbols():
    import backend.app.core_finance as core_finance

    assert core_finance.BalanceCurrencyBasis is not None
    assert core_finance.BalancePositionScope is not None
    assert core_finance.FormalZqtzBalanceFactRow.__name__ == "FormalZqtzBalanceFactRow"
    assert core_finance.FormalTywBalanceFactRow.__name__ == "FormalTywBalanceFactRow"
    assert callable(core_finance.project_zqtz_formal_balance_row)
    assert callable(core_finance.project_tyw_formal_balance_row)
