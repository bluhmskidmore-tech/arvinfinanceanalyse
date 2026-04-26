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
| 3. Refresh + Status | `PARTIAL` | `P0` | queue, sync fallback, and status flow exist; page tests freeze 409/503/failed-terminal + polling + `product-category-refresh-status` in-flight line (`runPollingTask` `onUpdate`); stale-banner / timeout UX still open |
| 4. Manual Adjustment Create | `PARTIAL` | `P0` | create path works in backend and page UI, but closure evidence is not complete enough for `CLOSED` |
| 5. Manual Adjustment List | `PARTIAL` | `P1` | list+sort query evidence in audit tests + ApiClient; Unit 5 list/timeline failure semantics frozen (`AsyncSection` + `product-category-audit-list-timeline-async` + `within` assertions: error + no stale rows + retry); dual-control “why” still narrative |
| 6. Manual Adjustment Export | `PARTIAL` | `P1` | list/export query symmetry + real-mode key alignment + client + page Blob pass-through evidence; backend UTF-8 BOM policy + large export + full UI↔CSV precision still open |
| 7. Manual Adjustment Lifecycle | `PARTIAL` | `P0` | edit/revoke/restore are implemented and tested, but not fully closed at UX/guardrail level |
| 8. Governance / Traceability | `PARTIAL` | `P0` | page-level strip + tests cover fallback/vendor/quality, dual-meta line, and explicit as_of_date gap; broader stale-banner contract still open |
| 9. Frontend Cross-Field Consistency | `PARTIAL` | `P0` | model + page test freeze liability abs vs asset signed money, footer-only grand total, yield unscaled in table; formal-table `AsyncSection` refetch-error semantics now page-frozen; full column matrix remains open |
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
  - **In-flight refresh contract (page-level, no API change):** `runRefreshWorkflow` wires `runPollingTask`’s `onUpdate` to `setRefreshPollSnapshot({ status, run_id })`; while `handleRefresh` sets `isRefreshing`, the page renders `data-testid="product-category-refresh-status"` with copy from `formatProductCategoryRefreshStatusLine` (queued/running/`启动中…` + optional `run_id` + explicit note that refresh-related controls are temporarily disabled); `handleRefresh` clears the snapshot in `finally` so the line only exists during user-triggered refresh polling
  - **`frontend/src/test/ProductCategoryPnlPage.test.tsx` — `Unit 3: refresh shows in-flight status (queued→running), disables refresh, then records last run id`:** first `getProductCategoryRefreshStatus` is delayed 100ms so `queued` is observable on `product-category-refresh-status`; then the line transitions to `running`; `product-category-refresh-button` is disabled while in flight; after completion the status line unmounts, `getProductCategoryRefreshStatus` is called twice with the same `run_id`, and `最近刷新任务：` shows `product_category_pnl:test-run`
  - **Error-path guardrails extended in the same file:** after 409 and 503 refresh failures, `product-category-refresh-status` stays absent and `最近刷新任务：` never appears; after terminal `failed` status, `product-category-refresh-status` is cleared (no stuck in-flight banner) while the error copy and failed `run_id` line remain visible and the refresh button returns to idle
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
  - **List/timeline failure semantics (audit page, `getProductCategoryManualAdjustments` rejects):** `LegacyProductCategoryAdjustmentAuditBody` wraps the list/timeline `AsyncSection` in `data-testid="product-category-audit-list-timeline-async"` for a single page-level region; the `AsyncSection` uses `isError={adjustmentsQuery.isError}` and `onRetry={() => adjustmentsQuery.refetch()}`; when `isError` is true, `AsyncSection` replaces its children (see `frontend/src/components/AsyncSection.tsx`), so `audit-current-state` / `audit-event-list` (and event `data-testid`s) are not rendered—no silent display of prior rows in the DOM (React Query may retain prior `data` in cache, but the error branch does not render row bodies)
  - **`frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` — `Unit 5: list/timeline failure surfaces AsyncSection error, hides current+event bodies, and retry refetches`:** waits until `审计-报表月份` has a value (adjustments query enabled); `getProductCategoryManualAdjustments` throws until a flag flips; scopes assertions with `within(screen.getByTestId("product-category-audit-list-timeline-async"))`: `数据载入失败` + “当前页面保留重试入口” copy, `audit-current-state` / `audit-event-list` absent inside that region, `重试` triggers a second fetch and then `audit-current-state` shows `after-retry-row`
  - **Same file — `Unit 5: failed list refetch does not leave prior current-state or timeline rows visible`:** first response includes `unit5-stale-marker` and timeline `audit-event-pca-audit-stale-1-edited`; after `audit-filter-account-code` + `audit-apply-filters`, second fetch rejects; `within(product-category-audit-list-timeline-async)` shows `数据载入失败` + `重试`, and that region does not contain `audit-current-state` / `audit-event-list`; stale marker and `audit-event-pca-audit-stale-1-edited` are gone from the document
