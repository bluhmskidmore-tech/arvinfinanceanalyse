# Product-Category Development Data Readiness

## Purpose

This note is the compact evidence baseline for the current system-development-data closure lane. It records what is known from local contracts, DuckDB read models, governance records, and checked-in tests/samples before any future implementation work.

It is not a metric approval document and does not change page closure status.

## Scope

Primary pilot page/workflow:

- Page: `PAGE-PROD-CAT-PNL-001` / `/product-category-pnl`
- Governed API: `GET /ui/pnl/product-category`
- Truth chain: paired ledger + daily-average sources -> product-category source service -> core finance calculation -> formal read model -> service -> API -> page

This baseline deliberately keeps broader system readiness as supporting context only. It does not generalize product-category conclusions to unrelated pages.

## Local Evidence Used

| Evidence source | What it contributes | Limit |
| --- | --- | --- |
| `docs/pnl/product-category-page-truth-contract.md` | Page truth chain, field freeze, row-authority prohibitions, explicit gaps | P0 approves only `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003`; detail `metric_id` expansion remains open. |
| `docs/pnl/product-category-closure-checklist.md` | Unit-by-unit closure status and evidence map | All units remain `PARTIAL` at this baseline |
| `docs/pnl/product-category-remaining-blockers.md` | Blocker class and cursor-safe next work | Product/API decision rows remain blocked |
| `docs/page_contracts.md` | Page contract binding for `PAGE-PROD-CAT-PNL-001` | Keeps `as_of_date` and detail `metric_id` gaps explicit |
| `docs/metric_dictionary.md` | Cross-sample dictionary stance | Only the three headline product-category metrics are approved; detail fields remain page/sample truth until separately approved. |
| `tests/golden_samples/GS-PROD-CAT-PNL-A/` | Capture-ready sample pack | Scenario remains a companion probe, not a second full sample |
| `tests/test_product_category_pnl_flow.py` | Backend route/materialization/scenario/manual-adjustment coverage | Targeted product-category flow, not full-system closure |
| `frontend/src/test/ProductCategoryPnlPage.test.tsx` | Main page behavior and governance strip evidence | Mock/client UI evidence, not source-authority evidence |

## DuckDB Readiness Snapshot

Read-only local catalog check against `data/moss.duckdb` found:

| Table | Rows | Report-date coverage | Notes |
| --- | ---: | --- | --- |
| `product_category_pnl_formal_read_model` | 2,052 | `2024-01-31` through `2026-03-31` | Four governed views present |
| `product_category_pnl_canonical_fact` | 218,176 | `2024-01-31` through `2026-03-31` | Source fact layer for product-category formal read model |
| `product_category_pnl_scenario_read_model` | 0 | none | Scenario is currently applied as governed overlay/probe, not persisted sample table evidence |

View coverage in `product_category_pnl_formal_read_model`:

| View | Rows | Distinct dates |
| --- | ---: | ---: |
| `monthly` | 513 | 27 |
| `qtd` | 513 | 27 |
| `ytd` | 513 | 27 |
| `year_to_report_month_end` | 513 | 27 |

Read-only reconciliation spot checks found:

- no `asset_total.business_net_income + liability_total.business_net_income != grand_total.business_net_income` violations above `0.01`
- no `ytd` versus `year_to_report_month_end` grand-total differences above `0.01`

These checks support readiness for the pilot closure lane, but they do not approve every displayed field, row, or metric definition.

## Governance Snapshot

The local governance stream `data/governance/cache_build_run.jsonl` includes a recent `product_category_pnl` run that completed after earlier stale/failed records.

Relevant interpretation:

- The formal read model has current local materialization evidence.
- Prior stale/failed records remain important for UI/state closure because stale/failed refresh states must stay visible rather than silently ignored.
- This evidence does not define timeout copy, fallback-date semantics, or permanent API policy.

## Explicit Gaps Preserved

Do not treat this baseline as resolving these blockers:

- detail product-category `metric_id` expansion beyond `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003` is still missing
- standalone outward `as_of_date` is still missing
- fallback-date semantics remain a product/API decision
- refresh timeout messaging remains a product decision
- CSV BOM / large-export policy remains a backend/API decision
- destructive revoke confirmation remains a product decision
- scenario comparison is still a companion probe, not a second full golden matrix sample

## MCP Residual Risk

Project MCP servers are configured in `.mcp.json` (`moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `gitnexus`, `playwright`), but MCP resources were not available to this session when the baseline was gathered.

Fallback evidence used here:

- local contract docs
- local DuckDB read-only queries
- local governance JSONL tail checks
- checked-in tests and golden sample files

Residual risk: if an external MCP runtime has newer contract/catalog/lineage evidence than the local files, this note may lag that runtime state. Future business-metric edits should re-attempt MCP evidence before implementation.

## Next Safe Use

Use this baseline to start decision-free closure work only:

1. split blockers into decision-free versus decision-required queues
2. strengthen already-defined sample/scenario assertions
3. add stale/fallback matrix skeletons with unknown cells marked as decision-required
4. keep all closure status changes evidence-gated
