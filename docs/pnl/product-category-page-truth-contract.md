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
- Baseline FTP policy is report-year based: 2025 uses `1.75%`; 2026 uses `1.60%`.
- Analytical overlay is not the default interpretation of this page
- Mock data must not masquerade as governed truth
- `ytd` and `year_to_report_month_end` are natural-year views: PnL fields must sum monthly `monthly_pnl` from January through the requested report month. They must not add prior-month `ending_balance` values or switch to ending-balance cash. Scale-sensitive calculations use each included month’s monthly scale basis weighted by calendar days, and return `quality_flag=warning` when prior months in the year are unavailable for coverage evidence.

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

The first freeze is field-level. P0 first approved the three headline `metric_id` bindings below.
On 2026-05-11, product decision `3C` approved expanding detail rows into formal metrics for scale, FTP, net income, and yield fields. The approval is directional; concrete `metric_id` numbering, field matrix, dictionary rows, and tests must be added in a dedicated follow-up before any new `MTR-PCP-*` id is treated as active.

Headline truth fields:

- `MTR-PCP-001`: `result.asset_total.business_net_income`
- `MTR-PCP-002`: `result.liability_total.business_net_income`
- `MTR-PCP-003`: `result.grand_total.business_net_income`

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

This is a page-level field freeze for detail semantics. It is also the starting field set for the 2026-05-11 detail-metric expansion decision, but individual detail fields are not dictionary-active until their concrete `metric_id` rows and tests are added.

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

- do not invent detail `metric_id` numbers from this table; add the approved field matrix and dictionary rows first
- do not treat liability sign normalization as backend truth
- do not use `available_views` to add first-screen controls
- do not recompute `grand_total` in frontend
- do not change row identity during scenario display

### 9.2 Manual adjustment create — client validation (main page)

`ProductCategoryPnlPage` `handleManualAdjustmentSubmit` runs **before** `createProductCategoryManualAdjustment`: empty `report_date` → `请选择报表月份。`; empty `account_code` → `请输入科目代码。`; all amount fields empty → `至少填写一个调整数值。`; any single amount non-empty (with date + code) proceeds to create. Frozen test names and matrix: `docs/pnl/product-category-closure-checklist.md` Unit 4 + `frontend/src/test/ProductCategoryPnlPage.test.tsx` (`Unit 4: …` cases).

### 9.3 Manual Adjustment Surface Ownership

This section documents existing tested surfaces; it does not add lifecycle friction or change endpoint policy.

- `/product-category-pnl`: canonical first-screen summary and quick-action surface.
- `/product-category-pnl/audit`: canonical full audit surface for current-state list, event timeline, filters, dual sort, pagination, retry, and CSV export.
- Full event-timeline evidence belongs to the audit page; the main page may show only a summary count and audit link.
- Lifecycle actions (`edit`, `revoke`, `restore`) are allowed on both surfaces only as already tested; the source-of-truth behavior is the shared manual-adjustment API plus PnL refresh path.
- No confirmation modal, dual-sort rationale, or export policy is approved by this surface note.

### 9.4 Manual Adjustment Edit Field Policy

This is a documentation freeze of existing tested behavior, not a new product approval.

- `report_date` is carried from the selected/current row and stays read-only in the form.
- `operator`, `approval_status`, `account_code`, `currency`, `account_name`, `beginning_balance`, `ending_balance`, `monthly_pnl`, `daily_avg_balance`, and `annual_avg_balance` are the current editable draft fields.
- `approval_status` controls revoke/restore availability only as already tested: approved -> revoke enabled, pending -> neither, rejected -> restore enabled.
- Edit remains enabled for approved, pending, and rejected rows in the existing tests; do not infer this as final product policy for every edge case.
- Edit submit reuses the same validation gate as create: report date, account code, and at least one numeric adjustment field are required before the API call.
- No confirmation modal or additional revoke friction is approved here.

## 10. Time Semantics

- `requested_report_date`: user-requested report date; currently query parameter `report_date`
- `resolved_report_date`: backend-returned report date; currently `result.report_date`
- `as_of_date`: intentionally not a standalone outward field for product-category PnL
- `generated_at`: system generation timestamp; currently `result_meta.generated_at`

Decision 1B (2026-05-11): do not add a standalone outward `as_of_date` field for this page. The page must show `report_date` and `generated_at` separately and must not present either as a replacement `as_of_date`.

