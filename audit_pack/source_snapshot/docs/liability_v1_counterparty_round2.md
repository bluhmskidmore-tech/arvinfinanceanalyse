# Liability V1 Counterparty Round 2

## Scope

This round focuses on:

- `/api/analysis/liabilities/counterparty?report_date=2026-02-26&top_n=2000`

Reference sample:

- [liabilities_counterparty_2026-02-26.json](D:/MOSS-SYSTEM-V1/tmp-api/liabilities_counterparty_2026-02-26.json)

Supporting row-level evidence:

- [v1_row_level_2026-02-26.csv](D:/MOSS-SYSTEM-V1/reports/v1_exports/2026-02-26/v1_row_level_2026-02-26.csv)

## Round-2 findings

Two implementation defects have now been confirmed and fixed:

1. `counterparty taxonomy alignment`

- the current seam had been flattening non-bank categories into `NonBank` / `Other`
- V1 uses `Bank / Non-Bank FI / Corporate/Other`
- the seam now follows the V1 legacy taxonomy

2. `classification source mismatch`

- the current seam had been using `core_customer_type + counterparty_name` to derive types
- V1 legacy classification is name-driven
- this caused names such as `青银理财有限责任公司` to be misclassified
- the seam now classifies from the counterparty name only

## Current outcome

For the shared names in the observed top group:

- `value` aligns
- `weighted_cost` aligns
- `type` now aligns

`by_type` now matches the V1 sample exactly at the three-bucket level:

- `Bank`
- `Non-Bank FI`
- `Corporate/Other`

Additional verification from the real sample:

- `total_value` is aligned
- shared top names now align on:
  - ranking order
  - grouped value
  - weighted cost
  - legacy type label

## What remains different

The remaining large diff count in the generic compatibility report is still mostly explained by seam-shape drift, not by value drift:

- V1 carries `pct`
- V1 carries `weighted_rate`
- current seam intentionally returns a narrower payload:
  - `report_date`
  - `total_value`
  - `top_10`
  - `by_type`

These are currently best treated as:

- `transitional-seam`, for omitted or extra presentation fields
- `historical-compatibility`, if the team later chooses whether to enrich the seam payload toward V1

## Disposition

### Confirmed implementation defects fixed

- counterparty taxonomy bucket mismatch
- name-versus-core-type classification mismatch

### Residual status

- no remaining high-signal value drift is evident in the currently compared top-name overlap and `by_type` totals
- the remaining diff surface should not be treated as a first-order semantic bug without a broader seam-shape decision

## Recommended next step

Do not spend another round on `counterparty` value logic unless the goal is to widen the seam payload toward full V1 compatibility.

The higher-value next target is now:

- `/api/liabilities/monthly`

Reason:

- `observed` basis is already approved
- the remaining diff surface is still large
- it is now the richest unresolved semantic lane
