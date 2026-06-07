# Bond Analysis Owner Evidence Packet

Page ID: `PAGE-BOND-ANALYSIS-001`
Page slug: `bond-analysis`
Primary API: `/api/bond-analytics/action-attribution`
Business contract status: `evidence-pending`
Business contract certified: `false`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Business owner approval captured: `false`
Handoff status: `owner_actions_required`

This packet does not approve page closure, write governance records, prove page execution, capture business-owner approval, promote fixed-income metrics to formal use, or certify Bond Analysis as formal fixed-income truth.

## Current Certification Blockers

- `golden_sample_boundary=action_attribution_capture_ready_pending_approval`
- `golden_sample_approval_artifact_status=captured-awaiting-approval`
- `approval_action_item_count=11`
- `business_owner_approval_captured=false`

## Boundary

Golden sample boundary: `action_attribution_capture_ready_pending_approval`
Dedicated golden sample: `GS-BOND-ANALYSIS-ACTION-ATTR-A`
Route-specific evidence scope: `bond_analysis_action_attribution_dto_only`
Borrowed dashboard evidence allowed: `false`
Dashboard evidence reuse status: `blocked_for_bond_analysis_certification`

PAGE-BOND-001, /bond-dashboard, GS-BOND-HEADLINE-A, and MTR-BOND-001 through MTR-BOND-004 are non-reusable for /bond-analysis certification.

Out of scope:

- PAGE-BOND-001
- /bond-dashboard
- GS-BOND-HEADLINE-A
- MTR-BOND-001 through MTR-BOND-004
- formal fixed-income metric truth
- trading instructions or action recommendations
- business-owner approval

## Governance Dry-Run

Governance record write status: `not_requested`
Governance validation status: `missing_direct_records`

## Configured Table Anchors

- `fact_formal_bond_analytics_daily`

## Evidence Anchors

- gate_i_lane: `docs/audits/2026-06-06-bond-analysis-gate-i-lane.md`
- signoff_packet: `docs/pnl/bond-analysis-sign-off-packet.md`
- governance_audit_packet: `docs/pnl/bond-analysis-governance-audit-packet.md`
- approval_template: `docs/pnl/bond-analysis-business-owner-approval-template.md`
- fixed_income_convention_decision_draft: `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`
- golden_sample: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A`
- readiness_command: `python scripts/codex_page_readiness.py --page-slug bond-analysis`

## Fixed-Income Convention Review

Delegated read-only review has been completed for the remaining fixed-income convention blockers. The current recommended owner choices are captured in `docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md`.

Owner confirmation is still required for:

- `market_value_basis=clean`
- `dirty_market_value_formula=market_value + accrued_interest`
- `accrued_interest_usage=dirty_price`; current carry and action attribution do not directly consume accrued interest as an independent attribution driver
- `day_count=ACT/365_approximation`
- `yield_compounding=nominal_annual_with_coupon_frequency`
- `duration_convexity_scope=vanilla_fixed_rate_only`
- `dv01_unit=CNY_per_1bp`
- `dv01_base=CNY_face_value`
- `mcp_evidence_status=fallback_local_evidence_until_mcp_recheck`

## MCP Evidence Gap

Deferred MCP app tools for moss-metric-contracts, moss-lineage-evidence, moss-data-catalog, and gitnexus were not exposed in this Codex App session; local scripts/mcp evidence is used as the current fallback.

## Reviewer Checklist

- Confirm GS-BOND-ANALYSIS-ACTION-ATTR-A remains scoped to GET /api/bond-analytics/action-attribution DTO evidence.
- Review fixed-income units and signs for action-attribution PnL, duration, DV01, KRD, yield/YTM, bp movement, credit-spread, holdings, and accounting-class fields.
- Review catalog/date evidence for fact_formal_bond_analytics_daily before signature.
- Review direct page/API governance records before signature; current packet does not write them.
- Complete and sign docs/pnl/bond-analysis-business-owner-approval-template.md before any closure claim.

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Approval decision: `approve` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Golden sample `GS-BOND-ANALYSIS-ACTION-ATTR-A` reviewed: `yes` (`pending`)
- Fixed-income convention decision draft reviewed: `yes` (`pending`)
- Fixed-income units/sign/date rules reviewed: `yes` (`pending`)
- UI/API payload evidence reviewed: `yes` (`pending`)
- Live smoke evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`
- `validates_required_fields=true`
