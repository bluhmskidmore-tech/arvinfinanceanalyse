# Product-Category Page Truth Contract

## 1. Purpose

This document freezes the minimum page-level truth for the product-category PnL page.

It exists to stop three recurring failures:

- treating the page like a generic frontend table
- letting AI infer row meaning from nearby holdings logic
- changing page output without an explicit page-level acceptance target

This is a page truth contract, not a replacement for implementation code, DTO schemas, or formula code.

## 2. Page Identity

- Page ID: `PAGE-PROD-CAT-001`
- Page name: `产品损益`
- Frontend route: `/product-category-pnl`
- Primary governed API: `/ui/pnl/product-category`
- Supporting APIs:
  - `/ui/pnl/product-category/dates`
  - `/ui/pnl/product-category/refresh`
  - `/ui/pnl/product-category/refresh-status`
  - `/ui/pnl/product-category/manual-adjustments`
  - `/ui/pnl/product-category/manual-adjustments/export`

## 3. Primary Business Question

The page must answer one question first:

`在选定 report_date 和 view 下，产品分类损益总计是多少，资产 / 负债 / 总计分别是多少，主要由哪些产品分类行贡献。`

The first screen is not allowed to bury that answer behind auxiliary controls or unrelated branch content.

## 4. Questions This Page Must Not Answer

This page must not silently turn into a holdings research page.

It must not answer:

- `利率债 / 信用债 / 转债` style holdings-side decomposition
- generic ledger-account PnL questions that belong to `/ledger-pnl`
- branch-specific monthly operating analysis conclusions
- ad hoc research categories inferred from nearby code

## 5. Truth Chain

The accepted truth chain for the page is:

`总账对账YYYYMM.xlsx + 日均YYYYMM.xlsx`
-> `backend/app/services/product_category_source_service.py`
-> `backend/app/core_finance/product_category_pnl.py`
-> `product_category_pnl_formal_read_model`
-> `backend/app/services/product_category_pnl_service.py`
-> `/ui/pnl/product-category`
-> `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`

Any edit that changes page meaning must trace through that full chain.

## 6. Page Basis and Boundaries

- Default basis: `formal`
- Backend governed detail views:
  - `monthly`
  - `qtd`
  - `ytd`
  - `year_to_report_month_end`
- Main page view selector:
  - `monthly`
  - `ytd`
- `qtd` and `year_to_report_month_end` are governed API/detail sample surfaces, not current first-screen UI requirements.
- Do not add `qtd` or `year_to_report_month_end` to the main page selector without updating this contract, the closure checklist, and page-level tests.
- Allowed scenario path: explicit `scenario_rate_pct`
- Analytical overlay is not the default interpretation of this page
- Mock data must not masquerade as governed truth

## 7. Row Authority

Page row meaning is governed by:

- the paired ledger + average source files
- the canonical mapping authority in `backend/app/core_finance/config/product_category_mapping.py`
- the formal aggregation path in `backend/app/core_finance/product_category_pnl.py`

Forbidden row authority:

- inferring categories from `zqtz` holdings-side logic
- inferring categories from research-style bond buckets
- copying semantics from unrelated PnL or analytics pages
- treating frontend sort order as business truth

## 8. First-Screen Required Sections

The minimum governed first-screen structure is:

- report-date selector
- view selector for the current main page scope: `monthly` and `ytd`
- baseline totals
- scenario comparison state
- category rows
- result metadata / freshness strip
- adjustment / audit entry point

## 9. Field Freeze

The first freeze is field-level. Do not invent `metric_id` bindings before they are approved.

Headline truth fields:

- `result.asset_total.business_net_income`
- `result.liability_total.business_net_income`
- `result.grand_total.business_net_income`

Minimum row fields:

- `category_id`
- `category_name`
- `side`
- `level`
- `view`
- `report_date`
- `business_net_income`
- `children`

Minimum scenario comparison fields:

- `scenario_rate_pct`
- `asset_total.cny_ftp`
- `asset_total.foreign_ftp`
- `asset_total.business_net_income`

### 9.1 First-Stage Field Freeze

This is a page-level field freeze, not a formal `metric_id` approval.

