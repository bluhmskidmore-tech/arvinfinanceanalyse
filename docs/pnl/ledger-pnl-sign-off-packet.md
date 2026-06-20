# Ledger PnL Sign-Off Packet

Page ID: `PAGE-LEDGER-PNL-001`
Page slug: `ledger-pnl`
Primary API: `/api/ledger-pnl/summary`
Approval status: `candidate_or_pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Decision Boundary

This packet is prepared for business-owner review only. It does not approve page closure, metric formal use, or formal PnL truth promotion.

- Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use.
- Do not replace formal PnL, product-category PnL, PnL bridge, or formal FI truth.
- Dedicated ledger summary golden sample `GS-LEDGER-PNL-SUMMARY-A` is captured-awaiting-approval and does not approve this page for formal use.

## Evidence Anchors

- Governance dry-run: `python scripts/emit_ledger_pnl_governance_record.py`
- Governance record write status: `not_requested`
- Existing record line: `null`
- Owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Business owner approval template: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Candidate status: `candidate_or_pending`
- Business owner approval captured: `false`
- Business owner approval status: `pending`
- Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, dedicated_golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Reviewer Checklist

- Confirm current `/api/ledger-pnl/summary` payload matches the reviewed dry-run governance candidate.
- Confirm `MTR-LPN-001` through `MTR-LPN-003` remain candidate metrics and that `GS-LEDGER-PNL-SUMMARY-A` is capture-ready but not approved.
- Confirm `formal_use_allowed=false` and `closure_approved=false` remain correct until written evidence and business-owner approval are captured.
- Confirm this packet does not approve or imply replacement of formal PnL, product-category PnL, PnL bridge, or formal FI truth.

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

## Business Owner Handoff

Handoff status: `ready_for_business_owner_review_pending_signature`
Approval action item count: `11`
Approval template to complete: `docs/pnl/ledger-pnl-business-owner-approval-template.md`

This handoff does not capture approval, write governance records, prove page execution, or grant closure.
Keep `formal_use_allowed=false` and `closure_approved=false` until business-owner approval is explicitly captured.
