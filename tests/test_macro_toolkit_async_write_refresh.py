from __future__ import annotations

import importlib
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.app.api.routes import macro_toolkit as route
from backend.app.api.routes.macro_toolkit import router
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.services import macro_toolkit_service as service
from fastapi import FastAPI
from fastapi.testclient import TestClient


class RecordingActor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: Exception | None = None
        self.fn_accessed = False

    def send(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return object()

    @property
    def fn(self) -> object:
        self.fn_accessed = True
        raise AssertionError("production must not run a synchronous task fallback")


def test_cffex_service_only_sends_once_for_repeated_key_and_has_no_sync_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_cffex_member_rank_refresh_task", actor, raising=False
    )
    monkeypatch.setattr(
        service,
        "materialize_cffex_member_rank",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("worker-only materialize")
        ),
        raising=False,
    )
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(tmp_path / "gov"),
        "trade_date": "2026-04-10",
        "contracts": ("T.CFE",),
        "sources": ("choice",),
        "idempotency_key": " cffex-key ",
    }

    first = service.refresh_cffex_member_rank(**kwargs)
    replay = service.refresh_cffex_member_rank(**kwargs)

    assert first.payload["status"] == "queued"
    assert first.quality_flag == "warning"
    assert "duckdb_path" not in first.payload
    assert replay.payload["run_id"] == first.payload["run_id"]
    assert replay.payload["idempotency_replay"] is True
    assert replay.quality_flag == "warning"
    assert "duckdb_path" not in replay.payload
    assert len(actor.calls) == 1

    governance_sql_dsn = f"sqlite:///{(tmp_path / 'governance-production.db').as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", governance_sql_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", governance_sql_dsn)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    actor.error = ConnectionError("broker unavailable")
    with pytest.raises(service.MacroToolkitQueueError):
        service.refresh_cffex_member_rank(
            **{
                **kwargs,
                "duckdb_path": str(tmp_path / "failure.duckdb"),
                "governance_path": str(tmp_path / "gov-failure"),
                "trade_date": "2026-04-11",
                "idempotency_key": None,
            }
        )
    assert actor.fn_accessed is False


def test_macro_source_backfill_endpoint_returns_202_and_queues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "gov",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    monkeypatch.setattr(
        route, "_ensure_source_backfill_refresh_allowed", lambda *_a, **_k: None
    )

    def fake_queue(**kwargs: object) -> service.MacroToolkitActionResult:
        calls.append(dict(kwargs))
        return service.MacroToolkitActionResult(
            payload={"status": "queued", "run_id": "source-run"},
            quality_flag="warning",
            as_of_date="2026-04-30",
        )

    monkeypatch.setattr(
        service, "queue_macro_source_backfill", fake_queue, raising=False
    )
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/ui/macro/toolkit/source-backfill/refresh",
        json={
            "alias": "M0041813",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ["tushare_macro"],
        },
        headers={"X-User-Id": "macro-user", "Idempotency-Key": "source-key"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["result"]["refresh"]["run_id"] == "source-run"
    assert calls[0]["governance_path"] == str(settings.governance_path)
    assert calls[0]["idempotency_key"] == "source-key"


def test_macro_source_service_dispatches_once_for_repeated_key(
    tmp_path, monkeypatch
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_macro_source_backfill_refresh_task", actor, raising=False
    )
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(tmp_path / "gov"),
        "alias": "M0041813",
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "backfill_mode": "macro_series",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "sources": ("tushare_macro",),
        "idempotency_key": " source-key ",
    }

    first = service.queue_macro_source_backfill(**kwargs)
    replay = service.queue_macro_source_backfill(**kwargs)

    assert first.payload["status"] == "queued"
    assert first.quality_flag == "warning"
    assert "duckdb_path" not in first.payload
    assert replay.payload["run_id"] == first.payload["run_id"]
    assert replay.payload["idempotency_replay"] is True
    assert replay.quality_flag == "warning"
    assert "duckdb_path" not in replay.payload
    assert len(actor.calls) == 1


