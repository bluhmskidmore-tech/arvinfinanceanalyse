# GS-BANK-LEDGER-CLASSIFICATION-A Assertions

## Scope

- Page: `PAGE-BANK-LEDGER-001`; route: `/bank-ledger-dashboard`.
- Endpoint: `GET /api/ledger/dashboard?as_of_date=2026-03-17`.
- Source: deterministic nine-row Ledger import through the production standardizer and `rv_ledger_classification_v2` classifier.
- This sample freezes page/API classification behavior only. It creates no approved `MTR-*` binding.

## Frozen classification matrix

- Five closed-allowlist pairs materialize as `ASSET`.
- `(发行类债券, 发行类债券)` materializes as `LIABILITY`.
- Missing pair, unknown pair, and the conflict pair `(发行类债券, 持有至到期类资产)` materialize as `UNCLASSIFIED`.
- Runtime reads do not reclassify any row.

## Frozen dashboard values

- `classification_status == "ready"` and rule version is `rv_ledger_classification_v2`.
- CNY asset face amount is `5.0` 亿元.
- CNY liability face amount is `2.0` 亿元.
- CNY net face exposure is `3.0` 亿元 (`ASSET - LIABILITY`).
- Three `UNCLASSIFIED` rows total `9.0` 亿元 and do not enter asset, liability, or net.
- Total row count is `9`; classified row count is `6`; row coverage is `66.67%`.
- Requested and resolved dates are both `2026-03-17`; `fallback=false`, `stale=false`, and `no_data=false`.

## Boundary

- Status remains `captured-awaiting-approval` and `formal_use_allowed=false`.
- The sample does not approve the allowlist, conflict policy, net exposure as a formal metric, cross-currency aggregation, FX conversion, historical backfill, or page certification.
- Owner approval, manual review, and an authorized real-page UAT remain separate gates.
