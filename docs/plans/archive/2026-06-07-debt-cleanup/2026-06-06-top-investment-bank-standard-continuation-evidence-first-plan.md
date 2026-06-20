# Top Investment Bank Standard Continuation Evidence-First Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from strong institutional frontend readiness to a defensible top investment-bank operating standard by closing route-level business certification with evidence, not cosmetics.

**Architecture:** Treat every route as a governed decision surface. Separate frontend flagship quality from business-contract certification, and require metric contract, source lineage, golden sample approval, manual audit closure, browser evidence, and business-owner sign-off before any certified claim.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright, Ant Design, MOSS design tokens, Python readiness scripts, page contracts, metric dictionary, golden samples, owner approval checkers, and local MCP evidence workflows.

---

## Current Verdict

MOSS has moved beyond ordinary dashboard polish, but it has not fully reached top investment-bank business certification.

Allowed claim:

> MOSS has several flagship-ready frontend surfaces and a governed route-certification operating model. The first business-contract certification lane is still pending owner, golden-sample, and manual-audit closure.

Forbidden claim:

> MOSS, or any individual route, is fully top investment-bank business-certified today.

Current evidence board:

- Route scope: `39` classified routes.
- `business-contract-certified=0`.
- `evidence-pending=12`.
- `gate-i-gap=2`.
- `frontend-ready=5`.
- `frontend-only=10`.
- `not-started=10`.
- First candidate: `/product-category-pnl`.
- First candidate status: `evidence-pending`, not certified.
- First candidate blockers: owner approval pending, golden artifact approval pending, manual audit closure pending, closure checklist still partial.

## What Top Investment-Bank Standard Means Here

A page reaches the target only when all of the following are true:

1. The first screen answers: can I trust this page, what is the conclusion, what evidence supports it, what is blocked, and what should happen next.
2. Every key metric shows source, report date, unit, precision, stale/fallback/no-data status, and formal-versus-candidate boundary.
3. Critical numbers trace from API response to adapter/model, selector/state, component, and visible chart/table.
4. Page contract, metric dictionary, data catalog/date evidence, lineage/governance evidence, and source freshness are documented.
5. Golden samples are route-scoped, approved with non-placeholder owner/approver/date fields, and tied to visible assertions.
6. Manual audit review is closed.
7. Business-owner approval is captured by a strict checker, not inferred from generated documents.
8. Browser evidence passes desktop, tablet, and mobile with no fallback route, permanent loading, horizontal overflow, or blocking console errors.
9. The route-scope board prevents one page's readiness from being overstated as whole-system certification.

## Strategy

Do not spend the next round on broad visual beautification. The frontend is already good enough to expose the next real constraint: trust closure.

The correct next optimization is evidence-first:

- Close one route completely.
- Use that route as the operating pattern.
- Scale to the next routes only after the first lane proves the process.
- Preserve every pending, stale, fallback, candidate, and no-data state visibly.

Chosen critical path:

1. `/product-category-pnl`
2. `/pnl-attribution`
3. `/ledger-pnl`
4. `/bond-analysis`
5. `/stock-analysis`
6. Remaining route board

## RALPLAN-DR Summary

### Principles

1. Certification is evidence, not appearance.
2. One closed route is worth more than ten half-polished routes.
3. Uncertainty must stay visible in the UI.
4. Generated packets can prepare sign-off, but cannot become sign-off.
5. No route may borrow another route's contract, golden sample, or governance record.

### Decision Drivers

1. `/product-category-pnl` is closest to a true first certification lane.
2. Its blockers are machine-visible and reviewable.
3. The fastest route to system credibility is a repeatable certification board, not another design pass.

### Options

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| A. Continue broad frontend polish | Improves screenshots quickly | Does not reduce certification blockers | Secondary only |
| B. Close `/product-category-pnl` first | Creates first defensible certification pattern | Needs real human owner/golden/manual audit action | Chosen |
| C. Run all priority routes in parallel | Broad visible progress | Higher risk of partial lanes and false claims | After first lane stabilizes |

## Task 1: Product-Category Certification Closure Lane

**Purpose:** Turn `/product-category-pnl` from strongest candidate into the first route that can be certified when human approval exists.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Inspect: `scripts/check_product_category_pnl_business_owner_approval.py`

**Steps:**

1. Confirm the owner packet lists every action item needed for real sign-off.
2. Confirm the golden approval artifact still blocks placeholder owner, approver, and approval date.
3. Confirm the closure checklist still blocks `PARTIAL` and `NOT_TRUSTED` units.
4. Keep the approval checker strict: normal mode may report pending; `--require-captured` must fail until real approval exists.
5. Re-run product-category route smoke and focused proof pack.
6. Do not set `closure_approved=true`, do not set golden `Status: approved`, and do not edit owner approval fields unless a real owner supplies the evidence.

