# WP-E · 子页面前端三件事：`/news-events` 移动端 176k px、`/stock-analysis` 契约锚点红灯、壳层行情条对比度

- 泳道：L3 前端·子页面，第 1 个（之后同一会话可继续 WP-F）
- 层：TSX/CSS/TS + vitest + Playwright
- 难度：中（三件互不相关的小事；E1 需要一点响应式判断）
- 前置：无
- 文件与其它包无交集，可与 L1/L2/L4 并行

## E1 · S1 `/news-events` 在 390 px 视口下文档高 176,515 px

**现象**（`.tmp-agent/market-overview-audit/spotcheck.mjs`）：`table` 高 172,184 px，50 行，**第一行 5,520 px**；1440 视口同页只有 8,025 px。约 209 屏。

**根因**：`NewsEventsPage.css:226-274` 的表格在窄视口没有任何收敛策略——`.news-events-page__table-scroll { overflow-x: auto }` 存在，但 `.news-events-page__table { width: 100% }` 让表格跟着 390 px 视口挤，`--summary` 单元格 `white-space: normal; word-break: break-word; max-width: 480px` 在窄列里逐字折行，每行摘要变成一根竖条。`@media (max-width: 720px)` 只处理了 `meta-grid`。

**修法**（二选一，倾向 A）：

- A. 让横向滚动真正生效：`@media (max-width: 720px)` 内给 `.news-events-page__table` 设 `min-width: 720px`（或按列数给一个能容下 8 列的下限），`--summary` 单元格 `max-width: 320px`。表格在容器内横滚，文档不横向溢出（容器已有 `overflow-x: auto`）。
- B. 窄视口改卡片列表（`display: block` 每行、`th` 隐藏、`td::before` 打标签）。改动大得多，只有 A 不可接受时再做。

**验收**：390×844 下 `document.documentElement.scrollHeight < 12,000`（50 行），`scrollWidth <= innerWidth + 2`（不横向溢出文档，容器内滚动允许），首行高度 < 200 px。用 `spotcheck.mjs` 第一段复测。`npm run test -- NewsEventsPage` 全绿。1440 视口截图对比无回归。

## E2 · S2 `/stock-analysis` 治理门禁红灯：两份契约互相矛盾

**现象**：`LiveRouteReadiness.test.tsx > keeps /stock-analysis tied to real page anchors and verification files` 失败：`stock-analysis-toolbar should remain in …StockAnalysisPage.tsx, …StockAnalysisPageImpl.tsx`。这是主页面门禁 175/176 里唯一的红灯。

**根因**：`frontend/src/test/liveRouteReadinessContracts.ts:158` 要求锚点 `["stock-analysis-toolbar", "stock-analysis-first-screen-main"]` 存在；而 `StockAnalysisPageChromeContract.test.ts:139-142` 断言 `stock-analysis-toolbar-*` 系列 testid **必须不存在**（页面已重构为 compact chrome）。`StockAnalysisPageImpl.tsx` 现在的锚点是 `stock-analysis-page`（`:2504`）、`stock-analysis-page-toolbar-owner`（`:2557`）、`stock-analysis-first-screen-workbench`（`:2594`）、`stock-analysis-first-screen-main`（`:2598`）。重构时更新了 chrome 契约，漏了 readiness 契约。

**修法**：`liveRouteReadinessContracts.ts:158` 的 `sourceAnchors` 改为 `["stock-analysis-page-toolbar-owner", "stock-analysis-first-screen-main"]`。只改这一行；`sourceFiles` 与 `verificationFiles` 不动。

**验收**：`npm run test -- LiveRouteReadiness StockAnalysisPageChromeContract` 全绿；主页面门禁组从 175/176 变为 176/176。

## E3 · S9 壳层行情条 `data-tone="down"` 对比度不足（出现在每一个市场页）

**现象**：axe `color-contrast (serious)` 命中 `.workbench-market-ticker-delta[data-tone="down"]`，在 `/market-data`（4 节点）、`/cross-asset`（9）、`/news-events`（2）重复出现。

**根因**：`frontend/src/styles/workbenchDeferredChrome.css:155-158` 把 `down` 与 `neutral` 一起用 `var(--dh-api-muted, …)`；Nocturne 主题下 `--dh-api-muted` 解析为 `var(--nct-muted)`（`tokens.css:531`），11 px 粗体字在 `#161826` 底上不到 4.5:1。

**修法**：先读 `DESIGN.md` 关于 muted 文本与状态色的条目，再在 `workbenchDeferredChrome.css` 里为 `[data-tone="down"]` 单独指定一个通过 4.5:1 的现有 token（优先 `--dh-api-ink-muted` 之外更亮一档的中性 ink token，或与 `up` 对称的语义色——注意 `DESIGN.md §11` 的"利率上行=琥珀、下行不赋色"决议：这条决议说的是**市场总览行情带**，壳层行情条是否沿用需要在报告里写明你的判断）。不新增色值；不改字号（11 px 是既有决议，且 `audit_font_size_floor` 有基线）。

**验收**：从 `frontend/` 复跑 `.tmp-agent/market-overview-audit/subpages.mjs`（复制到 `frontend/.tmp-audit/`），`/market-data`、`/cross-asset`、`/news-events` 的 axe 结果不再含 `color-contrast` 命中 `workbench-market-ticker-delta`；`npm run test -- WorkbenchShell theme` 全绿；`node ../scripts/audit_font_size_floor.mjs`（若存在于 `debt:audit`）不新增越界。

## 文件所有权

可改：`frontend/src/features/news-events/NewsEventsPage.css`（必要时 `.tsx`）、`frontend/src/test/liveRouteReadinessContracts.ts`、`frontend/src/styles/workbenchDeferredChrome.css` 及对应测试。

不得触碰：`StockAnalysisPageImpl.tsx`（红灯是契约文件过期，不是页面缺锚点）、`StockAnalysisPageChromeContract.test.ts`、`tokens.css`（不新增/改 token 值）、`workbenchShellTicker.ts`。

## 验证

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- NewsEventsPage LiveRouteReadiness StockAnalysisPageChromeContract WorkbenchShell
npm run test -- ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench \
  marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel \
  MarketOverviewDenseFirstScreen LiveRouteReadiness      # 期望 176/176
```

## 报告要求

按 E1–E3 逐条：根因、改动文件、验证结果、剩余风险（E1 若选 A，窄屏用户要横滚看列；E3 的色彩判断要引用 DESIGN.md 的具体条目）。对 `core_finance/` 的影响：无。
