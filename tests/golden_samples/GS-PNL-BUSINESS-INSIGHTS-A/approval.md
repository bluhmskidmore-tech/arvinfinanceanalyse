# GS-PNL-BUSINESS-INSIGHTS-A Approval

- Sample ID: `GS-PNL-BUSINESS-INSIGHTS-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-07-07`

## Capture Note

- `response.json` is captured from a real formal-facts-backed call to `GET /api/pnl/by-business-candidate-insights?year=2026&as_of_date=2026-02-28`.
- The fixture materializes two ZQTZ parent business types (国债/政策性金融债) across `2025-12-31`, `2026-01-31`, and `2026-02-28` via `fact_formal_pnl_fi` + `fact_formal_zqtz_balance_daily`; `2025-12-31` doubles as the prior-year baseline consumed by the share-drift metric.
- The endpoint only re-aggregates the existing `pnl_by_business_ytd_envelope` / `pnl_by_business_monthly_envelope` results; it does not re-query any raw formal fact table itself.

## Caveats

- 候选 DTO 已 capture-ready，未经业务审批；不批准业务种类集中度限额、不批准FTP利率口径、不批准份额漂移的战略解读。
- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve `MTR-PNLBIZ-001` through `MTR-PNLBIZ-005`, formal PnL truth, or any change to `PAGE-PNL-BY-BUSINESS-001` (`docs/page_contracts.md` §14.8.1).
- `formal_use_allowed=false` must remain visible until a dedicated page contract, governance evidence, manual audit, and owner approval are all closed.
