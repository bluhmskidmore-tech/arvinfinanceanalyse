"""Contract tests for executive dashboard service (fallback vs repo-backed, result_meta)."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories.formal_zqtz_balance_metrics_repo import FormalZqtzBalanceMetricsRepository
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
from tests.helpers import load_module


def _exec_service_module():
    """Fresh load of executive_service for patching (avoids mutating canonical import)."""
    return load_module(
        f"tests._exec_service_contract.executive_service_{uuid.uuid4().hex}",
        "backend/app/services/executive_service.py",
    )


def _fake_settings(tmp_path):
    ns = SimpleNamespace(
        duckdb_path=str(tmp_path / "x.duckdb"),
        governance_path=Path(tmp_path / "governance"),
    )
    return ns


@pytest.fixture
def exec_mod(monkeypatch, tmp_path):
    mod = _exec_service_module()
    monkeypatch.setattr(mod, "get_settings", lambda: _fake_settings(tmp_path))
    return mod


def _assert_analytical_meta(meta: dict) -> None:
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False


def test_executive_lineage_tokens_split_dirty_comma_separated_values(exec_mod):
    tokens = exec_mod._lineage_tokens(
        "sv_clean_a__sv_dirty_a,sv_dirty_b",
        "sv_dirty_b",
        "sv_clean_c, sv_clean_d",
    )

    assert tokens == [
        "sv_clean_a",
        "sv_clean_c",
        "sv_clean_d",
        "sv_dirty_a",
        "sv_dirty_b",
    ]


def test_executive_summary_static_contract(exec_mod):
    out = exec_mod.executive_summary()
    meta = out["result_meta"]
    _assert_analytical_meta(meta)
    assert meta["result_kind"] == "executive.summary"
    res = out["result"]
    assert res["title"] == "本周管理摘要"
    assert "受控摘要" in res["narrative"]
    assert len(res["points"]) == 3
    labels = {p["label"] for p in res["points"]}
    assert labels == {"收益", "风险", "建议"}
    texts = " ".join(p["text"] for p in res["points"])
    assert "票息" in texts or "利率" in texts
    assert "集中度" in texts or "暴露" in texts


def test_executive_summary_uses_overview_lineage_when_available(monkeypatch, exec_mod):
    monkeypatch.setattr(
        exec_mod,
        "executive_overview",
        lambda report_date=None: {
            "result_meta": {
                "source_version": "sv_summary_dep_a__sv_summary_dep_b",
                "rule_version": "rv_summary_dep_a__rv_summary_dep_b",
                "vendor_status": "ok",
            },
            "result": {"metrics": []},
        },
    )

    out = exec_mod.executive_summary()

    assert out["result_meta"]["source_version"] == "sv_summary_dep_a__sv_summary_dep_b"
    assert out["result_meta"]["rule_version"] == "rv_summary_dep_a__rv_summary_dep_b"


def test_executive_overview_fallback_when_repos_fail(monkeypatch, exec_mod):
    class BadFormal:
        def __init__(self, *_a, **_k):
            pass

        def fetch_latest_zqtz_asset_market_value(self, **_k):
            raise RuntimeError("duck")

    class BadPnl:
        def __init__(self, *_a, **_k):
            pass

        def sum_formal_total_pnl_for_year(self, *_a, **_k):
            raise RuntimeError("duck")

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", BadFormal)
    monkeypatch.setattr(exec_mod, "PnlRepository", BadPnl)
    out = exec_mod.executive_overview()
    meta = out["result_meta"]
    _assert_analytical_meta(meta)
    assert meta["result_kind"] == "executive.overview"
    assert meta["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert meta["vendor_status"] == "vendor_unavailable"
    assert out["result"]["metrics"] == []


def test_executive_overview_repo_backed_contract(monkeypatch, exec_mod):
    class OkFormal:
        def __init__(self, *_a, **_k):
            pass

        def fetch_latest_zqtz_asset_market_value(self, **_k):
            return {"total_market_value_amount": 1023.47e8}

        def list_report_dates(self):
            return ["2030-03-15", "2030-02-28"]

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            assert currency_basis == "CNY"
            values = {
                "2030-03-15": 1023.47e8,
                "2030-02-28": 1000.00e8,
            }
            return {"report_date": report_date, "total_market_value_amount": values[report_date]}

        def fetch_formal_overview(self, **kwargs):
            values = {
                "2030-03-15": 1023.47e8,
                "2030-02-28": 1000.00e8,
            }
            return {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "detail_row_count": 10,
                "summary_row_count": 10,
                "total_market_value_amount": values[kwargs["report_date"]],
                "total_amortized_cost_amount": values[kwargs["report_date"]],
                "total_accrued_interest_amount": 0.0,
                "source_version": "sv_balance_union",
                "rule_version": "rv_balance_union",
            }

    class OkPnl:
        def __init__(self, *_a, **_k):
            pass

        def sum_formal_total_pnl_for_year(self, year: int):
            assert year == 2030
            return 12.63e8

        def list_union_report_dates(self):
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

        def fetch_latest_risk_overview_snapshot(self):
            return {
                "report_date": "2030-03-15",
                "portfolio_dv01": 1234567.8,
            }

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
        "resolve_executive_kpi_metrics",
        lambda **_kwargs: [
            {
                "id": "goal",
                "label": "目标完成率",
                "value": "92.20%",
                "delta": "governed",
                "tone": "positive",
                "detail": "来自 KPI 年度汇总读面。",
            },
            {
                "id": "risk-budget",
                "label": "风险预算使用率",
                "value": "88.00%",
                "delta": "governed",
                "tone": "warning",
                "detail": "来自 KPI 年度汇总读面。",
            },
        ],
    )
    monkeypatch.setattr(exec_mod, "date", FixedDate)

    out = exec_mod.executive_overview()
    assert out["result_meta"]["result_kind"] == "executive.overview"
    assert out["result_meta"]["source_version"] == (
        "sv-liab-t__sv-liab-z__sv_balance_union__sv_bond_analytics__sv_exec_dashboard_v1__sv_pnl_formal"
    )
    assert out["result_meta"]["rule_version"] == (
        "rv-liab__rv_balance_union__rv_bond_analytics__rv_exec_dashboard_v1__rv_pnl_formal"
    )
    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert set(metrics) == {"aum", "yield", "nim", "dv01", "goal", "risk-budget"}
    assert metrics["aum"]["value"] == "1,023.47 亿"
    assert metrics["yield"]["value"] == "+12.63 亿"
    assert metrics["nim"]["value"] == "+0.38%"
    assert metrics["dv01"]["value"] == "1,234,568"
    assert metrics["aum"]["delta"] == "+2.35%"
    assert metrics["yield"]["delta"] == "+8.69%"
    assert metrics["nim"]["delta"] == "+0.05pp"
    assert metrics["dv01"]["delta"] == "+23.46%"
    assert metrics["goal"]["value"] == "92.20%"
    assert metrics["risk-budget"]["value"] == "88.00%"
    assert "fact_formal_zqtz_balance_daily" in metrics["aum"]["detail"]
    assert "截至 2030-03-15" in metrics["yield"]["detail"]
    assert "nim" in metrics["nim"]["detail"].lower()
    assert "DV01" in metrics["dv01"]["detail"]


def test_executive_overview_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, object]] = []

    class FormalRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-11-20", "2025-10-31"]

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            calls.append(("aum", report_date))
            assert currency_basis == "CNY"
            values = {
                "2025-11-20": 321.0e8,
                "2025-10-31": 300.0e8,
            }
            return {"report_date": report_date, "total_market_value_amount": values[report_date]}

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_union_report_dates(self):
            return ["2025-11-20", "2025-10-31"]

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            calls.append(("pnl", report_date))
            values = {
                "2025-11-20": 6.5e8,
                "2025-10-31": 5.0e8,
            }
            return values[report_date]

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-11-20", "2025-10-31"]

        def fetch_zqtz_rows(self, report_date: str):
            calls.append(("liab-z", report_date))
            return [{"source_version": "sv-liab-z", "rule_version": "rv-liab"}]

        def fetch_tyw_rows(self, report_date: str):
            calls.append(("liab-t", report_date))
            return [{"source_version": "sv-liab-t", "rule_version": "rv-liab"}]

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-11-20", "2025-10-31"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            calls.append(("risk", report_date))
            return {
                "report_date": report_date,
                "portfolio_dv01": 456789.0 if report_date == "2025-11-20" else 400000.0,
            }

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", FormalRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {
                "nim": 0.25 if report_date == "2025-11-20" else 0.20,
            },
        },
    )

    out = exec_mod.executive_overview(report_date="2025-11-20")

    assert calls == [
        ("aum", "2025-11-20"),
        ("aum", "2025-10-31"),
        ("pnl", "2025-11-20"),
        ("pnl", "2025-10-31"),
        ("liab-z", "2025-11-20"),
        ("liab-t", "2025-11-20"),
        ("liab-z", "2025-10-31"),
        ("liab-t", "2025-10-31"),
        ("risk", "2025-11-20"),
        ("risk", "2025-10-31"),
    ]
    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert "2025-11-20" in metrics["aum"]["detail"]
    assert "截至 2025-11-20" in metrics["yield"]["detail"]
    assert "2025-11-20" in metrics["nim"]["detail"]
    assert "2025-11-20" in metrics["dv01"]["detail"]
    assert metrics["aum"]["delta"] == "+7.00%"
    assert metrics["yield"]["delta"] == "+30.00%"
    assert metrics["nim"]["delta"] == "+0.05pp"
    assert metrics["dv01"]["delta"] == "+14.20%"


def test_executive_overview_without_report_date_uses_latest_governed_pnl_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, str]] = []

    class BalanceRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-12-31"]

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            calls.append(("aum", report_date))
            return {"report_date": report_date, "total_market_value_amount": 321.0e8}

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_union_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def sum_formal_total_pnl_for_year(self, year: int):
            raise AssertionError("wall-clock year path should not be used when latest governed report date exists")

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            calls.append(("pnl", report_date))
            values = {
                "2025-12-31": 6.5e8,
                "2025-11-30": 5.0e8,
            }
            return values[report_date]

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def resolve_latest_report_date(self):
            return "2025-12-31"

        def fetch_zqtz_rows(self, report_date: str):
            calls.append(("liab-z", report_date))
            return [{"source_version": "sv-liab-z", "rule_version": "rv-liab"}]

        def fetch_tyw_rows(self, report_date: str):
            calls.append(("liab-t", report_date))
            return [{"source_version": "sv-liab-t", "rule_version": "rv-liab"}]

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def fetch_latest_risk_overview_snapshot(self):
            calls.append(("risk", "2025-12-31"))
            return {
                "report_date": "2025-12-31",
                "portfolio_dv01": 456789.0,
            }

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            calls.append(("risk", report_date))
            return {
                "report_date": report_date,
                "portfolio_dv01": 456789.0 if report_date == "2025-12-31" else 400000.0,
            }

    class FixedDate:
        today = staticmethod(lambda: dt.date(2030, 3, 15))
        fromisoformat = staticmethod(dt.date.fromisoformat)

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", BalanceRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {
                "nim": 0.25 if report_date == "2025-12-31" else 0.20,
            },
        },
    )
    monkeypatch.setattr(exec_mod, "date", FixedDate)

    out = exec_mod.executive_overview()

    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["yield"]["value"] == "+6.50 亿"
    assert "2025-12-31" in metrics["yield"]["detail"]
    assert calls.count(("pnl", "2025-12-31")) == 1
    assert calls.count(("pnl", "2025-11-30")) == 1


def test_executive_overview_uses_latest_formal_fi_date_not_union_date_for_yield(monkeypatch, exec_mod):
    calls: list[tuple[str, str]] = []

    class BalanceRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self, currency_basis: str = "CNY"):
            return ["2025-12-31"]

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            return {"report_date": report_date, "total_market_value_amount": 321.0e8}

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_union_report_dates(self):
            return ["2026-01-31", "2025-12-31", "2025-11-30"]

        def list_formal_fi_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def sum_formal_total_pnl_for_year(self, year: int):
            raise AssertionError("wall-clock year path should not be used")

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            calls.append(("pnl", report_date))
            values = {
                "2025-12-31": 6.5e8,
                "2025-11-30": 5.0e8,
            }
            return values[report_date]

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def resolve_latest_report_date(self):
            return "2025-12-31"

        def fetch_zqtz_rows(self, report_date: str):
            return [{"source_version": "sv-liab-z", "rule_version": "rv-liab"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"source_version": "sv-liab-t", "rule_version": "rv-liab"}]

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-12-31", "2025-11-30"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            return {"report_date": report_date, "portfolio_dv01": 456789.0}

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", BalanceRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {"report_date": report_date, "kpi": {"nim": 0.25}},
    )

    out = exec_mod.executive_overview()

    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["yield"]["value"] == "+6.50 亿"
    assert "2025-12-31" in metrics["yield"]["detail"]
    assert "2026-01-31" not in metrics["yield"]["detail"]
    assert calls == [("pnl", "2025-12-31"), ("pnl", "2025-11-30")]


def test_executive_pnl_attribution_fallback_no_rows(monkeypatch, exec_mod):
    class EmptyRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return []

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", EmptyRepo)
    out = exec_mod.executive_pnl_attribution()
    _assert_analytical_meta(out["result_meta"])
    assert out["result_meta"]["result_kind"] == "executive.pnl-attribution"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    r = out["result"]
    assert "无受控" in r["title"]
    assert r["total"] == "0 亿"
    assert len(r["segments"]) == 5
    labels = [s["label"] for s in r["segments"]]
    assert labels == ["Carry", "Roll-down", "信用利差", "交易损益", "其他"]


def test_executive_pnl_attribution_fallback_when_repo_unusable(monkeypatch, exec_mod):
    class BrokenRepo:
        def __init__(self, *_a, **_k):
            raise RuntimeError("no duckdb")

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", BrokenRepo)
    out = exec_mod.executive_pnl_attribution()
    assert out["result_meta"]["result_kind"] == "executive.pnl-attribution"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result"]["total"] == "0 亿"
    assert len(out["result"]["segments"]) == 5


def test_executive_pnl_attribution_repo_aggregation_contract(monkeypatch, exec_mod):
    report = "2026-03-31"

    def rows():
        return [
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_tpl",
                "business_net_income": 1e8,
                "source_version": "sv_pc_a",
                "rule_version": "rv_pc_a",
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_ac",
                "business_net_income": 2e8,
                "source_version": "sv_pc_a",
                "rule_version": "rv_pc_a",
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_fvoci",
                "business_net_income": 1e8,
                "source_version": "sv_pc_b",
                "rule_version": "rv_pc_b",
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_ac_other",
                "business_net_income": 0.5e8,
                "source_version": "sv_pc_b",
                "rule_version": "rv_pc_b",
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_valuation_spread",
                "business_net_income": -3e8,
                "source_version": "sv_pc_c",
                "rule_version": "rv_pc_c",
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "unknown_bucket",
                "business_net_income": 0.25e8,
                "source_version": "sv_pc_c",
                "rule_version": "rv_pc_c",
            },
        ]

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return [report]

        def fetch_rows(self, rd, grain):
            assert rd == report
            assert grain == "monthly"
            return rows()

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_pnl_attribution()
    assert out["result_meta"]["result_kind"] == "executive.pnl-attribution"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_v1__sv_pc_a__sv_pc_b__sv_pc_c"
    assert out["result_meta"]["rule_version"] == "rv_exec_dashboard_v1__rv_pc_a__rv_pc_b__rv_pc_c"
    segs = {s["id"]: s for s in out["result"]["segments"]}
    assert segs["carry"]["amount"] == pytest.approx(3.0)
    assert segs["carry"]["display_amount"] == "+3.00 亿"
    assert segs["roll"]["amount"] == pytest.approx(-3.0)
    assert segs["roll"]["tone"] == "negative"
    assert segs["roll"]["display_amount"] == "-3.00 亿"
    assert segs["credit"]["amount"] == pytest.approx(0.5)
    assert segs["trading"]["amount"] == pytest.approx(1.0)
    assert segs["other"]["amount"] == pytest.approx(0.25)
    assert out["result"]["total"] == "+1.75 亿"


def test_executive_pnl_attribution_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, str]] = []

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2025-11-20"]

        def fetch_rows(self, rd, grain):
            calls.append((rd, grain))
            return [
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_ac",
                    "business_net_income": 2e8,
                    "source_version": "sv_pc_req",
                    "rule_version": "rv_pc_req",
                }
            ]

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_pnl_attribution(report_date="2025-11-20")

    assert calls == [("2025-11-20", "monthly")]
    assert out["result"]["total"] == "+2.00 亿"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_v1__sv_pc_req"
    assert out["result_meta"]["rule_version"] == "rv_exec_dashboard_v1__rv_pc_req"


def test_executive_contribution_fallback(monkeypatch, exec_mod):
    class BadRepo:
        def __init__(self, *_a, **_k):
            raise RuntimeError("no db")

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", BadRepo)
    out = exec_mod.executive_contribution()
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert out["result"]["title"] == "团队 / 账户 / 策略贡献"
    assert out["result"]["rows"] == []


def test_executive_contribution_repo_grouping_and_status(monkeypatch, exec_mod):
    report = "2026-02-28"

    def rows():
        return [
            {"level": 1, "is_total": False, "category_id": "bond_ac", "business_net_income": 10e8, "source_version": "sv_contrib_a", "rule_version": "rv_contrib_a"},
            {"level": 1, "is_total": False, "category_id": "bond_valuation_spread", "business_net_income": 5e8, "source_version": "sv_contrib_b", "rule_version": "rv_contrib_b"},
            {"level": 1, "is_total": False, "category_id": "bond_ac_other", "business_net_income": 8e8, "source_version": "sv_contrib_b", "rule_version": "rv_contrib_b"},
            {"level": 1, "is_total": False, "category_id": "bond_tpl", "business_net_income": 2e8, "source_version": "sv_contrib_c", "rule_version": "rv_contrib_c"},
        ]

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return [report]

        def fetch_rows(self, rd, grain):
            return rows()

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_contribution()
    assert out["result_meta"]["source_version"] == "sv_contrib_a__sv_contrib_b__sv_contrib_c__sv_exec_dashboard_v1"
    assert out["result_meta"]["rule_version"] == "rv_contrib_a__rv_contrib_b__rv_contrib_c__rv_exec_dashboard_v1"
    assert out["result"]["title"] == "团队 / 账户 / 策略贡献"
    by_id = {r["id"]: r for r in out["result"]["rows"]}
    assert by_id["rates"]["name"] == "利率组"
    assert by_id["credit"]["name"] == "信用组"
    assert by_id["trading"]["name"] == "交易组"
    max_abs = 15.0
    assert by_id["rates"]["completion"] == int(min(100, round(15 / max_abs * 100)))
    assert by_id["credit"]["completion"] == int(min(100, round(8 / max_abs * 100)))
    assert by_id["trading"]["completion"] == int(min(100, round(2 / max_abs * 100)))
    assert by_id["rates"]["status"] == "核心拉动"
    assert by_id["credit"]["status"] == "稳定贡献"
    assert by_id["trading"]["status"] == "波动偏大"


def test_executive_contribution_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, str]] = []

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2025-11-20"]

        def fetch_rows(self, rd, grain):
            calls.append((rd, grain))
            return [
                {"level": 1, "is_total": False, "category_id": "bond_tpl", "business_net_income": 1e8, "source_version": "sv_contrib_req", "rule_version": "rv_contrib_req"},
                {"level": 1, "is_total": False, "category_id": "bond_ac", "business_net_income": 3e8, "source_version": "sv_contrib_req", "rule_version": "rv_contrib_req"},
            ]

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_contribution(report_date="2025-11-20")

    assert calls == [("2025-11-20", "monthly")]
    assert out["result_meta"]["source_version"] == "sv_contrib_req__sv_exec_dashboard_v1"
    assert out["result_meta"]["rule_version"] == "rv_contrib_req__rv_exec_dashboard_v1"
    rows = {row["id"]: row for row in out["result"]["rows"]}
    assert rows["rates"]["contribution"] == "+3.00 亿"
    assert rows["trading"]["contribution"] == "+1.00 亿"


def test_executive_risk_overview_fallback(monkeypatch, exec_mod):
    class BadBond:
        def __init__(self, *_a, **_k):
            pass

        def fetch_latest_risk_overview_snapshot(self):
            return None

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BadBond)
    out = exec_mod.executive_risk_overview()
    assert out["result_meta"]["result_kind"] == "executive.risk-overview"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert out["result"]["title"] == "风险全景"
    assert out["result"]["signals"] == []


def test_executive_risk_overview_repo_backed(monkeypatch, exec_mod):
    snap = {
        "report_date": "2026-04-01",
        "portfolio_modified_duration": 4.567,
        "portfolio_dv01": 1234567.8,
        "credit_market_value_ratio_pct": 12.34,
        "weighted_years_to_maturity": 3.21,
    }

    class OkBond:
        def __init__(self, *_a, **_k):
            pass

        def fetch_latest_risk_overview_snapshot(self):
            return snap

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", OkBond)
    monkeypatch.setattr(
        exec_mod,
        "load_latest_bond_analytics_lineage",
        lambda **kwargs: {
            "source_version": "sv_risk_lineage",
            "rule_version": "rv_risk_lineage",
            "cache_version": "cv_risk_lineage",
            "vendor_version": "vv_none",
        },
        raising=False,
    )
    out = exec_mod.executive_risk_overview()
    assert out["result_meta"]["result_kind"] == "executive.risk-overview"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_v1__sv_risk_lineage"
    assert out["result_meta"]["rule_version"] == "rv_exec_dashboard_v1__rv_risk_lineage"
    by_label = {s["label"]: s for s in out["result"]["signals"]}
    assert "4.57" in by_label["久期风险"]["value"]
    assert "1,234,568" in by_label["杠杆风险"]["value"] or "1234568" in by_label["杠杆风险"]["value"]
    assert "12.3" in by_label["信用集中度"]["value"]
    assert "3.21" in by_label["流动性风险"]["value"]
    for sig in out["result"]["signals"]:
        assert "最新日期" in sig["detail"]


def test_executive_risk_overview_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[str] = []

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2025-11-20", "2026-02-28"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            calls.append(report_date)
            return {
                "report_date": report_date,
                "portfolio_modified_duration": 2.34,
                "portfolio_dv01": 456789.0,
                "credit_market_value_ratio_pct": 11.1,
                "weighted_years_to_maturity": 4.56,
            }

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", Repo)
    out = exec_mod.executive_risk_overview(report_date="2025-11-20")

    assert calls == ["2025-11-20"]
    for sig in out["result"]["signals"]:
        assert "2025-11-20" in sig["detail"]


def test_executive_alerts_fallback_empty_dates(monkeypatch, exec_mod):
    class EmptyDates:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return []

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", EmptyDates)
    out = exec_mod.executive_alerts()
    assert out["result_meta"]["result_kind"] == "executive.alerts"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert out["result"]["title"] == "预警与事件"
    assert out["result"]["items"] == []


def test_executive_alerts_fallback_on_exception(monkeypatch, exec_mod):
    class Boom:
        def __init__(self, *_a, **_k):
            raise OSError("boom")

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", Boom)
    out = exec_mod.executive_alerts()
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result"]["title"] == "预警与事件"
    assert out["result"]["items"] == []


def test_executive_alerts_repo_orchestration_contract(monkeypatch, exec_mod):
    class FakeTensor:
        pass

    fixed_alerts = [
        {
            "rule_id": "rule-a",
            "severity": "high",
            "title": "T1",
            "detail": "D1",
        },
        {
            "rule_id": "rule-b",
            "severity": "low",
            "title": "T2",
            "detail": "D2",
        },
    ]

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-05-01"]

        def fetch_bond_analytics_rows(self, report_date: str):
            return [{"market_value": 1, "dv01": 0}]

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "load_latest_bond_analytics_lineage",
        lambda **kwargs: {
            "source_version": "sv_alerts_lineage",
            "rule_version": "rv_alerts_lineage",
            "cache_version": "cv_alerts_lineage",
            "vendor_version": "vv_none",
        },
        raising=False,
    )
    monkeypatch.setattr(
        exec_mod,
        "compute_portfolio_risk_tensor",
        lambda rows, report_date: FakeTensor(),
    )
    monkeypatch.setattr(
        exec_mod,
        "evaluate_alerts",
        lambda tensor, rules=None: list(fixed_alerts),
    )
    fixed_now = dt.datetime(2026, 5, 1, 14, 30, 0)
    monkeypatch.setattr(exec_mod, "datetime", SimpleNamespace(now=lambda: fixed_now))

    out = exec_mod.executive_alerts()
    items = out["result"]["items"]
    assert out["result_meta"]["source_version"] == "sv_alerts_lineage__sv_exec_dashboard_v1"
    assert out["result_meta"]["rule_version"] == "rv_alerts_lineage__rv_exec_dashboard_v1"
    assert len(items) == 2
    assert items[0]["id"] == "rule-a"
    assert items[0]["severity"] == "high"
    assert items[0]["title"] == "T1"
    assert items[0]["detail"] == "D1"
    assert items[0]["occurred_at"] == "14:30"
    assert items[1]["id"] == "rule-b"


def test_executive_risk_overview_no_demo_fallback_when_requested_date_not_governed(monkeypatch, exec_mod):
    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2024-01-01"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            raise AssertionError("snapshot should not be queried for missing governed dates")

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", Repo)
    out = exec_mod.executive_risk_overview(report_date="2025-11-20")

    assert out["result_meta"]["result_kind"] == "executive.risk-overview"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result"]["signals"] == []


def test_executive_alerts_no_demo_fallback_when_requested_date_not_governed(monkeypatch, exec_mod):
    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28"]

        def fetch_bond_analytics_rows(self, report_date: str):
            raise AssertionError("rows should not load for missing governed dates")

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", Repo)
    out = exec_mod.executive_alerts(report_date="2025-11-20")

    assert out["result_meta"]["result_kind"] == "executive.alerts"
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert out["result"]["items"] == []


def test_executive_alerts_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[str] = []

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2025-11-20"]

        def fetch_bond_analytics_rows(self, report_date: str):
            calls.append(report_date)
            return [{"market_value": 1, "dv01": 0}]

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_portfolio_risk_tensor",
        lambda rows, report_date: SimpleNamespace(report_date=report_date),
    )
    monkeypatch.setattr(
        exec_mod,
        "evaluate_alerts",
        lambda tensor, rules=None: [
            {
                "rule_id": "rule-hist",
                "severity": "medium",
                "title": "Historical",
                "detail": f"as of {tensor.report_date.isoformat()}",
            }
        ],
    )
    monkeypatch.setattr(
        exec_mod,
        "datetime",
        SimpleNamespace(now=lambda: dt.datetime(2025, 11, 20, 9, 45, 0)),
    )

    out = exec_mod.executive_alerts(report_date="2025-11-20")

    assert calls == ["2025-11-20"]
    assert out["result"]["items"][0]["detail"] == "as of 2025-11-20"


def test_executive_overview_latest_governed_ytd_uses_latest_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, object]] = []

    class FormalRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2024-12-31", "2024-11-30"]

        def fetch_latest_zqtz_asset_market_value(self, **_k):
            calls.append(("aum-latest", None))
            return {"report_date": "2024-12-31", "total_market_value_amount": 500.0e8}

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            calls.append(("aum", report_date))
            values = {
                "2024-12-31": 500.0e8,
                "2024-11-30": 480.0e8,
            }
            return {"report_date": report_date, "total_market_value_amount": values[report_date]}

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_union_report_dates(self):
            return ["2024-12-31", "2024-11-30"]

        def sum_formal_total_pnl_for_year(self, year: int):
            raise AssertionError(f"wall-clock year path should not be used: {year}")

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            calls.append(("pnl", report_date))
            values = {
                "2024-12-31": 9.0e8,
                "2024-11-30": 8.0e8,
            }
            return values[report_date]

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def resolve_latest_report_date(self):
            return "2024-12-31"

        def list_report_dates(self):
            return ["2024-12-31", "2024-11-30"]

        def fetch_zqtz_rows(self, report_date: str):
            calls.append(("liab-z", report_date))
            return []

        def fetch_tyw_rows(self, report_date: str):
            calls.append(("liab-t", report_date))
            return []

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2024-12-31", "2024-11-30"]

        def fetch_latest_risk_overview_snapshot(self):
            calls.append(("risk-latest", None))
            return {
                "report_date": "2024-12-31",
                "portfolio_dv01": 2000.0,
            }

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            calls.append(("risk", report_date))
            values = {
                "2024-12-31": 2000.0,
                "2024-11-30": 1800.0,
            }
            return {
                "report_date": report_date,
                "portfolio_dv01": values[report_date],
            }

    class FixedDate:
        today = staticmethod(lambda: dt.date(2035, 1, 1))
        fromisoformat = staticmethod(dt.date.fromisoformat)

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", FormalRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {"nim": 0.42 if report_date == "2024-12-31" else 0.40},
        },
    )
    monkeypatch.setattr(exec_mod, "date", FixedDate)

    out = exec_mod.executive_overview()

    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["yield"]["value"] == "+9.00 亿"
    assert metrics["yield"]["delta"] == "+12.50%"
    assert "2024-12-31" in metrics["yield"]["detail"]
    assert ("pnl", "2024-12-31") in calls
    assert ("pnl", "2024-11-30") in calls


def test_executive_overview_aum_uses_combined_formal_balance_scope(monkeypatch, exec_mod):
    calls: list[tuple[str, object]] = []

    class BalanceRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            calls.append(("balance-dates", None))
            return ["2026-02-28", "2026-02-27"]

        def fetch_formal_overview(self, **kwargs):
            calls.append(("balance-overview", kwargs))
            values = {
                "2026-02-28": 3572.76e8,
                "2026-02-27": 3712.29e8,
            }
            return {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "detail_row_count": 10,
                "summary_row_count": 10,
                "total_market_value_amount": values[kwargs["report_date"]],
                "total_amortized_cost_amount": values[kwargs["report_date"]],
                "total_accrued_interest_amount": 0.0,
                "source_version": "sv_balance_union",
                "rule_version": "rv_balance_union",
            }

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_formal_fi_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            return 4.69e8 if report_date == "2026-02-28" else 4.60e8

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def resolve_latest_report_date(self):
            return "2026-02-28"

        def list_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def fetch_zqtz_rows(self, report_date: str):
            return []

        def fetch_tyw_rows(self, report_date: str):
            return []

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            return {
                "report_date": report_date,
                "portfolio_dv01": 13826218.0 if report_date == "2026-02-28" else 13855000.0,
            }

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", BalanceRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(exec_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        exec_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {"nim": 0.01},
        },
    )
    monkeypatch.setattr(exec_mod, "resolve_executive_kpi_metrics", lambda **_kwargs: [])

    out = exec_mod.executive_overview(report_date="2026-02-28")

    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["aum"]["value"].startswith("3,572.76")
    assert metrics["aum"]["delta"] == "-3.76%"
    assert "fact_formal_zqtz_balance_daily" in metrics["aum"]["detail"]
    assert "fact_formal_tyw_balance_daily" in metrics["aum"]["detail"]
    assert ("balance-dates", None) in calls
    assert (
        "balance-overview",
        {
            "report_date": "2026-02-28",
            "position_scope": "asset",
            "currency_basis": "CNY",
        },
    ) in calls
    assert (
        "balance-overview",
        {
            "report_date": "2026-02-27",
            "position_scope": "asset",
            "currency_basis": "CNY",
        },
    ) in calls


def test_formal_balance_metrics_repo_lists_report_dates(tmp_path):
    db_path = tmp_path / "formal_balance.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
                report_date date,
                position_scope varchar,
                currency_basis varchar,
                market_value_amount double
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
                ('2024-12-31', 'asset', 'CNY', 100.0),
                ('2024-11-30', 'asset', 'CNY', 90.0),
                ('2024-12-31', 'liability', 'CNY', 10.0)
            """
        )
    finally:
        conn.close()

    repo = FormalZqtzBalanceMetricsRepository(str(db_path))

    assert repo.list_report_dates() == ["2024-12-31", "2024-11-30"]


