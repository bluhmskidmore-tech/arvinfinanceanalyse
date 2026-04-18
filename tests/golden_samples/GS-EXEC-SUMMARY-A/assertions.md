# GS-EXEC-SUMMARY-A Assertions

## Source

- `tests/test_executive_service_contract.py`
- `tests/test_executive_dashboard_endpoints.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "analytical"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.scenario_flag == false`.
- `result_meta.result_kind == "executive.summary"`.
- `result_meta.source_version == "sv_summary_requested"`.
- `result_meta.rule_version == "rv_summary_requested"`.
- `result.report_date == "2026-02-28"`.
- `result.title == "本周管理摘要"`.
- `result.points.length == 3`.
- Point labels include:
  - `收益`
  - `风险`
  - `建议`

## Reconciliation

- This sample is narrative-only and should stay consistent with the current executive overview lineage source.
