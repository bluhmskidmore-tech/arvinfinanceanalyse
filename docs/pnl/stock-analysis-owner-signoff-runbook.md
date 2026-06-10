# Stock Analysis Owner Signoff Runbook

This runbook is for the human owner review of `/stock-analysis`. It does not approve closure by itself.

Page ID: `GAP-STOCK-ANALYSIS-PAGE`
Primary API: `/ui/market-data/livermore`
Owner approval template: `docs/pnl/stock-analysis-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/stock-analysis-owner-evidence-packet.md`
Sign-off packet: `docs/pnl/stock-analysis-sign-off-packet.md`
Governance audit packet: `docs/pnl/stock-analysis-governance-audit-packet.md`

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
4. Review `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`.
5. Review `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A`.
6. Run `python scripts/codex_page_readiness.py --page-slug stock-analysis`.
7. Run `python scripts/check_stock_analysis_business_owner_approval.py`.
8. Run `scripts/codex-verify-page.ps1 -PageSlug stock-analysis -Run`.

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
