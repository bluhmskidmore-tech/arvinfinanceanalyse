# MOSS Spec + Harness Governance Index

Status label: supporting

This file is a navigation and execution checklist for AI-assisted development.
It is non-authorizing and always defers to:

`AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`

If this file conflicts with that chain, follow the authority chain.

## Purpose

Use this index before starting work on a business metric page, workflow, adapter,
formatter, selector, API client, or data-fetch path. It connects the repo's
existing Spec documents with the Harness rules that govern how an AI agent
should run.

The goal is not to create a new source of truth. The goal is to make the
existing read path repeatable:

1. Read the execution boundary.
2. Read the page or workflow Spec.
3. Check metric, lineage, catalog, and test evidence.
4. Make the smallest scoped change.
5. Verify with page-level or workflow-level gates.

## Two-Layer Model

### General Spec Layer

The General Spec layer defines what the system should do.

Primary references:

- `prd-moss-agent-analytics-os.md`: system intent and product direction.
- `docs/page_contracts.md`: page-level purpose, sections, states, endpoints, and metric bindings.
- `docs/metric_dictionary.md`: governed metric IDs, units, source fields, and test anchors.
- `docs/data_contracts.md`: source data shape, grain, lineage, and formal fact contracts.
- `docs/calc_rules.md`: calculation and semantic rules.
- `docs/acceptance_tests.md`: acceptance and contract test expectations.

### Harness Governance Layer

The Harness layer defines how AI-assisted work should run.

Primary references:

- `AGENTS.md`: repo operating rules, current priorities, forbidden scopes, and validation expectations.
- `docs/DOCUMENT_AUTHORITY.md`: document precedence and conflict handling.
- `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`: current-state navigation entrypoint.
- `docs/MCP_RUNBOOK.md`: MCP evidence workflow, tool boundaries, trace bundles, and fallback rules.
- `.mcp.json`: local MCP server registration for repository graph, metric contracts, lineage, catalog, quality, and browser verification.
- Path-local `AGENTS.md` / `CLAUDE.md` files: narrower instructions for backend, frontend, and tests.

## Standard Read Path

Use this path for all business metric page or workflow work:

1. `AGENTS.md`
   - Confirm current priorities, forbidden scopes, work protocol, and validation rules.
2. `docs/DOCUMENT_AUTHORITY.md`
   - Confirm which documents win if planning material, historic docs, and current contracts disagree.
3. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
   - Confirm the current repo-level boundary and applicable scoped overrides.
4. Closest path-local rules
   - Read the nearest `AGENTS.md` or `CLAUDE.md` under `frontend/`, `backend/`, or `tests/` when touching that area.
5. Page or workflow contract
   - Read the relevant entry in `docs/page_contracts.md`, a dedicated truth contract, or `docs/page_contract_template.md` for new governed surfaces.
6. Metric and data contracts
   - Read `docs/metric_dictionary.md`, `docs/data_contracts.md`, and `docs/calc_rules.md` only for the relevant page, metric, or workflow.
7. Evidence tools
   - Use the MCP servers from `docs/MCP_RUNBOOK.md` when touching metric, lineage, catalog, quality, or visible page behavior.

## Harness Rules For AI Execution

- Business metric pages must use MCP evidence first when the tools are exposed in the session. If an MCP server is unavailable, record the unavailable server, the local evidence used instead, and the residual risk.
- Do not guess metric definitions, units, report dates, `as_of_date`, source lineage, or sample approval status.
- Do not recompute formal metrics in the frontend. Trace the governed value from API response through adapter/model/state/selector to the component or chart.
- Do not promote preview, vendor, analytical, placeholder, reserved, or excluded surfaces into formal truth.
- Do not add business logic to broad composition files when a domain client, adapter, service, or existing contract boundary exists.
- Stale data, fallback mode, no data, loading failure, vendor degradation, and pending metric definition states must remain visible to the user.
- Keep changes scoped to one page or one workflow unless the evidence proves a shared boundary is the root cause.
- Do not modify database schema, auth, scheduler, cache base layers, global SDK wrappers, or unrelated backend services unless explicitly requested or directly proven as the root cause.

