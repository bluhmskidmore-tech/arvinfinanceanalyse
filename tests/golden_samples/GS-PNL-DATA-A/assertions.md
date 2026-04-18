# GS-PNL-DATA-A Assertions

## Source

- `tests/test_pnl_api_contract.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result.report_date == "2025-12-31"`.
- `formal_fi_rows.length == 1`.
- `nonstd_bridge_rows.length == 1`.
- `formal_fi_rows[0].instrument_code == "240001.IB"`.
- `nonstd_bridge_rows[0].bond_code == "BOND-001"`.
- `formal_fi_rows[0]` retains fields for:
  - `MTR-PNL-001`
  - `MTR-PNL-002`
  - `MTR-PNL-003`
  - `MTR-PNL-004`
  - `MTR-PNL-005`
  - `MTR-PNL-103`
  - `MTR-PNL-104`

## Reconciliation

- Aggregate the returned rows and reconcile to `GS-PNL-OVERVIEW-A`.
