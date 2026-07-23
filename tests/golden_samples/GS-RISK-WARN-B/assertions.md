# GS-RISK-WARN-B Assertions

## Source

- `tests/test_risk_tensor_api.py::test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "risk.tensor"`.
- `result_meta.rule_version == "rv_risk_tensor_formal_materialize_v5"`.
- `result_meta.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v5"`.
- `result_meta.tables_used == ["fact_formal_risk_tensor_daily"]` and `result_meta.evidence_rows == 1`.
- `result_meta.quality_flag == "warning"`.
- `result.report_date == "2026-03-31"`.
- `result.bond_count == 3`.
- `result.quality_flag == "warning"`.
- `projection_quality_status == "available"`.
- `warnings` contains:
  - `Non-standard tenor buckets remapped` for `20Y`
  - `excluded from portfolio duration denominator`
  - `without maturity_date`
  - `lack an explicit payment frequency; annual coupon frequency is used as a proxy`
- `duration_excluded_count == 1`.
- `duration_excluded_market_value.raw == 99.0`.
- `missing_maturity_count == 1` and `missing_maturity_market_value.raw == 99.0`.
- `floating_rate_proxy_count == 0` and `floating_rate_proxy_market_value.raw == 0.0`.
- `payment_frequency_fallback_count == 2` and `payment_frequency_fallback_market_value.raw == 330.0`.
- `bullet_value_date_fallback_count == 0` and `bullet_value_date_fallback_market_value.raw == 0.0`.
- `rate_risk_market_value.raw == 330.0`.
- `rate_risk_modified_duration.raw == portfolio_modified_duration.raw`.
- The five duration-scope fields are served from the materialized Risk Tensor fact; no read-time Bond Analytics fallback is allowed.
- The formal result excludes accounting DV01 split, prior-period comparison, and scenario-control overlays.
- The captured zero-valued projection-quality fields above are asserted because the July 23, 2026 response returned explicit zeros, not because zero may be inferred when a field is absent or unknown.

## Reconciliation

- Reconcile this degraded-warning tensor against `GS-RISK-A`.
- This sample exists to freeze warning semantics, not to replace the primary risk sample.
