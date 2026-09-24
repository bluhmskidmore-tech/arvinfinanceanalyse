"""Contract tests for `/api/pnl-attribution/*` (envelope + empty DuckDB)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

PNL_ATTRIBUTION_READ_HEADERS = {"X-User-Id": "pnl-attribution-read-user", "X-User-Role": "viewer"}

_ENDPOINTS: list[tuple[str, dict[str, str | int | bool]]] = [
    ("/api/pnl-attribution/volume-rate", {}),
    ("/api/pnl-attribution/volume-rate", {"compare_type": "yoy"}),
    ("/api/pnl-attribution/tpl-market", {"months": 6}),
    ("/api/pnl-attribution/tpl-market", {"months": 6, "report_date": "2026-04-30"}),
    ("/api/pnl-attribution/composition", {}),
    ("/api/pnl-attribution/composition", {"include_trend": "false", "trend_months": 3}),
    ("/api/pnl-attribution/summary", {}),
    ("/api/pnl-attribution/advanced/carry-rolldown", {}),
    ("/api/pnl-attribution/advanced/spread", {"lookback_days": 14}),
    ("/api/pnl-attribution/advanced/krd", {"lookback_days": 14}),
    ("/api/pnl-attribution/advanced/summary", {}),
    ("/api/pnl-attribution/advanced/campisi", {"lookback_days": 7}),
]

_CAMPISI_ENDPOINTS: list[tuple[str, dict[str, str | int]]] = [
    ("/api/pnl-attribution/campisi/four-effects", {"end_date": "2026-03-31", "lookback_days": 30}),
    ("/api/pnl-attribution/campisi/enhanced", {"end_date": "2026-03-31", "lookback_days": 30}),
    ("/api/pnl-attribution/campisi/maturity-buckets", {"end_date": "2026-03-31", "lookback_days": 30}),
    ("/api/pnl-attribution/campisi/decision-grade", {"end_date": "2026-03-31", "lookback_days": 30}),
]


def _assert_formal_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    assert meta.get("basis") == "formal"
    assert meta.get("formal_use_allowed") is True
    for key in ("trace_id", "source_version", "rule_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"


def _grant_pnl_attribution_read_scope(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "pnl-attribution-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="pnl_attribution",
        action="read",
    )


def _pnl_attribution_client_with_read_scope(tmp_path, monkeypatch) -> TestClient:
    _grant_pnl_attribution_read_scope(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update(PNL_ATTRIBUTION_READ_HEADERS)
    return client


def test_pnl_attribution_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.pnl_attribution",
        "backend/app/api/routes/pnl_attribution.py",
    )
    for name in (
        "volume_rate_attribution_envelope",
        "tpl_market_correlation_envelope",
        "pnl_composition_envelope",
        "attribution_analysis_summary_envelope",
        "carry_roll_down_envelope",
        "spread_attribution_envelope",
        "krd_attribution_envelope",
        "advanced_attribution_summary_envelope",
        "campisi_attribution_envelope",
    ):
        monkeypatch.setattr(
            route_module,
            name,
            lambda **_kwargs: {"result_meta": {"result_kind": "pnl_attribution.stub"}, "result": {}},
        )
    sqlite_path = tmp_path / "pnl-attribution-read-denied.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, params in _ENDPOINTS:
        response = client.get(path, params=params, headers=PNL_ATTRIBUTION_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_campisi_attribution_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )

    class _StubService:
        def campisi_four_effects_envelope(self, **_kwargs):
            return {"result_meta": {"result_kind": "campisi.four_effects"}, "result": {}}

        def campisi_enhanced_envelope(self, **_kwargs):
            return {"result_meta": {"result_kind": "campisi.enhanced"}, "result": {}}

        def campisi_maturity_bucket_envelope(self, **_kwargs):
            return {"result_meta": {"result_kind": "campisi.maturity_buckets"}, "result": {}}

        def campisi_decision_grade_envelope(self, **_kwargs):
            return {"result_meta": {"result_kind": "campisi.decision_grade"}, "result": {}}

    monkeypatch.setattr(route_module, "_svc", lambda: _StubService())
    sqlite_path = tmp_path / "campisi-attribution-read-denied.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, params in _CAMPISI_ENDPOINTS:
        response = client.get(path, params=params, headers=PNL_ATTRIBUTION_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_campisi_lookback_days_out_of_range_returns_422(monkeypatch) -> None:
    """lookback_days 越界（含极端大值）必须 422，不得进入 date-timedelta 造成 500。

    边界与同前缀 /api/pnl-attribution/advanced/* 的 lookback_days(ge=1, le=365) 对齐。
    """
    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )

    def _service_must_not_run():
        raise AssertionError("campisi service must not run for invalid lookback_days")

    monkeypatch.setattr(route_module, "_svc", _service_must_not_run)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, _params in _CAMPISI_ENDPOINTS:
        for bad_value in (0, 366, 10**12):
            response = client.get(
                path,
                params={"end_date": "2026-03-31", "lookback_days": bad_value},
                headers=PNL_ATTRIBUTION_READ_HEADERS,
            )
            assert response.status_code == 422, (
                f"{path} lookback_days={bad_value}: {response.status_code} {response.text}"
            )
            assert "lookback_days" in response.text


def test_pnl_attribution_endpoints_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty_pnl_attr.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = _pnl_attribution_client_with_read_scope(tmp_path, monkeypatch)
    for path, params in _ENDPOINTS:
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path} {params} -> {response.status_code}: {response.text}"
        body = response.json()
        _assert_formal_envelope(body)
        assert body["result_meta"].get("quality_flag") == "warning"
        res = body["result"]
        assert "warnings" in res
        assert any("物化" in w for w in res["warnings"])
    get_settings.cache_clear()


def test_volume_rate_shape_keys(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "e.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = _pnl_attribution_client_with_read_scope(tmp_path, monkeypatch)
    r = client.get("/api/pnl-attribution/volume-rate")
    payload = r.json()["result"]
    for k in (
        "current_period",
        "previous_period",
        "compare_type",
        "total_current_pnl",
        "items",
        "has_previous_data",
    ):
        assert k in payload
    assert payload["items"] == []
    total = payload["total_current_pnl"]
    assert isinstance(total, dict)
    for nk in ("raw", "unit", "display", "precision", "sign_aware"):
        assert nk in total
    get_settings.cache_clear()
