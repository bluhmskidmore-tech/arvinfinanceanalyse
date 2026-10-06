"""Data-center control-plane tests; finance execution and host scheduling are isolated."""

from __future__ import annotations

import hashlib
import os
import time
from contextlib import contextmanager
from datetime import date
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import router as api_router
from backend.app.api.routes import data_updates as routes
from backend.app.repositories import data_update_repo as repo
from backend.app.repositories.pnl_precompute_state import (
    invalidate_pnl_by_business_precompute_on_connection,
)
from backend.app.security.auth_context import AuthContext
from backend.app.services import data_update_service as service
from backend.app.services import pnl_by_business_page_lifecycle
from backend.app.services import pnl_service
from backend.app.tasks import data_update_center as worker
from tests.test_snapshot_materialize_flow import _write_snapshot_xls, _write_synthetic_snapshot_inputs

REPORT_DATE = "2026-08-31"


def publication_failed_run(settings, *, failed_step="system_read_publish"):
    from backend.app.tasks.system_read_publication import SYSTEM_READ_CORE_REQUIRED_STEPS

    names = SYSTEM_READ_CORE_REQUIRED_STEPS
    if failed_step == "publish":
        names = names[:-1]
    steps = [
        {
            "name": name,
            "status": "completed",
            "result": {"status": "completed", "report_date": REPORT_DATE},
        }
        for name in names
    ]
    if failed_step == "system_read_publish":
        steps[-1]["result"].update(generation="pnl-fixture", manifest_sha256="a" * 64)
    steps.append({"name": failed_step, "status": "failed"})
    return repo.save_run(settings.governance_path, {
        "run_id": "failed-publication", "status": "failed", "workflow": "core_financial",
        "report_date": REPORT_DATE, "global_run_id": "global-fixture", "submitted_at": service.utc_now(),
        "failure_receipt": {"status": "failed", "run_id": "global-fixture", "report_date": REPORT_DATE,
                            "failed_step": failed_step, "steps": steps},
        "steps": [{"key": step["name"], "status": step["status"]} for step in steps],
    })


def test_publication_recovery_is_queued_without_restarting_finance(settings, monkeypatch):
    settings.system_read_publication_enabled = True
    settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    recovery = service.request_publication_recovery(
        settings, original["run_id"], requested_by="operator", idempotency_key="recover-fixture",
    )
    assert recovery["recovery_mode"] == "publication_only"
    assert recovery["recovery_of_run_id"] == original["run_id"]
    assert recovery["status"] == "queued"
    execute = Mock(side_effect=AssertionError("must not replay finance"))
    monkeypatch.setattr(worker, "_execute_core", execute)
    monkeypatch.setattr(worker, "input_preflight", Mock(side_effect=AssertionError("must not preflight finance")))
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    result = {"status": "completed", "generation": "fixture-system", "manifest_sha256": "b" * 64}
    monkeypatch.setattr("backend.app.tasks.system_read_publication.recover_committed_system_read_publication", Mock(return_value=result))
    assert worker.drain_updates(settings) == 0
    execute.assert_not_called()
    runs = repo.latest_runs(settings.governance_path)
    assert {run["status"] for run in runs} == {"completed"}
    repeated = service.request_publication_recovery(
        settings, original["run_id"], requested_by="operator", idempotency_key="recover-fixture",
    )
    assert repeated["run_id"] == recovery["run_id"]


@pytest.mark.parametrize("broken", ["missing_result", "date", "order", "body_failure", "workflow"])
def test_publication_recovery_rejects_incomplete_or_unrelated_receipts(settings, monkeypatch, broken):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    if broken == "missing_result":
        original["failure_receipt"]["steps"][0].pop("result")
    elif broken == "date":
        original["failure_receipt"]["report_date"] = "2026-07-31"
    elif broken == "order":
        original["failure_receipt"]["steps"].reverse()
    elif broken == "workflow":
        original["workflow"] = "balance_daily"
    else:
        original["failure_receipt"]["failed_step"] = "formal_pnl"
    repo.save_run(settings.governance_path, original)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    with pytest.raises(ValueError):
        service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="recover")
    assert len(repo.latest_runs(settings.governance_path)) == 1


def test_publication_recovery_dedupes_and_rejects_active_or_conflicting_request(settings, monkeypatch):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    recovery = service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="recover")
    assert service.request_publication_recovery(settings, original["run_id"], requested_by="other", idempotency_key="another")["run_id"] == recovery["run_id"]
    with pytest.raises(ValueError, match="原始"):
        service.request_publication_recovery(settings, recovery["run_id"], requested_by="operator", idempotency_key="child")
    repo.save_run(settings.governance_path, {**recovery, "status": "failed"})
    repo.save_run(settings.governance_path, {"run_id": "active-other-date", "status": "queued", "report_date": "2026-07-31"})
    with pytest.raises(ValueError, match="活跃"):
        service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="new")
    repo.save_run(settings.governance_path, {"run_id": "active-other-date", "status": "completed"})
    repo.save_run(settings.governance_path, {"run_id": "other-original", "status": "failed"})
    with pytest.raises(ValueError, match="不同"):
        service.request_publication_recovery(settings, "other-original", requested_by="operator", idempotency_key="recover")


def test_publication_recovery_failure_can_retry_original_without_finance(settings, monkeypatch):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    first = service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="first")
    finance = Mock(side_effect=AssertionError("finance must never run"))
    monkeypatch.setattr(worker, "_execute_core", finance)
    balance_check = Mock(side_effect=AssertionError("publication recovery must not parse current balances"))
    monkeypatch.setattr(worker, "_validate_balance_input_content", balance_check)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    publish = Mock(side_effect=RuntimeError("synthetic-private-provider-token"))
    monkeypatch.setattr(worker, "_recover_publication_only", publish)
    assert worker.drain_updates(settings) == 1
    failed = next(run for run in repo.latest_runs(settings.governance_path) if run["run_id"] == first["run_id"])
    assert failed["status"] == "failed" and failed["retry_after"] is None
    assert "synthetic-private" not in str(failed)
    second = service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="second")
    assert second["recovery_of_run_id"] == original["run_id"]
    publish.side_effect = None
    publish.return_value = {"status": "completed", "generation": "safe-publication", "manifest_sha256": "b" * 64}
    assert worker.drain_updates(settings) == 0
    finance.assert_not_called()
    balance_check.assert_not_called()


def test_publication_recovery_revalidates_original_receipt_before_publisher(settings, monkeypatch):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="recover")
    original["failure_receipt"]["steps"][0]["result"]["source_version"] = "replaced-after-request"
    repo.save_run(settings.governance_path, original)
    publish = Mock()
    monkeypatch.setattr(worker, "_recover_publication_only", publish)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    assert worker.drain_updates(settings) == 1
    publish.assert_not_called()


def test_publication_recovery_repairs_interrupted_receipt_after_original_saved(settings, monkeypatch):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    recovery = service.request_publication_recovery(settings, original["run_id"], requested_by="operator", idempotency_key="recover")
    repo.save_run(settings.governance_path, {**original, "status": "completed", "publication_recovered_by_run_id": recovery["run_id"]})
    repo.save_run(settings.governance_path, {**recovery, "status": "running"})
    committed = Mock(return_value={"status": "completed", "generation": "committed", "manifest_sha256": "c" * 64})
    monkeypatch.setattr("backend.app.tasks.system_read_publication.recover_committed_system_read_publication", committed)
    monkeypatch.setattr(worker, "_execute_core", Mock(side_effect=AssertionError("no finance")))
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    assert worker.drain_updates(settings) == 0
    assert all(run["status"] == "completed" for run in repo.latest_runs(settings.governance_path))
    committed.assert_called_once()


def test_publication_recovery_api_checks_permissions_idempotency_and_missing_run(settings, monkeypatch):
    settings.system_read_publication_enabled = settings.financial_publication_enabled = True
    original = publication_failed_run(settings)
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _: None)
    permissions = Mock()
    monkeypatch.setattr(routes, "ensure_user_allowed", permissions)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    client = TestClient(app)
    url = f"/api/data-updates/runs/{original['run_id']}/recover-publication"
    assert client.post(url).status_code == 422
    accepted = client.post(url, headers={"Idempotency-Key": "api-recovery"})
    assert accepted.status_code == 202
    assert accepted.json()["run_id"] != original["run_id"]
    assert accepted.json()["recovery_mode"] == "publication_only"
    assert accepted.json()["recovery_of_run_id"] == original["run_id"]
    for private_field in ("requested_by", "idempotency_key", "expected_failure_receipt_sha256"):
        assert private_field not in accepted.json()
    assert {call.kwargs["resource"] for call in permissions.call_args_list} == set(routes.CORE_RESOURCES)
    repeated = client.post(url, headers={"Idempotency-Key": "api-recovery"})
    assert repeated.json()["run_id"] == accepted.json()["run_id"]
    assert client.post("/api/data-updates/runs/absent/recover-publication", headers={"Idempotency-Key": "absent"}).status_code == 404
    permissions.side_effect = PermissionError("denied")
    assert client.post(url, headers={"Idempotency-Key": "denied"}).status_code == 403


