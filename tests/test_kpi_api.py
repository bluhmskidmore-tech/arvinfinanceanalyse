from __future__ import annotations

import uuid
from types import SimpleNamespace
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def _load_kpi_route_module():
    return load_module(
        f"tests._kpi_routes.kpi_{uuid.uuid4().hex}",
        "backend/app/api/routes/kpi.py",
    )


def test_fastapi_application_exposes_kpi_routes():
    module = _load_kpi_route_module()
    app = FastAPI()
    app.include_router(module.router)
    paths = {route.path for route in app.routes}
    assert "/api/kpi/owners" in paths
    assert "/api/kpi/values/summary" in paths
    assert "/api/kpi/metrics" in paths
    assert "/api/kpi/metrics/{metric_id}" in paths
    assert "/api/kpi/values" in paths
    assert "/api/kpi/values/{value_id}" in paths
    assert "/api/kpi/values/batch" in paths
    assert "/api/kpi/fetch_and_recalc" in paths
    assert "/api/kpi/report" in paths


def test_kpi_routes_return_read_models(monkeypatch):
    module = _load_kpi_route_module()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn="sqlite:///tmp/kpi.db", postgres_dsn="sqlite:///tmp/kpi.db"),
    )
    monkeypatch.setattr(
        module,
        "kpi_owners_payload",
        lambda **_kwargs: {"owners": [{"owner_id": 1, "owner_name": "固定收益部"}], "total": 1},
    )
    monkeypatch.setattr(
        module,
        "kpi_period_summary_payload",
        lambda **_kwargs: {
            "owner_id": 1,
            "owner_name": "固定收益部",
            "year": 2026,
            "period_type": "YEAR",
            "period_value": None,
            "period_label": "2026年度",
            "period_start_date": "2026-01-01",
            "period_end_date": "2026-12-31",
            "metrics": [],
            "total": 0,
            "total_weight": "100.000000",
            "total_score": "0.000000",
        },
    )

    owners = module.kpi_owners(year=2026, is_active=True)
    summary = module.kpi_values_summary(owner_id=1, year=2026, period_type="YEAR", period_value=None)

    assert owners["total"] == 1
    assert owners["owners"][0]["owner_name"] == "固定收益部"
    assert summary["owner_id"] == 1
    assert summary["period_label"] == "2026年度"


def _build_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "kpi.duckdb"))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{tmp_path / 'kpi.sqlite3'}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{tmp_path / 'kpi.sqlite3'}")
    module = _load_kpi_route_module()
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_unimplemented_kpi_routes_fail_closed_with_reserved_detail(tmp_path: Path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    cases = [
        ("get", "/api/kpi/metrics", None),
        ("get", "/api/kpi/metrics/1", None),
        ("post", "/api/kpi/metrics", {"metric_code": "GOAL"}),
        ("put", "/api/kpi/metrics/1", {"metric_code": "GOAL"}),
        ("delete", "/api/kpi/metrics/1", None),
        ("get", "/api/kpi/values", {"owner_id": 1, "as_of_date": "2026-04-13"}),
        ("post", "/api/kpi/values", {"metric_id": 1, "as_of_date": "2026-04-13"}),
        ("put", "/api/kpi/values/1", {"actual_value": "95"}),
        ("post", "/api/kpi/values/batch", {"as_of_date": "2026-04-13", "items": []}),
        ("post", "/api/kpi/fetch_and_recalc?owner_id=1&as_of_date=2026-04-13", {}),
        ("get", "/api/kpi/report", {"year": 2026}),
    ]

    for method, path, payload in cases:
        response = client.request(
            method.upper(),
            path,
            params=payload if method == "get" else None,
            json=payload if method in {"post", "put"} else None,
        )
        assert response.status_code == 503, path
        body = response.json()
        assert "reserved" in str(body.get("detail", "")).lower(), path