def test_liability_analytics_repo_lists_union_report_dates(tmp_path):
    db_path = tmp_path / "liability.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
                report_date date,
                instrument_code varchar,
                instrument_name varchar,
                asset_class varchar,
                bond_type varchar,
                is_issuance_like boolean,
                face_value_native double,
                market_value_native double,
                amortized_cost_native double,
                coupon_rate double,
                ytm_value double,
                maturity_date date,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
                report_date date,
                position_id varchar,
                product_type varchar,
                position_side varchar,
                counterparty_name varchar,
                core_customer_type varchar,
                principal_native double,
                funding_cost_rate double,
                maturity_date date,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
                ('2024-12-31', 'B1', 'Bond 1', 'bond', 'gov', false, 1, 1, 1, 2.0, 2.1, '2025-12-31', 'sv', 'rv'),
                ('2024-11-30', 'B2', 'Bond 2', 'bond', 'corp', false, 1, 1, 1, 2.0, 2.1, '2025-12-31', 'sv', 'rv')
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
                ('2024-12-15', 'P1', 'repo', 'liability', 'CP', 'core', 1, 1.5, '2025-01-01', 'sv', 'rv'),
                ('2024-10-31', 'P2', 'repo', 'asset', 'CP', 'core', 1, 1.5, '2025-01-01', 'sv', 'rv')
            """
        )
    finally:
        conn.close()

    repo = LiabilityAnalyticsRepository(str(db_path))

    assert repo.list_report_dates() == ["2024-12-31", "2024-12-15", "2024-11-30", "2024-10-31"]
