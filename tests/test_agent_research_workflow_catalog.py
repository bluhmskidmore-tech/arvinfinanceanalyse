from __future__ import annotations

from tests.helpers import load_module


def _catalog_module():
    return load_module(
        "backend.app.agent.runtime.research_workflow_catalog",
        "backend/app/agent/runtime/research_workflow_catalog.py",
    )


def test_catalog_lists_research_radar_brief():
    catalog = _catalog_module()

    workflows = catalog.list_research_workflows()

    assert [workflow.workflow_id for workflow in workflows] == ["research_radar_brief"]
    assert workflows[0].category == "research"


def test_catalog_recognizes_hyphenated_research_workflow_id():
    catalog = _catalog_module()

    assert catalog.is_research_workflow_id("research-radar-brief") is True
    assert catalog.get_research_workflow("research-radar-brief").workflow_id == "research_radar_brief"


def test_catalog_resolves_workflow_from_context_intent_or_workflow_id():
    catalog = _catalog_module()

    assert (
        catalog.resolve_research_workflow({"intent": "research_radar_brief"}).workflow_id
        == "research_radar_brief"
    )
    assert (
        catalog.resolve_research_workflow({"workflow_id": "research-radar-brief"}).workflow_id
        == "research_radar_brief"
    )
    assert catalog.resolve_research_workflow({"workflow_id": "unknown"}) is None
