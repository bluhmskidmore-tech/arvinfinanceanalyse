"""Main builder entry point - orchestrates all table builders."""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.core_finance.balance_analysis import (
    BalanceCurrencyBasis,
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_workbook._bond_tables import (
    _build_cards,
    _build_bond_business_type_table,
    _build_maturity_gap_table,
    _build_issuance_business_type_table,
    _build_issuer_concentration_table,
    _build_liquidity_layers_table,
    _build_portfolio_comparison_table,
    _build_cashflow_calendar_table,
    _build_vintage_analysis_table,
    _build_customer_attribute_analysis_table,
)
from backend.app.core_finance.balance_workbook._risk_tables import (
    _build_regulatory_limits_table,
    _build_overdue_credit_quality_detail_table,
    _build_overdue_credit_quality_rating_table,
    _build_risk_alerts_table,
)
from backend.app.core_finance.balance_workbook._ifrs9_tables import (
    _build_ifrs9_classification_table,
    _build_ifrs9_position_scope_table,
    _build_ifrs9_source_family_table,
    _build_account_category_comparison_table,
    _build_rule_reference_table,
)
from backend.app.core_finance.balance_workbook._analysis_tables import (
    _build_currency_split_table,
    _build_rating_table,
    _build_rate_distribution_table,
    _build_industry_table,
    _build_counterparty_type_table,
    _build_campisi_table,
    _build_cross_analysis_table,
    _build_interest_mode_table,
    _build_decision_items_table,
    _build_event_calendar_table,
)


def build_balance_analysis_workbook_payload(
    *,
    report_date: date,
    position_scope: BalancePositionScope,
    currency_basis: BalanceCurrencyBasis,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
    zqtz_currency_rows: list[FormalZqtzBalanceFactRow] | None = None,
) -> dict[str, Any]:
    """Build balance analysis workbook payload.

    Orchestrates all table builders from the modular structure.
    """
    zqtz_currency_rows = zqtz_currency_rows or zqtz_rows
    cards = _build_cards(zqtz_rows, tyw_rows)
    tables = [
        _build_bond_business_type_table(zqtz_rows),
        _build_maturity_gap_table(report_date, zqtz_rows, tyw_rows),
        _build_cashflow_calendar_table(report_date, zqtz_rows, tyw_rows),
        _build_issuer_concentration_table(zqtz_rows),
        _build_liquidity_layers_table(zqtz_rows),
        _build_regulatory_limits_table(report_date, zqtz_rows, tyw_rows),
        _build_overdue_credit_quality_detail_table(zqtz_rows),
        _build_overdue_credit_quality_rating_table(zqtz_rows),
        _build_vintage_analysis_table(zqtz_rows),
        _build_customer_attribute_analysis_table(zqtz_rows),
        _build_portfolio_comparison_table(zqtz_rows),
        _build_account_category_comparison_table(zqtz_rows),
        _build_ifrs9_classification_table(zqtz_rows, tyw_rows),
        _build_ifrs9_position_scope_table(zqtz_rows, tyw_rows),
        _build_ifrs9_source_family_table(zqtz_rows, tyw_rows),
        _build_rule_reference_table(),
        _build_issuance_business_type_table(zqtz_rows),
        _build_currency_split_table(zqtz_currency_rows),
        _build_rating_table(zqtz_rows),
        _build_rate_distribution_table(zqtz_rows, tyw_rows),
        _build_industry_table(zqtz_rows),
        _build_counterparty_type_table(tyw_rows),
        _build_campisi_table(zqtz_rows),
        _build_cross_analysis_table(zqtz_rows),
        _build_interest_mode_table(zqtz_rows),
        _build_decision_items_table(report_date, zqtz_rows, tyw_rows),
        _build_event_calendar_table(report_date, zqtz_rows, tyw_rows),
        _build_risk_alerts_table(report_date, zqtz_rows, tyw_rows),
    ]
    return {
        "report_date": report_date.isoformat(),
        "position_scope": position_scope,
        "currency_basis": currency_basis,
        "cards": cards,
        "tables": tables,
    }
