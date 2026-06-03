# Frontend Strict Build And Livermore Contract Review Summary

## Latest Verification Refresh

Refresh date: 2026-06-03

Current staged state:

- 29 staged files.
- No unstaged tracked diff.
- `git diff --cached --check`: passed.
- `git commit --dry-run --short`: passed and listed the same 29-file staged set.

Fresh verification passed:

- Continuation refresh re-ran the most relevant commit-readiness checks in the isolated worktree:
  - `cd frontend; npm run test`: 176 files / 1326 tests passed. jsdom emitted a non-fatal navigation warning during the run; Vitest exited 0.
  - `cd frontend; npx tsc -b --pretty false`: passed.
  - `cd frontend; npm run lint`: passed.
  - `cd frontend; npm run build`: passed.
  - `cd frontend; npm run debt:audit`: passed with no baseline growth.
  - `python -m pytest tests/test_market_data_livermore_candidate_history.py -q`: 43 passed.
  - `python -m pytest tests/test_market_data_livermore_api.py tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q`: 54 passed.
  - `python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q`: 82 passed.
  - Local Playwright smoke against `http://127.0.0.1:5177`: `/`, `/stock-analysis`, `/risk-tensor`, and `/pnl-by-business` each rendered non-empty body text, reported no browser console errors, and did not show fatal/error text. The temporary Vite dev server was stopped after the pass.
- Full frontend test stabilization:
  - `frontend/vitest.config.ts` now excludes `tests/playwright/**` from Vitest collection so Playwright specs stay under the Playwright runner.
  - `fileParallelism: false` is enabled to remove full-suite jsdom/page-test concurrency instability observed in Dashboard and CrossAsset page tests.
  - Mock formal PnL date discovery now returns deterministic formal report dates so formal FI attribution tabs can load in mock mode instead of returning early.
  - Dashboard account rows expose stable `data-testid` values for targeted drilldown assertions.
  - Dashboard and PnL page tests now assert the current rendered contract for mini-chart visibility, truncated source labels, and the bilingual Campisi tab label.
- Code review follow-up tightened Livermore snapshot query validation to exact `YYYY-MM-DD` and added a trailing-garbage API regression assertion.
- Local staged diff review found no additional code-level blocker after the date-validation follow-up.
- Architecture review status: `WATCH`, with no merge-blocking boundary issue found. Watch items: keep `return_10d` scoped to Livermore strategy score/optimization, and avoid further endpoint/fallback growth in `frontend/src/api/client.ts`.
- Final local staged-diff review found no additional merge-blocking issue. Livermore advanced endpoints remain in `frontend/src/api/marketDataClient.ts` rather than new `frontend/src/api/client.ts` endpoint implementations; `frontend/vitest.config.ts` only excludes `tests/playwright/**` from Vitest collection; `return_10d` is aligned across backend validation, frontend contracts, client query construction, UI labels, and regression tests.
- Independent subagent review was attempted, but both code-review and architecture-review agents failed with upstream `429 Too Many Requests` before producing findings. The final review evidence therefore comes from local staged-diff review plus the verification commands listed here.
- Tool discovery was re-run for the project MCP servers named in `AGENTS.md`; `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` still were not exposed in the current tool surface. Available discovered tools were unrelated surfaces such as Playwright, GitHub, Canva, and Node REPL.
- Browser smoke pass against `http://127.0.0.1:5177` covered `/`, `/stock-analysis`, `/risk-tensor`, and `/pnl-by-business`; each route rendered non-empty body text, no fatal/error text was detected, and no browser console errors were observed. The temporary Vite dev server was stopped after the pass.
- Earlier targeted frontend verification remains useful supporting evidence:
  - `cd frontend; npx tsc -b --pretty false`
  - `cd frontend; npm run lint`
  - `cd frontend; npm run build`
  - `cd frontend; npm run debt:audit`
  - `cd frontend; npm run test -- ApiClient`: 2 files / 82 tests passed.
  - `cd frontend; npm run test -- MarketDataLivermoreClientContract`: 1 file / 2 tests passed.
  - `cd frontend; npm run test -- StockAnalysisPage MarketDataLivermoreClientContract`: 3 files / 61 tests passed.
  - `cd frontend; npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage MarketDataLivermoreClientContract`: 7 files / 96 tests passed.
  - `python -m pytest tests/test_market_data_livermore_candidate_history.py -q`: 43 passed.
  - `python -m pytest tests/test_market_data_livermore_api.py tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q`: 54 passed.
  - `python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q`: 82 passed.

## Commit Title Draft

