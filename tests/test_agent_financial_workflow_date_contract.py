from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]

REQUESTED_DATE = date(2026, 3, 30)
RESOLVED_DATE = date(2026, 3, 31)


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


def _intent_handler(
    intent: str,
    *,
    evidence_report_date: object | None = None,
    requested_report_date: str | None = None,
    resolved_report_date: str | None = None,
    quality_flag: str = "ok",
):
    def _handler(request):
        payload: dict[str, Any] = {
            "answer": f"{intent} result",
            "basis": "formal",
            "result_kind": f"agent.{intent}",
            "formal_use_allowed": True,
            "source_version": f"sv_{intent}",
            "quality_flag": quality_flag,
            "row_count": 1,
            "tables_used": [f"fact_{intent}"],
            "cards": [{"type": "metric", "title": intent, "value": "1"}],
        }
        if evidence_report_date is not None:
            payload["filters_applied"] = {"report_date": evidence_report_date}
        if requested_report_date is not None:
            payload["requested_report_date"] = requested_report_date
        if resolved_report_date is not None:
            payload["resolved_report_date"] = resolved_report_date
        return payload

    return _handler


def _market_brief_tool(tmp_path, handlers):
    return _tool_module().AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=handlers,
    )


def _execute_market_brief(tool, request_module, **request_kwargs):
    context = dict(request_kwargs.pop("context", {}))
    context["workflow_mode"] = "execute"
    return tool.execute(
        request_module.AgentQueryRequest(
            question="/market-brief",
            context=context,
            **request_kwargs,
        )
    )


@pytest.mark.parametrize(
    "request_kwargs",
    [
        pytest.param(
            {"filters": {"report_date": REQUESTED_DATE}},
            id="filters-report-date-object",
        ),
        pytest.param(
            {"context": {"date": REQUESTED_DATE}},
            id="context-date-object",
        ),
        pytest.param(
            {"context": {"current_filters": {"report_date": REQUESTED_DATE}}},
            id="context-current-filters",
        ),
        pytest.param(
            {
                "page_context": {
                    "page_id": "market-brief",
                    "current_filters": {"date": REQUESTED_DATE},
                }
            },
            id="page-current-filters",
        ),
    ],
)
def test_plan_tracks_explicit_requested_date_without_resolving(tmp_path, request_kwargs):
    request_module = _request_module()
    tool = _market_brief_tool(tmp_path, {})

    request_kwargs = dict(request_kwargs)
    context = {"user_id": "user_a", **request_kwargs.pop("context", {})}
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/market-brief",
            context=context,
            **request_kwargs,
        )
    )

    assert envelope.result_meta.requested_report_date == REQUESTED_DATE.isoformat()
    assert envelope.result_meta.resolved_report_date is None


def test_all_successful_children_with_consistent_dates_resolve_workflow(tmp_path):
    request_module = _request_module()
    tool = _market_brief_tool(
        tmp_path,
        {
            "market_data": _intent_handler(
                "market_data",
                evidence_report_date=RESOLVED_DATE,
                quality_flag="error",
            ),
            "news": _intent_handler("news", evidence_report_date=RESOLVED_DATE),
        },
    )

    envelope = _execute_market_brief(
        tool,
        request_module,
        filters={"report_date": REQUESTED_DATE},
    )
    results_card = next(
        card for card in envelope.cards if card.title == "Mapped Intent Results"
    )

    assert envelope.result_meta.requested_report_date == REQUESTED_DATE.isoformat()
    assert envelope.result_meta.resolved_report_date == RESOLVED_DATE.isoformat()
    assert envelope.result_meta.quality_flag == "warning"
    assert [row["resolved_report_date"] for row in results_card.data] == [
        RESOLVED_DATE.isoformat(),
        RESOLVED_DATE.isoformat(),
    ]


