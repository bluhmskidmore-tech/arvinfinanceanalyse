# Frontend Strict Build Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore `frontend` project-reference typecheck coverage by closing the current StockAnalysis, Dashboard, and test-fixture contract drift reported by `npx tsc -b --pretty false`.

**Architecture:** Keep fixes inside existing frontend page, domain-client, component, and test-fixture boundaries. Do not change business metric definitions, API semantics, backend services, database schema, auth, scheduler, cache base, or shared application architecture unless a frontend call cannot work without a missing read-only route and that route is already backed by an existing service.

**Tech Stack:** React, TypeScript project references, Vite, TanStack React Query, Vitest, existing frontend API client composition.

---

## Current Scope

Worktree:
- `C:\Users\arvin\.config\superpowers\worktrees\MOSS-V3\codex\frontend-node-tsconfig-build`

Branch:
- `codex/frontend-node-tsconfig-build`

Current strict command:

```powershell
cd frontend
npx tsc -b --pretty false
```

Current remaining error groups:
- `src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- `src/features/workbench/pages/DashboardPage.tsx`
- `src/test/BalanceMovementAnalysisPage.test.tsx`
- `src/test/BondAnalyticsInstitutionalCockpit.test.tsx`
- `src/test/BondDashboardPage.test.tsx`
- `src/test/StockAnalysisPage.test.tsx`

Not touching:
- Main worktree `F:\MOSS-V3`.
- Database schema, auth, scheduler, cache base, global SDK wrappers, or shared app architecture.
- Metric formulas, units, dates, or governed source lineage.
- Unrelated page styling or page-level refactors.
- `frontend/src/api/client.ts` for new endpoint implementations.

## Current Evidence

- `npx tsc -b --pretty false` no longer reports Vite/plugin module-resolution errors.
- React Query refresh-policy, market-data macro model, Livermore strategy model, RiskTensor, and PnL type clusters have been fixed in earlier slices.
- StockAnalysis still calls three Livermore client methods that exist in test doubles but are missing from `MarketDataClientMethods` / real mock domain client wiring:
  - `getLivermoreStrategyOptimization`
  - `getLivermoreCycleProxyBacktest`
  - `getLivermoreCandidateHistoryPortfolioBacktest`
- Frontend contracts already define the payload types:
  - `LivermoreStrategyOptimizationPayload`
  - `LivermoreCycleProxyBacktestPayload`
  - `LivermoreCandidateHistoryPortfolioBacktestPayload`
  - `LivermoreStrategyOptimizationSlice`
- Backend service functions exist in `backend/app/services/livermore_candidate_history_service.py`.
- Backend route file currently exposes `/ui/market-data/livermore/candidate-history` and `/ui/market-data/livermore/strategy-score`; routes for the three advanced backtest/optimization calls must be verified before claiming runtime completeness.

## Task 1: Close StockAnalysis Livermore Client Contract

**Files:**
- Modify: `frontend/src/api/marketDataClient.ts`
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Add missing Livermore payload imports**

In `frontend/src/api/marketDataClient.ts`, import:

```ts
LivermoreCandidateHistoryPortfolioBacktestPayload,
LivermoreCycleProxyBacktestPayload,
LivermoreStrategyOptimizationPayload,
```

Expected:
- No new imports from `frontend/src/api/client.ts`.
- No dependency additions.

**Step 2: Extend `MarketDataClientMethods`**

Add method signatures next to `getLivermoreStrategyScore`:

```ts
getLivermoreStrategyOptimization: (options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
  currentMarketState?: string;
  minSample?: number;
  primaryHorizon?: "return_1d" | "return_5d" | "return_20d";
}) => Promise<ApiEnvelope<LivermoreStrategyOptimizationPayload>>;
getLivermoreCycleProxyBacktest: (options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
}) => Promise<ApiEnvelope<LivermoreCycleProxyBacktestPayload>>;
getLivermoreCandidateHistoryPortfolioBacktest: (options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
}) => Promise<ApiEnvelope<LivermoreCandidateHistoryPortfolioBacktestPayload>>;
```

Expected:
- `StockAnalysisPage.test.tsx` object-literal client methods become valid against `ApiClient`.

**Step 3: Reuse query builders conservatively**

Use the existing strategy-score query shape for strategy optimization:

```ts
buildStrategyScoreQuery(options)
```

Create or reuse a snapshot-window query helper for cycle proxy and portfolio backtest:

```ts
function buildSnapshotWindowQuery(options?: {
  snapshotFrom?: string;
  snapshotTo?: string;
}) {
  const params = new URLSearchParams();
  const sf = options?.snapshotFrom?.trim();
  const st = options?.snapshotTo?.trim();
  if (sf) params.set("snapshot_from", sf);
  if (st) params.set("snapshot_to", st);
  const query = params.toString();
  return query ? `?${query}` : "";
}
```

Expected:
- Existing `snapshotFrom` / `snapshotTo` camelCase frontend options map to backend snake_case query names.
- No business defaults are invented in the query layer.

**Step 4: Add mock implementations**

In `createMockMarketDataClient()`, add minimal payloads that satisfy contracts and explicitly signal proxy/unsupported/pending status where no real evidence is present.

Use empty collections and warning-quality envelopes rather than invented performance figures:

```ts
buildMockApiEnvelope("market_data.livermore.strategy_optimization", {
  as_of_date: options?.snapshotTo ?? null,
  snapshot_from: options?.snapshotFrom ?? null,
  snapshot_to: options?.snapshotTo ?? null,
  primary_horizon: options?.primaryHorizon ?? "return_5d",
  min_sample: options?.minSample ?? 20,
  current_market_state: options?.currentMarketState ?? null,
  backtest_window_summary: null,
  strategy_summaries: [],
  slices: [],
  recommendations: [],
  pending_summary: {
    primary_horizon: options?.primaryHorizon ?? "return_5d",
    pending_rows: 0,
    pending_dates: [],
    latest_pending_date: null,
    message: "Mock strategy optimization has no evidence rows.",
  },
  sample_maturity: null,
})
```

Expected:
- Mock mode renders empty/pending states instead of fake metric conclusions.
- Existing StockAnalysis tests remain able to override richer payloads.

**Step 5: Add real domain-client methods**

Add real request methods in `createMarketDataClient()` using domain client, not `client.ts`:

```ts
getLivermoreStrategyOptimization: (options) =>
  requestJson<LivermoreStrategyOptimizationPayload>(
    fetchImpl,
    baseUrl,
    `/ui/market-data/livermore/strategy-optimization${buildStrategyScoreQuery(options)}`,
  ),
