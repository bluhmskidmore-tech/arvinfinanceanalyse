from __future__ import annotations

from tests.helpers import load_module


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
