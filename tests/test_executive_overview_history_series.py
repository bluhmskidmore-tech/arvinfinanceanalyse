"""B-2：executive KPI history helpers 单元测试。"""

from __future__ import annotations

# Windows / Py3.14：与 test_executive_overview_history_field 一致，避免 SQLAlchemy import 阻塞
import platform as _platform

_platform.machine = lambda: "AMD64"  # type: ignore[method-assign, assignment]

import uuid

import pytest

from tests.helpers import load_module


def _exec_mod():
    return load_module(
        f"tests._exec_overview_hist_series.executive_service_{uuid.uuid4().hex}",
        "backend/app/services/executive_service.py",
    )


@pytest.fixture
def es():
    return _exec_mod()


def test_fetch_aum_history_happy_path_ordered(es):
    dates = ["2024-03-10", "2024-03-09", "2024-03-08", "2024-03-07", "2024-03-06"]
    amounts = {
        "2024-03-10": 10.0,
        "2024-03-09": 9.0,
        "2024-03-08": 8.0,
        "2024-03-07": 7.0,
        "2024-03-06": 6.0,
    }

    def fake_fetch(_repo, *, report_date: str, currency_basis: str = "CNY"):
        assert currency_basis == "CNY"
        return {"total_market_value_amount": amounts[report_date]}

    es._fetch_executive_aum_row = fake_fetch  # type: ignore[method-assign]
    repo = object()
    out = es._fetch_aum_history(repo, report_dates=dates, current_report_date="2024-03-10", n=20)
    assert out == [6.0, 7.0, 8.0, 9.0, 10.0]
    assert len(out) == 5
    assert all(type(x) is float for x in out)


def test_fetch_aum_history_skips_single_day_failure(es):
    dates = ["2024-03-10", "2024-03-09", "2024-03-08", "2024-03-07", "2024-03-06"]
    amounts = {
        "2024-03-10": 10.0,
        "2024-03-09": 9.0,
        "2024-03-08": 8.0,
        "2024-03-07": 7.0,
        "2024-03-06": 6.0,
    }

    def fake_fetch(_repo, *, report_date: str, currency_basis: str = "CNY"):
        if report_date == "2024-03-08":
            raise ValueError("simulated day failure")
        return {"total_market_value_amount": amounts[report_date]}

    es._fetch_executive_aum_row = fake_fetch  # type: ignore[method-assign]
    out = es._fetch_aum_history(object(), report_dates=dates, current_report_date="2024-03-10", n=20)
    assert out == [6.0, 7.0, 9.0, 10.0]
    assert len(out) == 4


def test_fetch_aum_history_all_days_fail_returns_none(es):
    def fake_fetch(_repo, *, report_date: str, currency_basis: str = "CNY"):
        raise RuntimeError("always fail")

    es._fetch_executive_aum_row = fake_fetch  # type: ignore[method-assign]
    out = es._fetch_aum_history(object(), report_dates=["2024-01-02", "2024-01-01"], current_report_date="2024-01-02")
    assert out is None


def test_fetch_aum_history_current_not_in_dates_returns_none(es):
    es._fetch_executive_aum_row = lambda *_a, **_k: {"total_market_value_amount": 1.0}  # type: ignore
    out = es._fetch_aum_history(
        object(),
        report_dates=["2024-01-02", "2024-01-01"],
        current_report_date="2024-01-03",
    )
    assert out is None


def test_fetch_ytd_history_cumulative_sequence(es):
    dates = ["2024-06-30", "2024-05-31", "2024-04-30"]
    cumulative = {"2024-06-30": 300e6, "2024-05-31": 200e6, "2024-04-30": 100e6}

    class _Pnl:
        def sum_formal_total_pnl_through_report_date(self, d: str) -> float:
            return cumulative[d]

    out = es._fetch_ytd_history(_Pnl(), report_dates=dates, current_report_date="2024-06-30", n=20)
    assert out == [100e6, 200e6, 300e6]
    assert all(isinstance(x, float) for x in out)


def test_fetch_ytd_history_all_fail_returns_none(es):
    class _Pnl:
        def sum_formal_total_pnl_through_report_date(self, _d: str):
            raise OSError("no db")

    out = es._fetch_ytd_history(_Pnl(), report_dates=["2024-01-01"], current_report_date="2024-01-01")
    assert out is None


def test_fetch_dv01_history_from_snapshots(es):
    dates = ["2024-02-02", "2024-02-01"]

    class _Bond:
        def fetch_risk_overview_snapshot(self, *, report_date: str):
            return {"portfolio_dv01": {"2024-02-02": 1.5, "2024-02-01": 2.5}[report_date]}

    out = es._fetch_dv01_history(_Bond(), report_dates=dates, current_report_date="2024-02-02", n=20)
    assert out == [2.5, 1.5]


def test_fetch_dv01_history_skips_none_snapshot(es):
    dates = ["2024-02-02", "2024-02-01", "2024-01-31"]

    class _Bond:
        def fetch_risk_overview_snapshot(self, *, report_date: str):
            if report_date == "2024-02-01":
                return None
            return {"portfolio_dv01": 99.0}

    out = es._fetch_dv01_history(_Bond(), report_dates=dates, current_report_date="2024-02-02", n=20)
    assert out == [99.0, 99.0]


def test_fetch_nim_history_uses_compute_kpi(es, monkeypatch):
    dates = ["2024-03-03", "2024-03-02", "2024-03-01"]

    class _Liab:
        def fetch_zqtz_rows(self, _d: str):
            return []

        def fetch_tyw_rows(self, _d: str):
            return []

    def fake_compute(report_date: str, _zqtz, _tyw):
        return {"kpi": {"nim": {"2024-03-03": 0.003, "2024-03-02": 0.002, "2024-03-01": 0.001}[report_date]}}

    monkeypatch.setattr(es, "compute_liability_yield_metrics", fake_compute)
    out = es._fetch_nim_history(_Liab(), report_dates=dates, current_report_date="2024-03-03", n=20)
    assert out == [0.001, 0.002, 0.003]


def test_fetch_nim_history_day_exception_skipped(es, monkeypatch):
    dates = ["2024-03-03", "2024-03-02"]

    class _Liab:
        def fetch_zqtz_rows(self, d: str):
            if d == "2024-03-02":
                raise RuntimeError("bad row fetch")
            return []

        def fetch_tyw_rows(self, _d: str):
            return []

    monkeypatch.setattr(
        es,
        "compute_liability_yield_metrics",
        lambda _d, _z, _t: {"kpi": {"nim": 0.001}},
    )
    out = es._fetch_nim_history(_Liab(), report_dates=dates, current_report_date="2024-03-03", n=20)
    assert out == [0.001]


def test_fetch_nim_history_current_missing_returns_none(es, monkeypatch):
    monkeypatch.setattr(
        es,
        "compute_liability_yield_metrics",
        lambda _d, _z, _t: {"kpi": {"nim": 0.001}},
    )

    class _Liab:
        def fetch_zqtz_rows(self, _d: str):
            return []

        def fetch_tyw_rows(self, _d: str):
            return []

    out = es._fetch_nim_history(
        _Liab(),
        report_dates=["2024-03-03", "2024-03-02"],
        current_report_date="2024-03-04",
    )
    assert out is None
