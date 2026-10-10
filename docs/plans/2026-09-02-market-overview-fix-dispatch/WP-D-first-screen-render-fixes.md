# WP-D · 市场总览首屏与图表区的 5 个 P0 渲染缺陷

- 泳道：L2 前端·市场页，第 2 个（**在 WP-B 之后、同一会话**；两包都改 `ModuleWorkbenchHomePage.test.tsx`）
- 层：TS/TSX + vitest + Playwright smoke
- 难度：中（五个独立缺陷，每个都小，但要守住现有 176 条测试与 smoke）
- 前置：WP-B 已合入
- 说明：这是**过渡期修法**。方案 Phase 2（WP-H）会把 gate / 行情带 / 图表选择全部换成后端 `market.snapshot` 的输出；本包只求"当前页面不自相矛盾、数字不撒谎、控件不失效"，改动越小越好，不做重构。

## 目标与验收（逐条）

### D1 · F1 首屏判断位自相矛盾

**现象**：hero 显示「暂停形成今日判断／因数据质量预警，本页不展示来源结论摘要」，同屏 40 px 下方「焦点解读·宏观工具」卡却原样打印后端 `conclusion.summary`。两条渲染链没有共享 gate。

**根因**：`MarketOverviewDenseFirstScreen.tsx:199-238 buildMacroObservationGate` 把 `quality_flag !== "ok"` 一律判 blocked 并**替换**后端文案；`moduleHomeModel.ts:3216-3225` 的宏观 briefing 不经过 gate。后端在 `quality_flag=warning` 时本就给了一条安全的"不下结论"结论（`stance=数据不足`，`tone=missing`，`summary=最近一次定时数据刷新未通过完整性校验…`，`recommended_action=请完成后端数据刷新并通过回执校验…`），信息量比前端替换后的"数据质量预警"更大。

**最小修法**（只改 hero 侧，不动 briefings）：blocked 时 hero 的 summary/action 展示**后端原文**——`observationSummary = macro.conclusion.summary`，`observationAction = macro.conclusion.recommended_action`，`observationTitle` 保留「暂停形成今日判断」并把 `stance` 挂进 title；`gate.reasonSummary`（"数据质量预警"等）收进「使用边界」那一格的现有位置（`data-testid=module-home-market-dense-observation-gate`），不再进正文。这样两条链展示同一段后端文字，矛盾消失。

**验收**：`MarketOverviewDenseFirstScreen.test.tsx` 新增用例——`quality_flag=warning` + `conclusion.tone=missing` 的 fixture 下，`observation-summary` 文本 === fixture 的 `conclusion.summary`，`observation-action` 含 `recommended_action`，`observation-gate` 含「数据质量预警」；现有 blocked 用例若断言了旧文案「本页不展示来源结论摘要」，改为断言新行为。`audit3.mjs` 复跑后 `observation.summary` 与 `focus[3]` 的正文一致。

### D2 · F2 行情带数值与自身 tooltip 精度不一致

**现象**：格子 `1.6988%`，title `1.7%`；`6.7811` vs `6.78`；`108,900` vs `108900`。

**根因**：`marketOverviewDenseModel.ts:385-428 pointMetric` 的 `value` 走 `compactPointValue`（`compactNumber`：<10 取 4 位），`title` 走 `formatChoiceMacroValue`（另一套精度）。

**修法**：title 使用与格子相同的格式化结果（`title: \`${point.series_name} · ${compactPointValue(point)} · ${point.trade_date}\``）。不改 `compactNumber` 的规则本身。

**验收**：`marketOverviewDenseModel.test.ts` 新增断言：任一 tape metric 的 `title` 包含其 `value` 原文。

### D3 · F3 `-0CNY/USD`、沪深300 变动无符号、`index` 单位英文透出

三处都在 `marketOverviewDenseModel.ts`：

- `-0`：`pointMetric` 生成 `delta` 后，若数值部分为 ±0（用 `normalizeTapeTone` 同样的正则判零），文本改为「持平」（与壳层 `workbenchShellTicker.ts:102 FLAT_DELTA_DISPLAY` 用词一致，不要引入第三种说法）。`normalizeTapeTone`（`MarketOverviewDenseFirstScreen.tsx:96-101`）已把 tone 归中性，只需文本跟上。
- 沪深300 `0.85%` 无符号：`changePoint` 分支（`:409-411`）用的是 `formatChoiceMacroValue`（不带符号）；改为对 `changePoint.value_numeric` 做带符号格式化（正数前置 `+`），单位沿用该序列的 `unit`。
- `index` 单位：`normalizeDenseUnit`（`:115-120`）后接一张**本文件局部**的中文映射 `{ index: "指数", point: "点" }`，照 `crossAssetDriversPageModel.ts:1240-1245 CROSS_ASSET_EVIDENCE_UNIT_ZH` 的做法（该处注释明确"unit aliases stay local"，所以不要抽成共享工具）。`%`/`bp` 不受影响。