@pytest.mark.parametrize("failure,status", [(LookupError, 404), (ValueError, 409), (RuntimeError, 503)])
def test_publication_recovery_api_does_not_echo_private_errors(settings, monkeypatch, failure, status):
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _: None)
    monkeypatch.setattr(routes, "ensure_user_allowed", lambda **_kwargs: None)
    private_marker = "synthetic-private-recovery-source"
    monkeypatch.setattr(service, "request_publication_recovery", Mock(side_effect=failure(private_marker)))
    response = TestClient(app).post(
        "/api/data-updates/runs/original/recover-publication",
        headers={"Idempotency-Key": "public-recovery"},
    )
    assert response.status_code == status
    assert private_marker not in response.text


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    root = tmp_path / "input"
    root.mkdir()
    return SimpleNamespace(
        data_input_root=root,
        governance_path=tmp_path / "governance",
        duckdb_path=tmp_path / "moss.duckdb",
        local_archive_path=tmp_path / "archive",
        fx_official_source_path="",
        fx_mid_csv_path="",
    )


def source_file(settings, name):
    path = settings.data_input_root / name
    path.write_bytes(b"synthetic source; parsers are independently tested")
    os.utime(path, (time.time() - 120, time.time() - 120))
    return path


def ready_files(settings, *, include_pnl=True):
    for name in ("ZQTZSHOW-20260831.xls", "TYWLSHOW-20260831.xls"):
        source_file(settings, name)
    if include_pnl:
        source_file(settings, "FI损益202608.xls")


def balance_workbooks(settings, **kwargs):
    _write_synthetic_snapshot_inputs(settings.data_input_root, REPORT_DATE, **kwargs)
    for path in settings.data_input_root.glob("*.xls"):
        os.utime(path, (time.time() - 120, time.time() - 120))


@pytest.mark.parametrize("workflow", ["balance_daily", "core_financial"])
@pytest.mark.parametrize("family", ["zqtz", "tyw"])
def test_bad_balance_content_is_rejected_before_ingest(settings, monkeypatch, workflow, family):
    from backend.app.repositories import snapshot_row_parse as parser
    from backend.app.tasks import formal_balance_pipeline

    balance_workbooks(settings, **{f"missing_{family}_amount": "应计利息"})
    path = settings.data_input_root / ("ZQTZSHOW-20260831.xls" if family == "zqtz" else "TYWLSHOW-20260831.xls")
    canonical = parser.parse_zqtz_snapshot_rows_from_bytes if family == "zqtz" else parser.parse_tyw_snapshot_rows_from_bytes
    with pytest.raises(ValueError, match="required amount invalid"):
        canonical(file_bytes=path.read_bytes(), ingest_batch_id="fixture", source_version="fixture",
                  source_file=path.name, rule_version="fixture")
    ingest = Mock(side_effect=AssertionError("ingest entered before rejecting known invalid XLS"))
    monkeypatch.setattr(formal_balance_pipeline, "ingest_demo_manifest", SimpleNamespace(fn=ingest))
    if workflow == "core_financial":
        monkeypatch.setattr("backend.app.services.pnl_source_service.load_latest_pnl_refresh_input",
                            lambda **_: SimpleNamespace(report_date=REPORT_DATE, fi_rows=[{"pnl": 1}]))
        monkeypatch.setattr("scripts.run_global_data_refresh.run_global_data_refresh",
                            lambda **_: formal_balance_pipeline.run_formal_balance_pipeline_sync(
                                report_date=REPORT_DATE, data_root=str(settings.data_input_root),
                                governance_dir=str(settings.governance_path),
                                duckdb_path=str(settings.duckdb_path), archive_dir=str(settings.local_archive_path)))
        execute = worker._execute_core
    else:
        execute = worker._execute_balance
    with pytest.raises(ValueError, match="required amount invalid"):
        execute(settings, REPORT_DATE, Mock())
    ingest.assert_not_called()


def archive_balance_source(settings, family, path, *, archived_path=None):
    from backend.app.repositories.governance_repo import GovernanceRepository
    from backend.app.repositories.source_manifest_repo import SourceManifestRepository

    archive = Path(archived_path) if archived_path else settings.local_archive_path / path.name
    archive.parent.mkdir(parents=True, exist_ok=True)
    payload = path.read_bytes()
    archive.write_bytes(payload)
    SourceManifestRepository(governance_repo=GovernanceRepository(base_dir=settings.governance_path)).add_many([{
        "source_family": family, "report_date": REPORT_DATE, "source_file": path.name,
        "source_version": f"sv_{hashlib.sha256(payload).hexdigest()[:12]}",
        "ingest_batch_id": f"archived-{family}", "archived_path": str(archive),
    }])
    return archive


def test_balance_input_guard_selects_only_target_date_directs(settings, monkeypatch):
    balance_workbooks(settings)
    target = settings.data_input_root / "ZQTZSHOW-20260831.xls"
    (settings.data_input_root / "ZQTZSHOW-2026.08.31.xls").write_bytes(target.read_bytes())
    _write_synthetic_snapshot_inputs(settings.data_input_root, "2026-07-31", missing_zqtz_amount="应计利息")
    original = Path.read_bytes
    read_paths = []

    def only_target(path):
        assert "20260731" not in path.name
        read_paths.append(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", only_target)
    worker._validate_balance_input_content(settings, REPORT_DATE)
    assert set(read_paths) == {"ZQTZSHOW-20260831.xls", "ZQTZSHOW-2026.08.31.xls", "TYWLSHOW-20260831.xls"}


def test_balance_input_guard_archive_fallback_and_partial_new_batch(settings):
    balance_workbooks(settings, missing_zqtz_amount="应计利息")
    zqtz = settings.data_input_root / "ZQTZSHOW-20260831.xls"
    tyw = settings.data_input_root / "TYWLSHOW-20260831.xls"
    old_bad = archive_balance_source(settings, "zqtz", zqtz)
    archive_balance_source(settings, "tyw", tyw)
    # Only TYW changes. The actual snapshot pipeline chooses this new batch's
    # TYW row, rather than parsing unchanged bad ZQTZ or its prior archive.
    _write_snapshot_xls(tyw, [{"流水号": "changed", "金额": 123, "应计利息": 0, "币种": "人民币"}])
    worker._validate_balance_input_content(settings, REPORT_DATE)
    # No new target rows: the same existing selector must now validate archives.
    archive_balance_source(settings, "tyw", tyw)
    zqtz.unlink()
    tyw.unlink()
    with pytest.raises(ValueError, match="required amount invalid"):
        worker._validate_balance_input_content(settings, REPORT_DATE)
    assert old_bad.is_file()


def test_balance_input_guard_accepts_valid_same_date_archives(settings):
    balance_workbooks(settings)
    for family, name in (("zqtz", "ZQTZSHOW-20260831.xls"), ("tyw", "TYWLSHOW-20260831.xls")):
        path = settings.data_input_root / name
        archive_balance_source(settings, family, path)
        path.unlink()
    worker._validate_balance_input_content(settings, REPORT_DATE)


def test_balance_input_guard_rejects_archive_outside_root_before_read(settings, tmp_path, monkeypatch):
    balance_workbooks(settings)
    path = settings.data_input_root / "ZQTZSHOW-20260831.xls"
    outside = archive_balance_source(settings, "zqtz", path, archived_path=tmp_path / "untrusted" / path.name)
    path.unlink()
    (settings.data_input_root / "TYWLSHOW-20260831.xls").unlink()
    original = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda path: (_ for _ in ()).throw(AssertionError("outside archive read"))
                        if path == outside else original(path))
    with pytest.raises(ValueError, match="outside local archive root"):
        worker._validate_balance_input_content(settings, REPORT_DATE)


@pytest.mark.parametrize("case", ["no_input", "wrong_sheet_date", "nonfinite", "read_failure"])
def test_balance_input_guard_rejects_missing_input_or_canonical_parse_failure(settings, monkeypatch, case):
    if case == "no_input":
        with pytest.raises(ValueError, match="没有可用"):
            worker._validate_balance_input_content(settings, REPORT_DATE)
        return
    balance_workbooks(settings)
    path = settings.data_input_root / "ZQTZSHOW-20260831.xls"
    if case == "wrong_sheet_date":
        row = {"日期": "2026-09-01", "债券代号": "date-conflict", "到期日": "2030-12-31",
               "面值": 100, "公允价值": 100, "摊余成本": 99, "应计利息": 0, "币种": "人民币"}
        _write_snapshot_xls(path, [row])
    elif case == "nonfinite":
        balance_workbooks(settings, zqtz_market_value=float("inf"))
    else:
        original = Path.read_bytes
        monkeypatch.setattr(Path, "read_bytes", lambda source: (_ for _ in ()).throw(PermissionError("private-source-secret"))
                            if source == path else original(source))
    with pytest.raises((ValueError, PermissionError)):
        worker._validate_balance_input_content(settings, REPORT_DATE)


