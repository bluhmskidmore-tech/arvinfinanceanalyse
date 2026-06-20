# GS-MKT-RATES-FRAGMENT-A Approval

- Sample ID: `GS-MKT-RATES-FRAGMENT-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-06-10`

## Capture Note

- `response.json` is captured from a deterministic fixture-backed service call for `GET /ui/market-data/rates`.
- The fixture seeds stable-tier Choice macro rows in `fact_choice_macro_daily` plus `phase1_macro_vendor_catalog` vendor metadata.
- The sample freezes the **formal rates fragment** DTO boundary for Market Tape / rate quote / money market tables only.

## Caveats

- This is **fragment-scoped** formal evidence, not a full-page closure approval for `PAGE-MKT-001`.
- It does **not** close `GAP-MKT-DATA` (no full-page `metric_id` dictionary or page-level golden approval).
- It does not approve Livermore, macro-bond-linkage, FX analytical, NCD proxy, bond futures/trades, or catalog-only preview surfaces.
- `formal_use_allowed=true` applies only to this rates fragment envelope; the page remains `mixed-source`.
