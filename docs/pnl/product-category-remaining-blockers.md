# Product-Category PnL — Remaining Blocker Triage

Derived from `product-category-closure-checklist.md` **Why not CLOSED** bullets (Units 1–10).  
Each row is one blocker. **Class** is the primary owner type.

## Classification legend

1. **Product decision required** — needs stakeholder choice on behavior, scope, or UX friction  
2. **Backend/API contract required** — needs schema/field/route/CSV policy from server or API spec  
3. **Frontend implementation required** — needs UI/code once contract or product choice exists  
4. **Evidence/test/documentation gap** — needs tests, golden samples, or docs to freeze behavior  
5. **Explicitly out of scope for this closure branch** — defer or non-goal for this effort  

**Cursor-safe without product/domain input:** can proceed from existing contracts/tests (docs/tests/refactors) without inventing policy.

| Unit | Blocker (from checklist) | Class | Minimal next action | Cursor-safe? | Suggested scope (if actionable) |
| --- | --- | --- | --- | --- | --- |
| 2 | decision 3C approves detail metric expansion but field matrix / numbering / dictionary rows / tests are not implemented | 3 | Create the detail metric matrix for scale, FTP, net income, and yield fields; then add concrete `MTR-PCP-*` rows and tests | Yes, after choosing numbering within the approved matrix | `docs/metric_dictionary.md`, `productCategoryPnlPageModel.test.ts`, golden assertions |
| 2 | exhaustive detail semantics are not fully page-frozen | 4 | Add page/model tests per approved headline metric row set; extend golden assertions | Yes (for the three approved headline metrics) | `productCategoryPnlPageModel.test.ts`, `ProductCategoryPnlPage.test.tsx`, `GS-PROD-CAT-PNL-A/` |
| 3 | no page-level explicit stale-state banner contract exists | 4 | Write UX contract (when banner shows, copy, dismiss) then implement | Partially (doc+test skeleton only) | `docs/pnl/…`, then `ProductCategoryPnlPage.tsx` + page tests |
| 3 | long-running refresh UX … timeout messaging vs `runPollingTask` generic timeout | 1 | Decide timeout user messaging and whether to surface run_id after timeout | No | `ProductCategoryPnlPage.tsx`, `runPollingTask`/`config`, tests |
| 4 | long copy/UX for validation beyond the two primary empty-payload cases is not exhaustively specified | 1 | Approve validation messages and edge-case rules | No | Page copy + tests once approved |
| 5 | product rationale for two independent sort controls … narrative gap | 1 | Document product “why” for dual sort vs single model | No | `docs/pnl/…` (ADR or truth contract) |
| 5 | broader stale/failure matrix (partial degradation, export vs list under error, main-page list parity) | 4 | Add tests/docs for each matrix cell once behaviors are defined | Partially | Audit + main page tests, checklist |
| 6 | backend/global UTF-8 BOM policy for generated CSV not specified | 2 | Record server BOM rule; align tests | No | Backend export + `docs/pnl/…` |
| 6 | no frozen behavior for very large exports | 2 | Define limits/streaming/timeouts; implement + test | No | Backend route + flow tests |
| 6 | no explicit e2e contract that UI money strings equal CSV in every cell | 4 | New fixture-scoped rendered-row vs export-row assertion is complete; broader golden/integration coverage waits for a governed sample that defines more cells | Partially complete | `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`, optionally `GS-PROD-CAT-PNL-A/` later |
| 7 | no confirmation modal for destructive revoke | 1 | Decide if friction is required | No | `ProductCategoryPnlPage.tsx`, audit page, tests |
| 8 | fuller stale/refresh/cross-endpoint UX contract … not yet frozen | 4 | Spec matrix (states × surfaces); then tests | Partially | `docs/pnl/…`, frontend tests |
| 9 | exhaustive column × row matrix not page-frozen | 4 | GS-backed narrow row/field matrix is complete; expand tests only after Unit 2 metric approval | Partially complete | Model + page tests |
| 9 | test rows tied to mock `category_id` / `side`, not cross-domain inference | 4 | GS-backed `repo_assets` / `repo_liabilities` cases are complete; add broader fixture cases only when domain catalog evidence is stable | Partially complete | `productCategoryPnlPageModel.test.ts`, mocks |
| 10 | scenario is companion probe, not second full golden matrix sample | 4 | Add `GS-…` scenario pack or extend assertions | Yes | `tests/golden_samples/`, `product-category-golden-sample-a.md` |
| 10 | full-repo golden/e2e uneven (process-wide) | 5 | Track outside product-category closure; don’t block unit closure on it | Yes | Repo CI docs (if any); not this branch |
| 10 | exhaustive page assertion ↔ pure helper pairing not claimed | 4 | Optionally add traceability table in docs | Yes | This file or checklist Unit 10 |

