from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.core_finance.product_category_pnl import CanonicalFactRow
from backend.app.schemas.ledger_pnl_analysis import LedgerPnlAnalysisContributor
from backend.app.services import ledger_pnl_service


def _fact(
    account_code: str,
    currency: str,
    *,
    account_name: str | None = None,
    beginning_balance: str = "0",
    ending_balance: str = "0",
    monthly_pnl: str = "0",
    report_date: date = date(2026, 4, 30),
) -> CanonicalFactRow:
    return CanonicalFactRow(
        report_date=report_date,
        account_code=account_code,
        currency=currency,
        account_name=account_name or account_code,
        beginning_balance=Decimal(beginning_balance),
        ending_balance=Decimal(ending_balance),
        monthly_pnl=Decimal(monthly_pnl),
        daily_avg_balance=Decimal("0"),
        annual_avg_balance=Decimal("0"),
        days_in_period=30,
    )


@pytest.mark.parametrize("account_code", ["55000000001", "514100"])
def test_ledger_pnl_contributor_accepts_detail_compatible_account_codes(account_code):
    contributor = LedgerPnlAnalysisContributor.model_validate(
        {
            "rank": 1,
            "account_code": account_code,
            "account_name": "测试损益科目",
            "amount": {"yuan": "100000000", "yi": "1.00"},
            "count": 1,
        }
    )

    assert contributor.account_code == account_code


def test_ledger_pnl_contributor_rejects_detail_incompatible_account_code_mutation():
    contributor = {
        "rank": 1,
        "account_code": "55000000001",
        "account_name": "测试损益科目",
        "amount": {"yuan": "100000000", "yi": "1.00"},
        "count": 1,
    }
    contributor["account_code"] = "5ABC"

    with pytest.raises(ValidationError, match="account_code"):
        LedgerPnlAnalysisContributor.model_validate(contributor)


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

    assert summary["data_status"] == "ready"
    assert summary["ledger_total_assets"]["yuan"] == "150"
    assert summary["ledger_total_liabilities"]["yuan"] == "80"
    assert summary["ledger_net_assets"]["yuan"] == "70"
    assert summary["ledger_monthly_pnl_core"]["yuan"] == "3"
    assert summary["ledger_monthly_pnl_all"]["yuan"] == "3"
    assert {item["currency"] for item in summary["by_currency"]} == {"CNX"}
    assert {item["account_code"] for item in summary["by_account"]} == {"51601000001"}


def test_ledger_pnl_summary_explicit_cny_uses_only_cny_basis(monkeypatch):
    facts = [
        _fact("10101000001", "CNX", ending_balance="100"),
        _fact("51401000001", "CNX", monthly_pnl="3"),
        _fact("10101000001", "CNY", ending_balance="40"),
        _fact("20101000001", "CNY", ending_balance="-10"),
        _fact("51401000001", "CNY", monthly_pnl="7"),
    ]

    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_test"),
    )

    summary = ledger_pnl_service.get_ledger_pnl_summary(
        "unused",
        date(2026, 4, 30),
        "CNY",
    )

    assert summary["ledger_total_assets"]["yuan"] == "40"
    assert summary["ledger_total_liabilities"]["yuan"] == "10"
    assert summary["ledger_monthly_pnl_all"]["yuan"] == "7"
    assert summary["by_currency"] == [
        {
            "currency": "CNY",
            "total_pnl": {"yuan": "7", "yi": "0.00"},
        }
    ]


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

    assert payload["data_status"] == "ready"
    assert [item["currency"] for item in payload["items"]] == ["CNX"]
    assert payload["summary"]["count"] == 1


