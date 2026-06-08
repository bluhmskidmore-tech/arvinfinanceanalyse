# Bond Analysis Governance Audit Packet

Page ID: `PAGE-BOND-ANALYSIS-001`
Route: `/bond-analysis`
Primary API: `/api/bond-analytics/action-attribution`
Governance record write status: `not_requested`
Governance validation status: `missing_direct_records`
Closure approved: `closure_approved=false`

This packet does not write governance records and does not approve page closure.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Audit Requirements

- Direct page/API governance record for `PAGE-BOND-ANALYSIS-001` or `/api/bond-analytics/action-attribution`.
- Catalog/date review for `fact_formal_bond_analytics_daily`.
- Lineage review for source/rule/cache versions and fallback/stale states.
- Manual review of DV01, duration, KRD, yield/YTM, bp movement, credit-spread, holdings, accounting-class, and action-attribution PnL units/sign/date rules.
- Business-owner approval after manual review.