@pytest.mark.parametrize(
    ("job_family", "terminal_status", "expected_quality"),
    (
        ("cffex", "completed", "ok"),
        ("cffex", "partial", "warning"),
        ("source", "completed", "ok"),
        ("source", "failed", "warning"),
    ),
)
def test_write_refresh_idempotency_replay_quality_matches_terminal_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_family: str,
    terminal_status: str,
    expected_quality: str,
) -> None:
    actor = RecordingActor()
    governance_path = tmp_path / job_family
    if job_family == "cffex":
        monkeypatch.setattr(
            service,
            "run_cffex_member_rank_refresh_task",
            actor,
            raising=False,
        )
        queue = service.refresh_cffex_member_rank
        kwargs = {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_path": str(governance_path),
            "trade_date": "2026-04-10",
            "contracts": ("T.CFE",),
            "sources": ("choice",),
            "idempotency_key": "quality-key",
        }
    else:
        monkeypatch.setattr(
            service,
            "run_macro_source_backfill_refresh_task",
            actor,
            raising=False,
        )
        queue = service.queue_macro_source_backfill
        kwargs = {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_path": str(governance_path),
            "alias": "M0041813",
            "series_id": "NCD.SHIBOR.3M",
            "series_name": "SHIBOR:3M",
            "backfill_mode": "macro_series",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ("tushare_macro",),
            "idempotency_key": "quality-key",
        }

    queue(**kwargs)
    repo = GovernanceRepository(base_dir=governance_path)
    internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": terminal_status,
            "trigger_mode": "terminal",
            "retryable": False,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )

    replay = queue(**kwargs)

    assert replay.payload["status"] == terminal_status
    assert replay.payload["idempotency_replay"] is True
    assert replay.quality_flag == expected_quality
    assert len(actor.calls) == 1


def test_write_refresh_status_services_return_latest_safe_record(
    tmp_path: Path,
) -> None:
    governance_path = tmp_path / "gov"
    repo = GovernanceRepository(base_dir=governance_path)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "cffex-status-run",
            "job_name": service.CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
            "cache_key": service.CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
            "status": "running",
            "trade_date": "2026-04-10",
            "contracts": ["T.CFE"],
            "sources": ["choice"],
            "row_count": None,
            "duckdb_path": r"C:\private\moss.duckdb",
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "cffex-status-run",
            "job_name": service.CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
            "cache_key": service.CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
            "status": "partial",
            "trade_date": "2026-04-10",
            "contracts": ["T.CFE"],
            "sources": ["choice", "tushare"],
            "row_count": 7,
            "attempt_count": 2,
            "error_message": r"token=secret C:\private\vendor.json",
            "result": {"private": "worker-only"},
            "duckdb_path": r"C:\private\moss.duckdb",
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-status-run",
            "job_name": service.MACRO_SOURCE_BACKFILL_JOB_NAME,
            "cache_key": service.MACRO_SOURCE_BACKFILL_CACHE_KEY,
            "status": "completed",
            "report_date": "2026-04-30",
            "alias": "m0041813",
            "series_ids": ["NCD.SHIBOR.3M"],
            "series_names": ["SHIBOR:3M"],
            "backfill_mode": "macro_series",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ["tushare_macro"],
            "total_added": 3,
            "total_fetched": 4,
            "processed_count": 1,
            "duckdb_path": r"C:\private\moss.duckdb",
            "failure_reason": "raw internal failure detail",
        },
    )

    cffex = service.cffex_member_rank_refresh_status(
        governance_path,
        run_id="cffex-status-run",
    )
    source = service.macro_source_backfill_refresh_status(
        governance_path,
        run_id="source-status-run",
    )

    assert cffex["status"] == "partial"
    assert cffex["row_count"] == 7
    assert cffex["attempt_count"] == 2
    assert source["status"] == "completed"
    assert source["total_added"] == 3
    for payload in (cffex, source):
        assert "duckdb_path" not in payload
        assert "error_message" not in payload
        assert "failure_reason" not in payload
        assert "result" not in payload
        assert "secret" not in str(payload)
        assert "private" not in str(payload)


