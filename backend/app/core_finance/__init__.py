"""Formal finance calculation entrypoints."""

from backend.app.core_finance.balance_analysis import (
    BalanceCurrencyBasis,
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
    TywSnapshotRow,
    ZqtzSnapshotRow,
    average_daily_cny_amounts,
    derive_accounting_basis,
    derive_invest_type_std,
    project_tyw_formal_balance_row,
    project_zqtz_formal_balance_row,
)
from backend.app.core_finance.pnl import (
    AccountingBasis,
    CurrencyBasis,
    FiPnlRecord,
    FormalPnlFiFactRow,
    InvestTypeStd,
    JournalType,
    NonStdJournalEntry,
    NonStdPnlBridgeRow,
    build_formal_pnl_fi_fact_rows,
    build_nonstd_pnl_bridge_rows,
    normalize_fi_pnl_records,
    normalize_nonstd_journal_entries,
)

__all__ = [
    "BalanceCurrencyBasis",
    "BalancePositionScope",
    "AccountingBasis",
    "CurrencyBasis",
    "FiPnlRecord",
    "FormalTywBalanceFactRow",
    "FormalPnlFiFactRow",
    "FormalZqtzBalanceFactRow",
    "InvestTypeStd",
    "JournalType",
    "NonStdJournalEntry",
    "NonStdPnlBridgeRow",
    "TywSnapshotRow",
    "ZqtzSnapshotRow",
    "average_daily_cny_amounts",
    "build_formal_pnl_fi_fact_rows",
    "build_nonstd_pnl_bridge_rows",
    "derive_accounting_basis",
    "derive_invest_type_std",
    "build_balance_analysis_workbook_payload",
    "normalize_fi_pnl_records",
    "normalize_nonstd_journal_entries",
    "project_tyw_formal_balance_row",
    "project_zqtz_formal_balance_row",
]


def build_balance_analysis_workbook_payload(*args, **kwargs):
    from backend.app.core_finance.balance_analysis_workbook import (
        build_balance_analysis_workbook_payload as _impl,
    )

    return _impl(*args, **kwargs)