```text
fix: close frontend strict build and livermore route contracts
```

## Commit Command Draft

`docs/lore-commit-protocol.md` is referenced by `AGENTS.md` but is not present in this worktree. The draft below follows the trailer pattern found in existing project plan examples.

```powershell
git commit -m "fix: close frontend strict build and livermore route contracts" `
  -m "Constraint: Business metric correctness and page-level closure take priority over broad frontend or backend refactors." `
  -m "Rejected: Add Livermore endpoint implementations to frontend/src/api/client.ts | would violate the domain-client boundary." `
  -m "Rejected: Fabricate advanced Livermore mock performance rows | would create unsupported business conclusions." `
  -m "Confidence: high" `
  -m "Scope-risk: moderate" `
  -m "Directive: Keep future market-data endpoint work in domain clients and keep unsupported analytical mock payloads explicit." `
  -m "Tested: full frontend Vitest suite, frontend strict build, lint, production build, debt audit, targeted frontend tests, Livermore backend route tests, adjacent Livermore API tests, PnL/Risk backend contract tests, browser smoke pass, diff whitespace check" `
  -m "Not-tested: full browser visual regression/reference comparison; project MCP contract/lineage/catalog checks because the required MCP servers were not exposed in this session"
```

## Staging Command Draft

```powershell
git add -- `
  backend/app/api/routes/market_data_livermore.py `
  frontend/src/api/client.ts `
  frontend/src/api/contracts.ts `
  frontend/src/api/marketDataClient.ts `
  frontend/src/api/pnlClient.ts `
  frontend/src/app/externalDataRefreshPolicy.ts `
  frontend/src/features/market-data/components/LivermoreStrategyPanel.test.tsx `
  frontend/src/features/market-data/lib/livermoreStrategyModel.ts `
  frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx `
  frontend/src/features/market-data/pages/marketDataPageModel.ts `
  frontend/src/features/pnl/PnlByBusinessPage.tsx `
  frontend/src/features/risk-tensor/RiskTensorPage.tsx `
  frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx `
  frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx `
  frontend/src/features/workbench/pages/DashboardPage.tsx `
  frontend/src/test/BalanceMovementAnalysisPage.test.tsx `
  frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx `
  frontend/src/test/BondDashboardPage.test.tsx `
  frontend/src/test/RiskOverviewPage.test.tsx `
  tests/test_market_data_livermore_candidate_history.py `
  docs/plans/2026-06-03-frontend-node-tsconfig-build.md `
  docs/plans/2026-06-03-frontend-strict-build-closure.md `
  docs/plans/2026-06-03-frontend-full-test-stabilization-closure.md `
  docs/plans/2026-06-03-review-ready-closure.md `
  docs/plans/2026-06-03-review-summary.md `
  frontend/vitest.config.ts `
  frontend/src/test/DashboardPage.test.tsx `
  frontend/src/test/PnlAttributionPage.test.tsx `
  frontend/src/test/MarketDataLivermoreClientContract.test.ts
```

After staging, verify the staged set before committing:

```powershell
git diff --cached --name-status
git diff --cached --check
```

Expected staged file count:

- 29 files total
- 23 modified tracked source/test/config files
- 6 added review/test files

## PR Body Draft

```markdown
## Summary

- Restores frontend project-reference build coverage and closes stale TypeScript contract drift.
- Adds missing Livermore advanced domain-client methods and matching read-only backend routes.
- Aligns Livermore `primary_horizon=return_10d` across backend route validation, frontend client options, payload contracts, and StockAnalysis labels.
- Keeps Livermore advanced mock data in explicit warning/empty-evidence states.
- Fixes Dashboard, PnL, RiskTensor, and fixture type drift surfaced by strict checking.

## Verification

- `cd frontend; npx tsc -b --pretty false`
- `cd frontend; npm run lint`
- `cd frontend; npm run build`
- `cd frontend; npm run debt:audit`
- `cd frontend; npm run test`: 176 files / 1326 tests passed
- `cd frontend; npm run test -- StockAnalysisPage MarketDataLivermoreClientContract`
- `cd frontend; npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage MarketDataLivermoreClientContract`
- `python -m pytest tests/test_market_data_livermore_candidate_history.py -q`
- `python -m pytest tests/test_market_data_livermore_api.py -q`
- `python -m pytest tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q`
- `python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q`
- Browser smoke against `http://127.0.0.1:5177`: `/`, `/stock-analysis`, `/risk-tensor`, `/pnl-by-business`; all four routes rendered non-empty body text with no console errors or fatal/error text.
- `git diff --check`