def test_write_refresh_status_services_raise_clear_not_found(
    tmp_path: Path,
) -> None:
    governance_path = tmp_path / "gov"

    with pytest.raises(
        ValueError,
        match="CFFEX member-rank refresh run not found: missing-cffex",
    ):
        service.cffex_member_rank_refresh_status(
            governance_path,
            run_id="missing-cffex",
        )
    with pytest.raises(
        ValueError,
        match="Macro source backfill refresh run not found: missing-source",
    ):
        service.macro_source_backfill_refresh_status(
            governance_path,
            run_id="missing-source",
        )


def test_write_refresh_status_endpoints_return_envelopes_and_map_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "gov",
    )
    repo = GovernanceRepository(base_dir=settings.governance_path)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "cffex-http-run",
            "job_name": service.CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
            "cache_key": service.CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
            "status": "completed",
            "trade_date": "2026-04-10",
            "row_count": 9,
            "contracts": ["T.CFE"],
            "sources": ["choice"],
            "duckdb_path": r"C:\private\moss.duckdb",
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-http-run",
            "job_name": service.MACRO_SOURCE_BACKFILL_JOB_NAME,
            "cache_key": service.MACRO_SOURCE_BACKFILL_CACHE_KEY,
            "status": "completed",
            "report_date": "2026-04-30",
            "alias": "m0041813",
            "series_ids": ["NCD.SHIBOR.3M"],
            "series_names": ["SHIBOR:3M"],
            "backfill_mode": "macro_series",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ["tushare_macro"],
            "total_added": 5,
        },
    )
    permission_checks: list[str] = []
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    monkeypatch.setattr(
        route,
        "_ensure_macro_toolkit_read_allowed",
        lambda *_args, **_kwargs: permission_checks.append("read"),
    )
    monkeypatch.setattr(
        route,
        "_cffex_member_rank_status",
        lambda *_args, **_kwargs: {
            "row_count": 9,
            "latest_trade_date": "2026-04-10",
        },
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    headers = {"X-User-Id": "macro-reader"}

    cffex_response = client.get(
        "/ui/macro/toolkit/cffex-member-rank/refresh-status",
        params={"run_id": "cffex-http-run"},
        headers=headers,
    )
    source_response = client.get(
        "/ui/macro/toolkit/source-backfill/refresh-status",
        params={"run_id": "source-http-run"},
        headers=headers,
    )
    missing_cffex = client.get(
        "/ui/macro/toolkit/cffex-member-rank/refresh-status",
        params={"run_id": "missing-cffex"},
        headers=headers,
    )
    missing_source = client.get(
        "/ui/macro/toolkit/source-backfill/refresh-status",
        params={"run_id": "missing-source"},
        headers=headers,
    )

    assert cffex_response.status_code == 200, cffex_response.text
    cffex_result = cffex_response.json()["result"]
    assert cffex_response.json()["result_meta"]["quality_flag"] == "ok"
    assert cffex_result["refresh"]["row_count"] == 9
    assert "duckdb_path" not in cffex_result["refresh"]
    assert cffex_result["cffex_member_rank"]["row_count"] == 9
    assert source_response.status_code == 200, source_response.text
    assert source_response.json()["result_meta"]["quality_flag"] == "ok"
    assert source_response.json()["result"]["refresh"]["total_added"] == 5
    assert missing_cffex.status_code == 404
    assert missing_source.status_code == 404
    assert permission_checks == ["read", "read", "read", "read"]


@pytest.mark.parametrize(
    ("backfill_mode", "expected_status"),
    (("macro_series", "completed"), ("crisis_score_inputs", "no_rows")),
)
def test_macro_source_worker_owns_backfill_and_governance_status(
    tmp_path,
    monkeypatch,
    backfill_mode,
    expected_status,
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    monkeypatch.setattr(
        task,
        "_backfill_macro_series",
        lambda **_kwargs: {"status": "completed", "total_added": 3, "errors": {}},
    )
    monkeypatch.setattr(
        task,
        "_backfill_crisis_score_inputs",
        lambda **_kwargs: {
            "results": {"M0041653": {"status": "no_rows", "written_rows": 0}},
            "errors": {},
        },
    )
    result = task.run_macro_source_backfill_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "gov"),
        run_id=f"source-{backfill_mode}",
        alias="M0041653" if backfill_mode == "crisis_score_inputs" else "M0041813",
        series_id=(
            "EMM00088132"
            if backfill_mode == "crisis_score_inputs"
            else "NCD.SHIBOR.3M"
        ),
        series_name=(
            "7D reverse repo"
            if backfill_mode == "crisis_score_inputs"
            else "SHIBOR:3M"
        ),
        backfill_mode=backfill_mode,
        start_date="2026-04-01",
        end_date="2026-04-30",
        sources=(
            ("choice_edb",)
            if backfill_mode == "crisis_score_inputs"
            else ("tushare_macro",)
        ),
    )
    records = GovernanceRepository(base_dir=tmp_path / "gov").read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert result["status"] == expected_status
    assert [record["status"] for record in records] == ["running", expected_status]
    assert records[-1]["attempt_count"] == 1