def test_divergent_dates_prefer_child_meta_and_fail_closed(tmp_path):
    request_module = _request_module()
    tool = _market_brief_tool(
        tmp_path,
        {
            "market_data": _intent_handler(
                "market_data",
                evidence_report_date=RESOLVED_DATE,
                resolved_report_date="2026-03-30",
            ),
            "news": _intent_handler(
                "news",
                evidence_report_date=date(2026, 4, 1),
            ),
        },
    )

    envelope = _execute_market_brief(tool, request_module)
    results_card = next(
        card for card in envelope.cards if card.title == "Mapped Intent Results"
    )
    memo_card = next(card for card in envelope.cards if card.title == "Workflow Memo")

    assert envelope.result_meta.resolved_report_date is None
    assert [row["resolved_report_date"] for row in results_card.data] == [
        "2026-03-30",
        "2026-04-01",
    ]
    assert "market_data=2026-03-30" in memo_card.value
    assert "news=2026-04-01" in memo_card.value


@pytest.mark.parametrize("failure_mode", ["missing", "error"])
def test_partial_failure_does_not_resolve_workflow_date(tmp_path, failure_mode):
    request_module = _request_module()
    handlers = {
        "market_data": _intent_handler(
            "market_data",
            resolved_report_date=RESOLVED_DATE.isoformat(),
        )
    }
    if failure_mode == "error":

        def _failing_handler(request):
            raise ValueError("news unavailable")

        handlers["news"] = _failing_handler
    tool = _market_brief_tool(tmp_path, handlers)

    envelope = _execute_market_brief(tool, request_module)

    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.resolved_report_date is None


def test_execute_without_explicit_date_pins_later_steps_to_first_resolved_date(tmp_path):
    request_module = _request_module()
    seen_report_dates: list[object | None] = []

    def _first_handler(request):
        seen_report_dates.append(request.context.get("report_date"))
        return {
            "answer": "market_data result",
            "basis": "formal",
            "result_kind": "agent.market_data",
            "formal_use_allowed": True,
            "source_version": "sv_market_data",
            "quality_flag": "ok",
            "row_count": 1,
            "tables_used": ["fact_market_data"],
            "resolved_report_date": RESOLVED_DATE.isoformat(),
            "cards": [{"type": "metric", "title": "market_data", "value": "1"}],
        }

    def _second_handler(request):
        seen_report_dates.append(request.context.get("report_date"))
        return {
            "answer": "news result",
            "basis": "formal",
            "result_kind": "agent.news",
            "formal_use_allowed": True,
            "source_version": "sv_news",
            "quality_flag": "ok",
            "row_count": 1,
            "tables_used": ["fact_news"],
            "resolved_report_date": RESOLVED_DATE.isoformat(),
            "cards": [{"type": "metric", "title": "news", "value": "1"}],
        }

    tool = _market_brief_tool(
        tmp_path,
        {
            "market_data": _first_handler,
            "news": _second_handler,
        },
    )

    envelope = _execute_market_brief(tool, request_module)

    assert seen_report_dates == [None, RESOLVED_DATE.isoformat()]
    assert envelope.evidence.filters_applied["workflow_pinned_report_date"] == RESOLVED_DATE.isoformat()
    assert envelope.result_meta.requested_report_date is None
    assert envelope.result_meta.resolved_report_date == RESOLVED_DATE.isoformat()


def test_execute_separates_degraded_and_failed_intents(tmp_path):
    request_module = _request_module()

    def _failing_handler(request):
        raise ValueError("news unavailable")

    tool = _market_brief_tool(
        tmp_path,
        {
            "market_data": _intent_handler(
                "market_data",
                resolved_report_date=RESOLVED_DATE.isoformat(),
                quality_flag="warning",
            ),
            "news": _failing_handler,
        },
    )

    envelope = _execute_market_brief(tool, request_module)
    steps_card = next(card for card in envelope.cards if card.title == "Workflow Execution Steps")

    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.filters_applied["workflow_degraded_intents"] == ["market_data"]
    assert envelope.evidence.filters_applied["workflow_failed_intents"] == ["news"]
    assert [row["status"] for row in steps_card.data] == ["ok", "error"]
    assert [row["quality_flag"] for row in steps_card.data] == ["warning", "warning"]
    assert "Failed intents: news" in envelope.answer
    assert "Degraded intents: market_data" in envelope.answer
