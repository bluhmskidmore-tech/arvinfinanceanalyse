"""Contract tests for bond-analytics portfolio headlines & top holdings (formal envelope)."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"


def _assert_formal_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    assert meta.get("basis") == "formal"
    assert meta.get("formal_use_allowed") is True
    for key in ("trace_id", "source_version", "rule_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"


def test_portfolio_headlines_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/portfolio-headlines",
            params={"report_date": REPORT_DATE},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        _assert_formal_envelope(payload)
        assert payload["result_meta"]["result_kind"] == "bond_analytics.portfolio_headlines"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["bond_count"] == 0
        assert result["by_asset_class"] == []
        assert result["warnings"]
    finally:
        get_settings.cache_clear()


def test_top_holdings_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/top-holdings",
            params={"report_date": REPORT_DATE, "top_n": 10},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        _assert_formal_envelope(payload)
        assert payload["result_meta"]["result_kind"] == "bond_analytics.top_holdings"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["top_n"] == 10
        assert result["items"] == []
    finally:
        get_settings.cache_clear()
