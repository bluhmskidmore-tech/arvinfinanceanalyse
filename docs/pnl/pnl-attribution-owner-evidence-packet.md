# PnL Attribution Owner Evidence Packet

Page ID: `PAGE-PNL-ATTR-WB-001`
Page slug: `pnl-attribution`
Primary API: `/api/pnl-attribution/volume-rate`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote metric formal use, or certify full-page PnL attribution.

## Current Certification Blockers

- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `golden_sample_approval_artifact_mismatch=false`
- `approval_action_item_count=11`
- `business_owner_approval_captured=false`

## Boundary

Golden sample boundary: `primary_workbench_dto_only`

## DTO vs Page Approval Boundary

Primary API DTO result_meta may be formal/formal_use_allowed=true.
This does not approve PAGE-PNL-ATTR-WB-001 page closure, owner approval, or full-page formal use.

Primary API result_meta scope: `primary_api_dto_formal_result_meta_only`
Primary API result_meta formal use allowed: `true`
Page formal use allowed: `false`
Page owner approval required: `true`

Out of scope:

- full page closure
- Advanced attribution surfaces
- Campisi surfaces
- /api/pnl/overview formal PnL truth
- executive analytical overlay /ui/pnl/attribution
- business-owner approval

## Governance Dry-Run

Governance record write status: `not_requested`
Governance validation status: `ready_for_audit_review`
Existing record line: `5403`

## Latest Verification Evidence

- Static readiness: `static-pass`
- Page smoke: `passed`
- Backend workbench/numeric/Campisi tests: `94 passed`
- Frontend page tests: `27 passed`
- Browser a11y smoke: `1 passed`
- Frontend typecheck: `passed`
- Frontend debt audit: `passed`
- Frontend production build: `passed`
- Full readiness run: `passed`
- Boundary: Full page readiness passed on 2026-06-06: static readiness, page smoke, MCP contract tests, backend tests, frontend tests, browser a11y smoke, typecheck, debt audit, and production build all completed. This is technical evidence only; owner approval remains pending.

## Catalog Date Evidence

Sampled table count: `5`

- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`
- `fact_formal_zqtz_balance_daily`
- `fact_formal_bond_analytics_daily`
- `yield_curve_daily`

## Evidence Anchors

- boundary_status: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- signoff_packet: `docs/pnl/pnl-attribution-sign-off-packet.md`
- governance_audit_packet: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- approval_template: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- golden_sample: `tests/golden_samples/GS-PNL-ATTR-WB-A`
- readiness_command: `python scripts/codex_page_readiness.py --page-slug pnl-attribution`
- governance_dry_run: `python scripts/emit_pnl_attribution_governance_record.py`

## Reviewer Checklist

- Confirm GS-PNL-ATTR-WB-A remains scoped to the primary /api/pnl-attribution/volume-rate DTO.
- Review current UI/API payload against the active workbench view before signature.
- Review live smoke/browser evidence before signature.
- Keep advanced attribution, Campisi, /api/pnl/overview, and /ui/pnl/attribution outside this packet.
- Complete and sign docs/pnl/pnl-attribution-business-owner-approval-template.md before any closure claim.

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

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `validates_required_fields=true`