- Why not `CLOSED`:
  - the product rationale for two independent sort controls (vs a single model) is still a narrative gap, not a code gap
  - broader stale/failure matrix (e.g. partial degradation, export vs list divergence under error, main-page list parity) is not fully closed
  - list closure mostly lives in the audit page rather than the main page, which increases cognitive split

## Unit 6: Manual Adjustment Export

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - export route exists
  - filtered export behavior and CSV section ordering are covered in `tests/test_product_category_pnl_flow.py`
  - audit-page export flow is exercised in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - `buildProductCategoryAuditListExportQuery` in `ProductCategoryAdjustmentAuditPage.tsx` is the single object passed to `exportProductCategoryManualAdjustmentsCsv` and matches the list request’s filter+sort options without `adjustment_limit` / `adjustment_offset` / `limit` / `offset` (see `buildProductCategoryAuditListExportQuery` + `CSV export uses the same applied filter+sort as the list request (omits only pagination options)` in `ProductCategoryAdjustmentAuditPage.test.tsx`)
  - **Page-level CSV pass-through (no frontend numeric rewrite; no BOM prepended by the download path):** `downloadAuditCsv` in `ProductCategoryAdjustmentAuditPage.tsx` is documented as passing the API string into `Blob` as a single part without prepending a BOM (BOM in the file, if any, is defined by the server response); **`Unit 6: export pipes API CSV into the download Blob without rewriting numbers or a BOM`** intercepts `Blob` and asserts the string body equals the mocked `exportProductCategoryManualAdjustmentsCsv` `content` byte-for-byte (including long decimal digits) and the first code point is not U+FEFF when the mock omits a BOM
  - **`frontend/src/test/ApiClient.test.ts` — `uses real mode to export filtered product-category manual adjustments as csv`:** `payload.content` is strictly `===` the `response().text` string; when that string has no leading BOM, `payload.content.codePointAt(0) !== 0xFEFF` (client does not insert a BOM in this path)
  - **`uses the same filter and sort query keys for real-mode list and export (export omits pagination only)`:** for every key present on the export URL, values match the list call; `adjustment_limit` / `adjustment_offset` / `limit` / `offset` are absent on export
- **BOM policy (closure stance):** no governed rule is recorded for whether the **backend** CSV is UTF-8 with or without a leading BOM; the **frontend** path shown above only forwards `text()` to `content` and into `new Blob([content], …)` without adding `\uFEFF`. Whether production exports include a BOM is **unknown** from these tests and must not be invented here.
- Why not `CLOSED`:
  - backend/global UTF-8 BOM policy for generated CSV is still not specified in tests or this checklist (only the non-mutation of “response as received” in the two shown layers)
  - no frozen behavior for very large exports
  - no explicit end-to-end product contract that UI-rendered money strings equal CSV number strings in every cell (only pass-through and sample decimals in tests)

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
  - **Formal table `AsyncSection` on failed baseline refetch (no silent stale success UI):** `ProductCategoryPnlPage.tsx` wires the formal table through `AsyncSection` with `isError={baselineQuery.isError}`; React Query v5 `QueryObserverRefetchErrorResult` keeps `isError: true` after a refetch failure even when prior `data` exists, so the error branch replaces table children (see `frontend/src/components/AsyncSection.tsx`). **`product-category-summary`** (passed as `extra`) and **`product-category-footer-total`** are gated with `!baselineQuery.isError` so cached baseline money is not shown beside the error state as if the load succeeded.
  - **`frontend/src/test/ProductCategoryPnlPage.test.tsx` — `Unit 9: formal baseline refetch failure shows AsyncSection error; no stale table, summary, or footer`:** initial `getProductCategoryPnl` succeeds with `repo_assets` row label `unit9-formal-asyncsection-stale-marker`; after `product-category-refresh-button` (sync-completed refresh mock so `runRefreshWorkflow` runs `baselineQuery.refetch()`), the next `getProductCategoryPnl` rejects; within the `<section>` that contains the title `产品类别损益分析表（单位：亿元）`, asserts `数据载入失败。` + retry copy + `重试`; document-wide asserts `product-category-table`, the stale marker, `product-category-summary`, and `product-category-footer-total` are absent.
- Why not `CLOSED`:
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
