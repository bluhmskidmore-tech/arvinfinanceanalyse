# Average Balance Owner Evidence Packet

Page ID: `GAP-AVERAGE-BALANCE-PAGE`
Page slug: `average-balance`
Primary API: `/api/analysis/adb`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote ADB metrics to formal use, replace formal balance truth, or approve monthly ADB/NIM truth.

## Current Certification Blockers

- `golden_sample_boundary=daily_and_monthly_adb_candidate_dto_capture_ready_pending_approval`
- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `approval_action_item_count=13`
- `business_owner_approval_captured=false`

## Boundary

Golden sample boundary: `daily_and_monthly_adb_candidate_dto_capture_ready_pending_approval`
Dedicated golden samples: `GS-AVERAGE-BALANCE-A`, `GS-AVERAGE-BALANCE-MONTHLY-A`
Monthly ADB/NIM approval allowed: `false`
Formal balance truth approval allowed: `false`

Daily candidate metrics covered by the sample:

- `MTR-ADB-001`
- `MTR-ADB-002`

Monthly candidate metrics covered only by the monthly candidate sample:

- `MTR-ADB-003`

Out of scope:

- formal balance truth
- PAGE-BALANCE-001 replacement
- balance-analysis formal closure
- monthly ADB/NIM approval
- MTR-ADB formal-use promotion
- business-owner approval

## Governance Dry-Run

Governance record write status: `not_requested`
Governance validation status: `ready_for_audit_review`
Existing record line: `dry-run not written`

## Configured Table Anchors

- `fact_formal_zqtz_balance_daily`
- `fact_formal_tyw_balance_daily`
- `zqtz_bond_daily_snapshot`
- `tyw_interbank_daily_snapshot`

## Evidence Anchors

- page_contract: `docs/pnl/average-balance-page-contract.md`
- owner_approval_template: `docs/pnl/average-balance-business-owner-approval-template.md`
- daily_golden_sample: `tests/golden_samples/GS-AVERAGE-BALANCE-A`
- monthly_golden_sample: `tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A`
- metric_dictionary: `docs/metric_dictionary.md`
- live_smoke_evidence: `docs/audits/2026-06-09-average-balance-live-smoke-evidence.md`
- latest_verification_snapshot: `docs/audits/2026-06-10-average-balance-candidate-verification.md`
- readiness_command: `python scripts/codex_page_readiness.py --page-slug average-balance`
- smoke_command: `scripts/codex-page-smoke.ps1 -PageSlug average-balance`
- verify_command: `scripts/codex-verify-page.ps1 -PageSlug average-balance -Run`
- governance_dry_run: `python scripts/emit_average_balance_governance_record.py`
- owner_approval_checker: `python scripts/check_average_balance_business_owner_approval.py`

## Reviewer Checklist

- Confirm MTR-ADB-001 and MTR-ADB-002 remain candidate daily ADB metrics bound to GS-AVERAGE-BALANCE-A.
- Confirm MTR-ADB-003 remains candidate monthly ADB/NIM evidence bound only to GS-AVERAGE-BALANCE-MONTHLY-A.
- Review the dry-run governance candidate without treating it as a written direct record.
- Review current UI/API payload and live smoke evidence before signature.
- Complete and sign docs/pnl/average-balance-business-owner-approval-template.md before any closure claim.

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Daily ADB golden sample reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- Candidate-only boundary accepted: `yes` (`pending`)
- Formal balance truth boundary accepted: `yes` (`pending`)
- Monthly ADB/NIM boundary accepted: `yes` (`pending`)

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `validates_required_fields=true`
- `approves_formal_balance_truth=false`
- `approves_monthly_adb_nim_truth=false`
