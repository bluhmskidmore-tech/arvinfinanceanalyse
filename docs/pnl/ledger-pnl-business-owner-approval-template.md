# Ledger PnL Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-LEDGER-PNL-001`
Page slug: `ledger-pnl`
Primary API: `/api/ledger-pnl/summary`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use.
- Do not replace formal PnL, product-category PnL, PnL bridge, or formal FI truth.
- Dedicated ledger summary golden sample `GS-LEDGER-PNL-SUMMARY-A` is captured-awaiting-approval and does not approve this page for formal use.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed sign-off packet: `docs/pnl/ledger-pnl-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/ledger-pnl-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Dedicated ledger summary golden sample reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
