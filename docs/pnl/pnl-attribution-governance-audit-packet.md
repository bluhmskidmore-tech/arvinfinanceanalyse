# PnL Attribution Governance Audit Packet

Page ID: `PAGE-PNL-ATTR-WB-001`
Page slug: `pnl-attribution`
Audit review status: `ready_for_audit_review`
Approval status: `candidate_or_pending`
Formal use allowed: `false`
Closure approved: `false`

## Boundary

- Does not approve page closure or metric formal use.
- Does not cover advanced/Campisi full-surface closure.
- Does not replace `/api/pnl/overview` formal PnL truth.
- Does not merge with executive overlay `/ui/pnl/attribution`.

## Evidence Summary

- MCP sections: `contract_trace, catalog_date_evidence, lineage_evidence, audit_review_queue_item`
- Manual blocker count: `1`
- Manual blockers: `business_owner_approval`
- Evidence references attached for reviewer confirmation: `ui_api_payload_review, live_smoke_evidence_review`
- Sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Approval status command: `python scripts/check_pnl_attribution_business_owner_approval.py`
- Strict approval gate command: `python scripts/check_pnl_attribution_business_owner_approval.py --require-captured`
- PowerShell readiness strict approval gate command: `scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured`
- PowerShell all-page readiness strict approval gate command: `scripts\codex-page-readiness.ps1 -All -RequireApprovalCaptured`
- Business owner approval captured: `false`
- Business owner approval status: `pending`
- Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`
- Record formal-use policy: `must_be_false_until_candidate_closure`

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Golden sample `GS-PNL-ATTR-WB-A` reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- Candidate-only boundary accepted: `yes` (`pending`)

## Required Follow-up

- Review current API payload and visible UI state.
- Confirm live smoke/browser evidence before signing.
- Page smoke rerun: `scripts\codex-page-smoke.ps1 -PageSlug pnl-attribution` (`passed`)
- Page verification rerun: `scripts\codex-verify-page.ps1 -PageSlug pnl-attribution -Run` (`passed`)
- Page readiness rerun: `scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run` (`passed`)
- Page closure command status: `verification rerun complete; business-owner review and signature still pending`
- Collect business-owner approval before any closure claim.
