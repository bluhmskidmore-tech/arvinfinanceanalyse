# Stock Analysis Governance Audit Packet

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Route: `/stock-analysis`
Primary API: `/ui/market-data/livermore`
Audit status: `pending`
Governance record write status: `not_requested`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Audit Boundary

This packet records the audit lane for the Stock Analysis observational route. It does not write governance records, prove page execution, approve a PAGE-STOCK contract, create MTR-STOCK rows, or capture business-owner approval.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## 2026-06-22 Governance Evidence Refresh

Latest refresh source: baseline commit `a71a0da55` (`Close Livermore stock analysis supply loop`) plus current working-tree output-closure changes, live API, and local governance-check commands on 2026-06-22; final commit hash is pending.

Static readiness evidence:

- `.venv\Scripts\python.exe scripts\codex_page_readiness.py --page-slug stock-analysis` returned `overall_status=static-pass`.
- `formal_use_allowed=false` and `approval_status=gap_or_observational` remain enforced.
- `catalog_date_evidence.status=sampled`.
- `catalog_date_evidence.present_table_count=4` and `date_sampled_table_count=4`.
- sampled tables: `livermore_position_snapshot`, `livermore_candidate_history`, `choice_stock_daily_observation`, `fact_livermore_gate_supplement_daily`.
- `governance_record_validation.status=direct_records_ready_for_audit_review`.
- `governance_record_validation.ready_record_count=1`.
- `audit_review.status=ready_for_audit_review`, with manual review still required for page contract, catalog/date, lineage freshness, UI/API payload, live smoke, and business-owner approval.

Live API evidence:

- `GET /ui/market-data/livermore?as_of_date=2026-06-18` returned `active_data_gaps=0`, `active_diagnostics=0`, `actionable_unsupported_outputs=0`, and `workbench_summary.actionable_boundary_count=0`.
- Live supported outputs are `market_gate,sector_rank,fresh_trend_watchlist,factor_screen_candidates,risk_exit`, with `fresh_trend_watchlist.candidate_count=20`.
- `sector_rank.formula_status=signed_off` and `sector_rank.formula_version=rv_livermore_sector_strength_observation_v1`.
- Remaining diagnostic evidence is informational only: `info:LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY`.

Approval evidence:

- `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py` returned `approval_status=pending`, `business_owner_approval_captured=false`, and `approval_action_item_count=11`.
- `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py --require-captured` exits `1` as expected until owner approval is completed.

## Required Evidence

- Direct page/API governance record review
- Catalog/date review for Livermore, Choice stock, candidate-history, and gate-supplement anchors
- Golden sample review for `GS-STOCK-ANALYSIS-OBS-A`
- Manual audit of no-trading-instruction language in the UI
- Verification command rerun before any owner signature
