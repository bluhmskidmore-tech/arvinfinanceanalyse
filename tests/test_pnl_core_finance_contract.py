from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from backend.app.core_finance import (
    FiPnlRecord,
    FormalPnlFiFactRow,
    NonStdJournalEntry,
    NonStdPnlBridgeRow,
    build_formal_pnl_fi_fact_rows,
    build_nonstd_pnl_bridge_rows,
    normalize_fi_pnl_records,
    normalize_nonstd_journal_entries,
)


def test_pnl_core_finance_exports_phase2_contract_types():
    assert FiPnlRecord.__name__ == "FiPnlRecord"
    assert NonStdJournalEntry.__name__ == "NonStdJournalEntry"
    assert FormalPnlFiFactRow.__name__ == "FormalPnlFiFactRow"
    assert NonStdPnlBridgeRow.__name__ == "NonStdPnlBridgeRow"
    assert callable(normalize_fi_pnl_records)
    assert callable(normalize_nonstd_journal_entries)


def test_pnl_core_finance_contract_shapes_match_governed_field_names():
    assert [field.name for field in fields(FiPnlRecord)] == [
        "report_date",
        "instrument_code",
        "portfolio_name",
        "cost_center",
        "invest_type_raw",
        "invest_type_std",
        "accounting_basis",
        "interest_income_514",
        "fair_value_change_516",
        "capital_gain_517",
        "manual_adjustment",
        "total_pnl",
        "currency_basis",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ]
    assert [field.name for field in fields(NonStdJournalEntry)] == [
        "voucher_date",
        "account_code",
        "asset_code",
        "portfolio_name",
        "cost_center",
        "journal_type",
        "signed_amount",
        "dc_flag",
        "event_type",
        "source_file",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ]
    assert [field.name for field in fields(FormalPnlFiFactRow)] == [
        "report_date",
        "instrument_code",
        "portfolio_name",
        "cost_center",
        "invest_type_std",
        "accounting_basis",
        "currency_basis",
        "interest_income_514",
        "fair_value_change_516",
        "capital_gain_517",
        "manual_adjustment",
        "total_pnl",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ]
    assert [field.name for field in fields(NonStdPnlBridgeRow)] == [
        "report_date",
        "bond_code",
        "portfolio_name",
        "cost_center",
        "interest_income_514",
        "fair_value_change_516",
        "capital_gain_517",
        "manual_adjustment",
        "total_pnl",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ]


def test_pnl_phase2_entrypoints_exist_for_phase2_execution():
    assert callable(build_nonstd_pnl_bridge_rows)
    assert callable(build_formal_pnl_fi_fact_rows)
