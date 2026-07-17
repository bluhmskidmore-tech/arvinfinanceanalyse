# Stock Analysis Owner QA Checklist

This checklist prepares the human owner review for `/stock-analysis`. It is not approval until the owner completes and signs `docs/pnl/stock-analysis-business-owner-approval-template.md`.

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Route: `/stock-analysis`
Primary API: `/ui/market-data/stock-analysis/workbench`
Evidence date: `2026-06-18`
Technical refresh commit: `7f67fdc39` (`Close Stock Analysis Livermore output loop`)
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Owner Question

Can the owner accept the page as an observational Livermore review surface whose live data boundary is technically clear for the sampled date, while retaining no-trading-instruction and no-formal-use boundaries?

## Required Page Checks

- [ ] `/stock-analysis` loads and shows the Stock Analysis observational review surface.
- [ ] The page shows `market_state=OVERHEAT` for `as_of_date=2026-06-18`.
- [ ] The page shows no active actionable boundary issues: `active_data_gaps=0`, `active_diagnostics=0`, `actionable_unsupported_outputs=0`, and `workbench_summary.actionable_boundary_count=0`.
- [ ] Supported outputs are visible or accepted as available: `market_gate`, `sector_rank`, `fresh_trend_watchlist`, `factor_screen_candidates`, and `risk_exit`.
- [ ] Policy-paused outputs remain visible as non-actionable boundaries under `market_state=OVERHEAT`: `stock_candidates`, `uptrend_momentum_candidates`, `mean_reversion_candidates`, `theme_breakout`, and `hybrid_fusion`.
- [ ] `fresh_trend_watchlist.candidate_count=20` is accepted as an observation-only growth-board watchlist, not a trading signal.
- [ ] `factor_screen_candidates.candidate_count=30` is accepted as an observational candidate pool, not an execution list.
- [ ] `sector_rank.formula_status=signed_off`, `sector_rank.formula_version=rv_livermore_sector_strength_observation_v1`, and `sector_rank.is_provisional=false` are reviewed as observation-prioritization evidence only.
- [ ] `risk_exit` remains backend-owned observational diagnostics, not a position-change command.
- [ ] `GS-STOCK-ANALYSIS-OBS-A` is reviewed and remains `captured-awaiting-approval`, not owner-approved.
- [ ] The owner confirms the page still gives no trading instruction, execution approval, allocation advice, or position-change command.

## Required Evidence Checks

- [ ] Review `docs/pnl/stock-analysis-owner-evidence-packet.md`.
- [ ] Review `docs/pnl/stock-analysis-sign-off-packet.md`.
- [ ] Review `docs/pnl/stock-analysis-governance-audit-packet.md`.
- [ ] Review `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`.
- [ ] Review `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A`.
- [ ] Review table anchors: `livermore_position_snapshot`, `livermore_candidate_history`, `choice_stock_daily_observation`, and `fact_livermore_gate_supplement_daily`.
- [ ] Review stale, fallback, no-data, unsupported, rule-readiness, and data-gap states before signing.
- [ ] Confirm the direct page/API governance record remains review evidence only and does not write closure approval.

## Required Verification Commands

- [ ] `.venv\Scripts\python.exe scripts\codex_page_readiness.py --page-slug stock-analysis`
- [ ] `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py`
- [ ] `.venv\Scripts\python.exe scripts\check_stock_analysis_business_owner_approval.py --require-captured` fails until the owner signs the approval template.
- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug stock-analysis -Run`

## Signing Rule

Only sign `docs/pnl/stock-analysis-business-owner-approval-template.md` after every required review item above is acceptable. Signing still keeps `formal_use_allowed=false`, `closure_approved=false`, `certification_effect=none`, and does not promote `PAGE-STOCK-*`, `MTR-STOCK-*`, or trading instructions.
