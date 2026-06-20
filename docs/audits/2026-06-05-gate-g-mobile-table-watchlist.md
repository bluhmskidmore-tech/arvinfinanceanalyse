# Gate G Mobile Table Watchlist

**Date:** 2026-06-05

**Scope:** Mobile decision readouts before dense lower-page tables on flagship finance routes.

**Rule:** Raw grids remain available for audit. Mobile readouts are display-only summaries over existing payload fields; they must not redefine metric formulas, formal-use status, or governance markers.

## Priority Watchlist

| Priority | Table test id | Page / section | Business question | Current mobile behavior | Proposed mobile readout | Raw grid preservation |
| --- | --- | --- | --- | --- | --- | --- |
| Done | `bond-analysis-accounting-dv01-raw-grid` | `/bond-analysis` accounting DV01 | Which accounting category carries the DV01/duration exposure? | Raw grid exists; mobile now gets a compact readout first. | Accounting category, largest DV01 category, duration, money value, position count. | Preserved after `bond-analysis-accounting-dv01-mobile-readout`. |
| Done | `bond-analysis-holdings-raw-grid` | `/bond-analysis` top holdings | Which holding dominates market value, yield, duration, and weight? | Raw grid exists; mobile now gets a compact readout first. | Top holding count, largest holding, rating, market value, yield, duration, weight. | Preserved after `bond-analysis-holdings-mobile-readout`. |
| Done | `pnl-attribution-product-category-attribution-raw-grid` | `/pnl-attribution` product-category attribution | How did monthly business net income move, and which effect explains the move? | Previously controlled horizontal scroll only. | Business-net-income delta, largest displayed effect, unexplained effect, closure error, row state. | Preserved after `pnl-attribution-product-category-attribution-mobile-readout`. |
| Done | `pnl-attribution-product-category-ytd-raw-grid` | `/pnl-attribution` product-category YTD | What is the YTD operating-income picture before inspecting the grid? | Previously controlled horizontal scroll only. | YTD business net income, scale, weighted yield, displayed row count. | Preserved after `pnl-attribution-product-category-ytd-mobile-readout`. |
| Done | `product-category-table` | `/product-category-pnl` formal table | What does the official product-category PnL table say for total, assets, liabilities, and first material category? | Raw grid exists; mobile now gets a compact formal table readout first. | Report date, view, displayed row count, total/asset/liability business net income, first material row, scale, and weighted yield. | Preserved after `product-category-formal-table-mobile-readout`; raw grid anchored as `product-category-formal-table-raw-grid`. |
| Done | `product-category-attribution-comparison-table` | `/product-category-pnl` attribution comparison | Which product category explains the monthly movement and whether the bridge closes? | Raw table exists; mobile now gets a compact attribution bridge readout first. | Delta, largest effect, unexplained effect, closure error, partial/complete state. | Preserved after `product-category-attribution-comparison-mobile-readout`. |
| Done | `product-category-attribution-detail-table` | `/product-category-pnl` attribution detail | What changed between current and prior periods for scale, yield, cash, FTP, and income? | Raw table exists; mobile now gets a compact current/prior detail readout first. | Current/prior date pair, selected category detail, current/prior business net income, current/prior scale/yield. | Preserved after `product-category-attribution-detail-mobile-readout`. |
| Done | `product-category-liability-side-detail-matrix` | `/product-category-pnl` liability trend matrix | Which liability bucket moved in amount and rate across periods? | Raw matrix remains; mobile now gets a compact liability readout first. | Latest liability bucket, amount movement, rate movement, period count, summary row. | Preserved after `product-category-liability-side-detail-matrix-mobile-readout`. |
| Done | `product-category-liability-side-currency-matrix-*` | `/product-category-pnl` liability currency matrices | Is the movement RMB or foreign-currency driven? | Raw matrices remain; mobile now gets compact per-currency readouts first. | Currency, latest amount/rate, amount delta, rate delta, period label. | Preserved after `product-category-liability-side-currency-matrix-*-mobile-readout`. |
| Boundary-reviewed | `product-category-liability-side-detail-table` | `/product-category-pnl` liability fallback table | What does the fallback liability detail say when matrix data is unavailable? | Current model-derived liability detail rows also produce detail-matrix rows, so this defensive branch is not a natural production browser path today. | Latest amount, amount movement, latest rate, rate movement, comparison period. | Fallback raw table remains defensive; model-boundary evidence now replaces synthetic production browser proof. |
| P3 | `pnl-attribution-advanced-*` tables | `/pnl-attribution` advanced / Campisi / TPL lower diagnostics | Which advanced attribution diagnostics need deeper inspection? | Several lower diagnostic tables still rely on native table layout or inline table styles. | Add only after decision-critical product-category and formal tables are mobile hardened. | Preserve all diagnostic tables. |

## Next Fix Order

1. Keep lower `/pnl-attribution` advanced diagnostics behind the completed product-category decision-critical surfaces.
2. Re-score any remaining Gate G work only after browser evidence exists for the specific raw table/readout pair.

## Latest Evidence

`/product-category-pnl` formal table mobile readout was completed after RED confirmed the missing `product-category-formal-table-mobile-readout` anchor. Evidence is saved under `frontend/.codex-tmp/product-category-pnl-gate-g/`, including desktop/tablet/mobile screenshots, `mobile-formal-table-readout.png`, and `layout-verification.json`.

`/product-category-pnl` attribution comparison/detail mobile readouts were completed after RED confirmed the missing `product-category-attribution-comparison-mobile-readout` and `product-category-attribution-detail-mobile-readout` anchors. Evidence is saved under `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/`, including desktop/tablet/mobile screenshots, `mobile-attribution-comparison-readout.png`, `mobile-attribution-detail-readout.png`, and `layout-verification.json`.

`/product-category-pnl` liability-side detail/currency mobile readouts were completed after RED confirmed the missing `product-category-liability-side-detail-matrix-mobile-readout` and `product-category-liability-side-currency-matrix-cny-mobile-readout` anchors. Evidence is saved under `frontend/.codex-tmp/product-category-pnl-gate-g-liability/`, including desktop/tablet/mobile screenshots and `browser-verification.json`. The normal local payload reaches `product-category-liability-side-detail-matrix`; model-level evidence now records that current liability detail rows also produce detail-matrix rows, so the fallback table readout should be reviewed as a defensive boundary rather than browser-proven with synthetic payloads.

## Evidence Limit

`moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` are not exposed in this Codex App session. This watchlist is therefore a frontend readability and traceability artifact only; it does not certify metric definitions or source lineage.
