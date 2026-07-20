from backend.app.governance.agent_audit import (
    AGENT_AUDIT_STREAM,
    AgentAuditPayload,
    append_agent_audit,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.services.agent_service import _append_audit, _envelope_tools_used


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
        run_id="agent_run:audit-contract",
        result_meta={"basis": "formal"},
    )

    target = append_agent_audit(repo, payload)

    assert target.endswith("agent_audit.jsonl")
    content = (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")
    assert "查询月均市值" in content
    assert "analysis_view_tool" in content
    assert '"run_id": "agent_run:audit-contract"' in content


def test_local_agent_audit_carries_managed_run_id(tmp_path):
    _append_audit(
        request=AgentQueryRequest(
            question="组合概览",
            context={"user_id": "u_demo", "run_id": "agent_run:local-audit"},
        ),
        governance_dir=str(tmp_path),
        trace_id="tr_agent_local_audit",
        tools_used=["analysis_view_tool"],
        tables_used=[],
        filters_applied={},
        result_meta={"basis": "formal"},
    )

    payload = GovernanceRepository(base_dir=tmp_path).read_all(AGENT_AUDIT_STREAM)[-1]
    assert payload["run_id"] == "agent_run:local-audit"


def _envelope_with_result_kind(result_kind: str) -> AgentEnvelope:
    return AgentEnvelope(
        answer="ok",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["fact_formal_bond_analytics_daily"],
            filters_applied={"report_date": "2026-03-31"},
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_tools_used",
            basis="formal",
            result_kind=result_kind,
            formal_use_allowed=True,
            source_version="sv_agent_test",
            vendor_version="vv_none",
            rule_version="rv_agent_mvp_v1",
            cache_version="cv_agent_test_v1",
            quality_flag="ok",
            scenario_flag=False,
        ),
    )


def test_local_audit_tools_used_records_resolved_intent():
    envelope = _envelope_with_result_kind("agent.duration_risk")

    assert _envelope_tools_used(envelope) == [
        "analysis_view_tool",
        "evidence_tool",
        "intent:duration_risk",
    ]


def test_local_audit_tools_used_records_workflow_and_unknown_kinds():
    assert _envelope_tools_used(_envelope_with_result_kind("agent.workflow.risk_memo")) == [
        "analysis_view_tool",
        "evidence_tool",
        "intent:workflow.risk_memo",
    ]
    # result_kind 为空时保持旧形态，追加式 JSONL 向后兼容。
    assert _envelope_tools_used(_envelope_with_result_kind("")) == [
        "analysis_view_tool",
        "evidence_tool",
    ]
