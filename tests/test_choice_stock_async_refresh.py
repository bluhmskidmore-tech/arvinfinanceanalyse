from __future__ import annotations

from backend.app.services import macro_toolkit_route_support as macro_toolkit_support

import inspect
import json
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
        macro_toolkit_support,
        "_choice_stock_refresh_overview",
        lambda *_args, **_kwargs: {"refresh": {"status": "queued"}},
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
    assert "user_id" not in public["permission"]
    assert "role" not in public["permission"]
    assert "identity_source" not in public["permission"]


def test_choice_stock_refresh_status_is_owner_scoped_for_explicit_and_latest_runs(tmp_path) -> None:
    from backend.app.services import macro_toolkit_service as service

    governance_path = tmp_path / "governance"
    owner_permission = {
        "mode": "scoped_refresh",
        "allowed": True,
        "user_id": "choice-owner",
        "role": "viewer",
        "identity_source": "header",
        "resource": "macro_toolkit.choice_stock",
        "actions": ["history", "factor_snapshot", "theme_overlay"],
    }
    other_permission = {
        **owner_permission,
        "user_id": "choice-other",
    }
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-owner-older",
            status="completed",
            as_of_date="2026-04-29",
            permission=owner_permission,
        ),
    )
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-other-latest",
            status="completed",
            as_of_date="2026-04-30",
            permission=other_permission,
        ),
    )
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-owner-latest",
            status="completed",
            as_of_date="2026-05-01",
            permission=owner_permission,
        ),
    )
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-owner-missing",
            status="completed",
            as_of_date="2026-05-02",
        ),
    )

    explicit = service.choice_stock_refresh_status(
        governance_path,
        run_id="choice-owner-latest",
        expected_user_id="choice-owner",
    )
    latest = service.choice_stock_refresh_status(
        governance_path,
        expected_user_id="choice-owner",
    )

    assert explicit["run_id"] == "choice-owner-latest"
    assert latest["run_id"] == "choice-owner-latest"
    assert "user_id" not in explicit["permission"]
    assert "role" not in explicit["permission"]
    assert "identity_source" not in explicit["permission"]

    with pytest.raises(PermissionError, match="Choice stock refresh run not found."):
        service.choice_stock_refresh_status(
            governance_path,
            run_id="choice-owner-latest",
            expected_user_id="choice-other",
        )
    with pytest.raises(PermissionError, match="Choice stock refresh run not found."):
        service.choice_stock_refresh_status(
            governance_path,
            run_id="choice-owner-missing",
            expected_user_id="choice-owner",
        )
    idle = service.choice_stock_refresh_status(
        governance_path,
        expected_user_id="unknown-owner",
    )
    assert idle["status"] == "idle"
    assert idle["run_id"] is None


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


def test_choice_stock_idempotency_key_does_not_replay_across_owners(
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
    owner_one = {
        "mode": "scoped_refresh",
        "allowed": True,
        "user_id": "choice-owner-one",
        "role": "viewer",
        "identity_source": "header",
        "resource": "macro_toolkit.choice_stock",
        "actions": ["history", "factor_snapshot", "theme_overlay"],
    }
    owner_two = {
        **owner_one,
        "user_id": "choice-owner-two",
    }
    first = service.queue_choice_stock_refresh(
        **{
            **_choice_queue_kwargs(tmp_path),
            "permission": owner_one,
        }
    )
    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    queued = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **queued,
            "status": "completed",
            "trigger_mode": "terminal",
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )
    second = service.queue_choice_stock_refresh(
        **{
            **_choice_queue_kwargs(tmp_path),
            "permission": owner_two,
        }
    )

    assert first.payload["run_id"] != second.payload["run_id"]
    assert len(sent) == 2


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


def test_choice_stock_actor_defers_livermore_closure_by_default_but_allows_explicit_opt_in(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service
    from backend.app.tasks import choice_stock_refresh as task

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_run_choice_stock_refresh_job",
        lambda **kwargs: calls.append(dict(kwargs)),
    )

    task.run_choice_stock_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(tmp_path / "governance"),
        archive_root=str(tmp_path / "archive"),
        run_id="choice-stock-full-closure",
        as_of_date="2026-08-18",
        queued_at="2026-08-18T10:00:00Z",
        refresh_history=True,
        refresh_factors=True,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission={"allowed": True},
    )

    assert calls[0]["complete_livermore_chain"] is False
    assert calls[0]["retry_managed_by_broker"] is True

    calls.clear()
    task.run_choice_stock_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(tmp_path / "governance"),
        archive_root=str(tmp_path / "archive"),
        run_id="choice-stock-explicit-full-closure",
        as_of_date="2026-08-18",
        queued_at="2026-08-18T10:00:00Z",
        refresh_history=True,
        refresh_factors=True,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission={"allowed": True},
        complete_livermore_chain=True,
    )

    assert calls[0]["complete_livermore_chain"] is True


