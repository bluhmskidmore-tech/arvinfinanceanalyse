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
| 2 | exhaustive detail semantics beyond active 3C metrics are not fully page-frozen | 4 | Active `MTR-PCP-004`~`MTR-PCP-012` field semantics are now model/page/golden-backed; expand only after a new governed metric matrix | Partially complete | `productCategoryPnlPageModel.test.ts`, `ProductCategoryPnlPage.test.tsx`, `GS-PROD-CAT-PNL-A/` |
| 3 | final stale-state banner copy / placement is not product-frozen | 4 | Governance strip and formal readiness marker now expose degraded state; freeze final banner wording only after product severity wording is approved | Partially complete | `docs/pnl/product-category-page-truth-contract.md`, `ProductCategoryPnlPage.test.tsx` |
| 3 | long-running refresh UX … timeout messaging vs `runPollingTask` generic timeout | 1 | Decide timeout user messaging and whether to surface run_id after timeout | No | `ProductCategoryPnlPage.tsx`, `runPollingTask`/`config`, tests |
| 4 | long copy/UX for validation beyond the two primary empty-payload cases is not exhaustively specified | 1 | Approve validation messages and edge-case rules | No | Page copy + tests once approved |
| 5 | product rationale for two independent sort controls … narrative gap | 1 | Document product “why” for dual sort vs single model | No | `docs/pnl/…` (ADR or truth contract) |
| 5 | broader stale/failure matrix (partial degradation, export vs list under error) | 4 | Audit list/timeline failures, export-failure/list-retention behavior, and main-page adjustment-summary refetch failure are now page-frozen; partial-degradation copy remains open | Partially complete | Audit + main page tests, checklist |
| 6 | backend/global UTF-8 BOM policy for generated CSV not specified | 2 | Record server BOM rule; align tests | No | Backend export + `docs/pnl/…` |
| 6 | no frozen behavior for very large exports | 2 | Define limits/streaming/timeouts; implement + test | No | Backend route + flow tests |
| 6 | no explicit e2e contract that UI money strings equal CSV in every cell | 4 | New fixture-scoped rendered-row vs export-row assertion is complete; broader golden/integration coverage waits for a governed sample that defines more cells | Partially complete | `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`, optionally `GS-PROD-CAT-PNL-A/` later |
| 8 | fuller stale/refresh/cross-endpoint UX copy … not yet frozen | 4 | Evidence matrix covers known states; add more cells only when timeout or cross-endpoint copy is approved | Partially complete | `docs/pnl/product-category-page-truth-contract.md`, frontend tests |
| 9 | exhaustive column × row matrix not page-frozen | 4 | GS-backed narrow row/field matrix is complete; expand tests only after Unit 2 metric approval | Partially complete | Model + page tests |
| 9 | test rows tied to mock `category_id` / `side`, not cross-domain inference | 4 | GS-backed `repo_assets` / `repo_liabilities` cases are complete; add broader fixture cases only when domain catalog evidence is stable | Partially complete | `productCategoryPnlPageModel.test.ts`, mocks |
| 10 | scenario is companion probe, not second full golden matrix sample | 4 | Scenario promotion gate is now documented; create a separate scenario sample pack only after non-placeholder scenario approval and metric-matrix evidence exist | Partially complete | `tests/golden_samples/`, `product-category-golden-sample-a.md` |
| 10 | full-repo golden/e2e uneven (process-wide) | 5 | Track outside product-category closure; don’t block unit closure on it | Yes | Repo CI docs (if any); not this branch |
| 10 | exhaustive page assertion ↔ pure helper pairing not claimed | 4 | Page-to-helper traceability map is now documented; keep residual as non-exhaustive per-field pairing boundary | Partially complete | `docs/pnl/product-category-closure-checklist.md` Unit 10 |

## Counts by class

| Class | Count |
| --- | ---: |
| 1 Product decision | 3 |
| 2 Backend/API contract | 2 |
| 3 Frontend implementation | 0 |
| 4 Evidence/test/documentation | 9 |
| 5 Out of scope (this branch) | 1 |
| **Total blockers** | **15** |

*Note:* The decision 3C dictionary-row implementation is now completed for `MTR-PCP-004` through `MTR-PCP-012`. The remaining open items are policy/API (1-2), evidence (4), or explicitly deferred (5).

## P0 execution boundary

P0 is about closure discipline for the already-governed product-category page.
It is not permission to invent metric definitions, API fields, or product copy.
Current active product-category metric ids are `MTR-PCP-001` through `MTR-PCP-012`; decision 3C detail activation is limited to the approved row-level fields in `docs/metric_dictionary.md`.

### Decision-required P0 items

- timeout / long-running refresh copy beyond the already-tested queued/running/failed states.

### Cursor-safe P0 items

- keep the stale/fallback/refresh matrix aligned with tests and mark unresolved copy/severity cells decision-required.
- keep golden-sample assertions clear that only `MTR-PCP-004`~`MTR-PCP-012` are active row-level 3C detail metrics.
- add regression tests only when a future change attempts to promote product-category fields outside the approved 3C set to `MTR-*` rows without a new matrix / numbering / dictionary row.
- document current evidence links across truth contract, checklist, golden sample, and page/model tests.
- Unit 5/7 surface cross-link note is now recorded in `docs/pnl/product-category-page-truth-contract.md` section 9.3 and `docs/pnl/product-category-closure-checklist.md`.

