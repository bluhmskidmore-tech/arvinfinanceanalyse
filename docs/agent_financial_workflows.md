# Agent Financial Workflows

This document records the first-stage MOSS integration of ideas from Anthropic's open source financial-services reference work. The integration is intentionally small: MOSS treats the reference as a workflow blueprint catalog, not as an external agent runtime.

## Scope

Included in this phase:

- Static workflow definitions under the MOSS agent runtime.
- Mapping from workflow IDs and slash commands to existing MOSS agent intents.
- A plan-only `AgentEnvelope` response that preserves MOSS `result_meta`, evidence, and audit boundaries.
- An explicit execute mode that runs the mapped MOSS intents in order and returns a workflow summary.
- A template-synthesized `Workflow Memo` card on successful execute responses (no LLM involved).

Not included in this phase:

- Claude API integration.
- Anthropic Managed Agents integration.
- FactSet, S&P, LSEG, PitchBook, or other external financial data connectors.
- Changes to formal compute, DuckDB writes, permissions, schedulers, or global SDK wrappers.
- Report generation.

## Workflow Mapping

| Workflow ID | Slash command | Category | MOSS mapped intents |
| --- | --- | --- | --- |
| `portfolio_review` | `/portfolio-review` | portfolio | `portfolio_overview`, `duration_risk`, `credit_exposure` |
| `pnl_review` | `/pnl-review` | pnl | `pnl_summary`, `pnl_bridge`, `product_pnl` |
| `risk_memo` | `/risk-memo` | risk | `duration_risk`, `credit_exposure`, `risk_tensor` |
| `market_brief` | `/market-brief` | market | `market_data`, `news` |

## Governance Contract

Workflow catalog responses are execution plans, not formal financial results.

The workflow envelope uses:

- `result_kind`: `agent.workflow.<workflow_id>`
- `formal_use_allowed`: `false`
- `source_version`: `sv_anthropic_financial_workflow_reference`
- `rule_version`: `rv_agent_financial_workflow_catalog_v1`
- `evidence.tables_used`: `[]`
- `evidence.evidence_rows`: `0`
- `evidence.quality_flag`: `warning`

The first suggested action points to the first mapped MOSS intent and requires confirmation. Its `payload` contains only the target `intent` (plus the server-injected `confirmation_scope`); it intentionally does not repeat `workflow_id`, so merging the payload into the follow-up request `context` executes that intent directly. (The payload previously also carried `workflow_id`, which made an echoed payload resolve back to the workflow and return the plan card again instead of executing.) The research workflow plan action keeps `workflow_id` plus `workflow_mode="execute"` in its payload because its action executes the whole single-intent workflow. The catalog does not write data, does not trigger side effects, and does not let any external agent bypass MOSS metric definitions, lineage, `result_meta`, or audit contracts.

Note: the `pnl_review` governance note previously said "plan card only", and the `risk_memo` note previously said the response "has no evidence rows"; both wordings were stale once execute mode landed. All four workflows support the explicit execute mode described below. The `pnl_review` note now reads "Plan card is the default; multi-intent execution requires explicit `context.workflow_mode=execute`." and the `risk_memo` note now reads "Plan responses are non-formal with no evidence rows; execute mode aggregates evidence from the mapped MOSS intents."

The research workflow `research_radar_brief` (`/research-radar`, keywords 「研究速读」/「研究雷达」) follows the same plan-default / execute-on-request contract; see `docs/AGENT_MVP_RUNBOOK.md`.

## Usage

Plan mode is the default:

```json
{
  "question": "/risk-memo",
  "basis": "formal",
  "context": {}
}
```

Execute mode is opt-in:

```json
{
  "question": "/risk-memo",
  "basis": "formal",
  "context": {
    "workflow_mode": "execute"
  }
}
```

The execute mode:

- Calls the workflow's mapped MOSS intent handlers in catalog order.
- Keeps the workflow-level `formal_use_allowed` value as `false`.
- Preserves child intent evidence in the workflow cards and aggregates `tables_used` / `evidence_rows` / `sql_executed`.
- Returns `quality_flag=warning` if any mapped intent is missing, fails, or returns a non-OK quality flag.
- Does not write data or trigger external systems.
- Prepends a `Workflow Memo` card (`type=markdown`, first card) synthesized purely from templates, with no LLM call:
  - workflow title and ID, plus the resolved report date taken from child intent filters;
  - a one-line conclusion per child intent, taken directly from the first line of each child envelope's answer (failed or missing intents are listed as failures);
  - a data-quality section listing any child intent whose `quality_flag` is not `ok`;
  - a fixed closing statement: 「非正式结果，仅供分析参考（formal_use_allowed=false）。」

The memo card does not change workflow-level `result_meta`: `formal_use_allowed` stays `false` and the quality-flag aggregation rule above is unchanged. The single-intent research workflow execute path (`research_radar_brief`) does not go through the multi-intent executor and has no memo card.

## Workbench Usage

Agent Workbench exposes four static financial workflow shortcuts:

| Button | Slash command | Local MOSS execution |
| --- | --- | --- |
| Portfolio Review | `/portfolio-review` | `portfolio_overview`, `duration_risk`, `credit_exposure` |
| PnL Review | `/pnl-review` | `pnl_summary`, `pnl_bridge`, `product_pnl` |
| Risk Memo | `/risk-memo` | `duration_risk`, `credit_exposure`, `risk_tensor` |
| Market Brief | `/market-brief` | `market_data`, `news` |

Clicking a workflow button sends `POST /api/agent/query` with `basis="formal"` and `context.workflow_mode="execute"`. The Workbench preserves any mounted `page_context`, then renders the returned `AgentEnvelope` in the same conversation.

The workflow result uses the existing Workbench panels:

- `Workflow Execution Steps` shows each mapped intent's order, status, quality flag, and evidence row count.
- `Mapped Intent Results` shows each child intent's answer, `result_kind`, source tables, and evidence row count.
- The right-side evidence and `result_meta` panels continue to show workflow-level governance state, including `formal_use_allowed=false`.

Normal free-text questions in Agent Workbench continue through the managed `/api/agent/runs` path. Only the four financial workflow shortcut buttons use the local `/api/agent/query` execute-mode path.

## Next Phases

Future work can add:

- Richer report generation beyond the template-synthesized `Workflow Memo` card (e.g. LLM-drafted narratives under explicit governance review).
- Optional external MCP data access only through explicit MOSS governance, lineage, and licensing checks.
