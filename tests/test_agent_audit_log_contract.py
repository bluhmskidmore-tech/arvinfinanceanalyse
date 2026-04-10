from backend.app.governance.agent_audit import (
    AGENT_AUDIT_STREAM,
    AgentAuditPayload,
    append_agent_audit,
)
from backend.app.repositories.governance_repo import GovernanceRepository


def test_agent_audit_stream_name_is_stable():
    assert AGENT_AUDIT_STREAM == "agent_audit"


def test_agent_audit_append_uses_existing_append_only_repository(tmp_path):
    repo = GovernanceRepository(base_dir=tmp_path)
    payload = AgentAuditPayload(
        user_id="u_demo",
        query_text="查询月均市值",
        tools_used=["analysis_view_tool"],
        tables_used=[],
        filters_applied={"month": "2026-03"},
        trace_id="tr_agent_phase1",
        result_meta={"basis": "formal"},
    )

    target = append_agent_audit(repo, payload)

    assert target.endswith("agent_audit.jsonl")
    content = (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")
    assert "查询月均市值" in content
    assert "analysis_view_tool" in content
