# Liability V1 Monthly Daily Member Audit Round 3

## Scope

This pass audits January and February 2026 daily member sets behind:

- `/api/liabilities/monthly?year=2026`

It focuses on two lanes:

1. interbank liability daily totals and member sets
2. issued-liability daily totals and snapshot state

## Evidence used

V1 sources:

- [finance.db](D:/MOSS-SYSTEM-V1/data_warehouse/finance.db)
  - `position_interbank`
  - `position_bonds`
- [v1_row_level_2026-02-26.csv](D:/MOSS-SYSTEM-V1/reports/v1_exports/2026-02-26/v1_row_level_2026-02-26.csv)
- [v1_position_interbank_liability_2026-02-26.csv](D:/MOSS-SYSTEM-V1/reports/v1_exports/2026-02-26/v1_position_interbank_liability_2026-02-26.csv)

Current V3 source:

- [moss.duckdb](F:/MOSS-V3/data/moss.duckdb)
  - `tyw_interbank_daily_snapshot`
  - `zqtz_bond_daily_snapshot`

Code references:

- [liabilities_service.py](D:/MOSS-SYSTEM-V1/tmp-api/services/liabilities_service.py)
- [liability_analytics_repo.py](F:/MOSS-V3/backend/app/repositories/liability_analytics_repo.py)
- [liability_analytics_compat.py](F:/MOSS-V3/backend/app/core_finance/liability_analytics_compat.py)

## Interbank audit

### January drift is real daily member drift, not seam math drift

The January interbank daily totals differ on 28 days.

Representative days:

- `2026-01-01`: V1 `55.699B`, V3 `54.893B`, drift `-0.8065B`
- `2026-01-07`: V1 `60.950B`, V3 `57.720B`, drift `-3.230B`
- `2026-01-20`: V1 `75.362B`, V3 `69.764B`, drift `-5.5975B`

Root-cause evidence:

- the daily drift is concentrated in a small number of `deal_id`
- those `deal_id` exist in both V1 and V3
- but V1 carries multiple same-day rows per `deal_id`, while current V3 snapshot keeps only one component amount

Examples:

- `2026-01-01`, `deal_id=3732130`
  - V1 rows: `693.5M + 665M + 141.5M = 1.5B`
  - current V3 snapshot: `693.5M`
- `2026-01-07`, `deal_id=3733501`
  - V1 rows: `2.565B + 435M = 3.0B`
  - current V3 snapshot: `435M`
- `2026-01-20`, `deal_id=3738626`
  - V1 rows: `693.5M + 665M + 641.5M = 2.0B`
  - current V3 snapshot: `641.5M`

Interpretation:

- this is consistent with pre-fix TYW snapshot history built under the old last-write-wins behavior
- the current seam code cannot reconstruct the missing components from the already-collapsed snapshot rows

### February drift splits into two patterns

Before `2026-02-27`, February shows the same collapsed-duplicate-deal pattern as January.

Representative days:

- `2026-02-02`: drift `-2.812B`
- `2026-02-14`: drift `-5.003237B`
- `2026-02-24`: drift `-5.075B`

Examples:

- `2026-02-24`, `deal_id=3746288`
  - V1 rows: `2.565B + 435M = 3.0B`
  - current V3 snapshot: `435M`
- `2026-02-24`, `deal_id=3746184`
  - V1 rows: `1.2B + 800M = 2.0B`
  - current V3 snapshot: `800M`

### `2026-02-27` is a separate historical-data failure

This day is not just a collapsed-duplicate issue. It contains duplicated snapshot batches in the current V3 DuckDB.

Evidence:

- `tyw_interbank_daily_snapshot` on `2026-02-27` has:
  - `3626` rows
  - `1813` distinct `position_id`
- two full report-date batches are present:
  - `ib_9c29e032c37b`
  - `ib_e977e69a008a`

This causes exact doubling for many IDs:

- `3747401`: V1 `2.0B`, V3 `4.0B`
- `3747408`: V1 `2.0B`, V3 `4.0B`
- `2023317`: V1 `1.03B`, V3 `2.06B`

One ID still keeps the pre-fix collapsed amount inside the duplicated state:

- `3747475`
  - V1 rows: `2.565B + 435M = 3.0B`
  - current V3 snapshot: `435M + 435M = 870M`

