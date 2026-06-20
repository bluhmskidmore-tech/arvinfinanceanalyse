# Institutional Frontend Next Optimization Implementation Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `using-superpowers`, `frontend-design`, `critique`, `audit`, `adapt`, `polish`, `karpathy-guidelines`, and `verification-before-completion` while executing this plan.

**Goal:** Move MOSS from one flagship proof point to a repeatable top investment-bank-grade frontend standard across the next business-critical pages.

**Architecture:** Keep the interface evidence-first and page-scoped. Use the institutional shell scope, page-local CSS, existing page primitives, route readiness contracts, and browser measurements. Do not change business metric definitions or governance statuses without MCP evidence.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, page-local CSS, existing MOSS design tokens.

---

## Direct Answer

The flagship page set has reached the current target for the seven audited business-critical routes.

`/cross-asset` demonstrates the direction: dense, calm, evidence-first, responsive, and verified. `/ledger-pnl` has reached page-level Gate A closure, `/macro-toolkit` has reached Gate B closure, `/stock-analysis` has reached Gate C closure after the narrow-screen decision-order pass, `/product-category-pnl` has reached Gate D closure after the formal-readiness band and governed first-screen preview pass, `/pnl-attribution` has reached Gate E closure after the attribution decision-strip and lens-boundary pass, and `/bond-analysis` has reached Gate F closure after the fixed-income decision cockpit pass.

This does not certify every route in MOSS. It means the audited flagship scope now has browser proof, regression coverage, and scorecard evidence. Metric definitions, formal-use semantics, and governance markers remain unchanged unless MCP metric/lineage evidence later authorizes a business-contract change.

Next recommended optimization: continue system hardening. Gate G now covers `/bond-analysis` accounting DV01/top holdings, `/pnl-attribution` product-category attribution/YTD readouts, and `/product-category-pnl` formal table readout; continue the same pattern on `/product-category-pnl` attribution comparison/detail and liability matrices. Gate H should lift accessibility from `3/4` to `4/4`, and Gate I should use MCP metric/lineage evidence to certify business contracts where the tools are available.

## Evidence Snapshot

Local evidence used:

- `/cross-asset` screenshots: `frontend/.codex-tmp/cross-asset-gate1-desktop-cascade-fixed.png`, `frontend/.codex-tmp/cross-asset-gate1-tablet-cascade-fixed.png`, `frontend/.codex-tmp/cross-asset-gate1-mobile-cascade-fixed.png`, `frontend/.codex-tmp/cross-asset-gate1-alias-desktop-cascade-fixed.png`.
- `/ledger-pnl` final screenshots: `frontend/.codex-tmp/ledger-pnl-gate2-desktop-final3.png`, `frontend/.codex-tmp/ledger-pnl-gate2-tablet-final3.png`, `frontend/.codex-tmp/ledger-pnl-gate2-mobile-final3.png`.
- `/ledger-pnl` final measured closure:
  - desktop functional audit strip top around `377px`, summary cards top around `880px`
  - tablet functional audit strip top around `516px`, summary cards top around `1203px`
  - mobile functional audit strip top around `505px`, summary cards top around `906px`
  - no horizontal overflow or blocking console errors in the final pass
- `/macro-toolkit` latest compact screenshots: `frontend/.codex-tmp/macro-toolkit-gateB-desktop-compact2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-tablet-compact2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-mobile-compact2.png`.
- `/macro-toolkit` latest measured blocker:
  - desktop governance/action console top around `1325px`
  - tablet governance/action console top around `3067px`
  - mobile governance top around `2043px`, operations/action console top around `2740px`, data-health evidence top around `7419px`
  - no horizontal overflow or blocking console errors, but mobile decision closure is still too late for flagship standard
- `/macro-toolkit` Gate B final screenshots: `frontend/.codex-tmp/macro-toolkit-gateB-desktop-final2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-tablet-final2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-mobile-final2.png`.
- `/macro-toolkit` Gate B final measured closure:
  - desktop governance/action console top around `1325px`
  - tablet governance top around `3067px`, action console top around `3375px`
  - mobile brief height around `437px`, governance top around `1554px`, action console top around `1907px`
  - page status `200`, no fallback route, no permanent busy state, no blocking console errors, and no document-level horizontal overflow