Implementation status: the no-standalone-field decision is now page-visible via `PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY`; API schemas should not add an `as_of_date` field for product-category PnL without reopening this decision.

No silent fallback is allowed. If degradation occurs, it must be visible.

### 10.1 Report-date list and default selection (UI)

- The report-date dropdown is populated from `GET /ui/pnl/product-category/dates` → `result.report_dates` in the order returned by the API (backend ordering is asserted in `tests/test_product_category_pnl_flow.py`).
- When local `selectedDate` is empty and `report_dates` is non-empty, the page sets `selectedDate` to the **first** list entry (`nextDefaultReportDateIfUnset` in `productCategoryPnlPageModel.ts`). This applies to the main product-category PnL page and the legacy manual-adjustment audit body on the same feature.
- Decision 2A (2026-05-11): after the user has a non-empty selected date, do not silently switch it. If the selected date disappears from the returned list, keep the selection and surface the existing no-data/error path rather than silently moving to the first returned date.
- The link from this page to `/ledger-pnl` for the same calendar selection uses `buildLedgerPnlHrefForReportDate`: empty selection → `/ledger-pnl` with no query; otherwise `report_date` is passed via `encodeURIComponent`.
- This subsection does not add an outward `as_of_date`; section 10 above records the permanent no-standalone-field decision.

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

The strip also states the explicit product decision that there is no standalone `as_of_date` field (see section 10); the page does not fabricate a calendar `as_of_date`.

The page must explicitly surface:

- no data
- stale data
- fallback mode
- loading failure
- metric-definition pending confirmation

### 11.1 Stale / Fallback / Refresh Matrix Skeleton

This skeleton separates behavior already evidenced by tests from behavior that still needs product/API approval. It is intentionally not final UX copy.

| State | Current evidence | Current page expectation | Open decision |
| --- | --- | --- | --- |
| `fallback_mode != none` | `ProductCategoryGovernanceStrip` / `collectProductCategoryGovernanceNotices`; page test covers degraded meta | Dedicated first-screen status line that references raw `fallback_mode` metadata | Final banner copy and whether it belongs outside the governance strip |
| `vendor_status in {vendor_stale, vendor_unavailable}` | governance-strip helper and page test | Dedicated first-screen status line; no holdings/ZQTZ inference | Product wording for stale/vendor unavailable severity |
| `quality_flag != ok` | governance-strip helper and page test | Dedicated first-screen status line | Product wording for warning/error/stale levels |
| formal and scenario both loaded | dual-meta helper and page test | Formal and scenario result metadata remain separate | None for the existing one-line distinction |
| refresh `queued` / `running` | Unit 3 page tests and `runRefreshWorkflow` polling snapshot | In-flight line shows status and disables refresh-related controls | None for queued/running visibility; timeout wording remains open |
| refresh terminal `failed` | Unit 3 page tests | Error remains visible and in-flight line clears | Final long-running failure/timeout copy |
| empty `report_dates` | Unit 1 page test | Skip PnL/adjustment fetches and keep ledger link bare | None for empty-list behavior |
| selected date no longer appears in `report_dates` | Decision 2A + `nextDefaultReportDateIfUnset` + Unit 1 page test | Keep the selected date; do not silently switch to the first returned date; surface the existing no-data/error path | None for no-silent-switch behavior |
| standalone `as_of_date` | no-standalone-field copy and page/model test | Do not fabricate `as_of_date` from report date or generated time | None unless product reopens 1B |

Unknown cells in this table must not be converted to code behavior without updating this contract and targeted tests.

### 11.2 Evidence-Only Cross-Surface State Matrix

This matrix records only states already covered by tests plus the 2026-05-11 no-silent-date-switch / no-standalone-as_of_date decisions; it does not define timeout copy.

