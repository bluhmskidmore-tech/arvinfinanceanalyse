from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers import load_module


def _build_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "liability.duckdb"))
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def test_liability_analytics_routes_fail_closed_while_surface_remains_reserved(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path, params in (
        ("/api/risk/buckets", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
        ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
        ("/api/liabilities/monthly", {"year": "2026"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        body = response.json()
        assert "result_meta" in body, path
        assert "result" in body, path
        assert body["result_meta"].get("basis") == "analytical", path


def test_liability_analytics_routes_still_validate_invalid_report_date(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path in (
        "/api/risk/buckets",
        "/api/analysis/yield_metrics",
        "/api/analysis/liabilities/counterparty",
    ):
        response = client.get(path, params={"report_date": "2026-99-99"})
        assert response.status_code == 422, path
        assert "invalid report_date" in response.json()["detail"].lower(), path


def test_liability_analytics_monthly_route_still_validates_year_bounds(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/liabilities/monthly", params={"year": "1999"})
    assert response.status_code == 422