getLivermoreCycleProxyBacktest: (options) =>
  requestJson<LivermoreCycleProxyBacktestPayload>(
    fetchImpl,
    baseUrl,
    `/ui/market-data/livermore/cycle-proxy-backtest${buildSnapshotWindowQuery(options)}`,
  ),
getLivermoreCandidateHistoryPortfolioBacktest: (options) =>
  requestJson<LivermoreCandidateHistoryPortfolioBacktestPayload>(
    fetchImpl,
    baseUrl,
    `/ui/market-data/livermore/candidate-history-portfolio-backtest${buildSnapshotWindowQuery(options)}`,
  ),
```

Expected:
- Typecheck exposes the methods through composed `ApiClient`.
- If backend routes are absent, record runtime residual risk instead of claiming browser-complete support.

**Step 6: Fix StockAnalysis tuple inference**

In `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`, import or use the existing `LivermoreStrategyOptimizationSlice` type and type the mapped rows:

```ts
const strategyOptimizationSliceRows: Array<[string, LivermoreStrategyOptimizationSlice | null]> = [
  ["最强", strategyOptimizationSlices.strongest],
  ["最弱", strategyOptimizationSlices.weakest],
];
```

Then render `strategyOptimizationSliceRows.map(...)`.

Expected:
- `slice` narrows to `LivermoreStrategyOptimizationSlice | null`, not `string | LivermoreStrategyOptimizationSlice`.

**Step 7: Verify StockAnalysis slice**

Run from `frontend/`:

```powershell
npm run test -- StockAnalysisPage
npx tsc -b --pretty false
```

Expected:
- StockAnalysis method and tuple errors disappear.
- Remaining errors, if any, are limited to Dashboard/test fixture groups.

## Task 2: Close Dashboard Component Drift

**Files:**
- Modify: `frontend/src/features/workbench/pages/DashboardPage.tsx`
- Modify only if needed: `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
- Test: `frontend/src/features/workbench/dashboard/dashboardCockpitModel.test.ts`

**Step 1: Remove stale `omitHeader` usage**

In `DashboardPage.tsx`, remove the prop:

```tsx
omitHeader
```

Expected:
- `DashboardCockpitMetricRailProps` remains unchanged unless there is a real product requirement to support hidden headers.
- No layout refactor.

**Step 2: Restore or replace the missing account table export**

Prefer restoring a small `DashboardCockpitAccountTable` in `DashboardCockpitSections.tsx` if the dashboard still intentionally renders `dashboardCockpit.accountRows`.

Use the existing `DashboardCockpitAccountRow` model fields:

```ts
import type { DashboardCockpitAccountRow } from "./dashboardCockpitModel";

type DashboardCockpitAccountTableProps = {
  rows: readonly DashboardCockpitAccountRow[];
};
```

Render an existing-style cockpit card with columns for:
- account name / segment
- exposure / weight
- duration / ytm
- daily change / risk
- status/source/action

Expected:
- No new model logic.
- Empty rows surface a compact no-data state.
- Existing `dashboardCockpitModel.test.ts` remains model-only and should not need semantic changes.

**Step 3: Verify Dashboard slice**

Run from `frontend/`:

```powershell
npm run test -- dashboardCockpitModel
npx tsc -b --pretty false
```

Expected:
- Dashboard export/prop errors disappear.
- Remaining errors, if any, are limited to test fixture contract drift.

