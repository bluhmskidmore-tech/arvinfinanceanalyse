# WP-F · `/cross-asset` 与 `/market-data` 对 `choice-series/latest` 各读两遍

- 泳道：L3 前端·子页面，第 2 个（WP-E 之后；文件与 E 无交集，但同属子页面，放同一会话省上下文）
- 层：TS + vitest
- 难度：低（改动小，但要核对 react-query 观察者选项的叠加效果）
- 前置：无（WP-B 在市场总览页做了同样的键统一，本包是子页面侧）
- 优先级：P1，可延后；不影响正确性，只影响每页一次 473 KB 的重复解析

## 现象

`.tmp-agent/market-overview-audit/dup_reads.py` / `timing.mjs`（Resource Timing）：

- `/market-data`：`queued@256ms` 与 `queued@706ms` 各拉一次 `/ui/macro/choice-series/latest` → 键不同，必然双拉。
- `/cross-asset`：`queued@268ms` 与 `queued@486ms` 各拉一次 → 键**相同**，但 `refetchOnMount: "always"` 强制在壳层刚取完之后再取一遍。

全应用对这条读注册了 6 个不同的 react-query 键（审计 §7.2）；本包只处理市场工作台内的两个子页面，其他消费方（bond-analytics、operations）不在范围。

## 根因与修法

### F1 · `/cross-asset`

`frontend/src/features/cross-asset/hooks/useCrossAssetViewModel.ts:113-118`：

```ts
const latestQuery = useQuery({
  queryKey: ["workbench-shell", "choice-macro-latest", client.mode],
  queryFn: () => client.getChoiceMacroLatest(),
  retry: false,
  refetchOnMount: "always",
});
```

删掉 `refetchOnMount: "always"`。壳层 `WorkbenchShellMarketTicker.tsx:13` 对同键设 `staleTime: 60_000`，页面挂载时若数据在 60 s 内就直接复用；超过 60 s react-query 默认 `refetchOnMount: true`（stale 才刷）已经足够。**先确认**：`CrossAssetPage.test.tsx` 是否有用例依赖"每次挂载必刷"（例如 `:221` "starts below-fold queries one stage before their panels mount" 或任何 `toHaveBeenCalledTimes(2)`）。测试 `QueryClient` 设 `staleTime: 0`（`:30`），默认行为下挂载仍会刷，所以多数用例不受影响；有依赖就把用例改成断言"复用缓存"。

### F2 · `/market-data`

`frontend/src/features/market-data/hooks/useMarketDataPageData.ts:85-91` 的键 `["market-data","choice-macro-latest",mode]` 改为壳层键 `["workbench-shell","choice-macro-latest",mode]`；同文件 `:253-256` `queryClient.getQueryData([...])` 用的同一个键要一起改（否则联动分析的 `report_date` 解析读不到缓存）。

注意叠加效果：该页给这条读套了 `externalDataQueryOptions({refresh_tier:"fallback", fetch_mode:"latest"})`（`frontend/src/app/externalDataRefreshPolicy.ts:78-96`，含 `refetchInterval` 轮询与 `refetchOnWindowFocus: true`），统一键后**这个观察者的轮询会顺带刷新壳层行情条**。这是可接受的（同一数据、更新更及时），但要在报告里写明，并确认 `MarketDataPage.test.tsx` 里对 `getChoiceMacroLatest` 调用次数的断言。

## 不得触碰

- `WorkbenchShellMarketTicker.tsx`、`workbenchShellTicker.ts`（壳层不改）。
- `externalDataRefreshPolicy.ts`（刷新策略是治理约定）。
- `useMarketHomeQueries.ts`（WP-B）。
- bond-analytics / operations 页的同类键。

## 验收

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- CrossAssetPage MarketDataPage crossAssetDriversPageModel
```

浏览器：从 `frontend/` 复跑 `.tmp-agent/market-overview-audit/timing.mjs`（复制到 `frontend/.tmp-audit/`），`/market-data` 与 `/cross-asset` 的 `choice-series/latest` 条目各 **1 次**；`/cross-asset` 从 `/market-overview` 导航过去时（同一 SPA 会话）为 **0 次**（复用市场总览 WP-B 之后的同键缓存）。

## 报告要求

根因、改动文件、验证结果、剩余风险（轮询叠加到壳层；`refetchOnMount` 删除后 `/cross-asset` 在 60 s 内二次进入不会刷新，这是设计意图而非退化）。对 `core_finance/` 的影响：无。
