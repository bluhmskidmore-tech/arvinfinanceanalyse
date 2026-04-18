# GS-BRIDGE-WARN-B Assertions

## Source

- `tests/test_pnl_api_contract.py::test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl.bridge"`.
- `result_meta.source_version == "fi-shared-v1__nonstd-shared-v1__sv-z-current__sv-z-prior"`.
- `result_meta.rule_version == "rv-z-current__rv-z-prior__rv_pnl_phase2_materialize_v1"`.
- `result_meta.vendor_version == "vv_none"`.
- `result.report_date == "2025-12-31"`.
- `rows.length == 1`.
- `rows[0].current_balance_found == true`.
- `rows[0].prior_balance_found == true`.
- `rows[0].balance_diagnostics == []`.
- `summary.total_beginning_dirty_mv == "91.00000000"`.
- `summary.total_ending_dirty_mv == "102.00000000"`.
- `summary.total_explained_pnl == "11.50000000"`.
- `summary.total_actual_pnl == "11.50000000"`.
- `summary.total_residual == "0.00000000"`.
- `warnings` contains:
  - current phase-3 partial delivery warning
  - `Balance lineage fallback used for report_date=2025-12-31`
  - `Balance lineage fallback used for prior_report_date=2025-10-31`
  - `No treasury curve available`

## Reconciliation

- Reconcile warning-profile bridge values against `GS-BRIDGE-A`.
- This sample exists to freeze warning semantics, not to replace the primary bridge sample.
