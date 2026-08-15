from __future__ import annotations

from tests.helpers import load_module

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _catalog_module():
    return load_module(
        "backend.app.agent.runtime.financial_workflow_catalog",
        "backend/app/agent/runtime/financial_workflow_catalog.py",
    )


def test_catalog_lists_four_reference_workflows():
    catalog = _catalog_module()

    workflows = catalog.list_financial_workflows()

    assert [workflow.workflow_id for workflow in workflows] == [
        "portfolio_review",
        "pnl_review",
        "risk_memo",
        "market_brief",
    ]
    assert all(
        workflow.source == "anthropic_financial_services_reference"
        for workflow in workflows
    )


def test_catalog_gets_workflow_by_id():
    catalog = _catalog_module()

    workflow = catalog.get_financial_workflow("risk_memo")

    assert workflow is not None
    assert workflow.workflow_id == "risk_memo"
    assert workflow.mapped_intents == [
        "duration_risk",
        "credit_exposure",
        "risk_tensor",
    ]


def test_catalog_gets_workflow_by_hyphenated_id():
    catalog = _catalog_module()

    workflow = catalog.get_financial_workflow("market-brief")

    assert workflow is not None
    assert workflow.workflow_id == "market_brief"


def test_catalog_identifies_only_registered_financial_workflow_ids():
    catalog = _catalog_module()

    assert catalog.is_financial_workflow_id("portfolio-review") is True
    assert catalog.is_financial_workflow_id("market_brief") is True
    assert catalog.is_financial_workflow_id("research_radar_brief") is False
    assert catalog.is_financial_workflow_id("unknown") is False


def test_catalog_resolves_slash_commands_from_question():
    catalog = _catalog_module()

    workflow = catalog.resolve_financial_workflow(
        question="Please prepare /pnl-review for the latest close.",
        context={},
    )

    assert workflow is not None
    assert workflow.workflow_id == "pnl_review"
    assert workflow.mapped_intents == ["pnl_summary", "pnl_bridge", "product_pnl"]


def test_catalog_resolves_all_supported_slash_commands():
    catalog = _catalog_module()

    assert {
        command: catalog.resolve_financial_workflow(
            question=f"please run {command}",
            context={},
        ).workflow_id
        for command in (
            "/portfolio-review",
            "/pnl-review",
            "/risk-memo",
            "/market-brief",
        )
    } == {
        "/portfolio-review": "portfolio_review",
        "/pnl-review": "pnl_review",
        "/risk-memo": "risk_memo",
        "/market-brief": "market_brief",
    }


def test_unknown_workflow_returns_none():
    catalog = _catalog_module()

    assert catalog.get_financial_workflow("unknown") is None
    assert (
        catalog.resolve_financial_workflow(
            question="/unknown-workflow",
            context={"workflow_id": "unknown"},
        )
        is None
    )


# —— envelope 形状用例：确保切片验证命令能直接覆盖 plan/execute 契约 ——

# 与目录条目一致的 (workflow_id, slash 命令, mapped_intents)；目录调整后必须同步。
_WORKFLOW_CASES = [
    (
        "portfolio_review",
        "/portfolio-review",
        ["portfolio_overview", "duration_risk", "credit_exposure"],
    ),
    ("pnl_review", "/pnl-review", ["pnl_summary", "pnl_bridge", "product_pnl"]),
    ("risk_memo", "/risk-memo", ["duration_risk", "credit_exposure", "risk_tensor"]),
    ("market_brief", "/market-brief", ["market_data", "news"]),
]


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


def _stub_intent_handler(intent: str, calls: list[str]):
    def _handler(request):
        calls.append(intent)
        return {
            "answer": f"{intent} result",
            "basis": "formal",
            "result_kind": f"agent.{intent}",
            "formal_use_allowed": True,
            "source_version": f"sv_{intent}",
            "quality_flag": "ok",
            "row_count": 2,
            "tables_used": [f"fact_{intent}"],
            "cards": [{"type": "metric", "title": intent, "value": "2"}],
        }

    return _handler