def test_cffex_worker_records_partial_and_reraises_retryable_failure(
    tmp_path, monkeypatch
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    governance_dir = tmp_path / "gov"
    monkeypatch.setattr(
        task,
        "_materialize_cffex_member_rank",
        lambda **_kwargs: {
            "trade_date": "2026-04-10",
            "row_count": 2,
            "attempts": [{"status": "materialized"}, {"status": "error"}],
        },
    )
    partial = task.run_cffex_member_rank_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(governance_dir),
        run_id="cffex-partial",
        trade_date="2026-04-10",
        contracts=("T.CFE",),
        sources=("choice", "tushare"),
    )
    assert partial["status"] == "partial"

    monkeypatch.setattr(
        task,
        "_materialize_cffex_member_rank",
        lambda **_kwargs: (_ for _ in ()).throw(ConnectionError("vendor timeout")),
    )
    with pytest.raises(ConnectionError, match="vendor timeout"):
        task.run_cffex_member_rank_refresh(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(governance_dir),
            run_id="cffex-retry",
            trade_date="2026-04-10",
            contracts=("T.CFE",),
            sources=("choice",),
        )
    retry_records = [
        record
        for record in GovernanceRepository(base_dir=governance_dir).read_all(
            CACHE_BUILD_RUN_STREAM
        )
        if record["run_id"] == "cffex-retry"
    ]
    assert [record["status"] for record in retry_records] == [
        "running",
        "retrying",
    ]
    assert retry_records[-1]["retryable"] is True


def test_cffex_worker_invalidates_market_home_cache_after_completed_append(
    tmp_path, monkeypatch
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    events: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        task,
        "_materialize_cffex_member_rank",
        lambda **_kwargs: {
            "trade_date": "2026-04-10",
            "row_count": 2,
            "attempts": [
                {"status": "materialized"},
                {"status": "materialized"},
            ],
        },
    )

    def fake_append(self, stream, record) -> None:
        events.append(("append", str(record["status"]), str(record["trigger_mode"])))

    def fake_invalidate() -> None:
        assert events == [("append", "running", "async")]
        events.append(("invalidate",))

    from backend.app.api.response_cache import market_home_response_cache

    monkeypatch.setattr(GovernanceRepository, "append", fake_append)
    monkeypatch.setattr(market_home_response_cache, "invalidate", fake_invalidate)

    result = task.run_cffex_member_rank_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "gov"),
        run_id="cffex-completed",
        trade_date="2026-04-10",
        contracts=("T.CFE",),
        sources=("choice",),
    )

    assert result["status"] == "completed"
    assert events == [
        ("append", "running", "async"),
        ("invalidate",),
        ("append", "completed", "terminal"),
    ]