def test_choice_stock_worker_full_closure_finishes_before_completed_record(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    governance_path = tmp_path / "governance"
    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 100,
            "stock_code_count": 100,
            "run_id": "choice-stock-materialize-fixture",
            "as_of_date": "2026-08-18",
            "source_version": "sv-choice-fixture",
            "vendor_version": "vv-choice-fixture",
            "rule_version": "rv-choice-fixture",
            "completed_request_items": ["stock_ohlcv:daily_ohlcv_amount"],
        },
    )
    monkeypatch.setattr(
        service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 100,
            "source_version": "sv-factor-fixture",
            "vendor_version": "vv-factor-fixture",
        },
    )
    monkeypatch.setattr(
        service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 100,
    )
    closure_calls: list[dict[str, object]] = []

    def fake_closure(**kwargs):
        closure_calls.append(dict(kwargs))
        repo = GovernanceRepository(base_dir=governance_path)
        records = repo.read_all(
            CACHE_BUILD_RUN_STREAM
        )
        assert [row["status"] for row in records] == ["running"]
        manifest = repo.read_latest_manifest("choice_stock.history_and_factor_snapshot")
        assert manifest is not None
        assert manifest["report_date"] == "2026-08-18"
        return {
            "status": "completed",
            "target_date": "2026-08-18",
            "steps": [{"name": "candidate_history", "result": {"status": "ok"}}],
        }

    monkeypatch.setattr(
        service,
        "run_livermore_daily_pretrade_refresh",
        fake_closure,
        raising=False,
    )

    service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(tmp_path / "archive"),
        run_id="choice-stock-full-closure-worker",
        as_of_date="2026-08-18",
        queued_at="2026-08-18T10:00:00Z",
        refresh_history=True,
        refresh_factors=True,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission={"allowed": True},
        complete_livermore_chain=True,
    )

    assert closure_calls == [
        {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "target_date": "2026-08-18",
            "skip_upstream_probe": True,
            "theme_overlay_mode": "archive",
            "export_pretrade": False,
        }
    ]
    records = GovernanceRepository(base_dir=governance_path).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert [row["status"] for row in records] == ["running", "completed"]
    assert records[-1]["livermore_closure_status"] == "completed"


def test_choice_stock_worker_full_closure_partial_is_terminal_without_retry(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    governance_path = tmp_path / "governance"
    completion_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "append_choice_stock_refresh_completion",
        lambda **kwargs: completion_calls.append(dict(kwargs)),
    )
    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 100,
            "stock_code_count": 100,
            "run_id": "choice-stock-materialize-fixture",
            "as_of_date": "2026-08-18",
            "source_version": "sv-choice-fixture",
            "vendor_version": "vv-choice-fixture",
            "rule_version": "rv-choice-fixture",
            "completed_request_items": ["stock_ohlcv:daily_ohlcv_amount"],
        },
    )
    monkeypatch.setattr(
        service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 100,
            "source_version": "sv-factor-fixture",
            "vendor_version": "vv-factor-fixture",
        },
    )
    monkeypatch.setattr(
        service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 100,
    )
    monkeypatch.setattr(
        service,
        "run_livermore_daily_pretrade_refresh",
        lambda **_kwargs: {
            "status": "partial",
            "reason": "signal_confluence_replay_not_ready",
            "target_date": "2026-08-18",
            "theme_overlay": {
                "status": "completed",
                "overlay_status": "completed",
                "member_count": 12,
                "message": "overlay archived",
            },
        },
        raising=False,
    )

    service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(tmp_path / "archive"),
        run_id="choice-stock-full-closure-partial",
        as_of_date="2026-08-18",
        queued_at="2026-08-18T10:00:00Z",
        refresh_history=True,
        refresh_factors=True,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission={"allowed": True},
        complete_livermore_chain=True,
    )

    records = GovernanceRepository(base_dir=governance_path).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert [row["status"] for row in records] == ["running", "partial"]
    assert completion_calls == []
    assert records[-1]["livermore_closure_status"] == "partial"
    assert records[-1]["livermore_closure_reason"] == "signal_confluence_replay_not_ready"
    assert records[-1]["history_row_count"] == 100
    assert records[-1]["factor_row_count"] == 100
    assert records[-1]["theme_overlay_status"] == "completed"
    assert records[-1]["theme_overlay_message"] == "overlay archived"
    assert records[-1]["theme_overlay_member_count"] == 12
    assert records[-1]["retryable"] is False
    assert records[-1]["error_message"] is None
    assert records[-1]["failure_category"] is None
    assert records[-1]["failure_reason"] is None