**验收**：`marketOverviewDenseModel.test.ts` 三条新用例：零变动 → `delta === "持平"`；CSI300 fixture（`changePoint.value_numeric = 0.85`）→ `delta` 以 `+` 开头；`unit: "index"` → `value` 含「指数」且不含 `index`。smoke 里 `toContainText("DR007")` 不受影响。

### D4 · F4 03 区默认 0 张画布，且一张图全页画两次

**现象**：`MarketFinancialChartsWorkbench` 默认只展开 `rates` 组，而该组两张图（`yield-curve`、`key-rate-trend`）正好在 `DENSE_FIRST_SCREEN_CHART_KEYS`（`:29`）里被换成「见 02 区」指路卡 → 打开页面 03 区 0 张画布；同时 02 区 `selectedDenseCharts`（`MarketOverviewDenseFirstScreen.tsx:58-75`）选了 `cross[1]`（最新一期跨资产变动），但去重集合没登记它 → 02/03 各画一遍。两份列表没有同一来源。

**修法**：

1. 在 `marketFinancialChartsModel.ts` 新增导出 `DENSE_FIRST_SCREEN_CHART_PICKS`（`{ sectionKey, chartIndex, indexLabel }[]`，内容就是现在 `selectedDenseCharts` 里的 `picks`）。`MarketOverviewDenseFirstScreen.tsx` 改为导入它；`MarketFinancialChartsWorkbench.tsx` 用同一份 picks 对着 `sections` 解析出 chart key 集合，替换硬编码的 `DENSE_FIRST_SCREEN_CHART_KEYS`。以后加减一张首屏图只改一处。
2. 默认展开组：`expandedKeys` 初值改为「第一个至少含一张非指路卡图的分组」（按当前数据是 `cross`），而不是固定 `SECTION_KEYS[0]`。`shouldReferenceFirstScreenChart` 的单期限例外（`:31-40`）保留。

**验收**：`MarketFinancialChartsWorkbench.test.tsx:306` 用例「expands only the first chart group…」改为断言默认展开组含真画布；新增用例：任一 `DENSE_FIRST_SCREEN_CHART_PICKS` 命中的 chart 在 03 区渲染为 `module-home-market-chart-ref-*` 而非 `module-home-market-chart-*`。`.tmp-agent/market-overview-audit/audit2.mjs` 复跑：`chartRender.beforeExpand > 0`，`duplicateHeadings` 里不再有两张真画布同名（允许「实图 + 指路卡」同名）。smoke 的 `denseCharts toHaveCount(6)` 不变。

### D5 · F5 「重点」模式下 6 个收起/展开按钮全部失效

**根因**：`MarketFinancialChartsWorkbench.tsx:429 isExpanded = viewMode === "focus" || expandedKeys.has(key)`，focus 下恒 true；按钮（`:467-476`）仍渲染、仍改 state，但没有任何可观察效果（`audit2.mjs`：点击前后高度 332.78 px 不变，标签一直「收起」）。

**修法**：focus 模式下不渲染折叠按钮（`viewMode === "overview" ? <button…/> : null`），或渲染为 `disabled` + `aria-disabled` 并把 title 写成「重点模式下分组始终展开」。倾向前者（少一个死控件）。

**验收**：`MarketFinancialChartsWorkbench.test.tsx:231` 用例「uses overview and focus button semantics…」补断言：切到 focus 后 `module-home-market-section-toggle-*` 数量为 0（或全部 `disabled`）；切回 overview 后恢复。`audit2.mjs` 的 `chartsSection.focus.toggleLabels` 为空数组。

## 文件所有权

可改：`MarketOverviewDenseFirstScreen.tsx`、`marketOverviewDenseModel.ts`、`MarketFinancialChartsWorkbench.tsx`、`marketFinancialChartsModel.ts`（仅新增导出）及四者的 `.test.*`；`frontend/src/test/ModuleWorkbenchHomePage.test.tsx` 中断言 hero 文案的用例。

不得触碰：`useMarketHomeQueries.ts`（WP-B）；`moduleHomeModel.ts`（D1 走 hero 侧，不改 briefings——若你判断必须改 `:3216-3225`，先停下在报告里说明，不要顺手改）；`marketHomeNocturne.module.css` 等样式（不涉及）；`MarketBackendDataWorkbench.tsx`；`DESIGN.md` 决议（利率格 tone 语义不动，F24 不在本包）。

## 验证

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench \
  marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel \
  MarketOverviewDenseFirstScreen LiveRouteReadiness
npx playwright test tests/playwright/market-overview-smoke.spec.mjs -c playwright.config.mjs
```

再从 `frontend/` 复跑 `.tmp-agent/market-overview-audit/audit2.mjs` 与 `audit3.mjs`（复制到 `frontend/.tmp-audit/` 下执行），对照上面每条的验收字段。截图 `shots/mo-1920.png` 重拍一张放进报告。

## 报告要求

按 D1–D5 逐条给：根因、改动文件、验证结果、剩余风险。整体风险至少写：这是过渡期修法，WP-H 切到 `market.snapshot` 时 D1/D2/D3 的前端派生逻辑会被整体删除，D4/D5 保留。对 `core_finance/` 的影响：无。
