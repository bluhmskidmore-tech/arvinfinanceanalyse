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
- `result_meta.requested_report_date == result_meta.resolved_report_date == result_meta.as_of_date == "2025-12-31"`.
- `result_meta.date_basis == "balance_analysis_report_date"`.
- `result_meta.filters_applied` freezes the requested report date, `position_scope="all"`, and `currency_basis="CNY"`.
- `result_meta.tables_used` names both formal balance fact tables and `result_meta.evidence_rows == 2`.
- `result.report_date == "2025-12-31"`.
- `result.position_scope == "all"`.
- `result.currency_basis == "CNY"`.
- `MTR-BAL-001 == "792.00000000"`（API 兼容市值毛额；`720.00000000 + 72.00000000`，不是资产规模或净头寸）.
- `MTR-BAL-002 == "720.00000000"`（API 兼容摊余成本毛额；`648.00000000 + 72.00000000`）.
- `MTR-BAL-003 == "50.40000000"`（API 兼容应计利息毛额；`36.00000000 + 14.40000000`）.
- 页面主展示的分项字段冻结为：资产/负债市值 `720.00000000` / `72.00000000`、资产/负债摊余成本 `648.00000000` / `72.00000000`、资产/负债应计利息 `36.00000000` / `14.40000000`；这些分项当前不自动批准新的 `metric_id`.
- `MTR-BAL-101 == 2`.
- `MTR-BAL-102 == 2`.

## Reconciliation

- Reconcile compatibility gross fields and side-specific page disclosures with `GS-BAL-WORKBOOK-A`; primary pages must render side-specific disclosures rather than label `total_*` gross fields as asset scale or net balance.
