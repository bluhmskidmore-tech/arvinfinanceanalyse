"""Isolated one-date request/worker/importer tests, never the live database."""

from __future__ import annotations

import copy
import json
import shutil
import socket
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import data_updates as routes
from backend.app.repositories import data_update_repo as repo
from backend.app.services import data_update_service as service
from backend.app.tasks import data_update_center as worker
from backend.app.tasks import data_update_choice_stock_pit as leaf
from tests.test_choice_stock_pit_import import (
    AS_OF_DATE,
    _build_fixture,
    _old_audit_hash,
    _sha256,
    _table_hash,
)

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]


@pytest.fixture
def pit_case(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    source, target = _build_fixture(tmp_path)
    (tmp_path / "input").mkdir()
    backup = tmp_path / "target-before.duckdb"
    shutil.copy2(target, backup)
    settings = SimpleNamespace(
        duckdb_path=target, governance_path=tmp_path / "governance",
        data_input_root=tmp_path / "input",
        system_read_publication_enabled=False, financial_publication_enabled=False,
    )
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    # The host's real maintenance/Windows-family contract is tested separately.
    # This suite exercises real importer SQL only in its two-stock fixture.
    monkeypatch.setattr(worker, "_require_pit_maintenance", lambda: None)
    for name in ("_execute_core", "_execute_balance", "_drain_publication_recovery"):
        monkeypatch.setattr(worker, name, Mock(side_effect=AssertionError("no financial path")))
    monkeypatch.setattr(worker, "input_preflight", Mock(side_effect=AssertionError("no financial inputs")))
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", Mock(return_value=0))
    publication = Mock(side_effect=AssertionError("PIT cannot recover financial publication"))
    monkeypatch.setattr(
        "backend.app.tasks.system_read_publication.recover_committed_system_read_publication", publication,
    )
    preflight = service.choice_stock_pit_preflight(
        settings, report_date=AS_OF_DATE, source_duckdb_path=str(source), expected_source_sha256=_sha256(source),
    )
    body = {
        "report_date": AS_OF_DATE, "source_duckdb_path": str(source),
        "expected_source_sha256": _sha256(source), "expected_plan_sha256": preflight["plan_sha256"],
        "target_backup_path": str(backup),
    }
    return SimpleNamespace(settings=settings, source=source, target=target, backup=backup,
                           body=body, publication=publication)


def _request(case):
    return service.request_choice_stock_pit_update(
        case.settings, **case.body, requested_by="pit-operator", idempotency_key="single-day-fixture",
    )


def _current(case, run_id):
    return next(run for run in repo.latest_runs(case.settings.governance_path) if run["run_id"] == run_id)


def _mark_running(case, run):
    running = {**run, "status": "running", "attempt": 1, "started_at": service.utc_now()}
    running["task_receipt_path"] = str(leaf.task_receipt_path(case.settings, running))
    repo.save_run(case.settings.governance_path, running)
    return running


def test_http_request_to_worker_uses_real_importer_and_exact_receipts(pit_case, monkeypatch):
    case = pit_case
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "get_settings", lambda: case.settings)
    permissions = Mock()
    monkeypatch.setattr(routes, "ensure_user_allowed", permissions)
    daily_before = _table_hash(case.target, "choice_stock_daily_observation")
    old_audits = _old_audit_hash(case.target)
    before = _sha256(case.target)
    with TestClient(app) as client:
        response = client.post("/api/data-updates/choice-stock-pit", json=case.body,
                               headers={"Idempotency-Key": "http-single-day"})
        assert response.status_code == 202, response.text
        run = response.json()
    assert run["workflow"] == service.CHOICE_STOCK_PIT_WORKFLOW
    assert _current(case, run["run_id"])["target_duckdb_path"] == str(case.target)
    for private_field in ("requested_by", "idempotency_key", "target_duckdb_path", "source_duckdb_path", "target_backup_path"):
        assert private_field not in run
    assert run["preflight"]["source_sha256"] == case.body["expected_source_sha256"]
    assert run["preflight"]["plan_sha256"] == case.body["expected_plan_sha256"]
    assert _sha256(case.target) == before  # API only queues; it never writes DuckDB.
    assert {(call.kwargs["resource"], call.kwargs["action"]) for call in permissions.call_args_list} == set(routes.MARKET_PERMISSIONS)

    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 0
    done = _current(case, run["run_id"])
    result = done["choice_stock_pit_result"]
    assert done["status"] == "completed" and done["attempt"] == 1
    assert [step["key"] for step in done["steps"]] == [leaf.STEP_NAME]
    assert result["data_update_run_id"] == done["run_id"] and result["attempt"] == 1
    receipt = Path(result["task_receipt_path"])
    assert result["task_receipt_sha256"] == _sha256(receipt)
    assert json.loads(receipt.read_text(encoding="utf-8"))["plan_sha256"] == case.body["expected_plan_sha256"]
    assert result["inserted_total"] == 9 and result["post_write_validation"]["coverage_full"] is True
    assert result["production_duckdb_written"] is False
    assert _table_hash(case.target, "choice_stock_daily_observation") == daily_before
    assert _old_audit_hash(case.target) == old_audits
    assert "system_read_publication" not in done
    case.publication.assert_not_called()
    worker._recover_pending_pnl_by_business_precompute.assert_not_called()
    # Running, per-step and terminal records remain on the existing run stream.
    records = repo.GovernanceRepository(base_dir=case.settings.governance_path).read_all(repo.RUN_STREAM)
    own = [row for row in records if row["run_id"] == done["run_id"]]
    assert {row["status"] for row in own} == {"queued", "running", "completed"}
    assert any(row.get("current_step") == leaf.STEP_NAME for row in own)
    assert worker.drain_updates(case.settings, run_id=done["run_id"]) == 0
    assert _current(case, done["run_id"])["attempt"] == 1