| Field path | Page meaning | Unit / display | Baseline vs scenario behavior | Frontend rule |
| --- | --- | --- | --- | --- |
| `result.view` | selected governed detail view | enum string | baseline and scenario use the selected view | pass through selected view; do not remap |
| `result.available_views` | backend governed detail API view surface | enum string list | comes from backend payload | do not use as current main-page selector source |
| `result.rows[].category_id` | governed product-category row identity | string id | scenario must preserve baseline row identity | do not infer from holdings or research buckets |
| `result.rows[].side` | row side for asset/liability presentation | `asset` / `liability` | scenario must preserve row side | may drive display-only liability sign normalization |
| `result.rows[].business_net_income` | row-level business net income contribution | page display uses two decimals in yi yuan | scenario may change value, not row identity | do not re-aggregate in frontend |
| `result.asset_total.business_net_income` | asset-side total business net income | page display uses two decimals in yi yuan | scenario may change value through scenario payload | display backend total; do not recompute from rows |
| `result.liability_total.business_net_income` | liability-side total business net income | page display uses two decimals in yi yuan | scenario may change value through scenario payload | display backend total; sign normalization is display-only |
| `result.grand_total.business_net_income` | page headline/footer total | page display uses two decimals in yi yuan | scenario grand total wins only when scenario payload exists | display backend total; do not recompute asset + liability in frontend |
| `result.scenario_rate_pct` | applied FTP scenario rate | percent value | null for formal baseline; populated for scenario payload | scenario display changes only after explicit apply |
| `result_meta.basis` | payload basis | `formal` / `scenario` | formal baseline uses `formal`; scenario request uses `scenario` | surface as metadata; do not reinterpret |
| `result_meta.scenario_flag` | whether payload is scenario output | boolean | false for formal baseline; true for scenario payload | must align with `basis` |

First-stage prohibitions:

- do not invent `metric_id` bindings from this table
- do not treat liability sign normalization as backend truth
- do not use `available_views` to add first-screen controls
- do not recompute `grand_total` in frontend
- do not change row identity during scenario display

## 10. Time Semantics

- `requested_report_date`: query parameter `report_date`
- `resolved_report_date`: currently `result.report_date`
- `generated_at`: `result_meta.generated_at`
- `as_of_date`: currently missing as a standalone outward field; treat this as an explicit contract gap, not an implicit assumption

No silent fallback is allowed. If degradation occurs, it must be visible.

### 10.1 Report-date list and default selection (UI)

- The report-date dropdown is populated from `GET /ui/pnl/product-category/dates` → `result.report_dates` in the order returned by the API (backend ordering is asserted in `tests/test_product_category_pnl_flow.py`).
- When local `selectedDate` is empty and `report_dates` is non-empty, the page sets `selectedDate` to the **first** list entry (`nextDefaultReportDateIfUnset` in `productCategoryPnlPageModel.ts`). This applies to the main product-category PnL page and the legacy manual-adjustment audit body on the same feature.
- The link from this page to `/ledger-pnl` for the same calendar selection uses `buildLedgerPnlHrefForReportDate`: empty selection → `/ledger-pnl` with no query; otherwise `report_date` is passed via `encodeURIComponent`.
- This subsection does not add an outward `as_of_date`; section 10 above remains the source of truth for that gap.

## 11. Result Meta Visibility

The page must make these fields inspectable:

- `basis`
- `result_kind`
- `formal_use_allowed`
- `scenario_flag`
- `quality_flag`
- `vendor_status`
- `fallback_mode`
- `trace_id`
- `source_version`
- `rule_version`
- `cache_version`
- `generated_at`

In addition, the first-screen governance strip (above the `FormalResultMetaPanel`) must not stay silent when:

- `fallback_mode` is not `none` (dedicated `role="status"` line; copy references the raw field value)
- `vendor_status` is `vendor_stale` or `vendor_unavailable`, or `quality_flag` is not `ok` (dedicated status lines; no ZQTZ/holdings inference)
- both formal baseline and scenario responses are loaded: a one-line line states that the two `result_meta` values are shown in separate cards and lists `basis` + `trace_id` for each (they must not be merged into a single effective meta)

The strip also states the explicit outward gap that there is no standalone `as_of_date` field (see §10); the page does not fabricate a calendar `as_of_date`.

The page must explicitly surface:

- no data
- stale data
- fallback mode
- loading failure
- metric-definition pending confirmation

## 12. Minimum Reconciliation Rules

Before the page can be treated as stable truth, these must remain true:

- `asset_total.business_net_income + liability_total.business_net_income == grand_total.business_net_income`
- `ytd` and `year_to_report_month_end` payloads match under the currently governed rules
- approved manual adjustments can change governed output through the same API path
- scenario requests change scenario-owned fields without changing baseline row identity

## 13. Current Evidence

Current evidence for this page-level contract:

- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `frontend/src/test/ProductCategoryPnlPage.test.tsx` (including governance-strip degraded-meta and formal/scenario distinct-line cases)
- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` (governance notice helpers)
- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.dateSemantics.test.ts`
- `frontend/src/test/ProductCategoryBranchSwitcher.test.tsx`
- `frontend/src/test/ApiClient.test.ts`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`

## 14. Open Gaps

This contract deliberately leaves these gaps visible:

- no approved `metric_id` freeze yet
- no standalone outward `as_of_date` yet
- first sample pack is now checked in as `GS-PROD-CAT-PNL-A`

These are not reasons to guess. They are the next governance gaps to close after the first sample freeze.
