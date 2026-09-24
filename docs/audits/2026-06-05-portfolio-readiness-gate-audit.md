# /portfolio Readiness Gate Audit - 2026-06-05

## Scope

This audit covers the `/portfolio` module home readiness gate, cross-page real-data consistency checks, and local MOSS MCP evidence used to decide whether the page may show decision-grade or same-day risk-closure wording.

No backend service, API schema, DuckDB schema, database data, auth, scheduler, or shared infrastructure was changed for this pass.

## Gate Contract

`/portfolio` is a module home and drilldown surface. It can render available real values when core data is present, but it must fail closed for decision-grade claims.

The page now separates three concerns:

- `coreRender`: existing core values can be displayed.
- `decisionReady`: the page may present a decision-grade conclusion.
- `riskClosureReady`: the page may say risk tensor evidence is same-day closed.

Decision anchor:

```text
bondHeadline.result.report_date ?? bondDates.result.report_dates[0]
```

Decision evidence must satisfy all of the following for bond headline, bond risk, balance overview, and PnL summary:

- payload data exists;
- payload `result.report_date` equals the anchor date;
- `result_meta.requested_report_date`, `result_meta.resolved_report_date`, and `result_meta.as_of_date` exist and equal the anchor date;
- `basis=formal`;
- `formal_use_allowed=true`;
- `quality_flag=ok`;
- `fallback_mode=none`;
- no `fallback_date`.

Risk closure additionally requires:

- `riskDates.result.report_dates` contains the anchor date;
- `riskDates.result_meta` is formal, ok, no fallback, and all relevant meta dates equal the anchor date.

`bondPortfolioComparison` remains a sub-portfolio drilldown input only. It does not block core render or decision evidence readiness.

## Implementation Evidence

Relevant files:

- `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
- `frontend/src/features/workbench/module-home/portfolioReadinessGate.ts`
- `frontend/src/features/workbench/module-home/portfolioDecisionModel.ts`
- `frontend/src/features/workbench/module-home/usePortfolioHomeQueries.ts`
- `frontend/src/test/PortfolioReadinessGate.test.ts`
- `frontend/src/test/PortfolioDecisionModel.test.ts`
- `frontend/src/test/PortfolioHomeCrossPageConsistency.test.tsx`
- `frontend/src/test/portfolioCrossPageGoldenSample.ts`
- `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`
- `frontend/src/test/ModuleWorkbenchHomePage.test.tsx`
- `frontend/src/test/BondDashboardPage.test.tsx`
- `frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts`
- `tests/golden_samples/GS-PORTFOLIO-HOME-A/`
- `tests/test_golden_samples_capture_ready.py`
- `scripts/portfolio_home_risk_warning_consistency.py`
- `tests/test_portfolio_home_risk_warning_consistency.py`
- `scripts/portfolio_home_krd_remap_review_queue.py`
- `tests/test_portfolio_home_krd_remap_review_queue.py`
- `scripts/portfolio_home_maturity_remediation_queue.py`
- `tests/test_portfolio_home_maturity_remediation_queue.py`
- `scripts/mcp/moss_project_mcp.py`

Cross-page hardening added a shared golden sample for `/portfolio`, `/bond-dashboard`, and `/balance-analysis` tests. The sample proves that the portfolio home renders bond market value, duration, DV01, bond count, balance asset/liability values, and PnL driver evidence from the same page-source fixtures and unit conversions.

## Local MCP Evidence

The Codex App tool panel did not directly expose the project MOSS/GitNexus MCP tools, so this pass used the repository-local read-only stdio MCP implementation in `scripts/mcp/moss_project_mcp.py`.

Read-only calls executed:

```text
moss-metric-contracts.get_page_trace_bundle({"page_slug":"PAGE-PORTFOLIO-HOME-001"})
moss-metric-contracts.get_page_evidence_readiness({"page_slugs":["PAGE-PORTFOLIO-HOME-001"]})
moss-data-catalog.get_page_catalog_date_evidence({"page_slugs":["PAGE-PORTFOLIO-HOME-001"],"limit":5})
moss-lineage-evidence.get_page_lineage_evidence({"page_slugs":["PAGE-PORTFOLIO-HOME-001"],"max_results":3})
moss-lineage-evidence.validate_page_governance_records({"page_slugs":["PAGE-PORTFOLIO-HOME-001"]})
moss-lineage-evidence.preflight_page_governance_record({"page_slug":"PAGE-PORTFOLIO-HOME-001","record":<candidate>})
```

Evidence obtained:

- Contract trace resolves `PAGE-PORTFOLIO-HOME-001` to route `/portfolio` and primary API `frontend aggregation: module-home/portfolio`.
- The trace now includes `/api/risk/tensor/dates`, `risk.tensor.dates`, `fact_formal_risk_tensor_daily`, and `backend/app/api/routes/risk_tensor.py`, matching the real risk-closure gate dependency.
- Readiness status remains `mixed_source_or_observational`; `formal_use_allowed=false`.
- Readiness checks show trace bundle present, lineage mapping present, catalog/date direct review required, and `GS-PORTFOLIO-HOME-A` registered as supporting-only governance evidence.
- Catalog/date evidence found 8 sampled table anchors for Portfolio Home.

Sampled table dates:

```text
fact_formal_zqtz_balance_daily      2026-05-31, 2026-04-30, ...
fact_formal_tyw_balance_daily       2026-05-31, 2026-04-30, ...
fact_formal_bond_analytics_daily    2026-05-31, 2026-04-30, ...
zqtz_bond_daily_snapshot            2026-05-31, 2026-04-30, ...
tyw_interbank_daily_snapshot        2026-05-31, 2026-04-30, ...
fact_formal_pnl_fi                  2026-05-31, 2026-04-30, ...
fact_nonstd_pnl_bridge              2026-05-31, 2026-04-30, ...
fact_formal_risk_tensor_daily       2026-05-31, 2026-04-30, ...
```

Decision impact:

- All 8 configured table anchors include `2026-05-31`.
- The risk tensor dates evidence now includes `2026-05-31`, and the dates envelope `result_meta` date fields also align to `2026-05-31`.
- Therefore `/portfolio` may say risk tensor date evidence is same-day closed for the `2026-05-31` anchor.
- This does not promote the downstream `2026-05-31` risk tensor payload to full decision-grade closure, because that payload remains warning-quality evidence.
- This matches the frontend gate behavior: `riskClosureReady=true` for same-day date evidence, while decision-grade wording remains blocked unless every required formal/ok/no-fallback evidence source closes.

## Governance Preflight

A candidate primary page governance record was preflighted with:

- `page_id=PAGE-PORTFOLIO-HOME-001`
- `frontend_route=/portfolio`
- `primary_api=frontend aggregation: module-home/portfolio`
- `report_date=2026-05-31`
- `basis=mixed_source_or_observational`
- all 8 configured table anchors
- `formal_use_allowed=false`
- `decision_anchor_date=2026-05-31`
- `risk_report_date=2026-05-31`
- `risk_result_meta_date=2026-05-31`
- `risk_closure_ready=true`

Preflight result:

```text
validation_status=ready_for_audit_review
missing_required_fields=[]
failed_required_field_groups=[]
direct_anchor_match=PAGE-PORTFOLIO-HOME-001
formal_use_allowed=false
```

The record was not written to `data/governance/cache_manifest.jsonl` in this pass because preflight validates checklist fields only. It does not prove page execution completeness, does not check record existence, does not grant formal approval, and does not replace business-owner sign-off.

## Verification

Frontend focused verification passed on the current worktree:

```text
npm.cmd run test -- src/test/PortfolioReadinessGate.test.ts src/test/PortfolioDecisionModel.test.ts src/test/PortfolioHomeCrossPageConsistency.test.tsx src/test/ModuleWorkbenchHomeModel.test.ts src/test/ModuleWorkbenchHomePage.test.tsx src/test/parseEnvMode.test.ts src/test/BondDashboardPage.test.tsx src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts
```

Result: 8 test files passed, 157 tests passed.

Frontend broad checks previously passed:

```text
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run debt:audit
npm.cmd run build
```

Result: all passed; frontend debt audit reported no baseline growth.

Focused MCP checks passed on the current worktree:

```text
python -m pytest tests/test_project_mcp_servers.py::test_module_home_trace_bundles_preserve_downstream_truth_boundaries tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_coverage_configures_seeded_pages_with_clear_table_anchors tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_evidence_samples_known_page_tables tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_module_home_pages_to_downstream_read_records -q
```

Result: 8 tests passed.

Portfolio supporting-sample checks passed on the current worktree:

```text
python -m pytest tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim tests/test_project_mcp_servers.py::test_metric_contracts_mcp_exposes_seeded_page_trace_bundles tests/test_project_mcp_servers.py::test_module_home_trace_bundles_preserve_downstream_truth_boundaries tests/test_project_mcp_servers.py::test_metric_contracts_evidence_readiness_has_explicit_status_for_every_seeded_page -q
```

Result: 29 tests passed.

At the audit's 2026-06-05 execution point, portfolio full-closure evidence checks passed with the then-current queues below. These observed counts are historical and are not the current owner-action contract:

```text
python -m pytest tests/test_portfolio_home_risk_warning_consistency.py tests/test_portfolio_home_krd_remap_review_queue.py tests/test_portfolio_home_maturity_remediation_queue.py tests/test_portfolio_home_full_closure_evidence.py tests/test_portfolio_home_signoff_packet.py -q
```

Result: targeted risk-warning consistency, KRD queue, maturity queue, evidence, and sign-off tests passed when last run for this audit packet.

The risk warning consistency check was read from DuckDB in `read_only=True` mode:

```text
python scripts/portfolio_home_risk_warning_consistency.py --require-consistent
python scripts/portfolio_home_risk_warning_consistency.py --require-clean
```

Observed result:

```text
warning_consistency_status=consistent
decision_status=blocked
decision_blockers=risk_tensor_quality_warning
duration_exclusion row_count=120, market_value_sum=38318400505.50000008, missing_maturity_rows=114, nonpositive_duration_rows=6
bond_liquidity_gap missing_maturity_rows=114
tyw_liability_liquidity_gap missing_maturity_rows=1455
krd_buckets=20Y, 2Y, 6M
```

The consistency gate passes because the warning text reconciles to recomputed DuckDB facts. The clean gate exits non-zero because `quality_flag=warning` still blocks decision-grade closure.

The KRD remap review queue was read from DuckDB in `read_only=True` mode:

```text
python scripts/portfolio_home_krd_remap_review_queue.py --limit 5
python scripts/portfolio_home_krd_remap_review_queue.py --limit 5 --require-clean
```

Observed result:

```text
review_status=decision_required
review_blockers=krd_contract_decision_required
20Y all_rows=39, nonzero_dv01_rows=39, dv01_sum=23598290.06912522, mapped_to=krd_30y
2Y all_rows=301, nonzero_dv01_rows=301, dv01_sum=9037781.19296191, mapped_to=krd_3y
6M all_rows=282, nonzero_dv01_rows=160, dv01_sum=544906.37425771, mapped_to=krd_1y
largest_dv01_sample=200004, dv01=8246445.66600614, tenor_bucket=20Y, mapped_to=krd_30y
```

The strict KRD clean gate exits non-zero until the nearest-bucket tensor contract is formally approved or the KRD schema/API is expanded to exact tenor buckets.

The maturity remediation queue was read from DuckDB in `read_only=True` mode:

```text
python scripts/portfolio_home_maturity_remediation_queue.py --limit 3
python scripts/portfolio_home_maturity_remediation_queue.py --limit 3 --require-empty
```

Observed result:

```text
remediation_status=blocked
remediation_blockers=bond_maturity_queue_not_empty, tyw_liability_maturity_queue_not_empty
bond_missing_maturity_rows=114
bond_missing_maturity_market_value=37622164239.83000008
tyw_liability_missing_maturity_rows=1455
tyw_liability_missing_maturity_principal=43822652393.01000002
```

The strict empty gate exits non-zero until the upstream missing-maturity rows are remediated or formally approved as a scoped exclusion.

Risk tensor date metadata checks passed after the `2026-05-31` materialization and dates-envelope metadata update:

```text
python -m pytest tests/test_risk_tensor_service.py::test_risk_tensor_dates_envelope_uses_risk_tensor_manifest_lineage tests/test_risk_tensor_service.py::test_risk_tensor_dates_envelope_falls_back_to_upstream_source_version_when_manifest_missing tests/test_risk_tensor_service.py::test_risk_tensor_dates_envelope_blocks_stale_report_dates tests/test_risk_tensor_api.py::test_risk_tensor_api_returns_available_report_dates tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim -q
```

Result: 5 tests passed.

Risk tensor KRD remap regression checks passed after adding the governed `6M -> 1Y` nearest-bucket mapping:

```text
python -m pytest tests/test_risk_tensor_core.py tests/test_risk_tensor_service.py::test_risk_tensor_service_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial tests/test_risk_tensor_api.py::test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial -q
```

Result: 18 tests passed.

The official `2026-05-31` risk tensor materialization was rerun with:

```text
run_id=codex_portfolio_risk_tensor_20260531_20260605_6m_krd_remap
status=completed
bond_count=1710
quality_flag=warning
```

Post-materialization fact-row check:

```text
portfolio_dv01=105628442.39590558
krd_sum=105628442.39590558
krd_1y=6248583.14700401
```

The prior `6M` unsupported-bucket exclusion is removed. The remaining warning boundary is now:

- `20Y`, `2Y`, and `6M` are nearest-bucket KRD remaps;
- 120 bond rows with market value are excluded from duration denominator;
- 114 bond rows lack maturity date for liquidity-gap projection;
- 1455 liability rows lack maturity date for liquidity-gap projection.

Governance review queue checks were also run because the lineage/query expansion changed:

```text
python -m pytest tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_prioritizes_formal_source_mix tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_summarizes_all_seeded_lanes tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_suggested_call_work_items tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_audits_queue_boundary tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_summarizes_closure_readiness tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_work_items tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_evidence_work_items tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_by_lane tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_audits_record_remediation_scope -q
```

Result: 9 tests passed.

## Live Page Fallback Proof

The live `/portfolio` page was rechecked on the current local services with headless Playwright as a fallback proof path. The Browser plugin / Playwright MCP path was not available in this Codex App pass, so this evidence should be treated as runtime smoke evidence, not as a full in-app browser governance capture.

Local connectivity:

```text
200 http://127.0.0.1:5888/portfolio
200 http://127.0.0.1:7888/api/risk/tensor/dates
200 http://127.0.0.1:7888/api/bond-dashboard/dates
200 http://127.0.0.1:7888/ui/balance-analysis/dates
```

Headless page proof:

```text
target=http://127.0.0.1:5888/portfolio
selectors present:
  module-workbench-home=1
  module-home-toolbar=1
  module-home-decision=1
  module-home-kpi-strip=1
  module-home-status-strip=1
  module-home-portfolio-terminal=1
  module-home-portfolio-risk=1
  module-home-data-note=1