def test_default_scheduler_leaves_pit_even_with_publication_recovery_flag(pit_case):
    case = pit_case
    run = _request(case)
    repo.save_run(case.settings.governance_path, {**run, "recovery_mode": "publication_only"})
    before = _sha256(case.target)
    assert worker.drain_updates(case.settings) == 0
    assert _current(case, run["run_id"])["status"] == "queued"
    assert _sha256(case.target) == before
    worker._drain_publication_recovery.assert_not_called()
    worker._execute_core.assert_not_called()
    # Default financial behavior still invokes its established PNL recovery.
    worker._recover_pending_pnl_by_business_precompute.assert_called_once_with(case.settings)


@pytest.mark.parametrize("workflow", ["core_financial", "balance_daily"])
def test_scoped_request_cannot_drain_other_workflows(pit_case, workflow):
    case = pit_case
    run = _request(case)
    other = {**run, "run_id": "data_update_" + "f" * 32, "workflow": workflow}
    repo.save_run(case.settings.governance_path, other)
    assert worker.drain_updates(case.settings, run_id=other["run_id"]) == 1
    assert worker.drain_updates(case.settings, run_id="missing") == 1
    assert _current(case, run["run_id"])["status"] == "queued"
    assert _current(case, other["run_id"])["status"] == "queued"
    worker._recover_pending_pnl_by_business_precompute.assert_not_called()


def test_scoped_worker_lock_timeout_is_nonzero_and_preserves_queue(pit_case, monkeypatch):
    case = pit_case
    run = _request(case)

    @contextmanager
    def unavailable(*args, **kwargs):
        raise TimeoutError("busy")
        yield

    monkeypatch.setattr(worker, "acquire_lock", unavailable)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 1
    assert _current(case, run["run_id"])["status"] == "queued"


@pytest.mark.parametrize("changed", ["source", "plan", "backup", "target_identity"])
def test_changed_execution_evidence_fails_closed_without_writes(pit_case, changed):
    case = pit_case
    run = _request(case)
    if changed == "source":
        with case.source.open("ab") as handle:
            handle.write(b"source changed after request")
    elif changed == "plan":
        with duckdb.connect(str(case.target)) as conn:
            conn.execute("update choice_stock_daily_observation set close_value = close_value + 1 where trade_date = ?", [AS_OF_DATE])
        shutil.copy2(case.target, case.backup)
    elif changed == "backup":
        case.backup.write_bytes(b"not the same database")
    else:
        run["target_duckdb_path"] = str(case.target.with_name("other.duckdb"))
        repo.save_run(case.settings.governance_path, run)
    before = _sha256(case.target)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 1
    failed = _current(case, run["run_id"])
    assert failed["status"] == "failed" and failed["retry_after"] is None
    assert failed["failure_receipt"]["commit_state"] == "unverified"
    assert _sha256(case.target) == before
    case.publication.assert_not_called()
    if changed != "target_identity":
        assert failed["steps"][0]["status"] == "failed"
        assert failed["failure_receipt"]["task_status"] == "failed"


def test_interrupted_run_cannot_use_missing_receipt_or_financial_publication(pit_case):
    case = pit_case
    run = _mark_running(case, _request(case))
    before = _sha256(case.target)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 1
    failed = _current(case, run["run_id"])
    assert failed["status"] == "failed"
    assert failed["failure_receipt"]["commit_state"] == "unverified"
    assert _sha256(case.target) == before
    case.publication.assert_not_called()


def test_commit_then_process_interrupt_recovers_exact_completed_task(pit_case, monkeypatch):
    case = pit_case
    run = _request(case)
    real_import = leaf.importer.import_choice_stock_pit_snapshot

    def interrupt_after_task_receipt(*args, **kwargs):
        real_import(*args, **kwargs)
        raise KeyboardInterrupt("simulated worker process interruption")

    monkeypatch.setattr(leaf.importer, "import_choice_stock_pit_snapshot", interrupt_after_task_receipt)
    with pytest.raises(KeyboardInterrupt):
        worker.drain_updates(case.settings, run_id=run["run_id"])
    interrupted = _current(case, run["run_id"])
    assert interrupted["status"] == "running" and Path(interrupted["task_receipt_path"]).exists()
    committed_hash = _sha256(case.target)
    execute = Mock(side_effect=AssertionError("must recover receipt, never replay import"))
    monkeypatch.setattr(leaf, "execute_choice_stock_pit_history", execute)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 0
    assert _current(case, run["run_id"])["status"] == "completed"
    assert _sha256(case.target) == committed_hash
    execute.assert_not_called()
    case.publication.assert_not_called()


