# Ledger PnL Owner Evidence Packet

Page ID: `PAGE-LEDGER-PNL-001`
Page slug: `ledger-pnl`
Primary API: `/api/ledger-pnl/summary`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote candidate metric formal use, or certify Ledger PnL as formal PnL truth.

## Current Certification Blockers

- `golden_sample_boundary=dedicated_summary_capture_ready_pending_approval`
- `approval_action_item_count=11`
- `business_owner_approval_captured=false`

## Boundary

Golden sample boundary: `dedicated_summary_capture_ready_pending_approval`
Dedicated golden sample: `GS-LEDGER-PNL-SUMMARY-A`

Candidate metrics:

- `MTR-LPN-001`
- `MTR-LPN-002`
- `MTR-LPN-003`

Out of scope:

- formal PnL overview truth
- product-category PnL truth
- PnL bridge truth
- formal financial indicator truth
- MTR-LPN formal-use promotion
- business-owner approval

## Governance Dry-Run

Governance record write status: `not_requested`
Governance validation status: `ready_for_audit_review`
Existing record line: `None`

## Configured Table Anchors

- `qdb_general_ledger_workbook`
- `ledger_import_batch`
- `ledger_raw_row`

## Evidence Anchors

- dedicated_summary_golden_sample_sync: `docs/audits/2026-06-06-ledger-pnl-dedicated-summary-golden-sample-sync.json`
- direct_record_preflight: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- approval_template: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- dedicated_golden_sample: `tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A`
- readiness_command: `python scripts/codex_page_readiness.py --page-slug ledger-pnl`
- governance_dry_run: `python scripts/emit_ledger_pnl_governance_record.py`

## Reviewer Checklist

- Confirm MTR-LPN-001 through MTR-LPN-003 remain candidate metrics with pending confirmation.
- Review the dry-run governance candidate without treating it as a written direct record.
- Review GS-LEDGER-PNL-SUMMARY-A as a capture-ready dedicated summary sample awaiting approval.
- Review current UI/API payload and live smoke evidence before signature.
- Complete and sign docs/pnl/ledger-pnl-business-owner-approval-template.md before any closure claim.

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Dedicated ledger summary golden sample reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- Candidate-only boundary accepted: `yes` (`pending`)

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `validates_required_fields=true`
