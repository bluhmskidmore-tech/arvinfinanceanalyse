# Product-Category PnL Closure Checklist

## 1. Purpose

This checklist turns `product-category-pnl` from a vague "one page" into explicit closure units.

It is meant to answer:

- what is already closed
- what is only partially closed
- what still lacks trustworthy evidence
- which gaps are product decisions versus implementation gaps

This is a governed status sheet, not a roadmap and not a refactor wish list.

## 2. Status Rules

Use one of four states per unit:

- `CLOSED`
  - functionality complete
  - evidence exists in code/tests/docs
  - edge conditions are handled
  - UI meaning matches backend contract
- `PARTIAL`
  - main path works
  - but tests, edge states, or UI semantics are incomplete
- `NOT_TRUSTED`
  - code may exist, but closure evidence is missing
  - or the behavior is still too ambiguous to trust
- `EXCLUDED`
  - explicitly out of scope for this page

Rule:

- no unit is `CLOSED` unless evidence exists
- no missing evidence may be silently treated as success

## 3. Evidence Scope Used For This First Pass

This first pass is based on:

- `backend/app/api/routes/product_category_pnl.py`
- `backend/app/core_finance/product_category_pnl.py`
- `backend/app/services/product_category_pnl_service.py`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- `frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx`
- `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
- `frontend/src/test/ApiClient.test.ts`
- `tests/test_product_category_pnl_flow.py`
- `tests/test_product_category_mapping_contract.py`
- `tests/test_result_meta_on_all_ui_endpoints.py`
- `docs/pnl/product-category-page-truth-contract.md`
- `docs/pnl/product-category-golden-sample-a.md`
- `docs/pnl/adr-product-category-truth-chain.md`

## 4. Status Matrix

| Unit | Status | Priority | Short reason |
| --- | --- | --- | --- |
| 1. Dates | `PARTIAL` | `P1` | page tests now pin first `report_dates` vs empty list for PnL/adjustments/ledger; `as_of_date` gap + fallback semantics still open |
| 2. Detail | `PARTIAL` | `P0` | formal/scenario/detail chain, `monthly`/`ytd` scope, selector evidence, and first page-level column freeze exist; metric_id approval and exhaustive detail coverage remain open |
| 3. Refresh + Status | `PARTIAL` | `P0` | queue, sync fallback, and status flow exist; page tests now freeze 409/503/failed-terminal + polling; stale-banner contract still open |
| 4. Manual Adjustment Create | `PARTIAL` | `P0` | create path works in backend and page UI, but closure evidence is not complete enough for `CLOSED` |
| 5. Manual Adjustment List | `PARTIAL` | `P1` | list+sort query evidence in audit tests + ApiClient; dual-control “why” still narrative |
| 6. Manual Adjustment Export | `PARTIAL` | `P1` | export shares applied filter/sort with list (code+tests); BOM / scale / precision still open |
| 7. Manual Adjustment Lifecycle | `PARTIAL` | `P0` | edit/revoke/restore are implemented and tested, but not fully closed at UX/guardrail level |
| 8. Governance / Traceability | `PARTIAL` | `P0` | page-level strip + tests cover fallback/vendor/quality, dual-meta line, and explicit as_of_date gap; broader stale-banner contract still open |
| 9. Frontend Cross-Field Consistency | `PARTIAL` | `P0` | model + page test freeze liability abs vs asset signed money, footer-only grand total, yield unscaled in table; full column matrix & formal-table AsyncSection error states remain open |
| 10. Test Coverage | `PARTIAL` | `P0` | backend and frontend tests are substantial and a golden sample exists, but closure coverage is still uneven |

## 5. Unit Details

## Unit 1: Dates

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - `GET /ui/pnl/product-category/dates` exists in `backend/app/api/routes/product_category_pnl.py`
  - backend date ordering is asserted in `tests/test_product_category_pnl_flow.py`
  - page selector consumes returned dates in `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
  - basic UI consumption is exercised in `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - default `selectedDate` and ledger deep-link query encoding are frozen as pure helpers in `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts` (`nextDefaultReportDateIfUnset`, `buildLedgerPnlHrefForReportDate`), reused on the main page and legacy audit body
  - dedicated unit tests: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.dateSemantics.test.ts`
  - page truth contract subsection: `docs/pnl/product-category-page-truth-contract.md` section 10.1
  - `frontend/src/test/ProductCategoryPnlPage.test.tsx` — page-level date wiring (mock client only):
    - `Unit 1: first report_dates entry drives baseline PnL, manual adjustments list, and ledger link`: `getProductCategoryDates` returns `report_dates: ["2026-03-31", "2026-02-28", "2026-01-31"]` (API order); spies show every `getProductCategoryPnl` call uses `reportDate: 2026-03-31` and `view: monthly`, every `getProductCategoryManualAdjustments` call uses `2026-03-31`, and `product-category-ledger-link` is `/ledger-pnl?report_date=2026-03-31`
    - `Unit 1: empty report_dates skips PnL and adjustments fetches; ledger stays bare; as_of gap does not inject meta dates`: `report_dates: []` with `result_meta.generated_at` set to `2026-05-01T12:00:00Z`; `getProductCategoryPnl` / `getProductCategoryManualAdjustments` are never invoked, ledger link stays `/ledger-pnl`, `product-category-as-of-date-gap` text remains exactly `PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY` (no injected `generated_at` / report date), month `<select>` has zero `<option>` rows
