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


def _wait_for_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    for _ in range(40):
        payload = client.get(f"/api/agent/runs/{run_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.025)
    raise AssertionError(f"agent run did not finish: {run_id}")


def test_agent_run_create_returns_queued_and_status_completes(monkeypatch, tmp_path):
    calls = []

    def fake_execute(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_hermes_model))
        return _sample_envelope()

    client, _ = _client(monkeypatch, tmp_path, fake_execute)

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
