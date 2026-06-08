# Top Investment Bank Standard Continuation Optimization Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from strong flagship frontend readiness toward a defensible top investment-bank operating standard by closing the first business-contract-certified route and then scaling the same evidence model across priority routes.

**Architecture:** Treat every page as a governed decision surface, not a dashboard skin. Keep visual quality, source-to-screen traceability, golden-sample approval, governance evidence, manual audit review, and business-owner approval as separate gates so no page is certified by screenshots or component tests alone.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright, Ant Design, page contracts, metric dictionary, golden samples, Python readiness scripts, approval checkers, local MCP evidence launchers, and MOSS frontend design tokens.

---

## Current Verified State

Fresh readiness checks on 2026-06-06 show:

- Route-scope classification covers `39` routes.
- `business-contract-certified=0`.
- `evidence-pending=12`.
- `gate-i-gap=2`.
- `frontend-ready=5`.
- `frontend-only=10`.
- `not-started=10`.
- `/product-category-pnl` is the strongest first certification candidate, but it remains `evidence-pending`.
- `/product-category-pnl` still has `business_owner_approval_captured=false`, `closure_approved=false`, `golden_sample_approval_artifact_mismatch=true`, and `GS-PROD-CAT-PNL-A/approval.md` remains `captured-awaiting-approval` with placeholder owner, approver, and approval date.

Allowed claim:

> MOSS has strong flagship frontend surfaces and controlled business-contract closure lanes. Full top-investment-bank business certification is still open and route-scoped.

Forbidden claim:

> MOSS, or any route, is top-investment-bank business-certified.

## Target Standard

A route reaches top investment-bank standard only when all of these are true:

1. First screen answers trust state, primary business conclusion, supporting evidence, and next action.
2. Every decision metric exposes source, date, unit, precision, stale/fallback/no-data state, and formal/candidate boundary.
3. Critical values trace from API response to adapter/model, selector/state, component, and visible chart/table.
4. Metric contract, catalog/date evidence, lineage, and governance readiness are documented.
5. Golden sample approval is direct, non-placeholder, and not stretched beyond captured scope.
6. Manual audit review is closed.
7. Business-owner approval is captured through the strict checker path.
8. Browser evidence passes at `1440px`, `768px`, and `390px` with no fallback route, permanent loading, horizontal overflow, or blocking console errors.
9. Route-scope classification prevents audited-route claims from becoming whole-system claims.

## Non-Negotiable Boundaries

- Do not change finance formulas to make evidence pass.
- Do not promote `formal_use_allowed`, `closure_approved`, golden approval, or business-owner approval without real evidence.
- Do not run governance writes without explicit workflow authority.
- Do not borrow evidence across routes, especially `/bond-dashboard` to certify `/bond-analysis`.
- Do not hide stale, fallback, no-data, pending-approval, or temporary-exception states for visual polish.
- Do not touch schema, auth, scheduler, queue, cache, or global SDK layers for this optimization lane.
- Do not commit unless the user explicitly asks.

## RALPLAN-DR Summary

### Principles

1. Certification is evidence, not aesthetics.
2. First close one route completely, then replicate.
3. Preserve business uncertainty visibly instead of smoothing it away.
4. Prefer strict blockers over optimistic wording.
5. Keep changes narrow, reviewable, and reversible.

### Decision Drivers

1. Highest certification leverage: `/product-category-pnl` already has route-specific evidence and approval checker wiring.
2. Lowest trust risk: strengthen checker/doc/test gates without changing business formulas or owner decisions.
3. Fastest scaling path: once one route is certified, reuse the closure model for `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis`.

### Viable Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Polish more flagship UI first | Makes screenshots stronger quickly | Does not reduce certification blockers | Reject as primary lane |
| B. Certify `/product-category-pnl` first | Highest chance of first real business-certified route | Depends on human owner approval for final closure | Choose as critical path |
| C. Build all Gate I lanes in parallel | Broad progress across many routes | Higher review risk and more unfinished lanes | Use only after first route pattern stabilizes |

