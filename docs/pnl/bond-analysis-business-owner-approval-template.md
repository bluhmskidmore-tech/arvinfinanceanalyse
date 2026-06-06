# Bond Analysis Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `PAGE-BOND-ANALYSIS-001`
Page slug: `bond-analysis`
Primary API: `/api/bond-analytics/action-attribution`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote fixed-income action-attribution, DV01, duration, KRD, yield/YTM, credit-spread, holdings, or accounting-class values to formal metric truth.
- Do not borrow `PAGE-BOND-001`, `/bond-dashboard`, `GS-BOND-HEADLINE-A`, or `MTR-BOND-001` through `MTR-BOND-004`.
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` is captured-awaiting-approval and does not approve this page for formal use.

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
Reviewed sign-off packet: `docs/pnl/bond-analysis-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/bond-analysis-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/bond-analysis-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `<yes | no>`
- Fixed-income units/sign/date rules reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
