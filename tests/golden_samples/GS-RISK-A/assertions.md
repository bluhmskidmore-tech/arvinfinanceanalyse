# GS-RISK-A Assertions

## Source

- `tests/test_risk_tensor_api.py`
- `tests/test_risk_tensor_service.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "risk.tensor"`.
- `result_meta.source_version == "sv_risk_tensor__sv_bond_snap_1"`.
- `result_meta.rule_version == "rv_risk_tensor_formal_materialize_v2"`.
- `result_meta.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2"`.
- `result_meta.quality_flag == "ok"`.
- `result.report_date == "2026-03-31"`.
- `MTR-RSK-101 == 3`.
- `MTR-RSK-020 == "429.00000000"`.
- `MTR-RSK-013 == "14.00000000"`.
- `MTR-RSK-014 == "14.00000000"`.
- `MTR-RSK-015 == "0.00000000"`.
- `MTR-RSK-016 == "0.00000000"`.
- `MTR-RSK-017 == "14.00000000"`.
- `MTR-RSK-018 == "14.00000000"`.
- `MTR-RSK-012 == "1.00000000"`.
- `MTR-RSK-001` is an 8-decimal string.
- `regulatory_dv01.unit == "dv01"` and `regulatory_dv01.raw == portfolio_dv01.raw` under the default all-included regulatory scope.
- `rate_risk_market_value.raw == total_market_value.raw` for the clean sample.
- `duration_excluded_count == 0` and `duration_excluded_market_value.raw == 0`.
- `rate_risk_modified_duration.raw == portfolio_modified_duration.raw`.
- `MTR-RSK-008 > 0`.
- `MTR-RSK-009 > 0`.

## Reconciliation

- Reconcile headline risk directionally with the future bond-analytics headline sample.
