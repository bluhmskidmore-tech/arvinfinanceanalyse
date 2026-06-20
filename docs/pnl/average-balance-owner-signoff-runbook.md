# Average Balance Owner Signoff Runbook

This runbook is for the human owner review of `/average-balance`. It does not approve closure by itself.

Page ID: `GAP-AVERAGE-BALANCE-PAGE`
Primary API: `/api/analysis/adb`
Owner approval template: `docs/pnl/average-balance-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/average-balance-owner-evidence-packet.md`

## Boundary

- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.
- Keep `certification_effect=none`.
- Do not promote `MTR-ADB-001`, `MTR-ADB-002`, or `MTR-ADB-003` to formal use.
- Do not replace `PAGE-BALANCE-001` or `/balance-analysis` formal balance truth.

## Before Signing

1. Review `docs/pnl/average-balance-owner-evidence-packet.md`.
2. Review `docs/pnl/average-balance-page-contract.md`.
3. Review `docs/audits/2026-06-10-average-balance-candidate-verification.md`.
4. Review `tests/golden_samples/GS-AVERAGE-BALANCE-A`.
5. Review `tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A`.
6. Run `python scripts/codex_page_readiness.py --page-slug average-balance`.
7. Run `scripts/codex-verify-page.ps1 -PageSlug average-balance -Run`.

## Approval Template Fill Rules

Only edit `docs/pnl/average-balance-business-owner-approval-template.md`.

For an approval decision:

- Set `Approval status` to `approval_status=approved`.
- Fill `Business owner name`.
- Fill `Business owner role`.
- Set `Approval decision` to `approve`.
- Fill `Approval date` as `YYYY-MM-DD`.
- Fill `Business owner signature`.
- Set every evidence review item to `yes`.

For `reject` or `request_changes`, leave closure unapproved and write the requested changes in `Decision notes`.

## After Signing

Run:

1. `python scripts/check_average_balance_business_owner_approval.py`
2. `python scripts/check_average_balance_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug average-balance`
4. `scripts/codex-verify-page.ps1 -PageSlug average-balance -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not promote ADB metrics to formal use.
