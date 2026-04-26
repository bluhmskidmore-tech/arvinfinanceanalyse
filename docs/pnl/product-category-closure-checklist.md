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
| 1. Dates | `PARTIAL` | `P1` | dates endpoint and selector exist, but outward date semantics are not fully frozen |
| 2. Detail | `PARTIAL` | `P0` | formal/scenario/detail chain, current `monthly`/`ytd` page scope, and core selector evidence exist, but field freeze and exhaustive detail coverage are not complete |
| 3. Refresh + Status | `PARTIAL` | `P0` | queue, sync fallback, and status flow exist; UI semantics are only partially verified |
| 4. Manual Adjustment Create | `PARTIAL` | `P0` | create path works in backend and page UI, but closure evidence is not complete enough for `CLOSED` |
| 5. Manual Adjustment List | `PARTIAL` | `P1` | audit page list/filter/paging are strong, but sorting semantics are not fully documented as product truth |
| 6. Manual Adjustment Export | `PARTIAL` | `P1` | export route and audit-page download flow exist, but large-volume and encoding guarantees are not fully frozen |
| 7. Manual Adjustment Lifecycle | `PARTIAL` | `P0` | edit/revoke/restore are implemented and tested, but not fully closed at UX/guardrail level |
| 8. Governance / Traceability | `PARTIAL` | `P0` | result metadata and run lineage exist, but degraded-state visibility is not fully closed at page level |
| 9. Frontend Cross-Field Consistency | `PARTIAL` | `P0` | there is some discipline and formatting logic, but not enough explicit evidence to call it fully closed |
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
- Why not `CLOSED`:
  - `as_of_date` is still an explicit outward contract gap
  - fallback-date semantics are not frozen at page level
  - there is no dedicated formatter/selector test for date semantics alone

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
- Why not `CLOSED`:
  - formal `metric_id` approval is still missing
  - core detail row/scenario/view-scope semantics now have isolated selector tests, but full field freeze and exhaustive detail semantics remain partially covered by page tests only

## Unit 3: Refresh + Status

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - `/refresh` and `/refresh-status` routes exist
  - queue path, sync fallback path, 409 conflict path, 503 failure path, and stale-run reconciliation are heavily tested in `tests/test_product_category_pnl_flow.py`
  - page polling behavior is tested in `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - page shows last run id and refresh error in `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Why not `CLOSED`:
  - no dedicated page-level UX evidence for long-running refresh semantics beyond queued polling
  - 409 and 503 are surfaced as generic error text, but the product meaning is not frozen as a contract
  - no page-level explicit stale-state banner contract exists

## Unit 4: Manual Adjustment Create

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - create route and schema exist
  - backend create path and read-model effect are exercised in `tests/test_product_category_pnl_flow.py`
  - page form submission is tested in `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - real-mode client serialization is tested in `frontend/src/test/ApiClient.test.ts`
- Why not `CLOSED`:
  - frontend validation is present, but still relatively thin
  - there is no explicit page-level closure contract for every create-field combination
  - create success is coupled to refresh, but that coupling is not frozen as a standalone product rule

## Unit 5: Manual Adjustment List

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - list route exists with rich query parameters
  - backend filtering, pagination, UTC timestamp validation, and export query symmetry are exercised in `tests/test_product_category_pnl_flow.py`
  - independent audit view renders current-state rows and timeline rows in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - audit filters and timeline pagination are exercised in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - real-mode query serialization is covered in `frontend/src/test/ApiClient.test.ts`
- Why not `CLOSED`:
  - the business reason for dual sort controls is still not frozen as product truth
  - page-level stale/failure semantics for the list view are not fully documented
  - list closure mostly lives in the audit page rather than the main page, which increases cognitive split

## Unit 6: Manual Adjustment Export

- Status: `PARTIAL`
- Priority: `P1`
- Evidence:
  - export route exists
  - filtered export behavior and CSV section ordering are covered in `tests/test_product_category_pnl_flow.py`
  - audit-page export flow is exercised in `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
  - real-mode export request and filename parsing are covered in `frontend/src/test/ApiClient.test.ts`
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
  - real-mode client calls are covered in `frontend/src/test/ApiClient.test.ts`
- Why not `CLOSED`:
  - no confirmation-modal evidence for revoke
  - lifecycle closure is spread across main page and audit page
  - field-level edit policy is implemented, but not yet frozen as human-readable product contract

## Unit 8: Governance / Traceability

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - `result_meta` is present and checked across UI endpoints in `tests/test_result_meta_on_all_ui_endpoints.py`
  - refresh governance records and run lineage are exercised in `tests/test_product_category_pnl_flow.py`
  - the main page now renders baseline/scenario `result_meta` through `product-category-result-meta`, with page tests checking basis, fallback mode, trace id, and scenario flag visibility
  - truth-chain ADR now fixes row authority in `docs/pnl/adr-product-category-truth-chain.md`
  - page truth contract and golden sample contract now exist under `docs/pnl/`
- Why not `CLOSED`:
  - degraded or fallback semantics are not fully frozen at page-UI level
  - no standalone outward `as_of_date`
  - page-level governance visibility now exists, but the exact degraded-state UX contract remains partial

## Unit 9: Frontend Cross-Field Consistency

- Status: `PARTIAL`
- Priority: `P0`
- Evidence:
  - the main page is relatively disciplined and mostly renders backend-returned rows
  - display order is explicit in `ProductCategoryPnlPage.tsx`
  - liability display normalization and number formatting are centralized in page helpers
  - no evidence of client-side re-aggregation of formal totals beyond scenario selection
- Why not `CLOSED`:
  - consistency is mostly implied by implementation, not frozen by dedicated tests
  - stale/fallback/no-data semantics are not fully covered
  - there is still page-side display transformation for liability values, which needs explicit governance if it is to count as fully closed

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
