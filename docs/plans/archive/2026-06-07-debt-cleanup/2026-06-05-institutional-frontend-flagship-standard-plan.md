# Institutional Frontend Flagship Standard Plan

> **For Codex:** REQUIRED SUB-SKILLS: use `frontend-design`, `critique`, `audit`, `normalize`, `adapt`, `polish`, and `verification-before-completion` when executing this plan.

**Goal:** Raise MOSS frontend from page-by-page closure to a top investment-bank-grade institutional workbench standard.

**Architecture:** Keep the product evidence-first and data-dense. Do not create a marketing-style redesign. Standardize around the existing institutional console tokens, page-v2 primitives, domain-local page CSS, route contracts, and browser verification.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, ECharts, AG Grid, page-local CSS, existing MOSS design tokens.

---

## Definition Of Top Investment-Bank Standard

The target is not "prettier." The target is a desk-grade decision surface:

1. **Trust before beauty**
   - Every visible metric has source, date, unit, status, stale/fallback/no-data semantics.
   - Evidence text is visible on desktop and mobile, not tooltip-only.
   - Temporary/governance markers are retired only with metric-contract and lineage evidence.

2. **First-screen decision closure**
   - Within two seconds, a user can answer: "Can I rely on this page today, and what is the primary conclusion?"
   - Hero/title, status strip, primary judgment, and top action/output entry points fit without incoherent overlap.
   - The first screen is dense, not decorative.

3. **Institutional visual system**
   - Compact, calm, aligned, data-dense, high contrast, low ornament.
   - Uses the existing institutional token family and avoids one-off color/spacing.
   - No generic AI tells: no decorative blobs, no marketing hero cards, no purple gradient aesthetic, no fake glassy dashboards.

4. **Operational resilience**
   - Loading, empty, stale, fallback, blocked-source, and error states are explicit.
   - Mobile is usable at 390px with no horizontal overflow.
   - Keyboard focus, contrast, and ARIA affordances are release gates.

5. **Verification as product behavior**
   - Each page has targeted component tests, route readiness checks, browser screenshots/measurements, debt audit, lint, typecheck, and build evidence.

## Current Status

`/cross-asset` Gate 1 is now a page-closure proof point:

- First-screen responsive selector mismatch fixed.
- Status evidence is visible and mobile-safe.
- Desktop/mobile/alias browser checks passed.
- Targeted tests, live-route tests, lint, typecheck, debt audit, and build passed.

It is not yet proof that the whole system has reached flagship standard. It proves the operating model works.

## Execution Model

Run this as page-level gates. Do not open broad app-wide redesign.

### Gate 0: Standardize The Audit Scorecard

**Files:**
- Create: `docs/frontend-institutional-standard.md`
- Modify only if needed: `frontend/src/test/liveRouteReadinessContracts.ts`

**Work:**
1. Write the scoring rubric:
   - Business trust: 0-4
   - First-screen closure: 0-4
   - Visual hierarchy: 0-4
   - Responsive resilience: 0-4
   - Accessibility/keyboard: 0-4
   - Token/design-system alignment: 0-4
   - Performance/runtime cleanliness: 0-4
2. Define pass levels:
   - 24-28: flagship-ready
   - 20-23: releaseable with watch items
   - 16-19: acceptable but not flagship
   - below 16: not releaseable
3. Record required browser measurements:
   - desktop 1440px
   - tablet 768px
   - mobile 390px
   - no horizontal overflow
   - no console errors/warnings
   - no fallback route or permanent loading

**Verification:**
```powershell
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
```

### Gate 1: Harden `/cross-asset` From Proof Point To Flagship

**Files:**
- Modify: `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- Modify: `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.css`
- Modify: `frontend/src/test/CrossAssetPage.test.tsx`
- Modify only if shell contract changes: `frontend/src/layouts/WorkbenchShell.tsx`
- Test only if shell contract changes: `frontend/src/test/WorkbenchShell.test.tsx`

**Work:**
1. Replace fragile route-scoped shell child selectors with a stable route/shell class or data attribute if a narrow shell change is justified.
2. Add browser-smoke or Vitest guard for the shell compression contract.
3. Review touch targets and focus states in first-screen controls.
4. Keep all status/source/fallback evidence visible.
5. Do not retire `temporary-exception` unless MCP contract/lineage evidence is available.

**Verification:**
```powershell
npm run test -- src/test/CrossAssetDriversRoute.test.tsx src/test/CrossAssetPage.test.tsx
npm run test -- src/test/WorkbenchShell.test.tsx src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Browser:
- `/cross-asset` desktop/mobile/tablet
- `/cross-asset-drivers` alias