def _build_tool(tmp_path, mapped_intents: list[str], calls: list[str]):
    return _tool_module().AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            intent: _stub_intent_handler(intent, calls) for intent in mapped_intents
        },
    )


@pytest.mark.parametrize(("workflow_id", "slash_command", "mapped_intents"), _WORKFLOW_CASES)
def test_plan_envelope_shape_for_each_financial_workflow(
    tmp_path, workflow_id, slash_command, mapped_intents
):
    request_module = _request_module()
    calls: list[str] = []
    tool = _build_tool(tmp_path, mapped_intents, calls)

    envelope = tool.execute(request_module.AgentQueryRequest(question=slash_command))

    assert calls == []
    assert envelope.result_meta.result_kind == f"agent.workflow.{workflow_id}"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.source_version == "sv_anthropic_financial_workflow_reference"
    assert envelope.result_meta.rule_version == "rv_agent_financial_workflow_catalog_v1"
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.quality_flag == "warning"
    assert [card.title for card in envelope.cards] == [
        "Workflow Plan",
        "Mapped MOSS Intents",
        "Governance Notes",
    ]
    assert envelope.cards[1].data == [
        {"order": index, "intent": intent}
        for index, intent in enumerate(mapped_intents, start=1)
    ]
    action = envelope.suggested_actions[0]
    assert action.type == "execute_intent"
    assert action.requires_confirmation is True
    assert action.confirmation_token
    assert action.payload["intent"] == mapped_intents[0]
    # payload 契约：不携带 workflow_id，回传 context 后不会再次命中 workflow 解析。
    assert "workflow_id" not in action.payload
    assert "workflow_mode" not in action.payload


@pytest.mark.parametrize(("workflow_id", "slash_command", "mapped_intents"), _WORKFLOW_CASES)
def test_execute_envelope_shape_for_each_financial_workflow(
    tmp_path, workflow_id, slash_command, mapped_intents
):
    request_module = _request_module()
    calls: list[str] = []
    tool = _build_tool(tmp_path, mapped_intents, calls)

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question=slash_command,
            context={"workflow_mode": "execute"},
        )
    )

    assert calls == mapped_intents
    assert envelope.result_meta.result_kind == f"agent.workflow.{workflow_id}"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "ok"
    assert envelope.evidence.evidence_rows == 2 * len(mapped_intents)
    assert envelope.evidence.tables_used == [f"fact_{intent}" for intent in mapped_intents]
    assert [card.title for card in envelope.cards] == [
        "Workflow Memo",
        "Workflow Execution Steps",
        "Mapped Intent Results",
        "Governance Notes",
    ]
    assert envelope.suggested_actions == []


def test_plan_action_payload_echoed_into_context_executes_first_intent(tmp_path):
    """回归：payload 回传 context 后应直接执行第一个 mapped intent，而非再次返回 plan 卡。"""
    request_module = _request_module()
    calls: list[str] = []
    tool = _build_tool(
        tmp_path,
        ["portfolio_overview", "duration_risk", "credit_exposure"],
        calls,
    )

    plan = tool.execute(request_module.AgentQueryRequest(question="/portfolio-review"))
    payload = dict(plan.suggested_actions[0].payload)

    follow_up = tool.execute(
        request_module.AgentQueryRequest(
            question="Execute suggested action",
            context=payload,
        )
    )

    assert calls == ["portfolio_overview"]
    assert follow_up.result_meta.result_kind == "agent.portfolio_overview"


def test_plan_action_payload_with_same_slash_question_executes_intent_not_plan(tmp_path):
    """回归（B15-9）：调用方 merge payload 回传且沿用原 slash 问题时，
    显式 context.intent 必须优先于问题级工作流解析，避免再次命中 plan 卡形成回环。"""
    request_module = _request_module()
    calls: list[str] = []
    tool = _build_tool(
        tmp_path,
        ["portfolio_overview", "duration_risk", "credit_exposure"],
        calls,
    )

    plan = tool.execute(request_module.AgentQueryRequest(question="/portfolio-review"))
    payload = dict(plan.suggested_actions[0].payload)
    assert payload["intent"] == "portfolio_overview"

    follow_up = tool.execute(
        request_module.AgentQueryRequest(
            question="/portfolio-review",
            context=payload,
        )
    )

    assert calls == ["portfolio_overview"]
    assert follow_up.result_meta.result_kind == "agent.portfolio_overview"
    assert all(card.title != "Workflow Plan" for card in follow_up.cards)


