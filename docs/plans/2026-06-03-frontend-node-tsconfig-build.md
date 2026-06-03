# Frontend Node Tsconfig Build Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore trustworthy frontend build/typecheck coverage for the current Macro Toolkit frontend branch by fixing the node tsconfig module-resolution gap and the market-data React Query type cascade.

**Architecture:** Keep the work inside the existing frontend boundaries. Do not change business metric definitions, API payload semantics, backend routes, or shared infrastructure; only align TypeScript configuration and local type surfaces so existing behavior can be checked correctly.

**Tech Stack:** Vite, React, TypeScript project references, TanStack React Query v5, Vitest, ESLint.

---

## Scope

Worktree:
- `C:\Users\arvin\.config\superpowers\worktrees\MOSS-V3\codex\frontend-node-tsconfig-build`

Branch:
- `codex/frontend-node-tsconfig-build`

Fixing:
- `frontend/tsconfig.node.json` no longer resolves Vite/plugin types under the current TypeScript settings.
- `frontend/src/app/externalDataRefreshPolicy.ts` pins React Query's `refetchInterval` callback to `Error` and `readonly unknown[]`, which breaks concrete `useQuery` inference.
- `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx` assumes `UseQueryResult<..., Error>` even though upstream query errors infer as `unknown`.
- `frontend/src/features/market-data/pages/marketDataPageModel.ts` uses `{}` as a fallback for `MacroBondLinkagePayload`, which widens away known optional fields under project-reference checking.

Not touching:
- Main worktree `F:\MOSS-V3`.
- Backend code, database schema, auth, scheduler, cache base, global SDK wrappers, or shared app architecture.
- Existing unrelated app-wide TypeScript debt except to record what remains after this slice.
- Business metric formulas, units, dates, or official finance calculations.

## Current Evidence

- `npm run typecheck` currently runs root `tsc --noEmit` and does not meaningfully check referenced frontend app/node projects.
- `npx tsc -b --pretty false` is the stricter command that revealed the real build gaps.
- `frontend/tsconfig.node.json` has already been changed from `moduleResolution: "Node"` to `"Bundler"` in this branch.
- `frontend/src/app/externalDataRefreshPolicy.ts` has an in-progress edit that changes query error typing from `Error` to `unknown`, but it still needs a full verification pass.
- Temporary file `frontend/.tsc-build-errors.log` exists and must not be committed.

## Task 1: Verify The Current Failure Shape

**Files:**
- Inspect: `frontend/src/app/externalDataRefreshPolicy.ts`
- Inspect: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- Inspect: `frontend/src/features/market-data/pages/marketDataPageModel.ts`
- Inspect: `frontend/.tsc-build-errors.log`

**Step 1: Run project-reference typecheck**

Run from `frontend/`:

```powershell
npx tsc -b --pretty false
```

Expected:
- No `vite` or `@vitejs/plugin-react` module-resolution errors.
- If `externalDataRefreshPolicy.ts` still fails, it should be around React Query generic compatibility.
- Remaining market-data errors should be limited to query error typing and `macroBondLinkage` fallback typing before later unrelated app debt appears.

**Step 2: Remove temporary build log**

Run from the worktree root:

```powershell
Remove-Item -LiteralPath frontend\.tsc-build-errors.log -ErrorAction SilentlyContinue
```

Expected:
- `git status --short` does not show `.tsc-build-errors.log`.

## Task 2: Lock React Query Refresh Policy Typing

**Files:**
- Modify: `frontend/src/app/externalDataRefreshPolicy.ts`
- Test: `frontend/src/app/externalDataRefreshPolicy.test.ts`

**Step 1: Keep refresh-policy behavior unchanged**

Run from `frontend/`:

```powershell
npm run test -- externalDataRefreshPolicy
```

Expected:
- Existing 7 tests pass.
- This proves stale, unavailable, section-level freshness, backoff, and non-cancelling refetch behavior stayed intact.

**Step 2: Make `refetchInterval` depend only on the query state it reads**

Use this shape in `externalDataRefreshPolicy.ts`:

```ts
import type { RefetchOptions } from "@tanstack/react-query";

type ExternalDataRefreshQuery = {
  state: {
    data: unknown;
    fetchFailureCount: number;
  };
};

export function externalDataRefetchInterval(
  query: ExternalDataRefreshQuery,
  sectionSignal?: ExternalRefreshSignal | null,
): number | false {
  // existing body unchanged
}

export function externalDataQueryOptions(sectionSignal?: ExternalRefreshSignal | null) {
  // existing stableDateSlice logic unchanged
  return {
    staleTime: stableDateSlice
      ? EXTERNAL_REFRESH_INTERVALS_MS.stableStaleTime
      : EXTERNAL_REFRESH_INTERVALS_MS.defaultStaleTime,
    refetchInterval: (query: ExternalDataRefreshQuery) =>
      externalDataRefetchInterval(query, sectionSignal),
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  };
}

function applyFailureBackoff(
  baseIntervalMs: number,
  query: ExternalDataRefreshQuery,
) {
  // existing body unchanged
}
```

**Step 3: Re-run refresh-policy tests**

Run from `frontend/`:

```powershell
npm run test -- externalDataRefreshPolicy
```

Expected:
- PASS.

## Task 3: Loosen Market Macro Tabs Query Error Type