@pytest.mark.parametrize("case", ["empty_rows", "other_content_date"])
def test_balance_input_guard_preserves_canonical_parse_result_semantics(settings, case):
    from backend.app.repositories.snapshot_row_parse import parse_tyw_snapshot_rows_from_bytes

    balance_workbooks(settings)
    path = settings.data_input_root / "TYWLSHOW-20260831.xls"
    if case == "empty_rows":
        _write_snapshot_xls(path, [{"流水号": None, "金额": None, "应计利息": None, "币种": None}])
    else:
        path = settings.data_input_root / "TYWLSHOW-20260930.xls"
        _write_snapshot_xls(path, [{"流水号": "other-date", "金额": 123, "应计利息": 0, "币种": "人民币"}])
        archive_balance_source(settings, "tyw", path)
        for source in settings.data_input_root.glob("*.xls"):
            source.unlink()
    rows = parse_tyw_snapshot_rows_from_bytes(
        file_bytes=(path.read_bytes() if case == "empty_rows" else (settings.local_archive_path / path.name).read_bytes()),
        ingest_batch_id="fixture", source_version="fixture", source_file=path.name, rule_version="fixture",
    )
    assert rows == [] if case == "empty_rows" else {row["report_date"] for row in rows} == {"2026-09-30"}
    # Parse results are deliberately left to the existing materialization and
    # post-write report-date checks; this guard only moves canonical parsing.
    worker._validate_balance_input_content(settings, REPORT_DATE)


def test_balance_input_guard_rejects_direct_outside_root_before_read(settings, tmp_path, monkeypatch):
    outside = tmp_path / "outside" / "ZQTZSHOW-20260831.xls"
    _write_synthetic_snapshot_inputs(outside.parent, REPORT_DATE)
    reads = Mock(side_effect=AssertionError("outside input must not be read"))
    monkeypatch.setattr("backend.app.services.ingest_service._iter_data_input_scan_paths", lambda _: [outside])
    monkeypatch.setattr(Path, "read_bytes", reads)
    with pytest.raises(ValueError, match="输入目录"):
        worker._validate_balance_input_content(settings, REPORT_DATE)
    reads.assert_not_called()


@pytest.mark.parametrize("workflow", ["core_financial", "balance_daily"])
@pytest.mark.parametrize("fault", ["required_amount", "read_failure"])
def test_invalid_balance_run_fails_without_retry_or_private_receipt(settings, monkeypatch, workflow, fault):
    balance_workbooks(settings, missing_zqtz_amount="应计利息")
    source_file(settings, "FI损益202608.xls")
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    run = service.request_core_update(settings, report_date=REPORT_DATE, wait_for_inputs=False,
                                      requested_by="operator", idempotency_key="bad-content", workflow=workflow)
    if fault == "read_failure":
        original = Path.read_bytes
        monkeypatch.setattr(Path, "read_bytes", lambda source: (_ for _ in ()).throw(PermissionError("private-source-secret"))
                            if source.name == "ZQTZSHOW-20260831.xls" else original(source))
    global_pipeline = Mock(side_effect=AssertionError("global pipeline must not begin"))
    balance_pipeline = Mock(side_effect=AssertionError("balance pipeline must not begin"))
    monkeypatch.setattr("scripts.run_global_data_refresh.run_global_data_refresh", global_pipeline)
    monkeypatch.setattr("backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync", balance_pipeline)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    assert worker.drain_updates(settings) == 1
    failed = next(row for row in repo.latest_runs(settings.governance_path) if row["run_id"] == run["run_id"])
    assert failed["status"] == "failed" and failed["retry_after"] is None and failed["attempt"] == 1
    assert "private-source-secret" not in str(failed) and str(settings.data_input_root) not in failed["message"]
    assert worker.drain_updates(settings) == 0
    global_pipeline.assert_not_called()
    balance_pipeline.assert_not_called()


def expected_curve_snapshots():
    return [
        {
            "anchor_date": "2026-08-31",
            "curve_type": "treasury",
            "snapshot_date": "2026-08-29",
            "source_version": "sv-treasury",
            "vendor_name": "Choice",
            "vendor_version": "vv-choice",
            "rule_version": "rv-curve",
        },
        {
            "anchor_date": "2026-08-01",
            "curve_type": "cdb",
            "snapshot_date": "2026-08-01",
            "source_version": "sv-cdb",
            "vendor_name": "AkShare",
            "vendor_version": "vv-akshare",
            "rule_version": "rv-curve",
        },
    ]


def request(settings, monkeypatch, *, wait=True, key="request-1", workflow="core_financial"):
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    return service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=wait,
        requested_by="operator",
        idempotency_key=key,
        workflow=workflow,
    )


def test_preflight_uses_exact_report_date_and_waits_for_stable_files(settings):
    ready_files(settings)
    assert service.input_preflight(settings, REPORT_DATE)["ready"] is True
    assert service.input_preflight(settings, "2026-07-31")["ready"] is False
    path = settings.data_input_root / "FI损益202608.xls"
    os.utime(path, None)
    checks = service.input_preflight(settings, REPORT_DATE)["checks"]
    assert next(row for row in checks if row["key"] == "pnl")["status"] == "waiting"


def test_undated_and_invalid_date_names_never_become_today_inputs(settings):
    for name in ("ZQTZSHOW.xls", "TYWLSHOW-20261399.xls", "FI损益.xls"):
        source_file(settings, name)
    result = service.input_preflight(settings, date.today().isoformat())
    assert result["ready"] is False
    assert all(row["files"] == [] for row in result["checks"] if row["key"] != "fx")


def test_missing_scheduler_or_inputs_cannot_create_immediate_run(settings, monkeypatch):
    monkeypatch.setattr(
        service, "scheduled_updates", lambda: {"status": "error", "tasks": []}
    )
    with pytest.raises(RuntimeError):
        service.request_core_update(
            settings,
            report_date=REPORT_DATE,
            wait_for_inputs=True,
            requested_by="operator",
            idempotency_key="first",
        )
    with pytest.raises(ValueError, match="尚未到齐"):
        request(settings, monkeypatch, wait=False)
    assert repo.latest_runs(settings.governance_path) == []


def test_duplicate_requests_are_durable_and_parameter_reuse_is_rejected(
    settings, monkeypatch
):
    first = request(settings, monkeypatch)
    assert request(settings, monkeypatch)["run_id"] == first["run_id"]
    assert (
        request(settings, monkeypatch, key="another-click")["run_id"] == first["run_id"]
    )
    with pytest.raises(ValueError, match="不同更新参数"):
        request(settings, monkeypatch, wait=False)
    assert len(repo.latest_runs(settings.governance_path)) == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"use_existing_fx_only": 1}, "布尔值"),
        ({"expected_fx_source_version": "fx-v1"}, "普通更新"),
        ({"use_existing_fx_only": True}, "必须指定"),
        (
            {
                "workflow": "balance_daily",
                "use_existing_fx_only": True,
                "expected_fx_source_version": "fx-v1",
                "recovery_of_run_id": "failed-run",
            },
            "仅支持完整财务更新",
        ),
    ],
)
def test_fx_recovery_request_rejects_invalid_internal_parameters(
    settings, monkeypatch, overrides, message
):
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    parameters = {
        "report_date": REPORT_DATE,
        "wait_for_inputs": True,
        "requested_by": "operator",
        "idempotency_key": "recovery-request",
        **overrides,
    }

    with pytest.raises(ValueError, match=message):
        service.request_core_update(settings, **parameters)

    assert repo.latest_runs(settings.governance_path) == []


def test_fx_recovery_request_requires_failed_same_date_core_run_and_persists_mode(
    settings, monkeypatch
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    original = {
        "run_id": "failed-core-run",
        "report_date": REPORT_DATE,
        "workflow": "core_financial",
        "status": "failed",
        "submitted_at": "2026-09-14T01:00:00+00:00",
    }
    repo.save_run(settings.governance_path, original)

    recovered = service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="recovery-request",
        use_existing_fx_only=True,
        expected_fx_source_version=" fx-source-v1 ",
        recovery_of_run_id=" failed-core-run ",
    )

    assert recovered["use_existing_fx_only"] is True
    assert recovered["expected_fx_source_version"] == "fx-source-v1"
    assert recovered["recovery_of_run_id"] == "failed-core-run"
    assert repo.latest_runs(settings.governance_path)[0] == recovered


