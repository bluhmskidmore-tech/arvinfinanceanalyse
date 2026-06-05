# Market Data Page Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Design Brief:** `docs/plans/2026-05-26-market-data-page-closure-design.md`

**Goal:** Make `/market-data` a page-level closure sample: first screen shows whether the market read surface is usable, every displayed block declares basis/status/source boundaries, and no source-pending or analytical surface can be mistaken for formal truth.

**Architecture:** Keep the work page-scoped. Use the existing `MarketDataPage` split (`useMarketDataPageData`, `marketDataPageModel`, `MarketDataHeroSection`, `MarketDataMacroDepthTabs`, terminal table components) and the shared page primitives rather than adding a new layout system. Do not change backend routes, metric definitions, global state architecture, or `frontend/src/api/client.ts`.

**Tech Stack:** React 18, TypeScript, TanStack Query, Ant Design, ECharts, Vitest, Testing Library, Playwright/a11y smoke where visible behavior changes.

---

## Scope

**Page/workflow being fixed:** `/market-data`

**Inspect first:**
- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- `frontend/src/features/market-data/pages/marketDataPageModel.ts`
- `frontend/src/features/market-data/hooks/useMarketDataPageData.ts`
- `frontend/src/features/market-data/pages/MarketDataHeroSection.tsx`
- `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- `frontend/src/features/market-data/components/RateQuoteTable.tsx`
- `frontend/src/features/market-data/components/MoneyMarketTable.tsx`
- `frontend/src/features/market-data/components/BondFuturesTable.tsx`
- `frontend/src/features/market-data/components/BondTradeDetail.tsx`
- `frontend/src/features/market-data/components/CreditBondTradesTable.tsx`
- `frontend/src/features/market-data/components/NcdMatrix.tsx`
- `frontend/src/features/market-data/components/NewsAndCalendar.tsx`
- `frontend/src/test/MarketDataPage.test.tsx`
- `frontend/src/features/market-data/pages/marketDataPageModel.test.ts`
- `frontend/src/features/market-data/lib/marketDataTerminalModel.test.ts`
- `docs/page_contracts.md` section `PAGE-MKT-001`
- `docs/metric_dictionary.md` `GAP-MKT-DATA`

**Will not touch:**
- backend schema, services, schedulers, cache, auth, or global SDK wrappers
- `frontend/src/api/client.ts`
- unconfirmed `MTR-*` definitions or new golden sample values
- product-hidden sections guarded by `MARKET_DATA_SHOW_*` unless a task explicitly says to keep them hidden and test that fact

## Subagent Lane Ownership

Use subagents for bounded lanes, but keep shared write hotspots single-owner. Do not run two implementation agents that both edit `MarketDataPage.tsx`, `MarketDataPage.test.tsx`, `MarketDataPage.css`, or `MarketDataMacroDepthTabs.tsx`.

- `Lane 0: contract/baseline`: read-only only.
- `Lane 1A: terminal status model`: owns `frontend/src/features/market-data/lib/marketDataTerminalModel.ts` and `frontend/src/features/market-data/lib/marketDataTerminalModel.test.ts`; must not edit `MarketDataPage.tsx` or `MarketDataPage.test.tsx`.
- `Lane 1B: page model semantics`: owns `frontend/src/features/market-data/pages/marketDataPageModel.ts` and `frontend/src/features/market-data/pages/marketDataPageModel.test.ts`; must not edit `MarketDataPage.tsx`, `MarketDataHeroSection.tsx`, or `MarketDataPage.test.tsx`.
- `Lane 2: first-screen shell/evidence rail`: single integration owner for `MarketDataPage.tsx`, `MarketDataHeroSection.tsx`, `MarketDataPage.css`, and `MarketDataPage.test.tsx`.
- `Lane 3: analytical surface boundaries`: owns NCD/Livermore-specific component/model files; edits to `MarketDataMacroDepthTabs.tsx` or `MarketDataPage.test.tsx` must wait for the integration owner.
- `Lane 4: query/mount behavior`: owns `useMarketDataPageData.ts`; only edits `MarketDataMacroDepthTabs.tsx` if tests prove the current mount behavior is insufficient.
- `Lane 5: style/browser validation`: runs last; may only change classes/layout and must not change business copy, test ids, model semantics, or query behavior.

Task 5 has an explicit exit condition: if existing `externalDataQueryOptions` and tab unmount behavior satisfy the tests, do not change query behavior. Style work has an explicit exit condition: no test id changes, no business-copy changes, no source/basis semantics changes.

## Current Evidence

- `npm run debt:audit` currently passes with no growth over baseline.
- `style:inventory` shows `/market-data` is not the worst page, but it still has `39` style props and mixed primitive adoption.
- `docs/page_contracts.md` marks `/market-data` as `PAGE-MKT-001`, mixed-source: formal rates fragment plus analytical macro, FX, NCD proxy, Livermore, and macro-bond linkage.
- `docs/metric_dictionary.md` keeps `GAP-MKT-DATA`: no full-page formal metric dictionary / capture-ready golden sample.
- Existing tests already cover many important states: formal/latest terminal data, no demo rows for empty rate/money panels, source-pending terminal panels, Livermore stale/reserved states, NCD Shibor proxy, macro-bond linkage warnings, NewsAndCalendar supply-auction load.

## MCP Evidence Note

The requested project MCP servers were not available in this Codex session: `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` were not exposed by tool discovery. This plan therefore uses local evidence only: `docs/page_contracts.md`, `docs/metric_dictionary.md`, `docs/golden_sample_catalog.md`, existing `/market-data` docs, and current frontend tests. During implementation, retry those MCP checks if the servers become available; do not invent metric definitions, lineage claims, report dates, or golden sample values from this plan alone.

## Contract Gates

- `/market-data` remains a mixed-source page. Only the formal rates fragment may be presented as formal.
- Do not create new `MTR-*` bindings, formulas, units, or sample values.
- Do not add a full-page `/market-data` golden sample.
- Keep KPI-band values such as stable recovered, fallback count, stable latest date, missing stable count, FX analytical counts, and linkage report date as display/status facts, not formal metrics.
- Evidence rail items must preserve per-item basis: formal rates, macro latest, FX analytical, NCD proxy, Livermore, and macro-bond linkage cannot be collapsed into a page-level "formal" claim.
- NCD must remain a Shibor/funding proxy, not an actual NCD tenor-by-rating matrix.
- Source-pending terminal panels must not render demo contracts, demo trades, or pseudo market values.

## Target UX

The first screen should answer:

> Is this market read surface ready, and which parts are formal, analytical, fallback, stale, or source-pending?

Recommended first-screen order:

1. `PageDecisionHero`: title, short business question, observation date, mode, refresh action.
2. `DataStatusStrip`: compact basis/status line only; no duplication with KPI band.
3. Filter tray: date, curve family, credit segment, source.
4. KPI band: catalog count, stable recovered, fallback count, stable latest date, missing stable count, FX analytical counts, linkage report date.
5. One visible evidence rail: formal rates, macro latest, FX analytical, NCD proxy, Livermore, linkage.
6. Main workbench: formal/latest rate and money panels first; analytical or source-pending panels clearly marked.

## Task 1: Lock Page Model Status Semantics

**Files:**
- Modify: `frontend/src/features/market-data/pages/marketDataPageModel.ts`
- Test: `frontend/src/features/market-data/pages/marketDataPageModel.test.ts`

**Step 1: Write failing tests**

Add tests for:
- `formalRatesMeta.basis === "formal"` drives `isFormalBasis=true`.
- analytical formal rates or missing formal rates drives `isFormalBasis=false`.
- every overview metric that represents analytical or mixed-source data keeps a non-formal detail string.
- `sourcePendingCount` counts only terminal sections with status `source-pending`.

**Step 2: Run the targeted model test**

Run from `frontend/`:

```bash
npm test -- marketDataPageModel
```

Expected before implementation: at least one new assertion fails if the current model does not expose enough status detail.

**Step 3: Implement minimal model changes**

Keep changes inside `buildMarketDataPageModel`. Prefer adding small derived fields to the page model rather than recomputing status in JSX.

Suggested output shape if needed:

```ts
statusBadges: {
  readinessVerdict,
  overviewReadinessLabel,
  secondaryLabel,
},
evidenceLines: {
  formalRates,
  macroLatest,
  fxAnalytical,
  ncdProxy,
  livermore,
  linkage,
},
```

Only add fields that the page will immediately render in later tasks.

**Step 4: Verify**

Run:

```bash
npm test -- marketDataPageModel
```

Expected: pass.

## Task 2: Make First-Screen Evidence Unambiguous

**Files:**
- Modify: `frontend/src/features/market-data/pages/MarketDataHeroSection.tsx`
- Modify: `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- Modify only if needed: `frontend/src/features/market-data/pages/MarketDataPage.css`
- Test: `frontend/src/test/MarketDataPage.test.tsx`