**Verification:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug product-category-pnl -CheckLive
python scripts\check_product_category_pnl_business_owner_approval.py
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
python -m pytest tests\test_product_category_pnl_owner_decision_packet.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_business_owner_approval_status.py tests\test_golden_samples_capture_ready.py::test_product_category_companion_scenario_documents_promotion_gate tests\test_codex_page_readiness_gate.py -q
```

**Acceptance Criteria:**

- Owner can review a single coherent packet set.
- Fake approval remains blocked.
- Route remains `evidence-pending` until human sign-off closes the lane.

## Task 2: Shared MCP Verify Stability

**Purpose:** Make the full page verification command citable again, or clearly isolate it as an environment/test-runner blocker.

**Files:**

- Inspect: `scripts/codex-verify-page.ps1`
- Inspect: `scripts/codex-page-readiness.ps1`
- Inspect: `tests/test_project_mcp_servers.py`
- Modify only if needed: a narrow page-scoped verify mode or safe temp-root preflight.

**Steps:**

1. Read the first MCP contract-test block in `scripts/codex-verify-page.ps1`.
2. Identify whether full-suite failure is caused by page evidence, pytest basetemp cleanup, or locked process ownership.
3. If it is an environment/test-runner issue, document it and keep focused MCP slice evidence separate.
4. If a narrow page-scoped mode is added, write or update tests first.
5. Do not delete locked temp directories or kill unrelated Python processes as a blind cleanup.

**Verification:**

```powershell
python -m pytest tests\test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records tests\test_project_mcp_servers.py::test_data_catalog_page_catalog_date_evidence_samples_known_page_tables tests\test_project_mcp_servers.py::test_lineage_evidence_governance_audit_review_checklist_keeps_ready_record_unapproved tests\test_project_mcp_servers.py::test_lineage_evidence_governance_audit_review_queue_routes_ready_pages_without_closure -q --basetemp=F:\MOSS-V3\.codex-tmp\pytest-focused-product-category-mcp
```

**Acceptance Criteria:**

- Product-category evidence is not blocked by unrelated temp-dir instability.
- Full verify is either passing or explicitly classified as an environment/test-runner issue.
- No certification claim depends on a failing shared verify run.

## Task 3: Product-Category Institutional UX Final Pass

**Purpose:** Make the first candidate feel like a desk-grade operating cockpit while preserving every evidence boundary.

**Files:**

- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Inspect: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Inspect: `docs/frontend-institutional-standard.md`

**Steps:**

1. Audit the first screen for trust state, conclusion, evidence, blocker, and next action.
2. Improve spacing, hierarchy, density, and responsive ordering only where the screen is harder to scan.
3. Preserve fallback, stale, no-data, quality, vendor, pending approval, and review-required markers.
4. Avoid ornamental redesigns that hide uncertainty.
5. Capture browser evidence at desktop, tablet, and mobile.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/ProductCategoryAdjustmentAuditPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm run typecheck
npm run debt:audit
npm run build
cd ..
```

**Acceptance Criteria:**

- First screen reads faster.
- No evidence-pending state is hidden.
- No horizontal overflow or fallback route appears in browser checks.

## Task 4: PnL Attribution Candidate-Boundary Lane

**Purpose:** Move `/pnl-attribution` forward without pretending the DTO-only workbench sample certifies every attribution surface.

**Files:**

- Inspect: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Inspect: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Inspect: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- Inspect: `scripts/check_pnl_attribution_business_owner_approval.py`
- Inspect: `tests/golden_samples/GS-PNL-ATTR-WB-A/`

**Steps:**

1. Keep `formal_use_allowed=false`.
2. Keep the primary workbench DTO golden boundary explicit.
3. Verify owner action items are clear.
4. Add only evidence-packaging or checker tests that preserve the candidate boundary.
5. Do not stretch the sample into advanced/Campisi/full-page certification.

**Verification:**

```powershell
python scripts\codex_page_readiness.py --page-slug pnl-attribution
python scripts\check_pnl_attribution_business_owner_approval.py
python scripts\check_pnl_attribution_business_owner_approval.py --require-captured
```

**Acceptance Criteria:**

- `/pnl-attribution` remains honest as `evidence-pending`.
- The next owner decision is machine-visible.
- Candidate DTO evidence is not overclaimed.

## Task 5: Ledger PnL Dedicated Summary Golden Lane

**Purpose:** Give `/ledger-pnl` its own direct summary golden and governance path before owner approval.

**Files:**

- Inspect: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Inspect: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- Inspect: `scripts/check_ledger_pnl_business_owner_approval.py`
- Inspect: `tests/test_ledger_pnl_owner_evidence_packet.py`

**Steps:**

1. Locate or create the plan for a dedicated ledger summary golden sample.
2. Keep dry-run governance status separate from written governance records.
3. Require written/direct validation before any closure wording.
4. Keep `formal_use_allowed=false` until the route has direct approval evidence.

**Verification:**

```powershell
python scripts\codex_page_readiness.py --page-slug ledger-pnl
python scripts\check_ledger_pnl_business_owner_approval.py
python scripts\check_ledger_pnl_business_owner_approval.py --require-captured
```

**Acceptance Criteria:**

