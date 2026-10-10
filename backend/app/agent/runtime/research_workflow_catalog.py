from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_SLASH_COMMANDS = {
    "/research-radar": "research_radar_brief",
}

_QUESTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "research_radar_brief": ("研究速读", "研究雷达", "research radar"),
}


@dataclass(frozen=True)
class ResearchWorkflow:
    workflow_id: str
    title: str
    description: str
    category: str
    result_kind: str
    source_version: str
    rule_version: str
    cache_version: str
    governance_notes: list[str]


_WORKFLOWS: tuple[ResearchWorkflow, ...] = (
    ResearchWorkflow(
        workflow_id="research_radar_brief",
        title="Research Radar Brief",
        description="Local analytical brief over governed Choice news events.",
        category="research",
        result_kind="agent.research_radar_brief",
        # rule/cache 与 handler（research_radar_service）实际输出对齐；
        # handler 的 source_version 为动态值 sv_research_radar_{event_count}，此处为 plan 卡使用的目录版本。
        source_version="sv_research_radar_catalog_v1",
        rule_version="rv_research_radar_v1",
        cache_version="cv_research_radar_v1",
        governance_notes=[
            "Analytical only: not a formal metric, stress result, or trading instruction.",
            "Raw Choice/news evidence must appear before interpretation.",
            "Human confirmation is required before any later scenario analysis.",
        ],
    ),
)

_WORKFLOW_BY_ID = {workflow.workflow_id: workflow for workflow in _WORKFLOWS}


def list_research_workflows() -> list[ResearchWorkflow]:
    return list(_WORKFLOWS)


def get_research_workflow(workflow_id: str) -> ResearchWorkflow | None:
    normalized = _normalize_workflow_id(workflow_id)
    return _WORKFLOW_BY_ID.get(normalized)


def is_research_workflow_id(workflow_id: str) -> bool:
    return get_research_workflow(workflow_id) is not None


def resolve_research_workflow(
    question: str,
    context: dict[str, Any] | None,
) -> ResearchWorkflow | None:
    context = context or {}
    workflow = get_research_workflow(str(context.get("workflow_id") or ""))
    if workflow is not None:
        return workflow

    normalized_question = str(question or "").strip().lower()
    if not normalized_question:
        return None
    for command, workflow_id in _SLASH_COMMANDS.items():
        if command in normalized_question:
            return get_research_workflow(workflow_id)
    for workflow_id, keywords in _QUESTION_KEYWORDS.items():
        if any(keyword.lower() in normalized_question for keyword in keywords):
            return get_research_workflow(workflow_id)
    return None


def _normalize_workflow_id(workflow_id: str) -> str:
    return str(workflow_id or "").strip().lower().replace("-", "_")
