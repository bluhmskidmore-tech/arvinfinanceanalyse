# Top Investment Bank Standard Certified Route Closure Implementation Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `using-superpowers`, `executing-plans`, `test-driven-development`, `karpathy-guidelines`, `finance-data-quality`, `frontend-design`, and `verification-before-completion` while executing this plan.

**Goal:** Move MOSS from flagship frontend-surface readiness toward a defensible top investment-bank operating standard by closing route certification with evidence, not visual polish alone.

**Architecture:** Treat each route as a governed business decision surface. Keep frontend UX, source-to-screen metric traceability, golden-sample scope, governance-record evidence, manual audit review, and business-owner approval as separate gates so no page is certified by screenshots or component tests alone.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, page contracts, metric dictionary, golden samples, Python readiness scripts, approval checkers, local MCP stdio launchers, and PowerShell page verification wrappers.

---

## Current Verdict

MOSS has not fully reached the top investment-bank standard yet.

Allowed claim now:

> The seven audited flagship frontend surfaces are flagship-ready. Full business-contract certification is still open.

Fresh evidence from the current readiness checks:

- `/product-category-pnl` is the strongest certification candidate, but it remains `evidence-pending`.
- `business_owner_approval_captured=false`.
- `closure_approved=false`.
- `GS-PROD-CAT-PNL-A/approval.md` still says `captured-awaiting-approval` with owner, approver, and approval date as `TBD`.
- The product-category closure checklist has `10` units, all still `PARTIAL`.
- Product-category blocker triage is machine-readable: `16` blockers total, including `4` owner/product decisions, `2` API-contract decisions, `9` evidence/test/doc blockers, and `1` out-of-scope process blocker.
- The product-category approval checker now reports `14` action items, including the owner decision packet review.
- `/ledger-pnl` and `/pnl-attribution` remain approval-pending with `11` action items each.
- Wider routes beyond the audited seven-route surface are not yet classified as certified, evidence-pending, frontend-only, or out of scope.

## Standard To Reach

A route can be called top investment-bank-grade only when all gates below pass:

1. First screen answers trust state, business conclusion, evidence, and next action.
2. Every decision metric exposes source, date, unit, precision, stale/fallback/no-data status, and formal/candidate boundary.
3. Critical values are traced from API response to adapter/model, state/selector, component, and visible chart/table.
4. MCP or documented local evidence supports metric contract, lineage, catalog/date status, and governance readiness.
5. Golden samples are approved directly and are not stretched beyond their captured scope.
6. Manual audit review is complete.
7. Business-owner approval is captured by strict checker.
8. Desktop `1440px`, tablet `768px`, and mobile `390px` browser checks show no fallback route, permanent loading, horizontal overflow, or blocking console errors.
9. Non-audited routes are classified so the final claim does not silently expand.

## Non-Negotiable Boundaries

- Do not change finance formulas to make evidence pass.
- Do not write governance records without explicit workflow authority.
- Do not mark golden samples approved without real owner, approver, and approval date.
- Do not set `closure_approved=true` or `formal_use_allowed=true` as a workaround.
- Do not borrow `/bond-dashboard` evidence to certify `/bond-analysis`.
- Do not touch schema, auth, scheduler, queue, cache, or global SDK layers for this plan.

## Task 1: Finish Product-Category Owner Decision Intake

**Purpose:** Convert the remaining product/API ambiguity into explicit owner decisions before implementation changes touch behavior.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Modify if wording drift exists: `scripts/check_product_category_pnl_business_owner_approval.py`
- Test: `tests/test_product_category_pnl_owner_decision_packet.py`
- Test: `tests/test_product_category_pnl_business_owner_approval_status.py`

**Steps:**

1. Re-run the owner decision packet generator.
2. Verify it includes only class `1` and class `2` blockers.
3. Verify the approval checker requires `- Owner decision packet reviewed: yes`.
4. Confirm the checker still reports pending approval while owner decisions are missing.
5. Update docs only if the generated packet and checker wording diverge.

**Acceptance Criteria:**

- Owner decision items remain visible and machine-checkable.
- The packet does not capture approval.
- Approval remains pending until the template, golden approval artifact, closure checklist, and owner review fields are all real.

**Verification:**

```powershell
python scripts/product_category_pnl_owner_decision_packet.py
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
python -m pytest tests/test_product_category_pnl_owner_decision_packet.py tests/test_product_category_pnl_business_owner_approval_status.py -q
```

