# Frontend Formal Recompute Audit

## Status

- date: 2026-04-24
- boundary class: docs-only frontend audit
- scope: component/page locations that parse, scale, or derive displayed business metrics
- non-scope: backend changes, frontend source edits, route promotion, global state refactor

## Search Evidence

Command:

```powershell
rg -n "parseFloat|Number\(|nativeToNumber|formatOverviewNumber|formatNumber" frontend/src -g "*.ts" -g "*.tsx"
```

Read first:

- `docs/plans/2026-04-24-frontend-page-chain-audit.md`
- `frontend/src/utils/format.ts`
- `frontend/src/components/page/FormalResultMetaPanel.tsx`

## Classification Rules

| classification | Meaning |
| --- | --- |
| adapter-owned view-model conversion | Numeric/string normalization is outside rendering components and can be unit-tested as a view model |
| harmless local display formatting | Formatting does not change business meaning, does not hide sign/unit/date, and only affects labels/tooltips |
| risky formal metric derivation in component | Component parses, scales, thresholds, sums, or changes sign/unit for formal metrics |
| mock/demo/placeholder-only behavior | Logic only exists in mock, preview, excluded, or demonstration surfaces; keep out of formal truth |

## Top Risks By Business Impact

| priority | page / surface | file / function | classification | risk | recommended order |
| --- | --- | --- | --- | --- | --- |
| P0 | product category PnL (`PAGE-PROD-CAT-PNL-001`) | `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx:89` `formatNumber`; `:100` `formatDisplayValue`; `:118` `toneForValue`; call sites around `:976`-`:1021` | risky formal metric derivation in component | Formal `business_net_income`, `weighted_yield`, scale, FTP, and net fields are parsed inside the page. `formatDisplayValue` also hides sign for `row.side === "liability"` via `Math.abs(...)`. This may be intended presentation, but it is not locked in the page model tests and can drift from `GS-PROD-CAT-PNL-A` field truth. | First code slice candidate: move display/tone helpers into the product-category page model or a local tested formatter, then assert liability sign display, grand total passthrough, and no client-side rollup. |
| P1 | balance analysis (`PAGE-BALANCE-001`) | `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx:136` `parseWorkbookNumber`; `:149` `formatOverviewNumber`; `:160`/`:174` unit conversions; chart panels around `:488`, `:526`, `:568`; component duplicates in `BalanceAnalysisCardsSection.tsx:18` and `BalanceAnalysisTableSection.tsx:18` | risky formal metric derivation in component | The page parses strings and converts yuan/wan/yi in several render paths. `parseWorkbookNumber` turns invalid values into `0` for visualization widths, so malformed formal data can look like a legitimate zero in workbook charts. | Second slice: centralize balance display formatting behind an adapter/selector helper and test null/invalid/zero/unit behavior against `GS-BAL-OVERVIEW-A` and workbook structure. |
| P1 | risk tensor / risk overview (`PAGE-RISK-001` plus excluded overview mirror) | `frontend/src/features/risk-tensor/RiskTensorPage.tsx:100` `chartMagnitude`; `:227`-`:235` derived chart axes; `:483` HHI tone threshold; `frontend/src/features/risk-overview/RiskOverviewPage.tsx:398` and `:441` threshold tones | risky formal metric derivation in component | Components parse display strings to drive chart magnitude, sorting, axis scaling, and risk tone thresholds. This does not re-compute source metrics, but it can change the visible conclusion if unit/ratio strings change. `/ui/risk/overview` is excluded and must not be treated as promotion evidence. | Third slice: extract a risk view model for chart magnitude/tone, test ratio and HHI thresholds, and keep risk overview marked excluded until boundary changes. |
| P2 | executive dashboard bond headline / counterparty overlays | `frontend/src/features/executive-dashboard/components/DashboardBondHeadlineSection.tsx:22` `parseHeadlineValue`; `:84`-`:91` derived cells; `DashboardBondCounterpartySection.tsx:41` `parseYuan`; `:47` `parseRateRatio`; `:78` `ratio` | adapter-owned view-model conversion needed | These are analytical/overlay sections, not formal source-of-truth pages, but they normalize mixed legacy percent-point strings and compute shares in components. Dashboard conclusions can still be affected by unit drift. | Fourth slice: move parsing into an executive-dashboard adapter/view-model test; keep basis as analytical and do not use this to promote bond dashboard. |
| P2 | PnL attribution workbench (`PAGE-PNL-ATTR-WB-001`) | `frontend/src/features/pnl-attribution/components/AttributionWaterfallChart.tsx:43`-`:73`; `CampisiAttributionPanel.tsx:76`-`:116`; `CampisiEnhancedPanel.tsx:73`; `PnLCompositionChart.tsx:111`-`:119` and `:218` onward | mostly harmless local display formatting, but scattered | Components mostly consume `Numeric.raw` and scale to 亿 for charts/tables. That is local display formatting, but the repeated `raw ?? 0` pattern can collapse missing data into zero in charts and labels. | Later slice: introduce one PnL attribution display helper and tests for `null` vs `0` vs missing `Numeric.raw`; do not start here before product-category/balance closure. |