## Task 3: Close Test Fixture Contract Drift

**Files:**
- Modify: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`
- Modify: `frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx`
- Modify: `frontend/src/test/BondDashboardPage.test.tsx`

**Step 1: Fix BalanceMovement Blob tuple typing**

At the failing Blob access, avoid indexing an empty tuple type.

Use a typed mock call extraction:

```ts
const blob = vi.mocked(URL.createObjectURL).mock.calls.at(-1)?.[0];
expect(blob).toBeInstanceOf(Blob);
```

If TypeScript still cannot infer after the assertion:

```ts
const blob = vi.mocked(URL.createObjectURL).mock.calls.at(-1)?.[0] as Blob | undefined;
expect(blob).toBeInstanceOf(Blob);
```

Expected:
- No `undefined as Blob` conversion.
- Test intent remains "export creates a Blob".

**Step 2: Loosen BondAnalytics top holdings mock parameter**

Change the mock signature from:

```ts
(reportDate: string, limit: number) => ...
```

to:

```ts
(reportDate: string, limit?: number) => ...
```

Expected:
- Mock conforms to `getBondAnalyticsTopHoldings(reportDate, topN?)`.
- No production client changes.

**Step 3: Add `duration_source` to BondDashboard fixture items**

In `BondDashboardPage.test.tsx`, add the required field to each `BondBusinessTypeMetricItem` fixture:

```ts
duration_source: "weighted_avg_duration",
```

If contract expects a narrower union, use the existing value from nearby production mocks or contract examples.

Expected:
- Fixture reflects the current contract.
- No display assertion changes unless the test already checks duration source text.

**Step 4: Verify fixture slice**

Run from `frontend/`:

```powershell
npm run test -- BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage
npx tsc -b --pretty false
```

Expected:
- Test fixture type errors disappear.
- Strict build reaches zero errors or exposes the next real cluster.

## Task 4: Full Frontend Verification

**Files:**
- Verify all touched files.

**Step 1: Run targeted tests for all touched slices**

Run from `frontend/`:

```powershell
npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage
```

Expected:
- PASS, or fail only with a clear pre-existing assertion unrelated to type-contract closure. Any failure must be investigated before claiming completion.

**Step 2: Run strict project-reference typecheck**

Run from `frontend/`:

```powershell
npx tsc -b --pretty false
```

Expected:
- PASS with zero TypeScript errors.

**Step 3: Run frontend debt audit**

Run from `frontend/`:

```powershell
npm run debt:audit
```

Expected:
- PASS with no baseline growth.
- If baseline growth appears, inspect whether the change violated page/API/mock debt guardrails.

**Step 4: Run lint if strict build passes**

Run from `frontend/`:

```powershell
npm run lint
```

Expected:
- PASS, or report exact unrelated pre-existing lint failures.

**Step 5: Check diff hygiene**

Run from worktree root:

```powershell
git diff --check
git status --short
```

Expected:
- No whitespace errors.
- No temporary `.tsc-build-errors.log`.
- Changed files are limited to the planned frontend files and plan docs, unless a missing backend route is proven necessary and implemented as a small read-only route.

## Completion Report Requirements

After execution, report:
- Root cause for each fixed cluster.
- Changed files.
- Validation commands and results.
- Any residual runtime risk, especially whether the three advanced Livermore backend routes exist.
- Any remaining strict-build errors if new clusters appear after the current set is cleared.

## Execution Update

The frontend strict-build closure was executed in the isolated worktree. After the initial frontend client/type fixes, the three advanced Livermore frontend URLs were found to need matching backend read-only routes. Those routes were added because the service envelope functions already existed and are DuckDB SELECT/read-only paths:

- `/ui/market-data/livermore/strategy-optimization`
- `/ui/market-data/livermore/cycle-proxy-backtest`
- `/ui/market-data/livermore/candidate-history-portfolio-backtest`

The original runtime residual risk about missing backend routes is now closed by:

- `backend/app/api/routes/market_data_livermore.py`
- `tests/test_market_data_livermore_candidate_history.py`
- `frontend/src/api/marketDataClient.ts`

The route contract was also aligned with the existing service/frontend payload contract so
`primary_horizon=return_10d` is accepted for strategy score and strategy optimization, while
unsupported horizons such as `return_30d` still return 422.

Verification completed after the route closure:

```powershell
cd frontend
npm run build
npm run lint
npm run debt:audit
npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage
npx tsc -b --pretty false
cd ..
python -m pytest tests/test_market_data_livermore_candidate_history.py -q
python -m pytest tests/test_market_data_livermore_api.py -q
git diff --check
```

Observed results:

- Frontend production build completed.
- Frontend lint passed.
- Frontend debt audit passed with no baseline growth.
- Targeted frontend tests passed: 6 files / 95 tests.
- Strict frontend project-reference build passed.
- Candidate-history backend tests passed: 43 tests.
- Adjacent Livermore API backend tests passed: 32 tests.
- Diff whitespace check passed.
