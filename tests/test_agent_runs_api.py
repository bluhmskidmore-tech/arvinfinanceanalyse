from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from tests.helpers import load_module


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        agent_enabled=True,
        agent_provider="hermes",
        agent_hermes_command="hermes",
        agent_hermes_wsl_distro="",
        agent_hermes_home="",
        agent_hermes_transport="bridge",
        agent_hermes_bridge_url="http://127.0.0.1:7891",
        agent_hermes_model="gpt-test",
        agent_hermes_toolsets="file",
        agent_hermes_max_turns=3,
        agent_hermes_timeout_seconds=9.0,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
    )


def _sample_envelope() -> AgentEnvelope:
    return AgentEnvelope(
        answer="Hermes managed answer.",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["hermes_cli"],
            filters_applied={
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "file",
            },
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_run_test",
            basis="formal",
            result_kind="agent.hermes",
            formal_use_allowed=False,
            source_version="sv_hermes_cli",
            vendor_version="vv_hermes",
            rule_version="rv_agent_hermes_v1",
            cache_version="cv_agent_hermes_v1",
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["hermes_cli"],
            filters_applied={"provider": "hermes"},
            evidence_rows=1,
        ),
    )


def _client(monkeypatch, tmp_path: Path, execute):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    settings = _settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", execute)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app), settings


def _wait_for_terminal(client: TestClient, run_id: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    for _ in range(200):
        payload = client.get(f"/api/agent/runs/{run_id}", headers=headers).json()
        status = payload.get("status")
        if status in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"agent run did not finish: {run_id}")


def _wait_for_terminal_record(settings, run_id: str) -> None:
    from backend.app.repositories.governance_repo import GovernanceRepository
    from backend.app.services.agent_run_service import AGENT_RUN_STREAM

    for _ in range(200):
        records = [
            record
            for record in GovernanceRepository(base_dir=settings.governance_path).read_all(AGENT_RUN_STREAM)
            if str(record.get("run_id") or "") == run_id
        ]
        if records and str(records[-1].get("status") or "") in {"completed", "failed"}:
            return
        time.sleep(0.05)
    raise AssertionError(f"agent run did not finish: {run_id}")


def test_agent_run_create_returns_queued_and_status_completes(monkeypatch, tmp_path):
    calls = []

    def fake_execute(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_hermes_model))
        return _sample_envelope()

    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "queued"
    assert created["run_id"].startswith("agent_run:")

    completed = _wait_for_terminal(client, created["run_id"])
    assert completed["status"] == "completed"
    assert completed["result"]["answer"] == "Hermes managed answer."
    assert completed["provider"] == "hermes"
    assert completed["model"] == "gpt-test"
    assert completed["transport"] == "bridge"
    assert calls and calls[0][2] == "gpt-test"

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records if record["run_id"] == created["run_id"]] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]


def test_agent_run_status_returns_404_for_unknown_run(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, lambda *args, **kwargs: _sample_envelope())

    response = client.get("/api/agent/runs/agent_run:nope")

    assert response.status_code == 404
    assert "Unknown agent run_id=agent_run:nope" in response.json()["detail"]


