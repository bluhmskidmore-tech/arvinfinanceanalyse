from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from threading import Lock, Thread
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.security.auth_context import AuthContext, get_auth_context

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



def test_livermore_refresh_route_queues_without_running_sync_compute(tmp_path, monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route

    calls: list[dict[str, object]] = []
    def fake_queue_gate_supplement_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "queued", "run_id": "livermore-refresh-run", "trigger_mode": "async"}

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
        fake_queue_gate_supplement_refresh,
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
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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


@pytest.mark.parametrize(
    ("stale_status", "timestamp_field"),
    [("queued", "queued_at"), ("running", "started_at"), ("retrying", "started_at")],
)
def test_livermore_status_marks_stale_inflight_run_failed_once(
    tmp_path,
    stale_status: str,
    timestamp_field: str,
) -> None:
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

    governance_path = tmp_path / "governance"
    repo = GovernanceRepository(base_dir=governance_path)
    stale_at = datetime.now(UTC) - service._LIVERMORE_REFRESH_STALE_AFTER - timedelta(seconds=1)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": f"livermore-stale-{stale_status}",
            "job_name": service.LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
            "status": stale_status,
            "trigger_mode": "async",
            "cache_key": service.LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
            "cache_version": service.LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION,
            "rule_version": service.RULE_VERSION,
            "as_of_date": "2026-04-30",
            "report_date": "2026-04-30",
            "lookback_days": 30,
            timestamp_field: stale_at.isoformat(),
        },
    )

    first = service.livermore_gate_supplement_refresh_status(
        governance_path,
        run_id=f"livermore-stale-{stale_status}",
    )
    second = service.livermore_gate_supplement_refresh_status(
        governance_path,
        run_id=f"livermore-stale-{stale_status}",
    )

    matching = [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("run_id") == f"livermore-stale-{stale_status}"
    ]
    stale_failures = [
        record
        for record in matching
        if record.get("status") == "failed" and record.get("failure_category") == "stale_inflight"
    ]
    assert first["status"] == "failed"
    assert first["trigger_mode"] == "terminal"
    assert first["failure_category"] == "stale_inflight"
    assert second["status"] == "failed"
    assert len(stale_failures) == 1
    assert stale_failures[0]["failure_reason"] == "stale_inflight"
    assert stale_failures[0]["trigger_mode"] == "terminal"
    assert stale_failures[0]["finished_at"]


def test_livermore_queue_requeues_same_key_after_status_reconciles_stale_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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
    repo = GovernanceRepository(base_dir=governance_path)
    stale_at = datetime.now(UTC) - service._LIVERMORE_REFRESH_STALE_AFTER - timedelta(seconds=1)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **repo.read_all(CACHE_BUILD_RUN_STREAM)[-1],
            "status": "queued",
            "trigger_mode": "async",
            "queued_at": stale_at.isoformat(),
        },
    )

    status = service.livermore_gate_supplement_refresh_status(
        governance_path,
        run_id=cast(str, first["run_id"]),
    )
    retry = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(governance_path),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )

    stale_failures = [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("run_id") == first["run_id"]
        and record.get("status") == "failed"
        and record.get("failure_category") == "stale_inflight"
    ]
    assert status["status"] == "failed"
    assert retry["status"] == "queued"
    assert retry["run_id"] != first["run_id"]
    assert retry["idempotency_replay"] is False
    assert len(stale_failures) == 1
    assert len(sent) == 2
    assert sent[-1]["run_id"] == retry["run_id"]


def test_livermore_queue_requeues_legacy_stale_failure_without_failure_reason(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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
    repo = GovernanceRepository(base_dir=governance_path)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **repo.read_all(CACHE_BUILD_RUN_STREAM)[-1],
            "status": "failed",
            "trigger_mode": "terminal",
            "finished_at": datetime.now(UTC).isoformat(),
            "failure_category": "stale_inflight",
            "failure_reason": None,
            "error_message": "legacy stale row without reason",
        },
    )

    retry = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(governance_path),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )

    assert retry["status"] == "queued"
    assert retry["run_id"] != first["run_id"]
    assert retry["idempotency_replay"] is False
    assert len(sent) == 2
    assert sent[-1]["run_id"] == retry["run_id"]


