# GS-BAL-OVERVIEW-A Assertions

## Source

- `tests/test_balance_analysis_api.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.formal_use_allowed == true`.
- `result_meta.result_kind == "balance-analysis.overview"`.
- `result_meta.source_version == "sv-fx-1__sv-t-1__sv-z-1"`.
- `result_meta.rule_version == "rv_balance_analysis_formal_materialize_v1"`.
- `result_meta.cache_version == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"`.
- `result.report_date == "2025-12-31"`.
- `result.position_scope == "all"`.
- `result.currency_basis == "CNY"`.
- `MTR-BAL-001 == "792.00000000"`.
- `MTR-BAL-002 == "720.00000000"`.
- `MTR-BAL-003 == "50.40000000"`.
- `MTR-BAL-101 == 2`.
- `MTR-BAL-102 == 2`.

## Reconciliation

- Reconcile headline totals with `GS-BAL-WORKBOOK-A`.
