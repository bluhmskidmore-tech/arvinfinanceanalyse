from __future__ import annotations

import pytest

from backend.app.agent.runtime.local_request_resolution import ONTOLOGY_PARSER_REVISION
from backend.app.governance.agent_audit import AGENT_AUDIT_STREAM
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_service, pnl_service
from tests.test_agent_api_contract import _seed_agent_scope
from tests.test_agent_runs_api import _local_client, _wait_for_terminal


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


@pytest.mark.parametrize("endpoint", ["/api/agent/query", "/api/agent/runs"])
@pytest.mark.parametrize(
    ("question", "reason_code", "explanation"),
    [
        (
            "查询截至 2026-03-31 最近30天正式总损益",
            "unsupported_period_query",
            "期间查询",
        ),
        (
            "2026-03-31 正式总损益占比是多少",
            "unsupported_derived_operation",
            "派生计算",
        ),
        (
            "查询 2026-03-31 的正式总损益，剔除现金",
            "unsupported_query_scope",
            "剔除",
        ),
        (
            "不要查询 2026-03-31 的正式总损益",
            "negated_metric_reference",
            "否定",
        ),
    ],
)
def test_review_scope_failures_are_blocked_at_sync_and_async_entrypoints(
    monkeypatch, tmp_path, endpoint, question, reason_code, explanation
):
    reads: list[str] = []

    def forbidden_overview(**_kwargs):
        reads.append("overview")
        raise AssertionError("unsupported or negated queries must not read formal PnL")

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", forbidden_overview)
    client, settings = _local_client(
        monkeypatch, tmp_path, agent_service.execute_agent_query
    )
    _seed_agent_scope(tmp_path, monkeypatch, action="execute")
    response = client.post(
        endpoint, json={"question": question, "currency_basis": "CNY"}
    )
    assert response.status_code == 200, response.text
    envelope = response.json()
    if endpoint.endswith("/runs"):
        completed = _wait_for_terminal(client, envelope["run_id"])
        assert completed["status"] == "completed", completed
        envelope = completed["result"]

    assert envelope["semantic_context"]["reason_code"] == reason_code
    assert envelope["semantic_context"]["result_check"] == "blocked"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert all(card["type"] != "metric" for card in envelope["cards"])
    assert explanation in envelope["answer"]
    assert reads == []
    audits = GovernanceRepository(settings.governance_path).read_all(AGENT_AUDIT_STREAM)
    assert any(
        row["result_meta"].get("semantic_parser_revision") == ONTOLOGY_PARSER_REVISION
        and row["result_meta"].get("semantic_reason_code") == reason_code
        for row in audits
    )
