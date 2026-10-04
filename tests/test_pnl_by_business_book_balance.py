from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services import pnl_service
from backend.app.services.pnl_service_by_business_support import _attach_pnl_by_business_balance_quality
from backend.app.tasks.pnl_by_business_precompute import _build_pnl_by_business_analysis_payloads_for_precompute


@pytest.mark.parametrize("dimension", ["monthly", "portfolio", "accounting", "currency", "cost_center", "instrument"])
def test_balance_only_holdings_reconcile_live_and_precomputed_drilldowns(dimension):
    common = {
        "report_date": "2025-01-01", "accounting_basis": "AC", "invest_type_std": "H",
        "currency_code": "CNY", "currency_basis": "CNY", "bond_type": "国债",
        "business_type_primary": "国债", "instrument_name": "国债测试券",
    }
    ordinary = {**common, "instrument_code": "BOND", "portfolio_name": "债券组合", "cost_center": "CC1",
                "avg_amount": Decimal("102"), "current_amount": Decimal("102")}
    voucher = {**common, "instrument_code": "VOUCHER", "portfolio_name": "凭证式国债组合", "cost_center": "CC2",
               "business_type_primary": "凭证式国债", "bond_type": "凭证式国债", "instrument_name": "凭证式国债",
               "avg_amount": Decimal("112"), "current_amount": Decimal("112")}
    kwargs = {
        "pnl_rows": [{**ordinary, "source_kind": "formal_fi", "interest_income_514": Decimal("10"),
                      "total_pnl": Decimal("10")}],
        "balance_rows": [ordinary, voucher], "loaded_dates": ["2025-01-01"],
        "period_start": "2025-01-01", "period_end": "2025-01-01", "ftp_rate_pct": Decimal("1.75"),
    }
    live = pnl_service._build_pnl_by_business_analysis_rows(
        **kwargs, business_key="asset_zqtz_treasury_bond", dimension=dimension
    )
    payloads = _build_pnl_by_business_analysis_payloads_for_precompute(**kwargs, year=2025, source_tables=[])
    cached = next(p.rows for p in payloads if p.business_key == "asset_zqtz_treasury_bond" and p.dimension == dimension)
    assert [r.model_dump() for r in live] == [r.model_dump() for r in cached]
    for rows in [live, cached]:
        assert sum(r.avg_balance for r in rows) == Decimal("214")
        assert sum(r.current_balance for r in rows) == Decimal("214")
        assert sum(r.total_pnl for r in rows) == Decimal("10")
        if dimension in {"portfolio", "cost_center", "instrument"}:
            balance_only, = [r for r in rows if r.total_pnl == 0]
            assert balance_only.avg_balance == Decimal("112")
            assert balance_only.ftp_cost > 0
            assert balance_only.ftp_net_pnl == -balance_only.ftp_cost


