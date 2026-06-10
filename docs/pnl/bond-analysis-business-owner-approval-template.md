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
- `certification_effect=none`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed sign-off packet: `docs/pnl/bond-analysis-sign-off-packet.md`
Reviewed governance audit packet: `docs/pnl/bond-analysis-governance-audit-packet.md`
Reviewed owner evidence packet: `docs/pnl/bond-analysis-owner-evidence-packet.md`
Reviewed fixed-income convention decision draft: `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`
Owner signoff runbook: `docs/pnl/bond-analysis-owner-signoff-runbook.md`

## Fixed-Income Convention Decisions

Market value basis: `<clean | dirty | other>`
Dirty market value formula: `<market_value + accrued_interest | other>`
Accrued interest usage: `<dirty_price_only | dirty_price_and_carry | dirty_price_and_action_attribution | other>`
Day-count convention: `<ACT/365_approximation | Actual/Actual | 30/360 | other>`
Yield compounding convention: `<nominal_annual_with_coupon_frequency | effective_annual | other>`
Duration and convexity scope: `<vanilla_fixed_rate_only | all_bonds_with_warnings | other>`
DV01 unit: `<CNY_per_1bp | other>`
DV01 base: `<CNY_face_value | CNY_market_value | CNY_dirty_value | other>`
MCP evidence status accepted: `<fallback_local_evidence_until_mcp_recheck | require_mcp_before_approval>`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `<yes | no>`
- Fixed-income convention decision draft reviewed: `<yes | no>`
- Fixed-income units/sign/date rules reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
