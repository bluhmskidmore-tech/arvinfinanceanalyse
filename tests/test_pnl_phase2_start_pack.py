from __future__ import annotations

from datetime import date
from decimal import Decimal

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


def test_phase2_fi_standardization_maps_raw_rows_into_governed_contract():
    assert normalize_fi_pnl_records(
        [
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": Decimal("12.50"),
                "fair_value_change_516": Decimal("-3.25"),
                "capital_gain_517": Decimal("1.75"),
                "manual_adjustment": Decimal("0.50"),
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-001",
                "trace_id": "trace-fi-001",
            }
        ]
    ) == [
        FiPnlRecord(
            report_date=date(2025, 12, 31),
            instrument_code="240001.IB",
            portfolio_name="FI Desk",
            cost_center="CC100",
            invest_type_raw="交易性金融资产",
            invest_type_std="T",
            accounting_basis="FVTPL",
            interest_income_514=Decimal("12.50"),
            fair_value_change_516=Decimal("-3.25"),
            capital_gain_517=Decimal("1.75"),
            manual_adjustment=Decimal("0.50"),
            total_pnl=Decimal("11.50"),
            currency_basis="CNY",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-fi-001",
        )
    ]


def test_phase2_nonstd_standardization_builds_signed_amount_before_formal_use():
    assert normalize_nonstd_journal_entries(
        [
            {
                "voucher_date": "2025-12-31",
                "account_code": "51601010004",
                "asset_code": "BOND-001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "direct_516_field",
                "event_type": "mtm",
                "raw_amount": Decimal("100.00"),
                "source_file": "nonstd-516.xlsx",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-001",
                "trace_id": "trace-nonstd-001",
            }
        ],
        journal_type="516",
    ) == [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51601010004",
            asset_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-100.00"),
            dc_flag="direct_516_field",
            event_type="mtm",
            source_file="nonstd-516.xlsx",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-nonstd-001",
        )
    ]


def test_phase2_nonstd_standardization_handles_raw_dc_flags_and_517_direct_fields():
    assert normalize_nonstd_journal_entries(
        [
            {
                "voucher_date": "2025-12-31",
                "account_code": "51401000004",
                "asset_code": "BOND-514-CREDIT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "\u8d37",
                "event_type": "interest",
                "raw_amount": Decimal("100.00"),
                "source_file": "nonstd-514.xlsx",
            },
            {
                "voucher_date": "2025-12-31",
                "account_code": "51401000004",
                "asset_code": "BOND-514-DEBIT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "\u501f",
                "event_type": "interest",
                "raw_amount": Decimal("100.00"),
                "source_file": "nonstd-514.xlsx",
            },
        ],
        journal_type="514",
    ) == [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51401000004",
            asset_code="BOND-514-CREDIT",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="514",
            signed_amount=Decimal("100.00"),
            dc_flag="\u8d37",
            event_type="interest",
            source_file="nonstd-514.xlsx",
            source_version="",
            rule_version="",
            ingest_batch_id="",
            trace_id="",
        ),
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51401000004",
            asset_code="BOND-514-DEBIT",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="514",
            signed_amount=Decimal("-100.00"),
            dc_flag="\u501f",
            event_type="interest",
            source_file="nonstd-514.xlsx",
            source_version="",
            rule_version="",
            ingest_batch_id="",
            trace_id="",
        ),
    ]

    assert normalize_nonstd_journal_entries(
        [
            {
                "voucher_date": "2025-12-31",
                "account_code": "51701010004",
                "asset_code": "BOND-517",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "direct_517_field",
                "event_type": "realized_gain",
                "raw_amount": Decimal("25.00"),
                "source_file": "nonstd-517.xlsx",
            }
        ],
        journal_type="517",
    ) == [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51701010004",
            asset_code="BOND-517",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="517",
            signed_amount=Decimal("-25.00"),
            dc_flag="direct_517_field",
            event_type="realized_gain",
            source_file="nonstd-517.xlsx",
            source_version="",
            rule_version="",
            ingest_batch_id="",
            trace_id="",
        )
    ]

    assert normalize_nonstd_journal_entries(
        [
            {
                "voucher_date": "2025-12-31",
                "account_code": "51601010004",
                "asset_code": "BOND-516-CREDIT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "\u8d37",
                "event_type": "mtm",
                "raw_amount": Decimal("10.00"),
                "source_file": "nonstd-516.xlsx",
            },
            {
                "voucher_date": "2025-12-31",
                "account_code": "51601010004",
                "asset_code": "BOND-516-DEBIT",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "\u501f",
                "event_type": "mtm",
                "raw_amount": Decimal("10.00"),
                "source_file": "nonstd-516.xlsx",
            },
        ],
        journal_type="516",
    ) == [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51601010004",
            asset_code="BOND-516-CREDIT",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("10.00"),
            dc_flag="\u8d37",
            event_type="mtm",
            source_file="nonstd-516.xlsx",
            source_version="",
            rule_version="",
            ingest_batch_id="",
            trace_id="",
        ),
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51601010004",
            asset_code="BOND-516-DEBIT",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-10.00"),
            dc_flag="\u501f",
            event_type="mtm",
            source_file="nonstd-516.xlsx",
            source_version="",
            rule_version="",
            ingest_batch_id="",
            trace_id="",
        ),
    ]