- Why not `CLOSED`:
  - `as_of_date` is still an explicit outward contract gap
  - fallback-date semantics are not frozen at page level beyond the default-first-list-item rule documented in section 10.1

## Unit 2: Detail

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - detail route exists at `GET /ui/pnl/product-category`
  - `AVAILABLE_VIEWS` and multi-view determinism are exercised in `tests/test_product_category_pnl_flow.py`
  - scenario path is exercised in `tests/test_product_category_pnl_flow.py`
  - category-tree authority is protected in `tests/test_product_category_mapping_contract.py`
  - page truth is now frozen in `docs/pnl/product-category-page-truth-contract.md`
  - the main page selector scope is explicitly frozen as `monthly` and `ytd`
  - `qtd` and `year_to_report_month_end` are governed API/detail sample surfaces, not current first-screen UI requirements
  - page-level sample exists in `tests/golden_samples/GS-PROD-CAT-PNL-A/`
  - dedicated detail adapter/selector unit tests: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` (pure selectors in `productCategoryPnlPageModel.ts`: baseline vs scenario row source, grand total overlay, main-page `monthly`/`ytd` scope vs governed `available_views` superset)
  - first-stage field freeze exists in `docs/pnl/product-category-page-truth-contract.md` section 9.1
  - `frontend/src/test/ProductCategoryPnlPage.test.tsx` — `Unit 2: formal detail table renders frozen backend fields in column order without metric_id invention` overrides one known backend row (`repo_assets`) with unique raw yuan values and proves the rendered table order is category label, `cnx_scale`, `cny_scale`, `foreign_scale`, `cnx_cash`, `cny_cash`, `cny_ftp`, `cny_net`, `foreign_cash`, `foreign_ftp`, `foreign_net`, `business_net_income`, then unscaled `weighted_yield`; the same test keeps advertised `available_views` as `monthly/qtd/ytd/year_to_report_month_end` while the main page exposes only two view controls
- Why not `CLOSED`:
  - formal `metric_id` approval is still missing
  - core detail row/scenario/view-scope semantics now have isolated selector tests and one page-level table field-freeze test, but exhaustive detail semantics are not fully page-frozen

## Unit 3: Refresh + Status

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - `/refresh` and `/refresh-status` routes exist
  - queue path, sync fallback path, 409 conflict path, 503 failure path, and stale-run reconciliation are heavily tested in `tests/test_product_category_pnl_flow.py`
  - page polling behavior is tested in `frontend/src/test/ProductCategoryPnlPage.test.tsx` (queued path calls `getProductCategoryRefreshStatus` twice: `running` then `completed`)
  - page-level refresh edge states are frozen in the same file: `ActionRequestError` with HTTP 409 (conflict copy aligned with `ProductCategoryRefreshConflictError`), HTTP 503 (sync-fallback copy aligned with `ProductCategoryRefreshServiceError`), and terminal `failed` status with `detail` (error visible alongside last run id; refresh control returns to idle)
  - page shows last run id and refresh error in `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Why not `CLOSED`:
  - no page-level explicit stale-state banner contract exists
  - long-running refresh UX beyond queued polling + error surfacing is not fully specified (e.g. in-flight banner copy, timeout messaging vs `runPollingTask` generic timeout)

