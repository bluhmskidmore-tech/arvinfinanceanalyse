# Ledger PnL Owner Signoff Runbook

This runbook is for the human owner review of `/ledger-pnl`. It does not approve closure by itself.

Page ID: `PAGE-LEDGER-PNL-001`
Primary API: `/api/ledger-pnl/summary`
Owner approval template: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
Sign-off packet: `docs/pnl/ledger-pnl-sign-off-packet.md`
Governance audit packet: `docs/pnl/ledger-pnl-governance-audit-packet.md`

## Boundary

- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.
- Keep `certification_effect=none`.
- Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use.
- Do not promote Ledger PnL summary values to formal PnL truth.
- Do not replace product-category PnL, PnL bridge, or formal financial indicator truth.
- Do not treat dry-run governance output as a written direct PAGE/API governance record.
- Do not treat `GS-LEDGER-PNL-SUMMARY-A` as owner-approved while its approval artifact remains `captured-awaiting-approval`.
- Keep `GS-LEDGER-PNL-FIN-IND-202603-B` scoped to formal financial indicator source-contract evidence only.

## Before Signing

1. Review `docs/pnl/ledger-pnl-owner-evidence-packet.md`.
2. Review `docs/pnl/ledger-pnl-sign-off-packet.md`.
3. Review `docs/pnl/ledger-pnl-governance-audit-packet.md`.
4. Review `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`.
5. Review `docs/audits/2026-06-06-ledger-pnl-dedicated-summary-golden-sample-sync.json`.
6. Review `tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A`.
7. Run `python scripts/codex_page_readiness.py --page-slug ledger-pnl`.
8. Run `python scripts/check_ledger_pnl_business_owner_approval.py`.
9. Run `scripts/codex-verify-page.ps1 -PageSlug ledger-pnl -Run`.

## Approval Template Fill Rules

Only edit `docs/pnl/ledger-pnl-business-owner-approval-template.md`.

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

1. `python scripts/check_ledger_pnl_business_owner_approval.py`
2. `python scripts/check_ledger_pnl_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug ledger-pnl`
4. `scripts/codex-verify-page.ps1 -PageSlug ledger-pnl -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not promote Ledger PnL to formal PnL truth or set `closure_approved=true`.