def test_curve_recovery_request_normalizes_manifest_and_supports_curve_only(
    settings, monkeypatch
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "failed-core-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": "failed",
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )

    recovered = service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="curve-recovery-request",
        use_existing_curves_only=True,
        expected_curve_snapshots=expected_curve_snapshots(),
        recovery_of_run_id="failed-core-run",
    )

    assert recovered["use_existing_fx_only"] is False
    assert recovered["use_existing_curves_only"] is True
    assert [
        (item["anchor_date"], item["curve_type"])
        for item in recovered["expected_curve_snapshots"]
    ] == [("2026-08-01", "cdb"), ("2026-08-31", "treasury")]
    assert recovered["recovery_of_run_id"] == "failed-core-run"


@pytest.mark.parametrize(
    "overrides",
    [
        {"use_existing_curves_only": 1},
        {"use_existing_curves_only": True},
        {"expected_curve_snapshots": expected_curve_snapshots()},
        {
            "workflow": "balance_daily",
            "use_existing_curves_only": True,
            "expected_curve_snapshots": expected_curve_snapshots(),
            "recovery_of_run_id": "failed-core-run",
        },
    ],
)
def test_curve_recovery_request_rejects_invalid_internal_parameters(
    settings, monkeypatch, overrides
):
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)

    with pytest.raises((TypeError, ValueError)):
        service.request_core_update(
            settings,
            report_date=REPORT_DATE,
            wait_for_inputs=True,
            requested_by="operator",
            idempotency_key="curve-recovery-request",
            **overrides,
        )

    assert repo.latest_runs(settings.governance_path) == []


@pytest.mark.parametrize("invalid_status", ["completed", "running"])
def test_fx_recovery_request_rejects_ineligible_audit_run(
    settings, monkeypatch, invalid_status
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "ineligible-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": invalid_status,
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )

    with pytest.raises(ValueError, match="同一报告日已失败"):
        service.request_core_update(
            settings,
            report_date=REPORT_DATE,
            wait_for_inputs=False,
            requested_by="operator",
            idempotency_key="recovery-request",
            use_existing_fx_only=True,
            expected_fx_source_version="fx-source-v1",
            recovery_of_run_id="ineligible-run",
        )


def test_idempotency_and_active_dedupe_do_not_merge_different_fx_modes(
    settings, monkeypatch
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "failed-core-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": "failed",
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )
    service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="normal-request",
    )
    recovery = {
        "report_date": REPORT_DATE,
        "wait_for_inputs": False,
        "requested_by": "operator",
        "use_existing_fx_only": True,
        "expected_fx_source_version": "fx-source-v1",
        "recovery_of_run_id": "failed-core-run",
    }

    with pytest.raises(ValueError, match="同一请求编号"):
        service.request_core_update(
            settings,
            idempotency_key="normal-request",
            **recovery,
        )
    with pytest.raises(ValueError, match="已有不同恢复参数"):
        service.request_core_update(
            settings,
            idempotency_key="recovery-request",
            **recovery,
        )


def test_curve_manifest_participates_in_idempotency_and_active_dedupe(
    settings, monkeypatch
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "failed-core-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": "failed",
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )
    parameters = {
        "report_date": REPORT_DATE,
        "wait_for_inputs": False,
        "requested_by": "operator",
        "use_existing_curves_only": True,
        "expected_curve_snapshots": expected_curve_snapshots(),
        "recovery_of_run_id": "failed-core-run",
    }
    first = service.request_core_update(
        settings,
        idempotency_key="curve-recovery-request",
        **parameters,
    )
    reordered = {
        **parameters,
        "expected_curve_snapshots": list(reversed(expected_curve_snapshots())),
    }
    assert (
        service.request_core_update(
            settings,
            idempotency_key="curve-recovery-request",
            **reordered,
        )["run_id"]
        == first["run_id"]
    )
    changed_manifest = expected_curve_snapshots()
    changed_manifest[0]["source_version"] = "sv-treasury-changed"
    changed = {**parameters, "expected_curve_snapshots": changed_manifest}

    with pytest.raises(ValueError, match="同一请求编号"):
        service.request_core_update(
            settings,
            idempotency_key="curve-recovery-request",
            **changed,
        )
    with pytest.raises(ValueError, match="已有不同恢复参数"):
        service.request_core_update(
            settings,
            idempotency_key="curve-recovery-request-2",
            **changed,
        )


def test_waiting_request_runs_after_arrival_without_a_browser(settings, monkeypatch):
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


def test_legacy_run_without_fx_fields_uses_three_argument_executor(
    settings, monkeypatch
):
    ready_files(settings)
    run = request(settings, monkeypatch, wait=False)
    legacy_run = dict(run)
    for key in (
        "use_existing_fx_only",
        "expected_fx_source_version",
        "use_existing_curves_only",
        "expected_curve_snapshots",
        "recovery_of_run_id",
    ):
        legacy_run.pop(key)
    repo.save_run(settings.governance_path, legacy_run)
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 0

    execute.assert_called_once()
    assert len(execute.call_args.args) == 3
    assert execute.call_args.kwargs == {}


def test_fx_recovery_run_passes_expected_version_to_executor(settings, monkeypatch):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "failed-core-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": "failed",
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )
    service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="recovery-request",
        use_existing_fx_only=True,
        expected_fx_source_version="fx-source-v1",
        recovery_of_run_id="failed-core-run",
    )
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 0

    assert execute.call_args.kwargs == {
        "use_existing_fx_only": True,
        "expected_fx_source_version": "fx-source-v1",
    }


@pytest.mark.parametrize("include_fx", [False, True])
def test_curve_recovery_run_passes_normalized_manifest_to_executor(
    settings, monkeypatch, include_fx
):
    ready_files(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    repo.save_run(
        settings.governance_path,
        {
            "run_id": "failed-core-run",
            "report_date": REPORT_DATE,
            "workflow": "core_financial",
            "status": "failed",
            "submitted_at": "2026-09-14T01:00:00+00:00",
        },
    )
    service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="curve-recovery-request",
        use_existing_fx_only=include_fx,
        expected_fx_source_version="fx-source-v1" if include_fx else None,
        use_existing_curves_only=True,
        expected_curve_snapshots=expected_curve_snapshots(),
        recovery_of_run_id="failed-core-run",
    )
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 0

    expected_kwargs = {
        "use_existing_curves_only": True,
        "expected_curve_snapshots": list(reversed(expected_curve_snapshots())),
    }
    if include_fx:
        expected_kwargs.update(
            use_existing_fx_only=True,
            expected_fx_source_version="fx-source-v1",
        )
    assert execute.call_args.kwargs == expected_kwargs


def test_execute_core_only_adds_fx_recovery_keywords_for_recovery_mode(
    settings, monkeypatch
):
    balance_workbooks(settings)
    pnl_source = import_module("backend.app.services.pnl_source_service")
    global_refresh = import_module("scripts.run_global_data_refresh")
    monkeypatch.setattr(
        pnl_source,
        "load_latest_pnl_refresh_input",
        Mock(
            return_value=SimpleNamespace(report_date=REPORT_DATE, fi_rows=[{"pnl": 1}])
        ),
    )
    refresh = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(global_refresh, "run_global_data_refresh", refresh)
    progress = Mock()

    worker._execute_core(settings, REPORT_DATE, progress)
    assert refresh.call_args.kwargs == {
        "report_date": REPORT_DATE,
        "on_progress": progress,
    }

    worker._execute_core(
        settings,
        REPORT_DATE,
        progress,
        use_existing_fx_only=True,
        expected_fx_source_version="fx-source-v1",
    )
    assert refresh.call_args.kwargs == {
        "report_date": REPORT_DATE,
        "on_progress": progress,
        "use_existing_fx_only": True,
        "expected_fx_source_version": "fx-source-v1",
    }


