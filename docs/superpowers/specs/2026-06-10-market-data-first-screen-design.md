# 市场数据页首屏收口（Route A）

**日期：** 2026-06-10
**页面：** `/market-data`（PAGE-MKT-001）
**状态：** 已批准，实施中

## 目标

打开市场数据页时，首屏优先展示正式利率读面（Tape、KPI、筛选、利率表 + 宏观深度）；Livermore 与长篇联动不抢占注意力；减少非必要请求与 DOM 挂载。

## 范围

### 做

1. Livermore 区块默认折叠（Collapse），标题保留「A 股防守策略 · 点击展开」。
2. Livermore API 仅在用户展开后 `enabled`（`getLivermoreStrategy` 延迟拉取）。
3. 宏观深度 Tab 保持按 `macroDepthTab` 条件渲染（已懒加载，补测试断言）。
4. `useMarketDataPageData` 对市场 data queries 设置 `refetchOnWindowFocus: false`（`staleTime` 继续沿用 `externalDataQueryOptions`）。
5. 确认 `WorkbenchShell` 在市场页隐藏子导航网格。
6. 回归：`MarketDataPage.test.tsx` + `debt:audit`。

### 不做

- 不接 source-pending 真实数据源。
- 不补算金融指标。
- 不拆整页 `MarketDataPage.tsx` 大重构（仅抽 Livermore 折叠区小组件）。

## 验收

- 默认 DOM 中无 `market-data-livermore-panel` 正文（折叠未展开）。
- 展开后 Livermore 面板与既有 testid 行为不变。
- 曲线 Tab 激活时，`market-data-macro-tab-spreads` 不存在。
- `data-layout-rev=2026-06-10d`。

## 风险

- 测试需先展开 Livermore 再断言面板内容。
- 证据轨在未展开时 Livermore 行可能仍为 pending（符合延迟加载语义）。
