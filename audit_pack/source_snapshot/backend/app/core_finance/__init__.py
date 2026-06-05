"""Formal finance calculation entrypoints."""

from importlib import import_module

from backend.app.core_finance.cashflow_projection import (
    CashflowEvent,
    DurationGapResult,
    MonthlyBucket,
    build_monthly_buckets,
    compute_duration_gap,
    project_bond_cashflows,
    project_liability_cashflows,
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
from backend.app.core_finance.pnl_bridge import PnlBridgeRow, build_pnl_bridge_rows

_BALANCE_ANALYSIS_EXPORTS = frozenset(
    {
        "BalanceCurrencyBasis",
        "BalancePositionScope",
        "FormalTywBalanceFactRow",
        "FormalZqtzBalanceFactRow",
        "TywSnapshotRow",
        "ZqtzSnapshotRow",
        "average_daily_cny_amounts",
        "derive_accounting_basis",
        "derive_invest_type_std",
        "project_tyw_formal_balance_row",
        "project_zqtz_formal_balance_row",
    }
)

__all__ = [
    "BalanceCurrencyBasis",
    "BalancePositionScope",
    "AccountingBasis",
    "CashflowEvent",
    "CurrencyBasis",
    "DurationGapResult",
    "FiPnlRecord",
    "FormalTywBalanceFactRow",
    "FormalPnlFiFactRow",
    "FormalZqtzBalanceFactRow",
    "InvestTypeStd",
    "JournalType",
    "MonthlyBucket",
    "NonStdJournalEntry",
    "NonStdPnlBridgeRow",
    "PnlBridgeRow",
    "TywSnapshotRow",
    "ZqtzSnapshotRow",
    "average_daily_cny_amounts",
    "build_formal_pnl_fi_fact_rows",
    "build_monthly_buckets",
    "build_pnl_bridge_rows",
    "build_nonstd_pnl_bridge_rows",
    "compute_duration_gap",
    "derive_accounting_basis",
    "derive_invest_type_std",
    "build_balance_analysis_workbook_payload",
    "normalize_fi_pnl_records",
    "normalize_nonstd_journal_entries",
    "project_bond_cashflows",
    "project_liability_cashflows",
    "project_tyw_formal_balance_row",
    "project_zqtz_formal_balance_row",
]


def __getattr__(name: str):
    if name in _BALANCE_ANALYSIS_EXPORTS:
        module = import_module(".balance_analysis", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def build_balance_analysis_workbook_payload(*args, **kwargs):
    from backend.app.core_finance.balance_analysis_workbook import (
        build_balance_analysis_workbook_payload as _impl,
    )

    return _impl(*args, **kwargs)