def test_agent_run_status_rejects_different_header_user(monkeypatch, tmp_path):
    def fake_execute(request, governance_dir, settings):
        return _sample_envelope()

    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post(
        "/api/agent/runs",
        json={"question": "ping"},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    _wait_for_terminal_record(settings, created["run_id"])

    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "other-user", "X-User-Role": "reviewer"},
    )
    allowed = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers=owner_headers,
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_agent_run_creation_uses_auth_context_instead_of_request_user_context(monkeypatch, tmp_path):
    def fake_execute(request, governance_dir, settings):
        return _sample_envelope()

    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post(
        "/api/agent/runs",
        json={"question": "ping", "context": {"user_id": "spoofed-user", "user_role": "admin"}},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    _wait_for_terminal_record(settings, created["run_id"])

    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "spoofed-user", "X-User-Role": "admin"},
    )
    allowed = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers=owner_headers,
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_agent_run_status_prefers_jsonl_terminal_state_over_in_memory_running_cache(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)

    service_module._remember_run_record(
        {
            "run_id": "agent_run:finished",
            "status": "running",
            "question": "ping",
            "provider": "hermes",
            "model": "gpt-test",
            "transport": "bridge",
            "toolsets": "file",
            "queued_at": "2026-05-09T01:00:00+00:00",
            "started_at": "2026-05-09T01:00:01+00:00",
        }
    )
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": "agent_run:finished",
                "status": "completed",
                "question": "ping",
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "file",
                "queued_at": "2026-05-09T01:00:00+00:00",
                "started_at": "2026-05-09T01:00:01+00:00",
                "finished_at": "2026-05-09T01:00:02+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    status = service_module.get_agent_run_status(run_id="agent_run:finished", settings=settings)

    assert status.status == "completed"
    assert status.run_id == "agent_run:finished"
    assert status.model == "gpt-test"


def test_agent_run_failure_records_error_message(monkeypatch, tmp_path):
    def fake_execute(request, governance_dir, settings):
        raise RuntimeError("Hermes bridge unavailable")

    client, _ = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    failed = _wait_for_terminal(client, created["run_id"])

    assert failed["status"] == "failed"
    assert failed["error_message"] == "Hermes bridge unavailable"
    assert "result" not in failed

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    latest = [record for record in records if record["run_id"] == created["run_id"]][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "Hermes bridge unavailable"


def test_agent_runs_accept_dexter_provider_and_persist_provider_metadata(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()

    class InlineThread:
        def __init__(self, *, target, kwargs, daemon, name):
            self._target = target
            self._kwargs = kwargs

        def start(self):
            self._target(**self._kwargs)

    monkeypatch.setattr(service_module.threading, "Thread", InlineThread)

    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    settings = SimpleNamespace(
        agent_enabled=True,
        agent_provider="dexter",
        agent_dexter_command="dexter",
        agent_dexter_transport="sidecar",
        agent_dexter_bridge_url="http://127.0.0.1:7892",
        agent_dexter_model="dexter-test",
        agent_dexter_toolsets="sql,files",
        agent_dexter_timeout_seconds=9.0,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)

    calls = []

    def fake_execute(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_dexter_model))
        sample = _sample_envelope()
        return sample.model_copy(
            update={
                "answer": "Dexter managed answer.",
                "evidence": sample.evidence.model_copy(
                    update={
                        "tables_used": ["dexter_sidecar"],
                        "filters_applied": {
                            "provider": "dexter",
                            "model": "dexter-test",
                            "transport": "sidecar",
                            "toolsets": "sql,files",
                        },
                    }
                ),
                "result_meta": sample.result_meta.model_copy(
                    update={
                        "result_kind": "agent.dexter",
                        "source_version": "sv_dexter_sidecar",
                        "vendor_version": "vv_dexter",
                        "rule_version": "rv_agent_dexter_v1",
                        "cache_version": "cv_agent_dexter_v1",
                        "tables_used": ["dexter_sidecar"],
                        "filters_applied": {"provider": "dexter"},
                    }
                ),
            }
        )

    monkeypatch.setattr(route_module, "execute_dexter_agent_query", fake_execute)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["provider"] == "dexter"
    assert created["model"] == "dexter-test"
    assert created["transport"] == "sidecar"
    assert created["toolsets"] == "sql,files"

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    matching = [record for record in records if record["run_id"] == created["run_id"]]
    assert [record["status"] for record in matching] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]
    completed = matching[-1]
    assert completed["provider"] == "dexter"
    assert completed["model"] == "dexter-test"
    assert completed["transport"] == "sidecar"
    assert completed["toolsets"] == "sql,files"
    assert completed["result"]["answer"] == "Dexter managed answer."
    assert completed["result"]["result_meta"]["result_kind"] == "agent.dexter"
    assert calls and calls[0][2] == "dexter-test"
