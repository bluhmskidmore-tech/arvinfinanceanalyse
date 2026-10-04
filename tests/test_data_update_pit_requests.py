"""Exact PIT recovery requests; synthetic DBs and isolated governance only."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import data_updates as routes
from backend.app.repositories import data_update_repo as repo
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services import data_update_service as service
from backend.app.tasks import choice_stock_pit_import as importer
from tests.test_choice_stock_pit_import import AS_OF_DATE, _build_fixture, _sha256

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]


@pytest.fixture
def pit_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    source, target = _build_fixture(tmp_path)
    (tmp_path / "input").mkdir()
    backup = tmp_path / "target-backup.duckdb"
    shutil.copyfile(target, backup)
    settings = SimpleNamespace(
        duckdb_path=target, governance_path=tmp_path / "governance",
        data_input_root=tmp_path / "input",
    )
    scheduler = Mock()
    monkeypatch.setattr(service, "require_scheduler", scheduler)
    preflight = service.choice_stock_pit_preflight(
        settings, report_date=AS_OF_DATE, source_duckdb_path=str(source),
        expected_source_sha256=_sha256(source),
    )
    return SimpleNamespace(settings=settings, source=source, target=target, backup=backup,
        scheduler=scheduler, preflight=preflight, parameters={
            "report_date": AS_OF_DATE, "source_duckdb_path": str(source),
            "expected_source_sha256": _sha256(source),
            "expected_plan_sha256": preflight["plan_sha256"], "target_backup_path": str(backup),
        })


def _request(case: SimpleNamespace, **overrides: str) -> dict[str, object]:
    return service.request_choice_stock_pit_update(
        case.settings, **{**case.parameters, **overrides},
        requested_by="operator", idempotency_key="pit-request",
    )


def _client(case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="operator", role="operator")
    monkeypatch.setattr(routes, "get_settings", lambda: case.settings)
    monkeypatch.setattr(routes, "_ensure_data_health_read_allowed", lambda _: None)
    permissions = Mock()
    monkeypatch.setattr(routes, "ensure_user_allowed", permissions)
    return TestClient(app), permissions


def test_pit_preflight_is_real_read_only_and_cleans_temporary_receipt(pit_case, monkeypatch):
    target_before = _sha256(pit_case.target)
    source_before = _sha256(pit_case.source)
    original = importer.import_choice_stock_pit_snapshot
    receipts = []

    def tracked_import(*args, **kwargs):
        assert kwargs["apply_changes"] is False
        receipts.append(Path(kwargs["receipt_path"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(importer, "import_choice_stock_pit_snapshot", tracked_import)
    result = service.choice_stock_pit_preflight(
        pit_case.settings, report_date=AS_OF_DATE, source_duckdb_path=str(pit_case.source),
        expected_source_sha256=source_before,
    )
    assert result["ready"] is True and result["duckdb_written"] is False
    assert result["insert_counts"] == {
        "choice_stock_universe": 2, "choice_stock_sector_membership": 2,
        "choice_stock_limit_quality": 2,
    }
    assert result["audit_insert_count"] == 3
    assert "audits" not in result and "rows_by_table" not in result
    assert _sha256(pit_case.target) == target_before and _sha256(pit_case.source) == source_before
    assert receipts and all(not path.exists() and not path.parent.exists() for path in receipts)
    assert repo.latest_runs(pit_case.settings.governance_path) == []


def test_pit_request_persists_exact_plan_without_business_writes(pit_case):
    target_before = _sha256(pit_case.target)
    run = _request(pit_case)
    assert run["workflow"] == "choice_stock_pit_history" and run["status"] == "queued"
    assert run["requested_by"] == "operator" and run["idempotency_key"] == "pit-request"
    assert run["target_duckdb_path"] == str(pit_case.target.resolve())
    assert all(run[key] == value for key, value in pit_case.parameters.items())
    assert run["preflight"]["plan_sha256"] == pit_case.parameters["expected_plan_sha256"]
    assert "受控维护主机" in run["message"]
    assert _sha256(pit_case.target) == target_before
    assert repo.latest_runs(pit_case.settings.governance_path) == [run]
    pit_case.scheduler.assert_called_once_with(service.QUEUE_TASK_NAME)


def test_pit_request_reuses_same_idempotency_and_same_active_date(pit_case):
    run = _request(pit_case)
    assert _request(pit_case) == run
    assert service.request_choice_stock_pit_update(
        pit_case.settings, **pit_case.parameters, requested_by="operator", idempotency_key="another-key",
    ) == run
    assert len(repo.latest_runs(pit_case.settings.governance_path)) == 1


@pytest.mark.parametrize("key", ["report_date", "source_duckdb_path", "expected_source_sha256", "expected_plan_sha256", "target_backup_path"])
def test_pit_idempotency_binds_every_recovery_parameter(pit_case, key):
    _request(pit_case)
    changed = {
        "report_date": "2026-09-03", "source_duckdb_path": str(pit_case.source.parent / "other-source.duckdb"),
        "expected_source_sha256": "b" * 64, "expected_plan_sha256": "c" * 64,
        "target_backup_path": str(pit_case.backup.parent / "other-backup.duckdb"),
    }
    with pytest.raises(ValueError, match="同一请求编号"):
        _request(pit_case, **{key: changed[key]})
    assert len(repo.latest_runs(pit_case.settings.governance_path)) == 1


def test_pit_same_date_different_active_recovery_is_rejected(pit_case):
    _request(pit_case)
    parameters = {**pit_case.parameters, "expected_plan_sha256": "b" * 64}
    with pytest.raises(ValueError, match="同一报告日"):
        service.request_choice_stock_pit_update(
            pit_case.settings, **parameters, requested_by="operator", idempotency_key="other-key",
        )


def test_pit_request_binds_target_and_does_not_reuse_financial_idempotency(pit_case):
    run = _request(pit_case)
    original_target = pit_case.settings.duckdb_path
    pit_case.settings.duckdb_path = original_target.parent / "other-target.duckdb"
    with pytest.raises(ValueError, match="同一请求编号"):
        _request(pit_case)
    pit_case.settings.duckdb_path = original_target
    repo.save_run(pit_case.settings.governance_path, {**run, "workflow": "core_financial"})
    with pytest.raises(ValueError, match="同一请求编号"):
        _request(pit_case)


def test_pit_request_rejects_changed_source_and_changed_reviewed_plan(pit_case):
    with pytest.raises(ValueError, match="计划已变化"):
        _request(pit_case, expected_plan_sha256="b" * 64)
    pit_case.source.write_bytes(pit_case.source.read_bytes() + b"changed")
    with pytest.raises(RuntimeError, match="预检未通过"):
        _request(pit_case)
    assert repo.latest_runs(pit_case.settings.governance_path) == []


@pytest.mark.parametrize("source,backup", [("relative.duckdb", "valid"), ("valid", "relative.duckdb"), ("target", "valid"), ("valid", "target"), ("valid", "source")])
def test_pit_request_rejects_relative_or_overlapping_paths(pit_case, source, backup):
    values = {"valid": None, "target": str(pit_case.target), "source": str(pit_case.source)}
    overrides = {}
    if source != "valid":
        overrides["source_duckdb_path"] = values.get(source, source)
    if backup != "valid":
        overrides["target_backup_path"] = values.get(backup, backup)
    with pytest.raises(ValueError):
        _request(pit_case, **overrides)
    assert repo.latest_runs(pit_case.settings.governance_path) == []


def test_pit_request_refuses_missing_backup_and_disabled_scheduler(pit_case, monkeypatch):
    pit_case.backup.unlink()
    with pytest.raises(ValueError, match="备份文件不存在"):
        _request(pit_case)
    monkeypatch.setattr(service, "require_scheduler", Mock(side_effect=RuntimeError("disabled")))
    with pytest.raises(RuntimeError, match="disabled"):
        _request(pit_case)
    assert repo.latest_runs(pit_case.settings.governance_path) == []


def test_pit_api_preflight_request_and_cancel_require_market_permissions(pit_case, monkeypatch):
    client, permissions = _client(pit_case, monkeypatch)
    body = pit_case.parameters
    with client:
        preflight = client.post("/api/data-updates/choice-stock-pit/preflight", json={key: body[key] for key in ("report_date", "source_duckdb_path", "expected_source_sha256")})
        assert preflight.status_code == 200
        public_preflight = preflight.json()
        assert public_preflight["source_sha256"] == body["expected_source_sha256"]
        assert public_preflight["plan_sha256"] == body["expected_plan_sha256"]
        assert public_preflight["insert_counts"] == pit_case.preflight["insert_counts"]
        assert "source_duckdb_path" not in public_preflight
        assert "target_duckdb_path" not in public_preflight
        expected = set(routes.MARKET_PERMISSIONS)
        assert {(call.kwargs["resource"], call.kwargs["action"]) for call in permissions.call_args_list} == expected
        permissions.reset_mock()
        accepted = client.post("/api/data-updates/choice-stock-pit", json=body, headers={"Idempotency-Key": "api-pit"})
        assert accepted.status_code == 202
        for private_field in ("requested_by", "idempotency_key", "target_duckdb_path", "source_duckdb_path", "target_backup_path"):
            assert private_field not in accepted.json()
        assert accepted.json()["preflight"]["plan_sha256"] == body["expected_plan_sha256"]
        assert {(call.kwargs["resource"], call.kwargs["action"]) for call in permissions.call_args_list} == expected
        run_id = accepted.json()["run_id"]
        permissions.reset_mock()
        def financial_only(**kwargs):
            if kwargs["resource"] not in routes.CORE_RESOURCES:
                raise PermissionError("synthetic private authorization detail")

        permissions.side_effect = financial_only
        denied = client.post(f"/api/data-updates/runs/{run_id}/cancel")
        assert denied.status_code == 403 and "synthetic private" not in denied.text
        assert permissions.call_args.kwargs["resource"] == routes.MARKET_PERMISSIONS[0][0]
        assert repo.latest_runs(pit_case.settings.governance_path)[0]["status"] == "queued"
        permissions.side_effect = None
        permissions.reset_mock()
        assert client.post(f"/api/data-updates/runs/{run_id}/cancel").status_code == 200
        assert {(call.kwargs["resource"], call.kwargs["action"]) for call in permissions.call_args_list} == expected


@pytest.mark.parametrize("url", ["/api/data-updates/choice-stock-pit", "/api/data-updates/choice-stock-pit/preflight"])
def test_pit_api_denies_financial_only_operator_before_source_read(pit_case, monkeypatch, url):
    client, permissions = _client(pit_case, monkeypatch)

    def financial_only(**kwargs):
        if kwargs["resource"] not in routes.CORE_RESOURCES:
            raise PermissionError("denied")

    permissions.side_effect = financial_only
    preview = Mock()
    monkeypatch.setattr(service, "choice_stock_pit_preflight", preview)
    body = pit_case.parameters if not url.endswith("preflight") else {key: pit_case.parameters[key] for key in ("report_date", "source_duckdb_path", "expected_source_sha256")}
    with client:
        assert client.post(url, json=body, headers={"Idempotency-Key": "denied"}).status_code == 403
    preview.assert_not_called()
    assert repo.latest_runs(pit_case.settings.governance_path) == []


@pytest.mark.parametrize("field,value", [("command", "anything"), ("target_duckdb_path", "other"), ("expected_source_sha256", "not-a-hash"), ("expected_plan_sha256", "A" * 64), ("source_duckdb_path", " "), ("target_backup_path", ""), ("report_date", "not-a-date")])
def test_pit_api_strict_body_rejects_arbitrary_command_target_and_invalid_fields(pit_case, monkeypatch, field, value):
    client, _ = _client(pit_case, monkeypatch)
    with client:
        response = client.post("/api/data-updates/choice-stock-pit", json={**pit_case.parameters, field: value}, headers={"Idempotency-Key": "invalid"})
    assert response.status_code == 422
    assert repo.latest_runs(pit_case.settings.governance_path) == []


def test_pit_api_private_preflight_failure_is_not_returned(pit_case, monkeypatch):
    client, _ = _client(pit_case, monkeypatch)
    preview = Mock(side_effect=RuntimeError("synthetic-private-provider-token"))
    monkeypatch.setattr(service, "choice_stock_pit_preflight", preview)
    body = {key: pit_case.parameters[key] for key in ("report_date", "source_duckdb_path", "expected_source_sha256")}
    with client:
        response = client.post("/api/data-updates/choice-stock-pit/preflight", json=body)
    assert response.status_code == 409
    assert "synthetic-private" not in response.text
    assert repo.latest_runs(pit_case.settings.governance_path) == []


def test_pit_preflight_rejects_hard_link_to_target_before_importer(pit_case, monkeypatch):
    alias = pit_case.target.parent / "target-alias.duckdb"
    os.link(pit_case.target, alias)
    preview = Mock(side_effect=AssertionError("importer must not see target alias"))
    monkeypatch.setattr(importer, "import_choice_stock_pit_snapshot", preview)
    with pytest.raises(ValueError, match="来源与目标数据库必须不同"):
        service.choice_stock_pit_preflight(
            pit_case.settings, report_date=AS_OF_DATE,
            source_duckdb_path=str(alias), expected_source_sha256=_sha256(alias),
        )
    preview.assert_not_called()


@pytest.mark.parametrize("linked_file", ["target", "source"])
def test_pit_request_rejects_hard_link_backup_without_queueing(pit_case, linked_file):
    alias = pit_case.target.parent / "backup-alias.duckdb"
    os.link(getattr(pit_case, linked_file), alias)
    with pytest.raises(ValueError, match="来源、目标与备份必须是不同文件"):
        _request(pit_case, target_backup_path=str(alias))
    assert repo.latest_runs(pit_case.settings.governance_path) == []
