# PnL Attribution Owner Signoff Runbook

This runbook is for the human owner review of `/pnl-attribution`. It does not approve closure by itself.

Page ID: `PAGE-PNL-ATTR-WB-001`
Primary API: `/api/pnl-attribution/volume-rate`
Owner approval template: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
Sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`
Governance audit packet: `docs/pnl/pnl-attribution-governance-audit-packet.md`

## Boundary

- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.
- Keep `certification_effect=none`.
- Do not promote this workbench to formal PnL truth.
- Do not replace `/api/pnl/overview`.
- Do not merge this workbench with `/ui/pnl/attribution`.
- Do not treat primary API DTO `formal_use_allowed=true` result metadata as full-page owner approval.
- Do not treat `GS-PNL-ATTR-WB-A` as owner-approved while its approval artifact remains `captured-awaiting-approval`.
- Keep advanced attribution and Campisi surfaces outside this owner signoff unless a separate owner decision expands the scope.

## Before Signing

1. Review `docs/pnl/pnl-attribution-owner-evidence-packet.md`.
2. Review `docs/pnl/pnl-attribution-sign-off-packet.md`.
3. Review `docs/pnl/pnl-attribution-governance-audit-packet.md`.
4. Review `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`.
5. Review `tests/golden_samples/GS-PNL-ATTR-WB-A`.
6. Run `python scripts/codex_page_readiness.py --page-slug pnl-attribution`.
7. Run `python scripts/check_pnl_attribution_business_owner_approval.py`.
8. Run `scripts/codex-verify-page.ps1 -PageSlug pnl-attribution -Run`.

## Approval Template Fill Rules

Only edit `docs/pnl/pnl-attribution-business-owner-approval-template.md`.

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

1. `python scripts/check_pnl_attribution_business_owner_approval.py`
2. `python scripts/check_pnl_attribution_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug pnl-attribution`
4. `scripts/codex-verify-page.ps1 -PageSlug pnl-attribution -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not promote the workbench to formal PnL truth or set `closure_approved=true`.
