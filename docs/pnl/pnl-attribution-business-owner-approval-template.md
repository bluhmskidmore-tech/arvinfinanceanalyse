# PnL Attribution Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-PNL-ATTR-WB-001`
Page slug: `pnl-attribution`
Primary API: `/api/pnl-attribution/volume-rate`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote this page to formal PnL truth.
- Do not replace `/api/pnl/overview`.
- Do not merge with `/ui/pnl/attribution`.
- Advanced/Campisi full-surface closure remains out of scope.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/pnl-attribution-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Golden sample `GS-PNL-ATTR-WB-A` reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
