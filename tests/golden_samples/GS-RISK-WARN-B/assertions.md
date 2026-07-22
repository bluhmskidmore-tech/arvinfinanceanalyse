# GS-RISK-WARN-B Assertions

## Source

- `tests/test_risk_tensor_api.py::test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "risk.tensor"`.
- `result_meta.rule_version == "rv_risk_tensor_formal_materialize_v3"`.
- `result_meta.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v3"`.
- `result_meta.tables_used == ["fact_formal_risk_tensor_daily"]` and `result_meta.evidence_rows == 1`.
- `result_meta.quality_flag == "warning"`.
- `result.report_date == "2026-03-31"`.
- `result.bond_count == 3`.
- `result.quality_flag == "warning"`.
- `warnings` contains:
  - `Non-standard tenor buckets remapped` for `20Y`
  - `excluded from portfolio duration denominator`
  - `without maturity_date`
- `duration_excluded_count == 1`.
- `duration_excluded_market_value.raw == 99.0`.
- `rate_risk_market_value.raw == 330.0`.
- `rate_risk_modified_duration.raw == portfolio_modified_duration.raw`.
- The five duration-scope fields are served from the materialized Risk Tensor fact; no read-time Bond Analytics fallback is allowed.
- The formal result excludes accounting DV01 split, prior-period comparison, and scenario-control overlays.

## Reconciliation

- Reconcile this degraded-warning tensor against `GS-RISK-A`.
- This sample exists to freeze warning semantics, not to replace the primary risk sample.
