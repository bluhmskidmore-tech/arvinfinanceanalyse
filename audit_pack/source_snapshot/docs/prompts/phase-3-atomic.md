# Phase 3: 债券分析页重构 — 原子任务

> 目标文件: `frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx`
> 子组件目录: `frontend/src/features/bond-analytics/components/` (21 个文件)
> Mockup: `.omx/mockups/bond_analysis_hd.png`

## 已有资产

- ✅ `BondAnalyticsViewContent.tsx` — 主编排组件，含 dates/filter/tab/refresh 逻辑
- ✅ `BondKpiRow.tsx` — 债券 KPI 行
- ✅ `BondAnalyticsHeadlineZone.tsx` — 标题区
- ✅ `BondAnalyticsMarketContextStrip.tsx` — 市场上下文条
- ✅ `BondAnalyticsFilterActionStrip.tsx` — 筛选与操作栏
- ✅ `BondAnalyticsInstitutionalCockpit.tsx` — 机构驾驶舱
- ✅ `BondAnalyticsOverviewPanels.tsx` — 概览面板
- ✅ `BondAnalyticsDetailSection.tsx` — 明细区
- ✅ `CreditSpreadView.tsx` — 信用利差
- ✅ `ReturnDecompositionView.tsx` — 收益拆解
- ✅ `KRDCurveRiskView.tsx` — KRD 曲线风险
- ✅ `PortfolioHeadlinesView.tsx` — 组合头条
- ✅ `TopHoldingsView.tsx` — 重仓明细
- ✅ `AccountingClassAuditView.tsx` — 会计分类审计
- ✅ `BenchmarkExcessView.tsx` — 基准超额
- ✅ `ActionAttributionView.tsx` — 行为归因
- ✅ `BondAnalyticsDecisionRail.tsx` — 决策轨
- ✅ `BondAnalyticsReadinessMatrix.tsx` — 就绪矩阵
- ✅ `BondAnalyticsFuturePanel.tsx` — 未来面板
- ✅ `BondAnalyticsOverviewWatchlistCard.tsx` — 观察名单

**现状**: 债券分析页已经是组件化最好的页面，有 21 个子组件。主要问题是部分模块处于 `placeholder-blocked` 就绪态，以及与 mockup 布局不完全匹配。

## 核心差距

1. 已有 21 个组件但缺少 mockup 中的**组合摘要叙述**区域
2. 缺少 mockup 中的**债券资产结构饼图**
3. **收益率与久期分布图**可能未单独呈现
4. 缺少**组合表现对比（年初至今）**表格
5. 缺少**风险趋势（近12周）**折线图
6. 缺少**关键事件与日历**区域
7. 候选动作/决策事项的呈现需要对照 mockup 调整

---

## 任务 3-1: 新增组合摘要组件

**新建文件**: `frontend/src/features/bond-analytics/components/PortfolioSummaryNarrative.tsx`

**内容**: `SummaryBlock` 组件包装:
- 标题: "组合摘要"
- 正文: mock 文本 "当前组合呈现'久期偏高、信用以高等级为主、浮盈较厚'的特征..."
- Tags: `久期:偏高`, `信用:以高等级为主`, `策略:票息>波段`

**在 `BondAnalyticsInstitutionalCockpit.tsx` 或 `BondAnalyticsOverviewPanels.tsx` 中** 找到概览区域，在 KPI 行下方插入此组件。

**验证**: typecheck

---

## 任务 3-2: 新增资产结构饼图

**新建文件**: `frontend/src/features/bond-analytics/components/AssetStructurePie.tsx`

**内容**: ECharts 饼图，mock 数据:
- 政策性金融债 35.2%
- 地方政府债 22.3%
- 同业存单 17.9%
- 信用债-企业 14.1%
- 金融债 3.5%
- 其他 7.0%

**在概览区域**插入，与组合摘要同行。

**验证**: typecheck + 浏览器可见饼图

---

## 任务 3-3: 新增组合表现对比表格

**新建文件**: `frontend/src/features/bond-analytics/components/PerformanceComparison.tsx`

**内容**: SectionCard + 简单表格（antd Table 或 inline table），mock 数据:

| 组合名称 | 规模(亿) | 收益率% | 初额较bp | 久期(年) | 最大回撤% |
|---------|---------|---------|---------|---------|----------|
| 利率债组合 | 1,256.34 | 1.85 | +23 | 4.12 | -1.32 |
| 信用债组合 | 1,152.76 | 2.65 | +45 | 2.87 | -0.85 |
| 同业存单组合 | 589.36 | 1.72 | +15 | 0.08 | -0.02 |
| 地方债组合 | 403.21 | 2.12 | +32 | 3.15 | -1.05 |
| 高等级组合 | 1,842.13 | 2.05 | +28 | 2.95 | -0.75 |
| 合计/加权 | 3,287.09 | 2.18 | +28 | 2.94 | -0.82 |

**验证**: typecheck

---

## 任务 3-4: 新增风险趋势折线图

**新建文件**: `frontend/src/features/bond-analytics/components/RiskTrendChart.tsx`

**内容**: ECharts 折线图，X 轴 12 周，双 Y 轴:
- 净敞口(亿) — 柱状
- 负债比(%) — 折线
- 对手方集中度(%) — 折线
- 全部 mock 数据

**验证**: typecheck + 浏览器可见

---

## 任务 3-5: 新增关键事件日历

**新建文件**: `frontend/src/features/bond-analytics/components/BondEventCalendar.tsx`

**内容**: CalendarList 组件，mock 数据:
- 03-05 政策性金融债招标 ｜ 提配 420 亿 ｜ 高
- 03-08 同业存单到期集中 ｜ 提配 256 亿 ｜ 中
- 03-10 美国非农与美债拍卖 ｜ 海外扰动 ｜ 高
- 03-12 CPI 数据公布 ｜ 通胀观察 ｜ 中
- 03-15 2 只信用债评级调整 ｜ 信用事件 ｜ 高

**验证**: typecheck

---

## 任务 3-6: 在主编排文件中整合新组件

**改什么**: `BondAnalyticsViewContent.tsx` 或 `BondAnalyticsInstitutionalCockpit.tsx`

**操作**: 在现有概览区域的合适位置，lazy import 并插入:
1. `PortfolioSummaryNarrative` — KPI 下方
2. `AssetStructurePie` — 与摘要同行
3. `PerformanceComparison` — 明细区上方
4. `RiskTrendChart` — 页面底部
5. `BondEventCalendar` — 页面底部，与风险趋势同行

每个都用 `<SectionCard>` 包裹。

**验证**: `cd frontend && npm run lint && npm run typecheck && npm run build`

---

## 执行顺序

```
3-1 → 3-2 → 3-3 → 3-4 → 3-5 → 3-6 (整合)
```

## 禁止事项

- ❌ 不要重写现有 21 个子组件
- ❌ 不要改变模块注册表机制 (`bondAnalyticsModuleRegistry`)
- ❌ 不要改变就绪态逻辑
- ❌ 不要删除现有 tab 切换结构
