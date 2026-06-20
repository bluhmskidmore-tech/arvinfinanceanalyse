# Institutional Frontend Continuation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the current seven-route flagship frontend from page-surface readiness to a stricter top investment-bank operating standard.

**Architecture:** Keep all work page-scoped, evidence-first, and contract-preserving. Improve mobile readouts, accessibility, visual consistency, and metric certification without changing finance formulas, governance markers, backend services, schema, auth, scheduler, queue, cache, or global SDK layers.

**Tech Stack:** React, TypeScript, Vite, Vitest, browser verification, Ant Design, page-local CSS/CSS modules, existing MOSS design tokens.

---

## Current Position

The audited flagship routes are page-surface ready:

- `/cross-asset`
- `/ledger-pnl`
- `/macro-toolkit`
- `/stock-analysis`
- `/product-category-pnl`
- `/pnl-attribution`
- `/bond-analysis`

The current scorecard shows `26/28` or `27/28` for these routes. This is strong enough to call the audited surface flagship-ready, but not enough to call the whole frontend fully certified. Remaining gaps are:

- Accessibility remains `3/4`, not `4/4`.
- Lower-page mobile tables still depend on controlled horizontal scroll in some places. `/bond-analysis` accounting-DV01/top-holdings, `/pnl-attribution` product-category attribution/YTD, and `/product-category-pnl` formal table now have mobile-first readouts; `/product-category-pnl` attribution comparison/detail remains next.
- Business metric and lineage certification is pending MCP evidence availability.
- Non-audited routes still need independent scorecards.

## Design Direction

Use the "institutional workbench" direction, not a marketing SaaS direction:

- Dense, calm, decision-first composition.
- Source/date/unit/status visible near every decision metric.
- Muted but not monochrome palette; reserve accent color for state, action, and risk.
- No decorative glassmorphism, purple-tech gradients, hero marketing patterns, or visual effects that reduce evidence clarity.
- Tables stay available for audit, but mobile users get a summary readout before raw grids.

The `ui-ux-pro-max` lookup recommended dashboard typography and finance chart patterns, but also returned glassmorphism and purple/gold SaaS cues. Reject those conflicting cues for MOSS because the project standard favors restrained institutional evidence surfaces over decorative depth.

## Gate G: Mobile Tabular Readout Hardening

**Primary question:** Can a desk user understand dense table content on mobile before entering raw grid exploration?

**Initial scope:** Start with `/bond-analysis`, then expand to `/product-category-pnl` and `/pnl-attribution`.

**Current status:** `/bond-analysis` accounting-DV01/top-holdings, `/pnl-attribution` product-category attribution/YTD, and `/product-category-pnl` formal table readouts are complete and verified. Continue Gate G with `/product-category-pnl` attribution comparison/detail and liability matrices.

### Task G1: Add Bond Mobile Readout Tests

**Files:**

- Modify: `frontend/src/test/BondAnalyticsView.test.tsx`
- Inspect: `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx`
- Inspect: `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css`

**Step 1: Add failing test**

Add assertions that:

- `bond-analysis-accounting-dv01-mobile-readout` renders before `bond-analysis-accounting-dv01-raw-grid`.
- `bond-analysis-holdings-mobile-readout` renders before `bond-analysis-holdings-raw-grid`.
- The DV01 readout includes labels for accounting category, highest DV01 category, duration, money value, and position count.
- The holdings readout includes labels for top holdings, largest holding, rating, market value, yield, duration, and weight.

**Step 2: Run RED**

```powershell
cd frontend
npm run test -- src/test/BondAnalyticsView.test.tsx
```

Expected: fail only because the mobile readout anchors are missing.

### Task G2: Implement Bond Mobile Readouts

**Files:**

- Modify: `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx`
- Modify: `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css`
- Test: `frontend/src/test/BondAnalyticsView.test.tsx`

**Step 1: Add display-only components**

Create page-local helper components:

- `AccountingDv01MobileReadout`
- `HoldingsMobileReadout`

Use only existing payload fields already shown on the page. Do not recalculate official DV01, KRD, duration, yield, PnL, or market value.

**Step 2: Place readouts before raw grids**

- Render `AccountingDv01MobileReadout` immediately before `.accountingDv01Grid`.
- Render `HoldingsMobileReadout` immediately before `.holdingsTable`.
- Keep `bond-analysis-accounting-dv01-summary` and `bond-analysis-holdings-table` available for audit.

