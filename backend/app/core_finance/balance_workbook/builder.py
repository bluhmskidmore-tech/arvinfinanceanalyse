"""Main builder entry point - delegates to original monolithic module.

This module serves as a facade during the refactoring transition.
The original balance_analysis_workbook.py remains intact for now.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.core_finance.balance_analysis import (
    BalanceCurrencyBasis,
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)

# Import from the original monolithic module
from backend.app.core_finance.balance_analysis_workbook import (
    build_balance_analysis_workbook_payload as _original_build,
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

    Currently delegates to the original monolithic implementation.
    Future refactoring will split this into modular table builders.
    """
    return _original_build(
        report_date=report_date,
        position_scope=position_scope,
        currency_basis=currency_basis,
        zqtz_rows=zqtz_rows,
        tyw_rows=tyw_rows,
        zqtz_currency_rows=zqtz_currency_rows,
    )
