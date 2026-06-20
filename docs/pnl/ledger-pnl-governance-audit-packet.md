# Ledger PnL Governance Audit Packet

Page ID: `PAGE-LEDGER-PNL-001`
Page slug: `ledger-pnl`
Audit review status: `evidence-pending`
Approval status: `candidate_or_pending`
Formal use allowed: `false`
Closure approved: `false`

## Boundary

- Does not approve page closure or metric formal use.
- Does not write a governance record.
- Does not treat dry-run preflight as a written direct PAGE/API governance record.
- Does not replace formal PnL, product-category PnL, PnL bridge, or formal FI truth.

## Evidence Summary

- Governance dry-run command: `python scripts/emit_ledger_pnl_governance_record.py`
- Governance record write status: `not_requested`
- Existing record line: `null`
- Governance validation status: `ready_for_audit_review`
- Dedicated ledger summary golden sample: `GS-LEDGER-PNL-SUMMARY-A captured-awaiting-approval`
- Owner evidence packet: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Sign-off packet: `docs/pnl/ledger-pnl-sign-off-packet.md`
- Approval status command: `python scripts/check_ledger_pnl_business_owner_approval.py`
- Strict approval gate command: `python scripts/check_ledger_pnl_business_owner_approval.py --require-captured`
- Business owner approval captured: `false`
- Business owner approval status: `pending`
- Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, dedicated_golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

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

## Required Follow-up

- Keep using dry-run generation until governance workflow authorizes an explicit write.
- After an authorized write, rerun governance validation and require a written direct PAGE/API record plus supporting expanded lineage.
- Review `GS-LEDGER-PNL-SUMMARY-A` before promoting `MTR-LPN-001` through `MTR-LPN-003`.
- Review current UI/API payload and live smoke evidence before signing.
- Collect business-owner approval before any closure claim.