Interpretation:

- `2026-02-27` is a historical snapshot-state failure in the current DuckDB
- it combines:
  - stale duplicated report-date batches
  - pre-fix collapsed duplicate-deal aggregation

## Issued-liability audit

### January shows a stable small undercount

Using the V1 `position_bonds` daily grouped `asset_class` results, the issuance-side daily total is consistently higher than current V3 by roughly the same magnitude throughout January.

Representative days:

- `2026-01-01`: V1 `121.849B`, V3 `121.271B`, drift `-578.432M`
- `2026-01-09`: V1 `121.901B`, V3 `121.270B`, drift `-630.780M`
- January average drift: about `-592.244M/day`

Observed subtype pattern on sample days:

- `同业存单` is lower in V3 by roughly `697M - 745M`
- `商业银行债` is slightly higher in V3 by roughly `68M - 75M`
- `次级债券` is slightly higher in V3 by roughly `31M - 46M`

Interpretation:

- this looks like a historical valuation/member-set drift
- it does not look like the monthly seam formulas fixed in round 2
- current evidence is not strong enough to promote this to a new implementation defect

Classification:

- `pending-confirmation`

### `2026-02-27` also has duplicated issued snapshot state

On `2026-02-27`:

- V1 issued total: `120.449B`
- current V3 issued total: `239.608B`
- drift: `+119.159B`

Current V3 snapshot evidence:

- `zqtz_bond_daily_snapshot` has:
  - `258` issuance-like rows
  - `129` distinct full-grain keys
- two full report-date batches are present:
  - `ib_9c29e032c37b`
  - `ib_e977e69a008a`

Interpretation:

- this is the same stale duplicated report-date batch problem seen on the interbank side

Classification:

- `data-issue`

## Disposition summary

### Confirmed blocker classes

- `data-issue`
  - `2026-02-27` duplicated report-date batches in both TYW and ZQTZ current snapshots
- `historical-compatibility`
  - none newly promoted in this pass
- `implementation-defect`
  - no new monthly seam-code defect confirmed in this pass
- `pending-confirmation`
  - January and pre-`2026-02-27` February issued-liability drift

### Strongly evidenced historical snapshot problems

These are not new seam-code bugs. They are current-data-state blockers:

1. pre-fix collapsed duplicate-deal history in TYW snapshot rows
2. stale duplicated report-date batches on `2026-02-27`

## Why no code patch was applied in this pass

The missing interbank amounts for January / early February are not present in the current V3 snapshot rows.

That means:

- a read-path patch cannot reliably reconstruct them
- the durable fix is rematerialization from raw source after the duplicate-aggregation fix

Likewise, the `2026-02-27` doubled state is a snapshot-history problem already explainable by duplicated batch presence in DuckDB.

## Recommended next step

1. Rematerialize January and February TYW snapshots into the current DuckDB using the duplicate-aggregation fix.
2. Rematerialize the affected ZQTZ report dates, especially `2026-02-27`, so duplicate report-date batches are removed.
3. Re-run the monthly focused diff after rematerialization before making any new seam-code changes.

## Follow-up execution result

The local DuckDB follow-up was executed after this audit:

- `2026-02-27` was rematerialized first and verified
- January / February TYW snapshot history was then rematerialized across the affected window
- stale `ib_9c29e032c37b` rows were removed on the dates where an explicit `ib_8d84e1a205c4` replay had temporarily left two full report-date partitions in place

Current local result in [moss.duckdb](F:/MOSS-V3/data/moss.duckdb):

- January interbank daily drift days: `0`
- February interbank daily drift days: `0`
- `2026-02-27` duplicated TYW / ZQTZ batch state: cleared

What still remains after the rematerialization:

- after the issued-basis correction in the monthly seam, issued-liability total drift is effectively cleared
- monthly `avg_liability_cost` residual drift is now only floating-point noise

Updated interpretation:

- the interbank blocker has been materially resolved in the local DuckDB state
- the issued-side drift was ultimately confirmed as a seam basis defect, not a historical member-set problem:
  - V1 `PositionBonds.market_value` for `发行类债劵` comes from `摊余成本`
  - current V3 seam had been reading `公允价值`
- after correcting the monthly issued basis, the remaining monthly residuals are:
  - floating-point presentation noise
  - a few same-value counterparty tie-order differences