def test_livermore_queue_same_key_stale_retry_is_single_dispatch_under_concurrency(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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
    repo = GovernanceRepository(base_dir=governance_path)
    stale_at = datetime.now(UTC) - service._LIVERMORE_REFRESH_STALE_AFTER - timedelta(seconds=1)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **repo.read_all(CACHE_BUILD_RUN_STREAM)[-1],
            "status": "queued",
            "trigger_mode": "async",
            "queued_at": stale_at.isoformat(),
        },
    )
    service.livermore_gate_supplement_refresh_status(
        governance_path,
        run_id=cast(str, first["run_id"]),
    )

    results: list[dict[str, object]] = []
    errors: list[Exception] = []
    results_lock = Lock()

    def invoke_retry() -> None:
        try:
            payload = service.queue_gate_supplement_refresh(
                duckdb_path=str(tmp_path / "moss.duckdb"),
                governance_path=str(governance_path),
                as_of_date=date(2026, 4, 30),
                lookback_days=30,
                idempotency_key="same-key",
            )
        except Exception as exc:  # noqa: BLE001
            with results_lock:
                errors.append(exc)
            return
        with results_lock:
            results.append(payload)

    first_thread = Thread(target=invoke_retry)
    second_thread = Thread(target=invoke_retry)
    first_thread.start()
    second_thread.start()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    retry_run_ids = {cast(str, payload["run_id"]) for payload in results}
    assert len(retry_run_ids) == 1
    replay_flags = [payload["idempotency_replay"] for payload in results]
    assert replay_flags.count(False) == 1
    assert replay_flags.count(True) == 1
    assert len(sent) == 2
    assert sent[-1]["run_id"] in retry_run_ids


def test_livermore_queue_keeps_replaying_non_stale_terminal_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import (
        livermore_gate_supplement_compute_service as service,
    )

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
    repo = GovernanceRepository(base_dir=governance_path)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **repo.read_all(CACHE_BUILD_RUN_STREAM)[-1],
            "status": "failed",
            "trigger_mode": "terminal",
            "finished_at": datetime.now(UTC).isoformat(),
            "failure_category": "materialization_failure",
            "failure_reason": "RuntimeError",
            "error_message": "worker failed",
        },
    )

    replay = service.queue_gate_supplement_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(governance_path),
        as_of_date=date(2026, 4, 30),
        lookback_days=30,
        idempotency_key="same-key",
    )

    assert replay["run_id"] == first["run_id"]
    assert replay["status"] == "failed"
    assert replay["idempotency_replay"] is True
    assert len(sent) == 1


def test_livermore_status_route_returns_404_for_unknown_run(tmp_path, monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route

    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            governance_path=tmp_path / "governance",
        ),
    )

    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="reader", role="admin")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/ui/market-data/livermore/refresh-gate-supplement/status",
        params={"run_id": "missing-run"},
    )

    assert response.status_code == 404
    assert "missing-run" in response.text


@pytest.mark.parametrize("params", [{}, {"run_id": ""}, {"run_id": "   "}])
def test_livermore_status_route_rejects_missing_or_blank_run_id(tmp_path, monkeypatch, params) -> None:
    from backend.app.api.routes import market_data_livermore as route

    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            governance_path=tmp_path / "governance",
        ),
    )

    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="operator", role="admin")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/ui/market-data/livermore/refresh-gate-supplement/status",
        params=params,
    )

    assert response.status_code == 422


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

    payload = task.run_livermore_gate_supplement_refresh(
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


def test_livermore_worker_actor_disables_hidden_retries() -> None:
    from backend.app.tasks import livermore_gate_supplement as task

    actor_options = cast(dict[str, object], task.run_livermore_gate_supplement_refresh_task.options)
    assert actor_options["max_retries"] == 0