## Unit 4: Manual Adjustment Create

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - create route and schema exist
  - backend create path and read-model effect are exercised in `tests/test_product_category_pnl_flow.py`
  - page form submission is tested in `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - real-mode client serialization is tested in `frontend/src/test/ApiClient.test.ts` (full happy-path body and explicit `null` optional amount fields in JSON)
  - page tests freeze empty create rejection: no API call when 科目代码 is blank or when all amount fields are empty (messages `请输入科目代码。` / `至少填写一个调整数值。` via `product-category-manual-error`)
  - after successful create, `runRefreshWorkflow` is evidenced by: one `refreshProductCategoryPnl` and a second `getProductCategoryDates` fetch (code path also `refetch`es baseline/adjustments/scenario; page test stably pins `getProductCategoryDates` initial + post-refresh)
- Why not `CLOSED`:
  - no explicit page-level closure contract for every create-field combination (e.g. report_date empty only reachable in edge data states)
  - long copy/UX for validation beyond the two primary empty-payload cases is not exhaustively specified

## Unit 5: Manual Adjustment List

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - list route exists with rich query parameters
  - backend filtering, pagination, UTC timestamp validation, and export query symmetry are exercised in `tests/test_product_category_pnl_flow.py`
  - independent audit view renders current-state rows and timeline rows in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - audit filters and timeline pagination are exercised in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - current-state `current_sort_field` / `current_sort_dir` and event-timeline `event_sort_field` / `event_sort_dir` are shown to serialize into `getProductCategoryManualAdjustments` options (page tests) and into real HTTP query strings in `frontend/src/test/ApiClient.test.ts` (`buildManualAdjustmentSearchParams` in `api/client.ts`)
  - `ProductCategoryAdjustmentAuditPage.tsx` uses explicit `CURRENT_QUERY_FILTER_KEYS` vs `EVENT_QUERY_FILTER_KEYS` to reset pagination on apply; `keeps current and event sort controls independent` test freezes dual-sort behavior
  - real-mode query serialization is covered in `frontend/src/test/ApiClient.test.ts`
- Why not `CLOSED`:
  - the product rationale for two independent sort controls (vs a single model) is still a narrative gap, not a code gap
  - page-level stale/failure semantics for the list view are not fully documented
  - list closure mostly lives in the audit page rather than the main page, which increases cognitive split

## Unit 6: Manual Adjustment Export

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - export route exists
  - filtered export behavior and CSV section ordering are covered in `tests/test_product_category_pnl_flow.py`
  - audit-page export flow is exercised in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - `buildProductCategoryAuditListExportQuery` in `ProductCategoryAdjustmentAuditPage.tsx` is the single object passed to `exportProductCategoryManualAdjustmentsCsv` and matches the list request’s filter+sort options without `adjustment_limit` / `adjustment_offset` / `limit` / `offset` (proven in `ProductCategoryAdjustmentAuditPage.test.tsx` and `buildProductCategoryAuditListExportQuery` unit block)
  - real-mode export request and filename parsing are covered in `frontend/src/test/ApiClient.test.ts`
  - `uses the same filter and sort query keys for real-mode list and export (export omits pagination only)` in `ApiClient.test.ts` asserts per-key equality between list and export query strings, excluding pagination keys
- Why not `CLOSED`:
  - no clear evidence for UTF-8 BOM policy
  - no frozen behavior for very large exports
  - no explicit product contract for numeric precision equality between UI and CSV beyond existing tests

## Unit 7: Manual Adjustment Lifecycle

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - revoke/edit/restore routes all exist
  - backend lifecycle behavior is deeply exercised in `tests/test_product_category_pnl_flow.py`
  - main-page revoke/edit/restore behavior is covered in `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - audit-page edit/revoke/restore controls are covered in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - page tests `disables revoke/restore by approval_status…` (main) and `disables audit revoke/restore…` (audit) freeze: `approved` → revoke on / restore off; `pending` → both off; `rejected` → revoke off / restore on; sample rows keep edit enabled (aligns with `disabled` in `ProductCategoryPnlPage.tsx` / `ProductCategoryAdjustmentAuditPage.tsx`)
  - `product-category-adjustment-lead` and `product-category-audit-timeline-lead` copy states lifecycle actions run the same PnL refresh path as the full-page refresh before list updates; audit lead notes in-flight refresh grays out controls
  - real-mode client calls are covered in `frontend/src/test/ApiClient.test.ts`
- Why not `CLOSED`:
  - no confirmation modal for destructive revoke; not added here, remains an explicit product gap if stakeholders want friction
  - lifecycle closure is spread across main page and audit page
  - field-level edit policy for every edge case is not written as a separate human contract beyond tests + these leads

## Unit 8: Governance / Traceability

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - `result_meta` is present and checked across UI endpoints in `tests/test_result_meta_on_all_ui_endpoints.py`
  - refresh governance records and run lineage are exercised in `tests/test_product_category_pnl_flow.py`
  - the main page now renders baseline/scenario `result_meta` through `product-category-result-meta`, with page tests checking basis, fallback mode, trace id, and scenario flag visibility
  - a first-screen governance strip (`product-category-governance-strip`) surfaces: explicit `as_of_date` contract gap, non-`none` `fallback_mode`, degraded `vendor_status` / `quality_flag`, and a one-line formal vs scenario `result_meta` distinction when the scenario query is active (`ProductCategoryGovernanceStrip.tsx` + `collectProductCategoryGovernanceNotices` / `formatProductCategoryDualMetaDistinctLine` in `productCategoryPnlPageModel.ts`); page and model unit tests in `ProductCategoryPnlPage.test.tsx` and `productCategoryPnlPageModel.test.ts`
  - truth-chain ADR now fixes row authority in `docs/pnl/adr-product-category-truth-chain.md`
  - page truth contract and golden sample contract now exist under `docs/pnl/`
