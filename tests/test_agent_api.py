from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.governance.settings import get_settings
from tests.helpers import load_module

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


def test_agent_query_is_not_published_without_governed_result_meta(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")
    monkeypatch.setenv("MOSS_AGENT_PROVIDER", "local")
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 404
    get_settings.cache_clear()


def _confirmation_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        agent_enabled=True,
        agent_dev_scope_bypass=True,
        agent_provider="local",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        postgres_dsn=f"sqlite:///{(tmp_path / 'agent-confirmation-scope.db').as_posix()}",
        governance_sql_dsn="",
    )


def _confirmation_envelope() -> AgentEnvelope:
    return AgentEnvelope(
        answer="Server confirmation catalog response.",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["agent_confirmation_catalog_test"],
            evidence_rows=1,
            quality_flag="warning",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_confirmation_catalog",
            basis="analytical",
            result_kind="agent.confirmation_catalog",
            formal_use_allowed=False,
            source_version="sv_test",
            vendor_version="vv_test",
            rule_version="rv_test",
            cache_version="cv_test",
            quality_flag="warning",
            scenario_flag=False,
            tables_used=["agent_confirmation_catalog_test"],
            evidence_rows=1,
        ),
    )


def _user_headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-User-Role": "analyst"}


def _confirmation_client(monkeypatch, tmp_path: Path) -> tuple[TestClient, list]:
    # 信任 X-User-Id/X-User-Role 头，便于用例区分 token 签发用户与提交用户。
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    settings = _confirmation_settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    calls: list = []

    def fake_execute_agent_query(request, duckdb_path, governance_dir):
        calls.append(request)
        return _confirmation_envelope()

    monkeypatch.setattr(route_module, "execute_agent_query", fake_execute_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app, client=("127.0.0.1", 50000)), calls


def test_confirmation_catalog_covers_all_issued_action_types() -> None:
    from backend.app.agent.runtime.action_token import (
        CONFIRMATION_REQUIRED_ACTION_TYPES,
        action_requires_server_confirmation,
    )

    # 与签发点保持同步：analysis_view_tool 与 research_radar_service。
    assert {"execute_intent", "inspect_drill", "inspect_news_events"} <= (
        CONFIRMATION_REQUIRED_ACTION_TYPES
    )
    assert action_requires_server_confirmation("execute_intent")
    assert action_requires_server_confirmation("  Execute_Intent  ")
    assert not action_requires_server_confirmation("")
    assert not action_requires_server_confirmation("open_link")


def test_server_catalog_enforces_confirmation_even_when_client_strips_flags(
    monkeypatch,
    tmp_path,
) -> None:
    """服务端目录强制：客户端剥离 requires_confirmation 声明不再绕过 token 校验。"""
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    client, calls = _confirmation_client(monkeypatch, tmp_path)
    stripped_action = {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {"intent": "portfolio_overview"},
    }

    stripped_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {"suggested_action": stripped_action},
        },
    )
    assert stripped_response.status_code == 403
    assert "confirmation token" in stripped_response.json()["detail"]
    assert calls == []

    valid_token = agent_action_confirmation_token(
        action_type=stripped_action["type"],
        label=stripped_action["label"],
        payload=stripped_action["payload"],
    )
    confirmed_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": stripped_action,
                "suggested_action_confirmation_token": valid_token,
            },
        },
    )
    assert confirmed_response.status_code == 200
    assert len(calls) == 1

    forged_token = valid_token[:-1] + ("0" if valid_token[-1] != "0" else "1")
    forged_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": stripped_action,
                "suggested_action_confirmation_token": forged_token,
            },
        },
    )
    assert forged_response.status_code == 403
    assert "confirmation token" in forged_response.json()["detail"]
    assert len(calls) == 1