**Step 1: Write failing tests**

Add or tighten tests that assert:
- `market-data-data-status-strip` contains basis/readiness/fallback status, but does not duplicate `market-data-linkage-report-date`.
- `market-data-macro-evidence-rail` is visible on the normal page.
- `market-data-macro-evidence-rail` consumes `pageModel.evidenceLines`; do not keep a second inline `metaEvidenceLine(...)` formatting path in `MarketDataPage.tsx`.
- the evidence rail contains `formal rates`, `formal_use_allowed`, `fallback`, and source version for formal rates.
- the evidence rail identifies NCD as proxy and Livermore/linkage as analytical.

**Step 2: Run targeted page test**

Run:

```bash
npm test -- MarketDataPage
```

Expected before implementation: new assertions fail where evidence is missing or too implicit.

**Step 3: Implement minimal UI changes**

Keep `PageDecisionHero`, `DataStatusStrip`, and `KpiBand`. Do not introduce a new hero pattern.

Implementation notes:
- Keep the business question short and operational.
- Keep report date in `reportDateSlot`.
- Move any repeated evidence text from ad hoc blocks into one visible evidence rail.
- Use the item-level model evidence generated in `buildMarketDataPageModel`; preserve each item's basis instead of building a page-level formal summary.
- Do not turn hidden `MARKET_DATA_SHOW_*` sections on.
- Do not create new business claims for unconfirmed metrics.

