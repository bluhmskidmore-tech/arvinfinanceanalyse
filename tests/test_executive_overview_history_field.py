"""executive_overview 序列化契约：每条 metric 均含 history 字段（B-1 占位）。"""

from __future__ import annotations

# Windows / Py3.14: 与 test_executive_service_contract 一致，避免 SQLAlchemy import 阻塞
import platform as _platform

_platform.machine = lambda: "AMD64"  # type: ignore[method-assign, assignment]

import datetime as dt
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _exec_service_module():
    return load_module(
        f"tests._exec_overview_history.executive_service_{uuid.uuid4().hex}",
        "backend/app/services/executive_service.py",
    )


def _fake_settings(tmp_path):
    return SimpleNamespace(
        duckdb_path=str(tmp_path / "x.duckdb"),
        governance_path=Path(tmp_path / "governance"),
    )


@pytest.fixture
def exec_mod(monkeypatch, tmp_path):
    mod = _exec_service_module()
    monkeypatch.setattr(mod, "get_settings", lambda: _fake_settings(tmp_path))
    return mod


def test_executive_overview_metrics_include_history_json_field(exec_mod, monkeypatch):
    """repo-backed 路径下每条 metric 的 JSON 均含 history（None 或 list）。"""

    class OkFormal:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2030-03-15", "2030-02-28"]

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            assert currency_basis == "CNY"
            values = {
                "2030-03-15": 1023.47e8,
                "2030-02-28": 1000.00e8,
            }
            return {"report_date": report_date, "total_market_value_amount": values[report_date]}

    class OkPnl:
        def __init__(self, *_a, **_k):
            pass

        def list_formal_fi_report_dates(self):
            return ["2030-03-15", "2030-02-28"]

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            values = {
                "2030-03-15": 12.63e8,
                "2030-02-28": 11.62e8,
            }
            return values[report_date]

    class OkLiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def resolve_latest_report_date(self):
            return "2030-03-15"

        def list_report_dates(self):
            return ["2030-03-15", "2030-02-28"]

        def fetch_zqtz_rows(self, report_date: str):
            assert report_date in {"2030-03-15", "2030-02-28"}
            return [{"source_version": "sv-liab-z", "rule_version": "rv-liab"}]

        def fetch_tyw_rows(self, report_date: str):
            assert report_date in {"2030-03-15", "2030-02-28"}
            return [{"source_version": "sv-liab-t", "rule_version": "rv-liab"}]

    class OkBondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2030-03-15", "2030-02-28"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            values = {
                "2030-03-15": 1234567.8,
                "2030-02-28": 1000000.0,
            }
            return {
                "report_date": report_date,
                "portfolio_dv01": values[report_date],
            }

    class FixedDate:
        today = staticmethod(lambda: dt.date(2030, 3, 15))
        fromisoformat = staticmethod(dt.date.fromisoformat)

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", OkFormal)
    monkeypatch.setattr(exec_mod, "PnlRepository", OkPnl)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", OkLiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", OkBondRepo)
    monkeypatch.setattr(
        exec_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: {
            "source_version": "sv_pnl_formal",
            "rule_version": "rv_pnl_formal",
            "cache_version": "cv_pnl_formal",
            "vendor_version": "vv_none",
            "report_date": kwargs["report_date"],
        },
        raising=False,
    )
    monkeypatch.setattr(
        exec_mod,
        "load_latest_bond_analytics_lineage",
        lambda **kwargs: {
            "source_version": "sv_bond_analytics",
            "rule_version": "rv_bond_analytics",
            "cache_version": "cv_bond_analytics",
            "vendor_version": "vv_none",
        },
        raising=False,
    )
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 2.45,
                "liability_cost": 2.07,
                "market_liability_cost": 2.07,
                "nim": 0.38 if report_date == "2030-03-15" else 0.33,
            },
        },
    )
    monkeypatch.setattr(
        exec_mod,
        "resolve_kpi_authority_gate",
        lambda **_kwargs: {"status": "blocked", "reason": "test", "owner_count": 0, "year": None},
    )
    monkeypatch.setattr(exec_mod, "date", FixedDate)

    out = exec_mod.executive_overview(report_date=None)
    metrics = out["result"]["metrics"]
    assert isinstance(metrics, list)
    assert len(metrics) >= 1
    for m in metrics:
        assert isinstance(m, dict)
        assert "history" in m
        h = m["history"]
        assert h is None or isinstance(h, list)

    def _is_numeric_scalar(x: object) -> bool:
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    non_none_histories = [m["history"] for m in metrics if m.get("history") is not None]
    for h in non_none_histories:
        assert isinstance(h, list)
        assert all(_is_numeric_scalar(x) for x in h)
        assert all(not isinstance(x, str) for x in h)

    has_any_history = bool(non_none_histories)
    if has_any_history:
        assert any(isinstance(h, list) and len(h) >= 2 for h in non_none_histories), (
            "在有两日以上报告期的 mock 下，至少一条 history 应含 2+ 个点"
        )
