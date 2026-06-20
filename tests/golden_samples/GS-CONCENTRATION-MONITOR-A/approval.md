# GS-CONCENTRATION-MONITOR-A Approval

- Sample ID: `GS-CONCENTRATION-MONITOR-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-09`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/bond-analytics/credit-spread-migration?report_date=2026-03-31&spread_scenarios=10,25`.
- The fixture provides two credit bond rows and one non-credit portfolio row to freeze concentration ratios and candidate metadata.
- The sample freezes the `/concentration-monitor` candidate concentration DTO boundary only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve MTR-CON metrics, formal risk truth, fixed-income metric truth, concentration-limit decisions, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
