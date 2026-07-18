# MOSS MCP Runbook

This repository has project-level MCP configuration for both Codex and
Cursor-style clients:

- Codex: `.codex/config.toml`
- Cursor-compatible clients: `.mcp.json`

Existing Codex sessions do not hot-reload MCP registrations. Start a new
thread/session after changing MCP config.

## App Surface Fallback

If the current Codex App tool surface does not directly expose the `moss-*`
resources, do not treat that alone as a repo configuration failure.

1. Verify the project registration with `codex mcp list`.
2. Confirm the local config files still declare the servers:
   `.codex/config.toml` and `.mcp.json`.
3. If those checks pass, treat the missing tool surface as a client/session
   exposure limitation and retry in a fresh session.
4. For a cwd-independent local handshake, use the launcher helper directly:

```powershell
python scripts/mcp/moss_mcp_launcher.py metric-contracts
```

The launcher forces the workspace root before loading
`scripts/mcp/moss_project_mcp.py`, which is useful when a client launches MCP
from the wrong working directory.

## Servers

| Server | Purpose | Command |
| --- | --- | --- |
| `gitnexus` | Repository graph, context, and processes. | `node scripts/mcp/gitnexus_mcp_launcher.mjs` |
| `moss-metric-contracts` | Read-only access to page contracts, metric dictionary, calc rules, product-category truth docs, and golden-sample catalog. | `cmd.exe /d /s /c scripts\mcp\moss_contracts.cmd` |
| `moss-lineage-evidence` | Read-only access to governance JSONL streams, latest evidence records, and lineage search. | `cmd.exe /d /s /c scripts\mcp\moss_lineage.cmd` |
| `moss-data-catalog` | Read-only DuckDB table inventory, schema registry, table description, and available date lookup. | `cmd.exe /d /s /c scripts\mcp\moss_catalog.cmd` |
| `moss-data-quality` | Read-only DuckDB quality summaries: row counts, null counts, date coverage, and golden-sample hints. | `cmd.exe /d /s /c scripts\mcp\moss_data_quality.cmd` |
| `playwright` | Browser/page QA through Playwright MCP. | `npx -y @playwright/mcp@latest` |
| `stitch` | Google Stitch UI generation (design screens, export HTML/screenshots). | `cmd.exe /d /s /c scripts\mcp\stitch_mcp.cmd` |

## Stitch setup

Stitch MCP uses the published `stitch-mcp-server` package and reads `STITCH_API_KEY`
from `config/.env` or the shell environment.

