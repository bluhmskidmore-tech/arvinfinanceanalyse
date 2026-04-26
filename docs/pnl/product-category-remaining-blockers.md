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
| 1 | `as_of_date` is still an explicit outward contract gap | 2 | Expose `as_of_date` (or equivalent) on governed envelopes **or** record a permanent “no field” decision in API/truth docs | No | `backend/.../product_category_pnl.py`, schemas, `docs/pnl/product-category-page-truth-contract.md` |
| 1 | fallback-date semantics are not frozen at page level beyond the default-first-list-item rule | 1 | Decide intended behavior when dates list is partial, stale, or conflicts with refresh | No | Then freeze in `docs/pnl/…` + targeted tests |
| 2 | formal `metric_id` approval is still missing | 1 | Approve governed metric list / IDs for detail columns | No | `docs/pnl/product-category-page-truth-contract.md` § open gaps |
| 2 | exhaustive detail semantics are not fully page-frozen | 4 | Add page/model tests per approved metric row set; extend golden assertions | Yes (given approved metrics) | `productCategoryPnlPageModel.test.ts`, `ProductCategoryPnlPage.test.tsx`, `GS-PROD-CAT-PNL-A/` |
| 3 | no page-level explicit stale-state banner contract exists | 4 | Write UX contract (when banner shows, copy, dismiss) then implement | Partially (doc+test skeleton only) | `docs/pnl/…`, then `ProductCategoryPnlPage.tsx` + page tests |
| 3 | long-running refresh UX … timeout messaging vs `runPollingTask` generic timeout | 1 | Decide timeout user messaging and whether to surface run_id after timeout | No | `ProductCategoryPnlPage.tsx`, `runPollingTask`/`config`, tests |
| 4 | no explicit page-level closure contract for every create-field combination | 4 | Matrix test or doc table: field → validation → API called? | Yes | `ProductCategoryPnlPage.test.tsx`, checklist |
| 4 | long copy/UX for validation beyond the two primary empty-payload cases is not exhaustively specified | 1 | Approve validation messages and edge-case rules | No | Page copy + tests once approved |
| 5 | product rationale for two independent sort controls … narrative gap | 1 | Document product “why” for dual sort vs single model | No | `docs/pnl/…` (ADR or truth contract) |
| 5 | broader stale/failure matrix (partial degradation, export vs list under error, main-page list parity) | 4 | Add tests/docs for each matrix cell once behaviors are defined | Partially | Audit + main page tests, checklist |
| 5 | list closure mostly in audit page … cognitive split | 4 | Add cross-links + “source of truth” note in checklist/truth contract | Yes | `product-category-closure-checklist.md`, `product-category-page-truth-contract.md` |
| 6 | backend/global UTF-8 BOM policy for generated CSV not specified | 2 | Record server BOM rule; align tests | No | Backend export + `docs/pnl/…` |
| 6 | no frozen behavior for very large exports | 2 | Define limits/streaming/timeouts; implement + test | No | Backend route + flow tests |
| 6 | no explicit e2e contract that UI money strings equal CSV in every cell | 4 | Golden or integration test comparing rendered vs export sample | Yes (given fixtures) | `GS-PROD-CAT-PNL-A/` or dedicated test |
| 7 | no confirmation modal for destructive revoke | 1 | Decide if friction is required | No | `ProductCategoryPnlPage.tsx`, audit page, tests |
| 7 | lifecycle closure spread across main page and audit page | 4 | Document which surface is canonical for which action | Yes | `docs/pnl/…` only |
| 7 | field-level edit policy for every edge case not a separate human contract | 4 | Add contract subsection + link to tests | Yes | `product-category-page-truth-contract.md` |
| 8 | no standalone outward `as_of_date` from the API | 2 | Same as Unit 1 `as_of_date` gap | No | Backend + truth docs |
| 8 | fuller stale/refresh/cross-endpoint UX contract … not yet frozen | 4 | Spec matrix (states × surfaces); then tests | Partially | `docs/pnl/…`, frontend tests |
| 9 | exhaustive column × row matrix not page-frozen | 4 | Expand tests after Unit 2 metric approval | Yes (given metrics) | Model + page tests |
| 9 | test rows tied to mock `category_id` / `side`, not cross-domain inference | 4 | Add fixture-driven cases when domain catalog is stable | Yes | `productCategoryPnlPageModel.test.ts`, mocks |
| 10 | scenario is companion probe, not second full golden matrix sample | 4 | Add `GS-…` scenario pack or extend assertions | Yes | `tests/golden_samples/`, `product-category-golden-sample-a.md` |
| 10 | full-repo golden/e2e uneven (process-wide) | 5 | Track outside product-category closure; don’t block unit closure on it | Yes | Repo CI docs (if any); not this branch |
| 10 | exhaustive page assertion ↔ pure helper pairing not claimed | 4 | Optionally add traceability table in docs | Yes | This file or checklist Unit 10 |

## Counts by class

| Class | Count |
| --- | ---: |
| 1 Product decision | 7 |
| 2 Backend/API contract | 5 |
| 3 Frontend implementation | 0 |
| 4 Evidence/test/documentation | 12 |
| 5 Out of scope (this branch) | 1 |
| **Total blockers** | **25** |

*Note:* Class 3 is empty as written: open items are either policy/API (1–2), evidence (4), or explicitly deferred (5). Frontend code changes follow after 1/2/4 clarify.

## Blockers that need user/product decision (Class 1)

- Unit 1: fallback-date semantics  
- Unit 2: `metric_id` approval  
- Unit 3: long-running refresh / timeout messaging  
- Unit 4: validation copy / edge-case rules beyond two empty-payload tests  
- Unit 5: dual-sort rationale (documentation of intent)  
- Unit 7: confirmation modal for revoke  

## Top 3 Cursor-safe next tasks (no new policy)

1. **Unit 4 / Unit 9 / Unit 10 — evidence:** extend matrices in docs + tests for *already-defined* behaviors (create-field matrix, column matrix placeholders tied to existing mock rows, scenario golden assertions). Scope: `ProductCategoryPnlPage.test.tsx`, `productCategoryPnlPageModel.test.ts`, `product-category-closure-checklist.md`, golden `assertions.md`.  
2. **Unit 5 / Unit 7 / Unit 10 — documentation only:** add “canonical surface” and cross-links (main vs audit lifecycle, checklist ↔ truth contract). Scope: `product-category-page-truth-contract.md`, this file.  
3. **Unit 3 / Unit 8 — documentation skeleton:** stale/banner state matrix *template* (empty cells OK) to fill when product approves copy. Scope: `docs/pnl/product-category-page-truth-contract.md` or subsection here — **do not invent** final banner text.
