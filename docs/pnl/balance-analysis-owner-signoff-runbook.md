# Balance Analysis Owner Signoff Runbook

This runbook is for the human owner review of `/balance-analysis`. It does not approve closure by itself.

Page ID: `PAGE-BALANCE-001`
Primary API: `/ui/balance-analysis/overview`
Owner approval template: `docs/pnl/balance-analysis-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/balance-analysis-owner-evidence-packet.md`
Live smoke evidence: `docs/audits/2026-06-07-balance-analysis-live-smoke-evidence.md`

## Boundary

- `PAGE-BALANCE-001` remains the formal balance truth surface.
- Keep `formal_use_allowed=true` for the governed overview/read-model evidence.
- Keep `closure_approved=false` until a separate closure approval process changes it.
- Do not treat this runbook, the live smoke artifact, or a passing verification run as business-owner approval.
- Do not treat `GS-BAL-OVERVIEW-A` or `GS-BAL-WORKBOOK-A` as owner-approved while their approval artifacts remain `captured-awaiting-approval`.
- Do not promote `advanced_attribution_bundle` or downstream analytical balance surfaces to governed workbook truth.

## Before Signing

1. Review `docs/pnl/balance-analysis-owner-evidence-packet.md`.
2. Review `docs/pnl/balance-analysis-sign-off-packet.md`.
3. Review `docs/pnl/balance-analysis-governance-audit-packet.md`.
4. Review `docs/audits/2026-06-07-balance-analysis-live-smoke-evidence.md`.
5. Review `tests/golden_samples/GS-BAL-OVERVIEW-A`.
6. Review `tests/golden_samples/GS-BAL-WORKBOOK-A`.
7. Run `python scripts/codex_page_readiness.py --page-slug balance-analysis`.
8. Run `python scripts/check_balance_analysis_business_owner_approval.py`.
9. Run `scripts/codex-verify-page.ps1 -PageSlug balance-analysis -Run`.

## Approval Template Fill Rules

Only edit `docs/pnl/balance-analysis-business-owner-approval-template.md`.

For an approval decision:

- Set `Approval status` to `approval_status=approved`.
- Fill `Business owner name`.
- Fill `Business owner role`.
- Set `Approval decision` to `approve`.
- Fill `Approval date` as `YYYY-MM-DD`.
- Fill `Business owner signature`.
- Set every evidence review item to `yes`.
- Keep `Formal use allowed` as `formal_use_allowed=true`.
- Keep `Closure approved` as `closure_approved=false`.

For `reject` or `request_changes`, leave approval pending or invalid and write the requested changes in `Decision notes`.

## After Signing

Run:

1. `python scripts/check_balance_analysis_business_owner_approval.py`
2. `python scripts/check_balance_analysis_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug balance-analysis`
4. `scripts/codex-verify-page.ps1 -PageSlug balance-analysis -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not set `closure_approved=true`.
