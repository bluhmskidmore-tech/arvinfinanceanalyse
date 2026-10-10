# 市场总览 v1.4 实施与复核

2026-09-09：已拆分布局、图表与情景、风险详情、浏览器验收四个子代理实施，由主代理整合并复核。最新生产构建已在 http://localhost:5888/market-overview 验证。功能验收通过，尚未达到像素完全一致。

此前的主要问题是首页信息分布与已批准设计不一致：风险、宏观与事件被折叠，图表缺少明确主次，页壳又重复渲染行情与导航。本次把市场摘要、曲线与影响、资金与跨资产、风险、宏观事件、组合状态依次常显；详细来源与原有专题继续保留在下钻入口。

## 实施文件

- `frontend/src/features/workbench/module-home/MarketHomeLayout.tsx`：章节导航、市场功能、跨页返回状态。
- `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.tsx`：首页排列、行情、宏观与事件摘要。
- `frontend/src/features/workbench/module-home/MarketFundingRatesObservations.tsx`：资金与关键利率切换、曲线与证据。
- `frontend/src/features/workbench/module-home/MarketPortfolioScenarioPanel.tsx`：首页情景状态与惰性风险读取。
- `frontend/src/features/workbench/module-home/MarketRiskObservation.tsx`：当前评分、历史、信号、事项及四类依据抽屉。
- `frontend/src/features/workbench/module-home/marketRiskObservationModel.ts`：发布资格与历史图展示。
- `frontend/src/features/workbench/module-home/marketSourceContext.ts`、`MarketSourceContextBanner.tsx`：来源参数与返回链接。
- `frontend/src/layouts/WorkbenchShell.tsx`、`frontend/src/styles/marketOverviewShell.css`：仅市场页的 176/64 像素侧栏及移动导航。
- `frontend/src/features/news-events/NewsEventsPage.tsx`、`frontend/src/features/macro-observation/pages/MacroObservationPage.tsx`：来源提示、新闻精确范围与返回入口。

各组件局部 CSS、针对性测试及本地授权字体随实现加入。工作区原有其他未提交改动未回退；本轮未修改后端计算、刷新作业、权限或数据库。

## 正确性与回归

主代理复核后修正了平板侧栏不可见、手机重复行情栏、关键利率专题锚点失效、嵌套抽屉 Escape、未知组成项被误标百分比、缺少路由上下文的测试，以及重复 React key。当前 Crisis 发布资格由 snapshot 决定，历史和完整分析不会回填当前值；商品影子结果和审批材料仅作研究展示。组合 +10bp 仍保留日期、权限、监管 DV01 和覆盖校验。

10 个定向 Vitest 文件共 160 项通过；最后 React key 修正后 Dense 的 30 项再次通过。`npm run typecheck`、`npm run lint`、`npm run build`、`npm run build:fast`、`npm run debt:audit` 六项审计及限定文件 `git diff --check` 均通过。最终改动还进行了定向 ESLint。

生产服务 5888 上 `npx playwright test tests/playwright/market-overview-figma.spec.mjs --workers=1` 四项通过。覆盖 1440/1024/390 宽度、风险屏蔽、60 期历史、按需读取、商品只读材料、键盘与焦点、12 项原图入口、全部行情和真实接口的宏观来源返回。合成样本只在测试拦截器内使用。

## 视觉证据与剩余差异

| 宽度 | Figma 全页高度 | 实现全页高度 |
|---|---:|---:|
| 1440 | 2783 | 2821 |
| 1024 | 2981 | 3029 |
| 390 | 5036 | 5262 |

截图在 `output/design/market-overview-figma-v1/implementation/browser-{width}-loaded.png`；浏览器报告为同目录 `browser-qa-v1.4.json`。高度差与截图只能证明布局接近，不能代替逐像素相等断言。

PENDING：中证全债尚无已核验真实序列映射；快照未独立提供部分宏观指标期、发布日期和新闻事件时间、来源。已有字段按真实接口展示，缺失处保留说明；不使用 Figma 样本填补。新闻收到的精确专题及接收时间范围会进入查询，非法范围阻止查询，宏观来源日期不会被解释为历史回放。以上数据缺口需在既有数据契约下补齐。
