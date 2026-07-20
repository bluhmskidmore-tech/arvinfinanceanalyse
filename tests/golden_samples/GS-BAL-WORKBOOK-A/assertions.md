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

## Recapture record — 2026-07-20

- Reason: recaptured after the balance H-2 `currency_basis` remediation in the
  calculation-audit sequence (`fa074e13f` / `f9697fe4b`; direct service fetch
  wiring in `d440c11a3`). A CNY request now consumes CNY-projected facts instead
  of summing native mixed-currency rows under a CNY label.
- Authorization: owner `arvin` authorized this recapture in-session.
- Arithmetic evidence:
  - bond asset: `100 USD × 7.2 CNY/USD = 720 CNY = 0.07200000 万元`
  - interbank liability: `10 USD × 7.2 CNY/USD = 72 CNY = 0.00720000 万元`
  - net position: `0.07200000 - 0.00720000 = 0.06480000 万元`
- Key value changes include:
  - `0.01000000 → 0.07200000`
  - `0.00100000 → 0.00720000`
  - `0.00900000 → 0.06480000`
  - `-0.00100000 → -0.00720000`
- Scope: 58 H-2-derived leaf values across cards, governed tables, and
  operational sections. Unrelated response-shape/dynamic metadata and
  pre-existing classification drift are outside this recapture.
