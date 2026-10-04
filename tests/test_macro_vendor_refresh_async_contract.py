from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]


def _append_refresh_state(
    governance_path: Path,
    *,
    run_id: str,
    status: str,
    status_deadline_at: str | None = None,
) -> None:
    GovernanceRepository(base_dir=governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "job_name": "choice_macro_refresh",
            "cache_key": "choice_macro.latest",
            "run_id": run_id,
            "status": status,
            "status_deadline_at": status_deadline_at,
        },
    )


def _status_route(tmp_path: Path, monkeypatch, *, run_id: str) -> dict[str, object]:
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    class _Settings:
        governance_path = tmp_path

    monkeypatch.setattr(route_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(route_module, "_ensure_macro_vendor_read_allowed", lambda _auth: None)
    return route_module.choice_series_refresh_status(
        auth=route_module.AuthContext(),
        run_id=run_id,
    )


def test_choice_macro_refresh_status_reads_governance_runs(tmp_path):
    from backend.app.services.macro_vendor_service import choice_macro_refresh_status

    _append_refresh_state(tmp_path, run_id="choice-run-1", status="running")

    payload = choice_macro_refresh_status(tmp_path, run_id="choice-run-1")

    assert payload["run_id"] == "choice-run-1"
    assert payload["trigger_mode"] == "async"
    with pytest.raises(ValueError, match="missing-run"):
        choice_macro_refresh_status(tmp_path, run_id="missing-run")


@pytest.mark.parametrize(
    ("terminal_status", "expected_invalidations"),
    [("completed", 1), ("partial", 1), ("degraded", 1), ("failed", 0)],
)
def test_choice_macro_refresh_status_invalidates_api_process_cache_on_success_terminal(
    tmp_path,
    monkeypatch,
    terminal_status: str,
    expected_invalidations: int,
):
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    run_id = f"choice-run-{terminal_status}"
    _append_refresh_state(tmp_path, run_id=run_id, status=terminal_status)

    class _Settings:
        governance_path = tmp_path

    invalidations: list[str] = []
    monkeypatch.setattr(route_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(route_module, "_ensure_macro_vendor_read_allowed", lambda _auth: None)
    monkeypatch.setattr(
        route_module.market_home_response_cache,
        "invalidate",
        lambda: invalidations.append("api-process"),
    )

    payload = route_module.choice_series_refresh_status(
        auth=route_module.AuthContext(),
        run_id=run_id,
    )

    assert payload["status"] == terminal_status
    assert len(invalidations) == expected_invalidations


def test_choice_macro_refresh_queue_records_deadline_before_dispatch(tmp_path):
    from backend.app.services.macro_vendor_refresh_service import (
        CHOICE_MACRO_REFRESH_QUEUE_GRACE_SECONDS,
        CHOICE_MACRO_REFRESH_QUEUE_POLL_WINDOW_SECONDS,
        queue_choice_macro_refresh,
    )

    sent: list[dict[str, object]] = []

    class _Actor:
        @staticmethod
        def send(**kwargs: object) -> None:
            sent.append(kwargs)

    payload = queue_choice_macro_refresh(
        duckdb_path=tmp_path / "macro.duckdb",
        governance_path=tmp_path,
        backfill_days=30,
        refresh_task=_Actor(),
    )

    queued_at = datetime.fromisoformat(str(payload["queued_at"]))
    deadline_at = datetime.fromisoformat(str(payload["status_deadline_at"]))
    assert deadline_at - queued_at == timedelta(
        seconds=CHOICE_MACRO_REFRESH_QUEUE_POLL_WINDOW_SECONDS
        + CHOICE_MACRO_REFRESH_QUEUE_GRACE_SECONDS
    )
    assert payload["status"] == "queued"
    assert payload["trigger_mode"] == "async"
    assert sent == [
        {
            "duckdb_path": str(tmp_path / "macro.duckdb"),
            "governance_dir": str(tmp_path),
            "run_id": payload["run_id"],
            "backfill_days": 30,
            "queued_at": payload["queued_at"],
            "status_deadline_at": payload["status_deadline_at"],
        }
    ]
    records = GovernanceRepository(base_dir=tmp_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert records[-1]["run_id"] == payload["run_id"]
    assert records[-1]["status"] == "queued"
    assert records[-1]["status_deadline_at"] == payload["status_deadline_at"]


def test_choice_macro_refresh_queue_dispatch_failure_is_terminal(tmp_path):
    from backend.app.services.macro_vendor_refresh_service import (
        MacroVendorQueueError,
        queue_choice_macro_refresh,
    )

    class _BrokenActor:
        @staticmethod
        def send(**_kwargs: object) -> None:
            raise RuntimeError("broker unavailable")

    with pytest.raises(MacroVendorQueueError, match="dispatch failed"):
        queue_choice_macro_refresh(
            duckdb_path=tmp_path / "macro.duckdb",
            governance_path=tmp_path,
            backfill_days=0,
            refresh_task=_BrokenActor(),
        )

    records = GovernanceRepository(base_dir=tmp_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert records[-1]["run_id"] == records[0]["run_id"]
    assert records[-1]["failure_category"] == "queue_dispatch_failure"


def test_choice_macro_refresh_worker_retries_transient_running_append(tmp_path, monkeypatch):
    from backend.app.observability import response_cache
    from backend.app.tasks import choice_macro as task_module

    real_repo = GovernanceRepository(base_dir=tmp_path)

    class _TransientRepo:
        append_calls = 0

        def __init__(self, *, base_dir: str):
            assert Path(base_dir) == tmp_path

        def append(self, stream: str, payload: dict[str, object]):
            type(self).append_calls += 1
            if type(self).append_calls == 1:
                raise OSError("temporary governance contention")
            return real_repo.append(stream, payload)

    monkeypatch.setattr(task_module, "GovernanceRepository", _TransientRepo)
    monkeypatch.setattr(task_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        task_module,
        "_refresh_choice_macro_snapshot",
        lambda **kwargs: {
            "status": "completed",
            "run_id": str(kwargs["run_id"]),
            "source_version": "sv_choice",
            "vendor_version": "vv_choice",
        },
    )
    monkeypatch.setattr(
        task_module,
        "refresh_public_cross_asset_headlines",
        lambda **_kwargs: {"status": "completed", "run_id": "public:test"},
    )
    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", lambda: None)

    payload = task_module.run_choice_macro_refresh_workflow.fn(
        duckdb_path=str(tmp_path / "macro.duckdb"),
        governance_dir=str(tmp_path),
        run_id="choice_macro_refresh:transient-append",
        backfill_days=3,
    )

    assert payload["status"] == "completed"
    assert _TransientRepo.append_calls == 3
    assert [record["status"] for record in real_repo.read_all(CACHE_BUILD_RUN_STREAM)] == [
        "running",
        "completed",
    ]


def test_choice_macro_refresh_running_append_failure_eventually_returns_503(tmp_path, monkeypatch):
    from backend.app.services import macro_vendor_service
    from backend.app.tasks import choice_macro as task_module

    run_id = "choice_macro_refresh:running-append-failed"
    queued_at = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)
    deadline = queued_at + timedelta(minutes=7)
    _append_refresh_state(
        tmp_path,
        run_id=run_id,
        status="queued",
        status_deadline_at=deadline.isoformat(),
    )

    class _BrokenRepo:
        append_calls = 0

        def __init__(self, *, base_dir: str):
            assert Path(base_dir) == tmp_path

        def append(self, _stream: str, _payload: dict[str, object]):
            type(self).append_calls += 1
            raise OSError("governance unavailable")

    monkeypatch.setattr(task_module, "GovernanceRepository", _BrokenRepo)
    monkeypatch.setattr(task_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="governance state could not be persisted"):
        task_module.run_choice_macro_refresh_workflow.fn(
            duckdb_path=str(tmp_path / "macro.duckdb"),
            governance_dir=str(tmp_path),
            run_id=run_id,
            backfill_days=0,
            queued_at=queued_at.isoformat(),
            status_deadline_at=deadline.isoformat(),
        )

    assert _BrokenRepo.append_calls == 3

    monkeypatch.setattr(
        macro_vendor_service,
        "_choice_macro_refresh_now",
        lambda: deadline - timedelta(seconds=1),
    )
    assert macro_vendor_service.choice_macro_refresh_status(tmp_path, run_id=run_id)["status"] == "queued"

    monkeypatch.setattr(
        macro_vendor_service,
        "_choice_macro_refresh_now",
        lambda: deadline + timedelta(seconds=1),
    )
    with pytest.raises(HTTPException) as exc_info:
        _status_route(tmp_path, monkeypatch, run_id=run_id)
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "code": "choice_macro_refresh_status_deadline_exceeded",
        "message": "Choice macro refresh terminal status is unavailable after its governed deadline.",
        "error_message": "Choice macro refresh terminal status is unavailable after its governed deadline.",
        "run_id": run_id,
        "last_status": "queued",
    }


def test_choice_macro_refresh_terminal_append_failure_is_running_until_deadline_then_503(
    tmp_path,
    monkeypatch,
):
    from backend.app.observability import response_cache
    from backend.app.services import macro_vendor_service
    from backend.app.services.macro_vendor_refresh_service import (
        CHOICE_MACRO_REFRESH_TASK_GRACE_SECONDS,
        CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_MS,
        CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_SECONDS,
    )
    from backend.app.tasks import choice_macro as task_module

    run_id = "choice_macro_refresh:terminal-append-failed"
    real_repo = GovernanceRepository(base_dir=tmp_path)

    class _TerminalBrokenRepo:
        append_calls = 0

        def __init__(self, *, base_dir: str):
            assert Path(base_dir) == tmp_path

        def append(self, stream: str, payload: dict[str, object]):
            type(self).append_calls += 1
            if type(self).append_calls == 1:
                return real_repo.append(stream, payload)
            raise OSError("governance unavailable")

    monkeypatch.setattr(task_module, "GovernanceRepository", _TerminalBrokenRepo)
    monkeypatch.setattr(task_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        task_module,
        "_refresh_choice_macro_snapshot",
        lambda **kwargs: {
            "status": "completed",
            "run_id": str(kwargs["run_id"]),
            "source_version": "sv_choice",
            "vendor_version": "vv_choice",
        },
    )
    monkeypatch.setattr(
        task_module,
        "refresh_public_cross_asset_headlines",
        lambda **_kwargs: {"status": "completed", "run_id": "public:test"},
    )
    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", lambda: None)

    with pytest.raises(RuntimeError, match="governance state could not be persisted"):
        task_module.run_choice_macro_refresh_workflow.fn(
            duckdb_path=str(tmp_path / "macro.duckdb"),
            governance_dir=str(tmp_path),
            run_id=run_id,
            backfill_days=30,
        )

    assert _TerminalBrokenRepo.append_calls == 4
    records = real_repo.read_all(CACHE_BUILD_RUN_STREAM)
    assert [record["status"] for record in records] == ["running"]
    deadline = datetime.fromisoformat(str(records[0]["status_deadline_at"]))
    started_at = datetime.fromisoformat(str(records[0]["started_at"]))
    assert deadline - started_at == timedelta(
        seconds=CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_SECONDS
        + CHOICE_MACRO_REFRESH_TASK_GRACE_SECONDS
    )
    assert task_module.run_choice_macro_refresh_workflow.options["time_limit"] == (
        CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_MS
    )

    monkeypatch.setattr(
        macro_vendor_service,
        "_choice_macro_refresh_now",
        lambda: deadline - timedelta(seconds=1),
    )
    assert macro_vendor_service.choice_macro_refresh_status(tmp_path, run_id=run_id)["status"] == "running"

    monkeypatch.setattr(
        macro_vendor_service,
        "_choice_macro_refresh_now",
        lambda: deadline + timedelta(seconds=1),
    )
    with pytest.raises(HTTPException) as exc_info:
        _status_route(tmp_path, monkeypatch, run_id=run_id)
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "choice_macro_refresh_status_deadline_exceeded"
    assert exc_info.value.detail["error_message"] == (
        "Choice macro refresh terminal status is unavailable after its governed deadline."
    )
    assert exc_info.value.detail["run_id"] == run_id
    assert exc_info.value.detail["last_status"] == "running"


def test_choice_macro_refresh_worker_records_completed_and_invalidates_worker_cache(tmp_path, monkeypatch):
    from backend.app.observability import response_cache
    from backend.app.services.macro_vendor_service import choice_macro_refresh_status
    from backend.app.tasks import choice_macro as task_module

    invalidations: list[str] = []

    def _choice_refresh(**kwargs: object) -> dict[str, object]:
        assert kwargs["record_build_run"] is False
        return {
            "status": "completed",
            "run_id": str(kwargs["run_id"]),
            "source_version": "sv_choice",
            "vendor_version": "vv_choice",
        }

    monkeypatch.setattr(task_module, "_refresh_choice_macro_snapshot", _choice_refresh)
    monkeypatch.setattr(
        task_module,
        "refresh_public_cross_asset_headlines",
        lambda **_kwargs: {"status": "completed", "run_id": "public:test"},
    )
    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", lambda: invalidations.append("yes"))

    payload = task_module.run_choice_macro_refresh_workflow.fn(
        duckdb_path=str(tmp_path / "macro.duckdb"),
        governance_dir=str(tmp_path),
        run_id="choice_macro_refresh:queued-test",
        backfill_days=3,
    )

    assert payload["status"] == "completed"
    assert payload["run_id"] == "choice_macro_refresh:queued-test"
    assert invalidations == ["yes"]
    records = GovernanceRepository(base_dir=tmp_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert [record["status"] for record in records] == ["running", "completed"]
    polled = choice_macro_refresh_status(tmp_path, run_id="choice_macro_refresh:queued-test")
    assert polled["status"] == "completed"
    assert polled["trigger_mode"] == "terminal"


def test_choice_macro_refresh_worker_invalidates_cache_for_degraded_terminal(tmp_path, monkeypatch):
    from backend.app.observability import response_cache
    from backend.app.tasks import choice_macro as task_module

    invalidations: list[str] = []

    def _choice_refresh(**kwargs: object) -> dict[str, object]:
        return {
            "status": "degraded",
            "run_id": str(kwargs["run_id"]),
            "quality_flag": "warning",
            "warning_code": "gate_supplement_failed",
            "warnings": [{"code": "gate_supplement_failed", "message": "livermore gate supplement failed"}],
        }

    monkeypatch.setattr(task_module, "_refresh_choice_macro_snapshot", _choice_refresh)
    monkeypatch.setattr(
        task_module,
        "refresh_public_cross_asset_headlines",
        lambda **_kwargs: {"status": "skipped"},
    )
    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", lambda: invalidations.append("yes"))

    payload = task_module.run_choice_macro_refresh_workflow.fn(
        duckdb_path=str(tmp_path / "macro.duckdb"),
        governance_dir=str(tmp_path),
        run_id="choice_macro_refresh:degraded-test",
        backfill_days=3,
    )

    assert payload["status"] == "degraded"
    assert payload["quality_flag"] == "warning"
    assert invalidations == ["yes"]


def test_choice_macro_refresh_worker_records_failed_terminal_when_all_sources_fail(tmp_path, monkeypatch):
    from backend.app.observability import response_cache
    from backend.app.tasks import choice_macro as task_module

    def _fail(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("source unavailable")

    invalidations: list[str] = []
    monkeypatch.setattr(task_module, "_refresh_choice_macro_snapshot", _fail)
    monkeypatch.setattr(task_module, "refresh_public_cross_asset_headlines", _fail)
    monkeypatch.setattr(task_module, "refresh_tushare_ncd_shibor_proxy", _fail)
    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", lambda: invalidations.append("yes"))

    payload = task_module.run_choice_macro_refresh_workflow.fn(
        duckdb_path=str(tmp_path / "macro.duckdb"),
        governance_dir=str(tmp_path),
        run_id="choice_macro_refresh:failed-test",
        backfill_days=0,
    )

    assert payload["status"] == "failed"
    assert invalidations == []
    records = GovernanceRepository(base_dir=tmp_path).read_all(CACHE_BUILD_RUN_STREAM)
    assert [record["status"] for record in records] == ["running", "failed"]