def test_commit_before_task_receipt_is_unverified_and_never_replayed(pit_case, monkeypatch):
    case = pit_case
    run = _request(case)
    before = _sha256(case.target)
    real_write = leaf.importer._write_json_atomic

    def interrupt_before_receipt(path, payload):
        if payload["status"] == "completed":
            raise KeyboardInterrupt("commit occurred but receipt not durable")
        real_write(path, payload)

    monkeypatch.setattr(leaf.importer, "_write_json_atomic", interrupt_before_receipt)
    with pytest.raises(KeyboardInterrupt):
        worker.drain_updates(case.settings, run_id=run["run_id"])
    committed_hash = _sha256(case.target)
    assert committed_hash != before
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 1
    failed = _current(case, run["run_id"])
    assert failed["status"] == "failed" and failed["failure_receipt"]["commit_state"] == "unverified"
    assert _sha256(case.target) == committed_hash
    assert "no_changes_committed" not in failed["failure_receipt"]


def test_recovery_rejects_wrong_date_hash_scope_backup_and_old_attempt(pit_case):
    case = pit_case
    run = _request(case)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 0
    done = _current(case, run["run_id"])
    result = json.loads(Path(done["task_receipt_path"]).read_text(encoding="utf-8"))
    parameters = leaf._request_parameters(case.settings, done)
    for field, value in (
        ("as_of_date", "2026-09-01"), ("source_sha256", "b" * 64),
        ("plan_sha256", "b" * 64), ("duckdb_path", str(case.source)),
        ("backup_path", str(case.source)), ("started_at", "2000-01-01T00:00:00+00:00"),
        ("backup_sha256", "b" * 64), ("write_scope", {}), ("post_write_validation", {"coverage_full": False}),
    ):
        invalid = copy.deepcopy(result)
        invalid[field] = value
        with pytest.raises(ValueError):
            leaf._completed_result(parameters, done, invalid)
    with pytest.raises(ValueError, match="路径"):
        leaf.recover_choice_stock_pit_result(case.settings, {**done, "attempt": 2})


def test_owner_failure_preserves_queued_request_and_token_is_not_logged(pit_case, monkeypatch, caplog):
    case = pit_case
    run = _request(case)

    def denied():
        raise RuntimeError("private-owner-token-must-not-appear")

    monkeypatch.setattr(worker, "_require_pit_maintenance", denied)
    assert worker.drain_updates(case.settings, run_id=run["run_id"]) == 1
    assert _current(case, run["run_id"])["status"] == "queued"
    assert "private-owner-token" not in caplog.text


@pytest.mark.parametrize("connect_result", [0, 10035])
def test_maintenance_guard_checks_owner_and_rejects_unproven_api_drain(monkeypatch, connect_result):
    owner = Mock(return_value={"state": "launch_blocked"})
    monkeypatch.setattr("scripts.dev_runtime_control.require_owner", owner)
    monkeypatch.setenv("MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN", "test-owner-only")
    probe = Mock()
    probe.connect_ex.return_value = connect_result
    context = Mock()
    context.__enter__ = Mock(return_value=probe)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(worker.socket, "socket", Mock(return_value=context))
    with pytest.raises(RuntimeError, match="API"):
        worker._require_pit_maintenance()
    assert owner.call_args.args[1] == "test-owner-only"
    probe.connect_ex.assert_called_once_with(("127.0.0.1", 7888))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows delays local connection refusal beyond one second")
def test_windows_closed_port_is_confirmed_without_timeout_false_block(monkeypatch):
    """Use a real isolated closed port; do not probe or stop the live API."""
    original_socket = socket.socket
    with original_socket(socket.AF_INET, socket.SOCK_STREAM) as selection:
        selection.bind(("127.0.0.1", 0))
        isolated_port = selection.getsockname()[1]
    statuses = []

    class IsolatedProbe:
        def __init__(self):
            self.actual = original_socket(socket.AF_INET, socket.SOCK_STREAM)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.actual.close()

        def settimeout(self, timeout):
            self.actual.settimeout(timeout)

        def connect_ex(self, address):
            assert address == ("127.0.0.1", 7888)
            status = self.actual.connect_ex(("127.0.0.1", isolated_port))
            statuses.append(status)
            return status

    monkeypatch.setattr("scripts.dev_runtime_control.require_owner", Mock(return_value={"state": "launch_blocked"}))
    monkeypatch.setattr(worker.socket, "socket", lambda *args: IsolatedProbe())
    worker._require_pit_maintenance()
    assert statuses == [10061]