- Why not `CLOSED`:
  - no standalone outward `as_of_date` from the API (page only states the gap; no invented date)
  - page-level non-silent coverage for the strip is in place, but a fuller stale/refresh/cross-endpoint UX contract (e.g. in-flight/stale banner matrix) is not yet frozen

## Unit 9: Frontend Cross-Field Consistency

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - the main page is relatively disciplined and mostly renders backend-returned rows
  - display order is explicit in `ProductCategoryPnlPage.tsx`
  - liability display normalization and number formatting are centralized in `productCategoryPnlPageModel` (`formatProductCategoryRowDisplayValue`, etc.) and covered by `productCategoryPnlPageModel.test.ts` (e.g. liability vs asset sign rules, `grand_total` removed from `selectProductCategoryDetailRows`, yield vs money scaling)
  - `frontend/src/test/ProductCategoryPnlPage.test.tsx` — `ProductCategoryPnlPage > Unit 9: table 营业减收入 uses liability absolute and asset signed display, and grand_total is only in footer (not in tbody)`:
    - overrides `getProductCategoryPnl` so `repo_liabilities` / `repo_assets` share the same raw yuan string for `business_net_income` (`-123456789`)
    - rendered 营业减收入 column (second-to-last tbody cell): liability row `1.23` (absolute), asset row `-1.23` (signed)
    - rendered 加权收益率 column (last tbody cell): liability `1.41`, asset `1.47`, matching mock `weighted_yield` (no yi-yuan money scaling; accidental `formatProductCategoryValue` would collapse toward `0.00`)
    - literal `grand_total` does not appear in the table; the summary total is only via `product-category-footer-total` (`result.grand_total` path)
- Why not `CLOSED`:
  - AsyncSection stale/fallback/empty error semantics for the formal table are not fully covered (adjacent Unit 3 refresh/load evidence gaps)
  - exhaustive column-by-column cross-field matrix (every metric × row kind) is not page-frozen; only a minimal Unit 9 slice is evidenced
  - `category_id` / `side` in the test are taken from the existing mock’s known rows (`repo_liabilities` / `repo_assets`), not inferred from other domains

## Unit 10: Test Coverage

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - backend flow coverage is substantial in `tests/test_product_category_pnl_flow.py`
  - mapping contract exists in `tests/test_product_category_mapping_contract.py`
  - UI page tests exist for the main page and independent audit page
  - real-mode client request serialization is covered in `frontend/src/test/ApiClient.test.ts`
  - a governed page-level golden sample now exists at `GS-PROD-CAT-PNL-A`
- Why not `CLOSED`:
  - there is not yet a clean separation between page tests, selector tests, and formatter tests
  - scenario remains a companion probe rather than a second frozen page sample
  - full-suite golden-sample verification still has unrelated existing failures elsewhere in the repo

## 6. Current Distribution

Current first-pass distribution:

- `CLOSED`: 0
- `PARTIAL`: 10
- `NOT_TRUSTED`: 0
- `EXCLUDED`: 0

This distribution does not mean "nothing works".

It means the page has a lot of real capability, but closure evidence is still incomplete or split across backend, page UI, and audit UI.

## 7. Immediate Interpretation

Two practical conclusions follow from this first pass:

- the page is much more implemented than a casual read suggests
- the missing work is concentrated in closure semantics, documentation freeze, and edge-state confidence, not in raw feature absence

That is why the project can feel both "already large" and "not finished at all" at the same time.

## 8. Development Use Rule

Future product-category-pnl work must start from this checklist, not from a broad page rewrite.

Rule:

- pick exactly one unit before editing code
- read that unit's `Why not CLOSED` list first
- make the smallest change that adds missing evidence for that unit
- do not modify unrelated domains to move a unit status
- do not change `PARTIAL` to `CLOSED` until every blocker for that unit is removed or reclassified with evidence
- after changing a status, update the status matrix, unit details, and targeted tests in the same change

Recommended next smallest unit:

- Unit 2: Detail
  - next evidence target: formal metric approval for governed detail fields
  - do not invent `metric_id` bindings until the approved metric freeze exists
