# Frontend Full Test Stabilization Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stabilize the full frontend Vitest run after the strict-build and Livermore contract changes, then refresh the review-ready staged set without committing.

**Architecture:** Keep this as a verification and test-environment closure pass, not a new feature pass. Preserve the existing Livermore/domain-client work, accept only the smallest test harness or mock-data corrections needed to make full-suite behavior match already-supported page contracts, and update the review summary with fresh evidence.

**Tech Stack:** React, TypeScript, Vite/Vitest, jsdom, Testing Library, FastAPI/Pytest for already-staged backend verification.

---

### Task 1: Confirm Current Debug Diffs Are Legitimate

**Files:**
- Inspect: `frontend/vitest.config.ts`
- Inspect: `frontend/src/api/client.ts`
- Inspect: `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
- Inspect: `frontend/src/test/DashboardPage.test.tsx`
- Inspect: `frontend/src/test/PnlAttributionPage.test.tsx`

**Step 1: Review the unstaged diff**

Run:

```powershell
git diff -- frontend/vitest.config.ts frontend/src/api/client.ts frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx frontend/src/test/DashboardPage.test.tsx frontend/src/test/PnlAttributionPage.test.tsx
```

Expected: the diff only contains these narrow changes:

- Vitest excludes Playwright specs from the unit-test runner.
- Vitest disables file-level parallelism for page tests that share jsdom globals and query clients.
- Mock formal PnL dates include deterministic formal report dates so formal FI tabs can load in mock mode.
- Dashboard account rows expose stable test IDs.
- Dashboard and PnL tests assert the current rendered contract instead of stale labels.

**Step 2: Reject any unrelated edits**

If the diff includes unrelated page behavior, endpoint implementation, styling, or broad refactor changes, stop and remove those unrelated edits by manually applying a minimal reverse patch only for the unrelated lines.

Expected: no unrelated edits remain.

### Task 2: Run The Full Frontend Test Suite

**Files:**
- Verify: `frontend/vitest.config.ts`
- Verify: `frontend/src/test/*`

**Step 1: Run the full suite**

Run:

```powershell
cd frontend
npm run test
```

Expected: all Vitest test files pass. A jsdom navigation warning is acceptable only if Vitest exits successfully.

**Step 2: If full suite fails, isolate the failing file**

Run one command per failing file, for example:

```powershell
npx vitest run src/test/CrossAssetPage.test.tsx --reporter verbose
npx vitest run src/test/DashboardPage.test.tsx --reporter verbose
```

Expected: the isolated failure explains whether the issue is stale test expectation, missing mock data, or real component behavior.

**Step 3: Apply the smallest fix**

Only use one of these fix categories:

- Test harness collection fix in `frontend/vitest.config.ts`.
- Deterministic mock data correction in an existing mock area.
- Stable selector/test ID for already-rendered content.
- Test assertion update to match a currently intended UI contract.

Do not add new endpoint implementations to `frontend/src/api/client.ts`. Do not invent business metrics or analytical fallback values.

### Task 3: Refresh Required Frontend Verification

**Files:**
- Verify: all changed frontend source and test files.

**Step 1: Run strict TypeScript build**

Run:

```powershell
cd frontend
npx tsc -b --pretty false
```

Expected: exit code 0.

**Step 2: Run lint**

Run:

```powershell
cd frontend
npm run lint
```

Expected: exit code 0.

**Step 3: Run production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: exit code 0.

**Step 4: Run frontend debt audit**

Run:

```powershell
cd frontend
npm run debt:audit
```

Expected: exit code 0 with no baseline growth.

### Task 4: Refresh Backend And Contract Verification

**Files:**
- Verify: `backend/app/api/routes/market_data_livermore.py`
- Verify: `tests/test_market_data_livermore_candidate_history.py`
- Verify: related already-staged PnL/Risk contract tests.

**Step 1: Run Livermore candidate-history tests**

Run:

```powershell
python -m pytest tests/test_market_data_livermore_candidate_history.py -q
```

Expected: all tests pass.

**Step 2: Run adjacent Livermore route tests**

Run:

```powershell
python -m pytest tests/test_market_data_livermore_api.py tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q
```

Expected: all tests pass.

**Step 3: Run PnL/Risk contract tests**

Run:

```powershell
python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q
```

Expected: all tests pass.

### Task 5: Update Review Summary

**Files:**
- Modify: `docs/plans/2026-06-03-review-summary.md`

**Step 1: Add the new full-suite evidence**

Update the latest verification section with:

- Full `npm run test` result and test/file counts.
- Vitest config fix excluding `tests/playwright/**`.
- Whether `fileParallelism: false` was needed to remove full-suite jsdom/test-global instability.
- Mock formal PnL report-date correction.
- New staged file count after adding the latest five debug files and this plan.

Expected: the summary no longer says there is "No unstaged tracked diff" unless that is true after staging.

**Step 2: Refresh residual risk**

Keep these risks explicit if still true:

- Project MCP servers from `AGENTS.md` were not exposed in this session.
- No commit has been created.
- No push or PR exists.
- Full visual regression/reference comparison was not run unless newly completed.

### Task 6: Stage And Recheck The Final Review-Ready Set

**Files:**
- Stage: `frontend/vitest.config.ts`
- Stage: `frontend/src/api/client.ts`
- Stage: `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
- Stage: `frontend/src/test/DashboardPage.test.tsx`
- Stage: `frontend/src/test/PnlAttributionPage.test.tsx`
- Stage: `docs/plans/2026-06-03-review-summary.md`
- Stage: `docs/plans/2026-06-03-frontend-full-test-stabilization-closure.md`

**Step 1: Stage only intentional files**

Run:

```powershell
git add -- frontend/vitest.config.ts frontend/src/api/client.ts frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx frontend/src/test/DashboardPage.test.tsx frontend/src/test/PnlAttributionPage.test.tsx docs/plans/2026-06-03-review-summary.md docs/plans/2026-06-03-frontend-full-test-stabilization-closure.md
```

Expected: only intended files are added to the staged set.

**Step 2: Check staged whitespace**

Run:

```powershell
git diff --cached --check
```

Expected: no output and exit code 0.

**Step 3: Confirm no unstaged tracked diff remains**

Run:

```powershell
git diff --quiet -- .
if ($LASTEXITCODE -eq 0) { "NO_UNSTAGED_DIFF" } else { git diff --name-only }
```

Expected: `NO_UNSTAGED_DIFF`.

**Step 4: Confirm staged file count and dry-run commit**

Run:

```powershell
(git diff --cached --name-only | Measure-Object -Line).Lines
git commit --dry-run --short
```

Expected: commit dry-run succeeds and lists the same intentional staged set. Do not create a real commit unless the user explicitly says to commit.

### Task 7: Final Readiness Report

**Files:**
- Read: `docs/plans/2026-06-03-review-summary.md`

**Step 1: Report the final state in Chinese**

Include:

- Root cause of this round.
- Changed files added in this round.
- Verification commands and pass/fail results.
- Remaining risks.
- Clear next action choices: review locally, commit, push/PR, or merge after requested verification.

Expected: the report is concise and does not claim a commit, push, PR, or merge unless it actually happened.