- `/ledger-pnl` has a clear next blocker: dedicated summary golden and direct governance validation.
- No dry-run evidence is described as approval.

## Task 6: Bond Analysis Direct Gate I Lane

**Purpose:** Stop `/bond-analysis` from relying on `/bond-dashboard` evidence and build its own fixed-income certification path.

**Files:**

- Inspect: `docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json`
- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Inspect: `frontend/src/features/bond-analytics/`
- Inspect: relevant bond analytics backend/service tests.

**Steps:**

1. Define route-specific `/bond-analysis` page contract boundaries.
2. Identify fixed-income metrics that need direct metric dictionary rows.
3. Define unit rules for DV01, duration, yield/YTM percent, bp movement, market value scale, and PnL.
4. Create or plan a direct `/bond-analysis` golden sample.
5. Require catalog/date, lineage/governance, manual audit, and owner approval before certification.

**Verification:**

```powershell
python scripts\codex_page_readiness.py --page-slug bond-analysis
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug bond-analysis -CheckLive
```

**Acceptance Criteria:**

- `/bond-analysis` remains `gate-i-gap` until direct evidence exists.
- No `/bond-dashboard` artifact is reused as certification.

## Task 7: Stock Analysis Observational Boundary Lane

**Purpose:** Make `/stock-analysis` trustworthy as an observational analytics surface without converting it into formal trading instruction.

**Files:**

- Inspect: `frontend/src/features/stock-analysis/`
- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`

**Steps:**

1. Define the route as observational unless formal metric contracts are created.
2. Add or plan a direct route contract that separates signal diagnostics from trade recommendations.
3. Create a golden/sample boundary only for observed display semantics.
4. Keep `formal_use_allowed=false`.
5. Keep disclaimers and review-required states visible.

**Verification:**

```powershell
python scripts\codex_page_readiness.py --page-slug stock-analysis
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug stock-analysis -CheckLive
```

**Acceptance Criteria:**

- `/stock-analysis` becomes an honest observational lane.
- No diagnostic output is described as formal trade instruction.

## Task 8: Recurring Certification Board

**Purpose:** Make the standard operational instead of a one-time scorecard.

**Files:**

- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Steps:**

1. Keep a row for every visible route.
2. Track frontend status, page contract, metric dictionary, golden sample, direct governance, manual audit, owner approval, required commands, and next blocker.
3. Keep allowed and forbidden claims at the top.
4. Re-run route scope after every certification-lane change.
5. Never convert `frontend-ready` into `business-contract-certified`.

**Verification:**

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q
```

**Acceptance Criteria:**

- Route claims are inspectable.
- No page or system claim can silently expand beyond its evidence.

## Execution Order

1. Re-prove `/product-category-pnl` smoke, focused MCP slice, focused Python tests, frontend tests, typecheck, debt audit, and approval pending state.
2. Diagnose shared MCP verify instability without destructive cleanup.
3. Package human owner review for `/product-category-pnl`.
4. Apply only decision-clarifying UX changes to `/product-category-pnl`.
5. Advance `/pnl-attribution` and `/ledger-pnl` with candidate-boundary and golden-summary discipline.
6. Build direct Gate I lanes for `/bond-analysis` and `/stock-analysis`.
7. Maintain the route-scope certification board after every pass.

## Next Round Concrete Work

Start with these in order:

1. Read `scripts/codex-verify-page.ps1` and isolate the full MCP verify basetemp failure.
2. Re-run the product-category focused MCP slice and approval checker.
3. Update the certification board if the verify blocker is fixed or explicitly isolated.
4. Review `/product-category-pnl` first screen against `docs/frontend-institutional-standard.md`.
5. If visual scan issues are found, patch only `ProductCategoryPnlPage.tsx`, `ProductCategoryPnlPage.css`, and targeted tests.
6. Run frontend product-category tests, typecheck, debt audit, and build.

## ADR

**Decision:** Continue with an evidence-first certification program, using `/product-category-pnl` as the first route-level critical path.

**Drivers:** It is the strongest candidate, its blockers are explicit, and it has strict approval tooling that prevents false certification.

**Alternatives considered:** More broad visual polish first; parallel certification for all priority routes; direct governance writes.

**Why chosen:** Top investment-bank quality is primarily trust, traceability, and operational closure. Visual excellence matters, but it is not enough without owner-approved business evidence.

**Consequences:** Codex can prepare evidence, improve UX, write tests, maintain boards, and make blockers machine-visible. Codex cannot approve business truth, sign owner packets, or promote golden/manual-audit status without real human evidence.

**Follow-ups:** Once `/product-category-pnl` is actually signed and certified, clone the checker-packet-board pattern to `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis` one route at a time.

## Final Checklist

- [x] Plan separates frontend flagship readiness from business certification.
- [x] Plan names concrete routes and files.
- [x] Plan includes verification commands.
- [x] Plan keeps approval, golden, and governance status honest.
- [x] Plan defines next round work.
- [x] Plan avoids backend/schema/auth/scheduler/cache/global SDK scope.