**Step 3: Style for mobile-first decision use**

CSS requirements:

- Visible and useful at `390px`.
- Compact institutional rows, no nested card-in-card feel.
- No document-level horizontal overflow.
- Hide or de-emphasize on desktop only if the desktop raw grid already answers the same question better.

**Step 4: Run GREEN**

```powershell
cd frontend
npm run test -- src/test/BondAnalyticsView.test.tsx
```

Expected: pass.

### Task G3: Verify Bond Slice

**Files:**

- Test: `frontend/src/test/BondAnalyticsViewContent.test.tsx`
- Test: `frontend/src/test/BondAnalyticsView.test.tsx`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`

**Commands:**

```powershell
cd frontend
npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Expected: all pass, debt baseline does not grow.

**Browser evidence:**

- Verify `/bond-analysis` at `1440x1000`, `768x1000`, and `390x1000`.
- Save screenshots under `frontend/.codex-tmp/bond-analysis-gate-g/`.
- Record no fallback route, no permanent loading, no blocking console errors, no document-level horizontal overflow, and mobile readout before raw grid.

**Completion evidence:**

- RED: `npm run test -- src/test/BondAnalyticsView.test.tsx` failed only because `bond-analysis-accounting-dv01-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/BondAnalyticsView.test.tsx`: 15 passed.
- Page slice: `npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx`: 64 passed.
- Live routes: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- `npm run lint`, `npm run typecheck`, `npm run debt:audit`, and `npm run build`: passed.
- Browser evidence: `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json`; screenshots under `frontend/.codex-tmp/bond-analysis-gate-g/`.

### Task G4: Inventory Remaining Mobile Table Watch Items

**Files:**

- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Inspect: `frontend/src/features/pnl-attribution/components/AdvancedAttributionChart.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/CampisiDecisionGradePanel.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/VolumeRateAnalysisChart.tsx`

**Step 1: Inventory**

Create a short watch list in `docs/audits/2026-06-05-institutional-frontend-scorecard.md` or a new Gate G audit note:

- table test id
- page/section
- business question
- current mobile behavior
- proposed summary readout
- raw grid preservation status

**Step 2: Prioritize**

Fix in this order:

1. `/bond-analysis` DV01 and holdings tables. Done.
2. `/pnl-attribution` product-category attribution and YTD tables. Done.
3. `/product-category-pnl` formal table. Done.
4. `/product-category-pnl` attribution comparison/detail and liability-side matrices.
4. Deep diagnostic tables only after first-screen and decision-critical tables are clean.

### Task G5: Add PnL Attribution Mobile Readouts

**Files:**

- Modified: `frontend/src/test/PnlAttributionPage.test.tsx`
- Modified: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Modified: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Added: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Intent:** Give mobile users a compact product-category attribution and YTD readout before raw grids, while keeping the raw tables available for audit.

**Implementation:**

- Added `pnl-attribution-product-category-attribution-mobile-readout` before `pnl-attribution-product-category-attribution-raw-grid`.
- Added `pnl-attribution-product-category-ytd-mobile-readout` before `pnl-attribution-product-category-ytd-raw-grid`.
- Used existing product-category payload fields only: business net income delta, displayed effects, unexplained effect, closure error, row state, YTD scale, YTD business net income, weighted yield, and row count.
- Kept `pnl-attribution-product-category-attribution-table` and `pnl-attribution-product-category-ytd-table` unchanged for raw reconciliation.

**Completion evidence:**

- RED: `npm run test -- src/test/PnlAttributionPage.test.tsx` failed only because `pnl-attribution-product-category-attribution-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/PnlAttributionPage.test.tsx`: 6 passed.
- Page slice: `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx`: 45 passed.
- Live routes: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- `npm run lint`, `npm run typecheck`, `npm run debt:audit`, and `npm run build`: passed.
- Browser evidence: `frontend/.codex-tmp/pnl-attribution-gate-g/layout-verification.json`; screenshots under `frontend/.codex-tmp/pnl-attribution-gate-g/`.

### Task G6: Add Product Category Formal Table Mobile Readout

**Files:**

