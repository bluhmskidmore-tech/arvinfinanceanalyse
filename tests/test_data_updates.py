"""Data-center request and worker controls use synthetic inputs and no host scheduler."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import router as api_router
from backend.app.api.routes import data_updates as routes
from backend.app.repositories import data_update_repo as repo
from backend.app.security.auth_context import AuthContext
from backend.app.services import data_update_service as service
from backend.app.tasks import data_update_center as worker

REPORT_DATE = "2026-08-31"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    input_root = tmp_path / "input"
    input_root.mkdir()
    return SimpleNamespace(
        data_input_root=input_root,
        governance_path=tmp_path / "governance",
        duckdb_path=tmp_path / "moss.duckdb",
        local_archive_path=tmp_path / "archive",
        fx_official_source_path="",
        fx_mid_csv_path="",
    )


def source_file(settings, name):
    path = settings.data_input_root / name
    path.write_bytes(b"synthetic source; formal parsers are independently tested")
    os.utime(path, (time.time() - 120, time.time() - 120))
    return path


def ready_files(settings, *, include_pnl=True):
    for name in ("ZQTZSHOW-20260831.xls", "TYWLSHOW-20260831.xls"):
        source_file(settings, name)
    if include_pnl:
        source_file(settings, "FI损益202608.xls")


def request(
    settings, monkeypatch, *, wait=True, key="request-1", workflow="core_financial"
):
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    return service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=wait,
        requested_by="operator",
        idempotency_key=key,
        workflow=workflow,
    )


def test_preflight_checks_exact_date_stability_and_workflow(settings):
    ready_files(settings, include_pnl=False)
    assert (
        service.input_preflight(settings, REPORT_DATE, "balance_daily")["ready"] is True
    )
    assert (
        service.input_preflight(settings, REPORT_DATE, "core_financial")["ready"]
        is False
    )
    assert (
        service.input_preflight(settings, "2026-07-31", "balance_daily")["ready"]
        is False
    )
    pnl = source_file(settings, "FI损益202608.xls")
    assert service.input_preflight(settings, REPORT_DATE)["ready"] is True
    os.utime(pnl, None)
    assert service.input_preflight(settings, REPORT_DATE)["ready"] is False


def test_undated_and_invalid_date_names_do_not_become_today_inputs(settings):
    for name in ("ZQTZSHOW.xls", "TYWLSHOW-20261399.xls", "FI损益.xls"):
        source_file(settings, name)
    result = service.input_preflight(settings, date.today().isoformat())
    assert result["ready"] is False
    assert all(row["files"] == [] for row in result["checks"] if row["key"] != "fx")


def test_new_request_requires_scheduler_and_immediate_inputs(settings, monkeypatch):
    monkeypatch.setattr(
        service, "scheduled_updates", lambda: {"status": "error", "tasks": []}
    )
    with pytest.raises(RuntimeError, match="后台任务"):
        service.request_core_update(
            settings,
            report_date=REPORT_DATE,
            wait_for_inputs=True,
            requested_by="operator",
            idempotency_key="new",
        )
    with pytest.raises(ValueError, match="尚未到齐"):
        request(settings, monkeypatch, wait=False)
    assert repo.latest_runs(settings.governance_path) == []


def test_existing_idempotency_receipt_survives_scheduler_outage(settings, monkeypatch):
    existing = request(settings, monkeypatch)
    unavailable = Mock(side_effect=RuntimeError("scheduler offline"))
    monkeypatch.setattr(service, "require_scheduler", unavailable)

    same = service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=True,
        requested_by="operator",
        idempotency_key="request-1",
    )
    assert same["run_id"] == existing["run_id"]
    merged = service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=True,
        requested_by="operator",
        idempotency_key="another-click",
    )
    assert merged["run_id"] == existing["run_id"]
    unavailable.assert_not_called()

    with pytest.raises(RuntimeError, match="scheduler offline"):
        service.request_core_update(
            settings,
            report_date="2026-09-01",
            wait_for_inputs=True,
            requested_by="operator",
            idempotency_key="new-date",
        )
    unavailable.assert_called_once()
    assert len(repo.latest_runs(settings.governance_path)) == 1


def test_idempotency_key_cannot_change_parameters(settings, monkeypatch):
    first = request(settings, monkeypatch)
    assert first["status"] == "waiting_inputs"
    with pytest.raises(ValueError, match="不同更新参数"):
        request(settings, monkeypatch, wait=False)
    assert len(repo.latest_runs(settings.governance_path)) == 1


def test_waiting_request_runs_once_after_arrival(settings, monkeypatch):
    request(settings, monkeypatch)
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 0
    execute.assert_not_called()
    ready_files(settings)
    assert worker.drain_updates(settings) == 0
    execute.assert_called_once()
    assert execute.call_args.args[1] == REPORT_DATE
    assert repo.latest_runs(settings.governance_path)[0]["status"] == "completed"
    worker.drain_updates(settings)
    execute.assert_called_once()


def test_cancelled_wait_does_not_execute(settings, monkeypatch):
    run = request(settings, monkeypatch)
    service.cancel_update(settings, run["run_id"], cancelled_by="operator")
    ready_files(settings)
    execute = Mock()
    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 0
    execute.assert_not_called()


def test_balance_scope_runs_without_monthly_pnl(settings, monkeypatch):
    ready_files(settings, include_pnl=False)
    request(settings, monkeypatch, wait=False, workflow="balance_daily")
    balance = Mock(return_value={"status": "completed"})
    core = Mock()
    monkeypatch.setattr(worker, "_execute_balance", balance)
    monkeypatch.setattr(worker, "_execute_core", core)
    assert worker.drain_updates(settings) == 0
    balance.assert_called_once()
    core.assert_not_called()


def test_worker_keeps_failed_step_and_does_not_claim_success(settings, monkeypatch):
    ready_files(settings)
    request(settings, monkeypatch)

    def execute(_settings, _report_date, progress):
        progress(
            {
                "steps": [
                    {
                        "name": "formal_balance",
                        "status": "completed",
                        "elapsed_seconds": 1.25,
                    },
                    {
                        "name": "verify",
                        "status": "failed",
                        "error_message": "missing date",
                    },
                ]
            }
        )
        raise ValueError("missing date")

    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert [step["status"] for step in run["steps"]] == ["completed", "failed"]
    assert run["steps"][0]["elapsed_seconds"] == 1.25


def test_transient_failure_retries_at_most_three_attempts(settings, monkeypatch):
    ready_files(settings)
    request(settings, monkeypatch)
    parse = Mock(side_effect=TimeoutError("temporary source read lock"))
    monkeypatch.setattr(
        "backend.app.services.pnl_source_service.load_latest_pnl_refresh_input",
        parse,
    )
    for attempt in range(1, 4):
        assert worker.drain_updates(settings) == 1
        run = repo.latest_runs(settings.governance_path)[0]
        assert run["attempt"] == attempt
        assert run["status"] == ("retrying" if attempt < 3 else "failed")
        repo.save_run(
            settings.governance_path,
            {**run, "retry_after": "2000-01-01T00:00:00+00:00"},
        )
    assert worker.drain_updates(settings) == 0
    assert parse.call_count == 3


def test_balance_pipeline_timeout_with_unknown_partial_write_never_retries(
    settings, monkeypatch
):
    ready_files(settings, include_pnl=False)
    request(settings, monkeypatch, workflow="balance_daily")
    pipeline = Mock(side_effect=TimeoutError("writer lock during balance update"))
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        pipeline,
    )
    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert run["retry_after"] is None
    assert run["steps"][0]["status"] == "failed"
    assert "人工复核" in run["message"]
    assert worker.drain_updates(settings) == 0
    pipeline.assert_called_once()


def test_balance_verify_timeout_after_completed_pipeline_never_replays_work(
    settings, monkeypatch
):
    ready_files(settings, include_pnl=False)
    request(settings, monkeypatch, workflow="balance_daily")
    pipeline = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        pipeline,
    )
    monkeypatch.setattr(
        worker,
        "verify_daily_balance_date",
        Mock(side_effect=TimeoutError("reader lock after balance write")),
    )
    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert run["retry_after"] is None
    assert "人工复核" in run["message"]
    assert [step["status"] for step in run["steps"]] == ["completed", "failed"]
    assert worker.drain_updates(settings) == 0
    pipeline.assert_called_once()


def test_core_progress_receipt_timeout_after_step_never_replays_work(
    settings, monkeypatch
):
    ready_files(settings)
    request(settings, monkeypatch)
    monkeypatch.setattr(
        "backend.app.services.pnl_source_service.load_latest_pnl_refresh_input",
        lambda **_kwargs: SimpleNamespace(
            report_date=REPORT_DATE, fi_rows=[{"synthetic": True}]
        ),
    )
    global_calls = 0

    def global_refresh(*, report_date, on_progress):
        nonlocal global_calls
        global_calls += 1
        assert report_date == REPORT_DATE
        on_progress({"steps": [{"name": "formal_balance", "status": "completed"}]})
        return {"status": "completed"}

    monkeypatch.setattr(
        "scripts.run_global_data_refresh.run_global_data_refresh", global_refresh
    )
    durable_save = worker.save_run
    receipt_save_failed = False

    def save_with_receipt_timeout(governance_path, run):
        nonlocal receipt_save_failed
        if (
            not receipt_save_failed
            and run.get("status") == "running"
            and any(step.get("status") == "completed" for step in run.get("steps", []))
        ):
            receipt_save_failed = True
            raise TimeoutError("governance receipt write timed out")
        return durable_save(governance_path, run)

    monkeypatch.setattr(worker, "save_run", save_with_receipt_timeout)
    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert receipt_save_failed is True
    assert run["status"] == "failed"
    assert run["steps"][0]["status"] == "completed"
    assert run["retry_after"] is None
    assert "人工复核" in run["message"]
    assert worker.drain_updates(settings) == 0
    assert global_calls == 1


@pytest.mark.parametrize(
    ("steps", "current_step"),
    [
        ([{"key": "formal_balance", "status": "completed"}], None),
        ([{"key": "daily_balance_and_risk", "status": "failed"}], None),
        ([], "formal_balance"),
    ],
)
def test_persisted_retry_with_started_step_stops_before_preflight(
    settings, monkeypatch, steps, current_step
):
    run = request(settings, monkeypatch)
    repo.save_run(
        settings.governance_path,
        {
            **run,
            "status": "retrying",
            "retry_after": "2000-01-01T00:00:00+00:00",
            "steps": steps,
            "current_step": current_step,
        },
    )
    preflight = Mock(side_effect=AssertionError("preflight should not run"))
    execute = Mock(side_effect=AssertionError("executor should not run"))
    monkeypatch.setattr(worker, "input_preflight", preflight)
    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert run["retry_after"] is None
    assert "人工复核" in run["message"]
    preflight.assert_not_called()
    execute.assert_not_called()


def test_interrupted_run_requires_review_before_replay(settings, monkeypatch):
    run = request(settings, monkeypatch)
    repo.save_run(settings.governance_path, {**run, "status": "running"})
    execute = Mock()
    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 1
    execute.assert_not_called()
    assert "中断" in repo.latest_runs(settings.governance_path)[0]["message"]


def test_final_receipt_timeout_is_not_reported_as_worker_lock_contention(
    settings, monkeypatch
):
    ready_files(settings)
    request(settings, monkeypatch)
    monkeypatch.setattr(
        worker, "_execute_core", Mock(return_value={"status": "completed"})
    )
    durable_save = worker.save_run

    def fail_final_save(governance_path, run):
        if run.get("status") == "completed":
            raise TimeoutError("final receipt write timed out")
        return durable_save(governance_path, run)

    monkeypatch.setattr(worker, "save_run", fail_final_save)
    with pytest.raises(TimeoutError, match="final receipt"):
        worker.drain_updates(settings)
    assert repo.latest_runs(settings.governance_path)[0]["status"] == "running"


def test_worker_lock_contention_does_not_claim_a_new_failure(settings, monkeypatch):
    @contextmanager
    def busy_lock(*_args, **_kwargs):
        raise TimeoutError("another drain owns the worker lock")
        yield

    monkeypatch.setattr(worker, "acquire_lock", busy_lock)
    assert worker.drain_updates(settings) == 0
    assert repo.latest_runs(settings.governance_path) == []


def test_database_open_failure_is_not_reported_as_missing_data(settings, monkeypatch):
    settings.duckdb_path.touch()
    monkeypatch.setattr(
        repo, "read_only_connection", Mock(side_effect=RuntimeError("locked"))
    )
    assert all(
        row["status"] == "error" and row["as_of_date"] is None
        for row in repo.financial_dates(settings.duckdb_path)
    )


def test_balance_verification_checks_requested_partition_not_latest(settings):
    with duckdb.connect(str(settings.duckdb_path)) as conn:
        for key, _label, table, column in repo.DATE_TABLES:
            conn.execute(f'CREATE TABLE "{table}" ("{column}" VARCHAR)')
            if key != "pnl":
                conn.execute(f'INSERT INTO "{table}" VALUES (?)', ["2026-09-01"])
    with pytest.raises(ValueError, match=REPORT_DATE):
        repo.verify_daily_balance_date(settings.duckdb_path, REPORT_DATE)
    with duckdb.connect(str(settings.duckdb_path)) as conn:
        for key, _label, table, _column in repo.DATE_TABLES:
            if key != "pnl":
                conn.execute(f'INSERT INTO "{table}" VALUES (?)', [REPORT_DATE])
    repo.verify_daily_balance_date(settings.duckdb_path, REPORT_DATE)


def test_balance_verification_fails_closed_when_count_query_has_no_row(settings, monkeypatch):
    @contextmanager
    def empty_count_query(*_args, **_kwargs):
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = None
        yield connection

    monkeypatch.setattr(repo, "read_only_connection", empty_count_query)
    with pytest.raises(RuntimeError, match="COUNT query returned no row"):
        repo.verify_daily_balance_date(settings.duckdb_path, REPORT_DATE)


def test_http_post_queue_get_uses_same_durable_receipt(settings, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "ensure_user_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(service, "require_scheduler", lambda _task: None)
    monkeypatch.setattr(
        service, "scheduled_updates", lambda: {"status": "available", "tasks": []}
    )
    ready_files(settings)
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "_execute_core", execute)
    client = TestClient(app)

    submitted = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "wait_for_inputs": False},
        headers={"Idempotency-Key": "http-queue"},
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]
    assert submitted.json()["status"] == "queued"
    assert "idempotency_key" not in submitted.json()
    assert worker.drain_updates(settings) == 0
    overview = client.get("/api/data-updates")
    assert overview.status_code == 200
    receipt = next(row for row in overview.json()["runs"] if row["run_id"] == run_id)
    assert receipt["status"] == "completed"
    assert receipt["report_date"] == REPORT_DATE
    assert "idempotency_key" not in receipt
    execute.assert_called_once()


def test_http_preflight_only_exposes_approved_fields(settings, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    client = TestClient(app)
    private_marker = "private customer cell 8675309"
    monkeypatch.setattr(
        service,
        "input_preflight",
        lambda *_args: {
            "report_date": REPORT_DATE,
            "workflow": "balance_daily",
            "ready": False,
            "input_directory": f"C:/private/{private_marker}",
            "internal_secret": private_marker,
            "checks": [
                {
                    "key": "zqtz",
                    "label": private_marker,
                    "status": "waiting",
                    "files": [f"C:/private/{private_marker}/ZQTZSHOW-20260831.xls"],
                    "detail": private_marker,
                    "internal_secret": private_marker,
                }
            ],
        },
    )
    response = client.get(
        f"/api/data-updates/preflight?report_date={REPORT_DATE}&workflow=balance_daily"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "report_date": REPORT_DATE,
        "workflow": "balance_daily",
        "ready": False,
        "input_directory": str(settings.data_input_root),
        "checks": [
            {
                "key": "zqtz",
                "label": "债券余额文件",
                "status": "waiting",
                "files": ["ZQTZSHOW-20260831.xls"],
                "detail": "文件正在写入，请等待一分钟。",
            }
        ],
    }
    assert private_marker not in str(payload)

    def invalid_date(*_args):
        raise ValueError(private_marker)

    monkeypatch.setattr(service, "input_preflight", invalid_date)
    invalid = client.get(
        f"/api/data-updates/preflight?report_date={REPORT_DATE}&workflow=balance_daily"
    )
    assert invalid.status_code == 422
    assert private_marker not in str(invalid.json())


def test_http_receipts_only_expose_approved_run_and_step_fields(settings, monkeypatch):
    original = request(settings, monkeypatch)
    private_marker = "private customer cell 8675309"
    preflight = dict(original["preflight"])
    preflight["input_directory"] = f"C:/private/{private_marker}"
    preflight["internal_secret"] = private_marker
    preflight["checks"] = [dict(row) for row in preflight["checks"]]
    preflight["checks"][0]["detail"] = private_marker
    preflight["checks"][0]["internal_secret"] = private_marker
    preflight["checks"][1]["files"] = [
        f"C:/private/{private_marker}/TYWLSHOW-20260831.xls"
    ]
    repo.save_run(
        settings.governance_path,
        {
            **original,
            "message": private_marker,
            "preflight": preflight,
            "steps": [
                {
                    "key": "daily_balance_and_risk",
                    "label": "余额更新",
                    "status": "failed",
                    "error_message": private_marker,
                    "result": {"source_data": "private source rows"},
                }
            ],
            "failure_receipt": {
                "status": "failed",
                "failed_step": "verify",
                "raw_traceback": "private stack trace",
            },
            "raw_traceback": "private stack trace",
        },
    )
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator-b", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "ensure_user_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(
        service, "scheduled_updates", lambda: {"status": "available", "tasks": []}
    )
    client = TestClient(app)

    overview = client.get("/api/data-updates")
    assert overview.status_code == 200
    get_receipt = next(
        run for run in overview.json()["runs"] if run["run_id"] == original["run_id"]
    )
    post = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "wait_for_inputs": True},
        headers={"Idempotency-Key": "operator-b-key"},
    )
    assert post.status_code == 202
    cancelled = client.post(f"/api/data-updates/runs/{original['run_id']}/cancel")
    assert cancelled.status_code == 200
    cancelled_overview = client.get("/api/data-updates")
    assert cancelled_overview.status_code == 200
    cancelled_get = next(
        run
        for run in cancelled_overview.json()["runs"]
        if run["run_id"] == original["run_id"]
    )

    for receipt in (get_receipt, post.json(), cancelled.json(), cancelled_get):
        assert receipt["run_id"] == original["run_id"]
        assert receipt["steps"] == [
            {
                "key": "daily_balance_and_risk",
                "label": "余额更新",
                "status": "failed",
                "error_message": "该步骤未完成，请检查后台回执。",
            }
        ]
        assert receipt["failure_receipt"] == {
            "status": "failed",
            "failed_step": "verify",
        }
        assert receipt["preflight"]["input_directory"] == str(settings.data_input_root)
        assert receipt["preflight"]["checks"][0]["detail"] == "尚未找到该报告日的文件。"
        assert receipt["preflight"]["checks"][1]["files"] == ["TYWLSHOW-20260831.xls"]
        for private_field in (
            "requested_by",
            "cancelled_by",
            "idempotency_key",
            "raw_traceback",
        ):
            assert private_field not in receipt
        assert "private source rows" not in str(receipt)
        assert "private stack trace" not in str(receipt)
        assert private_marker not in str(receipt)


def test_http_error_details_do_not_echo_internal_exception_text(settings, monkeypatch):
    run = request(settings, monkeypatch)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "ensure_user_allowed", lambda **_kwargs: None)
    client = TestClient(app)
    private_marker = "private customer cell 8675309"

    for failure, expected_status in ((ValueError, 409), (RuntimeError, 503)):

        def raise_request(*_args, **_kwargs):
            raise failure(private_marker)

        monkeypatch.setattr(service, "request_core_update", raise_request)
        response = client.post(
            "/api/data-updates/core",
            json={"report_date": REPORT_DATE, "wait_for_inputs": True},
            headers={"Idempotency-Key": "another-request"},
        )
        assert response.status_code == expected_status
        assert private_marker not in str(response.json())

    for failure, expected_status in ((LookupError, 404), (ValueError, 409)):

        def raise_cancel(*_args, **_kwargs):
            raise failure(private_marker)

        monkeypatch.setattr(service, "cancel_update", raise_cancel)
        response = client.post(f"/api/data-updates/runs/{run['run_id']}/cancel")
        assert response.status_code == expected_status
        assert private_marker not in str(response.json())


def test_http_merged_and_cancelled_receipts_do_not_expose_original_request_key(
    settings, monkeypatch
):
    monkeypatch.setattr(service, "require_scheduler", lambda _task: None)
    original = service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=True,
        requested_by="operator-a",
        idempotency_key="operator-a-private-key",
    )
    assert original["idempotency_key"] == "operator-a-private-key"

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator-b", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "ensure_user_allowed", lambda **_kwargs: None)
    client = TestClient(app)

    merged = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "wait_for_inputs": True},
        headers={"Idempotency-Key": "operator-b-key"},
    )
    assert merged.status_code == 202
    assert merged.json()["run_id"] == original["run_id"]
    assert "idempotency_key" not in merged.json()
    assert (
        repo.latest_runs(settings.governance_path)[0]["idempotency_key"]
        == "operator-a-private-key"
    )

    cancelled = client.post(f"/api/data-updates/runs/{original['run_id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert "idempotency_key" not in cancelled.json()
    assert (
        repo.latest_runs(settings.governance_path)[0]["idempotency_key"]
        == "operator-a-private-key"
    )


def test_data_update_routes_are_registered_in_api():
    paths = {route.path for route in api_router.routes}
    assert "/api/data-updates" in paths
    assert "/api/data-updates/core" in paths


def test_http_rejects_arbitrary_command_and_denied_write(settings, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(
        user_id="operator", role="operator"
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    authorize = Mock()
    monkeypatch.setattr(routes, "ensure_user_allowed", authorize)
    monkeypatch.setattr(service, "require_scheduler", lambda _task: None)
    client = TestClient(app)
    headers = {"Idempotency-Key": "http-denied"}
    invalid = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "command": "arbitrary"},
        headers=headers,
    )
    assert invalid.status_code == 422
    authorize.side_effect = PermissionError("denied")
    denied = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE},
        headers=headers,
    )
    assert denied.status_code == 403
    assert repo.latest_runs(settings.governance_path) == []


def test_market_control_starts_only_registered_task(monkeypatch):
    monkeypatch.setattr(service, "require_scheduler", lambda _task: None)
    execute = Mock()
    monkeypatch.setattr(service.subprocess, "run", execute)
    assert service.start_market_update()["status"] == "accepted"
    assert execute.call_args.args[0] == [
        "schtasks",
        "/Run",
        "/TN",
        "MOSS-DailyDataRefresh",
    ]