## Residual Risk

- Browser smoke pass was run; full visual regression/reference comparison was not run.
- Project MCP contract/lineage/catalog/gitnexus servers named in `AGENTS.md` were not exposed in this session; tool discovery was re-run and still only exposed unrelated surfaces. Local contracts, services, route tests, browser smoke, and frontend/backend verification were used instead.
- Independent subagent review could not complete because both reviewer agents hit upstream `429 Too Many Requests`; local staged-diff review was used instead.
- Work is currently uncommitted.
```

## Integration Notes

Current branch:

- `codex/frontend-node-tsconfig-build`

Likely base branch:

- `main`

Observed merge-base:

- `e5288b5f37d8112f5606d049c094efad4266f7ec`
- Decorated as: `main`
- Subject: `tests: grant product PnL refresh scope`

Remote:

- `origin https://github.com/bluhmskidmore-tech/arvinfinanceanalyse.git`

Current branch head before committing this work:

- `a4c955e5`
- Subject: `Fix frontend node tsconfig module resolution`

Post-review options:

1. Keep the worktree as-is for manual review.
2. Stage and commit using the staging and commit drafts above.
3. Push the committed branch and create a PR against `main` using the PR body draft above.
4. Merge locally only after committing and re-running the chosen verification on the merged result.

## Completion Audit

Evidence-proven:

- Frontend strict project-reference build has been restored for the changed frontend surface.
- React Query refresh-policy typing is aligned without changing refresh behavior.
- StockAnalysis advanced Livermore frontend calls have matching market-data domain-client methods.
- Backend exposes read-only UI routes for Livermore strategy optimization, cycle proxy backtest, and candidate-history portfolio backtest.
- `primary_horizon=return_10d` is accepted by backend route validation and frontend StrategyScore/Optimization contracts.
- Unsupported Livermore mock analytical payloads remain explicit warning/empty-evidence states.
- Dashboard, PnL, RiskTensor, and touched fixture type drift is closed under the verified strict build.
- Review, staging, commit, PR, delivery-audit, and file-manifest materials exist in this summary.
- A 29-file staged set has been produced and verified with `git diff --cached --name-status`, `git diff --cached --check`, and `git commit --dry-run --short`.
- Browser smoke pass rendered `/`, `/stock-analysis`, `/risk-tensor`, and `/pnl-by-business` with non-empty body text, no fatal/error text, and no browser console errors.

Evidence still missing or intentionally not claimed:

- No commit has been created.
- No branch push or PR exists.
- No full browser visual regression/reference comparison was run.
- Project MCP contract/lineage/catalog/gitnexus checks were not run because the required MCP servers were not exposed in this session even after re-running tool discovery.
- Independent subagent code/architecture review could not complete because both reviewer agents hit upstream `429 Too Many Requests`.
- No local merge into `main` has been attempted.

Current completion stance:

- The work is review-ready and commit-ready.
- The broader thread goal remains active because repository integration actions have not been requested or completed.

## Summary

- Restores frontend project-reference build coverage by closing stale TypeScript contracts exposed by `npx tsc -b`.
- Aligns React Query refresh-policy and market-data query typing with current inference without changing refresh behavior.
- Adds missing Livermore advanced domain-client methods and matching read-only backend routes for strategy optimization, cycle proxy backtest, and candidate-history portfolio backtest.
- Aligns Livermore `primary_horizon=return_10d` across backend route validation, frontend client options, payload contracts, and StockAnalysis horizon labels.
- Keeps advanced Livermore mock payloads in warning/empty evidence states instead of inventing performance conclusions.
- Fixes Dashboard, PnL, RiskTensor, and test fixture type drift surfaced by strict checking.

## Root Causes

- The stricter frontend project-reference command caught gaps that the existing root typecheck did not cover.
- StockAnalysis used Livermore advanced methods that existed in tests/service concepts but were missing from the real market-data domain client and backend UI routes.
- Backend Livermore services already handled `return_10d`, while frontend StrategyScore types and client option unions still rejected it.
- Dashboard and fixture tests had drifted from current component/model contracts.
- PnL and RiskTensor pages had small API/client type gaps exposed by stricter checking.

## Changed Areas

- Backend Livermore API:
  - `backend/app/api/routes/market_data_livermore.py`
  - `tests/test_market_data_livermore_candidate_history.py`
- Frontend API and contracts:
  - `frontend/src/api/contracts.ts`
  - `frontend/src/api/marketDataClient.ts`
  - `frontend/src/api/client.ts`
  - `frontend/src/api/pnlClient.ts`