def test_phase2_nonstd_standardization_rejects_unknown_dc_flag() -> None:
    with pytest.raises(ValueError, match="Unsupported dc_flag"):
        normalize_nonstd_journal_entries(
            [
                {
                    "voucher_date": "2025-12-31",
                    "account_code": "51601010004",
                    "asset_code": "BOND-516-UNKNOWN",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "mystery_flag",
                    "event_type": "mtm",
                    "raw_amount": Decimal("10.00"),
                    "source_file": "nonstd-516.xlsx",
                }
            ],
            journal_type="516",
        )

def test_phase2_nonstd_bridge_uses_month_end_mtd_semantics():
    entries = [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 30),
            account_code="51601010004",
            asset_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-40.00"),
            dc_flag="credit",
            event_type="mtm",
            source_file="nonstd-516.xlsx",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-001",
        ),
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51601010004",
            asset_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-60.00"),
            dc_flag="credit",
            event_type="mtm",
            source_file="nonstd-516.xlsx",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-002",
        ),
    ]

    assert build_nonstd_pnl_bridge_rows(
        entries,
        target_date=date(2025, 12, 31),
        is_month_end=True,
    ) == [
        NonStdPnlBridgeRow(
            report_date=date(2025, 12, 31),
            bond_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            interest_income_514=Decimal("0"),
            fair_value_change_516=Decimal("-100.00"),
            capital_gain_517=Decimal("0"),
            manual_adjustment=Decimal("0"),
            total_pnl=Decimal("-100.00"),
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-001,trace-002",
        )
    ]


def test_phase2_nonstd_bridge_normalizes_lineage_versions_with_double_underscore_separator():
    entries = [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 30),
            account_code="51601010004",
            asset_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-40.00"),
            dc_flag="credit",
            event_type="mtm",
            source_file="nonstd-516-a.xlsx",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-001",
        ),
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51601010004",
            asset_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="516",
            signed_amount=Decimal("-60.00"),
            dc_flag="credit",
            event_type="mtm",
            source_file="nonstd-516-b.xlsx",
            source_version="src-v2",
            rule_version="rule-v2",
            ingest_batch_id="batch-001",
            trace_id="trace-002",
        ),
    ]

    assert build_nonstd_pnl_bridge_rows(
        entries,
        target_date=date(2025, 12, 31),
        is_month_end=True,
    ) == [
        NonStdPnlBridgeRow(
            report_date=date(2025, 12, 31),
            bond_code="BOND-001",
            portfolio_name="FI Desk",
            cost_center="CC100",
            interest_income_514=Decimal("0"),
            fair_value_change_516=Decimal("-100.00"),
            capital_gain_517=Decimal("0"),
            manual_adjustment=Decimal("0"),
            total_pnl=Decimal("-100.00"),
            source_version="src-v1__src-v2",
            rule_version="rule-v1__rule-v2",
            ingest_batch_id="batch-001",
            trace_id="trace-001,trace-002",
        )
    ]


def test_phase2_nonstd_bridge_uses_unlabeled_fallback_when_asset_code_is_missing():
    entries = [
        NonStdJournalEntry(
            voucher_date=date(2025, 12, 31),
            account_code="51401000004",
            asset_code="",
            portfolio_name="FI Desk",
            cost_center="CC100",
            journal_type="514",
            signed_amount=Decimal("15.00"),
            dc_flag="贷",
            event_type="interest",
            source_file="nonstd-514.xlsx",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-514",
        )
    ]

    normalized = normalize_nonstd_journal_entries(
        [
            {
                "voucher_date": "2025-12-31",
                "account_code": "51401000004",
                "asset_code": None,
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "dc_flag": "\u8d37",
                "event_type": "interest",
                "raw_amount": Decimal("15.00"),
                "source_file": "nonstd-514.xlsx",
            }
        ],
        journal_type="514",
    )
    assert normalized[0].asset_code == ""

    assert build_nonstd_pnl_bridge_rows(
        entries,
        target_date=date(2025, 12, 31),
        is_month_end=False,
    ) == [
        NonStdPnlBridgeRow(
            report_date=date(2025, 12, 31),
            bond_code="未标注",
            portfolio_name="FI Desk",
            cost_center="CC100",
            interest_income_514=Decimal("15.00"),
            fair_value_change_516=Decimal("0"),
            capital_gain_517=Decimal("0"),
            manual_adjustment=Decimal("0"),
            total_pnl=Decimal("15.00"),
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-514",
        )
    ]