def test_cffex_worker_invalidates_market_home_cache_for_partial_write(
    tmp_path, monkeypatch
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    events: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        task,
        "_materialize_cffex_member_rank",
        lambda **_kwargs: {
            "trade_date": "2026-04-10",
            "row_count": 2,
            "attempts": [{"status": "materialized"}, {"status": "error"}],
        },
    )

    def fake_append(self, stream, record) -> None:
        events.append(("append", str(record["status"]), str(record["trigger_mode"])))

    def fake_invalidate() -> None:
        events.append(("invalidate",))

    from backend.app.api.response_cache import market_home_response_cache

    monkeypatch.setattr(GovernanceRepository, "append", fake_append)
    monkeypatch.setattr(market_home_response_cache, "invalidate", fake_invalidate)

    result = task.run_cffex_member_rank_refresh(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "gov"),
        run_id="cffex-partial-cache",
        trade_date="2026-04-10",
        contracts=("T.CFE",),
        sources=("choice",),
    )

    assert result["status"] == "partial"
    assert events == [
        ("append", "running", "async"),
        ("invalidate",),
        ("append", "partial", "terminal"),
    ]


def test_cffex_cache_invalidation_retry_reuses_materialized_write(
    tmp_path, monkeypatch
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    materialize_calls: list[str] = []
    invalidation_calls: list[str] = []

    def fake_materialize(**_kwargs: object) -> dict[str, object]:
        materialize_calls.append("write")
        return {
            "trade_date": "2026-04-10",
            "row_count": 2,
            "attempts": [
                {"status": "materialized"},
                {"status": "materialized"},
            ],
        }

    def flaky_invalidate() -> None:
        invalidation_calls.append("invalidate")
        if len(invalidation_calls) == 1:
            raise RuntimeError("cache invalidation failed")

    monkeypatch.setattr(task, "_materialize_cffex_member_rank", fake_materialize)
    monkeypatch.setattr(
        task,
        "_invalidate_cffex_member_rank_caches",
        flaky_invalidate,
    )
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_dir": str(tmp_path / "gov"),
        "run_id": "cffex-invalidate-failure",
        "trade_date": "2026-04-10",
        "contracts": ("T.CFE",),
        "sources": ("choice",),
        "request_fingerprint": "request-fingerprint",
        "idempotency_key": "worker-key",
    }

    with pytest.raises(RuntimeError, match="cache invalidation failed"):
        task.run_cffex_member_rank_refresh(**kwargs)
    result = task.run_cffex_member_rank_refresh(**kwargs)

    records = GovernanceRepository(base_dir=tmp_path / "gov").read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert result["status"] == "completed"
    assert materialize_calls == ["write"]
    assert invalidation_calls == ["invalidate", "invalidate"]
    assert [record["status"] for record in records] == [
        "running",
        "retrying",
        "running",
        "completed",
    ]
    assert [record["attempt_count"] for record in records] == [1, 1, 2, 2]
    assert records[1]["result"]["row_count"] == 2
    assert records[-1]["result"]["row_count"] == 2


