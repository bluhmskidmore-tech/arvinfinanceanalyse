"""Compatibility entry point for the authoritative balance workbook builder."""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.core_finance.balance_analysis import (
    BalanceCurrencyBasis,
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_analysis_workbook import (
    build_balance_analysis_workbook_payload as _build_authoritative_workbook_payload,
)


def build_balance_analysis_workbook_payload(
    *,
    report_date: date,
    position_scope: BalancePositionScope,
    currency_basis: BalanceCurrencyBasis,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
    zqtz_currency_rows: list[FormalZqtzBalanceFactRow] | None = None,
    zqtz_full_rows: list[FormalZqtzBalanceFactRow] | None = None,
    tyw_full_rows: list[FormalTywBalanceFactRow] | None = None,
) -> dict[str, Any]:
    """Delegate to the production authority so the public package cannot drift."""
    return _build_authoritative_workbook_payload(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        zqtz_rows=zqtz_rows,
        tyw_rows=tyw_rows,
        zqtz_currency_rows=zqtz_currency_rows,
        zqtz_full_rows=zqtz_full_rows,
        tyw_full_rows=tyw_full_rows,
    )