- `/stock-analysis` Gate C final screenshots: `frontend/.codex-tmp/stock-analysis-gateC-desktop-final.png`, `frontend/.codex-tmp/stock-analysis-gateC-tablet-final.png`, `frontend/.codex-tmp/stock-analysis-gateC-mobile-final.png`.
- `/stock-analysis` Gate C final measured closure:
  - desktop cockpit top around `105px`, review queue top around `405px`, closed-loop trust evidence top around `132px`, sector chart top around `525px`
  - tablet review queue top around `557px`, consensus top around `645px`, closed-loop trust evidence top around `742px`, sector chart top around `1035px`
  - mobile review queue top around `353px`, consensus top around `441px`, closed-loop trust evidence top around `538px`, sector chart top around `831px`
  - page status `200`, no fallback route, no permanent busy state, no blocking console errors, and no document-level horizontal overflow
- `/product-category-pnl` Gate D final screenshots: `frontend/.codex-tmp/product-category-pnl-gateD-desktop-final3.png`, `frontend/.codex-tmp/product-category-pnl-gateD-tablet-final3.png`, `frontend/.codex-tmp/product-category-pnl-gateD-mobile-final3.png`.
- `/product-category-pnl` Gate D final measurements: `frontend/.codex-tmp/product-category-pnl-gateD-final3-measurements.json`.
- `/product-category-pnl` Gate D final measured closure:
  - desktop hero `344px`, status strip `565px`, formal readiness band `997px`, first category row preview `1242px`
  - tablet hero `499px`, status strip `938px`, formal readiness band `1370px`, first category row preview `1709px`
  - mobile hero `398px`, status strip `781px`, formal readiness band `1358px`, first category row preview `1752px`
  - page status `200`, no fallback route, no permanent busy state, no document-level horizontal overflow, and only local dev-server/React informational console messages
- `/product-category-pnl` Gate G formal table screenshots: `frontend/.codex-tmp/product-category-pnl-gate-g/desktop-1440.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/tablet-768.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/mobile-390.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/mobile-formal-table-readout.png`.
- `/product-category-pnl` Gate G formal table measurements: `frontend/.codex-tmp/product-category-pnl-gate-g/layout-verification.json`.
- `/product-category-pnl` Gate G formal table measured closure:
  - desktop and tablet keep the mobile formal table readout DOM anchor hidden and preserve the raw grid experience
  - mobile `390px` shows the formal table readout before `product-category-formal-table-raw-grid`
  - status `200`, no document-level horizontal overflow, no console warnings/errors, no page errors, and readout-before-raw-grid order verified
- `/pnl-attribution` Gate E final screenshots: `frontend/.codex-tmp/pnl-attribution-gate-e/desktop-1440.png`, `frontend/.codex-tmp/pnl-attribution-gate-e/tablet-768.png`, `frontend/.codex-tmp/pnl-attribution-gate-e/mobile-390.png`.
- `/pnl-attribution` Gate E measurements: `frontend/.codex-tmp/pnl-attribution-gate-e/layout-verification.json`.
- `/pnl-attribution` Gate E final measured closure:
  - desktop title `199px`, decision strip `317px-523px`, product-category lens `543px`
  - tablet title `298px`, decision strip `479px-684px`, product-category lens `704px`
  - mobile title `269px`, decision strip `469px-786px`, product-category lens starts at `806px`; the decision strip is compacted into two-column evidence rows on narrow screens
  - page status `200`, no fallback route, no permanent busy state, no document-level horizontal overflow, no blocking console errors, and no page errors
- `/pnl-attribution` Gate G screenshots: `frontend/.codex-tmp/pnl-attribution-gate-g/desktop-1440.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/tablet-768.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-390.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-attribution-readout.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-ytd-readout.png`.
- `/pnl-attribution` Gate G measurements: `frontend/.codex-tmp/pnl-attribution-gate-g/layout-verification.json`.
- `/pnl-attribution` Gate G measured closure:
  - desktop and tablet keep the mobile readout DOM anchors hidden and preserve the raw grid experience
  - mobile `390px` shows product-category attribution and YTD readouts before the raw grids
  - status `200`, no document-level horizontal overflow, no console warnings/errors, no page errors, and readout-before-raw-grid order verified
- `/bond-analysis` Gate F final screenshots: `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-desktop-1440.png`, `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-tablet-768.png`, `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-mobile-390.png`.
- `/bond-analysis` Gate F measurements: `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-measurements.json`.
- `/bond-analysis` Gate F final measured closure:
  - desktop cockpit top around `207px`, cockpit height around `185px`
  - tablet cockpit top around `227px`, cockpit height around `260px`
  - mobile cockpit top around `349px`, cockpit height around `367px`
  - page status `200`, no fallback route, no permanent loading, no document-level horizontal overflow, no blocking console errors, and horizontal text layout retained for title and overview labels
  - Gate G now adds compact mobile readouts before the lower accounting-DV01 and holdings raw grids while preserving the raw grids for audit