def test_execute_core_adds_curve_keywords_only_for_curve_recovery(
    settings, monkeypatch
):
    balance_workbooks(settings)
    pnl_source = import_module("backend.app.services.pnl_source_service")
    global_refresh = import_module("scripts.run_global_data_refresh")
    monkeypatch.setattr(
        pnl_source,
        "load_latest_pnl_refresh_input",
        Mock(
            return_value=SimpleNamespace(report_date=REPORT_DATE, fi_rows=[{"pnl": 1}])
        ),
    )
    refresh = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(global_refresh, "run_global_data_refresh", refresh)
    progress = Mock()
    snapshots = list(reversed(expected_curve_snapshots()))

    worker._execute_core(
        settings,
        REPORT_DATE,
        progress,
        use_existing_curves_only=True,
        expected_curve_snapshots=snapshots,
    )

    assert refresh.call_args.kwargs == {
        "report_date": REPORT_DATE,
        "on_progress": progress,
        "use_existing_curves_only": True,
        "expected_curve_snapshots": snapshots,
    }


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"use_existing_fx_only": "true"},
        {"use_existing_fx_only": True, "expected_fx_source_version": None},
        {"use_existing_fx_only": False, "expected_fx_source_version": "fx-source-v1"},
        {
            "use_existing_fx_only": True,
            "expected_fx_source_version": "fx-source-v1",
            "recovery_of_run_id": "",
        },
        {
            "workflow": "balance_daily",
            "use_existing_fx_only": True,
            "expected_fx_source_version": "fx-source-v1",
            "recovery_of_run_id": "failed-core-run",
        },
        {"use_existing_curves_only": "true"},
        {"use_existing_curves_only": True, "expected_curve_snapshots": None},
        {
            "use_existing_curves_only": False,
            "expected_curve_snapshots": expected_curve_snapshots(),
        },
        {
            "use_existing_curves_only": True,
            "expected_curve_snapshots": expected_curve_snapshots(),
            "recovery_of_run_id": None,
        },
    ],
)
def test_invalid_persisted_fx_recovery_fields_fail_before_execution(
    settings, monkeypatch, invalid_fields
):
    ready_files(settings)
    run = request(settings, monkeypatch, wait=False)
    repo.save_run(settings.governance_path, {**run, **invalid_fields})
    execute = Mock()
    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 1

    execute.assert_not_called()
    failed = repo.latest_runs(settings.governance_path)[0]
    assert failed["status"] == "failed"
    assert "参数无效" in failed["message"]


def test_cancelled_wait_does_not_execute_after_file_arrival(settings, monkeypatch):
    run = request(settings, monkeypatch)
    service.cancel_update(settings, run["run_id"], cancelled_by="operator")
    ready_files(settings)
    execute = Mock()
    monkeypatch.setattr(worker, "_execute_core", execute)
    worker.drain_updates(settings)
    execute.assert_not_called()
    assert repo.latest_runs(settings.governance_path)[0]["cancelled_by"] == "operator"


def test_failed_verification_keeps_completed_steps_and_never_reports_success(
    settings, monkeypatch
):
    ready_files(settings)
    request(settings, monkeypatch)

    def execute(_settings, _report_date, progress):
        progress(
            {
                "steps": [
                    {
                        "name": "formal_balance",
                        "status": "completed",
                        "started_at": "2026-09-10T07:35:00+00:00",
                        "finished_at": "2026-09-10T07:35:01+00:00",
                        "elapsed_seconds": 1.234,
                    },
                    {
                        "name": "verify",
                        "status": "failed",
                        "error_message": "missing date",
                        "started_at": "2026-09-10T07:35:01+00:00",
                        "finished_at": "2026-09-10T07:35:01.100000+00:00",
                        "elapsed_seconds": 0.1,
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
    assert run["steps"][0]["elapsed_seconds"] == 1.234
    assert run["steps"][0]["started_at"] == "2026-09-10T07:35:00+00:00"
    assert run["steps"][1]["elapsed_seconds"] == 0.1
    assert run["attempt"] == 1


def test_progress_keeps_only_publication_step_results_and_global_run_id(
    settings, monkeypatch
):
    ready_files(settings)
    request(settings, monkeypatch, wait=False)
    prepare_result = {
        "status": "completed",
        "generation": "prepared-generation",
        "manifest_sha256": "prepare-manifest",
        "resource_limits": {"profile": "bounded_v1", "peak_rss_mb": 512},
    }
    publish_result = {
        "status": "completed",
        "generation": "published-generation",
        "manifest_sha256": "publish-manifest",
        "recovered_after_commit": False,
        "resource_limits": {"profile": "bounded_v1", "peak_rss_mb": 640},
    }

    def execute(_settings, _report_date, progress):
        progress(
            {
                "status": "completed",
                "run_id": "global-refresh-success",
                "current_step": None,
                "steps": [
                    {
                        "name": "formal_balance",
                        "status": "completed",
                        "result": {"large_business_payload": [1, 2, 3]},
                        "error_type": "SyntheticError",
                        "failure_category": "synthetic_failure",
                        "resource_limits": {"profile": "unrelated"},
                    },
                    {
                        "name": "pnl_by_business_page_prepare",
                        "status": "completed",
                        "result": prepare_result,
                    },
                    {
                        "name": "publish",
                        "status": "completed",
                        "result": publish_result,
                    },
                ],
            }
        )
        return {"status": "completed"}

    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 0

    run = repo.latest_runs(settings.governance_path)[0]
    assert run["global_run_id"] == "global-refresh-success"
    assert "result" not in run["steps"][0]
    assert "error_type" not in run["steps"][0]
    assert "failure_category" not in run["steps"][0]
    assert "resource_limits" not in run["steps"][0]
    assert run["steps"][1]["result"] == prepare_result
    assert run["steps"][2]["result"] == publish_result


@pytest.mark.parametrize("step_name", ["pnl_by_business_page_prepare", "publish"])
def test_progress_keeps_publication_failure_details(settings, monkeypatch, step_name):
    ready_files(settings)
    request(settings, monkeypatch, wait=False)
    resource_limits = {"profile": "bounded_v1", "stage": "before_persist"}

    def execute(_settings, _report_date, progress):
        progress(
            {
                "status": "failed",
                "run_id": "global-refresh-failure",
                "current_step": None,
                "steps": [
                    {
                        "name": step_name,
                        "status": "failed",
                        "error_type": "PnlByBusinessResourceBudgetExceeded",
                        "error_message": "resource budget exceeded",
                        "failure_category": "resource_over_budget",
                        "resource_limits": resource_limits,
                    }
                ],
            }
        )
        raise RuntimeError("resource budget exceeded")

    monkeypatch.setattr(worker, "_execute_core", execute)

    assert worker.drain_updates(settings) == 1

    run = repo.latest_runs(settings.governance_path)[0]
    assert run["global_run_id"] == "global-refresh-failure"
    assert run["steps"][0]["error_type"] == "PnlByBusinessResourceBudgetExceeded"
    assert run["steps"][0]["failure_category"] == "resource_over_budget"
    assert run["steps"][0]["resource_limits"] == resource_limits


def test_transient_failure_retries_at_most_three_attempts(settings, monkeypatch):
    ready_files(settings)
    request(settings, monkeypatch)
    execute = Mock(side_effect=TimeoutError("temporary writer lock"))
    monkeypatch.setattr(worker, "_execute_core", execute)
    for attempt in range(1, 4):
        worker.drain_updates(settings)
        run = repo.latest_runs(settings.governance_path)[0]
        assert run["attempt"] == attempt
        assert run["status"] == ("retrying" if attempt < 3 else "failed")
        repo.save_run(
            settings.governance_path,
            {**run, "retry_after": "2000-01-01T00:00:00+00:00"},
        )
    worker.drain_updates(settings)
    assert execute.call_count == 3


@pytest.mark.parametrize("error_type", [TimeoutError, ConnectionError])
def test_financial_publish_transient_failure_never_replays_completed_work(
    settings, monkeypatch, error_type
):
    from scripts.run_global_data_refresh import GlobalDataRefreshFailed

    ready_files(settings)
    request(settings, monkeypatch, wait=False)
    failure_receipt = {
        "status": "failed",
        "run_id": "global-publish-failure",
        "failed_step": "publish",
        "steps": [
            {"name": "formal_balance", "status": "completed"},
            {"name": "verify", "status": "completed"},
            {
                "name": "publish",
                "status": "failed",
                "error_type": error_type.__name__,
                "error_message": "temporary publication failure",
            },
        ],
    }

    def fail_publication(_settings, _report_date, progress):
        progress(failure_receipt)
        raise GlobalDataRefreshFailed(failure_receipt) from error_type(
            "temporary publication failure"
        )

    execute = Mock(side_effect=fail_publication)
    monkeypatch.setattr(worker, "_execute_core", execute)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)

    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert run["attempt"] == 1
    assert run.get("retry_after") is None
    assert run["failure_receipt"] == failure_receipt
    assert run["global_run_id"] == "global-publish-failure"
    assert [step["status"] for step in run["steps"]] == ["completed", "completed", "failed"]
    assert worker.drain_updates(settings) == 0
    execute.assert_called_once()


@pytest.mark.parametrize(
    "retry_after", ["2000-01-01T00:00:00+00:00", "2999-01-01T00:00:00+00:00"]
)
def test_persisted_publish_retry_is_stopped_before_preflight_or_execution(
    settings, monkeypatch, retry_after
):
    ready_files(settings)
    run = request(settings, monkeypatch, wait=False)
    failure_receipt = {
        "status": "failed",
        "failed_step": "publish",
        "run_id": "original-global-run",
        "steps": [
            {"name": "verify", "status": "completed"},
            {"name": "publish", "status": "failed", "error_message": "original timeout"},
        ],
    }
    steps = [
        {"key": "verify", "status": "completed", "elapsed_seconds": 2.5},
        {"key": "publish", "status": "failed", "error_message": "original timeout"},
    ]
    repo.save_run(
        settings.governance_path,
        {
            **run,
            "status": "retrying",
            "attempt": 1,
            "retry_after": retry_after,
            "failure_receipt": failure_receipt,
            "steps": steps,
            "global_run_id": "original-global-run",
        },
    )
    preflight = Mock(side_effect=AssertionError("completed work must not be preflighted again"))
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(worker, "input_preflight", preflight)
    monkeypatch.setattr(worker, "_execute_core", execute)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)

    assert worker.drain_updates(settings) == 1
    stopped = repo.latest_runs(settings.governance_path)[0]
    assert stopped["status"] == "failed"
    assert stopped["attempt"] == 1
    assert stopped.get("retry_after") is None
    assert stopped["failure_receipt"] == failure_receipt
    assert stopped["steps"] == steps
    assert stopped["global_run_id"] == "original-global-run"
    preflight.assert_not_called()
    execute.assert_not_called()
    assert worker.drain_updates(settings) == 0
    execute.assert_not_called()


@pytest.mark.parametrize("error_type", [TimeoutError, ConnectionError])
@pytest.mark.parametrize("failed_step", ["formal_balance", "source_preview"])
def test_failed_step_receipt_without_progress_never_replays_unknown_writes(
    settings, monkeypatch, error_type, failed_step
):
    from scripts.run_global_data_refresh import GlobalDataRefreshFailed

    ready_files(settings)
    request(settings, monkeypatch, wait=False)
    failure_receipt = {
        "status": "failed",
        "failed_step": failed_step,
        "steps": [{"name": failed_step, "status": "failed"}],
    }
    failure = GlobalDataRefreshFailed(failure_receipt)
    failure.__cause__ = error_type("temporary failure before completed body")
    execute = Mock(side_effect=[failure, {"status": "completed"}])
    monkeypatch.setattr(worker, "_execute_core", execute)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)

    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[0]
    assert run["status"] == "failed"
    assert run["attempt"] == 1
    assert run["retry_after"] is None
    assert run["failure_receipt"] == failure_receipt
    repo.save_run(
        settings.governance_path,
        {**run, "retry_after": "2000-01-01T00:00:00+00:00"},
    )
    assert worker.drain_updates(settings) == 0
    completed = repo.latest_runs(settings.governance_path)[0]
    assert completed["status"] == "failed"
    assert completed["attempt"] == 1
    assert execute.call_count == 1


def test_interrupted_run_is_failed_without_replaying_partial_writes(
    settings, monkeypatch
):
    run = request(settings, monkeypatch)
    repo.save_run(settings.governance_path, {**run, "status": "running"})
    execute = Mock()
    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 1
    execute.assert_not_called()
    assert "中断" in repo.latest_runs(settings.governance_path)[0]["message"]


def test_database_open_failure_is_not_reported_as_missing_data(settings, monkeypatch):
    settings.duckdb_path.touch()
    monkeypatch.setattr(
        repo, "read_only_connection", Mock(side_effect=RuntimeError("locked"))
    )
    assert all(
        row["status"] == "error" and row["as_of_date"] is None
        for row in repo.financial_dates(settings.duckdb_path)
    )


def test_financial_date_programming_error_is_not_reported_as_storage_failure(settings, monkeypatch):
    settings.duckdb_path.touch()
    monkeypatch.setattr(
        repo, "read_only_connection", Mock(side_effect=TypeError("invalid reader implementation"))
    )
    with pytest.raises(TypeError, match="invalid reader implementation"):
        repo.financial_dates(settings.duckdb_path)


def test_api_checks_every_existing_write_permission_and_rejects_command_input(
    settings, monkeypatch
):
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    authorize = Mock()
    monkeypatch.setattr(routes, "ensure_user_allowed", authorize)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    client = TestClient(app)
    headers = {"Idempotency-Key": "http-request"}
    response = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "wait_for_inputs": True},
        headers=headers,
    )
    assert response.status_code == 202
    assert {call.kwargs["resource"] for call in authorize.call_args_list} == set(
        routes.CORE_RESOURCES
    )
    invalid = client.post(
        "/api/data-updates/core",
        json={"report_date": REPORT_DATE, "command": "arbitrary"},
        headers=headers,
    )
    assert invalid.status_code == 422
    authorize.side_effect = PermissionError("denied")
    denied = client.post(
        "/api/data-updates/core", json={"report_date": "2026-09-01"}, headers=headers
    )
    assert denied.status_code == 403
    assert len(repo.latest_runs(settings.governance_path)) == 1


