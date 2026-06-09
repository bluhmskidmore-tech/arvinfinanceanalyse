# GS-CASHFLOW-PROJECTION-A Approval

- Sample ID: `GS-CASHFLOW-PROJECTION-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-09`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/cashflow-projection?report_date=2026-04-30`.
- The fixture provides one formal asset row, one formal liability row, and one matching bond-analytics duration row.
- The sample freezes the `/cashflow-projection` candidate liquidity projection DTO boundary only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve MTR-CFP metrics, formal liquidity truth, risk truth, balance truth, PnL truth, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