## Completed cursor-safe P0 evidence

- readiness baseline: `docs/pnl/product-category-development-data-readiness.md`
- headline sample metric assertions: `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md` and `docs/pnl/product-category-golden-sample-a.md`
- stale/fallback/refresh matrix skeleton: `docs/pnl/product-category-page-truth-contract.md` section 11.1
- Unit 8 stale/refresh cross-surface matrix: `docs/pnl/product-category-page-truth-contract.md` section 11.2
- Unit 3/8 degraded-state first-screen marker: `ProductCategoryFormalReadinessBand` and `ProductCategoryGovernanceStrip` expose degraded `fallback_mode`, `vendor_status`, `quality_flag`, and `data-state-review-required`; covered by `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Unit 5/7 surface ownership: `docs/pnl/product-category-page-truth-contract.md` section 9.3 and checklist Unit 5/7 evidence
- Unit 5 export/list failure split: `ProductCategoryAdjustmentAuditPage.tsx` renders export failures through `product-category-audit-export-error`, while `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` proves a failed export does not replace already-loaded current-state or event-timeline rows.
- Unit 5 main-page adjustment-summary refetch failure parity: `frontend/src/test/ProductCategoryPnlPage.test.tsx` proves stale main-page adjustment rows are hidden and retry remains available after `getProductCategoryManualAdjustments` refetch failure.
- Unit 7 field-level edit policy: `docs/pnl/product-category-page-truth-contract.md` section 9.4
- Unit 7 revoke confirmation: `ProductCategoryPnlPage.tsx` and `ProductCategoryAdjustmentAuditPage.tsx` require browser confirmation before destructive revoke; `ProductCategoryPnlPage.test.tsx` and `ProductCategoryAdjustmentAuditPage.test.tsx` prove cancel does not call revoke or refresh, and confirm does.
- Unit 10 page-to-helper traceability: `docs/pnl/product-category-closure-checklist.md`
- Unit 9 fixture-driven row matrix: `docs/pnl/product-category-closure-checklist.md`
- Unit 6 CSV precision scope note: `docs/pnl/product-category-closure-checklist.md`
- Unit 6 fixture-scoped UI-to-CSV parity: `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx` and `docs/pnl/product-category-closure-checklist.md`
- Unit 9 GS-backed row/field matrix: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` and `docs/pnl/product-category-closure-checklist.md`
- Unit 4 backend validation error-shape evidence: `tests/test_product_category_pnl_flow.py` and `docs/pnl/product-category-closure-checklist.md`
- Unit 1 decision 2A disappeared-selected-date page coverage: `frontend/src/test/ProductCategoryPnlPage.test.tsx` and `docs/pnl/product-category-closure-checklist.md`
- Unit 8 direct readiness evidence: `scripts/codex_page_readiness.py --page-slug product-category-pnl`, live smoke `scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl -CheckLive`, focused product-category MCP slice tests, full non-sandbox `scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run`, full non-sandbox `scripts/codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive`, and `docs/pnl/product-category-closure-checklist.md`; the prior shared MCP failure was isolated to sandbox temp filesystem delete/list permissions rather than product-category evidence.
- Unit 2 decision 3C field matrix: `docs/pnl/product-category-page-truth-contract.md` section 9.1.1 and `docs/pnl/product-category-closure-checklist.md`
- Unit 2 decision 3C dictionary rows/tests: `docs/metric_dictionary.md`, `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`, `docs/pnl/product-category-page-truth-contract.md` section 9.1.1, and `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- Unit 2/9 nonzero 3C display semantics: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` freezes asset signed display, liability absolute display, yuan-to-yi-yuan scaling, and yield non-money scaling for `MTR-PCP-004`~`MTR-PCP-012`
- Unit 10 scenario promotion gate: `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`, `docs/pnl/product-category-golden-sample-a.md`, and `tests/test_golden_samples_capture_ready.py` now define the evidence required before the companion scenario probe can become a second full golden matrix sample.
- 2026-05-11 decisions recorded: 1B no standalone `as_of_date`, 2A no silent selected-date switch, 3C active detail metric expansion for `MTR-PCP-004`~`MTR-PCP-012`
- outward `as_of_date`: decision 1B is already recorded in `docs/pnl/product-category-page-truth-contract.md`; the current page must not expose a standalone outward `as_of_date` unless product/API decision 1B is reopened with targeted tests.
- fallback-date boundary: `docs/pnl/product-category-page-truth-contract.md` section 10.2 now states there is no outward `fallback_date`, fallback evidence cannot be inferred from `report_date` / `resolved_report_date` / `generated_at`, and raw `fallback_mode` visibility is not replacement date truth.
- governance regression tests: `tests/test_governance_doc_contract.py` and `tests/test_golden_samples_capture_ready.py`

## Blockers that need user/product decision (Class 1)

- Unit 3: long-running refresh / timeout messaging
- Unit 4: validation copy / edge-case rules beyond two empty-payload tests
- Unit 5: dual-sort rationale (documentation of intent)

## Owner Review Queue

1. **refresh timeout/stale copy:** specify the copy shown when refresh exceeds the current UI polling window.
2. **Unit 4 extended validation copy:** freeze any additional backend validation wording beyond the two covered empty-payload cases.
3. **dual-sort rationale:** record the product intent for keeping current and event sort controls independent.
4. **revoke confirmation policy:** freeze whether destructive revoke needs policy beyond the already tested browser confirmation gate.
