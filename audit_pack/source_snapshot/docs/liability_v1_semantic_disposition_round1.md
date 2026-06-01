# Liability V1 Semantic Disposition Round 1

## Scope

This round compares the current V3 liability compatibility-seam endpoints against the real V1 sample manifest at:

- [manifest.json](F:/MOSS-V3/tests/fixtures/liability_v1_samples/manifest.json)

The round-1 machine-readable report is:

- [liability_v1_semantic_disposition_round1.json](F:/MOSS-V3/.omx/context/liability_v1_semantic_disposition_round1.json)

## Current stance

- This is a first-pass semantic disposition.
- It does not treat V1 as formal truth.
- It uses the current authority matrix and compatibility gates.
- `/api/liabilities/monthly` is evaluated under `basis = observed`.

## Interface summary

| interface | diff_count | transitional-seam | pending-confirmation | historical-compatibility | initial read |
|---|---:|---:|---:|---:|---|
| `/api/risk/buckets` | 109 | 58 | 12 | 39 | Mixed shape drift plus bucket taxonomy/value differences |
| `/api/analysis/yield_metrics` | 4 | 0 | 4 | 0 | Round-3 narrowed the issue: 2 implementation defects fixed, residual drift remains small |
| `/api/analysis/liabilities/counterparty` | 688 | 422 | 261 | 5 | Round-2 narrowed the issue: taxonomy/classification defects fixed; remaining drift is mostly seam-shape |
| `/api/liabilities/monthly` | 2626 | 1707 | 919 | 0 | Very large seam-shape drift plus observed-basis numeric divergence |

## Round-1 dispositions

### 1. Transitional-seam

These differences are currently treated as compatibility-surface drift, not direct semantic failures.

Examples:

- V1 includes `pct` fields that the current seam omits
- current seam exposes `amount_yi` convenience fields that V1 did not expose on the same path
- V1 exposes richer nested payload members such as `amount` / `pct` in monthly structures that the seam currently trims away
- V1 counterparty payload includes fields such as `weighted_rate` that the seam does not return

Interpretation:

- the seam shape is not yet aligned with the richer V1 outward contract
- these are valid replay differences, but not enough on their own to declare a semantic bug

### 2. Historical-compatibility

These differences indicate legacy taxonomy or bucket-family drift.

Examples:

- V1 `risk/buckets` term buckets use `0-3M / 3-6M / 6-12M / ... / Matured`
- current seam uses `已到期/逾期 / 3个月以内 / 3-6个月 / ...`
- V1 counterparty institution grouping is richer than the current seam grouping

Interpretation:

- these are not automatically implementation defects
- they need an explicit compatibility decision: preserve V1 taxonomy, keep current normalized taxonomy, or maintain a documented seam-only mapping

### 3. Pending-confirmation

These differences are value-bearing and need semantic review before being labeled bugs.

Examples:

- `yield_metrics.kpi.*` values differ materially between V1 and current V3
- `risk_buckets` grouped amounts and product-name ordering differ in several liability substructures
- `counterparty.top_10` ranking, names, values, and weighted costs differ
- `monthly.avg_*`, `mom_*`, `num_days`, and `ytd_*` values differ under the now-approved `observed` basis assumption

Interpretation:

- these are the main candidates for deeper semantic review
- they still require authority-matrix routing before being escalated to `implementation-defect`

## Not asserted in round 1

Round 1 intentionally does **not** assert any of the following yet:

- `implementation-defect`
- `architecture-invalid`
- `data-issue`

Reason:

- the current report is intended to separate obvious seam-shape drift from fields that need semantic review
- stronger labels should only be applied after authority-routed field-by-field inspection

## Highest-priority next review lanes

1. `yield_metrics`
Reason:
Only 4 diffs, all value-bearing, high signal, likely fastest route to a real semantic verdict.

2. `risk/buckets`
Reason:
Bucket-family and grouped-amount drift is material but still bounded enough to review manually.