**Step 4: Verify**

Run:

```bash
npm test -- MarketDataPage
```

Expected: pass.

## Task 3: Normalize Source-Pending Terminal Panels

**Files:**
- Modify: `frontend/src/features/market-data/lib/marketDataTerminalModel.ts`
- Modify: `frontend/src/features/market-data/components/BondFuturesTable.tsx`
- Modify: `frontend/src/features/market-data/components/BondTradeDetail.tsx`
- Modify: `frontend/src/features/market-data/components/CreditBondTradesTable.tsx`
- Modify only if needed: `frontend/src/features/market-data/components/RateQuoteTable.tsx`
- Modify only if needed: `frontend/src/features/market-data/components/MoneyMarketTable.tsx`
- Test: `frontend/src/features/market-data/lib/marketDataTerminalModel.test.ts`
- Test: `frontend/src/test/MarketDataPage.test.tsx`

**Step 1: Write failing tests**

Assert:
- unsupported bond futures, bond trade detail, and credit bond trades render `source-pending`.
- unsupported panels show no numeric demo rows.
- ready rate and money panels show basis, quality, fallback, and source.
- empty rate/money panels show no-data copy.

**Step 2: Run tests**

Run:

```bash
npm test -- marketDataTerminalModel MarketDataPage
```

Expected: fail only on newly required visibility/copy assertions.

**Step 3: Implement minimal normalization**

Use the existing `MarketDataTerminalStatus` model. If copy is duplicated, create a tiny page-local helper or component under `frontend/src/features/market-data/components/`; do not create an app-wide abstraction.

**Step 4: Verify**

Run:

```bash
npm test -- marketDataTerminalModel MarketDataPage
```

Expected: pass.

## Task 4: Tighten Analytical Surface Boundaries

**Files:**
- Modify: `frontend/src/features/market-data/components/NcdMatrix.tsx`
- Modify: `frontend/src/features/market-data/components/LivermoreStrategyPanel.tsx`
- Modify: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- Modify only if needed: `frontend/src/features/market-data/lib/livermoreStrategyModel.ts`
- Test: `frontend/src/test/MarketDataPage.test.tsx`
- Test: `frontend/src/features/market-data/lib/livermoreStrategyModel.test.ts`

**Step 1: Write failing tests**

Assert:
- NCD panel says it is a Shibor funding proxy and not an actual NCD issuance matrix.
- Livermore stale/fallback/reserved states remain visible.
- macro-bond linkage says analytical estimate and non-formal where relevant.
- switching to spreads tab still shows `market-data-spreads-live-meta`.

**Step 2: Run tests**

Run:

```bash
npm test -- MarketDataPage livermoreStrategyModel
```

Expected: fail only where state copy or evidence is not visible enough.

**Step 3: Implement minimal copy/status changes**

Do not change calculations. Do not convert analytical results into formal metrics. Prefer rendering backend `warnings`, `unsupported_outputs`, `quality_flag`, and `fallback_mode` already present in payloads.