**Files:**
- Modify: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`

**Step 1: Confirm component does not depend on `Error` methods**

Search:

```powershell
rg -n "latestQuery\.error|macroBondLinkageQuery\.error|UseQueryResult<ApiEnvelope" frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx
```

Expected:
- The component uses loading/error booleans, data, and refetch, but does not read `error.message`.

**Step 2: Change prop error types to `unknown`**

Replace:

```ts
latestQuery: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>, Error>;
macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, Error>;
```

With:

```ts
latestQuery: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>, unknown>;
macroBondLinkageQuery: UseQueryResult<ApiEnvelope<MacroBondLinkagePayload>, unknown>;
```

Expected:
- No behavior change; this only matches upstream React Query v5 inference.

## Task 4: Type The Macro Bond Linkage Empty State Explicitly

**Files:**
- Modify: `frontend/src/features/market-data/pages/marketDataPageModel.ts`
- Test: `frontend/src/features/market-data/pages/marketDataPageModel.test.ts`

**Step 1: Confirm empty-state expectations**

Run from `frontend/`:

```powershell
npm run test -- marketDataPageModel
```

Expected:
- Existing tests pass before or after the type-only change.
- Empty state should still expose no invented business values.

**Step 2: Replace `{}` fallback with a typed partial**

Use:

```ts
const macroBondLinkage: Partial<MacroBondLinkagePayload> =
  input.macroBondLinkageEnvelope?.result ?? {};
```

Expected:
- `top_correlations`, `warnings`, and `portfolio_impact` remain optional and are accessed through existing nullish fallbacks.
- Runtime output remains unchanged.

**Step 3: Re-run page-model tests**

Run from `frontend/`:

```powershell
npm run test -- marketDataPageModel
```

Expected:
- PASS.

## Task 5: Verify The Slice And Record Remaining Debt

**Files:**
- Verify: `frontend/tsconfig.node.json`
- Verify: `frontend/src/app/externalDataRefreshPolicy.ts`
- Verify: `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- Verify: `frontend/src/features/market-data/pages/marketDataPageModel.ts`

**Step 1: Run focused tests**

Run from `frontend/`:

```powershell
npm run test -- externalDataRefreshPolicy marketDataPageModel
```

Expected:
- PASS.

**Step 2: Run broader market-data tests if focused tests pass**

Run from `frontend/`:

```powershell
npm run test -- MarketDataPage NewsAndCalendar
```

Expected:
- PASS, or fail only for pre-existing fixture drift unrelated to the changed type surfaces. If it fails, capture the first failing assertion and decide whether it is inside this slice.

**Step 3: Run project-reference typecheck**

Run from `frontend/`:

```powershell
npx tsc -b --pretty false
```

Expected:
- No `tsconfig.node.json` Vite/plugin errors.
- No `externalDataRefreshPolicy.ts` generic mismatch.
- No market-data React Query `unknown` cascade from `useMarketDataPageData.ts`, `NewsAndCalendar.tsx`, or `DashboardNewsDigestSection.tsx`.
- Remaining failures, if any, should be unrelated app debt such as mock fixture drift, missing API client methods, PnL type imports, RiskTensor fields, or stale dashboard props.

**Step 4: Run lint and whitespace check**

Run from `frontend/`:

```powershell
npm run lint
```

Run from worktree root:

```powershell
git diff --check
```

Expected:
- PASS.

**Step 5: Run debt audit only if the final edit touches page/model paths**

Run from `frontend/`:

```powershell
npm run debt:audit
```

Expected:
- PASS; no new frontend debt baseline growth.

## Task 6: Commit And Push The Completed Slice

**Files:**
- Stage only intentional files:
  - `frontend/tsconfig.node.json`
  - `frontend/src/app/externalDataRefreshPolicy.ts`
  - `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
  - `frontend/src/features/market-data/pages/marketDataPageModel.ts`

**Step 1: Inspect final diff**

Run from worktree root:

```powershell
git status --short
git diff -- frontend/tsconfig.node.json frontend/src/app/externalDataRefreshPolicy.ts frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx frontend/src/features/market-data/pages/marketDataPageModel.ts
```

Expected:
- No `.tsc-build-errors.log`.
- No unrelated files.
- Diffs are type/config-only and behavior-preserving.

**Step 2: Commit**

Run from worktree root:

```powershell
git add frontend/tsconfig.node.json frontend/src/app/externalDataRefreshPolicy.ts frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx frontend/src/features/market-data/pages/marketDataPageModel.ts
git commit -m "Fix frontend build type coverage"
```

Expected:
- Commit created on `codex/frontend-node-tsconfig-build`.

**Step 3: Push**

Run from worktree root:

```powershell
git push
```

Expected:
- Branch pushed.

PR compare link:
- `https://github.com/bluhmskidmore-tech/arvinfinanceanalyse/compare/codex/macro-toolkit-shadow-frontend...codex/frontend-node-tsconfig-build?expand=1`

## Completion Report Template

After execution, report in Chinese:

- Root cause: root `typecheck` was weak because project references were not built; node tsconfig module resolution and React Query generic pinning caused the first actionable build failures.
- Changed files: list exact files.
- Verification: list each command and PASS/FAIL.
- Remaining risk: app-wide `npx tsc -b` may still fail on unrelated legacy type debt; list first 5 groups if present.
- Next round: choose the largest remaining error cluster from `npx tsc -b --pretty false` and fix it in a separate, small branch/slice.
