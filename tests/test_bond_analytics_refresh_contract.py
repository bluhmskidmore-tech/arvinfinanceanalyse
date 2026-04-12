"""Contract tests for bond-analytics POST /refresh and GET /refresh-status behavior."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from tests.helpers import load_module
from tests.test_bond_analytics_api import REPORT_DATE
from tests.test_bond_analytics_materialize_flow import _seed_bond_snapshot_rows

JOB_NAME = "bond_analytics_materialize"
CACHE_KEY = "bond_analytics:materialize:formal"
LOCK = "lock:duckdb:formal:bond-analytics:materialize"


def _configure_bond_analytics_api_env(tmp_path, monkeypatch) -> object:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    return governance_dir


def test_bond_analytics_refresh_returns_503_when_queue_dispatch_fails(tmp_path, monkeypatch):
    governance_dir = _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    monkeypatch.setattr(
        service_mod.materialize_bond_analytics_facts,
        "send",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic broker failure")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/bond-analytics/refresh", params={"report_date": REPORT_DATE})

    assert response.status_code == 503
    assert response.json()["detail"] == "Bond analytics refresh queue dispatch failed."

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    bond = [r for r in records if r.get("job_name") == JOB_NAME]
    assert len(bond) >= 2
    failed = [r for r in bond if r.get("status") == "failed" and r.get("source_version") == "sv_bond_analytics_failed"][-1]
    assert failed["status"] == "failed"
    assert failed["report_date"] == REPORT_DATE
    assert failed["error_message"] == "Bond analytics refresh queue dispatch failed."
    queued = [r for r in bond if r.get("status") == "queued" and r.get("run_id") == failed.get("run_id")]
    assert len(queued) == 1
    get_settings.cache_clear()


def test_bond_analytics_refresh_reconciles_stale_inflight_run_and_requeues(tmp_path, monkeypatch):
    governance_dir = _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="bond-analytics-stale-run",
                job_name=JOB_NAME,
                status="running",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
            "started_at": stale_time,
        },
    )

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
    response = client.post("/api/bond-analytics/refresh", params={"report_date": REPORT_DATE})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert len(queued_messages) == 1
    assert queued_messages[0]["run_id"] == payload["run_id"]
    assert queued_messages[0]["report_date"] == REPORT_DATE

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    stale_rows = [r for r in records if r.get("run_id") == "bond-analytics-stale-run"]
    assert stale_rows[-1]["status"] == "failed"
    assert stale_rows[-1]["error_message"] == "Marked stale bond analytics refresh run as failed."
    get_settings.cache_clear()


def test_bond_analytics_refresh_status_returns_latest_record_for_run_id_only(tmp_path, monkeypatch):
    governance_dir = _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    repo = GovernanceRepository(base_dir=governance_dir)

    target_run = "bond-analytics-status-chain"
    other_run = "bond-analytics-other-run"

    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=target_run,
                job_name=JOB_NAME,
                status="queued",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=target_run,
                job_name=JOB_NAME,
                status="running",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=target_run,
                job_name=JOB_NAME,
                status="completed",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_done",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=other_run,
                job_name=JOB_NAME,
                status="queued",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=other_run,
                job_name=JOB_NAME,
                status="running",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-analytics/refresh-status",
        params={"run_id": target_run},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == target_run
    assert body["status"] == "completed"
    assert body["source_version"] == "sv_bond_analytics_done"
    assert body["trigger_mode"] == "terminal"
    assert body["report_date"] == REPORT_DATE
    get_settings.cache_clear()


def test_bond_analytics_refresh_status_returns_failed_terminal_record(tmp_path, monkeypatch):
    governance_dir = _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    repo = GovernanceRepository(base_dir=governance_dir)
    run_id = "bond-analytics-failed-terminal"

    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name=JOB_NAME,
                status="queued",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name=JOB_NAME,
                status="failed",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_failed",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
            "error_message": "synthetic failure",
        },
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/bond-analytics/refresh-status", params={"run_id": run_id})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["trigger_mode"] == "terminal"
    assert body["error_message"] == "synthetic failure"
    assert body["run_id"] == run_id
    get_settings.cache_clear()


def test_bond_analytics_refresh_status_returns_503_when_status_backend_unavailable(tmp_path, monkeypatch):
    import sys

    _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    # Clear cached modules so monkeypatch targets the same GovernanceRepository
    # instance that the route handler will use.
    for mod_name in list(sys.modules):
        if mod_name.startswith("backend.app."):
            sys.modules.pop(mod_name, None)

    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    monkeypatch.setattr(
        service_mod.GovernanceRepository,
        "read_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status backend unavailable")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get("/api/bond-analytics/refresh-status", params={"run_id": "run-any"})

    assert response.status_code == 503
    assert response.json()["detail"] == "status backend unavailable"
    get_settings.cache_clear()


def test_bond_analytics_legacy_inflight_without_timestamps_is_stale_and_requeues(tmp_path, monkeypatch):
    """Locks current behavior: empty queued_at/started_at/created_at => stale => mark failed + new queue."""
    governance_dir = _configure_bond_analytics_api_env(tmp_path, monkeypatch)
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="bond-analytics-legacy-no-ts",
                job_name=JOB_NAME,
                status="queued",
                cache_key=CACHE_KEY,
                lock=LOCK,
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
        },
    )

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
    response = client.post("/api/bond-analytics/refresh", params={"report_date": REPORT_DATE})

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert len(queued_messages) == 1

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    legacy = [r for r in records if r.get("run_id") == "bond-analytics-legacy-no-ts"]
    assert legacy[0]["status"] == "queued"
    assert legacy[-1]["status"] == "failed"
    assert legacy[-1]["error_message"] == "Marked stale bond analytics refresh run as failed."
    assert legacy[-1]["source_version"] == "sv_bond_analytics_stale"
    get_settings.cache_clear()
