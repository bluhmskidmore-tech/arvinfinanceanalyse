# GS-RISK-WARN-B Assertions

## Source

- `tests/test_risk_tensor_api.py::test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "risk.tensor"`.
- `result_meta.quality_flag == "warning"`.
- `result.report_date == "2026-03-31"`.
- `result.bond_count == 3`.
- `result.quality_flag == "warning"`.
- `warnings` contains:
  - `Unsupported tenor buckets`
  - `without maturity_date`

## Reconciliation

- Reconcile this degraded-warning tensor against `GS-RISK-A`.
- This sample exists to freeze warning semantics, not to replace the primary risk sample.
