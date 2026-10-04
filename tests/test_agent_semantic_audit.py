from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.agent.runtime import local_request_resolution
from backend.app.agent.runtime.local_request_resolution import (
    SEMANTIC_EXECUTION_CONTEXT_KEY,
    pin_semantic_execution_request,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.agent_audit import AGENT_AUDIT_STREAM
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


def _pinned_request(*, definition: bool = False) -> AgentQueryRequest:
    request, _resolution = pin_semantic_execution_request(
        AgentQueryRequest(
            question=(
                "解释 MTR-PNL-005 的定义"
                if definition
                else "查询 2026-03-31 正式总损益"
            ),
            currency_basis="CNY",
            context={"user_id": "audit-user", "private_note": "private-context-marker"},
        )
    )
    return request


def _last_audit(tmp_path):
    return GovernanceRepository(base_dir=tmp_path).read_all(AGENT_AUDIT_STREAM)[-1]


def _raise_execution_error(_self, _request):
    raise RuntimeError("private-error-marker")


def _expected_semantic_fields(snapshot):
    return {
        "semantic_operation": snapshot["operation"],
        "semantic_metric_id": snapshot["metric_id"],
        "semantic_intent": snapshot["intent"],
        "semantic_reason": snapshot["reason"],
        "semantic_reason_code": snapshot["reason_code"],
        "semantic_required_resources": snapshot["required_resources"],
        "semantic_request_scope": snapshot["request_scope"],
        "semantic_ontology_revision": snapshot["ontology_revision"],
        "semantic_binding_revision": snapshot["binding_revision"],
        "semantic_parser_revision": snapshot["parser_revision"],
    }


@pytest.mark.parametrize("failed", [False, True], ids=["success", "exception"])
def test_sync_query_persists_validated_semantic_execution_fields(
    tmp_path, monkeypatch, failed
):
    request = _pinned_request(definition=not failed)
    if failed:
        monkeypatch.setattr(
            agent_service.ToolRegistry, "execute_query", _raise_execution_error
        )
        with pytest.raises(RuntimeError, match="private-error-marker"):
            agent_service.execute_agent_query(request, "unused.duckdb", str(tmp_path))
    else:
        envelope = agent_service.execute_agent_query(
            request, "unused.duckdb", str(tmp_path)
        )
        assert envelope.semantic_context.result_check == "not_applicable"

    audit = _last_audit(tmp_path)
    expected = _expected_semantic_fields(request.context[SEMANTIC_EXECUTION_CONTEXT_KEY])
    assert {key: audit["result_meta"].get(key) for key in expected} == expected
    assert audit["result_meta"].get("semantic_execution_validation") != "invalid"
    serialized = (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")
    assert "private-context-marker" not in serialized
    assert "private-error-marker" not in serialized
    assert SEMANTIC_EXECUTION_CONTEXT_KEY not in serialized


@pytest.mark.parametrize("failed", [False, True], ids=["success", "exception"])
def test_legacy_query_audit_has_no_semantic_execution_fields(
    tmp_path, monkeypatch, failed
):
    request = AgentQueryRequest(
        question="请说明可以提供哪些分析", context={"intent": "analysis_chat"}
    )
    if failed:
        monkeypatch.setattr(
            agent_service.ToolRegistry, "execute_query", _raise_execution_error
        )
        with pytest.raises(RuntimeError, match="private-error-marker"):
            agent_service.execute_agent_query(request, "unused.duckdb", str(tmp_path))
    else:
        agent_service.execute_agent_query(request, "unused.duckdb", str(tmp_path))

    audit = _last_audit(tmp_path)
    assert not any(key.startswith("semantic_") for key in audit["result_meta"])


@pytest.mark.parametrize("corruption", ["malformed", "stale", "scope_drift"])
def test_invalid_semantic_snapshot_audit_does_not_claim_trusted_execution(
    tmp_path, corruption
):
    request = _pinned_request()
    context = deepcopy(request.context)
    snapshot = context[SEMANTIC_EXECUTION_CONTEXT_KEY]
    if corruption == "malformed":
        snapshot.pop("required_resources")
    elif corruption == "stale":
        snapshot["parser_revision"] += "-untrusted"
    else:
        request = request.model_copy(update={"currency_basis": "USD"})
    request = request.model_copy(update={"context": context})

    with pytest.raises((TypeError, ValueError)):
        agent_service.execute_agent_query(request, "unused.duckdb", str(tmp_path))

    audit = _last_audit(tmp_path)
    assert audit["result_meta"]["semantic_execution_validation"] == "invalid"
    assert not (
        set(_expected_semantic_fields(_pinned_request().context[SEMANTIC_EXECUTION_CONTEXT_KEY]))
        & set(audit["result_meta"])
    )
    assert "-untrusted" not in (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("failed", [False, True], ids=["success", "exception"])
def test_ontology_read_error_during_audit_does_not_replace_query_outcome(
    tmp_path, monkeypatch, failed
):
    request = _pinned_request(definition=True)
    original_execute = agent_service.ToolRegistry.execute_query

    def unavailable_revision():
        raise OSError("private-ontology-path-marker")

    def execute_then_lose_ontology(registry, query):
        if not failed:
            envelope = original_execute(registry, query)
        monkeypatch.setattr(
            local_request_resolution, "ontology_content_revision", unavailable_revision
        )
        if failed:
            raise RuntimeError("original-query-error")
        return envelope

    monkeypatch.setattr(
        agent_service.ToolRegistry, "execute_query", execute_then_lose_ontology
    )
    if failed:
        with pytest.raises(RuntimeError, match="^original-query-error$"):
            agent_service.execute_agent_query(request, "unused.duckdb", str(tmp_path))
    else:
        envelope = agent_service.execute_agent_query(
            request, "unused.duckdb", str(tmp_path)
        )
        assert envelope.semantic_context.result_check == "not_applicable"

    audit = _last_audit(tmp_path)
    assert audit["result_meta"]["semantic_execution_validation"] == "invalid"
    assert "semantic_parser_revision" not in audit["result_meta"]
    serialized = (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")
    assert "private-ontology-path-marker" not in serialized
    assert "original-query-error" not in serialized
