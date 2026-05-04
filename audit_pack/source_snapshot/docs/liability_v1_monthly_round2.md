# Liability V1 Monthly Round 2

## Scope

This round focuses on:

- `/api/liabilities/monthly?year=2026`

Reference sample:

- [liabilities_monthly_2026-02-26.json](D:/MOSS-SYSTEM-V1/tmp-api/liabilities_monthly_2026-02-26.json)

Supporting evidence:

- [v1_row_level_2026-02-26.csv](D:/MOSS-SYSTEM-V1/reports/v1_exports/2026-02-26/v1_row_level_2026-02-26.csv)
- [liabilities_service.py](D:/MOSS-SYSTEM-V1/tmp-api/services/liabilities_service.py)

## Round-2 findings

This pass confirmed and fixed five high-signal compatibility defects in the current V3 seam implementation.

### 1. Counterparty proportion denominator

- V1 `counterparty_details[].proportion` and `counterparty_top10[].proportion` are shares of monthly counterparty average total
- V3 had been dividing by `avg_total_liabilities`
- the seam now uses the V1 denominator and keeps `pct` as the share of monthly total liabilities

### 2. Monthly institution-type collapse

- V1 monthly uses the legacy two-bucket outward grouping:
  - `Bank`
  - `NonBank`
- V3 had been reusing the richer counterparty seam taxonomy:
  - `Bank`
  - `Non-Bank FI`
  - `Corporate/Other`
- the monthly seam now follows the V1 monthly outward grouping and detail type tags

### 3. YTD liability cost nullability

- V1 explicitly returns `ytd_avg_liability_cost = null`
- V3 had been emitting a computed value
- the seam now matches the V1 null behavior

### 4. Monthly term-bucket family

- V1 monthly does not use the risk-bucket Chinese family
- it uses:
  - `0-3M`
  - `3-6M`
  - `6-12M`
  - `1-3Y`
  - `3-5Y`
  - `5-10Y`
  - `10Y+`
  - `Matured`
- V3 had been reusing the risk seam bucket family and omitting zero buckets
- the monthly seam now follows the V1 monthly family, ordering, missing-maturity fallback, and zero-bucket emission

### 5. Priority shape fields on monthly seam rows

The following priority structures now carry the V1-compatible presentation fields:

- `by_institution_type[].amount / pct`
- `structure_overview[].amount / pct`
- `term_buckets[].amount / pct`
- `interbank_term_buckets[].amount / pct`
- `issued_term_buckets[].amount / pct`
- `counterparty_details[].amount / pct`
- `counterparty_top10[].amount / pct`

This reduces the priority-lane shape drift without promoting the endpoint into a governed surface.

## Effect

The monthly compatibility diff count dropped:

- before round 2: `2626`
- after round 2 fixes: `2382`

Reduction:

- `244` diffs removed

Priority-section diff counts after round 2:

- `by_institution_type`: `12`
- `structure_overview`: `16`
- `term_buckets`: `42`
- `interbank_term_buckets`: `14`
- `issued_term_buckets`: `42`
- `avg_liability_cost`: `2`
- `ytd_avg_liability_cost`: `0`
- `counterparty_top10`: `104`
- `counterparty_details`: `2083`

## Current disposition

### Implementation-defect fixed

- monthly counterparty proportion denominator
- monthly institution-type collapse
- `ytd_avg_liability_cost` nullability
- monthly term-bucket family/order/zero-bucket emission
- priority seam presentation fields for monthly structures
- issued-liability amount basis:
  - V1 `PositionBonds.market_value` for `发行类债劵` is populated from `摊余成本`
  - the current V3 seam had been reading `market_value_native` (`公允价值`)
  - the seam now uses `amortized_cost_native` for issued-liability amounts, which aligns exactly with the V1 monthly totals

### Pending-confirmation

The remaining high-signal drift is still value-bearing and appears upstream of the fixed seam logic:

