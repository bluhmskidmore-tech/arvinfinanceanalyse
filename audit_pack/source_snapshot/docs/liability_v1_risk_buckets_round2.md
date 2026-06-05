# Liability V1 Risk Buckets Round 2

## Scope

This round focuses on:

- `/api/risk/buckets?report_date=2026-02-26`

Reference sample:

- [risk_buckets_2026-02-26.json](D:/MOSS-SYSTEM-V1/tmp-api/risk_buckets_2026-02-26.json)

## Confirmed implementation fixes

Two issues have been confirmed and fixed in the current V3 seam implementation:

1. `issued liability amount basis`

- V1 uses bond-liability `market_value`
- V3 seam was using issuance-side `face_value`
- this was corrected in [liability_analytics_compat.py](F:/MOSS-V3/backend/app/core_finance/liability_analytics_compat.py)

2. `missing maturity handling`

- V1 `_term_bucket_name(None)` falls back into the short bucket family
- V3 seam was routing missing maturity into `已到期/逾期`
- this was corrected in [liability_analytics_compat.py](F:/MOSS-V3/backend/app/core_finance/liability_analytics_compat.py)

3. `term bucket boundary semantics`

- V1 uses explicit day thresholds for liability term buckets
- an interbank liability with `181` days to maturity belongs to `6-12M` in V1
- the current seam had been using a year-ratio bucket rule that incorrectly routed `181` days into `3-6个月`
- this was corrected in [liability_analytics_compat.py](F:/MOSS-V3/backend/app/core_finance/liability_analytics_compat.py)

## Effect

The compatibility diff count for `risk_buckets` dropped:

- before round 2: `109`
- after issuance/missing-maturity fixes: `101`
- after term-boundary fix: `98`

## Current disposition

### Implementation-defect fixed

- issuance-side amount basis (`face_value` vs `market_value`)
- missing-maturity bucket fallback
- 181-day term-boundary routing (`3-6个月` vs `6-12个月`)

### Historical-compatibility

- bucket taxonomy:
  - V1 uses `0-3M / 3-6M / 6-12M / 1-3Y / ... / Matured`
  - current seam uses `3个月以内 / 3-6个月 / 6-12个月 / 1-2年 / 2-3年 / ... / 已到期/逾期`
- shape drift:
  - V1 exposes `pct`
  - current seam exposes `amount_yi`

These are not automatically bugs. They need an explicit compatibility decision.

### Still pending-confirmation

- `interbank_liabilities_structure` grouped ordering and grouped values
- `interbank_liabilities_term_buckets` grouped values
- `issued_liabilities_structure` small residual amount drift

## What has been ruled out

The current investigation ruled out one obvious hypothesis:

- `interbank liability product-family mismatch`

Reason:

- V1 uses `get_interbank_filter(DirectionEnum.LIABILITY)` in [risk_analysis_service.py](D:/MOSS-SYSTEM-V1/backend/app/services/risk_analysis_service.py)
- current V3 seam uses the `is_asset_side` complement from TYW snapshot parsing
- the product family seen in V3 still includes:
  - `同业存放`
  - `卖出回购证券`
  - `卖出回购票据`
  - `同业拆入`

So the remaining drift is more likely tied to:

- product-level direction parsing upstream
- bucket normalization differences
- row-level source differences between V1 DB models and current snapshot materialization

## Evidence limit hit in round 2

An attempted row-level membership audit could not be completed from the currently located V1 SQLite path:

- [finance.db](D:/MOSS-SYSTEM-V1/backend/data_warehouse/finance.db)

Current finding:

- the available V1 SQLite file does not expose the expected `position_interbank` table for direct row-membership comparison

Implication:

- the remaining `interbank` amount drift stays at `pending-confirmation`
- it should not yet be promoted to `implementation-defect`

Preferred stronger evidence for the next pass:

- the V1 raw interbank source workbook for `2026-02-26`
- a V1 exported row-level liability-side interbank query result for `2026-02-26`
- a different V1 database file that actually contains the interbank holdings table

## Additional row-level finding from supplied V1 export

After the V1 row-level export became available, a stronger implementation issue was identified upstream of the current seam read path:

- some V1 liability-side interbank rows share the same `deal_id` on the same day
- the current snapshot materialization path had been merging TYW rows by `(report_date, position_id)` using last-write-wins behavior
- this can collapse duplicated rows instead of summing them

Examples from the supplied V1 row-level export:

- `3747070`
- `3747135`
- `3747171`

Result:

- snapshot materialization was updated so duplicate TYW rows with the same canonical grain now aggregate additive amounts instead of silently overwriting
- true metadata conflicts still fail closed

Important caveat:

- this fix affects future snapshot rebuilds
- it does not retroactively change the currently materialized `data/moss.duckdb`
- therefore the live `/api/risk/buckets` seam will not reflect this fix until the relevant TYW snapshot rows are rematerialized

## Recommended next pass

The next highest-value pass is not another broad replay. It is a row-membership audit for the `interbank` liability subset on `2026-02-26`:

1. compare V1 `PositionInterbank` liability rows against current `tyw_interbank_daily_snapshot` liability rows
2. identify whether `卖出回购证券` and `同业存放` amounts diverge because of upstream parsing or row exclusion
3. only then decide whether the remaining grouped value drift should be promoted to `implementation-defect`