## Task 1: Repair Product-Category First-Certification Packet Test Drift

**Purpose:** Clear the known local test drift introduced by adding the stricter artifact-existence checklist item.

**Files:**

- Modify: `tests/test_product_category_pnl_first_certification_packet.py`
- Inspect: `scripts/product_category_pnl_first_certification_packet.py`

**Steps:**

1. Update the expected `reviewer_checklist` list to include:
   `Confirm reviewed boundary, first-certification, and owner-decision packet artifacts exist before marking template review fields yes.`
2. Run the packet test.
3. Confirm the test passes without changing packet semantics.

**Acceptance Criteria:**

- The expected checklist matches the generator.
- The packet still does not approve page closure or capture owner approval.

**Verification:**

```powershell
python -m pytest tests\test_product_category_pnl_first_certification_packet.py -q
```

## Task 2: Regenerate Product-Category Owner-Facing Evidence Packets

**Purpose:** Keep generated owner artifacts synchronized with the stricter approval checker.

**Files:**

- Generate: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Generate: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `scripts/check_product_category_pnl_business_owner_approval.py`

**Steps:**

1. Regenerate the first certification packet.
2. Regenerate the owner decision packet.
3. Run the approval checker in normal mode.
4. Run the approval checker in require-captured mode and confirm it still blocks.

**Acceptance Criteria:**

- Owner-facing packets exist at the expected paths.
- Normal checker succeeds while reporting approval pending.
- `--require-captured` exits non-zero until real approval exists.
- No owner, approver, date, golden approval, or closure flag is faked.

**Verification:**

```powershell
python scripts/product_category_pnl_first_certification_packet.py
python scripts/product_category_pnl_owner_decision_packet.py
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

## Task 3: Close Cursor-Safe Product-Category Evidence Blockers

**Purpose:** Reduce real residual risk by tightening tests/docs around already governed values, without making product decisions.

**Files:**

- Modify as needed: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- Modify as needed: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify as needed: `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`
- Modify as needed: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `docs/pnl/product-category-page-truth-contract.md`
- Inspect: `docs/pnl/product-category-golden-sample-a.md`

**Steps:**

1. Add or tighten tests only for already approved headline/detail fields.
2. Verify units, precision, null-vs-zero behavior, report date, row identity, fallback/stale state, and visible anchors.
3. Update checklist language only when evidence proves that exact unit has narrowed or closed.
4. Keep unresolved product decisions as explicit owner blockers.

**Acceptance Criteria:**

- At least one evidence/test/doc blocker is closed or narrowed.
- No metric definition is changed.
- No golden approval is promoted.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm run debt:audit
cd ..
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/codex_page_readiness.py --page-slug product-category-pnl
```

## Task 4: Run Product-Category Browser and Accessibility Evidence

**Purpose:** Re-prove that the certification candidate is still usable as an institutional decision surface after any page-level adjustments.

**Files:**