def test_macro_source_cache_invalidation_retry_reuses_backfill_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    backfill_calls: list[str] = []
    invalidation_calls: list[str] = []

    def fake_backfill(**_kwargs: object) -> dict[str, object]:
        backfill_calls.append("write")
        return {
            "status": "partial",
            "total_added": 3,
            "total_fetched": 4,
            "processed_count": 1,
            "errors": {"SHIBOR:3M": "one source unavailable"},
        }

    def flaky_invalidate() -> None:
        invalidation_calls.append("invalidate")
        if len(invalidation_calls) == 1:
            raise RuntimeError("macro cache invalidation failed")

    monkeypatch.setattr(task, "_backfill_macro_series", fake_backfill)
    monkeypatch.setattr(task, "_invalidate_macro_source_caches", flaky_invalidate)
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_dir": str(tmp_path / "gov"),
        "run_id": "source-invalidate-failure",
        "alias": "m0041813",
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "backfill_mode": "macro_series",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "sources": ("tushare_macro",),
    }

    with pytest.raises(RuntimeError, match="macro cache invalidation failed"):
        task.run_macro_source_backfill_refresh(**kwargs)
    result = task.run_macro_source_backfill_refresh(**kwargs)

    records = GovernanceRepository(base_dir=tmp_path / "gov").read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert result["status"] == "partial"
    assert backfill_calls == ["write"]
    assert invalidation_calls == ["invalidate", "invalidate"]
    assert [record["status"] for record in records] == [
        "running",
        "retrying",
        "running",
        "partial",
    ]
    assert [record["attempt_count"] for record in records] == [1, 1, 2, 2]
    assert records[1]["result"]["total_added"] == 3
    assert records[-1]["result"]["total_added"] == 3


def test_cffex_service_cold_import_does_not_load_task_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    code = (
        "import sys; "
        "import backend.app.services.cffex_member_rank_service; "
        "loaded = sorted(m for m in sys.modules if m.startswith('backend.app.tasks')); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_cffex_missing_read_helper_does_not_materialize(
    tmp_path, monkeypatch
) -> None:
    import pandas as pd
    from backend.app.services import cffex_member_rank_service as cffex_service

    monkeypatch.setattr(
        cffex_service, "load_member_rank_frame", lambda *_a, **_k: pd.DataFrame()
    )
    monkeypatch.setattr(
        cffex_service,
        "materialize_cffex_member_rank",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("read helper must remain read-only")
        ),
    )

    result = cffex_service.ensure_cffex_member_rank_for_request(
        duckdb_path=tmp_path / "moss.duckdb",
        trade_date="2026-04-10",
        contract="T.CFE",
    )

    assert result == {
        "status": "missing",
        "row_count": 0,
        "trade_date": "2026-04-10",
        "contract": "T.CFE",
    }


def test_macro_source_retryable_failure_blocks_duplicate_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_macro_source_backfill_refresh_task", actor, raising=False
    )
    governance_path = tmp_path / "gov"
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(governance_path),
        "alias": "M0041813",
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "backfill_mode": "macro_series",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "sources": ("tushare_macro",),
        "idempotency_key": None,
    }
    first = service.queue_macro_source_backfill(**kwargs)
    repo = GovernanceRepository(base_dir=governance_path)
    internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": "failed",
            "retryable": True,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )

    with pytest.raises(service.MacroToolkitConflictError):
        service.queue_macro_source_backfill(**kwargs)

    assert len(actor.calls) == 1

    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": "retrying",
            "retryable": True,
            "finished_at": (
                datetime.now(UTC) - timedelta(hours=2)
            ).isoformat(),
        },
    )
    stale_retry = service.queue_macro_source_backfill(**kwargs)
    assert stale_retry.payload["run_id"] != first.payload["run_id"]
    assert len(actor.calls) == 2

    stale_internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **stale_internal,
            "status": "failed",
            "retryable": False,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )
    non_retryable = service.queue_macro_source_backfill(**kwargs)
    assert non_retryable.payload["run_id"] != stale_retry.payload["run_id"]
    assert len(actor.calls) == 3


def test_cffex_retryable_failure_blocks_duplicate_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_cffex_member_rank_refresh_task", actor, raising=False
    )
    governance_path = tmp_path / "gov"
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(governance_path),
        "trade_date": "2026-04-10",
        "contracts": ("T.CFE",),
        "sources": ("choice",),
        "idempotency_key": None,
    }
    first = service.refresh_cffex_member_rank(**kwargs)
    repo = GovernanceRepository(base_dir=governance_path)
    internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": "failed",
            "retryable": True,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )

    with pytest.raises(service.MacroToolkitConflictError):
        service.refresh_cffex_member_rank(**kwargs)

    assert len(actor.calls) == 1

    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **internal,
            "status": "retrying",
            "retryable": True,
            "finished_at": (
                datetime.now(UTC) - timedelta(hours=2)
            ).isoformat(),
        },
    )
    stale_retry = service.refresh_cffex_member_rank(**kwargs)
    assert stale_retry.payload["run_id"] != first.payload["run_id"]
    assert len(actor.calls) == 2

    stale_internal = repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **stale_internal,
            "status": "failed",
            "retryable": False,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )
    non_retryable = service.refresh_cffex_member_rank(**kwargs)
    assert non_retryable.payload["run_id"] != stale_retry.payload["run_id"]
    assert len(actor.calls) == 3