def test_scope_bound_confirmation_token_passes_gate_and_rejects_scope_tamper(
    monkeypatch,
    tmp_path,
) -> None:
    """scope 内嵌 payload 后由既有 HMAC 门禁保护：原样回传通过，篡改 scope 即 403。"""
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    client, calls = _confirmation_client(monkeypatch, tmp_path)
    scoped_action = {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {
            "intent": "portfolio_overview",
            "confirmation_scope": {"user_id": "user_a", "run_id": "run_001"},
        },
    }
    token = agent_action_confirmation_token(
        action_type=scoped_action["type"],
        label=scoped_action["label"],
        payload=scoped_action["payload"],
    )

    # 提交者与签发 scope 同为 user_a（路由层用户比对生效后必须显式对齐）。
    ok_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": scoped_action,
                "suggested_action_confirmation_token": token,
            },
        },
        headers=_user_headers("user_a"),
    )
    assert ok_response.status_code == 200
    assert len(calls) == 1

    tampered_action = {
        **scoped_action,
        "payload": {
            "intent": "portfolio_overview",
            "confirmation_scope": {"user_id": "user_b", "run_id": "run_001"},
        },
    }
    tampered_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": tampered_action,
                "suggested_action_confirmation_token": token,
            },
        },
        headers=_user_headers("user_a"),
    )
    assert tampered_response.status_code == 403
    assert "confirmation token" in tampered_response.json()["detail"]
    assert len(calls) == 1


def _scoped_confirmation_action() -> dict[str, object]:
    return {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {
            "intent": "portfolio_overview",
            "confirmation_scope": {"user_id": "user_a", "run_id": "run_001"},
        },
    }


def test_confirmation_scope_matching_user_passes_route_gate(
    monkeypatch,
    tmp_path,
) -> None:
    """同用户带 scope：token 校验点比对签发用户与提交者一致后放行。"""
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    client, calls = _confirmation_client(monkeypatch, tmp_path)
    action = _scoped_confirmation_action()
    token = agent_action_confirmation_token(
        action_type=action["type"],
        label=action["label"],
        payload=action["payload"],
    )

    response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": action,
                "suggested_action_confirmation_token": token,
            },
        },
        headers=_user_headers("user_a"),
    )

    assert response.status_code == 200
    assert len(calls) == 1


def test_confirmation_scope_cross_user_replay_rejected_at_route(
    monkeypatch,
    tmp_path,
) -> None:
    """跨用户重放：token 与 payload 原样（HMAC 通过），提交者不同 → 路由层 403。"""
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    client, calls = _confirmation_client(monkeypatch, tmp_path)
    action = _scoped_confirmation_action()
    token = agent_action_confirmation_token(
        action_type=action["type"],
        label=action["label"],
        payload=action["payload"],
    )

    response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": action,
                "suggested_action_confirmation_token": token,
            },
        },
        headers=_user_headers("user_b"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Suggested action confirmation token is bound to a different user."
    )
    # 纵深防御在执行层之前拦截：不触达 service。
    assert calls == []


def test_confirmation_token_without_scope_keeps_passing(
    monkeypatch,
    tmp_path,
) -> None:
    """无 confirmation_scope 的历史 token 保持放行（向后兼容，仅收紧不放宽）。"""
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    client, calls = _confirmation_client(monkeypatch, tmp_path)
    legacy_action = {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {"intent": "portfolio_overview"},
    }
    token = agent_action_confirmation_token(
        action_type=legacy_action["type"],
        label=legacy_action["label"],
        payload=legacy_action["payload"],
    )

    response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "suggested_action": legacy_action,
                "suggested_action_confirmation_token": token,
            },
        },
        headers=_user_headers("user_b"),
    )

    assert response.status_code == 200
    assert len(calls) == 1


def test_uncataloged_action_without_client_flags_keeps_passing(
    monkeypatch,
    tmp_path,
) -> None:
    """向后兼容锁定：目录外且客户端未声明确认要求的动作不触发 token 校验。"""
    client, calls = _confirmation_client(monkeypatch, tmp_path)

    response = client.post(
        "/api/agent/query",
        json={
            "question": "查看外部链接",
            "context": {
                "suggested_action": {
                    "type": "open_link",
                    "label": "Open docs",
                    "payload": {"href": "/docs"},
                },
            },
        },
    )

    assert response.status_code == 200
    assert len(calls) == 1
