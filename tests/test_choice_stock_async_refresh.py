from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.security.auth_context import AuthContext, get_auth_context


def _choice_queue_kwargs(tmp_path) -> dict[str, object]:
    return {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "catalog_path": str(tmp_path / "choice-stock-catalog.json"),
        "governance_path": str(tmp_path / "governance"),
        "archive_root": str(tmp_path / "archive"),
        "as_of_date": "2026-04-30",
        "refresh_history": True,
        "refresh_factors": True,
        "factor_max_stock_count": None,
        "theme_overlay_mode": "off",
        "permission": {"allowed": True, "resource": "macro_toolkit.choice_stock"},
        "idempotency_key": "choice-key",
    }


def _choice_route_client(monkeypatch, tmp_path) -> TestClient:
    from backend.app.api.routes import macro_toolkit as route

    monkeypatch.setattr(route, "_ensure_choice_stock_refresh_allowed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
            governance_path=tmp_path / "governance",
            local_archive_path=tmp_path / "archive",
        ),
    )
    monkeypatch.setattr(
        route,
        "_choice_stock_refresh_overview",
        lambda *_args, **_kwargs: {"refresh": {"status": "queued"}},
    )
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="writer", role="admin")
    return TestClient(app, raise_server_exceptions=False)


def test_choice_stock_route_returns_202_and_does_not_pass_background_tasks(tmp_path, monkeypatch) -> None:
    from backend.app.api.routes import macro_toolkit as route
    from backend.app.services.macro_toolkit_service import MacroToolkitActionResult

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        route.macro_toolkit_service,
        "queue_choice_stock_refresh",
        lambda **kwargs: calls.append(dict(kwargs))
        or MacroToolkitActionResult(
            payload={"status": "queued", "run_id": "choice-route-run"},
            as_of_date="2026-04-30",
        ),
    )
    response = _choice_route_client(monkeypatch, tmp_path).post(
        "/ui/macro/toolkit/choice-stock/refresh",
        json={"as_of_date": "2026-04-30", "refresh_history": True, "refresh_factors": False},
    )

    assert response.status_code == 202
    assert response.json()["result"]["refresh"]["run_id"] == "choice-route-run"
    assert "background_tasks" not in calls[0]


def test_choice_stock_route_maps_queue_dispatch_failure_to_503(tmp_path, monkeypatch) -> None:
    from backend.app.api.routes import macro_toolkit as route

    monkeypatch.setattr(
        route.macro_toolkit_service,
        "queue_choice_stock_refresh",
        lambda **_kwargs: (_ for _ in ()).throw(
            route.macro_toolkit_service.MacroToolkitQueueError("queue dispatch failed")
        ),
    )
    response = _choice_route_client(monkeypatch, tmp_path).post(
        "/ui/macro/toolkit/choice-stock/refresh",
        json={"as_of_date": "2026-04-30", "refresh_history": True, "refresh_factors": False},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "queue dispatch failed"


@pytest.mark.parametrize(
    ("refresh_status", "expected_quality"),
    (("retrying", "warning"), ("failed", "warning"), ("completed", "ok")),
)
def test_choice_stock_status_route_quality_matches_refresh_status(
    tmp_path,
    monkeypatch,
    refresh_status: str,
    expected_quality: str,
) -> None:
    from backend.app.api.routes import macro_toolkit as route

    monkeypatch.setattr(
        route,
        "_ensure_macro_toolkit_read_allowed",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        route,
        "_choice_stock_refresh_status",
        lambda *_args, **_kwargs: {
            "run_id": "choice-quality-run",
            "status": refresh_status,
            "report_date": "2026-04-30",
        },
    )

    response = _choice_route_client(monkeypatch, tmp_path).get(
        "/ui/macro/toolkit/choice-stock/refresh-status",
        params={"run_id": "choice-quality-run"},
    )

    assert response.status_code == 200
    assert response.json()["result_meta"]["quality_flag"] == expected_quality


def test_choice_stock_queue_uses_actor_send_and_replays_without_duplicate_dispatch(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs))),
        raising=False,
    )

    assert "background_tasks" not in inspect.signature(service.queue_choice_stock_refresh).parameters
    first = service.queue_choice_stock_refresh(**_choice_queue_kwargs(tmp_path))
    second = service.queue_choice_stock_refresh(**_choice_queue_kwargs(tmp_path))

    assert first.payload["status"] == "queued"
    assert {
        "lock",
        "idempotency_key",
        "created_at",
        "error_message",
        "failure_reason",
    }.isdisjoint(first.payload)
    assert first.quality_flag == "warning"
    assert second.payload["run_id"] == first.payload["run_id"]
    assert second.payload["idempotency_replay"] is True
    assert second.quality_flag == "warning"
    assert len(sent) == 1


