# GS-AVERAGE-BALANCE-MONTHLY-A Approval

- Sample ID: `GS-AVERAGE-BALANCE-MONTHLY-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-08-14`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/analysis/adb/monthly?year=2025`.
- The fixture seeds temporary formal CNY balance fact rows for `2025-12-31` to freeze selected monthly ADB/NIM DTO fields without writing the project DuckDB.
- The sample freezes the `/average-balance` candidate monthly ADB analytical DTO boundary only.
- Re-captured `2026-08-14` after the monthly envelope began disclosing `filters_applied.accounting_basis_currency="CNX"` and `product_category_pnl_canonical_fact` as governed basis/calibration evidence. The deterministic fixture replay changed only those two governance metadata fields and left all frozen monthly/YTD values unchanged.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve `MTR-ADB-*` metrics, formal balance truth, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.

## Recapture record — 2026-09-02

- Reason: the previous file predated `result_meta.trace_id`, the top-level `calibration` block, and the monthly breakdown fields, so the new `AdbAnalysisEnvelope` response model rejected it (`tests/test_api_response_model_field_preservation.py`).
- Key changes: `calibration` block, `result_meta.trace_id = tr_adb_monthly`, `months[0].breakdown_assets` / `breakdown_liabilities` / `nim_stress` / `month_label`, asset & liability rate-coverage ratios, `accounting_basis_daily_avg_trend: []`, explicit optional `result_meta` fields. Every previously present monthly ADB / NIM value is unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.
