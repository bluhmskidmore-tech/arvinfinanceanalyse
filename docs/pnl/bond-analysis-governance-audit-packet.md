# Bond Analysis Governance Audit Packet

Page ID: `PAGE-BOND-ANALYSIS-001`
Route: `/bond-analysis`
Primary API: `/api/bond-analytics/action-attribution`
Governance record write status: `not_requested`
Governance validation status: `direct_records_ready_for_audit_review`
Direct page/API governance record status: `ready_for_audit_review`
Closure approved: `closure_approved=false`
Formal use allowed: `formal_use_allowed=false`

This packet does not write governance records, approve page closure, promote fixed-income metrics to formal use, prove live page/API execution, or capture business-owner approval.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Current Audit Status

- Direct page/API governance record: `ready_for_audit_review`
- Catalog/date evidence: `sampled`
- Golden sample boundary: `action_attribution_capture_ready_pending_approval`
- UI/API payload review evidence: `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`
- Live smoke evidence review: `docs/audits/2026-06-09-bond-analysis-live-smoke-evidence.md`
- Live smoke command reference: `scripts/codex-page-smoke.ps1 -PageSlug bond-analysis`
- Business owner approval: `pending`
- Business owner approval captured: `false`

## Configured Table Anchors

- `fact_formal_bond_analytics_daily`

## Audit Requirements

- Review direct page/API governance record for `PAGE-BOND-ANALYSIS-001` and `/api/bond-analytics/action-attribution`.
- Review catalog/date evidence for `fact_formal_bond_analytics_daily`.
- Review lineage for source/rule/cache versions and fallback/stale states.
- Manually review DV01, duration, KRD, yield/YTM, bp movement, credit-spread, holdings, accounting-class, and action-attribution PnL units/sign/date rules.
- Complete business-owner approval after manual review.

## Governance Record Commands

- Dry run: `python scripts/emit_bond_analysis_governance_record.py`
- Write: `python scripts/emit_bond_analysis_governance_record.py --write`
- Validate: `python scripts/codex_page_readiness.py --page-slug bond-analysis`

The write command appends a candidate direct record only. It does not approve page closure, promote fixed-income metrics to formal use, prove live page/API execution, or capture business-owner approval.
