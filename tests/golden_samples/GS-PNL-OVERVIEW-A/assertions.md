# GS-PNL-OVERVIEW-A Assertions

## Source

- `tests/test_pnl_api_contract.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl.overview"`.
- `result_meta.source_version == "fi-shared-v1__nonstd-shared-v1"`.
- `result_meta.vendor_version == "vv_none"`.
- `result_meta.rule_version == "rv_pnl_phase2_materialize_v1"`.
- `result_meta.cache_version == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"`.
- `result.report_date == "2025-12-31"`.
- `MTR-PNL-101 == 1`.
- `MTR-PNL-102 == 1`.
- `MTR-PNL-001 == "12.50"`.
- `MTR-PNL-002 == "96.75"`.
- `MTR-PNL-003 == "1.75"`.
- `MTR-PNL-004 == "0.50"`.
- `MTR-PNL-005 == "111.50"`.

## Reconciliation

- Reconcile overview totals with `GS-PNL-DATA-A`.
