from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REFERENCE_SOURCE = "anthropic_financial_services_reference"

_SLASH_COMMANDS = {
    "/portfolio-review": "portfolio_review",
    "/pnl-review": "pnl_review",
    "/risk-memo": "risk_memo",
    "/market-brief": "market_brief",
}


@dataclass(frozen=True)
class FinancialWorkflow:
    workflow_id: str
    title: str
    description: str
    category: str
    mapped_intents: list[str]
    output_kind: str
    governance_notes: list[str]
    source: str = REFERENCE_SOURCE


_WORKFLOWS: tuple[FinancialWorkflow, ...] = (
    FinancialWorkflow(
        workflow_id="portfolio_review",
        title="Portfolio Review",
        description="Reference workflow plan for reviewing portfolio scale, duration risk, and credit exposure.",
        category="portfolio",
        mapped_intents=["portfolio_overview", "duration_risk", "credit_exposure"],
        output_kind="workflow_plan",
        governance_notes=[
            "Uses Anthropic financial-services reference patterns only as a workflow blueprint.",
            "Routes through existing MOSS governed intents before any formal financial result can be produced.",
            "Does not connect to Claude API, Managed Agents, or external market-data providers.",
        ],
    ),
    FinancialWorkflow(
        workflow_id="pnl_review",
        title="PnL Review",
        description="Reference workflow plan for reviewing PnL summary, bridge, and product-level PnL.",
        category="pnl",
        mapped_intents=["pnl_summary", "pnl_bridge", "product_pnl"],
        output_kind="workflow_plan",
        governance_notes=[
            "Keeps formal PnL calculations inside existing MOSS intent handlers.",
            "Does not write adjustments or trigger downstream posting workflows.",
            "Current phase returns a plan card only; no multi-intent execution is performed.",
        ],
    ),
    FinancialWorkflow(
        workflow_id="risk_memo",
        title="Risk Memo",
        description="Reference workflow plan for preparing a governed risk memo outline.",
        category="risk",
        mapped_intents=["duration_risk", "credit_exposure", "risk_tensor"],
        output_kind="workflow_plan",
        governance_notes=[
            "Uses MOSS duration, credit exposure, and risk tensor evidence paths when executed later.",
            "Current response is non-formal and has no evidence rows.",
            "External agents cannot bypass MOSS result_meta, lineage, or audit contracts.",
        ],
    ),
    FinancialWorkflow(
        workflow_id="market_brief",
        title="Market Brief",
        description="Reference workflow plan for combining governed market data and news evidence.",
        category="market",
        mapped_intents=["market_data", "news"],
        output_kind="workflow_plan",
        governance_notes=[
            "Uses existing MOSS market-data and news intents rather than new external feeds.",
            "Any future provider integration must enter through governed MCP/data contracts.",
            "Current phase does not fetch or license external financial data.",
        ],
    ),
)

_WORKFLOW_BY_ID = {workflow.workflow_id: workflow for workflow in _WORKFLOWS}


def list_financial_workflows() -> list[FinancialWorkflow]:
    return list(_WORKFLOWS)


def get_financial_workflow(workflow_id: str) -> FinancialWorkflow | None:
    normalized = str(workflow_id or "").strip().lower().replace("-", "_")
    return _WORKFLOW_BY_ID.get(normalized)


def resolve_financial_workflow(
    question: str,
    context: dict[str, Any] | None,
) -> FinancialWorkflow | None:
    context = context or {}
    requested_id = context.get("workflow_id")
    if requested_id:
        workflow = get_financial_workflow(str(requested_id))
        if workflow is not None:
            return workflow

    normalized_question = str(question or "").strip().lower()
    for command, workflow_id in _SLASH_COMMANDS.items():
        if command in normalized_question:
            return get_financial_workflow(workflow_id)
    return None
