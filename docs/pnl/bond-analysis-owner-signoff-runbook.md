# Bond Analysis Owner Signoff Runbook

This runbook is for the human owner review of `/bond-analysis`. It does not approve closure by itself.

Page ID: `PAGE-BOND-ANALYSIS-001`
Primary API: `/api/bond-analytics/action-attribution`
Owner approval template: `docs/pnl/bond-analysis-business-owner-approval-template.md`
Owner evidence packet: `docs/pnl/bond-analysis-owner-evidence-packet.md`
Sign-off packet: `docs/pnl/bond-analysis-sign-off-packet.md`
Governance audit packet: `docs/pnl/bond-analysis-governance-audit-packet.md`
Fixed-income convention decision draft: `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`

## Boundary

- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.
- Keep `certification_effect=none`.
- Do not promote DV01, duration, KRD, yield/YTM, credit-spread, action-attribution PnL, holdings, accounting-class, or bp movement values to formal fixed-income metric truth.
- Do not use `PAGE-BOND-001`, `/bond-dashboard`, `GS-BOND-HEADLINE-A`, or `MTR-BOND-001` through `MTR-BOND-004` to certify `/bond-analysis`.
- Do not treat dry-run governance output as a written direct PAGE/API governance record.
- Do not treat `GS-BOND-ANALYSIS-ACTION-ATTR-A` as owner-approved while its approval artifact remains `captured-awaiting-approval`.
- Treat the fixed-income convention decision draft as reviewer input only until the owner confirms the units, signs, date basis, and clean/dirty value conventions.

## Before Signing

1. Review `docs/pnl/bond-analysis-owner-evidence-packet.md`.
2. Review `docs/pnl/bond-analysis-sign-off-packet.md`.
3. Review `docs/pnl/bond-analysis-governance-audit-packet.md`.
4. Review `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`.
5. Review `docs/audits/2026-06-06-bond-analysis-gate-i-lane.md`.
6. Review `docs/audits/2026-06-09-bond-analysis-live-smoke-evidence.md`.
7. Review `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A`.
8. Run `python scripts/codex_page_readiness.py --page-slug bond-analysis`.
9. Run `python scripts/check_bond_analysis_business_owner_approval.py`.
10. Run `scripts/codex-verify-page.ps1 -PageSlug bond-analysis -Run`.

## Approval Template Fill Rules

Only edit `docs/pnl/bond-analysis-business-owner-approval-template.md`.

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

1. `python scripts/check_bond_analysis_business_owner_approval.py`
2. `python scripts/check_bond_analysis_business_owner_approval.py --require-captured`
3. `python scripts/codex_page_readiness.py --page-slug bond-analysis`
4. `scripts/codex-verify-page.ps1 -PageSlug bond-analysis -Run`

The second command must pass before anyone can claim business-owner approval captured. Passing it still does not promote Bond Analysis to formal fixed-income metric truth or set `closure_approved=true`.
