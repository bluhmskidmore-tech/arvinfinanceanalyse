"""首页高频只读端点的 TTL 响应缓存契约测试。

覆盖 dashboard-home 首屏里每次请求都从 DuckDB 重算的四个端点：
credit-spread-migration / position-changes / research-reports / campisi four-effects。

契约：
- 相同参数的重复请求只重算一次，且响应逐字段相同；
- 参数不同必须落到不同缓存键（不得串味）；
- bond-analytics 刷新写入后缓存失效，下次请求重算。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module

READ_HEADERS = {"X-User-Id": "home-cache-read-user", "X-User-Role": "viewer"}
REPORT_DATE = "2026-03-31"


def _envelope(kind: str, **result: object) -> dict[str, object]:
    return {"result_meta": {"result_kind": kind}, "result": dict(result)}


_CAMPISI_BOND_ROW = {
    "bond_code": "X",
    "asset_class": "credit",
    "maturity_bucket": "3-5Y",
    "mod_duration": 3.0,
    "market_value_start": 100.0,
    "income_return": 0.0,
    "treasury_effect": 0.0,
    "spread_effect": 0.0,
    "selection_effect": 0.0,
    "total_return": 0.0,
    "has_accrued_interest": True,
    "treasury_effect_available": True,
    "spread_effect_available": True,
}


def _campisi_envelope(**result: object) -> dict[str, object]:
    """A complete four-effects envelope.

    `/campisi/four-effects` declares a `response_model`, so a partial stub would
    be rejected before the caching behaviour under test could be observed.
    """
    return {
        "result_meta": {
            "trace_id": "tr_home_cache_campisi",
            "result_kind": "campisi.four_effects",
            "source_version": "sv_home_cache",
            "rule_version": "rv_home_cache",
            "cache_version": "cv_home_cache",
        },
        "result": {
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "report_date": "2026-01-31",
            "num_days": 30,
            "totals": {
                "market_value_start": 0.0,
                "income_return": 0.0,
                "treasury_effect": 0.0,
                "spread_effect": 0.0,
                "selection_effect": 0.0,
                "total_return": 0.0,
            },
            "by_asset_class": [],
            "warnings": [],
            **result,
        },
    }


@pytest.fixture
def bond_analytics_client(monkeypatch) -> tuple[TestClient, object, list[tuple[object, ...]]]:
    route_module = load_module(
        "backend.app.api.routes.bond_analytics",
        "backend/app/api/routes/bond_analytics.py",
    )
    route_module.market_home_response_cache.invalidate()
    calls: list[tuple[object, ...]] = []

    def _credit_spread(report_date, spread_scenarios):
        calls.append(("credit_spread", report_date.isoformat(), spread_scenarios))
        return _envelope(
            "bond_analytics.credit_spread_migration",
            report_date=report_date.isoformat(),
            build_index=len(calls),
        )

    def _position_changes(report_date, *, top_n):
        calls.append(("position_changes", report_date.isoformat(), top_n))
        return _envelope(
            "bond_analytics.position_changes",
            report_date=report_date.isoformat(),
            build_index=len(calls),
        )

    monkeypatch.setattr(route_module, "get_credit_spread_migration", _credit_spread)
    monkeypatch.setattr(route_module, "get_position_changes", _position_changes)

    app = FastAPI()
    app.include_router(route_module.router)
    try:
        yield TestClient(app), route_module, calls
    finally:
        route_module.market_home_response_cache.invalidate()


def test_credit_spread_migration_repeat_request_reuses_cached_envelope(
    bond_analytics_client,
) -> None:
    client, _route_module, calls = bond_analytics_client
    params = {"report_date": REPORT_DATE}

    first = client.get(
        "/api/bond-analytics/credit-spread-migration", params=params, headers=READ_HEADERS
    )
    second = client.get(
        "/api/bond-analytics/credit-spread-migration", params=params, headers=READ_HEADERS
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["result"] == second.json()["result"]
    assert [call for call in calls if call[0] == "credit_spread"] == [
        ("credit_spread", REPORT_DATE, "10,25,50")
    ]


def test_credit_spread_migration_cache_key_separates_report_date_and_scenarios(
    bond_analytics_client,
) -> None:
    client, _route_module, calls = bond_analytics_client

    client.get(
        "/api/bond-analytics/credit-spread-migration",
        params={"report_date": REPORT_DATE},
        headers=READ_HEADERS,
    )
    client.get(
        "/api/bond-analytics/credit-spread-migration",
        params={"report_date": "2026-02-28"},
        headers=READ_HEADERS,
    )
    client.get(
        "/api/bond-analytics/credit-spread-migration",
        params={"report_date": REPORT_DATE, "spread_scenarios": "10,25"},
        headers=READ_HEADERS,
    )

    assert [call[1:] for call in calls if call[0] == "credit_spread"] == [
        (REPORT_DATE, "10,25,50"),
        ("2026-02-28", "10,25,50"),
        (REPORT_DATE, "10,25"),
    ]


def test_position_changes_repeat_request_reuses_cache_and_top_n_separates_keys(
    bond_analytics_client,
) -> None:
    client, _route_module, calls = bond_analytics_client

    first = client.get(
        "/api/bond-analytics/position-changes",
        params={"report_date": REPORT_DATE, "top_n": 5},
        headers=READ_HEADERS,
    )
    second = client.get(
        "/api/bond-analytics/position-changes",
        params={"report_date": REPORT_DATE, "top_n": 5},
        headers=READ_HEADERS,
    )
    third = client.get(
        "/api/bond-analytics/position-changes",
        params={"report_date": REPORT_DATE, "top_n": 10},
        headers=READ_HEADERS,
    )

    assert first.json()["result"] == second.json()["result"]
    assert third.json()["result"]["build_index"] != first.json()["result"]["build_index"]
    assert [call[1:] for call in calls if call[0] == "position_changes"] == [
        (REPORT_DATE, 5),
        (REPORT_DATE, 10),
    ]


def test_bond_analytics_refresh_invalidates_home_read_cache(
    bond_analytics_client, monkeypatch
) -> None:
    client, route_module, calls = bond_analytics_client
    monkeypatch.setattr(
        route_module,
        "ensure_user_allowed",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        route_module,
        "refresh_bond_analytics",
        lambda *_args, **_kwargs: {"status": "queued", "run_id": "run-1"},
    )
    params = {"report_date": REPORT_DATE}

    client.get("/api/bond-analytics/credit-spread-migration", params=params, headers=READ_HEADERS)
    refresh = client.post(
        "/api/bond-analytics/refresh", params=params, headers=READ_HEADERS
    )
    client.get("/api/bond-analytics/credit-spread-migration", params=params, headers=READ_HEADERS)

    assert refresh.status_code == 200, refresh.text
    assert len([call for call in calls if call[0] == "credit_spread"]) == 2


def test_home_research_reports_repeat_request_reuses_cache_and_limit_separates_keys(
    monkeypatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.executive",
        "backend/app/api/routes/executive.py",
    )
    route_module.market_home_response_cache.invalidate()
    calls: list[tuple[str, int]] = []

    def _research_reports(*, report_date: str, limit: int):
        calls.append((report_date, limit))
        return _envelope("home.research_reports", report_date=report_date, items=[])

    monkeypatch.setattr(route_module, "home_research_reports_envelope", _research_reports)
    monkeypatch.setattr(route_module, "_ensure_executive_read_allowed", lambda _auth: None)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    try:
        first = client.get(
            "/ui/home/research-reports",
            params={"report_date": "2026-08-11", "limit": 5},
            headers=READ_HEADERS,
        )
        second = client.get(
            "/ui/home/research-reports",
            params={"report_date": "2026-08-11", "limit": 5},
            headers=READ_HEADERS,
        )
        client.get(
            "/ui/home/research-reports",
            params={"report_date": "2026-08-11", "limit": 8},
            headers=READ_HEADERS,
        )

        assert first.status_code == 200, first.text
        assert first.json()["result"] == second.json()["result"]
        assert calls == [("2026-08-11", 5), ("2026-08-11", 8)]
    finally:
        route_module.market_home_response_cache.invalidate()


def test_campisi_four_effects_full_detail_stays_uncached(monkeypatch) -> None:
    """full envelope 体积大且键含用户可选日期，必须保持每次重算。"""
    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )
    route_module.market_home_response_cache.invalidate()
    calls: list[object] = []

    class _StubService:
        def campisi_four_effects_envelope(self, **kwargs):
            calls.append(kwargs["end_date"])
            return _campisi_envelope(by_bond=[])

        def campisi_four_effects_summary_envelope(self, **_kwargs):
            raise AssertionError("summary path should not be used without detail=summary")

    monkeypatch.setattr(route_module, "_svc", lambda: _StubService())
    monkeypatch.setattr(route_module, "_ensure_pnl_attribution_read_allowed", lambda _auth: None)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    params = {"end_date": "2026-01-31", "lookback_days": 30}
    try:
        client.get("/api/pnl-attribution/campisi/four-effects", params=params, headers=READ_HEADERS)
        client.get("/api/pnl-attribution/campisi/four-effects", params=params, headers=READ_HEADERS)

        assert calls == ["2026-01-31", "2026-01-31"]
    finally:
        route_module.market_home_response_cache.invalidate()


def test_campisi_four_effects_cache_separates_detail_and_dates(monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )
    route_module.market_home_response_cache.invalidate()
    calls: list[tuple[str, object, object, int]] = []

    class _StubService:
        def campisi_four_effects_summary_envelope(self, **kwargs):
            calls.append(("summary", kwargs["start_date"], kwargs["end_date"], kwargs["lookback_days"]))
            return _campisi_envelope(by_bond=[])

        def campisi_four_effects_envelope(self, **kwargs):
            calls.append(("full", kwargs["start_date"], kwargs["end_date"], kwargs["lookback_days"]))
            return _campisi_envelope(by_bond=[_CAMPISI_BOND_ROW])

    monkeypatch.setattr(route_module, "_svc", lambda: _StubService())
    monkeypatch.setattr(route_module, "_ensure_pnl_attribution_read_allowed", lambda _auth: None)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    base = {"end_date": "2026-01-31", "lookback_days": 30}
    try:
        summary_first = client.get(
            "/api/pnl-attribution/campisi/four-effects",
            params={**base, "detail": "summary"},
            headers=READ_HEADERS,
        )
        summary_second = client.get(
            "/api/pnl-attribution/campisi/four-effects",
            params={**base, "detail": "summary"},
            headers=READ_HEADERS,
        )
        full = client.get(
            "/api/pnl-attribution/campisi/four-effects",
            params=base,
            headers=READ_HEADERS,
        )
        other_date = client.get(
            "/api/pnl-attribution/campisi/four-effects",
            params={"end_date": "2026-02-28", "lookback_days": 30, "detail": "summary"},
            headers=READ_HEADERS,
        )

        assert summary_first.json() == summary_second.json()
        assert full.json()["result"]["by_bond"] == [_CAMPISI_BOND_ROW]
        assert other_date.status_code == 200, other_date.text
        # detail 与 end_date 都必须参与缓存键，summary 不得被 full 覆盖。
        assert calls == [
            ("summary", None, "2026-01-31", 30),
            ("full", None, "2026-01-31", 30),
            ("summary", None, "2026-02-28", 30),
        ]
    finally:
        route_module.market_home_response_cache.invalidate()
