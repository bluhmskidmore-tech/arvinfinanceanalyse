# V1 BondAnalytics 单页 → V3 债券驾驶舱 / 债券分析 对齐矩阵（Delta）

对照源：V1 `pages/BondAnalytics.tsx`（日常/月度双 Tab 巨型单页）及 V1 `features/bond-analytics/components/*View.tsx`（收益拆解、基准超额、动作归因、KRD、信用利差、会计审计等）。

## 模块对照表

| V1 模块 | V3 已实现位置 | V3 client 方法 | 实施决定 | 目标 V3 文件 |
|---|---|---|---|---|
| 日常分析：人民币/美元总市值、平均票息、平均估值净价等 KPI 四卡 + 汇率脚注 | `bond-dashboard`：`HeadlineKpis`（Numeric 口径 KPI 条，指标集合与 V1 卡片不完全一一对应） | `getBondDashboardHeadlineKpis` | 🔁 增强（文案/脚注与 V1 口径差异在后续迭代对齐） | `frontend/src/features/bond-dashboard/components/HeadlineKpis.tsx` |
| 授信客户集中度 Top10 条形图 + CR10 侧卡 | 无等价独立 widget；`RiskTrendChart` 等为示意/占位非 V1 数据源 | 无 `analytics/bonds` 或 `analysis/assets/counterparty` 封装；`getPositionsCounterpartyBonds` 为持仓维度非 V1 同口径 | ⏭️ 跳过 | — |
| 按资产分类（Top10）柱状图 | `AssetStructurePie` + `groupBy=bond_type` 等（饼/环图为主，非同款纵向柱图） | `getBondDashboardAssetStructure` | 🔁 增强（图表形态差异；数据维度可对齐） | `frontend/src/features/bond-dashboard/components/AssetStructurePie.tsx` |
| 结构占比饼图 + 亿元明细表 | `AssetStructurePie` 内饼图 + 中心合计 | 同上 | ✅ 已实现 | 同上 |
| 按部门/子类（Top10）柱状图 | `AssetStructurePie` 切换维度（券种/组合等），无独立「子类」柱图 | `getBondDashboardAssetStructure` | 🔁 增强（需产品确认 groupBy 与 V1 `by_sub_type` 映射） | 同上 |
| 到期剩余期限分桶（市值） | `MaturityStructureChart` | `getBondDashboardMaturityStructure` | ✅ 已实现 | `frontend/src/features/bond-dashboard/components/MaturityStructureChart.tsx` |
| 收益率/期限桶分布（柱状） | `YieldDistributionBar`（收益率 Tab + 期限 Tab） | `getBondDashboardYieldDistribution` + `getBondDashboardAssetStructure(..., tenor_bucket)` | ✅ 已实现 | `frontend/src/features/bond-dashboard/components/YieldDistributionBar.tsx` |
| 现金流/久期/利率风险桶（亿元，`/api/risk/buckets`） | 无同款三柱图组合 | 无 `getRiskBuckets` 等封装 | ⏭️ 跳过 | — |
| TopN 重仓表（可选 10–100） | `TopHoldingsView`（原默认 20，可扩展交互） | `getBondAnalyticsTopHoldings` | 🔁 增强 | `frontend/src/features/bond-analytics/components/TopHoldingsView.tsx` |
| 业务种类加权利率与加权久期表 | `IndustryTable` 为行业分布，非业务种类 YTM/久期矩阵 | `getBondDashboardIndustryDistribution` | ⏭️ 跳过（缺 `business_type_metrics` 端点） | — |
| 信用等级分布块 | `CreditRatingBlocks` | `getBondDashboardAssetStructure(..., rating)` | ✅ 已实现 | `frontend/src/features/bond-dashboard/components/CreditRatingBlocks.tsx` |
| 组合对比、利差、风险指标列表 | `PortfolioTable` / `SpreadTable` / `RiskIndicatorsPanel` | `getBondDashboardPortfolioComparison` / `getBondDashboardSpreadAnalysis` / `getBondDashboardRiskIndicators` | ✅ 已实现 | 对应 `bond-dashboard/components/*.tsx` |
| 行业分布表 | `IndustryTable` | `getBondDashboardIndustryDistribution` | ✅ 已实现 | `frontend/src/features/bond-dashboard/components/IndustryTable.tsx` |
| 月度统计（年/月选择、月日均全套图） | 无等价页面 | 无 `bonds/monthly` | ⏭️ 跳过 | — |
| 估值净价分布（V1 类型存在、页面未挂载） | — | — | ⏭️ 跳过 | — |
| 收益拆解 | `ReturnDecompositionView` + 分析详情区 | `getBondAnalyticsReturnDecomposition` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/ReturnDecompositionView.tsx` |
| 基准超额 | `BenchmarkExcessView` | `getBondAnalyticsBenchmarkExcess` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/BenchmarkExcessView.tsx` |
| 曲线/KRD 风险 | `KRDCurveRiskView` | `getBondAnalyticsKrdCurveRisk` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/KRDCurveRiskView.tsx` |
| 信用利差迁移 | `CreditSpreadView` | `getBondAnalyticsCreditSpreadMigration` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx` |
| 持仓动作归因 | `ActionAttributionView` | `getBondAnalyticsActionAttribution` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/ActionAttributionView.tsx` |
| 会计分类审计 | `AccountingClassAuditView` | `getBondAnalyticsAccountingClassAudit` | ✅ 已实现 | `frontend/src/features/bond-analytics/components/AccountingClassAuditView.tsx` |
| 组合 Headline / 驾驶舱首屏 | `PortfolioHeadlinesView`、`BondAnalyticsOverviewPanels` 等 | `getBondAnalyticsPortfolioHeadlines` 等 | ✅ 已实现 | `frontend/src/features/bond-analytics/components/` |

## 统计摘要

- V1 可识别主模块：**20** 行（上表）
- ✅ 已在 V3 落地：**11**
- 🔁 需增强或形态差异：**4**
- ⏭️ 缺端点或不在当前 client：**5**

## 本迭代实施边界

在不修改 `client.ts` / `contracts.ts` 前提下，优先完成 **Top 持仓 TopN 选择** 与 **驾驶舱关键卡片 `data-testid`**，便于 E2E 与后续接线。