def test_ledger_pnl_detail_default_keeps_cnx_details_but_totals_only_5_prefix(monkeypatch):
    facts = [
        _fact("10101000001", "CNX", ending_balance="100", monthly_pnl="100"),
        _fact("51401000001", "CNX", monthly_pnl="7"),
        _fact("51601000001", "CNY", monthly_pnl="3"),
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

    assert {item["account_code"] for item in payload["items"]} == {
        "10101000001",
        "51401000001",
    }
    assert payload["summary"]["total_pnl_cnx"]["yuan"] == "7"
    assert payload["summary"]["total_pnl_cny"]["yuan"] == "0"
    assert payload["summary"]["total_pnl"]["yuan"] == "7"
    assert payload["summary"]["count"] == 2


@pytest.mark.parametrize(
    "getter",
    [
        ledger_pnl_service.get_ledger_pnl_by_date,
        ledger_pnl_service.get_ledger_pnl_summary,
    ],
)
@pytest.mark.parametrize("currency", ["ALL", "USD"])
def test_ledger_pnl_service_rejects_unsupported_currency_basis(monkeypatch, getter, currency):
    monkeypatch.setattr(
        ledger_pnl_service,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: ([], "sv_ledger_pnl_empty"),
    )

    with pytest.raises(ValueError, match="Unsupported ledger currency basis") as exc_info:
        getter("unused", date(2026, 4, 30), currency)
    assert type(exc_info.value).__name__ == "LedgerPnlRequestError"


def test_ledger_pnl_summary_rejects_day_that_is_not_source_month_end(monkeypatch):
    class SourcePair:
        month_key = "202604"
        report_date = date(2026, 4, 30)
        source_version = "sv_test"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [_fact("51401000001", "CNX", monthly_pnl="7")],
    )

    with pytest.raises(ValueError, match="does not match source report_date 2026-04-30") as exc_info:
        ledger_pnl_service.get_ledger_pnl_summary(
            "unused",
            date(2026, 4, 15),
        )
    assert type(exc_info.value).__name__ == "LedgerPnlRequestError"


def test_ledger_pnl_summary_keeps_empty_result_when_source_month_is_missing(monkeypatch):
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [],
    )

    summary = ledger_pnl_service.get_ledger_pnl_summary(
        "unused",
        date(2026, 5, 15),
    )

    assert summary["data_status"] == "no_data"
    assert summary["source_version"] == "sv_ledger_pnl_empty"
    assert summary["ledger_monthly_pnl_all"]["yuan"] == "0"
    assert summary["by_currency"] == []


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
    assert meta["cache_version"] == "cv_ledger_pnl_v2"
    assert meta["rule_version"] == "rv_ledger_pnl_v2"
    assert meta["tables_used"] == [
        "qdb_gl_ledger_reconciliation_workbook",
        "qdb_gl_average_balance_workbook",
    ]
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
    )

    meta = envelope["result_meta"]
    assert meta["basis"] == "ledger"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "ledger_pnl.summary"
    assert meta["cache_version"] == "cv_ledger_pnl_v2"
    assert meta["rule_version"] == "rv_ledger_pnl_v2"
    assert meta["requested_report_date"] == "2026-04-30"
    assert meta["resolved_report_date"] == "2026-04-30"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["date_basis"] == "ledger_report_date"
    assert meta["filters_applied"] == {
        "report_date": "2026-04-30",
        "currency": "CNX",
        "currency_basis": "CNX",
        "currency_basis_note": "CNX=综本；CNY=人民币账",
    }
    assert meta["tables_used"] == [
        "qdb_gl_ledger_reconciliation_workbook",
        "qdb_gl_average_balance_workbook",
    ]
    assert meta["evidence_rows"] == 2
    assert meta["cache_key"] == "ledger_pnl.summary:2026-04-30:CNX"


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
    assert meta["cache_version"] == "cv_ledger_pnl_v2"
    assert meta["rule_version"] == "rv_ledger_pnl_v2"
    assert meta["requested_report_date"] == "2026-04-30"
    assert meta["resolved_report_date"] == "2026-04-30"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["date_basis"] == "ledger_report_date"
    assert meta["filters_applied"] == {
        "report_date": "2026-04-30",
        "currency": "CNX",
        "currency_basis": "CNX",
        "currency_basis_note": "CNX=综本；CNY=人民币账",
    }
    assert meta["tables_used"] == [
        "qdb_gl_ledger_reconciliation_workbook",
        "qdb_gl_average_balance_workbook",
    ]
    assert meta["evidence_rows"] == 1
    assert meta["cache_key"] == "ledger_pnl.data:2026-04-30:CNX"


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
    assert meta["filters_applied"] == {
        "report_date": "2026-04-30",
        "currency": "CNY",
        "currency_basis": "CNY",
        "currency_basis_note": "CNX=综本；CNY=人民币账",
    }
    assert meta["next_drill"][2]["label"] == "核对币种筛选"
    assert envelope["result"]["data_status"] == "no_data"
    assert envelope["result"]["items"] == []