- Frontend pages/models:
  - `frontend/src/app/externalDataRefreshPolicy.ts`
  - `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
  - `frontend/src/features/market-data/pages/marketDataPageModel.ts`
  - `frontend/src/features/market-data/lib/livermoreStrategyModel.ts`
  - `frontend/src/features/pnl/PnlByBusinessPage.tsx`
  - `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
  - `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
  - `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
  - `frontend/src/features/workbench/pages/DashboardPage.tsx`
- Tests:
  - `frontend/src/test/MarketDataLivermoreClientContract.test.ts`
  - `frontend/src/features/market-data/components/LivermoreStrategyPanel.test.tsx`
  - `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`
  - `frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx`
  - `frontend/src/test/BondDashboardPage.test.tsx`
  - `frontend/src/test/RiskOverviewPage.test.tsx`

## Delivery Audit

Tracked source/test files with modifications:

- `backend/app/api/routes/market_data_livermore.py`
- `frontend/src/api/client.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/api/marketDataClient.ts`
- `frontend/src/api/pnlClient.ts`
- `frontend/src/app/externalDataRefreshPolicy.ts`
- `frontend/src/features/market-data/components/LivermoreStrategyPanel.test.tsx`
- `frontend/src/features/market-data/lib/livermoreStrategyModel.ts`
- `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- `frontend/src/features/market-data/pages/marketDataPageModel.ts`
- `frontend/src/features/pnl/PnlByBusinessPage.tsx`
- `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx`
- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`
- `frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx`
- `frontend/src/test/BondDashboardPage.test.tsx`
- `frontend/src/test/RiskOverviewPage.test.tsx`
- `tests/test_market_data_livermore_candidate_history.py`

Untracked files intended for this review package:

- `docs/plans/2026-06-03-frontend-node-tsconfig-build.md`
- `docs/plans/2026-06-03-frontend-strict-build-closure.md`
- `docs/plans/2026-06-03-review-ready-closure.md`
- `docs/plans/2026-06-03-review-summary.md`
- `frontend/src/test/MarketDataLivermoreClientContract.test.ts`

Ignored/generated outputs observed and not intended for commit:

- `.codex-tmp/`
- `backend/**/__pycache__/`
- `tests/__pycache__/`
- `data/`
- `frontend/dist/`
- `frontend/node_modules/`
- `frontend/tsconfig.app.tsbuildinfo`
- `frontend/tsconfig.node.tsbuildinfo`

## File Manifest

| Area | File | Purpose |
| --- | --- | --- |
| Backend Livermore | `backend/app/api/routes/market_data_livermore.py` | Adds read-only UI routes for strategy optimization, cycle proxy backtest, and portfolio backtest; centralizes snapshot and horizon validation. |
| Backend tests | `tests/test_market_data_livermore_candidate_history.py` | Covers the new routes, invalid date/horizon handling, and `return_10d` route acceptance. |
| Frontend contracts | `frontend/src/api/contracts.ts` | Aligns StrategyScore/Optimization horizon types with `return_10d` without expanding candidate-history row requirements. |
| Frontend market-data client | `frontend/src/api/marketDataClient.ts` | Adds domain-client methods for advanced Livermore calls and keeps mock payloads warning/empty where evidence is unavailable. |
| Frontend API compatibility | `frontend/src/api/client.ts` | Adds missing RiskTensor mock cashflow fields for existing composition compatibility; no new endpoint implementation. |
| Frontend PnL client | `frontend/src/api/pnlClient.ts` | Closes PnL API type gaps exposed by strict project-reference checking. |
| React Query typing | `frontend/src/app/externalDataRefreshPolicy.ts` | Loosens refresh callback query typing to match React Query inference without changing refresh behavior. |
| Market-data page typing | `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx` | Aligns query result error typing with upstream inference. |
| Market-data model typing | `frontend/src/features/market-data/pages/marketDataPageModel.ts` | Keeps macro-bond linkage empty-state typing explicit under strict checking. |
| Livermore model/test | `frontend/src/features/market-data/lib/livermoreStrategyModel.ts` | Aligns Livermore strategy model contract drift. |
| Livermore component test | `frontend/src/features/market-data/components/LivermoreStrategyPanel.test.tsx` | Updates expected Livermore strategy model fixture fields. |
| StockAnalysis page | `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx` | Uses typed optimization slice rows and shows T+10 horizon labels correctly. |
| StockAnalysis contract test | `frontend/src/test/MarketDataLivermoreClientContract.test.ts` | Protects frontend client and payload contracts accepting `return_10d`. |
| Dashboard cockpit | `frontend/src/features/workbench/dashboard/DashboardCockpitSections.tsx` | Restores the account table component expected by the dashboard page. |
| Dashboard page | `frontend/src/features/workbench/pages/DashboardPage.tsx` | Removes stale prop usage after component contract drift. |
| PnL page | `frontend/src/features/pnl/PnlByBusinessPage.tsx` | Aligns page-level PnL result typing. |
| RiskTensor page | `frontend/src/features/risk-tensor/RiskTensorPage.tsx` | Aligns RiskTensor page contract with cashflow/liquidity fields. |
| Risk overview test | `frontend/src/test/RiskOverviewPage.test.tsx` | Updates mock fixture for current risk contract. |
| Balance movement test | `frontend/src/test/BalanceMovementAnalysisPage.test.tsx` | Fixes export Blob mock typing under strict checking. |
| Bond analytics test | `frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx` | Aligns optional top-holdings mock parameter. |
| Bond dashboard test | `frontend/src/test/BondDashboardPage.test.tsx` | Adds required duration-source fixture field. |
| Planning docs | `docs/plans/2026-06-03-frontend-node-tsconfig-build.md` | Records the initial strict-build repair plan. |
| Planning docs | `docs/plans/2026-06-03-frontend-strict-build-closure.md` | Records the wider frontend strict-build closure and route follow-up. |
| Planning docs | `docs/plans/2026-06-03-review-ready-closure.md` | Records review-readiness and verification closure. |
| Review docs | `docs/plans/2026-06-03-review-summary.md` | Provides commit/PR/staging/review manifest and residual-risk summary. |