- Modified: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modified: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modified: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Updated: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`
- Updated: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Intent:** Give mobile users a compact formal product-category table readout before the raw official grid, while preserving the raw table for audit and reconciliation.

**Implementation:**

- Added `product-category-formal-table-mobile-readout` before `product-category-formal-table-raw-grid`.
- Used existing formal table payload fields only: report date, view, displayed row count, grand/asset/liability business net income, first material business row, scale, and weighted yield.
- Kept `product-category-table` unchanged inside the raw grid wrapper.
- Desktop/tablet keep the readout hidden; mobile `390px` shows the compact readout before the raw grid.

**Completion evidence:**

- RED: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because `product-category-formal-table-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 84 passed.
- A dirty-worktree `/macro-toolkit` lint/build blocker was repaired narrowly, then `npm run test -- src/test/MacroToolkitPage.test.tsx`: 66 passed.
- Live routes: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- `npm run lint`, `npm run typecheck`, `npm run debt:audit`, and `npm run build`: passed.
- Browser evidence: `frontend/.codex-tmp/product-category-pnl-gate-g/layout-verification.json`; screenshots under `frontend/.codex-tmp/product-category-pnl-gate-g/`.

## Gate H: Accessibility 4/4 Upgrade

**Primary question:** Can keyboard and assistive-technology users complete the same decision workflow?

### Task H1: Keyboard Order Audit

**Files:**

- Inspect: `frontend/src/layouts/WorkbenchShell.tsx`
- Inspect changed flagship page files under `frontend/src/features/`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`

**Checklist:**

- Skip link or equivalent fast path to main content on nav-heavy pages.
- Logical tab order through shell, filters, tabs, drill actions, and data tables.
- No keyboard traps in drawer/tab/detail surfaces.
- Visible focus state on every custom action.

### Task H2: Non-Color Status Cues

**Files:**

- Inspect/modify page-local CSS and components for the seven flagship routes.

**Checklist:**

- Warning, stale, fallback, no-data, blocked, ready, and temporary-exception states have visible text or icons, not color alone.
- State labels remain visible at `390px`.
- Status badges have accessible names when visible text is not enough.

### Task H3: Accessibility Verification

**Commands:**

```powershell
cd frontend
npm run test -- src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run build
```

Expected: all pass, plus manual/browser keyboard walkthrough evidence recorded for all seven routes.

## Gate I: MCP-Backed Metric And Lineage Certification

**Primary question:** Which pages are only frontend-ready, and which are business-contract-certified?

**Required tools when available:**

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

**Rules:**

- Do not change metric definitions from local intuition.
- Do not retire `temporary-exception`, stale, fallback, no-data, or formal-use markers without evidence.
- Trace every changed metric through API response -> adapter/model -> state/selector -> component -> chart/table.

**Deliverable:**

Create a certification table with:

- route
- metric id/name
- unit
- report/as-of date rule
- source table/API
- fallback/stale behavior
- golden sample status
- certified/not certified
- unresolved evidence gap

## Gate J: Expansion Beyond Seven Flagship Routes

**Primary question:** Which next business page deserves flagship treatment?

**Selection criteria:**

- Business-critical decision page.
- Has visible metrics with source/date/unit/status semantics.
- Has known first-screen, responsive, or evidence-chain risk.
- Has targeted tests or can get small useful tests quickly.

**Process per route:**

1. Baseline against `docs/frontend-institutional-standard.md`.
2. Add route/page-specific tests before changing layout.
3. Implement one page-level decision surface.
4. Browser verify desktop/tablet/mobile.
5. Update scorecard only with evidence.

## Completion Bar For "Top Investment-Bank Standard"

Do not claim full-system completion until:

1. All audited flagship routes remain at least `24/28`.
2. Accessibility reaches `4/4` with keyboard evidence.
3. Mobile decision readouts exist before decision-critical raw grids.
4. Browser checks pass at `390px`, `768px`, and `1440px`.
5. Lint, typecheck, debt audit, targeted tests, live-route smoke, and build pass.
6. MCP-backed metric/lineage evidence certifies any business-contract wording changes.
7. Non-audited routes are either scored or explicitly excluded from the flagship claim.

## Execution Notes

- Use TDD for code changes.
- Keep each gate page-scoped.
- Do not add new dependencies unless there is no reasonable existing path.
- Do not commit unless the user explicitly asks for a commit.
- Record screenshots, measurements, and test output in the relevant docs after each gate.
