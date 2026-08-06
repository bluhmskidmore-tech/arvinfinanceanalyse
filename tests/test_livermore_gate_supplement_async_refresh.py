from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.security.auth_context import AuthContext, get_auth_context


def test_livermore_refresh_route_queues_without_running_sync_compute(tmp_path, monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(route, "_ensure_livermore_gate_supplement_refresh_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            governance_path=tmp_path / "governance",
        ),
    )
    monkeypatch.setattr(
        route,
        "queue_gate_supplement_refresh",
        lambda **kwargs: calls.append(dict(kwargs))
        or {"status": "queued", "run_id": "livermore-refresh-run", "trigger_mode": "async"},
        raising=False,
    )
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="writer", role="admin")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/ui/market-data/livermore/refresh-gate-supplement",
        params={"as_of_date": "2026-04-30", "lookback_days": 30},
        headers={"Idempotency-Key": "livermore-key"},
    )

    assert response.status_code == 202
    assert response.json()["run_id"] == "livermore-refresh-run"
    assert calls == [
        {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_path": str(tmp_path / "governance"),
            "as_of_date": date(2026, 4, 30),
            "lookback_days": 30,
            "idempotency_key": "livermore-key",
        }
    ]


def test_livermore_queue_replays_same_key_without_duplicate_dispatch(tmp_path, monkeypatch) -> None:
    from backend.app.services import livermore_gate_supplement_compute_service as service

    sent: list[dict[str, object]] = []
    actor = SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs)))
    monkeypatch.setattr(service, "run_livermore_gate_supplement_refresh_task", actor, raising=False)

    first = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )
    second = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )

    assert first["status"] == "queued"
    assert second["run_id"] == first["run_id"]
    assert second["idempotency_replay"] is True
    assert len(sent) == 1


@pytest.mark.parametrize(
    ("stale_status", "timestamp_field"),
    [("queued", "queued_at"), ("running", "started_at")],
)
def test_livermore_queue_replaces_stale_same_key_inflight_run(
    tmp_path,
    monkeypatch,
    stale_status: str,
    timestamp_field: str,
) -> None:
    from backend.app.services import livermore_gate_supplement_compute_service as service

    governance_path = tmp_path / "governance"
    sent: list[dict[str, object]] = []
    actor = SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs)))
    monkeypatch.setattr(service, "run_livermore_gate_supplement_refresh_task", actor, raising=False)

    first = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(governance_path),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )
    sent.clear()
    repo = GovernanceRepository(base_dir=governance_path)
    original_record = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]

    stale_at = datetime.now(UTC) - service._LIVERMORE_REFRESH_STALE_AFTER - timedelta(seconds=1)
    stale_record = {
        **original_record,
        "status": stale_status,
        "trigger_mode": "async",
        timestamp_field: stale_at.isoformat(),
    }
    repo.append(CACHE_BUILD_RUN_STREAM, stale_record)

    retry = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(governance_path),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )

    records = repo.read_all(CACHE_BUILD_RUN_STREAM)
    stale_failures = [
        record
        for record in records
        if record.get("run_id") == first["run_id"]
        and record.get("status") == "failed"
        and record.get("failure_category") == "stale_inflight"
    ]
    assert len(stale_failures) == 1
    assert retry["status"] == "queued"
    assert retry["run_id"] != first["run_id"]
    assert retry["idempotency_replay"] is False
    assert len(sent) == 1
    assert sent[0]["run_id"] == retry["run_id"]


def test_livermore_worker_records_partial_terminal_state(tmp_path, monkeypatch) -> None:
    from backend.app.tasks import livermore_gate_supplement as task

    monkeypatch.setattr(
        task,
        "_execute_livermore_gate_supplement_refresh",
        lambda **_kwargs: {
            "status": "partial",
            "failure_stage": "gate_supplement_materialize",
            "market_breadth_result": {"daily_row_count": 8},
        },
        raising=False,
    )

    payload = task.run_livermore_gate_supplement_refresh_task.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        run_id="livermore-governed-run",
        as_of_date="2026-04-30",
        lookback_days=30,
        storage_target_digest="storage-digest",
        request_fingerprint="request-fingerprint",
        idempotency_key="worker-key",
    )

    records = GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
    assert payload["status"] == "partial"
    assert records[-1]["run_id"] == "livermore-governed-run"
    assert records[-1]["status"] == "partial"
    assert records[-1]["failure_stage"] == "gate_supplement_materialize"
