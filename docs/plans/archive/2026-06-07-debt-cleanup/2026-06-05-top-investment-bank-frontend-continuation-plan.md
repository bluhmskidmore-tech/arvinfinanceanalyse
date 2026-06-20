# Top Investment Bank Frontend Continuation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from seven-route flagship readiness toward a repeatable top investment-bank frontend standard across audited and upcoming business pages.

**Architecture:** Keep every change page-scoped, evidence-first, and contract-preserving. Improve decision closure, mobile table readability, accessibility, and metric certification without changing finance formulas, backend services, schema, auth, scheduler, cache, queue, or global SDK layers.

**Tech Stack:** React, TypeScript, Vite, Vitest, browser verification, Ant Design, page-local CSS, existing MOSS design tokens, project MCP evidence servers when available.

---

## Current Verdict

The seven audited flagship routes are page-surface ready, but the whole system should not yet be called fully top investment-bank certified.

Current audited routes:

- `/cross-asset`
- `/ledger-pnl`
- `/macro-toolkit`
- `/stock-analysis`
- `/product-category-pnl`
- `/pnl-attribution`
- `/bond-analysis`

Known remaining gaps:

- Accessibility remains `3/4`, not `4/4`.
- `/product-category-pnl` formal table now has a mobile-first readout; attribution comparison/detail and liability matrices still need the same treatment.
- Business metric and lineage certification is pending because `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` are not exposed in this Codex App session.
- Non-audited routes are not yet covered by the flagship claim.

## Standard To Hit

A page reaches the target standard only when it satisfies all of the following:

1. The first screen answers the primary business question.
2. Every decision metric keeps source, date, unit, status, stale/fallback/no-data semantics visible.
3. Desktop and tablet keep dense audit-grade raw tables available.
4. Mobile gets a compact decision readout before dense raw grids.
5. Keyboard and assistive-technology workflows can reach the same decision state.
6. The page has targeted tests, live-route smoke, lint, typecheck, debt audit, build, and browser evidence.
7. Business-contract language is only certified when MCP metric and lineage evidence supports it.

## Next Execution Order

### Task 1: Finish Gate G On `/product-category-pnl` Formal Table

**Status:** Complete. Evidence saved under `frontend/.codex-tmp/product-category-pnl-gate-g/`.

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update: `docs/plans/2026-06-05-institutional-frontend-continuation-plan.md`

**Step 1: Write the failing test**

Add assertions that `product-category-formal-table-mobile-readout` exists, appears before `product-category-formal-table-raw-grid`, and summarizes:

- report date
- selected view
- total business net income
- asset-side business net income
- liability-side business net income
- first material business row
- average scale
- weighted yield
- displayed row count

**Step 2: Run RED**

Run from `frontend/`:

```powershell
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
```

Expected: fail only because `product-category-formal-table-mobile-readout` is missing.

**Step 3: Implement display-only readout**

Add page-local readout components in `ProductCategoryPnlPage.tsx`. Use existing table payload fields only:

- `selectedDate`
- `selectedView`
- `displayedGrandTotal`
- `displayedAssetTotal`
- `displayedLiabilityTotal`
- `rowsToRender`
- existing product-category formatters

Do not recalculate metric formulas or redefine official product-category PnL semantics.

**Step 4: Preserve raw grid**

Wrap the existing formal table with `data-testid="product-category-formal-table-raw-grid"` and keep the original `data-testid="product-category-table"` unchanged.

**Step 5: Add mobile styling**

In `ProductCategoryPnlPage.css`, hide the readout on desktop/tablet and show it under the existing mobile breakpoint. Requirements:

- readable at `390px`
- no document-level horizontal overflow
- compact institutional rows
- no decorative nested-card treatment
- raw table remains reachable after the readout

**Step 6: Run GREEN and verification**

Run from `frontend/`:

