# WP-COMMIT · 把工作包改动按范围提交（严禁 `git add -A`）

- 泳道：独立；**必须在其它所有包停止改动、且用户确认另一个 Cursor 会话已停手之后**执行
- 层：git
- 难度：低，但错一次代价极高
- 背景：这个工作树里有**几百个与本次修复无关的历史未提交改动**（`git status --short` 200+ 行，含 `core_finance/`、schema、release-control 等），另有一个会话在 `.git/_g*.json` 里做分组。任何一次 `git add -A` / `git add .` / `git commit -a` 都会把无关改动一起提交，且可能与那个会话的分组互相打架。

## 规则

1. 只用 `git add -- <显式路径>`，路径来自下表；每组一个 commit；提交前 `git diff --cached --stat` 的文件数必须等于该组路径数。
2. 不 `stash`、不 `checkout --`、不 `reset`、不 `rebase`、不改 `.git/` 里任何东西、不删 `.git/_g*.json`。
3. 提交信息用现有风格（`git log --oneline -20` 看得到：`fix(...)`, `test(...)`, `docs(...)` 前缀 + 英文短句），一句话写"为什么"。
4. 提交前跑该组的门禁（下表）；红了就停下报告，不要用 `--no-verify`。
5. 提交后 `git status --short -- <该组路径>` 应为空。

## 分组与路径

| # | 提交信息（建议） | 路径 | 门禁 |
| --- | --- | --- | --- |
| 1 | `fix(scheduling): keep the daily refresh driver alive when a step writes to stderr` | `scripts/scheduling/daily_data_refresh.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\scheduling\daily_data_refresh.ps1 -DryRun` |
| 2 | `fix(macro-toolkit): classify long-running refresh receipts as abandoned` | `backend/app/services/macro_toolkit_refresh_receipt_service.py` `tests/test_macro_toolkit_refresh_receipt_service.py` | `python -m pytest tests/test_macro_toolkit_refresh_receipt_service.py -q` |
| 3 | `perf(data-health): cache the schtasks scan instead of shelling out per request` | `backend/app/services/data_health_service.py` `tests/test_data_health.py` | `python -m pytest tests/test_data_health.py -q` |
| 4 | `feat(market-overview): add the module-level market.snapshot read and warm it` | `backend/app/api/__init__.py` `backend/app/api/routes/market_overview.py` `backend/app/services/market_overview_service.py` `backend/app/services/market_home_warmup_service.py` `backend/app/services/macro_vendor_service.py` `tests/test_market_overview_snapshot_api.py` `tests/test_market_home_warmup.py` `scripts/shadow_compare_market_snapshot.py` | `python -m pytest tests/test_market_overview_snapshot_api.py tests/test_market_home_warmup.py tests/test_macro_toolkit_scripts.py tests/test_live_route_page_contract_completeness.py -q` |
| 5 | `fix(market-overview): share the choice-latest cache with the shell and keep the warmed full analysis` | `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts` `frontend/src/test/ModuleWorkbenchHomeModel.test.ts` `frontend/src/test/ModuleWorkbenchHomePage.test.tsx` | `npm run test -- ModuleWorkbenchHomePage ModuleWorkbenchHomeModel` |
| 6 | `fix(market-overview): make the first screen consistent, precise and interactive` | `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.tsx` `frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts` `frontend/src/features/workbench/module-home/MarketFinancialChartsWorkbench.tsx` `frontend/src/features/workbench/module-home/marketFinancialChartsModel.ts` `frontend/src/features/workbench/module-home/marketOverviewDenseModel.test.ts` `frontend/src/features/workbench/module-home/MarketFinancialChartsWorkbench.test.tsx` | `npm run test -- MarketFinancialChartsWorkbench marketOverviewDenseModel MarketOverviewDenseFirstScreen && npx playwright test tests/playwright/market-overview-smoke.spec.mjs -c playwright.config.mjs` |
| 7 | `fix(subpages): converge the news table on narrow viewports, sync readiness anchors, fix ticker contrast` | `frontend/src/features/news-events/NewsEventsPage.css` `frontend/src/test/liveRouteReadinessContracts.ts` `frontend/src/test/WorkbenchShellThemeGuard.test.ts` `frontend/src/styles/workbenchDeferredChrome.css` | `npm run test -- NewsEventsPage LiveRouteReadiness WorkbenchShell` |
| 8 | `perf(market-pages): stop double-reading choice-latest on cross-asset and market-data` | `frontend/src/features/cross-asset/hooks/useCrossAssetViewModel.ts` `frontend/src/features/market-data/hooks/useMarketDataPageData.ts` `frontend/src/test/CrossAssetPage.test.tsx` `frontend/src/test/MarketDataPage.test.tsx` | `npm run test -- CrossAssetPage MarketDataPage` |
| 9 | `perf(stock-analysis): load data health through react-query` | `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.tsx` `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.test.tsx` `frontend/src/test/StockAnalysisPage.test.tsx` | `npm run test -- StockAnalysisDataHealthCard StockAnalysisPage` |
| 10 | `docs(market-overview): audit, module compute plan, dispatch briefs and contract sync` | `docs/audits/2026-09-02-market-overview-page-audit.md` `docs/audits/2026-09-02-market-overview-backend-compute-handoff.md` `docs/plans/2026-09-02-market-overview-module-compute-plan.md` `docs/plans/2026-09-02-market-overview-fix-dispatch/` `docs/page_contracts.md` | `python -m pytest tests/test_live_route_page_contract_completeness.py -q` |

**每组开始前**先 `git diff -- <路径>` 看一眼：若某文件的 diff 里出现与该组主题无关的改动（例如 `workbenchDeferredChrome.css` 有 +282/-… 的大改，其中只有 `[data-tone="down"]` 那几行属于 WP-E），说明该文件叠着别的会话的历史改动。**不要**拆 hunk 硬提交，把该文件从本组移除并在报告里列出，交人裁决。`docs/page_contracts.md` 同理（+65 行里 WP-B 只改了一句，其余是 WP-G 追加的契约段与更早的改动）。

## 不得触碰

上表之外的任何路径；`.git/`；分支（在当前 `codex/V1` 上提交，不新建）。

## 报告要求

每组：提交哈希、文件数、门禁结果；被移出的文件及原因；结束时 `git status --short | Measure-Object -Line` 的行数（应比开始时少约 40）。
