# Stock Analysis Owner Evidence Packet

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Page slug: `stock-analysis`
Primary API: `/ui/market-data/stock-analysis/workbench`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote stock-analysis outputs to formal use, or authorize trading instructions.

## Current Certification Blockers

- `golden_sample_boundary=observational_page_dto_capture_ready_pending_approval`
- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `approval_action_item_count=11`
- `business_owner_approval_captured=false`

## Boundary

Golden sample boundary: `observational_page_dto_capture_ready_pending_approval`
Dedicated golden sample: `GS-STOCK-ANALYSIS-OBS-A`
Route-specific evidence scope: `stock_analysis_observational_livermore_dto_only`
Trading instruction allowed: `false`
Execution approval allowed: `false`
Allocation advice allowed: `false`
Position-change command allowed: `false`
Formal stock metric promotion allowed: `false`
Observational boundary status: `no_trading_instruction_boundary_pending_owner_acceptance`

Out of scope:

- PAGE-STOCK contracts
- MTR-STOCK metric approvals
- trading instructions
- execution approvals
- allocation advice
- position-change commands
- formal stock-analysis truth
- business-owner approval

## Governance Dry-Run

Governance record write status: `not_requested`
Governance validation status: `direct_records_ready_for_audit_review`

## 2026-06-22 Technical Evidence Refresh

Refresh scope: `/stock-analysis` observational Livermore DTO and visible review surface.
Baseline implementation evidence commit: `a71a0da55` (`Close Livermore stock analysis supply loop`).
Current technical refresh commit: `7f67fdc39` (`Close Stock Analysis Livermore output loop`) adds the `fresh_trend_watchlist` observational output closure and the `uptrend_momentum_candidates` OVERHEAT policy-pause boundary.
Review status: `technical_evidence_refreshed_owner_approval_pending`.

Live API evidence for `GET /ui/market-data/livermore?as_of_date=2026-06-18`:

- `as_of_date=2026-06-18`
- `market_state=OVERHEAT`
- `supported_outputs=market_gate,sector_rank,fresh_trend_watchlist,factor_screen_candidates,risk_exit`
- `unsupported_outputs=stock_candidates,uptrend_momentum_candidates,mean_reversion_candidates,theme_breakout,hybrid_fusion`
- `active_data_gaps=0`
- `active_diagnostics=0`
- `actionable_unsupported_outputs=0`
- `workbench_summary.actionable_boundary_count=0`
- `workbench_summary.diagnostic_count=0`
- `workbench_summary.total_diagnostic_count=1`, with the remaining diagnostic limited to `info:LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY`
- `uptrend_momentum_candidates` is policy-paused under `market_state=OVERHEAT`; it is not counted as an actionable unsupported output.
- `fresh_trend_watchlist.candidate_count=20`; it is an observation-only growth-board watchlist and is not a trading instruction.
- `factor_screen_candidates.candidate_count=30`
- `sector_rank.formula_status=signed_off`
- `sector_rank.formula_version=rv_livermore_sector_strength_observation_v1`
- `sector_rank.is_provisional=false`

Command evidence captured on 2026-06-22:

- `.venv\Scripts\python.exe scripts\codex_page_readiness.py --page-slug stock-analysis` -> `overall_status=static-pass`, `formal_use_allowed=false`, `business_owner_approval_captured=false`, `catalog_date_evidence=4/4 table date samples`, `direct_governance_record_ready=1 ready direct record(s)`, and `business_owner_approval_status=pending`.
- `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py` -> exit `0`, `approval_status=pending`, `business_owner_approval_captured=false`, `approval_action_item_count=11`.
- `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py --require-captured` -> exit `1` as expected while owner approval remains pending.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug stock-analysis -DryRun` -> verification plan expands the MCP contract tests, backend Livermore tests, frontend Stock Analysis tests, browser a11y smoke, typecheck, debt audit, and production build.

Post-refresh checks captured on 2026-06-22:

- `.venv\Scripts\python.exe -m pytest tests/test_market_data_livermore_api.py backend/tests/core_finance/test_fresh_trend_watchlist_candidates.py -q` -> `55 passed`.
- `npm run test -- src/test/StockAnalysisPageModel.test.ts` -> `84 passed`.
- `npm run test -- src/test/StockAnalysisPageModel.test.ts src/test/StockAnalysisPage.test.tsx src/test/StockAnalysisPageLabels.test.ts src/test/MarketDataPage.test.tsx` -> `226 passed`.
- `npm run typecheck` -> passed.
- `npm run debt:audit` -> passed.
- `npm run lint` -> `0 errors`, with `5` pre-existing warnings.
- `npm run build` -> passed.
- Headless browser smoke for `http://localhost:5888/stock-analysis` confirmed page text contains `新趋势观察`, `过热`, and a clear-boundary label.

Previously executed implementation checks tied to commit `a71a0da55`:

- `.venv\Scripts\python.exe -m pytest backend/tests/core_finance/test_uptrend_momentum_candidates.py tests/test_livermore_sector_rank.py tests/test_market_data_livermore_api.py tests/test_market_data_livermore_candidate_history.py` -> `106 passed`.

This refresh updates technical review evidence only. It does not capture business-owner approval, approve page closure, promote PAGE-STOCK or MTR-STOCK contracts, authorize trading instructions, or enable formal use.

## Configured Table Anchors

- `livermore_position_snapshot`
- `livermore_candidate_history`
- `choice_stock_daily_observation`
- `fact_livermore_gate_supplement_daily`

## Evidence Anchors

- gate_i_lane: `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`
- signoff_packet: `docs/pnl/stock-analysis-sign-off-packet.md`
- governance_audit_packet: `docs/pnl/stock-analysis-governance-audit-packet.md`
- approval_template: `docs/pnl/stock-analysis-business-owner-approval-template.md`
- owner_signoff_runbook: `docs/pnl/stock-analysis-owner-signoff-runbook.md`
- owner_qa_checklist: `docs/pnl/stock-analysis-owner-qa-checklist.md`
- golden_sample: `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A`
- readiness_command: `python scripts/codex_page_readiness.py --page-slug stock-analysis`

## MCP Evidence Gap

Deferred MCP app tools for moss-metric-contracts, moss-lineage-evidence, moss-data-catalog, and gitnexus were not exposed in this Codex App session; local scripts/mcp evidence is used as the current fallback.

## Reviewer Checklist

- Review the 2026-06-22 technical evidence refresh and confirm it remains observational.
- Review `docs/pnl/stock-analysis-owner-qa-checklist.md` before completing the approval template.
- Confirm GS-STOCK-ANALYSIS-OBS-A remains scoped to GET /ui/market-data/livermore DTO evidence.
- Review as_of_date, requested_as_of_date, fallback/stale/no-data states, supported_outputs, unsupported_outputs, rule_readiness, and data_gaps before signature.
- Review the signed-off sector-strength observation formula and confirm it remains a review-prioritization/filtering formula, not a trading signal.
- Review the `fresh_trend_watchlist` observational output and confirm it remains a review watchlist, not a trading signal.
- Review the policy-paused outputs and confirm they are not counted as actionable gaps while `market_state=OVERHEAT`.
- Review Livermore, Choice stock, candidate-history, and gate-supplement table/date evidence before signature.
- Review direct page/API governance records before signature; current packet does not write them.
- Complete and sign docs/pnl/stock-analysis-business-owner-approval-template.md before any closure claim.

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Golden sample `GS-STOCK-ANALYSIS-OBS-A` reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- No-trading-instruction boundary accepted: `yes` (`pending`)

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `validates_required_fields=true`