## Counts by class

| Class | Count |
| --- | ---: |
| 1 Product decision | 4 |
| 2 Backend/API contract | 2 |
| 3 Frontend implementation | 1 |
| 4 Evidence/test/documentation | 9 |
| 5 Out of scope (this branch) | 1 |
| **Total blockers** | **17** |

*Note:* Class 3 now contains the decision 3C implementation matrix. The remaining open items are policy/API (1-2), implementation after an approved boundary (3), evidence (4), or explicitly deferred (5).

## P0 execution boundary

P0 is about closure discipline for the already-governed product-category page.
It is not permission to invent metric definitions, API fields, or product copy.
Current active product-category metric ids remain `MTR-PCP-001`, `MTR-PCP-002`, and `MTR-PCP-003`; decision 3C only opens the implementation matrix for future detail rows.

### Decision-required P0 items

- timeout / long-running refresh copy beyond the already-tested queued/running/failed states.

### Cursor-safe P0 items

- keep the stale/fallback/refresh matrix aligned with tests and mark unresolved copy/severity cells decision-required.
- keep golden-sample assertions clear that detail metric expansion is approved directionally but not dictionary-active until the 3C field matrix lands.
- add regression tests that prevent product-category fields from being promoted to `MTR-*` rows without the 3C field matrix / numbering / dictionary rows.
- document current evidence links across truth contract, checklist, golden sample, and page/model tests.
- Unit 5/7 surface cross-link note is now recorded in `docs/pnl/product-category-page-truth-contract.md` section 9.3 and `docs/pnl/product-category-closure-checklist.md`.

## Completed cursor-safe P0 evidence

- readiness baseline: `docs/pnl/product-category-development-data-readiness.md`
- headline sample metric assertions: `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md` and `docs/pnl/product-category-golden-sample-a.md`
- stale/fallback/refresh matrix skeleton: `docs/pnl/product-category-page-truth-contract.md` section 11.1
- Unit 8 stale/refresh cross-surface matrix: `docs/pnl/product-category-page-truth-contract.md` section 11.2
- Unit 5/7 surface ownership: `docs/pnl/product-category-page-truth-contract.md` section 9.3 and checklist Unit 5/7 evidence
- Unit 7 field-level edit policy: `docs/pnl/product-category-page-truth-contract.md` section 9.4
- Unit 10 page-to-helper traceability: `docs/pnl/product-category-closure-checklist.md`
- Unit 9 fixture-driven row matrix: `docs/pnl/product-category-closure-checklist.md`
- Unit 6 CSV precision scope note: `docs/pnl/product-category-closure-checklist.md`
- Unit 6 fixture-scoped UI-to-CSV parity: `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` and `docs/pnl/product-category-closure-checklist.md`
- Unit 9 GS-backed row/field matrix: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` and `docs/pnl/product-category-closure-checklist.md`
- Unit 4 backend validation error-shape evidence: `tests/test_product_category_pnl_flow.py` and `docs/pnl/product-category-closure-checklist.md`
- Unit 1 decision 2A disappeared-selected-date page coverage: `frontend/src/test/ProductCategoryPnlPage.test.tsx` and `docs/pnl/product-category-closure-checklist.md`
- 2026-05-11 decisions recorded: 1B no standalone `as_of_date`, 2A no silent selected-date switch, 3C approve detail metric expansion pending implementation matrix
- governance regression tests: `tests/test_governance_doc_contract.py` and `tests/test_golden_samples_capture_ready.py`

## Blockers that need user/product decision (Class 1)

- Unit 3: long-running refresh / timeout messaging  
- Unit 4: validation copy / edge-case rules beyond two empty-payload tests  
- Unit 5: dual-sort rationale (documentation of intent)  
- Unit 7: confirmation modal for revoke

## Next cursor-safe tasks

1. **Unit 2 decision 3C implementation matrix:** draft the detail metric field matrix for scale, FTP, net income, and yield fields before adding any new `MTR-PCP-*` rows.
2. **fallback-date semantics:** document the user-facing behavior for fallback dates before widening stale-state copy.
3. **outward `as_of_date`:** decide whether the page should expose `as_of_date` separately from the selected `report_date`.
4. **detail `metric_id` expansion:** define the approved detail metric rows before any new dictionary promotion.
5. **refresh timeout/stale copy:** specify the copy shown when refresh exceeds the current UI polling window.
6. **Unit 4 extended validation copy:** freeze any additional backend validation wording beyond the two covered empty-payload cases.
7. **dual-sort rationale:** record the product intent for keeping current and event sort controls independent.
8. **revoke confirmation policy:** decide whether revoke needs a confirmation modal before implementation.
