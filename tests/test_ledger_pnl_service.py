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
    assert summary["ledger_monthly_pnl_core"]["yuan"] == "7"
    assert {item["currency"] for item in summary["by_currency"]} == {"CNX", "CNY"}
    assert "23402000001" not in {item["currency"] for item in summary["by_currency"]}


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
    assert meta["evidence_rows"] == 4


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