## Verification Evidence

```powershell
cd frontend
npx tsc -b --pretty false
npm run lint
npm run build
npm run debt:audit
npm run test -- StockAnalysisPage MarketDataLivermoreClientContract
npm run test -- StockAnalysisPage dashboardCockpitModel BalanceMovementAnalysisPage BondAnalyticsInstitutionalCockpit BondDashboardPage MarketDataLivermoreClientContract
cd ..
python -m pytest tests/test_market_data_livermore_candidate_history.py -q
python -m pytest tests/test_market_data_livermore_api.py -q
python -m pytest tests/test_livermore_candidate_history_efficiency.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_risk_exit_source.py -q
python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_attribution_api_contract.py tests/test_risk_tensor_api.py -q
git diff --check
git commit --dry-run --short
```

Browser smoke evidence:

- Temporary Vite dev server: `http://127.0.0.1:5177`
- Routes checked: `/`, `/stock-analysis`, `/risk-tensor`, `/pnl-by-business`
- Result: each route rendered non-empty body text, no fatal/error text was detected, and no browser console errors were observed.
- Cleanup: the temporary Vite dev server was stopped after the smoke pass.

Observed results:

- Frontend strict build passed.
- Frontend lint passed.
- Continuation refresh re-ran frontend lint: passed.
- Frontend production build passed.
- Continuation refresh re-ran frontend production build: passed.
- Frontend debt audit passed with no baseline growth.
- StockAnalysis and Livermore client contract tests passed: 3 files / 61 tests.
- Continuation refresh re-ran StockAnalysis and Livermore client contract tests: 3 files / 61 tests passed.
- Broader targeted frontend tests passed: 7 files / 96 tests.
- Livermore candidate-history tests passed: 43 tests.
- Continuation refresh re-ran Livermore candidate-history route tests: 43 tests passed.
- Adjacent Livermore backend tests passed: 54 tests.
- Continuation refresh re-ran adjacent Livermore backend tests: 54 tests passed.
- PnL/Risk backend contract tests passed: 82 tests.
- Continuation refresh re-ran PnL/Risk backend contract tests: 82 tests passed.
- Browser smoke pass covered four page routes without fatal render text or browser console errors.
- Diff whitespace check passed.
- Commit dry-run passed and listed the expected 25 staged files.

## Residual Risks

- Project MCP servers named in `AGENTS.md` (`moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `gitnexus`) were not exposed in the current tool surface even after re-running tool discovery, so evidence came from local contracts, services, route tests, browser smoke, and frontend/backend verification.
- Independent subagent reviewers were attempted but unavailable due to upstream `429 Too Many Requests`; local staged-diff review found no additional code-level blocker.
- Work is intentionally uncommitted.
- Full browser visual regression/reference comparison was not run.
- Ignored generated outputs such as `frontend/dist/`, build info files, caches, and data outputs are not part of the change.