def test_market_control_starts_only_the_fixed_registered_task(monkeypatch):
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    execute = Mock()
    monkeypatch.setattr(service.subprocess, "run", execute)
    assert service.start_market_update()["status"] == "accepted"
    assert execute.call_args.args[0] == [
        "schtasks",
        "/Run",
        "/TN",
        "MOSS-DailyDataRefresh",
    ]


def test_daily_balance_refresh_does_not_wait_for_monthly_pnl(settings, monkeypatch):
    for name in ("ZQTZSHOW-20260831.xls", "TYWLSHOW-20260831.xls"):
        source_file(settings, name)
    assert (
        service.input_preflight(settings, REPORT_DATE, "balance_daily")["ready"] is True
    )
    assert (
        service.input_preflight(settings, REPORT_DATE, "core_financial")["ready"]
        is False
    )
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="daily",
        workflow="balance_daily",
    )
    daily = Mock(return_value={"status": "completed"})
    core = Mock()
    monkeypatch.setattr(worker, "_execute_balance", daily)
    monkeypatch.setattr(worker, "_execute_core", core)
    worker.drain_updates(settings)
    daily.assert_called_once()
    core.assert_not_called()


def test_daily_balance_progress_includes_successful_step_timings(settings, monkeypatch):
    balance_workbooks(settings)
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        Mock(return_value={"status": "completed"}),
    )
    monkeypatch.setattr(worker, "verify_daily_balance_date", lambda *_args: None)
    events = []

    result = worker._execute_balance(settings, REPORT_DATE, events.append)

    assert result == {
        "status": "completed",
        "report_date": REPORT_DATE,
        "pipeline": {"status": "completed"},
    }
    completed = events[-1]["steps"]
    assert [step["status"] for step in completed] == ["completed", "completed"]
    assert all(isinstance(step["elapsed_seconds"], float) for step in completed)
    assert all(step["elapsed_seconds"] >= 0 for step in completed)
    assert all(step["started_at"] and step["finished_at"] for step in completed)
    assert completed[0]["result"] == result


def test_daily_balance_enabled_publication_refreshes_preview_from_existing_manifests(
    settings, monkeypatch
):
    balance_workbooks(settings)
    settings.system_read_publication_enabled = True
    pipeline = {
        "status": "completed",
        "balance": {"run_id": "balance-child"},
        "bond_analytics": {"run_id": "bond-child"},
        "risk_tensor": {"run_id": "risk-child"},
    }
    preview_calls = []
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        Mock(return_value=pipeline),
    )
    monkeypatch.setattr(worker, "verify_daily_balance_date", lambda *_args: None)
    monkeypatch.setattr(
        "backend.app.tasks.source_preview_refresh._refresh_source_preview_cache",
        lambda **kwargs: preview_calls.append(kwargs)
        or {
            "status": "completed",
            "run_id": "preview-child",
            "cache_key": "source_preview.foundation",
            "report_dates": [REPORT_DATE],
            "source_version": "preview-source",
        },
    )
    events = []

    result = worker._execute_balance(settings, REPORT_DATE, events.append)

    assert preview_calls[0]["from_existing_manifests"] is True
    assert result["pipeline"]["source_preview"]["run_id"] == "preview-child"
    assert [step["name"] for step in events[-1]["steps"]] == [
        "daily_balance_and_risk",
        "verify",
        "source_preview",
    ]


def test_daily_balance_preview_dependency_failure_is_reported_after_balance_success(
    settings, monkeypatch
):
    balance_workbooks(settings)
    settings.system_read_publication_enabled = True
    pipeline_calls = 0

    def completed_pipeline(**_kwargs):
        nonlocal pipeline_calls
        pipeline_calls += 1
        return {"status": "completed"}

    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        completed_pipeline,
    )
    monkeypatch.setattr(worker, "verify_daily_balance_date", lambda *_args: None)
    monkeypatch.setattr(
        "backend.app.tasks.source_preview_refresh._refresh_source_preview_cache",
        Mock(side_effect=ValueError("existing manifests invalid")),
    )
    events = []

    with pytest.raises(RuntimeError, match="来源预览依赖失败.*ValueError") as caught:
        worker._execute_balance(settings, REPORT_DATE, events.append)

    assert pipeline_calls == 1
    assert isinstance(caught.value.__cause__, ValueError)
    assert "existing manifests invalid" not in str(caught.value)
    assert "existing manifests invalid" not in str(caught.value.receipt)
    assert caught.value.receipt["failed_step"] == "source_preview"
    assert caught.value.receipt["business_body_status"] == "completed"
    assert events[-1]["steps"][-1]["name"] == "source_preview"
    assert events[-1]["steps"][-1]["status"] == "failed"


