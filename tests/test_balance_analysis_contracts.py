from __future__ import annotations

from dataclasses import fields

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
