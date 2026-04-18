# GS-BAL-WORKBOOK-A Assertions

## Source

- `tests/test_balance_analysis_api.py`
- `tests/test_balance_analysis_workbook_contract.py`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "balance-analysis.workbook"`.
- `tables[].key` covers the governed workbook supported key set.
- `advanced_attribution_bundle` does not appear in `tables[].key`.
- `operational_sections` contains:
  - `decision_items`
  - `event_calendar`
  - `risk_alerts`
- `decision_items.section_kind == "decision_items"`.
- `event_calendar.section_kind == "event_calendar"`.
- `risk_alerts.section_kind == "risk_alerts"`.

## Reconciliation

- Reconcile workbook totals and supported section inventory with `GS-BAL-OVERVIEW-A`.

## Notes

- This is a structure sample, not a full-value lock for every workbook row.