| Surface | State | Evidence | Current expectation | Still open |
| --- | --- | --- | --- | --- |
| `/product-category-pnl` formal table | baseline refetch failure after refresh | `Unit 9: formal baseline refetch failure shows AsyncSection error; no stale table, summary, or footer` | error branch replaces table, summary, and footer instead of presenting cached money as success | final stale-banner copy |
| `/product-category-pnl` refresh control | queued / running | `Unit 3: refresh shows in-flight status (queued→running), disables refresh, then records last run id` | in-flight line is visible and refresh button is disabled until completion | timeout wording |
| `/product-category-pnl` refresh control | HTTP 409 conflict | `surfaces refresh conflict (409) with explicit copy and does not record a successful run id` | error copy is visible; no successful run id is recorded | product wording beyond current copy |
| `/product-category-pnl` refresh control | HTTP 503 sync fallback failure | `surfaces sync-fallback service failure (503) with explicit copy and does not record a successful run id` | error copy is visible; no successful run id is recorded | product wording beyond current copy |
| `/product-category-pnl` refresh control | terminal failed status | `surfaces terminal failed refresh status as an error (not silent success)` | terminal failure stays visible and the in-flight line clears | long-running failure copy |
| `/product-category-pnl/audit` list/timeline | initial/refetch list failure | `Unit 5: list/timeline failure surfaces AsyncSection error, hides current+event bodies, and retry refetches` | error region hides current-state and event bodies until retry succeeds | partial degradation policy |
| `/product-category-pnl/audit` list/timeline | failed refetch after prior rows | `Unit 5: failed list refetch does not leave prior current-state or timeline rows visible` | stale prior rows are not left in the DOM under the error region | export-vs-list divergence policy |
| `GET /ui/pnl/product-category` backend detail | read model locked | `test_product_category_detail_returns_503_when_read_model_is_locked` | endpoint fails closed with 503 instead of fabricating data | user-facing copy at page layer |
| `GET /ui/pnl/product-category/dates` backend dates | read model locked | `test_product_category_dates_returns_503_when_read_model_is_locked` | endpoint fails closed with 503 instead of fabricating dates | user-facing copy for date-list failure |

## 12. Minimum Reconciliation Rules

Before the page can be treated as stable truth, these must remain true:

- `asset_total.business_net_income + liability_total.business_net_income == grand_total.business_net_income`
- `ytd` and `year_to_report_month_end` payloads match under the currently governed rules
- partial YTD payloads are allowed, but must surface `result_meta.quality_flag=warning`
- approved manual adjustments can change governed output through the same API path
- scenario requests change scenario-owned fields without changing baseline row identity

## 13. Current Evidence

Current evidence for this page-level contract:

- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `tests/test_result_meta_on_all_ui_endpoints.py` (product-category dates sweep + formal vs scenario `basis` on detail)
- `frontend/src/test/ProductCategoryPnlPage.test.tsx` (including governance-strip degraded-meta and formal/scenario distinct-line cases)
- `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` (audit list, export, and `AsyncSection` failure semantics)
- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` (selectors, formatters, governance notice helpers, unknown `category_id` sort fallback)
- `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.dateSemantics.test.ts`
- `frontend/src/test/ProductCategoryBranchSwitcher.test.tsx`
- `frontend/src/test/ApiClient.test.ts`
- `tests/golden_samples/GS-PROD-CAT-PNL-A/` + `docs/pnl/product-category-golden-sample-a.md`
- Layered coverage index: `docs/pnl/product-category-closure-checklist.md` → **Unit 10: Test Coverage**
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`

## 14. Open Gaps

This contract deliberately leaves these gaps visible:

- detail `metric_id` expansion is approved directionally (2026-05-11, decision 3C), but concrete dictionary rows / numbering / tests are not yet implemented
- standalone outward `as_of_date` is intentionally not provided for this page (2026-05-11, decision 1B)
- first sample pack is now checked in as `GS-PROD-CAT-PNL-A`

These are not reasons to guess. They are the next governance gaps to close after the first sample freeze.

## 15. P0 Closure Gate

P0 is a closure gate, not a new feature lane.

The current P0 boundary is:

- P0-approved active formal metric ids are currently `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003`.
- detail `metric_id` expansion is approved directionally by decision 3C; it remains implementation-required for field matrix, numbering, dictionary rows, and tests
- standalone outward `as_of_date` is a no-field product/API decision for this page
- stale/fallback/refresh visibility may be locked only where current tests already prove behavior
- unresolved stale/fallback wording and timeout wording remain decision-required; decision 2A page coverage for disappeared selected dates is now frozen in the Unit 1 page test

Rules for this gate:

- do not add additional `MTR-*` rows for product-category fields from sample evidence alone; use the approved 3C detail-metric follow-up matrix
- do not infer `as_of_date` from `report_date` or `generated_at`
- do not treat the companion scenario probe as a second full golden matrix sample
- do not convert decision-required cells in section 11.1 into code behavior without updating this contract and targeted tests

P0 evidence can lock known stale/fallback behavior, but cannot choose unresolved product copy or API shape.
