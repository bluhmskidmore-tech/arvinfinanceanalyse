# GS-EXEC-PNL-ATTR-A Assertions

## Source

- `tests/test_executive_service_contract.py`
- `tests/test_executive_dashboard_endpoints.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "analytical"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.scenario_flag == false`.
- `result_meta.result_kind == "executive.pnl-attribution"`.
- `result_meta.source_version == "sv_exec_dashboard_v1__sv_pc_a__sv_pc_b__sv_pc_c"`.
- `result_meta.rule_version == "rv_exec_dashboard_v1__rv_pc_a__rv_pc_b__rv_pc_c"`.
- `result_meta.cache_version == "cv_exec_dashboard_v1"`.
- `result.title == "经营贡献拆解"`.
- `MTR-EXEC-101 == "+1.75 亿"`.
- Segment ids include:
  - `carry`
  - `roll`
  - `credit`
  - `trading`
  - `other`

## Reconciliation

- Reconcile overlay directionally against `GS-PNL-OVERVIEW-A` and `GS-BRIDGE-A`.
