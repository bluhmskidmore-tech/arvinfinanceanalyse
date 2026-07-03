from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        source_version="sv_agent_research_radar_brief_v1a",
        rule_version="rv_agent_research_radar_catalog_v1a",
        cache_version="cv_agent_research_radar_brief_v1a",
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


def resolve_research_workflow(context: dict[str, Any] | None) -> ResearchWorkflow | None:
    context = context or {}
    for key in ("workflow_id", "intent"):
        workflow = get_research_workflow(str(context.get(key) or ""))
        if workflow is not None:
            return workflow
    return None


def _normalize_workflow_id(workflow_id: str) -> str:
    return str(workflow_id or "").strip().lower().replace("-", "_")