@pytest.mark.parametrize("report_date", ["2024-02-29", "2025-01-01", "2026-07-31", "2027-01-01"])
def test_business_daily_balance_uses_book_amount_with_interest_for_all_dates(tmp_path, report_date):
    path = tmp_path / "moss.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute("""
            create table fact_formal_zqtz_balance_daily (
                report_date date, instrument_code varchar, instrument_name varchar,
                portfolio_name varchar, cost_center varchar, accounting_basis varchar,
                business_type_primary varchar, currency_basis varchar, position_scope varchar,
                market_value_amount decimal(20, 4), amortized_cost_amount decimal(20, 4),
                face_value_amount decimal(20, 4), accrued_interest_amount decimal(20, 4)
            )
        """)
        for code, basis, category, market, cost, face, interest, currency, scope in [
            ("H", "AC", "国债", 130, 100, 110, 2, "CNY", "asset"),
            ("A", "FVOCI", "国债", 130, 100, 110, 2, "CNY", "asset"),
            ("T", "FVTPL", "国债", 130, 100, 110, 2, "CNY", "asset"),
            ("VOUCHER", "AC", "凭证式国债", 0, 0, 110, 2, "CNY", "asset"),
            ("ZERO_MARKET", "FVOCI", "外国债券", 0, 100, 110, 2, "CNY", "asset"),
            ("ZERO_COST", "AC", "国债", 130, 0, 110, 0, "CNY", "asset"),
            ("NO_INTEREST", "FVTPL", "国债", 130, 100, 110, None, "CNY", "asset"),
            ("NATIVE", "AC", "国债", 130, 100, 110, 2, "NATIVE", "asset"),
            ("LIABILITY", "AC", "国债", 130, 100, 110, 2, "CNY", "liability"),
        ]:
            conn.execute(
                "insert into fact_formal_zqtz_balance_daily values (?, ?, '', 'P', 'C', ?, ?, ?, ?, ?, ?, ?, ?)",
                [report_date, code, basis, category, currency, scope, market, cost, face, interest],
            )
    rows = PnlRepository(str(path)).fetch_by_business_analysis_balance_rows(
        start_date=report_date, end_date=report_date
    )
    expected = {"H": 102, "A": 132, "T": 132, "VOUCHER": 112, "ZERO_MARKET": 2, "ZERO_COST": 0, "NO_INTEREST": 130}
    assert {row["instrument_code"]: row["avg_amount"] for row in rows} == expected
    assert all(row["avg_amount"] == row["current_amount"] for row in rows)
    assert all(isinstance(row["avg_amount"], Decimal) for row in rows)


def _record_pending(governance_dir):
    event = {
        "scope": "pnl_by_business_balance", "issue_id": "zqtz-date-mismatch-2025-11-20",
        "report_date": "2025-11-20", "status": "pending", "reason": "源表日期为 11 月 19 日，余额与前日相同。",
        "source_file": "ZQTZSHOW-2025.11.20.xls", "source_version": "sv_test",
    }
    GovernanceRepository(base_dir=governance_dir).append("data_quality_remediation", event)
    return event


def test_source_review_overlays_cached_payload_and_resolution_clears_it(tmp_path):
    event = _record_pending(tmp_path)
    payload = {
        "year": 2025, "as_of_date": "2025-12-31", "months": [
            {"month_key": "2025-10", "period_start_date": "2025-10-01", "period_end_date": "2025-10-31"},
            {"month_key": "2025-11", "period_start_date": "2025-11-01", "period_end_date": "2025-11-30"},
        ],
        "management_change": {"current_month_key": "2025-12", "previous_month_key": "2025-11",
                              "comparison_available": True, "comparison_status": "available"},
    }
    result = _attach_pnl_by_business_balance_quality(governance_dir=str(tmp_path), payload=payload, resolved_report_date="2025-12-31")
    assert len(result["balance_quality_issues"]) == 1
    assert result["months"][0]["balance_quality_issues"] == []
    assert len(result["months"][1]["balance_quality_issues"]) == 1
    assert result["management_change"]["comparison_status"] == "data_quality_warning"
    assert result["management_change"]["balance_quality_warning_months"] == ["2025-11"]
    assert "balance_quality_issues" not in payload
    assert "balance_quality_issues" not in payload["months"][1]
    GovernanceRepository(base_dir=tmp_path).append("data_quality_remediation", {**event, "status": "resolved"})
    resolved = _attach_pnl_by_business_balance_quality(governance_dir=str(tmp_path), payload=payload, resolved_report_date="2025-12-31")
    assert resolved["balance_quality_issues"] == []
    assert resolved["management_change"]["comparison_status"] == "available"


@pytest.mark.parametrize("kind", ["pnl.by_business_ytd", "pnl.by_business_monthly", "pnl.by_business_analysis"])
@pytest.mark.parametrize("cutoff,expected", [("2025-10-31", "ok"), ("2025-12-31", "warning"), ("2026-07-31", "ok")])
def test_source_date_review_reaches_all_business_envelopes(tmp_path, monkeypatch, kind, cutoff, expected):
    _record_pending(tmp_path)
    monkeypatch.setattr(pnl_service, "_build_pnl_formal_result_envelope_from_lineage", lambda **kwargs: {
        "result": kwargs["result_payload"], "result_meta": {"quality_flag": kwargs["quality_flag"] or "ok"}
    })
    envelope = pnl_service._build_pnl_by_business_analytical_result_envelope(
        governance_dir=str(tmp_path), requested_report_date=cutoff, resolved_report_date=cutoff,
        trace_id="t", result_kind=kind, result_payload={"as_of_date": cutoff, "source_tables": []},
    )
    assert envelope["result_meta"]["quality_flag"] == expected
    assert bool(envelope["result"]["balance_quality_issues"]) == (expected == "warning")