```powershell
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Expected: all pass, debt baseline does not grow.

**Step 7: Browser verify**

Open `/product-category-pnl` at:

- desktop `1440x1000`
- tablet `768x1000`
- mobile `390x1000`

Save evidence under:

- `frontend/.codex-tmp/product-category-pnl-gate-g/`

Record status `200`, no fallback route, no permanent loading, no page-level horizontal overflow, no blocking console errors, and mobile readout before raw grid.

**Completion evidence:**

- RED: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because `product-category-formal-table-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 84 passed.
- Related dirty-worktree blocker repair: `npm run test -- src/test/MacroToolkitPage.test.tsx`: 66 passed.
- Live routes: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- `npm run lint`, `npm run typecheck`, `npm run debt:audit`, and `npm run build`: passed.
- Browser verification: desktop `1440px`, tablet `768px`, and mobile `390px` returned status `200`; readout is hidden on desktop/tablet, visible at mobile `390px`, appears before the raw grid/table, and no document-level horizontal overflow or console/page errors were recorded.

### Task 2: Add `/product-category-pnl` Attribution Comparison And Detail Readouts

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Steps:**

1. Add failing tests for `product-category-attribution-comparison-table` and `product-category-attribution-detail-table` mobile readouts.
2. Summarize monthly delta, largest effect, unexplained effect, closure error, row state, selected category, current/prior date pair, current/prior income, scale, and yield.
3. Keep raw comparison/detail tables available for reconciliation.
4. Run the same product-category page tests and browser verification matrix.

### Task 3: Harden `/product-category-pnl` Liability Matrices

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Steps:**

1. Add mobile readouts for `product-category-liability-side-detail-matrix`.
2. Add mobile readouts for `product-category-liability-side-currency-matrix-*`.
3. Add fallback readout for `product-category-liability-side-detail-table`.
4. Preserve raw matrix tables.
5. Browser verify `390px`, `768px`, and `1440px`.

### Task 4: Gate H Accessibility `4/4`

**Files:**

- Inspect/modify: `frontend/src/layouts/WorkbenchShell.tsx`
- Inspect/modify: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Inspect/modify: page-local files under `frontend/src/features/` for the seven audited routes
- Test: `frontend/src/test/WorkbenchShell.test.tsx`
- Test: relevant page tests under `frontend/src/test/`
- Test if existing: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

**Steps:**

1. Audit keyboard order through shell navigation, route controls, tabs, drill actions, and data tables.
2. Add or tighten visible focus states for custom controls.
3. Ensure warnings, stale data, fallback, no-data, blocked, and ready states are not communicated by color alone.
4. Add accessible names only where visible labels are insufficient.
5. Browser-walk the seven flagship routes and record evidence.

**Verify from `frontend/`:**

```powershell
npm run test -- src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

### Task 5: Gate I MCP-Backed Business Contract Certification

**Files:**

- Read/update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Read/update: `docs/page_contracts.md`
- Read/update only with evidence: `docs/metric_dictionary.md`
- Read/update only with evidence: `docs/golden_sample_catalog.md`

**Required tools when available:**

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

**Steps:**

1. Trace each changed displayed metric through API response, adapter/model, selector/state, component, chart/table.
2. Confirm unit, precision, report date, as-of date, stale/fallback behavior, and golden sample status.
3. Separate `frontend-ready` from `business-contract-certified` in the scorecard.
4. Retire governance markers only when the MCP evidence supports it.

### Task 6: Expand Beyond The Seven Flagship Routes

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. dashboard/workbench home decision surfaces

**Steps per route:**

1. Baseline against `docs/frontend-institutional-standard.md`.
2. Identify the page's single primary business question.
3. Add a first-screen decision stack test.
4. Implement the smallest page-local layout/readout change.
5. Browser verify desktop/tablet/mobile.
6. Update scorecard only with evidence.

## Non-Goals

- No backend formula rewrite.
- No database schema change.
- No auth, scheduler, queue, cache, or global SDK refactor.
- No decorative redesign that hides source/date/unit/status evidence.
- No business definition changes without MCP metric and lineage proof.

## Completion Bar

Do not claim full-system top investment-bank certification until:

1. Gate G is complete for decision-critical mobile tables.
2. Gate H accessibility reaches `4/4` with evidence.
3. Gate I distinguishes frontend readiness from MCP-certified business contracts.
4. Non-audited business routes are scored or explicitly excluded.
5. Targeted tests, live-route smoke, lint, typecheck, debt audit, build, and browser evidence pass for the claimed scope.
