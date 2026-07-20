from __future__ import annotations

from tests.helpers import load_module


def _catalog_module():
    return load_module(
        "backend.app.agent.runtime.research_workflow_catalog",
        "backend/app/agent/runtime/research_workflow_catalog.py",
    )


def _tool_module():
    return load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )


def _request_module():
    return load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )


def _stub_research_handler(calls: list[str]):
    def _handler(request):
        calls.append(request.question)
        return {
            "answer": "research radar ok",
            "basis": "analytical",
            "result_kind": "agent.research_radar_brief",
            "formal_use_allowed": False,
            "source_version": "sv_research_radar_2",
            "rule_version": "rv_research_radar_v1",
            "cache_version": "cv_research_radar_v1",
            "quality_flag": "warning",
            "row_count": 2,
            "tables_used": ["choice_news_event"],
            "sql_executed": ["select event_key from choice_news_event where coalesce(error_code, 0) = 0 limit ?"],
            "cards": [{"type": "metric", "title": "事件数", "value": "2"}],
        }

    return _handler


def test_catalog_lists_research_radar_brief():
    catalog = _catalog_module()

    workflows = catalog.list_research_workflows()

    assert [workflow.workflow_id for workflow in workflows] == ["research_radar_brief"]
    assert workflows[0].category == "research"


def test_catalog_recognizes_hyphenated_research_workflow_id():
    catalog = _catalog_module()

    assert catalog.is_research_workflow_id("research-radar-brief") is True
    assert catalog.get_research_workflow("research-radar-brief").workflow_id == "research_radar_brief"


def test_catalog_versions_align_with_handler_values():
    catalog = _catalog_module()

    workflow = catalog.get_research_workflow("research_radar_brief")

    assert workflow.rule_version == "rv_research_radar_v1"
    assert workflow.cache_version == "cv_research_radar_v1"


def test_catalog_resolves_workflow_from_context_workflow_id():
    catalog = _catalog_module()

    assert (
        catalog.resolve_research_workflow("", {"workflow_id": "research-radar-brief"}).workflow_id
        == "research_radar_brief"
    )
    assert catalog.resolve_research_workflow("", {"workflow_id": "unknown"}) is None
    assert catalog.resolve_research_workflow("", {}) is None


def test_catalog_resolves_slash_command_and_keywords_from_question():
    catalog = _catalog_module()

    assert (
        catalog.resolve_research_workflow("please run /research-radar today", {}).workflow_id
        == "research_radar_brief"
    )
    assert catalog.resolve_research_workflow("研究速读", {}).workflow_id == "research_radar_brief"
    assert catalog.resolve_research_workflow("看一下研究雷达", {}).workflow_id == "research_radar_brief"
    assert catalog.resolve_research_workflow("组合概览", {}) is None


def test_research_slash_command_returns_plan_envelope_by_default(tmp_path):
    tool_module = _tool_module()
    request_module = _request_module()
    calls: list[str] = []

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"research_radar_brief": _stub_research_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="/research-radar")
    )

    assert calls == []
    assert envelope.result_meta.result_kind == "agent.workflow.research_radar_brief"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.rule_version == "rv_research_radar_v1"
    assert envelope.result_meta.cache_version == "cv_research_radar_v1"
    assert envelope.evidence.evidence_rows == 0
    assert [card.title for card in envelope.cards] == [
        "Workflow Plan",
        "Mapped MOSS Intents",
        "Governance Notes",
    ]
    assert envelope.cards[1].data == [{"order": 1, "intent": "research_radar_brief"}]
    assert envelope.suggested_actions[0].type == "execute_intent"
    assert envelope.suggested_actions[0].payload["workflow_mode"] == "execute"
    assert envelope.suggested_actions[0].confirmation_token


def test_research_keyword_returns_plan_envelope_by_default(tmp_path):
    tool_module = _tool_module()
    request_module = _request_module()
    calls: list[str] = []

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"research_radar_brief": _stub_research_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="帮我做一份研究速读")
    )

    assert calls == []
    assert envelope.result_meta.result_kind == "agent.workflow.research_radar_brief"


def test_research_workflow_execute_mode_runs_handler(tmp_path):
    tool_module = _tool_module()
    request_module = _request_module()
    calls: list[str] = []

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"research_radar_brief": _stub_research_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/research-radar",
            context={"workflow_mode": "execute"},
        )
    )

    assert calls == ["/research-radar"]
    assert envelope.result_meta.result_kind == "agent.research_radar_brief"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.tables_used == ["choice_news_event"]
    assert envelope.evidence.sql_executed
    assert all(sql.lower().startswith("select") for sql in envelope.evidence.sql_executed)


def test_explicit_research_intent_context_keeps_direct_execution(tmp_path):
    tool_module = _tool_module()
    request_module = _request_module()
    calls: list[str] = []

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"research_radar_brief": _stub_research_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="研究速读",
            basis="analytical",
            context={
                "intent": "research_radar_brief",
                "workflow_id": "research_radar_brief",
            },
        )
    )

    assert calls == ["研究速读"]
    assert envelope.result_meta.result_kind == "agent.research_radar_brief"
    assert envelope.result_meta.formal_use_allowed is False
