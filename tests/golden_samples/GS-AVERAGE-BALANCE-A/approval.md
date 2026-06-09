# GS-AVERAGE-BALANCE-A Approval

- Sample ID: `GS-AVERAGE-BALANCE-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-09`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/analysis/adb?start_date=2025-12-31&end_date=2025-12-31`.
- The fixture seeds temporary formal CNY balance fact rows for `2025-12-31` to freeze daily ADB summary, trend, and breakdown semantics without writing the project DuckDB.
- The sample freezes the `/average-balance` candidate ADB analytical DTO boundary only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve `MTR-ADB-*` metrics, formal balance truth, monthly ADB/NIM truth, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
