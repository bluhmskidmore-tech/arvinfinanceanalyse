"""Contract tests for `/api/pnl-attribution/*` (envelope + empty DuckDB)."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

_ENDPOINTS: list[tuple[str, dict[str, str | int | bool]]] = [
    ("/api/pnl-attribution/volume-rate", {}),
    ("/api/pnl-attribution/volume-rate", {"compare_type": "yoy"}),
    ("/api/pnl-attribution/tpl-market", {"months": 6}),
    ("/api/pnl-attribution/composition", {}),
    ("/api/pnl-attribution/composition", {"include_trend": "false", "trend_months": 3}),
    ("/api/pnl-attribution/summary", {}),
    ("/api/pnl-attribution/advanced/carry-rolldown", {}),
    ("/api/pnl-attribution/advanced/spread", {"lookback_days": 14}),
    ("/api/pnl-attribution/advanced/krd", {"lookback_days": 14}),
    ("/api/pnl-attribution/advanced/summary", {}),
    ("/api/pnl-attribution/advanced/campisi", {"lookback_days": 7}),
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


def test_pnl_attribution_endpoints_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty_pnl_attr.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
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
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
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
