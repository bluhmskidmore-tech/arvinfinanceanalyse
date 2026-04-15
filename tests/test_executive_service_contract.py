"""Contract tests for executive dashboard service (fallback vs repo-backed, result_meta)."""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _exec_service_module():
    """Fresh load of executive_service for patching (avoids mutating canonical import)."""
    return load_module(
        f"tests._exec_service_contract.executive_service_{uuid.uuid4().hex}",
        "backend/app/services/executive_service.py",
    )


def _fake_settings(tmp_path):
    ns = SimpleNamespace(duckdb_path=str(tmp_path / "x.duckdb"))
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
    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["aum"]["value"] == "—"
    assert metrics["yield"]["value"] == "—"
    assert metrics["goal"]["value"] == "—"
    assert metrics["risk-budget"]["value"] == "—"
    assert "无受控" in metrics["aum"]["detail"] or "未能读取" in metrics["aum"]["detail"]
    assert "无受控" in metrics["yield"]["detail"] or "未能读取" in metrics["yield"]["detail"]
    assert "fact_formal_zqtz_balance_daily" not in metrics["aum"]["detail"]


def test_executive_overview_repo_backed_contract(monkeypatch, exec_mod):
    class OkFormal:
        def __init__(self, *_a, **_k):
            pass

        def fetch_latest_zqtz_asset_market_value(self, **_k):
            return {"total_market_value_amount": 1023.47e8}

    class OkPnl:
        def __init__(self, *_a, **_k):
            pass

        def sum_formal_total_pnl_for_year(self, year: int):
            assert year == 2030
            return 12.63e8

    class FixedDate:
        today = staticmethod(lambda: dt.date(2030, 3, 15))
        fromisoformat = staticmethod(dt.date.fromisoformat)

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", OkFormal)
    monkeypatch.setattr(exec_mod, "PnlRepository", OkPnl)
    monkeypatch.setattr(exec_mod, "date", FixedDate)

    out = exec_mod.executive_overview()
    assert out["result_meta"]["result_kind"] == "executive.overview"
    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert metrics["aum"]["value"] == "1,023.47 亿"
    assert metrics["yield"]["value"] == "+12.63 亿"
    assert metrics["goal"]["value"] == "—"
    assert metrics["risk-budget"]["value"] == "—"
    assert "fact_formal_zqtz_balance_daily" in metrics["aum"]["detail"]
    assert "fact_formal_pnl_fi 当年" in metrics["yield"]["detail"]


def test_executive_overview_uses_requested_report_date(monkeypatch, exec_mod):
    calls: list[tuple[str, object]] = []

    class FormalRepo:
        def __init__(self, *_a, **_k):
            pass

        def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
            calls.append(("aum", report_date))
            assert currency_basis == "CNY"
            return {"report_date": report_date, "total_market_value_amount": 321.0e8}

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            calls.append(("pnl", report_date))
            return 6.5e8

    monkeypatch.setattr(exec_mod, "FormalZqtzBalanceMetricsRepository", FormalRepo)
    monkeypatch.setattr(exec_mod, "PnlRepository", PnlRepo)

    out = exec_mod.executive_overview(report_date="2025-11-20")

    assert calls == [("aum", "2025-11-20"), ("pnl", "2025-11-20")]
    metrics = {m["id"]: m for m in out["result"]["metrics"]}
    assert "2025-11-20" in metrics["aum"]["detail"]
    assert "截至 2025-11-20" in metrics["yield"]["detail"]


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
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_ac",
                "business_net_income": 2e8,
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_fvoci",
                "business_net_income": 1e8,
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_ac_other",
                "business_net_income": 0.5e8,
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "bond_valuation_spread",
                "business_net_income": -3e8,
            },
            {
                "level": 1,
                "is_total": False,
                "category_id": "unknown_bucket",
                "business_net_income": 0.25e8,
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
                }
            ]

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_pnl_attribution(report_date="2025-11-20")

    assert calls == [("2025-11-20", "monthly")]
    assert out["result"]["total"] == "+2.00 亿"


def test_executive_contribution_fallback(monkeypatch, exec_mod):
    class BadRepo:
        def __init__(self, *_a, **_k):
            raise RuntimeError("no db")

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", BadRepo)
    out = exec_mod.executive_contribution()
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    rows = out["result"]["rows"]
    names = [r["name"] for r in rows]
    assert "利率组" in names
    assert "信用组" in names
    assert "交易组" in names
    assert "无受控" in out["result"]["title"]
    assert all(row["contribution"] == "+0.00 亿" for row in rows)


def test_executive_contribution_repo_grouping_and_status(monkeypatch, exec_mod):
    report = "2026-02-28"

    def rows():
        return [
            {"level": 1, "is_total": False, "category_id": "bond_ac", "business_net_income": 10e8},
            {"level": 1, "is_total": False, "category_id": "bond_valuation_spread", "business_net_income": 5e8},
            {"level": 1, "is_total": False, "category_id": "bond_ac_other", "business_net_income": 8e8},
            {"level": 1, "is_total": False, "category_id": "bond_tpl", "business_net_income": 2e8},
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
                {"level": 1, "is_total": False, "category_id": "bond_tpl", "business_net_income": 1e8},
                {"level": 1, "is_total": False, "category_id": "bond_ac", "business_net_income": 3e8},
            ]

    monkeypatch.setattr(exec_mod, "ProductCategoryPnlRepository", Repo)
    out = exec_mod.executive_contribution(report_date="2025-11-20")

    assert calls == [("2025-11-20", "monthly")]
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
    labels = [s["label"] for s in out["result"]["signals"]]
    for want in ("久期风险", "杠杆风险", "信用集中度", "流动性风险"):
        assert want in labels
    assert all(signal["value"] == "—" for signal in out["result"]["signals"])


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
    out = exec_mod.executive_risk_overview()
    assert out["result_meta"]["result_kind"] == "executive.risk-overview"
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
    assert out["result"]["title"] == "预警与事件"
    assert len(out["result"]["items"]) == 1
    assert out["result"]["items"][0]["id"] == "governed-data-unavailable"


def test_executive_alerts_fallback_on_exception(monkeypatch, exec_mod):
    class Boom:
        def __init__(self, *_a, **_k):
            raise OSError("boom")

    monkeypatch.setattr(exec_mod, "BondAnalyticsRepository", Boom)
    out = exec_mod.executive_alerts()
    assert out["result_meta"]["source_version"] == "sv_exec_dashboard_explicit_miss_v1"
    assert len(out["result"]["items"]) == 1
    assert out["result"]["title"] == "预警与事件"


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
    for sig in out["result"]["signals"]:
        assert sig["value"] == "—"
        assert "2025-11-20" in sig["detail"]
        assert "演示" in sig["detail"]


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
    assert len(out["result"]["items"]) == 1
    assert out["result"]["items"][0]["id"] == "governed-date-miss"
    assert "2025-11-20" in out["result"]["items"][0]["detail"]


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