## Mock / Placeholder Notes

| surface | file / line | classification | note |
| --- | --- | --- | --- |
| frontend mock client balance overview | `frontend/src/api/client.ts:3968`-`:3970` | mock/demo/placeholder-only behavior | Mock mode sums fixture rows and returns a formal-looking envelope. This must remain dev/test-only and must not be used as golden truth or runtime fallback evidence. |
| ADB / average-balance normalization | `frontend/src/api/client.ts:2751` onward | adapter-owned conversion for analytical surface | This is not a current formal main-chain page in Prompt 4. Treat separately if average-balance is promoted later. |
| bond dashboard legacy components | `frontend/src/features/bond-dashboard/**` | candidate/overlay behavior | Many `nativeToNumber` usages are candidate bond-dashboard read-model display logic. They are not the first closure target because `GS-BOND-HEADLINE-A` remains blocked: contract/metric GAPs and **no** `tests/golden_samples/GS-BOND-HEADLINE-A/` on disk (not in `tests/test_golden_samples_capture_ready.py`). |

## Existing Safe Patterns To Reuse

- `frontend/src/utils/format.ts`
  - `formatNumeric(n)` is component-safe because it returns backend/adapter-owned display text.
  - `formatRawAsNumeric(...)` should stay in adapter/view-model code, not render paths.
- `frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.ts`
  - good pattern for API payload to view-model shaping before component rendering.
- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts`
  - already keeps row selection and grand-total selection out of the component and explicitly avoids re-aggregation.
- `frontend/src/components/page/FormalResultMetaPanel.tsx`
  - good pattern for showing `basis`, `quality_flag`, `fallback_mode`, and provenance without deriving financial metrics.

## Recommended First Code Slice

Pick product-category PnL first.

Why:

- It is a formal live page with `PAGE-PROD-CAT-PNL-001`.
- It has `GS-PROD-CAT-PNL-A`.
- Its risky logic is local to one page/model boundary.
- It does not require backend, schema, routing, or app-wide state changes.

Minimal execution shape:

1. Add or tighten tests in `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`.
2. Move display/tone decisions for decimal-like row values into the page model or a small local formatter.
3. Lock:
   - liability-side sign display rule
   - `business_net_income` display for `asset_total`, `liability_total`, `grand_total`
   - `null` / invalid / `0` behavior
   - no client-side aggregation of rows into totals
4. Run the narrow frontend test and then `python -m pytest -q tests/test_golden_samples_capture_ready.py`.

## Do Not Start Yet

- Do not promote `/ui/risk/overview`; it remains excluded.
- Do not use bond dashboard parsing cleanup as evidence for `GS-BOND-HEADLINE-A`.
- Do not replace all frontend number formatting globally.
- Do not change `frontend/src/api/client.ts` mock behavior inside a page-closure slice unless the slice explicitly targets mock-mode boundary hardening.
