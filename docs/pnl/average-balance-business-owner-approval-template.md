# Average Balance Business Owner Approval Template

This template is not an approval until completed and signed by the business owner.

Page ID: `GAP-AVERAGE-BALANCE-PAGE`
Page slug: `average-balance`
Primary API: `/api/analysis/adb`
Approval check: `business_owner_approval`
Approval status: `approval_status=pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Candidate Boundary

- Do not promote `MTR-ADB-001` through `MTR-ADB-003` to formal use.
- `GS-AVERAGE-BALANCE-A` covers only the daily `GET /api/analysis/adb` DTO for `MTR-ADB-001` and `MTR-ADB-002`.
- `GS-AVERAGE-BALANCE-MONTHLY-A` covers only selected candidate `GET /api/analysis/adb/monthly` DTO fields for `MTR-ADB-003`.
- `MTR-ADB-003` remains monthly ADB/NIM pending until explicit owner approval is completed.
- Do not replace `PAGE-BALANCE-001` or `/balance-analysis` formal balance truth.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `approves_formal_balance_truth=false`
- `approves_monthly_adb_nim_truth=false`

## Required Business Decision

Business owner name: `<required>`
Business owner role: `<required>`
Approval decision: `<approve | reject | request_changes>`
Approval date: `<YYYY-MM-DD>`
Business owner signature: `<required>`
Reviewed owner evidence packet: `docs/pnl/average-balance-owner-evidence-packet.md`

## Evidence Review

- Governance record reviewed: `<yes | no>`
- Daily ADB golden sample reviewed: `<yes | no>`
- UI/API payload evidence reviewed: `<yes | no>`
- Live smoke evidence reviewed: `<yes | no>`
- Verification commands rerun before approval: `<yes | no>`
- Candidate-only boundary accepted: `<yes | no>`
- Formal balance truth boundary accepted: `<yes | no>`
- Monthly ADB/NIM boundary accepted: `<yes | no>`

## Notes

Decision notes: `<required if reject or request_changes>`