- Inspect: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`
- Inspect: `scripts/codex-page-smoke.ps1`
- Inspect: `scripts/codex-verify-page.ps1`

**Steps:**

1. Run page smoke for `/product-category-pnl`.
2. Run page verification for `/product-category-pnl`.
3. Run relevant frontend tests, lint, typecheck, debt audit, and build.
4. Confirm no fallback route, permanent loading, horizontal overflow, blocking console errors, or accessibility regressions.

**Acceptance Criteria:**

- Product-category page remains frontend-surface flagship-ready.
- Evidence states remain visible and are not hidden for aesthetics.

**Verification:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run
cd frontend
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Task 5: Prepare Human Owner Sign-Off Without Capturing It

**Purpose:** Make the final owner step executable while preserving the boundary that Codex cannot approve business truth.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-approval-runbook.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Inspect: `docs/pnl/product-category-closure-checklist.md`

**Steps:**

1. Ensure the runbook lists exact artifacts the owner must review.
2. Ensure the template requires non-placeholder owner, role, decision, date, and signature.
3. Ensure golden sample approval artifact requires `Status: approved` plus non-placeholder owner, approver, and approval date.
4. Ensure checklist units cannot remain `PARTIAL` for captured approval.

**Acceptance Criteria:**

- The sign-off path is clear.
- Approval remains blocked until a real business owner acts.

**Verification:**

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

## Task 6: Scale The Pattern To The Next Priority Routes

**Purpose:** Use the first-route closure pattern to advance other high-value routes without overclaiming.

**Routes:**

- `/pnl-attribution`: keep DTO-only golden sample boundary honest.
- `/ledger-pnl`: keep governance dry-run authorization-safe.
- `/bond-analysis`: build direct fixed-income Gate I lane.
- `/stock-analysis`: build observational-versus-formal boundary lane.

**Files:**

- Inspect: `scripts/codex_page_readiness.py`
- Inspect: `tests/test_codex_page_readiness_gate.py`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect relevant route docs under `docs/pnl/`, `docs/page_contracts.md`, and `docs/metric_dictionary.md`

**Steps:**

1. Re-run readiness per route.
2. Record whether the blocker is golden approval, manual audit closure, owner approval, or missing direct Gate I lane.
3. Add checkers/packets only where a route already has enough evidence to justify owner review.
4. Keep `formal_use_allowed=false` where route status is observational or candidate-only.

**Acceptance Criteria:**

- No route is certified from borrowed evidence.
- Each priority route has a visible next blocker and verification command.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug pnl-attribution
python scripts/codex_page_readiness.py --page-slug ledger-pnl
python scripts/codex_page_readiness.py --page-slug bond-analysis
python scripts/codex_page_readiness.py --page-slug stock-analysis
python scripts/codex_page_readiness.py --route-scope
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

## Task 7: Institutional UX Final Layer

**Purpose:** Upgrade the experience from strong dashboard to institutional operating cockpit after evidence gates are honest.

**Files:**

- Modify page-by-page only under `frontend/src/features/`
- Modify page CSS only where touched
- Inspect: `docs/frontend-institutional-standard.md`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Check first-screen order: trust state, business verdict, evidence, blocker, next action.
2. Tighten density, alignment, rhythm, and responsive readouts where browser evidence shows weakness.
3. Preserve keyboard focus, semantic labels, non-color state cues, and mobile readouts before raw grids.
4. Avoid decorative effects that reduce scan speed.

**Acceptance Criteria:**

- UX improvements clarify decisions rather than adding ornament.
- No pending evidence is visually hidden.
- Browser and accessibility evidence remain fresh.

**Verification:**

```powershell
cd frontend
npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Execution Order

1. Repair known product-category packet test drift.
2. Regenerate owner-facing product-category evidence packets.
3. Close cursor-safe product-category evidence blockers.
4. Re-run product-category browser/accessibility evidence.
5. Prepare, but do not fake, human owner sign-off.
6. Scale the closure pattern to `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis`.
7. Apply final institutional UX hardening after evidence gates are honest.

## ADR

**Decision:** Use `/product-category-pnl` as the first certification critical path, then scale the pattern.

**Drivers:** It has the strongest current evidence, a strict approval checker, route-specific readiness, direct governance evidence, and a clear owner packet path.

**Alternatives considered:** More UI polish first; broad parallel Gate I work across all routes; direct governance writes.

**Why chosen:** It produces the first defensible business-certified route fastest while minimizing formula, approval, and governance-write risk.

**Consequences:** Final certification still depends on real business-owner action. Codex can prepare evidence and blockers, but cannot sign or approve business truth.

**Follow-ups:** After the first route is certified, convert the route-scope ledger into a recurring certification board with one owner packet, one checker, and one freshness command per priority route.