def test_daily_balance_preview_dependency_failure_does_not_retry_completed_balance(
    settings, monkeypatch
):
    settings.system_read_publication_enabled = True
    balance_workbooks(settings)
    monkeypatch.setattr(service, "require_scheduler", lambda _: None)
    service.request_core_update(
        settings,
        report_date=REPORT_DATE,
        wait_for_inputs=False,
        requested_by="operator",
        idempotency_key="balance-preview-failure",
        workflow="balance_daily",
    )
    pipeline = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        pipeline,
    )
    monkeypatch.setattr(worker, "verify_daily_balance_date", lambda *_args: None)
    monkeypatch.setattr(
        "backend.app.tasks.source_preview_refresh._refresh_source_preview_cache",
        Mock(side_effect=TimeoutError("preview writer lock")),
    )
    monkeypatch.setattr(
        worker,
        "_recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: 0,
    )

    assert worker.drain_updates(settings) == 1
    run = repo.latest_runs(settings.governance_path)[-1]
    assert pipeline.call_count == 1
    assert run["status"] == "failed"
    assert run.get("retry_after") is None
    assert run["failure_receipt"]["failed_step"] == "source_preview"
    assert run["steps"][-1]["key"] == "source_preview"
    assert run["steps"][-1]["status"] == "failed"
    assert worker.drain_updates(settings) == 0
    assert pipeline.call_count == 1


def test_daily_balance_progress_includes_failed_step_timing(settings, monkeypatch):
    balance_workbooks(settings)
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        Mock(side_effect=RuntimeError("writer lock")),
    )
    events = []

    with pytest.raises(RuntimeError, match="writer lock"):
        worker._execute_balance(settings, REPORT_DATE, events.append)

    failed = events[-1]["steps"][0]
    assert failed["name"] == "daily_balance_and_risk"
    assert failed["status"] == "failed"
    assert failed["error_message"] == "更新步骤失败（异常类型：RuntimeError）。"
    assert isinstance(failed["elapsed_seconds"], float)
    assert failed["elapsed_seconds"] >= 0


def test_daily_balance_progress_includes_failed_verification_timing(
    settings, monkeypatch
):
    balance_workbooks(settings)
    monkeypatch.setattr(
        "backend.app.tasks.formal_balance_pipeline.run_formal_balance_pipeline_sync",
        Mock(return_value={"status": "completed"}),
    )
    monkeypatch.setattr(
        worker,
        "verify_daily_balance_date",
        Mock(side_effect=ValueError("missing report date")),
    )
    events = []

    with pytest.raises(ValueError, match="missing report date"):
        worker._execute_balance(settings, REPORT_DATE, events.append)

    failed = events[-1]["steps"][-1]
    assert failed["name"] == "verify"
    assert failed["status"] == "failed"
    assert failed["error_message"] == "更新步骤失败（异常类型：ValueError）。"
    assert isinstance(failed["elapsed_seconds"], float)
    assert failed["elapsed_seconds"] >= 0


def test_daily_verification_checks_requested_partition_even_with_newer_data(settings):
    with duckdb.connect(str(settings.duckdb_path)) as conn:
        for key, _, table, column in repo.DATE_TABLES:
            if key != "pnl":
                conn.execute(f'CREATE TABLE "{table}" ("{column}" DATE)')
                conn.execute(
                    f'INSERT INTO "{table}" VALUES (?), (?)',
                    [REPORT_DATE, "2026-09-04"],
                )
    repo.verify_daily_balance_date(settings.duckdb_path, REPORT_DATE)
    with pytest.raises(ValueError, match="未通过核验"):
        repo.verify_daily_balance_date(settings.duckdb_path, "2026-08-30")


def test_durable_pnl_precompute_dirty_work_recovers_without_update_request(
    settings, monkeypatch
):
    with duckdb.connect(str(settings.duckdb_path), read_only=False) as conn:
        conn.execute("create table fact_formal_pnl_fi (report_date varchar)")
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-06-30",),
            reason="test_fact_replacement",
            supported_cutoffs=("2025-06-30",),
        )
        conn.execute("commit")

    dispatch = Mock()
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        dispatch,
    )

    assert repo.latest_runs(settings.governance_path) == []
    assert worker.drain_updates(settings) == 0
    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["year"] == 2025
    assert dispatch.call_args.kwargs["as_of_dates"] == ["2025-06-30"]
    assert dispatch.call_args.kwargs["dependency_revision"] == 1
    assert dispatch.call_args.kwargs["trigger_reason"] == "persistent_dirty_recovery"


def test_pnl_precompute_recovery_failure_does_not_block_other_dirty_years(
    settings, monkeypatch
):
    pnl_service = import_module("backend.app.services.pnl_service")
    with duckdb.connect(str(settings.duckdb_path), read_only=False) as conn:
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2024-12-31", "2025-12-31"),
            reason="test_cross_year_replacement",
            supported_cutoffs=("2024-12-31", "2025-12-31"),
        )
        conn.execute("commit")

    recovered_years: list[int] = []

    def recover(_settings, *, pending):
        recovered_years.append(int(pending["year"]))
        if pending["year"] == 2024:
            raise RuntimeError("first year dispatch failed")

    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_precompute",
        recover,
    )
    handoff_recovery = Mock(return_value=[])
    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_adjustment_handoffs",
        handoff_recovery,
    )

    assert worker.drain_updates(settings) == 1
    assert recovered_years == [2024, 2025]
    handoff_recovery.assert_called_once_with(settings)


def test_adjustment_handoff_recovery_runs_without_database_dirty_work(
    settings, monkeypatch
):
    pnl_service = import_module("backend.app.services.pnl_service")
    handoff_recovery = Mock(return_value=[])
    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_adjustment_handoffs",
        handoff_recovery,
    )

    assert worker.drain_updates(settings) == 0
    handoff_recovery.assert_called_once_with(settings)


def test_page_rebuild_recovery_runs_without_database_dirty_work_and_counts_failures(
    settings, monkeypatch
):
    page_recovery = Mock(
        return_value={
            "status": "partial_failure",
            "pending_count": 2,
            "dispatched_count": 1,
            "completed_count": 0,
            "failed_count": 1,
            "items": [],
        }
    )
    monkeypatch.setattr(
        pnl_by_business_page_lifecycle,
        "recover_pending_pnl_by_business_page_rebuilds",
        page_recovery,
    )

    assert worker.drain_updates(settings) == 1
    page_recovery.assert_called_once_with(settings)


def test_database_dirty_read_failure_does_not_block_governance_recovery(
    settings, monkeypatch
):
    pnl_service = import_module("backend.app.services.pnl_service")
    pnl_by_business_page_lifecycle = import_module(
        "backend.app.services.pnl_by_business_page_lifecycle"
    )
    monkeypatch.setattr(
        pnl_service.PnlRepository,
        "list_pending_pnl_by_business_precompute",
        Mock(side_effect=RuntimeError("active database is locked")),
    )
    handoff_recovery = Mock(return_value=[])
    page_recovery = Mock(
        return_value={
            "status": "completed",
            "pending_count": 0,
            "dispatched_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "items": [],
        }
    )
    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_adjustment_handoffs",
        handoff_recovery,
    )
    monkeypatch.setattr(
        pnl_by_business_page_lifecycle,
        "recover_pending_pnl_by_business_page_rebuilds",
        page_recovery,
    )

    assert worker.drain_updates(settings) == 1
    handoff_recovery.assert_called_once_with(settings)
    page_recovery.assert_called_once_with(settings)


def test_daily_dirty_range_without_month_end_source_stays_pending_without_dispatch(
    settings, monkeypatch
):
    with duckdb.connect(str(settings.duckdb_path), read_only=False) as conn:
        conn.execute("create table fact_formal_pnl_fi (report_date varchar)")
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=("2025-06-15",),
            reason="test_daily_balance_replacement",
        )
        conn.execute("commit")

    dispatch = Mock()
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        dispatch,
    )

    assert worker.drain_updates(settings) == 0
    dispatch.assert_not_called()
    pending = pnl_service.PnlRepository(
        str(settings.duckdb_path)
    ).list_pending_pnl_by_business_precompute()
    assert len(pending) == 1
    assert pending[0]["dirty_from_date"] == "2025-06-15"
    assert pending[0]["target_dates"] == ()