Expected:

- First two commands succeed.
- `--require-captured` exits non-zero until real approval exists.
- Tests pass.

## Task 2: Close Cursor-Safe Product-Category Evidence Blockers

**Purpose:** Reduce the product-category closure checklist from broad `PARTIAL` status to narrower evidence-backed blockers without making product decisions.

**Files:**

- Modify: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify if needed: `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`
- Modify if needed: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `docs/pnl/product-category-golden-sample-a.md`
- Inspect: `docs/pnl/product-category-page-truth-contract.md`

**Steps:**

1. Write failing tests for the approved headline metric row set from `GS-PROD-CAT-PNL-A`.
2. Assert unit, precision, null-vs-zero, report date, fallback/stale text, and row identity for the already approved metric IDs only.
3. Add or tighten component assertions that the same values are visible before dense drill-down tables.
4. Add a traceability table for helper-to-page assertions if the current checklist cannot explain coverage.
5. Update checklist language only from `PARTIAL` to a more specific state when evidence proves that exact unit.

**Acceptance Criteria:**

- No new metric definitions are invented.
- No golden approval is promoted.
- At least one evidence/test/doc blocker is either closed or narrowed to a precise owner/API blocker.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm run debt:audit
```

Then from repo root:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/codex_page_readiness.py --page-slug product-category-pnl
```

## Task 3: Build Product-Category Approval Evidence Runbook

**Purpose:** Make the human sign-off path executable without relying on memory or chat history.

**Files:**

- Create: `docs/pnl/product-category-pnl-approval-runbook.md`
- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`

**Steps:**

1. List the exact artifacts an owner must review.
2. List the exact fields that must change from placeholder to real values.
3. List the verification commands that must be rerun immediately before approval.
4. State explicitly that Codex cannot fill owner, approver, approval date, or signature.
5. State that the runbook does not approve the page.

**Acceptance Criteria:**

- A business owner can see the review sequence without reading source code.
- The runbook does not create approval, formal-use promotion, or governance writes.

**Verification:**

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/product_category_pnl_first_certification_packet.py
python scripts/product_category_pnl_owner_decision_packet.py
```

## Task 4: Harden PnL Attribution Candidate Boundary

**Purpose:** Keep `/pnl-attribution` moving while preventing primary DTO evidence from becoming accidental full-page certification.

**Files:**

- Inspect: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Inspect: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Inspect: `tests/golden_samples/GS-PNL-ATTR-WB-A/`
- Inspect: `scripts/check_pnl_attribution_business_owner_approval.py`
- Modify if needed: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Re-run readiness, governance dry-run, and approval checker.
2. Confirm `GS-PNL-ATTR-WB-A` covers only the primary workbench DTO.
3. Confirm advanced attribution, Campisi, formal PnL overview, and executive overlay remain outside that sample.
4. If any doc overclaims the sample, correct the wording.
5. Keep `formal_use_allowed=false`, `closure_approved=false`, and approval pending unless real evidence changes.

**Acceptance Criteria:**