def test_stalled_choice_stock_running_record_is_terminal_and_does_not_block_dispatch(
    tmp_path,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    governance_path = tmp_path / "governance"
    service.append_choice_stock_refresh_run(
        governance_path,
        service.build_choice_stock_refresh_run_payload(
            run_id="choice-stock-stalled",
            status="running",
            as_of_date="2026-08-18",
            started_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        ),
    )

    status = service.choice_stock_refresh_status(governance_path)

    assert status["status"] == "failed"
    assert status["failure_category"] == "worker_failure"
    assert status["stalled"] is True
    assert "failure_reason" not in status
    assert (
        service.latest_choice_stock_inflight_refresh(
            governance_path,
            as_of_date="2026-08-18",
        )
        is None
    )


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


def test_choice_stock_sync_failure_is_terminal_without_broker_retry(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.services import macro_toolkit_service as service

    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError(
                "choice vendor failed token=TOP-SECRET api_key=LEAKED-KEY "
                "UNLABELED-CHOICE-CREDENTIAL"
            )
        ),
    )
    monkeypatch.setenv("CHOICE_API_KEY", "UNLABELED-CHOICE-CREDENTIAL")

    with pytest.raises(RuntimeError, match="choice vendor failed"):
        service._run_choice_stock_refresh_job(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            catalog_path=str(tmp_path / "choice-stock-catalog.json"),
            governance_path=str(tmp_path / "governance"),
            archive_root=str(tmp_path / "archive"),
            run_id="choice-sync-failure",
            as_of_date="2026-04-30",
            queued_at="2026-05-01T00:00:00+00:00",
            refresh_history=True,
            refresh_factors=False,
            factor_max_stock_count=None,
            theme_overlay_mode="off",
            permission={"allowed": True},
            retry_managed_by_broker=False,
        )

    records = GovernanceRepository(base_dir=tmp_path / "governance").read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["running", "failed"]
    assert records[-1]["attempt_count"] == 1
    assert records[-1]["retryable"] is False
    serialized_records = json.dumps(records, ensure_ascii=False)
    assert "TOP-SECRET" not in serialized_records
    assert "LEAKED-KEY" not in serialized_records
    assert "UNLABELED-CHOICE-CREDENTIAL" not in serialized_records
    assert "***" in serialized_records


def test_choice_stock_full_closure_preserves_upstream_failure_record(tmp_path, monkeypatch) -> None:
    from backend.app.services import macro_toolkit_service as service

    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("choice connection closed")),
    )

    with pytest.raises(RuntimeError, match="choice connection closed"):
        service._run_choice_stock_refresh_job(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            catalog_path=str(tmp_path / "choice-stock-catalog.json"),
            governance_path=str(tmp_path / "governance"),
            archive_root=str(tmp_path / "archive"),
            run_id="choice-full-closure-upstream-failure",
            as_of_date="2026-08-18",
            queued_at="2026-08-19T00:00:00+00:00",
            refresh_history=True,
            refresh_factors=True,
            factor_max_stock_count=None,
            theme_overlay_mode="archive",
            permission={"allowed": True},
            complete_livermore_chain=True,
        )

    records = GovernanceRepository(base_dir=tmp_path / "governance").read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["running", "retrying"]
    assert records[-1]["failure_reason"] == "choice connection closed"
    assert records[-1]["livermore_closure_status"] == "failed"
    assert records[-1]["livermore_closure_reason"] == "choice connection closed"


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