## Before-Editing Checklist

- State the page or workflow being fixed.
- State the first files and contracts to inspect.
- State what will not be touched.
- Confirm the page/workflow status: `active`, `candidate`, `placeholder`, `excluded`, or `mixed-source`.
- Identify the primary business question the page must answer.
- Identify the governed API, DTO, adapter/model, selector/computed path, and component/table/chart path.
- Identify all headline metrics and their `metric_id` bindings, or record the explicit gap.
- Check unit, precision, date, fallback, null-vs-zero, and mock-data semantics.
- Check whether a golden sample exists and whether it freezes full-page truth, section-level truth, or DTO shape only.

## Completion Checklist

- Report the root cause or document-only rationale.
- List changed files.
- Report the validation commands and results.
- Confirm the existing authority chain was not changed.
- Confirm no supporting artifact was promoted into a new authority source.
- Confirm any MCP unavailability and the fallback evidence used.
- Confirm any remaining gaps, especially missing `as_of_date`, fallback visibility, metric dictionary coverage, or golden sample coverage.

## Page Maturity Matrix

| Page or workflow | Current maturity | Evidence anchors | Known gap |
| --- | --- | --- | --- |
| `dashboard-home` | Governed mixed dashboard surface with seeded trace bundle. | `docs/MCP_RUNBOOK.md`; `docs/dashboard_cockpit_contract.md`; `docs/page_contracts.md`; executive sub-surface samples `GS-EXEC-OVERVIEW-A`, `GS-EXEC-PNL-ATTR-A`, `GS-EXEC-SUMMARY-A`. | Aggregate homepage remains analytical or mixed-source; no full-page formal golden sample. |
| `product-category-pnl` | Highest maturity governed page. | `docs/pnl/product-category-page-truth-contract.md`; `docs/page_contracts.md`; `docs/metric_dictionary.md`; `GS-PROD-CAT-PNL-A`; `tests/test_product_category_pnl_flow.py`; `tests/test_product_category_mapping_contract.py`. | Standalone outward `as_of_date` is intentionally absent; unresolved stale/fallback wording remains visible in the truth contract. |
| `market-data` | Mixed-source page with a page contract and formal rates fragment. | `docs/page_contracts.md`; `docs/metric_dictionary.md`; `frontend/src/features/market-data/docs/REQUIREMENTS_SNAPSHOT.md`; `frontend/src/test/MarketDataPage.test.tsx`. | No full-page formal metric dictionary coverage or capture-ready golden sample; preview/vendor/analytical surfaces must stay labeled. |
| Other live pages | Register before extending. | Start from `docs/page_contracts.md`, `docs/metric_dictionary.md`, and path-local tests. | Do not backfill full specs opportunistically; record unknowns as gaps until evidence exists. |

## Evidence Tool Map

| Evidence need | Preferred source |
| --- | --- |
| Page contracts, metric definitions, calculation rules, golden samples | `moss-metric-contracts` |
| Source version, rule/cache lineage, fallback/stale status, governance evidence | `moss-lineage-evidence` |
| DuckDB table inventory, columns, schema registry, and available dates | `moss-data-catalog` |
| Data quality summaries, row counts, null counts, date coverage, sample hints | `moss-data-quality` |
| Repository graph, symbols, call paths, and cross-page impact | `gitnexus` |
| Browser-level visible behavior and page state verification | `playwright` |

## Minimum Handoff Shape

For every completed change, report:

- Page or workflow fixed.
- Root cause or governance rationale.
- Changed files.
- Evidence used, including MCP servers or fallback evidence.
- Validation performed.
- Known remaining risk or explicit "no known remaining risk".