@pytest.mark.parametrize("job_family", ("cffex", "source"))
def test_retryable_write_refresh_failure_is_retrying_until_budget_exhausted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_family: str,
) -> None:
    task = importlib.import_module("backend.app.tasks.macro_toolkit_write_refresh")
    governance_path = tmp_path / f"gov-{job_family}"
    if job_family == "cffex":
        monkeypatch.setattr(
            task,
            "_materialize_cffex_member_rank",
            lambda **_kwargs: (_ for _ in ()).throw(
                ConnectionError("vendor retry")
            ),
        )
        runner = task.run_cffex_member_rank_refresh
        kwargs = {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(governance_path),
            "run_id": "cffex-budget-run",
            "trade_date": "2026-04-10",
            "contracts": ("T.CFE",),
            "sources": ("choice",),
        }
        status_reader = service.cffex_member_rank_refresh_status
    else:
        monkeypatch.setattr(
            task,
            "_backfill_macro_series",
            lambda **_kwargs: (_ for _ in ()).throw(
                ConnectionError("source retry")
            ),
        )
        runner = task.run_macro_source_backfill_refresh
        kwargs = {
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(governance_path),
            "run_id": "source-budget-run",
            "alias": "m0041813",
            "series_id": "NCD.SHIBOR.3M",
            "series_name": "SHIBOR:3M",
            "backfill_mode": "macro_series",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ("tushare_macro",),
        }
        status_reader = service.macro_source_backfill_refresh_status

    for attempt in range(1, 5):
        with pytest.raises(ConnectionError, match="retry"):
            runner(**kwargs)
        refresh = status_reader(governance_path, run_id=str(kwargs["run_id"]))
        assert refresh["attempt_count"] == attempt
        if attempt < 4:
            assert refresh["status"] == "retrying"
            assert refresh["retryable"] is True
            assert refresh["trigger_mode"] == "async"
        else:
            assert refresh["status"] == "failed"
            assert refresh["retryable"] is False
            assert refresh["trigger_mode"] == "terminal"


def test_choice_stock_retry_backoff_blocks_overlapping_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service,
        "run_choice_stock_refresh_task",
        actor,
        raising=False,
    )
    governance_path = tmp_path / "gov"
    kwargs = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "catalog_path": str(tmp_path / "choice-stock-catalog.json"),
        "governance_path": str(governance_path),
        "archive_root": str(tmp_path / "archive"),
        "as_of_date": "2026-04-30",
        "refresh_history": True,
        "refresh_factors": False,
        "factor_max_stock_count": None,
        "theme_overlay_mode": "off",
        "permission": {"allowed": True},
        "idempotency_key": None,
    }
    queued = service.queue_choice_stock_refresh(**kwargs)
    monkeypatch.setattr(
        service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: (_ for _ in ()).throw(
            ConnectionError("choice vendor retry")
        ),
    )
    worker_kwargs = {
        **kwargs,
        "run_id": str(queued.payload["run_id"]),
        "queued_at": str(queued.payload["queued_at"]),
    }
    with pytest.raises(ConnectionError, match="choice vendor retry"):
        service._run_choice_stock_refresh_job(**worker_kwargs)

    refresh = service.choice_stock_refresh_status(
        governance_path,
        run_id=str(queued.payload["run_id"]),
    )
    assert refresh["status"] == "retrying"
    assert refresh["retryable"] is True
    assert refresh["trigger_mode"] == "async"
    with pytest.raises(service.MacroToolkitConflictError):
        service.queue_choice_stock_refresh(**kwargs)
    assert len(actor.calls) == 1

    for attempt in (2, 3, 4):
        with pytest.raises(ConnectionError, match="choice vendor retry"):
            service._run_choice_stock_refresh_job(**worker_kwargs)
        refresh = service.choice_stock_refresh_status(
            governance_path,
            run_id=str(queued.payload["run_id"]),
        )
        assert refresh["attempt_count"] == attempt
        if attempt < 4:
            assert refresh["status"] == "retrying"
            assert refresh["retryable"] is True
            assert refresh["trigger_mode"] == "async"
        else:
            assert refresh["status"] == "failed"
            assert refresh["retryable"] is False
            assert refresh["trigger_mode"] == "terminal"