- `/bond-analysis` Gate G screenshots: `frontend/.codex-tmp/bond-analysis-gate-g/desktop-1440.png`, `frontend/.codex-tmp/bond-analysis-gate-g/tablet-768.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-390.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-accounting-dv01-section.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-holdings-section.png`.
- `/bond-analysis` Gate G measurements: `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json`.
- `/bond-analysis` Gate G measured closure:
  - desktop and tablet keep the mobile readout DOM anchors hidden and preserve the raw grid experience
  - mobile `390px` shows the accounting-DV01 and holdings readouts before the raw grids
  - status `200`, no document-level horizontal overflow, no console warnings/errors, no page errors, and readout-before-raw-grid order verified
- Latest full verification for Gate D:
  - `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 81 passed
  - `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed
  - `npm run lint`: passed
  - `npm run typecheck`: passed
  - `npm run debt:audit`: passed, no growth over baseline
  - `npm run build`: passed
- Latest Gate E verification:
  - `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx`: 45 passed
  - `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed
  - `npm run lint`: passed
  - `npm run typecheck`: passed
  - `npm run debt:audit`: passed, no growth over baseline
  - `npm run build`: passed
- Latest Gate F verification:
  - `npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx`: 84 passed
  - `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed
  - `npm run lint`: passed
  - `npm run typecheck`: passed
  - `npm run debt:audit`: passed, no growth over baseline
  - `npm run build`: passed
  - production-preview screenshots and measurements passed at desktop `1440x1000`, tablet `768x1000`, and mobile `390x1000`

MCP status:

- `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` are not exposed in this Codex App session.
- Therefore, do not retire `temporary-exception`, change formal-use semantics, or rewrite metric definitions in this run.

## Gate A: Ledger PnL First-Screen Closure

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Can today’s总账损益 page be trusted for candidate ledger explanation, and what blocks formal/monthly use?

**Files:**