1. Sign in at [stitch.google.com](https://stitch.google.com/) and create an API key.
2. Add the key to `config/.env`:

```env
STITCH_API_KEY=your-key-here
```

3. Restart Cursor or start a new agent session so MCP reloads.
4. Smoke test locally:

```powershell
node scripts/mcp/stitch_mcp_launcher.mjs
```

If the key is missing, the launcher exits with a clear error. If the key is valid,
the process stays running and waits for MCP stdio traffic.

Generate the dashboard-home overview prototype:

```powershell
npm install --prefix scripts/stitch
node scripts/stitch/generate_dashboard_home.mjs
```

Outputs land in `artifacts/stitch/dashboard-home/` (`overview.html`, `overview.png`, `meta.json`).

Generate a Stitch mockup for balance-analysis (often too generic; prefer MOSS v2 HTML):

```powershell
node scripts/stitch/generate_balance_analysis.mjs
```

Generate the cross-asset drivers homepage mockup:

```powershell
node scripts/stitch/generate_cross_asset.mjs
```

Outputs land in `artifacts/stitch/cross-asset/` (`design-draft.html`, `design-draft.png`, `meta.json`, `UI-SPEC.md`).

Preferred balance-analysis design reference (MOSS tokens + 债券经营驾驶舱风格):

- `artifacts/design/balance-analysis-v4-cockpit.html` ← **current (专业驾驶舱)**
- `artifacts/design/balance-analysis-v3.html`
- `artifacts/design/balance-analysis-v2.html` (superseded)
- Spec: `artifacts/stitch/balance-analysis/UI-SPEC.md`
- 用户参考图：细线图标 + KPI 卡片行 + 图表三列 + 风险进度表

Stitch is a design/prototype tool only. Generated HTML must still be adapted to
MOSS `DESIGN.md` and `frontend/src/theme/designSystem.ts` before landing in
production pages.


- The local MOSS servers are read-only.
- `moss-data-catalog` only uses `information_schema` and fixed date-list queries; it does not accept arbitrary SQL.
- `moss-data-quality` validates table identifiers, rejects unknown tables/views, and only runs bounded read-only profiling queries.
- `moss-lineage-evidence` reads whitelisted governance streams only.
- `moss-metric-contracts` reads whitelisted docs and golden-sample metadata only.
- Browser MCP can interact with a running frontend, but it does not change backend data by itself.
- Do not add write-capable DB or task-runner MCP servers without a separate boundary review.

## Useful Resources

Metric contracts:

- `moss://metric-contracts/summary`
- `moss://metric-contracts/doc/page_contracts`
- `moss://metric-contracts/doc/calc_rules`
- `moss://metric-contracts/doc/metric_dictionary`
- `moss://metric-contracts/doc/product_category_truth`
- `moss://metric-contracts/doc/golden_sample_catalog`

Lineage/evidence:

- `moss://lineage/summary`
- `moss://lineage/streams`
- `moss://lineage/stream/cache_manifest`
- `moss://lineage/stream/source_manifest_latest`
- `moss://lineage/stream/agent_audit`

Data catalog:

- `moss://data-catalog/summary`
- `moss://data-catalog/schema-registry`
- `moss://data-catalog/tables`

Data quality:

- `moss://data-quality/summary`
- `moss://data-quality/targets`

## Useful Tools

Metric contracts:

- `search_contract_docs`
- `get_page_trace_bundle`
- `get_page_evidence_readiness`

Lineage/evidence:

- `read_governance_stream`
- `find_lineage_records`
- `get_page_lineage_evidence`
- `get_page_governance_record_requirements`
- `validate_page_governance_records`
- `get_page_governance_audit_review_checklist`
- `get_page_governance_audit_review_queue`
- `get_page_governance_audit_evidence_packet`
- `get_page_governance_audit_evidence_packet_queue`
- `get_page_governance_record_blueprint`
- `get_page_governance_record_blueprint_queue`
- `preflight_page_governance_record`
- `get_page_governance_gap_queue`

Data catalog:

- `describe_table`
- `list_available_dates`
- `get_page_catalog_date_evidence`
- `get_page_catalog_date_coverage`
- `get_page_catalog_date_lineage_review_queue`

Data quality:

- `list_quality_targets`
- `get_quality_summary`

## Page Trace Bundle

Use `moss-metric-contracts.get_page_trace_bundle` before changing a seeded business metric page. It returns a read-only evidence bundle with the page route, governed API, contract documents, truth chain, backend/frontend touchpoints, existing tests, golden samples, verification focus, and page-specific guardrails.

Use `moss-metric-contracts.get_page_evidence_readiness` when auditing candidate or mixed-source page progress across several pages. It returns a read-only matrix of seeded trace-bundle anchors, approval status, approval-status source, golden-sample status, residual gaps, and candidate metric watchlist entries.

Use `moss-data-catalog.get_page_catalog_date_evidence` after the readiness matrix identifies candidate tables that need direct catalog/date evidence. It samples configured DuckDB table descriptions and date columns for seeded high-risk pages, returning separate states for present tables, no date column, unknown table, missing DuckDB, and date-sample failures.

Use `moss-data-catalog.get_page_catalog_date_coverage` before widening catalog/date review beyond the high-risk default pages. It reports which unique seeded page trace bundles have explicit catalog/date table configuration, separates pages deferred because no direct table contract exists, prioritizes true missing formal/governed page configs, and suggests candidate table anchors without sampling DuckDB or granting approval.

Use `moss-data-catalog.get_page_catalog_date_lineage_review_queue` when turning the recommended next-pass page audit into assignment rows. It prioritizes formal/governed pages, candidate or mixed-source pages that use formal source tables, GAP/observational pages that must stay separate from formal closure, and deferred no-direct-table pages. The default scope covers every unique seeded trace bundle and includes `review_lane_breakdown` with lane-level page IDs and counts so reviewers can assign formal/governed, candidate formal-source, mixed/candidate, GAP/observational, and deferred no-direct-table work without scanning the full queue. Each row also includes `record_readiness`, copied from the existing direct-governance-record validation/checklist state, so reviewers can distinguish `ready_for_audit_review` rows from `blocked_by_record_gaps` rows before collecting catalog/date evidence. Each row also includes `record_remediation`, and the payload includes `record_remediation_breakdown`, `record_remediation_work_items`, `record_remediation_evidence_work_items`, and `record_remediation_review_lane_work_items`, so reviewers can assign ready rows, create-direct-record work, existing-record field completion, primary page/API anchor repair, cross-page evidence-key collection, and P1/P2 review-lane batches without opening the packet queue or scanning row-level remediation entries. Record-remediation work items expose `suggested_tool_call_count` and `suggested_tool_names` so dispatchers can see which read-only requirements, blueprint, audit-review, or evidence-packet queue tools are queued without expanding each call. Ready/manual-review remediation work items include read-only suggested calls to `moss-lineage-evidence.get_page_governance_audit_review_queue` and `moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue` for the ready pages, but they do not execute those calls. `record_gap_execution_plan` packages the same record-gap remediation groups into three ordered dispatch stages for remediation-type batches, evidence-key batches, and review-lane batches; it reports blocked and ready/manual-review page counts, source work-item group counts, page-slug arguments for blocked pages, and suggested read-only tool-call counts while keeping `queue_grants_closure=false`. `record_gap_execution_plan_scope_audit` checks those plan stages for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-approval drift and feeds the queue boundary audit. `record_remediation_scope_audit` checks those remediation, evidence, and lane-remediation work items for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-approval drift, and it also counts nested `suggested_tool_calls` against the explicit read-only allowlist for governance requirements, blueprint queue, audit-review queue, and audit-evidence packet queue calls. It also includes `suggested_tool_call_work_items`, which groups the existing suggested catalog, lineage, validation, coverage, or gap-queue calls by lane and tool with merged `page_slugs` for assignment; `suggested_tool_call_scope_audit` checks those grouped suggested-call work items for allowed tools and no-execution/no-sampling/no-lineage-check/no-page-execution/no-approval drift. `evidence_collection_execution_plan` packages the suggested-call work items into five ordered read-only stages for catalog/date evidence, lineage evidence, governance validation, deferred catalog/date coverage, and deferred governance gap queues; `evidence_collection_execution_plan_scope_audit` checks those plan stages for the same no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-approval drift and feeds the queue boundary audit. `manual_audit_review_execution_plan` packages ready/manual-review rows into two ordered read-only stages for audit-review queue collection and audit-evidence packet queue collection; `manual_audit_review_execution_plan_scope_audit` checks those plan stages for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-approval drift and feeds the queue boundary audit. `business_owner_approval_execution_plan` packages ready/manual-review rows into two ordered read-only stages for owner approval request batches and owner approval receipt review batches; `business_owner_approval_execution_plan_scope_audit` checks those plan stages for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-approval drift and feeds the queue boundary audit. `closure_blocker_work_items` routes the same residual closure requirements into read-only rows for record gaps, catalog/date-lineage evidence collection, manual audit review, and business-owner approval, carries `page_slugs` plus `arguments.page_slugs` for direct handoff to the source work-item groups, exposes `source_work_item_group_counts` so each blocker points back to the remediation, evidence, lane-remediation, or suggested-call batches it depends on, points the record-gap blocker to `use_record_gap_execution_plan`, points the catalog/date-lineage evidence blocker to `use_evidence_collection_execution_plan`, points the manual-audit blocker to `use_manual_audit_review_execution_plan`, points the business-owner blocker to `use_business_owner_approval_execution_plan`, and carries each matching `next_step`, `execution_plan`, `execution_stage`, and `execution_stage_detail` key while keeping writes, tool execution, sampling, smoke runs, approval capture, and page approval disabled; `closure_blocker_routing_index` keys those same blocker rows by blocker type for dispatcher lookup without rescanning the array and preserves the same next-step/execution-plan/stage keys and `execution_stage_detail`; `closure_blocker_scope_audit` checks those residual-blocker rows for the same no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-page-approval boundary and reports `execution_target_violations` when blocker rows point at the wrong next step, execution plan, execution stage, or embedded stage detail. `closure_dispatch_packet` repackages `closure_execution_sequence` into ordered dispatcher rows with `dispatch_action`, execution-plan/stage keys, stage detail, page-slug arguments, source work-item group counts, and no-closure scope flags; `closure_dispatch_packet_scope_audit` checks the packet and each dispatch row for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-page-approval drift. `queue_boundary_audit` rolls `record_gap_execution_plan_scope_audit`, `record_remediation_scope_audit`, `suggested_tool_call_scope_audit`, `evidence_collection_execution_plan_scope_audit`, `manual_audit_review_execution_plan_scope_audit`, `business_owner_approval_execution_plan_scope_audit`, `closure_blocker_scope_audit`, `next_closure_action_scope_audit`, and `closure_dispatch_packet_scope_audit` into one no-closure boundary summary, including closure-blocker execution-target drift, next-action pointer drift, embedded stage-detail scope drift, and closure-dispatch packet drift; the current all-seeded queue rolls up 50 assignment rows with a 3/15/14/5/2/2/4/1/4 source split and includes `checked_scope_audit_work_item_counts` so the total can be traced back to each checked audit. `closure_readiness` separately rolls up page count, ready/blocked counts, remediation work, suggested evidence-collection work, closure-blocker assignment work, closure-blocker page/work-item breakdown, `closure_execution_sequence`, `next_closure_action`, next-closure action scope audit, `closure_dispatch_packet`, closure-dispatch packet scope audit, and queue-boundary work, always with `closure_ready_count=0` and `queue_grants_closure=false`; it is a dispatch status so a clean boundary audit is not mistaken for page closure. `next_closure_action` embeds the matching `execution_stage_detail` from the chosen execution plan, so the first unresolved blocker exposes its stage work-item group, counts, stage arguments, next-step detail, and no-closure scope without requiring a second lookup. `closure_execution_sequence` orders residual work as record gaps, catalog/date-lineage evidence, manual audit, then business-owner approval while preserving no-closure scope, and each step carries page-slug arguments plus source work-item group counts so dispatchers do not have to join back to the blocker routing index. Each step also embeds the matching `execution_stage_detail` from its execution plan so dispatchers can see stage group, counts, arguments, next-step detail, and no-closure flags without reopening each plan; the record-gap step points to `use_record_gap_execution_plan`, the catalog/date-lineage evidence step points to `use_evidence_collection_execution_plan`, the manual-audit step points to `use_manual_audit_review_execution_plan`, and the business-owner step points to `use_business_owner_approval_execution_plan`. These work items and remediation-routing fields do not write records, execute calls, sample DuckDB, check lineage records, prove page/API execution, run smoke checks, capture approval, or approve formal use.

Current catalog/date-lineage queue boundary note: `next_closure_action_scope_audit` now checks the first closure pointer against `closure_execution_sequence[0]`, and `queue_boundary_audit` includes it as a distinct no-closure guard. Current validated snapshot: Snapshot counts are operational evidence from the current repository state; rerun the queue and its regression tests before treating them as current. The current all-seeded split is `3/15/14/5/2/2/4/1/4` across 50 checked assignment rows; this still grants no closure. Current queue state is 35 seeded pages, 29 review rows, 6 deferred rows, 13 ready/manual-review pages, 22 pages blocked by direct-record gaps, 22 `create_direct_record` remediation rows, and 13 `none` rows. Shared API records with a foreign `page_id`, `page_slug`, or `frontend_route` are supporting evidence only, not direct proof for the requested page.

Use `moss-lineage-evidence.get_page_lineage_evidence` when auditing whether a page has governance lineage records keyed directly by page ID, route, or API. It separates direct page/API records from expanded source-table, metric, golden-sample, or result-kind anchor records and returns conservative recommended next actions for the observed lineage status.

Use `moss-lineage-evidence.get_page_governance_record_requirements` before creating or reviewing direct page/API governance records. It returns required fields, required field groups such as `cache_key` or `run_id`, accepted direct page/API anchors plus structured `direct_anchor_targets` for `page_id`, `frontend_route`, `primary_api`, and `supporting_apis`, status-specific constraints, recommended metadata such as `result_kind`, and examples of insufficient evidence for seeded pages without writing records or granting approval.

Use `moss-lineage-evidence.validate_page_governance_records` after the requirements checklist to classify existing direct page/API governance records as ready for audit review, incomplete, missing, or supporting-anchor-only. Direct page/API records require exact structured field-value matches on accepted page IDs, frontend routes, primary APIs, or supporting APIs, so short route anchors such as `/` are not treated as substring matches against unrelated API paths. If a record declares `page_id`, `page_slug`, or `frontend_route`, at least one declared identity must match the requested page before a shared API can count as a direct record. Each direct validation row includes `direct_anchor_match` so reviewers can distinguish primary page/API anchors from `supporting_api` anchors; supporting-api-only or foreign-page-identity records stay blocked until a page ID, frontend route, or primary API anchor exists for the requested page. It reports missing required fields, failed required field groups, rejected foreign-identity direct candidates, and expanded anchor records separately. A ready result is field completeness only; it still does not prove page execution completeness or approve formal use.

Use `moss-lineage-evidence.get_page_governance_audit_review_checklist` after validation finds a field-complete direct record. It turns validation into a manual review checklist for page contract, catalog/date sampling, lineage freshness, current UI/API payload, live smoke evidence, and business-owner approval, and exposes direct-record `review_evidence_hints` such as report date, source/rule versions, table anchors, execution identifier, and live-smoke path for manual follow-up. A `ready_for_audit_review` result is still not closure or approval.

Use `moss-lineage-evidence.get_page_governance_audit_review_queue` when you need only the pages whose direct records are field-complete but still require manual audit review. It filters the checklist down to `ready_for_audit_review` pages, carries `remaining_manual_checks`, adds `manual_review_steps` with evidence-to-collect guidance, suggested tools, and page-aware `tool_calls` for each unresolved check, and preserves `closure_approved=false`; it is a review work queue, not an approval or closure mechanism.

Use `moss-lineage-evidence.get_page_governance_audit_evidence_packet` for one ready page when you want the MCP-backed review evidence in one payload. It aggregates the page trace bundle, contract trace summary, catalog/date evidence, lineage evidence, and audit-review queue item. When a field-complete direct record includes `live_smoke_evidence`, the packet reports it as `manual_review_evidence_present` with `evidence_present_needs_review` instead of treating that specific live-smoke evidence path as a missing manual blocker. Packet `manual_review_blocker_targets` turns unresolved UI/API payload and business-owner approval blockers into page/API/approval-record review targets for assignment, but it still does not run UI/API smoke checks, capture business-owner approval, write governance records, prove page/API execution, or approve formal use.

Use `moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue` when you want packets for every ready page in the selected scope. It filters to ready pages, returns one evidence packet per page, and summarizes remaining manual blockers plus any direct-record evidence that is present but still needs review; queue `summary` includes both `manual_review_blocker_count` and `manual_review_evidence_present_count`, `manual_review_evidence_present_work_items` for assignment-ready review of present evidence paths, `closure_readiness` for page-level closure routing, per-check breakdowns, per-check page lists for routing review work, `manual_review_mcp_work_items` for assignment-ready contract/catalog-date/lineage evidence collection calls, `manual_review_work_items` for assignment-ready UI/API payload, missing live-smoke evidence, and business-owner approval targets, `direct_record_remediation_work_items` for blocked-page record creation/repair routing, `blocked_by_record_gap_next_steps` plus next-step breakdown/page lists for page-level next remediation routing, `create_direct_record_table_anchor_work_items` for create-record table-anchor routing, `create_direct_record_evidence_work_items` and `repair_direct_record_evidence_work_items` for evidence-key-based batching of direct-record creation and repair fields/groups, and `blocked_by_record_gap_pages` for pages that must fix direct governance records before audit review. Blocked rows include direct/incomplete record counts, `remediation_type`, read-only `remediation_tool_calls` for requirements and blueprint collection, `repair_targets` for incomplete or supporting-anchor-only direct records so reviewers can see record locations, missing fields, failed field groups, current `formal_use_allowed` values, direct-anchor match details, field/group-level `evidence_hints`, and residual gaps without opening the full validation payload, `anchor_repair_target` for supporting-anchor-only records so reviewers can see the required primary page/API anchors and current supporting matches, and `creation_target` for missing direct records so reviewers can see the candidate page/API anchors, configured table anchors, manual-fill fields, per-field status, and evidence hints without opening the full blueprint payload; missing-record rows for pages with no direct table contract also include `table_anchor_resolution_target` so reviewers keep those pages out of direct table sampling and collect upstream/page-run evidence instead of inventing `tables_used`. The summary also includes remediation-type and next-step breakdowns with page lists so reviewers can distinguish create-direct-record work, complete-existing-record work, and primary page/API anchor repair. Supporting-anchor-only records route to primary page/API anchor repair even when they also have missing fields or failed field groups; field repair remains visible in the same repair target. `closure_readiness` rolls up ready, blocked, MCP-evidence-collection, manual-review, present-evidence-needs-review, and closure-approved counts, always with `queue_grants_closure=false`; it reports `manual_review_mcp_work_item_count` and adds `mcp_evidence_collection` to residual closure requirements when contract/catalog-date/lineage MCP evidence collection work remains, so it is a dispatch status, not approval. `manual_review_mcp_work_items` preserves the suggested `tool_calls` from the explicit MCP-evidence allowlist (`page_contract_review`, `catalog_date_sampling`, and `lineage_freshness_review`) without executing them, and `manual_review_mcp_scope_audit` checks those items for explicit no-write/no-approval/no-page-execution-proof/no-tool-execution scope; `manual_review_work_items` preserves the ready direct-record API target for UI/API payload review when it differs from the seeded contract API and exposes live-smoke review as a visible-state evidence target without running the smoke check, `manual_review_evidence_present_work_items` exposes direct-record evidence paths such as live-smoke artifacts as review-only rows, and `manual_review_scope_audit` checks both groups for explicit no-write/no-approval/no-page-execution-proof/no-smoke-run/no-approval-capture scope; `direct_record_remediation_work_items`, `blocked_by_record_gap_next_steps`, and `create_direct_record_table_anchor_work_items` preserve explicit no-write/no-approval/no-page-execution-proof/no-tool-execution/no-smoke-run/no-owner-approval-capture scope while making create-vs-repair and table-anchor work assignable from the summary; `create_direct_record_evidence_work_items` groups missing report date, basis, source/rule version, created timestamp, source surface, table anchor resolution, and execution-identifier evidence across create-direct-record pages without supplying substitute values; `repair_direct_record_evidence_work_items` groups missing/failed fields and field groups across existing-record repair and primary-anchor repair targets with record locations; `direct_record_remediation_scope_audit` checks those direct-record remediation groups, including `blocked_by_record_gap_next_steps`, for explicit no-write/no-approval/no-page-execution-proof/no-tool-execution/no-smoke-run/no-owner-approval-capture scope and counts every checked assignment row in `work_item_count`; `queue_boundary_audit` rolls the MCP, manual-review, and direct-record remediation scope audits into a queue-level guard for no-write/no-approval/no-execution/no-smoke/no-approval-capture drift; live-smoke checks remain in blocker/evidence-present classifications and are not executed by the queue. It still does not run UI/API smoke checks, execute suggested MCP calls, capture business-owner approval, write governance records, prove page/API execution, or approve formal use.

For `create_direct_record` rows, `creation_target.preflight_submission_template` packages the candidate record as a ready-to-call `moss-lineage-evidence.preflight_page_governance_record` request with manual placeholders. This is only a reviewer convenience for preflight validation; it does not execute the preflight call, write records, check record existence, prove page execution, or approve closure.

For `repair_primary_page_anchor` rows, `anchor_repair_target.preflight_repair_templates` repackages supporting-anchor-only records as candidate primary page/API records for preflight review. It preserves usable execution/source fields, replaces the page ID, route, and primary API with the seeded primary anchors, forces `formal_use_allowed=false`, and leaves any still-missing fields as manual placeholders. These templates are not record patches and are not executed by the queue.

For `complete_direct_record_fields` rows, each `repair_target.preflight_completion_template` packages the existing direct record as a candidate preflight call with invalid approval flags forced back to `formal_use_allowed=false` and missing execution/source fields left as manual placeholders. This helps reviewers validate a manually completed record before writing it; it does not patch the source record, fill missing evidence, or approve closure.

Use `moss-lineage-evidence.get_page_governance_record_blueprint` when preparing a candidate direct page/API governance record for manual review. It returns a read-only template populated from the seeded page trace bundle and explicit catalog/date table configuration, exposes structured `direct_anchor_targets`, lists manual-fill fields such as `report_date`, `basis`, source/rule versions, `created_at`, and `cache_key` or `run_id`, and embeds the current preflight result. The template intentionally does not write JSONL rows, check record existence, prove page execution, or approve formal use.

Use `moss-lineage-evidence.get_page_governance_record_blueprint_queue` after the gap queue when preparing many candidate direct page/API records for review. It attaches a blueprint and `candidate_record_readiness` explanation to each currently open gap in the default high-risk set or, with `all_seeded_pages=true`, every seeded page gap. The readiness explanation distinguishes create-direct-record work from complete-existing-record work, lists missing fields and failed field groups, includes `manual_fill_field_details` for required field/group status, adds `evidence_hints` to missing fields and failed execution-identifier groups so reviewers know which evidence source to consult, includes structured `direct_anchor_targets`, includes per-record `repair_targets` with field/group-level evidence hints for incomplete direct records, carries `expanded_anchor_samples` as supporting-only lineage hints for expanded-only gaps, preserves the gap ordering, and still does not write JSONL rows, check record existence, prove page execution, or approve formal use.

Use `moss-lineage-evidence.preflight_page_governance_record` before writing a candidate direct page/API governance record. It validates one supplied record against the page checklist, formal-use policy, accepted direct page/API anchors, and explicitly configured catalog/date table anchors when they exist, without writing JSONL rows, checking record existence, proving execution, or granting approval.

Use `moss-lineage-evidence.get_page_governance_gap_queue` to turn the validation results into a prioritized read-only action queue for the seeded high-risk pages. Pass `all_seeded_pages=true` when auditing every unique seeded page trace bundle. It highlights pages with neither direct nor expanded records before pages that only have expanded anchors, includes `expanded_anchor_samples` for supporting-only lineage hints, includes `direct_record_diagnostics` for incomplete direct records, and preserves the same no-write, no-execution-proof, no-approval boundary as the underlying validation tool.

Seeded pages:

- The current catalog/date-lineage seeded page universe is maintained by
  `product_page_trace_bundles()` and the `ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS`
  regression set in `tests/test_project_mcp_servers.py`.
- `dashboard-home`
- `product-category-pnl`
- `balance-analysis`
- `pnl`
- `pnl-bridge`
- `risk-tensor`
- `executive-overview`
- `concentration-monitor`
- `balance-movement-analysis`
- `pnl-by-business`
- `pnl-attribution`
- `operations-analysis`
- `liability-analytics`
- `bond-dashboard`
- `bond-analysis`
- `cube-query`
- `portfolio-home`
- `risk-home`
- `performance-home`
- `reports-home`
- `ledger-pnl`
- `positions`
- `market-data`
- `cross-asset`
- `platform-config`
- `news-events`
- `stock-analysis`
- `market-home`
- `executive-summary`
- `executive-pnl-attribution`
- `macro-toolkit`
- `macro-observation`
- `agent`
- `team-performance`
- `kpi-performance`

Default page scopes:

| Tool | Default scope |
| --- | --- |
| `moss-metric-contracts.get_page_evidence_readiness` | Seeded high-risk pages only |
| `moss-data-catalog.get_page_catalog_date_evidence` | Seeded high-risk pages only |
| `moss-data-catalog.get_page_catalog_date_lineage_review_queue` | Every catalog/date-lineage seeded page |

Boundary:

- The bundle is an evidence index only. It does not calculate metrics, inspect DuckDB rows, mutate data, or replace the contract documents it points to.
- The evidence-readiness matrix is an audit router only. It does not prove live catalog/date availability, read governance JSONL streams, approve dictionary-level `MTR-*` bindings, or replace direct calls to `moss-lineage-evidence`, `moss-data-catalog`, and `moss-data-quality`.
- Every seeded page should have an `approval_status_source="explicit_status_map"` entry. If a new page falls through to `unclassified_review_required`, add an explicit status before using the readiness matrix for audit closure.
- The page catalog/date evidence tool is sampled direct evidence only. It does not prove page/API execution, governance lineage, metric definition, data-quality approval, or formal-use approval.
- The page catalog/date coverage tool is a configuration gap router only. It does not sample DuckDB tables, does not prove table/date availability, and does not close catalog/date review without follow-up evidence sampling.
- The page catalog/date-lineage review queue is an assignment router only. It groups formal/governed pages, candidate formal-source mixes, GAP/observational pages, and deferred no-direct-table pages into review lanes with suggested follow-up MCP calls. Its `record_readiness` overlay is a copied direct-record validation status for progress visibility; it is not a lineage freshness check, page/API execution proof, or approval. Its `record_remediation` rows, `record_remediation_breakdown`, and `record_remediation_work_items` summarize read-only assignment metadata for ready rows, create-direct-record work, existing-record field completion, and primary page/API anchor repair; they do not create records, run preflight, execute suggested tools, or approve closure. `record_remediation_work_items` groups page slugs and read-only requirements/blueprint-queue calls for blocked-page assignment, and routes ready/manual-review rows to the audit-review queue and evidence-packet queue as suggested calls only. `record_remediation_evidence_work_items` groups the same blocked-page work by evidence key, such as direct page/API anchors, required record fields, execution identifiers, table-anchor resolution, and primary-anchor repair evidence, without supplying substitute values. `record_remediation_review_lane_work_items` cross-references review lanes with remediation types so P1 formal/governed and candidate formal-source work can be assigned without manually joining lane and remediation summaries. `record_gap_execution_plan` orders those three remediation groups into dispatcher stages and carries page-slug arguments for blocked pages, counts, and suggested-tool-call names, but it is still a plan over existing rows, not an executor. `record_gap_execution_plan_scope_audit` is included in `queue_boundary_audit` so plan-stage drift is visible with the other no-closure guards. `record_remediation_scope_audit` is a summary guard for those remediation, evidence, and lane-remediation work items only; it reports boundary drift and flags nested `suggested_tool_calls` outside the explicit read-only allowlist, but does not execute or repair anything. Its grouped `suggested_tool_call_work_items` merge call arguments for dispatch, while `suggested_tool_call_scope_audit` reports boundary drift or tools outside the explicit catalog/date-lineage allowlist. `evidence_collection_execution_plan` orders those suggested-call groups into dispatcher stages for catalog/date evidence, lineage evidence, governance validation, deferred catalog/date coverage, and deferred governance gap queues, and `evidence_collection_execution_plan_scope_audit` keeps that plan inside the same no-closure boundary. `manual_audit_review_execution_plan` orders ready/manual-review rows into dispatcher stages for audit-review queue and audit-evidence packet queue collection, and `manual_audit_review_execution_plan_scope_audit` keeps that plan inside the same no-closure boundary. `business_owner_approval_execution_plan` orders ready/manual-review rows into dispatcher stages for owner approval request batches and owner approval receipt review batches, and `business_owner_approval_execution_plan_scope_audit` keeps that plan inside the same no-closure boundary. `closure_readiness` keeps page closure separate from boundary cleanliness: it reports residual record-gap remediation, catalog/date-lineage evidence collection, manual audit review, business-owner approval, the closure-blocker assignment row count, closure-dispatch packet, closure-dispatch packet scope audit, and each blocker type's page/work-item counts, with zero queue-approved closures. Its `next_closure_action` points to the first unresolved blocker and matching next-step/execution-plan/stage key, currently `record_gap_remediation` through `record_gap_execution_plan` / `remediation_type_batches`; it also embeds that stage as `execution_stage_detail`, including `record_remediation_work_items`, stage counts, page-slug arguments, stage next-step, and no-closure scope. This is a dispatch pointer only and still keeps `queue_grants_closure=false`. `closure_blocker_work_items` makes those residual blockers assignment-ready without adding new authority, routes record-gap remediation to `use_record_gap_execution_plan`, routes catalog/date-lineage evidence collection to `use_evidence_collection_execution_plan`, routes manual audit review to `use_manual_audit_review_execution_plan`, routes business-owner approval to `use_business_owner_approval_execution_plan`, and carries matching next-step/execution-plan/stage keys plus matching `execution_stage_detail`; `closure_blocker_scope_audit` verifies those blocker rows and embedded stage details keep no-write/no-execution/no-sampling/no-smoke/no-approval-capture/no-page-approval scope and reports execution-target drift, including stale embedded stage type or work-item group detail, and it does not execute the referenced work, capture approval, or grant closure. `closure_execution_sequence` uses the same execution-plan pointers and embeds each matching execution stage detail, so record-gap dispatch stays on `use_record_gap_execution_plan` instead of falling back to raw remediation work items and each residual blocker remains readable without reopening the execution plans. `closure_dispatch_packet` repackages that sequence into ordered dispatcher rows, while `closure_dispatch_packet_scope_audit` checks packet-level and dispatch-row no-closure scope plus dispatch-target drift. `queue_boundary_audit` combines the record-gap execution-plan, remediation, suggested-call, evidence-collection execution-plan, manual-audit execution-plan, business-owner approval execution-plan, closure-blocker, next-closure action, and closure-dispatch packet guards, exposes per-audit work-item counts with the current 3/15/14/5/2/2/4/1/4 source split, aggregates closure-blocker execution-target drift plus next-action and closure-dispatch packet drift, and keeps `queue_grants_closure=false`. These audits still mark execution, sampling, lineage checks, page/API execution proof, smoke, owner-approval capture, and metric/page approval as false when clean. It does not run catalog/date sampling, lineage checks, validation, UI/API payload review, smoke checks, business-owner approval, record remediation, or formal-use approval.
- `closure_dispatch_packet` repackages `closure_execution_sequence` into ordered dispatcher rows with `dispatch_action`, execution-plan/stage keys, stage detail, page-slug arguments, source work-item group counts, and no-closure scope flags. It does not execute tools, write governance records, capture owner approval, or grant closure.
- `closure_dispatch_packet_scope_audit` checks the packet and each dispatch row for no-write/no-execution/no-sampling/no-lineage-check/no-smoke/no-approval-capture/no-page-approval drift and dispatch-target drift, including execution plan/stage/action, embedded stage-detail drift, dispatch-step count, pointer, sequence consistency, and source execution-sequence consistency, including missing or extra dispatcher rows.
- `queue_boundary_audit` also aggregates embedded stage-detail scope drift from `closure_blocker_scope_audit`, not only closure-blocker execution-target drift.
- `queue_boundary_audit` also aggregates next-closure-action and closure-dispatch packet consistency drift so a stale first-action pointer, top-level `dispatch_step_count`, `next_dispatch_step`, row `sequence`, or source execution-sequence copy cannot contradict the dispatcher rows silently.
- A `deferred_no_direct_table_config` page is not approved or closed; it means direct table sampling should wait until a page table contract exists and audit work should focus on upstream source pages, direct page/API governance records, visible no-data/stale/fallback states, and `result_meta`.
- Formal/governed seeded pages should have explicit catalog/date table configuration before their page-level evidence can be treated as ready for direct sampling review.
- The page lineage evidence tool is a governance-stream router only. Expanded anchor records and recommended next actions are useful audit guidance, but they must not be treated as proof of a specific page/API execution when direct page/API records are absent.
- The page governance-record requirements tool is a checklist only. It does not write JSONL rows, verify that a row exists, approve a metric/page, or prove page/API execution. Its accepted direct anchors are page IDs, frontend routes, primary APIs, and supporting APIs, exposed both as flat `accepted_direct_terms` and structured `direct_anchor_targets`; `result_kind` is recommended metadata, not a direct-anchor substitute.
- The page governance-record validation tool checks field completeness on existing direct records only. Direct-record lookup uses exact structured field-value matching for page/API anchors; validation rows expose whether the match was `page_id`, `frontend_route`, `primary_api`, or `supporting_api`. A supporting-api-only match is a record gap, not audit-review readiness, and repair targets carry `direct_anchor_match` so reviewers can see whether the remaining work is field completion or primary/page anchor repair. Expanded lineage lookup and generic lineage search can still surface supporting substring/query evidence, but those rows are not direct execution proof. It does not write JSONL rows, does not prove page/API execution completeness, and does not approve metric/page formal use.
- The page governance audit-review checklist tool routes manual review only. It can say records are ready for audit review by fields and can surface direct-record hints for the reviewer, but it does not check contract docs, sample catalog/date evidence, prove lineage freshness, inspect current UI/API payloads, verify live smoke evidence, capture business-owner approval, or approve closure.
- The page governance audit-review queue tool filters the checklist to field-complete direct records that still need manual review. `remaining_manual_checks` names the unresolved review categories and `manual_review_steps.tool_calls` gives read-only, page-aware suggested calls for evidence collection; it does not run those calls, perform the checks, prove page/API execution, write records, or approve closure.
- The page governance audit-evidence packet aggregates MCP-backed evidence for one ready page only. It can package contract, catalog/date, lineage, and queue evidence, but it still leaves UI/API smoke and business-owner approval as manual blockers and does not approve closure.
- The page governance audit-evidence packet queue batches the same packet shape over ready pages only. Its `closure_readiness` is a dispatch rollup only: it counts externally approved ready pages, keeps `queue_grants_closure=false`, and leaves pages blocked when record gaps, MCP evidence collection, manual review, present-evidence review, or business-owner approval remain unresolved. Its `manual_review_mcp_work_items` are assignment targets for contract/catalog-date/lineage MCP evidence collection, `manual_review_work_items` are assignment targets for human UI/API payload, missing live-smoke evidence, and business-owner review, `manual_review_evidence_present_work_items` are review-only targets for evidence paths already present in direct records, while `direct_record_remediation_work_items`, `blocked_by_record_gap_next_steps`, the next-step breakdown/page-list summaries, and `create_direct_record_table_anchor_work_items` are assignment targets for blocked direct-record creation, field completion, primary page/API anchor repair, or create-record table-anchor routing. `manual_review_mcp_scope_audit`, `manual_review_scope_audit`, `direct_record_remediation_scope_audit`, and queue-level `queue_boundary_audit` verify those work-item groups keep explicit no-write/no-approval/no-page-execution-proof/no-tool-execution/no-smoke/no-approval-capture scope, but they are summary guards only. These lists do not execute evidence collection, write records, sample catalog/date evidence, run smoke, capture approval, or grant approval. The queue does not package blocked pages as if they were review-ready, and it does not remove the packet-level manual blockers.
- Packet-queue `creation_target.preflight_submission_template` rows are preflight-call templates only. They carry blank execution/source placeholders forward from the blueprint so reviewers can validate a filled candidate later, but they do not fill those values, run smoke checks, check whether a governance row exists, write JSONL, or approve any page.
- Packet-queue `anchor_repair_target.preflight_repair_templates` rows are candidate preflight calls only. They do not mutate the original supporting-anchor records, do not prove that the supporting API evidence covers the primary page/API run, do not check whether a repaired record exists, and do not approve closure.
- Packet-queue `repair_target.preflight_completion_template` rows are candidate preflight calls only. They do not mutate existing direct records, do not fill missing rule/run evidence, do not check whether a completed record exists, and do not approve closure.
- Packet-queue `repair_direct_record_evidence_work_items` rows are assignment helpers for repairing existing or supporting-only direct records. They group missing fields and failed field groups by evidence key and record location, but they do not supply replacement values, patch JSONL rows, prove page execution, or approve closure.
- The page governance-record blueprint tool creates a candidate template only. It pre-fills stable page/API/table anchors and `formal_use_allowed=false`, leaves execution-specific evidence fields empty for manual proof, and does not write records, check existence, prove execution, or approve metric/page formal use.
- The page governance-record blueprint queue tool creates candidate templates and manual-fill explanations for open gaps only. Its `template_preflight_*` summary fields describe the blank candidate template preflight, `manual_fill_field_details` explains which required fields/groups are prefilled, missing, satisfied, or failed, and `evidence_hints` are read-only collection prompts for missing/failed items, not substitute values. `candidate_record_readiness.repair_targets` preserves per-record incomplete-direct-record fixes. Expanded anchor samples are marked `supporting_only=true` and `proves_page_execution=false`. It is a preparation queue, not a record writer or closure mechanism, and inherits the same no-write, no-existence-check, no-execution-proof, no-approval boundary.
- The page governance-record preflight tool validates a supplied candidate record only. The record must contain at least one accepted direct page/API anchor, and pages with explicit catalog/date table configuration must include at least one configured table anchor. Source-table and result-kind anchors are supporting evidence only. It does not write JSONL rows, does not check whether a record exists, does not prove page/API execution, and does not approve metric/page formal use.
- The page governance-gap queue is an action router only. Its expanded-anchor samples identify supporting source-table/result-kind lineage hints, falling back to the matched query when the raw record lacks explicit anchor fields, and its incomplete-record diagnostics identify missing fields and failed field groups for follow-up. It does not create missing records, does not prove that expanded anchors belong to a page execution, and does not close audit review by itself.
- For `dashboard-home`, `/ui/home/snapshot` is the primary evidence source. Supplemental dashboard, bond, market, and calendar surfaces must stay visibly supplemental and date-gated where the cockpit contract requires it.
- For the `PAGE-DASH-001` supporting API `/ui/home/macro-release-context`, MCP-unavailable work must record the unavailable server and the local substitute evidence; unresolved items remain `source_pending`. Local evidence cannot grant formal approval or justify static historical numeric fallback.
- For `product-category-pnl`, row meaning must stay tied to the paired ledger reconciliation + daily average source chain. Do not infer page rows from ZQTZ holdings-side logic or research buckets.

### Coverage Matrix

| Page slug | Route | Primary API | Trace bundle | Golden sample status | Known gaps |
| --- | --- | --- | --- | --- | --- |
| `dashboard-home` | `/`, `/dashboard` | `/ui/home/snapshot` | seeded | Executive sub-surface samples only: `GS-EXEC-OVERVIEW-A`, `GS-EXEC-PNL-ATTR-A`, `GS-EXEC-SUMMARY-A` | Aggregate homepage remains analytical/mixed-source; no full-page formal golden sample. |
| `product-category-pnl` | `/product-category-pnl` | `/ui/pnl/product-category` | seeded | `GS-PROD-CAT-PNL-A` | Standalone `as_of_date` remains an explicit contract gap. |

### Onboarding Checklist

When adding another page trace bundle, include all of:

- `page_slug`, `page_id`, `page_name`, route aliases, `frontend_route`, and `primary_api`.
- Supporting APIs, contract docs, truth chain, backend touchpoints, frontend touchpoints, test touchpoints, and golden samples.
- `verification_focus` entries for unit consistency, precision, null-vs-zero, date semantics, stale/fallback state, and `result_meta` visibility.
- `guardrails` that say what must not be inferred or promoted.
- A dry-run entry in `scripts/codex-verify-page.ps1`, a smoke checklist in `scripts/codex-page-smoke.ps1`, and assertions in `tests/test_project_mcp_servers.py`.

### Fallback Rules

If a client session cannot directly call the `moss-*` MCP tools, use the local docs, tests, DuckDB catalog helpers, and governance JSONL streams as fallback evidence only after checking the local MCP registration. The final work report must say which MCP server was unavailable and what local evidence substituted for it. Do not convert a missing MCP response into a metric definition, source lineage claim, or formal sample approval.

## Codex Page Helpers

Use the local helper scripts after the trace bundle has identified the page surface.

Dry-run the verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl
```

For the homepage cockpit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug dashboard-home
```

Run the page-specific verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run
```

Run the unified page-readiness gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug product-category-pnl
```

The readiness gate first evaluates the page trace bundle and evidence-readiness
matrix, then prints residual gaps, static evidence gates, smoke checklist, and
required verification command. Pass `-Run` to execute the checklist wrapper and
page-specific verification plan when local helpers are wired for that page:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug product-category-pnl -Run
```

Audit every seeded trace-bundle page in one dry run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -All
```

`-All` reports one row per seeded page, including mixed/candidate/formal status,
golden-sample boundary, static blockers, and whether local smoke/verify helpers
are wired. Batch dry-run is read-only and may surface blocking pages without
failing the command; `-Run` fails closed if static blockers remain and only runs
local page checks for rows with `run_supported=true`.

Emit the page smoke checklist:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl
```

For the homepage cockpit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug dashboard-home
```

The smoke helper intentionally prints the route, governed API, expected visible states, and Playwright MCP checklist. It does not replace browser verification or add a new browser automation dependency.

## Local Verification

Confirm Codex can see the configured MCP servers:

```powershell
codex mcp list
```

Run the local MCP contract tests:

```powershell
pytest tests/test_project_mcp_servers.py -q
```

Optional syntax check that does not write `__pycache__`:

```powershell
python -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/mcp/moss_project_mcp.py').read_text(encoding='utf-8')); print('syntax ok')"
```

## GitNexus Index

The `.mcp.json` config enables the GitNexus MCP server through a local GitNexus 1.3.11 install under `.tmp-gitnexus-v13/`.

The `.gitnexus/` index has been generated for this workspace. At the time of indexing it contained:

- 1,429 files
- 10,347 nodes
- 32,344 edges
- 874 communities
- 300 processes

GitNexus records the index metadata in `.gitnexus/meta.json`.

Re-index from the repository root with:

```powershell
node .tmp-gitnexus-v13\node_modules\gitnexus\dist\cli\index.js analyze .
```

Troubleshooting:

- The latest `gitnexus@latest` package currently fails in this Windows workspace with either `EPERM: operation not permitted, symlink ... tree-sitter-proto` or native dependency load/build errors. The local GitNexus 1.3.11 install avoids that path and is the configured MCP/runtime command.
- If re-indexing fails with access denied on `.gitnexus/kuzu.wal`, stop any active GitNexus process and rerun the command from the repository root.
- `.gitnexus/` and `.tmp-gitnexus-v13/` are local generated/runtime directories and are ignored by git.
