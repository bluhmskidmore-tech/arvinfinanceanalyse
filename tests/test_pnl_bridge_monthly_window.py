from __future__ import annotations

from importlib import import_module
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.services import campisi_attribution_service as campisi


def _active_bridge():
    return import_module("backend.app.services.pnl_bridge_service")


@pytest.fixture
def monthly_sources(monkeypatch):
    bridge = _active_bridge()
    calls = {"balance": [], "curves": []}
    dates = ["2026-07-31", "2026-08-30", "2026-08-31"]
    pnl = {
        "report_date": "2026-08-31", "instrument_code": "MONTHLY",
        "portfolio_name": "BOOK", "cost_center": "DESK", "currency_basis": "CNY",
        "accounting_basis": "AC", "interest_income_514": Decimal("31.25"),
        "fair_value_change_516": Decimal("0"), "capital_gain_517": Decimal("0"),
        "manual_adjustment": Decimal("0"), "total_pnl": Decimal("31.25"),
    }

    def balance_rows(*, report_date):
        calls["balance"].append(report_date)
        if report_date not in dates:
            return []
        return [{
            **pnl, "report_date": report_date,
            "market_value_amount": Decimal("1000") if report_date < "2026-08-01" else Decimal("2000"),
            "accrued_interest_amount": Decimal("2.5"), "maturity_date": "2030-08-31",
            "coupon_rate": Decimal("0.03"), "ytm_value": Decimal("0.03"),
        }]

    def prior_date(*, report_date):
        calls["prior_request"] = report_date
        return max((d for d in dates if d < report_date), default=None)

    def curves(**kwargs):
        calls["curves"].append((kwargs["prior_date"], kwargs["report_date"]))
        return None, None

    monkeypatch.setattr(bridge, "PnlRepository", lambda _: SimpleNamespace(
        list_formal_fi_report_dates=lambda: ["2026-08-31"],
        fetch_formal_fi_rows=lambda _: [pnl],
    ))
    monkeypatch.setattr(bridge, "BalanceAnalysisRepository", lambda _: SimpleNamespace(
        fetch_pnl_bridge_zqtz_balance_rows=balance_rows,
        resolve_prior_pnl_bridge_balance_report_date=prior_date,
        resolve_formal_fx_mid_rates_map=lambda **_: {},
    ))
    monkeypatch.setattr(bridge, "YieldCurveRepository", lambda _: SimpleNamespace())
    monkeypatch.setattr(bridge, "_attach_native_exposure_fields", lambda **kw: kw["balance_rows"])
    monkeypatch.setattr(bridge, "_resolve_curve_pair_if_needed", curves)
    monkeypatch.setattr(bridge, "_resolve_bridge_lineage", lambda **_: ({
        "source_version": "sv_monthly", "rule_version": "rv_monthly", "vendor_version": "vv_monthly",
    }, []))
    return dates, calls


def _read_bridge():
    return _active_bridge().pnl_bridge_envelope(duckdb_path="unused", governance_dir="unused", report_date="2026-08-31")


def test_monthly_pnl_uses_previous_month_end_not_previous_day(monthly_sources):
    _, calls = monthly_sources
    envelope = _read_bridge()
    assert calls["prior_request"] == "2026-08-01"
    assert calls["balance"] == ["2026-08-31", "2026-07-31"]
    assert calls["curves"] == [("2026-07-31", "2026-08-31")] * 3
    result = envelope["result"]
    assert Decimal(result["summary"]["total_beginning_dirty_mv"]["raw_text"]) == Decimal("1002.5")
    assert Decimal(result["summary"]["total_actual_pnl"]["raw_text"]) == Decimal("31.25")
    filters = envelope["result_meta"]["filters_applied"]
    assert filters["pnl_window"] == {"start": "2026-08-01", "end": "2026-08-31", "kind": "monthly_period"}
    assert filters["balance_window"] == {"start": "2026-07-31", "end": "2026-08-31"}
    assert filters["expected_balance_start"] == "2026-07-31"
    assert filters["window_aligned"] is True