def test_invalid_workflow_mode_returns_error_envelope(tmp_path):
    """回归（B15-8）：workflow_mode 只接受 plan/execute（或缺省）；
    其他值不得静默按 plan 处理，必须返回错误 envelope 且不执行任何 intent。"""
    request_module = _request_module()
    calls: list[str] = []
    tool = _build_tool(
        tmp_path,
        ["duration_risk", "credit_exposure", "risk_tensor"],
        calls,
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/risk-memo",
            context={"workflow_mode": "run"},
        )
    )

    assert calls == []
    assert envelope.result_meta.result_kind == "agent.workflow.risk_memo"
    assert envelope.result_meta.quality_flag == "error"
    assert "workflow_mode" in envelope.answer
    assert "'run'" in envelope.answer
    assert "plan" in envelope.answer
    assert "execute" in envelope.answer


def test_execute_mode_all_intents_failed_upgrades_quality_to_error(tmp_path):
    """回归（B15-10）：全部 mapped intents 失败（异常 + 未注册）时，
    整体与步骤 quality_flag 升为 error，answer 明示失败而非 'with warnings'。"""
    tool_module = _tool_module()
    request_module = _request_module()

    def failing_handler(request):
        raise ValueError("no governed market data available")

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        # market_data 抛异常；news 未注册 → missing。
        intent_handlers={"market_data": failing_handler},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/market-brief",
            context={"workflow_mode": "execute"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.workflow.market_brief"
    assert envelope.result_meta.quality_flag == "error"
    assert envelope.evidence.quality_flag == "error"
    steps_card = next(card for card in envelope.cards if card.title == "Workflow Execution Steps")
    assert [row["status"] for row in steps_card.data] == ["error", "missing"]
    assert all(row["quality_flag"] == "error" for row in steps_card.data)
    assert envelope.answer.startswith("Failed to execute financial workflow")
    assert "market_data" in envelope.answer
    assert "news" in envelope.answer


def _dated_intent_handler(intent: str, report_date: str):
    def _handler(request):
        return {
            "answer": f"{intent} result",
            "basis": "formal",
            "result_kind": f"agent.{intent}",
            "formal_use_allowed": True,
            "source_version": f"sv_{intent}",
            "quality_flag": "ok",
            "row_count": 1,
            "tables_used": [f"fact_{intent}"],
            "filters_applied": {"report_date": report_date},
            "cards": [{"type": "metric", "title": intent, "value": "1"}],
        }

    return _handler


def test_workflow_memo_lists_divergent_report_dates_per_intent(tmp_path):
    """回归（B15-11）：子意图 report_date 分歧时 memo 不得只取第一个命中值，
    必须逐子意图列出并标注不一致。"""
    tool_module = _tool_module()
    request_module = _request_module()

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "market_data": _dated_intent_handler("market_data", "2026-03-31"),
            "news": _dated_intent_handler("news", "2026-04-01"),
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/market-brief",
            context={"workflow_mode": "execute"},
        )
    )

    memo_card = next(card for card in envelope.cards if card.title == "Workflow Memo")
    assert "子意图日期不一致" in memo_card.value
    assert "market_data=2026-03-31" in memo_card.value
    assert "news=2026-04-01" in memo_card.value


def test_workflow_memo_shows_single_report_date_when_consistent(tmp_path):
    tool_module = _tool_module()
    request_module = _request_module()

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "market_data": _dated_intent_handler("market_data", "2026-03-31"),
            "news": _dated_intent_handler("news", "2026-03-31"),
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/market-brief",
            context={"workflow_mode": "execute"},
        )
    )

    memo_card = next(card for card in envelope.cards if card.title == "Workflow Memo")
    assert "报告日期：2026-03-31" in memo_card.value
    assert "子意图日期不一致" not in memo_card.value
