from __future__ import annotations

import pytest

from backend.app.agent.runtime.pi_jev_pilot import run_pi_jev_pilot
from backend.app.agent.schemas.agent_request import AgentQueryRequest


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def test_minimal_pi_jev_pilot_runs_real_local_moss_definition(tmp_path):
    result = run_pi_jev_pilot(
        AgentQueryRequest(question="正式总损益是什么"),
        duckdb_path=tmp_path / "pilot.duckdb",
        governance_dir=tmp_path / "governance",
    )

    assert result.decision.route == "ontology_definition"
    assert result.decision.allowed is True
    assert result.decision.ontology_revision
    assert result.decision.binding_revision == "ontology-pnl-bindings-v1"
    assert result.trace.runtime == "pi_local_pilot"
    assert result.trace.turns_used == 1
    assert result.trace.tool_calls == 1
    assert result.trace.stop_reason == "moss_envelope_returned"
    assert result.envelope is not None
    assert result.envelope.result_meta.result_kind == "agent.ontology_definition"
    assert result.envelope.result_meta.formal_use_allowed is False
    assert result.envelope.semantic_context is not None
    assert result.envelope.semantic_context.status == "resolved"
    assert result.envelope.semantic_context.result_check == "not_applicable"


def test_minimal_pi_jev_pilot_blocks_ambiguous_question_before_tool_call(tmp_path):
    calls = 0

    def unexpected_moss_call(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("blocked Jev decision must not call MOSS tools")

    result = run_pi_jev_pilot(
        AgentQueryRequest(question="收益是多少"),
        duckdb_path=tmp_path / "pilot.duckdb",
        governance_dir=tmp_path / "governance",
        execute_moss=unexpected_moss_call,
    )

    assert result.decision.allowed is False
    assert result.decision.route == "blocked"
    assert result.decision.reason_code == "multiple_metric_candidates"
    assert result.trace.tool_calls == 0
    assert result.trace.stop_reason == "semantic_blocked"
    assert result.envelope is None
    assert calls == 0


def test_minimal_pi_jev_pilot_keeps_numeric_scope_closed(tmp_path):
    result = run_pi_jev_pilot(
        AgentQueryRequest(
            question="2026-03-31 的利息收入（514）是多少",
            currency_basis="CNY",
        ),
        duckdb_path=tmp_path / "pilot.duckdb",
        governance_dir=tmp_path / "governance",
        execute_moss=lambda **_kwargs: pytest.fail(
            "numeric financial execution is outside the first pilot slice"
        ),
    )

    assert result.decision.allowed is False
    assert result.decision.reason_code == "pilot_scope_only_ontology_definition"
    assert result.trace.stop_reason == "pilot_scope_blocked"
    assert result.envelope is None