@pytest.mark.parametrize("prior", [None, "2026-07-30"])
def test_missing_month_end_is_disclosed_not_replaced_by_august_day(monthly_sources, prior):
    dates, calls = monthly_sources
    dates[:] = [d for d in dates if d != "2026-07-31"]
    if prior:
        dates.append(prior)
    envelope = _read_bridge()
    filters = envelope["result_meta"]["filters_applied"]
    assert filters["balance_window"]["start"] == prior
    assert filters["window_aligned"] is False
    assert envelope["result_meta"]["quality_flag"] in {"warning", "stale", "error"}
    assert any("PNL_BRIDGE_WINDOW_MISMATCH" in w for w in envelope["result"]["warnings"])
    assert "2026-08-30" not in calls["balance"]


def test_campisi_accepts_exact_monthly_window(monthly_sources):
    envelope = campisi._fetch_formal_bridge(
        settings=SimpleNamespace(duckdb_path="unused", governance_path="unused"),
        report_date="2026-08-31", start_date="2026-07-31",
    )
    assert envelope["result_meta"]["filters_applied"]["window_aligned"] is True


@pytest.mark.parametrize("start", ["2026-08-30", "2026-08-01", "2025-12-31"])
def test_campisi_does_not_relabel_monthly_pnl_as_different_period(monthly_sources, start):
    with pytest.raises(ValueError, match="PNL_BRIDGE_WINDOW_MISMATCH"):
        campisi._fetch_formal_bridge(
            settings=SimpleNamespace(duckdb_path="unused", governance_path="unused"),
            report_date="2026-08-31", start_date=start,
        )


def test_bridge_cache_separates_requested_start_dates():
    args = dict(duckdb_path="db", governance_path="gov", duckdb_fingerprint=(),
                governance_fingerprint=(), report_date="2026-08-31")
    assert campisi._campisi_bridge_cache_key(**args, start_date="2026-07-31") != campisi._campisi_bridge_cache_key(
        **args, start_date="2026-08-30",
    )


def test_mismatched_period_cannot_be_reported_as_closed(monthly_sources):
    closure = campisi._fetch_formal_closure(
        settings=SimpleNamespace(duckdb_path="unused", governance_path="unused"),
        report_date="2026-08-31", start_date="2026-08-30", campisi_total_return=Decimal("31.25"),
    )
    assert closure["status"] == "unavailable"
    assert closure["formal_actual_pnl"] is None
    assert "PNL_BRIDGE_WINDOW_MISMATCH" in closure["message"]


def test_missing_exact_baseline_cannot_be_reported_as_aligned(monthly_sources):
    dates, _ = monthly_sources
    dates.remove("2026-07-31")
    with pytest.raises(ValueError, match="PNL_BRIDGE_WINDOW_MISMATCH"):
        campisi._fetch_formal_bridge(
            settings=SimpleNamespace(duckdb_path="unused", governance_path="unused"),
            report_date="2026-08-31", start_date="2026-07-31",
        )


@pytest.mark.parametrize("endpoint", [
    campisi.campisi_four_effects_envelope, campisi.campisi_enhanced_envelope,
    campisi.campisi_maturity_bucket_envelope,
])
@pytest.mark.parametrize("start,end", [
    ("2025-12-31", "2026-01-31"), ("2026-01-31", "2026-02-28"),
    ("2024-01-31", "2024-02-29"), ("2026-07-31", "2026-08-31"),
])
def test_all_campisi_consumers_pass_period_and_preserve_source_quality(monkeypatch, endpoint, start, end):
    from tests.test_campisi_attribution_service import _bond_row, _install_full_service_fakes
    from tests.test_campisi_upstream_quality_propagation import _bridge

    row = _bond_row(code="QUALITY-01.IB", market_value=Decimal("1000"))
    _install_full_service_fakes(monkeypatch, dates=[end, start], rows_by_date={start: [row], end: [row]}, curves={})
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return _bridge({
            "quality_flag": "error", "vendor_status": "ok", "fallback_mode": "none",
            "filters_applied": {"balance_window": {"start": start, "end": end}, "window_aligned": True},
        })

    monkeypatch.setattr(campisi, "_fetch_formal_bridge", fetch)
    envelope = endpoint(start_date=start, end_date=end)
    assert calls[0]["start_date"] == start
    assert calls[0]["report_date"] == end
    assert envelope["result"]["period_start"] == start
    assert envelope["result"]["period_end"] == end
    assert envelope["result_meta"]["filters_applied"]["balance_window"] == {"start": start, "end": end}
    assert envelope["result_meta"]["quality_flag"] == "error"