def test_ledger_pnl_analysis_envelope_serializes_candidate_analysis(monkeypatch):
    class SourcePair:
        def __init__(self, month_key: str, report_date: date, source_version: str) -> None:
            self.month_key = month_key
            self.report_date = report_date
            self.source_version = source_version

    current_pair = SourcePair("202606", date(2026, 6, 30), "sv_current")
    previous_pair = SourcePair("202605", date(2026, 5, 31), "sv_previous")
    facts_by_month = {
        "202606": [
            _fact("10100000001", "CNX", ending_balance="100"),
            _fact("20100000001", "CNX", ending_balance="-40"),
            _fact("51400000001", "CNX", monthly_pnl="7"),
            _fact("50100000001", "CNX", monthly_pnl="-2"),
            _fact("10100000001", "CNY", ending_balance="80"),
            _fact("20100000001", "CNY", ending_balance="-30"),
            _fact("51400000001", "CNY", monthly_pnl="6"),
            _fact("50100000001", "CNY", monthly_pnl="-1"),
        ],
        "202605": [
            _fact("51400000001", "CNX", monthly_pnl="10"),
            _fact("50100000001", "CNX", monthly_pnl="1"),
            _fact("51400000001", "CNY", monthly_pnl="9"),
            _fact("50100000001", "CNY", monthly_pnl="1"),
        ],
    }
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [previous_pair, current_pair],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda pair: facts_by_month[pair.month_key],
    )

    envelope = ledger_pnl_service.ledger_pnl_analysis_envelope(
        "unused",
        "2026-06-30",
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert meta["basis"] == "ledger"
    assert meta["formal_use_allowed"] is False
    assert meta["result_kind"] == "ledger_pnl.analysis"
    assert meta["cache_version"] == "cv_ledger_pnl_analysis_v1"
    assert meta["rule_version"] == "rv_ledger_pnl_analysis_v1"
    assert meta["cache_key"] == "ledger_pnl.analysis:2026-06-30:CNX"
    assert meta["fallback_mode"] == "none"
    assert meta["requested_report_date"] == "2026-06-30"
    assert meta["resolved_report_date"] == "2026-06-30"
    assert meta["filters_applied"]["currency_basis"] == "CNX"
    assert meta["evidence_rows"] == 2
    assert result["analysis_status"] == "ready"
    assert result["metric_status"] == "candidate"
    assert result["basis_availability"] == {"CNX": "ready", "CNY": "ready"}
    assert result["conclusion"]["core_pnl"] == {"yuan": "7", "yi": "0.00"}
    assert result["conclusion"]["other_5_pnl"] == {"yuan": "-2", "yi": "0.00"}
    assert result["conclusion"]["all_pnl"] == {"yuan": "5", "yi": "0.00"}
    assert result["pnl_bridge"]["residual"] == {"yuan": "0", "yi": "0.00"}
    assert result["period_comparison"]["status"] == "available"
    assert result["period_comparison"]["previous_report_date"] == "2026-05-31"
    assert result["period_comparison"]["previous_source_version"] == "sv_previous"

    def assert_no_decimal(value):
        assert not isinstance(value, Decimal)
        if isinstance(value, dict):
            for nested in value.values():
                assert_no_decimal(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_no_decimal(nested)

    assert_no_decimal(envelope)


def test_ledger_pnl_analysis_envelope_marks_missing_current_source_no_data(monkeypatch):
    class SourcePair:
        month_key = "202605"
        report_date = date(2026, 5, 31)
        source_version = "sv_previous"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [_fact("51400000001", "CNX", monthly_pnl="10")],
    )

    envelope = ledger_pnl_service.ledger_pnl_analysis_envelope(
        "unused",
        "2026-06-30",
        "CNX",
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert meta["quality_flag"] == "warning"
    assert meta["fallback_mode"] == "none"
    assert meta["source_version"] == "sv_ledger_pnl_empty"
    assert meta["requested_report_date"] == "2026-06-30"
    assert meta["resolved_report_date"] == "2026-06-30"
    assert meta["evidence_rows"] == 0
    assert result["analysis_status"] == "no_data"
    assert result["conclusion"]["direction"] == "unavailable"
    assert result["conclusion"]["core_pnl"] is None
    assert result["conclusion"]["other_5_pnl"] is None
    assert result["conclusion"]["all_pnl"] is None
    assert result["pnl_bridge"]["total"] is None
    assert result["contributors"]["net_total"] is None
    assert result["period_comparison"]["status"] == "current_basis_no_data"
    assert result["period_comparison"]["previous_report_date"] == "2026-05-31"


def test_ledger_pnl_analysis_envelope_rejects_nested_contract_drift(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [_fact("51400000001", "CNX", monthly_pnl="10")],
    )
    original_builder = ledger_pnl_service.build_ledger_pnl_analysis

    def build_with_unexpected_nested_field(**kwargs):
        payload = original_builder(**kwargs)
        payload["conclusion"]["unexpected_metric"] = "contract drift"
        return payload

    monkeypatch.setattr(
        ledger_pnl_service,
        "build_ledger_pnl_analysis",
        build_with_unexpected_nested_field,
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ledger_pnl_service.ledger_pnl_analysis_envelope(
            "unused",
            "2026-06-30",
            "CNX",
        )


def test_ledger_pnl_analysis_envelope_preserves_partial_balance_evidence(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [_fact("10100000001", "CNX", ending_balance="100")],
    )

    envelope = ledger_pnl_service.ledger_pnl_analysis_envelope(
        "unused",
        "2026-06-30",
        "CNX",
    )

    rows = {
        row["metric_key"]: row
        for row in envelope["result"]["basis_comparison"]
    }
    assert rows["assets"]["cnx"] == {"yuan": "100", "yi": "0.00"}
    assert rows["assets"]["availability"]["CNX"] == "ready"
    assert rows["liabilities"]["cnx"] is None
    assert rows["net_assets"]["cnx"] is None
    assert rows["net_assets"]["availability"]["CNX"] == "no_data"
    assert rows["net_assets"]["evidence_rows"]["CNX"] == 1


def test_ledger_pnl_analysis_envelope_requires_exact_month_end(monkeypatch):
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [],
    )

    with pytest.raises(
        ledger_pnl_service.LedgerPnlRequestError,
        match="month-end",
    ):
        ledger_pnl_service.ledger_pnl_analysis_envelope(
            "unused",
            "2026-06-29",
            "CNX",
        )


def test_ledger_pnl_account_detail_envelope_serializes_strict_candidate_contract(monkeypatch):
    class SourcePair:
        def __init__(self, month_key: str, report_date: date, source_version: str) -> None:
            self.month_key = month_key
            self.report_date = report_date
            self.source_version = source_version

    current_pair = SourcePair("202606", date(2026, 6, 30), "sv_current")
    previous_pair = SourcePair("202605", date(2026, 5, 31), "sv_previous")
    facts_by_month = {
        "202606": [
            _fact(
                "55000000001",
                "CNX",
                account_name="当期所得税",
                beginning_balance="100",
                ending_balance="90",
                monthly_pnl="-10",
                report_date=date(2026, 6, 30),
            ),
            _fact(
                "55000000001",
                "CNY",
                account_name="当期所得税",
                monthly_pnl="-8",
                report_date=date(2026, 6, 30),
            ),
        ],
        "202605": [
            _fact(
                "55000000001",
                "CNX",
                account_name="当期所得税",
                monthly_pnl="-7",
                report_date=date(2026, 5, 31),
            ),
            _fact(
                "55000000001",
                "CNY",
                account_name="当期所得税",
                monthly_pnl="-6",
                report_date=date(2026, 5, 31),
            ),
        ],
    }
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [previous_pair, current_pair],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda pair: facts_by_month[pair.month_key],
    )

    envelope = ledger_pnl_service.ledger_pnl_account_detail_envelope(
        "unused",
        "2026-06-30",
        "55000000001",
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert meta["basis"] == "ledger"
    assert meta["result_kind"] == "ledger_pnl.account_detail"
    assert meta["formal_use_allowed"] is False
    assert meta["cache_key"] == (
        "ledger_pnl.account_detail:2026-06-30:CNX:55000000001"
    )
    assert meta["fallback_mode"] == "none"
    assert meta["evidence_rows"] == 1
    assert meta["filters_applied"] == {
        "report_date": "2026-06-30",
        "account_code": "55000000001",
        "currency": "CNX",
        "currency_basis": "CNX",
        "currency_basis_note": "CNX=综本；CNY=人民币账",
    }
    assert result["period_comparison"]["current_monthly_pnl"] == {
        "yuan": "-10",
        "yi": "0.00",
    }
    assert result["period_comparison"]["change"] == {
        "yuan": "-3",
        "yi": "0.00",
    }
    assert result["basis_comparison"]["current"]["cnx_minus_cny"] == {
        "yuan": "-2",
        "yi": "0.00",
    }
    assert len(result["canonical_evidence_rows"]) == 4
    assert result["canonical_evidence_rows"][0]["beginning_balance"] == {
        "yuan": "100",
        "yi": "0.00",
    }
    assert "daily_avg_balance" not in result["canonical_evidence_rows"][0]
    assert "annual_avg_balance" not in result["canonical_evidence_rows"][0]


def test_ledger_pnl_account_detail_envelope_keeps_missing_account_as_no_data(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [
            _fact(
                "55000000001",
                "CNY",
                monthly_pnl="0",
                report_date=date(2026, 6, 30),
            )
        ],
    )

    envelope = ledger_pnl_service.ledger_pnl_account_detail_envelope(
        "unused",
        "2026-06-30",
        "55000000001",
        "CNX",
    )

    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["evidence_rows"] == 0
    assert envelope["result"]["analysis_status"] == "no_data"
    assert envelope["result"]["period_comparison"]["status"] == (
        "current_account_no_data"
    )
    assert envelope["result"]["period_comparison"]["current_monthly_pnl"] is None
    assert envelope["result"]["basis_comparison"]["current"]["availability"] == {
        "CNX": "no_data",
        "CNY": "ready",
    }
    assert len(envelope["result"]["canonical_evidence_rows"]) == 1


def test_ledger_pnl_account_detail_money_rejects_inconsistent_yi_mutation(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [
            _fact(
                "55000000001",
                "CNX",
                monthly_pnl="100000000",
                report_date=date(2026, 6, 30),
            )
        ],
    )
    envelope = ledger_pnl_service.ledger_pnl_account_detail_envelope(
        "unused",
        "2026-06-30",
        "55000000001",
        "CNX",
    )
    result = envelope["result"]
    result["period_comparison"]["current_monthly_pnl"]["yi"] = "999.99"
    result["basis_comparison"]["current"]["cnx"]["yi"] = "999.99"

    with pytest.raises(ValidationError, match="yi must equal yuan"):
        ledger_pnl_service.LedgerPnlAccountDetailEnvelope.model_validate(envelope)


def test_ledger_pnl_account_detail_envelope_rejects_contract_drift(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [
            _fact(
                "55000000001",
                "CNX",
                monthly_pnl="0",
                report_date=date(2026, 6, 30),
            )
        ],
    )
    original_builder = ledger_pnl_service.build_ledger_pnl_account_detail

    def build_with_unexpected_field(**kwargs):
        payload = original_builder(**kwargs)
        payload["period_comparison"]["unexpected_metric"] = "contract drift"
        return payload

    monkeypatch.setattr(
        ledger_pnl_service,
        "build_ledger_pnl_account_detail",
        build_with_unexpected_field,
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ledger_pnl_service.ledger_pnl_account_detail_envelope(
            "unused",
            "2026-06-30",
            "55000000001",
            "CNX",
        )


def test_ledger_pnl_account_detail_envelope_rejects_snapshot_evidence_drift(monkeypatch):
    class SourcePair:
        month_key = "202606"
        report_date = date(2026, 6, 30)
        source_version = "sv_current"

    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [SourcePair()],
    )
    monkeypatch.setattr(
        ledger_pnl_service,
        "build_canonical_facts",
        lambda _pair: [
            _fact(
                "55000000001",
                "CNX",
                monthly_pnl="10",
                report_date=date(2026, 6, 30),
            )
        ],
    )
    original_builder = ledger_pnl_service.build_ledger_pnl_account_detail

    def build_with_inconsistent_snapshot(**kwargs):
        payload = original_builder(**kwargs)
        payload["basis_comparison"]["current"]["cnx"] = Decimal("11")
        payload["period_comparison"]["current_monthly_pnl"] = Decimal("11")
        return payload

    monkeypatch.setattr(
        ledger_pnl_service,
        "build_ledger_pnl_account_detail",
        build_with_inconsistent_snapshot,
    )

    with pytest.raises(ValidationError, match="canonical evidence amount"):
        ledger_pnl_service.ledger_pnl_account_detail_envelope(
            "unused",
            "2026-06-30",
            "55000000001",
            "CNX",
        )


@pytest.mark.parametrize("account_code", ["550ABC", "4", "5", "5" + "1" * 32])
def test_ledger_pnl_account_detail_envelope_rejects_invalid_account_code(account_code):
    with pytest.raises(
        ledger_pnl_service.LedgerPnlRequestError,
        match="account_code",
    ):
        ledger_pnl_service.ledger_pnl_account_detail_envelope(
            "unused",
            "2026-06-30",
            account_code,
            "CNX",
        )


def test_ledger_pnl_account_detail_envelope_requires_exact_month_end(monkeypatch):
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _source_dir: [],
    )

    with pytest.raises(
        ledger_pnl_service.LedgerPnlRequestError,
        match="month-end",
    ):
        ledger_pnl_service.ledger_pnl_account_detail_envelope(
            "unused",
            "2026-06-29",
            "55000000001",
            "CNX",
        )