def test_phase2_formal_fi_fact_projection_preserves_governed_components():
    fi_records = [
        FiPnlRecord(
            report_date=date(2025, 12, 31),
            instrument_code="240001.IB",
            portfolio_name="FI Desk",
            cost_center="CC100",
            invest_type_raw="TRADING_ASSET_RAW",
            invest_type_std="T",
            accounting_basis="FVTPL",
            interest_income_514=Decimal("12.50"),
            fair_value_change_516=Decimal("-3.25"),
            capital_gain_517=Decimal("1.75"),
            manual_adjustment=Decimal("0.50"),
            total_pnl=Decimal("999.00"),
            currency_basis="CNY",
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-fi",
            approval_status="approved",
            event_semantics="realized_formal",
            realized_flag=True,
        )
    ]

    assert build_formal_pnl_fi_fact_rows(fi_records) == [
        FormalPnlFiFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="240001.IB",
            portfolio_name="FI Desk",
            cost_center="CC100",
            invest_type_std="T",
            accounting_basis="FVTPL",
            currency_basis="CNY",
            interest_income_514=Decimal("12.50"),
            fair_value_change_516=Decimal("-3.25"),
            capital_gain_517=Decimal("1.75"),
            manual_adjustment=Decimal("0.50"),
            total_pnl=Decimal("11.50"),
            source_version="src-v1",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-fi",
        )
    ]


def test_phase2_formal_fi_fact_projection_applies_recognition_matrix_and_gating():
    rows = build_formal_pnl_fi_fact_rows(
        [
            FiPnlRecord(
                report_date=date(2025, 12, 31),
                instrument_code="AC-001",
                portfolio_name="FI Desk",
                cost_center="CC100",
                invest_type_raw="持有至到期",
                invest_type_std="H",
                accounting_basis="AC",
                interest_income_514=Decimal("10.00"),
                fair_value_change_516=Decimal("5.00"),
                capital_gain_517=Decimal("4.00"),
                manual_adjustment=Decimal("3.00"),
                total_pnl=Decimal("22.00"),
                approval_status="approved",
                event_semantics="realized_formal",
                realized_flag=True,
            ),
            FiPnlRecord(
                report_date=date(2025, 12, 31),
                instrument_code="OCI-001",
                portfolio_name="FI Desk",
                cost_center="CC100",
                invest_type_raw="可供出售",
                invest_type_std="A",
                accounting_basis="FVOCI",
                interest_income_514=Decimal("10.00"),
                fair_value_change_516=Decimal("5.00"),
                capital_gain_517=Decimal("4.00"),
                manual_adjustment=Decimal("3.00"),
                total_pnl=Decimal("22.00"),
                governance_status="pending",
                event_semantics="realized_formal",
                realized_flag=True,
            ),
            FiPnlRecord(
                report_date=date(2025, 12, 31),
                instrument_code="TPL-001",
                portfolio_name="FI Desk",
                cost_center="CC100",
                invest_type_raw="交易性金融资产",
                invest_type_std="T",
                accounting_basis="FVTPL",
                interest_income_514=Decimal("10.00"),
                fair_value_change_516=Decimal("5.00"),
                capital_gain_517=Decimal("4.00"),
                manual_adjustment=Decimal("3.00"),
                total_pnl=Decimal("22.00"),
                approval_status="pending",
                event_semantics="mark_to_market",
                realized_flag=False,
            ),
        ]
    )

    assert [row.instrument_code for row in rows] == ["AC-001", "OCI-001", "TPL-001"]
    assert [row.total_pnl for row in rows] == [
        Decimal("17.00"),
        Decimal("14.00"),
        Decimal("15.00"),
    ]


def test_phase2_fi_standardization_converts_usd_rows_to_cny_with_fx_rate() -> None:
    assert normalize_fi_pnl_records(
        [
            {
                "report_date": "2025-12-31",
                "instrument_code": "240002.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": Decimal("10.00"),
                "fair_value_change_516": Decimal("-2.00"),
                "capital_gain_517": Decimal("1.00"),
                "manual_adjustment": Decimal("0.50"),
                "currency_basis": "CNY",
                "fx_base_currency": "USD",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-001",
                "trace_id": "trace-fi-002",
            }
        ],
        fx_rates_by_currency={"USD": (Decimal("7.20"), "sv_fx_usd")},
    ) == [
        FiPnlRecord(
            report_date=date(2025, 12, 31),
            instrument_code="240002.IB",
            portfolio_name="FI Desk",
            cost_center="CC100",
            invest_type_raw="交易性金融资产",
            invest_type_std="T",
            accounting_basis="FVTPL",
            interest_income_514=Decimal("72.0000"),
            fair_value_change_516=Decimal("-14.4000"),
            capital_gain_517=Decimal("7.2000"),
            manual_adjustment=Decimal("3.6000"),
            total_pnl=Decimal("68.4000"),
            currency_basis="CNY",
            source_version="src-v1__sv_fx_usd",
            rule_version="rule-v1",
            ingest_batch_id="batch-001",
            trace_id="trace-fi-002",
        )
    ]