- `avg_interbank_liabilities`
- `avg_issued_liabilities`
- `avg_total_liabilities`
- `avg_liability_cost`
- `ytd_avg_total_liabilities`
- `structure_overview` values
- `by_institution_type` values
- `term_buckets / interbank_term_buckets / issued_term_buckets` balances
- `counterparty_details / counterparty_top10` membership, ordering, values, and weighted cost

Two observations matter here:

1. January `by_institution_type.Bank` drift is exactly the same as January `avg_interbank_liabilities` drift.
   This means the grouping fix is no longer the problem; the remaining issue is the monthly interbank member set.

2. The current V3 `2026-02-26` TYW liability snapshot matches the supplied V1 row-level export at the single-day grouped level.
   This suggests the unresolved monthly drift is more likely caused by date-window history/state differences than by the current single-day monthly seam formulas.

### Transitional-seam

The largest transitional-seam gap in the monthly priority lanes was reduced in round 2 by restoring V1-style presentation fields on the key structures above.

Residual monthly drift is now dominated by numeric/member-set differences rather than missing priority fields.

### Historical-compatibility

No new monthly priority finding needs to stay in `historical-compatibility` after this pass.

Reason:

- the monthly bucket family and institution-type outward labels were directly aligned to the V1 seam
- the unresolved drift now looks like row membership / historical-state behavior, not just taxonomy

## Remaining blockers

The main blockers are now upstream/historical, not local seam-shape bugs:

1. `counterparty_details` and `counterparty_top10` still carry the largest unresolved diff surface.
   This is the strongest remaining blocker for monthly closure.

2. Monthly interbank totals still drift even after the type/proportion fix.
   The strongest next hypothesis is historical member-set drift across January and February, not the current compatibility logic.

3. Issued-liability monthly drift still remains.
   This needs historical ZQTZ membership evidence across the full month window, not just the 2026-02-26 sample day.

## Recommended next pass

Do not reopen the monthly seam shape work first.

The highest-value next pass is a historical member-set audit:

1. compare January and February daily interbank liability totals between V1 and current snapshot history
2. compare January and February daily issuance totals between V1 and current snapshot history
3. trace the first day where monthly totals diverge, instead of diffing only the final aggregated month

That audit has now been performed:

- [liability_v1_monthly_daily_member_audit_round3.md](F:/MOSS-V3/docs/liability_v1_monthly_daily_member_audit_round3.md)

Current audit outcome:

- January and early-February interbank drift is explained by pre-fix collapsed duplicate `deal_id` history in the current TYW snapshot
- `2026-02-27` monthly distortion is explained by duplicated report-date batches in both current TYW and ZQTZ snapshots
- remaining issued-liability January drift stays at `pending-confirmation`

Follow-up local rematerialization result:

- January / February interbank daily drift is now `0` in the local DuckDB
- the issued-liability basis defect has now also been fixed locally:
  - `2026-01 avg_issued_liabilities` drift: effectively `0`
  - `2026-02 avg_issued_liabilities` drift: effectively `0`
- monthly totals now align:
  - `2026-01 avg_total_liabilities` drift: `0`
  - `2026-02 avg_total_liabilities` drift: `0`
- `ytd_avg_liability_cost` remains aligned at `null`
- monthly compatibility diff count is now down to:
  - `953`

Remaining residuals after both fixes:

- floating-point presentation noise
- a few same-value `counterparty_details` tie-order differences
  - current local diff inspection shows `8` residual name/type diffs, corresponding to `4` swapped equal-value counterparty pairs
  - inspection suggests the V1 order is likely a by-product of the old `tmp-api` pandas `groupby(...).reset_index().sort_values('amount', ascending=False)` path on the full monthly dataframe, not an explicit business-owned tie-break rule
  - no simple deterministic rule from the inspected V1 DB metadata was strong enough to safely encode as a seam-wide sort rule without overfitting
