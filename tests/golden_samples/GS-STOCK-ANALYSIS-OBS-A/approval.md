# GS-STOCK-ANALYSIS-OBS-A Approval

- Sample ID: `GS-STOCK-ANALYSIS-OBS-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-28`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /ui/market-data/livermore?as_of_date=2026-04-03`.
- The fixture seeds three CSI300 broad-index observations in `fact_choice_macro_daily`.
- The sample freezes the `/stock-analysis` Livermore observation DTO boundary only.

## Caveats

- This is route-scoped observational evidence, not a page closure approval.
- It does not approve PAGE-STOCK contracts, MTR-STOCK metrics, trading instructions, execution approvals, allocation advice, position-change commands, formal stock-analysis truth, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the direct route contract, golden approval, governance evidence, manual audit, and owner approval are all closed.

## Recapture record — 2026-09-02

- Reason: the previous file predates committed observational features (market-gate macro overlay, `module_states`, cycle-rotation `source_versions` / `vendor_versions`) and the credit-impulse evidence copy change.
- Key changes: `data_gaps[3].evidence` now reads "Credit-expansion proxy (social-financing-stock YoY delta proxy; M5525763 or M0001385) …"; `market_gate.exposure_raw` / `formula_version` / `macro_context` / `macro_overlay` and `module_states` are new fields; `result_meta` optional fields emitted explicitly. Candidate lists and gate state are unchanged. Observational only; not a trading instruction.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.
