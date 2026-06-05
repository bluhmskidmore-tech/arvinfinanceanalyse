# Market Data Page Closure Design Brief

## Purpose

`/market-data` should become the frontend sample for page-level closure on a mixed-source business page. The page should not merely show market tables; it should first tell the user whether the current market read surface is usable, which sections are formal, which sections are analytical, which sections are fallback or stale, and which sections are still source-pending.

The design goal is not visual novelty. This is an internal fixed-income and portfolio-management workbench, so the right tone is compact, institutional, and evidence-first. A user should be able to scan the first screen and know: "Can I rely on this page today, and where do I drill next?"

## Context

Current local evidence shows `/market-data` is a `PAGE-MKT-001` mixed-source page:

- formal fragment: `GET /ui/market-data/rates`
- analytical surfaces: macro latest/catalog, FX analytical, NCD funding proxy, Livermore, macro-bond linkage
- source-pending terminal panels: bond futures, bond trade detail, credit bond trades
- documented gap: `GAP-MKT-DATA`, no full-page formal metric dictionary or capture-ready golden sample

Current tests already protect several important states: no demo rows for missing formal/latest data, source-pending terminal panels, Livermore stale/reserved behavior, NCD as Shibor proxy, macro-bond linkage warnings, and supply-auction calendar loading.

## Design Options

### Option A: Evidence-First Closure

Keep the current page structure and make the first screen unambiguous. The hero answers readiness and basis boundaries. The KPI band remains compact. One visible evidence rail declares formal rates, macro latest, FX analytical, NCD proxy, Livermore, and linkage status. Terminal panels show ready, empty, or source-pending states without demo-like data.

This is the recommended path. It is the smallest change that improves business trust, preserves current tests, and matches the repository rule: page-level closure before broad refactor.

### Option B: Visual Redesign Pass

Recompose the page around a new dashboard layout, new card hierarchy, and wider component extraction. This could improve polish, but it risks touching too much at once and would distract from metric correctness and source boundaries.

This should wait until the page's evidence model is stable.

### Option C: Data Surface Expansion

Prioritize connecting more live endpoints, such as replacing source-pending panels with real bond futures or credit trade data. This may be valuable later, but it requires source lineage and contract evidence that is not available in this session.

This should not be the next frontend optimization step.

## Recommended Design

Use Option A.

The first viewport should answer one primary question:

> Is the market read surface ready, and which parts are formal, analytical, fallback, stale, or source-pending?

Recommended order:

1. `PageDecisionHero`: title, short business question, observation date, data-source mode, refresh action.
2. `DataStatusStrip`: compact readiness and basis line. Do not duplicate KPI-band fields such as linkage report date.
3. Filter tray: observation date, curve family, credit segment, source filter.
4. KPI band: catalog count, stable recovered, fallback count, stable latest date, missing stable count, FX analytical counts, linkage report date.
5. Evidence rail: one always-visible row or panel listing formal rates, macro latest, FX analytical, NCD proxy, Livermore, and linkage status.
6. Main workbench: formal/latest rate and money-market panels first; analytical and source-pending panels clearly marked.

## Component Shape

Keep existing local boundaries:

- `useMarketDataPageData` owns query orchestration and refresh.
- `buildMarketDataPageModel` owns derived display state.
- `MarketDataHeroSection` owns first-screen question, filters, status strip, and KPI band.
- `MarketDataPage` owns page composition and evidence rail placement.
- `MarketDataMacroDepthTabs` owns curve, spread, and linkage tab content.
- terminal components own ready/empty/source-pending rendering for their panels.

If new helpers are needed, keep them under `frontend/src/features/market-data/`. Do not add global primitives unless another page immediately reuses them.

## Data Flow

The intended display chain is:

API envelopes -> `useMarketDataPageData` -> `buildMarketDataPageModel` -> hero/evidence/terminal components -> table/chart/panel output.

The model should expose only derived view facts needed by the page, for example:

- `isFormalBasis`
- `sourcePendingCount`
- `statusBadges`
- evidence strings or evidence items for formal rates, macro latest, FX analytical, NCD proxy, Livermore, and linkage

Avoid recomputing basis, fallback, quality, or source labels repeatedly in JSX.

## State Rules

The page must make these states visible:

- no data: empty state, not demo rows
- error: visible failure with retry where already supported
- fallback: visible fallback mode
- stale: visible stale/vendor stale state
- analytical: not eligible for formal-use wording
- source-pending: no fake numeric market quotes
- proxy: NCD must say Shibor funding proxy, not actual NCD issuance matrix

Do not add unconfirmed `MTR-*`, units, formulas, or golden sample values.

## Test Strategy

Use test-first implementation:

1. `marketDataPageModel.test.ts`: model semantics for formal/analytical basis, source-pending count, evidence items.
2. `MarketDataPage.test.tsx`: first-screen status, evidence rail, source-pending panels, NCD proxy copy, Livermore/linkage analytical warnings.
3. `marketDataTerminalModel.test.ts`: ready/empty/source-pending terminal state rules.
4. Existing component tests for Livermore and NewsAndCalendar remain in scope.
5. Browser smoke after visible layout changes.

Minimum verification:

```bash
cd frontend
npm test -- MarketDataPage marketDataPageModel marketDataTerminalModel marketDataCategoryStore livermoreStrategyModel NewsAndCalendar
npm run debt:audit
npm run lint
npm run typecheck
```

## Non-Goals

- No backend changes.
- No schema, cache, scheduler, auth, or global API wrapper work.
- No changes to `frontend/src/api/client.ts`.
- No broad design-system refactor.
- No activation of hidden `MARKET_DATA_SHOW_*` sections without product confirmation.
- No new formal metric definitions or golden samples.

## Decision

Proceed with Option A: Evidence-First Closure.

The existing implementation plan in `docs/plans/2026-05-26-market-data-page-closure.md` should be treated as the execution plan for this design, after confirming that implementation still respects this design brief and the local `AGENTS.md` constraints.
