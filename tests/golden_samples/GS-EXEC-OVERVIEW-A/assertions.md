# GS-EXEC-OVERVIEW-A Assertions

## Source

- `tests/test_executive_service_contract.py`
- `tests/test_executive_dashboard_endpoints.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "analytical"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.scenario_flag == false`.
- `result_meta.result_kind == "executive.overview"`.
- `result_meta.source_version == "sv_balance_union__sv_exec_dashboard_v1"`.
- `result_meta.rule_version == "rv_balance_union__rv_exec_dashboard_v1"`.
- `result_meta.cache_version == "cv_exec_dashboard_v1"`.
- `result.title == "经营总览"`.
- `result.metrics.length == 4`.
- `result.metrics[id=aum].label == "总资产规模"`.
- `result.metrics[id=aum].caliber_label == "本币资产口径"`.
- `result.metrics[id=yield].caliber_label == null`.
- `result.metrics[id=nim].caliber_label == null`.
- `result.metrics[id=dv01].caliber_label == null`.
- `MTR-EXEC-001 == "3,572.76 亿"`.
- `MTR-EXEC-002 == "+4.69 亿"`.
- `MTR-EXEC-003 == "+1.00%"`.
- `MTR-EXEC-004 == "13,826,218"`.

## Reconciliation

- Reconcile the management DV01 directionally with `GS-RISK-A`.
