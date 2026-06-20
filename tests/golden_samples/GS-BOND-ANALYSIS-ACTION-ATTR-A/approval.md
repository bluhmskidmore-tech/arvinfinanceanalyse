# GS-BOND-ANALYSIS-ACTION-ATTR-A Approval

- Sample ID: `GS-BOND-ANALYSIS-ACTION-ATTR-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-06`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/bond-analytics/action-attribution?report_date=2026-03-31&period_type=MoM`.
- The fixture seeds one prior and one current bond snapshot plus matching 517 capital-gain allocation.
- The sample freezes the `/bond-analysis` action-attribution DTO boundary only.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve fixed-income formulas, direct governance records, manual audit closure, business-owner approval, or formal-use promotion.
- `formal_use_allowed=false` must remain visible until the direct page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.
