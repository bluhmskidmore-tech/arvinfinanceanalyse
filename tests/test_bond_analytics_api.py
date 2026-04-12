"""Contract tests for bond-analytics HTTP API (envelope + core result fields)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from httpx import ASGITransport
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.main import app
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import _seed_bond_snapshot_rows


REPORT_DATE = "2026-03-31"

_BOND_ANALYTICS_CASES: list[tuple[str, dict[str, str]]] = [
    (
        "/api/bond-analytics/return-decomposition",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/benchmark-excess",
        {
            "report_date": REPORT_DATE,
            "period_type": "MoM",
            "benchmark_id": "CDB_INDEX",
        },
    ),
    (
        "/api/bond-analytics/krd-curve-risk",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/credit-spread-migration",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/action-attribution",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/accounting-class-audit",
        {"report_date": REPORT_DATE},
    ),
]


def _assert_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"

    result = payload["result"]
    for key in ("report_date", "computed_at", "warnings"):
        assert key in result, f"result missing {key!r}"


async def _check_all_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path, params in _BOND_ANALYTICS_CASES:
            response = await client.get(path, params=params)
            assert response.status_code == 200, (
                f"{path} {params} -> {response.status_code}: {response.text}"
            )
            payload = response.json()
            _assert_envelope(payload)


def test_bond_analytics_endpoints_envelope_and_result_shape() -> None:
    """Six bond-analytics routes return 200 + result_meta/result with required keys."""
    asyncio.run(_check_all_endpoints())


def test_bond_analytics_each_path_distinct_contract() -> None:
    """Sanity: each configured path is exercised once."""
    paths = [p for p, _ in _BOND_ANALYTICS_CASES]
    assert len(paths) == len(set(paths)) == 6


def test_bond_analytics_refresh_queue_and_status_flow(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))

    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    queued_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        service_mod.materialize_bond_analytics_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    refresh_response = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
    )

    assert refresh_response.status_code == 200
    payload = refresh_response.json()
    assert payload["status"] == "queued"
    assert payload["job_name"] == "bond_analytics_materialize"
    assert payload["trigger_mode"] == "async"
    assert payload["cache_key"] == "bond_analytics:materialize:formal"
    assert queued_messages[0]["run_id"] == payload["run_id"]
    assert queued_messages[0]["report_date"] == REPORT_DATE

    status_response = client.get(
        "/api/bond-analytics/refresh-status",
        params={"run_id": payload["run_id"]},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"
    get_settings.cache_clear()


def test_bond_analytics_refresh_status_returns_404_for_unknown_run(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/bond-analytics/refresh-status",
        params={"run_id": "missing-run"},
    )

    assert response.status_code == 404
    get_settings.cache_clear()


def test_bond_analytics_refresh_returns_409_when_report_date_is_already_inflight(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="bond-analytics-inflight",
                job_name="bond_analytics_materialize",
                status="queued",
                cache_key="bond_analytics:materialize:formal",
                lock="lock:duckdb:formal:bond-analytics:materialize",
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]
    get_settings.cache_clear()
