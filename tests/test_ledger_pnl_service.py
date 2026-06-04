from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.product_category_pnl import CanonicalFactRow
from backend.app.services import ledger_pnl_service


def _fact(
    account_code: str,
    currency: str,
    *,
    ending_balance: str = "0",
    monthly_pnl: str = "0",
) -> CanonicalFactRow:
    return CanonicalFactRow(
        report_date=date(2026, 4, 30),
        account_code=account_code,
        currency=currency,
        account_name=account_code,
        beginning_balance=Decimal("0"),
        ending_balance=Decimal(ending_balance),
        monthly_pnl=Decimal(monthly_pnl),
        daily_avg_balance=Decimal("0"),
        annual_avg_balance=Decimal("0"),
        days_in_period=30,
    )


def test_ledger_pnl_summary_uses_qdb_1_2_prefix_totals_and_ignores_bad_currency(monkeypatch):
    facts = [
        _fact("10101000001", "CNX", ending_balance="100"),
        _fact("12301000001", "CNX", ending_balance="40"),
        _fact("14201000001", "CNX", ending_balance="10"),
        _fact("20101000001", "CNX", ending_balance="-50"),
        _fact("23401000001", "CNX", ending_balance="-30"),
        _fact("51401000001", "CNY", monthly_pnl="7"),
        _fact("51601000001", "CNX", monthly_pnl="3"),
        _fact("-20", "23402000001", ending_balance="999", monthly_pnl="99"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test"),
    )

    summary = ledger_pnl_service.get_ledger_pnl_summary(
        "unused",
        date(2026, 4, 30),
    )

    assert summary["ledger_total_assets"]["yuan"] == "150"
    assert summary["ledger_total_liabilities"]["yuan"] == "80"
    assert summary["ledger_net_assets"]["yuan"] == "70"
    assert summary["ledger_monthly_pnl_core"]["yuan"] == "10"
    assert summary["ledger_monthly_pnl_all"]["yuan"] == "10"
    assert {item["currency"] for item in summary["by_currency"]} == {"CNX", "CNY"}
    assert {item["account_code"] for item in summary["by_account"]} == {"51401000001", "51601000001"}


def test_ledger_pnl_detail_ignores_bad_currency(monkeypatch):
    facts = [
        _fact("51401000001", "CNX", monthly_pnl="7"),
        _fact("-20", "23402000001", ending_balance="999", monthly_pnl="99"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test"),
    )

    payload = ledger_pnl_service.get_ledger_pnl_by_date(
        "unused",
        date(2026, 4, 30),
    )

    assert [item["currency"] for item in payload["items"]] == ["CNX"]
    assert payload["summary"]["count"] == 1


def test_ledger_pnl_dates_envelope_is_ledger_basis_not_formal(monkeypatch):
    class SourcePair:
        report_date = date(2026, 4, 30)

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )

    envelope = ledger_pnl_service.ledger_pnl_dates_envelope("unused")

    meta = envelope["result_meta"]
    assert meta["basis"] == "ledger"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "ledger_pnl.dates"
    assert meta["tables_used"] == ["qdb_general_ledger_workbook"]
    assert meta["evidence_rows"] == 1
    assert envelope["result"]["dates"] == ["2026-04-30"]


def test_ledger_pnl_summary_envelope_is_ledger_basis_not_formal(monkeypatch):
    facts = [
        _fact("10101000001", "CNX", ending_balance="100"),
        _fact("20101000001", "CNX", ending_balance="-50"),
        _fact("51401000001", "CNX", monthly_pnl="7"),
        _fact("51401000001", "CNX", monthly_pnl="3"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test_ledger"),
    )

    envelope = ledger_pnl_service.ledger_pnl_summary_envelope(
        "unused",
        "2026-04-30",
        "CNX",
    )

    meta = envelope["result_meta"]
    assert meta["basis"] == "ledger"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "ledger_pnl.summary"
    assert meta["requested_report_date"] == "2026-04-30"
    assert meta["resolved_report_date"] == "2026-04-30"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["date_basis"] == "ledger_report_date"
    assert meta["filters_applied"] == {"report_date": "2026-04-30", "currency": "CNX"}
    assert meta["tables_used"] == ["qdb_general_ledger_workbook"]
    assert meta["evidence_rows"] == 2


def test_ledger_pnl_data_envelope_is_ledger_basis_not_formal(monkeypatch):
    facts = [
        _fact("51401000001", "CNX", monthly_pnl="7"),
        _fact("51601000001", "CNY", monthly_pnl="3"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test_ledger"),
    )

    envelope = ledger_pnl_service.ledger_pnl_data_envelope(
        "unused",
        "2026-04-30",
    )

    meta = envelope["result_meta"]
    assert meta["basis"] == "ledger"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "ledger_pnl.data"
    assert meta["requested_report_date"] == "2026-04-30"
    assert meta["resolved_report_date"] == "2026-04-30"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["date_basis"] == "ledger_report_date"
    assert meta["filters_applied"] == {"report_date": "2026-04-30", "currency": "ALL"}
    assert meta["tables_used"] == ["qdb_general_ledger_workbook"]
    assert meta["evidence_rows"] == 2


def test_ledger_pnl_summary_envelope_marks_missing_source_as_warning(monkeypatch):
    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: ([], "sv_ledger_pnl_empty"),
    )

    envelope = ledger_pnl_service.ledger_pnl_summary_envelope(
        "unused",
        "2026-05-31",
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert meta["quality_flag"] == "warning"
    assert meta["formal_use_allowed"] is False
    assert meta["evidence_rows"] == 0
    assert meta["source_version"] == "sv_ledger_pnl_empty"
    assert meta["next_drill"][0]["label"] == "核对总账报告日"
    assert result["by_currency"] == []
    assert result["ledger_monthly_pnl_all"]["yuan"] == "0"


def test_ledger_pnl_data_envelope_marks_filtered_empty_slice_as_warning(monkeypatch):
    facts = [
        _fact("51401000001", "CNX", monthly_pnl="7"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test_ledger"),
    )

    envelope = ledger_pnl_service.ledger_pnl_data_envelope(
        "unused",
        "2026-04-30",
        "CNY",
    )

    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["evidence_rows"] == 0
    assert meta["filters_applied"] == {"report_date": "2026-04-30", "currency": "CNY"}
    assert meta["next_drill"][2]["label"] == "核对币种筛选"
    assert envelope["result"]["items"] == []
