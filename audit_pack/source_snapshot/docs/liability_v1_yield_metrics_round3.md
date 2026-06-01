# Liability V1 Yield Metrics Round 3

## Scope

This round focuses only on:

- `/api/analysis/yield_metrics?report_date=2026-02-26`

Reference sample:

- [yield_metrics_2026-02-26.json](D:/MOSS-SYSTEM-V1/tmp-api/yield_metrics_2026-02-26.json)

## Round-3 findings

Two implementation defects have now been confirmed and fixed:

1. percentage-style bond rates in the current seam were not being defensively normalized back to decimal form
2. the current seam did not reproduce V1's interest-bearing bond asset scope because the read path did not surface `asset_class`

The fix was applied in:

- [liability_analytics_compat.py](F:/MOSS-V3/backend/app/core_finance/liability_analytics_compat.py)

Specifically:

- values `> 0.5 and <= 100` are now treated as percentage-style bond rates and divided by `100`

## Before vs after

### V1 reference

- `asset_yield = 0.02370545259138048`
- `liability_cost = 0.017515794990573118`
- `market_liability_cost = 0.016088982401661293`
- `nim = 0.0076164701897191885`

### Current V3 after round-3 fixes

- `asset_yield = 0.02395289225957926`
- `liability_cost = 0.017523432581815053`
- `market_liability_cost = 0.016080616606221735`
- `nim = 0.007872275653357528`

## Disposition

### Confirmed implementation defect

- `bond rate normalization`
- `interest-bearing bond asset scope`

Reason:

- before the fix, the V3 seam was returning bond-driven rates on a percentage scale rather than the decimal scale used by V1
- the gap was too large to be explained by taxonomy or basis alone
- V1 service logic explicitly performs defensive normalization for bond-side rates
- before the second fix, the V3 seam did not have `asset_class` available, so it could not reproduce V1's `get_bonds_interest_bearing_filter()` behavior

### Still pending confirmation

- `asset_yield`
- `liability_cost`
- `market_liability_cost`
- `nim`

Reason:

- after both fixes, all four KPIs are now in the same numerical neighborhood as V1
- remaining drift is small and no longer looks like a first-order scope or unit bug
- the residual gap is now more consistent with source-scope, ETL, or row-membership differences than with seam calculation logic

## Residual hypothesis

The strongest remaining hypothesis is now upstream data membership rather than seam formula logic:

- V1 computes directly from DB models and their filters in [analysis_service.py](D:/MOSS-SYSTEM-V1/backend/app/services/analysis_service.py)
- the current seam computes from standardized snapshots
- small differences may still come from row membership, ETL normalization, or source freshness rather than from the seam's rate math

## Next recommended review

Review residual row membership for the 2026-02-26 sample:

1. which ZQTZ rows are included in V1 asset-yield numerator/denominator
2. which corresponding snapshot rows are included in the current V3 seam
3. whether interest-bearing and issuance-like exclusions are aligned