3. `liabilities/counterparty`
Reason:
Need a decision on whether V1's richer institution taxonomy belongs in the seam or should remain a historical compatibility layer.

4. `liabilities/monthly`
Reason:
Now that `observed` is approved, the next pass can focus on value divergence rather than basis ambiguity.

## Recommended next step

Use the round-1 JSON report as input and perform a second-pass semantic review that promotes a subset of `pending-confirmation` findings into one of:

- `implementation-defect`
- `historical-compatibility`
- `transitional-seam`
- `architecture-invalid`

The best next slice is `yield_metrics` first, because it has the smallest diff surface and the highest semantic density.

## Follow-up status

`yield_metrics` has now completed a deeper follow-up pass:

- [liability_v1_yield_metrics_round3.md](F:/MOSS-V3/docs/liability_v1_yield_metrics_round3.md)

Current outcome:

- confirmed implementation defects fixed:
  - bond rate normalization
  - interest-bearing bond asset scope
- residual drift remains, but is now small enough to keep under `pending-confirmation`

`liabilities/counterparty` has now completed a deeper follow-up pass:

- [liability_v1_counterparty_round2.md](F:/MOSS-V3/docs/liability_v1_counterparty_round2.md)

Current outcome:

- confirmed implementation defects fixed:
  - taxonomy bucket alignment
  - classification source mismatch
- shared-name value and `weighted_cost` alignment is now effectively clean
- remaining drift is mainly seam-shape and presentation-field drift

`risk/buckets` has now completed a deeper follow-up pass:

- [liability_v1_risk_buckets_round2.md](F:/MOSS-V3/docs/liability_v1_risk_buckets_round2.md)

Current outcome:

- confirmed implementation defects fixed:
  - issuance-side amount basis
  - missing-maturity short-bucket fallback
  - 181-day term-boundary routing
  - TYW duplicate-row aggregation upstream of rematerialization
- remaining drift is still mostly bucket-history and row-membership review work

`liabilities/monthly` has now completed a deeper follow-up pass:

- [liability_v1_monthly_round2.md](F:/MOSS-V3/docs/liability_v1_monthly_round2.md)
- [liability_v1_monthly_daily_member_audit_round3.md](F:/MOSS-V3/docs/liability_v1_monthly_daily_member_audit_round3.md)

Current outcome:

- confirmed implementation defects fixed:
  - monthly counterparty proportion denominator
  - monthly institution-type collapse (`Bank / NonBank`)
  - `ytd_avg_liability_cost = null`
  - monthly V1 bucket family/order/zero-bucket emission
  - priority monthly seam `amount / pct` fields
- compatibility diff count dropped:
  - before round 2: `2626`
  - after round 2: `2382`
  - after daily rematerialization + issued-basis correction: `953`
- remaining blockers are now concentrated in:
  - monthly interbank and issuance member-set drift
  - `counterparty_details / counterparty_top10` historical membership/order drift
  - residual value drift in `avg_*`, `structure_overview`, `term_buckets`, and `ytd_avg_total_liabilities`

Daily audit outcome:

- January and early-February interbank drift is now traceable to specific duplicate `deal_id` rows in V1 that were collapsed in the current historical TYW snapshot
- `2026-02-27` current DuckDB contains duplicated report-date batches on both TYW and ZQTZ sides, producing doubled daily totals
- no new monthly seam-code defect was confirmed from the daily audit; the strongest remaining blockers are historical snapshot-state issues plus a smaller pending-confirmation issuance drift

Local follow-up result after rematerialization:

- January / February interbank daily drift has been cleared in the local DuckDB
- `2026-02-27` duplicated report-date batch state has been cleared locally
- a further issued-side seam defect was then confirmed and fixed:
  - V1 issued-liability amount basis uses `摊余成本`
  - the V3 compatibility seam had been using `公允价值`
- remaining monthly residuals are now mainly:
  - floating-point presentation noise
  - a few same-value counterparty tie-order differences