- Modify: `frontend/src/layouts/WorkbenchShell.tsx`
- Modify: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Modify: `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`
- Modify: `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.css`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`
- Test: `frontend/src/test/LedgerPnlPage.test.tsx`
- Test: `frontend/src/test/LiveRouteReadiness.test.tsx`
- Test if route smoke exists: `frontend/src/test/LedgerPnlRoutesSmoke.test.tsx`

### Task A1: Add Stable Shell Scope For Ledger PnL

**Intent:** Give `/ledger-pnl` a stable shell class so page compression does not rely on brittle descendants or route content selectors.

**Steps:**

1. Add `isLedgerPnlShell = currentSection.key === "ledger-pnl"` in `WorkbenchShell.tsx`.
2. Add `workbench-shell-grid--ledger-pnl` to the shell root when `isLedgerPnlShell` is true.
3. Add a `WorkbenchShell.test.tsx` assertion that `/ledger-pnl` exposes the class.
4. Add a CSS-contract assertion that ledger shell compression lives in `workbenchInstitutionalConsole.css`.

**Do not:**

- Do not change the page route.
- Do not hide governance banners globally.
- Do not apply ledger compression to all portfolio pages.

**Verify:**

```powershell
npm run test -- src/test/WorkbenchShell.test.tsx
```

### Task A2: Compress Ledger Shell Chrome Only Where It Blocks First-Screen Closure

**Intent:** On `/ledger-pnl`, reduce terminal bar, ticker, subnav, and temporary-exception banner footprint while keeping evidence visible.

**Steps:**

1. In `workbenchInstitutionalConsole.css`, add route-scoped ledger rules under `.workbench-shell-grid--institutional-console.workbench-shell-grid--ledger-pnl`.
2. Desktop and tablet: reduce main-column gaps, terminal bar min-height, subnav header footprint, link padding, and governance banner padding.
3. Mobile: keep route links accessible, but collapse visual bulk enough that the page title, filters, audit verdict, and first metrics enter the early scroll range.
4. Keep status/source/fallback text visible; shorten only layout chrome, not business evidence.

**Acceptance:**

- No horizontal overflow at 390px.
- Functional audit strip starts substantially earlier than the baseline `1136px` mobile top.
- Summary cards start substantially earlier than the baseline `3775px` mobile top.

**Verify:**

```powershell
npm run test -- src/test/WorkbenchShell.test.tsx
```

### Task A3: Reframe Ledger Page Header, Filters, Audit Strip, And Metrics Into A Decision Stack

**Intent:** The first content region should answer trust, conclusion, top metrics, and blocker/action without forcing a long scroll.

**Steps:**

1. Replace repeated inline header/filter/table layout styles touched in `LedgerPnlPage.tsx` with page-local CSS classes where practical.
2. Wrap the page title, mode badge, filters, functional audit strip, and summary cards in a `ledger-pnl-decision-stack`.
3. Make filters compact and tokenized with labelled controls.
4. Keep `ledger-pnl-functional-audit-strip` before monthly analysis and raw tables.
5. Present summary cards directly after the audit strip, but compact note typography on mobile so candidate evidence remains visible.
6. Do not change `ledgerCandidateSummaryMetrics` meanings, values, or formal-use labels.

**Acceptance:**

- `ledger-pnl-page-title`, `ledger-pnl-functional-audit-strip`, and `ledger-pnl-summary-cards` remain present.
- Candidate labels and notes remain visible.
- Formal/monthly blocker language remains explicit.
- No new duplicated `style={{ ... }}` layout blocks in touched areas.

**Verify:**

```powershell
npm run test -- src/test/LedgerPnlPage.test.tsx
```

### Task A4: Add First-Screen Regression Guards

**Intent:** Prevent future edits from pushing the decision content below navigation again.

**Steps:**

1. In `LedgerPnlPage.test.tsx`, add an order assertion:
   - title before filters
   - filters before functional audit strip
   - functional audit strip before summary cards
   - summary cards before monthly analysis
2. Add assertions that candidate metric badges/notes remain in the summary cards.
3. Add an assertion that the functional audit strip includes monthly analysis status and formal boundary/status text.

**Verify:**

```powershell
npm run test -- src/test/LedgerPnlPage.test.tsx
```

### Task A5: Browser Verification For Ledger PnL

**Steps:**

1. Open `/ledger-pnl` at desktop `1440x900`.
2. Open `/ledger-pnl` at tablet `768x1024`.
3. Open `/ledger-pnl` at mobile `390x844`.
4. Capture screenshots under `frontend/.codex-tmp/`.
5. Measure:
   - page status is `200`
   - no fallback route
   - no permanent loading
   - no horizontal overflow
   - functional audit strip top
   - summary cards top
   - monthly analysis panel top
   - visible evidence text for source/status/formal boundary

**Acceptance:**

- Desktop first screen includes title, controls, functional audit verdict, and key candidate metrics.
- Mobile first screen reaches the audit verdict and early decision facts without incoherent overlap.
- Summary cards are close enough to the first screen to support immediate decision-making.

## Gate B: Macro Toolkit Flagship Closure

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Is the macro toolkit ready to support today’s macro/risk workflow, and which source or execution gap blocks it?

**Files:**

- Inspect/modify: `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`
- Inspect/modify: `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.css`
- Test: `frontend/src/test/MacroToolkitPage.test.tsx`
- Route contract: `frontend/src/test/liveRouteReadinessContracts.ts`

**Steps:**

1. Keep the mobile first-screen hierarchy to four signals only: readiness verdict, blocker, next action, and source/data-health signoff.
2. Convert duplicated committee/readiness details below the first screen into horizontal evidence rails or later detail sections.
3. Push the governance/action console earlier on mobile by removing repeated first-screen summaries, not by hiding governance evidence.
4. Preserve all source/date/unit/status, stale/fallback/no-data, and temporary-exception semantics.
5. Add order tests that lock the sequence: cockpit -> investment brief -> governance gate -> operations console -> evidence/data-health detail.
6. Add evidence visibility tests for readiness status, blocker, action link, data-health signoff, and committee pack readiness.
7. Browser verify desktop/tablet/mobile and save final screenshots under `frontend/.codex-tmp/`.

**Acceptance:**

- Mobile brief height targets below about `600px`.
- Mobile governance/action console target top is around `1600px-2000px` or earlier.
- Mobile data-health signoff appears as early evidence, while full data-health detail may remain later.
- Desktop/tablet remain dense, aligned, and non-overflowing.
- No route fallback, permanent loading state, horizontal overflow, or blocking console errors.

**Verify:**

```powershell
npm run test -- src/test/MacroToolkitPage.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
```

## Gate C: Stock Analysis Flagship Closure

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Can the desk trust the current equity signal stack, and what evidence or review queue controls actionability?

**Files:**

- Inspect/modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Inspect/modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
- Inspect/modify only if model-display evidence requires it: `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`
- Route contract: `frontend/src/test/liveRouteReadinessContracts.ts`

**Steps:**

1. Score `/stock-analysis` against `docs/frontend-institutional-standard.md`.
2. Preserve the existing stock-specific shell labels and Agent panel behavior.
3. Ensure first screen exposes market state, strategy/data quality, evidence status, review queue, and primary action/drill path.
4. Move any risk, data-quality, or implementation-stage constraints above pure charts if they control actionability.
5. Add tests for first-screen anchor ordering and evidence visibility.
6. Browser verify desktop/tablet/mobile.

**Acceptance:**

- A desk user can see trust state, current signal conclusion, evidence status, and review/action queue before deep chart exploration.
- Mobile exposes the same decision path without horizontal overflow.
- No metric semantics or model calculations are changed without contract evidence.

**Verify:**

```powershell
npm run test -- src/test/StockAnalysisPage.test.tsx
npm run test -- src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
```

## Gate D: Product Category PnL Flagship Closure And Evidence Packet

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Can the desk trust the current product-category PnL result for governed review, and what formal/readiness evidence supports or blocks use?

**Files:**

- Modified: `frontend/src/layouts/WorkbenchShell.tsx`
- Modified: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Modified: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modified: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Tested: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Tested: `frontend/src/test/WorkbenchShell.test.tsx`
- Modify: `docs/frontend-institutional-standard.md`
- Updated: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Give `/product-category-pnl` a stable shell scope so page-specific chrome compression stays route-local.
2. Add a formal-readiness band above deep formal tables while retaining report date, view, basis, quality, vendor, fallback, generated-at, and formal metric anchors.
3. Move scenario controls ahead of adjustment and audit sections so the decision path is visible before detail work.
4. Keep full `FormalResultMetaPanel` evidence near the full formal table, not hidden or deleted.
5. Add first-screen and shell regression tests.
6. Browser verify desktop/tablet/mobile and save screenshots/measurements.
7. Record scorecard results for `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, and `/product-category-pnl`.
8. Record which MCP evidence servers were unavailable.
9. List retained governance markers and why they were not retired.
10. Record commands run and results.

