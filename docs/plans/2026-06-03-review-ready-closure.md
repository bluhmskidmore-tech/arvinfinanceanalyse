# Review Ready Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current frontend strict-build and Livermore route closure work into a review-ready change set with clear evidence, bounded risk, and no unrelated scope expansion.

**Architecture:** Keep this as an audit and packaging pass over the existing branch. Do not change metric definitions, page behavior, database schema, auth, cache, scheduler, shared SDK wrappers, or application architecture unless a verification command exposes a regression directly caused by this branch.

**Tech Stack:** Git worktree, React, TypeScript project references, Vite, Vitest, ESLint, pytest, existing backend FastAPI route tests.

---

## Scope

Worktree:
- `C:\Users\arvin\.config\superpowers\worktrees\MOSS-V3\codex\frontend-node-tsconfig-build`

Branch:
- `codex/frontend-node-tsconfig-build`

Fixing:
- Review readiness for the current uncommitted branch changes.
- Verification evidence completeness.
- Root-cause and risk summary for handoff, commit, or PR.

Not touching:
- Main worktree `F:\MOSS-V3`.
- New business metric definitions, units, dates, source lineage, or report logic.
- Database schema, auth, queue, scheduler, cache base, global SDK wrappers, or shared infrastructure layers.
- New frontend pages, visual redesign, or broad refactors.
- Commits or pushes unless the user explicitly asks.

## Current Evidence

Already observed passing checks:

```powershell
cd frontend
npx tsc -b --pretty false
npm run lint
npm run debt:audit
npm run build
npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage
cd ..
python -m pytest tests/test_market_data_livermore_candidate_history.py -q
python -m pytest tests/test_market_data_livermore_api.py -q
python -m pytest tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q
python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q
git diff --check
```

Observed results:
- Frontend strict build passed.
- Frontend lint passed.
- Frontend debt audit passed with no baseline growth.
- Frontend production build passed.
- Targeted frontend tests passed: 6 files / 95 tests.
- Livermore T+10 frontend contract test passed after a red/green typecheck cycle.
- Livermore candidate-history route tests passed: 43 tests.
- Adjacent Livermore API tests passed: 32 tests.
- Livermore adjacent backend tests passed: 22 tests.
- PnL/Risk backend API contract tests passed: 82 tests.
- Diff whitespace check passed.

## Task 1: Reconfirm Branch State

**Files:**
- Inspect: all changed files from `git status --short --branch`

**Step 1: Check status**

Run from the worktree root:

```powershell
git status --short --branch
```

Expected:
- Branch is `codex/frontend-node-tsconfig-build`.
- Changed files are limited to the current strict-build, Livermore route, PnL/Risk typing, dashboard, tests, and plan files.
- `frontend/dist/`, build info, caches, and data outputs remain ignored/untracked and are not staged.

**Step 2: Check diff hygiene**

Run from the worktree root:

```powershell
git diff --check
```

Expected:
- No whitespace errors.

## Task 2: Build The Review Summary

**Files:**
- Inspect: `backend/app/api/routes/market_data_livermore.py`
- Inspect: `frontend/src/api/marketDataClient.ts`
- Inspect: `frontend/src/api/client.ts`
- Inspect: `frontend/src/api/pnlClient.ts`
- Inspect: `frontend/src/app/externalDataRefreshPolicy.ts`
- Inspect: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Inspect: `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
- Inspect: `tests/test_market_data_livermore_candidate_history.py`

**Step 1: Group the root causes**

Create a concise summary with these clusters:
- TypeScript project-reference build was stricter than the existing root typecheck and exposed stale frontend contracts.
- React Query v5 inference required less-specific query error and refresh callback typing.
- StockAnalysis expected Livermore advanced endpoints that were represented in frontend tests/types but absent from the domain client and backend read-only routes.
- Livermore `return_10d` was accepted by the backend service/route contract but still rejected by frontend StrategyScore client and payload types.
- Dashboard and fixture tests drifted from current component/model contracts.
- PnL/Risk type surfaces had small contract gaps exposed by stricter checking.

**Step 2: Identify risk boundaries**

Record:
- No metric formulas were intentionally changed.
- Livermore route additions are read-only and call existing service envelope functions.
- `primary_horizon=return_10d` is now accepted where service/frontend contracts already support it.
- `return_30d` remains invalid and covered by route tests.
- T+10 frontend mock score data uses empty/null maturity stats, avoiding invented business conclusions.
- No database schema, auth, cache, scheduler, or shared architecture changes were made.

Expected:
- The summary explains why the change fixes build/runtime closure without pretending to revalidate business definitions.

## Task 3: Re-run Only If Evidence Is Stale

**Files:**
- Verify changed frontend and backend slices only.

**Step 1: Frontend strict closure**

Run from `frontend/` if code changed after the last verification:

```powershell
npx tsc -b --pretty false
npm run lint
npm run debt:audit
npm run build
npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage
```

Expected:
- All commands pass.

**Step 2: Backend route and adjacent contract checks**

Run from the worktree root if backend route code changed after the last verification:

```powershell
python -m pytest tests/test_market_data_livermore_candidate_history.py tests/test_market_data_livermore_api.py -q
python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q
```

Expected:
- All selected tests pass.

## Task 4: Prepare Commit Or PR Text Without Committing

**Files:**
- Create only if useful: `docs/plans/2026-06-03-review-ready-closure.md`

**Step 1: Draft commit title**

Use:

```text
fix: close frontend strict build and livermore route contracts
```

**Step 2: Draft review summary**

Include:
- Frontend project-reference build now passes.
- React Query and domain-client type contracts are aligned.
- Livermore advanced frontend calls now have backend read-only routes and tests.
- Dashboard, PnL, RiskTensor, and fixture drift are aligned with current contracts.

**Step 3: Draft test evidence**

Include all observed passing commands from the current evidence section.

Expected:
- Text is ready for commit/PR use.
- No commit is created unless the user explicitly asks.

## Task 5: Optional Independent Review

**Files:**
- Review-only: changed source and test files.

**Step 1: Dispatch a bounded reviewer if requested**

Ask an independent reviewer to check only:
- Runtime contract mismatches between frontend Livermore calls and backend routes.
- Whether any mock payload invents business conclusions.
- Whether `frontend/src/api/client.ts` growth is limited to existing composition/mock compatibility and not new endpoint implementation.
- Whether tests cover the new route validation boundaries.

Expected:
- Findings are actionable file/line issues, not broad style preferences.
- If no issues are found, record residual risks and keep the branch unchanged.

## Completion Report Requirements

Report:
- Root cause by cluster.
- Changed files by area.
- Verification commands and exact observed results.
- Remaining risks.
- Whether work is uncommitted.
- Whether ignored generated outputs exist and are intentionally not part of the change.
