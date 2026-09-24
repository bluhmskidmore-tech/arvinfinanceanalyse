# Stock Analysis Owner Signoff Runbook

This runbook is for the human owner review of `/stock-analysis`. It does not approve closure by itself.

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Primary API: `/ui/market-data/stock-analysis/workbench`
Owner approval template: `docs/pnl/stock-analysis-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/stock-analysis-owner-evidence-packet.md`
Sign-off packet: `docs/pnl/stock-analysis-sign-off-packet.md`
Governance audit packet: `docs/pnl/stock-analysis-governance-audit-packet.md`
Owner QA checklist: `docs/pnl/stock-analysis-owner-qa-checklist.md`

## Boundary

- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.
- Keep `certification_effect=none`.
- Do not create `PAGE-STOCK-*` page contracts.
- Do not create or promote `MTR-STOCK-*` metric approvals.
- Do not promote Livermore candidates, signal confluence, sector ranking, strategy scores, optimization diagnostics, proxy backtests, or risk-exit diagnostics to formal stock-analysis truth.
- Do not generate trading instructions, execution approvals, allocation advice, or position-change commands from this page.
- Do not treat dry-run governance output as a written direct PAGE/API governance record.
- Do not treat `GS-STOCK-ANALYSIS-OBS-A` as owner-approved while its approval artifact remains `captured-awaiting-approval`.
- Keep Livermore readiness, fallback, stale, unsupported, missing-input, and no-data states visible before any approval decision.

## Before Signing

1. Review `docs/pnl/stock-analysis-owner-evidence-packet.md`.
2. Review `docs/pnl/stock-analysis-sign-off-packet.md`.
3. Review `docs/pnl/stock-analysis-governance-audit-packet.md`.
4. Review `docs/pnl/stock-analysis-owner-qa-checklist.md`.
5. Review `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`.
6. Review `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A`.
7. Run `python scripts/codex_page_readiness.py --page-slug stock-analysis`.
8. Run `python scripts/check_stock_analysis_business_owner_approval.py`.
9. Run `scripts/codex-verify-page.ps1 -PageSlug stock-analysis -Run`.

## 2026-06-22 Evidence Review Addendum

Before filling the approval template, the owner must explicitly review the refreshed 2026-06-22 evidence:

- Live API evidence for `GET /ui/market-data/livermore?as_of_date=2026-06-18`.
- Technical refresh commit `7f67fdc39` (`Close Stock Analysis Livermore output loop`).
- `active_data_gaps=0`, `active_diagnostics=0`, `actionable_unsupported_outputs=0`, and `workbench_summary.actionable_boundary_count=0`.
- `sector_rank.formula_status=signed_off`, `sector_rank.formula_version=rv_livermore_sector_strength_observation_v1`, and `sector_rank.is_provisional=false`.
- `supported_outputs=market_gate,sector_rank,fresh_trend_watchlist,factor_screen_candidates,risk_exit`.
- `uptrend_momentum_candidates` is policy-paused under `market_state=OVERHEAT`; `fresh_trend_watchlist.candidate_count=20`; `factor_screen_candidates.candidate_count=30`.
- Remaining policy pauses under `market_state=OVERHEAT`, including uptrend momentum, are observational availability states, not trading instructions.
- `scripts/codex_page_readiness.py --page-slug stock-analysis` reports `static-pass`, but still keeps `formal_use_allowed=false`.
- `scripts/check_stock_analysis_business_owner_approval.py --require-captured` must continue to fail until the approval template is completed and signed.

## Approval Template Fill Rules

Only edit `docs/pnl/stock-analysis-business-owner-approval-template.md`.

For an approval decision:

- Set `Approval status` to `approval_status=approved`.
- Fill `Business owner name`.
- Fill `Business owner role`.
- Set `Approval decision` to `approve`.
- Fill `Approval date` as `YYYY-MM-DD`.
- Fill `Business owner signature`.
- Set every evidence review item to `yes`.
- Keep `Formal use allowed` as `formal_use_allowed=false`.
- Keep `Closure approved` as `closure_approved=false`.

For `reject` or `request_changes`, leave approval pending or invalid and write the requested changes in `Decision notes`.

## After Signing

Run:

1. `python scripts/check_stock_analysis_business_owner_approval.py`
2. `python scripts/check_stock_analysis_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug stock-analysis`
4. `scripts/codex-verify-page.ps1 -PageSlug stock-analysis -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not promote Stock Analysis to formal stock metric truth, authorize trading instructions, or set `closure_approved=true`.