- `/pnl-attribution` has an honest owner-ready boundary packet.
- No full-page certification is claimed from DTO-only evidence.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug pnl-attribution
python scripts/emit_pnl_attribution_governance_record.py
python scripts/check_pnl_attribution_business_owner_approval.py
python -m pytest tests/test_pnl_attribution_governance_record.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
```

## Task 5: Keep Ledger PnL Governance Closure Authorization-Safe

**Purpose:** Advance `/ledger-pnl` evidence without casually writing governance records.

**Files:**

- Inspect: `scripts/emit_ledger_pnl_governance_record.py`
- Inspect: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Inspect: `docs/pnl/ledger-pnl-governance-audit-packet.md`
- Inspect: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Inspect: `scripts/check_ledger_pnl_business_owner_approval.py`

**Steps:**

1. Re-run dry-run governance preflight only.
2. Confirm `record_write_status=not_requested`.
3. Confirm approval checker still requires manual governance review, no dedicated summary golden-sample review, UI/API payload review, live-smoke review, verification rerun, and candidate-boundary acceptance.
4. Create a written "authorized write required" note if missing, but do not run `--write`.

**Acceptance Criteria:**

- Ledger remains evidence-pending.
- The next authorized governance step is clear.
- No governance stream is modified.

**Verification:**

```powershell
python scripts/emit_ledger_pnl_governance_record.py
python scripts/check_ledger_pnl_business_owner_approval.py
python scripts/codex_page_readiness.py --page-slug ledger-pnl
python -m pytest tests/test_ledger_pnl_governance_record.py tests/test_ledger_pnl_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
```

## Task 6: Create Direct Bond-Analysis Gate I Lane

**Purpose:** Stop `/bond-analysis` from being measured only as a clean frontend surface and give it its own fixed-income certification path.

**Files:**

- Inspect: `frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx`
- Inspect: `frontend/src/test/BondAnalyticsView.test.tsx`
- Inspect: `frontend/src/test/BondAnalyticsViewContent.test.tsx`
- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Create or modify only if evidence supports it: `docs/audits/2026-06-06-bond-analysis-gate-i-lane.md`
- Modify if supported: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Steps:**

1. List `/bond-analysis` decision metrics directly visible on the page.
2. Separate DV01, duration, YTM/yield percent, bp movement, market value, holdings grain, and accounting-class evidence.
3. Confirm `/bond-dashboard` contract and `GS-BOND-HEADLINE-A` are non-reusable.
4. Add a direct `gate-i-gap` lane if the readiness script does not already expose one.
5. Do not certify until direct page contract, golden-sample boundary, governance validation, manual audit review, and business-owner approval exist.

**Acceptance Criteria:**

- `/bond-analysis` has a route-specific certification path.
- No fixed-income metric is certified from browser cleanliness alone.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug bond-analysis
python -m pytest tests/test_codex_page_readiness_gate.py -q
cd frontend
npm run test -- src/test/BondAnalyticsView.test.tsx src/test/BondAnalyticsViewContent.test.tsx
```

## Task 7: Gate J Route-Scope Classification

**Purpose:** Prevent the seven-route flagship claim from becoming accidental whole-system certification.

**Files:**

- Create: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify if needed: `scripts/codex_page_readiness.py`
- Test if script changes: `tests/test_codex_page_readiness_gate.py`
- Inspect: `frontend/src/router/routes.tsx`
- Inspect: `docs/page_contracts.md`

**Steps:**

1. Enumerate all visible business routes.
2. Classify each route as `business-contract-certified`, `evidence-pending`, `gate-i-gap`, `frontend-ready`, `frontend-only`, `not-started`, or `out-of-scope`.
3. Record which routes have run-supported smoke commands.
4. Record which routes have page contracts, metric dictionary rows, golden samples, governance evidence, and approval checkers.
5. Add a summary table to the scorecard.

**Acceptance Criteria:**

- The final claim is route-scoped.
- Unclassified routes cannot be described as top-bank certified.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --all
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

## Task 8: Final Institutional UX Hardening

**Purpose:** Make the already strong frontend surface feel like an institutional decision cockpit without adding decorative noise.

**Files:**

- Inspect/modify page-by-page only: `frontend/src/features/*`
- Inspect/modify route CSS only where touched.
- Inspect: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`
- Inspect: `docs/frontend-institutional-standard.md`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. For each certified-candidate route, check first-screen hierarchy: verdict, trust state, metric evidence, blocker/action.
2. Tighten density, alignment, and responsive behavior only where browser evidence shows weakness.
3. Preserve mobile readouts before raw grids.
4. Preserve accessibility names, focus states, and non-color state cues.
5. Re-run browser evidence at `1440px`, `768px`, and `390px`.

**Acceptance Criteria:**

- UX improvements make decisions clearer, not merely prettier.
- No governance uncertainty is hidden to improve visual appearance.
- No route loses keyboard, mobile, or evidence visibility.

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

1. Product-category owner decision intake and checker verification.
2. Product-category cursor-safe evidence blockers.
3. Product-category approval runbook.
4. PnL attribution boundary hardening.
5. Ledger authorization-safe governance closure.
6. Bond-analysis direct Gate I lane.
7. Gate J route-scope classification.
8. Final institutional UX hardening and fresh browser evidence.

## Final Claim Criteria

Only claim a route is top investment-bank-grade when:

- readiness is not merely `static-pass`, but has route-specific business-contract closure evidence;
- golden sample approval is direct and non-placeholder;
- manual audit review is closed;
- business-owner approval checker passes with captured approval;
- browser, accessibility, lint, typecheck, debt audit, build, and targeted tests pass fresh;
- the route is included in the route-scope classification ledger.

Until then, the correct claim remains:

> Frontend flagship readiness is strong; business-contract certification is still in controlled closure.