def test_macro_source_identity_is_case_canonical_for_idempotency_and_inflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_macro_source_backfill_refresh_task", actor, raising=False
    )
    base = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(tmp_path / "gov-keyed"),
        "alias": "M0041813",
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "backfill_mode": "macro_series",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "sources": ("tushare_macro",),
        "idempotency_key": "source-case-key",
    }
    variant = {**base, "alias": "m0041813", "sources": ("TUSHARE_MACRO",)}

    first = service.queue_macro_source_backfill(**base)
    replay = service.queue_macro_source_backfill(**variant)

    assert replay.payload["run_id"] == first.payload["run_id"]
    assert replay.payload["idempotency_replay"] is True
    assert len(actor.calls) == 1
    assert first.payload["alias"] == "m0041813"
    assert first.payload["sources"] == ["tushare_macro"]
    assert actor.calls[0]["alias"] == "m0041813"
    assert actor.calls[0]["sources"] == ("tushare_macro",)

    actor.calls.clear()
    unkeyed = {
        **base,
        "governance_path": str(tmp_path / "gov-unkeyed"),
        "idempotency_key": None,
    }
    service.queue_macro_source_backfill(**unkeyed)
    with pytest.raises(service.MacroToolkitConflictError):
        service.queue_macro_source_backfill(
            **{
                **unkeyed,
                "alias": "m0041813",
                "sources": ("TUSHARE_MACRO",),
            }
        )
    assert len(actor.calls) == 1


def test_cffex_identity_is_case_canonical_for_idempotency_and_inflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = RecordingActor()
    monkeypatch.setattr(
        service, "run_cffex_member_rank_refresh_task", actor, raising=False
    )
    base = {
        "duckdb_path": str(tmp_path / "moss.duckdb"),
        "governance_path": str(tmp_path / "gov-keyed"),
        "trade_date": "2026-04-10",
        "contracts": ("T.CFE",),
        "sources": ("choice",),
        "idempotency_key": "cffex-case-key",
    }
    variant = {**base, "contracts": ("t.cfe",), "sources": ("Choice",)}

    first = service.refresh_cffex_member_rank(**base)
    replay = service.refresh_cffex_member_rank(**variant)

    assert replay.payload["run_id"] == first.payload["run_id"]
    assert replay.payload["idempotency_replay"] is True
    assert len(actor.calls) == 1
    assert first.payload["contracts"] == ["T.CFE"]
    assert first.payload["sources"] == ["choice"]
    assert actor.calls[0]["contracts"] == ("T.CFE",)
    assert actor.calls[0]["sources"] == ("choice",)

    actor.calls.clear()
    unkeyed = {
        **base,
        "governance_path": str(tmp_path / "gov-unkeyed"),
        "idempotency_key": None,
    }
    service.refresh_cffex_member_rank(**unkeyed)
    with pytest.raises(service.MacroToolkitConflictError):
        service.refresh_cffex_member_rank(
            **{
                **unkeyed,
                "contracts": ("t.cfe",),
                "sources": ("Choice",),
            }
        )
    assert len(actor.calls) == 1
