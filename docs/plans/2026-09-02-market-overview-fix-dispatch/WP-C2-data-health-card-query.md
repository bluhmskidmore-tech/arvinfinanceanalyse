# WP-C2 · `StockAnalysisDataHealthCard` 绕过 react-query，一页发 2–4 次请求

- 泳道：L4 前端·股票页（独立泳道，文件与其它包无交集）
- 层：TSX + vitest
- 难度：低
- 前置：无
- 配套：WP-C1 修后端耗时；两包独立，任一先合都成立

## 目标

`/stock-analysis` 一次加载只发 **1 次** `GET /api/data-health`，重新挂载走缓存（`staleTime` 60 s），保留现有四态（loading / error+重试 / hidden / ready）与测试注入口 `loadHealth`。

## 根因

`frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.tsx:91-130` 用裸 `useState` + `useEffect` 调 `fetchDataHealth()`，没有缓存、没有去重。`main.tsx` 的 `React.StrictMode` 在开发态双跑 effect，加上页内其它重挂载，Resource Timing 实测一页 2–4 次请求、每次 3.3–4.3 s（后端侧慢是 WP-C1 的事）。这是全页最慢的一条读，且是 `/stock-analysis` 7.7–8.1 s 收敛时间的唯一主因。

## 改动范围

`StockAnalysisDataHealthCard.tsx`：

1. 用 `useQuery` 替换 `useEffect`：

```ts
const healthQuery = useQuery({
  queryKey: ["data-health", "overview"],
  queryFn: () => (loadHealth ?? fetchDataHealth)(),
  retry: false,
  staleTime: 60_000,
  refetchOnWindowFocus: false,
});
```

`loadHealth` 注入口保留（测试与接线都在用），进 `queryFn`；若 `loadHealth` 变化需要重取，把它的稳定性交给调用方（现有调用方 `StockAnalysisPageImpl.tsx:2772` 不传参）。

2. 四态映射：`isPending && !data` → loading；`isError` 或 `data.kind === "error"` → error（`reason` 取 `data.reason` 或 `error.message`）；`data.kind === "missing"` 或 sections 为空 → hidden；否则 ready。`fetchDataHealth` 本身把网络/解析失败都收进 `{kind:"error"}`，所以 `isError` 分支只在 `loadHealth` 抛异常时命中——保留，测试 `:149-153` 覆盖了这条路径。
3. 「重试」按钮从 `setAttempt(n+1)` 改为 `void healthQuery.refetch()`；重试期间保持 `error` 态或切回 loading 都可以，但要与现有测试 `:133-146` 的断言一致（先读测试再决定）。
4. 删除 `attempt` state 与 `cancelled` 逻辑。

`StockAnalysisDataHealthCard.test.tsx`：

- 组件现在需要 `QueryClientProvider`。照 `StockAnalysisPortfolioConstructionPage.test.tsx:159-179` 的 `Wrapper` 写法给每个 `render` 包一层（`retry: false`），每个用例新建 `QueryClient` 避免跨用例缓存串味。
- 新增 `test_dedupes_concurrent_mounts`：同一 `QueryClientProvider` 下渲染两个 `<StockAnalysisDataHealthCard loadHealth={spy} />`，`spy` 只被调用 1 次。
- 新增 `StrictMode` 用例：`render(<StrictMode>…</StrictMode>)`，`spy` 只被调用 1 次（这是本包的核心验收；仓库里 `LedgerPnlCandidateFinancialIndicatorsPanel.test.tsx:808` 有同类先例可参考）。

## 不得触碰

- 不改 `frontend/src/api/dataHealthClient.ts`（三分结果语义是契约的一部分）。
- 不改 `StockAnalysisPageImpl.tsx` 与页面其它部分；不改 CSS。
- 不改后端。

## 验收

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- StockAnalysisDataHealthCard StockAnalysisPage
```

浏览器（后端在线）：`node .tmp-audit/timing.mjs` 风格的 Resource Timing 复测——最简单是复用 `.tmp-agent/market-overview-audit/timing.mjs`（复制到 `frontend/.tmp-audit/` 下执行），`/stock-analysis` 的 `/api/data-health` 条目 **= 1**。

## 报告要求

根因、改动文件、验证命令与结果、剩余风险（`staleTime` 60 s 内健康面不会随后台变化刷新，页面有「重试」按钮可手动刷；后端单次 3 s 由 WP-C1 处理）。对 `core_finance/` 的影响：无。