**Step 4: Verify**

Run:

```bash
npm test -- MarketDataPage livermoreStrategyModel
```

Expected: pass.

## Task 5: Query Behavior And Performance Guard

**Files:**
- Modify: `frontend/src/features/market-data/hooks/useMarketDataPageData.ts`
- Modify only if needed: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- Test: `frontend/src/test/MarketDataPage.test.tsx`

**Step 1: Write failing tests**

Assert:
- stable/date-slice formal rates do not enter fallback polling.
- fallback/latest sections keep fallback polling policy.
- hidden macro depth tab content is not kept mounted.

**Step 2: Run tests**

Run:

```bash
npm test -- MarketDataPage
```

Expected: pass if current `externalDataQueryOptions` and `destroyOnHidden` behavior is already correct; otherwise fail narrowly.

**Step 3: Implement only if tests expose a gap**

If changes are needed, keep them inside:
- `externalDataQueryOptions(...)` calls in `useMarketDataPageData`
- `Tabs` props in `MarketDataMacroDepthTabs`

Do not tune global React Query defaults.

**Step 4: Verify**

Run:

```bash
npm test -- MarketDataPage
```

Expected: pass.

## Task 6: Reduce Page-Local Style Debt Without Behavior Change

**Files:**
- Modify: `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- Modify: `frontend/src/features/market-data/pages/MarketDataPage.css`
- Modify only if needed: `frontend/src/features/market-data/pages/MarketDataHeroSection.tsx`
- Modify only if needed: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`

**Step 1: Identify style debt**

Run:

```bash
npm run style:inventory
```

Record the `/market-data` style prop and hex counts before editing.

**Step 2: Move repeated presentational styles**

Move repeated layout styles into existing CSS classes. Keep ECharts `style={{ height, width }}` if local and necessary.

Avoid:
- new global tokens
- new design system components
- broad class renames outside market-data

**Step 3: Verify no behavior change**

Run:

```bash
npm test -- MarketDataPage
npm run debt:audit
```

Expected: tests pass and debt audit reports no growth.

## Task 7: Browser And Accessibility Smoke

**Files:**
- No source edits unless the browser check finds a visible issue.

**Step 1: Start local frontend**

Run from `frontend/`:

```bash
npm run dev
```

Use the shown local URL, normally `http://localhost:5173`.

**Step 2: Open `/market-data`**

Use the in-app browser or Playwright against:

```text
http://localhost:5173/market-data
```

Check:
- first screen shows title, data status, filters, KPI band, and evidence rail without overlap.
- no horizontal overflow at desktop width.
- terminal source-pending panels are visible and do not look like real market quotes.
- NCD proxy and Livermore analytical boundaries are visible.

**Step 3: Run available smoke test**

Run:

```bash
npm run test:a11y-smoke
```

If the full smoke suite is too broad or environment-gated, record the blocker and run a focused Playwright/manual browser check instead.

## Task 8: Final Verification

Run from `frontend/`:

```bash
npm test -- MarketDataPage marketDataPageModel marketDataTerminalModel marketDataCategoryStore livermoreStrategyModel NewsAndCalendar
npm run debt:audit
npm run lint
npm run typecheck
```

If the change affects visible layout and the dev server is available, also complete the browser check from Task 7.

Expected:
- targeted tests pass.
- debt audit passes with no growth.
- lint and typecheck pass, or failures are documented as pre-existing with evidence.
- browser check confirms no obvious overlap or hidden state evidence.

## Acceptance Criteria

- `/market-data` first screen answers readiness and basis boundaries before deep analysis.
- Formal rates are visibly separated from analytical macro/FX/NCD/Livermore/linkage surfaces.
- Source-pending panels show no demo-like numeric data.
- NCD is clearly labeled as Shibor funding proxy, not actual NCD issuance matrix.
- Livermore blocked/stale/fallback states remain visible.
- `GAP-MKT-DATA` remains respected: no new unapproved `MTR-*`, formula, unit, or golden sample assertion.
- `frontend/src/api/client.ts` is unchanged.
- Relevant tests and `npm run debt:audit` pass.

## Reporting Template

After implementation, report:

- Root cause: mixed-source market page had status evidence spread across sections, making basis/fallback/source-pending boundaries too easy to miss.
- Changed files.
- Validation commands and results.
- Remaining risks: `GAP-MKT-DATA`, no full-page golden sample, any unavailable MCP/source evidence, and any skipped browser/a11y checks.