@pytest.mark.parametrize("failure_stage", ["preflight", "execution", "interrupted_publication"])
def test_update_failure_public_receipt_omits_private_exception(settings, monkeypatch, caplog, failure_stage):
    ready_files(settings)
    request(settings, monkeypatch)
    marker = "synthetic-update-private-provider-token"
    execute = Mock(side_effect=TypeError(marker))
    monkeypatch.setattr(worker, "_execute_core", execute)
    monkeypatch.setattr(worker, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    if failure_stage == "preflight":
        monkeypatch.setattr(worker, "input_preflight", Mock(side_effect=OSError(marker)))
    elif failure_stage == "interrupted_publication":
        run = repo.latest_runs(settings.governance_path)[0]
        repo.save_run(settings.governance_path, {**run, "status": "running"})
        monkeypatch.setattr(
            "backend.app.tasks.system_read_publication.recover_committed_system_read_publication",
            Mock(side_effect=RuntimeError(marker)),
        )
    assert worker.drain_updates(settings) == 1
    stored = repo.latest_runs(settings.governance_path)[0]
    assert stored["status"] == "failed"
    assert stored.get("retry_after") is None
    assert execute.call_count == int(failure_stage == "execution")
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _: None)
    monkeypatch.setattr(routes, "_authorize", lambda *a, **kw: None)
    monkeypatch.setattr(service, "scheduled_updates", lambda: {})
    monkeypatch.setattr(service, "financial_dates", lambda _: {})
    with TestClient(app) as client:
        response = client.get("/api/data-updates")
    assert response.status_code == 200
    assert marker not in response.text
    assert marker not in str(stored)
    assert marker not in caplog.text
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("failure_stage", ["read", "year", "handoff", "page"])
def test_durable_recovery_failure_is_counted_without_private_log(settings, monkeypatch, caplog, failure_stage):
    marker = "synthetic-recovery-private-provider-token"
    read = Mock(return_value=[{"year": 2024, "dependency_revision": 1}, {"year": 2025, "dependency_revision": 2}])
    recover = Mock(return_value=None)
    handoff = Mock(return_value=[])
    page = Mock(return_value={"failed_count": 0})
    if failure_stage == "read":
        read.side_effect = RuntimeError(marker)
    elif failure_stage == "year":
        recover.side_effect = [TypeError(marker), None]
    elif failure_stage == "handoff":
        handoff.side_effect = TypeError(marker)
    else:
        page.side_effect = TypeError(marker)
    monkeypatch.setattr(pnl_service.PnlRepository, "list_pending_pnl_by_business_precompute", read)
    monkeypatch.setattr(pnl_service, "recover_pending_pnl_by_business_precompute", recover)
    monkeypatch.setattr(pnl_service, "recover_pending_pnl_by_business_adjustment_handoffs", handoff)
    monkeypatch.setattr(pnl_by_business_page_lifecycle, "recover_pending_pnl_by_business_page_rebuilds", page)
    assert worker._recover_pending_pnl_by_business_precompute(settings) == 1
    assert recover.call_count == (0 if failure_stage == "read" else 2)
    handoff.assert_called_once_with(settings)
    page.assert_called_once_with(settings)
    assert marker not in caplog.text
    assert ("RuntimeError" if failure_stage == "read" else "TypeError") in caplog.text
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("failure_stage", ["read", "preflight", "interrupted_publication"])
def test_bounded_update_reads_do_not_swallow_programming_errors(settings, monkeypatch, failure_stage):
    failure = TypeError("synthetic-programming-error")
    if failure_stage == "read":
        monkeypatch.setattr(pnl_service.PnlRepository, "list_pending_pnl_by_business_precompute", Mock(side_effect=failure))
        with pytest.raises(TypeError) as caught:
            worker._recover_pending_pnl_by_business_precompute(settings)
    else:
        ready_files(settings)
        request(settings, monkeypatch)
        if failure_stage == "preflight":
            monkeypatch.setattr(worker, "input_preflight", Mock(side_effect=failure))
        else:
            run = repo.latest_runs(settings.governance_path)[0]
            repo.save_run(settings.governance_path, {**run, "status": "running"})
            monkeypatch.setattr("backend.app.tasks.system_read_publication.recover_committed_system_read_publication", Mock(side_effect=failure))
        execute = Mock()
        monkeypatch.setattr(worker, "_execute_core", execute)
        with pytest.raises(TypeError) as caught:
            worker.drain_updates(settings)
        execute.assert_not_called()
        assert repo.latest_runs(settings.governance_path)[0]["status"] != "completed"
    assert caught.value is failure


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



def test_balance_pipeline_timeout_with_unknown_partial_write_never_retries(
    settings, monkeypatch
):
    balance_workbooks(settings)
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
    balance_workbooks(settings)
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
    balance_workbooks(settings)
    source_file(settings, "FI损益202608.xls")
    request(settings, monkeypatch)
    monkeypatch.setattr(
        "backend.app.services.pnl_source_service.load_latest_pnl_refresh_input",
        lambda **_kwargs: SimpleNamespace(
            report_date=REPORT_DATE, fi_rows=[{"synthetic": True}]
        ),
    )
    global_calls = 0

    def global_refresh(*, report_date, on_progress, data_update_run_id):
        assert data_update_run_id
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


def product_category_scope():
    return {
        "scanned_report_dates": ["2025-01-31", "2026-01-31", "2026-02-28"],
        "scanned_years": ["2025", "2026"], "scanned_date_count": 3,
        "rebuilt_report_dates": ["2026-01-31", "2026-02-28"],
        "rebuilt_years": ["2026"], "rebuilt_date_count": 2,
        "reused_report_dates": ["2025-01-31"], "reused_years": ["2025"], "reused_date_count": 1,
        "removed_report_dates": ["2024-12-31"], "removed_years": ["2024"], "removed_date_count": 1,
    }


def test_product_category_scope_survives_worker_and_public_api_without_private_fields(settings, monkeypatch):
    ready_files(settings)
    request(settings, monkeypatch, wait=False)
    scope = product_category_scope()
    def execute(_settings, _report_date, progress):
        progress({"run_id": "global-scope", "steps": [{
            "name": "product_category_pnl", "status": "completed",
            "result": {"status": "completed", "refresh_scope": {**scope, "source_path": "F:/private-source"},
                       "operator": "private-operator", "error_message": "private-exception"},
        }]})
        return {"status": "completed"}

    monkeypatch.setattr(worker, "_execute_core", execute)
    assert worker.drain_updates(settings) == 0
    stored = repo.latest_runs(settings.governance_path)[0]
    assert stored["steps"][0]["refresh_scope"]["rebuilt_date_count"] == 2
    assert "result" not in stored["steps"][0]

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: AuthContext(user_id="viewer", role="viewer")
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "_authorize", Mock(side_effect=routes.HTTPException(status_code=403)))
    monkeypatch.setattr(service, "scheduled_updates", lambda: {"status": "available", "tasks": []})
    response = TestClient(app).get("/api/data-updates")
    assert response.status_code == 200
    public = next(row for row in response.json()["runs"] if row["run_id"] == stored["run_id"])
    assert public["steps"][0]["refresh_scope"] == scope
    assert all(value not in response.text for value in ("private-source", "private-operator", "private-exception"))


@pytest.mark.parametrize("change", [
    {"key": "formal_balance"}, {"status": "failed"},
    {"refresh_scope": {"scanned_report_dates": ["F:/private-source"]}},
])
def test_public_scope_ignores_other_steps_failed_steps_and_invalid_metadata(change):
    step = {"key": "product_category_pnl", "status": "completed", "refresh_scope": product_category_scope(), **change}
    public = routes._public_run({"steps": [step]}, input_directory="F:/fixture")
    assert "refresh_scope" not in public["steps"][0]


@pytest.mark.parametrize("override", [
    {"scanned_report_dates": ["F:/private-source"]},
    {"scanned_report_dates": ["2026-13-31"]},
    {"scanned_years": ["private-operator"]},
    {"scanned_date_count": -1}, {"scanned_date_count": True}, {"scanned_date_count": 99},
])
def test_public_scope_rejects_invalid_values_without_exposing_them(override):
    scope = {**product_category_scope(), **override}
    public = routes._public_run({"steps": [{
        "key": "product_category_pnl", "status": "completed", "refresh_scope": scope,
    }]}, input_directory="F:/fixture")
    assert "refresh_scope" not in public["steps"][0]


@pytest.mark.parametrize("scope_name", ["scanned", "rebuilt", "reused", "removed"])
def test_public_scope_omits_non_ascii_years_without_losing_legacy_receipt(scope_name):
    scope = {**product_category_scope(), f"{scope_name}_years": ["٢٠٢٦"]}
    public = routes._public_run({
        "run_id": "legacy-scope", "report_date": REPORT_DATE, "status": "completed",
        "steps": [{"key": "product_category_pnl", "label": "产品损益", "status": "completed", "refresh_scope": scope}],
    }, input_directory="F:/fixture")
    assert "refresh_scope" not in public["steps"][0]
    assert public["run_id"] == "legacy-scope"
    assert public["report_date"] == REPORT_DATE
    assert public["status"] == "completed"
    assert public["steps"][0] == {"key": "product_category_pnl", "label": "产品损益", "status": "completed"}



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