## Gate E: PnL Attribution Decision-Surface Closure

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Can the desk explain the current PnL movement with the correct lens, date, source, and approval boundary before drilling into charts?

**Why this page mattered:** `/pnl-attribution` consumes product-category operating PnL, formal FI attribution, TPL market correlation, and Campisi panels. It is business-critical and already had useful guards for independent product-category versus formal FI report dates. Gate E turned the first screen into an approval-grade attribution cockpit rather than another chart-first analysis page.

**Files:**

- Modified: `frontend/src/layouts/WorkbenchShell.tsx`
- Modified: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Modified: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Created: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Tested: `frontend/src/test/PnlAttributionPage.test.tsx`
- Tested: `frontend/src/test/WorkbenchShell.test.tsx`
- Verified route contract: `frontend/src/test/liveRouteReadinessContracts.ts`

**Do not:**

- Do not merge product-category operating PnL and formal FI semantics.
- Do not force product-category and formal FI report dates to match.
- Do not change Campisi, TPL market, or volume/rate calculations.
- Do not retire fallback, stale, date-mismatch, no-data, or formal-boundary warnings without MCP evidence.
- Do not move endpoint implementations into `frontend/src/api/client.ts`.

### Task E1: Score And Baseline `/pnl-attribution`

**Intent:** Establish an honest pre-edit score against `docs/frontend-institutional-standard.md`.

**Steps:**

1. Open `/pnl-attribution` at desktop `1440x900`, tablet `768x1024`, and mobile `390x844`.
2. Measure the top positions of `pnl-attribution-page-title`, `pnl-attribution-workbench-lead`, `pnl-attribution-date-mismatch` or `pnl-attribution-source-date-warning` when present, `pnl-attribution-current-view-lead`, `pnl-attribution-current-view-meta`, and the first active tab body.
3. Record page status, fallback state, permanent loading state, horizontal overflow, and blocking console errors.
4. Score all seven standard dimensions before editing.

**Acceptance:**

- Baseline evidence shows what is actually blocking flagship readiness.
- The plan does not assume metric or lineage changes are allowed.

### Task E2: Add Stable Shell Scope For PnL Attribution

**Intent:** Let `/pnl-attribution` reduce shell chrome only where it blocks first-screen closure.

**Steps:**

1. Add a route-specific shell class such as `workbench-shell-grid--pnl-attribution` in `WorkbenchShell.tsx`.
2. Add a `WorkbenchShell.test.tsx` assertion that `/pnl-attribution` exposes the class.
3. Add route-scoped CSS in `workbenchInstitutionalConsole.css`; keep it narrower than the existing institutional console rules.