def test_choice_stock_public_status_redacts_internal_failure_details(tmp_path) -> None:
    from backend.app.services import macro_toolkit_service as service

    governance_path = tmp_path / "governance"
    internal = service.build_choice_stock_refresh_run_payload(
        run_id="choice-public-redaction",
        status="retrying",
        as_of_date="2026-04-30",
        error_message="ChoiceVendorError: private vendor detail",
        failure_category="ChoiceVendorError",
        failure_reason="private vendor detail",
        idempotency_key="private-idempotency-key",
        attempt_count=2,
        retryable=True,
    )
    service.append_choice_stock_refresh_run(governance_path, internal)

    public = service.choice_stock_refresh_status(
        governance_path,
        run_id="choice-public-redaction",
    )

    assert public["status"] == "retrying"
    assert public["failure_category"] == "worker_failure"
    assert public["attempt_count"] == 2
    assert public["retryable"] is True
    assert {
        "lock",
        "idempotency_key",
        "created_at",
        "error_message",
        "failure_reason",
    }.isdisjoint(public)


@pytest.mark.parametrize(
    ("terminal_status", "expected_quality"),
    (("completed", "ok"), ("failed", "warning")),
)
def test_choice_stock_idempotency_replay_quality_matches_terminal_status(
    tmp_path,
    monkeypatch,
    terminal_status: str,
    expected_quality: str,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs))),
        raising=False,
    )
    kwargs = _choice_queue_kwargs(tmp_path)
    service.queue_choice_stock_refresh(**kwargs)
    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": terminal_status,
            "retryable": False,
        },
    )

    replay = service.queue_choice_stock_refresh(**kwargs)

    assert replay.payload["status"] == terminal_status
    assert replay.payload["idempotency_replay"] is True
    assert replay.quality_flag == expected_quality
    assert len(sent) == 1


def test_choice_stock_overlay_pending_replay_is_running_warning(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs))),
        raising=False,
    )
    kwargs = {
        **_choice_queue_kwargs(tmp_path),
        "theme_overlay_mode": "archive",
    }
    service.queue_choice_stock_refresh(**kwargs)
    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": "completed",
            "theme_overlay_status": "pending",
        },
    )

    replay = service.queue_choice_stock_refresh(**kwargs)

    assert replay.payload["status"] == "running"
    assert replay.payload["choice_completion_status"] == "completed"
    assert replay.quality_flag == "warning"
    assert len(sent) == 1


def test_choice_stock_dispatch_failure_is_terminal_and_has_no_sync_fallback(tmp_path, monkeypatch) -> None:
    from backend.app.services import macro_toolkit_service as service

    sync_calls: list[str] = []
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        SimpleNamespace(send=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("broker down"))),
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_run_choice_stock_refresh_job",
        lambda **_kwargs: sync_calls.append("sync"),
    )

    with pytest.raises(service.MacroToolkitQueueError, match="queue dispatch failed"):
        service.queue_choice_stock_refresh(**_choice_queue_kwargs(tmp_path))

    records = GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
    assert sync_calls == []
    assert records[-1]["status"] == "failed"
    assert records[-1]["failure_category"] == "queue_dispatch_failure"


def test_choice_stock_worker_records_failure_and_propagates_it(tmp_path, monkeypatch) -> None:
    from backend.app.services import macro_toolkit_service as service

    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("choice vendor failed")),
    )
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "catalog_path": str(tmp_path / "choice-stock-catalog.json"),
        "governance_path": str(tmp_path / "governance"),
        "archive_root": str(tmp_path / "archive"),
        "run_id": "choice-worker-failure",
        "as_of_date": "2026-04-30",
        "queued_at": "2026-05-01T00:00:00+00:00",
        "refresh_history": True,
        "refresh_factors": False,
        "factor_max_stock_count": None,
        "theme_overlay_mode": "off",
        "permission": {"allowed": True},
        "idempotency_key": "choice-worker-key",
    }

    for attempt in range(1, 5):
        with pytest.raises(RuntimeError, match="choice vendor failed"):
            service._run_choice_stock_refresh_job(**kwargs)

        records = GovernanceRepository(
            base_dir=tmp_path / "governance"
        ).read_all(CACHE_BUILD_RUN_STREAM)
        assert records[-1]["run_id"] == "choice-worker-failure"
        assert records[-1]["attempt_count"] == attempt
        if attempt < 4:
            assert records[-1]["status"] == "retrying"
            assert records[-1]["retryable"] is True
        else:
            assert records[-1]["status"] == "failed"
            assert records[-1]["retryable"] is False


def test_choice_stock_expired_retrying_record_does_not_block_dispatch(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs))),
        raising=False,
    )
    governance_path = tmp_path / "governance"
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-expired-retry",
            status="retrying",
            as_of_date="2026-04-30",
            finished_at=(
                datetime.now(UTC) - timedelta(hours=2)
            ).isoformat(),
            refresh_history=True,
            refresh_factors=True,
            retryable=True,
        ),
    )

    queued = service.queue_choice_stock_refresh(**_choice_queue_kwargs(tmp_path))

    assert queued.payload["status"] == "queued"
    assert queued.payload["run_id"] != "choice-expired-retry"
    assert len(sent) == 1
