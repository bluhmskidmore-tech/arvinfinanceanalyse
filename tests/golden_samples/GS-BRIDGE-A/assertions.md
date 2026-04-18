# GS-BRIDGE-A Assertions

## Source

- `tests/test_pnl_api_contract.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl.bridge"`.
- `result.report_date == "2025-12-31"`.
- `rows.length == 1`.
- `rows[0].instrument_code == "240001.IB"`.
- `MTR-BRG-003 == "12.50000000"`.
- `MTR-BRG-008 == "1.75000000"`.
- `MTR-BRG-009 == "-3.25000000"`.
- `MTR-BRG-010 == "0.50000000"`.
- `MTR-BRG-011 == "11.50000000"`.
- `MTR-BRG-012 == "11.50000000"`.
- `MTR-BRG-013 == "0.00000000"`.
- `summary.row_count == 1`.
- `warnings[0]` keeps the current phase-3 partial delivery warning.

## Sample profile

- This is a `warning-profile normal sample`.
- It is valid even though current bridge coverage is not all-green.

## Reconciliation

- Reconcile `actual_pnl` directionally with `GS-PNL-OVERVIEW-A`.