**Acceptance:**

- Shell compression is route-local.
- Existing flagship routes retain their current shell classes.

**Verify:**

```powershell
npm run test -- src/test/WorkbenchShell.test.tsx
```

### Task E3: Convert The First Screen Into An Attribution Decision Stack

**Intent:** Make the first screen answer lens, trust, date, actionability, and drill path before charts.

**Steps:**

1. Replace repeated page-level inline layout blocks in `PnlAttributionPage.tsx` and touched `PnlAttributionView.tsx` areas with page-local classes where practical.
2. Group the title, report-date filter, date-resolution warning, lens boundary cards, active-view lead, active-view meta strip, and tab selector into a compact decision stack.
3. Keep `pnl-attribution-product-category-lens-card` and `pnl-attribution-formal-lens-card` visible before any chart-heavy section.
4. Surface the active lens conclusion in plain decision language:
   - product-category tab: product-category operating attribution, FTP-after, `/ui/pnl/product-category`
   - formal FI tabs: formal FI / bond attribution, not product-category operating net income
   - TPL market tab: explicit hybrid exception
   - Campisi tab: decision-grade state and fallback-to-legacy state when relevant
5. Keep `FormalResultMetaPanel` or equivalent compact meta evidence visible before deep panels.
6. Preserve existing data-loading, date-missing, and date-mismatch behavior.

**Acceptance:**

- First-screen order is title -> controls -> date/source warning when present -> lens boundary -> current view lead -> meta evidence -> tab content.
- A user can see whether they are in product-category, formal FI, TPL hybrid, or Campisi decision-grade context without reading chart internals.
- No metric calculation or endpoint behavior changes.

**Verify:**

```powershell
npm run test -- src/test/PnlAttributionPage.test.tsx
```

### Task E4: Add Regression Guards For Lens, Date, And Evidence Ordering

**Intent:** Prevent future edits from collapsing the formal-boundary and date-resolution contract.

**Steps:**

1. Add an order test for first-screen anchors:
   - `pnl-attribution-page-title`
   - `pnl-attribution-workbench-lead`
   - `pnl-attribution-current-view-lead`
   - `pnl-attribution-current-view-meta` or active tab meta evidence
   - active tab body
2. Add assertions that product-category and formal FI lens cards remain visible before advanced tabs.
3. Add assertions that mismatched dates still show both formal FI and product-category dates.
4. Add assertions that missing product-category dates do not block formal FI drill-down.
5. Add assertions that TPL market remains labeled as a hybrid exception with both `/api/pnl-attribution/tpl-market` and `/ui/pnl/product-category`.

**Verify:**

```powershell
npm run test -- src/test/PnlAttributionPage.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
```

### Task E5: Browser Verification For PnL Attribution

**Steps:**

1. Open `/pnl-attribution` at desktop `1440x900`.
2. Open `/pnl-attribution` at tablet `768x1024`.
3. Open `/pnl-attribution` at mobile `390x844`.
4. Capture screenshots under `frontend/.codex-tmp/`.
5. Measure:
   - page status is `200`
   - no fallback route
   - no permanent loading
   - no horizontal overflow
   - title, controls, lens cards, date warning, current view lead, and meta strip top positions
   - visible evidence text for source/date/formal boundary/hybrid exception

**Acceptance:**

- Desktop first screen includes title, controls, lens boundary, active-view conclusion, and meta evidence.
- Mobile first screen reaches the attribution decision state without incoherent overlap.
- Tab content remains reachable and source warnings are not hidden.

### Task E6: Final Verification And Scorecard Update

**Steps:**

1. Run the page-specific tests.
2. Run live-route readiness and smoke tests.
3. Run lint, typecheck, debt audit, and build.
4. Score `/pnl-attribution` against the seven-dimension standard.
5. Update `docs/audits/2026-06-05-institutional-frontend-scorecard.md` only if the evidence supports a flagship-ready verdict.

**Verify:**

