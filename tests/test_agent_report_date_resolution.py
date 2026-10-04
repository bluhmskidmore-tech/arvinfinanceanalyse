from __future__ import annotations

import importlib

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_agent_mvp]


def test_question_report_date_never_silently_selects_latest():
    service = importlib.import_module("backend.app.services.agent_service")
    request = AgentQueryRequest(question="2026-03-31 的组合概览")

    assert service._latest_or_requested(request, ["2026-04-01", "2026-03-31"]) == "2026-03-31"
    with pytest.raises(ValueError, match="not in available governed dates"):
        service._latest_or_requested(request, ["2026-04-01"])


@pytest.mark.parametrize("module_name", [
    "backend.app.services.agent_service",
    "backend.app.agent.tools.analysis_view_tool",
])
@pytest.mark.parametrize(("question", "filters", "expected", "error"), [
    ("2026-03-31 的组合概览", {}, "2026-03-31", None),
    ("/market-brief 2026-03-31", {"report_date": "2026-03-31"}, "2026-03-31", None),
    ("组合概览", {}, None, None),
    ("2026-03-31 的组合概览", {"report_date": "2026-04-01"}, None, "report_date_conflict"),
    ("比较 2026-03-30 和 2026-03-31 的组合", {}, None, "report_date_conflict"),
    ("2026-02-30 的组合概览", {}, None, "invalid_report_date"),
])
def test_handlers_and_workflows_share_explicit_date_validation(
    module_name, question, filters, expected, error,
):
    module = importlib.import_module(module_name)
    request = AgentQueryRequest(question=question, filters=filters)
    if error:
        with pytest.raises(ValueError, match=error):
            module._requested_report_date(request)
    else:
        assert module._requested_report_date(request) == expected


def test_workflow_question_date_is_pinned_before_first_handler(tmp_path):
    module = importlib.import_module("backend.app.agent.tools.analysis_view_tool")
    calls = []

    def handler(request):
        calls.append(request.context.get("report_date"))
        return {
            "answer": "fixture", "source_version": "sv_fixture",
            "quality_flag": "ok", "formal_use_allowed": False,
            "filters_applied": {"report_date": request.context.get("report_date")},
            "resolved_report_date": request.context.get("report_date"),
        }

    tool = module.AnalysisViewTool(
        str(tmp_path / "unused.duckdb"), str(tmp_path),
        intent_handlers={"market_data": handler, "news": handler},
    )
    result = tool.execute(AgentQueryRequest(
        question="/market-brief 2026-03-31", context={"workflow_mode": "execute"},
    ))
    assert calls == ["2026-03-31", "2026-03-31"]
    assert result.result_meta.requested_report_date == "2026-03-31"
    assert result.result_meta.resolved_report_date == "2026-03-31"
