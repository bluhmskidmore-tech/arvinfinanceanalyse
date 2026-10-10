# WP-B · 市场总览的查询层：改 `detail=core`、去 `history_limit`、与壳层共享 `choice-latest` 缓存

- 泳道：L2 前端·市场页，第 1 个（之后同一会话继续 WP-D）
- 层：TS + vitest
- 难度：低（改动一处文件，但有三处测试断言绑着源码字符串）
- 前置：无
- 配套：WP-B2 让后端预热 `full` 键，服务 `/macro-toolkit`；本包只管 `/market-overview`

## 目标

`/market-overview` 首屏对 `/ui/macro/toolkit/analysis` 的请求从 `detail=full&history_limit=430` 改为 `detail=core`，命中后端已在预热的缓存键；同一页对 `/ui/macro/choice-series/latest` 的读与壳层行情条共用一个 react-query 键，避免同一 473 KB 载荷解析两遍。

## 根因

- `detail=full` 与 `detail=core` 返回**完全相同的 23 个顶层键**，差别只在 `capability_results` 里的历史数组（`.tmp-agent/market-overview-audit/detail_cost.py`：51 KB vs 156 KB）。本页对历史数组的唯一消费是 `marketDeskIntelModel.ts:77-98` 的 `crisisHistoryDelta`（首尾差），而 `scoreDelta` / `percentileDelta` / `scoreHistory` 在本路由**没有任何渲染方**（唯一消费组件 `MarketCrossAssetGapBlock` 不在 `MarketHomeLayout` 渲染树里，全仓 grep 只有它自己的测试引用）。首屏 Crisis 位只显示 `crisisScore.toFixed(2)` 与 `regime`，`core` 档都有。
- 后端预热器只预热 `core`（`backend/app/services/market_home_warmup_service.py:123-134`），页面请求 `full/430` 永远不命中，每个 TTL 窗口第一个用户吃 3.3 s 冷计算，且这 3 s 卡在首屏判断位。`/macro-observation` 用的就是 `core`：2 条读、20 KB、852 ms 收敛。
- `useMarketHomeQueries.ts:20` 的键 `["module-home","choice-latest",mode]` 与壳层 `WorkbenchShellMarketTicker.tsx:10` 的 `["workbench-shell","choice-macro-latest",mode]` 不同，同一页加载两份。

## 改动范围

`frontend/src/features/workbench/module-home/useMarketHomeQueries.ts`：

1. `macroToolkitAnalysisQuery`（`:37-51`）：`queryFn: () => client.getMacroToolkitAnalysis({ detail: "core" })`；`queryKey` 改为 `["module-home", "macro-toolkit-analysis", "core", client.mode]`。
2. 删除 `export const MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT = 430`（`:7`）。
3. `choiceLatestQuery`（`:19-23`）的 `queryKey` 改为 `["workbench-shell", "choice-macro-latest", client.mode]`（与壳层完全一致；`useCrossAssetViewModel.ts:114` 已经这么做）。`staleTime` 等选项保持本 hook 的 `MARKET_HOME_QUERY_OPTIONS`——react-query 允许同键不同观察者选项。

测试同步（这三处是**源码字符串断言**，不改就红）：

- `frontend/src/test/ModuleWorkbenchHomeModel.test.ts:3197-3210`：把 `describe("useMarketHomeQueries contract")` 改为断言 `detail: "core"`、不含 `historyLimit`、不含 `MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT`、`queryKey` 含 `"core"`。用例名同步改。
- `frontend/src/test/ModuleWorkbenchHomePage.test.tsx:43`（import）与 `:2765-2769`（`toHaveBeenCalledWith({ detail: "full", historyLimit })`）改为 `toHaveBeenCalledWith({ detail: "core" })`，删 import。用例名 `:2748` 里的 "full" 字样一并改。
- `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.test.tsx:691` 起的 `useMarketHomeQueries` 用例：检查是否对 `getMacroToolkitAnalysis` 的参数有断言，有则同改。

契约文档：`docs/page_contracts.md` §14.6-C 有一句 "macro toolkit **full** analysis with `historyLimit: 430`"（`:2353`）改为 "macro toolkit `core` analysis"；同文件 `:1617/:1634` 是 `/macro-toolkit` 页（PAGE-MACRO-TOOLKIT-001）的条目，**不要动**。

## 不得触碰

- `MarketDeskIntelModel.ts` 的 `crisisHistoryDelta`、`MarketCrossAssetGapBlock.tsx`：死代码清理属 WP-D 或后续，本包不删。
- `/macro-toolkit` 页的 `detail: "full"`（`MacroToolkitPage.tsx:166-170`）：它渲染 Crisis 走势，需要历史，由 WP-B2 在后端补预热。
- `ModuleWorkbenchHomePage.tsx:231-233`（performance / governance 模块首页）的 `["module-home","choice-latest"]` 键：不是本页，不改。
- `MarketHomePage.tsx` 的刷新流程（`refetchAfterMarketRefresh(queries.choiceLatest)` 等）：共享键后 `refetch()` 会同时刷新壳层行情条，这是期望行为，不需要改代码，但报告里点明。

## 验收

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- ModuleWorkbenchHomePage ModuleWorkbenchHomeModel MarketOverviewDenseFirstScreen LiveRouteReadiness
```

浏览器（前后端在线，`frontend/` 下）：把 `.tmp-agent/market-overview-audit/timing.mjs` 复制到 `frontend/.tmp-audit/` 执行，`/market-overview` 应满足：`toolkit/analysis` 条目 URL 为 `?detail=core`，`server` 时长 < 500 ms（预热命中）；`choice-series/latest` 条目 **1 次**。`.tmp-agent/market-overview-audit/audit3.mjs` 复跑，Crisis 位仍显示分数与 regime（不是 `—`）。

## 报告要求

根因、改动文件、验证命令与结果、剩余风险（若 `/macro-toolkit` 尚未由 WP-B2 补预热，它仍吃冷计算——与本包无关但要点出；`core` 档若未来砍掉 `capability_results[crisis_score_cn]`，首屏 Crisis 位会退到 `—`，`MarketOverviewDenseFirstScreen.test.tsx` 应有一条用 `core` fixture 的断言守住）。对 `core_finance/` 的影响：无。