### Gate 2: Apply The Standard To The Next Three Business-Critical Pages

**Recommended order:**
1. `/ledger-pnl`
2. `/macro-toolkit`
3. `/stock-analysis`

**Why this order:**
- These are high-value analytical routes already touched by existing frontend work.
- They are likely to expose real consistency gaps without forcing backend platform refactor.
- They represent portfolio PnL, macro, and equity/risk surfaces: a good coverage spread.

**Per-page work:**
1. Identify the one primary business question.
2. Trace displayed metrics:
   - API response
   - adapter/transform
   - state/query
   - selector/computed model
   - component/chart/table
3. Rebuild first screen around:
   - trust/status strip
   - primary conclusion
   - top 3-5 decision metrics
   - one drill/action path
4. Normalize to institutional tokens and spacing.
5. Add narrow tests around changed selectors/adapters/formatters.
6. Run browser desktop/mobile verification.

**Per-page verification:**
```powershell
npm run test -- <page-specific-tests>
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

### Gate 3: System-Level Institutional Normalization

**Files:**
- `frontend/src/styles/global.css`
- `frontend/src/styles/workbenchInstitutionalConsole.css`
- `frontend/src/theme/tokens.ts`
- `frontend/src/theme/designSystem.ts`
- page CSS files only where they deviate from standards

**Work:**
1. Inventory one-off colors, spacing, borders, radii, shadows, and typography across live pages.
2. Convert repeated institutional patterns into tokens or existing page-v2 primitives.
3. Lower frontend debt baselines only after cleanup; never raise them without justification.
4. Keep page CSS local when a pattern is truly page-specific.
5. Do not create a new design system layer unless two or more pages immediately reuse it.

**Verification:**
```powershell
npm run test -- src/test/theme.test.ts src/test/StartupPerformanceGuards.test.ts src/test/WorkbenchShell.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

### Gate 4: Accessibility And Runtime Audit

**Files:**
- Page tests under `frontend/src/test/`
- Playwright smoke tests under `frontend/tests/playwright/`
- Page CSS/TSX only where findings are confirmed

**Work:**
1. Check contrast on institutional text, muted labels, tags, status pills, and chart legends.
2. Verify keyboard focus paths for page-level controls.
3. Add accessible names for icon-only or compact controls.
4. Ensure no state is communicated by color alone.
5. Confirm reduced-motion behavior where animations exist.
6. Capture mobile and desktop screenshot evidence for every flagship page.

**Verification:**
```powershell
npm run test:a11y-smoke
npm run lint
npm run typecheck
npm run build
```

### Gate 5: Governance Marker Retirement Review

**Files:**
- `frontend/src/mocks/navigation.ts`
- `frontend/src/test/RouteRegistry.test.tsx`
- `frontend/src/test/LiveRouteReadiness.test.tsx`
- `frontend/src/test/LiveRouteRealPageSmoke.test.tsx`
- Shell/page tests only if banner behavior changes

**Required evidence before retiring any marker:**
- `moss-metric-contracts`: page contracts, definitions, units, golden samples
- `moss-lineage-evidence`: source lineage, fallback/stale/proxy status
- `moss-data-catalog`: available tables, report dates, freshness
- `gitnexus`: route/symbol/call-path impact for shared changes

**Rule:**
If any required evidence server is unavailable, retain the marker and document the blocker.

**Verification:**
```powershell
npm run test -- src/test/RouteRegistry.test.tsx src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run build
```

## Recommended Next Ralph Run

Start with Gate 1 because `/cross-asset` is already warm and has fresh evidence.

Suggested command:

```text
$ralph execute docs/plans/2026-06-05-institutional-frontend-flagship-standard-plan.md Gate 1
```

Expected next result:
- `/cross-asset` remains evidence-first.
- Route shell compression becomes less fragile or gains a clear regression guard.
- The page can be used as the standard template for the next three route closures.

## Do Not Do

- Do not run a broad beautification pass across many pages.
- Do not hide governance evidence to make pages shorter.
- Do not retire `temporary-exception` from visual quality alone.
- Do not modify backend, auth, DB, scheduler/cache, or global SDK wrappers unless a page-specific verified root cause requires it.
- Do not raise debt baselines.

## Final Acceptance

The system reaches the target only when:

1. At least the top critical routes score `24/28` or higher on the institutional scorecard.
2. Every flagship route has browser proof for desktop, tablet, and mobile.
3. Every visible metric has traceable source/date/unit/status semantics.
4. No flagship route has console errors, horizontal overflow, fallback route, or permanent loading state.
5. Temporary-exception markers are either evidence-retired or explicitly retained with current blocker notes.
