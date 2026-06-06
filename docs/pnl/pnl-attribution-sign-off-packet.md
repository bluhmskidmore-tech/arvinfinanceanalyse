# PnL Attribution Sign-Off Packet

Page ID: `PAGE-PNL-ATTR-WB-001`
Page slug: `pnl-attribution`
Primary API: `/api/pnl-attribution/volume-rate`
Approval status: `candidate_or_pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`

## Decision Boundary

This packet is prepared for business-owner review only. It does not approve page closure, metric formal use, or formal PnL truth promotion.

- Do not promote this page to formal PnL truth.
- Do not replace `/api/pnl/overview`.
- Do not merge with `/ui/pnl/attribution`.
- Advanced/Campisi full-surface closure remains out of scope.

## Evidence Anchors

- Governance record: `data/governance/cache_manifest.jsonl:5403`
- Golden sample: `GS-PNL-ATTR-WB-A`
- Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Business owner approval template: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Candidate status: `candidate_or_pending`
- Evidence references attached for reviewer confirmation: `ui_api_payload_review`, `live_smoke_evidence_review`
- Remaining blocker: `business_owner_approval`
- Business owner approval captured: `false`
- Business owner approval status: `pending`
- Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`

## Reviewer Checklist

- Confirm the visible `pnl-attribution` page matches the reviewed `/api/pnl-attribution/volume-rate` payload for the approved report date and compare type.
- Confirm the golden sample `GS-PNL-ATTR-WB-A` remains the accepted candidate sample for this workbench page.
- Confirm `formal_use_allowed=false` and `closure_approved=false` remain correct until business-owner approval is explicitly recorded.
- Confirm this packet does not approve or imply replacement of `/api/pnl/overview` or merger with `/ui/pnl/attribution`.

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

## Business Owner Handoff

Handoff status: `ready_for_business_owner_review_pending_signature`
Approval action item count: `11`
Approval template to complete: `docs/pnl/pnl-attribution-business-owner-approval-template.md`

This handoff does not capture approval, write governance records, prove page execution, or grant closure.
Keep `formal_use_allowed=false` and `closure_approved=false` until business-owner approval is explicitly captured.

## Verification Evidence

Commands freshly verified for this candidate sign-off packet:

```text
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
python -m pytest tests/test_project_mcp_servers.py -q
python -m ruff check scripts/mcp/moss_project_mcp.py scripts/check_pnl_attribution_business_owner_approval.py scripts/codex_page_readiness.py scripts/emit_pnl_attribution_governance_record.py tests/test_project_mcp_servers.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py
python scripts/check_pnl_attribution_business_owner_approval.py
python scripts/check_pnl_attribution_business_owner_approval.py --require-captured
scripts\codex-page-smoke.ps1 -PageSlug pnl-attribution
scripts\codex-verify-page.ps1 -PageSlug pnl-attribution -Run
scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run
scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
scripts\codex-page-readiness.ps1 -All -RequireApprovalCaptured
```

Business-owner review still required before approval can be captured:

```text
Review current API payload and visible UI state.
Confirm live smoke/browser evidence.
Complete/sign docs\pnl\pnl-attribution-business-owner-approval-template.md.
```

Observed evidence from the readiness chain includes:

- Current pnl-attribution governance chain: `71 passed`
- Current MCP evidence suite: `151 passed`
- Current pnl-attribution page verification: `94 backend passed; 27 frontend passed; 1 browser a11y smoke passed; typecheck passed; debt audit passed`
- Current pnl-attribution readiness run: `Page readiness gate passed`
- Strict approval gate: `expected failure while business_owner_approval_captured=false`
- Page closure command status: `verification rerun complete; business-owner review and signature still pending`

## Sign-Off State

Current state remains candidate-only:

- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval` is still required before any closure or formal-use claim.