api statuses:
  /ui/balance-analysis/dates=200
  /api/bond-dashboard/dates=200
  /ui/balance-analysis/overview=200
  /api/risk/tensor/dates=200
  /api/bond-dashboard/risk-indicators=200
  /ui/balance-analysis/summary-by-basis=200
  /api/pnl-attribution/summary=200
  /api/bond-dashboard/home-summary=200
console_errors=0
```

Decision-boundary checks:

```text
analysis_only_conclusion=true
same_day_risk_closure=true
no_frontend_formal_metric_fill=true
warning_boundary_visible=true
```

The live page therefore proves that the current UI keeps the correct boundary: it displays real values and same-day risk-date closure evidence, but still downgrades the decision conclusion to analysis-only because the bond-dashboard evidence is `basis=analytical` / `quality=warning` and the risk tensor payload is not fully decision-grade.

## Current Score

Current score: 99.86 / 100.

Remaining gap to full score: 0.14.

What is now strong:

- frontend decision gate fails closed;
- payload and `result_meta` dates must both match the anchor;
- formal/ok/no-fallback checks are enforced;
- risk closure is separated from decision evidence;
- risk tensor dates now include the `2026-05-31` portfolio anchor and the dates-envelope metadata is date-aligned;
- `6M` tenor DV01 is no longer excluded from the KRD tensor; it maps to the nearest supported `1Y` bucket and the KRD total reconciles to portfolio DV01;
- `GS-PORTFOLIO-HOME-A` observes `risk_closure_ready=true` for same-day risk date evidence while staying supporting-only;
- live `/portfolio` fallback proof now verifies the main module regions, eight key read APIs, no console errors, analysis-only conclusion, same-day risk-date wording, and no frontend formal-metric fill;
- cross-page frontend values are fixture-aligned;
- MCP trace/catalog evidence now includes the risk-date dependency;
- `GS-PORTFOLIO-HOME-A` is registered as a supporting-only governance sample for the portfolio module home;
- a primary `/portfolio` governance record candidate preflights as ready for audit review.

Authoritative score blockers from the scorecard:

- `risk_tensor_quality_warning`, `krd_contract_decision_required`, `bond_matured_outstanding_reconciliation_required`, `tyw_liability_maturity_date_remediation_required`, `business_owner_approval`, and `owner_decision_intake_blocked`.

What still prevents 100:

- `risk_tensor_quality_warning`: the downstream `2026-05-31` risk tensor payload remains `quality_flag=warning`, so same-day date evidence cannot be restated as full risk-tensor decision closure;
- `krd_contract_decision_required`: the KRD tensor still depends on nearest-bucket remaps for `2Y`, `6M`, and `20Y`; this needs either an explicit business approval of the minimal-bucket tensor or a formally expanded KRD schema;
- `bond_matured_outstanding_reconciliation_required`: six matured non-zero bond positions remain and must be reconciled at source; exception evidence cannot close this blocker;
- `tyw_liability_maturity_date_remediation_required`: source TYW liability facts still lack maturity dates for material liability balances, so liquidity-gap evidence remains incomplete;
- `business_owner_approval`: business-owner approval is not present, so the page cannot claim full page-level formal closure;
- `owner_decision_intake_blocked`: risk-owner CSV decisions, nearest-bucket approval or exact-bucket schema evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval have not all been reconciled by the owner-decision intake gate.

Residual evidence risks, not independent score blockers:

- no primary `/portfolio` governance record was written because capture-ready payload parity and owner approval are not proven;
- `GS-PORTFOLIO-HOME-A` remains supporting-only; it proves neither capture-ready payload parity nor owner approval.
- GitNexus evidence was unavailable through this Codex App pass and should be rerun when the MCP surface is exposed; it does not replace or add to the current six score blockers.

## Full-Closure Handoff Packet

The remaining `0.14` gap has been converted into a review packet and an owner/risk-owner approval template:

- `docs/portfolio/portfolio-home-full-closure-sign-off-packet.md`
- `docs/portfolio/portfolio-home-business-owner-approval-template.md`
- `scripts/portfolio_home_full_closure_evidence.py`
- `scripts/portfolio_home_risk_warning_consistency.py`
- `scripts/portfolio_home_krd_remap_review_queue.py`
- `scripts/portfolio_home_krd_contract_decision_export.py`
- `scripts/portfolio_home_maturity_remediation_queue.py`
- `scripts/portfolio_home_maturity_remediation_export.py`
- `scripts/portfolio_home_closure_artifact_presence_check.py`
- `scripts/portfolio_home_evidence_packet_guard.py`
- `scripts/portfolio_home_closure_scorecard.py`
- `scripts/portfolio_home_evidence_snapshot.py`
- `scripts/portfolio_home_owner_action_packet.py`
- `scripts/portfolio_home_business_owner_approval_packet.py`
- `scripts/portfolio_home_dependency_consistency_check.py`
- `scripts/portfolio_home_owner_decision_intake_check.py`
- `scripts/check_portfolio_home_business_owner_approval.py`

The scorecard combines the full-closure evidence, risk-warning consistency gate, KRD review queue, maturity remediation queue, matured-outstanding reconciliation gate, business-owner approval status, owner-decision intake, approval-dependency consistency, and verification command coverage. It currently reports `score_status=blocked`, `full_score_ready=false`, `current_score=99.86 / 100`, and `remaining_gap=0.14`; its strict full-score mode exits non-zero until every listed blocker is closed. Its `score_blocker_actions` output maps each blocker to an owner, next action, evidence command, and exit criteria so the review queue can move without changing the score logic. Its `gates.krd_contract` and `gates.maturity_remediation` entries also carry the queue-level action maps and scope fields.

The score method is `discrete_full_closure_gate`. The `0.14` remaining gap is a full-score readiness gap, not a linear sum of blocker weights, and must not be allocated across `risk_tensor_quality_warning`, `krd_contract_decision_required`, `bond_matured_outstanding_reconciliation_required`, `tyw_liability_maturity_date_remediation_required`, `business_owner_approval`, or `owner_decision_intake_blocked` as pseudo-precision.

The scorecard also emits a machine-readable `verification_commands` list. It carries `score_blocker_action_coverage.status=clean` for the current blocker set; unknown or unassigned score blockers prevent strict activation. Evidence and regression commands are expected to exit 0 in the current blocked state, while strict gates such as `portfolio_home_full_closure_evidence.py --require-clean`, `portfolio_home_closure_scorecard.py --require-full-score`, and `check_portfolio_home_business_owner_approval.py --require-captured` are expected to exit non-zero until blockers close.

`scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current` verifies that the KRD decision export, maturity remediation export, business-owner approval template, and conditional nearest-bucket approval, exact-bucket schema, or scoped-exclusion evidence are present/current for the report date. `scripts/portfolio_home_evidence_packet_guard.py --require-clean` then verifies that the evidence snapshot, owner handoff packet, and sign-off packet explicitly carry that artifact-presence command and currentness summary. This proves packet freshness only; it does not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.

`scripts/verify_portfolio_home_scorecard_commands.py --require-matched` executes the allowlisted verification command set without shell expansion and compares each return code to the scorecard's blocked-state expectation. In the current evidence state it should report `verification_status=matched_expected_blocked_state`.

The same runner also supports `--expected-state full_score` for future closure reviews. Under the current evidence, full-score strict-gate expectations intentionally mismatch because clean data and full-page approval are not yet present.

`scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched` is the compact review entry point. It packages the scorecard, gate summary, score methodology, blocker action map, business owner approval packet summary, and verifier result into one JSON object. In the current real-data state it must still report `snapshot_kind=portfolio_home_closure_evidence`, `score_status=blocked`, `full_score_ready=false`, `business_owner_approval_packet_summary`, and `verification_status=matched_expected_blocked_state`; it does not approve full closure or change the `99.86 / 100` score. The compact snapshot also exposes the business-owner packet status, activation readiness, action-item count, and dependency-consistency status so stale or mismatched approval dependencies are visible from the first review artifact. The compact snapshot also exposes CSV row-count and blank owner-field status. The compact snapshot gate summary now exposes `owner_decision_intake_status=pending`, `owner_decision_intake_ready=false`, and the current owner-decision blockers. The compact snapshot gate summary now exposes `approval_dependency_consistency_status=consistent`, dependency blockers, and `generated_owner_fields_boundaries` from the scorecard gate. The compact snapshot now exposes `owner_decision_intake_summary` so reviewers can see owner-decision blockers from the first JSON artifact. The compact snapshot owner-decision intake summary now exposes `csv_check_summary` and `generated_owner_fields_boundaries`, so intake reviewers see queue row counts and generated-owner boundaries without opening the dependency check. The compact snapshot owner-decision intake summary now exposes `owner_input_boundary`, so filled owner CSV fields are visible as owner input rather than generated approval evidence. The compact snapshot now exposes `scorecard_owner_decision_intake_gate_summary` and `owner_decision_intake_alignment` so direct intake evidence is checked against the full-score gate view. The compact snapshot scorecard owner-decision gate summary now carries `owner_input_boundary`, and the alignment comparison includes it. The compact snapshot now exposes `decision_gap_counts` so reviewers can see KRD owner decision gaps of 503 rows and maturity owner decision gaps of 1455 rows (bond 0, TYW liability 1455) without opening the CSV queues. The compact snapshot now exposes `note_gap_counts`; current real CSVs have blank owner decisions, so note/comment gaps are empty until a decision is filled without rationale. The compact snapshot now exposes `exact_bucket_schema_evidence` so reviewers can see whether the exact-bucket schema path has metric-contract, API-schema, rematerialization, and verifier evidence. The compact snapshot now exposes `score_blocker_action_coverage` in both the gate summary and business-owner approval packet summary. The compact snapshot now exposes `owner_summary_paths` so reviewers can find KRD and maturity owner summaries without opening the full approval packet. The compact snapshot now exposes `generated_owner_fields_boundaries`; both KRD and maturity export manifests must carry `generated_owner_fields_must_be_blank=true`.

`scripts/portfolio_home_owner_action_packet.py --limit 3` is the owner handoff entry point. It groups the remaining blockers into `risk_owner`, `data_owner`, and `business_owner` packets, preserving the same score blockers and evidence commands. In the current real-data state it must report `handoff_status=owner_actions_required` and `assignment_coverage.status=clean`, with no unassigned, duplicate-assigned, or unexpected-assigned blockers; owner packets now carry `dependency_consistency_status=consistent` plus the shared CSV summary. The owner handoff Markdown now surfaces CSV row counts, blank owner-field status, generated-owner manifest boundaries, and export-current system-field gate in the summary before the checklist. The owner handoff Markdown now states export-current system fields prove package freshness only and do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure. The owner packets now carry KRD `note_gap_counts`, maturity `comment_gap_counts`, and `exact_bucket_schema_evidence` without changing approval status. The owner packets now carry `owner_decision_intake_alignment.status=consistent` so owners can see activation evidence alignment before signing. The current owner packets assign `owner_decision_intake_blocked` to the business owner; if dependency drift appears, they also assign `approval_dependency_consistency_blocked` so fallback blockers cannot be left unowned. Its strict clean mode exits non-zero until every owner packet is clean; strict clean mode also requires `score_blocker_action_coverage.status=clean`.

`scripts/portfolio_home_business_owner_approval_packet.py --limit 3` is the business-owner approval packet entry point. It packages the pending approval template status, 19 approval action items, evidence dependencies, and activation guard without changing approval fields. In the current real-data state it must report `packet_status=pending`, `activation_ready=false`, `approval_action_item_count=19`, and `dependency_consistency_status=consistent`. Its manifest consistency checks block stale or mismatched KRD and maturity exports by comparing the KRD report date, export status, remap tenor count, nonzero DV01 row count, and DV01 sum, plus the maturity report date, export status, missing row counts, market value, and principal totals. CSV consistency checks block row-count drift and any prefilled owner/proposed fields in the KRD or maturity export files, so review queues cannot be mistaken for signed decisions or frontend-filled remediation. The business-owner approval packet now carries `note_gap_counts` and `exact_bucket_schema_evidence` as review evidence, not approval evidence. The business-owner approval packet now lists the KRD and maturity owner summaries as dependencies without treating either summary as signed approval. The business-owner approval packet now exposes the scorecard `gates.owner_decision_intake` summary so approval review can compare direct intake evidence with the full-score gate view. The business-owner approval packet scorecard gate summary also carries `owner_input_boundary`, and activation alignment compares it before approval. The business-owner approval packet now enforces `owner_decision_intake_alignment.status=consistent` before activation. The business-owner approval packet now enforces `score_blocker_action_coverage.status=clean` before activation. The business-owner approval packet now exposes `generated_owner_fields_boundaries` directly so the approval entry point shows the generated-owner-field blank boundary without relying on the compact snapshot. Its guard records no automatic approval, invalid partial activation, and strict scorecard approval gates; business-owner activation guard also requires dependency consistency and owner decision intake strict gates. Its `--require-ready` mode exits non-zero until the approval template, strict scorecard, manifest consistency, owner-decision intake, and dependency evidence are all ready.

`scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent` is the standalone approval-dependency consistency gate. It returns the same KRD and maturity manifest checks used by the scorecard and business-owner approval packet, plus a compact CSV summary. It now exposes `generated_owner_fields_boundaries` directly, matching the scorecard and business-owner approval packet boundary summary. CSV summary currently reports `krd_summary_row_count=3`, `krd_detail_row_count=500`, `bond_missing_maturity_row_count=0`, and `tyw_liability_missing_maturity_row_count=1455`; owner/proposed fields remain blank.

`scripts/portfolio_home_owner_decision_intake_check.py --limit 3` is the post-owner-entry intake preflight. In the current real-data state it reports `intake_status=pending_owner_decisions` because risk-owner CSV decisions, data-owner CSV decisions, and business-owner approval are not filled; its `--require-ready` mode exits non-zero until all owner decisions are filled and dependency drift is absent. It now exposes `csv_check_summary` and `generated_owner_fields_boundaries` at the top level before owner decisions are accepted. It now exposes `owner_input_boundary`, separating allowed pre-intake owner-field blockers from active dependency blockers.

`scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision` is the risk-owner KRD contract decision export entry point. It writes full summary/detail CSV queues, an owner summary at `docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md`, and a manifest under `docs/portfolio/krd-contract-decision/2026-05-31/`; the current manifest reports `export_status=decision_required`, `remap_tenor_count=3`, `nonzero_dv01_rows=500`, and `dv01_sum=33180977.63634484`. The KRD owner summary now shows `generated_owner_fields_must_be_blank=true`. The CSV `risk_owner_decision` fields remain blank so the package cannot be mistaken for nearest-bucket approval. Its strict clean mode exits non-zero until the risk-owner decision is captured in the metric contract or exact-bucket schema is implemented.

`scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation` is the data-owner remediation export entry point. It writes full CSV queues, an owner summary at `docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md`, and a manifest under `docs/portfolio/maturity-remediation/2026-05-31/`; the current manifest reports `export_status=blocked`, `bond_missing_maturity_rows=0`, and `tyw_liability_missing_maturity_rows=1455`. The maturity owner summary now shows `generated_owner_fields_must_be_blank=true`. The CSV `proposed_maturity_date` fields remain blank so the package cannot be mistaken for frontend fill or inferred source remediation. Its strict clean mode exits non-zero until the source remediation queue is empty or signed exclusion evidence is captured. The separate matured-outstanding queue reports six non-zero matured bond positions and requires source reconciliation rather than an exception.

The scorecard now carries the material scale evidence directly in its gate payloads: risk tensor quality/source summary, parsed and recomputed risk-warning facts (including the stale 114-row bond warning), KRD remap scale, the six-row matured-outstanding bond queue, and TYW liability missing-maturity principal. Reviewers can therefore use one scorecard JSON as the first-pass decision ledger while still retaining the underlying evidence scripts for drilldown.

Its `gates.owner_decision_intake` entry carries intake status, owner statuses, owner-input boundary, decision alignment, decision gaps, note/comment gaps, and nearest-bucket approval or exact-bucket schema evidence. Its owner-decision intake alignment now compares `owner_input_boundary` so scorecard gate summaries cannot silently drop generated-owner-field boundaries. Owner-decision intake is also the final full-score guard: if all upstream gates are clean but intake is not ready, `owner_decision_intake_blocked` prevents `full_score_ready=true`.

Its `gates.approval_dependency_consistency` entry blocks full-score readiness when KRD or maturity export manifests are stale, missing, or mismatched against the current scorecard. Its `gates.approval_dependency_consistency` entry now exposes `generated_owner_fields_boundaries` so missing or false manifest acceptance criteria is visible from the scorecard gate itself. Any such mismatch adds `approval_dependency_consistency_blocked` to the score blockers, so `current_score=100.00 / 100` cannot be reported from clean data and approval flags unless the owner-facing export manifests match the same report date, statuses, row counts, and amount totals.

The full-score path is now test-covered: a clean risk tensor, supported KRD buckets, complete maturity data, and explicit full-page owner approval produce `current_score=100.00 / 100`, `remaining_gap=0.00`, and `full_score_ready=true` in the scorecard. The current real evidence does not activate that path because the production approval template remains pending and candidate-scoped.

The KRD and maturity queues also expose their own action maps. The KRD queue carries `decision_options=approve_nearest_bucket|require_exact_bucket_schema|reject` plus risk-owner `review_actions`; the maturity queue carries `remediation_scope` plus data-owner `remediation_actions`. These fields make the remaining 0.14-point gap actionable without lowering the data-quality gates.

These materials preserve `formal_use_allowed=false` and `closure_approved=false`. They do not approve page closure; they only package the KRD contract decision, maturity-data remediation, capture-ready page proof, and owner approval actions required before full closure can be claimed.

## Next Optimization

1. Decide the formal KRD contract: either approve nearest-bucket mappings for `2Y`, `6M`, and `20Y`, or expand the risk tensor schema/API to carry exact tenor buckets.
2. Remediate missing maturity dates in upstream bond and TYW liability facts, then re-materialize risk tensor and rerun payload/date evidence tests.
3. Convert the live `/portfolio` fallback proof into a primary governance record only after capture-ready payload parity and owner review exist; keep `formal_use_allowed=false` unless the page contract is formally upgraded.
4. Promote or replace `GS-PORTFOLIO-HOME-A` only after capture-ready live proof and owner review exist; keep it supporting-only until then.
5. Re-run GitNexus or equivalent impact evidence when the MCP surface is available, then package the audit record, focused test results, catalog/date evidence, and owner approval into a sign-off packet.
