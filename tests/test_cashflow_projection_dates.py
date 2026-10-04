from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.core_finance.cashflow_projection import (
    project_bond_cashflows,
    project_liability_cashflows,
    project_zqtz_cashflows,
)
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor


@pytest.mark.parametrize("project", [project_bond_cashflows, project_zqtz_cashflows])
@pytest.mark.parametrize(
    ("maturity", "mode", "expected"),
    [
        (date(2028, 8, 31), "semi-annual", ["2026-02-28", "2026-08-31", "2027-02-28", "2027-08-31", "2028-02-29", "2028-08-31"]),
        (date(2028, 8, 30), "semi-annual", ["2026-02-28", "2026-08-30", "2027-02-28", "2027-08-30", "2028-02-29", "2028-08-30"]),
        (date(2027, 2, 28), "quarterly", ["2026-02-28", "2026-05-28", "2026-08-28", "2026-11-28", "2027-02-28"]),
        (date(2027, 8, 31), "quarterly", ["2026-02-28", "2026-05-31", "2026-08-31", "2026-11-30", "2027-02-28", "2027-05-31", "2027-08-31"]),
    ],
)
def test_coupon_dates_preserve_original_maturity_anchor(project, maturity, mode, expected):
    row = {
        "instrument_code": "SYNTH-ANCHOR", "position_scope": "asset",
        "maturity_date": maturity, "face_value": Decimal("100"),
        "coupon_rate": Decimal("6"), "interest_mode": mode,
    }
    events = project([row], date(2026, 1, 1), horizon_months=36)
    coupons = [event for event in events if event.event_type == "coupon"]
    assert [event.event_date.isoformat() for event in coupons] == expected
    assert [event.amount for event in coupons] == [Decimal("1.5") if mode == "quarterly" else Decimal("3")] * len(expected)
    assert [(event.event_date, event.amount) for event in events if event.event_type == "principal"] == [(maturity, Decimal("100"))]


def test_bond_cashflows_reconcile_adjacent_date_windows():
    row = {
        "instrument_code": "SYNTH-SPLIT", "maturity_date": date(2028, 8, 31),
        "face_value": Decimal("100000000"), "coupon_rate": Decimal("6"),
        "interest_mode": "semi-annual",
    }
    whole = project_bond_cashflows([row], date(2026, 2, 28), horizon_months=30)
    first = project_bond_cashflows([row], date(2026, 2, 28), horizon_months=12)
    second = project_bond_cashflows([row], date(2027, 2, 28), horizon_months=18)
    assert first + second == whole
    assert [event.event_date for event in first] == [date(2026, 8, 31), date(2027, 2, 28)]


@pytest.mark.parametrize("days_before_coupon", [0, 2, 30, 31, 90, 91])
def test_risk_tensor_eom_coupon_respects_closed_30_and_90_day_windows(days_before_coupon):
    report = date(2026, 8, 31) - timedelta(days=days_before_coupon)
    row = {
        "instrument_code": "SYNTH-EOM", "maturity_date": date(2028, 8, 31),
        "face_value": Decimal("100000000"), "market_value": Decimal("100000000"),
        "coupon_rate": Decimal("0.06"), "interest_mode": "semi-annual",
    }
    tensor = compute_portfolio_risk_tensor([row], report_date=report)
    expected_30d = Decimal("3000000") if days_before_coupon <= 30 else Decimal("0")
    expected_90d = Decimal("3000000") if days_before_coupon <= 90 else Decimal("0")
    assert tensor.asset_cashflow_30d == tensor.liquidity_gap_30d == expected_30d
    assert tensor.asset_cashflow_90d == tensor.liquidity_gap_90d == expected_90d


@pytest.mark.parametrize("days_to_maturity", [0, 30, 31, 90, 91])
@pytest.mark.parametrize("funding_rate", [Decimal("10"), Decimal("0"), None])
def test_liability_windows_keep_real_report_date_as_interest_start(days_to_maturity, funding_rate):
    report = date(2026, 1, 1)
    row = {
        "position_id": "SYNTH-LIAB", "position_side": "liability",
        "maturity_date": report + timedelta(days=days_to_maturity),
        "principal_amount": Decimal("365000000"), "funding_cost_rate": funding_rate,
        "currency_code": "CNY",
    }
    expected = Decimal("365000000") + Decimal("100000") * days_to_maturity if funding_rate else Decimal("365000000")
    tensor = compute_portfolio_risk_tensor([], report_date=report, liability_rows=[row])
    assert tensor.liability_cashflow_30d == (expected if days_to_maturity <= 30 else 0)
    assert tensor.liability_cashflow_90d == (expected if days_to_maturity <= 90 else 0)
    projected = project_liability_cashflows([row], report, include_report_date=True)
    assert -sum(event.amount for event in projected) == expected
    assert len([event for event in projected if event.event_type == "maturity"]) == 1
    if days_to_maturity:
        assert projected == project_liability_cashflows([row], report)
    else:
        assert project_liability_cashflows([row], report) == []
        assert len(projected) == 1
    assert tensor.liquidity_gap_30d == -tensor.liability_cashflow_30d
    assert tensor.liquidity_gap_90d == -tensor.liability_cashflow_90d


def test_cashflow_service_leap_report_date_clamps_one_year_window(tmp_path, monkeypatch):
    from backend.app.governance.settings import get_settings
    from backend.app.services import cashflow_projection_service as service

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "leap-report.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    rows = [
        {
            "instrument_code": code, "position_scope": "asset",
            "maturity_date": maturity, "face_value_amount": Decimal("100"),
            "market_value_amount": Decimal("100"), "coupon_rate": Decimal("0"),
            "interest_mode": "annual", "currency_code": "CNY",
            "source_version": "sv_leap_report", "rule_version": "rv_leap_report",
        }
        for code, maturity in [
            ("report-day", date(2028, 2, 29)),
            ("tomorrow", date(2028, 3, 1)),
            ("boundary", date(2029, 2, 28)),
            ("outside", date(2029, 3, 1)),
        ]
    ]
    monkeypatch.setattr(service.CashflowProjectionRepository, "fetch_formal_zqtz_rows", lambda *_args, **_kwargs: rows)
    monkeypatch.setattr(service.CashflowProjectionRepository, "fetch_formal_tyw_liability_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service.BondAnalyticsRepository, "fetch_bond_analytics_rows", lambda *_args, **_kwargs: [])
    try:
        envelope = service.get_cashflow_projection(date(2028, 2, 29))
        assert envelope["result"]["report_date"] == "2028-02-29"
        assert [(row["instrument_code"], row["maturity_date"]) for row in envelope["result"]["top_maturing_assets_12m"]] == [
            ("tomorrow", "2028-03-01"), ("boundary", "2029-02-28")
        ]
        assert envelope["result_meta"]["requested_report_date"] == "2028-02-29"
        assert envelope["result_meta"]["resolved_report_date"] == "2028-02-29"
    finally:
        get_settings.cache_clear()