```powershell
npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Gate F: Bond Analysis Flagship Closure

**Status:** Page-level complete. Do not rework unless a regression appears during system verification.

**Primary business question:** Can the desk trust today's bond holding and risk readout, explain the main duration/DV01/action-attribution movement, and identify the next review action before entering module detail?

**Why this is the next page:** `/bond-analysis` is the upstream fixed-income risk and holding surface behind several PnL attribution questions. It already has a minimal shell and rich module structure, but the next institutional step is to compress the first screen into one decision cockpit: report date, data-quality status, primary action-attribution conclusion, duration/DV01 risk movement, warnings/blockers, and the one next drill path.

**Files:**

- Inspect/modify: `frontend/src/layouts/WorkbenchShell.tsx`
- Inspect/modify: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Inspect/modify: `frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx`
- Inspect/modify: `frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.module.css`
- Inspect/modify if the decision model needs display-only shaping: `frontend/src/features/bond-analytics/lib/bondAnalyticsOverviewModel.ts`
- Test: `frontend/src/test/BondAnalyticsView.test.tsx`
- Test: `frontend/src/test/BondAnalyticsViewContent.test.tsx`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`
- Route contract: `frontend/src/test/liveRouteReadinessContracts.ts`

**Do not:**

- Do not change bond analytics formulas, KRD/DV01 units, duration math, or action-attribution calculations without MCP metric evidence.
- Do not retire warnings, fallback, stale, no-data, or temporary-exception markers for visual density.
- Do not move endpoint implementations into `frontend/src/api/client.ts`.
- Do not refactor shared query architecture, backend services, database schema, auth, queue, scheduler, or cache layers.

### Task F1: Score And Baseline `/bond-analysis`

**Intent:** Establish a measured pre-edit score against `docs/frontend-institutional-standard.md`.

**Steps:**

1. Open `/bond-analysis` at desktop `1440x1000`, tablet `768x1000`, and mobile `390x1000`.
2. Measure top positions for `bond-analysis-toolbar`, `bond-analysis-overview`, the first data-quality banner, overview panels, and detail section.
3. Record page status, fallback state, permanent loading state, horizontal overflow, blocking console errors, and page errors.
4. Score all seven standard dimensions before editing.

**Acceptance:**

- Baseline evidence identifies whether the blocker is shell chrome, overview ordering, missing decision summary, responsive overflow, or delayed trust evidence.
- The plan does not assume metric or lineage changes are allowed.

### Task F2: Stabilize Route-Scoped Shell And First-Screen Chrome

**Intent:** Keep `/bond-analysis` dense without making a global shell change.

**Steps:**

1. Confirm `workbench-shell-grid--bond-analysis` is applied only for `/bond-analysis`.
2. Add or tighten `WorkbenchShell.test.tsx` assertions for the route class and CSS contract if missing.
3. Use route-scoped CSS only where shell chrome pushes the decision cockpit down.
4. Keep navigation and governance labels visible.

**Verify:**

```powershell
npm run test -- src/test/WorkbenchShell.test.tsx
```

### Task F3: Add A Bond Decision Cockpit Above Module Detail

**Intent:** Make the first screen answer trust, conclusion, risk movement, blocker, and next action.

**Steps:**

1. In `BondAnalyticsViewContent.tsx`, add a compact cockpit between the toolbar and lazy overview/detail modules.
2. Populate it from existing local evidence only:
   - report date and period type
   - client mode / formal basis
   - action-attribution quality and fallback status
   - total PnL from actions
   - duration change from actions
   - start/end DV01 when present
   - warning count and top warning category
   - next action: refresh, inspect action attribution, open credit spread, or resolve data-quality blocker
3. Use page-local module CSS and existing dashboard-home/institutional tokens.
4. Keep `DataQualityBanner`, overview panels, and detail section present; do not hide evidence to shorten the page.
5. Preserve all existing query behavior and error/empty states.

**Acceptance:**

- First screen exposes report date, trust state, primary bond risk/PnL conclusion, warning/blocker, and next action before module detail.
- Mobile is single-column, no horizontal overflow, with readable 390px evidence rows.
- No calculation or endpoint behavior changes.

**Verify:**

```powershell
npm run test -- src/test/BondAnalyticsViewContent.test.tsx
```

### Task F4: Add Regression Guards For Ordering And Evidence

**Intent:** Prevent future edits from pushing trust and risk evidence below module chrome.

**Steps:**

1. Add tests that lock the order: toolbar -> bond decision cockpit -> data-quality banner/overview -> detail section.
2. Add assertions for report date, period type, quality/fallback, total action PnL, duration change, DV01, warning count, and next action.
3. Add tests for missing dates and action-attribution error states so the cockpit does not show fake confidence.
4. Add a route-readiness assertion only if a new anchor is added.

**Verify:**

```powershell
npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
```

### Task F5: Browser Verification For Bond Analysis

**Steps:**

1. Build and serve the production frontend.
2. Open `/bond-analysis` at desktop `1440x1000`.
3. Open `/bond-analysis` at tablet `768x1000`.
4. Open `/bond-analysis` at mobile `390x1000`.
5. Capture screenshots under `frontend/.codex-tmp/bond-analysis-gate-f/`.
6. Measure:
   - page status is `200`
   - no fallback route
   - no permanent loading
   - no horizontal overflow
   - toolbar, decision cockpit, data-quality banner, overview, and detail top positions
   - visible source/date/status/unit evidence

**Acceptance:**

- Desktop first screen includes toolbar, trust state, primary action-attribution conclusion, duration/DV01 evidence, and next action.
- Mobile first screen reaches the decision cockpit without incoherent overlap.
- Warnings and no-data states remain explicit.

### Task F6: Final Verification And Scorecard Update

**Steps:**

1. Run page-specific tests.
2. Run live-route readiness and smoke tests.
3. Run lint, typecheck, debt audit, and build.
4. Score `/bond-analysis` against the seven-dimension standard.
5. Update `docs/audits/2026-06-05-institutional-frontend-scorecard.md` only if the evidence supports a flagship-ready verdict.

**Verify:**

```powershell
npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Gate G: Mobile Tabular Readout Hardening

**Status:** In progress. `/bond-analysis` accounting-DV01/holdings, `/pnl-attribution` product-category attribution/YTD, and `/product-category-pnl` formal table mobile readouts are complete; continue with `/product-category-pnl` attribution comparison/detail and liability matrices.

**Primary business question:** Can a desk user review dense tables on mobile without relying on raw horizontal grids for the first decision layer?

**Target scope:** lower-page tables and grids in `/bond-analysis`, `/product-category-pnl`, `/pnl-attribution`, and other flagship pages where a table is still the primary mobile readout.

**Steps:**

1. Inventory controlled horizontal-scroll grids under the seven flagship routes.
2. For each page, keep the desktop table intact but add a mobile-first summary row, compact comparison strip, or expandable detail list before the raw grid.
3. Preserve source/date/unit/status, stale/fallback/no-data, and governance markers.
4. Add regression tests for mobile summary presence and table fallback visibility.
5. Browser verify `390px`, `768px`, and `1440px` after each route.

**Acceptance:**

- No document-level horizontal overflow.
- The first mobile readout for each table answers the business question before the user enters raw grid exploration.
- Raw tables remain available for audit and reconciliation.

## Gate H: Accessibility 4/4 Upgrade

**Status:** Next recommended quality gate after Gate G begins.

**Primary business question:** Can the same institutional decision workflow be completed by keyboard and assistive technology without losing status, source, or action context?

**Steps:**

1. Audit keyboard order for toolbar controls, decision cockpit actions, tabs, drill-down buttons, and table controls.
2. Add visible focus states where tokenized components do not already provide them.
3. Ensure non-color status cues exist for warning, blocked, ready, fallback, stale, and no-data states.
4. Add aria labels or descriptions only where visible labels are insufficient.
5. Run focused keyboard and accessibility smoke checks across the seven flagship routes.

**Acceptance:**

- Scorecard accessibility can move from `3/4` to `4/4` with evidence, not assumption.
- No visual regression in desktop/tablet/mobile screenshots.

## Gate I: MCP-Backed Business Contract Certification

**Status:** Pending project MCP availability.

**Primary business question:** Which flagship pages can move from frontend page-level closure to business-contract-certified closure?

**Steps:**

1. Use `moss-metric-contracts` to verify metric definitions, units, and golden samples.
2. Use `moss-lineage-evidence` to verify source version, rule/cache lineage, fallback/stale status, and governance evidence.
3. Use `moss-data-catalog` to confirm tables, columns, and report dates.
4. Use `gitnexus` to inspect cross-page impact before changing shared business paths.
5. Only then retire temporary exceptions, update formal-use semantics, or change metric wording.

**Acceptance:**

- No governance marker is retired without source-backed evidence.
- Scorecards distinguish page-surface readiness from business-contract certification.

## Full Verification Matrix

After each page gate:

```powershell
npm run test -- <page-specific-tests>
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Completion Criteria

Do not claim the whole frontend has reached top investment-bank standard until:

1. `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis` each score at least `24/28`.
2. Each page has desktop/tablet/mobile browser proof.
3. Each page has no horizontal overflow, fallback route, permanent loading, or blocking console errors.
4. Visible metrics retain source/date/unit/status semantics.
5. Governance markers remain unless metric-contract and lineage evidence justify retirement.
6. Lint, typecheck, debt audit, build, targeted tests, and live route tests pass.

For the next expansion, keep adding pages only after each route has its own scorecard, screenshots, measurements, targeted tests, live-route tests, lint, typecheck, debt audit, and build evidence.
